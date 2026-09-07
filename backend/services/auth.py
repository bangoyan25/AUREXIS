"""
Authentication service for AUREXIS.

JWT-based authentication with refresh tokens.
Passwords are hashed with bcrypt. No plaintext passwords stored or logged.

Refresh token revocation:
- Each refresh token contains a unique JTI (JWT ID).
- The JTI is stored in refresh_tokens table on issue.
- Logout and rotation revoke the JTI (set revoked_at).
- A token with revoked or missing JTI is rejected.
- Expired tokens are rejected by JWT decode before DB check.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update

from backend.core.config import settings
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("auth")

# ── Password hashing ──────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plaintext password. Never call with an empty string."""
    if not plain:
        raise ValueError("Cannot hash an empty password")
    return cast("str", pwd_context.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return cast("bool", pwd_context.verify(plain, hashed))


# ── JWT tokens ────────────────────────────────────────────────────────────

class TokenError(Exception):
    """Raised when a JWT token is invalid, expired, or tampered."""


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    secret = settings.require_jwt_secret()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": datetime.now(UTC),
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return cast("str", jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM))


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """
    Create a long-lived refresh token.

    Returns (token_str, jti, expires_at) so the caller can persist the JTI.
    The token itself is NOT stored — only the JTI is persisted.
    """
    secret = settings.require_jwt_secret()
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": datetime.now(UTC),
        "exp": expire,
        "jti": jti,
        "type": "refresh",
    }
    token_str = cast("str", jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM))
    return token_str, jti, expire


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token. Raises TokenError if invalid."""
    secret = settings.require_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise TokenError(f"Token validation failed: {exc}") from exc
    if payload.get("type") != "access":
        raise TokenError("Token is not an access token")
    return cast("dict[str, Any]", payload)


def decode_refresh_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT refresh token (signature + expiry only).

    Does NOT check revocation — caller must call is_refresh_jti_valid() after.
    """
    secret = settings.require_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise TokenError(f"Token validation failed: {exc}") from exc
    if payload.get("type") != "refresh":
        raise TokenError("Token is not a refresh token")
    return cast("dict[str, Any]", payload)


def get_subject_from_token(token: str) -> str:
    """Extract and return the subject (user ID) from a valid access token."""
    payload = decode_access_token(token)
    sub = payload.get("sub")
    if not sub:
        raise TokenError("Token missing subject claim")
    return str(sub)


# ── JTI persistence (refresh token revocation) ────────────────────────────

async def store_refresh_jti(
    db: AsyncSession,
    *,
    jti: str,
    user_id: uuid.UUID,
    expires_at: datetime,
) -> None:
    """
    Persist a new refresh token JTI.

    Called immediately after issuing a refresh token.
    The token itself is never stored — only the JTI identifier.
    """
    from backend.db.models.refresh_token import RefreshToken

    row = RefreshToken(
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(row)
    # Caller commits as part of their transaction.


async def is_refresh_jti_valid(
    db: AsyncSession,
    jti: str,
) -> bool:
    """
    Check that a JTI exists, is not revoked, and has not expired.

    Returns True only if the DB row exists with revoked_at IS NULL
    and expires_at > now.  A valid JWT signature alone is insufficient
    after revocation.
    """
    from backend.db.models.refresh_token import RefreshToken

    now = datetime.now(UTC)
    result = await db.execute(
        select(RefreshToken.jti).where(
            RefreshToken.jti == jti,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
    )
    return result.scalar_one_or_none() is not None


async def revoke_refresh_jti(
    db: AsyncSession,
    jti: str,
) -> bool:
    """
    Revoke a refresh token JTI by setting revoked_at.

    Returns True if a previously-active row was revoked, False if the JTI
    was not found or was already revoked (idempotent — not an error).
    """
    from backend.db.models.refresh_token import RefreshToken

    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.jti == jti,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
        .returning(RefreshToken.jti)
    )
    revoked = result.scalar_one_or_none()
    return revoked is not None


async def revoke_all_user_refresh_tokens(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """
    Revoke all active refresh tokens for a user.

    Used on password change or account compromise.
    Returns the count of tokens revoked.
    """
    from backend.db.models.refresh_token import RefreshToken

    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
        .returning(RefreshToken.jti)
    )
    return len(result.fetchall())

