"use client";
import { Panel, Label, StatRow, NotConfigured, Badge } from "@/components/ui/primitives";
import { RiskStateBadge } from "@/components/ui/badges";
import { useRisk } from "@/lib/hooks/useRisk";
import { useSelectedAccount } from "@/lib/account-context";

export function RiskPanel() {
  const { selectedAccountId } = useSelectedAccount();
  const risk = useRisk(selectedAccountId);

  if (!selectedAccountId) {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
          <Label>Risk State</Label>
          <Badge variant="muted">NO ACCOUNT</Badge>
        </div>
        <div className="px-4 py-6 text-center">
          <p className="text-2xs text-aurexis-faint">No account selected. Register or select an account.</p>
        </div>
      </Panel>
    );
  }

  if (risk.status === "LOADING") {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
          <Label>Risk State</Label>
        </div>
        <div className="px-4 py-6 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
        </div>
      </Panel>
    );
  }

  if (risk.status === "ERROR" || !risk.data) {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
          <Label>Risk State</Label>
          <Badge variant="danger">ERROR</Badge>
        </div>
        <div className="px-4 py-6 text-center">
          <p className="text-2xs font-mono text-aurexis-danger">Unable to connect to AUREXIS backend</p>
          <p className="text-2xs text-aurexis-faint mt-1">Check backend service connection.</p>
        </div>
      </Panel>
    );
  }

  const r = risk.data;
  const isNotConfigured = r.risk_state === "NOT_CONFIGURED";

  return (
    <Panel>
      {/* Header row — state is primary signal */}
      <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
        <Label>Risk State</Label>
        <RiskStateBadge state={r.risk_state as Parameters<typeof RiskStateBadge>[0]["state"]} />
      </div>

      {/* Trading authorization — second most important */}
      <div className="px-4 py-2.5 border-b border-aurexis-border/60 flex items-center justify-between">
        <Label>Trading</Label>
        {r.trading_allowed
          ? <Badge variant="success">AUTHORIZED</Badge>
          : <Badge variant="danger">BLOCKED</Badge>
        }
      </div>

      {/* Blocking reason */}
      {r.block_reason && !r.trading_allowed && (
        <div className="px-4 py-2 border-b border-aurexis-border/40 bg-aurexis-danger/5">
          <p className="text-2xs font-mono text-aurexis-danger uppercase tracking-wide">{r.block_reason}</p>
          {r.note && <p className="text-2xs text-aurexis-faint mt-0.5">{r.note}</p>}
        </div>
      )}

      <div className="px-4 py-3">
        {isNotConfigured
          ? <NotConfigured name="Risk Engine" detail={r.note || "Risk parameters UNDEFINED. Trading BLOCKED until configured and approved."} />
          : <>
              <StatRow label="Daily Loss Limit" value={r.parameters?.daily_loss_limit_usd !== null ? `$${r.parameters?.daily_loss_limit_usd}` : <Badge variant="warning">UNDEFINED</Badge>} />
              <StatRow label="Max Drawdown"     value={r.parameters?.max_drawdown_usd !== null ? `$${r.parameters?.max_drawdown_usd}` : <Badge variant="warning">UNDEFINED</Badge>} />
              <StatRow label="Max Open Pos"     value={r.parameters?.max_open_positions !== null ? String(r.parameters?.max_open_positions) : <Badge variant="warning">UNDEFINED</Badge>} />
              <StatRow label="Risk Per Trade"   value={r.parameters?.risk_per_trade_pct !== null ? `${r.parameters?.risk_per_trade_pct}%` : <Badge variant="warning">UNDEFINED</Badge>} />
            </>
        }
      </div>
    </Panel>
  );
}


