"""
Verify live Phase 3 market data and risk gate in production.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from backend.db.models.equity import EquitySnapshot
from backend.db.session import AsyncSessionLocal
from backend.services.auth import create_access_token

user_id = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
account_id = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"

token = create_access_token(subject=user_id)


async def seed_equity():
    async with AsyncSessionLocal() as db:
        eq = EquitySnapshot(
            id=uuid.uuid4(),
            account_id=uuid.UUID(account_id),
            balance_usd=Decimal("500.00"),
            equity_usd=Decimal("500.00"),
            snapped_at=datetime.now(UTC),
        )
        db.add(eq)
        await db.commit()
        print("Equity snapshot seeded!")


asyncio.run(seed_equity())

with httpx.Client(base_url="http://127.0.0.1:8000") as client:
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Market State
    r_m = client.get(f"/api/v1/market/{account_id}/state", headers=headers)
    print("=== LIVE MARKET STATE ===")
    print(f"Status: {r_m.status_code}")
    print(r_m.json())

    # 2. Risk Decision
    r_r = client.get(f"/api/v1/risk/{account_id}/decision", headers=headers)
    print("\n=== LIVE RISK DECISION ===")
    print(f"Status: {r_r.status_code}")
    print(r_r.json())

    # 3. Tenancy test: try accessing with an unauthorized user token
    fake_token = create_access_token(subject="11111111-2222-3333-4444-555555555555")
    r_fake = client.get(f"/api/v1/market/{account_id}/state", headers={"Authorization": f"Bearer {fake_token}"})
    print("\n=== TENANCY TEST (Cross-User Access) ===")
    print(f"Status: {r_fake.status_code} (Expected 404)")
