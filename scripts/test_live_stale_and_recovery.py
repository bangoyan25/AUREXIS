"""
Live Stale Data and Disconnect/Reconnect Recovery Test.
"""

from __future__ import annotations

import time

import httpx

from backend.services.auth import create_access_token

user_id = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
account_id = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"

token = create_access_token(subject=user_id)
headers = {"Authorization": f"Bearer {token}"}

with httpx.Client(base_url="http://127.0.0.1:8000") as client:
    print("--- [STAGE 1] Querying current state (Expect ALLOW / HEALTHY) ---")
    r1 = client.get(f"/api/v1/risk/{account_id}/decision", headers=headers)
    print("Status:", r1.status_code)
    print("Response:", r1.json())

    print("\n--- [STAGE 2] Waiting for staleness (if MT5 stopped) ---")
    # Poll for 15 seconds to observe transition
    for i in range(1, 6):
        time.sleep(2)
        r = client.get(f"/api/v1/risk/{account_id}/decision", headers=headers)
        data = r.json()
        print(f"T+{i*2}s: decision={data.get('decision')}, reason_code={data.get('reason_code')}, reason={data.get('reason')}")
        if data.get("reason_code") in ("MARKET_DATA_STALE", "AGENT_OFFLINE"):
            print(f"VERIFIED: Stale or offline transition detected at T+{i*2}s!")
            break
