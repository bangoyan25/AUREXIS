"""
AUREXIS FastAPI application factory.

Creates and configures the FastAPI app instance.
All routes, middleware, and lifecycle events are registered here.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import router as v1_router
from backend.core.config import settings
from backend.core.logging import configure_logging, get_logger
from backend.core.redis import close_redis_pools, get_cache_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Configure logging before anything else logs.
configure_logging(settings.LOG_LEVEL)
logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    Handles startup and shutdown cleanly.
    """
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info(
        "aurexis.starting",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )

    # Verify database connection on startup
    import os
    if not settings.is_test and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            from sqlalchemy import text

            from backend.db.session import engine
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("aurexis.database_connected")
        except Exception as exc:
            logger.warning(
                "aurexis.database_unavailable",
                error=str(exc),
                note="Backend will start but DB-dependent features will fail.",
            )

        # Verify Redis connection on startup
        try:
            client = get_cache_client()
            await client.ping()
            logger.info("aurexis.redis_connected")
        except Exception as exc:
            logger.warning(
                "aurexis.redis_unavailable",
                error=str(exc),
                note="Backend will start but cache/realtime features will fail.",
            )

    logger.info("aurexis.started")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("aurexis.shutting_down")
    await close_redis_pools()
    from backend.db.session import engine
    await engine.dispose()
    logger.info("aurexis.stopped")


def create_app() -> FastAPI:
    """Factory function that creates and configures the FastAPI application."""

    app = FastAPI(
        title="AUREXIS API",
        description=(
            "AUREXIS — Centralized trading intelligence and risk-management platform.\n\n"
            "**WARNING**: This system controls real financial operations. "
            "Undefined trading parameters are NOT_CONFIGURED — no live trading "
            "will occur until all required parameters are formally approved."
        ),
        version=settings.APP_VERSION,
        lifespan=lifespan,
        # Disable auto-generated docs in production
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    # Development: allow localhost origins.
    # Production: restrict to approved origins (configured via CORS_ORIGINS).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
    )

    # ── Request ID middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next: Any) -> Response:
        """Attach a correlation ID to each request for traceability."""
        import uuid

        import structlog

        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Correlation-ID"] = correlation_id

        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(v1_router)

    # Root redirect to health
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "product": "AUREXIS",
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


# Application instance used by uvicorn
app = create_app()
