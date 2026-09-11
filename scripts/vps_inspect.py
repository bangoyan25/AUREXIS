import asyncio
import sys
import os
sys.path.insert(0, '/home/ubuntu/AUREXIS')
os.chdir('/home/ubuntu/AUREXIS')

from sqlalchemy import select
from backend.db.session import AsyncSessionLocal
from backend.db.models.account import TradingAccount
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.user import User
from backend.db.models.risk import RiskConfiguration

async def inspect():
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User))).scalars().all()
        for u in users:
            print(f'USER: id={u.id} email={u.email}')

        accounts = (await session.execute(select(TradingAccount))).scalars().all()
        for a in accounts:
            print(f'ACCOUNT: id={a.id} label={a.label} broker={a.broker} mt5={a.mt5_account_number} server={a.mt5_server} active={a.is_active} trading_enabled={a.trading_enabled}')

        agents = (await session.execute(select(MT5Agent))).scalars().all()
        for ag in agents:
            print(f'AGENT: id={ag.id} account_id={ag.account_id} label={ag.label} status={ag.last_known_status} last_seen={ag.last_seen_at}')

        cfgs = (await session.execute(select(RiskConfiguration))).scalars().all()
        for c in cfgs:
            print(f'RISK_CFG: id={c.id} account_id={c.account_id} daily_loss={c.daily_loss_limit_usd} max_dd={c.max_drawdown_usd} max_pos={c.max_open_positions}')

asyncio.run(inspect())
