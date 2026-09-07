"""
Tests for sensitivity, walk-forward, and robustness modules — TASK-003.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from brain.backtest.engine import BacktestConfig, BacktestTrade
from brain.backtest.robustness import run_monte_carlo_order_shuffle, run_robustness_battery
from brain.backtest.sensitivity import run_parameter_sweep
from brain.backtest.walk_forward import run_walk_forward
from brain.config import default_strat_config
from brain.market_data.types import DataSource, Tick


def create_tick_stream(n: int = 100) -> list[Tick]:
    base = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    ticks = []
    p = Decimal("2000.00")
    for i in range(n):
        p += Decimal("0.10") if i % 2 == 0 else Decimal("-0.05")
        t = base + timedelta(seconds=i * 10)
        ticks.append(Tick(
            symbol="XAUUSD", broker_symbol="XAUUSD",
            bid=p, ask=p + Decimal("0.20"),
            tick_time=t, received_at=t, source=DataSource.REPLAY,
        ))
    return ticks


def test_sensitivity_sweep_returns_report():
    ticks = create_tick_stream(50)
    base_cfg = BacktestConfig(
        initial_balance_usd=Decimal("10000.00"),
        brain_config=default_strat_config(),
    )
    report = run_parameter_sweep(
        ticks=ticks,
        base_config=base_cfg,
        param_path="brain_config.trend.fast_ma_period",
        test_values=[15, 20, 25],
    )
    assert len(report.points) == 3
    assert report.param_name == "brain_config.trend.fast_ma_period"
    assert "disclaimer" in dir(report)


def test_walk_forward_splits_data():
    ticks = create_tick_stream(100)
    cfg = BacktestConfig(
        initial_balance_usd=Decimal("10000.00"),
        brain_config=default_strat_config(),
    )
    wf_res = run_walk_forward(ticks, cfg)
    assert wf_res.train_size == 70
    assert wf_res.validation_size == 15
    assert wf_res.oos_size == 15
    assert wf_res.train_pct == Decimal("70.00")
    assert wf_res.oos_result is not None


def test_monte_carlo_order_shuffle():
    from brain.backtest.engine import BacktestResult
    trade1 = BacktestTrade(
        trade_id="t1", symbol="XAUUSD", side="BUY",
        entry_time=datetime.now(UTC), entry_price=Decimal("2000"),
        volume_lots=Decimal("0.10"), stop_loss=None, take_profit=None,
        realized_pnl_usd=Decimal("50.00"),
    )
    trade2 = BacktestTrade(
        trade_id="t2", symbol="XAUUSD", side="BUY",
        entry_time=datetime.now(UTC), entry_price=Decimal("2000"),
        volume_lots=Decimal("0.10"), stop_loss=None, take_profit=None,
        realized_pnl_usd=Decimal("-30.00"),
    )
    res = BacktestResult(
        initial_balance_usd=Decimal("10000.00"),
        final_balance_usd=Decimal("10020.00"),
        total_net_pnl_usd=Decimal("20.00"),
        total_trades=2, winning_trades=1, losing_trades=1,
        win_rate_pct=Decimal("50.00"), profit_factor=Decimal("1.67"),
        max_drawdown_usd=Decimal("30.00"), max_drawdown_pct=Decimal("0.30"),
        trades=[trade1, trade2],
    )
    dds = run_monte_carlo_order_shuffle(res, num_iterations=20, seed=123)
    assert len(dds) == 20
    assert all(isinstance(d, Decimal) for d in dds)


def test_robustness_battery():
    ticks = create_tick_stream(30)
    cfg = BacktestConfig(
        initial_balance_usd=Decimal("10000.00"),
        brain_config=default_strat_config(),
    )
    rob = run_robustness_battery(ticks, cfg, slippage_steps=[0, 1], mc_iterations=10)
    assert len(rob.runs) >= 2
    assert "disclaimer" in dir(rob)
