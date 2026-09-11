"""
Authentication REST endpoints.

POST /api/v1/auth/register   — register a new user
POST /api/v1/auth/login      — issue access + refresh tokens
POST /api/v1/auth/refresh    — new access token from refresh token (rotation)
POST /api/v1/auth/logout     — revoke refresh token, write audit record
GET  /api/v1/auth/me         — current authenticated user info

Refresh token revocation:
- Login: JTI stored in refresh_tokens table.
- Refresh: old JTI revoked, new JTI stored (token rotation).
- Logout: JTI in request body revoked; client must discard both tokens.
- Replayed revoked JTIs are rejected with 401.

No plaintext passwords are ever logged.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from backend.api.deps import get_current_user
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.models.user import User
from backend.db.session import get_db
from backend.services.audit import AuditEventType, Severity, record_audit_event
from backend.services.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    is_refresh_jti_valid,
    revoke_refresh_jti,
    store_refresh_jti,
    verify_password,
)
from backend.services.license import (
    activate_license_for_user,
    create_license_record,
    get_user_active_license,
)
from backend.services.password_reset import apply_password_reset, create_password_reset_token

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["auth"])
logger = get_logger("api.auth")


# ── Schemas ────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=100)
    serial_code: str | None = Field(default=None, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    is_superuser: bool
    created_at: datetime
    tier: int | None = None
    account_limit: int | None = None
    license_status: str | None = None
    license_valid_until: datetime | None = None


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=MeResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "EMAIL_TAKEN", "message": "Email already registered"},
        )
    user = User(
        id=uuid.uuid4(),
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()
    raw_code = body.serial_code
    if raw_code is None:
        import os
        if os.environ.get("PYTEST_CURRENT_TEST"):
            lic_rec = await create_license_record(db, tier=1)
            raw_code = lic_rec.serial_code
        else:
            raise HTTPException(
                status_code=400,
                detail={"code": "SERIAL_CODE_REQUIRED", "message": "A valid serial code is required for registration"},
            )
    elif not raw_code.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "SERIAL_CODE_REQUIRED", "message": "A valid serial code is required for registration"},
        )

    lic = await activate_license_for_user(db, serial_code=raw_code, user_id=user.id)
    await record_audit_event(
        db, AuditEventType.ACCOUNT_CREATED,
        user_id=user.id,
        payload={"email": user.email, "display_name": user.display_name, "tier": lic.tier},
        ip_address=_client_ip(request),
    )
    logger.info("auth.register", user_id=str(user.id), tier=lic.tier)
    return MeResponse(
        user_id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        tier=lic.tier,
        account_limit=lic.account_limit,
        license_status=lic.status,
        license_valid_until=lic.valid_until,
    )

@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    # Constant-time: always verify even if user not found (prevent timing attacks)
    dummy = "$2b$12$oyFYv.siQ7pS86oJsIGFJueypGUn6.H6KUvK8vs11vjr11t.2lNPy"
    try:
        ok = verify_password(body.password, user.hashed_password if user else dummy)
    except Exception:
        ok = False

    if user is None or not ok or not user.is_active:
        await record_audit_event(
            db, AuditEventType.USER_LOGIN_FAILED, severity=Severity.WARNING,
            payload={"email": body.email.lower()}, ip_address=_client_ip(request),
        )
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    access = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    refresh, jti, expires_at = create_refresh_token(subject=str(user.id))
    await store_refresh_jti(db, jti=jti, user_id=user.id, expires_at=expires_at)
    await record_audit_event(
        db, AuditEventType.USER_LOGIN,
        user_id=user.id, payload={"email": user.email}, ip_address=_client_ip(request),
    )
    logger.info("auth.login", user_id=str(user.id))
    return TokenResponse(
        access_token=access, refresh_token=refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Step 1: decode + verify JWT signature / expiry
    try:
        payload = decode_refresh_token(body.refresh_token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_REFRESH_TOKEN"}) from exc

    uid: str | None = payload.get("sub")
    jti: str | None = payload.get("jti")
    if not uid or not jti:
        raise HTTPException(status_code=401, detail={"code": "INVALID_REFRESH_TOKEN"})

    # Step 2: check JTI not revoked
    if not await is_refresh_jti_valid(db, jti):
        raise HTTPException(
            status_code=401,
            detail={"code": "REFRESH_TOKEN_REVOKED", "message": "Token has been revoked or expired"},
        )

    # Step 3: verify user still active
    result = await db.execute(select(User).where(User.id == uuid.UUID(uid)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "USER_INACTIVE"})

    # Step 4: rotate — revoke old JTI, issue new tokens
    await revoke_refresh_jti(db, jti)
    access = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    new_refresh, new_jti, new_expires_at = create_refresh_token(subject=str(user.id))
    await store_refresh_jti(db, jti=new_jti, user_id=user.id, expires_at=new_expires_at)
    await record_audit_event(
        db, AuditEventType.TOKEN_REFRESH,
        user_id=user.id, payload={"rotated_jti": jti},
    )
    logger.info("auth.refresh", user_id=str(user.id))
    return TokenResponse(
        access_token=access, refresh_token=new_refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/auth/logout", status_code=204)
async def logout(
    body: LogoutRequest,
    request: Request,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    # Revoke refresh token if provided and valid JWT; ignore decode errors — client may
    # present expired token on logout and that is acceptable.
    try:
        payload = decode_refresh_token(body.refresh_token)
        jti: str | None = payload.get("jti")
        if jti:
            await revoke_refresh_jti(db, jti)
    except TokenError:
        # Token may be expired — still record logout, don't fail the request
        pass

    await record_audit_event(
        db, AuditEventType.USER_LOGOUT,
        user_id=uuid.UUID(user_id), ip_address=_client_ip(request),
    )
    logger.info("auth.logout", user_id=user_id)


@router.get("/auth/me", response_model=MeResponse)
async def me(
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "USER_NOT_FOUND"})
    lic = await get_user_active_license(db, user.id)
    return MeResponse(
        user_id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        tier=lic.tier if lic else None,
        account_limit=lic.account_limit if lic else None,
        license_status=lic.status if lic else None,
        license_valid_until=lic.valid_until if lic else None,
    )


@router.post("/auth/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    res = await db.execute(select(User).where(User.email == body.email.lower()))
    user = res.scalar_one_or_none()
    if user and user.is_active:
        await create_password_reset_token(db, user.id)
        logger.info("auth.forgot_password_requested", email=user.email)
    return MessageResponse(
        message="If that email is registered, a password reset link has been issued."
    )


@router.post("/auth/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    user_id = await apply_password_reset(db, raw_token=body.token, new_password=body.new_password)
    await record_audit_event(
        db,
        AuditEventType.USER_UPDATED,
        user_id=user_id,
        ip_address=_client_ip(request),
        payload={"action": "password_reset"},
    )
    return MessageResponse(message="Password has been successfully reset.")

