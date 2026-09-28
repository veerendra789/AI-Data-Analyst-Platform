from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportGenerateRequest(BaseModel):
    dataset_id: int
    title: str = Field(default="Analytical report", min_length=1, max_length=255)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    title: str
    content: str
    created_at: datetime


class JobResponse(BaseModel):
    job_id: str
    status: str
    result: ReportResponse | None = None
    error: str | None = None
