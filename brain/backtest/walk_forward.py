"""
Walk-Forward Validation — AUREXIS Brain.

Splits data chronologically: 70% training, 15% validation, 15% OOS.
Never optimize on OOS data.

Decision:
- Train/Val: parameter selection and qualitative evaluation.
- OOS: final unoptimized out-of-sample check.
- If OOS degradation > threshold: signal curve-fitting, not genuine edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from brain.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brain.market_data.types import Tick


@dataclass(frozen=True)
class WalkForwardResult:
    train_result: BacktestResult
    validation_result: BacktestResult
    oos_result: BacktestResult
    train_pct: Decimal
    validation_pct: Decimal
    oos_pct: Decimal
    train_size: int
    validation_size: int
    oos_size: int
    disclaimer: str = "Walk-forward results are not proof of future profitability."


def run_walk_forward(
    ticks: Sequence[Tick],
    config: BacktestConfig,
    train_ratio: Decimal = Decimal("0.70"),
    validation_ratio: Decimal = Decimal("0.15"),
    oos_ratio: Decimal = Decimal("0.15"),
) -> WalkForwardResult:
    """
    Split ticks chronologically and run separate backtests on each split.
    Returns the three result sets for comparison.
    OOS data must NEVER be used to select parameters.
    """
    n = len(ticks)
    train_end = int(n * float(train_ratio))
    val_end = int(n * float(train_ratio + validation_ratio))

    train_ticks = list(ticks[:train_end])
    val_ticks = list(ticks[train_end:val_end])
    oos_ticks = list(ticks[val_end:])

    engine = BacktestEngine(config)
    train_res = engine.run(train_ticks)

    engine2 = BacktestEngine(config)
    val_res = engine2.run(val_ticks)

    engine3 = BacktestEngine(config)
    oos_res = engine3.run(oos_ticks)

    return WalkForwardResult(
        train_result=train_res,
        validation_result=val_res,
        oos_result=oos_res,
        train_pct=train_ratio * Decimal("100"),
        validation_pct=validation_ratio * Decimal("100"),
        oos_pct=oos_ratio * Decimal("100"),
        train_size=len(train_ticks),
        validation_size=len(val_ticks),
        oos_size=len(oos_ticks),
    )
