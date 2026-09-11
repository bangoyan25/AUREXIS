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

  // SVG Virtual Coordinate Dimensions (Resolution-independent viewBox)
  const SVG_WIDTH = 1000;
  const SVG_HEIGHT = 450;
  const PADDING = { top: 30, right: 80, bottom: 45, left: 20 };
  const VOLUME_RATIO = 0.18;

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

    if (livePrice !== null && livePrice !== undefined && livePrice > 0) {
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

  const chartAreaWidth = SVG_WIDTH - PADDING.left - PADDING.right; // 900
  const chartAreaHeight = SVG_HEIGHT - PADDING.top - PADDING.bottom; // 375
  const priceAreaHeight = chartAreaHeight * (1 - VOLUME_RATIO); // ~307
  const volumeAreaHeight = chartAreaHeight * VOLUME_RATIO; // ~68

  // Coordinate mappers
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

  // Y-axis grid lines (5 levels)
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

  const activeCandle =
    hoverIndex !== null && validData[hoverIndex]
      ? validData[hoverIndex]
      : validData.length > 0
      ? validData[validData.length - 1]
      : null;

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (validData.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * SVG_WIDTH;
    const svgY = ((e.clientY - rect.top) / rect.height) * SVG_HEIGHT;

    const slotWidth = chartAreaWidth / validData.length;
    const idx = Math.floor((svgX - PADDING.left) / slotWidth);

    if (idx >= 0 && idx < validData.length) {
      setHoverIndex(idx);
      setHoverCoords({ x: svgX, y: svgY });
    } else {
      setHoverIndex(null);
      setHoverCoords(null);
    }
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
    setHoverCoords(null);
  };

  const currentPrice =
    livePrice || (validData.length > 0 ? validData[validData.length - 1]?.close ?? null : null);
  const currentPriceY = currentPrice ? getY(currentPrice) : null;

  const slotWidth = validData.length > 0 ? chartAreaWidth / validData.length : 10;
  const candleBodyWidth = Math.max(3, Math.min(12, slotWidth * 0.72));

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
          <div className="text-2xs font-mono text-aurexis-faint">Synchronizing market bars...</div>
        )}
      </div>

      {/* SVG Canvas Area */}
      <div className="relative w-full h-[450px]">
        {isLoading && validData.length === 0 && (
          <div className="absolute inset-0 bg-aurexis-bg/60 backdrop-blur-[1px] flex items-center justify-center z-20">
            <span className="text-2xs font-mono text-aurexis-accent animate-pulse tracking-widest uppercase">
              SYNCHRONIZING REAL-TIME BROKER BARS...
            </span>
          </div>
        )}

        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          preserveAspectRatio="none"
          className="w-full h-full block cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id="volBullGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#22c55e" stopOpacity="0.08" />
            </linearGradient>
            <linearGradient id="volBearGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.08" />
            </linearGradient>
          </defs>

          {/* Background area */}
          <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="#0d1117" />

          {/* Price Grid Lines (horizontal) */}
          {priceTicks.map((tick, i) => (
            <g key={`tick-${i}`}>
              <line
                x1={PADDING.left}
                y1={tick.y}
                x2={SVG_WIDTH - PADDING.right}
                y2={tick.y}
                stroke="#21262d"
                strokeDasharray="3 3"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 8}
                y={tick.y + 3.5}
                fill="#8b949e"
                fontSize="10"
                fontFamily="monospace"
              >
                {tick.val.toFixed(2)}
              </text>
            </g>
          ))}

          {/* Volume Area Divider line */}
          <line
            x1={PADDING.left}
            y1={PADDING.top + priceAreaHeight}
            x2={SVG_WIDTH - PADDING.right}
            y2={PADDING.top + priceAreaHeight}
            stroke="#30363d"
          />

          {/* Candlesticks & Volume Bars */}
          {validData.map((d, index) => {
            const isBull = d.close >= d.open;
            const openY = getY(d.open);
            const closeY = getY(d.close);
            const highY = getY(d.high);
            const lowY = getY(d.low);

            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(2, Math.abs(closeY - openY));

            const volTop = getVolY(d.volume);
            const volHeight = Math.max(1, PADDING.top + chartAreaHeight - volTop);

            const color = isBull ? "#22c55e" : "#ef4444";
            const strokeColor = isBull ? "#16a34a" : "#dc2626";

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
                  fill={isBull ? "url(#volBullGrad)" : "url(#volBearGrad)"}
                  stroke={color}
                  strokeWidth="0.5"
                  opacity="0.8"
                />

                {/* Wick (High-Low Line) */}
                <line
                  x1={slotCenter}
                  y1={highY}
                  x2={slotCenter}
                  y2={lowY}
                  stroke={strokeColor}
                  strokeWidth="1.2"
                />

                {/* Candle Body */}
                <rect
                  x={bodyX}
                  y={bodyTop}
                  width={candleBodyWidth}
                  height={bodyHeight}
                  fill={color}
                  stroke={strokeColor}
                  strokeWidth="0.8"
                  rx="0.5"
                />

                {/* Time label on X-axis */}
                {index % Math.max(1, Math.floor(validData.length / 7)) === 0 && (
                  <text
                    x={slotCenter}
                    y={SVG_HEIGHT - PADDING.bottom + 18}
                    textAnchor="middle"
                    fill="#8b949e"
                    fontSize="9.5"
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
                x1={PADDING.left}
                y1={currentPriceY}
                x2={SVG_WIDTH - PADDING.right}
                y2={currentPriceY}
                stroke="#eab308"
                strokeWidth="1.2"
                strokeDasharray="4 3"
              />
              <rect
                x={SVG_WIDTH - PADDING.right + 2}
                y={currentPriceY - 8}
                width={PADDING.right - 6}
                height={16}
                fill="#eab308"
                rx="2"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 6}
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
              <line
                x1={hoverCoords.x}
                y1={PADDING.top}
                x2={hoverCoords.x}
                y2={SVG_HEIGHT - PADDING.bottom}
                stroke="rgba(255, 255, 255, 0.4)"
                strokeDasharray="3 3"
              />
              <line
                x1={PADDING.left}
                y1={hoverCoords.y}
                x2={SVG_WIDTH - PADDING.right}
                y2={hoverCoords.y}
                stroke="rgba(255, 255, 255, 0.4)"
                strokeDasharray="3 3"
              />
              <rect
                x={SVG_WIDTH - PADDING.right + 2}
                y={hoverCoords.y - 7}
                width={PADDING.right - 6}
                height={14}
                fill="#21262d"
                stroke="#484f58"
                strokeWidth="1"
                rx="1"
              />
              <text
                x={SVG_WIDTH - PADDING.right + 6}
                y={hoverCoords.y + 3}
                fill="#f0f6fc"
                fontSize="9"
                fontFamily="monospace"
              >
                {(maxPrice - ((hoverCoords.y - PADDING.top) / priceAreaHeight) * priceRange).toFixed(2)}
              </text>
            </g>
          )}
        </svg>
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
            <span className="w-2 h-0.5 bg-yellow-500" /> Live Market Price
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span>SERVER: UTC</span>
          <span>·</span>
          <span>AUTHORITATIVE MT5 STREAM ({validData.length} BARS)</span>
        </div>
      </div>
    </div>
  );
}
