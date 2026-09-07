# AUREXIS Backend — Production Dockerfile
#
# Purpose: Reliable, reproducible Railway/cloud deployment for the FastAPI backend.
# Why Dockerfile over Nixpacks: AUREXIS is a Python/Node monorepo; Nixpacks
# auto-detection at repo root would be ambiguous. Dockerfile gives deterministic
# build steps and non-root security hardening.
#
# Build context: repo root
# Required Railway Variables:
#   DATABASE_URL, REDIS_URL, JWT_SECRET, ENCRYPTION_KEY, MT5_AGENT_SECRET_KEY,
#   APP_ENV=production, CORS_ORIGINS=https://your-frontend.up.railway.app
# Railway injects PORT automatically — do NOT set PORT in Railway Variables.
#
# Local test:
#   docker build -t aurexis-backend .
#   docker run -e DATABASE_URL=... -e REDIS_URL=... -e JWT_SECRET=... \
#              -e APP_ENV=production -e PORT=8000 -p 8000:8000 aurexis-backend

FROM python:3.12-slim AS base

# System dependencies for psycopg2-binary and cryptography wheels
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        gcc \
        libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# Non-root user for security hardening
RUN useradd --uid 10001 --no-create-home --shell /sbin/nologin appuser

WORKDIR /app

# Install Python dependencies from pyproject.toml (production only — no dev extras)
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install --no-cache-dir .

# Copy application source
COPY backend/ ./backend/
COPY brain/ ./brain/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Ensure non-root ownership
RUN chown -R appuser:appuser /app

USER appuser

# Expose default development port (Railway overrides via $PORT at runtime)
EXPOSE 8000

# Start command:
# 1. Run Alembic migrations to head before launching the server.
#    If migrations fail, the container exits — Railway retries.
# 2. Bind to 0.0.0.0 so Railway routing can reach the process.
# 3. Use $PORT from Railway environment; fall back to 8000 locally.
CMD alembic upgrade head && \
    exec uvicorn backend.main:app \
         --host 0.0.0.0 \
         --port "${PORT:-8000}" \
         --workers 1 \
         --log-level info
