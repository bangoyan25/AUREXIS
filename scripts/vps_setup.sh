#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# AUREXIS VPS Setup Script
# Ubuntu 22.04 / 24.04 — Python 3.12 virtual environment
#
# Usage:
#   cd ~/AUREXIS
#   chmod +x scripts/vps_setup.sh
#   bash scripts/vps_setup.sh
#
# What this does:
#   1. Verifies Python 3.12+ is available.
#   2. Creates ~/AUREXIS/.venv if absent.
#   3. Upgrades pip, setuptools, wheel inside venv.
#   4. Installs all production + dev dependencies via:
#        pip install -e ".[dev]"
#   5. Verifies critical imports (dotenv, alembic, sqlalchemy, asyncpg, etc.)
#   6. Prints a clear summary.
#
# After this script succeeds:
#   1. Copy .env.example to .env and fill real values.
#   2. Run:  source .venv/bin/activate
#   3. Run:  alembic current
#   4. Run:  alembic upgrade head   (only after DATABASE_URL is configured)
#
# LIVE TRADING REMAINS DISABLED.
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
PYTHON_MIN_MINOR=12   # require 3.12+

echo "══════════════════════════════════════════════"
echo "  AUREXIS VPS Setup"
echo "  Repo: $REPO_DIR"
echo "══════════════════════════════════════════════"

cd "$REPO_DIR"

# ── Step 1: Find usable Python 3.12+ ──────────────────────────────────────────
find_python() {
    for candidate in python3.12 python3.13 python3 python; do
        if command -v "$candidate" &>/dev/null; then
            local ver
            ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            local major="${ver%%.*}"
            local minor="${ver##*.}"
            if [[ "$major" -ge 3 && "$minor" -ge "$PYTHON_MIN_MINOR" ]]; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_BIN=$(find_python) || {
    echo ""
    echo "ERROR: Python 3.$PYTHON_MIN_MINOR+ not found."
    echo "Install with:"
    echo "  sudo apt update && sudo apt install -y python3.12 python3.12-venv python3.12-dev"
    exit 1
}

PYTHON_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
echo "Python found: $PYTHON_BIN ($PYTHON_VERSION)"

# ── Step 2: Create venv ────────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating venv at $VENV_DIR ..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    echo "Venv created."
else
    echo "Venv exists at $VENV_DIR — reusing."
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"
VENV_ALEMBIC="$VENV_DIR/bin/alembic"

# ── Step 3: Upgrade pip / setuptools / wheel ───────────────────────────────────
echo ""
echo "Upgrading pip, setuptools, wheel ..."
"$VENV_PYTHON" -m pip install --quiet --upgrade pip setuptools wheel

# ── Step 4: Install all dependencies ──────────────────────────────────────────
echo ""
echo "Installing AUREXIS dependencies: pip install -e '.[dev]' ..."
"$VENV_PIP" install --quiet -e ".[dev]"
echo "Dependencies installed."

# ── Step 5: Verify critical imports ───────────────────────────────────────────
echo ""
echo "Verifying imports ..."

check_import() {
    local module="$1"
    if "$VENV_PYTHON" -c "import $module" 2>/dev/null; then
        echo "  [OK]  $module"
    else
        echo "  [FAIL] $module — import failed"
        IMPORT_FAILURES=1
    fi
}

IMPORT_FAILURES=0
check_import dotenv
check_import alembic
check_import sqlalchemy
check_import asyncpg
check_import psycopg2
check_import redis
check_import fastapi
check_import uvicorn
check_import pydantic
check_import email_validator
check_import structlog
check_import jose
check_import passlib
check_import httpx

if [[ "$IMPORT_FAILURES" -ne 0 ]]; then
    echo ""
    echo "ERROR: One or more imports failed. Check pip output above."
    exit 1
fi

# ── Step 6: Verify alembic executable ─────────────────────────────────────────
echo ""
echo "Alembic: $("$VENV_ALEMBIC" --version)"

# ── Step 7: Print summary ──────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  SETUP COMPLETE"
echo "══════════════════════════════════════════════"
echo "  Python exe:    $VENV_PYTHON"
echo "  Alembic exe:   $VENV_ALEMBIC"
echo "  Venv:          $VENV_DIR"
echo ""
echo "  Next steps:"
echo "    1. cp .env.example .env"
echo "    2. nano .env    # fill DATABASE_URL, REDIS_URL, JWT_SECRET, ENCRYPTION_KEY, MT5_AGENT_SECRET_KEY"
echo "    3. source .venv/bin/activate"
echo "    4. alembic current              # check migration state"
echo "    5. alembic upgrade head         # run only after DATABASE_URL is set and DB is reachable"
echo "    6. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1"
echo ""
echo "  AUREXIS LIVE TRADING STATUS: DISABLED"
echo "══════════════════════════════════════════════"
