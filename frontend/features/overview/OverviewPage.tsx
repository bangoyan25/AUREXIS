"use client";
/** AUREXIS Overview — risk-first command center */
import { RiskPanel } from "./panels/RiskPanel";
import { SystemPanel } from "./panels/SystemPanel";
import { BrainPanel } from "./panels/BrainPanel";
import { NewsPanel } from "./panels/NewsPanel";
import { AccountPanel } from "./panels/AccountPanel";
import { MarketPanel } from "./panels/MarketPanel";
import { ActivityPanel } from "./panels/ActivityPanel";
import { usePositions } from "@/lib/hooks/usePositions";
import { useRisk } from "@/lib/hooks/useRisk";
import { useSelectedAccount } from "@/lib/account-context";
import { Panel, Badge } from "@/components/ui/primitives";

export function OverviewPage() {
  const { selectedAccountId } = useSelectedAccount();
  const risk = useRisk(selectedAccountId);
  const positions = usePositions();

  const tradingBlocked = risk.status === "OK" ? !risk.data.trading_allowed : true;
  const positionCount = positions.status === "OK" ? positions.data.positions.length : null;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Overview</h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">XAUUSD · Command Center</p>
        </div>
        {/* Trading authorization — prominent at top level */}
        <div className="flex items-center gap-2">
          <span className="text-2xs font-mono uppercase tracking-widest text-aurexis-subtle">Trading</span>
          {tradingBlocked
            ? <Badge variant="danger">BLOCKED</Badge>
            : <Badge variant="success">AUTHORIZED</Badge>
          }
        </div>
      </div>

      {/* Row 1: Risk (largest) + System + (Brain + News stacked) */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Risk — primary panel, takes full weight */}
        <RiskPanel />
        <SystemPanel />
        <div className="space-y-4">
          <BrainPanel />
          <NewsPanel />
        </div>
      </div>

      {/* Row 2: Account + Positions + Market */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <AccountPanel />
        <Panel title="Positions">
          <div className="px-4 py-6 text-center">
            {positions.status === "LOADING" ? (
              <p className="text-xs text-aurexis-faint animate-pulse">LOADING...</p>
            ) : positions.status === "ERROR" ? (
              <p className="text-xs text-aurexis-danger font-mono">CONNECTION ERROR</p>
            ) : positionCount === 0 ? (
              <p className="text-xs text-aurexis-subtle uppercase tracking-wide">No open positions</p>
            ) : (
              <p className="text-xs text-aurexis-text">{positionCount} open</p>
            )}
          </div>
        </Panel>
        <MarketPanel />
      </div>

      {/* Row 3: Activity — full width */}
      <ActivityPanel />
    </div>
  );
}


