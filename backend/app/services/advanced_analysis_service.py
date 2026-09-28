from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.services.profiling_service import ProfilingError, load_dataframe


def forecast_file(file_path: str, date_column: str, target_column: str, periods: int) -> dict[str, Any]:
    frame = load_dataframe(file_path)
    if date_column not in frame.columns:
        raise ProfilingError("The selected date column does not exist.")
    if target_column not in frame.columns:
        raise ProfilingError("The selected target column does not exist.")
    dates = pd.to_datetime(frame[date_column], errors="coerce", format="mixed")
    values = pd.to_numeric(frame[target_column], errors="coerce")
    valid = dates.notna() & values.notna()
    if int(valid.sum()) < 3:
        raise ProfilingError("At least three valid chronological observations are required.")
    series = pd.DataFrame({"date": dates[valid], "value": values[valid]}).sort_values("date")
    series = series.groupby("date", as_index=False)["value"].mean()
    if len(series) < 3:
        raise ProfilingError("At least three unique dates are required.")
    x = np.arange(len(series), dtype=float)
    slope, intercept = np.polyfit(x, series["value"].to_numpy(dtype=float), 1)
    step = series["date"].diff().dropna().median()
    if pd.isna(step) or step <= pd.Timedelta(0):
        step = pd.Timedelta(days=1)
    future_dates = [series["date"].iloc[-1] + step * index for index in range(1, periods + 1)]
    future_values = [float(intercept + slope * (len(series) + index - 1)) for index in range(1, periods + 1)]
    return {
        "date_column": date_column,
        "target_column": target_column,
        "historical": [{"date": date.isoformat(), "value": float(value)} for date, value in zip(series["date"], series["value"])],
        "forecast": [{"date": date.isoformat(), "value": value} for date, value in zip(future_dates, future_values)],
        "model": "Linear trend forecast",
        "frequency": str(step),
        "observations": int(len(series)),
    }


def root_cause_file(file_path: str, question: str, metric_column: str | None, dimension_columns: list[str]) -> dict[str, Any]:
    frame = load_dataframe(file_path)
    numeric = [str(column) for column in frame.select_dtypes(include=[np.number]).columns]
    metric = metric_column or (numeric[0] if numeric else None)
    if not metric or metric not in frame.columns:
        raise ProfilingError("A valid numeric metric column is required.")
    dimensions = [column for column in dimension_columns if column in frame.columns]
    if not dimensions:
        dimensions = [str(column) for column in frame.columns if str(column) != metric and not pd.api.types.is_numeric_dtype(frame[column])][:5]
    values = pd.to_numeric(frame[metric], errors="coerce")
    associations = []
    overall = float(values.mean()) if values.notna().any() else 0.0
    for dimension in dimensions:
        grouped = frame.assign(_metric=values).groupby(dimension, dropna=False)["_metric"].agg(["mean", "count"]).dropna()
        if grouped.empty:
            continue
        grouped["difference"] = grouped["mean"] - overall
        for label, row in grouped.sort_values("difference", ascending=False).head(3).iterrows():
            associations.append({"dimension": dimension, "value": str(label), "mean_metric": float(row["mean"]), "difference_from_overall": float(row["difference"]), "observations": int(row["count"]), "relationship": "associated with"})
    return {"question": question, "observed_result": f"The observed average {metric} is {overall:.2f} across {int(values.notna().sum())} valid records.", "associations": associations, "caveat": "These are observed associations in the available data, not proven causal effects."}
