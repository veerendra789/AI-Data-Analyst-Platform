from __future__ import annotations

from pathlib import Path
from threading import Timer
from typing import Any

import duckdb
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.sql_validator import MAX_RESULT_ROWS, validate_read_only_sql


class DuckDbSettings(BaseSettings):
    query_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = DuckDbSettings()


class DataQueryService:
    def execute(self, file_path: str, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        validated_sql = validate_read_only_sql(sql)
        safe_path = Path(file_path).resolve()
        if not safe_path.is_file() or safe_path.suffix.lower() != ".csv":
            raise ValueError("The dataset file is unavailable.")

        connection = duckdb.connect(database=":memory:")
        timeout = Timer(settings.query_timeout_seconds, connection.interrupt)
        try:
            quoted_path = str(safe_path).replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE VIEW dataset_data AS SELECT * FROM read_csv_auto('{quoted_path}', HEADER=TRUE, SAMPLE_SIZE=-1)"
            )
            bounded_sql = f"SELECT * FROM ({validated_sql}) AS analysis_result LIMIT {MAX_RESULT_ROWS}"
            timeout.start()
            result = connection.execute(bounded_sql)
            columns = [description[0] for description in result.description]
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return columns, rows
        except duckdb.Error as exc:
            raise ValueError("The analytical query could not be executed safely.") from exc
        finally:
            timeout.cancel()
            connection.close()
