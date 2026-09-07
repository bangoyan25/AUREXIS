"use client";
/** Activity / Audit Log page — real API. */
import { Panel } from "@/components/ui/primitives";
import { useActivity } from "@/lib/hooks/useActivity";
import { clsx } from "clsx";

function sevBg(s: string): string {
  const upper = s.toUpperCase();
  if (upper === "CRITICAL") return "bg-aurexis-danger/20 border-l-2 border-l-aurexis-danger";
  if (upper === "ERROR")    return "bg-aurexis-danger/10";
  if (upper === "WARNING")  return "bg-aurexis-warning/5";
  return "";
}

function sevText(s: string): string {
  const upper = s.toUpperCase();
  if (upper === "ERROR" || upper === "CRITICAL") return "text-aurexis-danger";
  if (upper === "WARNING")  return "text-aurexis-warning";
  if (upper === "INFO")     return "text-aurexis-subtle";
  return "text-aurexis-faint";
}

export function ActivityPage() {
  const { data: events, loading, error } = useActivity(50);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Activity</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Operational event log from backend.</p>
      </div>
      <Panel title="Event Log">
        {loading ? (
          <div className="px-4 py-8 text-center">
            <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
          </div>
        ) : error ? (
          <div className="px-4 py-8 text-center">
            <p className="text-2xs font-mono text-aurexis-danger">{error}</p>
          </div>
        ) : events.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-xs text-aurexis-subtle">No activity events recorded.</p>
          </div>
        ) : (
          <div className="divide-y divide-aurexis-border/40">
            {events.map((ev) => (
              <div key={ev.id} className={clsx("flex items-start gap-3 px-4 py-3", sevBg(ev.severity))}>
                <span className={clsx("text-2xs font-mono uppercase w-14 flex-shrink-0 mt-px", sevText(ev.severity))}>{ev.severity}</span>
                <span className="text-2xs text-aurexis-faint font-mono w-28 flex-shrink-0">{ev.event_type}</span>
                <div className="flex-1">
                  <p className="text-xs text-aurexis-subtle leading-relaxed">
                    {ev.correlation_id ? `[${ev.correlation_id.slice(0, 8)}] ` : ""}{ev.event_type}
                  </p>
                  {ev.account_id && <p className="text-2xs text-aurexis-faint font-mono mt-0.5">Account: {ev.account_id}</p>}
                </div>
                <span className="text-2xs text-aurexis-faint font-mono flex-shrink-0">{new Date(ev.occurred_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

