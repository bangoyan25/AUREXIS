#!/usr/bin/env python3
"""CLI utility to generate cryptographic serial codes for AUREXIS subscription tiers.

Tiers:
- Tier 1: 1 trading account, 30 days
- Tier 2: 5 trading accounts, 30 days
- Tier 3: Unlimited trading accounts (-1), 30 days

Usage:
  python scripts/generate_serial_codes.py --tier 1 --quantity 5
  python scripts/generate_serial_codes.py --tier 2 --quantity 10 --db
  python scripts/generate_serial_codes.py --tier 3 --quantity 3 --output codes.txt
"""
from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.license import TIER_CONFIG, generate_serial_code


def format_table(codes: list[dict[str, str | int]]) -> str:
    headers = ["#", "Serial Code", "Tier", "Plan", "Accounts", "Duration", "Status"]
    col_w = [3, 26, 6, 18, 10, 10, 8]
    
    header_line = " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_w))
    separator = "-+-".join("-" * w for w in col_w)
    rows = []
    for i, c in enumerate(codes, 1):
        acct_str = "Unlimited" if c["account_limit"] == -1 else str(c["account_limit"])
        row = [
            str(i),
            str(c["serial_code"]),
            f"T{c['tier']}",
            str(c["plan"]),
            acct_str,
            f"{c['duration_days']}d",
            str(c["status"]),
        ]
        rows.append(" | ".join(f"{val:<{w}}" for val, w in zip(row, col_w)))
    
    return "\n".join([header_line, separator] + rows)


async def insert_into_db(codes: list[dict[str, str | int]]) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from backend.core.config import settings
    from backend.db.models.license import License

    db_url = settings.DATABASE_URL
    if not db_url:
        print("[ERROR] DATABASE_URL not set. Cannot persist to database.", file=sys.stderr)
        sys.exit(1)
    
    # Normalize postgresql schemes
    if db_url.startswith("postgres://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgres://"):]
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.now(UTC)
    async with session_factory() as session:
        for c in codes:
            tier_val = int(c["tier"])
            lic = License(
                id=uuid.uuid4(),
                license_key=f"lic_{secrets.token_urlsafe(24)}",
                serial_code=str(c["serial_code"]),
                tier=tier_val,
                plan=str(c["plan"]),
                status="UNUSED",
                account_limit=int(c["account_limit"]),
                issued_at=now,
                feature_strategy_engine=True,
                feature_brain=True,
                feature_backtest=True,
                feature_multi_account=(tier_val >= 2),
                revoked=False,
            )
            session.add(lic)
        await session.commit()
    await engine.dispose()
    print(f"[OK] Successfully committed {len(codes)} serial code(s) to the database.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AUREXIS subscription serial codes.")
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3],
        required=True,
        help="Subscription tier: 1 (1 account), 2 (5 accounts), 3 (unlimited)",
    )
    parser.add_argument(
        "--quantity",
        "-n",
        type=int,
        default=1,
        help="Number of serial codes to generate (default: 1)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="AURX",
        help="Code prefix (default: 'AURX')",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional path to write generated codes",
    )
    parser.add_argument(
        "--db",
        action="store_true",
        help="Persist generated codes to the database",
    )

    args = parser.parse_args()

    cfg = TIER_CONFIG[args.tier]
    generated = []
    for _ in range(args.quantity):
        code = generate_serial_code(tier=args.tier, prefix=args.prefix)
        generated.append({
            "serial_code": code,
            "tier": args.tier,
            "plan": cfg["name"],
            "account_limit": cfg["account_limit"],
            "duration_days": cfg["duration_days"],
            "status": "UNUSED",
        })

    table_text = format_table(generated)
    print("\n" + table_text + "\n")

    if args.output:
        out_path = Path(args.output)
        lines = [f"{c['serial_code']} (Tier {c['tier']}, {c['plan']})" for c in generated]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[OK] Saved {len(generated)} serial code(s) to {out_path.resolve()}")

    if args.db:
        asyncio.run(insert_into_db(generated))


if __name__ == "__main__":
    main()
