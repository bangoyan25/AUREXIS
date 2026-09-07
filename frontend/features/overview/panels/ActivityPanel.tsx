"use client";
import { clsx } from "clsx";
import { Panel } from "@/components/ui/primitives";
import { useActivity } from "@/lib/hooks/useActivity";

function sc(s: string) {
  const upper = s.toUpperCase();
  return upper === "ERROR" || upper === "CRITICAL" ? "text-aurexis-danger"
    : upper === "WARNING" ? "text-aurexis-warning"
    : upper === "INFO" ? "text-aurexis-subtle"
    : "text-aurexis-faint";
}

export function ActivityPanel() {
  const { data: events, loading, error } = useActivity(10);

  if (loading) {
    return (
      <Panel title="Recent Activity">
        <div className="px-4 py-6 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
        </div>
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel title="Recent Activity">
        <div className="px-4 py-6 text-center">
          <p className="text-2xs font-mono text-aurexis-danger">Unable to load activity log</p>
        </div>
      </Panel>
    );
  }

  if (events.length === 0) {
    return (
      <Panel title="Recent Activity">
        <div className="px-4 py-6 text-center">
          <p className="text-xs text-aurexis-subtle">No recent activity events recorded.</p>
        </div>
      </Panel>
    );
  }

  return (
    <Panel title="Recent Activity">
      <div className="divide-y divide-aurexis-border/40">
        {events.map((ev) => (
          <div key={ev.id} className="flex items-start gap-3 px-4 py-2.5">
            <span className={clsx("text-2xs font-mono uppercase w-14 flex-shrink-0 mt-px", sc(ev.severity))}>
              {ev.severity}
            </span>
            <span className="text-2xs text-aurexis-faint font-mono w-28 flex-shrink-0">
              {ev.event_type}
            </span>
            <span className="text-xs text-aurexis-subtle flex-1 leading-relaxed">
              {ev.correlation_id ? `[${ev.correlation_id.slice(0, 8)}] ` : ""}{ev.event_type}
            </span>
            <span className="text-2xs text-aurexis-faint font-mono flex-shrink-0">
              {new Date(ev.occurred_at).toLocaleTimeString()}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

