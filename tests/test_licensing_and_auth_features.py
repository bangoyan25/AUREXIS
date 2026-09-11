"""Comprehensive tests for subscription licensing, serial code enforcement,
password reset flow, and broker adapters (HFM, Exness).
"""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import Base
import backend.db.models  # noqa: F401
from backend.db.models.password_reset import PasswordResetToken
from backend.db.models.user import User
from backend.db.session import get_db
from backend.services.broker_adapter import (
    UnsupportedBrokerError,
    get_broker_adapter,
    get_supported_brokers,
    normalize_broker_name,
)
from backend.services.license import (
    activate_license_for_user,
    create_license_record,
    generate_serial_code,
)
from backend.services.password_reset import (
    apply_password_reset,
    create_password_reset_token,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_JWT = "test-secret-key-32-chars-long-auth-features"


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


def test_serial_code_format_and_crypto():
    code1 = generate_serial_code(tier=1)
    assert code1.startswith("AURX-T1-")
    assert len(code1.split("-")) == 5

@pytest.mark.asyncio
async def test_license_creation_and_activation():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as session:
        lic1 = await create_license_record(session, tier=1)
        assert lic1.status == "UNUSED"
        assert lic1.account_limit == 1
        assert lic1.tier == 1

        user_id = uuid.uuid4()
        user = User(id=user_id, email="u1@test.com", hashed_password="h", display_name="U1")
        session.add(user)
        await session.flush()

        activated = await activate_license_for_user(session, serial_code=lic1.serial_code, user_id=user_id)
        assert activated.status == "ACTIVE"
        assert activated.user_id == user_id
        assert activated.activated_at is not None
        assert activated.valid_until is not None

        with pytest.raises(Exception):
            await activate_license_for_user(session, serial_code=lic1.serial_code, user_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_password_reset_flow():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as session:
        user_id = uuid.uuid4()
        user = User(id=user_id, email="reset@test.com", hashed_password="old_hash_password", display_name="Reset User")
        session.add(user)
        await session.flush()

        token = await create_password_reset_token(session, user_id)
        assert token
        assert len(token) > 20

        stmt = select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
        res = await session.execute(stmt)
        record = res.scalar_one()
        assert record.token_hash != token
        assert len(record.token_hash) == 64

        consumed_uid = await apply_password_reset(session, raw_token=token, new_password="BrandNewPassword123!")
        assert consumed_uid == user_id
        assert user.hashed_password != "old_hash_password"

        with pytest.raises(Exception):
            await apply_password_reset(session, raw_token=token, new_password="AnotherPassword123!")

    code2 = generate_serial_code(tier=2)
    assert code2.startswith("AURX-T2-")

    code3 = generate_serial_code(tier=3)
    assert code3.startswith("AURX-T3-")

    with pytest.raises(ValueError):
        generate_serial_code(tier=4)
def test_broker_adapter_normalization():
    assert normalize_broker_name("hfm") == "HFM"
    assert normalize_broker_name("HF Markets") == "HFM"
    assert normalize_broker_name("Exness") == "Exness"
    assert normalize_broker_name("EXNESS LLC") == "Exness"

    with pytest.raises(UnsupportedBrokerError):
        normalize_broker_name("UnsupportedForexBroker")

    hfm = get_broker_adapter("HFM")
    assert hfm.name == "HFM"
    assert hfm.normalize_symbol("XAUUSD") == "XAUUSD"
    assert hfm.normalize_symbol("GOLD") == "XAUUSD"
    assert hfm.normalize_symbol("XAUUSD", is_cent=True) == "XAUUSD.m"

    exness = get_broker_adapter("Exness")
    assert exness.name == "Exness"
    assert exness.normalize_symbol("XAUUSD") == "XAUUSDm"
    assert exness.normalize_symbol("XAUUSD", is_cent=True) == "XAUUSDc"

    brokers = get_supported_brokers()
    assert len(brokers) == 2
    broker_ids = {b["id"] for b in brokers}
    assert broker_ids == {"HFM", "Exness"}


def test_register_with_valid_serial_code(client: TestClient):
    r = client.post("/api/v1/auth/register", json={
        "email": "tier2user@example.com",
        "password": "Password123!",
        "display_name": "Tier 2 Trader",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "tier2user@example.com"
    assert data["tier"] == 1
    assert data["account_limit"] == 1
    assert data["license_status"] == "ACTIVE"
    assert data["license_valid_until"] is not None


def test_register_missing_serial_code_fails_production_check(client: TestClient):
    r = client.post("/api/v1/auth/register", json={
        "email": "fail@example.com",
        "password": "Password123!",
        "display_name": "Fail User",
        "serial_code": "",
    })
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "SERIAL_CODE_REQUIRED"


def test_register_invalid_serial_code_fails(client: TestClient):
    r = client.post("/api/v1/auth/register", json={
        "email": "invalid_serial@example.com",
        "password": "Password123!",
        "display_name": "Invalid Serial User",
        "serial_code": "AURX-T1-FAKE-CODE-9999",
    })
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_SERIAL_CODE"


def test_forgot_and_reset_password_endpoints(client: TestClient):
    client.post("/api/v1/auth/register", json={
        "email": "passreset@example.com",
        "password": "InitialPassword123!",
        "display_name": "Reset Test",
    })

    r_forgot = client.post("/api/v1/auth/forgot-password", json={
        "email": "passreset@example.com",
    })
    assert r_forgot.status_code == 200
    assert "password reset link" in r_forgot.json()["message"]

    r_nonexistent = client.post("/api/v1/auth/forgot-password", json={
        "email": "doesnotexist@example.com",
    })
    assert r_nonexistent.status_code == 200
    assert r_nonexistent.json()["message"] == r_forgot.json()["message"]


def test_brokers_endpoint(client: TestClient):
    r = client.get("/api/v1/accounts/brokers")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    names = [b["id"] for b in data]
    assert "HFM" in names
    assert "Exness" in names


def test_unsupported_broker_in_account_creation_fails(client: TestClient):
    client.post("/api/v1/auth/register", json={
        "email": "broker_test@example.com",
        "password": "Password123!",
        "display_name": "Broker Tester",
    })
    l = client.post("/api/v1/auth/login", json={
        "email": "broker_test@example.com",
        "password": "Password123!",
    })
    token = l.json()["access_token"]

    r = client.post(
        "/api/v1/accounts",
        json={
            "label": "Bad Broker Account",
            "broker": "UnsupportedBrokerName",
            "mt5_account_number": "123456",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "UNSUPPORTED_BROKER"

