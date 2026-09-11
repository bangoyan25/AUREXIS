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

    print("\n[6] Testing Live Registration & Tier Account Limit Flow...")
    try:
        import uuid
        from backend.services.license import generate_serial_code
        fresh_code = generate_serial_code(tier=1)
        # Insert fresh code synchronously into licenses table
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO licenses (id, license_key, serial_code, tier, plan, status, account_limit, created_at) "
                    "VALUES (gen_random_uuid(), :lkey, :code, 1, 'AUREXIS TIER 1', 'UNUSED', 1, now())"
                ),
                {"lkey": f"key_{fresh_code}", "code": fresh_code},
            )
            conn.commit()

        uid = str(uuid.uuid4())[:8]
        test_email = f"audit_{uid}@aurexis.web.id"

        reg_resp = httpx.post(
            "http://127.0.0.1:8000/api/v1/auth/register",
            json={
                "email": test_email,
                "password": "Password123!Safe",
                "full_name": "Audit User",
                "serial_code": fresh_code,
            },
            timeout=5.0,
        )
        print(f"  + POST /api/v1/auth/register with fresh code {fresh_code} -> Status {reg_resp.status_code}")
        if reg_resp.status_code != 201:
            failures.append(f"Registration failed: {reg_resp.status_code} {reg_resp.text}")
        else:
            reg_data = reg_resp.json()
            print(f"  + User tier directly from register: {reg_data.get('tier')} (expected 1)")
            if reg_data.get("tier") != 1:
                failures.append("Registered user tier is not 1")

            # Login to get bearer token
            login_resp = httpx.post(
                "http://127.0.0.1:8000/api/v1/auth/login",
                json={"email": test_email, "password": "Password123!Safe"},
                timeout=5.0,
            )
            print(f"  + POST /api/v1/auth/login -> Status {login_resp.status_code}")
            if login_resp.status_code != 200:
                failures.append(f"Login failed: {login_resp.status_code} {login_resp.text}")
            else:
                tok = login_resp.json()["access_token"]
                hdrs = {"Authorization": f"Bearer {tok}"}
                me_resp = httpx.get("http://127.0.0.1:8000/api/v1/auth/me", headers=hdrs, timeout=5.0)
                user_data = me_resp.json()
                print(f"  + GET /api/v1/auth/me tier verified: {user_data.get('tier')} (expected 1)")
                if user_data.get("tier") != 1:
                    failures.append("User tier is not 1")

                # Account 1 creation (should succeed)
                acc1 = httpx.post(
                    "http://127.0.0.1:8000/api/v1/accounts",
                    headers=hdrs,
                    json={"broker_name": "Exness", "account_number": f"ex_{uid}_1", "account_type": "CENT", "currency": "USDC"},
                    timeout=5.0,
                )
                print(f"  + Account 1 creation (Exness Cent) -> Status {acc1.status_code}")
                if acc1.status_code != 201:
                    failures.append(f"Account 1 creation failed: {acc1.status_code} {acc1.text}")

                # Account 2 creation (should fail under Tier 1 limit)
                acc2 = httpx.post(
                    "http://127.0.0.1:8000/api/v1/accounts",
                    headers=hdrs,
                    json={"broker_name": "HFM", "account_number": f"hfm_{uid}_2", "account_type": "STANDARD", "currency": "USD"},
                    timeout=5.0,
                )
                print(f"  + Account 2 creation (Tier 1 limit check) -> Status {acc2.status_code}, detail: {acc2.json().get('detail')}")
                if acc2.status_code != 403:
                    failures.append(f"Account 2 should be rejected 403, got {acc2.status_code}")

                # Duplicate code reuse check
                dup_reg = httpx.post(
                    "http://127.0.0.1:8000/api/v1/auth/register",
                    json={
                        "email": f"dup_{uid}@aurexis.web.id",
                        "password": "Password123!Safe",
                        "full_name": "Dup User",
                        "serial_code": fresh_code,
                    },
                    timeout=5.0,
                )
                print(f"  + Duplicate serial reuse rejection -> Status {dup_reg.status_code}, detail: {dup_reg.json().get('detail')}")
                if dup_reg.status_code != 400:
                    failures.append(f"Duplicate serial should be rejected 400, got {dup_reg.status_code}")
    except Exception as e:
        failures.append(f"Registration/Tier flow error: {e}")

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
