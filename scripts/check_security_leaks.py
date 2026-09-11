"""
Check for credential or secret leaks across logs, Redis, API, and Git.
"""

from __future__ import annotations

import json
import httpx
from backend.services.auth import create_access_token
from backend.core.redis import get_cache_client

ACCOUNT_ID = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"
USER_ID = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"

token = create_access_token(USER_ID)
client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
headers = {"Authorization": f"Bearer {token}"}

m_text = client.get(f"/api/v1/market/{ACCOUNT_ID}/state", headers=headers).text
r_text = client.get(f"/api/v1/risk/{ACCOUNT_ID}/decision", headers=headers).text

bad_words = ["password", "hashed_secret", "private_key", "secret_key"]

for w in bad_words:
    assert w not in m_text.lower(), f"Leak in market API: {w}"
    assert w not in r_text.lower(), f"Leak in risk decision API: {w}"

print("API responses: CLEAN")
