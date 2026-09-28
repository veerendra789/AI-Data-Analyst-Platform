from typing import Any

from pydantic import BaseModel


class ProfileColumn(BaseModel):
    name: str
    data_type: str
    nullable: bool
    unique_count: int
    missing_count: int
    missing_percentage: float


class ProfileSummary(BaseModel):
    row_count: int
    column_count: int
    duplicate_rows: int
    missing_values: int
    missing_percentage: float
    numeric_columns: list[str]
    categorical_columns: list[str]
    date_columns: list[str]


class DatasetProfileResponse(BaseModel):
    dataset_id: int
    summary: ProfileSummary
    columns: list[ProfileColumn]
    numeric_statistics: dict[str, dict[str, float | None]]
    categorical_summaries: dict[str, dict[str, Any]]
    correlations: dict[str, dict[str, float | None]]
    distributions: dict[str, list[dict[str, float | int]]]
    outliers: dict[str, dict[str, float | int | None]]


class AnomalyRequest(BaseModel):
    column: str
    contamination: float = 0.05


class AnomalyResponse(BaseModel):
    dataset_id: int
    column: str
    number_of_anomalies: int
    anomaly_records: list[dict[str, Any]]
    relevant_columns: list[str]
    model: str
