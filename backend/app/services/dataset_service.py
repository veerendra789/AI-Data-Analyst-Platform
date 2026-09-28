from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatasetSettings(BaseSettings):
    upload_directory: str = "data/uploads"
    max_upload_size: int = 50 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = DatasetSettings()
ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"}
CHUNK_SIZE = 1024 * 1024


@dataclass
class ParsedCsv:
    headers: list[str]
    row_count: int
    rows: list[list[str]]
    column_stats: list[dict[str, object]]


class CsvValidationError(ValueError):
    pass


def validate_filename(filename: str | None) -> str:
    if not filename or Path(filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    normalized = filename.replace("\\", "/")
    return PurePosixPath(normalized).name


def validate_content_type(content_type: str | None) -> None:
    if not content_type or content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="The uploaded file must have a CSV MIME type.")


async def store_upload(upload: UploadFile) -> tuple[Path, int]:
    validate_filename(upload.filename)
    validate_content_type(upload.content_type)
    upload_dir = Path(settings.upload_directory).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{uuid4().hex}.csv"
    total_size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > settings.max_upload_size:
                    raise HTTPException(status_code=413, detail="The uploaded file is too large.")
                output.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return destination, total_size


def _infer_type(values: list[str]) -> str:
    non_empty = [value.strip() for value in values if value.strip()]
    if not non_empty:
        return "string"
    if all(value.lower() in {"true", "false"} for value in non_empty):
        return "boolean"
    try:
        for value in non_empty:
            int(value)
        return "integer"
    except ValueError:
        pass
    try:
        for value in non_empty:
            float(value)
        return "float"
    except ValueError:
        return "string"


def parse_csv(stream: BinaryIO, max_preview_rows: int = 100) -> ParsedCsv:
    try:
        content = stream.read()
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("The CSV file must use UTF-8 encoding.") from exc
    if not decoded.strip():
        raise CsvValidationError("The CSV file is empty.")

    reader = csv.reader(io.StringIO(decoded), strict=True)
    try:
        raw_headers = next(reader)
    except (StopIteration, csv.Error) as exc:
        raise CsvValidationError("The CSV file must contain a header row.") from exc
    headers = [header.strip() for header in raw_headers]
    if not headers or any(not header for header in headers) or len(set(headers)) != len(headers):
        raise CsvValidationError("The CSV header must contain unique, non-empty column names.")

    values_by_column: list[list[str]] = [[] for _ in headers]
    preview_rows: list[list[str]] = []
    row_count = 0
    try:
        for row in reader:
            if len(row) != len(headers):
                raise CsvValidationError("Every CSV row must have the same number of columns as the header.")
            row_count += 1
            if len(preview_rows) < max_preview_rows:
                preview_rows.append(row)
            for index, value in enumerate(row):
                values_by_column[index].append(value)
    except csv.Error as exc:
        raise CsvValidationError("The CSV file contains invalid CSV syntax.") from exc

    if row_count == 0:
        raise CsvValidationError("The CSV file must contain at least one data row.")

    column_stats = []
    for header, values in zip(headers, values_by_column):
        non_empty = [value for value in values if value.strip()]
        column_stats.append(
            {
                "column_name": header,
                "data_type": _infer_type(values),
                "nullable": len(non_empty) != len(values),
                "unique_count": len(set(non_empty)),
                "missing_count": len(values) - len(non_empty),
            }
        )
    return ParsedCsv(headers, row_count, preview_rows, column_stats)
