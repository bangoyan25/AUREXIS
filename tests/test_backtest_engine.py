"""
Unit and integration tests for Brain Backtest Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.risk.config import RiskConfig
from brain.backtest.engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
)
from brain.config import BrainConfig
from brain.market_data.types import Tick


def make_ticks(base_time: datetime, count: int, start_price: Decimal = Decimal("2000.00")):
    ticks = []
    price = start_price
    for i in range(count):
        t = base_time + timedelta(seconds=i * 5)
        price = price + Decimal("0.10") if i % 2 == 0 else price - Decimal("0.05")
        ticks.append(
            Tick(
                symbol="XAUUSD",
                bid=price,
                ask=price + Decimal("0.20"),
                tick_time=t,
            )
        )
    return ticks


def test_backtest_engine_empty_ticks():
    """Backtest on empty tick list returns zeroed result with disclaimer."""
    config = BacktestConfig(initial_balance_usd=Decimal("10000.00"))
    engine = BacktestEngine(config=config)
    res = engine.run([])

    assert res.initial_balance_usd == Decimal("10000.00")
    assert res.final_balance_usd == Decimal("10000.00")
    assert res.total_trades == 0
    assert res.disclaimer == "Backtest results are not proof of future profitability."


def test_backtest_engine_unconfigured_fails_safe():
    """Unconfigured brain/risk safely runs without unauthorized trades."""
    config = BacktestConfig(
        initial_balance_usd=Decimal("5000.00"),
        brain_config=BrainConfig(),  # not configured
        risk_config=RiskConfig(),   # not configured
    )
    engine = BacktestEngine(config=config)
    ticks = make_ticks(datetime(2026, 9, 1, 0, 0, tzinfo=UTC), 20)
    res = engine.run(ticks)

    assert res.total_trades == 0
    assert res.final_balance_usd == Decimal("5000.00")


def test_backtest_engine_full_run():
    """Configured backtest executes with bar building, equity tracking, and drawdown recording."""
    config = BacktestConfig(
        initial_balance_usd=Decimal("10000.00"),
        symbol="XAUUSD",
        timeframe="M1",
        slippage_points=1,
        commission_per_lot_usd=Decimal("3.50"),
        brain_config=BrainConfig(
            trend_adx_threshold=Decimal("20.0"),
            min_breakout_atr_mult=Decimal("1.0"),
            rsi_oversold=Decimal("30.0"),
            rsi_overbought=Decimal("70.0"),
            min_composite_score=Decimal("60.0"),
            execution_timeframe="M1",
        ),
        risk_config=RiskConfig(
            daily_loss_limit_usd=Decimal("500"),
            max_drawdown_usd=Decimal("1000"),
            max_open_positions=2,
            default_position_size_lots=Decimal("0.10"),
            risk_per_trade_pct=Decimal("0.01"),
        ),
    )
    engine = BacktestEngine(config=config)
    # Generate 150 ticks across ~12 minutes to generate multiple closed M1 bars
    ticks = make_ticks(datetime(2026, 9, 1, 0, 0, tzinfo=UTC), 150)
    res = engine.run(ticks)

    assert isinstance(res, BacktestResult)
    assert res.initial_balance_usd == Decimal("10000.00")
    assert res.max_drawdown_usd >= Decimal("0")
    assert res.disclaimer == "Backtest results are not proof of future profitability."
