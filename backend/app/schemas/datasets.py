from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    column_name: str
    data_type: str
    nullable: bool
    unique_count: int
    missing_count: int


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    original_filename: str
    row_count: int
    column_count: int
    file_size: int
    source_preparation_id: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    columns: list[DatasetColumnResponse] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]
    total: int


class DatasetPreviewResponse(BaseModel):
    dataset_id: int
    columns: list[str]
    rows: list[dict[str, str | None]]
    total_rows: int
    returned_rows: int
