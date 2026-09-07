# ADR-001: Redis Ephemeral Role and MT5 Connection State Authority

**Date:** 2026-09-06  
**Status:** Accepted  
**Deciders:** AUREXIS Architecture

---

## Context

The audit identified a contradiction between:

1. `backend/core/redis.py` docstring: *"Redis is NOT authoritative for durable financial state. PostgreSQL is the source of truth for all financial records."*
2. `backend/db/models/mt5_agent.py` comment on `last_known_status`: *"Connection state (ephemeral — authoritative state is in Redis)"*

Redis is configured with `--save "" --appendonly no` — no persistence. After a Redis restart, all Redis state is lost.

---

## Decision

**PostgreSQL is the authoritative durable store for MT5 connection state.**

Redis **may cache** the live connection state for fast reads (e.g., "is this agent currently connected?"),
but it is **not the authority**.

The `MT5Agent` model fields `last_seen_at` and `last_known_status` in PostgreSQL serve as the durable
record of the last known state. After a Redis restart, the system recovers by reading PostgreSQL.

### Behavioral rules

| Scenario | Correct behavior |
|---|---|
| Agent connects | Update `last_seen_at`, `last_known_status = "CONNECTED"` in PostgreSQL. Cache in Redis. |
| Agent disconnects | Update `last_known_status = "DISCONNECTED"` in PostgreSQL. Remove from Redis. |
| Redis restart | MT5 connection state is unknown in Redis. Read `last_known_status` from PostgreSQL. Unknown/DISCONNECTED → no execution allowed. |
| Unknown connection state | NEVER permits new trade execution. Safe default is: if state is unknown, treat as DISCONNECTED. |
| Agent reconnects after Redis loss | Agent sends heartbeat → update PostgreSQL + Redis. State is restored. |

### Safe recovery invariant

After Redis restart, `last_known_status` in PostgreSQL may be stale (e.g., agent was connected but Redis lost the live state). The system must **assume DISCONNECTED** until the agent sends a fresh heartbeat. This is fail-safe: stale "CONNECTED" state never permits trades.

---

## Consequences

1. `MT5Agent.last_known_status` comment is corrected: PostgreSQL is authoritative; Redis is a cache layer.
2. Redis `--save "" --appendonly no` is **correct** — no persistence needed because PostgreSQL is authoritative.
3. All code that reads MT5 connection state for trade authorization must read from PostgreSQL (or treat Redis cache miss as DISCONNECTED).
4. MT5 connectivity implementation (Phase 3) must persist state changes to PostgreSQL before responding to the agent.

---

## Corrected comment in MT5Agent model

```
# Connection state — PostgreSQL is authoritative.
# Redis may cache live state for fast reads.
# After Redis restart, read this field and treat UNKNOWN/CONNECTED as DISCONNECTED
# until the agent sends a fresh heartbeat.
```
