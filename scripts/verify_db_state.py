import asyncio
import sys
import os
sys.path.insert(0, '/home/ubuntu/AUREXIS')
os.chdir('/home/ubuntu/AUREXIS')

from sqlalchemy import select
from backend.db.session import AsyncSessionLocal
from backend.db.models.execution import Position as DbPosition
from backend.db.models.execution import ExecutionReport as DbExecutionReport
import uuid

ACCOUNT_ID = uuid.UUID("26597c4f-19a0-41d3-85f7-ae6197cc31fb")

async def check():
    async with AsyncSessionLocal() as session:
        positions = (await session.execute(select(DbPosition).where(DbPosition.account_id == ACCOUNT_ID))).scalars().all()
        print(f"TOTAL POSITIONS IN DB: {len(positions)}")
        for p in positions:
            print(f"Position: ticket={p.broker_ticket} symbol={p.symbol} side={p.side} lots={p.lots} open={p.open_price} close={p.close_price} status={p.status}")
        
        open_pos = [p for p in positions if p.status == "OPEN"]
        print(f"OPEN POSITIONS: {len(open_pos)}")
        
        reports = (await session.execute(select(DbExecutionReport).where(DbExecutionReport.account_id == ACCOUNT_ID))).scalars().all()
        print(f"TOTAL EXECUTION REPORTS: {len(reports)}")
        for r in reports:
            print(f"Report: ticket={r.broker_ticket} deal_id={r.broker_deal_id} status={r.status} fill_price={r.fill_price} fill_lots={r.fill_volume_lots} err_code={r.broker_error_code}")

asyncio.run(check())
