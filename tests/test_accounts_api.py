"""Tests for accounts REST endpoints — in-memory SQLite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models import (  # noqa: F401 — registers all models with Base.metadata
    AuditLog,
    MT5Agent,
    RefreshToken,
    TradingAccount,
    User,
)
from backend.db.session import get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_JWT = "test-secret-x12345678901234567890123456"
TEST_USER = {"email": "acct@example.com", "password": "secure-password-123", "display_name": "Acct User"}
TEST_ACCOUNT = {
    "label": "Demo Cent 1",
    "broker": "HFM",
    "mt5_account_number": "123456",
    "broker_currency": "Cent",
    "is_cent_account": True,
    "cent_normalization_factor": "0.01",
}


def _patch_settings(monkeypatch):
    from unittest.mock import MagicMock

    import backend.api.v1.accounts as c
    import backend.api.v1.auth as b
    import backend.services.auth as a
    ms = MagicMock()
    ms.JWT_ALGORITHM = "HS256"
    ms.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
    ms.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30
    ms.require_jwt_secret.return_value = TEST_JWT
    ms.FX_RATE_PROVIDER = None
    for mod in (a, b, c):
        monkeypatch.setattr(mod, "settings", ms)


@pytest.fixture
def client(monkeypatch):
    _patch_settings(monkeypatch)
    from backend.main import create_app
    app = create_app()
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_db] = _db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _register_and_login(client):
    client.post("/api/v1/auth/register", json=TEST_USER)
    r = client.post("/api/v1/auth/login", json={"email": TEST_USER["email"], "password": TEST_USER["password"]})
    return r.json()["access_token"]


@pytest.mark.unit
class TestAccounts:
    def test_list_empty(self, client):
        token = _register_and_login(client)
        r = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() == []

    def test_create_account(self, client):
        token = _register_and_login(client)
        r = client.post("/api/v1/accounts", json=TEST_ACCOUNT, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        d = r.json()
        assert d["label"] == "Demo Cent 1"
        assert d["is_cent_account"] is True
        assert d["trading_enabled"] is False
        assert d["idr_conversion"] == "NOT_CONFIGURED"
        assert d["cent_normalization_factor"] == "0.01"

    def test_list_after_create(self, client):
        token = _register_and_login(client)
        client.post("/api/v1/accounts", json=TEST_ACCOUNT, headers={"Authorization": f"Bearer {token}"})
        r = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_get_account(self, client):
        token = _register_and_login(client)
        create_r = client.post("/api/v1/accounts", json=TEST_ACCOUNT, headers={"Authorization": f"Bearer {token}"})
        aid = create_r.json()["id"]
        r = client.get(f"/api/v1/accounts/{aid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["id"] == aid

    def test_other_user_cannot_access_account(self, client):
        token = _register_and_login(client)
        create_r = client.post("/api/v1/accounts", json=TEST_ACCOUNT, headers={"Authorization": f"Bearer {token}"})
        aid = create_r.json()["id"]
        # Register second user
        client.post("/api/v1/auth/register", json={**TEST_USER, "email": "other@example.com"})
        r2 = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": TEST_USER["password"]})
        token2 = r2.json()["access_token"]
        r = client.get(f"/api/v1/accounts/{aid}", headers={"Authorization": f"Bearer {token2}"})
        assert r.status_code == 404

    def test_patch_label(self, client):
        token = _register_and_login(client)
        create_r = client.post("/api/v1/accounts", json=TEST_ACCOUNT, headers={"Authorization": f"Bearer {token}"})
        aid = create_r.json()["id"]
        r = client.patch(f"/api/v1/accounts/{aid}", json={"label": "Updated Label"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["label"] == "Updated Label"

    def test_delete_account(self, client):
        token = _register_and_login(client)
        create_r = client.post("/api/v1/accounts", json=TEST_ACCOUNT, headers={"Authorization": f"Bearer {token}"})
        aid = create_r.json()["id"]
        r = client.delete(f"/api/v1/accounts/{aid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204

    def test_no_auth_401(self, client):
        r = client.get("/api/v1/accounts")
        assert r.status_code == 401

    def test_invalid_factor_422(self, client):
        token = _register_and_login(client)
        r = client.post("/api/v1/accounts", json={**TEST_ACCOUNT, "cent_normalization_factor": "abc"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422

    def test_negative_factor_422(self, client):
        token = _register_and_login(client)
        r = client.post("/api/v1/accounts", json={**TEST_ACCOUNT, "cent_normalization_factor": "-0.01"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422

    def test_patch_trading_enabled(self, client):
        token = _register_and_login(client)
        create_r = client.post("/api/v1/accounts", json=TEST_ACCOUNT, headers={"Authorization": f"Bearer {token}"})
        aid = create_r.json()["id"]
        assert create_r.json()["trading_enabled"] is False

        r = client.patch(f"/api/v1/accounts/{aid}", json={"trading_enabled": True}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["trading_enabled"] is True

    def test_verify_agent_no_agent(self, client):
        token = _register_and_login(client)
        create_r = client.post("/api/v1/accounts", json=TEST_ACCOUNT, headers={"Authorization": f"Bearer {token}"})
        aid = create_r.json()["id"]

        r = client.post(f"/api/v1/accounts/{aid}/verify-agent", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["verified"] is False
        assert data["status"] == "NO_AGENT"
