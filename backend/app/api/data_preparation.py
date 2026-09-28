from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import DataPreparationSession, Dataset, DatasetColumn, DatasetStatus, User
from app.schemas.data_preparation import ApplyPreparationRequest, SavePreparationRequest
from app.schemas.datasets import DatasetResponse
from app.services.data_preparation_service import (
    PreparationError,
    analyze_csv,
    apply_plan,
    preview_frame,
    write_clean_csv,
)
from app.services.dataset_service import CsvValidationError, parse_csv, settings, store_upload


router = APIRouter(prefix="/api/data-preparation", tags=["Data Preparation"])


def get_preparation(preparation_id: str, current_user: User, db: Session) -> DataPreparationSession:
    query = select(DataPreparationSession).where(DataPreparationSession.id == preparation_id)
    if current_user.role != "ADMIN":
        query = query.where(DataPreparationSession.user_id == current_user.id)
    preparation = db.scalar(query)
    if preparation is None:
        raise HTTPException(status_code=404, detail="Preparation session not found.")
    return preparation


def _payload(preparation: DataPreparationSession) -> dict:
    return {
        "id": preparation.id,
        "status": preparation.status,
        "filename": preparation.source_filename,
        "overview": preparation.metadata_json["overview"],
        "columns": preparation.metadata_json["columns"],
        "issues": preparation.metadata_json["issues"],
        "plan": preparation.plan_json,
        "comparison": preparation.metadata_json.get("comparison"),
        "history": preparation.history_json,
    }


@router.post("/analyze", status_code=status.HTTP_201_CREATED)
async def analyze_dataset(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    path, _ = await store_upload(file)
    filename = Path((file.filename or "dataset.csv").replace("\\", "/")).name[:255]
    try:
        metadata, plan = analyze_csv(path, filename)
    except PreparationError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The CSV could not be analyzed.") from None
    preparation = DataPreparationSession(
        id=str(uuid4()),
        user_id=current_user.id,
        source_filename=filename,
        source_path=str(path),
        metadata_json=metadata,
        plan_json=plan,
        history_json=[],
    )
    db.add(preparation)
    db.commit()
    return {**_payload(preparation), "preview": metadata["preview"]}


@router.get("/{preparation_id}")
def read_preparation(
    preparation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _payload(get_preparation(preparation_id, current_user, db))


@router.get("/{preparation_id}/preview")
def preview_preparation(
    preparation_id: str,
    version: str = "original",
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    preparation = get_preparation(preparation_id, current_user, db)
    bounded_limit = min(max(limit, 1), 100)
    if version == "original":
        metadata = preparation.metadata_json["preview"]
        return {**metadata, "rows": metadata["rows"][:bounded_limit]}
    if version != "cleaned" or not preparation.output_path or not Path(preparation.output_path).is_file():
        raise HTTPException(status_code=409, detail="A cleaned preview is not available yet.")
    import pandas as pd

    try:
        frame = pd.read_csv(preparation.output_path, nrows=bounded_limit)
        return {**preview_frame(frame, bounded_limit), "total_rows": preparation.metadata_json["comparison"]["final_row_count"]}
    except Exception:
        raise HTTPException(status_code=500, detail="The cleaned preview could not be read.") from None


@router.post("/{preparation_id}/preview")
def preview_proposed_changes(
    preparation_id: str,
    request: ApplyPreparationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    preparation = get_preparation(preparation_id, current_user, db)
    try:
        frame, comparison, _ = apply_plan(
            Path(preparation.source_path),
            preparation.metadata_json,
            preparation.plan_json,
            request.model_dump(),
        )
        return {"preview": preview_frame(frame), "comparison": comparison, "status": "PROPOSED"}
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="The source file for this preparation has expired.") from None
    except Exception:
        raise HTTPException(status_code=400, detail="The proposed transformations could not be previewed.") from None


@router.post("/{preparation_id}/apply")
def apply_preparation(
    preparation_id: str,
    request: ApplyPreparationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    preparation = get_preparation(preparation_id, current_user, db)
    existing_dataset = db.scalar(select(Dataset.id).where(Dataset.source_preparation_id == preparation.id))
    if existing_dataset is not None:
        raise HTTPException(status_code=409, detail="This preparation has already been saved. Start a new preparation to revise it.")
    try:
        frame, comparison, history = apply_plan(
            Path(preparation.source_path),
            preparation.metadata_json,
            preparation.plan_json,
            request.model_dump(),
        )
        output_path = Path(settings.upload_directory).resolve() / "prepared" / f"{preparation.id}.csv"
        write_clean_csv(frame, output_path)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="The source file for this preparation has expired.") from None
    except Exception:
        raise HTTPException(status_code=400, detail="The selected transformations could not be applied.") from None
    preparation.output_path = str(output_path)
    preparation.status = "APPLIED"
    preparation.metadata_json = {**preparation.metadata_json, "comparison": comparison}
    preparation.history_json = preparation.history_json + history
    db.commit()
    return {**_payload(preparation), "preview": preview_frame(frame)}


@router.post("/{preparation_id}/save", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def save_preparation(
    preparation_id: str,
    request: SavePreparationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dataset:
    preparation = get_preparation(preparation_id, current_user, db)
    if preparation.status != "APPLIED" or not preparation.output_path or not Path(preparation.output_path).is_file():
        raise HTTPException(status_code=409, detail="Apply transformations before saving the prepared dataset.")
    try:
        with Path(preparation.output_path).open("rb") as source:
            parsed = parse_csv(source)
    except (CsvValidationError, OSError):
        raise HTTPException(status_code=400, detail="The prepared CSV failed dataset validation.") from None
    existing = db.scalar(select(Dataset).options(selectinload(Dataset.columns)).where(Dataset.source_preparation_id == preparation.id))
    if existing is not None:
        return existing
    original_name = f"{Path(preparation.source_filename).stem}_cleaned.csv"[:255]
    dataset = Dataset(
        user_id=current_user.id,
        name=(request.name or Path(original_name).stem)[:255],
        original_filename=original_name,
        file_path=preparation.output_path,
        row_count=parsed.row_count,
        column_count=len(parsed.headers),
        file_size=Path(preparation.output_path).stat().st_size,
        status=DatasetStatus.COMPLETED,
        source_preparation_id=preparation.id,
        columns=[DatasetColumn(**column) for column in parsed.column_stats],
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("/{preparation_id}/download")
def download_preparation(
    preparation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    preparation = get_preparation(preparation_id, current_user, db)
    if not preparation.output_path or not Path(preparation.output_path).is_file():
        raise HTTPException(status_code=409, detail="Apply transformations before downloading the CSV.")
    filename = f"{Path(preparation.source_filename).stem}_cleaned.csv"
    return FileResponse(preparation.output_path, media_type="text/csv", filename=filename)


@router.delete("/{preparation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preparation(
    preparation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    preparation = get_preparation(preparation_id, current_user, db)
    source_path = Path(preparation.source_path)
    output_path = Path(preparation.output_path) if preparation.output_path else None
    db.delete(preparation)
    db.commit()
    source_path.unlink(missing_ok=True)
    if output_path and not db.scalar(select(Dataset.id).where(Dataset.file_path == str(output_path))):
        output_path.unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)