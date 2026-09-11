#!/usr/bin/env python3
"""Safe administrative utility to wipe application users and trading data.

Safety protections:
- Requires explicit flag: --confirm
- Default is --dry-run
- Preserves database schema, tables, and alembic_version
- Reports row counts before and after execution
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import settings
from backend.db.base import Base

TABLE_CLEANUP_ORDER = [
    "audit_logs",
    "execution_reports",
    "positions",
    "execution_commands",
    "candidate_signals",
    "risk_decisions",
    "equity_snapshots",
    "daily_session_states",
    "risk_configurations",
    "mt5_agent_commands",
    "mt5_agents",
    "trading_accounts",
    "refresh_tokens",
    "password_resets",
    "licenses",
    "users",
]


async def get_table_counts(session: AsyncSession) -> dict[str, int]:
    counts = {}
    for table_name in TABLE_CLEANUP_ORDER:
        if table_name in Base.metadata.tables:
            table = Base.metadata.tables[table_name]
            res = await session.execute(select(func.count()).select_from(table))
            counts[table_name] = res.scalar() or 0
        else:
            counts[table_name] = 0
    return counts


async def run_reset(dry_run: bool, confirm: bool) -> None:
    if not confirm and not dry_run:
        print("\n[SAFETY BLOCK] Execution aborted: must specify either --dry-run or --confirm.", file=sys.stderr)
        print("Example safe run:   python scripts/reset_application_users.py --dry-run")
        print("Example actual run: python scripts/reset_application_users.py --confirm\n")
        sys.exit(1)

    db_url = settings.DATABASE_URL
    if not db_url:
        print("[ERROR] DATABASE_URL not configured in environment.", file=sys.stderr)
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgres://"):]
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 60)
    print(f" AUREXIS APPLICATION DATA RESET ({'DRY RUN' if dry_run else 'DESTRUCTIVE EXECUTION'})")
    print("=" * 60)

    async with session_factory() as session:
        before_counts = await get_table_counts(session)
        print("\nPre-cleanup row counts:")
        for tbl, count in before_counts.items():
            print(f"  {tbl:<25} : {count:>5} rows")

        total_rows = sum(before_counts.values())
        print(f"\nTotal rows targeted: {total_rows}")

        if dry_run:
            print("\n[DRY RUN COMPLETE] No records were deleted. Database left untouched.\n")
            await engine.dispose()
            return

        print("\nDeleting user data in safe dependency order...")
        for tbl_name in TABLE_CLEANUP_ORDER:
            if tbl_name in Base.metadata.tables:
                table = Base.metadata.tables[tbl_name]
                await session.execute(delete(table))
        
        await session.commit()
        print("[OK] Committed database transaction.")

        after_counts = await get_table_counts(session)
        print("\nPost-cleanup row counts:")
        for tbl, count in after_counts.items():
            print(f"  {tbl:<25} : {count:>5} rows")
        
        print("\n[SUCCESS] Application user and trading data wiped successfully.")
        print("Schema and alembic_version intact.\n")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely reset application users and account data.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate cleanup and report row counts without modifying DB.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        default=False,
        help="Explicit confirmation to permanently delete application data.",
    )
    args = parser.parse_args()

    # If neither or only dry-run, default to dry-run
    if not args.confirm and not args.dry_run:
        args.dry_run = True

    asyncio.run(run_reset(dry_run=args.dry_run, confirm=args.confirm))


if __name__ == "__main__":
    main()
