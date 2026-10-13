from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.core.supabase import get_supabase_client


def _principal(profile: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=str(profile["id"]),
        uid=str(profile["id"]),
        email=profile.get("email") or "",
        name=profile.get("display_name") or "Analyst",
        role=profile.get("role", "ANALYST"),
        is_active=profile.get("is_active", True),
        created_at=profile.get("created_at") or datetime.now(timezone.utc),
    )


def _record(table: str, data: dict[str, Any]) -> SimpleNamespace:
    values = dict(data)
    if table == "datasets":
        values["file_path"] = values.get("storage_path", "")
        values["storagePath"] = values.get("storage_path", "")
        values["user_id"] = values.get("user_id", "")
        values["ownerId"] = values.get("user_id", "")
        values["source_preparation_id"] = values.get("source_preparation_id")
        values["columns"] = [
            SimpleNamespace(id=index, **column)
            for index, column in enumerate(values.get("columns") or [])
        ]
    elif table == "structuring_jobs":
        values["source_path"] = values.get("source_storage_path", "")
        values["sourceStoragePath"] = values.get("source_storage_path", "")
        values["output_path"] = values.get("output_storage_path")
        values["outputStoragePath"] = values.get("output_storage_path")
        values["file_size"] = values.get("file_size", 0)
        values["fileSize"] = values.get("file_size", 0)
        values["source_filename"] = values.get("source_filename", "")
        values["sourceFilename"] = values.get("source_filename", "")
        values["user_id"] = values.get("user_id", "")
        values["ownerId"] = values.get("user_id", "")
    elif table == "analyses":
        values["generated_sql"] = values.get("generated_sql")
        values["execution_time"] = values.get("execution_time")
        values["result"] = values.get("result_json") or {}
        values["user_id"] = values.get("user_id", "")
        values["ownerId"] = values.get("user_id", "")
    elif table == "reports":
        values["user_id"] = values.get("user_id", "")
        values["ownerId"] = values.get("user_id", "")
    return SimpleNamespace(**values)


def _one(table: str, filters: dict[str, Any]) -> dict[str, Any] | None:
    query = get_supabase_client().table(table).select("*")
    for key, value in filters.items():
        query = query.eq(key, value)
    rows = query.limit(1).execute().data or []
    return rows[0] if rows else None


def get_user(uid: str) -> SimpleNamespace | None:
    profile = _one("profiles", {"id": uid})
    return _principal(profile) if profile else None


def create_or_update_user(uid: str, email: str, display_name: str) -> SimpleNamespace:
    client = get_supabase_client()
    profile = _one("profiles", {"id": uid})
    now = datetime.now(timezone.utc).isoformat()
    if profile:
        response = (
            client.table("profiles")
            .update({"email": email, "display_name": display_name, "updated_at": now})
            .eq("id", uid)
            .select("*")
            .execute()
        )
    else:
        response = client.table("profiles").insert(
            {"id": uid, "email": email, "display_name": display_name, "role": "ANALYST", "is_active": True}
        ).select("*").execute()
    rows = response.data or []
    if not rows:
        raise RuntimeError("The Supabase profile could not be synchronized.")
    return _principal(rows[0])


def check_database() -> None:
    get_supabase_client().table("profiles").select("id").limit(1).execute()


def _translate_fields(fields: dict[str, Any]) -> dict[str, Any]:
    names = {
        "originalFilename": "original_filename",
        "fileSize": "file_size",
        "rowCount": "row_count",
        "columnCount": "column_count",
        "storagePath": "storage_path",
        "sourcePreparationId": "source_preparation_id",
        "sourceFilename": "source_filename",
        "sourceStoragePath": "source_storage_path",
        "outputStoragePath": "output_storage_path",
        "metadata": "metadata_json",
        "plan": "plan_json",
        "history": "history_json",
    }
    return {names.get(key, key): value for key, value in fields.items()}


def create_dataset(owner_id: str, fields: dict[str, Any], dataset_id: str | None = None) -> SimpleNamespace:
    payload = _translate_fields(fields)
    payload.update({"id": dataset_id or str(uuid4()), "user_id": owner_id})
    response = get_supabase_client().table("datasets").insert(payload).select("*").execute()
    if not response.data:
        raise RuntimeError("The dataset record could not be saved.")
    return _record("datasets", response.data[0])


def get_dataset(dataset_id: str, owner_id: str, allow_admin: bool = False) -> SimpleNamespace | None:
    filters = {"id": dataset_id}
    if not allow_admin:
        filters["user_id"] = owner_id
    row = _one("datasets", filters)
    return _record("datasets", row) if row else None


def list_datasets(owner_id: str, offset: int, limit: int) -> tuple[list[SimpleNamespace], int]:
    response = (
        get_supabase_client()
        .table("datasets")
        .select("*", count="exact")
        .eq("user_id", owner_id)
        .order("created_at", desc=True)
        .range(max(offset, 0), max(offset, 0) + limit - 1)
        .execute()
    )
    return [_record("datasets", row) for row in response.data or []], int(response.count or 0)


def delete_dataset(dataset_id: str) -> None:
    get_supabase_client().table("datasets").delete().eq("id", dataset_id).execute()


def update_dataset(dataset_id: str, owner_id: str, **fields: Any) -> None:
    payload = _translate_fields(fields)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    response = (
        get_supabase_client()
        .table("datasets")
        .update(payload)
        .eq("id", dataset_id)
        .eq("user_id", owner_id)
        .select("id")
        .execute()
    )
    if not response.data:
        raise ValueError("Dataset not found for this owner.")


def create_analysis(owner_id: str, dataset_id: str, question: str) -> SimpleNamespace:
    payload = {
        "user_id": owner_id,
        "dataset_id": dataset_id,
        "question": question,
        "status": "PROCESSING",
    }
    response = get_supabase_client().table("analyses").insert(payload).select("*").execute()
    return _record("analyses", response.data[0])


def update_analysis(analysis_id: str, **fields: Any) -> None:
    payload = dict(fields)
    if "result_json" in payload:
        payload["result_json"] = payload.pop("result_json")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    get_supabase_client().table("analyses").update(payload).eq("id", analysis_id).execute()


def list_analyses(owner_id: str, dataset_id: str) -> list[SimpleNamespace]:
    response = (
        get_supabase_client()
        .table("analyses")
        .select("*")
        .eq("user_id", owner_id)
        .eq("dataset_id", dataset_id)
        .order("created_at")
        .execute()
    )
    return [_record("analyses", row) for row in response.data or []]


def latest_analysis_results(owner_id: str, dataset_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return [
        row.result_json
        for row in reversed(list_analyses(owner_id, dataset_id))
        if row.status == "COMPLETED"
    ][:limit]


def create_report(owner_id: str, dataset_id: str, title: str, content: str) -> SimpleNamespace:
    response = get_supabase_client().table("reports").insert(
        {"user_id": owner_id, "dataset_id": dataset_id, "title": title, "content": content}
    ).select("*").execute()
    return _record("reports", response.data[0])


def list_reports(owner_id: str, offset: int, limit: int) -> list[SimpleNamespace]:
    response = (
        get_supabase_client()
        .table("reports")
        .select("*")
        .eq("user_id", owner_id)
        .order("created_at", desc=True)
        .range(max(offset, 0), max(offset, 0) + limit - 1)
        .execute()
    )
    return [_record("reports", row) for row in response.data or []]


def get_report(report_id: str, owner_id: str) -> SimpleNamespace | None:
    row = _one("reports", {"id": report_id, "user_id": owner_id})
    return _record("reports", row) if row else None


def create_preparation(owner_id: str, fields: dict[str, Any], preparation_id: str | None = None) -> SimpleNamespace:
    payload = _translate_fields(fields)
    payload.update({"id": preparation_id or str(uuid4()), "user_id": owner_id})
    response = get_supabase_client().table("structuring_jobs").insert(payload).select("*").execute()
    return _record("structuring_jobs", response.data[0])


def get_preparation(preparation_id: str, owner_id: str) -> SimpleNamespace | None:
    row = _one("structuring_jobs", {"id": preparation_id, "user_id": owner_id})
    return _record("structuring_jobs", row) if row else None


def update_preparation(preparation_id: str, **fields: Any) -> None:
    payload = _translate_fields(fields)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    get_supabase_client().table("structuring_jobs").update(payload).eq("id", preparation_id).execute()


def delete_preparation(preparation_id: str) -> None:
    get_supabase_client().table("structuring_jobs").delete().eq("id", preparation_id).execute()


def find_dataset_by_preparation(owner_id: str, preparation_id: str) -> SimpleNamespace | None:
    row = _one("datasets", {"user_id": owner_id, "source_preparation_id": preparation_id})
    return _record("datasets", row) if row else None