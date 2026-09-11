"""Password reset service for AUREXIS.

Secure token generation, hashing, and one-time verification.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select

from backend.core.logging import get_logger
from backend.db.models.password_reset import PasswordResetToken
from backend.db.models.user import User
from backend.services.auth import hash_password, revoke_all_user_refresh_tokens

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("services.password_reset")

RESET_TOKEN_EXPIRY_MINUTES = 60


def _hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def create_password_reset_token(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> str:
    """Create secure single-use reset token and store hash."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)

    record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(record)
    await db.flush()
    logger.info("password_reset.token_created", user_id=str(user_id))
    return raw_token


async def verify_and_consume_token(
    db: AsyncSession,
    raw_token: str,
) -> uuid.UUID:
    """Verify reset token, mark used atomically, return user_id."""
    token_hash = _hash_token(raw_token.strip())
    now = datetime.now(UTC)

    query = (
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
        .with_for_update()
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_OR_EXPIRED_TOKEN", "message": "Invalid or expired password reset token"},
        )

    exp = record.expires_at if record.expires_at.tzinfo is not None else record.expires_at.replace(tzinfo=UTC)
    if exp < now:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_OR_EXPIRED_TOKEN", "message": "Invalid or expired password reset token"},
        )

    record.used_at = now
    await db.flush()
    return record.user_id


async def apply_password_reset(
    db: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
) -> uuid.UUID:
    """Validate token, update password hash, revoke active sessions."""
    user_id = await verify_and_consume_token(db, raw_token)

    query = select(User).where(User.id == user_id).with_for_update()
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found"})

    user.hashed_password = hash_password(new_password)
    # Revoke all active sessions
    await revoke_all_user_refresh_tokens(db, user_id)
    await db.flush()
    logger.info("password_reset.applied", user_id=str(user_id))
    return user_id
