"""
Phase 3 live pipeline latency measurement.

Samples the live production stack (MT5 -> WSS -> FastAPI -> Redis -> Risk Gate)
through the public HTTP API. Purely observational: no orders, no agent commands.
"""

from __future__ import annotations

import statistics
import time

import httpx

from backend.services.auth import create_access_token

USER_ID = "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
ACCOUNT_ID = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"
BASE_URL = "http://127.0.0.1:8000"
SAMPLES = 30


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1))))
    return ordered[idx]


def report(name: str, unit: str, values: list[float]) -> None:
    if not values:
        print(f"{name:<38} NOT MEASURED (no samples)")
        return
    print(
        f"{name:<38} n={len(values):<3} "
        f"min={min(values):8.2f} p50={pct(values, 50):8.2f} "
        f"p95={pct(values, 95):8.2f} max={max(values):8.2f} "
        f"mean={statistics.fmean(values):8.2f} {unit}"
    )


def main() -> None:
    token = create_access_token(subject=USER_ID)
    headers = {"Authorization": f"Bearer {token}"}

    tick_age_ms: list[float] = []
    market_api_ms: list[float] = []
    risk_api_ms: list[float] = []
    risk_tick_age_ms: list[float] = []
    seen_received_at: set[str] = set()
    tick_interval_ms: list[float] = []
    last_ts: float | None = None

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        print(f"Sampling live pipeline: {SAMPLES} iterations\n")
        for _ in range(SAMPLES):
            t0 = time.perf_counter()
            rm = client.get(f"/api/v1/market/{ACCOUNT_ID}/state", headers=headers)
            market_api_ms.append((time.perf_counter() - t0) * 1000)
            m = rm.json()
            if m.get("age_ms") is not None:
                tick_age_ms.append(float(m["age_ms"]))
            ra = m.get("received_at")
            if ra and ra not in seen_received_at:
                seen_received_at.add(ra)
                now = time.perf_counter()
                if last_ts is not None:
                    tick_interval_ms.append((now - last_ts) * 1000)
                last_ts = now

            t0 = time.perf_counter()
            rr = client.get(f"/api/v1/risk/{ACCOUNT_ID}/decision", headers=headers)
            risk_api_ms.append((time.perf_counter() - t0) * 1000)
            r = rr.json()
            det = r.get("details") or {}
            if det.get("age_ms") is not None:
                risk_tick_age_ms.append(float(det["age_ms"]))

            time.sleep(0.2)

    print("=== LIVE PIPELINE LATENCY (Phase 3) ===")
    report("Tick age at market read", "ms", tick_age_ms)
    report("Tick age at risk decision", "ms", risk_tick_age_ms)
    report("GET /market/{id}/state round trip", "ms", market_api_ms)
    report("GET /risk/{id}/decision round trip", "ms", risk_api_ms)
    report("Observed distinct tick interval", "ms", tick_interval_ms)
    print(f"\nDistinct ticks observed: {len(seen_received_at)} / {SAMPLES} polls")


if __name__ == "__main__":
    main()
