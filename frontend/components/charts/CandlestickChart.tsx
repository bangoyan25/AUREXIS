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

  // Zoom & Pan state
  const [visibleCount, setVisibleCount] = useState<number>(50);
  const [panOffset, setPanOffset] = useState<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartX = useRef<number>(0);
  const dragStartOffset = useRef<number>(0);

  // Countdown timer in current bar
  const [timeRemaining, setTimeRemaining] = useState<string>("—");

  const SVG_WIDTH = 1000;
  const SVG_HEIGHT = 460;
  const PADDING = { top: 32, right: 75, bottom: 45, left: 15 };
  const VOLUME_RATIO = 0.16;

  // Real-time ticking of latest candle with livePrice
  const fullData = useMemo(() => {
    const raw = [...(data || [])];
    if (raw.length === 0) return [];
    if (livePrice && livePrice > 0 && raw.length > 0) {
      const last = raw[raw.length - 1];
      if (last && typeof last.high === "number" && typeof last.low === "number") {
        raw[raw.length - 1] = {
          ...last,
          close: livePrice,
          high: livePrice > last.high ? livePrice : last.high,
          low: livePrice < last.low ? livePrice : last.low,
        };
      }
    }
    return raw;
  }, [data, livePrice]);

  // Viewport slice based on visibleCount and panOffset
  const validData = useMemo(() => {
    if (fullData.length === 0) return [];
    const count = Math.min(fullData.length, Math.max(15, visibleCount));
    const maxOffset = fullData.length - count;
    const clampedOffset = Math.max(0, Math.min(maxOffset, panOffset));
    const start = fullData.length - count - clampedOffset;
    const end = start + count;
    return fullData.slice(Math.max(0, start), Math.min(fullData.length, end));
  }, [fullData, visibleCount, panOffset]);

  // Compute EMA 20 & EMA 50
  const { ema20, ema50 } = useMemo(() => {
    const calcEma = (period: number) => {
      if (fullData.length < period) return [];
      const k = 2 / (period + 1);
      const res: number[] = [];
      let prevEma = fullData.slice(0, period).reduce((acc, c) => acc + c.close, 0) / period;
      res.push(prevEma);

      for (let i = period; i < fullData.length; i++) {
        const item = fullData[i];
        if (!item) continue;
        const curr = item.close * k + prevEma * (1 - k);
        res.push(curr);
        prevEma = curr;
      }
      return res;
    };

    const e20Full = calcEma(20);
    const e50Full = calcEma(50);

    // Slice to match validData viewport
    const count = validData.length;
    const maxOffset = fullData.length - count;
    const clampedOffset = Math.max(0, Math.min(maxOffset, panOffset));
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
  }, [fullData, validData.length, panOffset]);

  // Price calculations
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

    if (livePrice && livePrice > 0) {
      if (livePrice < min) min = livePrice;
      if (livePrice > max) max = livePrice;
    }

    const diff = max - min || 1;
    const pad = diff * 0.08;
    const finalMin = min - pad;
    const finalMax = max + pad;

    return {
      minPrice: finalMin,
      maxPrice: finalMax,
      maxVolume: maxVol || 1,
      priceRange: finalMax - finalMin || 1,
    };
  }, [validData, livePrice]);

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

  // Y-axis price ticks
  const priceTicks = useMemo(() => {
    if (priceRange <= 0) return [];
    const ticks = [];
    const count = 6;
    for (let i = 0; i < count; i++) {
      const val = minPrice + (priceRange * i) / (count - 1);
      ticks.push({
        val,
        y: getY(val),
      });
    }
    return ticks;
  }, [minPrice, priceRange, getY]);

  // Candle countdown update
  useEffect(() => {
    const updateCountdown = () => {
      const now = new Date();
      const mins = now.getUTCMinutes();
      const secs = now.getUTCSeconds();
      let tfMinutes = 15;
      if (timeframe === "M1") tfMinutes = 1;
      else if (timeframe === "M5") tfMinutes = 5;
      else if (timeframe === "M30") tfMinutes = 30;
      else if (timeframe === "H1") tfMinutes = 60;
      else if (timeframe === "H4") tfMinutes = 240;
      else if (timeframe === "D1") tfMinutes = 1440;

      const passedSecs = (mins % tfMinutes) * 60 + secs;
      const leftSecs = tfMinutes * 60 - passedSecs;
      const m = Math.floor(leftSecs / 60);
      const s = leftSecs % 60;
      setTimeRemaining(`${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`);
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [timeframe]);

  // Mouse drag & zoom handlers
  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      // Zoom in
      setVisibleCount((prev) => Math.max(15, prev - 5));
    } else {
      // Zoom out
      setVisibleCount((prev) => Math.min(fullData.length || 100, prev + 5));
    }
  };

  const handleMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    setIsDragging(true);
    dragStartX.current = e.clientX;
    dragStartOffset.current = panOffset;
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * SVG_WIDTH;
    const svgY = ((e.clientY - rect.top) / rect.height) * SVG_HEIGHT;

    if (isDragging) {
      const deltaPixels = e.clientX - dragStartX.current;
      const candlePixels = rect.width / (validData.length || 50);
      const candlesMoved = Math.round(deltaPixels / candlePixels);
      const maxOffset = Math.max(0, fullData.length - validData.length);
      setPanOffset(Math.max(0, Math.min(maxOffset, dragStartOffset.current + candlesMoved)));
      return;
    }

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
    setIsDragging(false);
  };

  const handleMouseLeave = () => {
    setIsDragging(false);
    setHoverIndex(null);
    setHoverCoords(null);
  };

  const activeCandle =
    hoverIndex !== null && validData[hoverIndex]
      ? validData[hoverIndex]
      : validData.length > 0
      ? validData[validData.length - 1]
      : null;

  const currentPrice =
    livePrice || (validData.length > 0 ? validData[validData.length - 1]?.close ?? null : null);
  const currentPriceY = currentPrice ? getY(currentPrice) : null;

  const slotWidth = validData.length > 0 ? chartAreaWidth / validData.length : 10;
  const candleBodyWidth = Math.max(2.5, Math.min(13, slotWidth * 0.74));

  const changeVal = activeCandle ? activeCandle.close - activeCandle.open : 0;
  const changePct = activeCandle && activeCandle.open > 0 ? (changeVal / activeCandle.open) * 100 : 0;

  return (
    <div
      ref={containerRef}
      onWheel={handleWheel}
      className={clsx(
        "bg-[#131722] border border-[#2a2e39] rounded flex flex-col select-none overflow-hidden font-sans",
        className
      )}
    >
      {/* TradingView Top Toolbar */}
      <div className="px-3.5 py-2 border-b border-[#2a2e39] flex flex-wrap items-center justify-between gap-3 bg-[#1e222d]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold text-white tracking-wider">{symbol}</span>
            <span className="text-3xs font-mono text-[#787b86]">GOLD/USD</span>
            <span className="w-2 h-2 rounded-full bg-[#089981] animate-pulse ml-1" />
          </div>

          <div className="h-4 w-px bg-[#2a2e39]" />

          {/* Timeframe Bar */}
          <div className="flex items-center gap-0.5 bg-[#131722] border border-[#2a2e39] rounded p-0.5">
            {availableTimeframes.map((tf) => (
              <button
                key={tf}
                onClick={() => {
                  onTimeframeChange?.(tf);
                  setPanOffset(0); // reset pan on timeframe switch
                }}
                className={clsx(
                  "px-2 py-0.5 text-2xs font-mono rounded transition-colors",
                  timeframe === tf
                    ? "bg-[#2962ff] text-white font-semibold"
                    : "text-[#787b86] hover:text-white hover:bg-[#2a2e39]"
                )}
              >
                {tf}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-[#2a2e39]" />

          {/* Chart Type Toggle (Candles vs Line) */}
          <div className="flex items-center gap-0.5 bg-[#131722] border border-[#2a2e39] rounded p-0.5">
            <button
              onClick={() => setChartMode("CANDLES")}
              className={clsx(
                "px-2 py-0.5 text-2xs font-mono rounded transition-colors",
                chartMode === "CANDLES" ? "bg-[#2a2e39] text-white" : "text-[#787b86] hover:text-white"
              )}
            >
              Candles
            </button>
            <button
              onClick={() => setChartMode("LINE")}
              className={clsx(
                "px-2 py-0.5 text-2xs font-mono rounded transition-colors",
                chartMode === "LINE" ? "bg-[#2a2e39] text-white" : "text-[#787b86] hover:text-white"
              )}
            >
              Line
            </button>
          </div>

          {/* Indicators Toggle */}
          <button
            onClick={() => setShowEma((v) => !v)}
            className={clsx(
              "px-2 py-1 text-2xs font-mono rounded border transition-colors flex items-center gap-1",
              showEma ? "bg-[#2962ff]/15 border-[#2962ff] text-[#2962ff]" : "border-[#2a2e39] text-[#787b86] hover:text-white"
            )}
          >
            EMA 20/50
          </button>
        </div>

        {/* Right Action: Countdown & Reset Pan */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-2xs font-mono text-[#787b86]">
            <span>CLOSE IN:</span>
            <span className="text-[#f0f3fa] font-bold">{timeRemaining}</span>
          </div>
          {panOffset > 0 && (
            <button
              onClick={() => setPanOffset(0)}
              className="px-2 py-0.5 bg-[#2962ff] hover:bg-[#1e4bd8] text-white text-3xs font-mono rounded font-semibold uppercase tracking-wider"
            >
              Go to Live Head
            </button>
          )}
        </div>
      </div>

      {/* Floating Legend / Stat Strip */}
      <div className="px-4 py-1.5 bg-[#131722] border-b border-[#2a2e39]/60 flex flex-wrap items-center justify-between text-2xs font-mono tabular-nums">
        {activeCandle ? (
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[#787b86]">
              O <span className="text-white font-medium">{activeCandle.open.toFixed(2)}</span>
            </span>
            <span className="text-[#787b86]">
              H <span className="text-white font-medium">{activeCandle.high.toFixed(2)}</span>
            </span>
            <span className="text-[#787b86]">
              L <span className="text-white font-medium">{activeCandle.low.toFixed(2)}</span>
            </span>
            <span className="text-[#787b86]">
              C <span className={activeCandle.close >= activeCandle.open ? "text-[#089981] font-bold" : "text-[#f23645] font-bold"}>
                {activeCandle.close.toFixed(2)}
              </span>
            </span>
            <span className={changeVal >= 0 ? "text-[#089981] font-medium" : "text-[#f23645] font-medium"}>
              {changeVal >= 0 ? "+" : ""}{changeVal.toFixed(2)} ({changeVal >= 0 ? "+" : ""}{changePct.toFixed(2)}%)
            </span>
            <span className="text-[#787b86]">
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
          <span className="text-[#787b86]">Awaiting live ticks...</span>
        )}
        <span className="text-3xs text-[#787b86]">
          {activeCandle ? new Date(activeCandle.time).toLocaleString() : ""}
        </span>
      </div>

      {/* SVG Canvas Area */}
      <div className="relative w-full h-[460px]">
        {isLoading && validData.length === 0 && (
          <div className="absolute inset-0 bg-[#131722]/80 backdrop-blur-sm flex items-center justify-center z-20">
            <span className="text-xs font-mono text-[#2962ff] animate-pulse tracking-widest uppercase font-semibold">
              SYNCHRONIZING BROKER DATA FEED...
            </span>
          </div>
        )}

        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          preserveAspectRatio="none"
          className={clsx("w-full h-full block", isDragging ? "cursor-grabbing" : "cursor-crosshair")}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id="tvVolBull" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#089981" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#089981" stopOpacity="0.05" />
            </linearGradient>
            <linearGradient id="tvVolBear" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f23645" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#f23645" stopOpacity="0.05" />
            </linearGradient>
            <linearGradient id="tvLineArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2962ff" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#2962ff" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Background Canvas */}
          <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="#131722" />

          {/* Grid Lines (Horizontal) */}
          {priceTicks.map((tick, i) => (
            <g key={`tick-${i}`}>
              <line
                x1={PADDING.left}
                y1={tick.y}
                x2={SVG_WIDTH - PADDING.right}
                y2={tick.y}
                stroke="#1e222d"
                strokeWidth="1"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 8}
                y={tick.y + 3.5}
                fill="#787b86"
                fontSize="10"
                fontFamily="monospace"
              >
                {tick.val.toFixed(2)}
              </text>
            </g>
          ))}

          {/* Grid Lines (Vertical) */}
          {validData.map((_, index) => {
            if (index % Math.max(1, Math.floor(validData.length / 8)) !== 0) return null;
            const slotCenter = PADDING.left + (index + 0.5) * slotWidth;
            return (
              <line
                key={`vert-grid-${index}`}
                x1={slotCenter}
                y1={PADDING.top}
                x2={slotCenter}
                y2={SVG_HEIGHT - PADDING.bottom}
                stroke="#1e222d"
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
            stroke="#2a2e39"
          />

          {/* EMA Lines (EMA 20 & EMA 50) */}
          {showEma && chartMode === "CANDLES" && (
            <>
              {/* EMA 20 (Light Blue) */}
              <polyline
                fill="none"
                stroke="#38bdf8"
                strokeWidth="1.2"
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
              {/* EMA 50 (Orange) */}
              <polyline
                fill="none"
                stroke="#fb923c"
                strokeWidth="1.2"
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

          {/* Line Chart Mode */}
          {chartMode === "LINE" && (
            <>
              {/* Shaded Area under Line */}
              <polygon
                fill="url(#tvLineArea)"
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
              {/* Main Line */}
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

            const color = isBull ? "#089981" : "#f23645";
            const slotCenter = PADDING.left + (index + 0.5) * slotWidth;
            const bodyX = slotCenter - candleBodyWidth / 2;

            return (
              <g key={`candle-${d.time}-${index}`}>
                {/* Volume Bar */}
                <rect
                  x={bodyX}
                  y={volTop}
                  width={candleBodyWidth}
                  height={volHeight}
                  fill={isBull ? "url(#tvVolBull)" : "url(#tvVolBear)"}
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

                    {/* Body */}
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

                {/* X-axis time label */}
                {index % Math.max(1, Math.floor(validData.length / 7)) === 0 && (
                  <text
                    x={slotCenter}
                    y={SVG_HEIGHT - PADDING.bottom + 18}
                    textAnchor="middle"
                    fill="#787b86"
                    fontSize="9.5"
                    fontFamily="monospace"
                  >
                    {new Date(d.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </text>
                )}
              </g>
            );
          })}

          {/* Current Live Price Line & Pulsing Dot */}
          {currentPriceY !== null && currentPrice !== null && (
            <g>
              <line
                x1={PADDING.left}
                y1={currentPriceY}
                x2={SVG_WIDTH - PADDING.right}
                y2={currentPriceY}
                stroke="#2962ff"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
              {/* Pulsing indicator on right scale */}
              <rect
                x={SVG_WIDTH - PADDING.right + 2}
                y={currentPriceY - 8.5}
                width={PADDING.right - 4}
                height={17}
                fill="#2962ff"
                rx="2"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 6}
                y={currentPriceY + 3.5}
                fill="#ffffff"
                fontSize="10"
                fontWeight="bold"
                fontFamily="monospace"
              >
                {currentPrice.toFixed(2)}
              </text>
            </g>
          )}

          {/* TradingView Crosshair */}
          {hoverCoords && activeCandle && (
            <g>
              {/* Vertical Crosshair */}
              <line
                x1={hoverCoords.x}
                y1={PADDING.top}
                x2={hoverCoords.x}
                y2={SVG_HEIGHT - PADDING.bottom}
                stroke="#787b86"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
              {/* Horizontal Crosshair */}
              <line
                x1={PADDING.left}
                y1={hoverCoords.y}
                x2={SVG_WIDTH - PADDING.right}
                y2={hoverCoords.y}
                stroke="#787b86"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
              {/* Y-axis Price Tag */}
              <rect
                x={SVG_WIDTH - PADDING.right + 2}
                y={hoverCoords.y - 7.5}
                width={PADDING.right - 4}
                height={15}
                fill="#2a2e39"
                stroke="#787b86"
                strokeWidth="0.8"
                rx="1"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 6}
                y={hoverCoords.y + 3}
                fill="#ffffff"
                fontSize="9"
                fontFamily="monospace"
              >
                {(maxPrice - ((hoverCoords.y - PADDING.top) / priceAreaHeight) * priceRange).toFixed(2)}
              </text>

              {/* X-axis Date Tag */}
              <rect
                x={hoverCoords.x - 35}
                y={SVG_HEIGHT - PADDING.bottom + 3}
                width={70}
                height={16}
                fill="#2a2e39"
                stroke="#787b86"
                strokeWidth="0.8"
                rx="1"
              />
              <text
                x={hoverCoords.x}
                y={SVG_HEIGHT - PADDING.bottom + 14}
                textAnchor="middle"
                fill="#ffffff"
                fontSize="9"
                fontFamily="monospace"
              >
                {new Date(activeCandle.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* TradingView Footer Bar */}
      <div className="px-4 py-2 border-t border-[#2a2e39] flex items-center justify-between text-3xs font-mono text-[#787b86] bg-[#1e222d]">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-[#089981]" /> Bullish Candle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-[#f23645]" /> Bearish Candle
          </span>
          {showEma && (
            <>
              <span className="flex items-center gap-1 text-[#38bdf8]">
                <span className="w-2 h-0.5 bg-[#38bdf8]" /> EMA 20
              </span>
              <span className="flex items-center gap-1 text-[#fb923c]">
                <span className="w-2 h-0.5 bg-[#fb923c]" /> EMA 50
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span>MOUSE WHEEL: ZOOM</span>
          <span>·</span>
          <span>CLICK & DRAG: PAN</span>
          <span>·</span>
          <span>FEED: BROKER MT5 STREAM</span>
        </div>
      </div>
    </div>
  );
}
