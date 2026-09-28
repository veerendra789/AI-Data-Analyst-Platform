from __future__ import annotations

import json
from typing import Any

from app.services.profiling_service import profile_file
from app.services.advanced_analysis_service import forecast_file
from app.services.profiling_service import ProfilingError


def build_report(dataset: Any, title: str, latest_results: list[dict[str, Any]]) -> str:
    profile = profile_file(dataset.file_path)
    summary = profile["summary"]
    forecast = None
    if summary["date_columns"] and summary["numeric_columns"]:
        try:
            forecast = forecast_file(dataset.file_path, summary["date_columns"][0], summary["numeric_columns"][0], 6)
        except ProfilingError:
            forecast = None
    report = {
        "executive_summary": f"{dataset.name} contains {summary['row_count']} rows and {summary['column_count']} columns. The report is based on computed dataset statistics and saved analytical results.",
        "dataset_overview": {"name": dataset.name, "filename": dataset.original_filename, "rows": summary["row_count"], "columns": summary["column_count"]},
        "data_quality": {"missing_values": summary["missing_values"], "missing_percentage": summary["missing_percentage"], "duplicate_rows": summary["duplicate_rows"]},
        "important_metrics": profile["numeric_statistics"],
        "trends": profile["distributions"],
        "anomalies": profile["outliers"],
        "forecast": forecast,
        "major_findings": [{"type": "computed", "finding": f"{column} has {stats['unique_count']} unique values."} for column, stats in profile["categorical_summaries"].items()],
        "ai_insights": [{"question": result.get("question"), "insight": result.get("insight"), "rows": result.get("rows", [])} for result in latest_results],
    }
    return json.dumps(report, default=str)
