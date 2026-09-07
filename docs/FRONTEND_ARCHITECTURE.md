# AUREXIS Frontend Architecture

## Overview

Next.js 15 (App Router) + TypeScript frontend. Display-only layer.
Backend is authoritative for all trading state.

## Page Architecture

```
/                    — Overview (command center, risk-first)
/risk                — Risk Center (equity, drawdown, profit-lock)
/brain               — Brain Monitor (pipeline explainability)
/market              — Market (XAUUSD state, price)
/signals             — Signals (CandidateSignal lifecycle)
/positions           — Positions (live open positions)
/execution           — Execution (command lifecycle)
/news                — News Protection (event states)
/structure           — Market Structure (BOS, CHoCH)
/regime              — Regime Classification
/exposure            — Exposure summary
/protection          — Profit lock / protection state
/accounts            — Account management
/agents              — MT5 Agents
/activity            — Audit / event log
/settings            — Configuration display
/performance         — Analytics (equity curve, stats)
/backtest            — Backtest interface
```

## Component Architecture

```
components/
  layout/
    AppShell.tsx       — sidebar + header + content wrapper
    Sidebar.tsx        — persistent navigation
    GlobalHeader.tsx   — status indicators, account, price
  ui/
    primitives.tsx     — Badge, Panel, Label, StatRow, EmptyState, etc.
    badges.tsx         — domain-state badges (RiskState, NewsState, etc.)
  system/
    SystemStatusBanner.tsx — legacy (preserved, connected to API)
  dashboard/
    DashboardShell.tsx     — legacy (preserved)

features/
  overview/panels/   — sub-panels for Overview page
  risk/              — RiskCenterPage
  brain/             — BrainPage (pipeline view)
  market/            — MarketPage
  positions/         — PositionsPage
  signals/           — SignalsPage
  execution/         — ExecutionPage
  news/              — NewsPage
  structure/         — StructurePage
  regime/            — RegimePage
  exposure/          — ExposurePage
  protection/        — ProtectionPage
  accounts/          — AccountsPage
  agents/            — AgentsPage
  activity/          — ActivityPage
  settings/          — SettingsPage
  performance/       — PerformancePage
  backtest/          — BacktestPage
```

## State Management

No global state library. Data flows from mock → component.
API-ready: swap MockProvider for ApiProvider — UI unchanged.

```
CURRENT:  mocks/*.ts → components
FUTURE:   lib/api.ts → SWR hooks → components
          lib/websocket.ts → React context → components
```

## Mock Data Architecture

```
mocks/
  system.ts    — SystemHealth, TradingAccount, MT5Agent, AuditEvent
  trading.ts   — RiskSnapshot, BrainSnapshot, NewsSnapshot, MarketTick
  market.ts    — LivePosition, CandidateSignal, ExecutionCommand, ClosedTrade, DailyPnl, PerformanceStats, BacktestResult
```

All mock data is:
- Deterministic (no Math.random())
- Typed against domain types
- Clearly labeled (IS_MOCK = true)
- Centralized — never scattered in JSX
- Replaceable: swap import path only

## API Integration Boundary

`lib/api.ts` — thin typed wrapper around fetch.
Currently only `healthApi.getHealth()` is implemented.
Pattern for new endpoints:
```ts
export const riskApi = {
  getSnapshot: (accountId: string) => apiFetch<RiskSnapshot>(`/api/v1/risk/${accountId}`),
};
```

## WebSocket Integration Boundary

`lib/websocket.ts` — `AurexisWebSocket` class with:
- exponential backoff reconnect
- typed event subscription: `ws.on("RISK_STATE_CHANGED", handler)`
- unsubscribe returns from `ws.on()`

For components: create React context wrapping `AurexisWebSocket`.
Never open WebSocket per-component.

## Design System

Tailwind config tokens:
```
aurexis-bg        #0A0C10   — obsidian background
aurexis-surface   #0F1219   — panels
aurexis-elevated  #141820   — dropdowns
aurexis-border    #1C2333   — borders
aurexis-muted     #252D3D   — hover states
aurexis-text      #E4EAF4   — primary text
aurexis-subtle    #7A8BA6   — secondary text
aurexis-faint     #3D4F6B   — disabled/placeholder
aurexis-accent    #C8A84B   — Aurex gold (restrained)
aurexis-success   #16A34A
aurexis-danger    #DC2626
aurexis-warning   #D97706
aurexis-info      #2563EB
```

Typography: Montserrat (UI), Cinzel (display), JetBrains Mono (financial numbers).
Gold is accent only — never dominant.

## Responsive Strategy

Primary: desktop/laptop (1280px+).
Secondary: tablet (768px+).
Mobile: overview, risk, system status only.
Grid: `grid-cols-1 xl:grid-cols-3` pattern.

## Accessibility

- Semantic HTML (`<nav>`, `<main>`, `<section>`, `<header>`)
- `aria-current="page"` on active nav items
- `aria-label` on nav, header
- `aria-hidden` on decorative elements
- Focus ring: gold outline (`focus-visible`)
- Reduced motion: `@media (prefers-reduced-motion)` in globals.css
- Color never sole signal: status text always accompanies colored dots

## Security Considerations

- No broker credentials in any file
- No JWT in localStorage
- No secrets in mock data
- API base URL via env var only (`NEXT_PUBLIC_API_URL`)
- WS URL via env var only (`NEXT_PUBLIC_WS_URL`)
- Account numbers treated as opaque identifiers
- Cent normalization only server-side

## Not Ready For Live Trading

Trading parameters (HTF/MTF timeframes, EMA/ADX/ATR/RSI periods, confidence thresholds,
SL/TP algorithms, risk limits, news windows) are UNDEFINED.
Frontend correctly displays this state rather than silently defaulting.
