from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.datasets import settings as dataset_settings
from app.main import app
from tests.supabase_test_utils import user_token


@pytest.fixture(autouse=True)
def reset_database(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_settings, "upload_directory", str(tmp_path))
    monkeypatch.setattr(dataset_settings, "max_upload_size", 1024)


@pytest.fixture
def client():
    return TestClient(app)


def register(client: TestClient, email: str, role: str = "ANALYST") -> str:
    return user_token(email, role)


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


def test_direct_storage_upload_is_owner_scoped_and_finalizes_metadata(client, supabase_test_services):
    owner = register(client, "direct-owner@example.com")
    other = register(client, "direct-other@example.com")
    content = b"product,revenue\nWidget,10\n"
    initialized = client.post(
        "/api/datasets/upload/init",
        json={"filename": "sales.csv", "content_type": "text/csv", "file_size": len(content)},
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert initialized.status_code == 201
    upload = initialized.json()
    assert upload["storage_path"].startswith("datasets/")
    supabase_test_services.objects[upload["storage_path"]] = content

    denied = client.post(
        "/api/datasets/upload/complete",
        json={"dataset_id": upload["dataset_id"]},
        headers={"Authorization": f"Bearer {other}"},
    )
    assert denied.status_code == 404

    completed = client.post(
        "/api/datasets/upload/complete",
        json={"dataset_id": upload["dataset_id"]},
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert completed.status_code == 201
    assert completed.json()["row_count"] == 1
    assert completed.json()["status"] == "COMPLETED"


def test_direct_storage_upload_size_mismatch_is_discarded(client, supabase_test_services):
    owner = register(client, "mismatch-owner@example.com")
    headers = {"Authorization": f"Bearer {owner}"}
    initialized = client.post(
        "/api/datasets/upload/init",
        json={"filename": "sales.csv", "content_type": "text/csv", "file_size": 100},
        headers=headers,
    )
    upload = initialized.json()
    supabase_test_services.objects[upload["storage_path"]] = b"product,revenue\nWidget,10\n"

    response = client.post(
        "/api/datasets/upload/complete",
        json={"dataset_id": upload["dataset_id"]},
        headers=headers,
    )

    assert response.status_code == 400
    assert upload["storage_path"] not in supabase_test_services.objects
    assert client.get(f"/api/datasets/{upload['dataset_id']}", headers=headers).status_code == 404


def test_direct_storage_upload_can_be_cancelled_by_owner(client, supabase_test_services):
    owner = register(client, "cancel-owner@example.com")
    other = register(client, "cancel-other@example.com")
    headers = {"Authorization": f"Bearer {owner}"}
    initialized = client.post(
        "/api/datasets/upload/init",
        json={"filename": "sales.csv", "content_type": "text/csv", "file_size": 20},
        headers=headers,
    ).json()
    supabase_test_services.objects[initialized["storage_path"]] = b"partial"
    other_response = client.post(
        "/api/datasets/upload/cancel",
        json={"dataset_id": initialized["dataset_id"]},
        headers={"Authorization": f"Bearer {other}"},
    )
    assert other_response.status_code == 404

    response = client.post(
        "/api/datasets/upload/cancel",
        json={"dataset_id": initialized["dataset_id"]},
        headers=headers,
    )
    assert response.status_code == 204
    assert initialized["storage_path"] not in supabase_test_services.objects


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


def test_path_traversal_filename_is_normalized_and_server_filename_is_unique(client, supabase_test_services):
    token = register(client, "path@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    content = b"product,revenue\nWidget,10\n"

    first = client.post("/api/datasets/upload", files={"file": ("..\\nested\\sales.csv", content, "text/csv")}, headers=headers)
    second = client.post("/api/datasets/upload", files={"file": ("..\\nested\\sales.csv", content, "text/csv")}, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["original_filename"] == "sales.csv"
    assert second.json()["original_filename"] == "sales.csv"
    stored_objects = list(supabase_test_services.objects)
    assert len(stored_objects) == 2
    assert stored_objects[0] != stored_objects[1]


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
    admin_token = register(client, "admin@example.com", role="ADMIN")
    owner_upload = client.post(
        "/api/datasets/upload",
        files=csv_file(),
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    dataset_id = owner_upload.json()["id"]
    response = client.get(
        f"/api/datasets/{dataset_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


def test_dataset_deletion_removes_metadata_and_file(client, supabase_test_services):
    token = register(client, "delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    upload = client.post("/api/datasets/upload", files=csv_file(), headers=headers)
    dataset_id = upload.json()["id"]
    assert len(supabase_test_services.objects) == 1

    response = client.delete(f"/api/datasets/{dataset_id}", headers=headers)

    assert response.status_code == 204
    assert not supabase_test_services.objects
    assert client.get(f"/api/datasets/{dataset_id}", headers=headers).status_code == 404


def test_cross_user_isolation_comprehensive(client):
    token_a = register(client, "user_a@example.com")
    token_b = register(client, "user_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    upload_a = client.post("/api/datasets/upload", files=csv_file(b"col1,col2\n1,a\n"), headers=headers_a)
    upload_b = client.post("/api/datasets/upload", files=csv_file(b"col1,col2\n2,b\n"), headers=headers_b)
    id_a = upload_a.json()["id"]
    id_b = upload_b.json()["id"]

    # User A accesses A -> 200, User B accesses B -> 200
    assert client.get(f"/api/datasets/{id_a}", headers=headers_a).status_code == 200
    assert client.get(f"/api/datasets/{id_b}", headers=headers_b).status_code == 200

    # User A cannot access or preview B's dataset -> 404
    assert client.get(f"/api/datasets/{id_b}", headers=headers_a).status_code == 404
    assert client.get(f"/api/datasets/{id_b}/preview", headers=headers_a).status_code == 404

    # User B cannot access or preview A's dataset -> 404
    assert client.get(f"/api/datasets/{id_a}", headers=headers_b).status_code == 404
    assert client.get(f"/api/datasets/{id_a}/preview", headers=headers_b).status_code == 404

    # User A cannot delete B's dataset -> 404
    assert client.delete(f"/api/datasets/{id_b}", headers=headers_a).status_code == 404
    # User B cannot delete A's dataset -> 404
    assert client.delete(f"/api/datasets/{id_a}", headers=headers_b).status_code == 404
