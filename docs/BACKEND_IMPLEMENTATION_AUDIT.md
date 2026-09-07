# AUREXIS Backend Implementation Audit

**Date:** 2026-09-06
**Phase:** Security Hardening complete

---

## 1. Completed tasks

### Phase 1 (TASK-101 to TASK-106)
Repo setup, Docker Compose, Alembic, Redis, FastAPI skeleton, Next.js baseline v1.

### TASK-201 — Database models ✓
User, TradingAccount, MT5Agent, AuditLog with FK/cascade/UTC timestamps.

### TASK-202 — Authentication ✓
JWT access+refresh (HS256), bcrypt passwords, `require_jwt_secret()` guard.

### TASK-203 — Account management API ✓
CRUD with DB-level ownership isolation. cent_normalization_factor as Decimal.

### TASK-204 — MT5 agent ✓
Read endpoints. PostgreSQL authoritative for last_known_status.

### TASK-205 — WebSocket infrastructure ✓
ConnectionManager, WsEvent schemas, /api/v1/ws with JWT + DB ownership auth.

### TASK-206 — Audit log ✓
record_audit_event(), AuditEventType constants, append-only. GET /api/v1/activity.

### Domain stubs ✓
All unimplemented domains return NOT_CONFIGURED/EMPTY/UNKNOWN. All require auth.

### TASK-702 — Security Hardening ✓ (2026-09-06)

#### Refresh token JTI revocation
- New model: `RefreshToken` (jti, user_id, expires_at, revoked_at).
- New migration: `002_refresh_tokens.py`.
- `create_refresh_token()` returns `(token, jti, expires_at)` — callers must store JTI.
- Login: stores JTI. Refresh: validates + rotates. Logout: revokes JTI.
- Replay → 401 `REFRESH_TOKEN_REVOKED`.
- `revoke_all_user_refresh_tokens()` for incident response.
- ADR: `adr/ADR-001-refresh-token-jti-tracking.md`.

#### WebSocket DB ownership
- `_resolve_and_authorize(db=AsyncSession)` queries `TradingAccount` for ownership.
- WS endpoint opens own session via injectable `_session_factory`.
- Non-owned or nonexistent account → close(4002), same as bad token (no leak).
- Token never logged.
- ADR: `adr/ADR-002-websocket-auth-transport.md`.

#### Audit additions
- `TOKEN_REFRESH` event on token rotation.
- `REFRESH_TOKEN_REVOKED` constant for future use.

---

## 2. Authorization model

| Resource | Auth mechanism | Ownership check |
|----------|---------------|-----------------|
| Accounts | JWT Bearer | TradingAccount.user_id == token.sub (SQL) |
| Agents | JWT Bearer | JOIN through TradingAccount.user_id |
| Activity | JWT Bearer | AuditLog.user_id == token.sub (SQL) |
| WebSocket | JWT query param | TradingAccount.user_id == token.sub (SQL, before accept()) |
| Domain stubs | JWT Bearer | N/A (NOT_CONFIGURED) |

Invariants: `UNKNOWN ≠ AUTHORIZED`, `USER A ≠ USER B`.
Client-supplied account_id is NEVER used as authorization — always DB-verified.

---

## 3. Refresh token lifecycle

```
LOGIN  → store JTI
REFRESH → validate JTI → revoke old → issue+store new (rotation)
LOGOUT → revoke JTI
REPLAY → is_refresh_jti_valid() = False → 401 REFRESH_TOKEN_REVOKED
```

Token string never stored. Only JTI (UUID).

---

## 4. Test results — 2026-09-06

Backend: ~198 tests — ALL PASS
Frontend: 42 tests — ALL PASS
Grand total: ~240

New test suites:
- test_auth_api.py: 19 tests (includes rotation, revocation, multi-session)
- test_websocket_auth.py: 19 tests (includes DB ownership, non-owner, reconnect)

---

## 5. Remaining blockers

1. TASK-004 blocks Phase 3 (MT5 connectivity)
2. TASK-002 blocks production risk configuration
3. TASK-003 blocks Brain + signal pipeline

Resolved in this phase:
- ~~WebSocket DB ownership scaffold~~ → DONE
- ~~Refresh token JTI not tracked~~ → DONE

---

## 6. NOT READY FOR LIVE TRADING

All trading parameters UNDEFINED. Risk Engine NOT_CONFIGURED.
Brain NOT_CONFIGURED. MT5 not connected. No orders will be sent.
