"""
Risk Engine — profit-lock unit tests.
LOCKED PCT_RETRACE formula, activation threshold ($10), floor (30%).
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.risk.config import RiskConfig
from backend.risk.engine import AccountRiskSnapshot, RiskEngine
from backend.risk.states import RiskState, SignalDecision

CONFIGURED = RiskConfig(
    daily_loss_limit_usd=Decimal("100.00"),
    max_drawdown_usd=Decimal("500.00"),
    max_open_positions=5,
    risk_per_trade_pct=Decimal("0.01"),
)


def snap(
    equity: str = "1000.00",
    equity_peak: str = "1000.00",
    session_open: str | None = None,
    session_peak_profit: str | None = None,
    daily_pnl: str = "0.00",
) -> AccountRiskSnapshot:
    return AccountRiskSnapshot(
        account_id="pl-test",
        current_balance_usd=Decimal(equity),
        current_equity_usd=Decimal(equity),
        equity_peak_usd=Decimal(equity_peak),
        daily_realized_pnl_usd=Decimal(daily_pnl),
        daily_floating_pnl_usd=Decimal("0.00"),
        open_position_count=0,
        snapshot_at=datetime.now(UTC),
        session_open_equity_usd=Decimal(session_open) if session_open else None,
        session_peak_profit_usd=Decimal(session_peak_profit) if session_peak_profit else None,
    )


@pytest.mark.unit
class TestProfitLock:
    def test_no_session_data_not_evaluated(self) -> None:
        d = RiskEngine(CONFIGURED).evaluate(snap())
        assert d.decision == SignalDecision.APPROVED
        assert d.profit_lock_status is None

    def test_below_threshold_inactive(self) -> None:
        d = RiskEngine(CONFIGURED).evaluate(
            snap(equity="1009.00", session_open="1000.00", session_peak_profit="9.00")
        )
        assert d.profit_lock_status is not None
        assert d.profit_lock_status.is_active is False
        assert d.decision == SignalDecision.APPROVED

    def test_at_threshold_active_floor_calculated(self) -> None:
        d = RiskEngine(CONFIGURED).evaluate(
            snap(equity="1010.00", session_open="1000.00", session_peak_profit="10.00")
        )
        assert d.profit_lock_status is not None
        assert d.profit_lock_status.is_active is True
        assert d.profit_lock_status.protected_floor_usd == Decimal("3.00")

    def test_peak_20_floor_6(self) -> None:
        d = RiskEngine(CONFIGURED).evaluate(
            snap(equity="1018.00", session_open="1000.00", session_peak_profit="20.00")
        )
        assert d.profit_lock_status.protected_floor_usd == Decimal("6.00")

    def test_above_floor_approved(self) -> None:
        d = RiskEngine(CONFIGURED).evaluate(
            snap(equity="1015.00", session_open="1000.00", session_peak_profit="20.00")
        )
        assert d.decision == SignalDecision.APPROVED
        assert d.profit_lock_status.is_breached is False

    def test_below_floor_blocked_state_protected(self) -> None:
        d = RiskEngine(CONFIGURED).evaluate(
            snap(equity="1005.00", session_open="1000.00", session_peak_profit="20.00")
        )
        assert d.decision == SignalDecision.BLOCKED
        assert d.risk_state == RiskState.PROTECTED
        assert "PROFIT_LOCK_FLOOR_BREACHED" in d.reason_code
        assert d.trading_allowed is False

    def test_emergency_stop_overrides_profit_lock(self) -> None:
        cfg = CONFIGURED.model_copy(update={"emergency_stop_active": True})
        d = RiskEngine(cfg).evaluate(
            snap(equity="1005.00", session_open="1000.00", session_peak_profit="20.00")
        )
        assert d.decision == SignalDecision.EMERGENCY

    def test_daily_loss_precedes_profit_lock(self) -> None:
        cfg = CONFIGURED.model_copy(update={"daily_loss_limit_usd": Decimal("10.00")})
        d = RiskEngine(cfg).evaluate(
            snap(equity="990.00", session_open="1000.00", session_peak_profit="20.00", daily_pnl="-10.00")
        )
        assert d.decision == SignalDecision.BLOCKED
        assert "DAILY_LOSS" in d.reason_code


@pytest.mark.unit
class TestTotalDailyPnl:
    def test_floating_pnl_counts_toward_daily_limit(self) -> None:
        """Realized -$5 + floating -$5 = -$10 total = limit -> BLOCKED."""
        cfg = CONFIGURED.model_copy(update={"daily_loss_limit_usd": Decimal("10.00")})
        sn = AccountRiskSnapshot(
            account_id="daily-float",
            current_balance_usd=Decimal("990.00"),
            current_equity_usd=Decimal("990.00"),
            equity_peak_usd=Decimal("1000.00"),
            daily_realized_pnl_usd=Decimal("-5.00"),
            daily_floating_pnl_usd=Decimal("-5.00"),
            open_position_count=0,
            snapshot_at=datetime.now(UTC),
        )
        d = RiskEngine(cfg).evaluate(sn)
        assert d.decision == SignalDecision.BLOCKED
        assert "DAILY_LOSS" in d.reason_code
        assert d.daily_pnl_at_decision == Decimal("-10.00")

    def test_floating_pnl_just_under_limit_approved(self) -> None:
        """Realized -$4 + floating -$5 = -$9 < $10 -> APPROVED."""
        cfg = CONFIGURED.model_copy(update={"daily_loss_limit_usd": Decimal("10.00")})
        sn = AccountRiskSnapshot(
            account_id="daily-float",
            current_balance_usd=Decimal("991.00"),
            current_equity_usd=Decimal("991.00"),
            equity_peak_usd=Decimal("1000.00"),
            daily_realized_pnl_usd=Decimal("-4.00"),
            daily_floating_pnl_usd=Decimal("-5.00"),
            open_position_count=0,
            snapshot_at=datetime.now(UTC),
        )
        d = RiskEngine(cfg).evaluate(sn)
        assert d.decision == SignalDecision.APPROVED
