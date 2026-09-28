from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


class ProfilingError(ValueError):
    pass


def load_dataframe(file_path: str) -> pd.DataFrame:
    path = Path(file_path).resolve()
    if not path.is_file() or path.suffix.lower() != ".csv":
        raise ProfilingError("The dataset file is unavailable.")
    try:
        return pd.read_csv(path)
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
        raise ProfilingError("The dataset could not be parsed for analysis.") from exc


def _is_date_series(series: pd.Series) -> bool:
    if series.empty or series.dropna().empty:
        return False
    converted = pd.to_datetime(series, errors="coerce", format="mixed")
    return float(converted.notna().mean()) >= 0.8 and not pd.api.types.is_numeric_dtype(series)


def _json_number(value: Any) -> float | None:
    if value is None or pd.isna(value) or not np.isfinite(float(value)):
        return None
    return float(value)


def profile_dataframe(frame: pd.DataFrame) -> dict[str, Any]:
    row_count, column_count = frame.shape
    numeric_columns = [str(column) for column in frame.select_dtypes(include=[np.number]).columns]
    date_columns = [str(column) for column in frame.columns if _is_date_series(frame[column])]
    categorical_columns = [
        str(column) for column in frame.columns if str(column) not in numeric_columns and str(column) not in date_columns
    ]
    missing_by_column = frame.isna().sum()
    total_cells = max(row_count * column_count, 1)
    columns = []
    for column in frame.columns:
        series = frame[column]
        missing_count = int(missing_by_column[column])
        if str(column) in numeric_columns:
            data_type = str(series.dtype)
        elif str(column) in date_columns:
            data_type = "date"
        else:
            data_type = "string"
        columns.append(
            {
                "name": str(column),
                "data_type": data_type,
                "nullable": missing_count > 0,
                "unique_count": int(series.nunique(dropna=True)),
                "missing_count": missing_count,
                "missing_percentage": round(missing_count / max(row_count, 1) * 100, 2),
            }
        )

    numeric_statistics: dict[str, dict[str, float | None]] = {}
    distributions: dict[str, list[dict[str, float | int]]] = {}
    outliers: dict[str, dict[str, float | int | None]] = {}
    for column in numeric_columns:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        numeric_statistics[column] = {
            "mean": _json_number(values.mean()),
            "median": _json_number(values.median()),
            "minimum": _json_number(values.min()),
            "maximum": _json_number(values.max()),
            "standard_deviation": _json_number(values.std(ddof=1)) if len(values) > 1 else 0.0,
        }
        if len(values) > 0 and values.nunique() > 1:
            counts, edges = np.histogram(values.to_numpy(), bins=min(10, values.nunique()))
            distributions[column] = [
                {"start": float(edges[index]), "end": float(edges[index + 1]), "count": int(counts[index])}
                for index in range(len(counts))
            ]
        else:
            distributions[column] = []
        if len(values) >= 4:
            q1, q3 = values.quantile([0.25, 0.75])
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            count = int(((values < lower) | (values > upper)).sum())
            outliers[column] = {"lower_bound": _json_number(lower), "upper_bound": _json_number(upper), "count": count}
        else:
            outliers[column] = {"lower_bound": None, "upper_bound": None, "count": 0}

    categorical_summaries: dict[str, dict[str, Any]] = {}
    for column in categorical_columns:
        counts = frame[column].fillna("<missing>").astype(str).value_counts().head(10)
        categorical_summaries[column] = {
            "unique_count": int(frame[column].nunique(dropna=True)),
            "top_categories": [{"value": str(value), "count": int(count)} for value, count in counts.items()],
        }

    correlations: dict[str, dict[str, float | None]] = {}
    if len(numeric_columns) >= 2:
        correlation_frame = frame[numeric_columns].corr(method="pearson")
        for column in numeric_columns:
            correlations[column] = {other: _json_number(correlation_frame.loc[column, other]) for other in numeric_columns}

    return {
        "summary": {
            "row_count": int(row_count),
            "column_count": int(column_count),
            "duplicate_rows": int(frame.duplicated().sum()),
            "missing_values": int(missing_by_column.sum()),
            "missing_percentage": round(float(missing_by_column.sum()) / total_cells * 100, 2),
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "date_columns": date_columns,
        },
        "columns": columns,
        "numeric_statistics": numeric_statistics,
        "categorical_summaries": categorical_summaries,
        "correlations": correlations,
        "distributions": distributions,
        "outliers": outliers,
    }


def profile_file(file_path: str) -> dict[str, Any]:
    return profile_dataframe(load_dataframe(file_path))


def detect_anomalies(file_path: str, column: str, contamination: float) -> dict[str, Any]:
    frame = load_dataframe(file_path)
    if column not in frame.columns:
        raise ProfilingError("The selected numeric column does not exist.")
    if not 0 < contamination <= 0.5:
        raise ProfilingError("Contamination must be between 0 and 0.5.")
    values = pd.to_numeric(frame[column], errors="coerce")
    valid = values.notna()
    if int(valid.sum()) < 5 or values[valid].nunique() < 2:
        return {"column": column, "number_of_anomalies": 0, "anomaly_records": [], "relevant_columns": [column], "model": "IsolationForest (not applicable to this dataset)"}
    model = IsolationForest(contamination=min(contamination, max(1 / int(valid.sum()), 0.5)), random_state=42)
    numeric_values = values[valid].to_numpy().reshape(-1, 1)
    model.fit(numeric_values)
    scores = model.decision_function(numeric_values)
    labels = model.predict(numeric_values)
    records = frame.loc[valid].copy()
    records["anomaly_score"] = scores
    records["is_anomaly"] = labels == -1
    anomalies = records[records["is_anomaly"]].drop(columns=["is_anomaly"]).replace({np.nan: None})
    return {
        "column": column,
        "number_of_anomalies": int(len(anomalies)),
        "anomaly_records": anomalies.to_dict(orient="records"),
        "relevant_columns": [column],
        "model": "IsolationForest",
    }
