"""
Phase 3 Live Tenancy Isolation Verification against production API.
"""

from __future__ import annotations

import subprocess
import httpx

ACCOUNT_ID_A = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"
BASE_URL = "https://app.aurexis.web.id"


def get_token(user_id: str) -> str:
    res = subprocess.run(
        ["powershell", "-File", "scripts/exec_ssh_cmd.ps1", f"cd ~/AUREXIS && .venv/bin/python /tmp/gen_token.py {user_id}"],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in res.stdout.strip().splitlines():
        line = line.strip()
        if line.startswith("ey"):
            return line
    raise RuntimeError(f"Could not extract token: {res.stdout}")


def main() -> None:
    # User B is a different valid UUID
    user_b_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    token_b = get_token(user_b_id)

    headers_b = {"Authorization": f"Bearer {token_b}"}
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    print("=== [1] USER B -> USER A MARKET STATE ===")
    r_market = client.get(f"/api/v1/market/{ACCOUNT_ID_A}/state", headers=headers_b)
    print(f"  Status code: {r_market.status_code}")
    print(f"  Body: {r_market.text}")
    assert r_market.status_code == 404, f"Expected 404, got {r_market.status_code}"

    print("\n=== [2] USER B -> USER A RISK DECISION ===")
    r_risk = client.get(f"/api/v1/risk/{ACCOUNT_ID_A}/decision", headers=headers_b)
    print(f"  Status code: {r_risk.status_code}")
    print(f"  Body: {r_risk.text}")
    assert r_risk.status_code == 404, f"Expected 404, got {r_risk.status_code}"

    print("\n=== TENANCY ENFORCEMENT VERIFIED: 404 NOT FOUND FOR UNAUTHORIZED ACCESS ===")


if __name__ == "__main__":
    main()
