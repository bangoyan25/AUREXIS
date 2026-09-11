"""
AUREXIS Production Verification Script.
Queries live backend at http://127.0.0.1:8000/api/v1
"""

from __future__ import annotations

import asyncio
import sys
import httpx
from sqlalchemy import select

from backend.db.session import AsyncSessionLocal
from backend.db.models.account import TradingAccount
from backend.services.auth import create_access_token


async def run_verification():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(TradingAccount))
        accounts = res.scalars().all()
        if not accounts:
            print("[FAIL] No accounts found.")
            sys.exit(1)

        print(f"[OK] Found {len(accounts)} trading accounts:")
        target = None
        for a in accounts:
            print(f"  - ID: {a.id}, Broker: '{a.broker}', Server: '{a.mt5_server}', Active: {a.is_active}")
            if a.is_active and "demo" in (a.mt5_server or "").lower():
                target = a

        if target is None:
            target = accounts[0]

        print(f"\n[TARGET]: ID={target.id}, User={target.user_id}, Broker={target.broker}")

    token = create_access_token(str(target.user_id))
    client = httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )

    # 1. Health check
    print("\n=== 1. HEALTH CHECK ===")
    r_health = client.get("/health")
    h = r_health.json()
    print(f"System: {h.get('status')}")
    mt5 = h.get("components", {}).get("mt5", {})
    print(f"MT5: status={mt5.get('status')}, agents={mt5.get('connected_agents')}")

    # 2. Strategy state
    print("\n=== 2. STRATEGY ENGINE STATE ===")
    r_strat = client.get(f"/accounts/{target.id}/strategy")
    if r_strat.status_code == 200:
        s = r_strat.json()
        print(f"  Enabled: {s.get('enabled')}, Dry Run: {s.get('dry_run')}, TF: {s.get('timeframe')}")
        print(f"  Last signal: {s.get('last_signal_direction')} at {s.get('last_signal_at')}")
        print(f"  Last risk: {s.get('last_risk_decision')} ({s.get('last_risk_reason_code')})")

    # 3. Closed bars & market data
    print("\n=== 3. MARKET DATA & CLOSED BARS ===")
    r_bars = client.get(f"/market-data/{target.id}/bars?symbol=XAUUSD&timeframe=M15")
    if r_bars.status_code == 200:
        bars = r_bars.json().get("bars", [])
        print(f"  M15 bars: {len(bars)}")
        if bars:
            print(f"  Latest bar: {bars[-1]}")

    r_mkt = client.get(f"/market-data/{target.id}/latest?symbol=XAUUSD")
    if r_mkt.status_code == 200:
        mkt = r_mkt.json()
        print(f"  Bid: {mkt.get('bid')}, Ask: {mkt.get('ask')}, Age: {mkt.get('age_seconds')}s")

    # 4. Risk Gate decision
    print("\n=== 4. LIVE RISK GATE DECISION ===")
    r_risk = client.get(f"/risk/{target.id}/decision")
    if r_risk.status_code == 200:
        rg = r_risk.json()
        print(f"  Decision: {rg.get('decision')}, Reason Code: {rg.get('reason_code')}")

    # 5. Kill Switch Verification
    print("\n=== 5. KILL SWITCH VERIFICATION ===")
    r_arm = client.post(f"/accounts/{target.id}/strategy/kill-switch", json={"active": True})
    print(f"Arm KS: {r_arm.status_code}")
    rg_armed = client.get(f"/risk/{target.id}/decision").json()
    print(f"Risk gate ARMED: {rg_armed.get('decision')} / {rg_armed.get('reason_code')}")
    assert rg_armed.get("decision") == "BLOCK" and rg_armed.get("reason_code") == "KILL_SWITCH_ACTIVE"

    r_disarm = client.post(f"/accounts/{target.id}/strategy/kill-switch", json={"active": False})
    print(f"Disarm KS: {r_disarm.status_code}")
    rg_disarmed = client.get(f"/risk/{target.id}/decision").json()
    print(f"Risk gate DISARMED: {rg_disarmed.get('decision')} / {rg_disarmed.get('reason_code')}")
    assert rg_disarmed.get("reason_code") != "KILL_SWITCH_ACTIVE"

    s_after = client.get(f"/accounts/{target.id}/strategy").json()
    print(f"Strategy enabled after disarm: {s_after.get('enabled')}")
    assert s_after.get("enabled") is False

    print("\n=== ALL VERIFICATION CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(run_verification())
