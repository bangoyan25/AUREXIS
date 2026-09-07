"""Tests for auth REST endpoints — in-memory SQLite, no PostgreSQL needed."""

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
TEST_USER = {
    "email": "test@example.com",
    "password": "secure-password-123",
    "display_name": "Test User",
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
    return ms


@pytest.fixture
def client(monkeypatch):
    _patch_settings(monkeypatch)
    from backend.main import create_app

    app = create_app()
    engine = create_async_engine(
        TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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


def _register(client):
    client.post("/api/v1/auth/register", json=TEST_USER)


def _login(client):
    _register(client)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    return r.json()


@pytest.mark.unit
class TestRegister:
    def test_register_creates_user(self, client):
        r = client.post("/api/v1/auth/register", json=TEST_USER)
        assert r.status_code == 201
        d = r.json()
        assert d["email"] == "test@example.com"
        assert "user_id" in d

    def test_register_duplicate_409(self, client):
        _register(client)
        r = client.post("/api/v1/auth/register", json=TEST_USER)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "EMAIL_TAKEN"

    def test_register_short_password_422(self, client):
        r = client.post("/api/v1/auth/register", json={**TEST_USER, "password": "short"})
        assert r.status_code == 422

    def test_register_normalizes_email(self, client):
        r = client.post(
            "/api/v1/auth/register", json={**TEST_USER, "email": "TEST@EXAMPLE.COM"}
        )
        assert r.status_code == 201
        assert r.json()["email"] == "test@example.com"


@pytest.mark.unit
class TestLogin:
    def test_login_returns_tokens(self, client):
        tokens = _login(client)
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] > 0

    def test_wrong_password_401(self, client):
        _register(client)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": TEST_USER["email"], "password": "wrong"},
        )
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "INVALID_CREDENTIALS"

    def test_unknown_email_401(self, client):
        r = client.post("/api/v1/auth/login", json={"email": "nobody@x.com", "password": "pw"})
        assert r.status_code == 401

    def test_token_not_plaintext_password(self, client):
        tokens = _login(client)
        assert TEST_USER["password"] not in tokens["access_token"]


@pytest.mark.unit
class TestMe:
    def test_me_returns_user(self, client):
        tokens = _login(client)
        r = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert r.status_code == 200
        assert r.json()["email"] == "test@example.com"

    def test_me_no_token_401(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_me_bad_token_401(self, client):
        r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer badtoken"})
        assert r.status_code == 401


@pytest.mark.unit
class TestRefresh:
    def test_refresh_returns_new_tokens(self, client):
        tokens = _login(client)
        r2 = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert r2.status_code == 200
        d = r2.json()
        assert "access_token" in d
        assert "refresh_token" in d

    def test_refresh_rotates_token(self, client):
        """After rotation, old refresh token must be rejected (revoked)."""
        tokens = _login(client)
        old_rt = tokens["refresh_token"]
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})
        assert r2.status_code == 200
        # Old token must now be revoked
        r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})
        assert r3.status_code == 401
        assert r3.json()["detail"]["code"] == "REFRESH_TOKEN_REVOKED"

    def test_invalid_refresh_401(self, client):
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
        assert r.status_code == 401

    def test_new_refresh_token_is_usable(self, client):
        """Newly issued refresh token from rotation must work."""
        tokens = _login(client)
        r2 = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        new_tokens = r2.json()
        r3 = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
        )
        assert r3.status_code == 200


@pytest.mark.unit
class TestLogout:
    def test_logout_204(self, client):
        tokens = _login(client)
        r2 = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert r2.status_code == 204

    def test_logout_revokes_refresh_token(self, client):
        """After logout, the refresh token must be rejected."""
        tokens = _login(client)
        client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        r = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "REFRESH_TOKEN_REVOKED"

    def test_logout_no_access_token_401(self, client):
        assert (
            client.post("/api/v1/auth/logout", json={"refresh_token": "x"}).status_code == 401
        )

    def test_multiple_sessions_independent(self, client):
        """Two login sessions revoke independently."""
        _register(client)
        t1 = client.post(
            "/api/v1/auth/login",
            json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
        ).json()
        t2 = client.post(
            "/api/v1/auth/login",
            json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
        ).json()

        # Logout session 1
        client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": t1["refresh_token"]},
            headers={"Authorization": f"Bearer {t1['access_token']}"},
        )

        # Session 1 revoked
        r_bad = client.post("/api/v1/auth/refresh", json={"refresh_token": t1["refresh_token"]})
        assert r_bad.status_code == 401

        # Session 2 still valid
        r_ok = client.post("/api/v1/auth/refresh", json={"refresh_token": t2["refresh_token"]})
        assert r_ok.status_code == 200

