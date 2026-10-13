from __future__ import annotations

import re
from pathlib import Path
from tempfile import gettempdir

from app.core.supabase import get_supabase_client


BUCKET = "datasets"


def object_path(owner_id: str, collection: str, document_id: str, filename: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", owner_id):
        raise ValueError("The Supabase user ID cannot be used as a Storage path segment.")
    safe_collection = re.sub(r"[^a-z0-9_-]", "_", collection.lower())
    safe_name = Path(filename).name
    return f"{safe_collection}/{owner_id}/{document_id}/{safe_name}"


def upload_file(local_path: Path, storage_path: str) -> None:
    get_supabase_client().storage.from_(BUCKET).upload(
        storage_path,
        local_path.read_bytes(),
        {"content-type": "text/csv", "upsert": "false"},
    )


def download_file(storage_path: str, owner_id: str, document_id: str) -> Path:
    safe_owner = re.sub(r"[^A-Za-z0-9_-]", "_", owner_id)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", document_id)
    local_path = Path(gettempdir()) / "ai-data-analyst" / safe_owner / f"{safe_id}.csv"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    content = get_supabase_client().storage.from_(BUCKET).download(storage_path)
    local_path.write_bytes(content)
    return local_path


def delete_file(storage_path: str) -> None:
    get_supabase_client().storage.from_(BUCKET).remove([storage_path])