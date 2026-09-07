# AUREXIS Frontend–Backend Integration

> **Status:** COMPLETE — All 23 frontend pages wired to real typed API hooks.
> **Date:** 2026-09-07
> **Author:** Cline (AI Coding Agent)

---

## Overview

AUREXIS frontend (Next.js 15 / TypeScript strict) integrates with the FastAPI backend via:
1. Typed REST API hooks (`frontend/lib/hooks/`)
2. Authenticated WebSocket context (`frontend/lib/websocket-context.tsx`)
3. Account selection context (`frontend/lib/account-context.tsx`)

All mock data has been replaced with real typed backend hooks. The only remaining mock components are explicitly documented below.

---

## API Hooks

All hooks are in `frontend/lib/hooks/`. All use `useAuth()` for token management. All preserve backend state without fabrication.

| Hook | Endpoint | Account-Scoped | Notes |
|---|---|---|---|
| `useHealth` | `GET /api/v1/health` | No | Public. Polls health state. |
| `useAccounts` | `GET /api/v1/accounts` | No | Returns `[]` until authenticated. |
| `useAgents` | `GET /api/v1/agents` | No | Returns `[]` until authenticated. |
| `useActivity` | `GET /api/v1/activity` | No | Returns `[]` until authenticated. |
| `useRisk` | `GET /api/v1/risk/{accountId}` | Yes | `NO_ACCOUNT` state when null accountId. |
| `useBrain` | `GET /api/v1/brain/{accountId}` | Yes | `NO_ACCOUNT` state when null accountId. |
| `useMarket` | `GET /api/v1/market/tick` | No | `NOT_CONFIGURED` until market data provider set. |
| `useSignals` | `GET /api/v1/signals` | No | Returns `[]` when no signals. |
| `usePositions` | `GET /api/v1/positions` | No | Returns `EMPTY` / `[]` when no positions. |
| `useExecution` | `GET /api/v1/execution` | No | Returns `[]` when no commands. |
| `useNews` | `GET /api/v1/news` | No | `UNKNOWN` is NOT coerced to `CLEAR`. Fail-closed. |
| `usePerformance` | `GET /api/v1/performance` | No | Returns zero stats when no trades. |
| `useBacktest` | `GET /api/v1/backtest` | No | `NOT_CONFIGURED` until parameters set. |

---

## Context Providers

### `AccountProvider` (`frontend/lib/account-context.tsx`)

- Loads accounts via `useAccounts()` after authentication.
- Auto-selects first account; preserves selection across re-renders.
- Clears on logout.
- Exposes: `accounts`, `selectedAccountId`, `selectedAccount`, `selectAccount`, `loading`, `error`, `refetchAccounts`.

### `WebSocketProvider` (`frontend/lib/websocket-context.tsx`)

- Wraps `AurexisWebSocket` from `frontend/lib/websocket.ts`.
- Connects **only** when `isAuthenticated && token && selectedAccountId` are non-null.
- Disconnects cleanly on logout, account change, or provider unmount.
- Reconnects safely with exponential backoff (2s–30s).
- Exposes real lifecycle state (`CONNECTING`, `CONNECTED`, `DISCONNECTED`, `ERROR`) via `ws.setStateCallback()`.
- **Previously**: optimistic `CONNECTED` after 200ms timer. **Now**: actual WebSocket lifecycle state.
- Token is never logged or exposed to UI.
- Security: backend validates JWT + DB account ownership before `accept()`. Non-owned accounts → close(4002). Cross-user subscription is server-rejected.
- Exposes: `connectionState: WsConnectionState`, `subscribe(eventType, handler): () => void`.

---

## Real-Time Page Subscriptions

Three pages subscribe to backend WebSocket events for live data invalidation.

| Page | Subscribes To | Action |
|---|---|---|
| `SignalsPage` | `SIGNAL_CREATED` | Calls `refetch()` on `useSignals` |
| `PositionsPage` | `POSITION_UPDATED` | Calls `refetch()` on `usePositions` |
| `ExecutionPage` | `COMMAND_CREATED`, `COMMAND_UPDATED` | Calls `refetch()` on `useExecution` |

Rules:
- Do NOT fabricate signal/position/command data from WS payload.
- Always refetch from backend REST — WS is a trigger only.
- Fail-safe states are preserved: `NOT_CONFIGURED`, `EMPTY`, `UNKNOWN` remain explicit.

---

## Error / Loading State Semantics

All pages strictly enforce:

| Wrong | Correct |
|---|---|
| `LOADING === SUCCESS` | `LOADING` shows spinner, no data |
| `ERROR === EMPTY` | `ERROR` shows error banner, `EMPTY` shows empty state |
| `UNKNOWN === CLEAR` | `UNKNOWN` treated as blocked (fail-closed) |
| `NOT_CONFIGURED === NORMAL` | `NOT_CONFIGURED` shows `<NotConfigured/>` component |
| `BLOCKED === AUTHORIZED` | `BLOCKED` shows red BLOCKED badge |
| `NO_ACCOUNT_SELECTED === account data` | `NO_ACCOUNT` shows prompt to select account |

No hook falls back from backend failure to mock data.

---

## Remaining Mock Components

| Component | Location | Reason |
|---|---|---|
| OHLCV Candlestick Chart | `frontend/features/market/MarketPage.tsx` | Backend OHLCV endpoint does not exist yet. |

No other mock data remains.

---

## PostgreSQL Runtime Verification

**Docker is NOT installed on this machine.**

Offline verification completed:
- `infrastructure/docker-compose.yml`: PostgreSQL 16 + Redis 7 correctly configured.
- `migrations/versions/`: 3 migration files (`001_initial.py`, `002_refresh_tokens.py`, `003_trading_domain.py`).
- `backend/db/models/__init__.py`: 14 ORM models registered with `Base.metadata`.
- Schema integrity tests: `tests/test_database_schema.py` — 7 tests pass.

**PostgreSQL runtime: NOT VERIFIED — Docker unavailable.**
**Redis runtime: NOT VERIFIED — Docker unavailable.**

---

## Local Startup Procedure

**Prerequisites:** Docker Desktop, `.env` from `.env.example` with `JWT_SECRET`, `ENCRYPTION_KEY`.

```bash
# 1. Start infra
cd infrastructure && docker compose up -d

# 2. Run migrations
alembic upgrade head && alembic current
# Expected: 003_trading_domain (head)

# 3. Start backend
.venv\Scripts\uvicorn backend.main:app --reload --port 8000

# 4. Verify health
curl http://localhost:8000/api/v1/health

# 5. Start frontend
cd frontend && npm run dev
# http://localhost:3000
```

---

## Remaining Blockers

| Blocker | Impact |
|---|---|
| Docker not installed on dev machine | Cannot verify PostgreSQL/Redis runtime |
| Market data provider UNDEFINED | `NOT_CONFIGURED`, MarketPage OHLCV uses mock |
| News provider UNDEFINED | `UNKNOWN` (fail-closed) |
| Risk parameters UNDEFINED | `NOT_CONFIGURED`, no trading |
| Brain parameters UNDEFINED | `NOT_CONFIGURED`, no signals |
| Live broker UNDEFINED | Simulation mode only |

---

| Lifecycle | `connectionState` |
|---|---|
| Before `ws.connect()` | `DISCONNECTED` |
| `ws = new WebSocket(url)` | `CONNECTING` |
| `ws.onopen` fires | `CONNECTED` |
| `ws.onerror` fires | `ERROR` |
| `ws.onclose` fires | `DISCONNECTED` |
| Provider cleanup / logout / account change | `DISCONNECTED` |

---

## Infrastructure Verification Status Matrix

| Component | Status | Details |
|---|---|---|
| PostgreSQL 16 schema | STATICALLY VERIFIED | 14 tables, migrations 001-003, 7 schema tests pass |
| PostgreSQL 16 runtime | NOT VERIFIED | Docker CLI unavailable on host |
| Redis 7 runtime | NOT VERIFIED | Docker CLI unavailable on host |
| FastAPI REST endpoints | STATICALLY & UNIT VERIFIED | 313 pytest tests pass, SQLite in-memory |
| WebSocket lifecycle | RUNTIME VERIFIED (client unit) | Tested via Jest/mock socket, backend WS unit tests pass |
| Frontend Next.js build | RUNTIME VERIFIED (build) | 23/23 static pages compiled clean |

---

AUREXIS LIVE TRADING STATUS: DISABLED

