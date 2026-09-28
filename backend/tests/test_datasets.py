from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.datasets import settings as dataset_settings
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.models import User, UserRole


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def reset_database(tmp_path, monkeypatch):
    Base.metadata.drop_all(TEST_ENGINE)
    Base.metadata.create_all(TEST_ENGINE)
    monkeypatch.setattr(dataset_settings, "upload_directory", str(tmp_path))
    monkeypatch.setattr(dataset_settings, "max_upload_size", 1024)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def register(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"name": "Dataset User", "email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct-horse-battery"},
    )
    return login.json()["access_token"]


def csv_file(content: bytes = b"product,region,revenue\nWidget,North,10\nGadget,South,20\n"):
    return {"file": ("sales.csv", content, "text/csv")}


def test_valid_csv_upload_database_and_preview_workflow(client):
    token = register(client, "owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    upload = client.post("/api/datasets/upload", files=csv_file(), headers=headers)

    assert upload.status_code == 201
    dataset = upload.json()
    assert dataset["row_count"] == 2
    assert dataset["column_count"] == 3
    assert dataset["status"] == "COMPLETED"
    assert [column["column_name"] for column in dataset["columns"]] == ["product", "region", "revenue"]
    assert Path(dataset["file_path"]).exists() if "file_path" in dataset else True

    listing = client.get("/api/datasets", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    preview = client.get(f"/api/datasets/{dataset['id']}/preview", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["rows"][0]["product"] == "Widget"
    assert preview.json()["returned_rows"] == 2


def test_invalid_file_is_rejected(client):
    token = register(client, "invalid@example.com")

    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.txt", b"a,b\n1,2\n", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "Only CSV" in response.json()["detail"]


def test_empty_csv_is_rejected(client):
    token = register(client, "empty@example.com")

    response = client.post("/api/datasets/upload", files=csv_file(b""), headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "filename,content_type,content,expected",
    [
        ("sales.csv", "text/csv", b"", "empty"),
        ("sales.csv", "text/csv", b"product,revenue\n", "at least one data row"),
        ("sales.csv", "text/csv", b"product,revenue\nWidget", "same number of columns"),
        ("sales.csv", "text/csv", b"product,revenue\n\xff\xfe", "UTF-8"),
        ("sales.csv", "text/csv", b",revenue\nWidget,10\n", "unique, non-empty"),
    ],
)
def test_invalid_csv_variants_are_rejected(client, filename, content_type, content, expected):
    token = register(client, f"invalid-{abs(hash(expected))}@example.com")

    response = client.post(
        "/api/datasets/upload",
        files={"file": (filename, content, content_type)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert expected.lower() in response.json()["detail"].lower()


def test_invalid_mime_type_is_rejected(client):
    token = register(client, "missing-mime@example.com")

    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", b"product,revenue\nWidget,10\n", "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_path_traversal_filename_is_normalized_and_server_filename_is_unique(client):
    token = register(client, "path@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    content = b"product,revenue\nWidget,10\n"

    first = client.post("/api/datasets/upload", files={"file": ("..\\nested\\sales.csv", content, "text/csv")}, headers=headers)
    second = client.post("/api/datasets/upload", files={"file": ("..\\nested\\sales.csv", content, "text/csv")}, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["original_filename"] == "sales.csv"
    assert second.json()["original_filename"] == "sales.csv"
    stored_files = list(Path(dataset_settings.upload_directory).glob("*.csv"))
    assert len(stored_files) == 2
    assert stored_files[0].name != stored_files[1].name


def test_large_file_is_rejected(client):
    token = register(client, "large@example.com")
    large_content = b"value\n" + b"x\n" * 600

    response = client.post("/api/datasets/upload", files=csv_file(large_content), headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 413


def test_dataset_is_not_accessible_to_another_user(client):
    owner_token = register(client, "first@example.com")
    other_token = register(client, "second@example.com")
    upload = client.post("/api/datasets/upload", files=csv_file(), headers={"Authorization": f"Bearer {owner_token}"})
    dataset_id = upload.json()["id"]

    response = client.get(f"/api/datasets/{dataset_id}", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 404


def test_admin_can_access_another_users_dataset(client):
    owner_token = register(client, "admin-owner@example.com")
    admin_token = register(client, "admin@example.com")
    owner_upload = client.post(
        "/api/datasets/upload",
        files=csv_file(),
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    dataset_id = owner_upload.json()["id"]
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.email == "admin@example.com").one()
    admin.role = UserRole.ADMIN
    db.commit()
    db.close()
    admin_token = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "correct-horse-battery"},
    ).json()["access_token"]

    response = client.get(
        f"/api/datasets/{dataset_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


def test_dataset_deletion_removes_metadata_and_file(client):
    token = register(client, "delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    upload = client.post("/api/datasets/upload", files=csv_file(), headers=headers)
    dataset_id = upload.json()["id"]
    stored_files = list(Path(dataset_settings.upload_directory).glob("*.csv"))
    assert len(stored_files) == 1

    response = client.delete(f"/api/datasets/{dataset_id}", headers=headers)

    assert response.status_code == 204
    assert not stored_files[0].exists()
    assert client.get(f"/api/datasets/{dataset_id}", headers=headers).status_code == 404
