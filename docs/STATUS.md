# AUREXIS Project Status

## Phase 0 complete — 2026-09-06

TASK-001: Master specification locked.
TASK-002: Risk Engine specification locked (PCT_RETRACE formula, LIFETIME_HWM reference, locked defaults).
TASK-003: Brain specification locked (6 evidence dimensions, closed-bar rule, full pipeline).
TASK-004: MT5 Command Protocol locked (wire schemas, heartbeat, lifecycle, execution report, sync, reconciliation).
TASK-005: Database schema finalized (`docs/DATABASE_SCHEMA.md` — 5 IMPLEMENTED tables verified against 001+002 migrations and ORM models; 9 PLANNED tables from migration 003; UNDEFINED items explicitly listed).
TASK-006: API contracts finalized (`docs/API_SPEC.md` — all REST endpoints with request/response schemas, error codes, auth).
TASK-007: WebSocket event contracts finalized (`docs/WEBSOCKET_SPEC.md` — envelope, close codes, all event payloads).

## Specification status

`docs/MASTER_SPECIFICATION.md` v1.0 locked 2026-09-06.

## Phase 1 complete — 2026-09-06

TASK-101 through TASK-106: repo setup, Docker, Alembic, Redis, FastAPI skeleton, Next.js skeleton.

## Phase 5 complete — 2026-09-06

TASK-501: Tick normalization and market data types (`brain/market_data/types.py`).
TASK-502: Market state model with is_fresh check.
TASK-503: Strategy interfaces (`brain/strategy/interfaces.py`).
TASK-504: Signal pipeline skeleton (`brain/pipeline.py`).
TASK-505: News protection interface scaffolded.

TASK-301: MT5 heartbeat & session management (`backend/services/mt5_session.py`).
TASK-302: Account-state reporting schema (`AccountStateReport`).
TASK-303: Position/order reporting schemas (`PositionReport`, `ExecutionReport`).
TASK-304: Command lifecycle state machine (`ExecutionCommand`, `CommandState`, `VALID_TRANSITIONS`, idempotency key, expiry).
TASK-305: Reconciliation engine skeleton (`ReconciliationEngine`; ORPHAN, PHANTOM, VOLUME_MISMATCH, SIDE_MISMATCH detection).

TASK-201: DB models (User, TradingAccount, MT5Agent, AuditLog).
TASK-202: Auth service + REST endpoints (register, login, refresh, logout, me).
TASK-203: Account management REST API (CRUD, ownership isolation, cent normalization).
TASK-204: MT5Agent model + read endpoints.
TASK-205: WebSocket infrastructure.
TASK-206: Audit log service + activity read endpoint.

Domain stub endpoints established for all unimplemented domains:
risk, brain, market, signals, positions, execution, news, performance, backtest.
All return NOT_CONFIGURED / EMPTY — no fake data.

## Security Hardening complete — 2026-09-06

**TASK-702 (Security Hardening):**

1. **Refresh token JTI revocation** — `refresh_tokens` table (migration 002).
   - Each refresh token has a unique JTI stored on login.
   - Refresh rotates: old JTI revoked, new JTI stored.
   - Logout revokes the JTI immediately.
   - Replay of revoked token → 401 REFRESH_TOKEN_REVOKED.
   - Multiple sessions per user supported independently.

2. **WebSocket DB ownership** — PostgreSQL-authoritative account ownership.
   - account_id verified against `TradingAccount.user_id` before accept().
   - User A cannot subscribe to User B's accounts.
   - Invalid account_id or non-owned account → close(4002).
   - Token never logged.

3. **Authorization audit** — all endpoints verified:
   - Accounts: DB-level `user_id` filter on all CRUD.
   - Agents: join through TradingAccount.user_id.
   - Activity: filtered by user_id.
   - WebSocket: DB ownership confirmed.

4. **ADRs created:** ADR-001 (JTI tracking), ADR-002 (WS auth transport).

## Phase 4 & Phase 5 Implementation Complete — 2026-09-06

- **Risk Engine:** Full deterministic state machine (`NORMAL`, `CAUTION`, `PROTECTED`, `STOPPED`, `EMERGENCY_STOP`).
- **Profit Lock:** Locked `PCT_RETRACE` formula over floating equity basis, monotonic rising floor.
- **Position Sizing:** `PercentageEquitySizingPolicy` (equity % at risk, Decimal arithmetic) and `FixedLotSizingPolicy`.
- **Brain Pipeline:** `SignalPipeline` with `BarBuilder` (enforcing closed-bar rule), regime classification, structure analysis, multi-factor scoring, fail-closed `SignalDirection.NONE` when unconfigured.
- **News Protection Engine:** `NewsProtectionEngine` with pre/post-event blackout windows, fail-closed news safety.
- **Backtest Engine:** `BacktestEngine` with chronological replay over identical Brain + Risk pipeline, slippage, commission, trade ledger, equity curves.
- **MT5 Simulator:** Deterministic local execution agent simulating fills, tickets, reports, positions, and account states.
- **Database Schema (ORM):** All 9 trading-domain ORM models (`RiskConfiguration`, `RiskDecision`, `CandidateSignal`, `ExecutionCommand`, `ExecutionReport`, `Position`, `EquitySnapshot`, `DailySessionState`, `NewsEvent`) implemented in `backend/db/models/` and verified against `Base.metadata` (14 tables registered). `docs/DATABASE_SCHEMA.md` Section 3 updated from PLANNED→IMPLEMENTED.
- **MT5AgentSimulator:** `backend/simulation/adapters.py` — deterministic local execution, SIMULATION-labelled, never touches live broker.
- **MT5SessionService:** In-memory session tracking class added to `backend/services/mt5_session.py`.
- **Risk Service:** `backend/services/risk_service.py` — DB-backed config load, snapshot build, evaluate + persist immutable audit trail.
- **Position Sizing:** `backend/risk/sizing.py` — `PercentageEquitySizingPolicy`, `FixedLotSizingPolicy` (Decimal-only arithmetic).
- **End-to-End Acceptance Pipeline:** `tests/test_local_acceptance_pipeline.py` verifies full 12-step lifecycle in-memory (SQLite, no live infra required).

## Phase 5 & TASK-003 Implementation Complete — 2026-09-06

- **Brain Strategy Engine (`AUREXIS-STRAT-1.0.0`):**
  - Canonical configuration in `brain/config.py` (`BrainConfig`, `default_strat_config`).
  - Structure Engine (`brain/structure.py`): Swing detection, BOS with ATR displacement, CHoCH, equal level tolerance.
  - Regime Engine (`brain/regime.py`): TREND_UP, TREND_DOWN, RANGE, TRANSITION, HIGH_VOLATILITY, UNKNOWN. Hysteresis, normalized ATR baseline.
  - Indicators (`brain/indicators.py`): EMA, SMA, ATR, RSI, Wilder ADX/DI, ATR rolling baseline.
  - Setup Detection (`brain/strategy/setups.py`): LONG_BREAKOUT, SHORT_BREAKOUT, LONG_FAKEOUT_REVERSAL, SHORT_FAKEOUT_REVERSAL, CONTINUATION.
  - Multi-Factor Scorer (`brain/scoring.py`): 6 independent evidence dimensions (Structure 25%, Setup 25%, Trend 20%, Momentum 10%, Volatility 10%, Regime 10%). Min confidence 0.70. Hard gates evaluated before scoring.
  - Backtest Engine Extensions (`brain/backtest/engine.py`): Full trade metrics (expectancy, profit factor, consecutive wins/losses, largest win/loss).
  - Advanced Backtest Tools:
    - Sensitivity sweep (`brain/backtest/sensitivity.py`)
    - Walk-forward 70/15/15 validation (`brain/backtest/walk_forward.py`)
    - Monte Carlo order shuffle & slippage battery (`brain/backtest/robustness.py`)
  - Audits: `docs/LOOKAHEAD_BIAS_AUDIT.md`, `docs/STRATEGY_PARAMETERS.md`, `docs/STRATEGY_VALIDATION_REPORT.md`, `adr/ADR-STRATEGY-001.md`.

## Test status — 2026-09-07

Backend (pytest): 313 passed, 0 failed (17 new end-to-end integration tests in tests/test_trading_pipeline.py)
Frontend (Jest): 42 passed, 0 failed
Type checking: mypy clean (75 files in backend/ and brain/), TypeScript clean
Frontend build: Next.js 23 static pages generated cleanly
Linting: ruff clean
Total tests: 355 passed

## Full Pipeline Integration (Stage D) — 2026-09-07

- **STAGE D (Brain → Risk → Execution → Reconciliation Integration): COMPLETE**
  - Canonical orchestrator: `backend/services/trading_pipeline.py` (`TradingPipeline`).
  - End-to-end integration flow verified:
    `MultiTimeframeBarManager` (M5/M15/H1 bar aggregation)
    → `SignalPipeline` (`CandidateSignal` proposal)
    → `DbCandidateSignal` persistence (`candidate_signals` table)
    → `evaluate_and_record_risk` (`RiskEngine` fail-closed authority)
    → `RiskDecision` persistence (`risk_decisions` table)
    → `ExecutionService.execute_approved_signal` (unique idempotency check)
    → `MT5AgentSimulator` (`ExecutionReport` with `is_simulated=True`)
    → `DbPosition` persistence (`positions` table)
    → `ReconciliationEngine` (compares DB vs simulator positions)
    → Reconciliation circuit breaker (`freeze_account` on critical discrepancies)
    → WebSocket event broadcast chain (`SIGNAL_CREATED`, `RISK_STATE_CHANGED`, `COMMAND_CREATED`, `COMMAND_UPDATED`, `POSITION_UPDATED`, `SYSTEM_ALERT`)
    → Immutable audit logs (`SIGNAL_CREATED`, `RISK_EVALUATED`, `COMMAND_DISPATCHED`, `RECONCILIATION_OK`/`MISMATCH`).
  - Simulator enhancements (`backend/execution/simulator.py`): in-memory position tracking, `get_open_positions()`, `MODE = "SIMULATION"`.
  - Idempotency deduplication: `ExecutionService` and `TradingPipeline` enforce unique `idempotency_key`, preventing duplicate broker orders.
  - Fail-safe gating: market stale, market warming, wide spread, unconfigured strategy, news blackout, risk NOT_CONFIGURED/BLOCKED/EMERGENCY, expired signal, duplicate key, reconciliation discrepancies all tested with 0 broker actions.
  - Documentation: `docs/TRADING_PIPELINE_INTEGRATION.md` created.
  - Test suite: `tests/test_trading_pipeline.py` (17 tests, all pass).

## Multi-Timeframe Market Data & Frontend Auth — 2026-09-06

- **STAGE C (Multi-Timeframe Market Data Manager): COMPLETE**
  - `brain/market_data/multi_timeframe.py`: `MultiTimeframeBarManager` provides explicit separation of M5, M15, and H1 bar streams.
  - Causal ingestion: ticks update all timeframes in non-decreasing chronological order.
  - Closed-bar-only: bars marked closed strictly when subsequent interval arrives.
  - Tick validation: symbol matching, non-positive price rejection, crossed-spread rejection, out-of-order rejection.
  - Staleness and spread tracking against configurable thresholds.
  - 22 automated tests in `tests/test_multi_timeframe.py` pass.

- **STAGE K (Frontend Authentication UX): COMPLETE**
  - `frontend/lib/auth-context.tsx`: `AuthProvider` with `useAuth` hook, session-scoped token management, transparent auth state.
  - `frontend/app/login/page.tsx`: Trader authentication with AUREXIS visual identity, error feedback, redirect on success.
  - `frontend/app/register/page.tsx`: Identity creation for operators.
  - `frontend/components/layout/AppShell.tsx`: Authenticated route gating; redirects unauthenticated operators to /login.
  - `frontend/components/layout/GlobalHeader.tsx`: Operator identity display and graceful session exit (logout).
  - Next.js production build: 23 static pages generated.
  - Jest suite: 42/42 tests pass.

## Database Migration & Schema Status — 2026-09-06

- **TASK-N01 (Alembic Migration 003 & ORM Alignment): COMPLETE**
  - `migrations/versions/003_trading_domain.py` finalized covering all 9 trading-domain tables:
    `risk_configurations`, `risk_decisions`, `candidate_signals`, `execution_commands`, `execution_reports`, `positions`, `equity_snapshots`, `daily_session_states`, `news_events`.
  - Mismatch audit resolved:
    - `execution_reports`: `fill_volume_lots` (canonical per spec) and `executed_at` aligned between ORM and migration; `idempotency_key` and `raw_broker_response_json` added for service compatibility.
    - `daily_session_states`: `profit_lock_floor_usd` added to migration 003 matching ORM model `DailySessionState` and risk engine.
  - All 14 tables verified in `Base.metadata`.
  - Precision: `NUMERIC(18, 8)` enforced across all monetary columns.
  - Timezone: `DateTime(timezone=True)` enforced across all timestamp columns.
  - Primary keys: UUIDv4 across all 14 tables.
  - Foreign key cascades and `SET NULL` policies verified.
  - Python AST validation confirms migrations 001, 002, 003 parse without errors.
  - 7 automated schema integrity tests pass in `tests/test_database_schema.py`.

## Local Integration Phase (Frontend Hooks & WebSocket Realtime) — 2026-09-07

- **Frontend Hook Migration: COMPLETE**
  - All 13 typed API hooks created in `frontend/lib/hooks/`.
  - All 23 pages migrated from mock data to real backend hooks.
  - Fail-closed loading/error semantics enforced across all pages.
  - Only remaining mock component: MarketPage OHLCV candlestick chart (backend OHLCV endpoint not yet implemented).
  - Jest: 65/65 tests pass.
  - ESLint: clean.
  - Next.js build: 23 static pages compile cleanly.
  - TypeScript: clean.

- **WebSocket Real Integration: COMPLETE**
  - Replaced optimistic 200ms connection timer with real WebSocket lifecycle states: `CONNECTING`, `CONNECTED`, `DISCONNECTED`, `ERROR`.
  - Extended `AurexisWebSocket` in `frontend/lib/websocket.ts` with `setStateCallback()`.
  - Connection strictly gated: only connects when `token` AND `selectedAccountId` are non-null.
  - Disconnects cleanly on logout, account switch, or provider unmount.
  - Real-time invalidation wired:
    - `SignalsPage` subscribes to `SIGNAL_CREATED` → refetches signals.
    - `PositionsPage` subscribes to `POSITION_UPDATED` → refetches positions.
    - `ExecutionPage` subscribes to `COMMAND_CREATED`, `COMMAND_UPDATED` → refetches commands.
  - Cross-user subscription blocked at backend (close 4002).

- **Infrastructure Verification:**
  - Docker Desktop is NOT installed on the host environment.
  - PostgreSQL runtime: NOT VERIFIED (Docker unavailable).
  - Redis runtime: NOT VERIFIED (Docker unavailable).
  - Offline model & migration consistency verified: all 14 ORM tables match migrations 001, 002, 003.
  - 7 schema integrity tests in `tests/test_database_schema.py` pass.

- **Acceptance & Regression:**
  - 313/313 backend pytest tests pass.
  - mypy: clean (75 source files).
  - ruff: clean.
  - End-to-end acceptance pipeline test: `tests/test_local_acceptance_pipeline.py` PASSES (covers full causal chain).

## Phase 12 — Railway Deployment Readiness — 2026-09-07

- **Repository Audit:** Complete. All Railway blockers addressed.

- **Backend Railway Changes:**
  - `backend/core/config.py`: Added `PORT` field (Railway dynamic port), `CORS_ORIGINS` field (production comma-separated origins), `effective_port` property, `async_database_url` property (normalizes `postgresql://`/`postgres://` → `postgresql+asyncpg://`), `allowed_cors_origins` property.
  - `backend/db/session.py`: Engine now uses `settings.async_database_url` (accepts Railway-provided URLs without `+asyncpg` prefix).
  - `backend/main.py`: CORS now uses `settings.allowed_cors_origins` (env-configurable for production).
  - `migrations/env.py`: Added `postgres://` → `postgresql://` normalization for Railway-provided `DATABASE_URL`.

- **Frontend Railway Changes:**
  - `frontend/lib/api.ts`: Added `NEXT_PUBLIC_API_BASE_URL` fallback before `NEXT_PUBLIC_API_URL`.
  - `frontend/lib/websocket.ts`: Added `getWsBaseUrl()` helper — auto-converts `https://`→`wss://`, derives from `NEXT_PUBLIC_API_BASE_URL`, falls back to `window.location`, then local default.
  - `frontend/next.config.js`: Exposes `NEXT_PUBLIC_API_BASE_URL` in env block.

- **Deployment Configuration Created:**
  - `Dockerfile` — production backend image (python:3.12-slim, non-root UID 10001, alembic + uvicorn CMD).
  - `railway.json` — backend Railway config (Dockerfile builder, health check `/api/v1/health/live`, ON_FAILURE restart).
  - `frontend/railway.json` — frontend Railway config (Nixpacks builder, `npm start`).

- **Documentation Created:**
  - `docs/RAILWAY_DEPLOYMENT.md` — full Railway architecture, env vars, migration procedure, WebSocket URL behavior, health probes, secrets, rollback, local vs Railway matrix.

- **Tests:** 326/326 pytest pass (13 new Railway readiness tests added to `tests/test_config.py`).
- **Type-check:** mypy clean (75 files).
- **Lint:** ruff clean.
- **Frontend:** 65/65 Jest pass, ESLint clean, Next.js 23 pages build clean.

- **Live Trading:** DISABLED. No change to any trading invariant.



- **Docker CLI Availability:**
  - Docker CLI: NOT AVAILABLE on host machine (`CommandNotFoundException`).
  - No containers running or started.

- **PostgreSQL 16 Status:**
  - Runtime: NOT VERIFIED — Docker unavailable on host.
  - Schema: STATICALLY VERIFIED — 14 ORM tables in `Base.metadata` match migrations `001_initial.py`, `002_refresh_tokens.py`, `003_trading_domain.py`.
  - Schema integrity: 7 automated tests in `tests/test_database_schema.py` PASS.

- **Redis 7 Status:**
  - Runtime: NOT VERIFIED — Docker unavailable on host.
  - Configuration: STATICALLY VERIFIED — `infrastructure/docker-compose.yml` uses `redis:7-alpine`, maxmemory 256mb, LRU eviction.

- **Alembic Status:**
  - Target head: `003_trading_domain`.
  - Offline AST validation: clean.
  - Migration run against PostgreSQL: NOT RUN — requires live PostgreSQL service.

- **Acceptance & Regression (in-memory SQLite):**
  - Backend: 313 passed (pytest).
  - Type-check: mypy clean (75 source files).
  - Lint: ruff clean.
  - Frontend: 65 passed (Jest, `--runInBand`).
  - Frontend lint: ESLint clean.
  - Next.js build: 23 static pages compiled cleanly.

- **Git Backup:**
  - Remote: `origin` → `https://github.com/bangoyan25/AUREXIS.git`
  - Branch: `main`

## Live Trading Status

AUREXIS LIVE TRADING STATUS: DISABLED
live_trading_enabled = false is strictly enforced across all configurations, database records, and API responses.


## Undefined decisions (blocking trading)

1. Empirical daily loss limit / drawdown monetary thresholds
2. Empirical indicator periods, thresholds, entry/exit parameters
3. Live news API provider credentials
4. Live broker credentials and bridge deployment

Risk Engine and Brain report NOT_CONFIGURED by default for undefined production values. No invented trading parameters.

## Local startup

```
Terminal 1: cd infrastructure && docker compose up -d
Terminal 2: alembic upgrade head
Terminal 3: .venv\Scripts\uvicorn backend.main:app --reload --port 8000
Terminal 4: cd frontend && npm run dev
```

## Status: NOT READY FOR LIVE TRADING
Live trading strictly disabled (`trading_enabled = False`, `NOT_CONFIGURED` fail-closed).

