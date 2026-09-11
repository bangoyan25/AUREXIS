"""
WebSocket authentication and account authorization tests.

Verifies:
- Unauthenticated connections rejected
- Invalid token rejected
- Expired token rejected
- Valid token + owned account accepted
- Missing account_id rejected
- Non-owner: cannot access another user's account
- Invalid account_id: rejected
- Multiple accounts handled independently
- Reconnect after disconnect works correctly

DB ownership tests use in-memory SQLite so no PostgreSQL required.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.services.auth as auth_module
from backend.api.v1.websocket import _resolve_and_authorize
from backend.api.v1.websocket import router as ws_router
from backend.db.base import Base
from backend.db.models import (  # noqa: F401 — registers all models with Base.metadata
    AuditLog,
    MT5Agent,
    RefreshToken,
    TradingAccount,
    User,
)
from backend.db.session import get_db
from backend.services.auth import create_access_token

TEST_JWT_SECRET = "test-secret-websocket-auth-x12345678"
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def patch_auth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    mock_settings = MagicMock()
    mock_settings.JWT_ALGORITHM = "HS256"
    mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
    mock_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30
    mock_settings.require_jwt_secret.return_value = TEST_JWT_SECRET
    monkeypatch.setattr(auth_module, "settings", mock_settings)


def make_token(
    subject: str = "user-001",
    expires_delta: timedelta | None = None,
) -> str:
    return create_access_token(subject=subject, expires_delta=expires_delta)


@pytest.fixture
def ws_app() -> FastAPI:
    """Minimal FastAPI app with WS router + in-memory SQLite for DB ownership checks."""
    app = FastAPI()
    from fastapi import APIRouter
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(ws_router)
    app.include_router(api_router)

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

    import backend.api.v1.websocket as ws_mod
    ws_mod._session_factory = sf

    return app


# ── _resolve_and_authorize unit tests (no DB) ─────────────────────────────

@pytest.mark.unit
class TestResolveAndAuthorize:
    """Unit tests for the internal auth helper — db=None skips DB check."""

    @pytest.mark.asyncio
    async def test_no_token_returns_none(self) -> None:
        result = await _resolve_and_authorize(None, "account-abc", db=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_account_id_returns_none(self) -> None:
        token = make_token()
        result = await _resolve_and_authorize(token, None, db=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_token_no_db_returns_user_and_account(self) -> None:
        token = make_token(subject="user-xyz")
        result = await _resolve_and_authorize(token, "account-001", db=None)
        assert result is not None
        user_id, account_id = result
        assert user_id == "user-xyz"
        assert account_id == "account-001"

    @pytest.mark.asyncio
    async def test_expired_token_returns_none(self) -> None:
        token = make_token(expires_delta=timedelta(seconds=-1))
        result = await _resolve_and_authorize(token, "account-001", db=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_tampered_token_returns_none(self) -> None:
        token = make_token()
        tampered = token[:-5] + "XXXXX"
        result = await _resolve_and_authorize(tampered, "account-001", db=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_both_none_returns_none(self) -> None:
        result = await _resolve_and_authorize(None, None, db=None)
        assert result is None


# ── WebSocket endpoint integration tests ─────────────────────────────────

@pytest.mark.unit
class TestWebSocketEndpoint:
    """WebSocket endpoint tests — with SQLite DB for ownership checks."""

    def test_unauthenticated_connection_rejected(self, ws_app: FastAPI) -> None:
        with TestClient(ws_app) as client, pytest.raises(Exception):  # noqa: B017,SIM117
            with client.websocket_connect("/api/v1/ws?account_id=acc-001"):
                pass

    def test_invalid_token_rejected(self, ws_app: FastAPI) -> None:
        with TestClient(ws_app) as client, pytest.raises(Exception):  # noqa: B017,SIM117
            with client.websocket_connect("/api/v1/ws?token=not.a.jwt&account_id=acc-001"):
                pass

    def test_expired_token_rejected(self, ws_app: FastAPI) -> None:
        token = make_token(expires_delta=timedelta(seconds=-1))
        with TestClient(ws_app) as client, pytest.raises(Exception):  # noqa: B017,SIM117
            with client.websocket_connect(f"/api/v1/ws?token={token}&account_id=acc-001"):
                pass

    def test_missing_account_id_rejected(self, ws_app: FastAPI) -> None:
        token = make_token()
        with TestClient(ws_app) as client, pytest.raises(Exception):  # noqa: B017,SIM117
            with client.websocket_connect(f"/api/v1/ws?token={token}"):
                pass

    def test_invalid_uuid_account_id_rejected(self, ws_app: FastAPI) -> None:
        """account_id that is not a valid UUID → rejected (DB check fails)."""
        token = make_token(subject=str(uuid.uuid4()))
        with TestClient(ws_app) as client, pytest.raises(Exception):  # noqa: B017,SIM117
            with client.websocket_connect(f"/api/v1/ws?token={token}&account_id=not-a-uuid"):
                pass

    def test_nonexistent_account_rejected(self, ws_app: FastAPI) -> None:
        """Valid token + account_id not in DB → rejected."""
        user_id = str(uuid.uuid4())
        token = make_token(subject=user_id)
        fake_account = str(uuid.uuid4())
        with TestClient(ws_app) as client, pytest.raises(Exception):  # noqa: B017,SIM117
            with client.websocket_connect(f"/api/v1/ws?token={token}&account_id={fake_account}"):
                pass



# ── DB ownership tests ────────────────────────────────────────────────────

def _make_full_app(monkeypatch):
    from unittest.mock import MagicMock

    import backend.api.v1.accounts as accounts_mod
    import backend.api.v1.auth as auth_api_mod
    import backend.api.v1.websocket as ws_mod
    from backend.main import create_app

    ms = MagicMock()
    ms.JWT_ALGORITHM = "HS256"
    ms.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
    ms.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30
    ms.require_jwt_secret.return_value = TEST_JWT_SECRET
    ms.FX_RATE_PROVIDER = None
    monkeypatch.setattr(accounts_mod, "settings", ms)
    monkeypatch.setattr(auth_api_mod, "settings", ms)

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

    # Inject test session factory into the WS module (no Depends needed)
    monkeypatch.setattr(ws_mod, "_session_factory", sf)

    return app


@pytest.mark.unit
class TestWebSocketDBOwnership:
    def test_owner_can_connect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_full_app(monkeypatch)
        with TestClient(app, raise_server_exceptions=True) as client:
            client.post("/api/v1/auth/register",
                json={"email": "ws_o@example.com", "password": "pass12345678",
                      "display_name": "O"})
            t = client.post("/api/v1/auth/login",
                json={"email": "ws_o@example.com", "password": "pass12345678"}).json()
            acc = client.post("/api/v1/accounts",
                json={"label": "T1", "broker": "Test Broker", "mt5_account_number": "999"},
                headers={"Authorization": f"Bearer {t['access_token']}"}).json()
            with client.websocket_connect(
                f"/api/v1/ws?token={t['access_token']}&account_id={acc['id']}"
            ) as ws:
                assert ws is not None

    def test_non_owner_cannot_connect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_full_app(monkeypatch)
        with TestClient(app, raise_server_exceptions=True) as client:
            client.post("/api/v1/auth/register",
                json={"email": "ws_aa@example.com", "password": "pass12345678",
                      "display_name": "A"})
            ta = client.post("/api/v1/auth/login",
                json={"email": "ws_aa@example.com", "password": "pass12345678"}).json()
            acc = client.post("/api/v1/accounts",
                json={"label": "A_Acct", "broker": "Test Broker", "mt5_account_number": "111"},
                headers={"Authorization": f"Bearer {ta['access_token']}"}).json()

            client.post("/api/v1/auth/register",
                json={"email": "ws_bb@example.com", "password": "pass12345678",
                      "display_name": "B"})
            tb = client.post("/api/v1/auth/login",
                json={"email": "ws_bb@example.com", "password": "pass12345678"}).json()

            with pytest.raises(Exception), client.websocket_connect(  # noqa: B017
                f"/api/v1/ws?token={tb['access_token']}&account_id={acc['id']}"
            ):
                pass

    def test_reconnect_with_owned_account_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _make_full_app(monkeypatch)
        with TestClient(app, raise_server_exceptions=True) as client:
            client.post("/api/v1/auth/register",
                json={"email": "ws_rc@example.com", "password": "pass12345678",
                      "display_name": "RC"})
            t = client.post("/api/v1/auth/login",
                json={"email": "ws_rc@example.com", "password": "pass12345678"}).json()
            acc = client.post("/api/v1/accounts",
                json={"label": "RC_Acct", "broker": "Test Broker", "mt5_account_number": "222"},
                headers={"Authorization": f"Bearer {t['access_token']}"}).json()
            # First connection
            with client.websocket_connect(
                f"/api/v1/ws?token={t['access_token']}&account_id={acc['id']}"
            ) as ws:
                assert ws is not None
            # Reconnect
            with client.websocket_connect(
                f"/api/v1/ws?token={t['access_token']}&account_id={acc['id']}"
            ) as ws:
                assert ws is not None



# ── Account isolation unit tests ──────────────────────────────────────────

@pytest.mark.unit
class TestAccountIsolation:
    @pytest.mark.asyncio
    async def test_no_token_cannot_access_any_account(self) -> None:
        assert await _resolve_and_authorize(None, "account-B", db=None) is None

    @pytest.mark.asyncio
    async def test_invalid_token_cannot_access_any_account(self) -> None:
        assert await _resolve_and_authorize("garbage.token.here", "account-B", db=None) is None

    @pytest.mark.asyncio
    async def test_user_a_token_resolves_to_user_a(self) -> None:
        token_a = make_token(subject="user-A")
        result = await _resolve_and_authorize(token_a, "account-A", db=None)
        assert result is not None
        assert result[0] == "user-A"

    @pytest.mark.asyncio
    async def test_multiple_accounts_handled_independently(self) -> None:
        token_1 = make_token(subject="user-1")
        token_2 = make_token(subject="user-2")
        r1 = await _resolve_and_authorize(token_1, "acc-1", db=None)
        r2 = await _resolve_and_authorize(token_2, "acc-2", db=None)
        assert r1 is not None and r2 is not None
        assert r1[0] == "user-1" and r1[1] == "acc-1"
        assert r2[0] == "user-2" and r2[1] == "acc-2"



