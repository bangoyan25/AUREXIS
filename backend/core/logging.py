"""
Structured logging configuration for AUREXIS.

Uses structlog for JSON-formatted, correlation-ID-aware logging.
All log levels route through the standard library logging system.

Renderer selection:
- Development / test: colored ConsoleRenderer (human-readable)
- Production: JSONRenderer (machine-parseable JSON lines)

Security: secrets, passwords, and JWTs must never be passed to any logger.
The logging layer does not enforce this — it is a coding discipline requirement.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO", *, force_json: bool = False) -> None:
    """
    Configure structlog + stdlib logging for AUREXIS.

    Call once at application startup.

    Args:
        log_level: Minimum log level string (DEBUG/INFO/WARNING/ERROR/CRITICAL).
        force_json: Override renderer to JSON regardless of APP_ENV.
                    Used by production startup and tests that verify JSON output.
    """
    from backend.core.config import settings

    use_json = force_json or settings.is_production

    # Map string level to int
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Shared processors for all environments
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    if use_json:
        # Production: machine-parseable JSON lines for log aggregators
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Development / test: colored, human-readable output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given component name."""
    from typing import cast
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))
