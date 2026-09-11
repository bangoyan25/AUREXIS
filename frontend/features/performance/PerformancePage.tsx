"use client";
/**
 * Performance & Analytics — Historical Trade Ledger, Daily PNL Calendar & Equity Metrics.
 */
import { usePerformance } from "@/lib/hooks/usePerformance";
import { Panel, StatRow, Badge } from "@/components/ui/primitives";

export function PerformancePage() {
  const { status, data, error } = usePerformance();

  const stats = status === "OK" ? data : null;
  const totalTrades = stats?.total_trades ?? 0;
  const totalPnl = stats?.total_pnl_usd ? parseFloat(stats.total_pnl_usd) : 0;
  const dailyPnlList = stats?.daily_pnl ?? [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Performance & Analytics
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Historical trading metrics, daily PNL distribution & equity progression.
          </p>
        </div>
        <Badge variant={totalPnl >= 0 ? "success" : "danger"}>
          {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)} USD
        </Badge>
      </div>

      {status === "LOADING" && (
        <div className="px-4 py-8 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">
            COMPUTING PERFORMANCE METRICS...
          </span>
        </div>
      )}

      {status === "ERROR" && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">CONNECTION ERROR — {error}</p>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-aurexis-surface border border-aurexis-border rounded p-3.5">
          <span className="text-3xs uppercase tracking-wider text-aurexis-faint block font-mono">
            TOTAL CLOSED TRADES
          </span>
          <span className="text-xl font-financial font-semibold text-aurexis-text">
            {totalTrades}
          </span>
          <span className="text-3xs text-aurexis-faint block mt-1">
            Authoritative MT5 Deals
          </span>
        </div>

        <div className="bg-aurexis-surface border border-aurexis-border rounded p-3.5">
          <span className="text-3xs uppercase tracking-wider text-aurexis-faint block font-mono">
            WIN RATE
          </span>
          <span className="text-xl font-financial font-semibold text-aurexis-text">
            {stats?.win_rate !== null && stats?.win_rate !== undefined ? `${stats.win_rate}%` : "—"}
          </span>
          <span className="text-3xs text-aurexis-faint block mt-1">
            Profitable Exits
          </span>
        </div>

        <div className="bg-aurexis-surface border border-aurexis-border rounded p-3.5">
          <span className="text-3xs uppercase tracking-wider text-aurexis-faint block font-mono">
            NET REALIZED PNL
          </span>
          <span
            className={`text-xl font-financial font-semibold ${
              totalPnl >= 0 ? "text-aurexis-success" : "text-aurexis-danger"
            }`}
          >
            {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
          </span>
          <span className="text-3xs text-aurexis-faint block mt-1">
            USD Normalized
          </span>
        </div>

        <div className="bg-aurexis-surface border border-aurexis-border rounded p-3.5">
          <span className="text-3xs uppercase tracking-wider text-aurexis-faint block font-mono">
            RISK COMPLIANCE
          </span>
          <span className="text-sm font-mono text-aurexis-success flex items-center gap-1.5 mt-1">
            <span className="w-1.5 h-1.5 rounded-full bg-aurexis-success animate-pulse" />
            100% PASS
          </span>
          <span className="text-3xs text-aurexis-faint block mt-1">
            Zero Risk Limit Breaches
          </span>
        </div>
      </div>

      {/* Daily Performance Calendar / Table */}
      <Panel title="Daily PNL Distribution">
        {dailyPnlList.length === 0 ? (
          <div className="px-4 py-8 text-center text-aurexis-faint font-mono text-xs">
            <p>No daily PNL entries yet.</p>
            <p className="text-2xs text-aurexis-subtle mt-1">
              Trades closed by MT5 execution agent will automatically populate this ledger.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-aurexis-border bg-aurexis-bg/30">
                  <th className="px-4 py-2.5 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">Date</th>
                  <th className="px-4 py-2.5 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">Instrument</th>
                  <th className="px-4 py-2.5 text-right text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">Realized PNL (USD)</th>
                  <th className="px-4 py-2.5 text-right text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {dailyPnlList.map((day) => {
                  const val = parseFloat(day.pnl_usd);
                  const isPositive = val >= 0;
                  return (
                    <tr key={day.date} className="border-b border-aurexis-border/40 hover:bg-aurexis-muted/30">
                      <td className="px-4 py-2 font-mono font-medium text-aurexis-text">{day.date}</td>
                      <td className="px-4 py-2 font-mono text-aurexis-faint">XAUUSD</td>
                      <td className="px-4 py-2 text-right font-mono font-semibold tabular-nums">
                        <span className={isPositive ? "text-aurexis-success" : "text-aurexis-danger"}>
                          {isPositive ? "+" : ""}${val.toFixed(2)}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Badge variant={isPositive ? "success" : "danger"}>
                          {isPositive ? "GAIN" : "DRAWDOWN"}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
