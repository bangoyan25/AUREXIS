# AUREXIS Task Board

## Phase 12 — Railway Deployment Readiness & Hardening

- [x] TASK-RW01: Repository audit & Railway architecture definition — **DONE 2026-09-07**
  - Backend/PostgreSQL/Redis/Frontend architecture defined.
  - Zero mock substitutions for real functionality; trading remains disabled.

- [x] TASK-RW02: Backend Railway compatibility hardening — **DONE 2026-09-07**
  - Dynamic `PORT` environment variable support added to `Settings`.
  - Database URL scheme normalizer (`async_database_url`) added: `postgresql://` and `postgres://` → `postgresql+asyncpg://`.
  - CORS origins made configurable via `CORS_ORIGINS` env var (`allowed_cors_origins`).
  - Migration environment (`migrations/env.py`) normalized for `postgres://` URLs.
  - 13 new unit tests in `tests/test_config.py` pass; 326/326 total backend pytest pass.

- [x] TASK-RW03: Frontend Railway URL & WebSocket compatibility — **DONE 2026-09-07**
  - `NEXT_PUBLIC_API_BASE_URL` alias support in `frontend/lib/api.ts` and `next.config.js`.
  - `getWsBaseUrl()` helper in `frontend/lib/websocket.ts` handles HTTPS → WSS conversion and auto-derivation.
  - 65/65 Jest tests pass; ESLint clean; Next.js 23 static pages compile cleanly.

- [x] TASK-RW04: Railway deployment configuration — **DONE 2026-09-07**
  - Root `Dockerfile` (Python 3.12-slim, non-root `appuser`, Alembic + Uvicorn entrypoint).
  - `railway.json` for backend service (Dockerfile builder, health check `/api/v1/health/live`).
  - `frontend/railway.json` for frontend service (Nixpacks builder, `npm start`).

- [x] TASK-RW05: Railway deployment documentation — **DONE 2026-09-07**
  - `docs/RAILWAY_DEPLOYMENT.md` created: architecture, required variables, migration procedure, WS URL behavior, health probes, secrets, rollback, local vs Railway matrix.
  - `.env.example` updated with `CORS_ORIGINS` and Railway frontend guidance.

- [x] TASK-RW06: Test verification & git backup — **DONE 2026-09-07**
  - Full test suite verified.
  - Committed and pushed to `origin/main`.

- [x] TASK-RW08: Fix Railway database URL resolution for Alembic — **DONE 2026-09-07**
  - Root cause: `migrations/env.py:get_database_url()` raised `RuntimeError: No database URL configured. Set ALEMBIC_DATABASE_URL in your .env file.` in Railway because:
    1. Railway injects `DATABASE_URL` as a real environment variable — not read by pydantic-settings into `os.environ`.
    2. Without `load_dotenv()`, local `.env` values never reached `os.environ` used by `get_database_url()`.
    3. Error message misled users to believe only `ALEMBIC_DATABASE_URL` was supported.
  - Fix: Rewrote `get_database_url()` with clean precedence:
    1. `ALEMBIC_DATABASE_URL` (explicit override).
    2. `DATABASE_URL` (Railway provides via `${{Postgres.DATABASE_URL}}` automatically).
    3. Lazy `load_dotenv(override=False)` for local `.env` fallback.
    4. `RuntimeError` with clear message if no URL is available.
  - Added safe configuration diagnostics to `migrations/env.py` logging whether `ALEMBIC_DATABASE_URL` / `DATABASE_URL` are configured and which source was selected, with ZERO credentials logged.
  - Kept separate driver handling: Alembic sync psycopg2 (`postgresql://`) vs SQLAlchemy async application engine (`settings.async_database_url` → `postgresql+asyncpg://`).
  - Model imports and `context.config` access in `migrations/env.py` guarded so file can be imported directly in unit tests (Alembic `context.config` only exists under Alembic CLI runner).
  - Regression tests: 17 tests in `tests/test_migrations_env.py` covering precedence, all normalization cases, error conditions, safe diagnostics, and async application URL integrity.
  - All gates: 343/343 pytest, mypy 75 files clean, ruff clean, 65/65 Jest, 23 Next.js pages clean.
  - No credentials committed. Migration 003 required before startup. Live trading DISABLED.

- [x] TASK-RW07: Stabilize Railway Python Docker build — **DONE 2026-09-07**
  - Root cause: `pyproject.toml` `build-backend = "setuptools.backends.legacy:build"` is an internal setuptools module path unavailable via PEP 517 bootstrap in Railway's Python 3.12 image → `BackendUnavailable: Cannot import 'setuptools.backends'`.
  - Root cause 2: Dockerfile `pip install --no-cache-dir ".[ " 2>/dev/null || pip install --no-cache-dir .` — malformed extras specifier, non-deterministic fallback chain silently masks errors.
  - Fix 1 (`pyproject.toml`): `requires = ["setuptools>=68", "wheel"]` + `build-backend = "setuptools.build_meta"` (stable PEP 517 entry point, compatible with all setuptools ≥40).
  - Fix 2 (`Dockerfile`): `python -m pip install --upgrade pip setuptools wheel && python -m pip install --no-cache-dir .` — deterministic, no fallback.
  - All gates pass: 326/326 pytest, mypy 75 files clean, ruff clean, 65/65 Jest, 23 Next.js pages clean.
  - Docker local verification: Docker CLI NOT AVAILABLE on host — Railway CI/CD builder required for final Docker verification.
  - Committed `fix: stabilize Railway Python build` and pushed to `origin/main`.

- [x] TASK-RW08: Include email-validator in production dependencies — **DONE 2026-09-07**
  - Root cause: `email-validator>=2.0` listed in `[project.optional-dependencies].dev`. Docker production container uses `pip install --no-cache-dir .` without `--extra dev`. Startup crashed on `from pydantic import EmailStr` in `backend/api/v1/auth.py` with `ImportError: email-validator is not installed, run pip install pydantic[email]`.
  - Fix: Moved `email-validator>=2.0` into `[project.dependencies]` in `pyproject.toml`.
  - Added regression test `tests/test_production_dependencies.py` verifying production dependency declaration, direct `email_validator` import and execution, and `EmailStr` Pydantic models.
  - All gates pass: 347/347 pytest, mypy clean (75 files), ruff clean, 65/65 Jest, Next.js build clean. Live trading strictly DISABLED.


## Phase 11 — Runtime Infrastructure Verification & Git Backup

- [x] TASK-R01: Docker CLI availability check — **DONE 2026-09-06**
  - Docker CLI: NOT AVAILABLE on host (`CommandNotFoundException`).
  - PostgreSQL 16 runtime: NOT VERIFIED — Docker unavailable.
  - Redis 7 runtime: NOT VERIFIED — Docker unavailable.
  - Alembic migration upgrade: NOT RUN — requires live PostgreSQL.

- [x] TASK-R02: Static infrastructure verification — **DONE 2026-09-06**
  - `infrastructure/docker-compose.yml`: PostgreSQL 16-alpine + Redis 7-alpine — STATICALLY VERIFIED.
  - `.env.example`: all required env vars present, no secrets, `JWT_SECRET` / `ENCRYPTION_KEY` blank placeholders — STATICALLY VERIFIED.
  - `migrations/versions/001_initial.py`, `002_refresh_tokens.py`, `003_trading_domain.py` — STATICALLY VERIFIED (Python AST clean).
  - 14 ORM models in `Base.metadata` match migrations 001, 002, 003 — STATICALLY VERIFIED.
  - 7 schema integrity tests (`tests/test_database_schema.py`) PASS.

- [x] TASK-R03: Backend smoke test (in-memory, no Docker) — **DONE 2026-09-06**
  - 313/313 pytest tests pass (SQLite in-memory, no live PostgreSQL required).
  - Includes: auth API, accounts API, health, WebSocket auth, stubs, trading pipeline, acceptance pipeline.
  - mypy: clean (75 source files).
  - ruff: clean.

- [x] TASK-R04: Frontend regression — **DONE 2026-09-06**
  - Jest: 65/65 pass (4 test suites, `--runInBand`).
  - ESLint: clean.
  - Next.js build: 23/23 static pages compile clean.

- [x] TASK-R05: Documentation infrastructure status matrix — **DONE 2026-09-06**
  - `docs/FRONTEND_BACKEND_INTEGRATION.md`: Infrastructure Verification Status Matrix added.
  - `docs/STATUS.md`: Phase 11 block added.
  - `ai/TASKS.md`: Phase 11 tasks added.

- [x] TASK-R06: Git backup to origin/main — **DONE 2026-09-06**
  - Secret scan: no `.env`, no credentials, no API keys staged.
  - `.gitignore` verified: `.env*` (except `.env.example`), `.venv/`, `__pycache__/`, `.next/`, `node_modules/` all excluded.
  - Committed and pushed to `https://github.com/bangoyan25/AUREXIS.git` branch `main`.


- [x] TASK-L01: 13 typed frontend API hooks — **DONE 2026-09-07**
  - `useHealth`, `useAccounts`, `useAgents`, `useActivity`, `useRisk`, `useBrain`, `useMarket`, `useSignals`, `usePositions`, `useExecution`, `useNews`, `usePerformance`, `useBacktest`.
  - All 23 pages migrated from mock data.
  - 65/65 Jest tests pass.

- [x] TASK-L02: AccountProvider context — **DONE 2026-09-07**
  - `frontend/lib/account-context.tsx`: auto-selects first account, preserves selection, clears on logout.

- [x] TASK-L03: WebSocketProvider context real lifecycle — **DONE 2026-09-07**
  - Replaced optimistic 200ms timer with actual `AurexisWebSocket.setStateCallback()`.
  - Accurate `CONNECTING`/`CONNECTED`/`DISCONNECTED`/`ERROR` lifecycle states.
  - Connection gated: only connects when auth + account selected.

- [x] TASK-L04: Real-time page subscriptions — **DONE 2026-09-07**
  - `SignalsPage`: subscribes `SIGNAL_CREATED` → refetch.
  - `PositionsPage`: subscribes `POSITION_UPDATED` → refetch.
  - `ExecutionPage`: subscribes `COMMAND_CREATED`, `COMMAND_UPDATED` → refetch.

- [x] TASK-L05: Infrastructure consistency verification — **DONE 2026-09-07**
  - Docker NOT available on host — runtime verification not possible.
  - Offline: docker-compose.yml, migrations, ORM models, .env.example verified consistent.
  - 313/313 backend pytest pass; schema integrity tests pass.

- [x] TASK-L06: Documentation update — **DONE 2026-09-07**
  - `docs/FRONTEND_BACKEND_INTEGRATION.md` created.
  - `docs/STATUS.md` updated.
  - `ai/TASKS.md` updated.

## Phase 0 — Documentation / architecture

- [x] TASK-001 Finalize and lock master specification — **DONE 2026-09-06**
- [x] TASK-002 Finalize risk formula and edge cases — **DONE 2026-09-06** (docs/RISK_ENGINE_SPECIFICATION.md LOCKED; all 18 owner decisions approved and implemented; RiskConfig updated with locked formulas; ProfitLockStatus + PCT_RETRACE engine live; 30 tests pass)
- [x] TASK-003 Finalize trading setup definitions — **DONE 2026-09-06** (docs/BRAIN_SPECIFICATION.md LOCKED; 6 evidence dimensions formalized; closed-bar rule locked; pipeline locked)
- [x] TASK-004 Finalize MT5 command protocol — **DONE 2026-09-06** (docs/MT5_COMMAND_PROTOCOL.md LOCKED; wire schemas, heartbeat, lifecycle, execution report, sync, reconciliation defined)
- [x] TASK-005 Finalize database schema — **DONE 2026-09-06** (`docs/DATABASE_SCHEMA.md` FINAL; IMPLEMENTED tables documented: `users`, `trading_accounts`, `mt5_agents`, `audit_logs`, `refresh_tokens` (verified against 001+002 migrations and ORM models); PLANNED tables documented: `risk_configurations`, `risk_decisions`, `candidate_signals`, `execution_commands`, `execution_reports`, `positions`, `equity_snapshots`, `daily_session_states`, `news_events` (migration 003 defined, ORM models pending); UNDEFINED items explicitly listed; NUMERIC(18,8) policy, UUID semantics, timestamp semantics, cascade behavior, immutability rules, ownership boundaries, Redis authority model all documented)
- [x] TASK-006 Finalize API contracts — **DONE 2026-09-06** (`docs/API_SPEC.md` FINAL; all implemented endpoints documented with request/response schemas, error codes, auth requirements; domain stubs documented with NOT_CONFIGURED/EMPTY contracts; WebSocket transport documented)
- [x] TASK-007 Finalize WebSocket event contracts — **DONE 2026-09-06** (`docs/WEBSOCKET_SPEC.md` FINAL; wire envelope, close codes 4001/4002, authority model, and all 11 canonical event schemas synchronized between backend/ws/events.py and frontend/types/domain.ts)

## Phase 1 — Foundation

- [x] TASK-101 Repository setup — **DONE 2026-09-06** (`pyproject.toml`, `Makefile`, `frontend/package.json`, `tsconfig.json`, `tailwind.config.js`, venv, linting config)
- [x] TASK-102 Docker development environment — **DONE 2026-09-06** (compose healthchecks, named volumes, postgres init, network)
- [x] TASK-103 PostgreSQL migrations — **DONE 2026-09-06** (Alembic scaffold, `migrations/env.py`, `script.py.mako`, `backend/db/base.py`, `backend/db/session.py`)
- [x] TASK-104 Redis configuration — **DONE 2026-09-06** (`backend/core/redis.py` — pools, health check, pub/sub client)
- [x] TASK-105 FastAPI skeleton — **DONE 2026-09-06** (`backend/main.py` app factory, `/api/v1/health`, `/health/live`, `/health/ready`, correlation IDs, structured logging)
- [x] TASK-106 Next.js skeleton — **DONE 2026-09-06** (`frontend/app/`, TypeScript strict, Tailwind, domain types, API client, WebSocket client, dashboard shell, status banner)

> TASK-101 through TASK-106 complete. 25/25 unit tests passing.
> None implement trading logic, risk formulas, or strategy parameters.

## Phase 2 — Core platform (database models, auth, accounts, API, realtime, audit)

- [x] TASK-201 Database models — **DONE 2026-09-06** (User, TradingAccount, MT5Agent, AuditLog with full FK/cascade/UTC timestamps)
- [x] TASK-202 Authentication — **DONE 2026-09-06** (JWT access+refresh tokens, bcrypt hashing, TokenError, require_jwt_secret)
- [x] TASK-203 Account management API — **DONE 2026-09-06** (CRUD, ownership isolation, cent normalization)
- [x] TASK-204 MT5 agent identity model — **DONE 2026-09-06** (MT5Agent model, hashed secret, connection state)
- [x] TASK-205 WebSocket infrastructure — **DONE 2026-09-06** (ConnectionManager, WsEvent schemas, /api/v1/ws endpoint, event constructors)
- [x] TASK-206 Audit log service — **DONE 2026-09-06** (AuditLog model, record_audit_event(), AuditEventType constants, Severity)

## Phase 3 — MT5 connectivity (models ready; protocol locked)

- [x] TASK-301 MT5 heartbeat and session management — **DONE 2026-09-06** (`backend/services/mt5_session.py` implemented; fail-closed connection check, heartbeat processing, timeout watchdog, DB-authoritative status)
- [x] TASK-302 Account-state reporting from MT5 — **DONE 2026-09-06** (`backend/execution/reports.py` `AccountStateReport` schema; USD normalization ready)
- [x] TASK-303 Position/order reporting from MT5 — **DONE 2026-09-06** (`backend/execution/reports.py` `PositionReport` and `ExecutionReport` schemas)
- [x] TASK-304 Command lifecycle scaffolding (idempotency, expiry) — **DONE 2026-09-06** (`backend/execution/commands.py` `ExecutionCommand` state machine: CREATED → SENT → ACKNOWLEDGED → EXECUTING → FILLED/PARTIALLY_FILLED/REJECTED/EXPIRED → RECONCILED; idempotency key, expiry enforcement)
- [x] TASK-305 Reconciliation engine skeleton — **DONE 2026-09-06** (`backend/execution/reconciliation.py` `ReconciliationEngine`; detects clean state, ORPHAN, PHANTOM, VOLUME_MISMATCH, SIDE_MISMATCH; 12 unit tests pass)


## Phase 4 — Risk Engine (LOCKED & IMPLEMENTED)

- [x] TASK-401 Risk state machine — **DONE 2026-09-06** (RiskState enum, SignalDecision, TRADING_ALLOWED_STATES)
- [x] TASK-402 Daily protection framework — **DONE 2026-09-06** (daily_loss_limit enforcement in RiskEngine)
- [x] TASK-403 Dynamic profit lock framework — **DONE 2026-09-06** (ProfitLockStatus + PCT_RETRACE formula, floating equity basis, monotonic floor)
- [x] TASK-404 Kill switches / emergency stop — **DONE 2026-09-06** (emergency_stop_active, EMERGENCY_STOP state)
- [x] TASK-405 Exposure controls — **DONE 2026-09-06** (max_open_positions, max_open_lots, max_drawdown_usd enforcement)
- [x] TASK-406 Position sizing policies — **DONE 2026-09-06** (`backend/risk/sizing.py` PercentageEquitySizingPolicy, FixedLotSizingPolicy; Decimal precision only)
- [x] TASK-407 Risk service persistence & audit — **DONE 2026-09-06** (`backend/services/risk_service.py` evaluates snapshot from DB, persists immutable RiskDecision, writes audit logs)

## Phase 5 — Brain / Market intelligence (LOCKED & IMPLEMENTED — TASK-003 COMPLETE)

- [x] TASK-501 Tick normalization and market data abstraction — **DONE 2026-09-06** (Tick, MarketDataStatus, DataSource, TickStatus, BarBuilder)
- [x] TASK-502 Market state model — **DONE 2026-09-06** (MarketDataStatus with is_fresh fail-safe)
- [x] TASK-503 Strategy interfaces — **DONE 2026-09-06** (MarketStructureAnalyzer, TrendAnalyzer, BreakoutAnalyzer, FakeoutAnalyzer, SignalScorer, StrategyEngine ABCs; NotConfiguredStrategyEngine)
- [x] TASK-504 Signal pipeline complete — **DONE 2026-09-06** (`brain/pipeline.py` SignalPipeline implemented; closed-bar rule enforced; fails-closed with direction=NONE when unconfigured; unit tests pass)
- [x] TASK-505 News protection interface — **DONE 2026-09-06** (`brain/news.py` NewsProtectionEngine with pre/post-event blackout windows; fail-closed behavior)
- [x] TASK-506 Regime, structure, and scoring modules — **DONE 2026-09-06** (`brain/regime.py`, `brain/structure.py`, `brain/scoring.py` with multi-factor evidence tracking)
- [x] TASK-507 AUREXIS-STRAT-1.0.0 complete implementation — **DONE 2026-09-06**
  - Canonical config (`brain/config.py`, `default_strat_config`)
  - Structure engine: BOS with ATR displacement, CHoCH, equal-level tolerance
  - Regime engine: 6 states, ADX, normalized ATR baseline, hysteresis
  - Momentum engine: RSI with exhaustion zones (overbought/oversold suppression)
  - Volatility engine: normalized ATR ratio against rolling baseline
  - Setup engine: LONG_BREAKOUT, SHORT_BREAKOUT, LONG_FAKEOUT_REVERSAL, SHORT_FAKEOUT_REVERSAL, CONTINUATION
  - Weighted 6-dimension scoring: 25%+25%+20%+10%+10%+10%=100%, threshold 0.70
  - SL: structural invalidation + 0.50 ATR buffer
  - TP: entry ± risk × 2.0 R:R (min R:R 1.5)
  - Full pipeline: spread gate, staleness gate, news gate, regime gate, setup detection, scoring
  - All CandidateSignals carry strategy_version, evidence breakdown, correlation_id, setup_type

## Phase 6 — Backtest & Local Simulation (IMPLEMENTED — EXTENDED)

- [x] TASK-601 Backtest Engine — **DONE 2026-09-06** (`brain/backtest/engine.py` identical Brain + Risk pipeline replay, chronological ordering, no lookahead, slippage, commission, equity tracking)
- [x] TASK-601b Backtest Metrics Extension — **DONE 2026-09-06** (expectancy, profit_factor, consecutive_wins, consecutive_losses, largest_win, largest_loss, gross_profit, gross_loss)
- [x] TASK-602 MT5 Simulator — **DONE 2026-09-06** (`backend/services/mt5_simulator.py` deterministic mock broker execution, fills, ticket generation, reports, and positions)
- [x] TASK-603 End-to-end Local Acceptance Test — **DONE 2026-09-06** (`tests/test_local_acceptance.py` full lifecycle verified)
- [x] TASK-604 Sensitivity Analysis — **DONE 2026-09-06** (`brain/backtest/sensitivity.py` — parameter sweep framework)
- [x] TASK-605 Walk-Forward Validation — **DONE 2026-09-06** (`brain/backtest/walk_forward.py` — 70/15/15 train/val/oos split)
- [x] TASK-606 Robustness Testing — **DONE 2026-09-06** (`brain/backtest/robustness.py` — Monte Carlo order shuffle, slippage battery)


## Phase 7 — Integration and hardening

- [x] TASK-701 End-to-end local simulation verified — **DONE 2026-09-06**
- [x] TASK-702 Security hardening — **DONE 2026-09-06**
  - Refresh token JTI tracking + revocation (migration 002, refresh_tokens table)
  - WebSocket DB ownership verification (PostgreSQL-authoritative)
  - Authorization audit (all endpoints verified)
  - ADR-001 (JTI tracking), ADR-002 (WS auth transport)
- [x] TASK-703 Full test coverage pass — **DONE 2026-09-06** (238/238 backend pytest tests pass; 42/42 frontend Jest tests pass)
- [x] TASK-704 Documentation sync — **DONE 2026-09-06** (DATABASE_SCHEMA.md, API_SPEC.md, WEBSOCKET_SPEC.md, STATUS.md synchronized)

## Phase 9 — Market Data, Frontend Auth, Pipeline Integration

- [x] STAGE-C: Multi-Timeframe Bar Manager — **DONE 2026-09-06**
  - `brain/market_data/multi_timeframe.py`: `MultiTimeframeBarManager` — M5/M15/H1 independent builders.
  - Tick validation: symbol, price range, spread, chronological ordering (causal invariant enforced).
  - Staleness and spread tracking methods.
  - 22 tests in `tests/test_multi_timeframe.py` pass.

- [x] STAGE-K: Frontend Authentication UX — **DONE 2026-09-06**
  - `frontend/lib/auth-context.tsx`: `AuthProvider`, `useAuth()` hook, session-scoped token storage.
  - `frontend/app/login/page.tsx`: Login page; adheres to locked AUREXIS visual identity.
  - `frontend/app/register/page.tsx`: Registration page.
  - `frontend/components/layout/AppShell.tsx`: Auth-gated route; redirect to /login when unauthenticated.
  - `frontend/components/layout/GlobalHeader.tsx`: Operator identity display; logout (EXIT) button.
  - `lib/auth.ts` left intact (DEFERRED stub) — 42/42 Jest tests still pass including AUTH_STATUS=DEFERRED.

- [x] STAGE-D: Full Brain → Risk → Execution → Reconciliation Integration — **DONE 2026-09-07**
  - `backend/services/trading_pipeline.py`: `TradingPipeline` — canonical orchestrator.
  - Complete fail-closed gate chain: tick validation, market readiness, spread, staleness, circuit breaker, brain NONE, signal expiry, risk NOT_CONFIGURED/BLOCKED/EMERGENCY, idempotency deduplication.
  - Reconciliation circuit breaker: critical discrepancy (ORPHAN, VOLUME_MISMATCH, SIDE_MISMATCH) freezes account for new entries.
  - WS events: SIGNAL_CREATED, RISK_STATE_CHANGED, COMMAND_CREATED, COMMAND_UPDATED, POSITION_UPDATED, SYSTEM_ALERT.
  - Idempotency DB check: `execution_commands.idempotency_key` prevents duplicate broker actions.
  - `MT5AgentSimulator.MODE = "SIMULATION"` enforced; in-memory position state; `get_open_positions()`.
  - 17 integration tests in `tests/test_trading_pipeline.py` pass (happy path + negative matrix + invariants).
  - mypy clean (75 files); ruff clean; 313/313 backend pytest pass; 42/42 Jest pass; 23 Next.js pages.
  - Docs: `docs/TRADING_PIPELINE_INTEGRATION.md` created.



## Phase 8 — Database Finalization & ORM Audit

- [x] TASK-N01 Alembic migration 003 & ORM consistency audit — **DONE 2026-09-06**
  - Migration 003 covers all 9 trading-domain tables with correct types, nullable, constraints, FKs, indexes.
  - ORM ExecutionReport aligned: `fill_volume_lots`, `executed_at` (canonical names per spec); `idempotency_key`, `raw_broker_response_json` added for service compat; `reported_at` and `filled_lots` retained as Python property aliases.
  - `daily_session_states` migration updated: `profit_lock_floor_usd` added (was in ORM, missing from migration).
  - `backend/services/execution_service.py` updated to use `fill_volume_lots`, `executed_at`, `correlation_id`, `broker_deal_id`, `broker_error_code`, `broker_error_message`.
  - 7 schema integrity tests added: `tests/test_database_schema.py` (tables, UUID PKs, NUMERIC(18,8), timezone-aware timestamps, FK ondelete policies, migration AST validity, migration 003 critical columns).
  - 274/274 backend pytest pass; 42/42 Jest pass; mypy clean; ruff clean.



