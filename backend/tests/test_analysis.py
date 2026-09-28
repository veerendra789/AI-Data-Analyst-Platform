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
from app.services.sql_validator import SqlValidationError, validate_read_only_sql
from app.services import llm_provider


TEST_ENGINE = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def reset_database(tmp_path, monkeypatch):
    Base.metadata.drop_all(TEST_ENGINE)
    Base.metadata.create_all(TEST_ENGINE)
    monkeypatch.setattr(dataset_settings, "upload_directory", str(tmp_path))
    monkeypatch.setattr(dataset_settings, "max_upload_size", 1024 * 1024)

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


def token_for(client: TestClient, email: str) -> str:
    client.post("/api/auth/register", json={"name": "Analyst", "email": email, "password": "correct-horse-battery"})
    return client.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery"}).json()["access_token"]


def test_sql_validator_accepts_read_only_query():
    assert validate_read_only_sql("SELECT product, SUM(revenue) FROM dataset_data GROUP BY product")


@pytest.mark.parametrize("sql", [
    "DELETE FROM dataset_data",
    "DROP TABLE dataset_data",
    "SELECT * FROM read_csv_auto('/tmp/secret.csv')",
    "SELECT * FROM '/tmp/secret.csv'",
    "SELECT 1; DELETE FROM dataset_data",
    "UPDATE dataset_data SET revenue = 0",
])
def test_sql_validator_rejects_unsafe_queries(sql):
    with pytest.raises(SqlValidationError):
        validate_read_only_sql(sql)


def test_complete_analysis_endpoint_returns_real_results_and_history(client):
    token = token_for(client, "analysis@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    csv_content = b"product,region,revenue\nWidget,North,100\nGadget,South,250\nWidget,South,150\nCable,North,75\nPhone,West,300\n"
    upload = client.post("/api/datasets/upload", files={"file": ("sales.csv", csv_content, "text/csv")}, headers=headers)
    dataset_id = upload.json()["id"]

    response = client.post(
        "/api/analysis/query",
        json={"dataset_id": dataset_id, "question": "What are the top 5 products by revenue?"},
        headers=headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["sql"].upper().startswith("SELECT")
    assert "DELETE" not in result["sql"].upper()
    assert result["columns"] == ["product", "revenue_total"]
    assert result["rows"][0] == {"product": "Phone", "revenue_total": 300}
    assert result["chart"]["type"] == "bar"
    assert result["chart"]["x_axis"] == "product"
    assert result["chart"]["y_axis"] == "revenue_total"
    assert "Phone" in result["insight"]
    assert result["execution_time_ms"] >= 0

    history = client.get(f"/api/analysis/history/{dataset_id}", headers=headers)
    assert history.status_code == 200
    history_item = history.json()[0]
    assert history_item["question"] == "What are the top 5 products by revenue?"
    assert history_item["sql"] == result["sql"]
    assert history_item["rows"] == result["rows"]
    assert history_item["insight"] == result["insight"]
    assert history_item["status"] == "COMPLETED"


def test_analysis_rejects_unauthorized_dataset(client):
    owner_token = token_for(client, "owner-analysis@example.com")
    other_token = token_for(client, "other-analysis@example.com")
    upload = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", b"product,revenue\nWidget,10\n", "text/csv")},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    response = client.post(
        "/api/analysis/query",
        json={"dataset_id": upload.json()["id"], "question": "What is the total revenue?"},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


def test_analysis_returns_empty_result_with_grounded_insight(client):
    token = token_for(client, "empty-result@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    upload = client.post("/api/datasets/upload", files={"file": ("sales.csv", b"product,revenue\nWidget,10\n", "text/csv")}, headers=headers)

    response = client.post(
        "/api/analysis/query",
        json={"dataset_id": upload.json()["id"], "question": "Show products where revenue is greater than 1000000"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["rows"] == []
    assert "no matching rows" in response.json()["insight"].lower()


def test_invalid_provider_response_is_rejected(client, monkeypatch):
    class InvalidProvider:
        def generate_sql(self, question, schema):
            raise ValueError("invalid structured response")

    monkeypatch.setattr(llm_provider, "get_provider", lambda: InvalidProvider())
    token = token_for(client, "invalid-provider@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    upload = client.post("/api/datasets/upload", files={"file": ("sales.csv", b"product,revenue\nWidget,10\n", "text/csv")}, headers=headers)

    response = client.post("/api/analysis/query", json={"dataset_id": upload.json()["id"], "question": "What is revenue?"}, headers=headers)

    assert response.status_code == 502
    assert "invalid structured response" in response.json()["detail"]


def test_dangerous_provider_sql_never_executes(client, monkeypatch):
    class DangerousProvider:
        def generate_sql(self, question, schema):
            return llm_provider.GeneratedAnalysis(sql="DROP TABLE dataset_data", chart_type="table")

    monkeypatch.setattr(llm_provider, "get_provider", lambda: DangerousProvider())
    token = token_for(client, "dangerous-provider@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    upload = client.post("/api/datasets/upload", files={"file": ("sales.csv", b"product,revenue\nWidget,10\n", "text/csv")}, headers=headers)

    response = client.post("/api/analysis/query", json={"dataset_id": upload.json()["id"], "question": "Destroy data"}, headers=headers)

    assert response.status_code == 422
