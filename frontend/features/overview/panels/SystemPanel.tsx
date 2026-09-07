"use client";
import { Panel, Label, StatusDot } from "@/components/ui/primitives";
import { useHealth } from "@/lib/hooks/useHealth";

export function SystemPanel() {
  const health = useHealth();

  if (health.status === "LOADING") {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border"><Label>System Health</Label></div>
        <div className="px-4 py-6 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">CONNECTING...</span>
        </div>
      </Panel>
    );
  }

  if (health.status === "ERROR" || !health.data) {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border"><Label>System Health</Label></div>
        <div className="px-4 py-6 text-center">
          <p className="text-2xs font-mono text-aurexis-danger">Unable to connect to AUREXIS backend</p>
          <button
            onClick={() => void health.refetch()}
            className="mt-2 text-2xs font-mono text-aurexis-subtle underline hover:text-aurexis-text"
          >
            RETRY
          </button>
        </div>
      </Panel>
    );
  }

  const h = health.data;
  return (
    <Panel>
      <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
        <Label>System Health</Label>
        <span className="text-2xs font-mono text-aurexis-faint">{h.version}</span>
      </div>
      <div className="px-4 py-2">
        {Object.entries(h.components).map(([key, comp]) => {
          const ok = comp.status === "healthy" || comp.status === "CONFIGURED";
          const warn = comp.status === "degraded" || comp.status === "NO_AGENTS" || comp.status === "NOT_CONFIGURED";
          const dot = ok ? ("success" as const) : warn ? ("warning" as const) : ("danger" as const);
          return (
            <div key={key} className="flex items-center justify-between py-1.5 border-b border-aurexis-border/40 last:border-0">
              <div className="flex items-center gap-1.5">
                <StatusDot color={dot} />
                <Label>{key.replace(/_/g, " ")}</Label>
              </div>
              <span className="text-2xs font-mono text-aurexis-faint">{String(comp.status)}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

