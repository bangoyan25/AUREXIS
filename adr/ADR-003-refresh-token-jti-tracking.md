# ADR-003: Refresh Token JTI Tracking via PostgreSQL

**Date:** 2026-09-06
**Status:** Accepted
**Deciders:** Engineering

## Context

The Phase 2 auth implementation issued refresh tokens but did not persist JTIs, so revocation (logout, rotation) could not be enforced. A replayed refresh token would succeed until JWT expiry (30 days).

## Decision

Track refresh token JTIs in a new `refresh_tokens` table in PostgreSQL.

- Each row stores: `jti`, `user_id`, `expires_at`, `revoked_at` (NULL = active).
- On login: JTI stored.
- On refresh (rotation): old JTI set `revoked_at = now()`, new JTI stored.
- On logout: JTI from request body set `revoked_at = now()`.
- On any refresh attempt: JTI checked against DB before issuing new tokens.
- Expired tokens are rejected by JWT decode before DB check.
- Replayed revoked tokens are rejected at DB check with 401.
- The refresh token string itself is NEVER stored — only the JTI.

## Alternatives considered

**Redis JTI blocklist**: faster reads but adds Redis as a hard dependency for auth correctness. If Redis is unavailable, token revocation would fail open. PostgreSQL is already a hard dependency and provides stronger durability.

**Stateless JWT only**: would require short refresh token TTL (e.g., 1 hour) to limit replay window. Conflicts with the 30-day session requirement.

## Consequences

- `refresh_tokens` table added (migration 002).
- `backend/services/auth.py`: `create_refresh_token()` now returns `(token, jti, expires_at)` — callers must destructure and call `store_refresh_jti()`.
- `backend/api/v1/auth.py`: login, refresh, logout all updated.
- Future: a cleanup job to DELETE rows where `expires_at < now() AND revoked_at IS NOT NULL` may be added when row accumulation becomes a concern (not yet).
- Multiple sessions per user are supported (each login creates one row).
- Bulk revocation (`revoke_all_user_refresh_tokens`) available for security incidents.
