# AUREXIS Database Schema Specification

> **Status:** FINAL — Verified against models and migrations  
> **Source of Truth:** PostgreSQL (Durable storage). Redis is transient cache / pub-sub ONLY.  
> **Date:** 2026-09-06  

---

## 1. Database Architecture & Principles

### 1.1 Authority Model
- **PostgreSQL is the single authoritative source of truth** for all platform state: users, accounts, agents, tokens, audit records, and trading data.
- **Redis is non-authoritative**: Used exclusively as a fast cache, WebSocket pub-sub message broker, and rate-limiting store. If Redis is flushed or restarts, the platform recovers its canonical state entirely from PostgreSQL.
- **Fail-Safe Startup**: If an MT5 agent status is cached in Redis but missing or stale in PostgreSQL, the system falls back to PostgreSQL `last_known_status` (`UNKNOWN` or `DISCONNECTED`), blocking new trade execution until a fresh heartbeat is validated.

### 1.2 Identifier & UUID Semantics
- Primary keys across all entities use **UUIDv4** (`postgresql.UUID(as_uuid=True)`).
- Default generation is delegated to PostgreSQL via server-side extension: `server_default=sa.text("uuid_generate_v4()")` (requires `uuid-ossp`).
- Python models provide fallback `default=uuid.uuid4` for ORM-level instantiations before commit.
- Opaque string identifiers (e.g., MT5 broker ticket numbers, MT5 account numbers) are kept in their native representation (`BigInteger` or `String`) and never converted to internal synthetic integers.

### 1.3 Timestamp Semantics
- **All timestamps are stored in UTC with timezone:** `TIMESTAMP WITH TIME ZONE` (`DateTime(timezone=True)`).
- Timezone conversions are deferred exclusively to the presentation/client layer.
- **Mutable Models** (`TimestampMixin`):
  - `created_at`: `server_default=func.now()`, `nullable=False`
  - `updated_at`: `server_default=func.now()`, `onupdate=func.now()`, `nullable=False`
- **Immutable / Append-Only Models** (`ImmutableTimestampMixin`):
  - `created_at`: `server_default=func.now()`, `nullable=False`
  - Deliberately **NO `updated_at` column**. Prevents inadvertent mutation and provides strict audit immutability guarantees.

### 1.4 Monetary Precision & Decimal Policy
- All monetary amounts, prices, equity balances, and PnL values are stored as **`NUMERIC(18, 8)`** (`sa.Numeric(precision=18, scale=8)`).
- In Python, all financial fields are mapped to `decimal.Decimal`. **`float` is strictly forbidden** in financial and risk paths to avoid IEEE 754 precision artifacts.
- Cent accounts (e.g. Standard Cent) are normalized to standard USD representation via `cent_normalization_factor`:
  $$\text{USD Value} = \text{Broker Raw Value} \times \text{cent\_normalization\_factor}$$
  *(e.g., $10{,}000\text{ cents} \times 0.01 = \$100.00\text{ USD}$)*.

### 1.5 Account Isolation & Ownership Boundaries
- Every trading account belongs to exactly one platform `User` via `user_id` Foreign Key with `ON DELETE CASCADE`.
- Multi-tenancy is enforced at the database query level: every trading query, risk check, position listing, and WebSocket subscription MUST include `account_id` and be verified against `user_id`.
- There is no global account. Account data is strictly partitioned.


---

## 2. IMPLEMENTED Entities (Migrations 001, 002 & SQLAlchemy Models)

The following tables are fully implemented in `migrations/versions/001_initial.py`, `migrations/versions/002_refresh_tokens.py`, and defined in `backend/db/models/`.

```
[ users ] (1) ──< [ trading_accounts ] (1) ──< [ mt5_agents ]
   │  │                       │                       │
   │  └──< [ refresh_tokens ] │                       │
   │                          │                       │
   └───────< [ audit_logs ] >─┴───────────────────────┘
```

---

### 2.1 `users`
Represents an authenticated platform operator. User identity is decoupled from broker credentials.

- **Table Name:** `users`
- **Inheritance:** `TimestampMixin`, `Base`

| Column | Type | Nullable | Default / Constraints | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | PK, `uuid_generate_v4()` | Unique user identifier |
| `email` | `VARCHAR(255)` | NO | UNIQUE, `ix_users_email` | Operator email / login username |
| `hashed_password` | `VARCHAR(255)` | NO | — | Bcrypt-hashed password |
| `display_name` | `VARCHAR(100)` | NO | — | Operator display name |
| `is_active` | `BOOLEAN` | NO | `true` | Inactive users cannot log in |
| `is_superuser` | `BOOLEAN` | NO | `false` | Superuser administrative privilege |
| `notes` | `TEXT` | YES | `NULL` | Internal administrative remarks |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Record creation timestamp (UTC) |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()`, `onupdate=now()` | Record last modification timestamp (UTC) |

- **Constraints & Indexes:**
  - `uq_users_email` (UNIQUE constraint on `email`)
  - `ix_users_email` (B-Tree index on `email`)
- **Relationships:**
  - `accounts`: 1-to-many with `TradingAccount` (`cascade="all, delete-orphan"`)
  - `audit_logs`: 1-to-many with `AuditLog`

---

### 2.2 `trading_accounts`
Represents an individual MT5 broker account. Serves as the root boundary for risk configuration, positions, orders, and execution.

- **Table Name:** `trading_accounts`
- **Inheritance:** `TimestampMixin`, `Base`

| Column | Type | Nullable | Default / Constraints | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | PK, `uuid_generate_v4()` | Unique internal account identifier |
| `user_id` | `UUID` | NO | FK `users.id` ON DELETE CASCADE | Owning platform operator |
| `label` | `VARCHAR(100)` | NO | — | Human-readable account label (e.g. "Cent Account 1") |
| `broker` | `VARCHAR(100)` | NO | — | Broker name (e.g. "Generic Broker") |
| `mt5_account_number` | `VARCHAR(50)` | NO | Index | MT5 login account number (opaque string) |
| `mt5_server` | `VARCHAR(200)` | YES | `NULL` | MT5 broker access server name |
| `broker_currency` | `VARCHAR(20)` | NO | `'USD'` | Currency reported by broker |
| `is_cent_account` | `BOOLEAN` | NO | `false` | Cent account indicator flag |
| `cent_normalization_factor` | `NUMERIC(18, 8)`| NO | `1.0` | Multiplier to normalize broker units to USD |
| `symbol_mapping_json` | `VARCHAR(1000)`| YES | `NULL` | JSON map for broker symbol variants |
| `is_active` | `BOOLEAN` | NO | `true` | Platform active status |
| `trading_enabled` | `BOOLEAN` | NO | `false` | Explicit master trade authorization flag |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Record creation timestamp (UTC) |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()`, `onupdate=now()` | Record last modification timestamp (UTC) |

- **Constraints & Indexes:**
  - `ix_trading_accounts_user_id` (Index on `user_id`)
  - `ix_trading_accounts_mt5_account_number` (Index on `mt5_account_number`)
- **Relationships:**
  - `user`: Many-to-1 with `User`
  - `mt5_agents`: 1-to-many with `MT5Agent` (`cascade="all, delete-orphan"`)


---

### 2.3 `mt5_agents`
Represents an authorized MT5 Expert Advisor (EA) instance connected to the platform for a specific trading account.

- **Table Name:** `mt5_agents`
- **Inheritance:** `TimestampMixin`, `Base`

| Column | Type | Nullable | Default / Constraints | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | PK, `uuid_generate_v4()` | Unique agent instance identifier |
| `account_id` | `UUID` | NO | FK `trading_accounts.id` ON DELETE CASCADE | Bound trading account |
| `label` | `VARCHAR(100)` | NO | — | Human-readable agent label |
| `hashed_secret` | `VARCHAR(255)` | NO | — | Bcrypt-hashed pre-shared authentication secret |
| `last_seen_at` | `TIMESTAMPTZ` | YES | `NULL` | Most recent heartbeat timestamp (UTC) |
| `last_known_status` | `VARCHAR(50)` | NO | `'UNKNOWN'` | `'UNKNOWN'`, `'CONNECTED'`, `'DISCONNECTED'`, `'ERROR'` |
| `mt5_version` | `VARCHAR(50)` | YES | `NULL` | MT5 terminal build / version |
| `ea_version` | `VARCHAR(50)` | YES | `NULL` | AUREXIS MQL5 EA software version |
| `notes` | `TEXT` | YES | `NULL` | Technical remarks / deployment notes |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Record creation timestamp (UTC) |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()`, `onupdate=now()` | Record last modification timestamp (UTC) |

- **Constraints & Indexes:**
  - `ix_mt5_agents_account_id` (Index on `account_id`)
- **Relationships:**
  - `account`: Many-to-1 with `TradingAccount`

---

### 2.4 `audit_logs`
Immutable audit log tracking all operational, authentication, risk, and execution transitions across the system. Append-only: updates and deletions are strictly forbidden.

- **Table Name:** `audit_logs`
- **Inheritance:** `ImmutableTimestampMixin`, `Base` (No `updated_at`)

| Column | Type | Nullable | Default / Constraints | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | PK, `uuid_generate_v4()` | Unique audit event identifier |
| `user_id` | `UUID` | YES | FK `users.id` ON DELETE SET NULL | Operator who initiated event (if applicable) |
| `account_id` | `UUID` | YES | FK `trading_accounts.id` ON DELETE SET NULL | Target trading account (if applicable) |
| `mt5_agent_id` | `UUID` | YES | FK `mt5_agents.id` ON DELETE SET NULL | Reporting MT5 agent (if applicable) |
| `event_type` | `VARCHAR(100)` | NO | Index | Classification (e.g. `USER_LOGIN`, `RISK_STATE_CHANGED`) |
| `severity` | `VARCHAR(20)` | NO | `'INFO'` | `'INFO'`, `'WARNING'`, `'ERROR'`, `'CRITICAL'` |
| `payload_json` | `TEXT` | YES | `NULL` | Structured contextual event data |
| `correlation_id` | `VARCHAR(100)`| YES | Index | Trace ID across Brain -> Risk -> MT5 |
| `ip_address` | `VARCHAR(45)` | YES | `NULL` | Client IP address (secrets/passwords omitted) |
| `occurred_at` | `TIMESTAMPTZ` | NO | `now()`, Index | Application event timestamp (UTC) |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Database insertion timestamp (UTC) |

- **Constraints & Indexes:**
  - `ix_audit_logs_user_id` (Index on `user_id`)
  - `ix_audit_logs_account_id` (Index on `account_id`)
  - `ix_audit_logs_event_type` (Index on `event_type`)
  - `ix_audit_logs_correlation_id` (Index on `correlation_id`)
  - `ix_audit_logs_occurred_at` (Index on `occurred_at`)
- **Relationships:**
  - `user`: Many-to-1 with `User` (Read-only navigation)

---

### 2.5 `refresh_tokens`
Tracks JWT refresh token identifiers (JTI) for cryptographic token revocation, rotation, and multi-session management.

- **Table Name:** `refresh_tokens`
- **Inheritance:** `ImmutableTimestampMixin`, `Base`

| Column | Type | Nullable | Default / Constraints | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | PK, `uuid_generate_v4()` | Unique token tracking identifier |
| `jti` | `VARCHAR(64)` | NO | UNIQUE, Index | JWT ID claim extracted from token payload |
| `user_id` | `UUID` | NO | FK `users.id` ON DELETE CASCADE | Bound platform operator |
| `expires_at` | `TIMESTAMPTZ` | NO | — | Expiration timestamp matching JWT `exp` claim |
| `revoked_at` | `TIMESTAMPTZ` | YES | `NULL` | Timestamp when revoked; `NULL` indicates active token |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Record creation timestamp (UTC) |

- **Constraints & Indexes:**
  - `ix_refresh_tokens_jti` (UNIQUE index on `jti`)
  - `ix_refresh_tokens_user_id` (Index on `user_id`)
- **Lifecycle Guarantees:**
  - On login: New record inserted with `revoked_at = NULL`.
  - On rotation: Old record updated with `revoked_at = now()`, new record inserted.
  - On logout: Active record updated with `revoked_at = now()`.
  - Token replay of revoked JTI produces immediate `401 REFRESH_TOKEN_REVOKED`.


---

## 3. IMPLEMENTED Trading Domain Entities (Migration 003 & SQLAlchemy Models)

The following tables are fully defined in database migration `003_trading_domain.py` and implemented as SQLAlchemy ORM models in `backend/db/models/` (`risk.py`, `signal.py`, `execution.py`, `equity.py`, `news.py`) supporting the locked Risk Engine (`docs/RISK_ENGINE_SPECIFICATION.md`), Brain Engine (`docs/BRAIN_SPECIFICATION.md`), and MT5 Command Protocol (`docs/MT5_COMMAND_PROTOCOL.md`).

*Status: Migration 003 + SQLAlchemy models fully implemented and verified with database metadata.*

```
[ trading_accounts ]
   │
   ├──< [ risk_configurations ] (versioned)
   ├──< [ risk_decisions ]      (immutable decision audit)
   ├──< [ candidate_signals ]   (Brain output lifecycle)
   ├──< [ execution_commands ]  (idempotent broker commands)
   │        │
   │        └──< [ execution_reports ] (broker fills/rejects)
   │
   ├──< [ positions ]           (live & historical MT5 tickets)
   ├──< [ equity_snapshots ]    (HWM, drawdown tracking)
   └──< [ daily_session_states ](daily PnL & profit-lock floors)

[ news_events ] (global economic calendar / blackout gating)
```

---

### 3.1 `risk_configurations` (PLANNED)
Versioned risk control parameters per trading account. Parameter changes insert a new version row rather than updating in-place to guarantee historical auditability.

- **Table Name:** `risk_configurations`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `account_id`: `UUID` (FK `trading_accounts.id` ON DELETE CASCADE)
  - `version`: `INTEGER` (Incrementing version number per account)
  - `effective_from`: `TIMESTAMPTZ` (UTC activation boundary)
  - `created_by_user_id`: `UUID` (FK `users.id` ON DELETE SET NULL)
  - `daily_reset_timezone`: `VARCHAR(50)` (Locked: `'UTC'`)
  - `drawdown_reference`: `VARCHAR(50)` (Locked: `'LIFETIME_HWM'`)
  - `profit_lock_formula`: `VARCHAR(50)` (Locked: `'PCT_RETRACE'`)
  - `profit_lock_basis`: `VARCHAR(50)` (Locked: `'FLOATING_EQUITY'`)
  - `profit_lock_threshold_usd`: `NUMERIC(18, 8)` (Default: `10.00`)
  - `profit_lock_floor_pct`: `NUMERIC(18, 8)` (Default: `0.30` = 30%)
  - `max_tick_staleness_ms`: `INTEGER` (Default: `2000`)
  - `news_pre_event_window_minutes`: `INTEGER` (Default: `30`)
  - `news_post_event_window_minutes`: `INTEGER` (Default: `30`)
  - `daily_loss_limit_usd`: `NUMERIC(18, 8)` (Nullable, UNDEFINED until configured)
  - `max_drawdown_usd`: `NUMERIC(18, 8)` (Nullable, UNDEFINED until configured)
  - `max_open_positions`: `INTEGER` (Nullable, UNDEFINED until configured)
  - `max_open_lots`: `NUMERIC(18, 8)` (Nullable, UNDEFINED until configured)
  - `max_spread_usd`: `NUMERIC(18, 8)` (Nullable, UNDEFINED until configured)
  - `risk_per_trade_pct`: `NUMERIC(18, 8)` (Nullable, UNDEFINED until configured)
  - `created_at`: `TIMESTAMPTZ` (UTC)
- **Constraints & Indexes:**
  - `uq_risk_config_account_version` (UNIQUE on `(account_id, version)`)
  - `ix_risk_configurations_account_id` (Index on `account_id`)

---

### 3.2 `risk_decisions` (PLANNED)
Immutable audit trail of every Risk Engine evaluation (approved or blocked) for candidate signals.

- **Table Name:** `risk_decisions`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `account_id`: `UUID` (FK `trading_accounts.id` ON DELETE SET NULL)
  - `risk_config_version`: `INTEGER`
  - `signal_id`: `UUID` (Reference to `candidate_signals.id`)
  - `correlation_id`: `VARCHAR(100)`
  - `decision`: `VARCHAR(30)` (`APPROVED`, `BLOCKED`, `NOT_CONFIGURED`, `EMERGENCY`)
  - `reason_code`: `VARCHAR(200)`
  - `risk_state`: `VARCHAR(50)` (`NORMAL`, `CAUTION`, `PROTECTED`, `STOPPED`, `EMERGENCY_STOP`, `NOT_CONFIGURED`)
  - `equity_at_decision`: `NUMERIC(18, 8)`
  - `drawdown_at_decision`: `NUMERIC(18, 8)`
  - `daily_pnl_at_decision`: `NUMERIC(18, 8)`
  - `profit_lock_active`: `BOOLEAN`
  - `profit_lock_floor_usd`: `NUMERIC(18, 8)`
  - `decided_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ`
- **Constraints & Indexes:**
  - Indexes on `account_id`, `decided_at`, `signal_id`, `correlation_id`

---

### 3.3 `candidate_signals` (PLANNED)
Stores Brain engine outputs, setup details, confidence scores, and multi-factor evidence.

- **Table Name:** `candidate_signals`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `account_id`: `UUID` (FK `trading_accounts.id` ON DELETE SET NULL)
  - `correlation_id`: `VARCHAR(100)`
  - `symbol`: `VARCHAR(20)` (Default: `'XAUUSD'`)
  - `direction`: `VARCHAR(10)` (`BUY`, `SELL`)
  - `strategy_id`: `VARCHAR(100)`
  - `strategy_version`: `VARCHAR(50)`
  - `regime`: `VARCHAR(50)`
  - `setup_type`: `VARCHAR(50)`
  - `confidence_score`: `NUMERIC(18, 8)`
  - `entry_reference`: `NUMERIC(18, 8)`
  - `suggested_stop_loss`: `NUMERIC(18, 8)`
  - `suggested_take_profit`: `NUMERIC(18, 8)`
  - `spread_at_signal`: `NUMERIC(18, 8)`
  - `news_state_at_signal`: `VARCHAR(50)`
  - `evidence_json`: `TEXT` (Serialized multi-factor evidence)
  - `status`: `VARCHAR(50)` (`CANDIDATE_FORMING`, `PENDING_RISK`, `APPROVED`, `BLOCKED`, `EXPIRED`)
  - `generated_at`: `TIMESTAMPTZ`
  - `expires_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ`


---

### 3.4 `execution_commands` (PLANNED)
Authoritative execution commands dispatched to the MT5 EA. Guarantees deterministic idempotency and prevents duplicate trade execution.

- **Table Name:** `execution_commands`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `account_id`: `UUID` (FK `trading_accounts.id` ON DELETE SET NULL)
  - `signal_id`: `UUID` (FK `candidate_signals.id` ON DELETE SET NULL)
  - `risk_decision_id`: `UUID` (FK `risk_decisions.id` ON DELETE SET NULL)
  - `correlation_id`: `VARCHAR(100)`
  - `idempotency_key`: `VARCHAR(100)` (UNIQUE — prevents duplicate commands)
  - `action`: `VARCHAR(30)` (`ORDER_OPEN`, `ORDER_CLOSE`, `BASKET_CLOSE`, `POSITION_MODIFY`)
  - `symbol`: `VARCHAR(20)`
  - `order_type`: `VARCHAR(10)` (`BUY`, `SELL`)
  - `volume_lots`: `NUMERIC(18, 8)`
  - `price`: `NUMERIC(18, 8)`
  - `stop_loss`: `NUMERIC(18, 8)`
  - `take_profit`: `NUMERIC(18, 8)`
  - `slippage_points`: `INTEGER`
  - `magic_number`: `INTEGER`
  - `position_ticket`: `BIGINT` (For close/modify commands)
  - `status`: `VARCHAR(30)` (`CREATED`, `SENT`, `ACKNOWLEDGED`, `EXECUTING`, `FILLED`, `REJECTED`, `EXPIRED`)
  - `reason`: `VARCHAR(200)`
  - `expires_at`: `TIMESTAMPTZ`
  - `sent_at`: `TIMESTAMPTZ`
  - `acknowledged_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ`

---

### 3.5 `execution_reports` (PLANNED)
Broker fill/rejection outcomes reported back by the MT5 EA.

- **Table Name:** `execution_reports`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `command_id`: `UUID` (FK `execution_commands.id` ON DELETE SET NULL)
  - `account_id`: `UUID` (FK `trading_accounts.id` ON DELETE SET NULL)
  - `correlation_id`: `VARCHAR(100)`
  - `status`: `VARCHAR(30)` (`FILLED`, `PARTIALLY_FILLED`, `REJECTED`, `ERROR`)
  - `broker_ticket`: `BIGINT`
  - `broker_deal_id`: `BIGINT`
  - `fill_price`: `NUMERIC(18, 8)`
  - `fill_volume_lots`: `NUMERIC(18, 8)`
  - `slippage_points`: `INTEGER`
  - `commission_usd`: `NUMERIC(18, 8)`
  - `swap_usd`: `NUMERIC(18, 8)`
  - `broker_error_code`: `INTEGER`
  - `broker_error_message`: `VARCHAR(500)`
  - `executed_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ`

---

### 3.6 `positions` (PLANNED)
Live tracking and lifecycle history of broker positions. Reconciled periodically against MT5 broker state.

- **Table Name:** `positions`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `account_id`: `UUID` (FK `trading_accounts.id` ON DELETE SET NULL)
  - `command_id`: `UUID` (FK `execution_commands.id` ON DELETE SET NULL)
  - `broker_ticket`: `BIGINT` (Unique MT5 position ticket per account)
  - `symbol`: `VARCHAR(20)`
  - `side`: `VARCHAR(10)` (`BUY`, `SELL`)
  - `lots`: `NUMERIC(18, 8)`
  - `open_price`: `NUMERIC(18, 8)`
  - `stop_loss`: `NUMERIC(18, 8)`, `take_profit`: `NUMERIC(18, 8)`
  - `current_price`: `NUMERIC(18, 8)`, `unrealized_pnl_usd`: `NUMERIC(18, 8)`
  - `commission_usd`: `NUMERIC(18, 8)`, `swap_usd`: `NUMERIC(18, 8)`
  - `magic_number`: `INTEGER`
  - `status`: `VARCHAR(30)` (`OPEN`, `CLOSED`, `ORPHANED`)
  - `opened_at`: `TIMESTAMPTZ`, `closed_at`: `TIMESTAMPTZ`
  - `close_price`: `NUMERIC(18, 8)`, `realized_pnl_usd`: `NUMERIC(18, 8)`
  - `last_synced_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ`, `updated_at`: `TIMESTAMPTZ`
- **Constraints:**
  - `uq_positions_account_ticket` (UNIQUE on `(account_id, broker_ticket)`)


---

### 3.7 `equity_snapshots` (PLANNED)
Periodic balance and equity snapshots used to compute account High-Water Marks (HWM), maximum drawdown, and portfolio statistics.

- **Table Name:** `equity_snapshots`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `account_id`: `UUID` (FK `trading_accounts.id` ON DELETE CASCADE)
  - `balance_usd`: `NUMERIC(18, 8)`, `equity_usd`: `NUMERIC(18, 8)`
  - `margin_usd`: `NUMERIC(18, 8)`, `free_margin_usd`: `NUMERIC(18, 8)`
  - `floating_pnl_usd`: `NUMERIC(18, 8)`
  - `open_position_count`: `INTEGER`
  - `snapped_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ`

---

### 3.8 `daily_session_states` (PLANNED)
Per-account daily tracking for session open equity, peak floating profit, realized PnL, daily loss limit triggers, and dynamic profit-lock floor levels.

- **Table Name:** `daily_session_states`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `account_id`: `UUID` (FK `trading_accounts.id` ON DELETE CASCADE)
  - `session_date`: `DATE`
  - `session_open_equity_usd`: `NUMERIC(18, 8)`
  - `session_peak_profit_usd`: `NUMERIC(18, 8)` (Default: `0`)
  - `realized_pnl_usd`: `NUMERIC(18, 8)` (Default: `0`)
  - `floating_pnl_usd`: `NUMERIC(18, 8)`
  - `daily_loss_stop_triggered`: `BOOLEAN` (Default: `false`)
  - `profit_lock_active`: `BOOLEAN` (Default: `false`)
  - `profit_lock_activated_at`: `TIMESTAMPTZ`
  - `last_updated_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ`
- **Constraints:**
  - `uq_daily_session_account_date` (UNIQUE on `(account_id, session_date)`)

---

### 3.9 `news_events` (PLANNED)
Economic calendar events with pre- and post-event blackout windows to protect against high-impact volatility spikes.

- **Table Name:** `news_events`
- **Key Columns:**
  - `id`: `UUID` (PK)
  - `source`: `VARCHAR(100)` (e.g. `'FOREX_FACTORY'`, `'FXSTREET'`)
  - `source_event_id`: `VARCHAR(200)`
  - `event_name`: `VARCHAR(500)`
  - `currency`: `VARCHAR(10)` (e.g. `'USD'`)
  - `impact`: `VARCHAR(20)` (`HIGH`, `MEDIUM`, `LOW`, `NON_ECONOMIC`)
  - `event_time`: `TIMESTAMPTZ`
  - `pre_event_window_start`: `TIMESTAMPTZ`
  - `post_event_window_end`: `TIMESTAMPTZ`
  - `actual_value`, `forecast_value`, `previous_value`: `VARCHAR(100)`
  - `created_at`: `TIMESTAMPTZ`
- **Constraints:**
  - `uq_news_events_source_id` (UNIQUE on `(source, source_event_id)`)

---

## 4. UNDEFINED Elements (Awaiting User/Owner Authorization)

To uphold the core governance rule:
> *"Undefined decisions remain UNDEFINED until explicitly approved by the user; no coding agent may invent them."*

The following database fields and parameters are explicitly **UNDEFINED** at the database layer:

1. **Production Numeric Risk Thresholds:**
   - Specific production dollar thresholds for `daily_loss_limit_usd` and `max_drawdown_usd` are account-specific and remain `NULL` until configured by the user via authenticated API.
   - Max open lot volume (`max_open_lots`) and max positions (`max_open_positions`) remain `NULL` until configured.
   - Fixed risk percentage per trade (`risk_per_trade_pct`) remains `NULL` until configured.

2. **Strategy-Specific Numerical Parameters:**
   - Moving average periods, ATR multipliers, swing pivot lengths, breakout candle lookbacks, and confidence weights are NOT hardcoded into database schemas. They belong to versioned strategy manifests.

3. **External News Provider Credentials & Source API:**
   - Specific third-party calendar provider credentials (e.g., ForexFactory scrapers, Investing.com API keys) are not yet bound.

---

## 5. Verification & Testing

Schema integrity and constraints are verified via automated tests:
- `tests/test_account_normalization.py`: Validates cent normalization factor arithmetic and USD conversion.
- `tests/test_accounts_api.py`: Validates account ownership isolation, FK cascading, and unique constraints.
- `tests/test_audit_log.py`: Validates audit log immutability and correlation tracing.
- `tests/test_auth.py` & `tests/test_auth_api.py`: Validates refresh token JTI storage, rotation, and revocation.
- Alembic migrations `001_initial.py`, `002_refresh_tokens.py`, and `003_trading_domain.py` pass Python `ast.parse()` syntax validation.

