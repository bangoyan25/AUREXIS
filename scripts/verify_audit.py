import asyncio
import sys
import os
sys.path.insert(0, '/home/ubuntu/AUREXIS')
os.chdir('/home/ubuntu/AUREXIS')

from sqlalchemy import select
from backend.db.session import AsyncSessionLocal
from backend.db.models.audit_log import AuditLog
import uuid

ACCOUNT_ID = uuid.UUID("26597c4f-19a0-41d3-85f7-ae6197cc31fb")

async def check():
    async with AsyncSessionLocal() as session:
        logs = (await session.execute(
            select(AuditLog)
            .where(AuditLog.account_id == ACCOUNT_ID)
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )).scalars().all()
        print(f"RECENT AUDIT LOGS: {len(logs)}")
        for l in reversed(logs):
            print(f"Audit: event_type={l.event_type} severity={l.severity} created={l.created_at}")

asyncio.run(check())
