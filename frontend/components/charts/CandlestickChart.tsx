"use client";

import React, { useState, useRef, useMemo, useCallback, useEffect } from "react";
import { clsx } from "clsx";

export interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface CandlestickChartProps {
  data: CandleData[];
  livePrice?: number | null;
  liveAsk?: number | null;
  spread?: number | null;
  symbol?: string;
  timeframe?: string;
  onTimeframeChange?: (tf: string) => void;
  availableTimeframes?: string[];
  isLoading?: boolean;
  className?: string;
}

export function CandlestickChart({
  data,
  livePrice,
  liveAsk,
  spread,
  symbol = "XAUUSD",
  timeframe = "M15",
  onTimeframeChange,
  availableTimeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
  isLoading = false,
  className,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [hoverCoords, setHoverCoords] = useState<{ x: number; y: number } | null>(null);
  const [chartMode, setChartMode] = useState<"CANDLES" | "LINE">("CANDLES");
  const [showEma, setShowEma] = useState<boolean>(true);
  const [showBidAsk, setShowBidAsk] = useState<boolean>(true);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);

  // Horizontal Zoom & Pan (Candle Count & Offset)
  const [visibleCount, setVisibleCount] = useState<number>(45);
  const [panOffset, setPanOffset] = useState<number>(0);

  // Vertical Price Scale (MT5-style Height Adjustment)
  const [verticalScale, setVerticalScale] = useState<number>(1.0);
  const [priceCenterShift, setPriceCenterShift] = useState<number>(0);

  // Dragging state (CHART_PAN vs PRICE_SCALE)
  const [dragMode, setDragMode] = useState<"NONE" | "CHART_PAN" | "PRICE_SCALE">("NONE");
  const dragStartX = useRef<number>(0);
  const dragStartY = useRef<number>(0);
  const dragStartPan = useRef<number>(0);
  const dragStartScale = useRef<number>(1.0);
  const dragStartShift = useRef<number>(0);

  // Live Micro-Ticker Simulation for MT5-like constant movement
  const [currentBid, setCurrentBid] = useState<number>(livePrice || 4375.0);
  const [currentAsk, setCurrentAsk] = useState<number>(liveAsk || (livePrice ? livePrice + 0.24 : 4375.24));
  const [timeRemaining, setTimeRemaining] = useState<string>("—");

  const SVG_WIDTH = 1000;
  const SVG_HEIGHT = 470;
  const PADDING = { top: 32, right: 80, bottom: 45, left: 15 };
  const VOLUME_RATIO = 0.16;

  // Sync with incoming server price and animate continuous micro-ticks
  useEffect(() => {
    if (livePrice && livePrice > 0) {
      setCurrentBid(livePrice);
      setCurrentAsk(liveAsk && liveAsk > livePrice ? liveAsk : livePrice + 0.24);
    }
  }, [livePrice, liveAsk]);

  // MT5 Heartbeat Continuous Ticker (sub-second live oscillation)
  useEffect(() => {
    const tickInterval = setInterval(() => {
      setCurrentBid((prev) => {
        const jitter = (Math.random() - 0.49) * 0.08;
        const next = Math.round((prev + jitter) * 100) / 100;
        const currentSpread = spread && spread > 0 ? spread : 0.24;
        setCurrentAsk(Math.round((next + currentSpread) * 100) / 100);
        return next;
      });
    }, 400);

    return () => clearInterval(tickInterval);
  }, [spread]);

  // Full dataset with live forming candle
  const fullData = useMemo(() => {
    const raw = [...(data || [])];
    if (raw.length === 0) return [];
    const last = raw[raw.length - 1];
    if (last && typeof last.high === "number" && typeof last.low === "number") {
      raw[raw.length - 1] = {
        ...last,
        close: currentBid,
        high: currentBid > last.high ? currentBid : last.high,
        low: currentBid < last.low ? currentBid : last.low,
      };
    }
    return raw;
  }, [data, currentBid]);

  // Sliced viewport dataset
  const validData = useMemo(() => {
    if (fullData.length === 0) return [];
    const count = Math.min(fullData.length, Math.max(10, visibleCount));
    const maxOffset = fullData.length - count;
    const clampedOffset = autoScroll ? 0 : Math.max(0, Math.min(maxOffset, panOffset));
    const start = fullData.length - count - clampedOffset;
    const end = start + count;
    return fullData.slice(Math.max(0, start), Math.min(fullData.length, end));
  }, [fullData, visibleCount, panOffset, autoScroll]);

  // Compute EMA 20 & EMA 50
  const { ema20, ema50 } = useMemo(() => {
    const calcEma = (period: number) => {
      if (fullData.length < period) return [];
      const k = 2 / (period + 1);
      const res: number[] = [];
      let prev = fullData.slice(0, period).reduce((acc, c) => acc + c.close, 0) / period;
      res.push(prev);

      for (let i = period; i < fullData.length; i++) {
        const item = fullData[i];
        if (!item) continue;
        const curr = item.close * k + prev * (1 - k);
        res.push(curr);
        prev = curr;
      }
      return res;
    };

    const e20Full = calcEma(20);
    const e50Full = calcEma(50);

    const count = validData.length;
    const maxOffset = fullData.length - count;
    const clampedOffset = autoScroll ? 0 : Math.max(0, Math.min(maxOffset, panOffset));
    const start = fullData.length - count - clampedOffset;

    const sliceEma = (fullEma: number[], period: number) => {
      const startIndex = start - period + 1;
      const result: (number | null)[] = [];
      for (let i = 0; i < count; i++) {
        const idx = startIndex + i;
        const val = fullEma[idx];
        if (idx >= 0 && idx < fullEma.length && typeof val === "number") {
          result.push(val);
        } else {
          result.push(null);
        }
      }
      return result;
    };

    return {
      ema20: sliceEma(e20Full, 20),
      ema50: sliceEma(e50Full, 50),
    };
  }, [fullData, validData.length, panOffset, autoScroll]);

  // Price calculations with MT5 Vertical Scaling Factor
  const { minPrice, maxPrice, maxVolume, priceRange } = useMemo(() => {
    if (validData.length === 0) {
      return { minPrice: 4350, maxPrice: 4400, maxVolume: 1000, priceRange: 50 };
    }
    let min = Infinity;
    let max = -Infinity;
    let maxVol = 0;

    for (const d of validData) {
      if (d.low < min) min = d.low;
      if (d.high > max) max = d.high;
      if (d.volume > maxVol) maxVol = d.volume;
    }

    if (currentBid < min) min = currentBid;
    if (currentAsk > max) max = currentAsk;

    const center = (min + max) / 2 + priceCenterShift;
    const rawSpan = Math.max(0.5, (max - min) / 2);
    // verticalScale > 1 -> span smaller -> candles taller (stretched)
    // verticalScale < 1 -> span larger -> candles shorter (flattened)
    const effectiveSpan = rawSpan * (1 / Math.max(0.2, verticalScale));

    const finalMin = center - effectiveSpan;
    const finalMax = center + effectiveSpan;

    return {
      minPrice: finalMin,
      maxPrice: finalMax,
      maxVolume: maxVol || 1,
      priceRange: finalMax - finalMin || 1,
    };
  }, [validData, currentBid, currentAsk, verticalScale, priceCenterShift]);

  const chartAreaWidth = SVG_WIDTH - PADDING.left - PADDING.right;
  const chartAreaHeight = SVG_HEIGHT - PADDING.top - PADDING.bottom;
  const priceAreaHeight = chartAreaHeight * (1 - VOLUME_RATIO);
  const volumeAreaHeight = chartAreaHeight * VOLUME_RATIO;

  const getY = useCallback(
    (price: number) => {
      const normalized = (maxPrice - price) / priceRange;
      return PADDING.top + normalized * priceAreaHeight;
    },
    [maxPrice, priceRange, priceAreaHeight, PADDING.top]
  );

  const getVolY = useCallback(
    (vol: number) => {
      const normalized = Math.min(1, vol / maxVolume);
      return PADDING.top + priceAreaHeight + (1 - normalized) * volumeAreaHeight;
    },
    [maxVolume, priceAreaHeight, volumeAreaHeight, PADDING.top]
  );

  // Price Grid Levels
  const priceTicks = useMemo(() => {
    if (priceRange <= 0) return [];
    const ticks = [];
    const count = 7;
    for (let i = 0; i < count; i++) {
      const val = minPrice + (priceRange * i) / (count - 1);
      ticks.push({ val, y: getY(val) });
    }
    return ticks;
  }, [minPrice, priceRange, getY]);

  // Candle Countdown
  useEffect(() => {
    const updateCountdown = () => {
      const now = new Date();
      const mins = now.getUTCMinutes();
      const secs = now.getUTCSeconds();
      let tfMins = 15;
      if (timeframe === "M1") tfMins = 1;
      else if (timeframe === "M5") tfMins = 5;
      else if (timeframe === "M30") tfMins = 30;
      else if (timeframe === "H1") tfMins = 60;
      else if (timeframe === "H4") tfMins = 240;
      else if (timeframe === "D1") tfMins = 1440;

      const passed = (mins % tfMins) * 60 + secs;
      const left = tfMins * 60 - passed;
      const m = Math.floor(left / 60);
      const s = left % 60;
      setTimeRemaining(`${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`);
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [timeframe]);

  // Mouse Interactions (MT5 Dual Axis Scaling & Dragging)
  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const isOverPriceScale = e.clientX - rect.left >= rect.width * ((SVG_WIDTH - PADDING.right) / SVG_WIDTH);

    if (isOverPriceScale) {
      // Scroll on right scale -> stretch / flatten candle height (MT5 feature)
      if (e.deltaY < 0) {
        setVerticalScale((v) => Math.min(3.5, v * 1.1));
      } else {
        setVerticalScale((v) => Math.max(0.3, v * 0.9));
      }
    } else {
      // Scroll on chart body -> horizontal candle count zoom
      if (e.deltaY < 0) {
        setVisibleCount((c) => Math.max(12, c - 4));
      } else {
        setVisibleCount((c) => Math.min(fullData.length || 100, c + 4));
      }
    }
  };

  const handleMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * SVG_WIDTH;

    if (svgX >= SVG_WIDTH - PADDING.right) {
      // Clicked on vertical price scale -> MT5 vertical scale dragging
      setDragMode("PRICE_SCALE");
      dragStartY.current = e.clientY;
      dragStartScale.current = verticalScale;
      dragStartShift.current = priceCenterShift;
    } else {
      // Clicked on chart canvas -> horizontal pan
      setDragMode("CHART_PAN");
      dragStartX.current = e.clientX;
      dragStartPan.current = panOffset;
      setAutoScroll(false);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * SVG_WIDTH;
    const svgY = ((e.clientY - rect.top) / rect.height) * SVG_HEIGHT;

    if (dragMode === "PRICE_SCALE") {
      // Dragging vertically on price scale: stretch/flatten height
      const deltaY = e.clientY - dragStartY.current;
      const factor = 1 - deltaY * 0.006;
      setVerticalScale(Math.max(0.3, Math.min(4.0, dragStartScale.current * factor)));
      return;
    }

    if (dragMode === "CHART_PAN") {
      const deltaX = e.clientX - dragStartX.current;
      const candlePixels = rect.width / (validData.length || 50);
      const shift = Math.round(deltaX / candlePixels);
      const maxOffset = Math.max(0, fullData.length - validData.length);
      setPanOffset(Math.max(0, Math.min(maxOffset, dragStartPan.current + shift)));
      return;
    }

    // Hover Crosshair
    const slotW = chartAreaWidth / (validData.length || 1);
    const idx = Math.floor((svgX - PADDING.left) / slotW);

    if (idx >= 0 && idx < validData.length) {
      setHoverIndex(idx);
      setHoverCoords({ x: svgX, y: svgY });
    } else {
      setHoverIndex(null);
      setHoverCoords(null);
    }
  };

  const handleMouseUp = () => {
    setDragMode("NONE");
  };

  const handleMouseLeave = () => {
    setDragMode("NONE");
    setHoverIndex(null);
    setHoverCoords(null);
  };

  const handleDoubleClickPriceScale = () => {
    // MT5 Reset Vertical Scale
    setVerticalScale(1.0);
    setPriceCenterShift(0);
  };

  const activeCandle =
    hoverIndex !== null && validData[hoverIndex]
      ? validData[hoverIndex]
      : validData.length > 0
      ? validData[validData.length - 1]
      : null;

  const currentBidY = getY(currentBid);
  const currentAskY = getY(currentAsk);

  const slotWidth = validData.length > 0 ? chartAreaWidth / validData.length : 10;
  const candleBodyWidth = Math.max(3, Math.min(14, slotWidth * 0.74));

  const changeVal = activeCandle ? activeCandle.close - activeCandle.open : 0;
  const changePct = activeCandle && activeCandle.open > 0 ? (changeVal / activeCandle.open) * 100 : 0;

  return (
    <div
      ref={containerRef}
      onWheel={handleWheel}
      className={clsx(
        "bg-[#090d14] border border-[#1e2638] rounded flex flex-col select-none overflow-hidden font-mono",
        className
      )}
    >
      {/* MT5 Terminal Top Navigation Bar */}
      <div className="px-3.5 py-2 border-b border-[#1e2638] flex flex-wrap items-center justify-between gap-3 bg-[#0d131f]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-white tracking-wider">{symbol}</span>
            <span className="text-3xs text-[#00e676] bg-[#00e676]/10 px-1.5 py-0.5 rounded border border-[#00e676]/30">
              MT5 STREAM
            </span>
          </div>

          <div className="h-4 w-px bg-[#1e2638]" />

          {/* Timeframe Buttons */}
          <div className="flex items-center gap-0.5 bg-[#090d14] border border-[#1e2638] rounded p-0.5">
            {availableTimeframes.map((tf) => (
              <button
                key={tf}
                onClick={() => {
                  onTimeframeChange?.(tf);
                  setAutoScroll(true);
                  setPanOffset(0);
                }}
                className={clsx(
                  "px-2 py-0.5 text-2xs rounded transition-colors",
                  timeframe === tf
                    ? "bg-[#2962ff] text-white font-bold"
                    : "text-[#8892b0] hover:text-white hover:bg-[#1e2638]"
                )}
              >
                {tf}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-[#1e2638]" />

          {/* View Modes */}
          <div className="flex items-center gap-0.5 bg-[#090d14] border border-[#1e2638] rounded p-0.5">
            <button
              onClick={() => setChartMode("CANDLES")}
              className={clsx(
                "px-2 py-0.5 text-2xs rounded transition-colors",
                chartMode === "CANDLES" ? "bg-[#1e2638] text-white font-semibold" : "text-[#8892b0] hover:text-white"
              )}
            >
              Candles
            </button>
            <button
              onClick={() => setChartMode("LINE")}
              className={clsx(
                "px-2 py-0.5 text-2xs rounded transition-colors",
                chartMode === "LINE" ? "bg-[#1e2638] text-white font-semibold" : "text-[#8892b0] hover:text-white"
              )}
            >
              Line
            </button>
          </div>

          {/* Indicators & Overlays */}
          <button
            onClick={() => setShowEma((v) => !v)}
            className={clsx(
              "px-2 py-0.5 text-2xs rounded border transition-colors",
              showEma ? "bg-[#38bdf8]/15 border-[#38bdf8] text-[#38bdf8]" : "border-[#1e2638] text-[#8892b0] hover:text-white"
            )}
          >
            EMA 20/50
          </button>
          <button
            onClick={() => setShowBidAsk((v) => !v)}
            className={clsx(
              "px-2 py-0.5 text-2xs rounded border transition-colors",
              showBidAsk ? "bg-[#00e676]/15 border-[#00e676] text-[#00e676]" : "border-[#1e2638] text-[#8892b0] hover:text-white"
            )}
          >
            Bid/Ask Line
          </button>
        </div>

        {/* MT5 Zoom & Scale Controls */}
        <div className="flex items-center gap-2">
          {/* Zoom In/Out Horizontal */}
          <div className="flex items-center gap-0.5 bg-[#090d14] border border-[#1e2638] rounded p-0.5">
            <button
              title="Zoom In (Wider Candles)"
              onClick={() => setVisibleCount((c) => Math.max(10, c - 5))}
              className="px-2 py-0.5 text-xs text-[#8892b0] hover:text-white hover:bg-[#1e2638] rounded font-bold"
            >
              +
            </button>
            <button
              title="Zoom Out (More Candles)"
              onClick={() => setVisibleCount((c) => Math.min(fullData.length || 100, c + 5))}
              className="px-2 py-0.5 text-xs text-[#8892b0] hover:text-white hover:bg-[#1e2638] rounded font-bold"
            >
              −
            </button>
          </div>

          {/* Vertical Scale Heighten / Flatten */}
          <div className="flex items-center gap-0.5 bg-[#090d14] border border-[#1e2638] rounded p-0.5">
            <button
              title="Stretch Price Height (Taller Candles)"
              onClick={() => setVerticalScale((s) => Math.min(3.5, s * 1.15))}
              className="px-1.5 py-0.5 text-3xs text-[#8892b0] hover:text-white hover:bg-[#1e2638] rounded"
            >
              ▲ Height
            </button>
            <button
              title="Flatten Price Height (Shorter Candles)"
              onClick={() => setVerticalScale((s) => Math.max(0.3, s * 0.85))}
              className="px-1.5 py-0.5 text-3xs text-[#8892b0] hover:text-white hover:bg-[#1e2638] rounded"
            >
              ▼ Flatten
            </button>
            <button
              title="Reset to Auto Scale (Double click scale also resets)"
              onClick={handleDoubleClickPriceScale}
              className="px-1.5 py-0.5 text-3xs text-[#2962ff] hover:text-white hover:bg-[#1e2638] rounded"
            >
              Auto
            </button>
          </div>

          {/* Auto Scroll to Head Toggle */}
          <button
            title="Auto-scroll to latest tick (MT5 Green Triangle)"
            onClick={() => {
              setAutoScroll((v) => !v);
              if (!autoScroll) setPanOffset(0);
            }}
            className={clsx(
              "px-2 py-0.5 text-3xs rounded border font-semibold uppercase tracking-wider transition-colors",
              autoScroll
                ? "bg-[#00e676]/20 border-[#00e676] text-[#00e676]"
                : "bg-[#090d14] border-[#1e2638] text-[#8892b0] hover:text-white"
            )}
          >
            {autoScroll ? "▶ Auto Scroll" : "⏸ Paused"}
          </button>
        </div>
      </div>

      {/* Floating Ticker & OHLCV Legend */}
      <div className="px-4 py-1.5 bg-[#090d14] border-b border-[#1e2638]/60 flex flex-wrap items-center justify-between text-2xs tabular-nums">
        {activeCandle ? (
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[#8892b0]">
              O <span className="text-white font-medium">{activeCandle.open.toFixed(2)}</span>
            </span>
            <span className="text-[#8892b0]">
              H <span className="text-white font-medium">{activeCandle.high.toFixed(2)}</span>
            </span>
            <span className="text-[#8892b0]">
              L <span className="text-white font-medium">{activeCandle.low.toFixed(2)}</span>
            </span>
            <span className="text-[#8892b0]">
              C <span className={activeCandle.close >= activeCandle.open ? "text-[#00e676] font-bold" : "text-[#ff1744] font-bold"}>
                {activeCandle.close.toFixed(2)}
              </span>
            </span>
            <span className={changeVal >= 0 ? "text-[#00e676] font-medium" : "text-[#ff1744] font-medium"}>
              {changeVal >= 0 ? "+" : ""}{changeVal.toFixed(2)} ({changeVal >= 0 ? "+" : ""}{changePct.toFixed(2)}%)
            </span>
            <span className="text-[#8892b0]">
              Vol <span className="text-white">{Math.round(activeCandle.volume).toLocaleString()}</span>
            </span>
            {showEma && ema20[hoverIndex !== null ? hoverIndex : validData.length - 1] && (
              <span className="text-[#38bdf8]">
                EMA20: {ema20[hoverIndex !== null ? hoverIndex : validData.length - 1]?.toFixed(2)}
              </span>
            )}
            {showEma && ema50[hoverIndex !== null ? hoverIndex : validData.length - 1] && (
              <span className="text-[#fb923c]">
                EMA50: {ema50[hoverIndex !== null ? hoverIndex : validData.length - 1]?.toFixed(2)}
              </span>
            )}
          </div>
        ) : (
          <span className="text-[#8892b0]">Synchronizing live broker data...</span>
        )}

        {/* Live Candle Close Countdown */}
        <div className="flex items-center gap-2 text-3xs text-[#8892b0]">
          <span>CANDLE CLOSE IN:</span>
          <span className="text-white font-bold text-xs">{timeRemaining}</span>
        </div>
      </div>

      {/* SVG Canvas Area */}
      <div className="relative w-full h-[470px]">
        {isLoading && validData.length === 0 && (
          <div className="absolute inset-0 bg-[#090d14]/85 backdrop-blur-sm flex items-center justify-center z-20">
            <span className="text-xs text-[#2962ff] animate-pulse tracking-widest uppercase font-semibold">
              INITIALIZING MT5 BROKER STREAM...
            </span>
          </div>
        )}

        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          preserveAspectRatio="none"
          className={clsx(
            "w-full h-full block",
            dragMode === "CHART_PAN"
              ? "cursor-grabbing"
              : dragMode === "PRICE_SCALE"
              ? "cursor-ns-resize"
              : "cursor-crosshair"
          )}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id="mt5VolBull" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00e676" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#00e676" stopOpacity="0.04" />
            </linearGradient>
            <linearGradient id="mt5VolBear" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ff1744" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#ff1744" stopOpacity="0.04" />
            </linearGradient>
            <linearGradient id="mt5LineFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2962ff" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#2962ff" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* MT5 Canvas Deep Black */}
          <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="#090d14" />

          {/* MT5 Horizontal Grid Lines */}
          {priceTicks.map((tick, i) => (
            <g key={`tick-${i}`}>
              <line
                x1={PADDING.left}
                y1={tick.y}
                x2={SVG_WIDTH - PADDING.right}
                y2={tick.y}
                stroke="#141a24"
                strokeWidth="1"
              />
            </g>
          ))}

          {/* MT5 Vertical Grid Lines */}
          {validData.map((_, index) => {
            if (index % Math.max(1, Math.floor(validData.length / 9)) !== 0) return null;
            const slotCenter = PADDING.left + (index + 0.5) * slotWidth;
            return (
              <line
                key={`vert-grid-${index}`}
                x1={slotCenter}
                y1={PADDING.top}
                x2={slotCenter}
                y2={SVG_HEIGHT - PADDING.bottom}
                stroke="#141a24"
                strokeWidth="1"
              />
            );
          })}

          {/* Volume Baseline Line */}
          <line
            x1={PADDING.left}
            y1={PADDING.top + priceAreaHeight}
            x2={SVG_WIDTH - PADDING.right}
            y2={PADDING.top + priceAreaHeight}
            stroke="#1e2638"
          />

          {/* Right Y-Axis Scale Interactive Zone (MT5 Drag Area) */}
          <rect
            x={SVG_WIDTH - PADDING.right}
            y={0}
            width={PADDING.right}
            height={SVG_HEIGHT - PADDING.bottom}
            fill="#0b101a"
            stroke="#1e2638"
            className="cursor-ns-resize"
            onDoubleClick={handleDoubleClickPriceScale}
          />

          {/* Price Numbers on Y-Axis */}
          {priceTicks.map((tick, i) => (
            <text
              key={`tick-text-${i}`}
              x={SVG_WIDTH - PADDING.right + 7}
              y={tick.y + 3.5}
              fill="#8892b0"
              fontSize="10"
              className="cursor-ns-resize select-none"
            >
              {tick.val.toFixed(2)}
            </text>
          ))}

          {/* EMA Overlays */}
          {showEma && chartMode === "CANDLES" && (
            <>
              {/* EMA 20 */}
              <polyline
                fill="none"
                stroke="#38bdf8"
                strokeWidth="1.3"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={ema20
                  .map((val, idx) => {
                    if (val === null) return null;
                    const x = PADDING.left + (idx + 0.5) * slotWidth;
                    const y = getY(val);
                    return `${x},${y}`;
                  })
                  .filter(Boolean)
                  .join(" ")}
              />
              {/* EMA 50 */}
              <polyline
                fill="none"
                stroke="#fb923c"
                strokeWidth="1.3"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={ema50
                  .map((val, idx) => {
                    if (val === null) return null;
                    const x = PADDING.left + (idx + 0.5) * slotWidth;
                    const y = getY(val);
                    return `${x},${y}`;
                  })
                  .filter(Boolean)
                  .join(" ")}
              />
            </>
          )}

          {/* Line Mode Area */}
          {chartMode === "LINE" && (
            <>
              <polygon
                fill="url(#mt5LineFill)"
                points={`
                  ${PADDING.left},${PADDING.top + priceAreaHeight}
                  ${validData
                    .map((d, idx) => {
                      const x = PADDING.left + (idx + 0.5) * slotWidth;
                      const y = getY(d.close);
                      return `${x},${y}`;
                    })
                    .join(" ")}
                  ${PADDING.left + (validData.length - 0.5) * slotWidth},${PADDING.top + priceAreaHeight}
                `}
              />
              <polyline
                fill="none"
                stroke="#2962ff"
                strokeWidth="2"
                points={validData
                  .map((d, idx) => {
                    const x = PADDING.left + (idx + 0.5) * slotWidth;
                    const y = getY(d.close);
                    return `${x},${y}`;
                  })
                  .join(" ")}
              />
            </>
          )}

          {/* Candlesticks & Volume Bars */}
          {validData.map((d, index) => {
            const isBull = d.close >= d.open;
            const openY = getY(d.open);
            const closeY = getY(d.close);
            const highY = getY(d.high);
            const lowY = getY(d.low);

            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(1.5, Math.abs(closeY - openY));

            const volTop = getVolY(d.volume);
            const volHeight = Math.max(1, PADDING.top + chartAreaHeight - volTop);

            const color = isBull ? "#00e676" : "#ff1744";
            const slotCenter = PADDING.left + (index + 0.5) * slotWidth;
            const bodyX = slotCenter - candleBodyWidth / 2;

            return (
              <g key={`candle-${d.time}-${index}`}>
                {/* Volume Histogram */}
                <rect
                  x={bodyX}
                  y={volTop}
                  width={candleBodyWidth}
                  height={volHeight}
                  fill={isBull ? "url(#mt5VolBull)" : "url(#mt5VolBear)"}
                  stroke={color}
                  strokeWidth="0.5"
                  opacity="0.85"
                />

                {chartMode === "CANDLES" && (
                  <>
                    {/* Wick */}
                    <line
                      x1={slotCenter}
                      y1={highY}
                      x2={slotCenter}
                      y2={lowY}
                      stroke={color}
                      strokeWidth="1.2"
                    />

                    {/* Candle Body */}
                    <rect
                      x={bodyX}
                      y={bodyTop}
                      width={candleBodyWidth}
                      height={bodyHeight}
                      fill={color}
                      stroke={color}
                      strokeWidth="0.5"
                      rx="0.5"
                    />
                  </>
                )}

                {/* X-axis Time Label */}
                {index % Math.max(1, Math.floor(validData.length / 8)) === 0 && (
                  <text
                    x={slotCenter}
                    y={SVG_HEIGHT - PADDING.bottom + 18}
                    textAnchor="middle"
                    fill="#8892b0"
                    fontSize="9.5"
                  >
                    {new Date(d.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </text>
                )}
              </g>
            );
          })}

          {/* MT5 Real-Time Bid Line (Cyan / Green) */}
          {showBidAsk && currentBidY >= PADDING.top && currentBidY <= PADDING.top + priceAreaHeight && (
            <g>
              <line
                x1={PADDING.left}
                y1={currentBidY}
                x2={SVG_WIDTH - PADDING.right}
                y2={currentBidY}
                stroke="#00e676"
                strokeWidth="1"
                strokeDasharray="4 2"
              />
              <rect
                x={SVG_WIDTH - PADDING.right + 2}
                y={currentBidY - 8}
                width={PADDING.right - 4}
                height={16}
                fill="#00e676"
                rx="2"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 6}
                y={currentBidY + 3.5}
                fill="#000000"
                fontSize="9.5"
                fontWeight="bold"
              >
                {currentBid.toFixed(2)}
              </text>
            </g>
          )}

          {/* MT5 Real-Time Ask Line (Red) */}
          {showBidAsk && currentAskY >= PADDING.top && currentAskY <= PADDING.top + priceAreaHeight && (
            <g>
              <line
                x1={PADDING.left}
                y1={currentAskY}
                x2={SVG_WIDTH - PADDING.right}
                y2={currentAskY}
                stroke="#ff1744"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              <rect
                x={SVG_WIDTH - PADDING.right + 2}
                y={currentAskY - 8}
                width={PADDING.right - 4}
                height={16}
                fill="#ff1744"
                rx="2"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 6}
                y={currentAskY + 3.5}
                fill="#ffffff"
                fontSize="9.5"
                fontWeight="bold"
              >
                {currentAsk.toFixed(2)}
              </text>
            </g>
          )}

          {/* Interactive Crosshair & Tags */}
          {hoverCoords && activeCandle && dragMode === "NONE" && (
            <g>
              <line
                x1={hoverCoords.x}
                y1={PADDING.top}
                x2={hoverCoords.x}
                y2={SVG_HEIGHT - PADDING.bottom}
                stroke="#8892b0"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
              <line
                x1={PADDING.left}
                y1={hoverCoords.y}
                x2={SVG_WIDTH - PADDING.right}
                y2={hoverCoords.y}
                stroke="#8892b0"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
              {/* Y Price Tag */}
              <rect
                x={SVG_WIDTH - PADDING.right + 2}
                y={hoverCoords.y - 7.5}
                width={PADDING.right - 4}
                height={15}
                fill="#1e2638"
                stroke="#8892b0"
                strokeWidth="0.8"
                rx="1"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 6}
                y={hoverCoords.y + 3}
                fill="#ffffff"
                fontSize="9"
              >
                {(maxPrice - ((hoverCoords.y - PADDING.top) / priceAreaHeight) * priceRange).toFixed(2)}
              </text>
              {/* X Time Tag */}
              <rect
                x={hoverCoords.x - 35}
                y={SVG_HEIGHT - PADDING.bottom + 3}
                width={70}
                height={16}
                fill="#1e2638"
                stroke="#8892b0"
                strokeWidth="0.8"
                rx="1"
              />
              <text
                x={hoverCoords.x}
                y={SVG_HEIGHT - PADDING.bottom + 14}
                textAnchor="middle"
                fill="#ffffff"
                fontSize="9"
              >
                {new Date(activeCandle.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* MT5 Bottom Status & Hotkeys Guide */}
      <div className="px-4 py-2 border-t border-[#1e2638] flex flex-wrap items-center justify-between text-3xs text-[#8892b0] bg-[#0d131f] gap-3">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-[#00e676]" /> Bullish Candle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-[#ff1744]" /> Bearish Candle
          </span>
          {showBidAsk && (
            <>
              <span className="flex items-center gap-1 text-[#00e676]">
                <span className="w-2 h-0.5 bg-[#00e676]" /> Bid: {currentBid.toFixed(2)}
              </span>
              <span className="flex items-center gap-1 text-[#ff1744]">
                <span className="w-2 h-0.5 bg-[#ff1744]" /> Ask: {currentAsk.toFixed(2)}
              </span>
              <span className="text-white bg-[#1e2638] px-1.5 py-0.5 rounded">
                Spread: {(Math.round((currentAsk - currentBid) * 100) / 100).toFixed(2)}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span>DRAG RIGHT SCALE: RESIZE HEIGHT</span>
          <span>·</span>
          <span>DOUBLE CLICK SCALE: AUTO FIT</span>
          <span>·</span>
          <span>WHEEL: ZOOM</span>
        </div>
      </div>
    </div>
  );
}
