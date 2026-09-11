"""
Inspect MT5Agent table and connected agents.
"""
from __future__ import annotations

import asyncio
from sqlalchemy import select

from backend.db.session import AsyncSessionLocal
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.account import TradingAccount
from backend.ws.agent_manager import agent_manager


async def main():
    async with AsyncSessionLocal() as session:
        agents = (await session.execute(select(MT5Agent))).scalars().all()
        print(f"=== DB AGENTS ({len(agents)}) ===")
        for a in agents:
            print(f"Agent ID: {a.id}")
            print(f"  Account ID: {a.account_id}")
            print(f"  Active: {a.is_active}")
            print(f"  Last heartbeat: {a.last_heartbeat_at}")
            print(f"  Version: {a.version}")
            print(f"  In-memory connected: {agent_manager.is_connected(str(a.id))}")
            print(f"  Account connected: {agent_manager.is_account_connected(str(a.account_id))}")

        print(f"\n=== REGISTRY CONNECTED AGENT IDS ===")
        print(f"Connected agents count: {len(agent_manager._connections)}")
        for aid, agent in agent_manager._connections.items():
            print(f"  Agent ID: {aid}, account_id: {agent.account_id}")

        accounts = (await session.execute(select(TradingAccount))).scalars().all()
        print(f"\n=== DB ACCOUNTS ({len(accounts)}) ===")
        for acct in accounts:
            print(f"Account ID: {acct.id}, Broker: {acct.broker}, Server: {acct.mt5_server}, Active: {acct.is_active}")


if __name__ == "__main__":
    asyncio.run(main())
