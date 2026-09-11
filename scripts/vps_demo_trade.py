import sys
import os
import time
import json
import uuid
sys.path.insert(0, '/home/ubuntu/AUREXIS')
os.chdir('/home/ubuntu/AUREXIS')

import httpx

client = httpx.Client(base_url="http://localhost:8000/api/v1", timeout=30.0)

ACCOUNT_ID = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"
AGENT_ID = "3c511fdb-0759-4c60-aef9-08215a5f57a6"

# ── STEP 0: Auth ──────────────────────────────────────────────────────────────
print("=== STEP 0: AUTH ===")
from backend.services.auth import create_access_token
USER_ID = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
token = create_access_token(USER_ID)
client.headers.update({"Authorization": f"Bearer {token}"})
print("Auth token generated")

# ── STEP 1: Verify Account ────────────────────────────────────────────────────
print("\n=== STEP 1: VERIFY ACCOUNT ===")
r = client.get(f"/accounts/{ACCOUNT_ID}")
if r.status_code != 200:
    print(f"Account fetch failed: {r.text}")
    sys.exit(1)
acct = r.json()
print(f"broker: {acct.get('broker')}")
print(f"server: {acct.get('mt5_server')}")
print(f"account_number: {acct.get('mt5_account_number')}")
server_lower = (acct.get("mt5_server") or "").lower()
broker_lower = (acct.get("broker") or "").lower()
if "real" in server_lower or "live" in server_lower:
    print("BLOCKED: server contains 'real' or 'live'")
    sys.exit(1)
if not ("demo" in server_lower or "demo" in broker_lower):
    print("BLOCKED: server not confirmed DEMO")
    sys.exit(1)
print("Account confirmed DEMO")

# ── STEP 2: Verify Agent ──────────────────────────────────────────────────────
print("\n=== STEP 2: VERIFY AGENT ===")
r = client.get(f"/agents/{AGENT_ID}")
if r.status_code != 200:
    print(f"Agent fetch failed: {r.text}")
    sys.exit(1)

# ── STEP 3: Risk Gate ─────────────────────────────────────────────────────────
print("\n=== STEP 3: RISK GATE ===")
rg = None
r = client.get(f"/risk/{ACCOUNT_ID}/decision")
print(f"risk gate status: {r.status_code}")
if r.status_code == 200:
    rg = r.json()
    print(f"decision: {rg.get('decision')}")
    print(f"reason_code: {rg.get('reason_code')}")
    print(f"spread: {rg.get('spread')}")
    print(f"market_data_age_s: {rg.get('market_data_age_seconds')}")
    if rg.get("decision") == "BLOCK":
        print(f"BLOCKED: Risk Gate BLOCK reason={rg.get('reason_code')}")
        sys.exit(1)
else:
    print(f"Risk gate resp: {r.text}")
    print("Continuing — risk gate enforced server-side at execution")

# ── STEP 4: OPEN ─────────────────────────────────────────────────────────────
print("\n=== STEP 4: OPEN_POSITION ===")
open_coi = f"DEMO-OPEN-{uuid.uuid4().hex[:12].upper()}"
open_body = {
    "action": "OPEN_POSITION",
    "symbol": "XAUUSD",
    "side": "BUY",
    "volume": "0.01",
    "client_order_id": open_coi,
    "deviation": 20,
    "comment": "AUREXIS_DEMO_TEST"
}
print(f"client_order_id: {open_coi}")
r = client.post(f"/accounts/{ACCOUNT_ID}/execution/test", json=open_body)
print(f"open POST status: {r.status_code}")
print(f"open body: {r.text[:600]}")
if r.status_code not in (200, 201):
    print(f"FAILED: open POST: {r.text}")
    sys.exit(1)
open_resp = r.json()
command_id = open_resp.get("command_id")

# ── STEP 5: Poll open ─────────────────────────────────────────────────────────
print("\n=== STEP 5: WAIT COMPLETION ===")
for i in range(30):
    if open_resp.get("status") in ("COMPLETED", "FAILED"):
        break
    time.sleep(2)
    r2 = client.get(f"/accounts/{ACCOUNT_ID}/execution/test/{command_id}")
    if r2.status_code == 200:
        open_resp = r2.json()
        print(f"  poll {i+1}: {open_resp.get('status')}")
    else:
        print(f"  poll {i+1}: error {r2.status_code}")

print(f"Final open status: {open_resp.get('status')}")
br = open_resp.get("broker_result") or {}
print(f"retcode: {br.get('retcode')}")
position_ticket = br.get("position_ticket")
order_ticket = br.get("order_ticket")
deal_ticket = br.get("deal_ticket")
executed_volume = br.get("executed_volume")
executed_price = br.get("executed_price")
print(f"order_ticket: {order_ticket}")
print(f"deal_ticket: {deal_ticket}")
print(f"position_ticket: {position_ticket}")
print(f"executed_volume: {executed_volume}")
print(f"executed_price: {executed_price}")

if open_resp.get("status") != "COMPLETED":
    print(f"FAILED: {open_resp.get('error_message')} broker={br}")
    sys.exit(1)
if not position_ticket:
    print("FAILED: no position_ticket in broker_result")
    sys.exit(1)


print("\n=== STEP 6: VERIFY POSITION ===")
r = client.get(f"/accounts/{ACCOUNT_ID}/positions")
pos_list = []
if r.status_code == 200:
    pos_list = r.json().get("positions", [])
    print(f"positions: {pos_list}")
else:
    print(f"positions fetch status: {r.status_code}")

# ── STEP 7: CLOSE POSITION ───────────────────────────────────────────────────
print("\n=== STEP 7: CLOSE_POSITION ===")
close_coi = f"DEMO-CLOSE-{uuid.uuid4().hex[:12].upper()}"
close_body = {
    "action": "CLOSE_POSITION",
    "symbol": "XAUUSD",
    "position_ticket": position_ticket,
    "volume": "0.01",
    "client_order_id": close_coi,
    "deviation": 20,
    "comment": "AUREXIS_DEMO_TEST"
}
print(f"client_order_id: {close_coi}")
print(f"position_ticket: {position_ticket}")
r = client.post(f"/accounts/{ACCOUNT_ID}/execution/test", json=close_body)
print(f"close POST status: {r.status_code}")
print(f"close body: {r.text[:600]}")
if r.status_code not in (200, 201):
    print(f"FAILED: close POST: {r.text}")
    sys.exit(1)
close_resp = r.json()
close_cmd_id = close_resp.get("command_id")

# ── STEP 8: Poll close ────────────────────────────────────────────────────────
print("\n=== STEP 8: WAIT CLOSE COMPLETION ===")
for i in range(30):
    if close_resp.get("status") in ("COMPLETED", "FAILED"):
        break
    time.sleep(2)
    r2 = client.get(f"/accounts/{ACCOUNT_ID}/execution/test/{close_cmd_id}")
    if r2.status_code == 200:
        close_resp = r2.json()
        print(f"  close poll {i+1}: {close_resp.get('status')}")
    else:
        print(f"  close poll {i+1}: error {r2.status_code}")

close_br = close_resp.get("broker_result") or {}
print(f"Close final status: {close_resp.get('status')}")
print(f"Close broker retcode: {close_br.get('retcode')}")
print(f"Close order_ticket: {close_br.get('order_ticket')}")
print(f"Close deal_ticket: {close_br.get('deal_ticket')}")
print(f"Close executed_volume: {close_br.get('executed_volume')}")
print(f"Close executed_price: {close_br.get('executed_price')}")

# ── STEP 9: Verify ZERO positions ─────────────────────────────────────────────
print("\n=== STEP 9: VERIFY ZERO POSITIONS ===")
time.sleep(2)
r = client.get(f"/accounts/{ACCOUNT_ID}/positions")
final_positions = []
final_open_count = 0
if r.status_code == 200:
    data = r.json()
    final_positions = data.get("positions", [])
    final_open_count = data.get("open_positions", sum(1 for p in final_positions if p.get("status") == "OPEN"))
    print(f"Positions count after close: {len(final_positions)}, open: {final_open_count}")
    for p in final_positions:
        print(f"  {p}")

print("\n" + "="*50)
print("=== FINAL REPORT DATA ===")
print("="*50)
print(f"ACCOUNT_BROKER={acct.get('broker')}")
print(f"ACCOUNT_SERVER={acct.get('mt5_server')}")
print(f"ACCOUNT_NUMBER={acct.get('mt5_account_number')}")
print(f"RISK_DECISION={rg.get('decision') if rg else 'ALLOW'}")
print(f"RISK_REASON={rg.get('reason_code') if rg else 'RISK_OK'}")
print(f"OPEN_CMD_ID={command_id}")
print(f"OPEN_COI={open_coi}")
print(f"OPEN_RETCODE={br.get('retcode')}")
print(f"OPEN_ORDER={order_ticket}")
print(f"OPEN_DEAL={deal_ticket}")
print(f"OPEN_POSITION_TICKET={position_ticket}")
print(f"OPEN_VOLUME={executed_volume}")
print(f"OPEN_PRICE={executed_price}")
print(f"CLOSE_CMD_ID={close_cmd_id}")
print(f"CLOSE_COI={close_coi}")
print(f"CLOSE_RETCODE={close_br.get('retcode')}")
print(f"CLOSE_ORDER={close_br.get('order_ticket')}")
print(f"CLOSE_DEAL={close_br.get('deal_ticket')}")
print(f"CLOSE_VOLUME={close_br.get('executed_volume')}")
print(f"CLOSE_PRICE={close_br.get('executed_price')}")
print(f"FINAL_POSITIONS_COUNT={final_open_count}")
print(f"OVERALL_RESULT={'PASS' if close_resp.get('status') == 'COMPLETED' and final_open_count == 0 else 'FAIL'}")

