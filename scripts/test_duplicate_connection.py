import asyncio
import websockets
import json
import os

AGENT_ID = os.environ.get("AGENT_ID", "3c511fdb-0759-4c60-aef9-08215a5f57a6")
SECRET = os.environ.get("AGENT_SECRET", "placeholder_agent_secret_value_for_testing")
WS_URL = f"wss://app.aurexis.web.id/api/v1/agents/{AGENT_ID}/ws"

async def test_duplicate():
    print("=== [Phase 12] Testing Duplicate Connection ===")
    headers = {"Authorization": f"Bearer {SECRET}"}
    
    # 1. Connect a second socket
    print("Connecting second socket from test runner...")
    async with websockets.connect(WS_URL, additional_headers=headers) as ws2:
        print("Second socket connected! Sending hello...")
        await ws2.send(json.dumps({"type": "hello", "agent_version": "test-2", "capabilities": ["PING"]}))
        resp = await ws2.recv()
        print(f"Received from backend: {resp}")
        
        # Keep open for 2 seconds to confirm MT5 was disconnected
        await asyncio.sleep(2)
        print("Closing test socket so MT5 can reconnect...")

    print("Test socket closed. MT5 EA should now reconnect.")

if __name__ == "__main__":
    asyncio.run(test_duplicate())
