# AUREXIS WebSocket Event Contracts

> **Status:** FINAL — Synchronized with `backend/ws/events.py` and `frontend/types/domain.ts`  
> **Protocol:** RFC 6455 WebSocket (`ws://` / `wss://`)  
> **Path:** `/api/v1/ws`  
> **Date:** 2026-09-06  

---

## 1. Connection Lifecycle & Transport Security

### 1.1 Authentication Handshake
Clients connect to `/api/v1/ws` providing a JWT Bearer token and optional account scope via query parameters:
```
GET /api/v1/ws?token=<access_token>&account_id=<account_uuid>
```
The server validates:
1. JWT signature, expiration, and user identity.
2. If `account_id` is supplied: queries PostgreSQL to verify account ownership (`trading_accounts.user_id == current_user.id`).
3. Connection is accepted only after DB-level authorization succeeds.

### 1.2 Close Codes
- `4001 UNAUTHORIZED`: Missing, invalid, or expired JWT access token.
- `4002 FORBIDDEN`: Account does not exist or is not owned by the authenticated user.
- `1000 NORMAL_CLOSURE`: Graceful client disconnect.
- `1011 INTERNAL_ERROR`: Server unhandled exception during processing.

### 1.3 Authority Policy
- The WebSocket is a **downlink notification and synchronization channel only**.
- Browser clients CANNOT initiate trading commands or alter risk parameters over WebSocket.
- All state-changing operations require signed REST calls (`POST`, `PATCH`, `DELETE`).

---

## 2. Event Wire Envelope

Every event transmitted over the WebSocket conforms to the standard versioned envelope:

```json
{
  "event": "EVENT_TYPE_STRING",
  "version": 1,
  "timestamp": "2026-09-06T12:00:00.000Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "payload": {}
}
```

| Field | Type | Description |
|---|---|---|
| `event` | `string` | Canonical event type literal |
| `version` | `integer` | Envelope schema version (current: `1`) |
| `timestamp` | `string` (ISO 8601 UTC) | Server emission timestamp |
| `correlation_id` | `string` (UUIDv4) | Correlation ID tracing the operation |
| `account_id` | `string` (UUIDv4) \| `null` | Scoped trading account ID (if account-specific) |
| `payload` | `object` | Event-specific data dictionary |


---

## 3. Canonical Event Payloads

### 3.1 `RISK_STATE_CHANGED`
Emitted when an account's risk engine transitions state or blocks trading.
```json
{
  "event": "RISK_STATE_CHANGED",
  "version": 1,
  "timestamp": "2026-09-06T12:00:00.000Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "payload": {
    "state": "STOPPED",
    "trading_allowed": false,
    "block_reason": "DAILY_LOSS_LIMIT_REACHED"
  }
}
```

### 3.2 `ACCOUNT_UPDATED`
Emitted when account balance, equity, margin, or floating PnL changes.
```json
{
  "event": "ACCOUNT_UPDATED",
  "version": 1,
  "timestamp": "2026-09-06T12:00:00.000Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "payload": {
    "balance_usd": "100.00",
    "equity_usd": "104.50",
    "floating_pnl_usd": "4.50",
    "margin_usd": "15.00",
    "free_margin_usd": "89.50",
    "open_position_count": 1
  }
}
```

### 3.3 `POSITION_UPDATED`
Emitted when a broker position is opened, modified, or price changes.
```json
{
  "event": "POSITION_UPDATED",
  "version": 1,
  "timestamp": "2026-09-06T12:00:00.000Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "payload": {
    "broker_ticket": 89412051,
    "symbol": "XAUUSD",
    "side": "BUY",
    "lots": "0.01",
    "open_price": "2735.40",
    "current_price": "2738.10",
    "stop_loss": "2725.00",
    "take_profit": "2755.00",
    "unrealized_pnl_usd": "2.70",
    "status": "OPEN"
  }
}
```

### 3.4 `PNL_UPDATED`
Emitted upon trade closure or daily session calculation.
```json
{
  "event": "PNL_UPDATED",
  "version": 1,
  "timestamp": "2026-09-06T12:00:00.000Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "payload": {
    "session_date": "2026-09-06",
    "realized_pnl_usd": "12.50",
    "floating_pnl_usd": "1.20",
    "daily_net_usd": "13.70",
    "profit_lock_active": true,
    "protected_floor_usd": "3.75"
  }
}
```

### 3.5 `SIGNAL_CREATED`
Emitted when Brain produces a new candidate trade signal.
```json
{
  "event": "SIGNAL_CREATED",
  "version": 1,
  "timestamp": "2026-09-06T12:00:00.000Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "payload": {
    "signal_id": "00000000-0000-0000-0000-000000000003",
    "symbol": "XAUUSD",
    "direction": "BUY",
    "regime": "TREND_UP",
    "setup_type": "TREND_CONTINUATION",
    "confidence_score": "0.85",
    "expires_at": "2026-09-06T12:01:00.000Z"
  }
}
```

### 3.6 `COMMAND_CREATED` & `COMMAND_UPDATED`
Tracks execution command progression (`CREATED` $\to$ `SENT` $\to$ `ACKNOWLEDGED` $\to$ `FILLED`).
```json
{
  "event": "COMMAND_UPDATED",
  "version": 1,
  "timestamp": "2026-09-06T12:00:01.200Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "payload": {
    "command_id": "00000000-0000-0000-0000-000000000004",
    "status": "FILLED",
    "broker_ticket": 89412051,
    "fill_price": "2735.40",
    "fill_volume_lots": "0.01"
  }
}
```

### 3.7 `MT5_CONNECTED` & `MT5_DISCONNECTED`
Reports EA terminal connectivity changes.
```json
{
  "event": "MT5_CONNECTED",
  "version": 1,
  "timestamp": "2026-09-06T12:00:00.000Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "payload": {
    "agent_id": "00000000-0000-0000-0000-000000000005",
    "mt5_version": "Build 4150"
  }
}
```

### 3.8 `SYSTEM_ALERT`
Urgent platform announcements or fail-safe notifications.
```json
{
  "event": "SYSTEM_ALERT",
  "version": 1,
  "timestamp": "2026-09-06T12:00:00.000Z",
  "correlation_id": "00000000-0000-0000-0000-000000000001",
  "account_id": null,
  "payload": {
    "message": "Market data stale: tick age > 2000ms. New entries gated.",
    "severity": "WARNING"
  }
}
```

---

## 4. Verification & Testing

- `tests/test_websocket.py`: Validates connection authentication, database ownership gating (ADR-002), and event dispatching.
- `backend/ws/events.py`: Unit test coverage for event envelope constructors and schema validation.

