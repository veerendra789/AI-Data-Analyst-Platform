import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.datasets import settings as dataset_settings
from app.core.database import get_db
from app.core.redis import clear_memory, make_cache_key, normalize_text
from app.main import app
from app.models import Base
from app.services import job_service


ENGINE = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


def register(client: TestClient, email: str) -> str:
    client.post("/api/auth/register", json={"name": "Report User", "email": email, "password": "correct-horse-battery"})
    return client.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery"}).json()["access_token"]


def setup_function():
    Base.metadata.drop_all(ENGINE)
    Base.metadata.create_all(ENGINE)
    clear_memory()
    dataset_settings.upload_directory = ""


def teardown_function():
    app.dependency_overrides.clear()


def client_with_database(tmp_path):
    dataset_settings.upload_directory = str(tmp_path)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def upload(client: TestClient, token: str, content: bytes = b"date,region,revenue\n2025-01-01,North,10\n2025-02-01,South,20\n2025-03-01,North,30\n") -> int:
    response = client.post("/api/datasets/upload", files={"file": ("sales.csv", content, "text/csv")}, headers={"Authorization": f"Bearer {token}"})
    return response.json()["id"]


def test_report_generation_contains_grounded_sections(tmp_path):
    client = client_with_database(tmp_path)
    token = register(client, "report@example.com")
    dataset_id = upload(client, token)

    response = client.post("/api/reports/generate", json={"dataset_id": dataset_id, "title": "Sales report"}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    content = __import__("json").loads(response.json()["content"])
    assert content["dataset_overview"]["rows"] == 3
    assert content["data_quality"]["missing_values"] == 0
    assert content["forecast"]["target_column"] == "revenue"
    assert content["ai_insights"] == []
    assert {"executive_summary", "important_metrics", "trends", "anomalies", "major_findings"}.issubset(content)


def test_cache_keys_are_normalized_and_isolated():
    assert make_cache_key("analysis", 1, 2, normalize_text("What is revenue?")) == make_cache_key("analysis", 1, 2, normalize_text("what   is revenue?"))
    assert make_cache_key("analysis", 1, 2, "what is revenue?") != make_cache_key("analysis", 2, 2, "what is revenue?")
    assert make_cache_key("analysis", 1, 2, "what is revenue?") != make_cache_key("analysis", 1, 3, "what is revenue?")


def test_analysis_cache_hit_and_miss(tmp_path, monkeypatch):
    client = client_with_database(tmp_path)
    token = register(client, "cache@example.com")
    dataset_id = upload(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    from app.api import analysis

    original_execute = analysis.query_service.execute
    calls = {"count": 0}

    def counted_execute(file_path, sql):
        calls["count"] += 1
        return original_execute(file_path, sql)

    monkeypatch.setattr(analysis.query_service, "execute", counted_execute)
    first = client.post("/api/analysis/query", json={"dataset_id": dataset_id, "question": "What is the total revenue?"}, headers=headers)
    second = client.post("/api/analysis/query", json={"dataset_id": dataset_id, "question": "  what   is the TOTAL revenue?  "}, headers=headers)
    third = client.post("/api/analysis/query", json={"dataset_id": dataset_id, "question": "Show the top revenue values"}, headers=headers)

    assert first.status_code == second.status_code == third.status_code == 200
    assert calls["count"] == 2
    assert second.json() == first.json()


def test_background_job_success_and_owner_isolation(tmp_path):
    client = client_with_database(tmp_path)
    owner_token = register(client, "job-owner@example.com")
    other_token = register(client, "job-other@example.com")
    dataset_id = upload(client, owner_token)

    response = client.post("/api/reports/jobs", json={"dataset_id": dataset_id}, headers={"Authorization": f"Bearer {owner_token}"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert client.get(f"/api/reports/jobs/{job_id}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404

    for _ in range(100):
        status = client.get(f"/api/reports/jobs/{job_id}", headers={"Authorization": f"Bearer {owner_token}"}).json()
        if status["status"] == "COMPLETED":
            assert status["result"]["dataset_id"] == dataset_id
            break
        time.sleep(0.1)
    else:
        raise AssertionError(f"report job did not complete: {status}")


def test_background_job_failure_hides_exception(tmp_path, monkeypatch):
    client = client_with_database(tmp_path)
    token = register(client, "failed-job@example.com")
    dataset_id = upload(client, token)
    monkeypatch.setattr("app.api.reports.submit", lambda function, owner_id: job_service.Job("failed", owner_id, "FAILED", error="The background operation could not be completed."))

    response = client.post("/api/reports/jobs", json={"dataset_id": dataset_id}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 202
    assert response.json()["status"] == "FAILED"
    assert "traceback" not in str(response.json()).lower()


def test_report_rate_limit_and_error_envelope(tmp_path, monkeypatch):
    client = client_with_database(tmp_path)
    token = register(client, "limited@example.com")
    dataset_id = upload(client, token)
    monkeypatch.setattr("app.core.limits.increment_with_expiry", lambda key, ttl: 11)

    response = client.post("/api/reports/generate", json={"dataset_id": dataset_id}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert response.json()["error"]["message"] == response.json()["detail"]
