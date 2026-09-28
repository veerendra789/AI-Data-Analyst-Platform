from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.data_preparation import settings as dataset_settings
from app.core.database import get_db
from app.main import app
from app.models import Base


ENGINE = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


def setup_function():
    Base.metadata.drop_all(ENGINE)
    Base.metadata.create_all(ENGINE)
    dataset_settings.upload_directory = ""


def teardown_function():
    app.dependency_overrides.clear()


def make_client(tmp_path):
    dataset_settings.upload_directory = str(tmp_path)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def token_for(client: TestClient, email: str) -> str:
    client.post("/api/auth/register", json={"name": "Prep User", "email": email, "password": "correct-horse-battery"})
    return client.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery"}).json()["access_token"]


def raw_csv():
    return {"file": ("kaggle raw.csv", b"Customer ID,Revenue,Gender,Date\n0012,\"$1,200\",Male,2025-01-01\n0012,\"$1,200\",Male,2025-01-01\n0003,500,male,03/04/2025\n", "text/csv")}


def test_complete_preparation_to_dataset_workflow(tmp_path):
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

    original_files = list(Path(tmp_path).glob("*.csv"))
    assert len(original_files) == 1
    assert b"Customer ID" in original_files[0].read_bytes()


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