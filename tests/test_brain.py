"""
Tests for market data types and strategy interfaces.

Verifies:
- Tick math (spread, mid)
- Mock provider is clearly labeled as non-live
- MarketDataStatus fail-safe when threshold is UNDEFINED
- NotConfiguredStrategyEngine never generates live signals
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from brain.market_data.types import DataSource, MarketDataStatus, Tick
from brain.strategy.interfaces import (
    NotConfiguredStrategyEngine,
    SignalDirection,
    StrategyStatus,
)


@pytest.mark.unit
class TestTickMath:
    def test_spread_calculation(self) -> None:
        tick = Tick(
            symbol="XAUUSD",
            broker_symbol="XAUUSD.m",
            bid=Decimal("2000.00"),
            ask=Decimal("2000.50"),
            tick_time=datetime.now(UTC),
            received_at=datetime.now(UTC),
            source=DataSource.MOCK,
        )
        assert tick.spread == Decimal("0.50")

    def test_mid_price(self) -> None:
        tick = Tick(
            symbol="XAUUSD",
            broker_symbol="XAUUSD.m",
            bid=Decimal("2000.00"),
            ask=Decimal("2001.00"),
            tick_time=datetime.now(UTC),
            received_at=datetime.now(UTC),
            source=DataSource.MOCK,
        )
        assert tick.mid == Decimal("2000.50")

    def test_mock_tick_is_identified(self) -> None:
        tick = Tick(
            symbol="XAUUSD",
            broker_symbol="XAUUSD.MOCK",
            bid=Decimal("2000.00"),
            ask=Decimal("2000.50"),
            tick_time=datetime.now(UTC),
            received_at=datetime.now(UTC),
            source=DataSource.MOCK,
        )
        assert tick.is_mock() is True

    def test_live_tick_not_mock(self) -> None:
        tick = Tick(
            symbol="XAUUSD",
            broker_symbol="XAUUSD",
            bid=Decimal("2000.00"),
            ask=Decimal("2000.50"),
            tick_time=datetime.now(UTC),
            received_at=datetime.now(UTC),
            source=DataSource.LIVE_BROKER,
        )
        assert tick.is_mock() is False


@pytest.mark.unit
class TestMarketDataStatusFailSafe:
    def test_undefined_threshold_not_fresh(self) -> None:
        """When staleness threshold is UNDEFINED (None), data is never fresh — fail safe."""
        status = MarketDataStatus(
            symbol="XAUUSD",
            is_live=True,
            source=DataSource.LIVE_BROKER,
            last_tick_at=datetime.now(UTC),
            staleness_seconds=1.0,
            staleness_threshold_seconds=None,  # UNDEFINED
        )
        assert status.is_fresh is False

    def test_no_last_tick_not_fresh(self) -> None:
        status = MarketDataStatus(
            symbol="XAUUSD",
            is_live=True,
            source=DataSource.LIVE_BROKER,
            last_tick_at=None,
            staleness_seconds=None,
            staleness_threshold_seconds=30,
        )
        assert status.is_fresh is False

    def test_not_live_not_fresh(self) -> None:
        status = MarketDataStatus(
            symbol="XAUUSD",
            is_live=False,
            source=DataSource.MOCK,
            last_tick_at=datetime.now(UTC),
            staleness_seconds=0.1,
            staleness_threshold_seconds=30,
        )
        assert status.is_fresh is False

    def test_fresh_within_threshold(self) -> None:
        status = MarketDataStatus(
            symbol="XAUUSD",
            is_live=True,
            source=DataSource.LIVE_BROKER,
            last_tick_at=datetime.now(UTC),
            staleness_seconds=5.0,
            staleness_threshold_seconds=30,
        )
        assert status.is_fresh is True

    def test_stale_beyond_threshold(self) -> None:
        status = MarketDataStatus(
            symbol="XAUUSD",
            is_live=True,
            source=DataSource.LIVE_BROKER,
            last_tick_at=datetime.now(UTC),
            staleness_seconds=31.0,
            staleness_threshold_seconds=30,
        )
        assert status.is_fresh is False


@pytest.mark.unit
class TestNotConfiguredStrategyEngine:
    def test_generates_no_signal(self) -> None:
        engine = NotConfiguredStrategyEngine()
        signal = engine.generate_signal("XAUUSD")
        assert signal.direction == SignalDirection.NONE
        assert signal.is_configured is False

    def test_status_is_not_configured(self) -> None:
        engine = NotConfiguredStrategyEngine()
        assert engine.status == StrategyStatus.NOT_CONFIGURED

    def test_signal_has_no_confidence_score(self) -> None:
        signal = NotConfiguredStrategyEngine().generate_signal("XAUUSD")
        assert signal.confidence_score is None

    def test_signal_has_no_sl_tp(self) -> None:
        signal = NotConfiguredStrategyEngine().generate_signal("XAUUSD")
        assert signal.suggested_stop_loss is None
        assert signal.suggested_take_profit is None

    def test_signal_identifies_as_not_configured(self) -> None:
        signal = NotConfiguredStrategyEngine().generate_signal("XAUUSD")
        assert signal.strategy_id == "NOT_CONFIGURED"
        assert "UNDEFINED" in signal.market_state_summary
