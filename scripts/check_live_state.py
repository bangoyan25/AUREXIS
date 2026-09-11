from __future__ import annotations

import json
import httpx
from backend.services.auth import create_access_token

USER_ID = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
ACCOUNT_ID = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"

token = create_access_token(subject=USER_ID)
headers = {"Authorization": f"Bearer {token}"}
client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=10.0)

m = client.get(f"/api/v1/market/{ACCOUNT_ID}/state", headers=headers).json()
print("=== LIVE MARKET STATE ===")
print(json.dumps(m, indent=2))

r = client.get(f"/api/v1/risk/{ACCOUNT_ID}/decision", headers=headers).json()
print("\n=== LIVE RISK DECISION ===")
print(json.dumps(r, indent=2))

pos = client.get(f"/api/v1/accounts/{ACCOUNT_ID}/positions", headers=headers).json()
print("\n=== LIVE POSITIONS ===")
print(json.dumps(pos, indent=2))

strat = client.get(f"/api/v1/accounts/{ACCOUNT_ID}/strategy", headers=headers).json()
print("\n=== LIVE STRATEGY ENGINE STATE ===")
print(json.dumps(strat, indent=2))

bars = client.get(f"/api/v1/accounts/{ACCOUNT_ID}/strategy/bars", headers=headers).json()
print("\n=== LIVE CLOSED M15 BARS SUMMARY ===")
print("count:", bars.get("count"))
print("symbol:", bars.get("symbol"))
print("timeframe:", bars.get("timeframe"))
print("first_candle_ts:", bars.get("first_candle_ts"))
print("last_candle_ts:", bars.get("last_candle_ts"))
if bars.get("bars"):
    print("latest_closed_bar:", json.dumps(bars["bars"][-1], indent=2))

