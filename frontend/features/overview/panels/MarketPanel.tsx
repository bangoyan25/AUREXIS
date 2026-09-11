"use client";
import Link from "next/link";
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { RegimeBadge } from "@/components/ui/badges";
import { FreshnessBadge, AgentLinkBadge, RiskDecisionBadge, ReasonCodeBadge } from "@/components/ui/phase3";
import { useMarket } from "@/lib/hooks/useMarket";
import { useMarketState } from "@/lib/hooks/useMarketState";
import { useRiskDecision } from "@/lib/hooks/useRiskDecision";
import { useAgents } from "@/lib/hooks/useAgents";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";

export function MarketPanel() {
  const { selectedAccountId } = useSelectedAccount();
  const legacyMarket = useMarket();
  const liveMarket = useMarketState(selectedAccountId);
  const liveRisk = useRiskDecision(selectedAccountId);
  const { agents } = useAgents();
  const brain = useBrain(selectedAccountId);

  // Match active agent for selected account
  const accountAgent = agents.find((a) => a.account_id === selectedAccountId);
  const agentStatus = accountAgent?.last_known_status ?? (selectedAccountId ? "UNKNOWN" : "NOT_ATTACHED");

  const tick = liveMarket.status === "OK" ? liveMarket.data : null;
  const legacy = legacyMarket.status === "OK" ? legacyMarket.data : null;
  const risk = liveRisk.status === "OK" ? liveRisk.data : null;
  const b = brain.status === "OK" ? brain.data : null;

  const freshness = tick?.status ?? (legacy?.status ?? "NO_DATA");
  const bidVal = tick?.bid ?? (legacy?.bid !== null && legacy?.bid !== undefined ? legacy.bid.toFixed(2) : null);
  const askVal = tick?.ask ?? (legacy?.ask !== null && legacy?.ask !== undefined ? legacy.ask.toFixed(2) : null);
  const spreadVal = tick?.spread ?? (legacy?.spread_pips !== null && legacy?.spread_pips !== undefined ? `${legacy.spread_pips} pips` : null);

  return (
    <Panel title="Market">
      <div className="px-4 py-3">
        <StatRow label="Symbol" value="XAUUSD" />
        <StatRow
          label="Market Data"
          value={
            <div className="flex items-center gap-1.5">
              <FreshnessBadge status={freshness} />
              {tick?.age_ms !== null && tick?.age_ms !== undefined && (
                <span className="text-2xs font-mono text-aurexis-faint">({tick.age_ms}ms)</span>
              )}
            </div>
          }
        />
        <StatRow
          label="Agent Link"
          value={<AgentLinkBadge status={agentStatus} />}
        />
        <StatRow
          label="Bid"
          value={bidVal !== null ? bidVal : <Badge variant="muted">UNAVAILABLE</Badge>}
        />
        <StatRow
          label="Ask"
          value={askVal !== null ? askVal : <Badge variant="muted">UNAVAILABLE</Badge>}
        />
        <StatRow
          label="Spread"
          value={spreadVal !== null ? spreadVal : <Badge variant="muted">UNAVAILABLE</Badge>}
        />
        {tick?.point && (
          <StatRow
            label="Point / Digits"
            value={<span className="font-mono text-2xs">{tick.point} / {tick.digits}</span>}
          />
        )}
        <StatRow
          label="Risk Gate"
          value={
            risk ? (
              <div className="flex items-center gap-1.5">
                <RiskDecisionBadge decision={risk.decision} />
                <ReasonCodeBadge code={risk.reason_code} decision={risk.decision} />
              </div>
            ) : (
              <Badge variant="muted">NOT EVALUATED</Badge>
            )
          }
        />
        <StatRow
          label="Regime"
          value={<RegimeBadge state={(b?.regime ?? "NOT_CONFIGURED") as Parameters<typeof RegimeBadge>[0]["state"]} />}
        />
        <StatRow
          label="Trend"
          value={<Badge variant="muted">{b?.trend ?? "NOT_CONFIGURED"}</Badge>}
        />
        <StatRow
          label="Volatility"
          value={<Badge variant="muted">{b?.volatility ?? "NOT_CONFIGURED"}</Badge>}
        />
        <div className="pt-2.5 mt-2 border-t border-aurexis-border/40 flex justify-end">
          <Link
            href="/market"
            className="text-2xs font-mono text-aurexis-accent hover:underline flex items-center gap-1"
          >
            Open Interactive Candlestick Chart →
          </Link>
        </div>
      </div>
    </Panel>
  );
}


