"""
TradingAccount model.

One TradingAccount = one MT5 broker account.
Each account has isolated risk state, positions, trades, and PNL.
Never use a global account — always filter by account_id.

Cent account handling:
  broker reports cents → normalize to USD via cent_normalization_factor
  10000 cents × 0.01 = $100 USD
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.mt5_agent import MT5Agent
    from backend.db.models.user import User


class TradingAccount(TimestampMixin, Base):
    __tablename__ = "trading_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="uuid_generate_v4()",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Display / identification
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    broker: Mapped[str] = mapped_column(String(100), nullable=False)

    # MT5 account details
    # mt5_account_number is stored as string — treat as opaque identifier
    mt5_account_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    mt5_server: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Currency / cent normalization
    # broker_currency: the currency as reported by the broker (e.g. "USD", "Cent")
    broker_currency: Mapped[str] = mapped_column(String(20), nullable=False, default="USD")
    # is_cent_account: true for Cent-denominated accounts (any broker).
    # This is a characteristic of the ACCOUNT DENOMINATION, not of any broker brand.
    # AUREXIS is broker-agnostic: never branch on broker name — branch on this flag
    # plus cent_normalization_factor.
    is_cent_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # cent_normalization_factor: multiply broker units by this to get USD
    # For normal USD accounts: 1.0
    # For Cent accounts: 0.01 (10000 cents = $100)
    # IMPORTANT: This value must be set explicitly — never assume.
    cent_normalization_factor: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8),
        nullable=False,
        default=Decimal("1.0"),
    )

    # Broker-specific symbol mappings (JSON string)
    # e.g. {"XAUUSD": "XAUUSD.m"} for brokers that use different suffixes
    symbol_mapping_json: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Account state
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trading_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # trading_enabled requires explicit user activation — not automatic

    # Relationships
    user: Mapped[User] = relationship(
        "User", back_populates="accounts"
    )
    mt5_agents: Mapped[list[MT5Agent]] = relationship(
        "MT5Agent", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<TradingAccount id={self.id} label={self.label!r} "
            f"broker={self.broker!r} mt5={self.mt5_account_number!r}>"
        )

    def normalize_to_usd(self, broker_value: Decimal) -> Decimal:
        """
        Convert a broker-native monetary value to USD.

        Delegates to the canonical ``normalize_broker_to_usd`` service function
        to ensure consistent Decimal arithmetic and 2dp rounding across all call sites.

        For Cent accounts: multiply by cent_normalization_factor (0.01)
        For USD accounts: factor is 1.0, no change.

        Always use Decimal for monetary arithmetic — never float.
        """
        from backend.services.normalization import normalize_broker_to_usd
        return normalize_broker_to_usd(broker_value, self.cent_normalization_factor)
