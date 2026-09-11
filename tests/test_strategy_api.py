"""
Phase 4B: Strategy Engine API Tests.

Covers:
1.  GET strategy for own account → 200
2.  GET strategy for tenant B's account → 404
3.  POST enable (no body) → dry_run=True, 200
4.  POST enable explicit dry_run=True → 200
5.  POST disable → 200, enabled=False
6.  POST evaluate (disabled strategy) → 200, STRATEGY_DISABLED
7.  GET latest signal when empty → signal=null, 200
8.  GET latest signal only shows own account's signals
9.  Tenant B cannot evaluate account A → 404
10. Tenant B cannot enable account A → 404
11. Tenant B cannot disable account A → 404
12. Tenant B cannot read signals of account A → 404
13. dry_run=True does not cause broker order
14. Risk Gate blocks execution when data stale
15. Unauthenticated requests → 401
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

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
from backend.db.models.signal import CandidateSignal as DbCandidateSignal
from backend.db.models.strategy import StrategyEngineState
from backend.db.models.user import User
from backend.main import create_app
from backend.services import market_data_service
from backend.services.auth import create_access_token
from backend.services import strategy_service


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def configure_test_env(monkeypatch: pytest.MonkeyPatch):
    """Provide test JWT secret and mock redis."""
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
async def test_env():
    """In-memory SQLite app with get_db override."""
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

    # Clear bar manager cache between tests
    strategy_service.clear_bar_managers()

    yield app, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()
    strategy_service.clear_bar_managers()


async def _seed_demo_account(
    session_factory,
    email: str = "trader@example.com",
) -> tuple[User, TradingAccount, MT5Agent, str]:
    """Seed user + demo account + agent + equity + risk config. Return token."""
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
            label="Demo Strategy Account",
            broker="Demo Broker",
            mt5_server="MetaQuotes-Demo",
            mt5_account_number=f"5055{uuid.uuid4().hex[:6]}",
            is_cent_account=False,
            cent_normalization_factor=Decimal("1.0"),
            is_active=True,
            trading_enabled=True,
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
            balance_usd=Decimal("1000.00"),
            equity_usd=Decimal("1000.00"),
            snapped_at=datetime.now(UTC),
        )
        session.add(eq)

        cfg = RiskConfiguration(
            account_id=account.id,
            version=1,
            effective_from=datetime.now(UTC),
            daily_loss_limit_usd=Decimal("50.00"),
            max_drawdown_usd=Decimal("100.00"),
            max_open_positions=5,
        )
        session.add(cfg)
        await session.commit()

        token = create_access_token(subject=str(user.id))
        return user, account, agent, token


# ── Test classes ──────────────────────────────────────────────────────────────


class TestStrategyStateEndpoint:
    """Test 1: GET strategy for own account → 200
       Test 15: Unauthenticated → 401
    """

    @pytest.mark.asyncio
    async def test_get_strategy_state_own_account(self, test_env):
        """GET /accounts/{id}/strategy returns 200 with valid state fields."""
        app, sf = test_env
        _, account, _, token = await _seed_demo_account(sf, "user1@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(
                f"/api/v1/accounts/{account.id}/strategy",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["account_id"] == str(account.id)
        assert data["enabled"] is False
        assert data["dry_run"] is True
        assert data["strategy_id"] == "AUREXIS_CORE"
        assert data["symbol"] == "XAUUSD"
        assert data["timeframe"] == "M15"

    @pytest.mark.asyncio
    async def test_get_strategy_unauthenticated(self, test_env):
        """Unauthenticated request → 401."""
        app, sf = test_env
        _, account, _, _ = await _seed_demo_account(sf, "user2@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(f"/api/v1/accounts/{account.id}/strategy")
        assert res.status_code == 401


class TestStrategyTenantIsolation:
    """Tests 2, 9, 10, 11, 12: Tenant B cannot access account A."""

    @pytest.mark.asyncio
    async def test_get_strategy_tenant_isolation(self, test_env):
        """Test 2: Tenant B reading account A → 404."""
        app, sf = test_env
        _, account_a, _, _ = await _seed_demo_account(sf, "usera@example.com")
        _, _, _, token_b = await _seed_demo_account(sf, "userb@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(
                f"/api/v1/accounts/{account_a.id}/strategy",
                headers={"Authorization": f"Bearer {token_b}"},
            )
        assert res.status_code == 404
        assert res.json()["detail"] == "Account not found"

    @pytest.mark.asyncio
    async def test_enable_tenant_isolation(self, test_env):
        """Test 10: Tenant B cannot enable account A."""
        app, sf = test_env
        _, account_a, _, _ = await _seed_demo_account(sf, "usera2@example.com")
        _, _, _, token_b = await _seed_demo_account(sf, "userb2@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.post(
                f"/api/v1/accounts/{account_a.id}/strategy/enable",
                headers={"Authorization": f"Bearer {token_b}"},
            )
        assert res.status_code == 404
        assert res.json()["detail"] == "Account not found"

    @pytest.mark.asyncio
    async def test_disable_tenant_isolation(self, test_env):
        """Test 11: Tenant B cannot disable account A."""
        app, sf = test_env
        _, account_a, _, _ = await _seed_demo_account(sf, "usera3@example.com")
        _, _, _, token_b = await _seed_demo_account(sf, "userb3@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.post(
                f"/api/v1/accounts/{account_a.id}/strategy/disable",
                headers={"Authorization": f"Bearer {token_b}"},
            )
        assert res.status_code == 404
        assert res.json()["detail"] == "Account not found"

    @pytest.mark.asyncio
    async def test_evaluate_tenant_isolation(self, test_env):
        """Test 9: Tenant B cannot evaluate account A."""
        app, sf = test_env
        _, account_a, _, _ = await _seed_demo_account(sf, "usera4@example.com")
        _, _, _, token_b = await _seed_demo_account(sf, "userb4@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.post(
                f"/api/v1/accounts/{account_a.id}/strategy/evaluate",
                headers={"Authorization": f"Bearer {token_b}"},
            )
        assert res.status_code == 404
        assert res.json()["detail"] == "Account not found"

    @pytest.mark.asyncio
    async def test_signals_tenant_isolation(self, test_env):
        """Test 12: Tenant B cannot read signals of account A."""
        app, sf = test_env
        _, account_a, _, _ = await _seed_demo_account(sf, "usera5@example.com")
        _, _, _, token_b = await _seed_demo_account(sf, "userb5@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(
                f"/api/v1/accounts/{account_a.id}/strategy/signals/latest",
                headers={"Authorization": f"Bearer {token_b}"},
            )
        assert res.status_code == 404
        assert res.json()["detail"] == "Account not found"




class TestEnableDisableStrategy:
    """Tests 3, 4, 5."""

    @pytest.mark.asyncio
    async def test_enable_no_body_defaults_dry_run_true(self, test_env):
        """Test 3: POST enable with no body → dry_run=True."""
        app, sf = test_env
        _, account, _, token = await _seed_demo_account(sf, "e1@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.post(
                f"/api/v1/accounts/{account.id}/strategy/enable",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["enabled"] is True
        assert data["dry_run"] is True

    @pytest.mark.asyncio
    async def test_enable_explicit_dry_run_true(self, test_env):
        """Test 4: POST enable with explicit dry_run=true → dry_run=True."""
        app, sf = test_env
        _, account, _, token = await _seed_demo_account(sf, "e2@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.post(
                f"/api/v1/accounts/{account.id}/strategy/enable",
                headers={"Authorization": f"Bearer {token}"},
                json={"dry_run": True},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["enabled"] is True
        assert data["dry_run"] is True

    @pytest.mark.asyncio
    async def test_disable_strategy(self, test_env):
        """Test 5: POST disable → enabled=False, 200."""
        app, sf = test_env
        _, account, _, token = await _seed_demo_account(sf, "e3@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post(
                f"/api/v1/accounts/{account.id}/strategy/enable",
                headers={"Authorization": f"Bearer {token}"},
            )
            res = await c.post(
                f"/api/v1/accounts/{account.id}/strategy/disable",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["enabled"] is False


class TestLatestSignal:
    """Tests 7, 8."""

    @pytest.mark.asyncio
    async def test_latest_signal_empty(self, test_env):
        """Test 7: GET latest signal when no signals exist → signal=null."""
        app, sf = test_env
        _, account, _, token = await _seed_demo_account(sf, "sig1@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(
                f"/api/v1/accounts/{account.id}/strategy/signals/latest",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["signal"] is None
        assert data["account_id"] == str(account.id)

    @pytest.mark.asyncio
    async def test_latest_signal_only_own_account(self, test_env):
        """Test 8: Account A queries latest signal — must not see Account B's signals."""
        app, sf = test_env
        _, account_a, _, token_a = await _seed_demo_account(sf, "siga@example.com")
        _, account_b, _, _ = await _seed_demo_account(sf, "sigb@example.com")

        async with sf() as session:
            sig_b = DbCandidateSignal(
                id=uuid.uuid4(),
                account_id=account_b.id,
                correlation_id=str(uuid.uuid4()),
                symbol="XAUUSD",
                direction="BUY",
                strategy_id="AUREXIS_CORE",
                strategy_version="AUREXIS-STRAT-1.0.0",
                status="PROPOSED",
                generated_at=datetime.now(UTC),
            )
            session.add(sig_b)
            await session.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(
                f"/api/v1/accounts/{account_a.id}/strategy/signals/latest",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["signal"] is None

    @pytest.mark.asyncio
    async def test_latest_signal_with_existing_signal(self, test_env):
        """GET latest signal returns CandidateSignal when one exists for own account."""
        app, sf = test_env
        _, account, _, token = await _seed_demo_account(sf, "sig2@example.com")

        async with sf() as session:
            sig = DbCandidateSignal(
                id=uuid.uuid4(),
                account_id=account.id,
                correlation_id=str(uuid.uuid4()),
                symbol="XAUUSD",
                direction="SELL",
                strategy_id="AUREXIS_CORE",
                strategy_version="AUREXIS-STRAT-1.0.0",
                status="PROPOSED",
                generated_at=datetime.now(UTC),
            )
            session.add(sig)
            await session.commit()
            signal_id = str(sig.id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(
                f"/api/v1/accounts/{account.id}/strategy/signals/latest",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["signal"] is not None
        assert data["signal"]["id"] == signal_id
        assert data["signal"]["direction"] == "SELL"
        assert data["signal"]["symbol"] == "XAUUSD"
        assert data["account_id"] == str(account.id)


class TestEvaluateStrategy:
    """Tests 6, 13, 14."""

    @pytest.mark.asyncio
    async def test_evaluate_disabled_strategy(self, test_env):
        """Test 6: POST evaluate with disabled strategy → STRATEGY_DISABLED."""
        app, sf = test_env
        _, account, _, token = await _seed_demo_account(sf, "ev1@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.post(
                f"/api/v1/accounts/{account.id}/strategy/evaluate",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["execution_reason"] == "STRATEGY_DISABLED"
        assert data["execution_status"] == "SKIPPED"

    @pytest.mark.asyncio
    async def test_dry_run_does_not_send_broker_order(self, test_env):
        """Test 13: dry_run=True never causes broker order dispatch via agent_manager."""
        app, sf = test_env
        _, account, agent, token = await _seed_demo_account(sf, "ev2@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post(
                f"/api/v1/accounts/{account.id}/strategy/enable",
                headers={"Authorization": f"Bearer {token}"},
                json={"dry_run": True},
            )

        fresh_tick = {
            "symbol": "XAUUSD",
            "bid": "2645.10",
            "ask": "2645.35",
            "spread": "0.25",
            "point": "0.01",
            "digits": 2,
            "tick_time": datetime.now(UTC).strftime("%Y.%m.%d %H:%M:%S"),
            "received_at": datetime.now(UTC).isoformat(),
            "tick_volume": 100,
        }

        from backend.ws.agent_manager import agent_manager

        with patch.object(
            market_data_service,
            "get_latest_market_data",
            new=AsyncMock(return_value=fresh_tick),
        ), patch.object(
            market_data_service,
            "evaluate_freshness",
            return_value=(True, "FRESH", 100),
        ), patch.object(
            agent_manager,
            "send_json",
            new=AsyncMock(return_value=True),
        ) as mock_send:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                res = await c.post(
                    f"/api/v1/accounts/{account.id}/strategy/evaluate",
                    headers={"Authorization": f"Bearer {token}"},
                )
            data = res.json()
            assert res.status_code == 200
            exec_status = data.get("execution_status", "")
            assert exec_status not in ("EXECUTION_PENDING",), (
                f"dry_run=True must never result in EXECUTION_PENDING, got: {exec_status}"
            )
            # send_json must not be called during dry_run
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_no_market_data(self, test_env):
        """Test 14: Evaluate returns blocked state when market data unavailable."""
        app, sf = test_env
        _, account, _, token = await _seed_demo_account(sf, "ev3@example.com")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post(
                f"/api/v1/accounts/{account.id}/strategy/enable",
                headers={"Authorization": f"Bearer {token}"},
                json={"dry_run": True},
            )

        with patch.object(
            market_data_service,
            "get_latest_market_data",
            new=AsyncMock(return_value=None),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                res = await c.post(
                    f"/api/v1/accounts/{account.id}/strategy/evaluate",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert res.status_code == 200
        data = res.json()
        assert data["execution_status"] != "EXECUTION_PENDING"
        assert data.get("execution_reason") is not None

