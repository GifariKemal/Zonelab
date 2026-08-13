"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Chart } from "@/components/chart";
import { Toolbox } from "@/components/toolbox";
import { ZonePanel } from "@/components/zone-panel";
import { fetchConfig, fetchDrawing } from "@/lib/api";
import {
  DEFAULT_PARAMS,
  type Candle,
  type DrawResponse,
  type ServerConfig,
  type SupplyDemandParams,
} from "@/lib/types";

// Long enough that dragging a slider is one request, short enough that the
// chart still feels attached to the control. Free data tiers are metered.
const DEBOUNCE_MS = 280;

export default function Page() {
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [symbol, setSymbol] = useState("XAUUSD");
  const [interval, setInterval] = useState("15m");
  const [provider, setProvider] = useState("binance");
  const [bars, setBars] = useState(500);
  const [params, setParams] = useState<SupplyDemandParams>(DEFAULT_PARAMS);

  const [data, setData] = useState<DrawResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hovered, setHovered] = useState<Candle | null>(null);

  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchConfig()
      .then((c) => {
        setConfig(c);
        setProvider(c.default_provider);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      inflight.current?.abort();
      const controller = new AbortController();
      inflight.current = controller;
      setLoading(true);

      fetchDrawing({
        symbol,
        interval,
        bars,
        provider,
        supply_demand: params,
        signal: controller.signal,
      })
        .then((response) => {
          setData(response);
          setError(null);
        })
        .catch((e: Error) => {
          if (e.name === "AbortError") return;
          setError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [symbol, interval, bars, provider, params]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const patchParams = useCallback(
    (patch: Partial<SupplyDemandParams>) =>
      setParams((prev) => ({ ...prev, ...patch })),
    [],
  );

  const candles = data?.candles ?? [];
  const zones = data?.drawing.zones ?? [];
  const last = candles.at(-1) ?? null;
  const readout = hovered ?? last;

  return (
    <div className="flex h-dvh flex-col bg-bg">
      <header className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-line px-4 py-2">
        <div className="flex items-baseline gap-2">
          <span className="text-[13px] font-semibold tracking-tight text-text">
            Zonelab
          </span>
          <span className="text-[10px] uppercase tracking-[0.16em] text-text-faint">
            Supply and demand
          </span>
        </div>

        <div className="h-4 w-px bg-line" aria-hidden />

        <Picker
          label="Symbol"
          value={symbol}
          onChange={setSymbol}
          options={(config?.symbols ?? [{ id: "XAUUSD", providers: [] }]).map(
            (s) => s.id,
          )}
        />
        <Picker
          label="Source"
          value={provider}
          onChange={setProvider}
          options={(config?.providers ?? [])
            .filter((p) => p.available)
            .map((p) => p.id)}
        />
        <Picker
          label="Bars"
          value={String(bars)}
          onChange={(v) => setBars(Number(v))}
          options={["200", "500", "1000"]}
        />

        <div className="flex border border-line-strong" role="group" aria-label="Timeframe">
          {(config?.intervals ?? ["15m"]).map((id) => (
            <button
              key={id}
              onClick={() => setInterval(id)}
              aria-pressed={interval === id}
              className={`num px-2 py-1 text-[11px] transition-colors ${
                interval === id
                  ? "bg-accent/15 text-accent"
                  : "text-text-faint hover:text-text-dim"
              }`}
            >
              {id}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-4">
          {readout ? (
            <div className="num flex gap-3 text-[11px]">
              {(["open", "high", "low", "close"] as const).map((key) => (
                <span key={key}>
                  <span className="text-text-faint">{key[0].toUpperCase()}</span>{" "}
                  <span
                    className={
                      readout.close >= readout.open ? "text-demand" : "text-supply"
                    }
                  >
                    {readout[key].toFixed(2)}
                  </span>
                </span>
              ))}
            </div>
          ) : null}
          <span
            className="num text-[11px] text-text-faint"
            aria-live="polite"
            role="status"
          >
            {loading ? "loading" : `${candles.length} bars`}
          </span>
        </div>
      </header>

      {error ? (
        <div
          role="alert"
          className="shrink-0 border-b border-supply/40 bg-supply/10 px-4 py-2 text-[12px] text-supply"
        >
          {error}
        </div>
      ) : null}

      {provider === "binance" ? (
        <p className="shrink-0 border-b border-line bg-panel px-4 py-1 text-[11px] text-text-faint">
          Binance serves PAXG/USDT, tokenized gold. It tracks XAU closely and its
          structure is faithful, but it carries its own premium and trades
          weekends. Add a Twelve Data key for true spot XAU/USD.
        </p>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <aside className="order-2 h-64 shrink-0 border-t border-line bg-panel lg:order-1 lg:h-auto lg:w-[276px] lg:border-r lg:border-t-0">
          <Toolbox
            params={params}
            onChange={patchParams}
            onReset={() => setParams(DEFAULT_PARAMS)}
            stats={data?.meta.supply_demand}
            config={config}
          />
        </aside>

        <main className="order-1 min-h-0 flex-1 lg:order-2">
          {candles.length > 0 ? (
            <Chart
              candles={candles}
              zones={zones}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onHover={setHovered}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-[12px] text-text-faint">
                {error ? "No data to chart." : "Loading candles."}
              </p>
            </div>
          )}
        </main>

        <aside className="order-3 h-72 shrink-0 border-t border-line bg-panel lg:h-auto lg:w-[300px] lg:border-l lg:border-t-0">
          <ZonePanel
            zones={zones}
            selectedId={selectedId}
            onSelect={setSelectedId}
            lastPrice={last?.close ?? null}
          />
        </aside>
      </div>
    </div>
  );
}

function Picker({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label className="flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-[0.12em] text-text-faint">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="num border border-line-strong bg-panel px-1.5 py-1 text-[11px] text-text"
      >
        {options.map((id) => (
          <option key={id} value={id}>
            {id}
          </option>
        ))}
      </select>
    </label>
  );
}
