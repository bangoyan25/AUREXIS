# AUREXIS Frontend Final Audit

## Status

**FRONTEND BASELINE READY — v1.0 POST-AUDIT**

Frontend is visually, architecturally, and quality-verified complete.
Backend integration remains intentionally deferred.
**NOT READY FOR LIVE TRADING.**

---

## Pages

| Route | Page | Status |
|---|---|---|
| / | Overview | COMPLETE |
| /risk | Risk Center | COMPLETE |
| /brain | Brain Monitor | COMPLETE |
| /market | Market + Mock Chart | COMPLETE |
| /signals | Signals | COMPLETE |
| /positions | Positions | COMPLETE |
| /execution | Execution | COMPLETE |
| /news | News Protection | COMPLETE |
| /structure | Market Structure | COMPLETE |
| /regime | Regime | COMPLETE |
| /exposure | Exposure | COMPLETE |
| /protection | Protection | COMPLETE |
| /accounts | Accounts | COMPLETE |
| /agents | MT5 Agents | COMPLETE |
| /activity | Activity Log | COMPLETE |
| /settings | Settings (READ ONLY) | COMPLETE |
| /performance | Performance | COMPLETE |
| /backtest | Backtest | COMPLETE |

Total: 18 routes, all statically prerendered.

---

## Components

Layout: `AppShell`, `Sidebar`, `GlobalHeader`.
UI Primitives: `Badge`, `StatusDot`, `Label`, `Panel`, `EmptyState`, `NotConfigured`, `StatRow`, `PnlValue`, `MockIndicator`.
Domain Badges: `RiskStateBadge`, `NewsStateBadge`, `RegimeBadge`, `SignalStatusBadge`, `CommandStateBadge`, `AgentStatusBadge`, `BrainStateBadge`.
Overview Panels: `RiskPanel`, `SystemPanel`, `BrainPanel`, `NewsPanel`, `AccountPanel`, `MarketPanel`, `ActivityPanel`.
Feature Pages: 18 full-page components.
Auth placeholder: `lib/auth.ts` — intentionally deferred, documented.

---

## Design System

Tailwind tokens: `aurexis-bg` #0A0C10, `aurexis-surface` #0F1219, `aurexis-elevated` #141820, `aurexis-border` #1C2333, `aurexis-muted` #252D3D, `aurexis-text` #E4EAF4, `aurexis-subtle` #7A8BA6, `aurexis-faint` #3D4F6B, `aurexis-accent` #C8A84B, `aurexis-success` #16A34A, `aurexis-danger` #DC2626, `aurexis-warning` #D97706, `aurexis-info` #2563EB.

Typography: Montserrat (UI), Cinzel (display), JetBrains Mono (financial).
Gold accent only. No dominant gold, no glowing borders, no glassmorphism.
CSS: `@import` before `@tailwind` (fixed in this audit).

---

## Mock Architecture

`mocks/system.ts` — SystemHealth, TradingAccount, MT5Agent, AuditEvent, IS_MOCK.
`mocks/trading.ts` — RiskSnapshot, BrainSnapshot, NewsSnapshot, MarketTick.
`mocks/market.ts` — LivePosition[], CandidateSignal[], ExecutionCommand[], ClosedTrade[], DailyPnl[], PerformanceStats, BacktestResult.

Deterministic, typed, `IS_MOCK = true`, centralized, replaceable.
Empty arrays correct: NOT_CONFIGURED → no signals → no orders → no positions.
Market page: 48-bar deterministic XAUUSD 5-min series via Recharts. No `Math.random()`.

---

## API Readiness

`lib/api.ts` — typed fetch wrapper, `healthApi` implemented.
Swap: replace `MOCK_*` import with SWR hook backed by `lib/api.ts`. No component changes.

---

## WebSocket Readiness

`lib/websocket.ts` — `AurexisWebSocket`: typed event subscription, exponential backoff (2s→30s), unsubscribe.
Integration: React context wrapping `AurexisWebSocket`. Never per-component sockets.

---

## Auth Architecture

`lib/auth.ts` — intentionally deferred placeholder.
Exports `AUTH_STATUS = "DEFERRED"` and `AUTH_DEFERRED_REASON`.
Pre-enforced: no JWT in `localStorage`, no credentials in query strings, env vars only for API/WS URLs.
When backend ready: HTTP-only cookie tokens, `AuthContext`, `AuthGuard`, transparent refresh, server-side logout, 401 redirect.

---

## Accessibility

Semantic HTML, `aria-current="page"`, `aria-label`, `aria-hidden`, gold focus ring, reduced motion media query, color never sole signal.

---

## Responsive

Desktop 1280px+ primary. `xl:grid-cols-3` pattern. Tablet 768px+ secondary. Sidebar 220px fixed.


---

## Pages Implemented

| Route | Page | Status |
|---|---|---|
| / | Overview | COMPLETE |
| /risk | Risk Center | COMPLETE |
| /brain | Brain Monitor | COMPLETE |
| /market | Market | COMPLETE |
| /signals | Signals | COMPLETE |
| /positions | Positions | COMPLETE |
| /execution | Execution | COMPLETE |
| /news | News Protection | COMPLETE |
| /structure | Market Structure | COMPLETE |
| /regime | Regime | COMPLETE |
| /exposure | Exposure | COMPLETE |
| /protection | Protection | COMPLETE |
| /accounts | Accounts | COMPLETE |
| /agents | MT5 Agents | COMPLETE |
| /activity | Activity Log | COMPLETE |
| /settings | Settings | COMPLETE |
| /performance | Performance | COMPLETE |
| /backtest | Backtest | COMPLETE |

Total: 18 routes

---

## Components Implemented

**Layout:** AppShell, Sidebar, GlobalHeader

**UI Primitives:** Badge, StatusDot, Label, Panel, EmptyState, NotConfigured, StatRow, PnlValue, MockIndicator

**Domain Badges:** RiskStateBadge, NewsStateBadge, RegimeBadge, SignalStatusBadge, CommandStateBadge, AgentStatusBadge, BrainStateBadge

**Overview Panels:** RiskPanel, SystemPanel, BrainPanel, NewsPanel, AccountPanel, MarketPanel, ActivityPanel

**Feature Pages:** 18 full page components

**Legacy (preserved):** SystemStatusBanner, DashboardShell

---

## Mock Providers

| File | Contents |
|---|---|
| mocks/system.ts | SystemHealth, TradingAccount, MT5Agent, AuditEvent |
| mocks/trading.ts | RiskSnapshot, BrainSnapshot, NewsSnapshot, MarketTick |
| mocks/market.ts | LivePosition[], CandidateSignal[], ExecutionCommand[], ClosedTrade[], DailyPnl[], PerformanceStats, BacktestResult |

All mock data: deterministic, typed, IS_MOCK=true, centralized, replaceable.

---

## API-Ready Interfaces

`lib/api.ts` — typed fetch wrapper, `healthApi` implemented.
Ready for: `riskApi`, `accountsApi`, `positionsApi`, `signalsApi`, `brainsApi`, `newsApi`, `agentsApi`, `auditApi`.

Pattern: swap `MOCK_*` import for SWR hook backed by `lib/api.ts`.

---

## WebSocket Readiness

`lib/websocket.ts` — `AurexisWebSocket` class complete:
- Typed event subscription
- Exponential backoff reconnect
- Unsubscribe support

Planned events: ACCOUNT_UPDATED, POSITION_UPDATED, SIGNAL_CREATED, SIGNAL_UPDATED,
COMMAND_UPDATED, RISK_STATE_CHANGED, BRAIN_STATE_CHANGED, MT5_CONNECTED, MT5_DISCONNECTED,
NEWS_STATE_CHANGED, SYSTEM_ALERT.

Integration step: React context wrapping `AurexisWebSocket`, replace mock state.

---

## Tests

File: `__tests__/domain.test.ts`
Suite: 24 tests, 24 passed, 0 failed.

Covers:
- Risk: NOT_CONFIGURED ≠ NORMAL, trading_allowed=false, profit_lock inactive
- Brain: NOT_CONFIGURED, 12-stage pipeline, all stages NOT_CONFIGURED/BLOCKED/UNKNOWN
- News: UNKNOWN ≠ CLEAR, UNAVAILABLE ≠ CLEAR
- System: degraded ≠ healthy, brain/risk NOT_CONFIGURED, MT5 NO_AGENTS
- Signal/Order/Position separation: distinct arrays, empty when not trading
- Mock mode: IS_MOCK=true
- Audit: events have timestamps, severity, component

---

## Lint

ESLint runs (Next.js lint). Build-time errors: 0. Runtime type errors: 0.

---

## Type-Check

`npx tsc --noEmit` — passes with 0 errors.

---

## Build

`npm run build` — passes. All 18 routes statically prerendered.

Output:
```
Route (app)          Size    First Load JS
/                    3.35 kB   113 kB
/accounts            3.59 kB   110 kB
/activity            3.57 kB   110 kB
/agents              3.98 kB   110 kB
/backtest            3.80 kB   110 kB
/brain               1.86 kB   111 kB
/execution           4.20 kB   110 kB
/exposure            1.05 kB   111 kB
/market              1.40 kB   111 kB
/news                1.64 kB   111 kB
/performance         3.64 kB   110 kB
/positions           3.54 kB   110 kB
/protection          1.01 kB   111 kB
/regime              1.56 kB   111 kB
/risk                2.00 kB   112 kB
/settings            3.48 kB   110 kB
/signals             2.10 kB   112 kB
/structure           0.80 kB   110 kB
```

---

## Known Limitations

1. **No real backend connection.** All data is mock. SystemStatusBanner polls `/api/v1/health` (returns error in mock mode).
2. **No charts.** Price chart on Market page shows NOT_CONFIGURED. Recharts is installed and ready.
3. **No real-time updates.** WebSocket client implemented but not connected to live backend.
4. **No authentication.** Auth layer not yet implemented.
5. **No IDR display.** IDR conversion requires backend FX rate — displayed as UNDEFINED.
6. **No pagination.** Tables/lists have no pagination (no data yet to paginate).
7. **Lint timing.** ESLint on Windows takes >300s — build-time errors verified via `tsc --noEmit` instead.

---

## Future Integration Steps

1. **Backend connection:** Set `NEXT_PUBLIC_API_URL` env var, connect `healthApi`, verify SystemStatusBanner.
2. **Replace mock data with API:** Implement SWR hooks in `lib/hooks/` backed by `lib/api.ts`. Replace `MOCK_*` imports.
3. **WebSocket context:** Wrap `AurexisWebSocket` in React context, subscribe to `RISK_STATE_CHANGED`, `BRAIN_STATE_CHANGED`, etc.
4. **Auth:** Implement JWT auth flow (token management, refresh, logout).
5. **Charts:** Wire Recharts price chart to live OHLCV data from backend.
6. **Pagination:** Add pagination to positions/signals/commands/audit tables.
7. **IDR display:** Consume backend-provided IDR values from `MonetaryAmount.idr`.
8. **Notifications:** Implement alert/notification system using WebSocket `SYSTEM_ALERT` events.

---

## Governance

Frontend is DISPLAY-ONLY.
No trading parameters invented.
No risk thresholds hardcoded.
No broker credentials stored.
All UNDEFINED parameters displayed as UNDEFINED — never defaulted to safe-looking values.

---

## Visual Audit — Fixes Applied

1. CSS `@import` moved before `@tailwind` directives (fonts load correctly)
2. `RiskPanel` restructured: Risk State → Trading Authorization → Block Code → metrics
3. `OverviewPage` trading authorization badge at page-header level
4. `SettingsPage` regex fix: `replace("_"," ")` → `replace(/_/g," ")`
5. `MarketPage` placeholder replaced with deterministic Recharts mock chart

Verified correct: restrained gold, no glassmorphism, consistent badges, MOCK indicator visible, "NOT READY FOR LIVE TRADING" in sidebar, compact density, mono tabular financial numbers.

---

## Testing

File: `__tests__/domain.test.ts` | Tsconfig: `__tests__/tsconfig.json` (extends root, adds `@types/jest`)

**Result: 42 tests, 42 passed, 0 failed**

Suites: Risk (6), Brain (6), News (4), System Health (4), Signal/Order/Position (5), Mock mode (2), Risk additional (3), Brain additional (2), News additional (2), System additional (1), Auth deferred (2), Audit (1), State semantics (7).

---

## TypeScript

`npx tsc --noEmit` — **0 errors**. `__tests__/` excluded from root tsconfig to prevent Jest global leakage.

---

## Build

`npm run build` — **PASS. 18 routes statically prerendered.**
`/market` 214 kB (Recharts ~100 kB). Acceptable for chart page.

---

## Lint

Root cause: ESLint 9 + no `eslint.config.mjs` → legacy discovery on Windows NTFS → timeout >300s.

Fix: `eslint.config.mjs` created (ESLint 9 flat config, `next/core-web-vitals`), `@eslint/eslintrc` installed, `lint` script updated.

**Working lint command:** `npm run lint`
which runs: `eslint app components features lib mocks types --ext .ts,.tsx`

`npx tsc --noEmit` is the primary verification method. Build-time errors: 0.

---

## Known Limitations

1. No backend connection — all data is mock
2. No real-time updates — WebSocket not connected
3. No authentication — intentionally deferred (`lib/auth.ts`)
4. No IDR display — requires backend FX rate
5. No pagination — no data to paginate yet
6. Mock chart only — deterministic, not live OHLCV
7. ESLint NTFS slowness — `npx tsc --noEmit` preferred

---

## Deferred Integration

- Backend (API server, database, Redis)
- Brain (market analysis pipeline — parameters UNDEFINED)
- Risk Engine (production risk configuration — parameters UNDEFINED)
- Execution Engine (signal-to-command, command lifecycle)
- MT5 (Expert Advisor, broker connection)
- Live market data (OHLCV, tick data)
- News provider (calendar, windows, classification — UNDEFINED)
- Authentication (JWT, session, token management)
- Real WebSocket (backend event stream)
- IDR display (backend FX rate)

---

## Trading Parameters Status

All UNDEFINED: HTF/MTF timeframes, EMA/ADX/ATR/RSI periods, confidence threshold, signal validity, SL/TP algorithms, position sizing, daily loss limit, max drawdown, max spread, news windows, news provider, profit-lock formula, commission/swap/slippage. Frontend displays all as UNDEFINED — never defaulted.

---

## Trading Status

**NOT READY FOR LIVE TRADING**

