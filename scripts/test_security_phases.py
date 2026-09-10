import asyncio
import httpx
import websockets
import json
import os
import uuid
from backend.services.auth import create_access_token

USER_A_ID = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
USER_B_ID = str(uuid.uuid4()) # Fake user B
AGENT_ID = os.environ.get("AGENT_ID", "3c511fdb-0759-4c60-aef9-08215a5f57a6")
FAKE_AGENT_ID = str(uuid.uuid4())
VALID_SECRET = os.environ.get("AGENT_SECRET", "placeholder_agent_secret_value_for_testing")
BAD_SECRET = "WrongSecret1234567890123456789012345678901234567890123456"

BASE_URL = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"

async def test_auth_and_safety():
    print("=== [Phase 13] Authentication Negative Tests ===")
    
    # 1. No secret
    try:
        async with websockets.connect(f"{WS_BASE}/api/v1/agents/{AGENT_ID}/ws") as ws:
            pass
        print("FAIL: Connected without secret!")
    except Exception as e:
        print(f"PASS: No secret rejected: {e}")

    # 2. Invalid secret
    try:
        async with websockets.connect(
            f"{WS_BASE}/api/v1/agents/{AGENT_ID}/ws",
            additional_headers={"Authorization": f"Bearer {BAD_SECRET}"},
        ) as ws:
            pass
        print("FAIL: Connected with invalid secret!")
    except Exception as e:
        print(f"PASS: Invalid secret rejected: {e}")

    # 3. Nonexistent agent
    try:
        async with websockets.connect(
            f"{WS_BASE}/api/v1/agents/{FAKE_AGENT_ID}/ws",
            additional_headers={"Authorization": f"Bearer {VALID_SECRET}"},
        ) as ws:
            pass
        print("FAIL: Connected with nonexistent agent!")
    except Exception as e:
        print(f"PASS: Nonexistent agent rejected: {e}")

    print("\n=== [Phase 14] Tenancy Isolation Tests ===")
    token_a = create_access_token(USER_A_ID)
    token_b = create_access_token(USER_B_ID)

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # User B attempts to access User A agent
        r = await client.get(
            f"/api/v1/agents/{AGENT_ID}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        print(f"User B GET Agent: status={r.status_code} (Expected 404)")
        assert r.status_code == 404

        # User B attempts to create command for User A agent
        r = await client.post(
            f"/api/v1/agents/{AGENT_ID}/commands",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"command_type": "PING"},
        )
        print(f"User B POST Command: status={r.status_code} (Expected 404)")
        assert r.status_code == 404

        print("\n=== [Phase 15] Command Safety Verification ===")
        # Trading commands must be rejected
        for forbidden in ["BUY", "SELL", "OPEN_ORDER", "CLOSE_POSITION", "EXECUTE_TRADE"]:
            r = await client.post(
                f"/api/v1/agents/{AGENT_ID}/commands",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"command_type": forbidden},
            )
            print(f"Command '{forbidden}' attempt: status={r.status_code} (Expected 422)")
            assert r.status_code == 422
            detail = r.json()
            assert detail["detail"]["code"] == "UNSUPPORTED_COMMAND_TYPE"

    print("\nALL SECURITY, TENANCY, AND SAFETY PHASES PASSED!")

if __name__ == "__main__":
    asyncio.run(test_auth_and_safety())

