"use client";
/** News protection page — real API. */
import { Panel, StatRow, NotConfigured } from "@/components/ui/primitives";
import { NewsStateBadge } from "@/components/ui/badges";
import { useNews } from "@/lib/hooks/useNews";

const NEWS_STATES_INFO = [
  { state: "CLEAR",      desc: "No high-impact events in configured window. New entries permitted (subject to other rules)." },
  { state: "PRE_EVENT",  desc: "High-impact event approaching. Trading new entries BLOCKED." },
  { state: "IN_EVENT",   desc: "High-impact event in progress. Trading new entries BLOCKED." },
  { state: "POST_EVENT", desc: "Post-event window active. Trading new entries BLOCKED." },
  { state: "UNKNOWN",    desc: "News state cannot be determined. Treated as PRE_EVENT — new entries BLOCKED." },
  { state: "UNAVAILABLE",desc: "News provider unavailable. Treated as PRE_EVENT — new entries BLOCKED." },
  { state: "STALE",      desc: "News data is stale. Treated as PRE_EVENT — new entries BLOCKED." },
];

export function NewsPage() {
  const { status, data, error } = useNews();

  const newsState = status === "OK" ? (data.status as string).toUpperCase() : "UNKNOWN";
  const provider = status === "OK" ? data.provider : null;
  const note = status === "OK" ? data.note : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">News Protection</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">High-impact event protection. Fail-closed: UNKNOWN = BLOCKED.</p>
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

      {/* Current state — prominent */}
      <div className="bg-aurexis-surface border border-aurexis-border rounded p-6 flex flex-col items-center gap-4">
        <span className="text-2xs font-medium uppercase tracking-widest text-aurexis-subtle">Current News State</span>
        <NewsStateBadge state={newsState as Parameters<typeof NewsStateBadge>[0]["state"]} />
        {newsState !== "CLEAR" && (
          <div className="text-center">
            <p className="text-sm font-medium text-aurexis-warning">TRADING BLOCKED</p>
            <p className="text-2xs text-aurexis-faint mt-1">News protection active. No new entries permitted.</p>
          </div>
        )}
        {provider ? (
          <StatRow label="Provider" value={provider} />
        ) : (
          <NotConfigured name="News Provider" detail={note || "News provider UNDEFINED. Not configured — system is fail-closed."} />
        )}
      </div>

      {/* State reference */}
      <Panel title="State Reference">
        <div className="divide-y divide-aurexis-border/40">
          {NEWS_STATES_INFO.map(({ state, desc }) => (
            <div key={state} className="flex items-start gap-4 px-4 py-3">
              <NewsStateBadge state={state as Parameters<typeof NewsStateBadge>[0]["state"]} />
              <p className="text-xs text-aurexis-subtle flex-1 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </Panel>

      <div className="bg-aurexis-surface border border-aurexis-border/50 rounded px-4 py-3">
        <p className="text-2xs text-aurexis-faint leading-relaxed">
          <span className="text-aurexis-subtle">Note: </span>
          Calendar provider, pre-event window, post-event window, and impact classification are all UNDEFINED.
          News parameters must be configured before live trading.
        </p>
      </div>
    </div>
  );
}

