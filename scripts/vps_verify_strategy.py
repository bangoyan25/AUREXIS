"""
Verify Phase 6 strategy engine state, risk gate, closed bars, and safety gates on VPS.
"""

from __future__ import annotations

import asyncio
from sqlalchemy import select

from backend.db.session import AsyncSessionLocal
from backend.db.models.account import TradingAccount
from backend.services.strategy_service import get_or_create_strategy_state, evaluate_strategy_for_account
from backend.services.risk_gate import evaluate_risk_gate
from backend.services.market_data_service import get_closed_bars, get_latest_market_data


async def main():
    async with AsyncSessionLocal() as s:
        res = await s.execute(select(TradingAccount))
        accounts = res.scalars().all()
        print(f"=== ACCOUNTS: {len(accounts)} ===")
        for a in accounts:
            print(f"Account: ID={a.id}, Label={a.label}, Broker={a.broker}, Server={a.mt5_server}, Active={a.is_active}")
            state = await get_or_create_strategy_state(s, a.id)
            print(f"  Strategy: enabled={state.enabled}, dry_run={state.dry_run}, sym={state.symbol}, tf={state.timeframe}")
            print(f"  Last signal: dir={state.last_signal_direction}, at={state.last_signal_at}, candle_ts={state.last_signal_candle_ts}")
            print(f"  Last risk: {state.last_risk_decision} ({state.last_risk_reason_code}), exec={state.last_execution_status}")

            bars = await get_closed_bars(a.id, "XAUUSD", "M15")
            print(f"  Closed M15 bars count: {len(bars) if bars else 0}")
            if bars:
                print(f"  Latest bar: open_time={bars[-1].get('open_time')}, close={bars[-1].get('close')}")

            mkt = await get_latest_market_data(a.id, "XAUUSD")
            print(f"  Latest market data: bid={mkt.get('bid') if mkt else None}, ask={mkt.get('ask') if mkt else None}, received_at={mkt.get('received_at') if mkt else None}")

            gate = await evaluate_risk_gate(s, a.id, "XAUUSD")
            print(f"  Risk Gate evaluation: decision={gate.decision}, reason={gate.reason_code}")


if __name__ == "__main__":
    asyncio.run(main())
