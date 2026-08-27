from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest-only"
os.environ["DEFAULT_ADMIN_EMAIL"] = "admin@example.com"
os.environ["DEFAULT_ADMIN_PASSWORD"] = "admin123"

from jobflow.api.main import app  # noqa: E402
from jobflow.db import get_db  # noqa: E402
from jobflow.db.models import Base  # noqa: E402

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    from jobflow.services.bootstrap import ensure_default_admin

    db = TestingSessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin123"})
    if resp.status_code != 200:
        client.post(
            "/api/auth/register",
            json={"email": "admin@example.com", "password": "admin123", "full_name": "Admin"},
        )
        resp = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_and_login(client: TestClient):
    resp = client.post(
        "/api/auth/register",
        json={"email": "user1@example.com", "password": "secret12", "full_name": "User One"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    login = client.post("/api/auth/login", json={"email": "user1@example.com", "password": "secret12"})
    assert login.status_code == 200


def test_protected_route_requires_auth(client: TestClient):
    assert client.get("/api/jobs").status_code == 401


def test_ingest_and_list_jobs(client: TestClient, auth_headers: dict):
    ingest = client.post(
        "/api/ingest/webhook",
        headers=auth_headers,
        json={
            "source": "greenhouse",
            "id": "test-job-1",
            "title": "Backend Engineer",
            "company": {"name": "TestCo"},
            "description": "Python FastAPI PostgreSQL Docker AWS",
            "requirements": ["Python", "FastAPI", "PostgreSQL"],
        },
    )
    assert ingest.status_code == 200
    jobs = client.get("/api/jobs", headers=auth_headers).json()
    assert len(jobs) >= 1


def test_dashboard_stats(client: TestClient, auth_headers: dict):
    stats = client.get("/api/dashboard/stats", headers=auth_headers).json()
    assert "total_jobs" in stats
    assert "awaiting_approval" in stats
