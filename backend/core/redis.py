"""
Redis connection management for AUREXIS.

AUREXIS uses Redis for:
- Cache (fast reads for market state, account summaries)
- Realtime pub/sub (WebSocket event broadcasting)
- Ephemeral coordination (e.g., distributed locks)

Redis is NOT authoritative for durable financial state.
PostgreSQL is the source of truth for all financial records.
"""

from __future__ import annotations

from redis.asyncio import ConnectionPool, Redis

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("redis")

# ── Connection pools ───────────────────────────────────────────────────────
_cache_pool: ConnectionPool | None = None
_pubsub_pool: ConnectionPool | None = None


def _make_pool(db: int) -> ConnectionPool:
    return ConnectionPool.from_url(
        settings.REDIS_URL,
        db=db,
        max_connections=20,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )


def get_cache_pool() -> ConnectionPool:
    """Return (creating if necessary) the cache connection pool."""
    global _cache_pool
    if _cache_pool is None:
        _cache_pool = _make_pool(settings.REDIS_CACHE_DB)
    return _cache_pool


def get_pubsub_pool() -> ConnectionPool:
    """Return (creating if necessary) the pub/sub connection pool."""
    global _pubsub_pool
    if _pubsub_pool is None:
        _pubsub_pool = _make_pool(settings.REDIS_PUBSUB_DB)
    return _pubsub_pool


def get_cache_client() -> Redis:
    """Return an async Redis client for cache operations."""
    return Redis(connection_pool=get_cache_pool())


def get_pubsub_client() -> Redis:
    """Return an async Redis client for pub/sub operations."""
    return Redis(connection_pool=get_pubsub_pool())


async def close_redis_pools() -> None:
    """Close all Redis connection pools — call on application shutdown."""
    global _cache_pool, _pubsub_pool
    if _cache_pool:
        await _cache_pool.disconnect()
        _cache_pool = None
    if _pubsub_pool:
        await _pubsub_pool.disconnect()
        _pubsub_pool = None
    logger.info("redis.pools_closed")


async def check_redis_health() -> dict[str, object]:
    """
    Ping Redis and return health status.
    Used by /health endpoint.
    """
    try:
        client = get_cache_client()
        pong = await client.ping()
        info = await client.info("server")
        return {
            "status": "healthy",
            "ping": pong,
            "redis_version": info.get("redis_version", "unknown"),
        }
    except Exception as exc:
        logger.warning("redis.health_check_failed", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}
