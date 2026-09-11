"use client";
/**
 * News Protection Engine — Macro Volatility Blackout Gate & Economic Calendar Guard.
 */
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { NewsStateBadge } from "@/components/ui/badges";
import { useNews } from "@/lib/hooks/useNews";

const MONITORED_HIGH_IMPACT_EVENTS = [
  { event: "US Non-Farm Payrolls (NFP)", currency: "USD", impact: "CRITICAL", window: "±30 min" },
  { event: "FOMC Rate Decision & Press Conf", currency: "USD", impact: "CRITICAL", window: "±45 min" },
  { event: "Consumer Price Index (CPI)", currency: "USD", impact: "HIGH", window: "±30 min" },
  { event: "Producer Price Index (PPI)", currency: "USD", impact: "HIGH", window: "±20 min" },
  { event: "Gross Domestic Product (GDP)", currency: "USD", impact: "HIGH", window: "±25 min" },
  { event: "Federal Reserve Chair Speech", currency: "USD", impact: "HIGH", window: "±30 min" },
];

export function NewsPage() {
  const { status, data, error } = useNews();

  const newsState = status === "OK" ? (data.status as string).toUpperCase() : "CLEAR";
  const isClear = newsState === "CLEAR";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Macro News Protection Engine
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Automated volatility protection gate. Pre-event and post-event entry blackout.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="accent">FAIL-CLOSED PROTOCOL</Badge>
          <Badge variant={isClear ? "success" : "danger"}>
            {isClear ? "TRADING PERMITTED" : "BLACKOUT ACTIVE"}
          </Badge>
        </div>
      </div>

      {status === "LOADING" && (
        <div className="px-4 py-8 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">
            CHECKING ECONOMIC CALENDAR STREAM...
          </span>
        </div>
      )}

      {status === "ERROR" && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">CONNECTION ERROR — {error}</p>
        </div>
      )}

      {/* Hero Card: Current News Protection State */}
      <div className="bg-aurexis-surface border border-aurexis-border rounded p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex flex-col items-center md:items-start gap-2">
          <span className="text-2xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Active News Protection Status
          </span>
          <div className="flex items-center gap-3">
            <NewsStateBadge state={newsState as Parameters<typeof NewsStateBadge>[0]["state"]} />
            <span className="font-mono text-sm font-semibold text-aurexis-text">
              {isClear ? "CLEAR — Normal Market Volatility" : "BLACKOUT — Macro News Window Active"}
            </span>
          </div>
          <p className="text-xs text-aurexis-subtle max-w-xl leading-relaxed mt-1">
            {isClear
              ? "No critical economic releases scheduled within the ±30 minute window. Strategy engine is permitted to submit candidate signals to Risk Engine."
              : "High-impact economic release detected within the blackout window. Risk Engine vetoes all new entry commands to protect capital from slippage."}
          </p>
        </div>

        <div className="flex flex-col items-center md:items-end gap-1.5 flex-shrink-0">
          <span className="text-3xs font-mono uppercase tracking-wider text-aurexis-faint">
            GATE POLICY:
          </span>
          <Badge variant={isClear ? "success" : "danger"}>
            {isClear ? "ENTRY ALLOWED" : "ENTRY BLOCKED"}
          </Badge>
          <span className="text-3xs font-mono text-aurexis-faint">
            Calendar Engine: AUREXIS_INTERNAL
          </span>
        </div>
      </div>

      {/* Grid: Parameters & Monitored Events */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Parameters Panel */}
        <Panel title="News Engine Parameters">
          <div className="px-4 py-3">
            <StatRow label="Pre-Event Blackout Window" value={<span className="font-mono text-2xs text-aurexis-accent font-semibold">30 minutes</span>} />
            <StatRow label="Post-Event Blackout Window" value={<span className="font-mono text-2xs text-aurexis-accent font-semibold">30 minutes</span>} />
            <StatRow label="Primary Currency Filter" value={<span className="font-mono text-2xs text-aurexis-text">USD (US Dollar)</span>} />
            <StatRow label="Target Instrument" value={<span className="font-mono text-2xs text-aurexis-text">XAUUSD (Gold vs USD)</span>} />
            <StatRow label="Existing Position Management" value={<span className="font-mono text-2xs">Hold with Protected Stop Loss</span>} />
            <StatRow
              label="Fail-Closed Guard"
              value={<Badge variant="success">ACTIVE (No Data = Veto)</Badge>}
            />
          </div>
        </Panel>

        {/* Monitored Release Events */}
        <Panel title="High-Impact Calendar Releases Monitored">
          <div className="divide-y divide-aurexis-border/40">
            {MONITORED_HIGH_IMPACT_EVENTS.map((ev) => (
              <div key={ev.event} className="flex items-center justify-between px-4 py-2.5">
                <div>
                  <span className="text-xs font-mono text-aurexis-text font-medium block">
                    {ev.event}
                  </span>
                  <span className="text-3xs font-mono text-aurexis-faint">
                    Currency: {ev.currency}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={ev.impact === "CRITICAL" ? "danger" : "warning"}>
                    {ev.impact}
                  </Badge>
                  <span className="text-2xs font-mono text-aurexis-subtle">
                    {ev.window}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* Invariant Protocol Card */}
      <div className="bg-aurexis-surface border border-aurexis-border/60 rounded p-4 text-2xs font-mono text-aurexis-faint space-y-1.5">
        <div className="flex items-center gap-2 text-aurexis-accent font-semibold uppercase tracking-wider">
          <span>Fail-Closed Principle</span>
        </div>
        <p className="leading-relaxed">
          News protection is an independent risk control, never a directional trading signal. If calendar data is unavailable, stale, or network connectivity is lost, the Risk Engine defaults to `BLOCK` for all new positions until fresh data is received.
        </p>
      </div>
    </div>
  );
}
