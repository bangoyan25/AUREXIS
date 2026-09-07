"use client";
/** Backtest page — real API. */
import { Panel, StatRow, Badge, NotConfigured } from "@/components/ui/primitives";
import { useBacktest } from "@/lib/hooks/useBacktest";

export function BacktestPage() {
  const { status, data, error } = useBacktest();

  const backendNote = status === "OK" ? data.note : null;
  const backtestStatus = status === "OK" ? data.status : "NOT_CONFIGURED";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Backtest</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Historical strategy validation. Walk-forward ready. No backend business logic in UI.</p>
      </div>

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

      {backendNote && (
        <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-warning font-medium">{backtestStatus}</p>
          <p className="text-2xs text-aurexis-faint mt-1">{backendNote}</p>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Configuration">
          <div className="px-4 py-3">
            <StatRow label="Symbol"         value="XAUUSD" />
            <StatRow label="Dataset"        value={<Badge variant="muted">NOT SET</Badge>} />
            <StatRow label="Date Range"     value={<Badge variant="muted">NOT SET</Badge>} />
            <StatRow label="HTF Timeframe"  value={<Badge variant="warning">UNDEFINED</Badge>} />
            <StatRow label="MTF Timeframe"  value={<Badge variant="warning">UNDEFINED</Badge>} />
            <StatRow label="Status"         value={<Badge variant="warning">{backtestStatus}</Badge>} />
          </div>
        </Panel>
        <Panel title="Execution Model">
          <div className="px-4 py-3">
            <StatRow label="Entry Model"  value="MARKET" />
            <StatRow label="Spread"       value={<Badge variant="warning">UNDEFINED</Badge>} />
            <StatRow label="Slippage"     value={<Badge variant="warning">UNDEFINED</Badge>} />
            <StatRow label="Commission"   value={<Badge variant="warning">UNDEFINED</Badge>} />
            <StatRow label="Risk Engine"  value={<Badge variant="success">Active</Badge>} />
          </div>
        </Panel>
      </div>

      <Panel title="Results">
        <div className="px-4 py-8 text-center">
          <NotConfigured name="Backtest Results" detail="No backtest has been run. Configure parameters and connect to backend to execute." />
        </div>
      </Panel>
    </div>
  );
}

