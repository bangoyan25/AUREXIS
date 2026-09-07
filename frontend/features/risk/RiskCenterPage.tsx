"use client";
/** Risk Center — full risk dashboard — real API. */
import { Panel, Label, StatRow, NotConfigured, PnlValue, Badge } from "@/components/ui/primitives";
import { RiskStateBadge } from "@/components/ui/badges";
import { useRisk } from "@/lib/hooks/useRisk";
import { useSelectedAccount } from "@/lib/account-context";

export function RiskCenterPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: risk, error } = useRisk(selectedAccountId);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Risk Center</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Authoritative risk state from backend. Frontend display only.</p>
      </div>

      {status === "NO_ACCOUNT" && (
        <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-warning font-medium">NO ACCOUNT SELECTED</p>
          <p className="text-2xs text-aurexis-faint mt-1">Register and select an account to view risk state.</p>
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

      {status === "OK" && risk && (
        <>
          {/* Primary risk state */}
          <div className="bg-aurexis-surface border border-aurexis-border rounded p-6 flex flex-col items-center gap-4">
            <Label>Risk State</Label>
            {risk.risk_state === "NOT_CONFIGURED" ? (
              <NotConfigured name="Risk Engine" detail={risk.note || "All risk parameters are UNDEFINED. No live trading permitted."} />
            ) : (
              <>
                <RiskStateBadge state={risk.risk_state as Parameters<typeof RiskStateBadge>[0]["state"]} />
                <div className="w-full max-w-sm">
                  <StatRow label="Trading" value={risk.trading_allowed ? <Badge variant="success">AUTHORIZED</Badge> : <Badge variant="danger">BLOCKED</Badge>} />
                  {risk.block_reason && <StatRow label="Block reason" value={<span className="text-2xs font-mono text-aurexis-danger">{risk.block_reason}</span>} />}
                  {risk.note && <StatRow label="Note" value={<span className="text-2xs text-aurexis-faint">{risk.note}</span>} />}
                </div>
              </>
            )}
          </div>

          {/* Risk parameters grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <Panel title="Parameters">
              <div className="px-4 py-3">
                <StatRow label="Daily Loss Limit"  value={risk.parameters?.daily_loss_limit_usd !== null ? `$${risk.parameters?.daily_loss_limit_usd}` : <Badge variant="warning">UNDEFINED</Badge>} />
                <StatRow label="Max Drawdown"      value={risk.parameters?.max_drawdown_usd !== null ? `$${risk.parameters?.max_drawdown_usd}` : <Badge variant="warning">UNDEFINED</Badge>} />
                <StatRow label="Max Open Pos"      value={risk.parameters?.max_open_positions !== null ? String(risk.parameters?.max_open_positions) : <Badge variant="warning">UNDEFINED</Badge>} />
                <StatRow label="Risk Per Trade"    value={risk.parameters?.risk_per_trade_pct !== null ? `${risk.parameters?.risk_per_trade_pct}%` : <Badge variant="warning">UNDEFINED</Badge>} />
              </div>
            </Panel>

            <Panel title="Profit Lock">
              <div className="px-4 py-3">
                <StatRow label="Formula"    value={<span className="text-2xs font-mono text-aurexis-faint">{risk.parameters?.profit_lock_formula || "UNDEFINED"}</span>} />
                <StatRow label="Threshold"  value={risk.parameters?.profit_lock_threshold_usd || <Badge variant="warning">UNDEFINED</Badge>} />
                <StatRow label="Floor %"    value={risk.parameters?.profit_lock_floor_pct || <Badge variant="warning">UNDEFINED</Badge>} />
                <StatRow label="DD Ref"     value={risk.parameters?.drawdown_reference || <Badge variant="warning">UNDEFINED</Badge>} />
              </div>
            </Panel>

            <Panel title="Configuration">
              <div className="px-4 py-3">
                <StatRow label="Reset TZ"   value={risk.parameters?.daily_reset_timezone || <Badge variant="warning">UNDEFINED</Badge>} />
                <StatRow label="Note"       value={<span className="text-2xs text-aurexis-faint">{risk.note}</span>} />
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

