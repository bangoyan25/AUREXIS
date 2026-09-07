"""
Position sizing policy interfaces and implementations.

Strict role separation:
- Brain suggests stop loss price level (or None).
- Risk Engine calculates the authorized lot size based on equity and approved risk percentage.
- Decimal precision only — float arithmetic is forbidden.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from typing import Protocol


class PositionSizingPolicy(Protocol):
    """Protocol for calculating risk-authorized order volume."""

    def calculate_lot_size(
        self,
        equity_usd: Decimal,
        entry_price: Decimal | None,
        stop_loss_price: Decimal | None,
    ) -> Decimal | None:
        """Return authorized lot size in Decimal, or None if sizing cannot be determined."""
        ...


class PercentageEquitySizingPolicy:
    """
    Owner-approved default position sizing policy: Percentage of Equity at Risk.

    Lot size formula for XAUUSD (contract size 100 oz):
      risk_amount_usd = equity_usd * risk_per_trade_pct
      stop_distance = abs(entry_price - stop_loss_price)
      raw_lots = risk_amount_usd / (stop_distance * contract_size)
    """

    def __init__(
        self,
        risk_per_trade_pct: Decimal,
        contract_size: Decimal = Decimal("100"),
        min_lot: Decimal = Decimal("0.01"),
        max_lot: Decimal | None = None,
        lot_step: Decimal = Decimal("0.01"),
    ) -> None:
        self.risk_per_trade_pct = risk_per_trade_pct
        self.contract_size = contract_size
        self.min_lot = min_lot
        self.max_lot = max_lot
        self.lot_step = lot_step

    def calculate_lot_size(
        self,
        equity_usd: Decimal,
        entry_price: Decimal | None,
        stop_loss_price: Decimal | None,
    ) -> Decimal | None:
        if entry_price is None or stop_loss_price is None:
            return None
        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance <= Decimal("0"):
            return None
        if equity_usd <= Decimal("0"):
            return None

        risk_amount_usd = equity_usd * self.risk_per_trade_pct
        dollar_risk_per_lot = stop_distance * self.contract_size
        raw_lots = risk_amount_usd / dollar_risk_per_lot

        # Round down to nearest lot step
        steps = (raw_lots / self.lot_step).quantize(Decimal("1"), rounding=ROUND_DOWN)
        lots = steps * self.lot_step

        if lots < self.min_lot:
            return None  # Risk allocation is smaller than broker minimum lot
        if self.max_lot is not None and lots > self.max_lot:
            lots = self.max_lot

        return lots.quantize(self.lot_step)


class FixedLotSizingPolicy:
    """Legacy or explicit fixed lot policy."""

    def __init__(self, fixed_lots: Decimal) -> None:
        self.fixed_lots = fixed_lots

    def calculate_lot_size(
        self,
        equity_usd: Decimal,
        entry_price: Decimal | None,
        stop_loss_price: Decimal | None,
    ) -> Decimal | None:
        return self.fixed_lots
