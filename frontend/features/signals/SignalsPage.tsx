"use client";
/**
 * Signals & Brain Intelligence — Strategy Engine State & Candidate Signal Observability.
 */
import { useEffect, useState } from "react";
import { Panel, EmptyState, Badge, StatRow } from "@/components/ui/primitives";
import { useStrategy } from "@/lib/hooks/useStrategy";
import { useSelectedAccount } from "@/lib/account-context";
import { useWebSocket } from "@/lib/websocket-context";

export function SignalsPage() {
  const { selectedAccountId } = useSelectedAccount();
  const strategy = useStrategy(selectedAccountId);
  const { subscribe } = useWebSocket();
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [evalMsg, setEvalMsg] = useState<string | null>(null);

  // Real-time: refetch signals when SIGNAL_CREATED arrives
  useEffect(() => {
    const unsub = subscribe("SIGNAL_CREATED", () => {
      void strategy.refresh();
    });
    return unsub;
  }, [subscribe, strategy]);

  const s = strategy.status === "OK" ? strategy.state : null;
  const sig = strategy.status === "OK" ? strategy.latestSignal?.signal : null;

  const handleEvaluate = async () => {
    setEvaluating(true);
    setEvalMsg(null);
    try {
      const res = await strategy.evaluate();
      if (res) {
        setEvalMsg(
          `Evaluated candle: ${res.candle_ts ? new Date(res.candle_ts).toLocaleTimeString() : "Live"} | Direction: ${
            res.signal_direction
          } | Status: ${res.execution_status}`
        );
      }
    } catch (err: unknown) {
      setEvalMsg(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Strategy Signals & Brain Intelligence
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Server-side strategy engine evaluation. SIGNAL ≠ ORDER ≠ POSITION.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={s?.enabled ? "success" : "muted"}>
            {s?.enabled ? "ENGINE ENABLED" : "ENGINE STANDBY"}
          </Badge>
          <Badge variant={s?.dry_run ? "warning" : "danger"}>
            {s?.dry_run ? "DRY-RUN MODE" : "LIVE EXECUTION"}
          </Badge>
        </div>
      </div>

      {evalMsg && (
        <div className="p-3 bg-aurexis-surface border border-aurexis-accent/30 rounded text-xs text-aurexis-accent font-mono flex items-center justify-between">
          <span>{evalMsg}</span>
          <button
            onClick={() => setEvalMsg(null)}
            className="text-3xs text-aurexis-faint hover:text-aurexis-text"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Grid: Strategy State & Latest Signal */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Strategy Engine Parameters */}
        <Panel title="AUREXIS-STRAT-1.0.0 Configuration">
          <div className="px-4 py-3">
            <StatRow
              label="Engine Status"
              value={
                <Badge variant={s?.enabled ? "success" : "muted"}>
                  {s?.enabled ? "ACTIVE" : "STANDBY"}
                </Badge>
              }
            />
            <StatRow
              label="Evaluation Mode"
              value={
                <Badge variant={s?.dry_run ? "warning" : "danger"}>
                  {s?.dry_run ? "DRY RUN (No Broker Orders)" : "LIVE DEMO EXECUTION"}
                </Badge>
              }
            />
            <StatRow label="Strategy ID" value={<span className="font-mono text-2xs">{s?.strategy_id ?? "AUREXIS_CORE"}</span>} />
            <StatRow label="Symbol & Timeframe" value={<span className="font-mono text-2xs">{s?.symbol ?? "XAUUSD"} · {s?.timeframe ?? "M15"}</span>} />
            <StatRow
              label="M15 Bars Synchronized"
              value={
                <span className="font-mono text-2xs text-aurexis-success">
                  {s?.bars_count ?? 0} closed candles ({s?.warmup_status ?? "READY"})
                </span>
              }
            />
            <StatRow
              label="Kill Switch"
              value={
                <Badge variant={strategy.killSwitchActive ? "danger" : "muted"}>
                  {strategy.killSwitchActive ? "ARMED (BLOCK ALL)" : "DISARMED (NORMAL)"}
                </Badge>
              }
            />
            <div className="pt-3 border-t border-aurexis-border/40 flex items-center justify-between">
              <span className="text-3xs font-mono text-aurexis-faint">
                Closed-Bar Invariant: M15 interval required.
              </span>
              <button
                disabled={evaluating || !selectedAccountId}
                onClick={handleEvaluate}
                className="px-3 py-1 bg-aurexis-accent text-aurexis-bg font-semibold text-2xs uppercase tracking-wider rounded transition-colors hover:bg-aurexis-accent/90 disabled:opacity-50"
              >
                {evaluating ? "Evaluating..." : "Run Evaluation"}
              </button>
            </div>
          </div>
        </Panel>

        {/* Latest Candidate Signal */}
        <Panel title="Latest Candidate Signal">
          {sig ? (
            <div className="px-4 py-3">
              <StatRow
                label="Direction"
                value={
                  <Badge variant={sig.direction === "BUY" ? "success" : sig.direction === "SELL" ? "danger" : "muted"}>
                    {sig.direction}
                  </Badge>
                }
              />
              <StatRow label="Setup Type" value={<span className="font-mono text-2xs text-aurexis-accent">{sig.setup_type ?? "CONTINUATION"}</span>} />
              <StatRow
                label="Confidence Score"
                value={
                  <span className="font-mono text-2xs font-semibold text-aurexis-text">
                    {sig.confidence_score ? `${(parseFloat(sig.confidence_score) * 100).toFixed(0)}%` : "70%"}
                  </span>
                }
              />
              <StatRow
                label="Entry Reference"
                value={<span className="font-mono text-2xs">{sig.entry_reference ?? "Current Market"}</span>}
              />
              <StatRow
                label="Suggested SL"
                value={<span className="font-mono text-2xs text-aurexis-danger">{sig.suggested_stop_loss ?? "—"}</span>}
              />
              <StatRow
                label="Suggested TP"
                value={<span className="font-mono text-2xs text-aurexis-success">{sig.suggested_take_profit ?? "—"}</span>}
              />
              <StatRow
                label="Generated At"
                value={
                  <span className="font-mono text-3xs text-aurexis-faint">
                    {sig.generated_at ? new Date(sig.generated_at).toLocaleString() : "—"}
                  </span>
                }
              />
            </div>
          ) : (
            <div className="px-4 py-6 text-center">
              <p className="text-xs text-aurexis-subtle font-mono">
                Last Signal: {s?.last_signal_direction ?? "NONE"}
              </p>
              <p className="text-2xs text-aurexis-faint mt-1">
                {s?.last_signal_reason || "Awaiting closed M15 bar trigger that satisfies all 6 evidence dimensions."}
              </p>
            </div>
          )}
        </Panel>
      </div>

      {/* 6 Evidence Dimensions Architecture */}
      <Panel title="6-Dimension Multi-Factor Intelligence (Scoring Engine)">
        <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <div className="bg-aurexis-bg/50 border border-aurexis-border/50 rounded p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-2xs font-mono font-medium text-aurexis-text">1. Market Structure</span>
              <span className="text-3xs font-mono text-aurexis-accent font-semibold">25% WEIGHT</span>
            </div>
            <p className="text-3xs text-aurexis-faint leading-relaxed">
              Swing High/Low detection, Break of Structure (BOS) with ATR displacement & CHoCH.
            </p>
          </div>

          <div className="bg-aurexis-bg/50 border border-aurexis-border/50 rounded p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-2xs font-mono font-medium text-aurexis-text">2. Setup Engine</span>
              <span className="text-3xs font-mono text-aurexis-accent font-semibold">25% WEIGHT</span>
            </div>
            <p className="text-3xs text-aurexis-faint leading-relaxed">
              Breakouts, Fakeout Reversals, Retest confirmations & Liquidity sweeping events.
            </p>
          </div>

          <div className="bg-aurexis-bg/50 border border-aurexis-border/50 rounded p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-2xs font-mono font-medium text-aurexis-text">3. Trend Engine</span>
              <span className="text-3xs font-mono text-aurexis-accent font-semibold">20% WEIGHT</span>
            </div>
            <p className="text-3xs text-aurexis-faint leading-relaxed">
              EMA 20 & EMA 50 alignment, Wilder ADX & Directional Movement Index (DI+/DI-).
            </p>
          </div>

          <div className="bg-aurexis-bg/50 border border-aurexis-border/50 rounded p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-2xs font-mono font-medium text-aurexis-text">4. Momentum Engine</span>
              <span className="text-3xs font-mono text-aurexis-accent font-semibold">10% WEIGHT</span>
            </div>
            <p className="text-3xs text-aurexis-faint leading-relaxed">
              RSI 14 with Bullish (&gt;52) and Bearish (&lt;48) zones and exhaustion suppression.
            </p>
          </div>

          <div className="bg-aurexis-bg/50 border border-aurexis-border/50 rounded p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-2xs font-mono font-medium text-aurexis-text">5. Volatility Engine</span>
              <span className="text-3xs font-mono text-aurexis-accent font-semibold">10% WEIGHT</span>
            </div>
            <p className="text-3xs text-aurexis-faint leading-relaxed">
              Normalized ATR(14) ratio against rolling baseline (50 bars).
            </p>
          </div>

          <div className="bg-aurexis-bg/50 border border-aurexis-border/50 rounded p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-2xs font-mono font-medium text-aurexis-text">6. Regime Filter</span>
              <span className="text-3xs font-mono text-aurexis-accent font-semibold">10% WEIGHT</span>
            </div>
            <p className="text-3xs text-aurexis-faint leading-relaxed">
              Hysteresis-based classification: TREND_UP, TREND_DOWN, RANGE, HIGH_VOLATILITY, TRANSITION.
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}
