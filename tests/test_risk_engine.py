"""
Risk Engine unit tests.

Tests: NOT_CONFIGURED, daily loss, drawdown, positions, emergency stop, approved.
All tests use explicit test configuration — no production values assumed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.risk.config import RiskConfig
from backend.risk.engine import AccountRiskSnapshot, RiskEngine
from backend.risk.states import RiskState, SignalDecision


def make_snapshot(
    account_id: str = "test-account",
    equity: str = "1000.00",
    equity_peak: str = "1000.00",
    daily_pnl: str = "0.00",
    open_positions: int = 0,
) -> AccountRiskSnapshot:
    return AccountRiskSnapshot(
        account_id=account_id,
        current_balance_usd=Decimal(equity),
        current_equity_usd=Decimal(equity),
        equity_peak_usd=Decimal(equity_peak),
        daily_realized_pnl_usd=Decimal(daily_pnl),
        daily_floating_pnl_usd=Decimal("0.00"),
        open_position_count=open_positions,
        snapshot_at=datetime.now(UTC),
    )


CONFIGURED = RiskConfig(
    daily_loss_limit_usd=Decimal("10.00"),
    max_drawdown_usd=Decimal("50.00"),
    max_open_positions=2,
    risk_per_trade_pct=Decimal("0.01"),
)


@pytest.mark.unit
class TestNotConfigured:
    def test_all_none_not_configured(self) -> None:
        d = RiskEngine(config=RiskConfig()).evaluate(make_snapshot())
        assert d.decision == SignalDecision.NOT_CONFIGURED
        assert d.risk_state == RiskState.NOT_CONFIGURED
        assert d.trading_allowed is False

    def test_partial_config_not_configured(self) -> None:
        partial = RiskConfig(daily_loss_limit_usd=Decimal("10"), max_drawdown_usd=Decimal("50"))
        d = RiskEngine(config=partial).evaluate(make_snapshot())
        assert d.decision == SignalDecision.NOT_CONFIGURED

    def test_missing_params_listed_in_reason(self) -> None:
        d = RiskEngine(config=RiskConfig()).evaluate(make_snapshot())
        assert "daily_loss_limit_usd" in d.reason_code
        assert "max_drawdown_usd" in d.reason_code

    def test_config_missing_params_property(self) -> None:
        cfg = RiskConfig(daily_loss_limit_usd=Decimal("10"))
        assert "daily_loss_limit_usd" not in cfg.missing_parameters
        assert "max_drawdown_usd" in cfg.missing_parameters


@pytest.mark.unit
class TestEmergencyStop:
    def test_emergency_stop_blocks(self) -> None:
        base = CONFIGURED.model_dump()
        base["emergency_stop_active"] = True
        cfg = RiskConfig(**base)
        d = RiskEngine(config=cfg).evaluate(make_snapshot())
        assert d.decision == SignalDecision.EMERGENCY
        assert d.risk_state == RiskState.EMERGENCY_STOP
        assert d.trading_allowed is False

    def test_emergency_overrides_profitable_account(self) -> None:
        base = CONFIGURED.model_dump()
        base["emergency_stop_active"] = True
        cfg = RiskConfig(**base)
        d = RiskEngine(config=cfg).evaluate(make_snapshot(daily_pnl="100.00"))
        assert d.decision == SignalDecision.EMERGENCY


@pytest.mark.unit
class TestDailyLoss:
    def test_at_limit_blocks(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot(daily_pnl="-10.00"))
        assert d.decision == SignalDecision.BLOCKED
        assert d.risk_state == RiskState.STOPPED
        assert "DAILY_LOSS" in d.reason_code

    def test_below_limit_not_blocked_by_daily_loss(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot(daily_pnl="-9.99"))
        assert "DAILY_LOSS" not in d.reason_code


@pytest.mark.unit
class TestDrawdown:
    def test_at_limit_blocks(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(
            make_snapshot(equity_peak="1000.00", equity="950.00")
        )
        assert d.decision == SignalDecision.BLOCKED
        assert "MAX_DRAWDOWN" in d.reason_code

    def test_below_limit_ok(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(
            make_snapshot(equity_peak="1000.00", equity="951.00")
        )
        assert "MAX_DRAWDOWN" not in d.reason_code


@pytest.mark.unit
class TestPositions:
    def test_at_max_blocks(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot(open_positions=2))
        assert d.decision == SignalDecision.BLOCKED
        assert "MAX_POSITIONS" in d.reason_code

    def test_below_max_ok(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot(open_positions=1))
        assert "MAX_POSITIONS" not in d.reason_code


@pytest.mark.unit
class TestApproved:
    def test_clean_account_approved(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot())
        assert d.decision == SignalDecision.APPROVED
        assert d.risk_state == RiskState.NORMAL
        assert d.trading_allowed is True

    def test_correlation_id_propagated(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot(), correlation_id="cid-x")
        assert d.correlation_id == "cid-x"

    def test_correlation_id_auto_generated(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot())
        assert len(d.correlation_id) > 0

    def test_trading_allowed_false_for_non_approved(self) -> None:
        assert RiskEngine(config=RiskConfig()).evaluate(make_snapshot()).trading_allowed is False
        base = CONFIGURED.model_dump()
        base["emergency_stop_active"] = True
        assert RiskEngine(config=RiskConfig(**base)).evaluate(make_snapshot()).trading_allowed is False


@pytest.mark.unit
class TestExposureLimits:
    def test_basket_lots_exceeded_blocks(self) -> None:
        cfg = RiskConfig(
            daily_loss_limit_usd=Decimal("10.00"),
            max_drawdown_usd=Decimal("50.00"),
            max_open_positions=5,
            max_open_lots=Decimal("2.0"),
            default_position_size_lots=Decimal("0.5"),
        )
        snap = AccountRiskSnapshot(
            account_id="test-account",
            current_balance_usd=Decimal("1000.00"),
            current_equity_usd=Decimal("1000.00"),
            equity_peak_usd=Decimal("1000.00"),
            daily_realized_pnl_usd=Decimal("0.00"),
            daily_floating_pnl_usd=Decimal("0.00"),
            open_position_count=2,
            snapshot_at=datetime.now(UTC),
            open_lot_exposure=Decimal("1.8"),
        )
        d = RiskEngine(config=cfg).evaluate(snap)
        assert d.decision == SignalDecision.BLOCKED
        assert "MAX_LOTS_EXCEEDED" in d.reason_code
        assert d.risk_state == RiskState.CAUTION


@pytest.mark.unit
class TestMarketConditionChecks:
    def test_stale_market_data_blocks(self) -> None:
        from backend.risk.engine import MarketCondition
        cfg = CONFIGURED
        cond = MarketCondition(tick_age_ms=2500)
        d = RiskEngine(config=cfg).evaluate(make_snapshot(), market_condition=cond)
        assert d.decision == SignalDecision.BLOCKED
        assert "STALE_MARKET_DATA" in d.reason_code
        assert d.risk_state == RiskState.CAUTION

    def test_market_data_not_ready_blocks(self) -> None:
        from backend.risk.engine import MarketCondition
        cfg = CONFIGURED
        cond = MarketCondition(market_data_status="DISCONNECTED")
        d = RiskEngine(config=cfg).evaluate(make_snapshot(), market_condition=cond)
        assert d.decision == SignalDecision.BLOCKED
        assert "MARKET_DATA_NOT_READY" in d.reason_code

    def test_spread_too_high_blocks(self) -> None:
        from backend.risk.engine import MarketCondition
        cfg = RiskConfig(
            daily_loss_limit_usd=Decimal("10.00"),
            max_drawdown_usd=Decimal("50.00"),
            max_open_positions=5,
            default_position_size_lots=Decimal("0.01"),
            max_spread_usd=Decimal("0.50"),
        )
        cond = MarketCondition(spread=Decimal("0.75"))
        d = RiskEngine(config=cfg).evaluate(make_snapshot(), market_condition=cond)
        assert d.decision == SignalDecision.BLOCKED
        assert "SPREAD_TOO_HIGH" in d.reason_code


@pytest.mark.unit
class TestNewsProtectionChecks:
    def test_pre_event_news_blocks(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot(), news_state="PRE_EVENT")
        assert d.decision == SignalDecision.BLOCKED
        assert "NEWS_EVENT_WINDOW" in d.reason_code

    def test_news_unavailable_blocks(self) -> None:
        d = RiskEngine(config=CONFIGURED).evaluate(make_snapshot(), news_state="PROVIDER_UNAVAILABLE")
        assert d.decision == SignalDecision.BLOCKED
        assert "NEWS_DATA_UNAVAILABLE" in d.reason_code


@pytest.mark.unit
class TestCautionDrawdown:
    def test_caution_drawdown_blocks_with_caution_state(self) -> None:
        cfg = RiskConfig(
            daily_loss_limit_usd=Decimal("10.00"),
            max_drawdown_usd=Decimal("100.00"),
            caution_drawdown_pct=Decimal("0.80"),
            max_open_positions=5,
            default_position_size_lots=Decimal("0.01"),
        )
        # Peak 1000, current 915 -> drawdown 85 >= 80 (80% of 100)
        snap = make_snapshot(equity_peak="1000.00", equity="915.00")
        d = RiskEngine(config=cfg).evaluate(snap)
        assert d.decision == SignalDecision.BLOCKED
        assert "CAUTION_DRAWDOWN_REACHED" in d.reason_code
        assert d.risk_state == RiskState.CAUTION


@pytest.mark.unit
class TestPositionSizing:
    def test_percentage_equity_sizing_calculates_lots(self) -> None:
        from dataclasses import dataclass

        @dataclass
        class MockCandidate:
            entry_reference: Decimal = Decimal("2000.00")
            suggested_stop_loss: Decimal = Decimal("1995.00")  # $5 distance = $500 risk per 1.0 lot

        cfg = CONFIGURED  # risk_per_trade_pct = 0.01 (1%)
        snap = make_snapshot(equity="10000.00")  # 1% of 10,000 = $100 risk
        # $100 risk / ($5 * 100) = 0.20 lots
        d = RiskEngine(config=cfg).evaluate(snap, candidate_signal=MockCandidate())
        assert d.decision == SignalDecision.APPROVED
        assert d.authorized_lot_size == Decimal("0.20")

