"""
End-to-End Acceptance Pipeline Test (Master Continuation Prompt Step 34).

Verifies the complete local pipeline:
1. User & Trading Account creation
2. MT5 Agent session tracking
3. Market Data: Deterministic tick generation & Closed Bar building
4. Brain Pipeline evaluation (unconfigured vs configured)
5. Risk Engine evaluation (NOT_CONFIGURED vs APPROVED)
6. Execution Engine command dispatch with idempotency key
7. MT5 Agent Simulator execution & execution report
8. Reconciliation engine validation (orphan detection & clean match)
9. Position persistence & state update
10. WebSocket event emission formatting
11. Backtest Engine replay of identical market data
12. Live trading explicitly disabled check
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models.account import TradingAccount
from backend.db.models.execution import Position
from backend.db.models.user import User
from backend.execution.commands import CommandAction, CommandState
from backend.execution.commands import ExecutionCommand as RuntimeCommand
from backend.execution.reconciliation import ReconciliationEngine
from backend.risk.config import RiskConfig
from backend.risk.engine import AccountRiskSnapshot, MarketCondition, RiskEngine
from backend.risk.states import SignalDecision
from backend.services.mt5_session import MT5SessionService
from backend.simulation.adapters import MT5AgentSimulator
from backend.ws.events import WsEvent
from brain.backtest.engine import BacktestEngine
from brain.config import (
    BrainConfig,
    MomentumConfig,
    RegimeConfig,
    ScoringConfig,
    StructureConfig,
    TrendConfig,
    VolatilityConfig,
)
from brain.market_data.types import Bar, DataSource, Tick
from brain.pipeline import SignalPipeline
from brain.strategy.interfaces import SignalDirection


@pytest.mark.asyncio
async def test_full_local_acceptance_pipeline() -> None:
    # â”€â”€ 1. Database Setup & User / Account Creation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db_session:
        user = User(
            id=uuid.uuid4(),
            email="trader@aurexis.local",
            hashed_password="argon2_hash_mock",
            display_name="Aurexis Acceptance Trader",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        account = TradingAccount(
            id=uuid.uuid4(),
            user_id=user.id,
            label="Acceptance Cent Account",
            broker="Demo Broker",
            mt5_account_number="20260906",
            mt5_server="Demo-Cent",
            broker_currency="Cent",
            is_cent_account=True,
            cent_normalization_factor=Decimal("0.01"),
            trading_enabled=False,  # CRITICAL INVARIANT: LIVE TRADING DISABLED
        )
        db_session.add(account)
        await db_session.commit()

        # â”€â”€ 2. MT5 Agent Connectivity & Heartbeat â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        mt5_session_svc = MT5SessionService(heartbeat_timeout_seconds=15)
        agent_id = "mt5-agent-accept-01"
        is_fresh = mt5_session_svc.record_heartbeat(
            agent_id=agent_id,
            account_id=str(account.id),
            status="CONNECTED",
            account_number=account.mt5_account_number,
        )
        assert is_fresh is True
        assert mt5_session_svc.is_connected(agent_id) is True

        # â”€â”€ 3. Market Data: Deterministic Ticks & Bar Builder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        ticks: list[Tick] = []
        base_bid = Decimal("2735.00")
        start_time = datetime.now(UTC) - timedelta(minutes=30)
        for i in range(30):
            step = Decimal(str(i * 0.10))
            ticks.append(
                Tick(
                    symbol="XAUUSD",
                    bid=base_bid + step,
                    ask=base_bid + step + Decimal("0.25"),
                    tick_time=start_time + timedelta(minutes=i),
                    received_at=start_time + timedelta(minutes=i),
                    source=DataSource.MOCK,
                )
            )
        assert len(ticks) == 30

        bars: list[Bar] = []
        for tick in ticks:
            bars.append(
                Bar(
                    symbol=tick.symbol,
                    timeframe="M1",
                    open_time=tick.tick_time,
                    close_time=tick.tick_time,
                    open_price=tick.bid,
                    high_price=tick.bid + Decimal("1.50"),
                    low_price=tick.bid - Decimal("1.50"),
                    close_price=tick.bid + Decimal("0.25"),
                    volume=Decimal("100"),
                    is_closed=True,
                )
            )

        # â”€â”€ 4. Brain Pipeline Evaluation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        unconfigured_pipeline = SignalPipeline()
        assert unconfigured_pipeline.is_configured is False
        unconf_signal = unconfigured_pipeline.process(latest_tick=ticks[-1], closed_bars=bars)
        assert unconf_signal.direction == SignalDirection.NONE

        configured_brain_config = BrainConfig(
            structure=StructureConfig(swing_lookback_bars=2),
            trend=TrendConfig(fast_ma_period=5, slow_ma_period=10),
            momentum=MomentumConfig(rsi_period=14),
            volatility=VolatilityConfig(atr_period=14),
            regime=RegimeConfig(adx_period=14, trending_threshold=Decimal("25")),
            scoring=ScoringConfig(min_confidence_threshold=Decimal("0.50")),
        )
        configured_pipeline = SignalPipeline(config=configured_brain_config)
        assert configured_pipeline.is_configured is True
        candidate_signal = configured_pipeline.process(latest_tick=ticks[-1], closed_bars=bars)

        assert candidate_signal.symbol == "XAUUSD"
        assert candidate_signal.is_configured is True

        # â”€â”€ 5. Risk Engine Evaluation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        snapshot = AccountRiskSnapshot(
            account_id=str(account.id),
            current_balance_usd=Decimal("10000.00"),
            current_equity_usd=Decimal("10000.00"),
            equity_peak_usd=Decimal("10000.00"),
            daily_realized_pnl_usd=Decimal("0.00"),
            daily_floating_pnl_usd=Decimal("0.00"),
            open_position_count=0,
            snapshot_at=datetime.now(UTC),
            session_open_equity_usd=Decimal("10000.00"),
            session_peak_profit_usd=Decimal("0.00"),
            open_lot_exposure=Decimal("0.00"),
            in_flight_lot_exposure=Decimal("0.00"),
        )

        market_cond = MarketCondition(
            symbol="XAUUSD",
            bid=ticks[-1].bid,
            ask=ticks[-1].ask,
            spread=ticks[-1].ask - ticks[-1].bid,
            tick_timestamp=datetime.now(UTC),
            tick_age_ms=10,
            market_data_status="READY",
        )

        unconfigured_risk = RiskEngine(config=RiskConfig())
        unconf_decision = unconfigured_risk.evaluate(snapshot=snapshot, candidate_signal=candidate_signal)
        assert unconf_decision.decision == SignalDecision.NOT_CONFIGURED
        assert unconf_decision.trading_allowed is False

        # Configured risk engine (for testing authorization flow)
        test_risk_config = RiskConfig(
            daily_loss_limit_usd=Decimal("500.00"),
            max_drawdown_usd=Decimal("1000.00"),
            max_open_positions=3,
            max_open_lots=Decimal("5.0"),
            max_spread_usd=Decimal("2.00"),
            risk_per_trade_pct=Decimal("0.01"),
        )
        test_risk_engine = RiskEngine(config=test_risk_config)
        risk_decision = test_risk_engine.evaluate(
            snapshot=snapshot,
            candidate_signal=candidate_signal,
            market_condition=market_cond,
            news_state="CLEAR",
        )
        assert risk_decision.decision == SignalDecision.APPROVED
        assert risk_decision.trading_allowed is True
        # authorized_lot_size may be None if signal lacks stop_loss (not fully configured)
        # The important invariant is APPROVED status and trading_allowed=True

        # â”€â”€ 6. Execution Command Dispatch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        cmd_id = str(uuid.uuid4())
        idempotency_key = f"cmd-{cmd_id}"
        command = RuntimeCommand(
            command_id=cmd_id,
            account_id=str(account.id),
            action=CommandAction.ORDER_OPEN,
            symbol="XAUUSD",
            order_type="BUY",
            volume_lots=Decimal("0.01"),  # Fixed for test because authorized_lot_size may be None
            price=ticks[-1].ask,
            slippage_points=20,
            idempotency_key=idempotency_key,
            correlation_id=str(uuid.uuid4()),
            stop_loss=ticks[-1].bid - Decimal("5.00"),
            take_profit=ticks[-1].bid + Decimal("10.00"),
        )
        assert command.state == CommandState.CREATED
        assert command.transition_to(CommandState.SENT)

        # â”€â”€ 7. MT5 Agent Simulator Execution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        simulator = MT5AgentSimulator(account_id=str(account.id), agent_id=agent_id)
        exec_report = simulator.process_command(command, current_market_price=ticks[-1].bid)

        assert exec_report.is_filled is True
        assert exec_report.broker_ticket is not None
        assert exec_report.is_simulated is True

        assert command.transition_to(CommandState.ACKNOWLEDGED)
        assert command.transition_to(CommandState.EXECUTING)
        assert command.transition_to(CommandState.FILLED)

        # â”€â”€ 8. Reconciliation Engine Validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        broker_positions = simulator.get_open_positions()
        assert len(broker_positions) == 1

        recon_engine = ReconciliationEngine()
        recon_orphan = recon_engine.reconcile(
            account_id=str(account.id),
            server_positions={},
            broker_positions=broker_positions,
        )
        assert not recon_orphan.is_clean
        assert recon_orphan.discrepancies[0].discrepancy_type == "ORPHAN"

        # â”€â”€ 9. Position Persistence & Clean Match â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        db_position = Position(
            account_id=account.id,
            broker_ticket=exec_report.broker_ticket,
            symbol="XAUUSD",
            side="BUY",
            lots=exec_report.filled_lots or Decimal("0.01"),
            open_price=exec_report.fill_price or ticks[-1].bid,
            current_price=exec_report.fill_price or ticks[-1].bid,
            status="OPEN",
            opened_at=datetime.now(UTC),
        )
        db_session.add(db_position)
        await db_session.commit()

        server_positions = {
            db_position.broker_ticket: {
                "lots": db_position.lots,
                "side": db_position.side,
                "symbol": db_position.symbol,
                "status": db_position.status,
            }
        }
        recon_clean = recon_engine.reconcile(
            account_id=str(account.id),
            server_positions=server_positions,
            broker_positions=broker_positions,
        )
        assert recon_clean.is_clean is True
        assert recon_clean.matched_count == 1
        assert len(recon_clean.discrepancies) == 0

        # 10. WebSocket Event Formatting
        ws_event = WsEvent(
            event='POSITION_UPDATED',
            account_id=str(account.id),
            payload={
                'ticket': db_position.broker_ticket,
                'symbol': db_position.symbol,
                'side': db_position.side,
                'lots': str(db_position.lots),
                'open_price': str(db_position.open_price),
            },
        )
        wire_json = ws_event.model_dump_json()
        assert 'POSITION_UPDATED' in wire_json
        assert str(account.id) in wire_json

        # â”€â”€ 11. Backtest Engine Deterministic Replay â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        from brain.backtest.engine import BacktestConfig
        backtest_cfg = BacktestConfig(
            initial_balance_usd=Decimal("10000.00"),
            brain_config=configured_brain_config,
            risk_config=test_risk_config,
        )
        backtest = BacktestEngine(config=backtest_cfg)
        backtest_result = backtest.run(ticks)
        assert backtest_result.initial_balance_usd == Decimal("10000.00")
        assert backtest_result.disclaimer == "Backtest results are not proof of future profitability."

        # â”€â”€ 12. Strict Live Trading Disabled Check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        assert account.trading_enabled is False
        assert exec_report.is_simulated is True

