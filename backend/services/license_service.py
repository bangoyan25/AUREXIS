"""LicenseService — licensing validation and feature entitlement checks.

Provides a skeleton for future commercial licensing.
Currently defaults to allowing all features in demo/dev mode.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class LicenseService:
    """Checks feature entitlement against active licenses."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_feature_enabled(self, feature: str, license_key: str | None = None) -> bool:
        """Check if a named feature is enabled.

        In development / demo (no license configured), returns True.
        When a license record is found, enforces `valid_until` and `revoked`.
        """
        if not license_key:
            # Default: all features open in development/demo
            return True

        from backend.db.models.license import License

        result = await self.session.execute(
            select(License).where(
                License.license_key == license_key,
                License.revoked.is_(False),
            )
        )
        lic = result.scalar_one_or_none()
        if not lic:
            return False

        # Expiry check
        if lic.valid_until and lic.valid_until < datetime.datetime.now(datetime.timezone.utc):
            logger.warning("license.expired", license_key=license_key)
            return False

        # Feature map
        features = {
            "strategy_engine": lic.feature_strategy_engine,
            "brain":           lic.feature_brain,
            "backtest":        lic.feature_backtest,
            "multi_account":   lic.feature_multi_account,
        }
        return bool(features.get(feature, False))
