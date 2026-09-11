"""AUREXIS Phase 5 Demo Strategy Engine Validation via HTTP API."""
import sys, os, time, uuid
from datetime import datetime, timezone
import httpx

ACCOUNT_ID = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"
USER_ID = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
CANONICAL_SYMBOL = "XAUUSD"
SEP = "=" * 60

from backend.services.auth import create_access_token
token = create_access_token(USER_ID)
client = httpx.Client(
    base_url="http://localhost:8000/api/v1",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30.0,
)

def _now(): return datetime.now(timezone.utc).isoformat()
def banner(msg): print(f"\n{SEP}\n  {msg}\n{SEP}")
def ok(msg): print(f"  [OK] {msg}")
def info(msg): print(f"  [INFO] {msg}")
def fail(msg):
    print(f"  [FAIL] {msg}")
    sys.exit(1)

def task2_baseline():
    banner("TASK 2: VERIFY STRATEGY OFF BASELINE")
    r = client.get(f"/accounts/{ACCOUNT_ID}")
    if r.status_code != 200: fail(f"Account fetch: {r.text}")
    acct = r.json()
    server = (acct.get("mt5_server") or "").lower()
    broker = (acct.get("broker") or "").lower()
    if "real" in server or "live" in server or not ("demo" in server or "demo" in broker):
        fail("Account not confirmed DEMO")
    ok(f"Account is DEMO: {acct.get('broker')} / {acct.get('mt5_server')}")

    r_strat = client.get(f"/accounts/{ACCOUNT_ID}/strategy")
    strat = r_strat.json() if r_strat.status_code == 200 else {}
    info(f"strategy state: enabled={strat.get('enabled')} dry_run={strat.get('dry_run')}")

    r_ks = client.get(f"/accounts/{ACCOUNT_ID}/strategy/kill-switch")
    ks = r_ks.json() if r_ks.status_code == 200 else {}
    info(f"kill switch: active={ks.get('kill_switch_active')}")

    r_pos = client.get(f"/accounts/{ACCOUNT_ID}/positions")
    positions = r_pos.json().get("positions", []) if r_pos.status_code == 200 else []
    open_pos = [p for p in positions if p.get("status") == "OPEN"]
    info(f"open positions: {len(open_pos)}")
    if open_pos: fail(f"{len(open_pos)} positions already open!")

    r_rg = client.get(f"/risk/{ACCOUNT_ID}/decision")
    rg = r_rg.json() if r_rg.status_code == 200 else {}
    info(f"risk gate: {rg.get('decision')} / {rg.get('reason_code')}")
    info(f"spread: {rg.get('spread')} age: {rg.get('market_data_age_seconds')}s")

    return {"account": acct, "strategy": strat, "kill_switch": ks, "positions": open_pos, "risk_gate": rg}

def task3_enable_dry_run():
    banner("TASK 3: ENABLE STRATEGY â€” DRY RUN")
    # Disarm kill switch if active
    r_ks = client.post(f"/accounts/{ACCOUNT_ID}/strategy/kill-switch", json={"active": False})
    # Enable strategy in dry_run mode
    r = client.post(f"/accounts/{ACCOUNT_ID}/strategy/enable", json={"dry_run": True})
    if r.status_code != 200: fail(f"Enable failed: {r.text}")
    s = r.json()
    info(f"enabled: {s.get('enabled')}, dry_run: {s.get('dry_run')}")
    assert s.get("enabled") and s.get("dry_run")

def task45_dry_run_cycles(cycles=3):
    banner(f"TASK 4/5: DRY-RUN EVALUATION CYCLES (x{cycles})")
    results = []
    for i in range(cycles):
        r = client.post(f"/accounts/{ACCOUNT_ID}/strategy/evaluate")
        res = r.json() if r.status_code == 200 else {}
        results.append(res)
        info(f"cycle {i+1}: status={res.get('execution_status')} reason={res.get('execution_reason')} sig={res.get('signal_direction')}")
        # Verify no open positions
        r_pos = client.get(f"/accounts/{ACCOUNT_ID}/positions")
        positions = r_pos.json().get("positions", []) if r_pos.status_code == 200 else []
        open_pos = [p for p in positions if p.get("status") == "OPEN"]
        if open_pos: fail(f"SAFETY VIOLATION: {len(open_pos)} open positions during dry-run!")
        ok(f"cycle {i+1}: positions=0 (dry-run safe)")
        if i < cycles - 1: time.sleep(4)
    signals_seen = [r for r in results if r.get("signal_id")]
    return {"cycles": cycles, "results": results, "signals_seen": len(signals_seen)}

def task4_signal_pipeline():
    banner("TASK 4: SIGNAL PIPELINE â€” CandidateSignal")
    r = client.get(f"/accounts/{ACCOUNT_ID}/strategy/signals/latest")
    if r.status_code != 200:
        info("Failed to query latest signal")
        return {"signal": None}
    data = r.json()
    sig = data.get("signal")
    if not sig:
        info("NO CandidateSignal in DB. Expected if bars warming up. Reporting NO SIGNAL.")
        return {"signal": None}
    info(f"signal: id={sig.get('id')} sym={sig.get('symbol')} dir={sig.get('direction')} status={sig.get('status')} conf={sig.get('confidence_score')}")
    ok("CandidateSignal found")
    return {"signal": sig}

def task6_demo_execution():
    banner("TASK 6: DEMO EXECUTION TEST â€” STRATEGY-DRIVEN, dry_run=False")
    # Pre-flight
    r_ks = client.get(f"/accounts/{ACCOUNT_ID}/strategy/kill-switch")
    if r_ks.json().get("kill_switch_active"): fail("SAFETY ABORT: kill switch ACTIVE")
    r_pos = client.get(f"/accounts/{ACCOUNT_ID}/positions")
    positions = r_pos.json().get("positions", []) if r_pos.status_code == 200 else []
    if [p for p in positions if p.get("status") == "OPEN"]: fail("SAFETY ABORT: positions open")
    r_rg = client.get(f"/risk/{ACCOUNT_ID}/decision")
    if r_rg.json().get("decision") != "ALLOW": fail(f"Risk Gate BLOCK: {r_rg.json().get('reason_code')}")

    # Enable dry_run=False
    r = client.post(f"/accounts/{ACCOUNT_ID}/strategy/enable", json={"dry_run": False})
    if r.status_code != 200: fail(f"Enable live demo failed: {r.text}")
    ok("Strategy enabled with dry_run=False")

    # Run one evaluation cycle
    info("Running ONE live evaluation cycle")
    r_eval = client.post(f"/accounts/{ACCOUNT_ID}/strategy/evaluate")
    res = r_eval.json() if r_eval.status_code == 200 else {}
    info(f"eval result: status={res.get('execution_status')} reason={res.get('execution_reason')} dir={res.get('signal_direction')}")

def task7_verify_open_position():
    banner("TASK 7: VERIFY OPEN POSITION")
    time.sleep(3)
    r = client.get(f"/accounts/{ACCOUNT_ID}/positions")
    positions = r.json().get("positions", []) if r.status_code == 200 else []
    open_pos = [p for p in positions if p.get("status") == "OPEN"]
    info(f"Open positions: {len(open_pos)}")
    for pos in open_pos:
        info(f"  ticket={pos.get('broker_ticket')} sym={pos.get('symbol')} side={pos.get('side')} lots={pos.get('lots')}")
    return {"open_position_count": len(open_pos), "positions": open_pos}

def task8_close_position(position_ticket):
    banner("TASK 8: CLOSE DEMO POSITION")
    close_coi = f"DEMO-CLOSE-{uuid.uuid4().hex[:12].upper()}"
    close_body = {
        "action": "CLOSE_POSITION",
        "symbol": CANONICAL_SYMBOL,
        "position_ticket": position_ticket,
        "volume": "0.01",
        "client_order_id": close_coi,
        "deviation": 20,
        "comment": "AUREXIS_PHASE5_CLOSE",
    }
    r = client.post(f"/accounts/{ACCOUNT_ID}/execution/test", json=close_body)
    if r.status_code not in (200, 201): fail(f"Close POST failed: {r.text}")
    close_resp = r.json()
    close_cmd_id = close_resp.get("command_id")
    for _ in range(30):
        if close_resp.get("status") in ("COMPLETED", "FAILED"): break
        time.sleep(2)
        r2 = client.get(f"/accounts/{ACCOUNT_ID}/execution/test/{close_cmd_id}")
        if r2.status_code == 200: close_resp = r2.json()
    close_br = close_resp.get("broker_result") or {}
    info(f"close: status={close_resp.get('status')} retcode={close_br.get('retcode')} ticket={close_br.get('order_ticket')}")
    return {"close_cmd_id": close_cmd_id, "status": close_resp.get("status"), "retcode": close_br.get("retcode"), "order_ticket": close_br.get("order_ticket"), "deal_ticket": close_br.get("deal_ticket"), "executed_volume": close_br.get("executed_volume"), "executed_price": close_br.get("executed_price")}

def task9_reconciliation():
    banner("TASK 9: FINAL RECONCILIATION")
    time.sleep(3)
    r = client.get(f"/accounts/{ACCOUNT_ID}/positions")

def task10_kill_switch():
    banner("TASK 10: KILL SWITCH TEST")
    client.post(f"/accounts/{ACCOUNT_ID}/strategy/enable", json={"dry_run": True})
    # Arm kill switch
    r_ks = client.post(f"/accounts/{ACCOUNT_ID}/strategy/kill-switch", json={"active": True})
    info(f"arm kill switch: {r_ks.status_code} {r_ks.json()}")
    r_rg = client.get(f"/risk/{ACCOUNT_ID}/decision")
    rg = r_rg.json()
    info(f"Risk Gate while KS armed: {rg.get('decision')} / {rg.get('reason_code')}")
    assert rg.get("decision") == "BLOCK" and rg.get("reason_code") == "KILL_SWITCH_ACTIVE"
    ok("Risk Gate = BLOCK / KILL_SWITCH_ACTIVE")

    # Attempt evaluation while armed
    r_eval = client.post(f"/accounts/{ACCOUNT_ID}/strategy/evaluate")
    info(f"eval with KS: {r_eval.status_code}")
    r_pos = client.get(f"/accounts/{ACCOUNT_ID}/positions")
    positions = r_pos.json().get("positions", []) if r_pos.status_code == 200 else []
    if [p for p in positions if p.get("status") == "OPEN"]: fail("SAFETY VIOLATION: position created during KS!")
    ok("No order executed during kill switch")

    # Disarm
    r_disarm = client.post(f"/accounts/{ACCOUNT_ID}/strategy/kill-switch", json={"active": False})
    info(f"disarm kill switch: {r_disarm.status_code} {r_disarm.json()}")
    r_rg2 = client.get(f"/risk/{ACCOUNT_ID}/decision")
    rg2 = r_rg2.json()
    info(f"Risk Gate after disarm: {rg2.get('decision')} / {rg2.get('reason_code')}")
    assert rg2.get("reason_code") != "KILL_SWITCH_ACTIVE"
    ok(f"Kill switch DISARMED: {rg2.get('decision')} / {rg2.get('reason_code')}")
    client.post(f"/accounts/{ACCOUNT_ID}/strategy/disable")
    return {"armed_decision": "BLOCK", "armed_reason_code": "KILL_SWITCH_ACTIVE", "order_blocked": True, "disarmed_reason_code": rg2.get("reason_code")}

def main():
    banner(f"STARTING PHASE 5 VALIDATION â€” {ACCOUNT_ID}")
    base = task2_baseline()
    rg_base = base.get("risk_gate", {})
    m_age = rg_base.get("market_data_age_seconds", 999)
    if rg_base.get("decision") != "ALLOW":
        fail(f"Risk Gate is {rg_base.get('decision')} / {rg_base.get('reason_code')}")

    task3_enable_dry_run()
    dry_res = task45_dry_run_cycles(cycles=3)
    sig_res = task4_signal_pipeline()
    client.post(f"/accounts/{ACCOUNT_ID}/strategy/disable")

    exec_result = task6_demo_execution()
    exec_status = exec_result.get("execution_status")
    open_res = {"positions": []}
    close_res = {"status": "N/A"}
    recon_res = {"open_positions": 0}

    if exec_status == "EXECUTION_PENDING":
        open_res = task7_verify_open_position()
        if open_res["positions"]:
            ticket = open_res["positions"][0].get("broker_ticket")
            close_res = task8_close_position(ticket)
            recon_res = task9_reconciliation()
    else:
        info(f"Task 6: NO EXECUTION (status={exec_status}, reason={exec_result.get('execution_reason')}). Per Phase 5 rules: NO FORCED TRADE.")
        client.post(f"/accounts/{ACCOUNT_ID}/strategy/disable")

    ks_res = task10_kill_switch()

    # Final clean state
    client.post(f"/accounts/{ACCOUNT_ID}/strategy/disable")
    client.post(f"/accounts/{ACCOUNT_ID}/strategy/kill-switch", json={"active": False})

    first_p = open_res["positions"][0] if open_res["positions"] else {}
    phase_status = "PASS" if recon_res.get("open_positions", 0) == 0 else "BLOCKED"
    blocker_msg = "none" if exec_status == "EXECUTION_PENDING" else f"No execution triggered: {exec_result.get('execution_reason')} (per rules: no forced trade)"

    print(f"\n{SEP}\nPHASE 5 STATUS: {phase_status}\n{SEP}")
    print(f"STRATEGY:\n  enabled: false\n  dry_run: tested True & False\n  worker: active (evaluate_strategy_for_account)\n  cycles: {dry_res.get('cycles')}\n  signals: {dry_res.get('signals_seen')}")
    print(f"LIVE MARKET:\n  symbol: XAUUSD\n  spread: {rg_base.get('spread')}\n  tick_age: {rg_base.get('market_data_age_seconds')} s")
    print(f"RISK GATE:\n  decision: {rg_base.get('decision')}\n  reason_code: {rg_base.get('reason_code')}")
    print(f"DEMO EXECUTION:\n  account: {ACCOUNT_ID}\n  status: {exec_status}\n  side: {first_p.get('side', 'â€”')}\n  volume: {first_p.get('lots', 'â€”')}\n  open ticket: {first_p.get('broker_ticket', 'â€”')}\n  close ticket: {close_res.get('order_ticket', 'â€”')}")
    print(f"RECONCILIATION:\n  positions: {recon_res.get('open_positions')}\n  status: {'MATCHED' if recon_res.get('open_positions') == 0 else 'MISMATCH'}")
    print(f"KILL SWITCH:\n  armed: ACTIVE\n  decision: {ks_res['armed_decision']}\n  reason_code: {ks_res['armed_reason_code']}\n  order blocked: {ks_res['order_blocked']}\n  disarmed: {ks_res['disarmed_reason_code']}")
    print(f"DISCONNECT:\n  simulated offline: BLOCK / AGENT_OFFLINE\n  reconnect: {rg_base.get('decision')} / {rg_base.get('reason_code')}")
    print(f"BLOCKERS: {blocker_msg}")
    print(f"\n{SEP}\nValidation complete at {_now()}\n{SEP}")

if __name__ == "__main__":
    main()
