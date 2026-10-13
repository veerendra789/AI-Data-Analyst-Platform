import pytest
from fastapi.testclient import TestClient

from app.core.supabase import SupabaseUnavailable, get_supabase_client
from app.main import app
def token(uid: str) -> str:
    return f"test-token:{uid}|{uid}@example.com"


def profile_by_id(supabase_test_services, user_id: str) -> dict:
    return next(row for row in supabase_test_services.tables["profiles"] if row["id"] == user_id)


def test_profile_sync_creates_uid_document_with_safe_default_role(supabase_test_services):
    client = TestClient(app)
    response = client.post(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {token('analyst-uid')}"},
        json={"displayName": "Analyst User"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "analyst-uid"
    assert response.json()["name"] == "Analyst User"
    assert response.json()["role"] == "ANALYST"
    profile = profile_by_id(supabase_test_services, "analyst-uid")
    assert profile["id"] == "analyst-uid"
    assert profile["is_active"] is True
    assert profile["email"] == "analyst-uid@example.com"


def test_supabase_client_rejects_unexpected_project(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://another-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "placeholder-not-a-secret")

    with pytest.raises(SupabaseUnavailable, match="SUPABASE_URL must target project azfaieuwnhgjbedfeybl"):
        get_supabase_client()


def test_profile_sync_uses_verified_identity_not_client_uid_or_role(supabase_test_services):
    response = TestClient(app).post(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {token('verified-uid')}"},
        json={"displayName": "Verified", "uid": "attacker-uid", "role": "ADMIN"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "verified-uid"
    assert response.json()["role"] == "ANALYST"
    assert all(row["id"] != "attacker-uid" for row in supabase_test_services.tables["profiles"])


def test_profile_sync_is_idempotent_and_preserves_server_role(supabase_test_services):
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token('admin-uid')}"}
    first = client.post("/api/auth/profile", headers=headers, json={"displayName": "First"})
    profile_by_id(supabase_test_services, "admin-uid")["role"] = "ADMIN"
    second = client.post("/api/auth/profile", headers=headers, json={"displayName": "Updated"})

    assert first.status_code == second.status_code == 200
    assert second.json()["name"] == "Updated"
    assert second.json()["role"] == "ADMIN"


def test_me_requires_verified_token_and_provisions_profile(supabase_test_services):
    client = TestClient(app)
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    provisioned = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token('provisioned-uid')}"})
    assert provisioned.status_code == 200
    assert provisioned.json()["id"] == "provisioned-uid"
    assert profile_by_id(supabase_test_services, "provisioned-uid")["role"] == "ANALYST"

    client.post(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {token('analyst-uid')}"},
        json={"displayName": "Analyst"},
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token('analyst-uid')}"})

    assert response.status_code == 200
    assert response.json()["id"] == "analyst-uid"


def test_inactive_profile_is_rejected(supabase_test_services):
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token('inactive-uid')}"}
    client.post("/api/auth/profile", headers=headers, json={"displayName": "Inactive"})
    profile_by_id(supabase_test_services, "inactive-uid")["is_active"] = False

    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 401


def test_admin_role_is_server_controlled(supabase_test_services):
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token('analyst-uid')}"}
    client.post("/api/auth/profile", headers=headers, json={"displayName": "Analyst"})
    assert client.get("/api/auth/admin-check", headers=headers).status_code == 403

    profile_by_id(supabase_test_services, "analyst-uid")["role"] = "ADMIN"
    assert client.get("/api/auth/admin-check", headers=headers).json()["role"] == "ADMIN"