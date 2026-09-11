# AUREXIS REST API Contracts

> **Status:** FINAL — Verified against router, schemas, and endpoints  
> **Base URL:** `/api/v1`  
> **Format:** JSON (`Content-Type: application/json`)  
> **Auth:** Bearer JWT in `Authorization: Bearer <access_token>` header  
> **Date:** 2026-09-06  

---

## 1. Global API Standards

### 1.1 Authentication & Header Requirements
- Protected endpoints require: `Authorization: Bearer <access_token>`.
- System / operational endpoints (`/health`, `/health/live`, `/health/ready`) do not require authentication.
- Request correlation: All requests accept optional `X-Correlation-ID` header. If absent, backend generates a UUIDv4 and returns it in response headers.

### 1.2 Error Envelope
All error responses follow the standard JSON envelope:
```json
{
  "detail": {
    "code": "ERROR_CODE_STRING",
    "message": "Human readable explanation"
  }
}
```
Standard error codes:
- `401 UNAUTHORIZED`: `NOT_AUTHENTICATED`, `TOKEN_EXPIRED`, `INVALID_TOKEN`, `REFRESH_TOKEN_REVOKED`
- `403 FORBIDDEN`: `PERMISSION_DENIED`, `ACCOUNT_NOT_OWNED`
- `404 NOT_FOUND`: `NOT_FOUND`
- `409 CONFLICT`: `EMAIL_TAKEN`, `TRADING_ENABLED`
- `422 UNPROCESSABLE_ENTITY`: `VALIDATION_ERROR`, `INVALID_FACTOR`
- `503 SERVICE_UNAVAILABLE`: `DATABASE_UNHEALTHY`, `REDIS_UNHEALTHY`

### 1.3 Monetary Representation
- All monetary and price fields in requests and responses use **stringified decimals** (e.g. `"100.00"`, `"0.01"`) to prevent IEEE 754 float precision loss on clients.

---

## 2. Implemented Endpoints

### 2.1 Health & Diagnostics

#### `GET /api/v1/health`
Operational state of all subsystem components. Never reports fake health.
- **Auth:** None
- **Response 200 OK:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "check_duration_ms": 4.2,
  "components": {
    "backend": {"status": "healthy"},
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "brain": {"status": "NOT_CONFIGURED", "note": "..."},
    "risk_engine": {"status": "NOT_CONFIGURED", "missing_parameters": ["daily_loss_limit", "..."]},
    "market_data": {"status": "NOT_CONFIGURED"},
    "news": {"status": "NOT_CONFIGURED"},
    "mt5": {"status": "NO_AGENTS", "connected_agents": 0}
  }
}
```

#### `GET /api/v1/health/live`
Process liveness check.
- **Response 200 OK:** `{"status": "alive"}`

#### `GET /api/v1/health/ready`
Database and Redis connectivity check.
- **Response 200 OK:** `{"status": "ready"}`
- **Response 503 Service Unavailable:** `{"status": "not_ready", ...}`

---

### 2.2 Authentication

#### `POST /api/v1/auth/register`
Create platform user account.
- **Body:**
```json
{
  "email": "trader@example.com",
  "password": "Password123!",
  "display_name": "Trader Name"
}
```
- **Response 201 Created:**
```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "email": "trader@example.com",
  "display_name": "Trader Name",
  "is_superuser": false,
  "created_at": "2026-09-06T10:00:00Z"
}
```

#### `POST /api/v1/auth/login`
Issue access + refresh token pair.
- **Body:**
```json
{
  "email": "trader@example.com",
  "password": "Password123!"
}
```
- **Response 200 OK:**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 900
}
```

#### `POST /api/v1/auth/refresh`
Rotate refresh token: revokes old JTI, issues new token pair.
- **Body:** `{"refresh_token": "eyJhbGciOi..."}`
- **Response 200 OK:** `TokenResponse`

#### `POST /api/v1/auth/logout`
Revoke refresh token JTI in database.
- **Body:** `{"refresh_token": "eyJhbGciOi..."}`
- **Response 204 No Content**

#### `GET /api/v1/auth/me`
Current operator profile.
- **Response 200 OK:** `MeResponse`

---

### 2.3 Account Management

#### `GET /api/v1/accounts`
List all trading accounts belonging to authenticated operator.
- **Response 200 OK:** Array of `AccountResponse`.

#### `POST /api/v1/accounts`
Create new trading account binding.
- **Body:**
```json
{
  "label": "Demo Cent Account 1",
  "broker": "Demo Broker",
  "mt5_account_number": "12345678",
  "mt5_server": "DemoBroker-Demo",
  "broker_currency": "USD",
  "is_cent_account": true,
  "cent_normalization_factor": "0.01"
}
```
- **Response 201 Created:** `AccountResponse`

#### `GET /api/v1/accounts/{account_id}`
Get single account by UUID. Rejects non-owned accounts with 404.

#### `PATCH /api/v1/accounts/{account_id}`
Update account label, server, or active status.

#### `DELETE /api/v1/accounts/{account_id}`
Deactivate account (`is_active = false`). Blocked if `trading_enabled = true`.

---

### 2.4 MT5 Agent Management

#### `GET /api/v1/agents`
List registered MT5 EA instances for user's accounts.

#### `GET /api/v1/agents/{agent_id}`
Single agent details and last known connection status.

---

### 2.5 Activity / Audit Trail

#### `GET /api/v1/activity?limit=50`
Paginated audit events scoped to authenticated user.


---

## 3. Domain Endpoints (Stubs / Contract Boundaries)

The following endpoints represent domain boundaries established by `backend/api/v1/stubs.py`. All return explicit `NOT_CONFIGURED` or `EMPTY` states without inventing trading parameters or fake data.

### 3.1 Risk Subsystem

#### `GET /api/v1/risk/{account_id}`
Returns current risk gatekeeper state and account-configured thresholds.
- **Response 200 OK:**
```json
{
  "account_id": "00000000-0000-0000-0000-000000000001",
  "risk_state": "NOT_CONFIGURED",
  "trading_allowed": false,
  "block_reason": "MISSING_PARAMETERS",
  "note": "Risk Engine parameters are UNDEFINED. Trading is blocked.",
  "parameters": {
    "daily_loss_limit_usd": null,
    "max_drawdown_usd": null,
    "max_open_positions": null,
    "risk_per_trade_pct": null,
    "profit_lock_formula": "PCT_RETRACE",
    "profit_lock_threshold_usd": "10.00",
    "profit_lock_floor_pct": "0.30",
    "drawdown_reference": "LIFETIME_HWM",
    "daily_reset_timezone": "UTC"
  }
}
```

### 3.2 Brain Intelligence Subsystem

#### `GET /api/v1/brain/{account_id}`
Returns market regime classification, market structure status, and active strategy state.
- **Response 200 OK:**
```json
{
  "account_id": "00000000-0000-0000-0000-000000000001",
  "brain_state": "NOT_CONFIGURED",
  "regime": "NOT_CONFIGURED",
  "structure": "NOT_CONFIGURED",
  "trend": "NOT_CONFIGURED",
  "confidence": null,
  "note": "Brain strategy parameters are UNDEFINED."
}
```

### 3.3 Market Data Subsystem

#### `GET /api/v1/market/tick`
Returns latest normalized tick for XAUUSD.
- **Response 200 OK:**
```json
{
  "symbol": "XAUUSD",
  "status": "NOT_CONFIGURED",
  "bid": null,
  "ask": null,
  "spread_pips": null,
  "note": "Market data provider is UNDEFINED. No live tick data available."
}
```

### 3.4 Signals Subsystem

#### `GET /api/v1/signals`
List active candidate signals generated by the Brain.
- **Response 200 OK:**
```json
{
  "status": "NOT_CONFIGURED",
  "signals": [],
  "note": "No signals generated — Brain is NOT_CONFIGURED."
}
```

### 3.5 Positions Subsystem

#### `GET /api/v1/positions`
List open broker positions for user's accounts.
- **Response 200 OK:**
```json
{
  "status": "EMPTY",
  "positions": [],
  "note": "No live positions. MT5 not connected."
}
```

### 3.6 Execution Subsystem

#### `GET /api/v1/execution`
List recent execution commands and their lifecycle states.
- **Response 200 OK:**
```json
{
  "status": "EMPTY",
  "commands": [],
  "note": "No execution commands. MT5 not connected and Brain NOT_CONFIGURED."
}
```

### 3.7 Economic News Subsystem

#### `GET /api/v1/news`
Current economic news calendar events and blackout protection window state.
- **Response 200 OK:**
```json
{
  "status": "UNKNOWN",
  "provider": null,
  "upcoming_events": [],
  "pre_event_window_minutes": 30,
  "post_event_window_minutes": 30,
  "note": "News provider is UNDEFINED. Fail-safe: UNKNOWN."
}
```

### 3.8 Performance & Analytics Subsystem

#### `GET /api/v1/performance`
Account performance metrics and historical trade analytics.
- **Response 200 OK:**
```json
{
  "status": "EMPTY",
  "total_trades": 0,
  "win_rate": null,
  "total_pnl_usd": "0.00",
  "daily_pnl": [],
  "note": "No trade history available."
}
```

### 3.9 Backtesting Subsystem

#### `GET /api/v1/backtest`
Status and historical simulation results.
- **Response 200 OK:**
```json
{
  "status": "NOT_CONFIGURED",
  "results": [],
  "note": "Backtest engine is NOT_CONFIGURED. Strategy parameters must be finalized before backtesting."
}
```


---

## 4. Realtime WebSocket Transport

### `GET /api/v1/ws`
Full-duplex WebSocket connection for client dashboard updates.
- **Protocol:** `ws://` or `wss://`
- **Authentication Handshake:**
  - Token transport via query parameter: `?token=<access_token>`
  - Optional account scoping: `&account_id=<account_uuid>`
- **Authorization & Ownership:**
  - Server validates JWT before `websocket.accept()`.
  - If `account_id` is supplied, server queries PostgreSQL to verify `trading_accounts.user_id == current_user.id`.
  - Mismatched or non-owned account closes immediately with `4002 FORBIDDEN`.
  - Invalid/expired token closes with `4001 UNAUTHORIZED`.
- **Message Format:** See `docs/WEBSOCKET_SPEC.md` for full event schemas.

---

## 5. Verification & Test Suite

All API contracts are tested under:
- `tests/test_auth_api.py` (Register, login, refresh rotation, revocation, logout)
- `tests/test_accounts_api.py` (CRUD, cent normalization, ownership isolation)
- `tests/test_stubs_api.py` (All domain stub responses match schema without fake data)
- `tests/test_health.py` (Health, liveness, readiness probes)

