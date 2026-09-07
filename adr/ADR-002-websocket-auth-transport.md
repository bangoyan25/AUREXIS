# ADR-002: WebSocket Authentication Transport (Query Parameter)

**Date:** 2026-09-06
**Status:** Accepted

## Context

WebSocket connections cannot carry custom HTTP headers during the initial handshake
in browser environments. `Authorization: Bearer` is not available at WS connect time.

## Decision

Pass JWT access token as URL query parameter (`?token=<jwt>`).
Token is NEVER logged. Validation happens before `manager.connect()`.
Account ownership confirmed via PostgreSQL query — DB is authoritative.
A non-owned account_id yields same rejection as a nonexistent one.

## Security controls

1. Token missing: close 4001 before accept.
2. Token invalid/expired: close 4002 before accept.
3. account_id missing: close 4003 before accept.
4. Account not owned by token user: close 4002 (PostgreSQL ownership query).
5. Token never in log output.
6. Connection never accepted until all checks pass.

## Consequences

- Production MUST use TLS (WSS).
- Token TTL 60 minutes: clients reconnect with new access token after expiry.
- Refresh via REST /auth/refresh only — no in-band WS refresh.
