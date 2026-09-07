"use client";
/** Signals page — real API with WebSocket real-time invalidation. */
import { useEffect } from "react";
import { Panel, EmptyState, NotConfigured, Badge } from "@/components/ui/primitives";
import { useSignals } from "@/lib/hooks/useSignals";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";
import { useWebSocket } from "@/lib/websocket-context";

export function SignalsPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data, error, refetch } = useSignals();
  const brain = useBrain(selectedAccountId);
  const { subscribe } = useWebSocket();

  // Real-time: refetch signals when SIGNAL_CREATED arrives
  useEffect(() => {
    const unsub = subscribe("SIGNAL_CREATED", () => {
      void refetch();
    });
    return unsub;
  }, [subscribe, refetch]);

  const brainNotConfigured = brain.status === "OK" && brain.data.brain_state === "NOT_CONFIGURED";
  const signals = status === "OK" ? data.signals : [];
  const backendNote = status === "OK" ? data.note : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Signals</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Candidate signals from Brain. SIGNAL ≠ ORDER ≠ POSITION.</p>
      </div>

      {brainNotConfigured && (
        <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-warning font-medium">Brain NOT CONFIGURED — no signals will be generated</p>
          <p className="text-2xs text-aurexis-faint mt-1">Strategy parameters are UNDEFINED. No candidate signals produced until parameters are defined and approved.</p>
        </div>
      )}

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

      <Panel title="Active Signals">
        {status !== "OK" ? null : signals.length === 0 ? (
          <EmptyState title="No signals" description="No candidate signals. Brain must be configured and market must be READY." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-aurexis-border">
                  {["Signal ID", "Direction", "Status"].map(h => (
                    <th key={h} className="px-4 py-2 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(signals as Record<string, unknown>[]).map((sig, i) => (
                  <tr key={String(sig.signal_id ?? i)} className="border-b border-aurexis-border/40">
                    <td className="px-4 py-2 font-mono text-aurexis-faint text-2xs">{String(sig.signal_id ?? "—").slice(0, 8)}…</td>
                    <td className="px-4 py-2"><Badge variant={String(sig.direction) === "BUY" ? "success" : "danger"}>{String(sig.direction ?? "—")}</Badge></td>
                    <td className="px-4 py-2 font-mono text-2xs text-aurexis-faint">{String(sig.status ?? "—")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="bg-aurexis-surface border border-aurexis-border rounded px-4 py-3">
        <p className="text-2xs text-aurexis-faint">
          <span className="text-aurexis-subtle font-medium">Signal lifecycle: </span>
          CANDIDATE_FORMING → CANDIDATE_READY → NEWS_BLOCKED ⇄ CANDIDATE_READY → PENDING_RISK → RISK_APPROVED → FORWARDED (terminal) | RISK_REJECTED (terminal) | EXPIRED (terminal) | INVALIDATED (terminal)
        </p>
      </div>
    </div>
  );
}

