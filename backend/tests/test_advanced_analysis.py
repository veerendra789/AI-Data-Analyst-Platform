import pytest
from fastapi.testclient import TestClient

from app.api.datasets import settings as dataset_settings
from app.main import app
from tests.supabase_test_utils import user_token

@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_settings, "upload_directory", str(tmp_path))

@pytest.fixture
def client(): return TestClient(app)

def token(client, email):
    return user_token(email)

def upload(client, auth):
    content = b"date,region,category,revenue\n2025-01-01,North,A,100\n2025-02-01,South,B,120\n2025-03-01,North,A,140\n2025-04-01,South,B,160\n2025-05-01,North,A,180\n"
    return client.post("/api/datasets/upload", files={"file":("sales.csv",content,"text/csv")}, headers={"Authorization":f"Bearer {auth}"}).json()["id"]

def test_forecast_returns_sorted_history_and_future(client):
    auth=token(client,"forecast@example.com"); dataset_id=upload(client,auth)
    response=client.post(f"/api/analysis/forecast/{dataset_id}",json={"date_column":"date","target_column":"revenue","periods":3},headers={"Authorization":f"Bearer {auth}"})
    body=response.json()
    assert response.status_code==200
    assert len(body["historical"])==5 and len(body["forecast"])==3
    assert body["forecast"][0]["date"] > body["historical"][-1]["date"]
    assert body["model"] == "Linear trend forecast"

def test_forecast_validates_columns_and_observations(client):
    auth=token(client,"forecast-errors@example.com"); dataset_id=upload(client,auth)
    response=client.post(f"/api/analysis/forecast/{dataset_id}",json={"date_column":"missing","target_column":"revenue"},headers={"Authorization":f"Bearer {auth}"})
    assert response.status_code==422

def test_root_cause_returns_observational_associations(client):
    auth=token(client,"root@example.com"); dataset_id=upload(client,auth)
    response=client.post(f"/api/analysis/root-cause/{dataset_id}",json={"question":"Why did sales change?","metric_column":"revenue","dimension_columns":["region","category"]},headers={"Authorization":f"Bearer {auth}"})
    body=response.json()
    assert response.status_code==200
    assert "observed" in body["observed_result"]
    assert "associated with" in {item["relationship"] for item in body["associations"]}
    assert "not proven causal" in body["caveat"]

def test_advanced_endpoints_enforce_ownership(client):
    owner=token(client,"advanced-owner@example.com"); other=token(client,"advanced-other@example.com"); dataset_id=upload(client,owner)
    response=client.post(f"/api/analysis/forecast/{dataset_id}",json={"date_column":"date","target_column":"revenue"},headers={"Authorization":f"Bearer {other}"})
    assert response.status_code==404
