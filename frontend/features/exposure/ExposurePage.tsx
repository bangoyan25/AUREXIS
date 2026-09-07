"use client";
/** Exposure page — real API. */
import { Panel, StatRow, Badge, EmptyState } from "@/components/ui/primitives";
import { useRisk } from "@/lib/hooks/useRisk";
import { usePositions } from "@/lib/hooks/usePositions";
import { useSelectedAccount } from "@/lib/account-context";

export function ExposurePage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status: riskStatus, data: risk } = useRisk(selectedAccountId);
  const { status: posStatus, data: positions } = usePositions();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Exposure</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Open position exposure summary.</p>
      </div>

      <Panel title="Exposure Summary">
        <div className="px-4 py-3">
          {riskStatus === "NO_ACCOUNT" && (
            <p className="text-2xs text-aurexis-warning">No account selected.</p>
          )}
          {riskStatus === "LOADING" && (
            <p className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</p>
          )}
          {riskStatus === "ERROR" && (
            <p className="text-2xs font-mono text-aurexis-danger">Unable to load risk state</p>
          )}
          {riskStatus === "OK" && risk && (
            <>
              <StatRow label="Risk State"     value={<Badge variant="muted">{risk.risk_state}</Badge>} />
              <StatRow label="Exposure Limit" value={<Badge variant="warning">UNDEFINED</Badge>} />
              <StatRow label="Note"           value={<span className="text-2xs text-aurexis-faint">{risk.note}</span>} />
            </>
          )}
        </div>
      </Panel>

      <Panel title="Open Positions">
        {posStatus === "LOADING" ? (
          <div className="px-4 py-8 text-center">
            <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
          </div>
        ) : posStatus === "ERROR" ? (
          <div className="px-4 py-8 text-center">
            <p className="text-2xs font-mono text-aurexis-danger">Unable to load positions</p>
          </div>
        ) : !positions || positions.positions.length === 0 ? (
          <EmptyState title="No open positions" description="No active trades." />
        ) : (
          <p className="px-4 py-3 text-xs text-aurexis-text">{positions.positions.length} positions open</p>
        )}
      </Panel>
    </div>
  );
}

