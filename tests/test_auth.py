"""
Unit tests for authentication service.

Tests password hashing, JWT creation/validation, token error handling.
No database required.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import backend.services.auth as auth_module
from backend.services.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_subject_from_token,
    hash_password,
    verify_password,
)

# Test JWT secret — must be ≤ 72 bytes for bcrypt compat, ≥ 32 chars for security
TEST_JWT_SECRET = "test-secret-x12345678901234567890123456"


@pytest.fixture(autouse=True)
def patch_auth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the settings object reference inside auth.py module scope."""
    from unittest.mock import MagicMock
    mock_settings = MagicMock()
    mock_settings.JWT_ALGORITHM = "HS256"
    mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
    mock_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30
    mock_settings.require_jwt_secret.return_value = TEST_JWT_SECRET
    monkeypatch.setattr(auth_module, "settings", mock_settings)


@pytest.mark.unit
class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        plain = "my-secure-password-123"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_correct_password(self) -> None:
        plain = "correct-password"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self) -> None:
        plain = "correct-password"
        hashed = hash_password(plain)
        assert verify_password("wrong-password", hashed) is False

    def test_same_password_different_hashes(self) -> None:
        """Bcrypt uses random salt — same password must produce different hashes."""
        plain = "same-password"
        h1 = hash_password(plain)
        h2 = hash_password(plain)
        assert h1 != h2

    def test_empty_password_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            hash_password("")


@pytest.mark.unit
class TestJwtAccessToken:
    def test_create_and_decode(self) -> None:
        token = create_access_token(subject="user-123")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_get_subject(self) -> None:
        token = create_access_token(subject="user-abc")
        assert get_subject_from_token(token) == "user-abc"

    def test_extra_claims_embedded(self) -> None:
        token = create_access_token(subject="u1", extra_claims={"role": "admin"})
        payload = decode_access_token(token)
        assert payload["role"] == "admin"

    def test_expired_token_raises(self) -> None:
        token = create_access_token(subject="u1", expires_delta=timedelta(seconds=-1))
        with pytest.raises(TokenError):
            decode_access_token(token)

    def test_tampered_token_raises(self) -> None:
        token = create_access_token(subject="u1")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(TokenError):
            decode_access_token(tampered)

    def test_refresh_token_rejected_as_access(self) -> None:
        refresh, _jti, _exp = create_refresh_token(subject="u1")
        with pytest.raises(TokenError, match="not an access token"):
            decode_access_token(refresh)

    def test_jti_present(self) -> None:
        """JWT ID must be present for future revocation support."""
        token = create_access_token(subject="u1")
        payload = decode_access_token(token)
        assert "jti" in payload
        assert len(payload["jti"]) > 0


@pytest.mark.unit
class TestJwtRefreshToken:
    def test_create_and_decode_refresh(self) -> None:
        token, jti, expires_at = create_refresh_token(subject="user-999")
        payload = decode_refresh_token(token)
        assert payload["sub"] == "user-999"
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti
        assert expires_at is not None

    def test_access_token_rejected_as_refresh(self) -> None:
        access = create_access_token(subject="u1")
        with pytest.raises(TokenError, match="not a refresh token"):
            decode_refresh_token(access)
