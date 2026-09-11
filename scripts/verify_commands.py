import asyncio
import sys
import os
sys.path.insert(0, '/home/ubuntu/AUREXIS')
os.chdir('/home/ubuntu/AUREXIS')

from sqlalchemy import select
from backend.db.session import AsyncSessionLocal
from backend.db.models.agent_command import MT5AgentCommand
import uuid

AGENT_ID = uuid.UUID("3c511fdb-0759-4c60-aef9-08215a5f57a6")

async def check():
    async with AsyncSessionLocal() as session:
        cmds = (await session.execute(
            select(MT5AgentCommand)
            .where(MT5AgentCommand.agent_id == AGENT_ID)
            .order_by(MT5AgentCommand.created_at.asc())
        )).scalars().all()
        print(f"TOTAL COMMANDS: {len(cmds)}")
        for c in cmds:
            print(f"Command: id={c.id} type={c.command_type} status={c.status} created={c.created_at} sent={c.sent_at} ack={c.acknowledged_at} completed={c.completed_at}")


asyncio.run(check())
