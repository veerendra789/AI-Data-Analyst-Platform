from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalysisQueryRequest(BaseModel):
    dataset_id: int
    question: str = Field(min_length=3, max_length=1000)


class ChartConfiguration(BaseModel):
    type: Literal["bar", "line", "pie", "area", "scatter", "table"]
    x_axis: str | None = None
    y_axis: str | None = None


class AnalysisQueryResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    chart: ChartConfiguration
    insight: str
    execution_time_ms: int


class ChatHistoryMessage(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class AnalysisHistoryItem(BaseModel):
    query_id: int
    question: str
    sql: str | None
    columns: list[str]
    rows: list[dict[str, Any]]
    insight: str | None
    status: str
    created_at: str
