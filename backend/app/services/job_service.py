from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from app.core.redis import get_json, set_json


@dataclass
class Job:
    job_id: str
    owner_id: int
    status: str = "PENDING"
    result: Any = None
    error: str | None = None


_jobs: dict[str, Job] = {}
_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=2)
JOB_TTL_SECONDS = 86_400


def _key(job_id: str) -> str:
    return f"job:{job_id}"


def _save(job: Job) -> None:
    result = job.result.model_dump(mode="json") if hasattr(job.result, "model_dump") else job.result
    set_json(_key(job.job_id), {"job_id": job.job_id, "owner_id": job.owner_id, "status": job.status, "result": result, "error": job.error}, ttl_seconds=JOB_TTL_SECONDS)


def submit(function: Callable[[], Any], owner_id: int) -> Job:
    job = Job(job_id=uuid4().hex, owner_id=owner_id)
    with _lock:
        _jobs[job.job_id] = job
    _save(job)

    def run() -> None:
        job.status = "PROCESSING"
        _save(job)
        try:
            job.result = function()
            job.status = "COMPLETED"
        except Exception as exc:
            job.error = "The background operation could not be completed."
            job.status = "FAILED"
        _save(job)

    _executor.submit(run)
    return job


def get(job_id: str, owner_id: int) -> Job | None:
    with _lock:
        job = _jobs.get(job_id)
    if job is None:
        payload = get_json(_key(job_id))
        if not payload:
            return None
        job = Job(**payload)
    return job if job.owner_id == owner_id else None
