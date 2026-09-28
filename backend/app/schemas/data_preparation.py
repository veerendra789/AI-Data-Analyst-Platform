from typing import Literal

from pydantic import BaseModel, Field


class ColumnOverride(BaseModel):
    column_index: int = Field(ge=0)
    name: str | None = Field(default=None, max_length=255)
    data_type: Literal["string", "integer", "float", "boolean", "date", "datetime", "categorical"] | None = None
    date_format: Literal["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"] | None = None


class MissingStrategy(BaseModel):
    column_index: int = Field(ge=0)
    strategy: Literal["keep", "drop_rows", "mean", "median", "mode", "constant"]
    value: str | None = Field(default=None, max_length=500)


class ApplyPreparationRequest(BaseModel):
    selected_operation_ids: list[str] = Field(default_factory=list, max_length=1000)
    column_overrides: list[ColumnOverride] = Field(default_factory=list, max_length=500)
    missing_strategies: list[MissingStrategy] = Field(default_factory=list, max_length=500)
    category_mappings: dict[str, dict[str, str]] = Field(default_factory=dict)
    missing_markers: dict[str, list[str]] = Field(default_factory=dict)
    remove_duplicates: bool = False
    drop_column_indexes: list[int] = Field(default_factory=list, max_length=500)


class SavePreparationRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)