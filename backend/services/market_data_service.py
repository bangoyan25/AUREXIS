"""
Market Data Service for AUREXIS.

Authoritative server-side market data ingestion and state store.
Caches latest ticks in Redis (fast reads) with in-process memory fallback.
Enforces tenant isolation: all ticks strictly keyed by account_id and agent_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.core.logging import get_logger
from backend.core.redis import get_cache_client
from backend.ws.agent_protocol import BarsMessage, MarketDataMessage

logger = get_logger("market_data.service")

# In-process cache: id_str -> {symbol: tick_dict}
_in_memory_account_ticks: dict[str, dict[str, dict[str, Any]]] = {}
_in_memory_agent_ticks: dict[str, dict[str, dict[str, Any]]] = {}

# In-process cache: id_str -> {symbol: {timeframe: list[bar_dict]}}
_in_memory_account_bars: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = {}
_in_memory_agent_bars: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = {}
_in_memory_symbol_bars: dict[str, dict[str, list[dict[str, Any]]]] = {}

CANONICAL_SYMBOL = "XAUUSD"

TIMEFRAME_SECONDS: dict[str, int] = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}


def parse_market_time(raw_ts: str | None, default_dt: datetime | None = None) -> datetime:
    """Safely parse MT5 time (e.g. '2026.09.11 07:12:19') or ISO format into UTC datetime."""
    if not raw_ts:
        dt = default_dt or datetime.now(UTC)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    cleaned = raw_ts.strip().replace(".", "-")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            dt = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = default_dt or datetime.now(UTC)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


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
    _in_memory_account_bars.clear()
    _in_memory_agent_bars.clear()


async def record_closed_bars(
    agent_id: uuid.UUID,
    account_id: uuid.UUID,
    msg: BarsMessage,
) -> list[dict[str, Any]]:
    """Ingest and store validated closed bars from an authenticated MT5 agent."""
    norm_symbol = normalize_symbol(msg.symbol)
    norm_tf = msg.timeframe.strip().upper()
    sec = TIMEFRAME_SECONDS.get(norm_tf, 900)

    agent_id_str = str(agent_id)
    account_id_str = str(account_id)

    raw_bars: list[dict[str, Any]] = []
    for b in msg.bars:
        ot = parse_market_time(b.time)
        ct = ot + timedelta(seconds=sec)
        raw_bars.append({
            "symbol": norm_symbol,
            "timeframe": norm_tf,
            "open_time": ot.isoformat(),
            "close_time": ct.isoformat(),
            "open": str(b.open),
            "high": str(b.high),
            "low": str(b.low),
            "close": str(b.close),
            "volume": str(b.tick_volume or 0),
            "is_closed": True,
        })

    # Sort chronological ascending
    raw_bars.sort(key=lambda x: x["open_time"])

    # Deduplicate by open_time, keep at most 300
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for b in raw_bars:
        if b["open_time"] not in seen:
            seen.add(b["open_time"])
            deduped.append(b)

    if len(deduped) > 300:
        deduped = deduped[-300:]

    if account_id_str not in _in_memory_account_bars:
        _in_memory_account_bars[account_id_str] = {}
    if norm_symbol not in _in_memory_account_bars[account_id_str]:
        _in_memory_account_bars[account_id_str][norm_symbol] = {}
    _in_memory_account_bars[account_id_str][norm_symbol][norm_tf] = deduped

    if agent_id_str not in _in_memory_agent_bars:
        _in_memory_agent_bars[agent_id_str] = {}
    if norm_symbol not in _in_memory_agent_bars[agent_id_str]:
        _in_memory_agent_bars[agent_id_str][norm_symbol] = {}
    _in_memory_agent_bars[agent_id_str][norm_symbol][norm_tf] = deduped

    # Global symbol cache
    if norm_symbol not in _in_memory_symbol_bars:
        _in_memory_symbol_bars[norm_symbol] = {}
    _in_memory_symbol_bars[norm_symbol][norm_tf] = deduped

    try:
        redis = get_cache_client()
        account_key = f"market_data:bars:account:{account_id_str}:{norm_symbol}:{norm_tf}"
        agent_key = f"market_data:bars:agent:{agent_id_str}:{norm_symbol}:{norm_tf}"
        symbol_key = f"market_data:bars:symbol:{norm_symbol}:{norm_tf}"
        serialized = json.dumps(deduped)
        async with redis.pipeline(transaction=True) as pipe:
            pipe.set(account_key, serialized, ex=86400)
            pipe.set(agent_key, serialized, ex=86400)
            pipe.set(symbol_key, serialized, ex=86400)
            await pipe.execute()
    except Exception as exc:
        logger.warning(
            "market_data.bars_redis_write_failed",
            error=str(exc),
            account_id=account_id_str,
            agent_id=agent_id_str,
        )

    # Seed into strategy service's BarManager for immediate availability
    try:
        from backend.services.strategy_service import seed_account_bars
        seed_account_bars(account_id_str, norm_symbol, norm_tf, deduped)
    except Exception as exc:
        logger.warning(
            "market_data.seed_strategy_bars_failed",
            error=str(exc),
            account_id=account_id_str,
        )

    return deduped



async def get_closed_bars(
    account_id: uuid.UUID,
    symbol: str = CANONICAL_SYMBOL,
    timeframe: str = "M15",
) -> list[dict[str, Any]]:
    """Retrieve stored closed bars for account, symbol, and timeframe."""
    account_id_str = str(account_id)
    norm_symbol = normalize_symbol(symbol)
    norm_tf = timeframe.strip().upper()

    if (
        account_id_str in _in_memory_account_bars
        and norm_symbol in _in_memory_account_bars[account_id_str]
        and norm_tf in _in_memory_account_bars[account_id_str][norm_symbol]
    ):
        return _in_memory_account_bars[account_id_str][norm_symbol][norm_tf]

    try:
        redis = get_cache_client()
        account_key = f"market_data:bars:account:{account_id_str}:{norm_symbol}:{norm_tf}"
        raw = await redis.get(account_key)
        if raw:
            bars_list = json.loads(raw)
            if account_id_str not in _in_memory_account_bars:
                _in_memory_account_bars[account_id_str] = {}
            if norm_symbol not in _in_memory_account_bars[account_id_str]:
                _in_memory_account_bars[account_id_str][norm_symbol] = {}
            _in_memory_account_bars[account_id_str][norm_symbol][norm_tf] = bars_list
            return bars_list
    except Exception as exc:
        logger.warning(
            "market_data.bars_redis_read_failed",
            error=str(exc),
            account_id=account_id_str,
        )

    return []


def aggregate_bars(m15_bars: list[dict[str, Any]], target_tf: str) -> list[dict[str, Any]]:
    """Synthesize multi-timeframe OHLCV bars from canonical M15 broker bars."""
    if not m15_bars:
        return []
    target_tf = target_tf.strip().upper()
    if target_tf == "M15":
        return m15_bars

    if target_tf in ("M30", "H1", "H4", "D1"):
        buckets: dict[str, list[dict[str, Any]]] = {}
        for b in m15_bars:
            ot_str = b.get("open_time")
            dt = parse_market_time(ot_str)
            if target_tf == "M30":
                bucket_dt = dt.replace(minute=(dt.minute // 30) * 30, second=0, microsecond=0)
            elif target_tf == "H1":
                bucket_dt = dt.replace(minute=0, second=0, microsecond=0)
            elif target_tf == "H4":
                bucket_dt = dt.replace(hour=(dt.hour // 4) * 4, minute=0, second=0, microsecond=0)
            elif target_tf == "D1":
                bucket_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                bucket_dt = dt
            k = bucket_dt.isoformat()
            if k not in buckets:
                buckets[k] = []
            buckets[k].append(b)

        result = []
        for k in sorted(buckets.keys()):
            items = buckets[k]
            items.sort(key=lambda x: x.get("open_time", ""))
            open_p = float(items[0].get("open", 0))
            high_p = max(float(x.get("high", 0)) for x in items)
            low_p = min(float(x.get("low", 0)) for x in items)
            close_p = float(items[-1].get("close", 0))
            vol = sum(float(x.get("volume", 0)) for x in items)
            result.append({
                "open_time": k,
                "close_time": items[-1].get("close_time", k),
                "open": str(round(open_p, 2)),
                "high": str(round(high_p, 2)),
                "low": str(round(low_p, 2)),
                "close": str(round(close_p, 2)),
                "volume": str(round(vol)),
                "is_closed": True,
            })
        return result

    if target_tf in ("M1", "M5"):
        sub_count = 3 if target_tf == "M5" else 15
        sub_min = 5 if target_tf == "M5" else 1
        result = []
        for b in m15_bars:
            dt = parse_market_time(b.get("open_time"))
            o = float(b.get("open", 0))
            h = float(b.get("high", 0))
            l = float(b.get("low", 0))
            c = float(b.get("close", 0))
            vol = float(b.get("volume", 0)) / sub_count
            for j in range(sub_count):
                sub_dt = dt + timedelta(minutes=j * sub_min)
                sub_close_dt = sub_dt + timedelta(minutes=sub_min)
                ratio = (j + 1) / sub_count
                prev_ratio = j / sub_count
                sub_o = o + (c - o) * prev_ratio
                sub_c = o + (c - o) * ratio
                sub_h = max(sub_o, sub_c) + (h - max(o, c)) * (1.0 if j == sub_count // 2 else 0.2)
                sub_l = min(sub_o, sub_c) - (min(o, c) - l) * (1.0 if j == sub_count // 4 else 0.2)
                result.append({
                    "open_time": sub_dt.isoformat(),
                    "close_time": sub_close_dt.isoformat(),
                    "open": str(round(sub_o, 2)),
                    "high": str(round(max(sub_h, sub_o, sub_c), 2)),
                    "low": str(round(min(sub_l, sub_o, sub_c), 2)),
                    "close": str(round(sub_c, 2)),
                    "volume": str(round(vol)),
                    "is_closed": True,
                })
        return result

    return m15_bars


async def get_symbol_closed_bars(
    symbol: str = CANONICAL_SYMBOL,
    timeframe: str = "M15",
) -> list[dict[str, Any]]:
    """Retrieve stored closed bars for symbol across the platform."""
    norm_symbol = normalize_symbol(symbol)
    norm_tf = timeframe.strip().upper()

    if norm_symbol in _in_memory_symbol_bars and norm_tf in _in_memory_symbol_bars[norm_symbol]:
        return _in_memory_symbol_bars[norm_symbol][norm_tf]

    # Search in any active account memory
    for acct_data in _in_memory_account_bars.values():
        if norm_symbol in acct_data and norm_tf in acct_data[norm_symbol] and acct_data[norm_symbol][norm_tf]:
            return acct_data[norm_symbol][norm_tf]

    # Search in any active agent memory
    for agent_data in _in_memory_agent_bars.values():
        if norm_symbol in agent_data and norm_tf in agent_data[norm_symbol] and agent_data[norm_symbol][norm_tf]:
            return agent_data[norm_symbol][norm_tf]

    try:
        redis = get_cache_client()
        symbol_key = f"market_data:bars:symbol:{norm_symbol}:{norm_tf}"
        raw = await redis.get(symbol_key)
        if raw:
            bars_list = json.loads(raw)
            if norm_symbol not in _in_memory_symbol_bars:
                _in_memory_symbol_bars[norm_symbol] = {}
            _in_memory_symbol_bars[norm_symbol][norm_tf] = bars_list
            return bars_list
    except Exception:
        pass

    # If requested non-M15 timeframe and direct bars not in cache, synthesize from M15
    if norm_tf != "M15":
        m15_bars = await get_symbol_closed_bars(symbol=norm_symbol, timeframe="M15")
        if m15_bars:
            synth = aggregate_bars(m15_bars, norm_tf)
            if norm_symbol not in _in_memory_symbol_bars:
                _in_memory_symbol_bars[norm_symbol] = {}
            _in_memory_symbol_bars[norm_symbol][norm_tf] = synth
            return synth

    return []


async def get_agent_closed_bars(
    agent_id: uuid.UUID,
    symbol: str = CANONICAL_SYMBOL,
    timeframe: str = "M15",
) -> list[dict[str, Any]]:
    """Retrieve stored closed bars for agent, symbol, and timeframe."""
    agent_id_str = str(agent_id)
    norm_symbol = normalize_symbol(symbol)
    norm_tf = timeframe.strip().upper()

    if (
        agent_id_str in _in_memory_agent_bars
        and norm_symbol in _in_memory_agent_bars[agent_id_str]
        and norm_tf in _in_memory_agent_bars[agent_id_str][norm_symbol]
    ):
        return _in_memory_agent_bars[agent_id_str][norm_symbol][norm_tf]

    try:
        redis = get_cache_client()
        agent_key = f"market_data:bars:agent:{agent_id_str}:{norm_symbol}:{norm_tf}"
        raw = await redis.get(agent_key)
        if raw:
            bars_list = json.loads(raw)
            if agent_id_str not in _in_memory_agent_bars:
                _in_memory_agent_bars[agent_id_str] = {}
            if norm_symbol not in _in_memory_agent_bars[agent_id_str]:
                _in_memory_agent_bars[agent_id_str][norm_symbol] = {}
            _in_memory_agent_bars[agent_id_str][norm_symbol][norm_tf] = bars_list
            return bars_list
    except Exception as exc:
        logger.warning(
            "market_data.bars_redis_read_failed",
            error=str(exc),
            agent_id=agent_id_str,
        )

    return []
