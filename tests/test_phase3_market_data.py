"""
Tests for Phase 3 Market Data validation and service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.services import market_data_service
from backend.ws.agent_protocol import MarketDataMessage, parse_agent_message


@pytest.mark.unit
class TestMarketDataMessageValidation:
    """Test MarketDataMessage strict validation and error handling."""

    def test_valid_market_data_message(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "XAUUSD",
            "bid": "2650.50",
            "ask": "2650.75",
            "spread": "0.25",
            "point": "0.01",
            "digits": 2,
            "tick_time": "2026-09-10 12:00:00",
            "tick_volume": 15,
        }
        msg = parse_agent_message(payload)
        assert isinstance(msg, MarketDataMessage)
        assert msg.symbol == "XAUUSD"
        assert msg.bid == Decimal("2650.50")
        assert msg.ask == Decimal("2650.75")
        assert msg.spread == Decimal("0.25")
        assert msg.point == Decimal("0.01")
        assert msg.digits == 2
        assert msg.tick_volume == 15

    def test_missing_fields_rejected(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "XAUUSD",
            # missing bid, ask, spread
        }
        with pytest.raises(ValueError):
            parse_agent_message(payload)

    def test_nan_numeric_rejected(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "XAUUSD",
            "bid": float("nan"),
            "ask": "2650.75",
            "spread": "0.25",
            "tick_time": "2026-09-10 12:00:00",
        }
        with pytest.raises(ValueError, match="cannot be NaN"):
            parse_agent_message(payload)

    def test_inf_numeric_rejected(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "XAUUSD",
            "bid": "2650.50",
            "ask": float("inf"),
            "spread": "0.25",
            "tick_time": "2026-09-10 12:00:00",
        }
        with pytest.raises(ValueError, match="cannot be NaN or Infinite"):
            parse_agent_message(payload)

    def test_invalid_string_numeric_rejected(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "XAUUSD",
            "bid": "not-a-number",
            "ask": "2650.75",
            "spread": "0.25",
            "tick_time": "2026-09-10 12:00:00",
        }
        with pytest.raises(ValueError, match="valid numeric value"):
            parse_agent_message(payload)

    def test_bid_less_than_zero_rejected(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "XAUUSD",
            "bid": "-10.00",
            "ask": "2650.75",
            "spread": "0.25",
            "tick_time": "2026-09-10 12:00:00",
        }
        with pytest.raises(ValueError, match="greater than 0"):
            parse_agent_message(payload)

    def test_ask_less_than_bid_rejected(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "XAUUSD",
            "bid": "2650.50",
            "ask": "2640.00",
            "spread": "0.25",
            "tick_time": "2026-09-10 12:00:00",
        }
        with pytest.raises(ValueError, match="cannot be less than bid"):
            parse_agent_message(payload)

    def test_negative_spread_rejected(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "XAUUSD",
            "bid": "2650.50",
            "ask": "2650.75",
            "spread": "-0.25",
            "tick_time": "2026-09-10 12:00:00",
        }
        with pytest.raises(ValueError, match="cannot be negative"):
            parse_agent_message(payload)

    def test_empty_symbol_rejected(self) -> None:
        payload = {
            "type": "market_data",
            "symbol": "   ",
            "bid": "2650.50",
            "ask": "2650.75",
            "spread": "0.25",
            "tick_time": "2026-09-10 12:00:00",
        }
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            parse_agent_message(payload)


@pytest.mark.unit
@pytest.mark.asyncio
class TestMarketDataServiceStateAndFreshness:
    """Test market data service storage, symbol normalization, and staleness."""

    async def test_record_and_get_tick(self) -> None:
        market_data_service.clear_local_cache()
        agent_id = uuid.uuid4()
        account_id = uuid.uuid4()

        msg = MarketDataMessage(
            type="market_data",
            symbol="XAUUSD.raw",
            bid=Decimal("2650.50"),
            ask=Decimal("2650.75"),
            spread=Decimal("0.25"),
            point=Decimal("0.01"),
            digits=2,
            tick_time="2026-09-10 12:00:00",
            tick_volume=10,
        )

        recorded = await market_data_service.record_market_data(agent_id, account_id, msg)
        assert recorded["symbol"] == "XAUUSD"
        assert recorded["raw_symbol"] == "XAUUSD.RAW"
        assert recorded["bid"] == "2650.50"

        fetched = await market_data_service.get_latest_market_data(account_id, "XAUUSD")
        assert fetched is not None
        assert fetched["bid"] == "2650.50"
        assert fetched["ask"] == "2650.75"

@pytest.mark.unit
class TestMarketDataServiceFreshness:
    """Test tick freshness evaluation."""

    def test_freshness_evaluation(self) -> None:
        now = datetime.now(UTC)
        fresh_tick = {"received_at": now.isoformat()}
        is_fresh, code, age_ms = market_data_service.evaluate_freshness(fresh_tick, max_staleness_ms=2000)
        assert is_fresh is True
        assert code == "FRESH"
        assert age_ms is not None and age_ms < 500

        stale_time = now - timedelta(seconds=5)
        stale_tick = {"received_at": stale_time.isoformat()}
        is_fresh_stale, code_stale, age_stale = market_data_service.evaluate_freshness(
            stale_tick, max_staleness_ms=2000
        )
        assert is_fresh_stale is False
        assert code_stale == "STALE"
        assert age_stale is not None and age_stale >= 4500

        is_fresh_none, code_none, age_none = market_data_service.evaluate_freshness(None)
        assert is_fresh_none is False
        assert code_none == "NO_DATA"
        assert age_none is None

