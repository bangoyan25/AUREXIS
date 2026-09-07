"use client";
/** Performance / Analytics page — real API. */
import { Panel, StatRow, NotConfigured, Badge } from "@/components/ui/primitives";
import { usePerformance } from "@/lib/hooks/usePerformance";

export function PerformancePage() {
  const { status, data, error } = usePerformance();

  const stats = status === "OK" ? data : null;
  const backendNote = status === "OK" ? data.note : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Performance</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Historical performance analytics.</p>
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
        <div className="bg-aurexis-surface border border-aurexis-border/50 rounded px-4 py-3">
          <p className="text-2xs text-aurexis-faint">{backendNote}</p>
        </div>
      )}

      {!backendNote && status === "OK" && (
        <div className="bg-aurexis-surface border border-aurexis-border/50 rounded px-4 py-3">
          <p className="text-2xs text-aurexis-faint">
            Performance data requires live trading history. Currently: {stats?.total_trades ?? 0} trades. Connect to backend and complete trades to populate.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <Panel title="Trade Stats">
          <div className="px-4 py-3">
            <StatRow label="Total Trades"  value={String(stats?.total_trades ?? 0)} />
            <StatRow label="Win Rate"      value={stats?.total_trades ? (stats.win_rate !== null ? `${stats.win_rate.toFixed(1)}%` : "—") : "—"} />
          </div>
        </Panel>
        <Panel title="PNL">
          <div className="px-4 py-3">
            <StatRow label="Total PNL"    value={stats ? String(stats.total_pnl_usd) : "—"} />
          </div>
        </Panel>
        <Panel title="Status">
          <div className="px-4 py-3">
            <StatRow label="Backend State" value={<Badge variant="muted">{stats?.status ?? "UNKNOWN"}</Badge>} />
          </div>
        </Panel>
      </div>

      <Panel title="Equity Curve">
        <div className="px-4 py-8 text-center">
          <NotConfigured name="Equity Curve" detail="No trade history. Equity curve requires live trade data from backend." />
        </div>
      </Panel>
    </div>
  );
}

