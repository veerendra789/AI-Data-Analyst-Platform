from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.datasets import settings as dataset_settings
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.services.profiling_service import ProfilingError, detect_anomalies, profile_dataframe


TEST_ENGINE = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def reset_database(tmp_path, monkeypatch):
    Base.metadata.drop_all(TEST_ENGINE)
    Base.metadata.create_all(TEST_ENGINE)
    monkeypatch.setattr(dataset_settings, "upload_directory", str(tmp_path))

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
    client.post("/api/auth/register", json={"name": "Profiler", "email": email, "password": "correct-horse-battery"})
    return client.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery"}).json()["access_token"]


def upload(client: TestClient, token: str, content: bytes) -> int:
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("profile.csv", content, "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_profile_dataframe_covers_quality_statistics_and_edge_types():
    frame = pd.DataFrame(
        {
            "value": [1, 2, 2, 100, None],
            "category": ["a", "a", "b", "b", "b"],
            "event_date": ["2025-01-01", "bad-date", "2025-01-03", "2025-01-04", "2025-01-05"],
        }
    )

    profile = profile_dataframe(frame)

    assert profile["summary"]["row_count"] == 5
    assert profile["summary"]["column_count"] == 3
    assert profile["summary"]["missing_values"] == 1
    assert profile["summary"]["numeric_columns"] == ["value"]
    assert profile["summary"]["categorical_columns"] == ["category"]
    assert profile["summary"]["date_columns"] == ["event_date"]
    assert profile["numeric_statistics"]["value"]["mean"] == 26.25
    assert profile["numeric_statistics"]["value"]["median"] == 2.0
    assert profile["categorical_summaries"]["category"]["top_categories"][0] == {"value": "b", "count": 3}


def test_profile_edge_cases_are_safe():
    assert profile_dataframe(pd.DataFrame({"only": ["a", "b", "a"]}))["numeric_statistics"] == {}
    assert profile_dataframe(pd.DataFrame({"only": [1, 1, 1]}))["distributions"]["only"] == []
    assert profile_dataframe(pd.DataFrame({"only": [1, 1, 1]}))["outliers"]["only"]["count"] == 0
    assert profile_dataframe(pd.DataFrame())["summary"]["row_count"] == 0


def test_anomaly_detection_handles_small_and_constant_data(tmp_path):
    constant_path = Path(tmp_path) / "constant.csv"
    pd.DataFrame({"value": [1, 1, 1]}).to_csv(constant_path, index=False)
    result = detect_anomalies(str(constant_path), "value", 0.05)
    assert result["number_of_anomalies"] == 0

    with pytest.raises(ProfilingError):
        detect_anomalies(str(constant_path), "missing", 0.05)


def test_eda_endpoint_handles_small_categorical_duplicate_and_large_values(client):
    cases = [
        b"only\na\nb\n",
        b"a,b\n1,2\n1,2\n",
        b"a,b\n1,999999999999999999999999\n",
    ]
    for index, content in enumerate(cases):
        token = token_for(client, f"eda-{index}@example.com")
        dataset_id = upload(client, token, content)
        response = client.post(f"/api/analysis/eda/{dataset_id}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        result = response.json()
        assert result["dataset_id"] == dataset_id
        assert "numeric_statistics" in result
        assert "categorical_summaries" in result
        assert "outliers" in result


def test_eda_rejects_unauthorized_dataset(client):
    owner = token_for(client, "eda-owner@example.com")
    other = token_for(client, "eda-other@example.com")
    dataset_id = upload(client, owner, b"value\n1\n2\n3\n4\n5\n")

    response = client.post(f"/api/analysis/eda/{dataset_id}", headers={"Authorization": f"Bearer {other}"})

    assert response.status_code == 404


def test_anomaly_endpoint_returns_structured_anomalies(client):
    token = token_for(client, "anomaly@example.com")
    dataset_id = upload(client, token, b"value,label\n1,a\n2,a\n3,b\n4,b\n5,c\n1000,c\n")

    response = client.post(
        f"/api/analysis/anomalies/{dataset_id}",
        json={"column": "value"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["model"] == "IsolationForest"
    assert result["column"] == "value"
    assert result["number_of_anomalies"] >= 1
    assert result["relevant_columns"] == ["value"]
    assert all("anomaly_score" in record for record in result["anomaly_records"])


def test_anomaly_endpoint_handles_constant_and_categorical_data(client):
    token = token_for(client, "tiny-anomaly@example.com")
    constant_id = upload(client, token, b"value\n1\n1\n")
    categorical_id = upload(client, token, b"label\na\nb\nc\nd\ne\n")

    constant_response = client.post(
        f"/api/analysis/anomalies/{constant_id}", json={"column": "value"}, headers={"Authorization": f"Bearer {token}"}
    )
    categorical_response = client.post(
        f"/api/analysis/anomalies/{categorical_id}", json={"column": "label"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert constant_response.status_code == 200
    assert constant_response.json()["number_of_anomalies"] == 0
    assert categorical_response.status_code == 200
    assert categorical_response.json()["number_of_anomalies"] == 0
