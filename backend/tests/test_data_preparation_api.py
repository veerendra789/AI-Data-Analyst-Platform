from pathlib import Path

from fastapi.testclient import TestClient

from app.services.dataset_service import settings as dataset_settings
from app.main import app
from tests.supabase_test_utils import user_token


def setup_function():
    dataset_settings.upload_directory = ""


def make_client(tmp_path):
    dataset_settings.upload_directory = str(tmp_path)
    return TestClient(app)


def token_for(client: TestClient, email: str) -> str:
    return user_token(email)


def raw_csv():
    return {"file": ("kaggle raw.csv", b"Customer ID,Revenue,Gender,Date\n0012,\"$1,200\",Male,2025-01-01\n0012,\"$1,200\",Male,2025-01-01\n0003,500,male,03/04/2025\n", "text/csv")}


def test_complete_preparation_to_dataset_workflow(tmp_path, supabase_test_services):
    client = make_client(tmp_path)
    token = token_for(client, "prep-owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    analyzed = client.post("/api/data-preparation/analyze", files=raw_csv(), headers=headers)

    assert analyzed.status_code == 201, analyzed.text
    data = analyzed.json()
    prep_id = data["id"]
    assert data["overview"]["duplicate_rows"] == 1
    assert data["columns"][0]["examples"] == ["0012", "0003"]
    assert any(issue["type"] == "ambiguous_date" for issue in data["issues"])
    assert client.get(f"/api/data-preparation/{prep_id}/preview", headers=headers).json()["returned_rows"] == 3

    selected = [item["id"] for item in data["plan"] if item["type"] in {"rename_column", "remove_duplicate_rows", "parse_numeric"}]
    applied = client.post(f"/api/data-preparation/{prep_id}/apply", json={"selected_operation_ids": selected, "remove_duplicates": True}, headers=headers)

    assert applied.status_code == 200, applied.text
    assert applied.json()["comparison"]["rows_removed"] == 1
    cleaned_preview = client.get(f"/api/data-preparation/{prep_id}/preview?version=cleaned", headers=headers)
    assert cleaned_preview.status_code == 200
    assert cleaned_preview.json()["columns"] == ["customer_id", "revenue", "gender", "date_value"]
    download = client.get(f"/api/data-preparation/{prep_id}/download", headers=headers)
    assert download.status_code == 200
    assert b"customer_id,revenue,gender,date_value" in download.content

    saved = client.post(f"/api/data-preparation/{prep_id}/save", json={"name": "Prepared Kaggle Data"}, headers=headers)
    assert saved.status_code == 201, saved.text
    dataset = saved.json()
    assert dataset["source_preparation_id"] == prep_id
    assert client.get(f"/api/datasets/{dataset['id']}", headers=headers).status_code == 200
    assert client.get(f"/api/datasets/{dataset['id']}/preview", headers=headers).json()["total_rows"] == 2

    source_objects = [
        content
        for path, content in supabase_test_services.objects.items()
        if path.endswith("/source.csv")
    ]
    assert len(source_objects) == 1
    assert b"Customer ID" in source_objects[0]
    assert b"customer_id" not in source_objects[0]


def test_direct_storage_upload_analyzes_and_persists_preparation(tmp_path, supabase_test_services):
    client = make_client(tmp_path)
    token = token_for(client, "direct-prep-owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    filename, content, content_type = raw_csv()["file"]
    initialized = client.post(
        "/api/data-preparation/upload/init",
        json={"filename": filename, "content_type": content_type, "file_size": len(content)},
        headers=headers,
    )
    assert initialized.status_code == 201
    upload = initialized.json()
    supabase_test_services.objects[upload["storage_path"]] = content

    completed = client.post(
        "/api/data-preparation/upload/complete",
        json={"preparation_id": upload["preparation_id"]},
        headers=headers,
    )

    assert completed.status_code == 201, completed.text
    assert completed.json()["overview"]["duplicate_rows"] == 1
    assert completed.json()["filename"] == filename
    assert upload["storage_path"].startswith("structuringjobs/")


def test_preparation_is_owner_scoped_and_requires_auth(tmp_path):
    client = make_client(tmp_path)
    owner_token = token_for(client, "prep-first@example.com")
    other_token = token_for(client, "prep-second@example.com")
    created = client.post("/api/data-preparation/analyze", files=raw_csv(), headers={"Authorization": f"Bearer {owner_token}"})
    prep_id = created.json()["id"]

    assert client.get(f"/api/data-preparation/{prep_id}").status_code == 401
    assert client.get(f"/api/data-preparation/{prep_id}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
    assert client.delete(f"/api/data-preparation/{prep_id}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
    assert client.delete(f"/api/data-preparation/{prep_id}", headers={"Authorization": f"Bearer {owner_token}"}).status_code == 204
    assert client.get(f"/api/data-preparation/{prep_id}", headers={"Authorization": f"Bearer {owner_token}"}).status_code == 404


def test_invalid_csv_and_unapproved_operation_are_rejected(tmp_path):
    client = make_client(tmp_path)
    token = token_for(client, "prep-invalid@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    invalid = client.post("/api/data-preparation/analyze", files={"file": ("empty.csv", b"", "text/csv")}, headers=headers)
    assert invalid.status_code == 400

    created = client.post("/api/data-preparation/analyze", files=raw_csv(), headers=headers)
    prep_id = created.json()["id"]
    rejected = client.post(f"/api/data-preparation/{prep_id}/apply", json={"selected_operation_ids": ["arbitrary-code"]}, headers=headers)
    assert rejected.status_code == 400
    assert "unknown operation" in rejected.json()["detail"]