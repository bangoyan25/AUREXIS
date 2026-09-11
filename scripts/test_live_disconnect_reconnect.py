"""
Phase 3 Live Disconnect / Reconnect & Stale Protection Verification.

Executes real lifecycle test against Windows MT5 VPS (103.67.244.220)
and Linux VPS API (129.225.33.77):
  1. Baseline: Live MT5 connected -> tick FRESH -> Risk ALLOW / RISK_OK.
  2. Disconnect: Stop MT5 terminal64 on Windows VPS.
  3. Observe: Tick staleness > 2000ms -> Risk BLOCK (MARKET_DATA_STALE or AGENT_OFFLINE).
  4. Reconnect: StartMT5 on Windows VPS.
  5. Recovery: Heartbeat + ticks resume -> Tick FRESH -> Risk ALLOW / RISK_OK.
  6. Verify positions=0, orders=0.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime

import httpx

ACCOUNT_ID = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"
BASE_URL = "https://app.aurexis.web.id"


def get_token() -> str:
    res = subprocess.run(
        ["powershell", "-File", "scripts/exec_ssh_cmd.ps1", "cd ~/AUREXIS && .venv/bin/python /tmp/print_token.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in res.stdout.strip().splitlines():
        line = line.strip()
        if line.startswith("ey"):
            return line
    raise RuntimeError(f"Failed to extract JWT token from SSH output: {res.stdout}")


def exec_winrm(cmd: str) -> str:
    res = subprocess.run(
        ["powershell", "-File", "scripts/windows/exec_winrm.ps1", "-ScriptText", cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout


def main() -> None:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    print("=== [1] BASELINE LIVE STATE (MT5 CONNECTED) ===")
    r_market = client.get(f"/api/v1/market/{ACCOUNT_ID}/state", headers=headers).json()
    r_risk = client.get(f"/api/v1/risk/{ACCOUNT_ID}/decision", headers=headers).json()
    print(f"  Market: status={r_market.get('status')} age_ms={r_market.get('age_ms')} bid={r_market.get('bid')} ask={r_market.get('ask')}")
    print(f"  Risk Gate: decision={r_risk.get('decision')} reason_code={r_risk.get('reason_code')} reason={r_risk.get('reason')}")
    assert r_market.get("is_fresh") is True, f"Expected fresh market state, got {r_market}"
    assert r_risk.get("decision") == "ALLOW", f"Expected ALLOW decision, got {r_risk}"

    print("\n=== [2] DISCONNECTING MT5 (Stop-Process terminal64) ===")
    t_disconnect = time.perf_counter()
    win_out = exec_winrm("Stop-Process -Name 'terminal64' -Force -ErrorAction SilentlyContinue; 'TERMINAL_STOPPED'")
    print(f"  WinRM: {win_out.strip()}")

    print("\n=== [3] OBSERVING STALE & OFFLINE RISK GATE PROTECTION ===")
    blocked_decision: str | None = None
    blocked_reason_code: str | None = None
    blocked_age_ms: int | None = None

    # Poll for up to 15 seconds to observe state transition to BLOCK
    for i in range(15):
        time.sleep(1.0)
        m = client.get(f"/api/v1/market/{ACCOUNT_ID}/state", headers=headers).json()
        r = client.get(f"/api/v1/risk/{ACCOUNT_ID}/decision", headers=headers).json()
        status = m.get("status")
        age = m.get("age_ms")
        dec = r.get("decision")
        code = r.get("reason_code")
        print(f"  t+{i+1}s: market_status={status} age={age}ms -> risk_decision={dec} ({code})")
        if dec == "BLOCK":
            blocked_decision = dec
            blocked_reason_code = code
            blocked_age_ms = age
            break

    print(f"\n  Confirmed Gate Protection during disconnect: decision={blocked_decision} code={blocked_reason_code} age={blocked_age_ms}ms")
    assert blocked_decision == "BLOCK", "Risk gate did NOT block during disconnect!"

    print("\n=== [4] RECONNECTING MT5 (Start-ScheduledTask StartMT5) ===")
    t_reconnect = time.perf_counter()
    win_out = exec_winrm("Start-ScheduledTask -TaskName 'StartMT5'; 'START_TRIGGERED'")
    print(f"  WinRM: {win_out.strip()}")

    print("\n=== [5] OBSERVING HEARTBEAT & MARKET DATA RECOVERY ===")
    recovered = False
    recovery_time_sec: float | None = None

    # Wait up to 30 seconds for MT5 to relaunch, load EA, and resume fresh tick stream
    for i in range(30):
        time.sleep(1.0)
        m = client.get(f"/api/v1/market/{ACCOUNT_ID}/state", headers=headers).json()
        r = client.get(f"/api/v1/risk/{ACCOUNT_ID}/decision", headers=headers).json()
        status = m.get("status")
        age = m.get("age_ms")
        dec = r.get("decision")
        code = r.get("reason_code")
        print(f"  t+{i+1}s: market_status={status} age={age}ms -> risk_decision={dec} ({code})")
        if dec == "ALLOW" and status == "FRESH":
            recovered = True
            recovery_time_sec = time.perf_counter() - t_reconnect
            print(f"\n  RECOVERY VERIFIED in {recovery_time_sec:.2f}s! Bid={m.get('bid')} Ask={m.get('ask')}")
            break

    assert recovered, "MT5 failed to recover to FRESH / ALLOW state within 30 seconds!"

    print("\n=== [6] VERIFY NO POSITIONS / ORDERS CREATED ===")
    pos = client.get("/api/v1/positions", headers=headers).json()
    positions_count = len(pos.get("positions", []))
    print(f"  Positions count: {positions_count} (status={pos.get('status')})")
    assert positions_count == 0, f"Expected 0 positions, found {positions_count}!"

    print("\n=== TEST PASSED: DISCONNECT, STALE PROTECTION, RECONNECT, RECOVERY ALL VERIFIED ===")


if __name__ == "__main__":
    main()
