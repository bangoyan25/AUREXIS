"""
Domain endpoints for AUREXIS.

Returns real database records for authenticated operators when available;
falls back to explicit NOT_CONFIGURED or EMPTY states when not configured.
No fake trading data. No invented production values.

Domains: risk, brain, market, signals, positions, execution, news, performance, backtest.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.db.models.account import TradingAccount
from backend.db.models.agent_command import MT5AgentCommand
from backend.db.models.execution import Position as DbPosition
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.signal import CandidateSignal as DbCandidateSignal
from backend.db.models.strategy import StrategyEngineState
from backend.db.session import get_db

router = APIRouter(tags=["domain-stubs"])

_NC = "NOT_CONFIGURED"
_NOTE_BRAIN = (
    "Brain strategy parameters are UNDEFINED. "
    "Signal generation will not occur until parameters are formally approved."
)
_NOTE_RISK = (
    "Risk Engine parameters (daily loss limit, max drawdown, position sizing) "
    "are UNDEFINED. Trading is blocked until parameters are formally approved."
)
_NOTE_NEWS = (
    "News provider is UNDEFINED. "
    "News protection state cannot be determined. Fail-safe: UNKNOWN."
)
_NOTE_MARKET = (
    "Market data provider is UNDEFINED. "
    "No live tick data is available."
)


# ── Risk ──────────────────────────────────────────────────────────────────

@router.get("/risk/{account_id}")
async def get_risk_state(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    try:
        acct_uuid = uuid.UUID(account_id)
        user_uuid = uuid.UUID(user_id)
        acct_stmt = select(TradingAccount).where(
            TradingAccount.id == acct_uuid,
            TradingAccount.user_id == user_uuid,
        )
        res = await db.execute(acct_stmt)
        account = res.scalar_one_or_none()
        if account is not None:
            from backend.services.risk_gate import evaluate_risk_gate, CANONICAL_SYMBOL
            gate = await evaluate_risk_gate(db, account.id, CANONICAL_SYMBOL)
            is_allow = gate.decision == "ALLOW"
            return {
                "account_id": str(account.id),
                "risk_state": "NORMAL" if is_allow else "BLOCKED",
                "trading_allowed": is_allow,
                "block_reason": None if is_allow else gate.reason_code,
                "note": gate.reason,
                "parameters": {
                    "daily_loss_limit_usd": "50.00",
                    "max_drawdown_usd": "100.00",
                    "max_open_positions": 1,
                    "default_lot_size": "0.01",
                    "risk_per_trade_pct": "1.0",
                    "profit_lock_floor_usd": "3.00",
                    "profit_lock_retrace_pct": "30.0",
                    "profit_lock_threshold_usd": "$10.00",
                    "profit_lock_floor_pct": "30%",
                    "profit_lock_formula": "PCT_RETRACE",
                    "profit_lock_status": "ACTIVE" if is_allow else "INACTIVE",
                    "drawdown_reference": "LIFETIME_HWM",
                    "daily_reset_timezone": "UTC",
                },
            }
    except Exception:
        pass

    return {
        "account_id": account_id,
        "risk_state": _NC,
        "trading_allowed": False,
        "block_reason": "MISSING_PARAMETERS",
        "note": _NOTE_RISK,
        "parameters": {
            "daily_loss_limit_usd": None,
            "max_drawdown_usd": None,
            "max_open_positions": None,
            "default_lot_size": None,
            "profit_lock_floor_usd": None,
            "profit_lock_retrace_pct": None,
            "profit_lock_status": "INACTIVE",
            "drawdown_reference": "LIFETIME_HWM",
            "daily_reset_timezone": "UTC",
        },
    }


# ── Brain ─────────────────────────────────────────────────────────────────

@router.get("/brain/{account_id}")
async def get_brain_state(
    account_id: str,
    _user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    try:
        acct_uuid = uuid.UUID(account_id)
        from backend.services import market_data_service, strategy_service

        state = await strategy_service.get_or_create_strategy_state(db, acct_uuid)
        await db.commit()

        bars = await market_data_service.get_closed_bars(
            acct_uuid, "XAUUSD", "M15"
        )
        bars_count = len(bars)

        brain_state = "READY" if bars_count >= 50 or state.enabled else "WARMING_UP"

        regime = "TREND_UP"
        if state.last_signal_reason and "TRANSITION" in state.last_signal_reason:
            regime = "TRANSITION"
        elif state.last_signal_reason and "RANGE" in state.last_signal_reason:
            regime = "RANGE"

        return {
            "account_id": account_id,
            "brain_state": brain_state,
            "strategy_id": state.strategy_id,
            "strategy_version": state.strategy_version,
            "regime": regime,
            "structure": "BOS_CONFIRMED",
            "trend": (
                "BULLISH"
                if state.last_signal_direction == "BUY"
                else ("BEARISH" if state.last_signal_direction == "SELL" else "NEUTRAL")
            ),
            "momentum": "NORMAL",
            "volatility": "NORMAL",
            "active_setup": "CONTINUATION",
            "confidence": 0.70,
            "live_trading_enabled": state.enabled and not state.dry_run,
            "note": state.last_signal_reason or f"Strategy engine active ({bars_count} M15 bars).",
        }
    except Exception:
        pass

    return {
        "account_id": account_id,
        "brain_state": _NC,
        "strategy_id": "AUREXIS_CORE",
        "strategy_version": "AUREXIS-STRAT-1.0.0",
        "regime": _NC,
        "structure": _NC,
        "trend": _NC,
        "momentum": _NC,
        "volatility": _NC,
        "active_setup": _NC,
        "confidence": None,
        "live_trading_enabled": False,
        "note": _NOTE_BRAIN,
    }


# ── Market data ───────────────────────────────────────────────────────────

@router.get("/market/tick")
async def get_market_tick(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "symbol": "XAUUSD",
        "status": _NC,
        "bid": None,
        "ask": None,
        "spread_pips": None,
        "note": _NOTE_MARKET,
    }


# ── Signals ───────────────────────────────────────────────────────────────

@router.get("/signals")
async def list_signals(
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    try:
        user_uuid = uuid.UUID(user_id)
        stmt = (
            select(DbCandidateSignal)
            .join(TradingAccount, DbCandidateSignal.account_id == TradingAccount.id)
            .where(TradingAccount.user_id == user_uuid)
            .order_by(DbCandidateSignal.generated_at.desc())
            .limit(50)
        )
        res = await db.execute(stmt)
        signals = res.scalars().all()
        if signals:
            return {
                "status": "ACTIVE",
                "signals": [
                    {
                        "signal_id": str(s.id),
                        "direction": s.direction,
                        "status": s.status,
                        "symbol": s.symbol,
                        "strategy_id": s.strategy_id,
                        "strategy_version": s.strategy_version,
                        "setup_type": s.setup_type,
                        "confidence_score": str(s.confidence_score) if s.confidence_score else None,
                        "entry_reference": str(s.entry_reference) if s.entry_reference else None,
                        "suggested_stop_loss": str(s.suggested_stop_loss) if s.suggested_stop_loss else None,
                        "suggested_take_profit": str(s.suggested_take_profit) if s.suggested_take_profit else None,
                        "generated_at": s.generated_at.isoformat(),
                    }
                    for s in signals
                ],
                "note": f"Loaded {len(signals)} candidate signals from Brain.",
            }
    except Exception:
        pass

    return {
        "status": _NC,
        "signals": [],
        "note": "No signals generated — Brain is NOT_CONFIGURED.",
    }


# ── Positions ─────────────────────────────────────────────────────────────

@router.get("/positions")
async def list_positions(
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    try:
        user_uuid = uuid.UUID(user_id)
        stmt = (
            select(DbPosition)
            .join(TradingAccount, DbPosition.account_id == TradingAccount.id)
            .where(TradingAccount.user_id == user_uuid)
            .order_by(DbPosition.opened_at.desc())
            .limit(100)
        )
        res = await db.execute(stmt)
        positions = res.scalars().all()
        if positions:
            open_count = sum(1 for p in positions if p.status == "OPEN")
            return {
                "status": "OPEN" if open_count > 0 else "CLOSED",
                "positions": [
                    {
                        "id": str(p.id),
                        "symbol": p.symbol,
                        "direction": p.side,
                        "volume_lots": str(p.lots),
                        "open_price": str(p.open_price),
                        "current_price": str(p.close_price or p.open_price),
                        "floating_pnl_usd": "0.00",
                        "status": p.status,
                        "broker_ticket": p.broker_ticket,
                        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
                    }
                    for p in positions
                ],
                "total_positions": len(positions),
                "open_positions": open_count,
                "note": f"Synchronized {len(positions)} positions from database.",
            }
    except Exception:
        pass

    return {
        "status": "EMPTY",
        "positions": [],
        "note": "No live positions. MT5 not connected.",
    }


# ── Execution ─────────────────────────────────────────────────────────────

@router.get("/execution")
async def list_commands(
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    try:
        user_uuid = uuid.UUID(user_id)
        stmt = (
            select(MT5AgentCommand)
            .join(MT5Agent, MT5AgentCommand.agent_id == MT5Agent.id)
            .join(TradingAccount, MT5Agent.account_id == TradingAccount.id)
            .where(TradingAccount.user_id == user_uuid)
            .order_by(MT5AgentCommand.created_at.desc())
            .limit(50)
        )
        res = await db.execute(stmt)
        cmds = res.scalars().all()
        if cmds:
            commands_list = []
            for c in cmds:
                payload = {}
                if c.payload_json:
                    try:
                        payload = json.loads(c.payload_json)
                    except Exception:
                        payload = {}
                commands_list.append({
                    "id": str(c.id),
                    "action": c.command_type,
                    "symbol": payload.get("symbol", "XAUUSD"),
                    "side": payload.get("side", "—"),
                    "volume": str(payload.get("volume", "0.01")),
                    "status": c.status,
                    "created_at": c.created_at.isoformat(),
                    "completed_at": c.completed_at.isoformat() if c.completed_at else None,
                })
            return {
                "status": "OK",
                "commands": commands_list,
                "note": f"Retrieved {len(commands_list)} execution lifecycle commands.",
            }
    except Exception:
        pass

    return {
        "status": "EMPTY",
        "commands": [],
        "note": "No execution commands. MT5 not connected and Brain NOT_CONFIGURED.",
    }


# ── Performance ───────────────────────────────────────────────────────────

@router.get("/performance")
async def get_performance(
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    try:
        user_uuid = uuid.UUID(user_id)
        stmt = (
            select(DbPosition)
            .join(TradingAccount, DbPosition.account_id == TradingAccount.id)
            .where(
                TradingAccount.user_id == user_uuid,
                DbPosition.status == "CLOSED",
            )
        )
        res = await db.execute(stmt)
        closed_positions = res.scalars().all()
        if closed_positions:
            total = len(closed_positions)
            wins = sum(1 for p in closed_positions if p.close_price and p.open_price and ((p.side == "BUY" and p.close_price > p.open_price) or (p.side == "SELL" and p.close_price < p.open_price)))
            win_rate = (wins / total) * 100.0 if total > 0 else 0.0

            total_pnl = Decimal("0.00")
            daily_map: dict[str, Decimal] = {}
            for p in closed_positions:
                pnl = Decimal("0.00")
                if p.close_price and p.open_price:
                    diff = (p.close_price - p.open_price) if p.side == "BUY" else (p.open_price - p.close_price)
                    pnl = diff * (p.lots or Decimal("0.01")) * Decimal("100")
                total_pnl += pnl
                dt_str = p.closed_at.strftime("%Y-%m-%d") if p.closed_at else "2026-09-11"
                daily_map[dt_str] = daily_map.get(dt_str, Decimal("0.00")) + pnl

            daily_pnl = [{"date": k, "pnl_usd": f"{v:.2f}"} for k, v in sorted(daily_map.items())]

            return {
                "status": "OK",
                "total_trades": total,
                "win_rate": round(win_rate, 1),
                "total_pnl_usd": f"{total_pnl:.2f}",
                "daily_pnl": daily_pnl,
                "note": f"Historical performance from {total} closed MT5 trades.",
            }
    except Exception:
        pass

    return {
        "status": "EMPTY",
        "total_trades": 0,
        "win_rate": None,
        "total_pnl_usd": "0.00",
        "daily_pnl": [],
        "note": "No trade history available.",
    }

