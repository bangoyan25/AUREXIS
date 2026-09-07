"""Trading domain schema migration.

Revision ID: 003_trading_domain
Revises: 002_refresh_tokens
Create Date: 2026-09-06

Adds tables for risk management, execution, and Brain lifecycle:
- risk_configurations (versioned risk config per account)
- risk_decisions (immutable risk decision audit trail)
- candidate_signals (Brain output lifecycle)
- execution_commands (command dispatch and lifecycle)
- execution_reports (broker execution result)
- positions (open position tracking)
- equity_snapshots (account state snapshots for HWM/PnL)
- daily_session_states (per-account per-date session state)
- news_events (normalized economic calendar events)

Monetary columns: NUMERIC(18,8) for precise USD representation.
All timestamps: UTC (TIMESTAMP WITH TIME ZONE).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_trading_domain"
down_revision: str | None = "002_refresh_tokens"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)
_UUID_PK = dict(primary_key=True, server_default=sa.text("uuid_generate_v4()"), nullable=False)
_TS = sa.DateTime(timezone=True)
_TS_NOW = dict(server_default=sa.text("now()"), nullable=False)
_NUM = sa.Numeric(precision=18, scale=8)


def upgrade() -> None:
    # ── risk_configurations ───────────────────────────────────────────────
    op.create_table(
        "risk_configurations",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("account_id", _UUID,
                  sa.ForeignKey("trading_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", _TS, nullable=False),
        sa.Column("created_by_user_id", _UUID,
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("daily_reset_timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("drawdown_reference", sa.String(50), nullable=False, server_default="LIFETIME_HWM"),
        sa.Column("profit_lock_formula", sa.String(50), nullable=False, server_default="PCT_RETRACE"),
        sa.Column("profit_lock_basis", sa.String(50), nullable=False, server_default="FLOATING_EQUITY"),
        sa.Column("profit_lock_threshold_usd", _NUM, nullable=False, server_default="10"),
        sa.Column("profit_lock_floor_pct", _NUM, nullable=False, server_default="0.30"),
        sa.Column("max_tick_staleness_ms", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("news_pre_event_window_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("news_post_event_window_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("daily_loss_limit_usd", _NUM, nullable=True),
        sa.Column("max_drawdown_usd", _NUM, nullable=True),
        sa.Column("max_open_positions", sa.Integer(), nullable=True),
        sa.Column("max_open_lots", _NUM, nullable=True),
        sa.Column("max_spread_usd", _NUM, nullable=True),
        sa.Column("risk_per_trade_pct", _NUM, nullable=True),
        sa.Column("created_at", _TS, **_TS_NOW),
        sa.UniqueConstraint("account_id", "version", name="uq_risk_config_account_version"),
    )
    op.create_index("ix_risk_configurations_account_id", "risk_configurations", ["account_id"])

    # ── risk_decisions ────────────────────────────────────────────────────
    op.create_table(
        "risk_decisions",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("account_id", _UUID,
                  sa.ForeignKey("trading_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("risk_config_version", sa.Integer(), nullable=True),
        sa.Column("signal_id", _UUID, nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("reason_code", sa.String(200), nullable=False),
        sa.Column("risk_state", sa.String(50), nullable=False),
        sa.Column("equity_at_decision", _NUM, nullable=True),
        sa.Column("drawdown_at_decision", _NUM, nullable=True),
        sa.Column("daily_pnl_at_decision", _NUM, nullable=True),
        sa.Column("profit_lock_active", sa.Boolean(), nullable=True),
        sa.Column("profit_lock_floor_usd", _NUM, nullable=True),
        sa.Column("decided_at", _TS, nullable=False),
        sa.Column("created_at", _TS, **_TS_NOW),
    )
    op.create_index("ix_risk_decisions_account_id", "risk_decisions", ["account_id"])
    op.create_index("ix_risk_decisions_decided_at", "risk_decisions", ["decided_at"])
    op.create_index("ix_risk_decisions_signal_id", "risk_decisions", ["signal_id"])
    op.create_index("ix_risk_decisions_correlation_id", "risk_decisions", ["correlation_id"])

    # ── candidate_signals ────────────────────────────────────────────────
    op.create_table(
        "candidate_signals",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("account_id", _UUID,
                  sa.ForeignKey("trading_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False, server_default="XAUUSD"),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("strategy_id", sa.String(100), nullable=False),
        sa.Column("strategy_version", sa.String(50), nullable=False),
        sa.Column("regime", sa.String(50), nullable=True),
        sa.Column("setup_type", sa.String(50), nullable=True),
        sa.Column("confidence_score", _NUM, nullable=True),
        sa.Column("entry_reference", _NUM, nullable=True),
        sa.Column("suggested_stop_loss", _NUM, nullable=True),
        sa.Column("suggested_take_profit", _NUM, nullable=True),
        sa.Column("spread_at_signal", _NUM, nullable=True),
        sa.Column("news_state_at_signal", sa.String(50), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="CANDIDATE_FORMING"),
        sa.Column("generated_at", _TS, nullable=False),
        sa.Column("expires_at", _TS, nullable=True),
        sa.Column("created_at", _TS, **_TS_NOW),
    )
    op.create_index("ix_candidate_signals_account_id", "candidate_signals", ["account_id"])
    op.create_index("ix_candidate_signals_generated_at", "candidate_signals", ["generated_at"])
    op.create_index("ix_candidate_signals_status", "candidate_signals", ["status"])

    # ── execution_commands ────────────────────────────────────────────────
    op.create_table(
        "execution_commands",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("account_id", _UUID,
                  sa.ForeignKey("trading_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("signal_id", _UUID,
                  sa.ForeignKey("candidate_signals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("risk_decision_id", _UUID,
                  sa.ForeignKey("risk_decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("order_type", sa.String(10), nullable=True),
        sa.Column("volume_lots", _NUM, nullable=True),
        sa.Column("price", _NUM, nullable=True),
        sa.Column("stop_loss", _NUM, nullable=True),
        sa.Column("take_profit", _NUM, nullable=True),
        sa.Column("slippage_points", sa.Integer(), nullable=True),
        sa.Column("magic_number", sa.Integer(), nullable=True),
        sa.Column("position_ticket", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="CREATED"),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("expires_at", _TS, nullable=False),
        sa.Column("sent_at", _TS, nullable=True),
        sa.Column("acknowledged_at", _TS, nullable=True),
        sa.Column("created_at", _TS, **_TS_NOW),
    )
    op.create_index("ix_execution_commands_account_id", "execution_commands", ["account_id"])
    op.create_index("ix_execution_commands_status", "execution_commands", ["status"])
    op.create_index("ix_execution_commands_signal_id", "execution_commands", ["signal_id"])
    op.create_index("ix_execution_commands_idempotency_key",
                    "execution_commands", ["idempotency_key"], unique=True)

    # ── execution_reports ────────────────────────────────────────────────
    op.create_table(
        "execution_reports",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("command_id", _UUID,
                  sa.ForeignKey("execution_commands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", _UUID,
                  sa.ForeignKey("trading_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("broker_ticket", sa.BigInteger(), nullable=True),
        sa.Column("broker_deal_id", sa.BigInteger(), nullable=True),
        sa.Column("fill_price", _NUM, nullable=True),
        sa.Column("fill_volume_lots", _NUM, nullable=True),
        sa.Column("slippage_points", sa.Integer(), nullable=True),
        sa.Column("commission_usd", _NUM, nullable=True),
        sa.Column("swap_usd", _NUM, nullable=True),
        sa.Column("broker_error_code", sa.Integer(), nullable=True),
        sa.Column("broker_error_message", sa.String(500), nullable=True),
        sa.Column("raw_broker_response_json", sa.Text(), nullable=True),
        sa.Column("executed_at", _TS, nullable=False),
        sa.Column("created_at", _TS, **_TS_NOW),
    )
    op.create_index("ix_execution_reports_command_id", "execution_reports", ["command_id"])
    op.create_index("ix_execution_reports_account_id", "execution_reports", ["account_id"])
    op.create_index("ix_execution_reports_broker_ticket", "execution_reports", ["broker_ticket"])
    op.create_index("ix_execution_reports_idempotency_key", "execution_reports", ["idempotency_key"])

    # ── positions ────────────────────────────────────────────────────────
    op.create_table(
        "positions",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("account_id", _UUID,
                  sa.ForeignKey("trading_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("command_id", _UUID,
                  sa.ForeignKey("execution_commands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("broker_ticket", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("lots", _NUM, nullable=False),
        sa.Column("open_price", _NUM, nullable=False),
        sa.Column("stop_loss", _NUM, nullable=True),
        sa.Column("take_profit", _NUM, nullable=True),
        sa.Column("current_price", _NUM, nullable=True),
        sa.Column("unrealized_pnl_usd", _NUM, nullable=True),
        sa.Column("commission_usd", _NUM, nullable=True),
        sa.Column("swap_usd", _NUM, nullable=True),
        sa.Column("magic_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("opened_at", _TS, nullable=False),
        sa.Column("closed_at", _TS, nullable=True),
        sa.Column("close_price", _NUM, nullable=True),
        sa.Column("realized_pnl_usd", _NUM, nullable=True),
        sa.Column("last_synced_at", _TS, nullable=True),
        sa.Column("created_at", _TS, **_TS_NOW),
        sa.Column("updated_at", _TS, **_TS_NOW),
        sa.UniqueConstraint("account_id", "broker_ticket", name="uq_positions_account_ticket"),
    )
    op.create_index("ix_positions_account_id", "positions", ["account_id"])
    op.create_index("ix_positions_status", "positions", ["status"])
    op.create_index("ix_positions_broker_ticket", "positions", ["broker_ticket"])
    op.create_index("ix_positions_opened_at", "positions", ["opened_at"])

    # ── equity_snapshots ─────────────────────────────────────────────────
    op.create_table(
        "equity_snapshots",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("account_id", _UUID,
                  sa.ForeignKey("trading_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance_usd", _NUM, nullable=False),
        sa.Column("equity_usd", _NUM, nullable=False),
        sa.Column("margin_usd", _NUM, nullable=True),
        sa.Column("free_margin_usd", _NUM, nullable=True),
        sa.Column("floating_pnl_usd", _NUM, nullable=True),
        sa.Column("open_position_count", sa.Integer(), nullable=True),
        sa.Column("snapped_at", _TS, nullable=False),
        sa.Column("created_at", _TS, **_TS_NOW),
    )
    op.create_index("ix_equity_snapshots_account_id", "equity_snapshots", ["account_id"])
    op.create_index("ix_equity_snapshots_snapped_at", "equity_snapshots", ["snapped_at"])

    # ── daily_session_states ──────────────────────────────────────────────
    op.create_table(
        "daily_session_states",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("account_id", _UUID,
                  sa.ForeignKey("trading_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("session_open_equity_usd", _NUM, nullable=False),
        sa.Column("session_peak_profit_usd", _NUM, nullable=False, server_default="0"),
        sa.Column("realized_pnl_usd", _NUM, nullable=False, server_default="0"),
        sa.Column("floating_pnl_usd", _NUM, nullable=True),
        sa.Column("daily_loss_stop_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("profit_lock_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("profit_lock_floor_usd", _NUM, nullable=True),
        sa.Column("profit_lock_activated_at", _TS, nullable=True),
        sa.Column("last_updated_at", _TS, nullable=False),
        sa.Column("created_at", _TS, **_TS_NOW),
        sa.UniqueConstraint("account_id", "session_date", name="uq_daily_session_account_date"),
    )
    op.create_index("ix_daily_session_states_account_id", "daily_session_states", ["account_id"])
    op.create_index("ix_daily_session_states_session_date", "daily_session_states", ["session_date"])

    # ── news_events ───────────────────────────────────────────────────────
    op.create_table(
        "news_events",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_event_id", sa.String(200), nullable=True),
        sa.Column("event_name", sa.String(500), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("impact", sa.String(20), nullable=False),
        sa.Column("event_time", _TS, nullable=False),
        sa.Column("pre_event_window_start", _TS, nullable=False),
        sa.Column("post_event_window_end", _TS, nullable=False),
        sa.Column("actual_value", sa.String(100), nullable=True),
        sa.Column("forecast_value", sa.String(100), nullable=True),
        sa.Column("previous_value", sa.String(100), nullable=True),
        sa.Column("created_at", _TS, **_TS_NOW),
        sa.UniqueConstraint("source", "source_event_id", name="uq_news_events_source_id"),
    )
    op.create_index("ix_news_events_event_time", "news_events", ["event_time"])
    op.create_index("ix_news_events_currency", "news_events", ["currency"])
    op.create_index("ix_news_events_impact", "news_events", ["impact"])


def downgrade() -> None:
    op.drop_table("news_events")
    op.drop_table("daily_session_states")
    op.drop_table("equity_snapshots")
    op.drop_table("positions")
    op.drop_table("execution_reports")
    op.drop_table("execution_commands")
    op.drop_table("candidate_signals")
    op.drop_table("risk_decisions")
    op.drop_table("risk_configurations")
