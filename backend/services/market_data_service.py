"""
Market Data Service for AUREXIS.

Authoritative server-side market data ingestion and state store.
Caches latest ticks in Redis (fast reads) with in-process memory fallback.
Enforces tenant isolation: all ticks strictly keyed by account_id and agent_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.core.logging import get_logger
from backend.core.redis import get_cache_client
from backend.ws.agent_protocol import MarketDataMessage

logger = get_logger("market_data.service")

# In-process cache: id_str -> {symbol: tick_dict}
_in_memory_account_ticks: dict[str, dict[str, dict[str, Any]]] = {}
_in_memory_agent_ticks: dict[str, dict[str, dict[str, Any]]] = {}

CANONICAL_SYMBOL = "XAUUSD"


def normalize_symbol(raw_symbol: str) -> str:
    """Normalize broker symbol variations to canonical instrument name."""
    s = raw_symbol.strip().upper()
    if s.startswith("XAUUSD"):
        return CANONICAL_SYMBOL
    return s


def evaluate_freshness(
    tick_data: dict[str, Any] | None,
    max_staleness_ms: int = 2000,
) -> tuple[bool, str, int | None]:
    """
    Evaluate freshness of a market tick.
    Returns: (is_fresh: bool, status_code: str, age_ms: int | None)
    """
    if not tick_data or "received_at" not in tick_data:
        return False, "NO_DATA", None

    try:
        received_at_dt = datetime.fromisoformat(tick_data["received_at"])
        if received_at_dt.tzinfo is None:
            received_at_dt = received_at_dt.replace(tzinfo=UTC)
        age_ms = max(0, int((datetime.now(UTC) - received_at_dt).total_seconds() * 1000))
    except Exception:
        return False, "NO_DATA", None

    if age_ms > max_staleness_ms:
        return False, "STALE", age_ms

    return True, "FRESH", age_ms


async def record_market_data(
    agent_id: uuid.UUID,
    account_id: uuid.UUID,
    msg: MarketDataMessage,
) -> dict[str, Any]:
    """Ingest and store validated market tick from an authenticated MT5 agent."""
    norm_symbol = normalize_symbol(msg.symbol)
    now = datetime.now(UTC)
    now_iso = now.isoformat()

    agent_id_str = str(agent_id)
    account_id_str = str(account_id)

    tick_dict: dict[str, Any] = {
        "agent_id": agent_id_str,
        "account_id": account_id_str,
        "symbol": norm_symbol,
        "raw_symbol": msg.symbol,
        "bid": str(msg.bid),
        "ask": str(msg.ask),
        "spread": str(msg.spread),
        "point": str(msg.point),
        "digits": msg.digits,
        "tick_time": msg.tick_time,
        "tick_volume": msg.tick_volume or 0,
        "received_at": now_iso,
    }

    if account_id_str not in _in_memory_account_ticks:
        _in_memory_account_ticks[account_id_str] = {}
    _in_memory_account_ticks[account_id_str][norm_symbol] = tick_dict

    if agent_id_str not in _in_memory_agent_ticks:
        _in_memory_agent_ticks[agent_id_str] = {}
    _in_memory_agent_ticks[agent_id_str][norm_symbol] = tick_dict

    try:
        redis = get_cache_client()
        serialized = json.dumps(tick_dict)
        account_key = f"market_data:account:{account_id_str}:{norm_symbol}"
        agent_key = f"market_data:agent:{agent_id_str}:{norm_symbol}"
        async with redis.pipeline(transaction=True) as pipe:
            pipe.set(account_key, serialized, ex=300)
            pipe.set(agent_key, serialized, ex=300)
            await pipe.execute()
    except Exception as exc:
        logger.warning(
            "market_data.redis_write_failed",
            error=str(exc),
            account_id=account_id_str,
            agent_id=agent_id_str,
        )

    return tick_dict


async def get_latest_market_data(
    account_id: uuid.UUID,
    symbol: str = CANONICAL_SYMBOL,
) -> dict[str, Any] | None:
    """Retrieve latest tick for account and symbol. Memory first, then Redis."""
    account_id_str = str(account_id)
    norm_symbol = normalize_symbol(symbol)

    if (
        account_id_str in _in_memory_account_ticks
        and norm_symbol in _in_memory_account_ticks[account_id_str]
    ):
        return _in_memory_account_ticks[account_id_str][norm_symbol]

    try:
        redis = get_cache_client()
        account_key = f"market_data:account:{account_id_str}:{norm_symbol}"
        raw = await redis.get(account_key)
        if raw:
            tick_dict = json.loads(raw)
            if account_id_str not in _in_memory_account_ticks:
                _in_memory_account_ticks[account_id_str] = {}
            _in_memory_account_ticks[account_id_str][norm_symbol] = tick_dict
            return tick_dict
    except Exception as exc:
        logger.warning("market_data.redis_read_failed", error=str(exc), account_id=account_id_str)

    return None


async def get_latest_agent_market_data(
    agent_id: uuid.UUID,
    symbol: str = CANONICAL_SYMBOL,
) -> dict[str, Any] | None:
    """Retrieve latest tick for agent and symbol."""
    agent_id_str = str(agent_id)
    norm_symbol = normalize_symbol(symbol)

    if (
        agent_id_str in _in_memory_agent_ticks
        and norm_symbol in _in_memory_agent_ticks[agent_id_str]
    ):
        return _in_memory_agent_ticks[agent_id_str][norm_symbol]

    try:
        redis = get_cache_client()
        agent_key = f"market_data:agent:{agent_id_str}:{norm_symbol}"
        raw = await redis.get(agent_key)
        if raw:
            tick_dict = json.loads(raw)
            if agent_id_str not in _in_memory_agent_ticks:
                _in_memory_agent_ticks[agent_id_str] = {}
            _in_memory_agent_ticks[agent_id_str][norm_symbol] = tick_dict
            return tick_dict
    except Exception as exc:
        logger.warning("market_data.redis_read_failed", error=str(exc), agent_id=agent_id_str)

    return None


def clear_local_cache() -> None:
    """Clear in-memory cache for tests."""
    _in_memory_account_ticks.clear()
    _in_memory_agent_ticks.clear()
