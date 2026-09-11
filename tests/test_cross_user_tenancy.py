from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.db.base import Base
import backend.db.models
from backend.db.session import get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_JWT = "tenancy-isolation-secret-1234567890abcd"

def _patch_settings(monkeypatch):
    from unittest.mock import MagicMock
    import backend.api.v1.accounts as acc
    import backend.api.v1.agents as agt
    import backend.api.v1.auth as auth
    import backend.services.auth as svc
    ms = MagicMock()
    ms.JWT_ALGORITHM = "HS256"
    ms.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
    ms.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30
    ms.require_jwt_secret.return_value = TEST_JWT
    ms.FX_RATE_PROVIDER = None
    for mod in (svc, auth, acc, agt):
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

def _rlogin(client, email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "display_name": "User"})
    assert r.status_code == 201
    l = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert l.status_code == 200
    return l.json()["access_token"]

def _acct(client, token):
    r = client.post("/api/v1/accounts", json={"label": "A", "broker": "HFM", "mt5_account_number": "1"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    return r.json()["id"]

def _agent(client, token, acct_id):
    r = client.post("/api/v1/agents", json={"account_id": acct_id, "label": "Agt"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    return r.json()

@pytest.mark.unit
class TestCrossUserIsolation:
    def test_cannot_see_other_accounts(self, client):
        ta = _rlogin(client, "a1@t.com"); tb = _rlogin(client, "b1@t.com")
        ab = _acct(client, tb)
        res = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {ta}"})
        assert res.status_code == 200
        assert ab not in [x["id"] for x in res.json()]

    def test_cannot_get_other_account_by_id(self, client):
        ta = _rlogin(client, "a2@t.com"); tb = _rlogin(client, "b2@t.com")
        ab = _acct(client, tb)
        res = client.get(f"/api/v1/accounts/{ab}", headers={"Authorization": f"Bearer {ta}"})
        assert res.status_code == 404

    def test_cannot_patch_other_account(self, client):
        ta = _rlogin(client, "a3@t.com"); tb = _rlogin(client, "b3@t.com")
        ab = _acct(client, tb)
        res = client.patch(f"/api/v1/accounts/{ab}", json={"label": "X"}, headers={"Authorization": f"Bearer {ta}"})
        assert res.status_code == 404

    def test_cannot_see_other_agents(self, client):
        ta = _rlogin(client, "a4@t.com"); tb = _rlogin(client, "b4@t.com")
        ab = _acct(client, tb); ag = _agent(client, tb, ab)
        res = client.get("/api/v1/agents", headers={"Authorization": f"Bearer {ta}"})
        assert res.status_code == 200
        assert ag["id"] not in [x["id"] for x in res.json()]

    def test_cannot_get_other_agent(self, client):
        ta = _rlogin(client, "a5@t.com"); tb = _rlogin(client, "b5@t.com")
        ab = _acct(client, tb); ag = _agent(client, tb, ab)
        res = client.get(f"/api/v1/agents/{ag['id']}", headers={"Authorization": f"Bearer {ta}"})
        assert res.status_code == 404

    def test_cannot_create_agent_on_other_account(self, client):
        ta = _rlogin(client, "a6@t.com"); tb = _rlogin(client, "b6@t.com")
        ab = _acct(client, tb)
        res = client.post("/api/v1/agents", json={"account_id": ab, "label": "X"}, headers={"Authorization": f"Bearer {ta}"})
        assert res.status_code == 404

    def test_cannot_dispatch_command_to_other_agent(self, client):
        ta = _rlogin(client, "a7@t.com"); tb = _rlogin(client, "b7@t.com")
        ab = _acct(client, tb); ag = _agent(client, tb, ab)
        res = client.post(f"/api/v1/agents/{ag['id']}/commands", json={"command_type": "PING"}, headers={"Authorization": f"Bearer {ta}"})
        assert res.status_code == 404

    def test_cannot_list_commands_for_other_agent(self, client):
        ta = _rlogin(client, "a8@t.com"); tb = _rlogin(client, "b8@t.com")
        ab = _acct(client, tb); ag = _agent(client, tb, ab)
        res = client.get(f"/api/v1/agents/{ag['id']}/commands", headers={"Authorization": f"Bearer {ta}"})
        assert res.status_code == 404
