# AUREXIS — Local development Makefile
# Targets are documented; run `make help` for a summary.

.DEFAULT_GOAL := help
SHELL := cmd.exe
PYTHON := python
PIP := pip
VENV := .venv
BACKEND_DIR := backend
BRAIN_DIR := brain
FRONTEND_DIR := frontend
INFRA_DIR := infrastructure

.PHONY: help setup setup-backend setup-frontend install install-dev lint type-check \
        test test-unit test-integration coverage \
        db-upgrade db-downgrade db-reset db-seed \
        dev-backend dev-frontend dev \
        docker-up docker-down docker-reset \
        clean

# ── Help ────────────────────────────────────────────────────────────────────
help:
	@echo.
	@echo  AUREXIS Development Commands
	@echo  ─────────────────────────────────────────────────────────
	@echo  Setup:
	@echo    make setup            Full first-time setup
	@echo    make setup-backend    Python venv + dependencies
	@echo    make setup-frontend   npm install in frontend/
	@echo.
	@echo  Code quality:
	@echo    make lint             Run ruff linter
	@echo    make type-check       Run mypy type checking
	@echo    make test             Run all tests
	@echo    make test-unit        Run unit tests only
	@echo    make coverage         Run tests with coverage report
	@echo.
	@echo  Database:
	@echo    make db-upgrade       Apply all pending Alembic migrations
	@echo    make db-downgrade     Rollback one migration
	@echo    make db-reset         Drop and recreate DB (dev only)
	@echo.
	@echo  Development:
	@echo    make dev-backend      Start FastAPI dev server
	@echo    make dev-frontend     Start Next.js dev server
	@echo.
	@echo  Infrastructure:
	@echo    make docker-up        Start PostgreSQL + Redis via Docker Compose
	@echo    make docker-down      Stop Docker Compose services
	@echo    make docker-reset     Stop, remove volumes, restart
	@echo.
	@echo  Cleanup:
	@echo    make clean            Remove build artifacts and caches
	@echo  ─────────────────────────────────────────────────────────

# ── Setup ───────────────────────────────────────────────────────────────────
setup: setup-backend setup-frontend
	@echo Setup complete. Copy .env.example to .env and fill in values.

setup-backend:
	$(PYTHON) -m venv $(VENV)
	$(VENV)\Scripts\pip install --upgrade pip
	$(VENV)\Scripts\pip install -e ".[dev]"
	@echo Backend environment ready.

setup-frontend:
	cd $(FRONTEND_DIR) && npm install
	@echo Frontend environment ready.

install:
	$(VENV)\Scripts\pip install -e .

install-dev:
	$(VENV)\Scripts\pip install -e ".[dev]"

# ── Code quality ─────────────────────────────────────────────────────────────
lint:
	$(VENV)\Scripts\ruff check $(BACKEND_DIR) $(BRAIN_DIR) tests

type-check:
	$(VENV)\Scripts\mypy $(BACKEND_DIR) $(BRAIN_DIR)

# ── Tests ────────────────────────────────────────────────────────────────────
test:
	$(VENV)\Scripts\pytest tests -v

test-unit:
	$(VENV)\Scripts\pytest tests -v -m unit

test-integration:
	$(VENV)\Scripts\pytest tests -v -m integration

coverage:
	$(VENV)\Scripts\pytest tests --cov --cov-report=term-missing --cov-report=html

# ── Database ─────────────────────────────────────────────────────────────────
db-upgrade:
	$(VENV)\Scripts\alembic upgrade head

db-downgrade:
	$(VENV)\Scripts\alembic downgrade -1

db-reset:
	@echo WARNING: This drops the development database.
	$(VENV)\Scripts\alembic downgrade base
	$(VENV)\Scripts\alembic upgrade head

# ── Development servers ───────────────────────────────────────────────────────
dev-backend:
	$(VENV)\Scripts\uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd $(FRONTEND_DIR) && npm run dev

# ── Infrastructure ────────────────────────────────────────────────────────────
docker-up:
	cd $(INFRA_DIR) && docker compose up -d

docker-down:
	cd $(INFRA_DIR) && docker compose down

docker-reset:
	cd $(INFRA_DIR) && docker compose down -v && docker compose up -d

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	if exist .pytest_cache rmdir /s /q .pytest_cache
	if exist .mypy_cache  rmdir /s /q .mypy_cache
	if exist htmlcov      rmdir /s /q htmlcov
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
	@echo Clean complete.
