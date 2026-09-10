"""
Tests for Phase 3 Server-Side Risk Gate.
Verifies authoritative ALLOW/BLOCK evaluation, deterministic reason codes,
and invariant that NO trade execution ever occurs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models.account import TradingAccount
from backend.db.models.equity import EquitySnapshot
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.risk import RiskConfiguration
from backend.db.models.user import User
from backend.services.risk_gate import evaluate_risk_gate


@pytest.fixture
async def db_session():
    """In-memory SQLite async database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _create_test_environment(session: AsyncSession) -> tuple[User, TradingAccount, MT5Agent]:
    """Helper to seed user, account, agent, equity, and risk configuration."""
    user = User(
        id=uuid.uuid4(),
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Test User",
        hashed_password="hash",
    )
    session.add(user)
    await session.flush()

    account = TradingAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        label="Main Cent",
        broker="Demo Broker",
        mt5_account_number="123456",
        mt5_server="Demo-Server",
        is_cent_account=True,
        cent_normalization_factor=Decimal("0.01"),
        is_active=True,
    )
    session.add(account)
    await session.flush()

    agent = MT5Agent(
        id=uuid.uuid4(),
        account_id=account.id,
        label="TestAgent",
        hashed_secret="secret_hash",
        last_known_status="CONNECTED",
    )
    session.add(agent)

    equity = EquitySnapshot(
        account_id=account.id,
        balance_usd=Decimal("1000.00"),
        equity_usd=Decimal("1000.00"),
        snapped_at=datetime.now(UTC),
    )
    session.add(equity)

    config = RiskConfiguration(
        account_id=account.id,
        version=1,
        effective_from=datetime.now(UTC),
        daily_loss_limit_usd=Decimal("100.00"),
        max_drawdown_usd=Decimal("200.00"),
        max_open_positions=3,
        max_spread_usd=Decimal("1.50"),
        max_tick_staleness_ms=2000,
    )
    session.add(config)
    await session.commit()

    return user, account, agent


@pytest.mark.unit
@pytest.mark.asyncio
class TestPhase3RiskGateEvaluation:
    """Test deterministic ALLOW / BLOCK outcomes and reason codes."""

    def _make_valid_tick(self) -> dict:
        return {
            "symbol": "XAUUSD",
            "bid": "2650.50",
            "ask": "2650.75",
            "spread": "0.25",
            "point": "0.01",
            "digits": 2,
            "tick_time": "2026-09-10 12:00:00",
            "received_at": datetime.now(UTC).isoformat(),
        }

    async def test_healthy_state_allows(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        tick = self._make_valid_tick()

        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "ALLOW"
        assert decision.reason_code == "RISK_OK"

    async def test_agent_offline_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        tick = self._make_valid_tick()

        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=False,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "AGENT_OFFLINE"

    async def test_invalid_symbol_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        tick = self._make_valid_tick()

        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "EURUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "INVALID_SYMBOL"

    async def test_stale_market_data_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        tick = self._make_valid_tick()
        stale_time = datetime.now(UTC) - timedelta(seconds=10)
        tick["received_at"] = stale_time.isoformat()

        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "MARKET_DATA_STALE"

    async def test_invalid_bid_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        tick = self._make_valid_tick()
        tick["bid"] = "-5.00"

        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "INVALID_BID"

    async def test_invalid_ask_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        tick = self._make_valid_tick()
        tick["ask"] = "2640.00"

        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "INVALID_ASK"

    async def test_spread_exceeds_threshold_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        tick = self._make_valid_tick()
        tick["spread"] = "2.50"

        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "INVALID_SPREAD"

    async def test_zero_equity_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        eq = EquitySnapshot(
            account_id=account.id,
            balance_usd=Decimal("0.00"),
            equity_usd=Decimal("0.00"),
            snapped_at=datetime.now(UTC) + timedelta(seconds=1),
        )
        db_session.add(eq)
        await db_session.commit()

        tick = self._make_valid_tick()
        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "ACCOUNT_STATE_UNAVAILABLE"

    async def test_no_trade_execution_invariant(self, db_session: AsyncSession) -> None:
        """Verify that evaluate_risk_gate never modifies orders, positions, or dispatches trades."""
        _, account, _ = await _create_test_environment(db_session)
        tick = self._make_valid_tick()
        d_allow = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert d_allow.decision == "ALLOW"

        from sqlalchemy import select

        from backend.db.models.execution import ExecutionCommand, Position

        pos_res = await db_session.execute(select(Position).where(Position.account_id == account.id))
        assert len(pos_res.scalars().all()) == 0

        cmd_res = await db_session.execute(
            select(ExecutionCommand).where(ExecutionCommand.account_id == account.id)
        )
        assert len(cmd_res.scalars().all()) == 0

    async def test_kill_switch_active_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        # Update config to have emergency stop active
        from unittest.mock import patch

        from backend.risk.config import RiskConfig

        mock_cfg = RiskConfig(
            emergency_stop_active=True,
            daily_loss_limit_usd=Decimal("100.00"),
            max_drawdown_usd=Decimal("200.00"),
            max_open_positions=3,
            risk_per_trade_pct=Decimal("0.01"),
        )
        with patch("backend.services.risk_gate.get_latest_risk_config", return_value=mock_cfg):
            tick = self._make_valid_tick()
            decision = await evaluate_risk_gate(
                db_session,
                account.id,
                "XAUUSD",
                override_tick=tick,
                override_agent_connected=True,
            )
            assert decision.decision == "BLOCK"
            assert decision.reason_code == "KILL_SWITCH_ACTIVE"

    async def test_daily_loss_limit_breached_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        from backend.db.models.equity import DailySessionState

        # Daily loss limit is 100.00. Set realized PNL to -150.00
        sess_state = DailySessionState(
            account_id=account.id,
            session_date=datetime.now(UTC).date(),
            realized_pnl_usd=Decimal("-150.00"),
            floating_pnl_usd=Decimal("0.00"),
            session_open_equity_usd=Decimal("1000.00"),
            last_updated_at=datetime.now(UTC),
        )
        db_session.add(sess_state)
        await db_session.commit()

        tick = self._make_valid_tick()
        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "RISK_LIMIT_BLOCK"

    async def test_drawdown_breached_blocks(self, db_session: AsyncSession) -> None:
        _, account, _ = await _create_test_environment(db_session)
        # Max drawdown is 200.00. Peak is 1000.00. Set current equity to 750.00 (drawdown = 250.00)
        eq = EquitySnapshot(
            account_id=account.id,
            balance_usd=Decimal("750.00"),
            equity_usd=Decimal("750.00"),
            snapped_at=datetime.now(UTC) + timedelta(seconds=2),
        )
        db_session.add(eq)
        await db_session.commit()

        tick = self._make_valid_tick()
        decision = await evaluate_risk_gate(
            db_session,
            account.id,
            "XAUUSD",
            override_tick=tick,
            override_agent_connected=True,
        )
        assert decision.decision == "BLOCK"
        assert decision.reason_code == "RISK_LIMIT_BLOCK"

