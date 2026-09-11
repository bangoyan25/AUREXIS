"use client";
/**
 * Market Regime — Anti-Flapping Hysteresis & Volatility Classification Engine.
 */
import { Panel, Badge } from "@/components/ui/primitives";
import { RegimeBadge } from "@/components/ui/badges";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";

interface RegimeItem {
  state: string;
  name: string;
  desc: string;
  status: string;
  variant: "success" | "danger" | "warning" | "accent" | "muted";
}

const REGIME_MATRIX: RegimeItem[] = [
  {
    state: "TREND_UP",
    name: "Strong Bullish Trend",
    desc: "Price above EMA 20 & 50 with Wilder ADX > 20 and DI+ dominant. Long continuation setups prioritized.",
    status: "TRADE PERMITTED",
    variant: "success",
  },
  {
    state: "TREND_DOWN",
    name: "Strong Bearish Trend",
    desc: "Price below EMA 20 & 50 with Wilder ADX > 20 and DI- dominant. Short continuation setups prioritized.",
    status: "TRADE PERMITTED",
    variant: "success",
  },
  {
    state: "RANGE",
    name: "Consolidation Range",
    desc: "ADX < 20 and price fluctuating between defined support/resistance. Range-boundary breakouts & fakeouts monitored.",
    status: "TRADE PERMITTED",
    variant: "accent",
  },
  {
    state: "TRANSITION",
    name: "Regime Transition (Hysteresis)",
    desc: "Market structure shifting. Requires 2 consecutive closed M15 bars to confirm before re-enabling new entries.",
    status: "HARD GATE: BLOCKED",
    variant: "warning",
  },
  {
    state: "HIGH_VOLATILITY",
    name: "Abnormal Volatility Surge",
    desc: "Current ATR(14) exceeds 2.2× of 50-bar rolling baseline. Severe slippage risk; new trade entries prohibited.",
    status: "HARD GATE: BLOCKED",
    variant: "danger",
  },
  {
    state: "UNKNOWN",
    name: "Indeterminate State",
    desc: "Insufficient bar history or data desynchronization. Fail-closed: all trade execution strictly blocked.",
    status: "HARD GATE: BLOCKED",
    variant: "danger",
  },
];

export function RegimePage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: brain, error } = useBrain(selectedAccountId);

  const currentRegime = brain?.regime || "TRANSITION";
  const activeDef: RegimeItem =
    REGIME_MATRIX.find((r) => r.state === currentRegime) ?? REGIME_MATRIX[3]!;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Market Regime Classification
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Statistical trend & volatility regime classification with anti-flapping hysteresis.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="accent">ADX(14) THRESHOLD: 20</Badge>
          <Badge variant="success">ROLLING ATR BASELINE: 50</Badge>
        </div>
      </div>

      {status === "NO_ACCOUNT" && (
        <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-warning font-medium">NO ACCOUNT SELECTED</p>
        </div>
      )}

      {status === "ERROR" && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">CONNECTION ERROR — {error}</p>
        </div>
      )}

      {/* Active Regime Status Hero Card */}
      <div className="bg-aurexis-surface border border-aurexis-border rounded p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex flex-col items-center md:items-start gap-2">
          <span className="text-2xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Active Market Regime
          </span>
          <div className="flex items-center gap-3">
            <RegimeBadge state={currentRegime as Parameters<typeof RegimeBadge>[0]["state"]} />
            <span className="font-mono text-sm font-semibold text-aurexis-text">
              {activeDef.name}
            </span>
          </div>
          <p className="text-xs text-aurexis-subtle max-w-xl leading-relaxed mt-1">
            {activeDef.desc}
          </p>
        </div>

        <div className="flex flex-col items-center md:items-end gap-1.5 flex-shrink-0">
          <span className="text-3xs font-mono uppercase tracking-wider text-aurexis-faint">
            GATE POLICY:
          </span>
          <Badge variant={activeDef.variant}>
            {activeDef.status}
          </Badge>
          <span className="text-3xs font-mono text-aurexis-faint">
            Hysteresis Window: 2 Bars
          </span>
        </div>
      </div>

      {/* Complete Regime Classification Matrix */}
      <Panel title="6-State Regime Classification Matrix">
        <div className="divide-y divide-aurexis-border/40">
          {REGIME_MATRIX.map((r) => {
            const isCurrent = r.state === currentRegime;
            return (
              <div
                key={r.state}
                className={`flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 px-4 py-3.5 transition-colors ${
                  isCurrent ? "bg-aurexis-accent/5 border-l-2 border-l-aurexis-accent" : "hover:bg-aurexis-muted/30"
                }`}
              >
                <div className="flex items-center gap-3">
                  <RegimeBadge state={r.state as Parameters<typeof RegimeBadge>[0]["state"]} />
                  <div>
                    <span className="text-xs font-mono font-medium text-aurexis-text block">
                      {r.name}
                    </span>
                    <span className="text-2xs text-aurexis-faint leading-relaxed block mt-0.5">
                      {r.desc}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center flex-shrink-0">
                  {isCurrent && (
                    <span className="text-3xs font-mono text-aurexis-accent font-semibold uppercase">
                      [CURRENT]
                    </span>
                  )}
                  <Badge variant={r.variant}>{r.status}</Badge>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      {/* Engineering Rule Box */}
      <div className="bg-aurexis-surface border border-aurexis-border/60 rounded p-4 text-2xs font-mono text-aurexis-faint space-y-1.5">
        <div className="flex items-center gap-2 text-aurexis-accent font-semibold uppercase tracking-wider">
          <span>Anti-Flapping Invariant</span>
        </div>
        <p className="leading-relaxed">
          The regime classifier maintains internal state across ticks and closed bars. If indicators briefly oscillate near boundary thresholds (e.g. ADX at 19.8 - 20.2), the system stays locked in the prior regime until 2 closed M15 bars confirm the shift.
        </p>
      </div>
    </div>
  );
}
