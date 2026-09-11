"use client";
/** Backtest page — connected to real backend historical simulation engine. */
import { useState } from "react";
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { useBacktest } from "@/lib/hooks/useBacktest";
import { backtestApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export function BacktestPage() {
  const { status, data, error, refetch } = useBacktest();
  const { token } = useAuth();
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const handleRunBacktest = async () => {
    if (!token) return;
    setIsRunning(true);
    setRunError(null);
    try {
      await backtestApi.run(token, {
        symbol: "XAUUSD",
        timeframe: "M15",
        dataset_days: 7,
        initial_balance_usd: 10000,
        slippage_points: 1,
      });
      refetch();
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : "Failed to run simulation");
    } finally {
      setIsRunning(false);
    }
  };

  const isCompleted = status === "OK" && data?.total_trades !== undefined;
  const netPnlNum = parseFloat(data?.total_net_pnl_usd || "0");
  const isProfitable = netPnlNum >= 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Backtest Engine</h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Deterministic historical strategy validation — AUREXIS-STRAT-1.0.0.
          </p>
        </div>
        <button
          onClick={handleRunBacktest}
          disabled={isRunning || !token}
          className="px-3 py-1.5 bg-aurexis-gold/10 hover:bg-aurexis-gold/20 border border-aurexis-gold/30 rounded text-2xs font-mono font-medium text-aurexis-gold transition-colors disabled:opacity-50"
        >
          {isRunning ? "SIMULATING..." : "RUN SIMULATION (7D)"}
        </button>
      </div>

      {status === "LOADING" && (
        <div className="px-4 py-8 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING SIMULATION DATA...</span>
        </div>
      )}

      {(error || runError) && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">SIMULATION ERROR — {error || runError}</p>
        </div>
      )}

      {data?.disclaimer && (
        <div className="bg-aurexis-surface border border-aurexis-border rounded px-4 py-2.5 flex items-center justify-between">
          <span className="text-2xs text-aurexis-faint font-mono">{data.disclaimer}</span>
          <Badge variant="muted">MODEL INVARIANT</Badge>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Simulation Parameters">
          <div className="px-4 py-3">
            <StatRow label="Symbol"         value="XAUUSD" />
            <StatRow label="Strategy"       value="AUREXIS-STRAT-1.0.0" />
            <StatRow label="Timeframe"      value={data?.timeframe || "M15"} />
            <StatRow label="Execution Model" value="Chronological Bid/Ask Replay" />
            <StatRow label="Initial Capital" value={`$${data?.initial_balance_usd || "10,000.00"}`} />
            <StatRow label="Engine Status"   value={<Badge variant={isCompleted ? "success" : "warning"}>{data?.status || "READY"}</Badge>} />
          </div>
        </Panel>

        <Panel title="Performance Metrics">
          <div className="px-4 py-3">
            <StatRow
              label="Net Profit / Loss"
              value={
                <span className={`font-mono font-medium ${isProfitable ? "text-aurexis-success" : "text-aurexis-danger"}`}>
                  {isProfitable ? `+$${data?.total_net_pnl_usd || "0.00"}` : `-$${Math.abs(netPnlNum).toFixed(2)}`}
                </span>
              }
            />
            <StatRow label="Win Rate"        value={<span className="font-mono text-aurexis-text">{data?.win_rate_pct ? `${data.win_rate_pct}%` : "—"}</span>} />
            <StatRow label="Profit Factor"   value={<span className="font-mono text-aurexis-text">{data?.profit_factor || "—"}</span>} />
            <StatRow label="Total Trades"    value={<span className="font-mono text-aurexis-text">{data?.total_trades !== undefined ? `${data.winning_trades || 0}W / ${data.losing_trades || 0}L (${data.total_trades})` : "—"}</span>} />
            <StatRow label="Max Drawdown"    value={<span className="font-mono text-aurexis-warning">{data?.max_drawdown_usd ? `$${data.max_drawdown_usd} (${data.max_drawdown_pct}%)` : "—"}</span>} />
            <StatRow label="Expectancy"      value={<span className="font-mono text-aurexis-text">{data?.expectancy_usd ? `$${data.expectancy_usd}/trade` : "—"}</span>} />
          </div>
        </Panel>
      </div>

      {data?.trades && data.trades.length > 0 && (
        <Panel title={`Simulated Trades (${data.trades.length})`}>
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-2xs">
              <thead className="border-b border-aurexis-border text-aurexis-faint uppercase bg-aurexis-surface">
                <tr>
                  <th className="py-2 px-3">Side</th>
                  <th className="py-2 px-3">Entry Time</th>
                  <th className="py-2 px-3">Entry Price</th>
                  <th className="py-2 px-3">Volume</th>
                  <th className="py-2 px-3">Exit Price</th>
                  <th className="py-2 px-3">Realized PnL</th>
                  <th className="py-2 px-3">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-aurexis-border/50">
                {data.trades.slice(-10).reverse().map((t, idx) => {
                  const pnl = parseFloat(t.realized_pnl_usd);
                  return (
                    <tr key={t.trade_id || idx} className="hover:bg-aurexis-surface/50 transition-colors">
                      <td className="py-2 px-3">
                        <span className={`font-semibold ${t.side === "BUY" ? "text-aurexis-success" : "text-aurexis-danger"}`}>
                          {t.side}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-aurexis-faint">{t.entry_time.slice(0, 16).replace("T", " ")}</td>
                      <td className="py-2 px-3 text-aurexis-text">${t.entry_price}</td>
                      <td className="py-2 px-3 text-aurexis-faint">{t.volume_lots}L</td>
                      <td className="py-2 px-3 text-aurexis-text">${t.exit_price || "—"}</td>
                      <td className={`py-2 px-3 font-semibold ${pnl >= 0 ? "text-aurexis-success" : "text-aurexis-danger"}`}>
                        {pnl >= 0 ? `+$${pnl.toFixed(2)}` : `-$${Math.abs(pnl).toFixed(2)}`}
                      </td>
                      <td className="py-2 px-3 text-aurexis-faint">{t.exit_reason || "CLOSE"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
