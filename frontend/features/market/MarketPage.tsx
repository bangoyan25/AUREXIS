"use client";
/** Market page — XAUUSD state — real API with MOCK chart labeled. */
import { Panel, Label, StatRow, Badge } from "@/components/ui/primitives";
import { RegimeBadge } from "@/components/ui/badges";
import { useMarket } from "@/lib/hooks/useMarket";
import { useBrain } from "@/lib/hooks/useBrain";
import { useSelectedAccount } from "@/lib/account-context";
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, Tooltip, ReferenceLine,
} from "recharts";

/** Deterministic mock price series — XAUUSD 5-min bars.
 *  No Math.random(). Replace with live hook when backend connected.
 */
const MOCK_SERIES = [
  { t: "08:00", p: 2318.4 }, { t: "08:05", p: 2319.1 }, { t: "08:10", p: 2317.8 },
  { t: "08:15", p: 2320.5 }, { t: "08:20", p: 2322.0 }, { t: "08:25", p: 2321.3 },
  { t: "08:30", p: 2319.7 }, { t: "08:35", p: 2323.1 }, { t: "08:40", p: 2325.6 },
  { t: "08:45", p: 2324.2 }, { t: "08:50", p: 2322.9 }, { t: "08:55", p: 2326.4 },
  { t: "09:00", p: 2328.0 }, { t: "09:05", p: 2326.7 }, { t: "09:10", p: 2325.1 },
  { t: "09:15", p: 2329.3 }, { t: "09:20", p: 2331.8 }, { t: "09:25", p: 2330.5 },
  { t: "09:30", p: 2328.9 }, { t: "09:35", p: 2332.7 }, { t: "09:40", p: 2334.2 },
  { t: "09:45", p: 2333.0 }, { t: "09:50", p: 2331.4 }, { t: "09:55", p: 2327.8 },
  { t: "10:00", p: 2325.2 }, { t: "10:05", p: 2323.6 }, { t: "10:10", p: 2321.9 },
  { t: "10:15", p: 2320.3 }, { t: "10:20", p: 2318.7 }, { t: "10:25", p: 2317.1 },
  { t: "10:30", p: 2315.5 }, { t: "10:35", p: 2313.9 }, { t: "10:40", p: 2312.4 },
  { t: "10:45", p: 2310.8 }, { t: "10:50", p: 2309.2 }, { t: "10:55", p: 2311.6 },
  { t: "11:00", p: 2313.1 }, { t: "11:05", p: 2314.5 }, { t: "11:10", p: 2316.2 },
  { t: "11:15", p: 2318.7 }, { t: "11:20", p: 2320.1 }, { t: "11:25", p: 2321.4 },
  { t: "11:30", p: 2319.8 }, { t: "11:35", p: 2317.2 }, { t: "11:40", p: 2315.6 },
  { t: "11:45", p: 2318.0 }, { t: "11:50", p: 2320.4 }, { t: "11:55", p: 2322.8 },
];

const PMIN = Math.min(...MOCK_SERIES.map(d => d.p));
const PMAX = Math.max(...MOCK_SERIES.map(d => d.p));
const POPEN = MOCK_SERIES[0]?.p ?? 0;
const PLAST = MOCK_SERIES[MOCK_SERIES.length - 1]?.p ?? 0;
const PCHANGE = PLAST - POPEN;

type TPayload = { value?: number };
function ChartTooltip({ active, payload, label }: {
  active?: boolean; payload?: TPayload[]; label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-aurexis-elevated border border-aurexis-border rounded px-3 py-2">
      <p className="text-2xs text-aurexis-faint font-mono">{label}</p>
      <p className="text-xs font-financial text-aurexis-text tabular-nums">
        {payload[0]?.value?.toFixed(2)}
      </p>
    </div>
  );
}

export function MarketPage() {
  const { selectedAccountId } = useSelectedAccount();
  const market = useMarket();
  const brain = useBrain(selectedAccountId);

  const m = market.status === "OK" ? market.data : null;
  const b = brain.status === "OK" ? brain.data : null;
  const up = PCHANGE >= 0;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Market</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">XAUUSD market state. Price chart is MOCK DATA — backend does not yet provide OHLCV endpoint.</p>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Price">
          <div className="px-4 py-3">
            <StatRow label="Symbol"       value="XAUUSD" />
            <StatRow label="Status"       value={<Badge variant="muted">{m?.status ?? "LOADING"}</Badge>} />
            <StatRow label="Bid"          value={m?.bid !== null && m?.bid !== undefined ? m.bid.toFixed(2) : <Badge variant="muted">UNAVAILABLE</Badge>} />
            <StatRow label="Ask"          value={m?.ask !== null && m?.ask !== undefined ? m.ask.toFixed(2) : <Badge variant="muted">UNAVAILABLE</Badge>} />
            <StatRow label="Spread"       value={m?.spread_pips !== null && m?.spread_pips !== undefined ? `${m.spread_pips} pips` : <Badge variant="muted">UNAVAILABLE</Badge>} />
          </div>
        </Panel>
        <Panel title="Analysis">
          <div className="px-4 py-3">
            <StatRow label="Regime"        value={<RegimeBadge state={(b?.regime ?? "NOT_CONFIGURED") as Parameters<typeof RegimeBadge>[0]["state"]} />} />
            <StatRow label="Structure"     value={<Badge variant="muted">{b?.structure ?? "NOT_CONFIGURED"}</Badge>} />
            <StatRow label="Trend"         value={<Badge variant="muted">{b?.trend ?? "NOT_CONFIGURED"}</Badge>} />
            <StatRow label="Momentum"      value={<Badge variant="muted">{b?.momentum ?? "NOT_CONFIGURED"}</Badge>} />
            <StatRow label="Volatility"    value={<Badge variant="muted">{b?.volatility ?? "NOT_CONFIGURED"}</Badge>} />
          </div>
        </Panel>
      </div>

      <Panel title="XAUUSD — Mock Price Series">
        <div className="px-4 pt-3 pb-1 flex items-center justify-between border-b border-aurexis-border/40">
          <div className="flex items-center gap-4">
            <span className="font-financial text-sm text-aurexis-text tabular-nums">{PLAST.toFixed(2)}</span>
            <span className={`text-xs font-financial tabular-nums ${up ? "text-aurexis-success" : "text-aurexis-danger"}`}>
              {up ? "+" : ""}{PCHANGE.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Label>H: {PMAX.toFixed(2)}</Label>
            <Label>L: {PMIN.toFixed(2)}</Label>
            <Badge variant="warning">MOCK DATA</Badge>
          </div>
        </div>
        <div className="px-2 py-4" style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={MOCK_SERIES} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="t" tick={{ fontSize: 9, fontFamily: "JetBrains Mono,monospace", fill: "#3D4F6B" }} tickLine={false} axisLine={false} interval={7} />
              <YAxis domain={[PMIN - 5, PMAX + 5]} tick={{ fontSize: 9, fontFamily: "JetBrains Mono,monospace", fill: "#3D4F6B" }} tickLine={false} axisLine={false} width={50} tickFormatter={(v: number) => v.toFixed(0)} />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={POPEN} stroke="#3D4F6B" strokeDasharray="3 3" strokeWidth={1} />
              <Line type="monotone" dataKey="p" stroke={up ? "#16A34A" : "#DC2626"} strokeWidth={1.5} dot={false} activeDot={{ r: 3, strokeWidth: 0 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="px-4 py-2 border-t border-aurexis-border/40">
          <p className="text-2xs text-aurexis-faint">
            <span className="text-aurexis-warning font-mono">MOCK</span>
            {" "}— Deterministic demo data. Not connected to live market data. Replace with live OHLCV when backend connected.
          </p>
        </div>
      </Panel>
    </div>
  );
}
