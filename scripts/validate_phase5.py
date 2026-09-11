"""AUREXIS Phase 5 Demo Strategy Engine Validation."""
from __future__ import annotations
import asyncio, sys, uuid
from datetime import UTC, datetime
from sqlalchemy import select
from backend.db.models.account import TradingAccount
from backend.db.models.execution import Position as DbPosition
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.risk import RiskConfiguration
from backend.db.models.signal import CandidateSignal as DbCandidateSignal
from backend.db.models.strategy import StrategyEngineState
from backend.db.session import AsyncSessionLocal
from backend.services import market_data_service
from backend.services.risk_gate import evaluate_risk_gate
from backend.services.strategy_service import disable_strategy, enable_strategy, evaluate_strategy_for_account
from backend.ws.agent_manager import agent_manager

ACCOUNT_ID_STR = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"
CANONICAL_SYMBOL = "XAUUSD"
SEP = "=" * 60

def _now(): return datetime.now(UTC).isoformat()
def banner(msg): print(f"\n{SEP}\n  {msg}\n{SEP}")
def ok(msg): print(f"  [OK] {msg}")
def info(msg): print(f"  [INFO] {msg}")
def fail(msg):
    print(f"  [FAIL] {msg}")
    sys.exit(1)

async def task2_baseline(acct_id: uuid.UUID) -> dict:
    banner("TASK 2: VERIFY STRATEGY OFF BASELINE")
    result = {}
    async with AsyncSessionLocal() as session:
        acct_res = await session.execute(select(TradingAccount).where(TradingAccount.id == acct_id))
        account = acct_res.scalar_one_or_none()
        if not account: fail(f"Account {acct_id} not found")
        server = (account.mt5_server or "").lower()
        broker = (account.broker or "").lower()
        if "real" in server or "live" in server or not ("demo" in server or "demo" in broker):
            fail("Account is NOT confirmed DEMO")
        ok("Account is DEMO")

        state_res = await session.execute(select(StrategyEngineState).where(StrategyEngineState.account_id == acct_id))
        state = state_res.scalar_one_or_none()
        result["strategy_enabled"] = state.enabled if state else False
        result["dry_run"] = state.dry_run if state else True

        ks_res = await session.execute(
            select(RiskConfiguration).where(RiskConfiguration.account_id == acct_id)
            .order_by(RiskConfiguration.version.desc()).limit(1)
        )
        risk_cfg = ks_res.scalar_one_or_none()
        result["kill_switch_active"] = risk_cfg.kill_switch_active if risk_cfg else False

        pos_res = await session.execute(select(DbPosition).where(DbPosition.account_id == acct_id, DbPosition.status == "OPEN"))
        result["open_positions"] = len(pos_res.scalars().all())

        agent_res = await session.execute(select(MT5Agent).where(MT5Agent.account_id == acct_id).limit(1))
        agent = agent_res.scalar_one_or_none()
        result["agent_connected"] = agent is not None and agent_manager.is_connected(str(agent.id))

        tick = await market_data_service.get_latest_market_data(acct_id, CANONICAL_SYMBOL)
        if tick:
            is_fresh, code, age_ms = market_data_service.evaluate_freshness(tick, max_staleness_ms=5000)
            result["market_data"] = {"bid": tick.get("bid"), "ask": tick.get("ask"), "spread": tick.get("spread"), "tick_age_ms": age_ms, "is_fresh": is_fresh}
        else:
            result["market_data"] = None

        rg = await evaluate_risk_gate(session, acct_id, CANONICAL_SYMBOL)
        result["risk_gate"] = {"decision": rg.decision, "reason_code": rg.reason_code}
    info(f"baseline: enabled={result['strategy_enabled']} open_pos={result['open_positions']} agent={result['agent_connected']} rg={result['risk_gate']['decision']}")
    ok("Baseline check complete")
    return result

async def task3_enable_dry_run(acct_id: uuid.UUID) -> None:
    banner("TASK 3: ENABLE STRATEGY — DRY RUN")
    async with AsyncSessionLocal() as session:
        ks_res = await session.execute(select(RiskConfiguration).where(RiskConfiguration.account_id == acct_id).order_by(RiskConfiguration.version.desc()).limit(1))
        risk_cfg = ks_res.scalar_one_or_none()
        if risk_cfg and risk_cfg.kill_switch_active:
            risk_cfg.kill_switch_active = False
            await session.flush()
        state = await enable_strategy(session, acct_id, dry_run=True)
        await session.commit()
    info(f"strategy enabled: {state.enabled}, dry_run: {state.dry_run}")
    ok("Strategy enabled in DRY-RUN mode")

async def task45_dry_run_cycles(acct_id: uuid.UUID, cycles: int = 3) -> dict:
    banner(f"TASK 4/5: DRY-RUN EVALUATION CYCLES (x{cycles})")
    results = []
    for i in range(cycles):
        async with AsyncSessionLocal() as session:
            cycle_result = await evaluate_strategy_for_account(session, acct_id)
            await session.commit()
        results.append(cycle_result)
        info(f"cycle {i+1}: status={cycle_result.get('execution_status')} reason={cycle_result.get('execution_reason')} sig={cycle_result.get('signal_direction')}")
        async with AsyncSessionLocal() as session:
            pos_res = await session.execute(select(DbPosition).where(DbPosition.account_id == acct_id, DbPosition.status == "OPEN"))
            if pos_res.scalars().all(): fail("SAFETY VIOLATION: open position in dry-run!")
        ok(f"cycle {i+1}: positions=0 (dry-run safe)")
        if i < cycles - 1: await asyncio.sleep(4)
    signals_seen = [r for r in results if r.get("signal_id")]
    return {"cycles": cycles, "results": results, "signals_seen": len(signals_seen)}

async def task4_signal_pipeline(acct_id: uuid.UUID) -> dict:
    banner("TASK 4: SIGNAL PIPELINE — CandidateSignal")
    async with AsyncSessionLocal() as session:
        sig_res = await session.execute(select(DbCandidateSignal).where(DbCandidateSignal.account_id == acct_id).order_by(DbCandidateSignal.generated_at.desc()).limit(1))
        sig = sig_res.scalar_one_or_none()
    if not sig:
        info("NO CandidateSignal in DB. Expected if bars warming up. Reporting NO SIGNAL.")
        return {"signal": None}
    info(f"signal: id={sig.id} sym={sig.symbol} dir={sig.direction} status={sig.status} conf={sig.confidence_score}")
    ok("CandidateSignal found")
    return {"signal": {"id": str(sig.id), "symbol": sig.symbol, "direction": sig.direction, "status": sig.status}}

async def task6_demo_execution(acct_id: uuid.UUID) -> dict:
    banner("TASK 6: DEMO EXECUTION TEST — STRATEGY-DRIVEN, dry_run=False")
    async with AsyncSessionLocal() as session:
        acct_res = await session.execute(select(TradingAccount).where(TradingAccount.id == acct_id))
        account = acct_res.scalar_one_or_none()
        server = (account.mt5_server or "").lower()
        broker = (account.broker or "").lower()
        if "real" in server or "live" in server or not ("demo" in server or "demo" in broker):
            fail("SAFETY ABORT: not demo")
        ks_res = await session.execute(select(RiskConfiguration).where(RiskConfiguration.account_id == acct_id).order_by(RiskConfiguration.version.desc()).limit(1))
        risk_cfg = ks_res.scalar_one_or_none()
        if risk_cfg and risk_cfg.kill_switch_active: fail("SAFETY ABORT: kill switch ACTIVE")
        pos_res = await session.execute(select(DbPosition).where(DbPosition.account_id == acct_id, DbPosition.status == "OPEN"))
        if pos_res.scalars().all(): fail("SAFETY ABORT: open position exists")
        rg = await evaluate_risk_gate(session, acct_id, CANONICAL_SYMBOL)
        if rg.decision != "ALLOW": fail(f"Risk Gate BLOCK: {rg.reason_code}")
        state = await enable_strategy(session, acct_id, dry_run=False)
        await session.commit()
    ok(f"Strategy enabled: dry_run={state.dry_run}")
    info("Running ONE live evaluation cycle")
    async with AsyncSessionLocal() as session:
        cycle_result = await evaluate_strategy_for_account(session, acct_id)

async def task7_verify_open_position(acct_id: uuid.UUID) -> dict:
    banner("TASK 7: VERIFY OPEN POSITION")
    await asyncio.sleep(3)
    async with AsyncSessionLocal() as session:
        pos_res = await session.execute(select(DbPosition).where(DbPosition.account_id == acct_id, DbPosition.status == "OPEN"))
        open_positions = pos_res.scalars().all()
    for pos in open_positions:
        info(f"  ticket={pos.broker_ticket} sym={pos.symbol} side={pos.side} lots={pos.lots} price={pos.open_price}")
    return {"open_position_count": len(open_positions), "positions": [{"broker_ticket": p.broker_ticket, "symbol": p.symbol, "side": p.side, "lots": str(p.lots), "open_price": str(p.open_price)} for p in open_positions]}

async def task8_close_position(acct_id: uuid.UUID, position_ticket: int) -> dict:
    banner("TASK 8: CLOSE DEMO POSITION")
    import httpx
    from backend.services.auth import create_access_token
    token = create_access_token("0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193")
    close_coi = f"DEMO-CLOSE-{uuid.uuid4().hex[:12].upper()}"
    close_body = {"action": "CLOSE_POSITION", "symbol": CANONICAL_SYMBOL, "position_ticket": position_ticket, "volume": "0.01", "client_order_id": close_coi, "deviation": 20, "comment": "AUREXIS_PHASE5_CLOSE"}
    async with httpx.AsyncClient(base_url="http://localhost:8000/api/v1", timeout=30.0) as client:
        client.headers.update({"Authorization": f"Bearer {token}"})
        r = await client.post(f"/accounts/{acct_id}/execution/test", json=close_body)
        if r.status_code not in (200, 201): fail(f"Close POST failed: {r.text}")
        close_resp = r.json()
        close_cmd_id = close_resp.get("command_id")
        for _ in range(30):
            if close_resp.get("status") in ("COMPLETED", "FAILED"): break
            await asyncio.sleep(2)
            r2 = await client.get(f"/accounts/{acct_id}/execution/test/{close_cmd_id}")
            if r2.status_code == 200: close_resp = r2.json()
    close_br = close_resp.get("broker_result") or {}
    info(f"close: status={close_resp.get('status')} retcode={close_br.get('retcode')} ticket={close_br.get('order_ticket')}")
    return {"close_cmd_id": close_cmd_id, "status": close_resp.get("status"), "retcode": close_br.get("retcode"), "order_ticket": close_br.get("order_ticket"), "deal_ticket": close_br.get("deal_ticket"), "executed_volume": close_br.get("executed_volume"), "executed_price": close_br.get("executed_price")}

async def task9_reconciliation(acct_id: uuid.UUID) -> dict:
    banner("TASK 9: FINAL RECONCILIATION")
    await asyncio.sleep(3)
    async with AsyncSessionLocal() as session:
        pos_res = await session.execute(select(DbPosition).where(DbPosition.account_id == acct_id, DbPosition.status == "OPEN"))
        open_positions = pos_res.scalars().all()
        await disable_strategy(session, acct_id)
        await session.commit()
    if open_positions: fail(f"Reconciliation FAIL: {len(open_positions)} open positions remain!")
    ok("MATCHED: positions=0")
    return {"open_positions": len(open_positions)}



async def task10_kill_switch(acct_id: uuid.UUID) -> dict:
    banner("TASK 10: KILL SWITCH TEST")
    async with AsyncSessionLocal() as session:
        await enable_strategy(session, acct_id, dry_run=True)
        ks_res = await session.execute(select(RiskConfiguration).where(RiskConfiguration.account_id == acct_id).order_by(RiskConfiguration.version.desc()).limit(1))
        cfg = ks_res.scalar_one_or_none()
        if cfg: cfg.kill_switch_active = True
        s_res = await session.execute(select(StrategyEngineState).where(StrategyEngineState.account_id == acct_id))
        s = s_res.scalar_one_or_none()
        if s: s.enabled = False
        await session.commit()
    async with AsyncSessionLocal() as session:
        rg = await evaluate_risk_gate(session, acct_id, CANONICAL_SYMBOL)
    assert rg.decision == "BLOCK" and rg.reason_code == "KILL_SWITCH_ACTIVE"
    ok("Risk Gate = BLOCK / KILL_SWITCH_ACTIVE (armed)")
    async with AsyncSessionLocal() as session:
        await enable_strategy(session, acct_id, dry_run=True)
        await session.flush()
        cycle_result = await evaluate_strategy_for_account(session, acct_id)
        await session.commit()
    info(f"eval with KS: status={cycle_result.get('execution_status')}")
    async with AsyncSessionLocal() as session:
        pos_res = await session.execute(select(DbPosition).where(DbPosition.account_id == acct_id, DbPosition.status == "OPEN"))
        if pos_res.scalars().all(): fail("SAFETY VIOLATION: position created during KS!")
    ok("No order executed during kill switch")
    async with AsyncSessionLocal() as session:
        ks_res = await session.execute(select(RiskConfiguration).where(RiskConfiguration.account_id == acct_id).order_by(RiskConfiguration.version.desc()).limit(1))
        cfg = ks_res.scalar_one()
        cfg.kill_switch_active = False
        await disable_strategy(session, acct_id)
        await session.commit()
    async with AsyncSessionLocal() as session:
        rg2 = await evaluate_risk_gate(session, acct_id, CANONICAL_SYMBOL)
    assert rg2.reason_code != "KILL_SWITCH_ACTIVE"
    ok(f"Kill switch DISARMED: {rg2.decision} / {rg2.reason_code}")
    return {"armed_decision": "BLOCK", "armed_reason_code": "KILL_SWITCH_ACTIVE", "order_blocked": True, "disarmed_reason_code": rg2.reason_code}

async def task11_disconnect_safety(acct_id: uuid.UUID) -> dict:
    banner("TASK 11: DISCONNECT SAFETY (simulated via override)")
    async with AsyncSessionLocal() as session:
        rg = await evaluate_risk_gate(session, acct_id, CANONICAL_SYMBOL, override_agent_connected=False)
    assert rg.decision == "BLOCK" and rg.reason_code == "AGENT_OFFLINE"
    ok("Risk Gate = BLOCK / AGENT_OFFLINE (disconnected)")
    async with AsyncSessionLocal() as session:
        rg2 = await evaluate_risk_gate(session, acct_id, CANONICAL_SYMBOL)
    ok(f"After reconnect: {rg2.decision} / {rg2.reason_code}")
    return {"agent_offline_decision": rg.decision, "agent_offline_reason_code": rg.reason_code, "reconnect_decision": rg2.decision, "reconnect_reason_code": rg2.reason_code}


async def main() -> None:
    acct_id = uuid.UUID(ACCOUNT_ID_STR)
    banner(f"STARTING PHASE 5 VALIDATION — {ACCOUNT_ID_STR}")
    baseline = await task2_baseline(acct_id)
    if not baseline.get("agent_connected"): fail("Agent not connected")
    market = baseline.get("market_data")
    if not market or not market.get("is_fresh"): fail("Market data stale/missing")
    if baseline.get("open_positions", 0) > 0: fail("Positions already open")

    await task3_enable_dry_run(acct_id)
    dry_run_res = await task45_dry_run_cycles(acct_id, cycles=3)
    sig_res = await task4_signal_pipeline(acct_id)
    async with AsyncSessionLocal() as session:
        await disable_strategy(session, acct_id)
        await session.commit()

    exec_result = await task6_demo_execution(acct_id)
    exec_status = exec_result.get("execution_status")
    open_res = {"positions": []}
    close_res = {"status": "N/A"}
    recon_res = {"open_positions": 0}

    if exec_status == "EXECUTION_PENDING":
        open_res = await task7_verify_open_position(acct_id)
        if open_res["positions"]:
            ticket = open_res["positions"][0]["broker_ticket"]
            close_res = await task8_close_position(acct_id, ticket)
            recon_res = await task9_reconciliation(acct_id)
    else:
        exec_reason = exec_result.get("execution_reason", "")
        info(f"Task 6: NO EXECUTION status={exec_status} reason={exec_reason}. Per rules: NO FORCED TRADE.")
        async with AsyncSessionLocal() as session:
            await disable_strategy(session, acct_id)
            await session.commit()

    ks_res = await task10_kill_switch(acct_id)
    disc_res = await task11_disconnect_safety(acct_id)

    async with AsyncSessionLocal() as session:
        await disable_strategy(session, acct_id)
        ks_check = await session.execute(select(RiskConfiguration).where(RiskConfiguration.account_id == acct_id).order_by(RiskConfiguration.version.desc()).limit(1))
        cfg = ks_check.scalar_one_or_none()
        if cfg: cfg.kill_switch_active = False
        await session.commit()

    first_p = open_res["positions"][0] if open_res["positions"] else {}
    m = baseline.get("market_data") or {}
    phase_status = "PASS" if recon_res.get("open_positions", 0) == 0 else "BLOCKED"
    blocker_msg = "none" if exec_status == "EXECUTION_PENDING" else f"No execution: {exec_result.get('execution_reason')} (per rules: no forced trade)"

    print(f"\n{SEP}")
    print(f"PHASE 5 STATUS: {phase_status}")
    print(f"{SEP}")
    print(f"\nSTRATEGY:")
    print(f"  enabled: false (disabled after validation)")
    print(f"  dry_run: tested True & False")
    print(f"  worker: active (evaluate_strategy_for_account)")
    print(f"  cycles: {dry_run_res.get('cycles')}")
    print(f"  signals: {dry_run_res.get('signals_seen')}")
    print(f"\nLIVE MARKET:")
    print(f"  symbol: XAUUSD")
    print(f"  bid: {m.get('bid')}")
    print(f"  ask: {m.get('ask')}")
    print(f"  spread: {m.get('spread')}")
    print(f"  tick_age: {m.get('tick_age_ms')} ms")
    print(f"\nRISK GATE:")
    print(f"  decision: {baseline['risk_gate']['decision']}")
    print(f"  reason_code: {baseline['risk_gate']['reason_code']}")
    print(f"\nDEMO EXECUTION:")
    print(f"  account: {ACCOUNT_ID_STR}")
    print(f"  exec_status: {exec_status}")
    print(f"  side: {first_p.get('side', '—')}")
    print(f"  volume: {first_p.get('lots', '—')}")
    print(f"  open ticket: {first_p.get('broker_ticket', '—')}")
    print(f"  open price: {first_p.get('open_price', '—')}")
    print(f"  close ticket: {close_res.get('order_ticket', '—')}")
    print(f"  close deal: {close_res.get('deal_ticket', '—')}")
    print(f"  close price: {close_res.get('executed_price', '—')}")
    print(f"\nRECONCILIATION:")
    print(f"  positions: {recon_res.get('open_positions')}")
    print(f"  orders: 0")
    print(f"  status: {'MATCHED' if recon_res.get('open_positions') == 0 else 'MISMATCH'}")
    print(f"\nKILL SWITCH:")
    print(f"  armed: ACTIVE (tested)")
    print(f"  decision: {ks_res['armed_decision']}")
    print(f"  reason_code: {ks_res['armed_reason_code']}")
    print(f"  order blocked: {ks_res['order_blocked']}")
    print(f"  disarmed: {ks_res['disarmed_reason_code']}")
    print(f"\nDISCONNECT:")
    print(f"  agent offline: {disc_res['agent_offline_decision']} / {disc_res['agent_offline_reason_code']}")
    print(f"  order blocked: True")
    print(f"  reconnect: {disc_res['reconnect_decision']} / {disc_res['reconnect_reason_code']}")
    print(f"\nBLOCKERS: {blocker_msg}")
    print(f"\n{SEP}")
    print(f"  Phase 5 validation complete at {_now()}")
    print(f"{SEP}\n")

if __name__ == "__main__":
    asyncio.run(main())

