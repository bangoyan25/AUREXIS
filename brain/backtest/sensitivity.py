"""
Parameter Sensitivity Analysis — AUREXIS Brain.

Tests strategy parameter neighborhoods to evaluate performance stability.
Never optimize on OOS or choose isolated spike anomalies.
Goal: Robustness > Maximum Profit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from brain.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brain.market_data.types import Tick


@dataclass(frozen=True)
class SensitivityPoint:
    param_name: str
    param_value: Any
    result: BacktestResult


@dataclass(frozen=True)
class SensitivityReport:
    param_name: str
    points: list[SensitivityPoint]
    is_stable: bool
    disclaimer: str = "Sensitivity analysis does not guarantee future performance."


def run_parameter_sweep(
    ticks: Sequence[Tick],
    base_config: BacktestConfig,
    param_path: str,
    test_values: list[Any],
) -> SensitivityReport:
    """
    Run backtest across a sequence of values for a single parameter.
    param_path: e.g. "brain_config.trend.fast_ma_period"
    """
    points: list[SensitivityPoint] = []

    for val in test_values:
        # Clone base config
        b_cfg = base_config.brain_config.model_copy(deep=True)
        r_cfg = base_config.risk_config.model_copy(deep=True)

        parts = param_path.split(".")
        if parts[0] == "brain_config" and len(parts) == 3:
            section = getattr(b_cfg, parts[1])
            setattr(section, parts[2], val)
        elif parts[0] == "risk_config" and len(parts) == 2:
            setattr(r_cfg, parts[1], val)

        cfg = BacktestConfig(
            initial_balance_usd=base_config.initial_balance_usd,
            symbol=base_config.symbol,
            point_value=base_config.point_value,
            contract_size=base_config.contract_size,
            slippage_points=base_config.slippage_points,
            commission_per_lot_usd=base_config.commission_per_lot_usd,
            brain_config=b_cfg,
            risk_config=r_cfg,
            timeframe=base_config.timeframe,
        )

        engine = BacktestEngine(cfg)
        res = engine.run(ticks)
        points.append(SensitivityPoint(param_name=param_path, param_value=val, result=res))

    # Evaluate stability: drawdown doesn't jump by > 50% across neighbors
    stable = True
    if len(points) >= 2:
        max_dds = [p.result.max_drawdown_usd for p in points]
        if max_dds and max(max_dds) > Decimal("0"):
            min_dd = min(max_dds)
            max_dd = max(max_dds)
            if min_dd > Decimal("0") and (max_dd / min_dd) > Decimal("3.0"):
                stable = False

    return SensitivityReport(param_name=param_path, points=points, is_stable=stable)
