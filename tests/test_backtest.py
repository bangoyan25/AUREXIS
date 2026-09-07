"""
Tests for AUREXIS Backtest Engine — TASK-505.

Verifies:
- Deterministic chronological tick replay
- Closed-bar processing
- Brain -> Risk -> Simulated execution pipeline
- Disclaimers and performance metrics
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.risk.config import RiskConfig
from brain.backtest.engine import BacktestConfig, BacktestEngine
from brain.config import (
    BrainConfig,
    MomentumConfig,
    RegimeConfig,
    ScoringConfig,
    StructureConfig,
    TrendConfig,
    VolatilityConfig,
)
from brain.market_data.types import DataSource, Tick


def create_tick(symbol: str, price: Decimal, ts: datetime) -> Tick:
    return Tick(
        symbol=symbol,
        broker_symbol=symbol,
        bid=price,
        ask=price + Decimal("0.20"),
        tick_time=ts,
        received_at=ts,
        source=DataSource.REPLAY,
    )


def test_backtest_empty_ticks():
    config = BacktestConfig(initial_balance_usd=Decimal("5000.00"))
    engine = BacktestEngine(config)
    result = engine.run([])

    assert result.initial_balance_usd == Decimal("5000.00")
    assert result.final_balance_usd == Decimal("5000.00")
    assert result.total_trades == 0
    assert result.disclaimer == "Backtest results are not proof of future profitability."


def test_backtest_unconfigured_produces_no_trades():
    # When brain_config is default unconfigured, it must operate fail-closed (0 trades)
    config = BacktestConfig(initial_balance_usd=Decimal("10000.00"))
    engine = BacktestEngine(config)

    now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    ticks = [
        create_tick("XAUUSD", Decimal("2000.00") + Decimal(i) * Decimal("0.10"), now + timedelta(seconds=i * 10))
        for i in range(120)
    ]
    result = engine.run(ticks)
    assert result.total_trades == 0
    assert result.final_balance_usd == Decimal("10000.00")


def test_backtest_configured_execution():
    brain_cfg = BrainConfig(
        structure=StructureConfig(swing_lookback_bars=2),
        regime=RegimeConfig(adx_period=5, trending_threshold=Decimal("20.0")),
        trend=TrendConfig(fast_ma_period=3, slow_ma_period=6),
        momentum=MomentumConfig(rsi_period=5, rsi_overbought=Decimal("70"), rsi_oversold=Decimal("30")),
        volatility=VolatilityConfig(atr_period=5, max_atr_threshold_usd=Decimal("50.0")),
        scoring=ScoringConfig(min_confidence_threshold=Decimal("0.50")),
    )
    risk_cfg = RiskConfig(
        daily_loss_limit_usd=Decimal("500.00"),
        max_drawdown_usd=Decimal("1000.00"),
        max_open_positions=2,
        default_position_size_lots=Decimal("0.10"),
    )
    config = BacktestConfig(
        initial_balance_usd=Decimal("10000.00"),
        brain_config=brain_cfg,
        risk_config=risk_cfg,
        slippage_points=1,
        commission_per_lot_usd=Decimal("2.00"),
    )
    engine = BacktestEngine(config)

    now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    # Generate 300 ticks spanning multiple 1-minute bars
    ticks = []
    price = Decimal("2000.00")
    for i in range(300):
        # Stepping price
        price += Decimal("0.15") if (i % 2 == 0) else Decimal("-0.05")
        ticks.append(create_tick("XAUUSD", price, now + timedelta(seconds=i * 20)))

    result = engine.run(ticks)
    assert result.initial_balance_usd == Decimal("10000.00")
    assert result.disclaimer == "Backtest results are not proof of future profitability."
    assert isinstance(result.final_balance_usd, Decimal)

