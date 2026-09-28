import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.main import app
from app.models import Base
from app.models import User, UserRole
from app.core.security import settings


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(TEST_ENGINE)
    Base.metadata.create_all(TEST_ENGINE)

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


def registration_payload(email: str = "analyst@example.com"):
    return {"name": "Test Analyst", "email": email, "password": "correct-horse-battery"}


def test_successful_registration(client):
    response = client.post("/api/auth/register", json=registration_payload())

    assert response.status_code == 201
    assert response.json()["email"] == "analyst@example.com"
    assert response.json()["role"] == "ANALYST"
    assert "password" not in response.json()


def test_duplicate_email(client):
    client.post("/api/auth/register", json=registration_payload())

    response = client.post("/api/auth/register", json=registration_payload("ANALYST@example.com"))

    assert response.status_code == 409
    assert response.json()["detail"] == "Email is already registered."


def test_successful_login(client):
    client.post("/api/auth/register", json=registration_payload())

    response = client.post(
        "/api/auth/login",
        json={"email": "analyst@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_wrong_password(client):
    client.post("/api/auth/register", json=registration_payload())

    response = client.post(
        "/api/auth/login",
        json={"email": "analyst@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_invalid_token(client):
    response = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer definitely-not-a-token"}
    )

    assert response.status_code == 401


def test_expired_token(client):
    token = jwt.encode(
        {"sub": "1", "role": "ANALYST", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm="HS256",
    )

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_protected_endpoint_without_authentication(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_user_profile_endpoint(client):
    client.post("/api/auth/register", json=registration_payload())
    login_response = client.post(
        "/api/auth/login",
        json={"email": "analyst@example.com", "password": "correct-horse-battery"},
    )
    token = login_response.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["name"] == "Test Analyst"
    assert response.json()["role"] == "ANALYST"


def test_role_authorization_for_admin_endpoint(client):
    analyst_token = client.post("/api/auth/login", json={"email": "missing@example.com", "password": "x"})
    assert analyst_token.status_code == 401
    client.post("/api/auth/register", json=registration_payload())
    analyst_token = client.post(
        "/api/auth/login", json={"email": "analyst@example.com", "password": "correct-horse-battery"}
    ).json()["access_token"]
    assert client.get("/api/auth/admin-check", headers={"Authorization": f"Bearer {analyst_token}"}).status_code == 403

    db = TestingSessionLocal()
    user = db.get(User, 1)
    user.role = UserRole.ADMIN
    db.commit()
    db.close()
    admin_token = client.post(
        "/api/auth/login", json={"email": "analyst@example.com", "password": "correct-horse-battery"}
    ).json()["access_token"]
    response = client.get("/api/auth/admin-check", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"
