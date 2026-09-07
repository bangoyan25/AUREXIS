"use client";
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { RegimeBadge } from "@/components/ui/badges";
import { useMarket } from "@/lib/hooks/useMarket";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";

export function MarketPanel() {
  const { selectedAccountId } = useSelectedAccount();
  const market = useMarket();
  const brain = useBrain(selectedAccountId);

  const m = market.status === "OK" ? market.data : null;
  const b = brain.status === "OK" ? brain.data : null;

  return (
    <Panel title="Market">
      <div className="px-4 py-3">
        <StatRow label="Symbol" value="XAUUSD" />
        <StatRow
          label="Bid"
          value={m?.bid !== null && m?.bid !== undefined ? m.bid.toFixed(2) : <Badge variant="muted">UNAVAILABLE</Badge>}
        />
        <StatRow
          label="Ask"
          value={m?.ask !== null && m?.ask !== undefined ? m.ask.toFixed(2) : <Badge variant="muted">UNAVAILABLE</Badge>}
        />
        <StatRow
          label="Spread"
          value={m?.spread_pips !== null && m?.spread_pips !== undefined ? `${m.spread_pips} pips` : <Badge variant="muted">UNAVAILABLE</Badge>}
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
          label="Momentum"
          value={<Badge variant="muted">{b?.momentum ?? "NOT_CONFIGURED"}</Badge>}
        />
        <StatRow
          label="Volatility"
          value={<Badge variant="muted">{b?.volatility ?? "NOT_CONFIGURED"}</Badge>}
        />
      </div>
    </Panel>
  );
}

