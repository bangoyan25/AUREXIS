"use client";
/** Brain Monitor — pipeline explainability — real API. */
import { Panel, NotConfigured, StatRow, Badge } from "@/components/ui/primitives";
import { RegimeBadge, BrainStateBadge } from "@/components/ui/badges";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";

export function BrainPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: brain, error } = useBrain(selectedAccountId);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Brain Monitor</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Market analysis pipeline — explainability view.</p>
      </div>

      {status === "NO_ACCOUNT" && (
        <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-warning font-medium">NO ACCOUNT SELECTED</p>
          <p className="text-2xs text-aurexis-faint mt-1">Register and select an account to view Brain monitor.</p>
        </div>
      )}

      {status === "LOADING" && (
        <div className="px-4 py-8 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
        </div>
      )}

      {status === "ERROR" && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">CONNECTION ERROR</p>
          <p className="text-2xs text-aurexis-faint mt-1">{error}</p>
        </div>
      )}

      {status === "OK" && brain && (
        <>
          {/* Status summary */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <Panel title="Brain State">
              <div className="px-4 py-3">
                <div className="flex items-center gap-2 mb-3">
                  <BrainStateBadge state={brain.brain_state.toUpperCase() as Parameters<typeof BrainStateBadge>[0]["state"]} />
                </div>
                <StatRow label="Strategy" value={<span className="text-2xs font-mono text-aurexis-faint">{brain.strategy_id} v{brain.strategy_version}</span>} />
                <StatRow label="Regime" value={<RegimeBadge state={brain.regime as Parameters<typeof RegimeBadge>[0]["state"]} />} />
                <StatRow label="Structure" value={<Badge variant="muted">{brain.structure}</Badge>} />
                <StatRow label="Trend" value={<Badge variant="muted">{brain.trend}</Badge>} />
                <StatRow label="Momentum" value={<Badge variant="muted">{brain.momentum}</Badge>} />
                <StatRow label="Volatility" value={<Badge variant="muted">{brain.volatility}</Badge>} />
              </div>
            </Panel>

            <Panel title="State Details" className="xl:col-span-2">
              <div className="px-4 py-4">
                <div className="flex items-center gap-2 mb-3">
                  <Badge variant={brain.live_trading_enabled ? "success" : "warning"}>
                    {brain.live_trading_enabled ? "LIVE ENABLED" : "LIVE DISABLED"}
                  </Badge>
                  <span className="text-xs font-mono text-aurexis-subtle">Setup: {brain.active_setup}</span>
                </div>
                {brain.note ? (
                  <p className="text-xs text-aurexis-subtle leading-relaxed mb-4">{brain.note}</p>
                ) : (
                  <NotConfigured name="Brain" detail="No analysis available." />
                )}
                <div className="space-y-1.5 pt-2 border-t border-aurexis-border/40">
                  <StatRow label="Confidence" value={brain.confidence !== null ? `${(brain.confidence * 100).toFixed(0)}%` : <Badge variant="muted">N/A</Badge>} />
                  <StatRow label="Live Trading" value={brain.live_trading_enabled ? <Badge variant="danger">STRICTLY DISABLED</Badge> : <Badge variant="success">SAFE (DISABLED)</Badge>} />
                </div>
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

