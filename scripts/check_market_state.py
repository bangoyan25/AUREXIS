import sys
import os
sys.path.insert(0, '/home/ubuntu/AUREXIS')
os.chdir('/home/ubuntu/AUREXIS')

import httpx
from backend.services.auth import create_access_token

USER_ID = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
ACCOUNT_ID = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"

token = create_access_token(USER_ID)
client = httpx.Client(base_url="http://localhost:8000/api/v1", timeout=30.0)
client.headers.update({"Authorization": f"Bearer {token}"})

r = client.get(f"/market/{ACCOUNT_ID}/state")
print("MARKET STATE:", r.status_code)
print(r.text)

r2 = client.get(f"/risk/{ACCOUNT_ID}/decision")
print("RISK DECISION:", r2.status_code)
print(r2.text)
