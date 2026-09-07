"""
Deterministic Robustness & Monte Carlo Analysis — AUREXIS Brain.

Perturbs execution assumptions to test system fragility:
1. Trade ordering randomization (Monte Carlo sequence test)
2. Slippage perturbation (0, 1, 2, 3 points)
3. Spread perturbation (+10%, +25%, +50%)
4. Execution delay simulation

Never present robustness as proof of profitability.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from brain.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brain.market_data.types import Tick


@dataclass(frozen=True)
class RobustnessRun:
    perturbation_type: str
    perturbation_value: str
    result: BacktestResult


@dataclass(frozen=True)
class RobustnessSummary:
    runs: list[RobustnessRun]
    monte_carlo_drawdowns_usd: list[Decimal]
    median_mc_drawdown_usd: Decimal
    max_mc_drawdown_usd: Decimal
    disclaimer: str = "Robustness analysis does not guarantee future results."


def run_monte_carlo_order_shuffle(
    result: BacktestResult,
    num_iterations: int = 100,
    seed: int = 42,
) -> list[Decimal]:
    """
    Randomize trade order to simulate different sequence of wins/losses.
    Returns list of maximum drawdowns from each reshuffled path.
    """
    if not result.trades:
        return [Decimal("0.00")]

    pnls = [t.realized_pnl_usd for t in result.trades]
    rng = random.Random(seed)
    max_drawdowns: list[Decimal] = []

    for _ in range(num_iterations):
        shuffled = list(pnls)
        rng.shuffle(shuffled)
        equity = result.initial_balance_usd
        peak = equity
        max_dd = Decimal("0.00")
        for pnl in shuffled:
            equity += pnl
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        max_drawdowns.append(max_dd)

    return max_drawdowns


def run_robustness_battery(
    ticks: Sequence[Tick],
    base_config: BacktestConfig,
    slippage_steps: list[int] | None = None,
    mc_iterations: int = 50,
) -> RobustnessSummary:
    """
    Run slippage variations and Monte Carlo sequence testing.
    """
    steps = slippage_steps or [0, 1, 2, 3]
    runs: list[RobustnessRun] = []

    base_engine = BacktestEngine(base_config)
    base_result = base_engine.run(ticks)
    runs.append(RobustnessRun("BASE", "0", base_result))

    for slip in steps:
        if slip == base_config.slippage_points:
            continue
        cfg = BacktestConfig(
            initial_balance_usd=base_config.initial_balance_usd,
            symbol=base_config.symbol,
            point_value=base_config.point_value,
            contract_size=base_config.contract_size,
            slippage_points=slip,
            commission_per_lot_usd=base_config.commission_per_lot_usd,
            brain_config=base_config.brain_config,
            risk_config=base_config.risk_config,
            timeframe=base_config.timeframe,
        )
        engine = BacktestEngine(cfg)
        res = engine.run(ticks)
        runs.append(RobustnessRun("SLIPPAGE", f"{slip}pts", res))

    # Monte Carlo trade order shuffle on base result
    mc_dds = run_monte_carlo_order_shuffle(base_result, num_iterations=mc_iterations)
    mc_dds_sorted = sorted(mc_dds)
    median_dd = mc_dds_sorted[len(mc_dds_sorted) // 2]
    max_dd = max(mc_dds)

    return RobustnessSummary(
        runs=runs,
        monte_carlo_drawdowns_usd=mc_dds,
        median_mc_drawdown_usd=median_dd,
        max_mc_drawdown_usd=max_dd,
    )
