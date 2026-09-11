"""
AUREXIS VPS Update Audit Script.
"""
import sys
import httpx
from sqlalchemy import create_engine, inspect, text

def run_audit():
    print("=" * 60)
    print("AUREXIS VPS DEPLOYMENT AUDIT")
    print("=" * 60)
    failures = []

    print("\n[1] Checking Database Schema & Tables...")
    try:
        import os
        sys.path.insert(0, os.path.abspath("."))
        from backend.core.config import settings
        engine = create_engine(str(settings.DATABASE_SYNC_URL))
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if "password_resets" in tables:
            cols = [c["name"] for c in inspector.get_columns("password_resets")]
            print(f"  + Table 'password_resets' found: {cols}")
        else:
            failures.append("Table 'password_resets' missing")

        if "licenses" in tables:
            cols = [c["name"] for c in inspector.get_columns("licenses")]
            req = ["tier", "serial_code", "status", "account_limit", "activated_at", "user_id"]
            missing = [c for c in req if c not in cols]
            if not missing:
                print(f"  + Table 'licenses' has all required columns: {req}")
            else:
                failures.append(f"Table 'licenses' missing: {missing}")
        else:
            failures.append("Table 'licenses' missing")

        with engine.connect() as conn:
            res = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            rev = res[0] if res else None
            print(f"  + Alembic Revision: {rev}")
            if rev != "008":
                failures.append(f"Alembic revision expected 008, got {rev}")
    except Exception as e:
        failures.append(f"DB check error: {e}")

    print("\n[2] Checking Local Backend Health...")
    try:
        r = httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=5.0)
        print(f"  + GET /api/v1/health -> Status {r.status_code}")
        d = r.json()
        print(f"    Backend: {d.get('components', {}).get('backend', {}).get('status')}")
        print(f"    DB: {d.get('components', {}).get('database', {}).get('status')}")
        print(f"    Redis: {d.get('components', {}).get('redis', {}).get('status')}")
        print(f"    MT5: {d.get('components', {}).get('mt5', {}).get('status')}, Agents: {d.get('components', {}).get('mt5', {}).get('connected_agents')}")
        if r.status_code != 200:
            failures.append("Health status != 200")
    except Exception as e:
        failures.append(f"Health error: {e}")

    print("\n[3] Checking New Backend Endpoints...")
    try:
        r = httpx.get("http://127.0.0.1:8000/api/v1/accounts/brokers", timeout=5.0)
        brokers = [b["id"] for b in r.json()]
        print(f"  + GET /api/v1/accounts/brokers -> {brokers}")
        if "HFM" not in brokers or "Exness" not in brokers:
            failures.append("Missing HFM or Exness broker")

        r = httpx.post("http://127.0.0.1:8000/api/v1/auth/forgot-password", json={"email": "audit@test.com"}, timeout=5.0)
        print(f"  + POST /api/v1/auth/forgot-password -> Status {r.status_code}")
        if r.status_code != 200:
            failures.append("Forgot password != 200")

        r = httpx.post("http://127.0.0.1:8000/api/v1/auth/register", json={"email": "audit@test.com", "password": "Pass"}, timeout=5.0)
        print(f"  + POST /api/v1/auth/register (no serial) -> Status {r.status_code}")
        if r.status_code != 422:
            failures.append("Register without serial != 422")

        r = httpx.post("http://127.0.0.1:8000/api/v1/auth/register", json={"email": "audit@test.com", "password": "Pass1234Secure!", "serial_code": "INVALID"}, timeout=5.0)
        print(f"  + POST /api/v1/auth/register (bad serial) -> Status {r.status_code}")
        if r.status_code != 400:
            failures.append("Register invalid serial != 400")
    except Exception as e:
        failures.append(f"Endpoints error: {e}")

    print("\n[4] Checking Local Frontend Pages...")
    for route in ["/", "/login", "/register", "/forgot-password", "/reset-password", "/accounts", "/market"]:
        try:
            r = httpx.get(f"http://127.0.0.1:3000{route}", timeout=5.0)
            print(f"  + GET {route} -> Status {r.status_code}")
            if r.status_code != 200:
                failures.append(f"Route {route} != 200")
        except Exception as e:
            failures.append(f"Route {route} error: {e}")

    print("\n[5] Checking External HTTPS Domains...")
    targets = [
        ("Backend HTTPS", "https://app.aurexis.web.id/api/v1/health"),
        ("Frontend Login", "https://web.aurexis.web.id/login"),
        ("Frontend Forgot PW", "https://web.aurexis.web.id/forgot-password"),
        ("Frontend Reset PW", "https://web.aurexis.web.id/reset-password"),
    ]
    for desc, url in targets:
        try:
            r = httpx.get(url, timeout=10.0, follow_redirects=True)
            print(f"  + {desc} ({url}) -> Status {r.status_code}")
            if r.status_code != 200:
                failures.append(f"External {url} != 200")
        except Exception as e:
            failures.append(f"External {url} error: {e}")

    print("\n" + "=" * 60)
    if not failures:
        print("AUDIT RESULT: ALL CHECKS PASSED (100% HEALTHY)")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"AUDIT RESULT: FAILED ({len(failures)} issues):")
        for f in failures:
            print(f"  * {f}")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    run_audit()
