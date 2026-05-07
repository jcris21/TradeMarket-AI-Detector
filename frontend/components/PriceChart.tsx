"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type LineData, type Time } from "lightweight-charts";
import { getTickerHistory } from "@/lib/api";

interface PriceChartProps {
  ticker: string | null;
  getHistory: (ticker: string) => number[];
}

export default function PriceChart({ ticker, getHistory }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#161b22" },
        textColor: "#8b949e",
        fontFamily: "ui-monospace, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#21262d" },
        horzLines: { color: "#21262d" },
      },
      crosshair: {
        vertLine: { color: "#30363d", labelBackgroundColor: "#30363d" },
        horzLine: { color: "#30363d", labelBackgroundColor: "#30363d" },
      },
      rightPriceScale: {
        borderColor: "#30363d",
      },
      timeScale: {
        borderColor: "#30363d",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const series = chart.addSeries(LineSeries, {
      color: "#209dd7",
      lineWidth: 2,
      crosshairMarkerRadius: 4,
      crosshairMarkerBackgroundColor: "#209dd7",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          chart.applyOptions({ width, height });
        }
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Fetch historical data from backend when ticker changes
  useEffect(() => {
    if (!seriesRef.current || !ticker) return;

    setLoadingHistory(true);
    seriesRef.current.setData([]);

    getTickerHistory(ticker)
      .then(({ data }) => {
        if (!seriesRef.current) return;
        const chartData: LineData[] = data.map((d) => ({
          time: d.time as Time,
          value: d.value,
        }));
        seriesRef.current.setData(chartData);
        chartRef.current?.timeScale().fitContent();
      })
      .catch(() => {
        // Fall back to live-only mode on error
      })
      .finally(() => setLoadingHistory(false));
  }, [ticker]);

  // Append the latest live price as a new bar
  useEffect(() => {
    if (!seriesRef.current || !ticker) return;
    const history = getHistory(ticker);
    if (history.length === 0) return;

    const now = Math.floor(Date.now() / 1000);
    seriesRef.current.update({
      time: now as Time,
      value: history[history.length - 1],
    });
  });

  if (!ticker) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-sm">
        Select a ticker from the watchlist
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2">
        <h2 className="text-xs font-bold text-text-secondary uppercase tracking-wider">
          {ticker} — Price Chart
        </h2>
        {loadingHistory && (
          <span className="text-xs text-text-muted animate-pulse">cargando...</span>
        )}
      </div>
      <div ref={containerRef} className="flex-1 min-h-0" />
    </div>
  );
}
