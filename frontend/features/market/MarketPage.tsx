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

export function MarketPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { token } = useAuth();
  const liveMarket = useMarketState(selectedAccountId);
  const brain = useBrain(selectedAccountId);

  const [timeframe, setTimeframe] = useState<string>("M15");
  const [candles, setCandles] = useState<CandleData[]>([]);
  const [isLoadingChart, setIsLoadingChart] = useState<boolean>(false);

  const fetchChart = useCallback(async () => {
    if (!selectedAccountId || !token) return;
    try {
      const res = await marketApi.getChart(selectedAccountId, token, timeframe, 100);
      if (res.bars && res.bars.length > 0) {
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

  // Periodic refresh for new closed bars (every 6 seconds)
  useEffect(() => {
    const timer = setInterval(() => {
      void fetchChart();
    }, 6000);
    return () => clearInterval(timer);
  }, [fetchChart]);

  const tick = liveMarket.status === "OK" ? liveMarket.data : null;
  const b = brain.status === "OK" ? brain.data : null;
  const liveBid = tick?.bid ? parseFloat(tick.bid) : null;

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
        symbol="XAUUSD"
        timeframe={timeframe}
        onTimeframeChange={(tf) => setTimeframe(tf)}
        availableTimeframes={["M5", "M15", "H1", "H4", "D1"]}
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
