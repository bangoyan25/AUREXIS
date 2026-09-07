"use client";
/** Market Structure page — real API. */
import { Panel, StatRow, Badge, NotConfigured } from "@/components/ui/primitives";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";

export function StructurePage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: brain, error } = useBrain(selectedAccountId);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Market Structure</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Swing detection, Break of Structure, CHoCH.</p>
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

      {status === "OK" && brain && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <Panel title="Structure Analysis">
            <div className="px-4 py-3">
              <StatRow label="Structure"       value={<Badge variant="muted">{brain.structure}</Badge>} />
              <StatRow label="Regime"          value={<Badge variant="muted">{brain.regime}</Badge>} />
              <StatRow label="Trend"           value={<Badge variant="muted">{brain.trend}</Badge>} />
              <StatRow label="Momentum"        value={<Badge variant="muted">{brain.momentum}</Badge>} />
              <StatRow label="Volatility"      value={<Badge variant="muted">{brain.volatility}</Badge>} />
              <StatRow label="Active Setup"    value={<Badge variant="muted">{brain.active_setup}</Badge>} />
            </div>
          </Panel>
          <Panel title="Configuration">
            <div className="px-4 py-3">
              <NotConfigured name="Swing Parameters" detail="HTF/MTF timeframes, swing lookback N, MIN_BOS_DISTANCE — all UNDEFINED. Pending backtest calibration." />
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}

