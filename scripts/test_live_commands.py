import asyncio
import time
import httpx
from backend.services.auth import create_access_token

USER_ID = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
AGENT_ID = "3c511fdb-0759-4c60-aef9-08215a5f57a6"
BASE_URL = "http://127.0.0.1:8000"

async def test_live_roundtrip():
    token = create_access_token(USER_ID)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Check agent status first
        print("=== Checking Agent Status ===")
        r = await client.get(f"/api/v1/agents/{AGENT_ID}", headers=headers)
        print(f"Agent GET status_code: {r.status_code}")
        agent_data = r.json()
        print(f"Agent Status: {agent_data.get('last_known_status')}")
        print(f"Last Seen At: {agent_data.get('last_seen_at')}")
        print(f"MT5 Version:  {agent_data.get('mt5_version')}")
        print(f"EA Version:   {agent_data.get('ea_version')}")

        # 1. PING Command Round Trip
        print("\n=== [Phase 7] Testing PING Command Round Trip ===")
        t0 = time.time()
        r = await client.post(
            f"/api/v1/agents/{AGENT_ID}/commands",
            headers=headers,
            json={"command_type": "PING"},
        )
        print(f"POST PING status_code: {r.status_code}")
        cmd_ping = r.json()
        cmd_id = cmd_ping["id"]
        print(f"Command ID: {cmd_id}, Initial Status: {cmd_ping.get('status')}")

        # Poll for completion
        completed = False
        for i in range(25):
            await asyncio.sleep(0.4)
            r = await client.get(f"/api/v1/agents/{AGENT_ID}/commands/{cmd_id}", headers=headers)
            cdata = r.json()
            status = cdata.get("status")
            elapsed_ms = int((time.time() - t0) * 1000)
            print(f"  Poll {i+1}: status={status} ({elapsed_ms}ms)")
            if status == "COMPLETED":
                completed = True
                print(f"  SUCCESS! PING Completed in {elapsed_ms}ms")
                print(f"  Result Payload: {cdata.get('result')}")
                break
            elif status == "FAILED":
                print(f"  FAILED! Error: {cdata.get('error_message')}")
                break

        if not completed:
            print("  ERROR: PING command did not complete within timeout.")

        # 2. GET_STATUS Command Round Trip
        print("\n=== [Phase 8] Testing GET_STATUS Command Round Trip ===")
        t0 = time.time()
        r = await client.post(
            f"/api/v1/agents/{AGENT_ID}/commands",
            headers=headers,
            json={"command_type": "GET_STATUS"},
        )
        print(f"POST GET_STATUS status_code: {r.status_code}")
        cmd_status = r.json()
        status_id = cmd_status["id"]
        print(f"Command ID: {status_id}, Initial Status: {cmd_status.get('status')}")

        # Poll for completion
        completed_status = False
        for i in range(25):
            await asyncio.sleep(0.4)
            r = await client.get(f"/api/v1/agents/{AGENT_ID}/commands/{status_id}", headers=headers)
            cdata = r.json()
            status = cdata.get("status")
            elapsed_ms = int((time.time() - t0) * 1000)
            print(f"  Poll {i+1}: status={status} ({elapsed_ms}ms)")
            if status == "COMPLETED":
                completed_status = True
                print(f"  SUCCESS! GET_STATUS Completed in {elapsed_ms}ms")
                print(f"  Account Info: {cdata.get('result')}")
                break
            elif status == "FAILED":
                print(f"  FAILED! Error: {cdata.get('error_message')}")
                break

        if not completed_status:
            print("  ERROR: GET_STATUS command did not complete within timeout.")

if __name__ == "__main__":
    asyncio.run(test_live_roundtrip())
