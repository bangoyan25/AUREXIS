"use client";
/** Regime page — real API. */
import { Panel, Badge, NotConfigured } from "@/components/ui/primitives";
import { RegimeBadge } from "@/components/ui/badges";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";

const REGIME_DESCS: Record<string, string> = {
  TREND_UP:       "Strong upward trend. Trend-continuation setups preferred.",
  TREND_DOWN:     "Strong downward trend. Trend-continuation setups preferred.",
  RANGE:          "Market ranging between support/resistance. Breakout setups monitored.",
  BREAKOUT:       "Active breakout of prior range. High-probability continuation or fakeout.",
  HIGH_VOLATILITY:"Abnormally high volatility. No new entries.",
  TRANSITION:     "Regime change in progress. Anti-flapping hysteresis active. No new entries.",
  UNKNOWN:        "Regime cannot be determined. No new entries.",
  NOT_CONFIGURED: "Regime classifier not configured. Parameters UNDEFINED.",
};

export function RegimePage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: brain, error } = useBrain(selectedAccountId);

  const regime = brain?.regime ?? "NOT_CONFIGURED";
  const desc   = REGIME_DESCS[regime] ?? "Unknown regime.";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Regime</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Market regime classification. Hysteresis prevents rapid flapping.</p>
      </div>

      {status === "NO_ACCOUNT" && (
        <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-warning font-medium">NO ACCOUNT SELECTED</p>
        </div>
      )}

      {status === "LOADING" && (
        <div className="px-4 py-8 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
        </div>
      )}

      {status === "ERROR" && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">CONNECTION ERROR — {error}</p>
        </div>
      )}

      {status === "OK" && (
        <div className="bg-aurexis-surface border border-aurexis-border rounded p-6 flex flex-col items-center gap-3">
          <span className="text-2xs font-medium uppercase tracking-widest text-aurexis-subtle">Current Regime</span>
          <RegimeBadge state={regime as Parameters<typeof RegimeBadge>[0]["state"]} />
          <p className="text-xs text-aurexis-subtle text-center max-w-xs leading-relaxed">{desc}</p>
        </div>
      )}

      <Panel title="Regime States">
        <div className="divide-y divide-aurexis-border/40">
          {Object.entries(REGIME_DESCS).map(([state, d]) => (
            <div key={state} className="flex items-start gap-4 px-4 py-3">
              <RegimeBadge state={state as Parameters<typeof RegimeBadge>[0]["state"]} />
              <p className="text-xs text-aurexis-subtle flex-1 leading-relaxed">{d}</p>
            </div>
          ))}
        </div>
      </Panel>
      <div className="bg-aurexis-surface border border-aurexis-border/50 rounded px-4 py-3">
        <p className="text-2xs text-aurexis-faint">HTF/MTF timeframes, ADX threshold, hysteresis parameters: UNDEFINED pending calibration.</p>
      </div>
    </div>
  );
}

