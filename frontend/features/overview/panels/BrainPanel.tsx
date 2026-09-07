"use client";
import { Panel, Label, StatRow, Badge } from "@/components/ui/primitives";
import { BrainStateBadge, RegimeBadge } from "@/components/ui/badges";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";

export function BrainPanel() {
  const { selectedAccountId } = useSelectedAccount();
  const brain = useBrain(selectedAccountId);

  if (!selectedAccountId) {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
          <Label>Brain</Label>
          <Badge variant="muted">NO ACCOUNT</Badge>
        </div>
        <div className="px-4 py-4 text-center">
          <p className="text-2xs text-aurexis-faint">No account selected.</p>
        </div>
      </Panel>
    );
  }

  if (brain.status === "LOADING") {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
          <Label>Brain</Label>
        </div>
        <div className="px-4 py-4 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
        </div>
      </Panel>
    );
  }

  if (brain.status === "ERROR" || !brain.data) {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
          <Label>Brain</Label>
          <Badge variant="danger">ERROR</Badge>
        </div>
        <div className="px-4 py-4 text-center">
          <p className="text-2xs font-mono text-aurexis-danger">Unable to connect to AUREXIS backend</p>
        </div>
      </Panel>
    );
  }

  const b = brain.data;
  // Preserve backend state exactly — brain_state from backend
  const brainMarketState = (b.brain_state as string).toUpperCase();

  return (
    <Panel>
      <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
        <Label>Brain</Label>
        <BrainStateBadge state={brainMarketState as Parameters<typeof BrainStateBadge>[0]["state"]} />
      </div>
      <div className="px-4 py-3">
        {b.active_setup && b.active_setup !== "NOT_CONFIGURED" && (
          <div className="mb-2">
            <Badge variant="muted">SETUP — {b.active_setup}</Badge>
          </div>
        )}
        <StatRow label="Strategy" value={<span className="text-2xs font-mono text-aurexis-faint">{b.strategy_version}</span>} />
        <StatRow label="Regime" value={<RegimeBadge state={b.regime as Parameters<typeof RegimeBadge>[0]["state"]} />} />
        <StatRow label="Trend" value={<Badge variant="muted">{b.trend}</Badge>} />
        <StatRow label="Momentum" value={<Badge variant="muted">{b.momentum}</Badge>} />
      </div>
    </Panel>
  );
}

