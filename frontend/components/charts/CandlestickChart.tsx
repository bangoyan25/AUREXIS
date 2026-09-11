"use client";

import React, { useState, useRef, useMemo, useCallback } from "react";
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
  availableTimeframes = ["M5", "M15", "H1", "H4", "D1"],
  isLoading = false,
  className,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [hoverCoords, setHoverCoords] = useState<{ x: number; y: number } | null>(null);

  // Dimensions
  const height = 440;
  const padding = { top: 25, right: 65, bottom: 45, left: 15 };
  const volumeHeightRatio = 0.18;

  const validData = useMemo(() => {
    return (data || []).filter(
      (d) =>
        d &&
        typeof d.open === "number" &&
        typeof d.high === "number" &&
        typeof d.low === "number" &&
        typeof d.close === "number" &&
        !isNaN(d.open) &&
        !isNaN(d.close)
    );
  }, [data]);

  // Price calculations
  const { minPrice, maxPrice, maxVolume, priceRange } = useMemo(() => {
    if (validData.length === 0) {
      return { minPrice: 0, maxPrice: 100, maxVolume: 1, priceRange: 100 };
    }
    let min = Infinity;
    let max = -Infinity;
    let maxVol = 0;

    for (const d of validData) {
      if (d.low < min) min = d.low;
      if (d.high > max) max = d.high;
      if (d.volume > maxVol) maxVol = d.volume;
    }

    if (livePrice !== null && livePrice !== undefined && livePrice > 0) {
      if (livePrice < min) min = livePrice;
      if (livePrice > max) max = livePrice;
    }

    // Add 8% vertical padding for wicks & price levels
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

  const chartAreaHeight = height - padding.top - padding.bottom;
  const priceAreaHeight = chartAreaHeight * (1 - volumeHeightRatio);
  const volumeAreaHeight = chartAreaHeight * volumeHeightRatio;

  // Coordinate mappers
  const getY = useCallback(
    (price: number) => {
      const normalized = (maxPrice - price) / priceRange;
      return padding.top + normalized * priceAreaHeight;
    },
    [maxPrice, priceRange, priceAreaHeight, padding.top]
  );

  const getVolY = useCallback(
    (vol: number) => {
      const normalized = Math.min(1, vol / maxVolume);
      const topY = padding.top + priceAreaHeight + (1 - normalized) * volumeAreaHeight;
      return topY;
    },
    [maxVolume, priceAreaHeight, volumeAreaHeight, padding.top]
  );

  // Y-axis grid lines & price ticks (5 ticks)
  const priceTicks = useMemo(() => {
    if (priceRange <= 0) return [];
    const ticks = [];
    const count = 5;
    for (let i = 0; i < count; i++) {
      const val = minPrice + (priceRange * i) / (count - 1);
      ticks.push({
        val,
        y: getY(val),
      });
    }
    return ticks;
  }, [minPrice, priceRange, getY]);

  const activeCandle = hoverIndex !== null && validData[hoverIndex] ? validData[hoverIndex] : validData[validData.length - 1];

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!containerRef.current || validData.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    const availableWidth = rect.width - padding.left - padding.right;
    const candleSlotWidth = availableWidth / validData.length;
    const idx = Math.floor((clientX - padding.left) / candleSlotWidth);

    if (idx >= 0 && idx < validData.length) {
      setHoverIndex(idx);
      setHoverCoords({ x: clientX, y: clientY });
    } else {
      setHoverIndex(null);
      setHoverCoords(null);
    }
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
    setHoverCoords(null);
  };

  const currentPrice = livePrice || (validData.length > 0 ? (validData[validData.length - 1]?.close ?? null) : null);
  const currentPriceY = currentPrice ? getY(currentPrice) : null;

  return (
    <div
      ref={containerRef}
      className={clsx(
        "bg-aurexis-surface border border-aurexis-border rounded flex flex-col select-none overflow-hidden",
        className
      )}
    >
      {/* Header bar: Symbol, Timeframe, Live Stats */}
      <div className="px-4 py-2.5 border-b border-aurexis-border/60 flex flex-wrap items-center justify-between gap-3 bg-aurexis-bg/50">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold text-aurexis-text tracking-wider">{symbol}</span>
            <span className="w-1.5 h-1.5 rounded-full bg-aurexis-success animate-pulse" />
            <span className="text-3xs font-mono uppercase tracking-widest text-aurexis-success">LIVE FEED</span>
          </div>

          {/* Timeframe Selector */}
          <div className="flex items-center gap-1 bg-aurexis-surface border border-aurexis-border/60 rounded p-0.5">
            {availableTimeframes.map((tf) => (
              <button
                key={tf}
                onClick={() => onTimeframeChange?.(tf)}
                className={clsx(
                  "px-2 py-0.5 text-2xs font-mono rounded transition-colors",
                  timeframe === tf
                    ? "bg-aurexis-accent text-aurexis-bg font-semibold"
                    : "text-aurexis-subtle hover:text-aurexis-text hover:bg-aurexis-surface"
                )}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        {/* OHLCV Stat display */}
        {activeCandle ? (
          <div className="flex items-center gap-3 text-2xs font-mono tabular-nums">
            <span className="text-aurexis-faint">
              O: <span className="text-aurexis-text">{activeCandle.open.toFixed(2)}</span>
            </span>
            <span className="text-aurexis-faint">
              H: <span className="text-aurexis-text">{activeCandle.high.toFixed(2)}</span>
            </span>
            <span className="text-aurexis-faint">
              L: <span className="text-aurexis-text">{activeCandle.low.toFixed(2)}</span>
            </span>
            <span className="text-aurexis-faint">
              C:{" "}
              <span
                className={
                  activeCandle.close >= activeCandle.open ? "text-aurexis-success font-medium" : "text-aurexis-danger font-medium"
                }
              >
                {activeCandle.close.toFixed(2)}
              </span>
            </span>
            <span className="text-aurexis-faint">
              Vol: <span className="text-aurexis-subtle">{Math.round(activeCandle.volume)}</span>
            </span>
            <span className="text-aurexis-faint text-3xs">
              {new Date(activeCandle.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        ) : (
          <div className="text-2xs font-mono text-aurexis-faint">Awaiting market bars...</div>
        )}
      </div>

      {/* SVG Canvas Area */}
      <div className="relative w-full" style={{ height }}>
        {isLoading && (
          <div className="absolute inset-0 bg-aurexis-bg/60 backdrop-blur-[1px] flex items-center justify-center z-20">
            <span className="text-2xs font-mono text-aurexis-accent animate-pulse tracking-widest uppercase">
              UPDATING CHART DATA...
            </span>
          </div>
        )}

        {validData.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-aurexis-faint font-mono text-xs gap-1">
            <p>No closed candle data available for {symbol} ({timeframe})</p>
            <p className="text-2xs text-aurexis-subtle">Connecting to live MT5 broker stream...</p>
          </div>
        ) : (
          <svg
            className="w-full h-full block cursor-crosshair"
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
          >
            <defs>
              <linearGradient id="volBullGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22c55e" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#22c55e" stopOpacity="0.05" />
              </linearGradient>
              <linearGradient id="volBearGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0.05" />
              </linearGradient>
            </defs>

            {/* Price Grid Lines (horizontal) */}
            {priceTicks.map((tick, i) => (
              <g key={`tick-${i}`}>
                <line
                  x1={padding.left}
                  y1={tick.y}
                  x2={`calc(100% - ${padding.right}px)`}
                  y2={tick.y}
                  stroke="rgba(255, 255, 255, 0.05)"
                  strokeDasharray="3 3"
                />
                <text
                  x={`calc(100% - ${padding.right - 8}px)`}
                  y={tick.y + 4}
                  fill="#71717a"
                  fontSize="10"
                  fontFamily="monospace"
                >
                  {tick.val.toFixed(2)}
                </text>
              </g>
            ))}

            {/* Volume Area Divider line */}
            <line
              x1={padding.left}
              y1={padding.top + priceAreaHeight}
              x2={`calc(100% - ${padding.right}px)`}
              y2={padding.top + priceAreaHeight}
              stroke="rgba(255, 255, 255, 0.08)"
            />

            {/* Candlesticks & Volume Bars */}
            {validData.map((d, index) => {
              const count = validData.length;
              const slotPercent = (100 - ((padding.left + padding.right) / 800) * 100) / count;
              // Render candle within relative slot
              const isBull = d.close >= d.open;
              const openY = getY(d.open);
              const closeY = getY(d.close);
              const highY = getY(d.high);
              const lowY = getY(d.low);

              const bodyTop = Math.min(openY, closeY);
              const bodyHeight = Math.max(2, Math.abs(closeY - openY));

              const volTop = getVolY(d.volume);
              const volHeight = Math.max(1, padding.top + chartAreaHeight - volTop);

              const color = isBull ? "#22c55e" : "#ef4444";
              const strokeColor = isBull ? "#16a34a" : "#dc2626";

              // Slot center percentage
              const xPercent =
                ((padding.left + (index + 0.5) * ((800 - padding.left - padding.right) / count)) / 800) * 100;

              return (
                <g key={`candle-${d.time}-${index}`}>
                  {/* Volume Bar */}
                  <rect
                    x={`calc(${xPercent}% - 3px)`}
                    y={volTop}
                    width="6"
                    height={volHeight}
                    fill={isBull ? "url(#volBullGrad)" : "url(#volBearGrad)"}
                    stroke={color}
                    strokeWidth="0.5"
                    opacity="0.75"
                  />

                  {/* Wick (High-Low Line) */}
                  <line
                    x1={`${xPercent}%`}
                    y1={highY}
                    x2={`${xPercent}%`}
                    y2={lowY}
                    stroke={strokeColor}
                    strokeWidth="1.2"
                  />

                  {/* Candle Body */}
                  <rect
                    x={`calc(${xPercent}% - 4.5px)`}
                    y={bodyTop}
                    width="9"
                    height={bodyHeight}
                    fill={color}
                    stroke={strokeColor}
                    strokeWidth="0.8"
                    rx="0.5"
                  />

                  {/* Time label on X-axis (every N candles) */}
                  {index % Math.max(1, Math.floor(count / 6)) === 0 && (
                    <text
                      x={`${xPercent}%`}
                      y={height - padding.bottom + 20}
                      textAnchor="middle"
                      fill="#71717a"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      {new Date(d.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Current Price Line */}
            {currentPriceY !== null && currentPrice !== null && (
              <g>
                <line
                  x1={padding.left}
                  y1={currentPriceY}
                  x2={`calc(100% - ${padding.right}px)`}
                  y2={currentPriceY}
                  stroke="#eab308"
                  strokeWidth="1"
                  strokeDasharray="4 3"
                />
                {/* Price tag on right scale */}
                <rect
                  x={`calc(100% - ${padding.right}px)`}
                  y={currentPriceY - 8}
                  width={padding.right - 4}
                  height={16}
                  fill="#eab308"
                  rx="2"
                />
                <text
                  x={`calc(100% - ${padding.right - 4}px)`}
                  y={currentPriceY + 3.5}
                  fill="#000000"
                  fontSize="9.5"
                  fontWeight="bold"
                  fontFamily="monospace"
                >
                  {currentPrice.toFixed(2)}
                </text>
              </g>
            )}

            {/* Hover Crosshair & Details */}
            {hoverCoords && activeCandle && (
              <g>
                {/* Vertical Crosshair Line */}
                <line
                  x1={hoverCoords.x}
                  y1={padding.top}
                  x2={hoverCoords.x}
                  y2={height - padding.bottom}
                  stroke="rgba(255, 255, 255, 0.3)"
                  strokeDasharray="3 3"
                />
                {/* Horizontal Crosshair Line */}
                <line
                  x1={padding.left}
                  y1={hoverCoords.y}
                  x2={`calc(100% - ${padding.right}px)`}
                  y2={hoverCoords.y}
                  stroke="rgba(255, 255, 255, 0.3)"
                  strokeDasharray="3 3"
                />
                {/* Hover Price Tag */}
                <rect
                  x={`calc(100% - ${padding.right}px)`}
                  y={hoverCoords.y - 7}
                  width={padding.right - 4}
                  height={14}
                  fill="#27272a"
                  stroke="#3f3f46"
                  strokeWidth="1"
                  rx="1"
                />
                <text
                  x={`calc(100% - ${padding.right - 4}px)`}
                  y={hoverCoords.y + 3}
                  fill="#fafafa"
                  fontSize="9"
                  fontFamily="monospace"
                >
                  {(maxPrice - ((hoverCoords.y - padding.top) / priceAreaHeight) * priceRange).toFixed(2)}
                </text>
              </g>
            )}
          </svg>
        )}
      </div>

      {/* Footer bar: Legend & Broker Info */}
      <div className="px-4 py-2 border-t border-aurexis-border/40 flex items-center justify-between text-3xs font-mono text-aurexis-faint bg-aurexis-surface">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-aurexis-success" /> Bullish Candle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-aurexis-danger" /> Bearish Candle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-0.5 bg-yellow-500" /> Current Market Price
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span>SERVER TIME: UTC</span>
          <span>·</span>
          <span>AUTHORITATIVE MT5 STREAM</span>
        </div>
      </div>
    </div>
  );
}
