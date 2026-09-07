"use client";
/** Execution lifecycle page — real API with WebSocket real-time invalidation. */
import { useEffect } from "react";
import { Panel, EmptyState, Badge } from "@/components/ui/primitives";
import { CommandStateBadge } from "@/components/ui/badges";
import { useExecution } from "@/lib/hooks/useExecution";
import { useWebSocket } from "@/lib/websocket-context";

const LIFECYCLE = [
  "SIGNAL", "RISK", "COMMAND", "MT5", "BROKER", "RESULT", "RECONCILIATION"
];

export function ExecutionPage() {
  const { status, data, error, refetch } = useExecution();
  const { subscribe } = useWebSocket();

  // Real-time: refetch execution data on COMMAND_CREATED or COMMAND_UPDATED
  useEffect(() => {
    const unsubCreated = subscribe("COMMAND_CREATED", () => {
      void refetch();
    });
    const unsubUpdated = subscribe("COMMAND_UPDATED", () => {
      void refetch();
    });
    return () => {
      unsubCreated();
      unsubUpdated();
    };
  }, [subscribe, refetch]);

  const commands = status === "OK" ? data.commands : [];
  const backendNote = status === "OK" ? data.note : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Execution</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Command lifecycle. SIGNAL ≠ ORDER ≠ POSITION.</p>
      </div>

      {/* Lifecycle diagram */}
      <Panel title="Execution Lifecycle">
        <div className="px-4 py-4">
          <div className="flex items-center gap-1 flex-wrap">
            {LIFECYCLE.map((step, i) => (
              <div key={step} className="flex items-center gap-1">
                <span className="text-2xs font-mono uppercase tracking-wide bg-aurexis-muted px-2 py-1 rounded text-aurexis-subtle border border-aurexis-border">
                  {step}
                </span>
                {i < LIFECYCLE.length - 1 && (
                  <span className="text-aurexis-faint text-xs">→</span>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {["CREATED","SENT","ACKNOWLEDGED","EXECUTING","FILLED","PARTIALLY_FILLED","REJECTED","EXPIRED","RECONCILED"].map((s) => (
              <CommandStateBadge key={s} state={s as Parameters<typeof CommandStateBadge>[0]["state"]} />
            ))}
          </div>
        </div>
      </Panel>

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

      {backendNote && status === "OK" && (
        <div className="bg-aurexis-surface border border-aurexis-border/50 rounded px-4 py-2">
          <p className="text-2xs text-aurexis-faint">{backendNote}</p>
        </div>
      )}

      <Panel title="Command History">
        {status !== "OK" ? null : commands.length === 0 ? (
          <EmptyState title="No commands" description="No execution commands. Commands created when Risk Engine approves a signal." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-aurexis-border">
                  {["Command ID","Signal","Direction","Volume","State","Created"].map(h => (
                    <th key={h} className="px-4 py-2 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(commands as Record<string, unknown>[]).map((cmd, i) => (
                  <tr key={String(cmd.command_id ?? i)} className="border-b border-aurexis-border/40">
                    <td className="px-4 py-2 font-mono text-2xs text-aurexis-faint">{String(cmd.command_id ?? "—").slice(0,8)}…</td>
                    <td className="px-4 py-2 font-mono text-2xs text-aurexis-faint">{String(cmd.signal_id ?? "—").slice(0,8)}…</td>
                    <td className="px-4 py-2"><Badge variant={String(cmd.direction) === "BUY" ? "success" : "danger"}>{String(cmd.direction ?? "—")}</Badge></td>
                    <td className="px-4 py-2 font-mono">{String(cmd.volume_lots ?? "—")}</td>
                    <td className="px-4 py-2 font-mono text-2xs text-aurexis-faint">{String(cmd.state ?? "—")}</td>
                    <td className="px-4 py-2 text-aurexis-faint">{cmd.created_at ? new Date(String(cmd.created_at)).toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

