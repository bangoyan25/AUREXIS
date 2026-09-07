"""
Risk Engine logging regression tests (M-1).

Verifies that Risk Engine log calls never use float() for Decimal values.
Logging must not alter decision values.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

import backend.risk.engine as engine_module
from backend.risk.config import RiskConfig
from backend.risk.engine import AccountRiskSnapshot, RiskEngine


def make_configured_config() -> RiskConfig:
    return RiskConfig(
        daily_loss_limit_usd=Decimal("10.00"),
        max_drawdown_usd=Decimal("50.00"),
        max_open_positions=2,
        risk_per_trade_pct=Decimal("0.01"),
    )


def make_snapshot(
    equity: str = "1000.00",
    equity_peak: str = "1000.00",
    daily_pnl: str = "0.00",
    open_positions: int = 0,
) -> AccountRiskSnapshot:
    return AccountRiskSnapshot(
        account_id="log-test-account",
        current_balance_usd=Decimal(equity),
        current_equity_usd=Decimal(equity),
        equity_peak_usd=Decimal(equity_peak),
        daily_realized_pnl_usd=Decimal(daily_pnl),
        daily_floating_pnl_usd=Decimal("0.00"),
        open_position_count=open_positions,
        snapshot_at=datetime.now(UTC),
    )


@pytest.mark.unit
class TestRiskEngineLoggingNeverUsesFloat:
    """
    Capture log calls and verify no float() conversion on Decimal values.
    """

    def _capture_log_kwargs(self, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
        """Patch logger and collect keyword arguments from all calls."""
        captured: list[dict] = []
        mock_logger = MagicMock()

        def capture_call(*args, **kwargs):
            captured.append(kwargs)

        mock_logger.warning.side_effect = capture_call
        mock_logger.info.side_effect = capture_call
        monkeypatch.setattr(engine_module, "logger", mock_logger)
        return captured

    def _has_float_in_kwargs(self, captured: list[dict]) -> list[str]:
        """Return list of kwarg names that were passed as float."""
        bad = []
        for kwargs in captured:
            for k, v in kwargs.items():
                if isinstance(v, float):
                    bad.append(f"{k}={v!r}")
        return bad

    def test_daily_limit_log_uses_str_not_float(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._capture_log_kwargs(monkeypatch)
        engine = RiskEngine(config=make_configured_config())
        engine.evaluate(make_snapshot(daily_pnl="-10.00"))
        floats = self._has_float_in_kwargs(captured)
        assert not floats, f"Float values found in log kwargs: {floats}"

    def test_drawdown_log_uses_str_not_float(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._capture_log_kwargs(monkeypatch)
        engine = RiskEngine(config=make_configured_config())
        engine.evaluate(make_snapshot(equity_peak="1000.00", equity="950.00"))
        floats = self._has_float_in_kwargs(captured)
        assert not floats, f"Float values found in log kwargs: {floats}"

    def test_approved_log_uses_str_not_float(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._capture_log_kwargs(monkeypatch)
        engine = RiskEngine(config=make_configured_config())
        engine.evaluate(make_snapshot())
        floats = self._has_float_in_kwargs(captured)
        assert not floats, f"Float values found in log kwargs: {floats}"

    def test_decision_value_unchanged_by_logging(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Decision Decimal values must not be altered by log calls."""
        self._capture_log_kwargs(monkeypatch)
        engine = RiskEngine(config=make_configured_config())
        snap = make_snapshot(equity="975.00", equity_peak="1000.00")
        decision = engine.evaluate(snap)
        # drawdown = 1000.00 - 975.00 = 25.00
        assert decision.drawdown_at_decision == Decimal("25.00")
        assert isinstance(decision.equity_at_decision, Decimal)
