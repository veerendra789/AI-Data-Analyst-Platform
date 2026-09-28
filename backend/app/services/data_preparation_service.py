from __future__ import annotations

import csv
import io
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


MAX_PREPARATION_ROWS = 250_000
MAX_PREPARATION_COLUMNS = 300
PREVIEW_LIMIT = 100
MISSING_MARKERS = {"", "na", "n/a", "null", "none", "nan"}
IDENTIFIER_PARTS = {"id", "zip", "postal", "phone", "code", "sku", "ssn", "account", "identifier"}
RESERVED_NAMES = {"select", "from", "where", "table", "group", "order", "by", "limit", "user", "date", "null"}


class PreparationError(ValueError):
    pass


def normalize_column_names(names: list[str]) -> list[str]:
    result: list[str] = []
    used: set[str] = set()
    for position, original in enumerate(names, start=1):
        normalized = re.sub(r"[^a-z0-9]+", "_", original.strip().lower()).strip("_")
        normalized = re.sub(r"_+", "_", normalized) or f"column_{position}"
        if normalized[0].isdigit():
            normalized = f"column_{normalized}"
        if normalized in RESERVED_NAMES:
            normalized = f"{normalized}_value"
        candidate = normalized
        suffix = 2
        while candidate in used:
            candidate = f"{normalized}_{suffix}"
            suffix += 1
        used.add(candidate)
        result.append(candidate)
    return result


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path, header=None, dtype=str, keep_default_na=False, encoding="utf-8-sig", nrows=MAX_PREPARATION_ROWS + 2)
    except (UnicodeDecodeError, pd.errors.ParserError, csv.Error, ValueError) as exc:
        raise PreparationError("The CSV must be valid UTF-8 with consistent row widths.") from exc
    if frame.empty or len(frame.index) < 2:
        raise PreparationError("The CSV must contain a header and at least one data row.")
    if len(frame.index) - 1 > MAX_PREPARATION_ROWS:
        raise PreparationError(f"The CSV exceeds the supported limit of {MAX_PREPARATION_ROWS:,} rows.")
    if len(frame.columns) > MAX_PREPARATION_COLUMNS:
        raise PreparationError(f"The CSV exceeds the supported limit of {MAX_PREPARATION_COLUMNS} columns.")
    headers = [str(value).strip() for value in frame.iloc[0].tolist()]
    if not headers or all(not name for name in headers):
        raise PreparationError("The CSV must contain at least one named column.")
    headers = [name or f"unnamed_{index + 1}" for index, name in enumerate(headers)]
    data = frame.iloc[1:].reset_index(drop=True)
    data.columns = range(len(headers))
    data.attrs["headers"] = headers
    return data


def _missing_mask(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip().str.lower().isin(MISSING_MARKERS)


def _identifier_like(name: str, values: pd.Series) -> bool:
    parts = set(re.split(r"[^a-z0-9]+", name.lower()))
    examples = values[~_missing_mask(values)].astype(str).head(30).tolist()
    return bool(parts & IDENTIFIER_PARTS) or any(re.fullmatch(r"0\d{3,}", value.strip()) for value in examples)


def _numeric_values(series: pd.Series) -> tuple[pd.Series, int, list[str], bool]:
    raw = series.astype("string").fillna("").astype(str).str.strip()
    nonmissing = ~_missing_mask(raw)
    recognized_currency = raw.str.contains(r"(?:[$£€¥₹]|\b(?:USD|EUR|GBP|INR)\b)", case=False, regex=True)
    cleaned = raw.str.replace(r"(?:[$£€¥₹]|\b(?:USD|EUR|GBP|INR)\b)", "", case=False, regex=True)
    cleaned = cleaned.str.replace(",", "", regex=False)
    parsed = pd.to_numeric(cleaned.where(nonmissing), errors="coerce")
    failures = int((nonmissing & parsed.isna()).sum())
    examples = raw[nonmissing & parsed.isna()].drop_duplicates().head(5).tolist()
    return parsed, failures, examples, bool((recognized_currency & nonmissing).any())


def _detect_type(name: str, series: pd.Series) -> tuple[str, bool, dict[str, Any] | None]:
    clean = series.astype(str).str.strip()
    missing = _missing_mask(clean)
    values = clean[~missing]
    if values.empty:
        return "string", False, None
    if values.str.lower().isin({"true", "false", "yes", "no"}).all():
        return "boolean", True, None
    if _identifier_like(name, values):
        return "string", True, None
    parsed, failures, examples, currency = _numeric_values(clean)
    numeric_count = int(parsed.notna().sum())
    if failures == 0 or numeric_count >= max(1, int(len(values) * 0.8)):
        kind = "integer" if np.equal(np.mod(parsed.dropna().to_numpy(dtype=float), 1), 0).all() else "float"
        return kind, failures == 0, {"currency": currency, "numeric_failures": failures, "invalid_examples": examples}
    slash_date_values = values[values.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}")]
    if not slash_date_values.empty:
        return "string", False, {"ambiguous_date": True, "count": int(len(slash_date_values)), "examples": slash_date_values.head(5).tolist()}
    iso_date_mask = values.str.match(r"^\d{4}-\d{2}-\d{2}(?:[T ].*)?$")
    if iso_date_mask.any():
        parsed_dates = pd.to_datetime(values, errors="coerce", format="mixed", utc=False)
        if parsed_dates.notna().all():
            return ("datetime" if parsed_dates.dt.hour.any() else "date"), True, None
        if iso_date_mask.all():
            invalid = values[parsed_dates.isna()]
            return "string", False, {"invalid_date": True, "count": int(len(invalid)), "examples": invalid.head(5).tolist()}
    unique = int(values.nunique(dropna=True))
    if unique <= min(30, max(2, int(len(values) * 0.2))):
        return "categorical", True, None
    return "string", True, None


def _safe_examples(series: pd.Series) -> list[str]:
    return [str(value)[:100] for value in series.astype(str).drop_duplicates().head(5).tolist()]


def analyze_csv(path: Path, filename: str) -> dict[str, Any]:
    frame = _read_csv(path)
    headers: list[str] = frame.attrs["headers"]
    normalized = normalize_column_names(headers)
    missing_total = int(sum(_missing_mask(frame[index]).sum() for index in frame.columns))
    duplicate_rows = int(frame.duplicated(keep="first").sum())
    issues: list[dict[str, Any]] = []
    plan: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []

    duplicates = {name for name, count in Counter(header.strip().casefold() for header in headers).items() if count > 1}
    for index, (original, standard) in enumerate(zip(headers, normalized)):
        series = frame[index].astype(str)
        missing_mask = _missing_mask(series)
        nonmissing = series[~missing_mask]
        detected, confident, flags = _detect_type(original, series)
        if standard != original:
            plan.append({"id": f"rename:{index}", "type": "rename_column", "column_index": index, "column": original, "parameters": {"name": standard}, "reason": "Standardize the column name for consistent analysis.", "affected_count": 0, "examples": [], "safe": True, "selected": False, "status": "proposed"})
        trimmed_count = int((series != series.str.strip()).sum())
        if trimmed_count:
            issues.append({"column": original, "type": "extra_whitespace", "affected_count": trimmed_count, "examples": _safe_examples(series[series != series.str.strip()]), "recommendation": "Trim leading and trailing whitespace.", "automatable": True})
            plan.append({"id": f"trim:{index}", "type": "trim_whitespace", "column_index": index, "column": original, "parameters": {}, "reason": "Trim leading and trailing whitespace.", "affected_count": trimmed_count, "examples": [], "safe": True, "selected": False, "status": "proposed"})
        if missing_mask.any():
            issues.append({"column": original, "type": "missing_values", "affected_count": int(missing_mask.sum()), "examples": [], "recommendation": "Choose a missing-value strategy for review.", "automatable": False})
        if len(nonmissing) == 0:
            issues.append({"column": original, "type": "empty_column", "affected_count": len(frame.index), "examples": [], "recommendation": "Remove only if this column is not needed.", "automatable": False})
        if nonmissing.nunique() == 1 and len(nonmissing):
            issues.append({"column": original, "type": "constant_value", "affected_count": len(frame.index), "examples": _safe_examples(nonmissing), "recommendation": "Review whether this constant column is useful.", "automatable": False})
        review_markers = nonmissing[nonmissing.str.strip().str.lower().isin({"-", "unknown"})]
        if not review_markers.empty:
            issues.append({"column": original, "type": "possible_missing_markers", "affected_count": int(len(review_markers)), "examples": _safe_examples(review_markers), "recommendation": "These placeholders are retained as values; review before treating them as missing.", "automatable": False})
        if detected in {"integer", "float"} and nonmissing.map(lambda value: bool(re.search(r"[$£€¥₹]|\b(?:USD|EUR|GBP|INR)\b|,", value, re.I))).any():
            issues.append({"column": original, "type": "formatted_numeric_text", "affected_count": len(nonmissing), "examples": _safe_examples(nonmissing), "recommendation": "Remove recognized currency symbols and thousands separators, without currency conversion.", "automatable": True})
            plan.append({"id": f"numeric:{index}", "type": "parse_numeric", "column_index": index, "column": original, "parameters": {"data_type": detected}, "reason": "Parse recognized numeric formatting without changing currency units.", "affected_count": len(nonmissing), "examples": [], "safe": True, "selected": False, "status": "proposed"})
        elif detected in {"integer", "float"} and nonmissing.map(lambda value: not bool(re.fullmatch(r"[+-]?(?:\d+\.?\d*|\.\d+)", value.strip()))).any():
            issues.append({"column": original, "type": "numeric_stored_as_text", "affected_count": len(nonmissing), "examples": _safe_examples(nonmissing), "recommendation": f"Convert to {detected} after reviewing parse failures.", "automatable": True})
            plan.append({"id": f"numeric:{index}", "type": "parse_numeric", "column_index": index, "column": original, "parameters": {"data_type": detected}, "reason": "Parse numeric values stored as strings.", "affected_count": len(nonmissing), "examples": [], "safe": True, "selected": False, "status": "proposed"})
        if detected in {"integer", "float", "boolean", "date", "datetime"}:
            has_conversion = any(operation["column_index"] == index and operation["type"] in {"parse_numeric", "convert_type"} for operation in plan)
            if not has_conversion:
                operation_type = "parse_numeric" if detected in {"integer", "float"} else "convert_type"
                operation_id = f"numeric:{index}" if operation_type == "parse_numeric" else f"type:{index}"
                plan.append({"id": operation_id, "type": operation_type, "column_index": index, "column": original, "parameters": {"data_type": detected}, "reason": f"Convert values to the detected {detected} type after review.", "affected_count": len(nonmissing), "examples": flags.get("invalid_examples", []) if flags else [], "safe": bool(confident), "selected": False, "status": "proposed"})
        if flags and flags.get("numeric_failures"):
            issues.append({"column": original, "type": "invalid_numeric_values", "affected_count": flags["numeric_failures"], "examples": flags["invalid_examples"], "recommendation": "Review values that will remain missing if this numeric conversion is approved.", "automatable": False})
        if detected in {"integer", "float"}:
            numeric, _, _, _ = _numeric_values(nonmissing)
            quartiles = numeric.dropna().quantile([0.25, 0.75])
            if len(quartiles) == 2:
                spread = quartiles.loc[0.75] - quartiles.loc[0.25]
                low, high = quartiles.loc[0.25] - 1.5 * spread, quartiles.loc[0.75] + 1.5 * spread
                outliers = numeric[(numeric < low) | (numeric > high)].dropna()
                if len(outliers):
                    issues.append({"column": original, "type": "potential_outliers", "affected_count": int(len(outliers)), "examples": [str(value) for value in outliers.head(5).tolist()], "recommendation": "Review unusual values; outliers may be valid and are not removed automatically.", "automatable": False})
        if flags and flags.get("ambiguous_date"):
            issues.append({"column": original, "type": "ambiguous_date", "affected_count": flags["count"], "examples": flags["examples"], "recommendation": "Confirm day/month order; values are retained as strings until then.", "automatable": False})
        if flags and flags.get("invalid_date"):
            issues.append({"column": original, "type": "invalid_dates", "affected_count": flags["count"], "examples": flags["examples"], "recommendation": "Review invalid ISO-like dates; values remain unchanged until conversion is approved.", "automatable": False})
        if len(duplicates) and original.strip().casefold() in duplicates:
            issues.append({"column": original, "type": "duplicate_column_name", "affected_count": 1, "examples": [], "recommendation": f"Use unique standardized name {standard}.", "automatable": True})
        if nonmissing.nunique() <= 20 and len(nonmissing) > nonmissing.nunique():
            folded = nonmissing.str.strip().str.casefold()
            if folded.nunique() < nonmissing.nunique():
                issues.append({"column": original, "type": "inconsistent_categories", "affected_count": int(nonmissing.nunique() - folded.nunique()), "examples": _safe_examples(nonmissing), "recommendation": "Review capitalization variants and approve explicit mappings.", "automatable": False})
        columns.append({"column_index": index, "original_name": original, "suggested_name": standard, "detected_type": detected, "suggested_type": detected if confident else "string", "type_confident": confident, "null_count": int(missing_mask.sum()), "unique_count": int(nonmissing.nunique()), "examples": _safe_examples(nonmissing), "warnings": [issue["type"] for issue in issues if issue["column"] == original]})

    if duplicate_rows:
        issues.append({"column": None, "type": "duplicate_rows", "affected_count": duplicate_rows, "examples": [], "recommendation": "Optionally remove repeated full rows, keeping the first occurrence.", "automatable": True})
        plan.append({"id": "duplicates:rows", "type": "remove_duplicate_rows", "column_index": None, "column": None, "parameters": {"keep": "first"}, "reason": "Remove fully duplicated rows while preserving the first occurrence.", "affected_count": duplicate_rows, "examples": [], "safe": True, "selected": False, "status": "proposed"})

    original_count = len(headers)
    return {
        "filename": filename,
        "status": "ANALYZED",
        "overview": {"row_count": len(frame.index), "column_count": original_count, "missing_values": missing_total, "missing_percentage": round(missing_total / max(1, frame.size) * 100, 2), "duplicate_rows": duplicate_rows, "inconsistent_type_columns": sum(not column["type_confident"] for column in columns), "inconsistent_format_columns": len({issue["column"] for issue in issues if issue["type"] in {"extra_whitespace", "formatted_numeric_text", "inconsistent_categories", "ambiguous_date"}}), "suggested_transformations": len(plan), "warnings": len(issues)},
        "columns": columns,
        "issues": issues,
        "preview": {"columns": _unique_preview_names(headers), "rows": [{_unique_preview_names(headers)[index]: value for index, value in enumerate(row)} for row in frame.head(PREVIEW_LIMIT).itertuples(index=False, name=None)], "total_rows": len(frame.index), "returned_rows": min(len(frame.index), PREVIEW_LIMIT)},
        "comparison": None,
    }, plan


def _unique_preview_names(headers: list[str]) -> list[str]:
    used: set[str] = set()
    output: list[str] = []
    for index, header in enumerate(headers, start=1):
        name = header
        suffix = 2
        while name in used:
            name = f"{header} ({suffix})"
            suffix += 1
        if not name:
            name = f"Column {index}"
        used.add(name)
        output.append(name)
    return output


def _convert_type(series: pd.Series, data_type: str, date_format: str | None = None) -> tuple[pd.Series, int, list[str]]:
    raw = series.fillna("").astype(str)
    missing = _missing_mask(raw)
    if data_type in {"integer", "float"}:
        parsed, failures, examples, _ = _numeric_values(raw)
        if data_type == "integer":
            fractional = parsed.notna() & (parsed % 1 != 0)
            failures += int(fractional.sum())
            examples += raw[fractional].head(5).tolist()
            parsed = parsed.where(~fractional)
            parsed = parsed.astype("Int64")
        return parsed, failures, examples
    if data_type == "boolean":
        values = raw.str.strip().str.lower().map({"true": True, "yes": True, "false": False, "no": False})
        failures = int((~missing & values.isna()).sum())
        return values.astype("boolean"), failures, raw[~missing & values.isna()].head(5).tolist()
    if data_type in {"date", "datetime"}:
        format_map = {"MM/DD/YYYY": "%m/%d/%Y", "DD/MM/YYYY": "%d/%m/%Y", "YYYY-MM-DD": "%Y-%m-%d"}
        parsed = pd.to_datetime(raw.where(~missing), errors="coerce", format=format_map.get(date_format, "mixed"))
        failures = int((~missing & parsed.isna()).sum())
        return parsed, failures, raw[~missing & parsed.isna()].head(5).tolist()
    return raw, 0, []


def apply_plan(source_path: Path, metadata: dict[str, Any], plan: list[dict[str, Any]], request: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    frame = _read_csv(source_path)
    headers: list[str] = frame.attrs["headers"]
    selected_ids = set(request.get("selected_operation_ids", []))
    if request.get("remove_duplicates"):
        selected_ids.add("duplicates:rows")
    plan_ids = {operation["id"] for operation in plan}
    if selected_ids - plan_ids:
        raise PreparationError("The selected transformation plan contains an unknown operation.")
    overrides = {item["column_index"]: item for item in request.get("column_overrides", [])}
    mappings = request.get("category_mappings", {})
    histories: list[dict[str, Any]] = []
    failed_conversions: list[dict[str, Any]] = []
    renamed_indexes: set[int] = set()
    transformed_indexes: set[int] = set()

    for operation in plan:
        if operation["id"] not in selected_ids:
            continue
        kind = operation["type"]
        index = operation["column_index"]
        if kind == "rename_column":
            headers[index] = overrides.get(index, {}).get("name") or operation["parameters"]["name"]
            renamed_indexes.add(index)
        elif kind == "trim_whitespace" and index is not None:
            transformed_indexes.add(index)
            frame[index] = frame[index].astype(str).str.strip()
        elif kind in {"parse_numeric", "convert_type"} and index is not None:
            transformed_indexes.add(index)
            data_type = overrides.get(index, {}).get("data_type") or operation["parameters"]["data_type"]
            converted, failures, examples = _convert_type(frame[index], data_type, overrides.get(index, {}).get("date_format"))
            frame[index] = converted
            if failures:
                failed_conversions.append({"column_index": index, "count": failures, "examples": examples})
        elif kind == "remove_duplicate_rows":
            frame = frame.drop_duplicates(keep="first").reset_index(drop=True)
        histories.append({"operation_id": operation["id"], "type": kind, "column_index": index, "status": "applied"})

    applied_type_indexes = {entry["column_index"] for entry in histories if entry["type"] in {"parse_numeric", "convert_type"}}
    for index, override in overrides.items():
        if index >= len(headers):
            raise PreparationError("A column override refers to an unknown column.")
        if override.get("name"):
            headers[index] = override["name"].strip()
            renamed_indexes.add(index)
        data_type = override.get("data_type")
        if data_type and index not in applied_type_indexes:
            transformed_indexes.add(index)
            if data_type in {"date", "datetime"} and metadata["columns"][index]["warnings"] and "ambiguous_date" in metadata["columns"][index]["warnings"] and not override.get("date_format"):
                raise PreparationError("Choose MM/DD/YYYY or DD/MM/YYYY before converting this ambiguous date column.")
            converted, failures, examples = _convert_type(frame[index], data_type, override.get("date_format"))
            frame[index] = converted
            histories.append({"operation_id": f"type:{index}", "type": "convert_type", "column_index": index, "data_type": data_type, "status": "applied", "failed_count": failures})
            if failures:
                failed_conversions.append({"column_index": index, "count": failures, "examples": examples})

    for item in request.get("missing_strategies", []):
        index, strategy = item["column_index"], item["strategy"]
        if index >= len(headers):
            raise PreparationError("A missing-value strategy refers to an unknown column.")
        series = frame[index]
        missing = _missing_mask(series)
        if strategy == "drop_rows":
            frame = frame.loc[~missing].copy()
        elif strategy in {"mean", "median", "mode", "constant"}:
            if missing.all():
                raise PreparationError("Cannot impute an entirely missing column.")
            if _identifier_like(headers[index], series):
                raise PreparationError("Identifier columns cannot be imputed with numeric or arbitrary values.")
            if strategy in {"mean", "median"}:
                numeric, failures, examples, _ = _numeric_values(series)
                if failures or numeric.notna().sum() == 0:
                    raise PreparationError("Mean or median imputation requires a fully numeric column.")
                fill_value = numeric.mean() if strategy == "mean" else numeric.median()
            elif strategy == "mode":
                modes = series.loc[~missing].mode()
                if modes.empty:
                    raise PreparationError("Mode imputation is unavailable for this column.")
                fill_value = modes.iloc[0]
            else:
                fill_value = item.get("value")
                if fill_value is None:
                    raise PreparationError("Constant imputation requires a value.")
            frame.loc[missing, index] = fill_value
        histories.append({"operation_id": f"missing:{index}", "type": "missing_value_strategy", "column_index": index, "strategy": strategy, "affected_count": int(missing.sum()), "status": "applied"})
        transformed_indexes.add(index)

    for index_text, mapping in mappings.items():
        index = int(index_text)
        if index >= len(headers) or not isinstance(mapping, dict):
            raise PreparationError("A category mapping refers to an invalid column.")
        frame[index] = frame[index].replace(mapping)
        histories.append({"operation_id": f"categories:{index}", "type": "replace_categories", "column_index": index, "mapping_count": len(mapping), "status": "applied"})
        transformed_indexes.add(index)

    for index_text, markers in request.get("missing_markers", {}).items():
        index = int(index_text)
        if index < 0 or index >= len(headers) or len(markers) > 50:
            raise PreparationError("A configurable missing marker refers to an invalid column or exceeds the marker limit.")
        normalized_markers = {str(marker).strip().casefold() for marker in markers if str(marker).strip()}
        if any(len(marker) > 100 for marker in normalized_markers):
            raise PreparationError("A configurable missing marker is too long.")
        series = frame[index].astype("string")
        mask = series.str.strip().str.casefold().isin(normalized_markers)
        frame.loc[mask, index] = pd.NA
        histories.append({"operation_id": f"markers:{index}", "type": "configure_missing_markers", "column_index": index, "marker_count": len(normalized_markers), "affected_count": int(mask.sum()), "status": "applied"})
        transformed_indexes.add(index)

    for index in request.get("drop_column_indexes", []):
        if index < 0 or index >= len(headers):
            raise PreparationError("A requested column removal refers to an unknown column.")
    if request.get("drop_column_indexes"):
        dropped = set(request["drop_column_indexes"])
        frame = frame.drop(columns=list(dropped))
        headers = [header for index, header in enumerate(headers) if index not in dropped]
        histories.append({"operation_id": "drop_columns", "type": "drop_columns", "column_indexes": sorted(dropped), "status": "applied"})

    # Apply user-selected types only to the original identity index; duplicate names are never used as keys.
    output_names = [normalize_column_names([name])[0] if index in renamed_indexes or index in transformed_indexes else name for index, name in enumerate(headers)]
    if len(set(output_names)) != len(output_names):
        raise PreparationError("Selected column names are not unique. Review and approve the suggested names for duplicate columns.")
    if any(not name.strip() for name in output_names):
        raise PreparationError("Column names cannot be empty.")
    frame.columns = output_names
    if len(set(frame.columns)) != len(frame.columns):
        raise PreparationError("The transformed column names must be unique.")
    if frame.empty or len(frame.columns) == 0:
        raise PreparationError("Transformations cannot produce an empty table.")
    source = _read_csv(source_path)
    before_missing = int(sum(_missing_mask(source[index]).sum() for index in source.columns))
    after_missing = int(sum(_missing_mask(frame[column]).sum() for column in frame.columns))
    before_rows = int(metadata["overview"]["row_count"])
    after_duplicates = int(frame.duplicated().sum())
    original_duplicates = int(metadata["overview"]["duplicate_rows"])
    comparison = {"original_row_count": before_rows, "final_row_count": len(frame.index), "original_column_count": metadata["overview"]["column_count"], "final_column_count": len(frame.columns), "missing_before": before_missing, "missing_after": after_missing, "duplicate_rows_before": original_duplicates, "duplicate_rows_after": after_duplicates, "successful_type_conversions": len([entry for entry in histories if entry["type"] == "convert_type"]), "failed_type_conversions": failed_conversions, "columns_renamed": sum(1 for index, name in enumerate(headers) if name != metadata["columns"][index]["original_name"]), "categories_standardized": sum(entry.get("mapping_count", 0) for entry in histories), "rows_removed": before_rows - len(frame.index), "warnings": ["Some selected type conversions contained values that could not be parsed." for _ in failed_conversions]}
    return frame, comparison, histories


def preview_frame(frame: pd.DataFrame, limit: int = PREVIEW_LIMIT) -> dict[str, Any]:
    rows = frame.head(min(max(limit, 1), PREVIEW_LIMIT)).replace({np.nan: None}).to_dict(orient="records")
    normalized_rows = [{str(key): (None if pd.isna(value) else value.item() if isinstance(value, np.generic) else value.isoformat() if hasattr(value, "isoformat") else value) for key, value in row.items()} for row in rows]
    return {"columns": [str(column) for column in frame.columns], "rows": normalized_rows, "total_rows": len(frame.index), "returned_rows": len(normalized_rows)}


def write_clean_csv(frame: pd.DataFrame, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8")
    return path.stat().st_size