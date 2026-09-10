"""
Live MARKET_DATA_STALE gate verification.

Verifies that the authoritative server-side Risk Gate returns
BLOCK / MARKET_DATA_STALE when the agent is CONNECTED but the
latest cached tick has exceeded the staleness threshold.

Read-only with respect to trading: no orders, no commands, no execution.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime, timedelta

from backend.db.session import AsyncSessionLocal
from backend.services import market_data_service
from backend.services.risk_gate import evaluate_risk_gate

ACCOUNT_ID = uuid.UUID("26597c4f-19a0-41d3-85f7-ae6197cc31fb")
SYMBOL = "XAUUSD"


def _tick(age_ms: int) -> dict:
    received_at = datetime.now(UTC) - timedelta(milliseconds=age_ms)
    return {
        "agent_id": "3c511fdb-0759-4c60-aef9-08215a5f57a6",
        "account_id": str(ACCOUNT_ID),
        "symbol": SYMBOL,
        "raw_symbol": SYMBOL,
        "bid": "4385.00",
        "ask": "4385.20",
        "spread": "0.20",
        "point": "0.01",
        "digits": 2,
        "tick_time": "2026.09.10 14:30:00",
        "tick_volume": 0,
        "received_at": received_at.isoformat(),
    }


async def main() -> None:
    failures: list[str] = []

    async with AsyncSessionLocal() as session:
        print("=== [1] FRESHNESS EVALUATOR UNIT CHECK ===")
        for age, expect_fresh, expect_code in (
            (100, True, "FRESH"),
            (1999, True, "FRESH"),
            (5000, False, "STALE"),
        ):
            is_fresh, code, measured = market_data_service.evaluate_freshness(_tick(age))
            ok = is_fresh is expect_fresh and code == expect_code
            print(f"  age~{age}ms -> is_fresh={is_fresh} code={code} measured={measured}ms {'OK' if ok else 'FAIL'}")
            if not ok:
                failures.append(f"freshness age={age}")

        print("\n=== [2] RISK GATE: AGENT CONNECTED + STALE TICK ===")
        t0 = time.perf_counter()
        res = await evaluate_risk_gate(
            session,
            ACCOUNT_ID,
            SYMBOL,
            override_agent_connected=True,
            override_tick=_tick(5000),
        )
        stale_eval_ms = (time.perf_counter() - t0) * 1000
        print(f"  decision={res.decision} reason_code={res.reason_code}")
        print(f"  reason={res.reason}")
        print(f"  details={res.details}")
        print(f"  eval_latency={stale_eval_ms:.2f}ms")
        if res.decision != "BLOCK" or res.reason_code != "MARKET_DATA_STALE":
            failures.append("stale tick did not produce BLOCK/MARKET_DATA_STALE")

        print("\n=== [3] RISK GATE: AGENT CONNECTED + FRESH TICK ===")
        t0 = time.perf_counter()
        res_fresh = await evaluate_risk_gate(
            session,
            ACCOUNT_ID,
            SYMBOL,
            override_agent_connected=True,
            override_tick=_tick(50),
        )
        fresh_eval_ms = (time.perf_counter() - t0) * 1000
        print(f"  decision={res_fresh.decision} reason_code={res_fresh.reason_code}")
        print(f"  eval_latency={fresh_eval_ms:.2f}ms")
        if res_fresh.decision != "ALLOW" or res_fresh.reason_code != "RISK_OK":
            failures.append("fresh tick did not produce ALLOW/RISK_OK")

        print("\n=== [4] RISK GATE: AGENT DISCONNECTED ===")
        res_off = await evaluate_risk_gate(
            session,
            ACCOUNT_ID,
            SYMBOL,
            override_agent_connected=False,
            override_tick=_tick(50),
        )
        print(f"  decision={res_off.decision} reason_code={res_off.reason_code}")
        if res_off.decision != "BLOCK" or res_off.reason_code != "AGENT_OFFLINE":
            failures.append("disconnected agent did not produce BLOCK/AGENT_OFFLINE")

        print("\n=== [5] RISK GATE: NO MARKET DATA ===")
        res_nodata = await evaluate_risk_gate(
            session,
            ACCOUNT_ID,
            SYMBOL,
            override_agent_connected=True,
            override_tick={},
        )
        print(f"  decision={res_nodata.decision} reason_code={res_nodata.reason_code}")
        if res_nodata.decision != "BLOCK" or res_nodata.reason_code != "MARKET_DATA_NOT_READY":
            failures.append("empty tick did not produce BLOCK/MARKET_DATA_NOT_READY")

        print("\n=== [6] RISK GATE: LIVE (no overrides) ===")
        samples: list[float] = []
        for i in range(5):
            t0 = time.perf_counter()
            live = await evaluate_risk_gate(session, ACCOUNT_ID, SYMBOL)
            samples.append((time.perf_counter() - t0) * 1000)
            age = (live.details or {}).get("age_ms")
            print(f"  run {i + 1}: {live.decision}/{live.reason_code} tick_age={age}ms eval={samples[-1]:.2f}ms")
            await asyncio.sleep(0.3)
        samples.sort()
        print(f"  eval latency p50={samples[len(samples) // 2]:.2f}ms max={samples[-1]:.2f}ms")

    print("\n=== RESULT ===")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        raise SystemExit(1)
    print("  ALL RISK GATE REASON CODES VERIFIED")


if __name__ == "__main__":
    asyncio.run(main())
