from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseSettings):
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_provider: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = ProviderSettings()


class GeneratedAnalysis(BaseModel):
    sql: str
    reasoning_summary: str = Field(default="")
    chart_type: str = "table"


class LLMProvider(Protocol):
    def generate_sql(self, question: str, schema: list[dict[str, Any]]) -> GeneratedAnalysis: ...
    def explain(self, question: str, sql: str, columns: list[str], rows: list[dict[str, Any]]) -> str: ...


class OpenAICompatibleProvider:
    def __init__(self, provider_settings: ProviderSettings):
        if not provider_settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required for the configured LLM provider.")
        self.settings = provider_settings

    def _complete(self, system: str, user: str) -> str:
        try:
            response = httpx.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                json={
                    "model": self.settings.llm_model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
                timeout=httpx.Timeout(45.0, connect=10.0),
            )
            response.raise_for_status()
            payload = response.json()
            content = payload.get("choices", [{}])[0].get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("The LLM returned an empty response.")
            return content
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            raise RuntimeError("The configured LLM provider did not return a valid response.") from exc

    def generate_sql(self, question: str, schema: list[dict[str, Any]]) -> GeneratedAnalysis:
        system = "Return JSON with sql, reasoning_summary, chart_type. Generate only read-only DuckDB SQL using table dataset_data. Never use filesystem functions or destructive SQL."
        user = json.dumps({"dialect": "DuckDB", "schema": schema, "question": question, "table": "dataset_data"})
        return GeneratedAnalysis.model_validate_json(self._complete(system, user))

    def explain(self, question: str, sql: str, columns: list[str], rows: list[dict[str, Any]]) -> str:
        system = "Return JSON with one string field insight. Explain only the supplied result rows. Never invent values or claim causation."
        user = json.dumps({"question": question, "sql": sql, "columns": columns, "rows": rows})
        try:
            payload = json.loads(self._complete(system, user))
            insight = payload.get("insight")
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise RuntimeError("The LLM returned an invalid explanation.") from exc
        if not isinstance(insight, str) or not insight.strip():
            raise RuntimeError("The LLM returned an empty explanation.")
        return insight.strip()


class DevelopmentProvider:
    """Local provider for development; SQL is generated from the supplied schema and question."""

    def generate_sql(self, question: str, schema: list[dict[str, Any]]) -> GeneratedAnalysis:
        lowered = question.lower()
        names = [str(column["column_name"]) for column in schema]
        numeric = [name for name in names if str(next(column["data_type"] for column in schema if column["column_name"] == name)).lower() in {"integer", "float", "number"}]
        dimensions = [name for name in names if name not in numeric]
        metric = next((name for name in numeric if name in lowered or name.rstrip("s") in lowered), numeric[0] if numeric else None)
        dimension = next((name for name in dimensions if name in lowered or name.rstrip("s") in lowered), dimensions[0] if dimensions else None)
        threshold_match = re.search(r"(?:greater|more|above|over) than\s+([0-9]+(?:\.[0-9]+)?)", lowered)
        if threshold_match and metric:
            threshold = threshold_match.group(1)
            return GeneratedAnalysis(
                sql=f"SELECT * FROM dataset_data WHERE {metric} > {threshold} LIMIT 50",
                reasoning_summary="Filtered the selected numeric field using the threshold in the question.",
                chart_type="table",
            )
        if "top" in lowered and dimension and metric:
            sql = f"SELECT {dimension}, SUM({metric}) AS {metric}_total FROM dataset_data GROUP BY {dimension} ORDER BY {metric}_total DESC LIMIT 5"
            return GeneratedAnalysis(sql=sql, reasoning_summary="Grouped the requested metric by the matching dimension and ranked it descending.", chart_type="bar")
        if ("total" in lowered or "sum" in lowered) and metric:
            return GeneratedAnalysis(sql=f"SELECT SUM({metric}) AS {metric}_total FROM dataset_data", reasoning_summary="Calculated the total of the matching numeric field.", chart_type="table")
        if dimension and metric:
            return GeneratedAnalysis(sql=f"SELECT {dimension}, SUM({metric}) AS {metric}_total FROM dataset_data GROUP BY {dimension} ORDER BY {metric}_total DESC", reasoning_summary="Grouped the matching metric by the matching dimension.", chart_type="bar")
        return GeneratedAnalysis(sql="SELECT * FROM dataset_data LIMIT 50", reasoning_summary="Returned a bounded preview because no analytical shape was unambiguous.", chart_type="table")

    def explain(self, question: str, sql: str, columns: list[str], rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "The query returned no matching rows."
        if len(rows) == 1 and len(rows[0]) == 1:
            key, value = next(iter(rows[0].items()))
            return f"The result for this question is {value} ({key})."
        first = rows[0]
        preview = ", ".join(f"{key}={value}" for key, value in first.items())
        return f"The query returned {len(rows)} result rows. The leading result is {preview}."


def get_provider() -> LLMProvider:
    if settings.llm_provider.lower() in {"openai", "openai-compatible"}:
        return OpenAICompatibleProvider(settings)
    return DevelopmentProvider()
