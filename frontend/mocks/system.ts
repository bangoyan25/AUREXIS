/** MOCK — system, account, health data */
import type { SystemHealth, TradingAccount, MT5Agent, AuditEvent } from "@/types/domain";

export const IS_MOCK = true;

export const MOCK_ACCOUNT: TradingAccount = {
  id: "mock-account-001",
  label: "HFM Cent Demo",
  broker: "HFM",
  mt5_account_number: "XXXXXXXX",
  broker_currency: "USC",
  is_cent_account: true,
  cent_normalization_factor: 0.01,
  is_active: true,
  mt5_connection_state: "DISCONNECTED",
  created_at: "2026-09-06T00:00:00Z",
};

export const MOCK_SYSTEM_HEALTH: SystemHealth = {
  status: "degraded",
  version: "0.1.0-dev",
  environment: "development",
  check_duration_ms: 14,
  components: {
    backend:     { status: "healthy" },
    database:    { status: "healthy" },
    redis:       { status: "healthy" },
    brain:       { status: "NOT_CONFIGURED", note: "Strategy parameters UNDEFINED" },
    risk_engine: { status: "NOT_CONFIGURED", note: "Risk parameters UNDEFINED" },
    market_data: { status: "healthy" },
    news:        { status: "NOT_CONFIGURED", note: "News provider UNDEFINED" },
    mt5:         { status: "NO_AGENTS", note: "No MT5 agents registered" },
  },
};

export const MOCK_AGENTS: MT5Agent[] = [];

export const MOCK_AUDIT: AuditEvent[] = [
  { id: "evt-001", severity: "INFO",    component: "SYSTEM",      event_type: "system.startup",                description: "AUREXIS initialized — development mode",                      timestamp: "2026-09-06T00:00:00Z" },
  { id: "evt-002", severity: "WARNING", component: "BRAIN",       event_type: "brain.indicator_not_configured", description: "Brain NOT_CONFIGURED — strategy parameters UNDEFINED",       timestamp: "2026-09-06T00:00:01Z" },
  { id: "evt-003", severity: "WARNING", component: "RISK_ENGINE", event_type: "risk.not_configured",           description: "Risk Engine NOT_CONFIGURED — trading is BLOCKED",            timestamp: "2026-09-06T00:00:02Z" },
];
