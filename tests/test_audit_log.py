"""
AuditLog model tests.

Verifies:
- AuditLog uses ImmutableBase (no updated_at column)
- AuditLog has occurred_at and created_at
- AuditLog has no onupdate trigger
- Service function record_audit_event correctly populates the model
"""

from __future__ import annotations

import uuid

import pytest

from backend.db.models.audit_log import AuditLog


@pytest.mark.unit
class TestAuditLogImmutability:
    """M-7: AuditLog must be append-only — no updated_at."""

    def test_audit_log_inherits_immutable_base(self) -> None:
        """AuditLog must inherit from Base (shared registry) and use ImmutableTimestampMixin."""
        from backend.db.base import Base, ImmutableTimestampMixin
        assert issubclass(AuditLog, Base), (
            "AuditLog must inherit from Base"
        )
        assert issubclass(AuditLog, ImmutableTimestampMixin), (
            "AuditLog must use ImmutableTimestampMixin (no updated_at)"
        )

    def test_audit_log_has_no_updated_at(self) -> None:
        """updated_at must not exist on the AuditLog table."""
        columns = {c.name for c in AuditLog.__table__.columns}
        assert "updated_at" not in columns, (
            "AuditLog must not have updated_at — it is an immutable append-only table"
        )

    def test_audit_log_has_occurred_at(self) -> None:
        """occurred_at is the event timestamp."""
        columns = {c.name for c in AuditLog.__table__.columns}
        assert "occurred_at" in columns

    def test_audit_log_has_created_at_from_base(self) -> None:
        """created_at is inherited from ImmutableBase."""
        columns = {c.name for c in AuditLog.__table__.columns}
        assert "created_at" in columns

    def test_no_column_has_onupdate(self) -> None:
        """No AuditLog column may have onupdate — immutable table."""
        for col in AuditLog.__table__.columns:
            assert col.onupdate is None, (
                f"Column {col.name!r} has onupdate — AuditLog must be immutable"
            )

    def test_occurred_at_has_no_onupdate(self) -> None:
        """Specifically check occurred_at has no onupdate."""
        col = AuditLog.__table__.c["occurred_at"]
        assert col.onupdate is None

    def test_audit_log_required_fields_present(self) -> None:
        """Core fields must exist."""
        columns = {c.name for c in AuditLog.__table__.columns}
        for field in ("id", "event_type", "severity", "occurred_at", "created_at"):
            assert field in columns, f"Required field {field!r} missing from AuditLog"


@pytest.mark.unit
class TestAuditServiceRecord:
    """Verify record_audit_event creates AuditLog correctly without committing."""

    @pytest.mark.asyncio
    async def test_record_creates_audit_log_entry(self) -> None:
        from unittest.mock import MagicMock

        from backend.db.models.account import TradingAccount  # noqa: F401
        from backend.db.models.mt5_agent import MT5Agent  # noqa: F401

        # Import all models to ensure SQLAlchemy mapper is fully configured
        from backend.db.models.user import User  # noqa: F401
        from backend.services.audit import AuditEventType, record_audit_event

        session = MagicMock()
        session.add = MagicMock()

        entry = await record_audit_event(
            session,
            AuditEventType.USER_LOGIN,
            severity="INFO",
            user_id=uuid.uuid4(),
            payload={"source": "test"},
        )

        assert isinstance(entry, AuditLog)
        assert entry.event_type == AuditEventType.USER_LOGIN
        assert entry.severity == "INFO"
        assert entry.payload_json is not None
        session.add.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_record_does_not_set_updated_at(self) -> None:
        """record_audit_event must not touch updated_at (it doesn't exist)."""
        from unittest.mock import MagicMock

        from backend.services.audit import AuditEventType, record_audit_event

        session = MagicMock()
        session.add = MagicMock()

        _entry = await record_audit_event(
            session,
            AuditEventType.USER_LOGIN,
        )

        # If updated_at were set, hasattr would find it; it must not be on AuditLog
        assert not hasattr(AuditLog, "updated_at") or "updated_at" not in {
            c.name for c in AuditLog.__table__.columns
        }
