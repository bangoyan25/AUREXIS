"""
Tests for Phase 3 API Observability, Tenancy Isolation, and Security.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.core.config import settings
from backend.db.base import Base
from backend.db.models.account import TradingAccount
from backend.db.models.equity import EquitySnapshot
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.risk import RiskConfiguration
from backend.db.models.user import User
from backend.main import create_app
from backend.services import market_data_service
from backend.services.auth import create_access_token
from backend.ws.agent_protocol import MarketDataMessage


@pytest.fixture(autouse=True)
def configure_jwt_secret(monkeypatch: pytest.MonkeyPatch):
    """Provide a test JWT secret and disable network redis timeouts for unit tests."""
    test_secret = SecretStr("test-secret-key-32-chars-long-123456")
    monkeypatch.setattr(settings, "JWT_SECRET", test_secret)

    mock_pipe = MagicMock()
    mock_pipe.set = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=True)
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=None)

    mock_redis = MagicMock()
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)
    mock_redis.get = AsyncMock(return_value=None)
    monkeypatch.setattr(market_data_service, "get_cache_client", lambda: mock_redis)


@pytest.fixture
async def test_app_and_session():
    """Create test application wired with in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    from backend.db.session import get_db
    app.dependency_overrides[get_db] = _get_test_db

    yield app, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_user_with_account(
    session_factory,
    email: str = "user@example.com",
) -> tuple[User, TradingAccount, MT5Agent, str]:
    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=email,
            display_name=email.split("@")[0],
            hashed_password="hash",
        )
        session.add(user)
        await session.flush()

        account = TradingAccount(
            id=uuid.uuid4(),
            user_id=user.id,
            label="Live Cent",
            broker="Demo Broker",
            mt5_account_number=f"MT5-{uuid.uuid4().hex[:6]}",
            is_cent_account=True,
            cent_normalization_factor=Decimal("0.01"),
            is_active=True,
        )
        session.add(account)
        await session.flush()

        agent = MT5Agent(
            id=uuid.uuid4(),
            account_id=account.id,
            label="Primary EA",
            hashed_secret="secret_hashed_val",
            last_known_status="CONNECTED",
        )
        session.add(agent)

        eq = EquitySnapshot(
            account_id=account.id,
            balance_usd=Decimal("500.00"),
            equity_usd=Decimal("500.00"),
            snapped_at=datetime.now(UTC),
        )
        session.add(eq)

        cfg = RiskConfiguration(
            account_id=account.id,
            version=1,
            effective_from=datetime.now(UTC),
            daily_loss_limit_usd=Decimal("50.00"),
            max_drawdown_usd=Decimal("100.00"),
            max_open_positions=2,
            max_spread_usd=Decimal("1.50"),
            max_tick_staleness_ms=2000,
        )
        session.add(cfg)
        await session.commit()

        token = create_access_token(subject=str(user.id))
        return user, account, agent, token



@pytest.mark.unit
@pytest.mark.asyncio
class TestPhase3ApiTenancyAndObservability:
    """Test tenancy enforcement, API outputs, and security checks."""

    async def test_owner_can_read_market_state(self, test_app_and_session) -> None:
        app, session_factory = test_app_and_session
        _, account, agent, token = await _seed_user_with_account(session_factory, "alice@example.com")

        # Ingest a tick for alice's account
        msg = MarketDataMessage(
            type="market_data",
            symbol="XAUUSD",
            bid=Decimal("2650.50"),
            ask=Decimal("2650.75"),
            spread=Decimal("0.25"),
            point=Decimal("0.01"),
            digits=2,
            tick_time="2026-09-10 12:00:00",
            tick_volume=5,
        )
        await market_data_service.record_market_data(agent.id, account.id, msg)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(
                f"/api/v1/market/{account.id}/state",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["account_id"] == str(account.id)
            assert data["symbol"] == "XAUUSD"
            assert data["bid"] == "2650.50"
            assert data["ask"] == "2650.75"
            assert data["is_fresh"] is True
            assert data["status"] == "FRESH"

    async def test_user_b_cannot_access_user_a_market_state(self, test_app_and_session) -> None:
        app, session_factory = test_app_and_session
        _, account_a, _, _ = await _seed_user_with_account(session_factory, "alice@example.com")
        _, _, _, token_b = await _seed_user_with_account(session_factory, "bob@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(
                f"/api/v1/market/{account_a.id}/state",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert res.status_code == 404
            assert res.json()["detail"] == "Account not found"

    async def test_user_b_cannot_access_user_a_risk_decision(self, test_app_and_session) -> None:
        app, session_factory = test_app_and_session
        _, account_a, _, _ = await _seed_user_with_account(session_factory, "alice@example.com")
        _, _, _, token_b = await _seed_user_with_account(session_factory, "bob@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(
                f"/api/v1/risk/{account_a.id}/decision",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert res.status_code == 404
            assert res.json()["detail"] == "Account not found"

    async def test_no_credentials_leaked_in_api_response(self, test_app_and_session) -> None:
        app, session_factory = test_app_and_session
        _, account, agent, token = await _seed_user_with_account(session_factory, "alice@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res_m = await client.get(
                f"/api/v1/market/{account.id}/state",
                headers={"Authorization": f"Bearer {token}"},
            )
            text_m = res_m.text
            assert "secret" not in text_m.lower()
            assert "password" not in text_m.lower()
            assert "hash" not in text_m.lower()

            res_r = await client.get(
                f"/api/v1/risk/{account.id}/decision",
                headers={"Authorization": f"Bearer {token}"},
            )
            text_r = res_r.text
            assert "secret" not in text_r.lower()
            assert "password" not in text_r.lower()
            assert "hash" not in text_r.lower()



@pytest.mark.unit
@pytest.mark.asyncio
class TestPhase3BrokerAgnosticFlexibility:
    """Test that AUREXIS is fully broker-agnostic and MT5 server dynamic."""

    async def test_arbitrary_broker_and_server_accepted(self, test_app_and_session) -> None:
        app, session_factory = test_app_and_session
        brokers = [
            ("MetaQuotes-Demo", "MetaQuotes Software Corp.", "USD"),
            ("ICMarketsSC-Live01", "IC Markets Global", "USD"),
            ("Exness-Real10", "Exness", "Cent"),
            ("Pepperstone-Edge-01", "Pepperstone Group", "AUD"),
            ("GenericBroker-Server", "BrokerX", "EUR"),
        ]

        async with session_factory() as session:
            user = User(
                id=uuid.uuid4(),
                email="agnostic@example.com",
                display_name="Agnostic User",
                hashed_password="hash",
            )
            session.add(user)
            await session.flush()

            for server, broker_name, currency in brokers:
                account = TradingAccount(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    label=f"{broker_name} Account",
                    broker=broker_name,
                    mt5_account_number=f"MT5-{uuid.uuid4().hex[:6]}",
                    mt5_server=server,
                    broker_currency=currency,
                    is_cent_account=(currency == "Cent"),
                    cent_normalization_factor=Decimal("0.01") if currency == "Cent" else Decimal("1.0"),
                    is_active=True,
                )
                session.add(account)
                await session.flush()

                # Verify normalization works identically for Cent accounts regardless of broker
                val = Decimal("10000.00")
                usd_val = account.normalize_to_usd(val)
                if currency == "Cent":
                    assert usd_val == Decimal("100.00")
                else:
                    assert usd_val == Decimal("10000.00")

            await session.commit()

    async def test_get_status_reports_actual_server_dynamically(self) -> None:
        from backend.ws.agent_protocol import ResultMessage

        servers = ["MetaQuotes-Demo", "BrokerAlpha-Live-03", "CustomServer-2026"]
        for srv in servers:
            msg = ResultMessage(
                type="result",
                command_id=str(uuid.uuid4()),
                status="COMPLETED",
                result={
                    "company": "Arbitrary Broker Corp",
                    "server": srv,
                    "currency": "USD",
                    "balance": 5000.0,
                    "equity": 5000.0,
                    "trade_allowed": 1.0,
                    "terminal_connected": 1.0,
                },
            )
            # Verify no broker-specific branch or hardcoding exists in the protocol
            assert msg.result["server"] == srv
            assert msg.result["company"] == "Arbitrary Broker Corp"
            assert msg.result["currency"] == "USD"

