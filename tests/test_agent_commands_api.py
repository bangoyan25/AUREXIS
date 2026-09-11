"""Tests for MT5 Agent Command / Control-Plane endpoints.

Phases tested:
  D - User-facing command API
  E - Agent-facing pending poll
  F - Agent ack / result
  G - Audit payloads
  Concurrency / integrity

Runs entirely in-memory SQLite via StaticPool.
No real DB required.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models import (  # noqa: F401 - registers all models
    MT5Agent,
    MT5AgentCommand,
    AuditLog,
    RefreshToken,
    TradingAccount,
    User,
)
from backend.db.session import get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_JWT = "test-secret-x12345678901234567890123456"

USER_A = {
    "email": "cmd-user-a@example.com",
    "password": "CmdUserAPassword123!",
    "display_name": "Command User A",
}
USER_B = {
    "email": "cmd-user-b@example.com",
    "password": "CmdUserBPassword123!",
    "display_name": "Command User B",
}
TEST_ACCOUNT = {
    "label": "Cmd Test Account",
    "broker": "HFM",
    "mt5_account_number": "111222333",
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


# -- Test helpers --

def _register_and_login(c: TestClient, user: dict) -> str:
    r = c.post("/api/v1/auth/register", json=user)
    assert r.status_code == 201, r.text
    r = c.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _create_account(c: TestClient, token: str, account: dict | None = None) -> str:
    r = c.post(
        "/api/v1/accounts",
        json=account or TEST_ACCOUNT,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _register_agent(c: TestClient, token: str, account_id: str) -> tuple[str, str]:
    """Returns (agent_id, plaintext_secret)."""
    r = c.post(
        "/api/v1/agents",
        json={"account_id": account_id, "label": "Test EA Agent"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return data["id"], data["agent_secret"]


def _create_command(c: TestClient, token: str, agent_id: str, command_type: str = "PING", payload: dict | None = None) -> dict:
    body = {"command_type": command_type}
    if payload is not None:
        body["payload"] = payload
    r = c.post(
        f"/api/v1/agents/{agent_id}/commands",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    return r


@pytest.mark.unit
class TestUserCommandAPI:
    """User-facing command API tests."""

    def test_create_ping_command(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        r = _create_command(client, token, agent_id, "PING")
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["command_type"] == "PING"
        assert data["status"] == "PENDING"
        assert data["agent_id"] == agent_id
        assert data["result"] is None
        assert data["error_message"] is None
        assert data["sent_at"] is None
        assert data["acknowledged_at"] is None
        assert data["completed_at"] is None
        # secret must never appear
        assert "secret" not in r.text
        assert "hashed_secret" not in r.text

    def test_create_get_status_command(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        r = _create_command(client, token, agent_id, "GET_STATUS")
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["command_type"] == "GET_STATUS"
        assert data["status"] == "PENDING"

    def test_create_command_lowercase_normalised(self, client):
        """command_type should be normalised to uppercase."""
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        r = _create_command(client, token, agent_id, "ping")
        assert r.status_code == 201, r.text
        assert r.json()["command_type"] == "PING"

    def test_create_unsupported_command_returns_422(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        r = _create_command(client, token, agent_id, "OPEN_ORDER")
        assert r.status_code == 422, r.text

    def test_create_command_unauthenticated(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        r = client.post(f"/api/v1/agents/{agent_id}/commands", json={"command_type": "PING"})
        assert r.status_code == 401, r.text

    def test_create_command_for_other_users_agent_returns_404(self, client):
        token_a = _register_and_login(client, USER_A)
        account_a = _create_account(client, token_a)
        agent_id_a, _ = _register_agent(client, token_a, account_a)

        token_b = _register_and_login(client, USER_B)

        # User B tries to create command for Agent A
        r = _create_command(client, token_b, agent_id_a, "PING")
        assert r.status_code == 404, r.text

    def test_list_commands(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        _create_command(client, token, agent_id, "PING")
        _create_command(client, token, agent_id, "GET_STATUS")

        r = client.get(f"/api/v1/agents/{agent_id}/commands", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) == 2
        types = {c["command_type"] for c in data}
        assert types == {"PING", "GET_STATUS"}

    def test_get_command(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        created = _create_command(client, token, agent_id, "PING").json()
        cmd_id = created["id"]

        r = client.get(f"/api/v1/agents/{agent_id}/commands/{cmd_id}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["id"] == cmd_id

    def test_cannot_get_another_agents_command(self, client):
        token_a = _register_and_login(client, USER_A)
        account_a = _create_account(client, token_a)
        agent_id_a, _ = _register_agent(client, token_a, account_a)
        cmd_id = _create_command(client, token_a, agent_id_a, "PING").json()["id"]

        token_b = _register_and_login(client, USER_B)
        account_b = _create_account(client, token_b, account={"label": "B Acct", "broker": "HFM", "mt5_account_number": "9999", "mt5_server": "Demo-B"})
        agent_id_b, _ = _register_agent(client, token_b, account_b)

        # User B with Agent B cannot read Agent A command
        r = client.get(f"/api/v1/agents/{agent_id_b}/commands/{cmd_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert r.status_code == 404, r.text

    def test_command_with_payload(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        r = _create_command(client, token, agent_id, "PING", payload={"timeout_ms": 3000})
        assert r.status_code == 201, r.text
        assert r.json()["payload"] == {"timeout_ms": 3000}


@pytest.mark.unit
class TestAgentCommandAPI:
    """Agent-facing command API tests."""

    def test_pending_commands_with_correct_secret(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)

        _create_command(client, token, agent_id, "PING")

        r = client.get(
            f"/api/v1/agents/{agent_id}/commands/pending",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) == 1
        assert data[0]["command_type"] == "PING"
        assert data[0]["status"] == "SENT"  # claimed = transitions to SENT

    def test_pending_commands_wrong_secret_returns_401(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        r = client.get(
            f"/api/v1/agents/{agent_id}/commands/pending",
            headers={"Authorization": "Bearer wrongsecret12345"},
        )
        assert r.status_code == 401, r.text

    def test_agent_a_secret_cannot_access_agent_b_pending(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id_a, secret_a = _register_agent(client, token, account_id)
        agent_id_b, _ = _register_agent(client, token, account_id)

        _create_command(client, token, agent_id_b, "PING")

        # Agent A's secret used with Agent B's endpoint
        r = client.get(
            f"/api/v1/agents/{agent_id_b}/commands/pending",
            headers={"Authorization": f"Bearer {secret_a}"},
        )
        assert r.status_code == 401, r.text

    def test_nonexistent_agent_returns_401(self, client):
        import uuid
        r = client.get(
            f"/api/v1/agents/{uuid.uuid4()}/commands/pending",
            headers={"Authorization": "Bearer anysecret"},
        )
        assert r.status_code == 401, r.text

    def test_claim_transitions_pending_to_sent(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        _create_command(client, token, agent_id, "PING")

        # First claim -> SENT
        r1 = client.get(
            f"/api/v1/agents/{agent_id}/commands/pending",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert r1.status_code == 200
        assert r1.json()[0]["status"] == "SENT"

        # Second claim -> empty (no longer PENDING)
        r2 = client.get(
            f"/api/v1/agents/{agent_id}/commands/pending",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert r2.status_code == 200
        assert r2.json() == []

    def test_ack_valid_transition(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        cmd_id = _create_command(client, token, agent_id, "PING").json()["id"]

        # Claim first (PENDING -> SENT)
        client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})

        # Ack (SENT -> ACKNOWLEDGED)
        r = client.post(
            f"/api/v1/agents/{agent_id}/commands/{cmd_id}/ack",
            json={"status": "ACKNOWLEDGED"},
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ACKNOWLEDGED"
        assert data["acknowledged_at"] is not None

    def test_result_completed_valid_transition(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        cmd_id = _create_command(client, token, agent_id, "PING").json()["id"]

        # Claim
        client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        # Ack
        client.post(f"/api/v1/agents/{agent_id}/commands/{cmd_id}/ack", json={"status": "ACKNOWLEDGED"}, headers={"Authorization": f"Bearer {secret}"})
        # Complete
        r = client.post(
            f"/api/v1/agents/{agent_id}/commands/{cmd_id}/result",
            json={"status": "COMPLETED", "result": {"latency_ms": 42}},
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "COMPLETED"
        assert data["result"] == {"latency_ms": 42}
        assert data["completed_at"] is not None

    def test_result_failed_valid_transition(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        cmd_id = _create_command(client, token, agent_id, "PING").json()["id"]

        # Claim
        client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        # Fail directly from SENT
        r = client.post(
            f"/api/v1/agents/{agent_id}/commands/{cmd_id}/result",
            json={"status": "FAILED", "error_message": "Connection timeout"},
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "FAILED"
        assert data["error_message"] == "Connection timeout"
        assert data["completed_at"] is not None

    def test_invalid_state_transition_rejected(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        cmd_id = _create_command(client, token, agent_id, "PING").json()["id"]

        # Claim & Complete directly without ack
        client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        client.post(f"/api/v1/agents/{agent_id}/commands/{cmd_id}/result", json={"status": "COMPLETED"}, headers={"Authorization": f"Bearer {secret}"})

        # Try to ack after COMPLETED -> should be 409
        r = client.post(
            f"/api/v1/agents/{agent_id}/commands/{cmd_id}/ack",
            json={"status": "ACKNOWLEDGED"},
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert r.status_code == 409, r.text

    def test_command_belonging_to_another_agent_rejected(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id_a, secret_a = _register_agent(client, token, account_id)
        agent_id_b, secret_b = _register_agent(client, token, account_id)

        # Create command for Agent A
        cmd_id = _create_command(client, token, agent_id_a, "PING").json()["id"]
        # Claim with Agent A so it is SENT
        client.get(f"/api/v1/agents/{agent_id_a}/commands/pending", headers={"Authorization": f"Bearer {secret_a}"})

        # Agent B tries to ack Agent A command via its own endpoint
        r = client.post(
            f"/api/v1/agents/{agent_id_b}/commands/{cmd_id}/ack",
            json={"status": "ACKNOWLEDGED"},
            headers={"Authorization": f"Bearer {secret_b}"},
        )
        assert r.status_code == 404, r.text

    def test_secret_absent_from_command_response(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        r = _create_command(client, token, agent_id, "PING")
        assert r.status_code == 201
        assert "secret" not in r.text
        assert "hashed_secret" not in r.text

    def test_hashed_secret_absent_from_pending_response(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        _create_command(client, token, agent_id, "PING")
        r = client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        assert r.status_code == 200
        assert "hashed_secret" not in r.text


@pytest.mark.unit
class TestCommandConcurrencyIntegrity:
    """Concurrency and integrity tests."""

    def test_same_command_cannot_be_claimed_twice(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        _create_command(client, token, agent_id, "PING")

        # First claim
        r1 = client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        assert r1.status_code == 200
        assert len(r1.json()) == 1

        # Second claim - must be empty
        r2 = client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        assert r2.status_code == 200
        assert len(r2.json()) == 0

    def test_invalid_command_uuid_handled_safely(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)

        r = client.get(
            f"/api/v1/agents/{agent_id}/commands/not-a-uuid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404, r.text

    def test_ownership_enforced_list(self, client):
        """User B cannot list User A agent commands."""
        token_a = _register_and_login(client, USER_A)
        account_a = _create_account(client, token_a)
        agent_id_a, _ = _register_agent(client, token_a, account_a)
        _create_command(client, token_a, agent_id_a, "PING")

        token_b = _register_and_login(client, USER_B)

        r = client.get(f"/api/v1/agents/{agent_id_a}/commands", headers={"Authorization": f"Bearer {token_b}"})
        assert r.status_code == 404, r.text

    def test_no_partial_command_state_on_invalid_transition(self, client):
        """After rejected transition, command status unchanged."""
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        cmd_id = _create_command(client, token, agent_id, "PING").json()["id"]

        # Ack while still PENDING (not SENT yet) -> should fail
        r = client.post(
            f"/api/v1/agents/{agent_id}/commands/{cmd_id}/ack",
            json={"status": "ACKNOWLEDGED"},
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert r.status_code == 409, r.text

        # Command still PENDING
        r2 = client.get(
            f"/api/v1/agents/{agent_id}/commands/{cmd_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.json()["status"] == "PENDING"


@pytest.mark.unit
class TestCommandAudit:
    """Audit event tests for agent commands."""

    def test_command_creation_audit_exists(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)
        _create_command(client, token, agent_id, "PING")

        r = client.get("/api/v1/activity", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        events = r.json()
        event_types = [e["event_type"] for e in events]
        assert "MT5_AGENT_COMMAND_CREATED" in event_types

    def test_audit_payload_contains_no_secret(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, _ = _register_agent(client, token, account_id)
        _create_command(client, token, agent_id, "PING")

        r = client.get("/api/v1/activity", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        response_text = r.text
        assert "hashed_secret" not in response_text
        # The plaintext secret is not stored in audit; ensure no "secret" key appears
        # (the activity endpoint returns JSON, so check full text)
        import json
        events = json.loads(response_text)
        for ev in events:
            payload = ev.get("payload", {})
            if payload:
                assert "secret" not in payload
                assert "hashed_secret" not in payload

    def test_ack_audit_event_exists(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        cmd_id = _create_command(client, token, agent_id, "PING").json()["id"]

        # Claim
        client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        # Ack
        client.post(f"/api/v1/agents/{agent_id}/commands/{cmd_id}/ack", json={"status": "ACKNOWLEDGED"}, headers={"Authorization": f"Bearer {secret}"})

        r = client.get("/api/v1/activity", headers={"Authorization": f"Bearer {token}"})
        event_types = [e["event_type"] for e in r.json()]
        assert "MT5_AGENT_COMMAND_ACKNOWLEDGED" in event_types

    def test_completion_audit_event_exists(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        cmd_id = _create_command(client, token, agent_id, "PING").json()["id"]

        # Full lifecycle
        client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        client.post(f"/api/v1/agents/{agent_id}/commands/{cmd_id}/ack", json={"status": "ACKNOWLEDGED"}, headers={"Authorization": f"Bearer {secret}"})
        client.post(f"/api/v1/agents/{agent_id}/commands/{cmd_id}/result", json={"status": "COMPLETED", "result": {"pong": True}}, headers={"Authorization": f"Bearer {secret}"})

        r = client.get("/api/v1/activity", headers={"Authorization": f"Bearer {token}"})
        event_types = [e["event_type"] for e in r.json()]
        assert "MT5_AGENT_COMMAND_COMPLETED" in event_types

    def test_failure_audit_event_exists(self, client):
        token = _register_and_login(client, USER_A)
        account_id = _create_account(client, token)
        agent_id, secret = _register_agent(client, token, account_id)
        cmd_id = _create_command(client, token, agent_id, "PING").json()["id"]

        client.get(f"/api/v1/agents/{agent_id}/commands/pending", headers={"Authorization": f"Bearer {secret}"})
        client.post(f"/api/v1/agents/{agent_id}/commands/{cmd_id}/result", json={"status": "FAILED", "error_message": "EA crash"}, headers={"Authorization": f"Bearer {secret}"})

        r = client.get("/api/v1/activity", headers={"Authorization": f"Bearer {token}"})
        event_types = [e["event_type"] for e in r.json()]
        assert "MT5_AGENT_COMMAND_FAILED" in event_types
