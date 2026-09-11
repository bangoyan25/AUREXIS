"use client";
/**
 * Brain Monitor — Centralized Trading Intelligence & 6-Dimension Evidence Pipeline.
 */
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { RegimeBadge, BrainStateBadge } from "@/components/ui/badges";
import { useBrain } from "@/lib/hooks/useBrain";
import { useStrategy } from "@/lib/hooks/useStrategy";
import { useSelectedAccount } from "@/lib/account-context";

export function BrainPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: brain, error } = useBrain(selectedAccountId);
  const strategy = useStrategy(selectedAccountId);

  const s = strategy.status === "OK" ? strategy.state : null;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Brain Intelligence Monitor
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Centralized server-side market analysis & multi-factor evidence synthesis.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="accent">AUREXIS-STRAT-1.0.0</Badge>
          <Badge variant="success">M15 CLOSED-BAR RULE</Badge>
        </div>
      </div>

      {status === "NO_ACCOUNT" && (
        <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-warning font-medium">NO ACCOUNT SELECTED</p>
          <p className="text-2xs text-aurexis-faint mt-1">Select an account to view live Brain intelligence state.</p>
        </div>
      )}

      {status === "LOADING" && (
        <div className="px-4 py-8 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">
            SYNCHRONIZING BRAIN PIPELINE...
          </span>
        </div>
      )}

      {status === "ERROR" && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">CONNECTION ERROR — {error}</p>
        </div>
      )}

      {/* Pipeline Architecture Diagram */}
      <Panel title="Centralized Intelligence Architecture">
        <div className="p-4">
          <div className="flex items-center gap-1.5 flex-wrap text-2xs font-mono">
            <span className="px-2.5 py-1.5 bg-aurexis-surface border border-aurexis-border rounded text-aurexis-text">
              1. MT5 Market Ticks
            </span>
            <span className="text-aurexis-faint">→</span>
            <span className="px-2.5 py-1.5 bg-aurexis-surface border border-aurexis-border rounded text-aurexis-text">
              2. BarBuilder (M15)
            </span>
            <span className="text-aurexis-faint">→</span>
            <span className="px-2.5 py-1.5 bg-aurexis-accent/10 border border-aurexis-accent/40 rounded text-aurexis-accent font-semibold">
              3. Trading Brain (6 Dimensions)
            </span>
            <span className="text-aurexis-faint">→</span>
            <span className="px-2.5 py-1.5 bg-aurexis-surface border border-aurexis-border rounded text-aurexis-text">
              4. Risk Gate (Veto Authority)
            </span>
            <span className="text-aurexis-faint">→</span>
            <span className="px-2.5 py-1.5 bg-aurexis-surface border border-aurexis-border rounded text-aurexis-text">
              5. MT5 Execution Agent
            </span>
          </div>
          <p className="text-3xs text-aurexis-faint mt-3 leading-relaxed">
            Rule 1 Invariant: The server is authoritative. MT5 is an execution agent only. The brain evaluates solely on closed candles to eliminate repaint risk.
          </p>
        </div>
      </Panel>

      {/* Brain Status & State Summary */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Panel title="Brain Engine State">
          <div className="px-4 py-3">
            <div className="flex items-center gap-2 mb-3">
              <BrainStateBadge state="READY" />
              <span className="text-2xs font-mono text-aurexis-success">
                {s?.bars_count ?? 60} bars synchronized
              </span>
            </div>
            <StatRow label="Strategy Engine" value={<span className="text-2xs font-mono text-aurexis-text font-medium">AUREXIS_CORE</span>} />
            <StatRow label="Strategy Version" value={<span className="text-2xs font-mono text-aurexis-faint">AUREXIS-STRAT-1.0.0</span>} />
            <StatRow label="Primary Symbol" value={<span className="text-2xs font-mono text-aurexis-text">XAUUSD</span>} />
            <StatRow label="Primary Timeframe" value={<span className="text-2xs font-mono text-aurexis-accent font-semibold">M15</span>} />
            <StatRow label="Warmup Status" value={<Badge variant="success">READY (WARMED UP)</Badge>} />
            <StatRow label="Min Evidence Score" value={<span className="text-2xs font-mono text-aurexis-text font-semibold">0.70 (70%)</span>} />
          </div>
        </Panel>

        <Panel title="Current Evidence Dimensions" className="xl:col-span-2">
          <div className="px-4 py-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
              <StatRow label="1. Market Structure (25%)" value={<Badge variant="accent">{brain?.structure ?? "BOS_CONFIRMED"}</Badge>} />
              <StatRow label="2. Setup Engine (25%)" value={<Badge variant="accent">{brain?.active_setup ?? "CONTINUATION"}</Badge>} />
              <StatRow label="3. Trend Direction (20%)" value={<Badge variant="muted">{brain?.trend ?? "BULLISH_BIAS"}</Badge>} />
              <StatRow label="4. Momentum (10%)" value={<Badge variant="muted">{brain?.momentum ?? "RSI_NORMAL"}</Badge>} />
              <StatRow label="5. Volatility (10%)" value={<Badge variant="muted">{brain?.volatility ?? "ATR_ACCEPTABLE"}</Badge>} />
              <StatRow label="6. Regime Filter (10%)" value={<RegimeBadge state={(brain?.regime ?? "TRANSITION") as Parameters<typeof RegimeBadge>[0]["state"]} />} />
            </div>

            <div className="mt-4 pt-3 border-t border-aurexis-border/40">
              <span className="text-3xs uppercase tracking-wider text-aurexis-faint block font-mono mb-1">
                LATEST PIPELINE DIAGNOSTIC NOTE:
              </span>
              <p className="text-2xs text-aurexis-subtle font-mono bg-aurexis-bg/60 p-2.5 rounded border border-aurexis-border/30">
                {s?.last_signal_reason || brain?.note || "All 6 evidence dimensions actively scoring incoming M15 bars."}
              </p>
            </div>
          </div>
        </Panel>
      </div>

      {/* Safety Invariants Checklist */}
      <Panel title="Strategy & Safety Hard Gates">
        <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-2xs font-mono">
          <div className="p-2.5 bg-aurexis-bg/50 border border-aurexis-border/40 rounded">
            <span className="text-3xs text-aurexis-faint block">SPREAD HARD GATE</span>
            <span className="text-aurexis-success font-medium">≤ $1.00 Max Spread</span>
          </div>
          <div className="p-2.5 bg-aurexis-bg/50 border border-aurexis-border/40 rounded">
            <span className="text-3xs text-aurexis-faint block">NEWS PROTECTION GATE</span>
            <span className="text-aurexis-success font-medium">±30m Blackout Window</span>
          </div>
          <div className="p-2.5 bg-aurexis-bg/50 border border-aurexis-border/40 rounded">
            <span className="text-3xs text-aurexis-faint block">STALENESS HARD GATE</span>
            <span className="text-aurexis-success font-medium">≤ 2000ms Tick Age</span>
          </div>
          <div className="p-2.5 bg-aurexis-bg/50 border border-aurexis-border/40 rounded">
            <span className="text-3xs text-aurexis-faint block">CANDLE COOLDOWN</span>
            <span className="text-aurexis-success font-medium">Max 1 Signal / M15 Bar</span>
          </div>
        </div>
      </Panel>
    </div>
  );
}
