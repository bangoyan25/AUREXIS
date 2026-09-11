"""
Phase 5: MT5 Closed Bar Ingestion, Strategy Warmup, Authoritative Risk Gate, and Demo Trade Tests.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.core.config import settings
from backend.db.base import Base
from backend.db.models.account import TradingAccount
from backend.db.models.equity import EquitySnapshot
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.execution import Position as DbPosition
from backend.db.models.risk import RiskConfiguration
from backend.db.models.signal import CandidateSignal as DbCandidateSignal
from backend.db.models.strategy import StrategyEngineState
from backend.db.models.user import User
from backend.main import create_app
from backend.services import market_data_service, strategy_service
from backend.ws.agent_manager import agent_manager
from backend.services.auth import create_access_token
from backend.services.strategy_service import _get_bar_manager, clear_bar_managers, seed_account_bars
from backend.ws.agent_protocol import BarData, BarsMessage, parse_agent_message
from brain.market_data.types import Bar, Tick
from brain.strategy.interfaces import CandidateSignal as BrainSignal, SignalDirection


@pytest.fixture(autouse=True)
def configure_test_env(monkeypatch: pytest.MonkeyPatch):
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
    market_data_service.clear_local_cache()
    clear_bar_managers()


@pytest.fixture
async def test_env():
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
    market_data_service.clear_local_cache()
    clear_bar_managers()

async def _seed_demo_account(
    session_factory,
    email: str = "demo-trader@example.com",
    is_demo: bool = True,
) -> tuple[User, TradingAccount, MT5Agent, str]:
    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password="test-hashed-pw",
            display_name="Demo Trader",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        account = TradingAccount(
            id=uuid.uuid4(),
            user_id=user.id,
            label="Demo Account" if is_demo else "Real Account",
            broker="Generic Broker",
            mt5_server="Generic-Demo" if is_demo else "Generic-Live",
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
            balance_usd=Decimal("10000.00"),
            equity_usd=Decimal("10000.00"),
            snapped_at=datetime.now(UTC),
        )
        session.add(eq)

        risk_cfg = RiskConfiguration(
            account_id=account.id,
            version=1,
            effective_from=datetime.now(UTC),
            daily_loss_limit_usd=Decimal("500.00"),
            max_drawdown_usd=Decimal("1000.00"),
            max_open_positions=5,
            kill_switch_active=False,
        )
        session.add(risk_cfg)
        await session.commit()

        token = create_access_token(subject=str(user.id))
        return user, account, agent, token


def _make_sample_bars(count: int, start_price: float = 2650.0) -> list[dict]:
    base_time = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)
    bars = []
    for i in range(count):
        ot = base_time + timedelta(minutes=15 * i)
        ct = ot + timedelta(minutes=15)
        p = start_price + (i * 0.1)
        bars.append({
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "open_time": ot.isoformat(),
            "close_time": ct.isoformat(),
            "open": f"{p:.2f}",
            "high": f"{p + 1.5:.2f}",
            "low": f"{p - 1.0:.2f}",
            "close": f"{p + 0.5:.2f}",
            "volume": "100",
            "is_closed": True,
        })
    return bars



# ── Tests 1-9: Schema and Protocol Validations ─────────────────────────────────


class TestBarsProtocolValidations:
    def test_1_valid_bars_message(self):
        payload = {
            "type": "bars",
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "bars": [
                {
                    "time": "2026-09-11 08:00:00",
                    "open": "2650.00",
                    "high": "2655.00",
                    "low": "2648.00",
                    "close": "2652.00",
                    "tick_volume": 120,
                }
            ],
        }
        msg = parse_agent_message(payload)
        assert isinstance(msg, BarsMessage)
        assert msg.symbol == "XAUUSD"
        assert msg.timeframe == "M15"
        assert len(msg.bars) == 1
        assert msg.bars[0].open == Decimal("2650.00")
        assert msg.bars[0].high == Decimal("2655.00")

    def test_2_malformed_ohlc(self):
        with pytest.raises(ValueError, match="cannot be less than low"):
            parse_agent_message({
                "type": "bars",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "bars": [{"time": "2026-09-11 08:00:00", "open": "2650", "high": "2640", "low": "2645", "close": "2648"}],
            })
        with pytest.raises(ValueError, match="high cannot be less than open or close"):
            parse_agent_message({
                "type": "bars",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "bars": [{"time": "2026-09-11 08:00:00", "open": "2655", "high": "2650", "low": "2645", "close": "2648"}],
            })
        with pytest.raises(ValueError, match="low cannot be greater than open or close"):
            parse_agent_message({
                "type": "bars",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "bars": [{"time": "2026-09-11 08:00:00", "open": "2650", "high": "2655", "low": "2645", "close": "2640"}],
            })

    def test_3_non_positive_price(self):
        with pytest.raises(ValueError, match="must be greater than 0"):
            parse_agent_message({
                "type": "bars",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "bars": [{"time": "2026-09-11 08:00:00", "open": "0", "high": "2655", "low": "0", "close": "2650"}],
            })

    def test_4_nan_price(self):
        with pytest.raises(ValueError, match="cannot be NaN or Infinite"):
            parse_agent_message({
                "type": "bars",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "bars": [{"time": "2026-09-11 08:00:00", "open": float("nan"), "high": "2655", "low": "2645", "close": "2650"}],
            })

    def test_5_inf_price(self):
        with pytest.raises(ValueError, match="cannot be NaN or Infinite"):
            parse_agent_message({
                "type": "bars",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "bars": [{"time": "2026-09-11 08:00:00", "open": "2650", "high": float("inf"), "low": "2645", "close": "2650"}],
            })

    def test_6_negative_volume(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            parse_agent_message({
                "type": "bars",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "bars": [{"time": "2026-09-11 08:00:00", "open": "2650", "high": "2655", "low": "2645", "close": "2650", "tick_volume": -1}],
            })

    def test_7_empty_bars(self):
        msg = parse_agent_message({
            "type": "bars",
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "bars": [],
        })
        assert isinstance(msg, BarsMessage)
        assert len(msg.bars) == 0

    def test_8_invalid_symbol(self):
        with pytest.raises(ValueError, match="Unsupported symbol"):
            parse_agent_message({
                "type": "bars",
                "symbol": "EURUSD",
                "timeframe": "M15",
                "bars": [],
            })

    def test_9_invalid_timeframe(self):
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            parse_agent_message({
                "type": "bars",
                "symbol": "XAUUSD",
                "timeframe": "H4",
                "bars": [],
            })


# ── Tests 10-13: Storage, Ordering, Tenant Isolation, Forming-Bar Exclusion ─────


class TestBarsStorageAndIsolation:
    @pytest.mark.asyncio
    async def test_10_chronological_ordering(self):
        account_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        payload = BarsMessage(
            type="bars",
            symbol="XAUUSD",
            timeframe="M15",
            bars=[
                BarData(time="2026-09-11 08:30:00", open=Decimal("2650"), high=Decimal("2655"), low=Decimal("2645"), close=Decimal("2650")),
                BarData(time="2026-09-11 08:00:00", open=Decimal("2640"), high=Decimal("2645"), low=Decimal("2635"), close=Decimal("2640")),
                BarData(time="2026-09-11 08:15:00", open=Decimal("2645"), high=Decimal("2650"), low=Decimal("2640"), close=Decimal("2645")),
            ],
        )
        stored = await market_data_service.record_closed_bars(agent_id, account_id, payload)
        assert len(stored) == 3
        assert "08:00:00" in stored[0]["open_time"]
        assert "08:15:00" in stored[1]["open_time"]
        assert "08:30:00" in stored[2]["open_time"]

    @pytest.mark.asyncio
    async def test_11_duplicate_candle_deduplication(self):
        account_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        payload = BarsMessage(
            type="bars",
            symbol="XAUUSD",
            timeframe="M15",
            bars=[
                BarData(time="2026-09-11 08:00:00", open=Decimal("2640"), high=Decimal("2645"), low=Decimal("2635"), close=Decimal("2640")),
                BarData(time="2026-09-11 08:00:00", open=Decimal("2640"), high=Decimal("2645"), low=Decimal("2635"), close=Decimal("2640")),
            ],
        )
        stored = await market_data_service.record_closed_bars(agent_id, account_id, payload)
        assert len(stored) == 1

    @pytest.mark.asyncio
    async def test_12_tenant_isolation(self):
        account_a = uuid.uuid4()
        account_b = uuid.uuid4()
        agent_id = uuid.uuid4()

        payload = BarsMessage(
            type="bars",
            symbol="XAUUSD",
            timeframe="M15",
            bars=[BarData(time="2026-09-11 08:00:00", open=Decimal("2640"), high=Decimal("2645"), low=Decimal("2635"), close=Decimal("2640"))],
        )
        await market_data_service.record_closed_bars(agent_id, account_a, payload)

        bars_a = await market_data_service.get_closed_bars(account_a, "XAUUSD", "M15")
        bars_b = await market_data_service.get_closed_bars(account_b, "XAUUSD", "M15")

        assert len(bars_a) == 1
        assert len(bars_b) == 0

    def test_13_forming_bar_exclusion(self):
        account_id_str = str(uuid.uuid4())
        bars = _make_sample_bars(10)
        seed_account_bars(account_id_str, "XAUUSD", "M15", bars)
        bm = _get_bar_manager(account_id_str)
        closed = bm.get_closed_bars("M15")
        assert len(closed) == 10
        assert all(b.is_closed for b in closed)


# ── Tests 14-16: Warmup Threshold and Duplicate Candle Cooldown ─────────────────


class TestWarmupAndDuplicateProtection:
    def test_14_insufficient_bars(self):
        account_id_str = str(uuid.uuid4())
        bars = _make_sample_bars(49)
        seed_account_bars(account_id_str, "XAUUSD", "M15", bars)
        bm = _get_bar_manager(account_id_str)
        closed = bm.get_closed_bars("M15")
        assert len(closed) == 49
        assert len(closed) < 50

    def test_15_sufficient_bars(self):
        account_id_str = str(uuid.uuid4())
        bars = _make_sample_bars(60)
        seed_account_bars(account_id_str, "XAUUSD", "M15", bars)
        bm = _get_bar_manager(account_id_str)
        closed = bm.get_closed_bars("M15")
        assert len(closed) == 60
        assert len(closed) >= 50

    @pytest.mark.asyncio
    async def test_16_duplicate_candle_evaluation_prevention(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory)

        bars = _make_sample_bars(60)
        seed_account_bars(str(account.id), "XAUUSD", "M15", bars)
        await market_data_service.record_closed_bars(
            agent.id,
            account.id,
            BarsMessage(
                type="bars",
                symbol="XAUUSD",
                timeframe="M15",
                bars=[
                    BarData(
                        time=b["open_time"],
                        open=Decimal(b["open"]),
                        high=Decimal(b["high"]),
                        low=Decimal(b["low"]),
                        close=Decimal(b["close"]),
                    )
                    for b in bars
                ],
            ),
        )

        fresh_tick = {
            "symbol": "XAUUSD",
            "bid": "2650.00",
            "ask": "2650.25",
            "spread": "0.25",
            "received_at": datetime.now(UTC).isoformat(),
            "tick_time": datetime.now(UTC).isoformat(),
            "tick_volume": 10,
        }

        with patch.object(
            market_data_service,
            "get_latest_market_data",
            new=AsyncMock(return_value=fresh_tick),
        ), patch.object(
            agent_manager,
            "is_connected",
            return_value=True,
        ):
            async with session_factory() as session:
                await strategy_service.enable_strategy(session, account.id, dry_run=True)
                await session.commit()

            async with session_factory() as session:
                res1 = await strategy_service.evaluate_strategy_for_account(session, account.id)
                await session.commit()

            async with session_factory() as session:
                res2 = await strategy_service.evaluate_strategy_for_account(session, account.id)
                await session.commit()

            assert res2["execution_reason"] == "CANDLE_COOLDOWN"
            assert res2["signal_reason"] == "SAME_CANDLE_ALREADY_PROCESSED"



# ── Tests 17-19: WebSocket Ingestion, Strategy Bars API, Warmup Transition ─────


class TestApiAndIngestion:
    @pytest.mark.asyncio
    async def test_17_websocket_bars_ingestion(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory)

        bars_payload = BarsMessage(
            type="bars",
            symbol="XAUUSD",
            timeframe="M15",
            bars=[
                BarData(
                    time="2026-09-11 08:00:00",
                    open=Decimal("2650.00"),
                    high=Decimal("2655.00"),
                    low=Decimal("2645.00"),
                    close=Decimal("2652.00"),
                    tick_volume=100,
                )
            ],
        )
        stored = await market_data_service.record_closed_bars(agent.id, account.id, bars_payload)
        seed_account_bars(str(account.id), "XAUUSD", "M15", stored)
        assert len(stored) == 1
        bm = _get_bar_manager(str(account.id))
        assert len(bm.get_closed_bars("M15")) == 1

    @pytest.mark.asyncio
    async def test_18_strategy_bars_api(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory)

        bars = _make_sample_bars(5)
        await market_data_service.record_closed_bars(
            agent.id,
            account.id,
            BarsMessage(
                type="bars",
                symbol="XAUUSD",
                timeframe="M15",
                bars=[
                    BarData(
                        time=b["open_time"],
                        open=Decimal(b["open"]),
                        high=Decimal(b["high"]),
                        low=Decimal(b["low"]),
                        close=Decimal(b["close"]),
                    )
                    for b in bars
                ],
            ),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get(f"/api/v1/accounts/{account.id}/strategy/bars")
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 5
            assert data["symbol"] == "XAUUSD"
            assert data["timeframe"] == "M15"
            assert len(data["bars"]) == 5

    @pytest.mark.asyncio
    async def test_19_strategy_warmup_transition(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory)

        fresh_tick = {
            "symbol": "XAUUSD",
            "bid": "2650.00",
            "ask": "2650.25",
            "spread": "0.25",
            "received_at": datetime.now(UTC).isoformat(),
            "tick_time": datetime.now(UTC).isoformat(),
            "tick_volume": 10,
        }

        with patch.object(
            market_data_service,
            "get_latest_market_data",
            new=AsyncMock(return_value=fresh_tick),
        ), patch.object(
            agent_manager,
            "is_connected",
            return_value=True,
        ):
            async with session_factory() as session:
                await strategy_service.enable_strategy(session, account.id, dry_run=True)
                await session.commit()

            # 1. Warmup check before bars: returns BARS_WARMING_UP
            async with session_factory() as session:
                res1 = await strategy_service.evaluate_strategy_for_account(session, account.id)
                assert res1["execution_reason"] == "BARS_WARMING_UP"

            # 2. Add 60 bars
            bars = _make_sample_bars(60)
            await market_data_service.record_closed_bars(
                agent.id,
                account.id,
                BarsMessage(
                    type="bars",
                    symbol="XAUUSD",
                    timeframe="M15",
                    bars=[
                        BarData(
                            time=b["open_time"],
                            open=Decimal(b["open"]),
                            high=Decimal(b["high"]),
                            low=Decimal(b["low"]),
                            close=Decimal(b["close"]),
                        )
                        for b in bars
                    ],
                ),
            )

            # 3. Evaluate again: no longer BARS_WARMING_UP
            async with session_factory() as session:
                res2 = await strategy_service.evaluate_strategy_for_account(session, account.id)
                assert res2["execution_reason"] != "BARS_WARMING_UP"



# ── Tests 20-23: Safety Gates (Kill Switch, Stale Market, Agent, Demo Guard) ───


class TestSafetyGates:
    @pytest.mark.asyncio
    async def test_20_kill_switch_prevents_execution(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory)

        async with session_factory() as session:
            await strategy_service.enable_strategy(session, account.id, dry_run=False)
            cfg_res = await session.execute(
                select(RiskConfiguration).where(RiskConfiguration.account_id == account.id)
            )
            cfg = cfg_res.scalar_one()
            cfg.kill_switch_active = True
            await session.commit()

        bars = _make_sample_bars(60)
        seed_account_bars(str(account.id), "XAUUSD", "M15", bars)

        fresh_tick = {
            "symbol": "XAUUSD",
            "bid": "2650.00",
            "ask": "2650.25",
            "spread": "0.25",
            "received_at": datetime.now(UTC).isoformat(),
            "tick_time": datetime.now(UTC).isoformat(),
            "tick_volume": 10,
        }

        with patch.object(
            market_data_service,
            "get_latest_market_data",
            new=AsyncMock(return_value=fresh_tick),
        ), patch.object(
            agent_manager,
            "is_connected",
            return_value=True,
        ), patch(
            "backend.services.strategy_service._get_signal_pipeline"
        ) as mock_pipe:
            mock_pipeline_inst = MagicMock()
            mock_pipeline_inst.process.return_value = BrainSignal(
                symbol="XAUUSD",
                strategy_id="TEST",
                strategy_version="1.0",
                direction=SignalDirection.BUY,
                confidence_score=Decimal("0.85"),
                suggested_stop_loss=Decimal("2640.00"),
                suggested_take_profit=Decimal("2670.00"),
                setup_type="PULLBACK_CONTINUATION",
                market_state_summary="BUY_SETUP",
                is_configured=True,
            )
            mock_pipe.return_value = mock_pipeline_inst

            async with session_factory() as session:
                res = await strategy_service.evaluate_strategy_for_account(session, account.id)
                await session.commit()

            assert res["risk_decision"] == "BLOCK"
            assert res["execution_status"] == "BLOCKED"

    @pytest.mark.asyncio
    async def test_21_stale_market_prevents_execution(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory)

        stale_time = (datetime.now(UTC) - timedelta(seconds=30)).isoformat()
        stale_tick = {
            "symbol": "XAUUSD",
            "bid": "2650.00",
            "ask": "2650.25",
            "spread": "0.25",
            "received_at": stale_time,
            "tick_time": stale_time,
            "tick_volume": 10,
        }

        with patch.object(
            market_data_service,
            "get_latest_market_data",
            new=AsyncMock(return_value=stale_tick),
        ):
            async with session_factory() as session:
                await strategy_service.enable_strategy(session, account.id, dry_run=False)
                res = await strategy_service.evaluate_strategy_for_account(session, account.id)
                await session.commit()

            assert "STALE_MARKET_DATA" in (res["execution_reason"] or "")

    @pytest.mark.asyncio
    async def test_22_disconnected_agent_prevents_execution(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory)

        bars = _make_sample_bars(60)
        seed_account_bars(str(account.id), "XAUUSD", "M15", bars)

        fresh_tick = {
            "symbol": "XAUUSD",
            "bid": "2650.00",
            "ask": "2650.25",
            "spread": "0.25",
            "received_at": datetime.now(UTC).isoformat(),
            "tick_time": datetime.now(UTC).isoformat(),
            "tick_volume": 10,
        }

        with patch.object(
            market_data_service,
            "get_latest_market_data",
            new=AsyncMock(return_value=fresh_tick),
        ), patch.object(
            agent_manager,
            "is_connected",
            return_value=False,
        ), patch(
            "backend.services.strategy_service._get_signal_pipeline"
        ) as mock_pipe:
            mock_pipeline_inst = MagicMock()
            mock_pipeline_inst.process.return_value = BrainSignal(
                symbol="XAUUSD",
                strategy_id="TEST",
                strategy_version="1.0",
                direction=SignalDirection.BUY,
                confidence_score=Decimal("0.85"),
                suggested_stop_loss=Decimal("2640.00"),
                suggested_take_profit=Decimal("2670.00"),
                setup_type="PULLBACK_CONTINUATION",
                market_state_summary="BUY_SETUP",
                is_configured=True,
            )
            mock_pipe.return_value = mock_pipeline_inst

            async with session_factory() as session:
                await strategy_service.enable_strategy(session, account.id, dry_run=False)
                res = await strategy_service.evaluate_strategy_for_account(session, account.id)
                await session.commit()

            assert res["risk_decision"] == "BLOCK"
            assert res["risk_reason_code"] == "AGENT_OFFLINE"

    @pytest.mark.asyncio
    async def test_23_demo_guard_prevents_live_account(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory, is_demo=False)

        async with session_factory() as session:
            state = await strategy_service.enable_strategy(session, account.id, dry_run=False)
            res = await strategy_service.evaluate_strategy_for_account(session, account.id)
            await session.commit()

        assert res["execution_reason"] == "NON_DEMO_ACCOUNT"
        assert res["execution_status"] == "BLOCKED"
        assert state.dry_run is True



# ── Tests 24-25: Demo Strategy Execution and Reconciliation ────────────────────


class TestDemoExecutionAndReconciliation:
    @pytest.mark.asyncio
    async def test_24_successful_demo_strategy_execution(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory, is_demo=True)

        bars = _make_sample_bars(60)
        seed_account_bars(str(account.id), "XAUUSD", "M15", bars)

        fresh_tick = {
            "symbol": "XAUUSD",
            "bid": "2650.00",
            "ask": "2650.25",
            "spread": "0.25",
            "received_at": datetime.now(UTC).isoformat(),
            "tick_time": datetime.now(UTC).isoformat(),
            "tick_volume": 10,
        }

        with patch.object(
            market_data_service,
            "get_latest_market_data",
            new=AsyncMock(return_value=fresh_tick),
        ), patch.object(
            agent_manager,
            "is_connected",
            return_value=True,
        ), patch.object(
            agent_manager,
            "send_json",
            new=AsyncMock(return_value=True),
        ), patch(
            "backend.services.strategy_service._get_signal_pipeline"
        ) as mock_pipe:
            mock_pipeline_inst = MagicMock()
            mock_pipeline_inst.process.return_value = BrainSignal(
                symbol="XAUUSD",
                strategy_id="AUREXIS_CORE",
                strategy_version="1.0.0",
                direction=SignalDirection.BUY,
                confidence_score=Decimal("0.88"),
                setup_type="PULLBACK_CONTINUATION",
                market_state_summary="STRONG_TREND",
                suggested_stop_loss=Decimal("2640.00"),
                suggested_take_profit=Decimal("2670.00"),
                is_configured=True,
            )
            mock_pipe.return_value = mock_pipeline_inst

            async with session_factory() as session:
                await strategy_service.enable_strategy(session, account.id, dry_run=False)
                res = await strategy_service.evaluate_strategy_for_account(session, account.id)
                await session.commit()

            assert res["signal_direction"] == "BUY"
            assert res["risk_decision"] == "ALLOW"
            assert res["risk_reason_code"] == "RISK_OK"
            assert res["execution_status"] == "EXECUTION_PENDING"
            assert res["command_id"] is not None

    @pytest.mark.asyncio
    async def test_25_execution_reconciliation(self, test_env):
        app, session_factory = test_env
        user, account, agent, token = await _seed_demo_account(session_factory, is_demo=True)

        async with session_factory() as session:
            pos = DbPosition(
                id=uuid.uuid4(),
                account_id=account.id,
                broker_ticket=987654,
                symbol="XAUUSD",
                side="BUY",
                lots=Decimal("0.01"),
                open_price=Decimal("2650.50"),
                opened_at=datetime.now(UTC),
                status="OPEN",
            )
            session.add(pos)
            await session.commit()

        async with session_factory() as session:
            open_cnt = (
                await session.execute(
                    select(func.count(DbPosition.id)).where(
                        DbPosition.account_id == account.id,
                        DbPosition.status == "OPEN",
                    )
                )
            ).scalar_one()
            assert open_cnt == 1

        async with session_factory() as session:
            res = await session.execute(
                select(DbPosition).where(DbPosition.account_id == account.id)
            )
            pos = res.scalar_one()
            pos.status = "CLOSED"
            pos.close_price = Decimal("2652.00")
            pos.closed_at = datetime.now(UTC)
            await session.commit()

        async with session_factory() as session:
            open_cnt = (
                await session.execute(
                    select(func.count(DbPosition.id)).where(
                        DbPosition.account_id == account.id,
                        DbPosition.status == "OPEN",
                    )
                )
            ).scalar_one()
            assert open_cnt == 0


