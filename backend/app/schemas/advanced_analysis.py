from typing import Any, Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    date_column: str
    target_column: str
    periods: int = Field(default=6, ge=1, le=52)


class ForecastResponse(BaseModel):
    dataset_id: int
    date_column: str
    target_column: str
    historical: list[dict[str, Any]]
    forecast: list[dict[str, Any]]
    model: str
    frequency: str
    observations: int


class RootCauseRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    metric_column: str | None = None
    dimension_columns: list[str] = Field(default_factory=list, max_length=10)


class RootCauseResponse(BaseModel):
    dataset_id: int
    question: str
    observed_result: str
    associations: list[dict[str, Any]]
    caveat: str
    sql: str | None = None
