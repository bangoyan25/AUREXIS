# AUREXIS Serial Code Generation & Licensing Guide

This guide documents the serial code system, subscription tiers, CLI utilities, and database management for AUREXIS.

---

## 1. Subscription Tier Definitions

All AUREXIS subscriptions have a default duration of **30 days** upon activation. The tier dictates the maximum number of MT5 trading accounts a user can create on the platform:

| Tier | Plan Name | Trading Account Limit | Duration | Features |
|---|---|---|---|---|
| **Tier 1** | `AUREXIS TIER 1` | **1 Account** | 30 Days | Strategy Engine, Brain Analysis, Risk Gate |
| **Tier 2** | `AUREXIS TIER 2` | **5 Accounts** | 30 Days | Tier 1 + Multi-Account Management (up to 5) |
| **Tier 3** | `AUREXIS TIER 3` | **Unlimited (-1)** | 30 Days | Full Platform Access + Unlimited Accounts |

---

## 2. Serial Code Format & Cryptography

Serial codes are cryptographically generated using Python's `secrets` module (CSPRNG):
- Format: `AURX-T{tier}-{PART1}-{PART2}-{PART3}`
- Examples:
  - `AURX-T1-81B2-6098-910B`
  - `AURX-T2-4AE0-37C9-21F4`
  - `AURX-T3-EE91-884A-B02C`

### Status Lifecycle
Each code in the database transitions through these states:
- `UNUSED`: Generated and stored in the database; waiting for user registration.
- `ACTIVE`: Claimed during user registration. `user_id`, `activated_at`, `valid_from`, and `valid_until` are set.
- `EXPIRED`: License validity period has passed (`valid_until < NOW()`).
- `REVOKED`: Manually or programmatically invalidated (`revoked = true`).

---

## 3. CLI Generation Utility

The CLI utility is located at `scripts/generate_serial_codes.py`.

### Generating Codes to Console
```bash
# Generate 5 Tier 1 codes
python scripts/generate_serial_codes.py --tier 1 --quantity 5

# Generate 3 Tier 2 codes
python scripts/generate_serial_codes.py --tier 2 --quantity 3

# Generate 1 Tier 3 code
python scripts/generate_serial_codes.py --tier 3 --quantity 1
```

### Generating Codes and Inserting into Database
When running on the production server (or locally with `DATABASE_URL` configured):
```bash
python scripts/generate_serial_codes.py --tier 1 --quantity 10 --db
python scripts/generate_serial_codes.py --tier 2 --quantity 5 --db
python scripts/generate_serial_codes.py --tier 3 --quantity 2 --db
```

### Exporting Codes to File
```bash
python scripts/generate_serial_codes.py --tier 1 --quantity 20 --output batch_tier1.txt
```

---

## 4. User Registration Flow

1. Registration requires: Email, Password, Confirm Password, and Serial Code.
2. The endpoint `POST /api/v1/auth/register` validates the code:
   - Must exist in `licenses` table with `status = 'UNUSED'`.
   - Must not be `revoked`.
   - Uses `SELECT ... FOR UPDATE` row locking to prevent race conditions during activation.
3. Upon activation, the license is bound to the newly registered `user.id` and sets:
   - `activated_at = NOW()`
   - `valid_from = NOW()`
   - `valid_until = NOW() + 30 days`
   - `status = 'ACTIVE'`

---

## 5. Account Creation Enforcement

When a user attempts to add an MT5 trading account via `POST /api/v1/accounts`:
1. Server queries the user's active license (`get_user_active_license`).
2. If no active license or license is expired/revoked: returns `403 Forbidden`.
3. If `account_limit != -1`:
   - Checks count of active accounts for `user_id`.
   - If count >= `account_limit`: returns `403 Forbidden` with detailed tier limit error.
