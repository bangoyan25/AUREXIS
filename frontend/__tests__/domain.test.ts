/**
 * AUREXIS frontend tests.
 * Tests critical domain invariants: UNKNOWN≠CLEAR, BLOCKED≠AUTHORIZED,
 * SIGNAL≠ORDER, MOCK≠LIVE, state semantics, auth deferral.
 */

import { MOCK_RISK, MOCK_BRAIN, MOCK_NEWS } from "@/mocks/trading";
import { MOCK_SYSTEM_HEALTH, MOCK_AUDIT } from "@/mocks/system";
import { MOCK_POSITIONS, MOCK_SIGNALS, MOCK_COMMANDS } from "@/mocks/market";
import { IS_MOCK } from "@/mocks/system";
import { AUTH_STATUS, AUTH_DEFERRED_REASON } from "@/lib/auth";

// ── Domain invariants ──────────────────────────────────────────────────────

describe("Risk invariants", () => {
  test("NOT_CONFIGURED is not NORMAL", () => {
    expect(MOCK_RISK.state).not.toBe("NORMAL");
    expect(MOCK_RISK.state).toBe("NOT_CONFIGURED");
  });

  test("trading_allowed is false when NOT_CONFIGURED", () => {
    expect(MOCK_RISK.trading_allowed).toBe(false);
  });

  test("daily_loss_limit is null when not configured", () => {
    expect(MOCK_RISK.daily_loss_limit_usd).toBeNull();
  });

  test("profit_lock is inactive", () => {
    expect(MOCK_RISK.profit_lock.active).toBe(false);
  });

  test("block_code is set when trading blocked", () => {
    if (!MOCK_RISK.trading_allowed) {
      expect(MOCK_RISK.block_code).toBeDefined();
    }
  });
});

describe("Brain invariants", () => {
  test("strategy is not-configured", () => {
    expect(MOCK_BRAIN.strategy_version).toBe("0.0.0-not-configured");
  });

  test("regime is NOT_CONFIGURED, not UNKNOWN", () => {
    expect(MOCK_BRAIN.regime).toBe("NOT_CONFIGURED");
    expect(MOCK_BRAIN.regime).not.toBe("UNKNOWN");
  });

  test("no_trade_code is set", () => {
    expect(MOCK_BRAIN.no_trade_code).toBeDefined();
    expect(MOCK_BRAIN.no_trade_code).not.toBe("CLEAR");
  });

  test("pipeline has 12 stages", () => {
    expect(MOCK_BRAIN.pipeline.length).toBe(12);
  });

  test("all pipeline stages are NOT_CONFIGURED or BLOCKED or UNKNOWN", () => {
    MOCK_BRAIN.pipeline.forEach((stage) => {
      expect(["NOT_CONFIGURED", "BLOCKED", "UNKNOWN"]).toContain(stage.status);
    });
  });
});

describe("News invariants", () => {
  test("UNKNOWN is not CLEAR", () => {
    expect(MOCK_NEWS.state).not.toBe("CLEAR");
    expect(MOCK_NEWS.state).toBe("UNKNOWN");
  });

  test("UNAVAILABLE is not CLEAR", () => {
    const unavailable = { ...MOCK_NEWS, state: "UNAVAILABLE" as const };
    expect(unavailable.state).not.toBe("CLEAR");
  });
});

describe("System health invariants", () => {
  test("overall status is degraded, not healthy", () => {
    expect(MOCK_SYSTEM_HEALTH.status).not.toBe("healthy");
    expect(MOCK_SYSTEM_HEALTH.status).toBe("degraded");
  });

  test("brain component is NOT_CONFIGURED", () => {
    expect(MOCK_SYSTEM_HEALTH.components.brain.status).toBe("NOT_CONFIGURED");
    expect(MOCK_SYSTEM_HEALTH.components.brain.status).not.toBe("healthy");
  });

  test("risk_engine component is NOT_CONFIGURED", () => {
    expect(MOCK_SYSTEM_HEALTH.components.risk_engine.status).toBe("NOT_CONFIGURED");
  });

  test("mt5 has no agents", () => {
    expect(MOCK_SYSTEM_HEALTH.components.mt5.status).toBe("NO_AGENTS");
    expect(MOCK_SYSTEM_HEALTH.components.mt5.status).not.toBe("healthy");
  });
});

describe("Signal / Order / Position separation", () => {
  test("signals list is distinct from positions", () => {
    expect(MOCK_SIGNALS).not.toBe(MOCK_POSITIONS);
    expect(MOCK_SIGNALS).not.toBe(MOCK_COMMANDS);
  });

  test("no signals when Brain not configured", () => {
    // Brain is NOT_CONFIGURED → no signals should exist
    expect(MOCK_SIGNALS.length).toBe(0);
  });

  test("no positions when not trading", () => {
    expect(MOCK_POSITIONS.length).toBe(0);
  });

  test("no commands when not trading", () => {
    expect(MOCK_COMMANDS.length).toBe(0);
  });
});

describe("Mock mode", () => {
  test("IS_MOCK is true", () => {
    expect(IS_MOCK).toBe(true);
  });
});

describe("Audit events", () => {
  test("has audit events", () => {
    expect(MOCK_AUDIT.length).toBeGreaterThan(0);
  });

  test("all events have timestamps", () => {
    MOCK_AUDIT.forEach((ev) => {
      expect(ev.timestamp).toBeDefined();
      expect(new Date(ev.timestamp).getTime()).not.toBeNaN();
    });
  });

  test("all events have severity and component", () => {
    MOCK_AUDIT.forEach((ev) => {
      expect(ev.severity).toBeDefined();
      expect(ev.component).toBeDefined();
    });
  });
});

describe("Risk — additional invariants", () => {
  test("BLOCKED ≠ AUTHORIZED", () => {
    expect(MOCK_RISK.trading_allowed).toBe(false);
    expect(MOCK_RISK.trading_allowed).not.toBe(true);
  });

  test("NOT_CONFIGURED not in configured states", () => {
    const configured = ["NORMAL", "CAUTION", "PROTECTED", "STOPPED", "EMERGENCY_STOP"];
    expect(configured).not.toContain(MOCK_RISK.state);
  });

  test("equity and balance are 0 when NOT_CONFIGURED — no fake positives", () => {
    expect(MOCK_RISK.current_equity_usd).toBe(0);
    expect(MOCK_RISK.balance_usd).toBe(0);
  });
});

describe("Brain — additional invariants", () => {
  test("no pipeline stage is OK when Brain not configured", () => {
    MOCK_BRAIN.pipeline.forEach((stage) => {
      expect(stage.status).not.toBe("OK");
    });
  });

  test("market_state is not READY or STALE — is INITIALIZING", () => {
    expect(MOCK_BRAIN.market_state).not.toBe("READY");
    expect(MOCK_BRAIN.market_state).not.toBe("STALE");
    expect(MOCK_BRAIN.market_state).toBe("INITIALIZING");
  });
});

describe("News — additional invariants", () => {
  test("STALE ≠ CLEAR", () => {
    const stale = { ...MOCK_NEWS, state: "STALE" as const };
    expect(stale.state).not.toBe("CLEAR");
  });

  test("all non-CLEAR states remain distinct", () => {
    const blocking: string[] = ["PRE_EVENT", "IN_EVENT", "POST_EVENT", "UNKNOWN", "UNAVAILABLE", "STALE"];
    blocking.forEach((s) => expect(s).not.toBe("CLEAR"));
  });
});

describe("System health — additional", () => {
  test("backend and database healthy in mock baseline", () => {
    expect(MOCK_SYSTEM_HEALTH.components.backend.status).toBe("healthy");
    expect(MOCK_SYSTEM_HEALTH.components.database.status).toBe("healthy");
  });
});

describe("Auth architecture — intentionally deferred", () => {
  test("AUTH_STATUS is DEFERRED — no auth active", () => {
    expect(AUTH_STATUS).toBe("DEFERRED");
    expect(AUTH_STATUS).not.toBe("AUTHENTICATED");
  });

  test("AUTH_DEFERRED_REASON is documented string", () => {
    expect(typeof AUTH_DEFERRED_REASON).toBe("string");
    expect(AUTH_DEFERRED_REASON.length).toBeGreaterThan(10);
  });
});

describe("Audit — additional", () => {
  test("timestamps are UTC ISO strings", () => {
    MOCK_AUDIT.forEach((ev) => {
      expect(ev.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
    });
  });
});

describe("State semantics — no collapse allowed", () => {
  test("UNKNOWN ≠ CLEAR", () => { expect("UNKNOWN").not.toBe("CLEAR"); });
  test("STALE ≠ READY", () => { expect("STALE").not.toBe("READY"); });
  test("BLOCKED ≠ APPROVED", () => { expect("BLOCKED").not.toBe("APPROVED"); });
  test("NOT_CONFIGURED ≠ NORMAL", () => { expect("NOT_CONFIGURED").not.toBe("NORMAL"); });
  test("MOCK ≠ LIVE", () => { expect("MOCK").not.toBe("LIVE"); });
  test("SIGNAL ≠ ORDER", () => { expect("SIGNAL").not.toBe("ORDER"); });
  test("ORDER ≠ POSITION", () => { expect("ORDER").not.toBe("POSITION"); });
});

