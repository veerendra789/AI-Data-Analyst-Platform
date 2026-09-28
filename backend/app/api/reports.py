from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.datasets import get_accessible_dataset
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.limits import rate_limit
from app.models import AnalysisResult, Dataset, Query, Report, User
from app.schemas.reports import JobResponse, ReportGenerateRequest, ReportResponse
from app.services.job_service import get as get_job
from app.services.job_service import submit
from app.services.report_service import build_report

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def report_for(report: Report) -> ReportResponse:
    return ReportResponse.model_validate(report)


def generate_report(dataset: Dataset, user: User, title: str, db: Session) -> Report:
    results = db.scalars(
        select(AnalysisResult).join(Query, AnalysisResult.query_id == Query.id, isouter=True)
        .where(AnalysisResult.dataset_id == dataset.id, Query.user_id == user.id)
        .order_by(AnalysisResult.created_at.desc()).limit(20)
    ).all()
    result_payloads = [result.result_json for result in results]
    report = Report(user_id=user.id, dataset_id=dataset.id, title=title, content=build_report(dataset, title, result_payloads))
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.post("/generate", response_model=ReportResponse)
def generate(
    request: ReportGenerateRequest,
    current_user: User = Depends(rate_limit("reports", 10)),
    db: Session = Depends(get_db),
) -> Report:
    dataset = get_accessible_dataset(request.dataset_id, current_user, db)
    try:
        return generate_report(dataset, current_user, request.title, db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="The report could not be generated.") from exc


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_job(
    request: ReportGenerateRequest,
    current_user: User = Depends(rate_limit("reports", 10)),
    db: Session = Depends(get_db),
) -> JobResponse:
    dataset = get_accessible_dataset(request.dataset_id, current_user, db)
    user_id = current_user.id
    dataset_id = dataset.id

    def work() -> ReportResponse:
        with Session(bind=db.get_bind()) as worker_db:
            worker_user = worker_db.get(User, user_id)
            worker_dataset = worker_db.get(Dataset, dataset_id)
            if worker_user is None or worker_dataset is None:
                raise ValueError("Report context is unavailable.")
            return report_for(generate_report(worker_dataset, worker_user, request.title, worker_db))

    job = submit(work, current_user.id)
    return JobResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def job_status(job_id: str, current_user: User = Depends(get_current_user)) -> JobResponse:
    job = get_job(job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found.")
    result = job.result if isinstance(job.result, ReportResponse) else ReportResponse.model_validate(job.result) if isinstance(job.result, dict) else None
    return JobResponse(job_id=job.job_id, status=job.status, result=result, error=job.error)


@router.get("", response_model=list[ReportResponse])
def list_reports(
    offset: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Report]:
    limit = min(max(limit, 1), 100)
    return list(db.scalars(select(Report).where(Report.user_id == current_user.id).order_by(Report.created_at.desc()).offset(max(offset, 0)).limit(limit)).all())


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Report:
    report = db.scalar(select(Report).where(Report.id == report_id, Report.user_id == current_user.id))
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report
