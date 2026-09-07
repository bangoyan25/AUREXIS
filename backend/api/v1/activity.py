"""
Activity / Audit log REST endpoints.

GET /api/v1/activity         — recent audit events for the current user

Audit log is immutable and append-only.
No DELETE or UPDATE operations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import get_current_user
from backend.db.models.audit_log import AuditLog
from backend.db.session import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["activity"])


class AuditEventResponse(BaseModel):
    id: str
    event_type: str
    severity: str
    account_id: str | None
    correlation_id: str | None
    occurred_at: datetime


@router.get("/activity", response_model=list[AuditEventResponse])
async def list_activity(
    user_id: Annotated[str, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventResponse]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == uuid.UUID(user_id))
        .order_by(AuditLog.occurred_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [
        AuditEventResponse(
            id=str(e.id),
            event_type=e.event_type,
            severity=e.severity,
            account_id=str(e.account_id) if e.account_id else None,
            correlation_id=e.correlation_id,
            occurred_at=e.occurred_at,
        )
        for e in events
    ]
