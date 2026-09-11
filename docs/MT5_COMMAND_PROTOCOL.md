# AUREXIS MT5 Command Protocol Specification

> **Status:** LOCKED — 2026-09-06
> **Authority:** `docs/MASTER_SPECIFICATION.md` v1.0, `docs/EXECUTION_ENGINE.md`, `docs/MT5_EA_SPEC.md`
> **Role:** Authoritative wire protocol between AUREXIS Execution Engine and MT5 Execution Agent (EA).
> **Mandatory Rule:** MT5 EA is an execution-only agent. No strategy intelligence in the EA.

---

## 1. Architecture Overview

```
Brain (CandidateSignal)
    ↓
Risk Engine (Approved RiskDecision)
    ↓
Execution Engine (Dispatches Command)
    ↓  [MT5 Command Protocol via authenticated WebSocket / REST]
MT5 Agent / EA (Terminal Execution)
    ↓
Broker Server (MT5 Broker)
```

The protocol guarantees:
1. **At-most-once execution:** Duplicate commands NEVER create duplicate orders.
2. **Deterministic idempotency:** Repeated receipt of `command_id` returns existing command state.
3. **Fail-closed execution:** Any validation failure, account mismatch, or timeout aborts execution.
4. **Bi-directional auditability:** Every request and response carries `command_id` and `correlation_id`.

---

## 2. Authentication & Session Protocol

### 2.1 Agent Identity Handshake
Each MT5 terminal hosts an EA instance configured with:
- `agent_id`: UUID of registered MT5Agent in PostgreSQL
- `agent_secret`: Pre-shared key (hashed via bcrypt in database)
- `account_id`: UUID of TradingAccount bound to this agent

On connection, EA transmits handshake:
```json
{
  "type": "HANDSHAKE",
  "agent_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "secret": "<agent_secret>",
  "terminal_build": 4150,
  "ea_version": "1.0.0",
  "timestamp": "2026-09-06T12:00:00.000Z"
}
```

Server validates:
1. `agent_id` exists and is `ACTIVE`.
2. `secret` matches stored bcrypt hash.
3. `account_id` matches `TradingAccount.id` foreign key.
4. Server responds with `HANDSHAKE_ACK` containing session token (JWT, valid 1 hour) or closes with `4001 UNAUTHORIZED`.

### 2.2 Heartbeat & Health Monitoring
- Heartbeat interval: `5000 ms` (5 seconds).
- Missed heartbeat threshold: `3 consecutive` (15 seconds) → server marks agent `OFFLINE`.
- While agent is `OFFLINE`: Risk Engine blocks new entries for this account.

Heartbeat payload:
```json
{
  "type": "HEARTBEAT",
  "agent_id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "sequence": 1042,
  "timestamp": "2026-09-06T12:00:05.000Z",
  "terminal_connected": true,
  "broker_ping_ms": 28
}
```

---

## 3. Command Lifecycle & States

```
[CREATED] → [SENT] → [ACKNOWLEDGED] → [EXECUTING] → [FILLED]
                                                 → [PARTIALLY_FILLED]
                                                 → [REJECTED]
                                                 → [EXPIRED]
                                                 → [RECONCILED]
```

| State | Description | Transition Trigger |
|---|---|---|
| `CREATED` | Stored in PostgreSQL with unique UUID | Execution Engine creates command from approved signal |
| `SENT` | Transmitted over wire to MT5 EA | Socket send success |
| `ACKNOWLEDGED` | EA confirmed receipt and syntax validity | EA sends `COMMAND_ACK` |
| `EXECUTING` | EA submitted order to broker API | `OrderSend()` invoked |
| `FILLED` | Broker returned DEAL ticket | EA sends `EXECUTION_REPORT` with `FILLED` |
| `PARTIALLY_FILLED` | Volume partially filled | EA sends `EXECUTION_REPORT` with remaining volume |
| `REJECTED` | Broker rejected or EA safety check failed | EA sends `EXECUTION_REPORT` with error code |
| `EXPIRED` | Time elapsed past `expires_at` | Server or EA drops expired command |
| `RECONCILED` | State matched with broker order history | Reconciliation service passes command |

---

## 4. Command Schemas

### 4.1 Order Entry Command (`ORDER_OPEN`)
Sent by Execution Engine to MT5 EA:
```json
{
  "command_id": "c1a2b3c4-0000-0000-0000-000000000001",
  "action": "ORDER_OPEN",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "signal_id": "s1a2b3c4-0000-0000-0000-000000000001",
  "correlation_id": "corr-uuid-12345",
  "symbol": "XAUUSD",
  "order_type": "BUY",
  "volume_lots": "0.01",
  "price": "2025.50",
  "slippage_points": 20,
  "stop_loss": "2015.00",
  "take_profit": "2045.00",
  "magic_number": 1001,
  "comment": "AUREXIS:s1a2b3c4",
  "expires_at": "2026-09-06T12:01:00.000Z",
  "idempotency_key": "c1a2b3c4-0000-0000-0000-000000000001",
  "created_at": "2026-09-06T12:00:30.000Z"
}
```

### 4.2 Order Close Command (`ORDER_CLOSE`)
Used by Profit-Lock, Daily Loss Stop, or Operator:
```json
{
  "command_id": "c2a2b3c4-0000-0000-0000-000000000002",
  "action": "ORDER_CLOSE",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "position_ticket": 84920194,
  "symbol": "XAUUSD",
  "volume_lots": "0.01",
  "slippage_points": 20,
  "reason": "PROFIT_LOCK_FLOOR_BREACHED",
  "expires_at": "2026-09-06T12:01:00.000Z",
  "idempotency_key": "c2a2b3c4-0000-0000-0000-000000000002",
  "created_at": "2026-09-06T12:00:30.000Z"
}
```

### 4.3 Basket Close Command (`BASKET_CLOSE`)
Closes all open positions for an account (Emergency Stop or Daily Loss Stop):
```json
{
  "command_id": "c3a2b3c4-0000-0000-0000-000000000003",
  "action": "BASKET_CLOSE",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "symbol": "XAUUSD",
  "reason": "EMERGENCY_STOP_ACTIVE",
  "expires_at": "2026-09-06T12:01:00.000Z",
  "idempotency_key": "c3a2b3c4-0000-0000-0000-000000000003",
  "created_at": "2026-09-06T12:00:30.000Z"
}
```

---

## 5. Execution Reporting Protocol

Upon broker execution or rejection, the EA transmits an `EXECUTION_REPORT`:
```json
{
  "type": "EXECUTION_REPORT",
  "command_id": "c1a2b3c4-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "correlation_id": "corr-uuid-12345",
  "status": "FILLED",
  "broker_ticket": 84920194,
  "fill_price": "2025.52",
  "fill_volume_lots": "0.01",
  "slippage_points": 2,
  "commission_usd": "0.07",
  "swap_usd": "0.00",
  "broker_deal_id": 9940182,
  "executed_at": "2026-09-06T12:00:31.120Z",
  "error_code": null,
  "error_message": null
}
```

If rejected:
```json
{
  "type": "EXECUTION_REPORT",
  "command_id": "c1a2b3c4-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "correlation_id": "corr-uuid-12345",
  "status": "REJECTED",
  "broker_ticket": null,
  "fill_price": null,
  "fill_volume_lots": "0.00",
  "slippage_points": null,
  "commission_usd": "0.00",
  "swap_usd": "0.00",
  "broker_deal_id": null,
  "executed_at": "2026-09-06T12:00:31.200Z",
  "error_code": 10016,
  "error_message": "TRADE_RETCODE_INVALID_STOPS"
}
```

---

## 6. Periodic State Reporting

Every 1000 ms, EA streams `ACCOUNT_SYNC` and `POSITION_SYNC`:

### 6.1 Account State Sync
```json
{
  "type": "ACCOUNT_SYNC",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "balance": "1000.00",
  "equity": "1015.50",
  "margin": "20.25",
  "free_margin": "995.25",
  "margin_level_pct": "5014.81",
  "unrealized_pnl": "15.50",
  "currency": "USD",
  "timestamp": "2026-09-06T12:00:32.000Z"
}
```

### 6.2 Open Positions Sync
```json
{
  "type": "POSITION_SYNC",
  "account_id": "00000000-0000-0000-0000-000000000002",
  "positions": [
    {
      "ticket": 84920194,
      "symbol": "XAUUSD",
      "side": "BUY",
      "lots": "0.01",
      "open_price": "2025.52",
      "current_price": "2027.02",
      "stop_loss": "2015.00",
      "take_profit": "2045.00",
      "profit_usd": "1.50",
      "swap_usd": "0.00",
      "magic_number": 1001,
      "open_time": "2026-09-06T12:00:31.120Z"
    }
  ],
  "timestamp": "2026-09-06T12:00:32.000Z"
}
```

---

## 7. State Reconciliation Engine

Every 5000 ms, backend runs two-way reconciliation:
1. **Orphan Position Check:** Position exists in MT5 but not in PostgreSQL → Flag `RECONCILIATION_MISMATCH_UNKNOWN_POSITION`.
2. **Missing Position Check:** Open position recorded in PostgreSQL is missing in MT5 → Query trade history for stop-out/close deal. If no deal found → Flag `RECONCILIATION_MISMATCH_MISSING_POSITION`.
3. **Volume Mismatch:** Volume in MT5 != Volume in PostgreSQL → Flag `VOLUME_MISMATCH`.
4. **SL/TP Mismatch:** SL/TP in MT5 != expected risk SL/TP → Command MT5 to update SL/TP immediately.

Any severe mismatch enters `RiskState.CAUTION` and blocks new trade entries until reconciled.

---

## 8. Fail-Safe Rules for EA

1. If communication with server is lost: DO NOT OPEN ANY TRADES.
2. If command has expired (`now > expires_at`): REJECT command with code `COMMAND_EXPIRED`.
3. If duplicate `command_id` is received: RETURN current state of that command, DO NOT EXECUTE.
4. If account context does not match EA login: REJECT with `ACCOUNT_MISMATCH`.
5. If symbol does not map cleanly to `XAUUSD`: REJECT with `INVALID_SYMBOL`.
