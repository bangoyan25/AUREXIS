"use client";
/** Protection / Profit Lock page — real API. */
import { Panel, StatRow, Badge, NotConfigured } from "@/components/ui/primitives";
import { useRisk } from "@/lib/hooks/useRisk";
import { useSelectedAccount } from "@/lib/account-context";

export function ProtectionPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: risk, error } = useRisk(selectedAccountId);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Protection</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Dynamic profit lock and equity protection. Formula: UNDEFINED.</p>
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

      {status === "OK" && risk && (
        <>
          <div className="bg-aurexis-surface border border-aurexis-border rounded p-6 flex flex-col items-center gap-3">
            <span className="text-2xs font-medium uppercase tracking-widest text-aurexis-subtle">Profit Lock</span>
            <Badge variant="muted">INACTIVE</Badge>
          </div>

          <Panel title="Profit Lock State">
            <div className="px-4 py-3">
              <StatRow label="Formula"     value={<span className="text-2xs font-mono text-aurexis-faint">{risk.parameters?.profit_lock_formula || "UNDEFINED"}</span>} />
              <StatRow label="Threshold"   value={risk.parameters?.profit_lock_threshold_usd || <Badge variant="warning">UNDEFINED</Badge>} />
              <StatRow label="Floor %"     value={risk.parameters?.profit_lock_floor_pct || <Badge variant="warning">UNDEFINED</Badge>} />
              <StatRow label="DD Reference" value={risk.parameters?.drawdown_reference || <Badge variant="warning">UNDEFINED</Badge>} />
              <div className="mt-2 pt-2 border-t border-aurexis-border">
                <p className="text-2xs text-aurexis-faint leading-relaxed">
                  Profit-lock concept: approved. Mathematical formula: UNDEFINED. Not active until formula specified and approved.
                  Frontend displays backend decisions only — never calculates protection thresholds independently.
                </p>
              </div>
            </div>
          </Panel>
        </>
      )}

      <div className="bg-aurexis-surface border border-aurexis-border/50 rounded px-4 py-3">
        <p className="text-2xs text-aurexis-faint leading-relaxed">
          Dynamic profit lock and equity protection parameters must be approved before activation.
        </p>
      </div>
    </div>
  );
}

