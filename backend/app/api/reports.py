from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.datasets import get_accessible_dataset
from app.api.deps import get_current_user
from app.core.limits import rate_limit
from app.schemas.reports import JobResponse, ReportGenerateRequest, ReportResponse
from app.services.job_service import get as get_job
from app.services.job_service import submit
from app.services.report_service import build_report
from app.services.supabase_repository import (
    create_report,
    get_report as load_report,
    latest_analysis_results,
    list_reports as load_reports,
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def report_for(report: Report) -> ReportResponse:
    return ReportResponse.model_validate(report)


def generate_report(dataset: object, user: object, title: str) -> object:
    result_payloads = latest_analysis_results(user.uid, dataset.id)
    content = build_report(dataset, title, result_payloads)
    return create_report(user.uid, dataset.id, title, content)


@router.post("/generate", response_model=ReportResponse)
def generate(
    request: ReportGenerateRequest,
    current_user: object = Depends(rate_limit("reports", 10)),
) -> object:
    dataset = get_accessible_dataset(request.dataset_id, current_user)
    try:
        return generate_report(dataset, current_user, request.title)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The report could not be generated.") from exc


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_job(
    request: ReportGenerateRequest,
    current_user: object = Depends(rate_limit("reports", 10)),
) -> JobResponse:
    dataset = get_accessible_dataset(request.dataset_id, current_user)

    def work() -> ReportResponse:
        return report_for(generate_report(dataset, current_user, request.title))

    job = submit(work, current_user.uid)
    return JobResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def job_status(job_id: str, current_user: object = Depends(get_current_user)) -> JobResponse:
    job = get_job(job_id, current_user.uid)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found.")
    result = job.result if isinstance(job.result, ReportResponse) else ReportResponse.model_validate(job.result) if isinstance(job.result, dict) else None
    return JobResponse(job_id=job.job_id, status=job.status, result=result, error=job.error)


@router.get("", response_model=list[ReportResponse])
def list_reports(
    offset: int = 0,
    limit: int = 20,
    current_user: object = Depends(get_current_user),
) -> list[object]:
    limit = min(max(limit, 1), 100)
    return load_reports(current_user.uid, max(offset, 0), limit)


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, current_user: object = Depends(get_current_user)) -> object:
    report = load_report(report_id, current_user.uid)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report
