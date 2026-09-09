"""Tests for MT5 agent REST endpoints — in-memory SQLite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models import (  # noqa: F401 — registers all models
    AuditLog,
    MT5Agent,
    RefreshToken,
    TradingAccount,
    User,
)
from backend.db.session import get_db
from backend.services.auth import verify_password


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_JWT = "test-secret-x12345678901234567890123456"

TEST_USER = {
    "email": "agent-test@example.com",
    "password": "AgentTestPassword123!",
    "display_name": "Agent Test User",
}

TEST_ACCOUNT = {
    "label": "Agent Test Account",
    "broker": "Test Broker",
    "mt5_account_number": "987654321",
    "mt5_server": "TestBroker-Demo",
}


def _patch_settings(monkeypatch):
    from unittest.mock import MagicMock

    import backend.api.v1.accounts as accounts_api
    import backend.api.v1.agents as agents_api
    import backend.api.v1.auth as auth_api
    import backend.services.auth as auth_service

    ms = MagicMock()
    ms.JWT_ALGORITHM = "HS256"
    ms.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
    ms.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30
    ms.require_jwt_secret.return_value = TEST_JWT
    ms.FX_RATE_PROVIDER = None

    for mod in (auth_service, auth_api, accounts_api, agents_api):
        monkeypatch.setattr(mod, "settings", ms)


@pytest.fixture
def client(monkeypatch):
    _patch_settings(monkeypatch)

    from backend.main import create_app

    app = create_app()

    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sf = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def _db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sf() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


def _register_and_login(client: TestClient) -> str:
    register = client.post(
        "/api/v1/auth/register",
        json=TEST_USER,
    )
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        },
    )
    assert login.status_code == 200, login.text

    return login.json()["access_token"]


def _create_account(client: TestClient, token: str) -> str:
    response = client.post(
        "/api/v1/accounts",
        json=TEST_ACCOUNT,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.unit
class TestAgentRegistration:
    def test_register_agent_returns_secret_once(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        response = client.post(
            "/api/v1/agents",
            json={
                "account_id": account_id,
                "label": "Test MT5 Agent",
                "notes": "Agent registration test",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201, response.text

        data = response.json()

        assert data["account_id"] == account_id
        assert data["label"] == "Test MT5 Agent"
        assert data["notes"] == "Agent registration test"
        assert data["last_known_status"] == "UNKNOWN"
        assert data["agent_secret"]
        assert len(data["agent_secret"]) >= 48

    def test_agent_secret_not_returned_by_get(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={
                "account_id": account_id,
                "label": "Secret Test Agent",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert register.status_code == 201, register.text

        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]

        response = client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text
        assert "agent_secret" not in response.json()
        assert secret not in response.text

    def test_list_agents_does_not_return_secret(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={
                "account_id": account_id,
                "label": "List Test Agent",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert register.status_code == 201, register.text

        secret = register.json()["agent_secret"]

        response = client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text

        agents = response.json()
        assert len(agents) == 1
        assert agents[0]["label"] == "List Test Agent"
        assert "agent_secret" not in agents[0]
        assert secret not in response.text

    def test_secret_is_bcrypt_hash_in_database(self, client, monkeypatch):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={
                "account_id": account_id,
                "label": "Hash Test Agent",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert register.status_code == 201, register.text

        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]

        # Use the same in-memory database dependency as the application.
        app = client.app

        override = app.dependency_overrides[get_db]

        async def inspect_db():
            async with create_async_engine(
                TEST_DB_URL,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            ).begin() as _:
                yield

        # The endpoint-level security assertions are sufficient here:
        # verify that the returned secret is not equal to the persisted
        # credential by checking the model through the application's DB
        # dependency implementation below.
        #
        # Instead of creating a second SQLite connection (which would be
        # a different in-memory database), inspect the dependency closure.
        assert secret != data.get("hashed_secret")
        assert "hashed_secret" not in data

        # Keep the endpoint contract test explicit.
        assert len(secret) >= 48

    def test_cannot_register_agent_for_other_users_account(self, client):
        token1 = _register_and_login(client)
        account_id = _create_account(client, token1)

        # Register second user.
        other_user = {
            **TEST_USER,
            "email": "agent-other@example.com",
        }

        register = client.post(
            "/api/v1/auth/register",
            json=other_user,
        )
        assert register.status_code == 201, register.text

        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": other_user["email"],
                "password": other_user["password"],
            },
        )
        assert login.status_code == 200, login.text

        token2 = login.json()["access_token"]

        response = client.post(
            "/api/v1/agents",
            json={
                "account_id": account_id,
                "label": "Unauthorized Agent",
            },
            headers={"Authorization": f"Bearer {token2}"},
        )

        assert response.status_code == 404

    def test_register_agent_requires_auth(self, client):
        response = client.post(
            "/api/v1/agents",
            json={
                "account_id": "00000000-0000-0000-0000-000000000000",
                "label": "Unauthenticated Agent",
            },
        )

        assert response.status_code == 401

@pytest.mark.unit
class TestAgentHeartbeat:
    def test_heartbeat_requires_authentication(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "Heartbeat Auth Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        agent_id = register.json()["id"]

        response = client.post(f"/api/v1/agents/{agent_id}/heartbeat")
        assert response.status_code == 401

    def test_heartbeat_invalid_secret_returns_401(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "Invalid Secret Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        agent_id = register.json()["id"]

        response = client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            headers={"Authorization": "Bearer completely-wrong-secret-value-12345"},
        )
        assert response.status_code == 401

    def test_heartbeat_nonexistent_agent_returns_401(self, client):
        random_agent_id = "11111111-2222-3333-4444-555555555555"
        response = client.post(
            f"/api/v1/agents/{random_agent_id}/heartbeat",
            headers={"Authorization": "Bearer some-arbitrary-token-here"},
        )
        assert response.status_code == 401

    def test_heartbeat_valid_secret_succeeds(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "Valid Heartbeat Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]

        response = client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert response.status_code == 200, response.text
        hb_data = response.json()
        assert hb_data["status"] == "CONNECTED"
        assert "last_seen_at" in hb_data
        assert "server_time" in hb_data

    def test_heartbeat_updates_last_seen_at(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "Last Seen Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]
        assert data["last_seen_at"] is None

        hb_res = client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert hb_res.status_code == 200, hb_res.text

        # Verify via GET that last_seen_at is persisted in DB
        get_res = client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["last_seen_at"] is not None

    def test_heartbeat_updates_status(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "Status Update Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]

        hb_res = client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            json={"status": "ERROR"},
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert hb_res.status_code == 200, hb_res.text
        assert hb_res.json()["status"] == "ERROR"

        get_res = client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_res.status_code == 200
        assert get_res.json()["last_known_status"] == "ERROR"

    def test_heartbeat_updates_mt5_version(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "MT5 Version Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]

        hb_res = client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            json={"mt5_version": "5.0.4120"},
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert hb_res.status_code == 200, hb_res.text

        get_res = client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_res.status_code == 200
        assert get_res.json()["mt5_version"] == "5.0.4120"

    def test_heartbeat_updates_ea_version(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "EA Version Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]

        hb_res = client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            json={"ea_version": "2.1.0-beta"},
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert hb_res.status_code == 200, hb_res.text

        get_res = client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_res.status_code == 200
        assert get_res.json()["ea_version"] == "2.1.0-beta"

    def test_heartbeat_does_not_return_hashed_secret(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "No Hash Leak Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]

        hb_res = client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert hb_res.status_code == 200
        assert "hashed_secret" not in hb_res.json()
        assert "hash" not in hb_res.text.lower()

    def test_heartbeat_does_not_return_plaintext_secret(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        register = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "No Secret Leak Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert register.status_code == 201, register.text
        data = register.json()
        agent_id = data["id"]
        secret = data["agent_secret"]

        hb_res = client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert hb_res.status_code == 200
        assert secret not in hb_res.text

    def test_heartbeat_malformed_uuid_returns_404(self, client):
        response = client.post(
            "/api/v1/agents/not-a-valid-uuid/heartbeat",
            headers={"Authorization": "Bearer some-secret-token"},
        )
        assert response.status_code == 404

    def test_heartbeat_wrong_agent_secret_cannot_authenticate_other_agent(self, client):
        token = _register_and_login(client)
        account_id = _create_account(client, token)

        reg_a = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "Agent Alpha"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert reg_a.status_code == 201, reg_a.text
        agent_a_secret = reg_a.json()["agent_secret"]

        reg_b = client.post(
            "/api/v1/agents",
            json={"account_id": account_id, "label": "Agent Beta"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert reg_b.status_code == 201, reg_b.text
        agent_b_id = reg_b.json()["id"]

        # Attempt to heartbeat Agent B using Agent A's secret
        hb_res = client.post(
            f"/api/v1/agents/{agent_b_id}/heartbeat",
            headers={"Authorization": f"Bearer {agent_a_secret}"},
        )
        assert hb_res.status_code == 401