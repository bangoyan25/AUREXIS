# AUREXIS — Railway Deployment Specification & Guide

## 1. Target Architecture

```
Railway Project: aurexis
│
├── PostgreSQL Service (Railway Plugin)
│   ├── Authoritative database for all financial records
│   └── Injected variable: DATABASE_URL (postgresql://...)
│
├── Redis Service (Railway Plugin)
│   ├── Realtime pub/sub, event broadcasting, ephemeral cache
│   └── Injected variable: REDIS_URL (redis://...)
│
├── Backend Service (FastAPI / Uvicorn)
│   ├── Built via: Dockerfile (repo root)
│   ├── Migration: alembic upgrade head on every container start
│   ├── Listener: 0.0.0.0:${PORT} (Railway assigns PORT dynamically)
│   └── Public domain: https://<backend-service>.up.railway.app
│
└── Frontend Service (Next.js)
    ├── Root directory: frontend
    ├── Builder: Nixpacks (Node.js, npm run build -> npm start)
    └── Public domain: https://<frontend-service>.up.railway.app
```

---

## 2. Live Trading Safety Invariant

```
AUREXIS LIVE TRADING STATUS: DISABLED
```

- `trading_enabled = False` strictly enforced across all DB records, API responses, and configs.
- `MT5AgentSimulator.MODE = "SIMULATION"` — no real orders.
- No broker credentials connected on Railway.
- All undefined trading parameters remain `NOT_CONFIGURED`.
- Railway deployment is for: backend testing, frontend integration, database validation, WebSocket streaming, and simulation only.

---

## 3. Required Railway Services

### 3.1 PostgreSQL Service
- Provision: Railway Dashboard -> **+ New -> Database -> Add PostgreSQL**
- Railway injects: `DATABASE_URL` (`postgresql://postgres:<password>@<host>:<port>/railway`)
- AUREXIS converts `postgresql://` and legacy `postgres://` to `postgresql+asyncpg://` automatically in `settings.async_database_url`.
- Alembic uses psycopg2 sync driver, normalized in `migrations/env.py`.

### 3.2 Redis Service
- Provision: Railway Dashboard -> **+ New -> Database -> Add Redis**
- Railway injects: `REDIS_URL` (`redis://default:<password>@<host>:<port>`)
- Backend starts in degraded mode if Redis unreachable — fails safely.
- PostgreSQL remains sole authoritative store for all durable financial state.

### 3.3 Backend Service
- Provision: Railway Dashboard -> **+ New -> GitHub Repo -> Root Directory: `/`**
- Builder: Dockerfile (root-level `Dockerfile`, specified in `railway.json`)
- Start command (in `railway.json` and Dockerfile CMD):
  ```bash
  alembic upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --log-level info
  ```
- Health check: `GET /api/v1/health/live` (timeout 30s)
- Restart policy: ON_FAILURE, max 3 retries

### 3.4 Frontend Service
- Provision: Railway Dashboard -> **+ New -> GitHub Repo -> Root Directory: `frontend`**
- Builder: Nixpacks (Node.js 22 LTS)
- Build: `npm run build`
- Start: `npm start`
- Health check: `GET /`

---

## 4. Environment Variables

### Backend Service Variables (set in Railway Variables UI)

| Variable | Description | Example / Source |
|---|---|---|
| `APP_ENV` | Environment mode | `production` |
| `APP_VERSION` | Application version | `0.1.0` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `DATABASE_URL` | PostgreSQL connection | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | Redis connection | `${{Redis.REDIS_URL}}` |
| `JWT_SECRET` | JWT signing secret (32+ random bytes) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `60` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `30` |
| `ENCRYPTION_KEY` | Field encryption key | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MT5_AGENT_SECRET_KEY` | MT5 agent HMAC secret | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated) | `https://<frontend>.up.railway.app` |

**Do NOT set `PORT`**: Railway injects it dynamically.

### Frontend Service Variables (set in Railway Variables UI)

| Variable | Description | Example |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend HTTPS URL | `https://<backend>.up.railway.app` |
| `NEXT_PUBLIC_WS_URL` | Backend WSS URL | `wss://<backend>.up.railway.app` |

---

## 5. WebSocket URL Behavior (HTTPS -> WSS)

`getWsBaseUrl()` in `frontend/lib/websocket.ts` resolves the WebSocket base:

1. `NEXT_PUBLIC_WS_URL` if set (must be `wss://`).
2. `NEXT_PUBLIC_API_BASE_URL` with `https://` -> `wss://` conversion.
3. `NEXT_PUBLIC_API_URL` with `https://` -> `wss://` conversion.
4. Browser runtime: derived from `window.location.protocol` (`https:` -> `wss:`).
5. Static fallback: `ws://localhost:8000`.

Result: setting only `NEXT_PUBLIC_API_BASE_URL` is sufficient — WSS is derived automatically.

### WebSocket Security (unchanged from production spec)
- Token query parameter auth (`?token=...&account_id=...`)
- Validated before `accept()` — PostgreSQL ownership check
- Non-owned account -> close code `4002`
- Tokens never logged

---

## 6. Database Migrations

Migration chain:
```
001_initial -> 002_refresh_tokens -> 003_trading_domain (head)
```

- Runs automatically on container start: `alembic upgrade head`
- If migration fails, container exits (no traffic routed to un-migrated DB)
- Verify via one-off command: `alembic current` -> expect `003_trading_domain (head)`
- Rollback: `alembic downgrade -1` or `alembic downgrade base` (full `downgrade()` methods exist in all 3 migrations)

---

## 7. Health Probes

| Endpoint | Use | Response |
|---|---|---|
| `GET /api/v1/health/live` | Railway health check (liveness) | `{"status": "alive"}` — always 200 if process up |
| `GET /api/v1/health/ready` | Readiness (after deploy before traffic) | 200 if DB+Redis healthy, 503 if not |
| `GET /api/v1/health` | Full diagnostic report | All component statuses — no secrets exposed |

---

## 8. Secret Handling

- Zero secrets in this repository.
- `.gitignore` excludes all `.env*` except `.env.example` (placeholder values only).
- All secrets live in Railway service Variables only.
- All secret fields use Pydantic `SecretStr` — not serializable by default.
- Secrets are never logged or returned in API responses.

---

## 9. Rollback

- **Application**: Railway dashboard instant rollback to any prior deployment.
- **Database**: `alembic downgrade -1` (step) or `alembic downgrade base` (all).
- **Data backup**: Railway managed PostgreSQL — daily backups included.

---

## 10. Local vs. Railway Environment

| Dimension | Local | Railway |
|---|---|---|
| Database | SQLite (tests) / PostgreSQL via Docker | Railway PostgreSQL 16 plugin |
| Redis | Mock / Redis 7 via Docker | Railway Redis 7 plugin |
| Backend URL | `http://localhost:8000` | `https://<backend>.up.railway.app` |
| Frontend URL | `http://localhost:3000` | `https://<frontend>.up.railway.app` |
| WebSocket | `ws://` | `wss://` (auto-converted) |
| CORS | localhost:3000 (automatic) | Set via `CORS_ORIGINS` env var |
| Server Port | `8000` (fixed) | `$PORT` (Railway-assigned) |
| Live Trading | **DISABLED** | **DISABLED** |
| MT5 Mode | `SIMULATION` | `SIMULATION` |

