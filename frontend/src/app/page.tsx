"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Chart } from "@/components/chart";
import { Toolbox } from "@/components/toolbox";
import { ZonePanel } from "@/components/zone-panel";
import { fetchConfig, fetchDrawing } from "@/lib/api";
import {
  DEFAULT_IMBALANCE,
  DEFAULT_PARAMS,
  type Candle,
  type DetectorId,
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
  // Supply and demand is top-down: the zone belongs to the higher timeframe,
  // the entry to the lower. Off by default so the chart starts uncluttered.
  const [htf, setHtf] = useState<string>("off");
  // Brokers do not all start their day at UTC midnight. Getting this wrong puts
  // every H4 and D1 zone one candle away from the terminal's own.
  const [sessionOffset, setSessionOffset] = useState("0");
  const [refine, setRefine] = useState(false);
  // Supply and demand only, by default. The other two are measured and real,
  // but three detectors at once is a chart nobody can read, and picking what to
  // look at is the user's call rather than ours.
  const [detectors, setDetectors] = useState<DetectorId[]>(["supply_demand"]);
  const [params, setParams] = useState<SupplyDemandParams>(DEFAULT_PARAMS);
  // Kept as the raw field text so "" stays distinct from 0. Empty means no
  // account was given, and the backend then returns no position size rather
  // than sizing against an account it invented.
  const [equity, setEquity] = useState("");

  const [data, setData] = useState<DrawResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hovered, setHovered] = useState<Candle | null>(null);

  const inflight = useRef<AbortController | null>(null);

  // Live refresh. A counter rather than a timestamp, because a timestamp in the
  // dependency array re-fires on every render.
  const [live, setLive] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!live) return;
    // ponytail: a fixed 30s poll, not a WebSocket and not a cadence derived
    // from the timeframe. Polling faster than the bar length only re-fetches a
    // bar that is still forming, and the engine already marks a zone built on
    // the newest run as unconfirmed. Move to a stream when someone needs
    // sub-bar latency, which is a different product than this one.
    // `window.` is load-bearing: the chart's timeframe state is called
    // `interval`, so its setter is `setInterval` and it shadows the global.
    const timer = window.setInterval(() => setTick((n) => n + 1), 30_000);
    return () => window.clearInterval(timer);
  }, [live]);

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
        detectors,
        imbalance: DEFAULT_IMBALANCE,
        htf: htf === "off" ? null : htf,
        // Anything not a positive number is "no account". The backend rejects
        // 0 outright, so a half-typed field must not reach it.
        equity: Number(equity) > 0 ? Number(equity) : null,
        refine,
        session_offset_hours: Number(sessionOffset),
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
  }, [symbol, interval, bars, provider, htf, refine, sessionOffset, params, detectors, equity, tick]);

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
  // Hoisted out of the JSX for the same reason as `patchParams`: an inline
  // arrow is a new prop on every render, which is all it takes to defeat the
  // memo on Toolbox that the crosshair makes worth having.
  const resetParams = useCallback(() => setParams(DEFAULT_PARAMS), []);

  const allIntervals = config?.intervals ?? [];
  const candles = data?.candles ?? [];
  const zones = data?.drawing.zones ?? [];
  const last = candles.at(-1) ?? null;
  const readout = hovered ?? last;

  return (
    <div
      data-workstation
      className="flex min-h-dvh flex-col bg-bg lg:h-dvh lg:min-h-0 lg:overflow-hidden"
    >
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

        <div className="flex border border-line-strong" role="group" aria-label="Detectors">
          {(
            [
              ["supply_demand", "S&D"],
              ["fvg", "FVG"],
              ["order_block", "OB"],
            ] as [DetectorId, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() =>
                setDetectors((prev) =>
                  prev.includes(id)
                    ? // Never leave the chart with nothing selected: an empty
                      // drawing is indistinguishable from a broken one.
                      prev.length > 1
                      ? prev.filter((d) => d !== id)
                      : prev
                    : [...prev, id],
                )
              }
              aria-pressed={detectors.includes(id)}
              className={`num px-2 py-1 text-[11px] transition-colors ${
                detectors.includes(id)
                  ? "bg-accent/15 text-accent"
                  : "text-text-faint hover:text-text-dim"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <button
          onClick={() => setLive((v) => !v)}
          aria-pressed={live}
          title="Muat ulang tiap 30 detik"
          className={`num flex items-center gap-1.5 border px-2 py-1 text-[11px] uppercase tracking-wider transition-colors ${
            live
              ? "border-accent text-accent"
              : "border-line-strong text-text-faint hover:text-text-dim"
          }`}
        >
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${
              live ? "bg-accent" : "bg-text-faint"
            }`}
          />
          Live
        </button>

        {/* The handbook also sits under the toolbox, which is the panel it
            explains, but that is the far end of a scroll through the twelve
            sliders that are the reason to open it. */}
        <Link
          href="/docs"
          className="num border border-line-strong px-2 py-1 text-[11px] uppercase tracking-wider text-text-faint transition-colors hover:border-accent hover:text-accent"
        >
          Panduan
        </Link>

        <Picker
          label="HTF"
          value={htf}
          onChange={setHtf}
          options={[
            "off",
            // Only genuinely higher timeframes; anything at or below the
            // chart's own would aggregate to nothing.
            ...(config?.intervals ?? []).filter(
              (id) => allIntervals.indexOf(id) > allIntervals.indexOf(interval),
            ),
          ]}
        />

        {htf !== "off" ? (
          <>
            <Picker
              label="Session"
              value={sessionOffset}
              onChange={setSessionOffset}
              options={["0", "-2", "1", "2", "3"]}
            />
            {/* Only offered with HTF on, because there is no lower timeframe to
                refine from otherwise. Measured: it halves the stop and costs
                4 to 10 points of survival, so it is a choice, not a default. */}
            <Picker
              label="Refine"
              value={refine ? "on" : "off"}
              onChange={(v) => setRefine(v === "on")}
              options={["off", "on"]}
            />
          </>
        ) : null}

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
        <aside className="order-2 h-[70dvh] shrink-0 border-t border-line bg-panel lg:order-1 lg:h-auto lg:w-[276px] lg:border-r lg:border-t-0">
          <Toolbox
            params={params}
            onChange={patchParams}
            onReset={resetParams}
            stats={data?.meta.supply_demand}
            htfStats={data?.meta.htf}
            detectors={detectors}
            config={config}
          />
        </aside>

        {/* The chart is the product. On a phone it gets most of the fold and
            the panels stack under it; on a desk it fills the middle column.

            `relative` here and `absolute inset-0` below is load-bearing, not
            decoration. A percentage height resolves against a parent with a
            definite height, and this parent's height comes from `flex-1`, so
            `h-full` on the canvas host collapsed to nothing and the chart
            rendered as a bare time axis. An absolutely positioned box has a
            definite height by construction. */}
        <main className="relative order-1 min-h-[58dvh] flex-1 lg:order-2 lg:min-h-0">
          <div className="absolute inset-0">
            {candles.length > 0 ? (
              <Chart
                candles={candles}
                zones={zones}
                interval={interval}
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
          </div>
        </main>

        <aside className="order-3 h-[70dvh] shrink-0 border-t border-line bg-panel lg:h-auto lg:w-[300px] lg:border-l lg:border-t-0">
          <ZonePanel
            zones={zones}
            selectedId={selectedId}
            onSelect={setSelectedId}
            lastPrice={last?.close ?? null}
            chartInterval={interval}
            plans={data?.plans ?? []}
            advice={data?.advice ?? []}
            equity={equity}
            onEquity={setEquity}
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
