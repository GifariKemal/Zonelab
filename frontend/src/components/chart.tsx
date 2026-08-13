"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import type { Candle, Zone } from "@/lib/types";
import { ZoneSeriesPrimitive } from "./zone-primitive";

interface Props {
  candles: Candle[];
  zones: Zone[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onHover: (candle: Candle | null) => void;
}

export function Chart({ candles, zones, selectedId, onSelect, onHover }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Candlestick", Time> | null>(null);
  const primitive = useRef<ZoneSeriesPrimitive | null>(null);

  // Handlers are subscribed once for the chart's lifetime, so they read the
  // latest props through refs instead of forcing a chart teardown per render.
  const zonesRef = useRef(zones);
  const candlesRef = useRef(candles);
  const onSelectRef = useRef(onSelect);
  const onHoverRef = useRef(onHover);
  zonesRef.current = zones;
  candlesRef.current = candles;
  onSelectRef.current = onSelect;
  onHoverRef.current = onHover;

  useEffect(() => {
    if (!host.current) return;

    const instance = createChart(host.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#0b0d10" },
        textColor: "#8d99a8",
        fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#141920" },
        horzLines: { color: "#141920" },
      },
      rightPriceScale: {
        borderColor: "#1c222b",
        scaleMargins: { top: 0.08, bottom: 0.08 },
      },
      timeScale: {
        borderColor: "#1c222b",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#3b4653", width: 1, style: 2, labelBackgroundColor: "#2a323e" },
        horzLine: { color: "#3b4653", width: 1, style: 2, labelBackgroundColor: "#2a323e" },
      },
    });

    const candleSeries = instance.addSeries(CandlestickSeries, {
      upColor: "#2ea36f",
      downColor: "#d4574f",
      borderUpColor: "#2ea36f",
      borderDownColor: "#d4574f",
      wickUpColor: "#2ea36f99",
      wickDownColor: "#d4574f99",
    });

    const zonePrimitive = new ZoneSeriesPrimitive();
    candleSeries.attachPrimitive(zonePrimitive);

    instance.subscribeClick((param) => {
      if (!param.point || param.time === undefined) {
        onSelectRef.current(null);
        return;
      }
      const price = candleSeries.coordinateToPrice(param.point.y);
      if (price === null) return;
      const time = param.time as number;

      // Zones stack, so the click must resolve to one. Prefer the tightest box
      // under the cursor: the small zone is the precise level, and the big one
      // stays reachable by clicking where they do not overlap.
      const hits = zonesRef.current
        .filter(
          (z) =>
            time >= z.time_from &&
            time <= z.time_to &&
            price <= z.top &&
            price >= z.bottom,
        )
        .sort((a, b) => a.top - a.bottom - (b.top - b.bottom));

      onSelectRef.current(hits[0]?.id ?? null);
    });

    instance.subscribeCrosshairMove((param) => {
      if (param.time === undefined) {
        onHoverRef.current(null);
        return;
      }
      const time = param.time as number;
      onHoverRef.current(candlesRef.current.find((c) => c.time === time) ?? null);
    });

    chart.current = instance;
    series.current = candleSeries;
    primitive.current = zonePrimitive;

    return () => {
      instance.remove();
      chart.current = null;
      series.current = null;
      primitive.current = null;
    };
  }, []);

  useEffect(() => {
    if (!series.current || candles.length === 0) return;
    series.current.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
  }, [candles]);

  useEffect(() => {
    primitive.current?.setZones(zones);
  }, [zones]);

  useEffect(() => {
    primitive.current?.setSelected(selectedId);
  }, [selectedId]);

  return <div ref={host} className="h-full w-full" />;
}
