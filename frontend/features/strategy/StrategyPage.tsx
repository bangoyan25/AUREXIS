"use client";
import { useState } from "react";
import { Panel, EmptyState, Badge } from "@/components/ui/primitives";
import { useStrategy } from "@/lib/hooks/useStrategy";
import { useSelectedAccount } from "@/lib/account-context";

function StatusBadge({ value }: { value: string | null | boolean }) {
  if (value === null || value === undefined) return <span className="text-aurexis-faint">—</span>;
  if (value === "ALLOW" || value === "ENABLED") return <Badge variant="success">{String(value)}</Badge>;
  if (value === "BLOCK" || value === "BLOCKED" || value === "DISABLED") return <Badge variant="danger">{String(value)}</Badge>;
  if (value === "DRY_RUN" || value === "SKIPPED") return <Badge variant="warning">{String(value)}</Badge>;
  return <span className="text-aurexis-subtle font-mono text-2xs">{String(value)}</span>;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-aurexis-border/30 last:border-0">
      <span className="text-2xs uppercase tracking-wide text-aurexis-faint font-medium">{label}</span>
      <span className="text-xs text-right">{value}</span>
    </div>
  );
}

export function StrategyPage() {
  const { selectedAccountId } = useSelectedAccount();
  const strategy = useStrategy(selectedAccountId);
  const [dryRunMode, setDryRunMode] = useState(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const s = strategy.status === "OK" ? strategy.state : null;
  const sig = strategy.status === "OK" ? strategy.latestSignal : null;

  const handleEnable = async () => {
    setActionMsg(null);
    try { await strategy.enable(dryRunMode); setActionMsg("Strategy enabled."); }
    catch (e: unknown) { setActionMsg(`Error: ${e instanceof Error ? e.message : String(e)}`); }
  };

  const handleDisable = async () => {
    setActionMsg(null);
    try { await strategy.disable(); setActionMsg("Strategy disabled."); }
    catch (e: unknown) { setActionMsg(`Error: ${e instanceof Error ? e.message : String(e)}`); }
  };

  const handleEvaluate = async () => {
    setActionMsg(null);
    try {
      const res = await strategy.evaluate();
      if (res) setActionMsg(`Signal: ${res.signal_direction} | Risk: ${res.risk_decision ?? "—"}`);
    } catch (e: unknown) { setActionMsg(`Error: ${e instanceof Error ? e.message : String(e)}`); }
  };

  if (!selectedAccountId) {
    return (
      <div className="space-y-4">
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Strategy Engine</h1>
        <EmptyState title="No account selected" description="Select a trading account." />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Strategy Engine</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Server-side intelligence. Signal ≠ Order ≠ Position.</p>
      </div>
      <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
        <p className="text-2xs text-aurexis-warning font-medium uppercase tracking-wide">Dry-Run default. No broker order in Dry-Run mode.</p>
        <p className="text-2xs text-aurexis-faint mt-1">Risk Gate is always authoritative. Strategy never bypasses risk.</p>
      </div>
      {strategy.status === "LOADING" && <div className="px-4 py-8 text-center"><span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span></div>}
      {strategy.status === "ERROR" && <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3"><p className="text-xs text-aurexis-danger font-medium">ERROR — {strategy.error}</p></div>}
      {strategy.status === "OK" && s && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Panel title="Engine State">
            <div className="px-4 py-2">
              <Row label="Enabled" value={<StatusBadge value={s.enabled ? "ENABLED" : "DISABLED"} />} />
              <Row label="Mode" value={<StatusBadge value={s.dry_run ? "DRY_RUN" : "LIVE DEMO"} />} />
              <Row label="Strategy ID" value={<span className="font-mono text-2xs">{s.strategy_id}</span>} />
              <Row label="Version" value={<span className="font-mono text-2xs">{s.strategy_version}</span>} />
              <Row label="Symbol" value={<span className="font-mono text-2xs">{s.symbol}</span>} />
              <Row label="Timeframe" value={<span className="font-mono text-2xs">{s.timeframe}</span>} />
            </div>
          </Panel>
          <Panel title="Last Evaluation">
            <div className="px-4 py-2">
              <Row label="Signal" value={s.last_signal_direction ? <Badge variant={s.last_signal_direction === "BUY" ? "success" : "danger"}>{s.last_signal_direction}</Badge> : <span className="text-aurexis-faint">—</span>} />
              <Row label="Signal At" value={<span className="font-mono text-2xs">{s.last_signal_at ? new Date(s.last_signal_at).toLocaleString() : "—"}</span>} />
              <Row label="Risk" value={<StatusBadge value={s.last_risk_decision} />} />
              <Row label="Risk Code" value={<span className="font-mono text-2xs text-aurexis-faint">{s.last_risk_reason_code ?? "—"}</span>} />
              <Row label="Execution" value={<span className="font-mono text-2xs">{s.last_execution_status ?? "—"}</span>} />
            </div>
          </Panel>
          <Panel title="Latest Candidate Signal">
            {sig ? (
              <div className="px-4 py-2">
                <Row label="Signal ID" value={<span className="font-mono text-2xs text-aurexis-faint">{sig.signal_id.slice(0,12)}…</span>} />
                <Row label="Symbol" value={<span className="font-mono text-2xs">{sig.symbol}</span>} />
                <Row label="Direction" value={<Badge variant={sig.direction === "BUY" ? "success" : "danger"}>{sig.direction}</Badge>} />
                <Row label="Status" value={<span className="font-mono text-2xs">{sig.status}</span>} />
                <Row label="Generated" value={<span className="font-mono text-2xs text-aurexis-faint">{new Date(sig.generated_at).toLocaleString()}</span>} />
              </div>
            ) : <EmptyState title="No signals" description="No candidate signals generated yet." />}
          </Panel>
          <Panel title="Controls">
            <div className="px-4 py-4 space-y-4">
              <div className="flex items-center gap-3">
                <input type="checkbox" id="dryrun-toggle" checked={dryRunMode} onChange={(e) => setDryRunMode(e.target.checked)} className="accent-aurexis-accent" />
                <label htmlFor="dryrun-toggle" className="text-xs text-aurexis-subtle">Dry-Run mode</label>
              </div>
              <div className="flex flex-wrap gap-2">
                <button onClick={handleEnable} className="px-3 py-1.5 text-xs bg-aurexis-accent/10 text-aurexis-accent border border-aurexis-accent/30 rounded hover:bg-aurexis-accent/20 transition-colors">Enable</button>
                <button onClick={handleDisable} className="px-3 py-1.5 text-xs bg-aurexis-danger/10 text-aurexis-danger border border-aurexis-danger/30 rounded hover:bg-aurexis-danger/20 transition-colors">Disable</button>
                <button onClick={handleEvaluate} disabled={strategy.evaluating || !s.enabled} className="px-3 py-1.5 text-xs bg-aurexis-muted text-aurexis-text border border-aurexis-border rounded disabled:opacity-40 disabled:cursor-not-allowed">{strategy.evaluating ? "Evaluating…" : "Evaluate Now"}</button>
              </div>
              {actionMsg && <div className="bg-aurexis-surface border border-aurexis-border rounded px-3 py-2"><p className="text-2xs font-mono text-aurexis-subtle">{actionMsg}</p></div>}
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
