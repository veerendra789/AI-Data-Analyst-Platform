from __future__ import annotations

from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.datasets import get_accessible_dataset
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.limits import rate_limit
from app.core.redis import get_json, make_cache_key, normalize_text, set_json
from app.models import AnalysisResult, ChatMessage, Dataset, MessageRole, Query, User
from app.schemas.analysis import AnalysisHistoryItem, AnalysisQueryRequest, AnalysisQueryResponse, ChartConfiguration
from app.schemas.profiling import AnomalyRequest, AnomalyResponse, DatasetProfileResponse
from app.schemas.advanced_analysis import ForecastRequest, ForecastResponse, RootCauseRequest, RootCauseResponse
from app.services.duckdb_service import DataQueryService
from app.services import llm_provider
from app.services.llm_provider import GeneratedAnalysis
from app.services.profiling_service import ProfilingError, detect_anomalies, profile_file
from app.services.advanced_analysis_service import forecast_file, root_cause_file
from app.services.sql_validator import SqlValidationError, validate_read_only_sql


router = APIRouter(prefix="/api/analysis", tags=["Analysis"])
query_service = DataQueryService()


def chart_for(result: GeneratedAnalysis, columns: list[str], rows: list[dict[str, Any]]) -> ChartConfiguration:
    chart_type = result.chart_type if result.chart_type in {"bar", "line", "pie", "area", "scatter", "table"} else "table"
    if chart_type == "table":
        return ChartConfiguration(type="table")
    x_axis = next((column for column in columns if rows and isinstance(rows[0].get(column), str)), columns[0] if columns else None)
    y_axis = next((column for column in columns if rows and isinstance(rows[0].get(column), (int, float))), columns[1] if len(columns) > 1 else None)
    if not x_axis or not y_axis:
        return ChartConfiguration(type="table")
    return ChartConfiguration(type=chart_type, x_axis=x_axis, y_axis=y_axis)


def schema_for(dataset: Dataset) -> list[dict[str, Any]]:
    return [
        {"column_name": column.column_name, "data_type": column.data_type, "nullable": column.nullable}
        for column in dataset.columns
    ]


@router.post("/query", response_model=AnalysisQueryResponse)
def analyze_query(
    request: AnalysisQueryRequest,
    current_user: User = Depends(rate_limit("analysis", 30)),
    db: Session = Depends(get_db),
) -> AnalysisQueryResponse:
    dataset = get_accessible_dataset(request.dataset_id, current_user, db)
    cache_key = make_cache_key("analysis", current_user.id, dataset.id, normalize_text(request.question))
    cached = get_json(cache_key)
    if cached:
        return AnalysisQueryResponse.model_validate(cached)
    schema = schema_for(dataset)
    query_record = Query(
        user_id=current_user.id,
        dataset_id=dataset.id,
        question=request.question,
        status="PROCESSING",
    )
    db.add(query_record)
    db.commit()
    db.refresh(query_record)

    try:
        provider = llm_provider.get_provider()
        generated = provider.generate_sql(request.question, schema)
        validated_sql = validate_read_only_sql(generated.sql)
        started_at = perf_counter()
        columns, rows = query_service.execute(dataset.file_path, validated_sql)
        rows = jsonable_encoder(rows)
        execution_time_ms = round((perf_counter() - started_at) * 1000)
        insight = provider.explain(request.question, validated_sql, columns, rows)
        query_record.generated_sql = validated_sql
        query_record.execution_time = execution_time_ms / 1000
        query_record.status = "COMPLETED"
        result_payload = {
            "question": request.question,
            "sql": validated_sql,
            "columns": columns,
            "rows": rows,
            "chart": chart_for(generated, columns, rows).model_dump(),
            "insight": insight,
            "execution_time_ms": execution_time_ms,
        }
        db.add_all(
            [
                AnalysisResult(query_id=query_record.id, dataset_id=dataset.id, analysis_type="QUERY", result_json=result_payload),
                ChatMessage(user_id=current_user.id, dataset_id=dataset.id, role=MessageRole.USER, content=request.question),
                ChatMessage(user_id=current_user.id, dataset_id=dataset.id, role=MessageRole.ASSISTANT, content=insight),
            ]
        )
        db.commit()
        response = AnalysisQueryResponse(
            question=request.question,
            sql=validated_sql,
            columns=columns,
            rows=rows,
            chart=chart_for(generated, columns, rows),
            insight=insight,
            execution_time_ms=execution_time_ms,
        )
        set_json(cache_key, response.model_dump(), ttl_seconds=300)
        return response
    except (SqlValidationError, ValidationError) as exc:
        query_record.status = "REJECTED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"The generated query was rejected: {exc}") from exc
    except (RuntimeError, ValueError) as exc:
        query_record.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Analysis could not be completed: {exc}") from exc
    except Exception as exc:
        query_record.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=500, detail="Analysis could not be completed.") from exc


@router.get("/history/{dataset_id}", response_model=list[AnalysisHistoryItem])
def analysis_history(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AnalysisHistoryItem]:
    get_accessible_dataset(dataset_id, current_user, db)
    queries = db.scalars(
        select(Query).where(Query.dataset_id == dataset_id, Query.user_id == current_user.id).order_by(Query.created_at.asc())
    ).all()
    history = []
    for query in queries:
        result = db.scalar(select(AnalysisResult).where(AnalysisResult.query_id == query.id))
        payload = result.result_json if result and query.status == "COMPLETED" else {}
        history.append(
            AnalysisHistoryItem(
                query_id=query.id,
                question=query.question,
                sql=query.generated_sql,
                columns=payload.get("columns", []),
                rows=payload.get("rows", []),
                insight=payload.get("insight"),
                status=query.status,
                created_at=query.created_at.isoformat(),
            )
        )
    return history


@router.post("/eda/{dataset_id}", response_model=DatasetProfileResponse)
def exploratory_data_analysis(
    dataset_id: int,
    current_user: User = Depends(rate_limit("eda", 10)),
    db: Session = Depends(get_db),
) -> DatasetProfileResponse:
    dataset = get_accessible_dataset(dataset_id, current_user, db)
    cache_key = make_cache_key("eda", current_user.id, dataset_id, dataset.file_path)
    cached = get_json(cache_key)
    if cached:
        return DatasetProfileResponse.model_validate(cached)
    try:
        profile = profile_file(dataset.file_path)
    except ProfilingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = DatasetProfileResponse(dataset_id=dataset_id, **profile)
    set_json(cache_key, response.model_dump(), ttl_seconds=900)
    return response


@router.post("/anomalies/{dataset_id}", response_model=AnomalyResponse)
def find_anomalies(
    dataset_id: int,
    request: AnomalyRequest,
    current_user: User = Depends(rate_limit("anomalies", 10)),
    db: Session = Depends(get_db),
) -> AnomalyResponse:
    dataset = get_accessible_dataset(dataset_id, current_user, db)
    cache_key = make_cache_key("anomalies", current_user.id, dataset_id, dataset.file_path, request.column, request.contamination)
    cached = get_json(cache_key)
    if cached:
        return AnomalyResponse.model_validate(cached)
    try:
        anomalies = detect_anomalies(dataset.file_path, request.column, request.contamination)
    except ProfilingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = AnomalyResponse(dataset_id=dataset_id, **anomalies)
    set_json(cache_key, response.model_dump(), ttl_seconds=900)
    return response


@router.post("/forecast/{dataset_id}", response_model=ForecastResponse)
def forecast_dataset(
    dataset_id: int,
    request: ForecastRequest,
    current_user: User = Depends(rate_limit("forecast", 10)),
    db: Session = Depends(get_db),
) -> ForecastResponse:
    dataset = get_accessible_dataset(dataset_id, current_user, db)
    cache_key = make_cache_key("forecast", current_user.id, dataset_id, dataset.file_path, request.date_column, request.target_column, request.periods)
    cached = get_json(cache_key)
    if cached:
        return ForecastResponse.model_validate(cached)
    try:
        result = forecast_file(dataset.file_path, request.date_column, request.target_column, request.periods)
    except ProfilingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = ForecastResponse(dataset_id=dataset_id, **result)
    set_json(cache_key, response.model_dump(), ttl_seconds=900)
    return response


@router.post("/root-cause/{dataset_id}", response_model=RootCauseResponse)
def root_cause_analysis(
    dataset_id: int,
    request: RootCauseRequest,
    current_user: User = Depends(rate_limit("root-cause", 10)),
    db: Session = Depends(get_db),
) -> RootCauseResponse:
    dataset = get_accessible_dataset(dataset_id, current_user, db)
    try:
        result = root_cause_file(dataset.file_path, request.question, request.metric_column, request.dimension_columns)
    except ProfilingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RootCauseResponse(dataset_id=dataset_id, **result)
