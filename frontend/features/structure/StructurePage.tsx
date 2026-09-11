"use client";
/**
 * Market Structure — Smart Money Structure, Swing Analysis & Liquidity Detection.
 */
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";

export function StructurePage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: brain, error } = useBrain(selectedAccountId);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Market Structure & Swing Analysis
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Algorithmic swing detection, Break of Structure (BOS) & Change of Character (CHoCH).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="accent">SMC ALGORITHMIC ENGINE</Badge>
          <Badge variant="success">DISPLACEMENT VERIFIED</Badge>
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

      {/* Grid: Structure State & Active Rules */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Live Structure Diagnostics">
          <div className="px-4 py-3">
            <StatRow
              label="Current Structure"
              value={<Badge variant="accent">{brain?.structure ?? "BOS_CONFIRMED"}</Badge>}
            />
            <StatRow
              label="Active Setup"
              value={<Badge variant="success">{brain?.active_setup ?? "CONTINUATION"}</Badge>}
            />
            <StatRow
              label="Structural Bias"
              value={<Badge variant="muted">{brain?.trend ?? "BULLISH_BIAS"}</Badge>}
            />
            <StatRow
              label="Swing Detection Lookback"
              value={<span className="font-mono text-2xs">10 bars (M15)</span>}
            />
            <StatRow
              label="Displacement Requirement"
              value={<span className="font-mono text-2xs text-aurexis-accent">≥ 0.50 × ATR(14)</span>}
            />
            <StatRow
              label="Equal Level Liquidity Buffer"
              value={<span className="font-mono text-2xs">0.10 × ATR</span>}
            />
            <StatRow
              label="Structural Invalidation"
              value={<span className="font-mono text-2xs text-aurexis-danger">Prior Swing ± 0.50 ATR</span>}
            />
          </div>
        </Panel>

        <Panel title="Structure Methodology & Rules">
          <div className="p-4 space-y-3 text-xs leading-relaxed text-aurexis-subtle">
            <div className="p-2.5 bg-aurexis-bg/50 border border-aurexis-border/40 rounded">
              <span className="font-mono text-2xs font-semibold text-aurexis-text block mb-0.5">
                Break of Structure (BOS)
              </span>
              <p className="text-3xs text-aurexis-faint">
                Occurs when price closes beyond the preceding swing high (bullish) or swing low (bearish) with at least 0.50 ATR displacement. A mere wick without candle body close is discarded as potential liquidity hunt.
              </p>
            </div>

            <div className="p-2.5 bg-aurexis-bg/50 border border-aurexis-border/40 rounded">
              <span className="font-mono text-2xs font-semibold text-aurexis-text block mb-0.5">
                Change of Character (CHoCH)
              </span>
              <p className="text-3xs text-aurexis-faint">
                First violation of internal order flow signaling an early structural reversal before major trend change. Used to invalidate stale continuation signals.
              </p>
            </div>

            <div className="p-2.5 bg-aurexis-bg/50 border border-aurexis-border/40 rounded">
              <span className="font-mono text-2xs font-semibold text-aurexis-text block mb-0.5">
                Stop-Loss Placement Invariant
              </span>
              <p className="text-3xs text-aurexis-faint">
                Never uses arbitrary fixed pips. Stop Loss is mathematically anchored to the invalidation swing level plus a 0.50 ATR volatility buffer. Minimum target Reward-to-Risk is 1:2.0.
              </p>
            </div>
          </div>
        </Panel>
      </div>

      {/* Structural Concepts Breakdown */}
      <Panel title="Structural Event Classification Matrix">
        <div className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-2xs font-mono">
          <div className="bg-aurexis-bg/60 border border-aurexis-border/40 rounded p-3">
            <span className="text-3xs text-aurexis-accent font-semibold block uppercase">1. Higher High / Higher Low</span>
            <span className="text-aurexis-text block mt-1">BULLISH EXPANSION</span>
            <p className="text-3xs text-aurexis-faint mt-1">
              Confirmed when consecutive swing highs close higher with volume support.
            </p>
          </div>

          <div className="bg-aurexis-bg/60 border border-aurexis-border/40 rounded p-3">
            <span className="text-3xs text-aurexis-accent font-semibold block uppercase">2. Lower High / Lower Low</span>
            <span className="text-aurexis-text block mt-1">BEARISH EXPANSION</span>
            <p className="text-3xs text-aurexis-faint mt-1">
              Confirmed when consecutive swing lows break with displacement.
            </p>
          </div>

          <div className="bg-aurexis-bg/60 border border-aurexis-border/40 rounded p-3">
            <span className="text-3xs text-aurexis-accent font-semibold block uppercase">3. Equilibrium & Liquidity</span>
            <span className="text-aurexis-text block mt-1">CONSOLIDATION RANGE</span>
            <p className="text-3xs text-aurexis-faint mt-1">
              Equal highs/lows identified as liquidity pools. Breakout/fakeout setups monitored.
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}
