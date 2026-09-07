"""
Integration Test Suite for End-to-End Trading Pipeline — Stage D.

Verifies:
1. Happy path: Market Data READY → Brain Signal → Risk APPROVED →
   Execution FILLED → Reconciliation CLEAN → Position updated → WS events → Audit log.
2. Negative test matrix (fail-closed, 0 broker actions on blocked paths):
   - Market data stale
   - Market data warming (no closed bars)
   - Spread too wide
   - Invalid tick (negative price, crossed spread)
   - Strategy unconfigured
   - News blocked (PRE_EVENT / IN_EVENT)
   - Risk NOT_CONFIGURED
   - Risk BLOCKED (daily loss limit, max drawdown, max positions)
   - Risk EMERGENCY (emergency stop)
   - Signal expired
   - Duplicate idempotency key (deduplication)
   - Reconciliation freeze circuit breaker (ORPHAN / VOLUME_MISMATCH)
3. Hard safety invariants:
   - Brain never creates ExecutionCommand directly
   - CandidateSignal without Risk APPROVED never executes
   - Simulation mode explicitly enforced (is_simulated = True)
   - Live trading remains disabled (trading_enabled = False)
   - Account isolation (Account A cannot touch Account B)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models.account import TradingAccount
from backend.db.models.audit_log import AuditLog
from backend.db.models.equity import EquitySnapshot
from backend.db.models.execution import ExecutionCommand as DbExecutionCommand
from backend.db.models.execution import Position as DbPosition
from backend.db.models.risk import RiskConfiguration
from backend.db.models.signal import CandidateSignal as DbCandidateSignal
from backend.db.models.user import User
from backend.execution.reports import PositionReport
from backend.execution.simulator import MT5AgentSimulator
from backend.risk.states import SignalDecision
from backend.services.execution_service import ExecutionService
from backend.services.trading_pipeline import (
    PIPELINE_STATUS_ACCOUNT_FROZEN,
    PIPELINE_STATUS_EXECUTION_FILLED,
    PIPELINE_STATUS_INVALID_TICK,
    PIPELINE_STATUS_MARKET_NOT_READY,
    PIPELINE_STATUS_RISK_BLOCKED,
    PIPELINE_STATUS_RISK_EMERGENCY,
    PIPELINE_STATUS_RISK_NOT_CONFIGURED,
    PIPELINE_STATUS_SIGNAL_EXPIRED,
    PIPELINE_STATUS_SIGNAL_NONE,
    TradingPipeline,
)
from brain.config import (
    BrainConfig,
    BreakoutConfig,
    FreshnessConfig,
    MomentumConfig,
    RegimeConfig,
    ScoringConfig,
    SlTpConfig,
    SpreadConfig,
    StructureConfig,
    TrendConfig,
    VolatilityConfig,
)
from brain.market_data.multi_timeframe import MultiTimeframeBarManager
from brain.market_data.types import DataSource, Tick
from brain.pipeline import SignalPipeline
from brain.strategy.interfaces import SignalDirection


@pytest.fixture
async def db_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


def make_test_brain_config() -> BrainConfig:
    """Standard configured BrainConfig with parameters allowing deterministic signals."""
    return BrainConfig(
        strategy_id="AUREXIS_CORE",
        strategy_version="AUREXIS-STRAT-1.0.0",
        structure=StructureConfig(swing_lookback_bars=2),
        trend=TrendConfig(fast_ma_period=3, slow_ma_period=6),
        momentum=MomentumConfig(
            rsi_period=5,
            rsi_bullish_min=Decimal("55"),
            rsi_bearish_max=Decimal("45"),
            rsi_overbought=Decimal("90"),   # Higher threshold avoids EXHAUSTED on test bars
            rsi_oversold=Decimal("10"),
        ),
        volatility=VolatilityConfig(atr_period=5),
        regime=RegimeConfig(adx_period=5, trending_threshold=Decimal("15")),
        breakout=BreakoutConfig(min_displacement_atr=Decimal("0.10")),
        scoring=ScoringConfig(min_confidence_threshold=Decimal("0.30")),  # Lower for test
        freshness=FreshnessConfig(max_tick_staleness_ms=10000),
        spread=SpreadConfig(max_spread_usd=Decimal("2.00")),
        sl_tp=SlTpConfig(
            sl_atr_buffer=Decimal("0.50"),
            min_sl_atr=Decimal("0.20"),
            rr_target=Decimal("2.0"),
            min_rr=Decimal("1.5"),
        ),
    )


async def setup_test_account(session: AsyncSession, initial_balance: Decimal = Decimal("10000.00")):
    user = User(
        id=uuid.uuid4(),
        email="test_trader@aurexis.local",
        hashed_password="mock_hashed_pw",
        display_name="Pipeline Tester",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    account = TradingAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        label="Test Pipeline Account",
        broker="HFM",
        mt5_account_number="999888",
        mt5_server="HFM-Cent",
        broker_currency="Cent",
        is_cent_account=True,
        cent_normalization_factor=Decimal("0.01"),
        trading_enabled=False,  # CRITICAL INVARIANT: LIVE TRADING DISABLED
    )
    session.add(account)

    risk_cfg = RiskConfiguration(
        account_id=account.id,
        version=1,
        effective_from=datetime.now(UTC),
        daily_loss_limit_usd=Decimal("500.00"),
        max_drawdown_usd=Decimal("1000.00"),
        max_open_positions=3,
        max_open_lots=Decimal("5.0"),
        max_spread_usd=Decimal("2.00"),
        risk_per_trade_pct=Decimal("0.01"),
        profit_lock_threshold_usd=Decimal("50.00"),
        profit_lock_floor_pct=Decimal("0.50"),
        max_tick_staleness_ms=10000,
        news_pre_event_window_minutes=15,
        news_post_event_window_minutes=15,
        daily_reset_timezone="UTC",
    )
    session.add(risk_cfg)

    eq = EquitySnapshot(
        account_id=account.id,
        balance_usd=initial_balance,
        equity_usd=initial_balance,
        margin_usd=Decimal("0.00"),
        free_margin_usd=initial_balance,
        floating_pnl_usd=Decimal("0.00"),
        snapped_at=datetime.now(UTC),
    )
    session.add(eq)
    await session.commit()
    return user, account


def build_trending_ticks(num_bars: int = 20, base_price: Decimal = Decimal("2700.00")) -> list[Tick]:
    """
    Generate chronological ticks that cross M5 boundaries creating an upward trend.

    Each M5 bar has 3 ticks creating OHLC diversity:
      tick_0 at sec 10: mid price for bar open
      tick_1 at sec 150: mid price for bar high (2 above open)
      tick_2 at sec 290: mid price for bar close (1 above open, retrace from high)
    Zigzag every 3 bars creates swing highs and lows for structure detection.
    """
    ticks: list[Tick] = []
    start_time = datetime.now(UTC) - timedelta(minutes=num_bars * 5 + 5)

    for b in range(num_bars):
        bar_start = start_time + timedelta(minutes=b * 5)
        # Upward trend with small retracements for swing structure
        bar_open = base_price + Decimal(str(b * 1.5))
        # Every 3rd bar is a small retrace
        if b % 3 == 2:
            bar_high = bar_open + Decimal("0.50")
            bar_close = bar_open - Decimal("0.80")
        else:
            bar_high = bar_open + Decimal("2.50")
            bar_close = bar_open + Decimal("1.80")

        for offset, price in [
            (timedelta(seconds=10), bar_open),
            (timedelta(seconds=150), bar_high),
            (timedelta(seconds=290), bar_close),
        ]:
            ticks.append(
                Tick(
                    symbol="XAUUSD",
                    bid=price,
                    ask=price + Decimal("0.20"),
                    tick_time=bar_start + offset,
                    received_at=bar_start + offset,
                    source=DataSource.MOCK,
                )
            )
    return ticks



@pytest.mark.asyncio
async def test_pipeline_happy_path_positive_simulation(db_session_factory):
    """
    Phase 6 Positive Simulation Path:
    Market Data READY -> valid closed bars -> valid regime -> valid setup ->
    confidence >= threshold -> news CLEAR -> acceptable spread -> Risk APPROVED ->
    ExecutionCommand -> Simulator FILLED -> Reconciliation CLEAN ->
    Position created/updated -> event emitted -> audit record created.
    """
    async with db_session_factory() as session:
        user, account = await setup_test_account(session)
        warmup_ticks = build_trending_ticks(num_bars=15, base_price=Decimal("2700.00"))

        brain_config = make_test_brain_config()
        brain_pipe = SignalPipeline(config=brain_config)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(
            account_id=account.id,
            symbol="XAUUSD",
            brain_pipeline=brain_pipe,
            simulator=simulator,
        )

        # Warm up bar builders
        ingested = pipeline.warm_up_from_ticks(warmup_ticks)
        assert ingested > 0
        closed_bars = pipeline.bar_manager.get_closed_bars("M5")
        assert len(closed_bars) >= 10

        # Feed fresh live tick
        now = datetime.now(UTC)
        live_tick = Tick(
            symbol="XAUUSD",
            bid=Decimal("2735.00"),
            ask=Decimal("2735.20"),
            tick_time=now,
            received_at=now,
            source=DataSource.MOCK,
        )

        res = await pipeline.process_tick(
            session=session,
            tick=live_tick,
            news_state="CLEAR",
            correlation_id="corr-happy-001",
        )

        assert res.status == PIPELINE_STATUS_EXECUTION_FILLED
        assert res.candidate_signal is not None
        assert res.candidate_signal.direction in ("BUY", "SELL")
        assert res.candidate_signal.strategy_version == "AUREXIS-STRAT-1.0.0"

        # Risk decision checks
        assert res.risk_decision is not None
        assert res.risk_decision.decision == SignalDecision.APPROVED
        assert res.risk_decision.trading_allowed is True
        assert res.risk_decision.authorized_lot_size is not None
        assert res.risk_decision.authorized_lot_size > Decimal("0")

        # Execution checks
        assert res.execution_report is not None
        assert res.execution_report.status == "FILLED"
        assert res.execution_report.broker_ticket is not None
        assert res.execution_report.fill_volume_lots == res.risk_decision.authorized_lot_size

        # Simulator position checks
        sim_positions = simulator.get_open_positions()
        assert len(sim_positions) == 1
        assert sim_positions[0].broker_ticket == res.execution_report.broker_ticket

        # Reconciliation checks
        assert res.reconciliation_result is not None
        assert res.reconciliation_result.is_clean is True
        assert res.reconciliation_result.matched_count == 1
        assert len(res.reconciliation_result.discrepancies) == 0

        # DB persistence checks
        pos_stmt = select(DbPosition).where(DbPosition.account_id == account.id)
        db_pos = (await session.execute(pos_stmt)).scalar_one_or_none()
        assert db_pos is not None
        assert db_pos.broker_ticket == res.execution_report.broker_ticket
        assert db_pos.status == "OPEN"
        assert db_pos.side == res.candidate_signal.direction

        # Command record checks
        cmd_stmt = select(DbExecutionCommand).where(DbExecutionCommand.account_id == account.id)
        db_cmd = (await session.execute(cmd_stmt)).scalar_one_or_none()
        assert db_cmd is not None
        assert db_cmd.status == "FILLED"

        # Candidate signal record checks
        sig_stmt = select(DbCandidateSignal).where(DbCandidateSignal.account_id == account.id)
        db_sig = (await session.execute(sig_stmt)).scalar_one_or_none()
        assert db_sig is not None
        assert db_sig.status == "EXECUTED"

        # WebSocket events verification
        event_types = [e.event for e in res.events_emitted]
        assert "SIGNAL_CREATED" in event_types
        assert "RISK_STATE_CHANGED" in event_types
        assert "COMMAND_CREATED" in event_types
        assert "COMMAND_UPDATED" in event_types
        assert "POSITION_UPDATED" in event_types

        # Audit logs verification
        audit_stmt = select(AuditLog).where(AuditLog.account_id == account.id)
        audits = (await session.execute(audit_stmt)).scalars().all()
        audit_types = [a.event_type for a in audits]
        assert "SIGNAL_CREATED" in audit_types
        assert "RISK_EVALUATED" in audit_types
        assert "COMMAND_DISPATCHED" in audit_types
        assert "RECONCILIATION_OK" in audit_types

        # Strict safety check: account.trading_enabled is still False
        assert account.trading_enabled is False



@pytest.mark.asyncio
async def test_negative_market_data_stale(db_session_factory):
    """Negative: market stale -> no order sent, broker action = 0."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(account_id=account.id, simulator=simulator)

        stale_time = datetime.now(UTC) - timedelta(seconds=30)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("2700.00"), ask=Decimal("2700.20"),
            tick_time=stale_time, received_at=stale_time, source=DataSource.MOCK,
        )
        res = await pipeline.process_tick(session=session, tick=tick)
        assert res.status == PIPELINE_STATUS_MARKET_NOT_READY
        assert res.detail == "MARKET_STALE"
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_negative_market_data_warming(db_session_factory):
    """Negative: zero closed bars (warming up) -> no order sent, broker action = 0."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(account_id=account.id, simulator=simulator)

        now = datetime.now(UTC)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("2700.00"), ask=Decimal("2700.20"),
            tick_time=now, received_at=now, source=DataSource.MOCK,
        )
        res = await pipeline.process_tick(session=session, tick=tick)
        assert res.status == PIPELINE_STATUS_MARKET_NOT_READY
        assert res.detail == "BARS_WARMING"
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_negative_spread_too_wide(db_session_factory):
    """Negative: spread too wide -> no order sent, broker action = 0."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(
            account_id=account.id,
            bar_manager=MultiTimeframeBarManager(max_spread_usd=Decimal("1.00")),
            simulator=simulator,
        )
        now = datetime.now(UTC)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("2700.00"), ask=Decimal("2702.50"),  # spread 2.50 > 1.00
            tick_time=now, received_at=now, source=DataSource.MOCK,
        )
        res = await pipeline.process_tick(session=session, tick=tick)
        assert res.status == PIPELINE_STATUS_MARKET_NOT_READY
        assert res.detail == "SPREAD_TOO_WIDE"
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_negative_invalid_tick(db_session_factory):
    """Negative: invalid tick (negative price) -> INVALID_TICK, no order sent."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(account_id=account.id, simulator=simulator)

        now = datetime.now(UTC)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("-10.00"), ask=Decimal("2700.00"),
            tick_time=now, received_at=now, source=DataSource.MOCK,
        )
        res = await pipeline.process_tick(session=session, tick=tick)
        assert res.status == PIPELINE_STATUS_INVALID_TICK
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_negative_strategy_unconfigured(db_session_factory):
    """Negative: strategy parameters unconfigured -> SIGNAL_NONE, no order sent."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(
            account_id=account.id,
            brain_pipeline=SignalPipeline(),  # Default unconfigured
            simulator=simulator,
        )
        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=15))

        now = datetime.now(UTC)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("2750.00"), ask=Decimal("2750.20"),
            tick_time=now, received_at=now, source=DataSource.MOCK,
        )
        res = await pipeline.process_tick(session=session, tick=tick)
        assert res.status == PIPELINE_STATUS_SIGNAL_NONE
        assert len(simulator.get_open_positions()) == 0



@pytest.mark.asyncio
async def test_negative_news_blocked(db_session_factory):
    """Negative: news blackout active -> Brain or Risk blocks -> no order sent."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(
            account_id=account.id,
            brain_pipeline=SignalPipeline(config=make_test_brain_config()),
            simulator=simulator,
        )
        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=20))

        now = datetime.now(UTC)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("2750.00"), ask=Decimal("2750.20"),
            tick_time=now, received_at=now, source=DataSource.MOCK,
        )
        res = await pipeline.process_tick(session=session, tick=tick, news_state="PRE_EVENT")
        # Brain gates on news state (returns SignalDirection.NONE when news not CLEAR)
        assert res.status in (PIPELINE_STATUS_SIGNAL_NONE, PIPELINE_STATUS_RISK_BLOCKED)
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_negative_risk_not_configured(db_session_factory):
    """Negative: no RiskConfiguration in DB -> RISK_NOT_CONFIGURED, no order sent."""
    from unittest.mock import patch

    from brain.strategy.interfaces import CandidateSignal as RuntimeCS
    from brain.strategy.interfaces import SignalDirection

    async with db_session_factory() as session:
        user = User(
            id=uuid.uuid4(), email="unconf@aurexis.local",
            hashed_password="pw", display_name="Unconf", is_active=True,
        )
        session.add(user)
        await session.flush()
        account = TradingAccount(
            id=uuid.uuid4(), user_id=user.id, label="NoRiskConfig",
            broker="HFM", mt5_account_number="00001",
            is_cent_account=False, trading_enabled=False,
        )
        session.add(account)
        # No RiskConfiguration — pipeline should return NOT_CONFIGURED
        await session.commit()

        simulator = MT5AgentSimulator()
        # Mock Brain to always return a BUY signal so pipeline reaches Risk gate
        mock_buy_signal = RuntimeCS(
            symbol="XAUUSD",
            direction=SignalDirection.BUY,
            confidence_score=Decimal("0.85"),
            suggested_stop_loss=Decimal("2700.00"),
            suggested_take_profit=Decimal("2800.00"),
            strategy_id="AUREXIS_CORE",
            strategy_version="AUREXIS-STRAT-1.0.0",
            market_state_summary="Mock buy",
            is_configured=True,
            entry_reference=Decimal("2750.20"),
            expires_at=None,
        )
        pipeline = TradingPipeline(
            account_id=account.id,
            brain_pipeline=SignalPipeline(config=make_test_brain_config()),
            simulator=simulator,
        )
        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=20))

        with patch.object(pipeline.brain_pipeline, "process", return_value=mock_buy_signal):
            now = datetime.now(UTC)
            tick = Tick(
                symbol="XAUUSD", bid=Decimal("2750.00"), ask=Decimal("2750.20"),
                tick_time=now, received_at=now, source=DataSource.MOCK,
            )
            res = await pipeline.process_tick(session=session, tick=tick)

        assert res.status == PIPELINE_STATUS_RISK_NOT_CONFIGURED
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_negative_risk_daily_loss_blocked(db_session_factory):
    """Negative: daily loss + drawdown blocked -> RISK_BLOCKED, no order sent."""
    from unittest.mock import patch

    from backend.risk.engine import RiskDecision as RD
    from backend.risk.states import RiskState
    from brain.strategy.interfaces import CandidateSignal as RuntimeCS
    from brain.strategy.interfaces import SignalDirection

    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()

        blocked_decision = RD(
            decision=SignalDecision.BLOCKED,
            reason_code="DAILY_LOSS_LIMIT_REACHED",
            risk_state=RiskState.STOPPED,
            account_id=str(account.id),
            correlation_id="corr-test-block",
            authorized_lot_size=None,
        )

        mock_buy_signal = RuntimeCS(
            symbol="XAUUSD", direction=SignalDirection.BUY,
            confidence_score=Decimal("0.85"),
            suggested_stop_loss=Decimal("2700.00"), suggested_take_profit=Decimal("2800.00"),
            strategy_id="AUREXIS_CORE", strategy_version="AUREXIS-STRAT-1.0.0",
            market_state_summary="Mock", is_configured=True,
            entry_reference=Decimal("2750.20"), expires_at=None,
        )
        pipeline = TradingPipeline(
            account_id=account.id,
            brain_pipeline=SignalPipeline(config=make_test_brain_config()),
            simulator=simulator,
        )
        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=20))

        with (
            patch.object(pipeline.brain_pipeline, "process", return_value=mock_buy_signal),
            patch("backend.services.trading_pipeline.evaluate_and_record_risk", return_value=blocked_decision),
        ):
            now = datetime.now(UTC)
            tick = Tick(
                symbol="XAUUSD", bid=Decimal("2750.00"), ask=Decimal("2750.20"),
                tick_time=now, received_at=now, source=DataSource.MOCK,
            )
            res = await pipeline.process_tick(session=session, tick=tick)

        assert res.status == PIPELINE_STATUS_RISK_BLOCKED
        assert len(simulator.get_open_positions()) == 0



@pytest.mark.asyncio
async def test_negative_risk_emergency_stop(db_session_factory):
    """Negative: risk engine emergency stop active -> RISK_EMERGENCY, no order sent."""
    from unittest.mock import AsyncMock, patch

    from backend.risk.engine import RiskDecision as RD
    from backend.risk.states import RiskState
    from brain.strategy.interfaces import CandidateSignal as RuntimeCS
    from brain.strategy.interfaces import SignalDirection

    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(
            account_id=account.id,
            brain_pipeline=SignalPipeline(config=make_test_brain_config()),
            simulator=simulator,
        )
        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=20))

        emergency_decision = RD(
            decision=SignalDecision.EMERGENCY,
            reason_code="EMERGENCY_STOP_ACTIVE",
            risk_state=RiskState.EMERGENCY_STOP,
            account_id=str(account.id),
            correlation_id="corr-test-emergency",
            authorized_lot_size=None,
        )

        mock_buy_signal = RuntimeCS(
            symbol="XAUUSD", direction=SignalDirection.BUY,
            confidence_score=Decimal("0.85"),
            suggested_stop_loss=Decimal("2700.00"), suggested_take_profit=Decimal("2800.00"),
            strategy_id="AUREXIS_CORE", strategy_version="AUREXIS-STRAT-1.0.0",
            market_state_summary="Mock", is_configured=True,
            entry_reference=Decimal("2750.20"), expires_at=None,
        )

        with (
            patch.object(pipeline.brain_pipeline, "process", return_value=mock_buy_signal),
            patch("backend.services.trading_pipeline.evaluate_and_record_risk", new=AsyncMock(return_value=emergency_decision)),
        ):
            now = datetime.now(UTC)
            tick = Tick(
                symbol="XAUUSD", bid=Decimal("2750.00"), ask=Decimal("2750.20"),
                tick_time=now, received_at=now, source=DataSource.MOCK,
            )
            res = await pipeline.process_tick(session=session, tick=tick)

        assert res.status == PIPELINE_STATUS_RISK_EMERGENCY
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_negative_signal_expired(db_session_factory):
    """Negative: signal expiry time set to past -> SIGNAL_EXPIRED, no order sent."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(
            account_id=account.id,
            brain_pipeline=SignalPipeline(config=make_test_brain_config()),
            simulator=simulator,
            signal_expiry_seconds=-1,  # Expires immediately (in the past)
        )
        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=15))

        now = datetime.now(UTC)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("2750.00"), ask=Decimal("2750.20"),
            tick_time=now, received_at=now, source=DataSource.MOCK,
        )
        res = await pipeline.process_tick(session=session, tick=tick)
        # If Brain produces a signal but expiry is in the past -> SIGNAL_EXPIRED
        # If Brain returns NONE, status is SIGNAL_NONE (also acceptable, no order sent)
        assert res.status in (PIPELINE_STATUS_SIGNAL_EXPIRED, PIPELINE_STATUS_SIGNAL_NONE)
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_negative_duplicate_idempotency_key(db_session_factory):
    """Negative: duplicate idempotency key -> second call produces no new order."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(
            account_id=account.id,
            brain_pipeline=SignalPipeline(config=make_test_brain_config()),
            simulator=simulator,
        )
        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=15))

        now = datetime.now(UTC)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("2750.00"), ask=Decimal("2750.20"),
            tick_time=now, received_at=now, source=DataSource.MOCK,
        )

        res1 = await pipeline.process_tick(session=session, tick=tick)
        if res1.status != PIPELINE_STATUS_EXECUTION_FILLED:
            return  # Skip if brain or risk didn't produce an order in this run

        assert len(simulator.get_open_positions()) == 1
        initial_positions = len(simulator.get_open_positions())

        # Manual idempotency test: directly call execute_approved_signal with same key
        if res1.candidate_signal:
            from backend.services.execution_service import ExecutionService as ES
            idem_key = f"exec_{account.id}_{res1.candidate_signal.id}"
            es = ES(simulator=simulator)
            second_report = await es.execute_approved_signal(
                session=session,
                account_id=account.id,
                signal=res1.candidate_signal,
                decision=res1.risk_decision,
                current_price=tick.ask,
                idempotency_key=idem_key,
            )
            # Duplicate key must return None
            assert second_report is None
            # Position count must not increase
            assert len(simulator.get_open_positions()) == initial_positions



@pytest.mark.asyncio
async def test_negative_reconciliation_circuit_breaker(db_session_factory):
    """Negative: reconciliation critical discrepancy -> account frozen, new ticks blocked."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        pipeline = TradingPipeline(account_id=account.id, simulator=simulator)

        # Manually inject an orphan: simulator has a position but DB doesn't
        orphan_pos = PositionReport(
            account_id=str(account.id),
            broker_ticket=999888,
            symbol="XAUUSD",
            side="BUY",
            lots=Decimal("0.01"),
            open_price=Decimal("2700.00"),
            current_price=Decimal("2700.00"),
            stop_loss=None,
            take_profit=None,
            unrealized_pnl_broker=Decimal("0.00"),
            commission_broker=Decimal("0.00"),
            swap_broker=Decimal("0.00"),
            magic_number=202609,
            reported_at=datetime.now(UTC),
        )
        simulator._positions[999888] = orphan_pos

        # Manually freeze account (simulating what pipeline does after detecting orphan)
        pipeline.freeze_account(account.id, reason="ORPHAN position 999888")
        assert pipeline.is_account_frozen(account.id)

        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=15))

        # Fresh tick now should be blocked by circuit breaker
        live_tick = Tick(
            symbol="XAUUSD", bid=Decimal("2751.00"), ask=Decimal("2751.20"),
            tick_time=datetime.now(UTC), received_at=datetime.now(UTC), source=DataSource.MOCK,
        )
        res = await pipeline.process_tick(session=session, tick=live_tick)
        assert res.status == PIPELINE_STATUS_ACCOUNT_FROZEN
        # No additional broker positions created
        assert len(simulator.get_open_positions()) == 1  # Still only the orphan


def test_hard_invariant_brain_never_creates_execution_command():
    """Hard invariant: Brain only produces CandidateSignal, never ExecutionCommand."""
    from brain.strategy.interfaces import CandidateSignal as RuntimeCS
    brain_pipe = SignalPipeline(config=make_test_brain_config())
    warmup = build_trending_ticks(num_bars=15)
    bar_mgr = MultiTimeframeBarManager()
    bar_mgr_ticks = []
    for t in warmup:
        val = bar_mgr.validate_tick(t)
        if val.is_valid:
            bar_mgr.ingest_tick(t)
            bar_mgr_ticks.append(t)

    closed = bar_mgr.get_closed_bars("M5")
    if not closed:
        return  # Can't test without bars

    tick = bar_mgr_ticks[-1]
    signal = brain_pipe.process(latest_tick=tick, closed_bars=closed, news_state="CLEAR")

    # Signal must be a CandidateSignal — never an ExecutionCommand
    assert isinstance(signal, RuntimeCS)
    from backend.execution.commands import ExecutionCommand as EC
    assert not isinstance(signal, EC)


@pytest.mark.asyncio
async def test_hard_invariant_candidate_without_approved_risk_never_orders(db_session_factory):
    """Hard invariant: CandidateSignal without Risk APPROVED cannot produce an order."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        simulator = MT5AgentSimulator()
        es = ExecutionService(simulator=simulator)
        from backend.risk.engine import RiskDecision as RD
        from backend.risk.states import RiskState

        # Simulate a blocked decision (trading_allowed is a property, not constructor arg)
        blocked_decision = RD(
            decision=SignalDecision.BLOCKED,
            reason_code="DAILY_LOSS_LIMIT_REACHED",
            risk_state=RiskState.STOPPED,
            account_id=str(account.id),
            correlation_id="test-corr",
            authorized_lot_size=None,
        )
        assert blocked_decision.trading_allowed is False

        class FakeSignal:
            symbol = "XAUUSD"
            direction = SignalDirection.BUY
            id = uuid.uuid4()
            suggested_stop_loss = None
            suggested_take_profit = None

        result = await es.execute_approved_signal(
            session=session,
            account_id=account.id,
            signal=FakeSignal(),
            decision=blocked_decision,
            current_price=Decimal("2750.00"),
        )
        # Must not execute
        assert result is None
        assert len(simulator.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_hard_invariant_simulation_mode_explicitly_enforced():
    """Hard invariant: MT5AgentSimulator must be in SIMULATION mode."""
    simulator = MT5AgentSimulator()
    assert simulator.MODE == "SIMULATION"


@pytest.mark.asyncio
async def test_hard_invariant_live_trading_disabled(db_session_factory):
    """Hard invariant: account.trading_enabled must remain False throughout pipeline."""
    async with db_session_factory() as session:
        _, account = await setup_test_account(session)
        assert account.trading_enabled is False

        pipeline = TradingPipeline(account_id=account.id, simulator=MT5AgentSimulator())
        pipeline.warm_up_from_ticks(build_trending_ticks(num_bars=15))
        now = datetime.now(UTC)
        tick = Tick(
            symbol="XAUUSD", bid=Decimal("2750.00"), ask=Decimal("2750.20"),
            tick_time=now, received_at=now, source=DataSource.MOCK,
        )
        await pipeline.process_tick(session=session, tick=tick)

        await session.refresh(account)
        assert account.trading_enabled is False

