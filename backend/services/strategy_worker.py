"""strategy_worker — background loop for server-side strategy execution.

Wakes every STRATEGY_WORKER_INTERVAL_SEC, queries all accounts with
`StrategyEngineState.enabled = True`, and triggers the strategy evaluation
cycle via `StrategyService.evaluate_and_execute`.

Safety properties:
  - Never bypasses RiskGate. Each evaluation calls the full risk check.
  - Kill-switch is enforced inside RiskGate via `emergency_stop_active`.
  - Does NOT run in test environment (`settings.is_test` or PYTEST_CURRENT_TEST).
  - Errors per account are caught, logged, and DO NOT crash the loop.
  - Graceful shutdown: cancels the asyncio task on app shutdown.
"""
from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import structlog

from backend.core.config import settings

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

_worker_task: asyncio.Task | None = None  # noqa: UP007


async def _run_loop() -> None:
    """Main worker loop — runs until cancelled."""
    logger.info("strategy_worker.started", interval=settings.STRATEGY_WORKER_INTERVAL_SEC)
    while True:
        await asyncio.sleep(settings.STRATEGY_WORKER_INTERVAL_SEC)
        await _tick()


async def _tick() -> None:
    """Single worker tick: evaluate strategy for all enabled accounts."""
    try:
        from sqlalchemy import select

        from backend.db.models.strategy import StrategyEngineState
        from backend.db.session import AsyncSessionLocal
        from backend.services.strategy_service import StrategyService

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(StrategyEngineState).where(StrategyEngineState.enabled.is_(True))
            )
            states = result.scalars().all()

        for state in states:
            try:
                async with AsyncSessionLocal() as session:
                    svc = StrategyService(session)
                    await svc.evaluate_and_execute(state.account_id)
            except Exception as exc:
                logger.warning(
                    "strategy_worker.account_error",
                    account_id=str(state.account_id),
                    error=str(exc),
                )

    except Exception as exc:
        logger.error("strategy_worker.tick_error", error=str(exc))


def start_worker() -> None:
    """Start the background worker task. Safe to call from lifespan startup.

    Does nothing in test environment.
    """
    global _worker_task  # noqa: PLW0603

    if settings.is_test or os.environ.get("PYTEST_CURRENT_TEST"):
        logger.debug("strategy_worker.skipped_in_test")
        return

    if not settings.STRATEGY_WORKER_ENABLED:
        logger.info("strategy_worker.disabled_by_config")
        return

    if _worker_task is not None and not _worker_task.done():
        logger.warning("strategy_worker.already_running")
        return

    _worker_task = asyncio.create_task(_run_loop(), name="strategy_worker")
    logger.info("strategy_worker.task_created")


def stop_worker() -> None:
    """Cancel the background worker task. Call from lifespan shutdown."""
    global _worker_task  # noqa: PLW0603

    if _worker_task is not None and not _worker_task.done():
        _worker_task.cancel()
        logger.info("strategy_worker.stopped")

    _worker_task = None
