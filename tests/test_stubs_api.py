"""Tests for domain stub endpoints — verify NOT_CONFIGURED/EMPTY states."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.session import get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_JWT = "test-secret-x12345678901234567890123456"
TEST_USER = {"email": "stub@example.com", "password": "secure-password-123", "display_name": "Stub User"}


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


def _token(client):
    client.post("/api/v1/auth/register", json=TEST_USER)
    r = client.post("/api/v1/auth/login", json={"email": TEST_USER["email"], "password": TEST_USER["password"]})
    return r.json()["access_token"]


@pytest.mark.unit
class TestDomainStubs:
    def test_risk_not_configured(self, client):
        tok = _token(client)
        r = client.get("/api/v1/risk/some-account-id", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        d = r.json()
        assert d["risk_state"] == "NOT_CONFIGURED"
        assert d["trading_allowed"] is False

    def test_brain_not_configured(self, client):
        tok = _token(client)
        r = client.get("/api/v1/brain/some-account-id", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json()["brain_state"] == "NOT_CONFIGURED"

    def test_market_not_configured(self, client):
        tok = _token(client)
        r = client.get("/api/v1/market/tick", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json()["status"] == "NOT_CONFIGURED"

    def test_signals_not_configured(self, client):
        tok = _token(client)
        r = client.get("/api/v1/signals", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        d = r.json()
        assert d["signals"] == []

    def test_positions_empty(self, client):
        tok = _token(client)
        r = client.get("/api/v1/positions", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "EMPTY"
        assert d["positions"] == []

    def test_execution_empty(self, client):
        tok = _token(client)
        r = client.get("/api/v1/execution", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json()["commands"] == []

    def test_news_unknown(self, client):
        tok = _token(client)
        r = client.get("/api/v1/news", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "UNKNOWN"
        assert d["provider"] is None

    def test_performance_empty(self, client):
        tok = _token(client)
        r = client.get("/api/v1/performance", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json()["total_trades"] == 0

    def test_backtest_not_configured(self, client):
        tok = _token(client)
        r = client.get("/api/v1/backtest", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json()["status"] == "NOT_CONFIGURED"

    def test_stubs_require_auth(self, client):
        for path in ["/api/v1/signals", "/api/v1/positions", "/api/v1/news"]:
            assert client.get(path).status_code == 401, f"Expected 401 for {path}"
