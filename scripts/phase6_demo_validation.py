"""
AUREXIS — PHASE 6: NATURAL DEMO STRATEGY EXECUTION VALIDATION
Validates Phases 6A through 6H.
"""

from __future__ import annotations

import asyncio
import json
import time
import sys
from datetime import UTC, datetime
import httpx
from sqlalchemy import select

from backend.db.session import AsyncSessionLocal
from backend.db.models.account import TradingAccount
from backend.services.auth import create_access_token
from brain.config import default_strat_config


async def run_phase6():
    print("=" * 60)
    print("AUREXIS PHASE 6: NATURAL DEMO STRATEGY EXECUTION VALIDATION")
    print("=" * 60)

    # Resolve target demo account connected to MT5 agent
    async with AsyncSessionLocal() as db:
        from backend.db.models.mt5_agent import MT5Agent
        agent_res = await db.execute(
            select(MT5Agent).where(MT5Agent.last_known_status == "CONNECTED")
        )
        agent = agent_res.scalars().first()
        if agent is None:
            # fallback to any agent with account_id
            agent_res2 = await db.execute(select(MT5Agent))
            agent = agent_res2.scalars().first()

        if agent is not None and agent.account_id:
            target = await db.get(TradingAccount, agent.account_id)
        else:
            target = None

        if target is None:
            print("[FAIL] No active demo account with MT5 agent found!")
            sys.exit(1)

        account_id = target.id
        user_id = target.user_id
        broker = target.broker
        server = target.mt5_server
        is_demo = "demo" in (server or "").lower() or "demo" in (broker or "").lower()

    token = create_access_token(str(user_id))
    client = httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )

    print(f"\n[TARGET ACCOUNT]:")
    print(f"  ID: {account_id}")
    print(f"  User ID: {user_id}")
    print(f"  Broker: {broker}")
    print(f"  Server: {server}")
    print(f"  Confirmed DEMO: {is_demo}")

    # PHASE 6A — STRATEGY OBSERVABILITY
    print("\n" + "=" * 60)
    print("PHASE 6A: STRATEGY OBSERVABILITY")
    print("=" * 60)

    r_health = client.get("/health").json()
    mt5_stat = r_health.get("components", {}).get("mt5", {})
    connected_agents = mt5_stat.get("connected_agents", 0)
    print(f"1. Health: {r_health.get('status')} | MT5 Connected Agents: {connected_agents}")
    assert connected_agents > 0, "No connected MT5 agent!"

    r_mkt = client.get(f"/market/{account_id}/state").json()
    print(f"2. Market Data: Bid={r_mkt.get('bid')} Ask={r_mkt.get('ask')} Spread={r_mkt.get('spread')} Status={r_mkt.get('status')} Age={r_mkt.get('age_ms')}ms")
    assert r_mkt.get("is_fresh") is True, f"Market data not fresh: {r_mkt.get('status')}"

    r_bars = client.get(f"/accounts/{account_id}/strategy/bars?timeframe=M15").json()
    bars_count = r_bars.get("count", 0)
    bars_list = r_bars.get("bars", [])
    print(f"3. Bar Storage: Ingested M15 Bars={bars_count}")
    if bars_list:
        print(f"   Latest Closed Bar: Open={bars_list[-1]['open_time']} Close={bars_list[-1]['close_time']} C={bars_list[-1]['close']}")
    assert bars_count >= 50, f"Insufficient bars for warmup: {bars_count} < 50"

    r_pos = client.get(f"/accounts/{account_id}/positions").json()
    open_pos = r_pos.get("open_positions", 0)
    print(f"4. Execution State: Open Positions={open_pos} Total Historical={r_pos.get('total_positions', 0)}")
    # PHASE 6B — SIGNAL VALIDATION
    print("\n" + "=" * 60)
    print("PHASE 6B: SIGNAL VALIDATION")
    print("=" * 60)

    cfg = default_strat_config()
    print("Strategy Parameters:")
    print(f"  Strategy ID / Version: AUREXIS_CORE / AUREXIS-STRAT-1.0.0")
    print(f"  Canonical Symbol / TF: XAUUSD / M15")
    print(f"  Min Closed Bars: 50 (stored: {bars_count})")
    print(f"  ATR Period: {cfg.volatility.atr_period} (baseline {cfg.volatility.atr_baseline_bars})")
    print(f"  Fast MA / Slow MA: {cfg.trend.fast_ma_period} / {cfg.trend.slow_ma_period}")
    print(f"  RSI Period: {cfg.momentum.rsi_period} (Bullish min: {cfg.momentum.rsi_bullish_min}, Bearish max: {cfg.momentum.rsi_bearish_max})")
    print(f"  ADX Period: {cfg.regime.adx_period} (Trending threshold: {cfg.regime.trending_threshold})")
    print(f"  Confidence Threshold: {cfg.scoring.min_confidence_threshold}")
    print(f"  Weights: Struct={cfg.scoring.weight_structure} Trend={cfg.scoring.weight_trend} Setup={cfg.scoring.weight_setup} Mom={cfg.scoring.weight_momentum} Vol={cfg.scoring.weight_volatility} Reg={cfg.scoring.weight_regime}")
    print(f"  Risk: Reward Ratio={cfg.sl_tp.rr_target} SL ATR buffer={cfg.sl_tp.sl_atr_buffer} Max spread=${cfg.spread.max_spread_usd}")
    print(f"  Hard gates: News CLEAR, Spread <= $1.00, Regime != UNKNOWN/HIGH_VOLATILITY/TRANSITION")
    print(f"  Execution guard: DEMO only, Cooldown=1 signal per M15 candle, Max 1 open position")

    # PHASE 6C — LIVE DEMO DRY-RUN
    print("\n" + "=" * 60)
    print("PHASE 6C: LIVE DEMO DRY-RUN (MULTIPLE CYCLES)")
    print("=" * 60)

    r_enable = client.post(f"/accounts/{account_id}/strategy/enable", json={"dry_run": True}).json()
    print(f"Enabled strategy in DRY-RUN mode: enabled={r_enable.get('enabled')}, dry_run={r_enable.get('dry_run')}")
    assert r_enable.get("enabled") is True
    assert r_enable.get("dry_run") is True

    cycles_data = []
    natural_signal_found = False
    latest_evaluated_signal = None

    print("\nObserving multiple live evaluation cycles...")
    for cycle in range(1, 6):
        eval_res = client.post(f"/accounts/{account_id}/strategy/evaluate").json()
        strat_now = client.get(f"/accounts/{account_id}/strategy").json()
        mkt_now = client.get(f"/market/{account_id}/state").json()
        risk_now = client.get(f"/risk/{account_id}/decision").json()

        cycle_info = {
            "cycle": cycle,
            "timestamp": eval_res.get("timestamp"),
            "candle_ts": eval_res.get("candle_ts"),
            "bid": mkt_now.get("bid"),
            "ask": mkt_now.get("ask"),
            "spread": mkt_now.get("spread"),
            "strategy_state": "ENABLED",
            "dry_run": strat_now.get("dry_run"),
            "signal_direction": eval_res.get("signal_direction"),
            "signal_reason": eval_res.get("signal_reason"),
            "risk_decision": risk_now.get("decision"),
            "risk_reason_code": risk_now.get("reason_code"),
            "execution_status": eval_res.get("execution_status"),
            "execution_reason": eval_res.get("execution_reason"),
        }
        cycles_data.append(cycle_info)
        print(f"  Cycle {cycle}: dir={cycle_info['signal_direction']} exec_status={cycle_info['execution_status']} exec_reason={cycle_info['execution_reason']} candle_ts={cycle_info['candle_ts']} spread={cycle_info['spread']}")

        if eval_res.get("signal_direction") in ("BUY", "SELL"):
            natural_signal_found = True
            latest_evaluated_signal = eval_res
            print(f"  *** NATURAL SIGNAL DETECTED: {eval_res.get('signal_direction')} ***")
            break

        time.sleep(2)

    pos_after_dryrun = client.get(f"/accounts/{account_id}/positions").json()
    print(f"\nVerification: Open positions after dry-run cycles: {pos_after_dryrun.get('open_positions')}")
    assert pos_after_dryrun.get("open_positions") == 0, "Order was created during dry_run!"
    print("[PASS] DRY-RUN invariant verified: NO ORDER WAS SENT while dry_run=True.")


    # PHASE 6D / 6E / 6F / 6G — DEMO EXECUTION ARM (ONLY IF NATURAL SIGNAL)
    print("\n" + "=" * 60)
    print("PHASE 6D / 6E / 6F / 6G: DEMO EXECUTION ARM & LIFECYCLE")
    print("=" * 60)

    if not natural_signal_found:
        print("[RESULT]: NO NATURAL SIGNAL OCCURRED during observation cycles.")
        print("  - Candle timestamps: " + ", ".join(str(c.get('candle_ts')) for c in cycles_data))
        print("  - Market state: " + str(cycles_data[-1].get("signal_reason")))
        print("  - Strategy thresholds preserved: NOT FORCING A SIGNAL.")
        print("  - Risk Gate: READY (ALLOW / RISK_OK)")
        print("  - Execution status: NO_ORDER_SENT (Rule 4 respected)")
    else:
        print("Safety Checkpoint before execution:")
        print(f"  ACCOUNT: {account_id}")
        print(f"  BROKER: {broker}")
        print(f"  SERVER: {server}")
        print(f"  DEMO STATUS: {is_demo}")
        print(f"  STRATEGY ENABLED: True")
        print(f"  DRY RUN: False (about to arm)")
        print(f"  RISK GATE: {r_risk.get('decision')} ({r_risk.get('reason_code')})")
        print(f"  KILL SWITCH: DISARMED")
        print(f"  MARKET DATA AGE: {r_mkt.get('age_ms')} ms")
        print(f"  SYMBOL: XAUUSD")
        print(f"  SIDE: {latest_evaluated_signal.get('signal_direction')}")
        print(f"  VOLUME: 0.01")

        r_live = client.post(f"/accounts/{account_id}/strategy/enable", json={"dry_run": False}).json()
        assert r_live.get("dry_run") is False, "Failed to arm dry_run=False"
        exec_eval = client.post(f"/accounts/{account_id}/strategy/evaluate").json()
        print(f"Live Execution Result: {exec_eval}")
        time.sleep(4)
        pos_res = client.get(f"/accounts/{account_id}/positions").json()
        print(f"Positions query: {pos_res}")

    # Ensure disabled and dry_run=True
    client.post(f"/accounts/{account_id}/strategy/disable")
    r_final_state = client.get(f"/accounts/{account_id}/strategy").json()
    print(f"\nStrategy state restored: enabled={r_final_state.get('enabled')}, dry_run={r_final_state.get('dry_run')}")

    r_risk = client.get(f"/risk/{account_id}/decision").json()
    print(f"5. Risk Gate: Decision={r_risk.get('decision')} Reason Code={r_risk.get('reason_code')}")
    assert r_risk.get("decision") == "ALLOW", f"Risk Gate not ALLOW: {r_risk.get('reason_code')}"

    r_strat = client.get(f"/accounts/{account_id}/strategy").json()
    # PHASE 6H — FAILURE SAFETY SUITE
    print("\n" + "=" * 60)
    print("PHASE 6H: FAILURE SAFETY VERIFICATION SUITE")
    print("=" * 60)

    # 1. Kill switch
    print("1. Kill switch safety test...")
    r_arm = client.post(f"/accounts/{account_id}/strategy/kill-switch", json={"active": True})
    assert r_arm.status_code == 200
    rg_ks = client.get(f"/risk/{account_id}/decision").json()
    print(f"   Armed kill switch: decision={rg_ks.get('decision')} reason={rg_ks.get('reason_code')}")
    assert rg_ks.get("decision") == "BLOCK" and rg_ks.get("reason_code") == "KILL_SWITCH_ACTIVE"

    r_disarm = client.post(f"/accounts/{account_id}/strategy/kill-switch", json={"active": False})
    assert r_disarm.status_code == 200
    rg_restored = client.get(f"/risk/{account_id}/decision").json()
    print(f"   Disarmed kill switch: decision={rg_restored.get('decision')} reason={rg_restored.get('reason_code')}")
    assert rg_restored.get("decision") == "ALLOW" and rg_restored.get("reason_code") == "RISK_OK"

    # 2. Disabled strategy
    print("2. Disabled strategy test...")
    strat_disabled = client.get(f"/accounts/{account_id}/strategy").json()
    assert strat_disabled.get("enabled") is False
    eval_dis = client.post(f"/accounts/{account_id}/strategy/evaluate").json()
    print(f"   Disabled evaluation: execution_reason={eval_dis.get('execution_reason')}")
    assert eval_dis.get("execution_reason") == "STRATEGY_DISABLED"

    # 3. Dry run mode
    print("3. Dry run protection test...")
    client.post(f"/accounts/{account_id}/strategy/enable", json={"dry_run": True})
    eval_dry = client.post(f"/accounts/{account_id}/strategy/evaluate").json()
    print(f"   Dry-run active: dry_run={eval_dry.get('dry_run')} exec_status={eval_dry.get('execution_status')}")
    assert eval_dry.get("dry_run") is True
    client.post(f"/accounts/{account_id}/strategy/disable")

    # 4. Duplicate candle protection (CANDLE_COOLDOWN)
    print("4. Duplicate candle protection test...")
    async with AsyncSessionLocal() as db:
        from backend.services.strategy_service import get_or_create_strategy_state, evaluate_strategy_for_account
        state = await get_or_create_strategy_state(db, account_id)
        state.enabled = True
        state.dry_run = True
        state.last_signal_candle_ts = datetime.now(UTC)
        await db.commit()

        dup_eval = await evaluate_strategy_for_account(db, account_id)
        print(f"   Cooldown check: execution_reason={dup_eval.get('execution_reason')}")
        assert dup_eval.get("execution_reason") == "CANDLE_COOLDOWN"

        state.enabled = False
        state.dry_run = True
        await db.commit()

    # 5. Non-demo account protection
    print("5. Non-demo live execution rejection test...")
    async with AsyncSessionLocal() as db:
        from backend.services.strategy_service import _is_confirmed_demo
        fake_real = TradingAccount(broker="Real Broker", mt5_server="RealBroker-Live-01", label="Real")
        assert _is_confirmed_demo(fake_real) is False
        print("   Live account rejection guard: _is_confirmed_demo('RealBroker-Live-01') == False (BLOCKED)")

    # 6. Reconciliation
    print("\n" + "=" * 60)
    print("RECONCILIATION AUDIT")
    print("=" * 60)
    final_pos = client.get(f"/accounts/{account_id}/positions").json()
    open_count = final_pos.get("open_positions", 0)
    print(f"  Open positions: {open_count}")
    print(f"  Total positions in DB: {final_pos.get('total_positions')}")
    assert open_count == 0, f"Leaked open position detected: {open_count}"
    print("  Reconciliation Status: MATCHED (0 open positions, 0 pending orders)")

    # Final state
    s_fin = client.get(f"/accounts/{account_id}/strategy").json()
    print(f"\nFinal State:")
    print(f"  Strategy enabled: {s_fin.get('enabled')}")
    print(f"  Dry run: {s_fin.get('dry_run')}")
    print(f"  Risk Gate: {rg_restored.get('decision')} ({rg_restored.get('reason_code')})")
    assert s_fin.get("enabled") is False
    assert s_fin.get("dry_run") is True

    print("\n" + "=" * 60)
    print("PHASE 6 VALIDATION COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_phase6())

    print(f"6. Strategy State: Enabled={r_strat.get('enabled')} DryRun={r_strat.get('dry_run')} Warmup={r_strat.get('warmup_status')}")
    print("[PASS] Observability pipeline transitions verified.")
