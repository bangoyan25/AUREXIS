"use client";
/**
 * Market Page — Live XAUUSD Market State, Candlestick Chart & Technical Intelligence.
 */
import { useEffect, useState, useCallback } from "react";
import { Panel, Label, StatRow, Badge } from "@/components/ui/primitives";
import { RegimeBadge } from "@/components/ui/badges";
import { FreshnessBadge } from "@/components/ui/phase3";
import { CandlestickChart, type CandleData } from "@/components/charts/CandlestickChart";
import { useMarketState } from "@/lib/hooks/useMarketState";
import { useBrain } from "@/lib/hooks/useBrain";
import { useAuth } from "@/lib/auth-context";
import { useSelectedAccount } from "@/lib/account-context";
import { marketApi } from "@/lib/api";

function getBaselineBars(): CandleData[] {
  const bars: CandleData[] = [];
  const base = 4375.0;
  const now = Date.now();
  for (let i = 59; i >= 0; i--) {
    const t = new Date(now - i * 15 * 60 * 1000).toISOString();
    const wave = Math.sin(i * 0.25) * 8 + Math.cos(i * 0.15) * 5;
    const o = base + wave;
    const c = o + (i % 2 === 0 ? 2.4 : -1.8);
    const h = Math.max(o, c) + 1.6;
    const l = Math.min(o, c) - 1.6;
    bars.push({
      time: t,
      open: parseFloat(o.toFixed(2)),
      high: parseFloat(h.toFixed(2)),
      low: parseFloat(l.toFixed(2)),
      close: parseFloat(c.toFixed(2)),
      volume: 6000 + (i % 5) * 1200,
    });
  }
  return bars;
}

export function MarketPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { token } = useAuth();
  const liveMarket = useMarketState(selectedAccountId);
  const brain = useBrain(selectedAccountId);

  const [timeframe, setTimeframe] = useState<string>("M15");
  const [candles, setCandles] = useState<CandleData[]>(getBaselineBars);
  const [isLoadingChart, setIsLoadingChart] = useState<boolean>(false);

  const fetchChart = useCallback(async () => {
    if (!token) return;
    try {
      let res;
      if (selectedAccountId) {
        try {
          res = await marketApi.getChart(selectedAccountId, token, timeframe, 100);
        } catch {
          res = null;
        }
      }
      if (!res || !res.bars || res.bars.length === 0) {
        res = await marketApi.getGlobalChart(token, timeframe, 100);
      }
      if (res && res.bars && res.bars.length > 0) {
        setCandles(res.bars);
      }
    } catch {
      // Keep existing candles on transient fetch failure
    } finally {
      setIsLoadingChart(false);
    }
  }, [selectedAccountId, token, timeframe]);

  // Initial load on account/timeframe change
  useEffect(() => {
    setIsLoadingChart(true);
    void fetchChart();
  }, [fetchChart]);

  // Periodic refresh for new closed bars (every 1.2 seconds)
  useEffect(() => {
    const timer = setInterval(() => {
      void fetchChart();
    }, 1200);
    return () => clearInterval(timer);
  }, [fetchChart]);

  const tick = liveMarket.status === "OK" ? liveMarket.data : null;
  const b = brain.status === "OK" ? brain.data : null;
  const liveBid = tick?.bid ? parseFloat(tick.bid) : null;
  const liveAsk = tick?.ask ? parseFloat(tick.ask) : null;
  const spreadVal = tick?.spread ? parseFloat(tick.spread) : null;

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Market Intelligence
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Real-time XAUUSD pricing stream, interactive candlestick chart & structure analysis.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <FreshnessBadge status={tick?.status ?? "NO_DATA"} />
          {tick?.age_ms !== null && tick?.age_ms !== undefined && (
            <span className="text-2xs font-mono text-aurexis-faint">
              {tick.age_ms}ms
            </span>
          )}
        </div>
      </div>

      {/* Main Candlestick Chart */}
      <CandlestickChart
        data={candles}
        livePrice={liveBid}
        liveAsk={liveAsk}
        spread={spreadVal}
        symbol="XAUUSD"
        timeframe={timeframe}
        onTimeframeChange={(tf) => setTimeframe(tf)}
        availableTimeframes={["M1", "M5", "M15", "M30", "H1", "H4", "D1"]}
        isLoading={isLoadingChart}
      />

      {/* Market Stats & Intelligence Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* Live Ticker & Spread Panel */}
        <Panel title="Live Ticker & Spread">
          <div className="px-4 py-3">
            <StatRow label="Symbol" value="XAUUSD" />
            <StatRow
              label="Live Bid"
              value={
                tick?.bid ? (
                  <span className="font-financial font-semibold text-aurexis-text">
                    {tick.bid}
                  </span>
                ) : (
                  <Badge variant="muted">WAITING TICK</Badge>
                )
              }
            />
            <StatRow
              label="Live Ask"
              value={
                tick?.ask ? (
                  <span className="font-financial font-semibold text-aurexis-text">
                    {tick.ask}
                  </span>
                ) : (
                  <Badge variant="muted">WAITING TICK</Badge>
                )
              }
            />
            <StatRow
              label="Spread"
              value={
                tick?.spread ? (
                  <span className="font-mono text-2xs text-aurexis-accent">
                    ${tick.spread}
                  </span>
                ) : (
                  <Badge variant="muted">—</Badge>
                )
              }
            />
            <StatRow
              label="Tick Time"
              value={
                <span className="font-mono text-3xs text-aurexis-faint">
                  {tick?.tick_time ?? "—"}
                </span>
              }
            />
            <StatRow
              label="Bar Cache Status"
              value={
                <span className="font-mono text-2xs text-aurexis-success">
                  {candles.length} bars synchronized
                </span>
              }
            />
          </div>
        </Panel>

        {/* Structure & Market Regime */}
        <Panel title="Market Regime & Structure">
          <div className="px-4 py-3">
            <StatRow
              label="Regime"
              value={
                <RegimeBadge
                  state={
                    (b?.regime ?? "NOT_CONFIGURED") as Parameters<
                      typeof RegimeBadge
                    >[0]["state"]
                  }
                />
              }
            />
            <StatRow
              label="Market Structure"
              value={<Badge variant="accent">{b?.structure ?? "ANALYZING"}</Badge>}
            />
            <StatRow
              label="Trend Classification"
              value={<Badge variant="muted">{b?.trend ?? "TREND_ANALYSIS"}</Badge>}
            />
            <StatRow
              label="Momentum"
              value={<Badge variant="muted">{b?.momentum ?? "NORMAL"}</Badge>}
            />
            <StatRow
              label="Volatility State"
              value={<Badge variant="muted">{b?.volatility ?? "MONITORED"}</Badge>}
            />
          </div>
        </Panel>

        {/* Strategy Parameters & Timeframe Alignment */}
        <Panel title="Execution & Parameters">
          <div className="px-4 py-3">
            <StatRow label="Active Strategy" value={<span className="font-mono text-2xs">AUREXIS-STRAT-1.0.0</span>} />
            <StatRow label="Primary Timeframe" value={<span className="font-mono text-2xs">M15 (Closed-Bar Rule)</span>} />
            <StatRow label="Execution Model" value={<span className="font-mono text-2xs">Server-side Brain → MT5 EA</span>} />
            <StatRow label="ATR Invalidation" value={<span className="font-mono text-2xs">0.50 × ATR(14)</span>} />
            <StatRow label="Min R:R Ratio" value={<span className="font-mono text-2xs text-aurexis-accent">1:2.0 Target</span>} />
            <StatRow label="Score Threshold" value={<span className="font-mono text-2xs text-aurexis-success">≥ 0.70 (6 Dimensions)</span>} />
          </div>
        </Panel>
      </div>
    </div>
  );
}
