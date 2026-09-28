from __future__ import annotations

import re


MAX_SQL_LENGTH = 5000
MAX_RESULT_ROWS = 500
FORBIDDEN_PATTERNS = (
    r"\b(insert|update|delete|drop|alter|truncate|create|attach|detach|copy|install|load|export|merge|call|execute|pragma)\b",
    r"\b(read_csv|read_csv_auto|read_json|read_parquet|glob|parquet_scan|httpfs|sqlite_scan)\b",
    r"\b(pragma|information_schema|pg_catalog|duckdb_settings)\b",
)


class SqlValidationError(ValueError):
    pass


def validate_read_only_sql(sql: str) -> str:
    normalized = sql.strip()
    if not normalized:
        raise SqlValidationError("The generated SQL is empty.")
    if len(normalized) > MAX_SQL_LENGTH:
        raise SqlValidationError("The generated SQL is too long.")
    if normalized.count(";") > 0:
        raise SqlValidationError("Only one read-only SQL statement is allowed.")
    if "--" in normalized or "/*" in normalized or "*/" in normalized:
        raise SqlValidationError("SQL comments are not allowed.")
    if not re.match(r"^(select|with)\b", normalized, flags=re.IGNORECASE):
        raise SqlValidationError("Only SELECT or WITH queries are allowed.")
    if not re.search(r"\bdataset_data\b", normalized, flags=re.IGNORECASE):
        raise SqlValidationError("Queries must read from the registered dataset view.")
    if re.search(r"\b(from|join)\s*['\"]", normalized, flags=re.IGNORECASE):
        raise SqlValidationError("Direct file scans are not allowed.")
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            raise SqlValidationError("The generated SQL contains a forbidden operation.")
    return normalized
