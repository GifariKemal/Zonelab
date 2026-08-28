"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Chart } from "@/components/chart";
import { Toolbox } from "@/components/toolbox";
import { ChecklistPanel } from "@/components/checklist-panel";
import { LiquidityPanel } from "@/components/liquidity-panel";
import { PoskoPanel } from "@/components/posko-panel";
import { ZonePanel } from "@/components/zone-panel";
import {
  fetchAccount,
  fetchConfig,
  fetchDrawing,
  fetchForming,
  saveSnapshot,
} from "@/lib/api";
import { CLOCK_ZONES, type ClockZone } from "@/lib/clock";
import { priceDecimals } from "@/lib/price";
import {
  DEFAULT_LAYERS,
  DEFAULT_LAYER_PARAMS,
  type Candle,
  type DrawResponse,
  type LayerParams,
  type ServerConfig,
} from "@/lib/types";

// Long enough that dragging a slider is one request, short enough that the
// chart still feels attached to the control. Free data tiers are metered.
const DEBOUNCE_MS = 280;

const SOURCE_NOTE: Record<string, string> = {
  mt5: "Your local MetaTrader 5 terminal: the broker's own tape, spot CFD, with its real per-bar spread. This is the venue your orders actually fill on, and it is not COMEX - the contract months, the basis and the daily break all differ.",
  yahoo:
    "Yahoo serves the COMEX/NYMEX front-month contract - GC=F for gold, SI=F silver, PL=F platinum, PA=F palladium, HG=F copper. That is the same continuous series TradingView draws as COMEX:GC1!, so this is the source to pick when the divergence read should be the futures complex.",
  binance:
    "Binance serves PAXG/USDT, tokenized gold. It tracks XAU closely and its structure is faithful, but it carries its own premium and trades weekends. Add a Twelve Data key for true spot XAU/USD.",
  dukascopy:
    "Dukascopy spot ticks, bid and ask, so this is the one network source that yields a measured spread. Its own venue, not your broker's.",
};

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
  // Which clock the TIME AXIS is labelled in. UTC by default and deliberately
  // left there: it is what every screenshot, every harness expectation and every
  // number anyone has written down against this chart was read in. The owner
  // trades in WIB and reads sessions in New York, so both are offered - but
  // moving the default silently would move all of that at once.
  const [clock, setClock] = useState<ClockZone>("UTC");
  // EVERY drawing to produce, by name, and the only enable there is. Thirteen
  // things used to be switched on two different ways - five detector ids in a
  // list, and an `enabled` boolean inside each of seven overlays' own params -
  // which is why this file used to hold nine `useState` hooks, nine patch
  // callbacks and every id typed out again in the header.
  //
  // Supply and demand alone by default, and that is measured rather than taste:
  // five detectors alone paint 31.6% of the chart, and past about a third the
  // boxes stop annotating price and become its background.
  const [layers, setLayers] = useState<string[]>(DEFAULT_LAYERS);
  // Every layer's knobs in ONE record, keyed by the name the registry gives
  // each params block. A `DrawRequest` body is then `{ ...params, layers }`.
  const [params, setParams] = useState<LayerParams>(DEFAULT_LAYER_PARAMS);
  // How many drawn zones the price scale is currently hiding. Reported by the
  // chart, because the scale autoscales to the VISIBLE candles and nothing here
  // can predict where it lands.
  const [clipped, setClipped] = useState({ above: 0, below: 0 });
  // Kept as the raw field text so "" stays distinct from 0. Empty means no
  // account was given, and the backend then returns no position size rather
  // than sizing against an account it invented.
  const [equity, setEquity] = useState("");

  // WHERE THE EQUITY NUMBER CAME FROM, which matters as much as the number. A
  // figure read from the terminal and a figure typed by hand size positions
  // identically and mean different things: the first is only as current as the
  // instant it was read, and it moves with every open position. Held as text so
  // the panel can say it rather than imply it.
  const [equityFrom, setEquityFrom] = useState<string | null>(null);

  /** Read the account from the connected terminal, or say why not.
   *
   *  Only offered where it can work. A price feed answers 501 and that is a fact
   *  about the feed, not a failure to hide - so the message is shown as-is.
   *
   *  EQUITY, NOT BALANCE. They diverge by the floating result of whatever is
   *  already open, and sizing on balance in a drawdown sizes UP exactly when it
   *  should size down. The balance is reported beside it so the gap is visible.
   */
  const readAccount = useCallback(async () => {
    try {
      const acc = await fetchAccount(provider);
      setEquity(String(acc.equity));
      const drift = acc.balance - acc.equity;
      setEquityFrom(
        `${acc.provider} at ${new Date(acc.read_at * 1000).toLocaleTimeString()} - ` +
          `equity ${acc.equity.toLocaleString()} ${acc.currency}` +
          (Math.abs(drift) > 0.005
            ? `, balance ${acc.balance.toLocaleString()} (${drift > 0 ? "-" : "+"}${Math.abs(drift).toLocaleString()} floating)`
            : ", flat") +
          `, leverage 1:${acc.leverage}`,
      );
    } catch (cause) {
      setEquityFrom(cause instanceof Error ? cause.message : "Could not read the account.");
    }
  }, [provider]);
  // Empty is the generic per-instrument row, which is what shipped. Naming a
  // profile prices the plan at that venue instead; see the Broker picker.
  const [broker, setBroker] = useState("");

  const [data, setData] = useState<DrawResponse | null>(null);

  // THE AUDIT TRAIL. `snapshotSaid` holds the last outcome as plain text rather
  // than a modal, because taking a snapshot must not interrupt reading a chart -
  // and because the one thing worth reading back is short: the id, and how far
  // behind the tape the record was.
  const [snapshotNote, setSnapshotNote] = useState("");
  const [snapshotSaid, setSnapshotSaid] = useState<string | null>(null);
  const [snapshotBusy, setSnapshotBusy] = useState(false);

  /** Write down exactly what is on screen, with the note beside it.
   *
   *  `data` IS THE STATE, posted back untouched. Nothing is redrawn and nothing
   *  is recomputed here, because the value of the record is that it is the same
   *  body this page is rendering - a refetched snapshot would be of a chart
   *  nobody looked at.
   *
   *  No rule is attached from this button. A deduction needs a nominated draw on
   *  liquidity, and nominating it is a judgement the reader makes deliberately,
   *  not a side effect of pressing save. `/api/snapshot` takes `deduce` and
   *  `draw` for the shadow-trading harness, which is where a pre-registered rule
   *  belongs. */
  const takeSnapshot = useCallback(async () => {
    if (!data) return;
    setSnapshotBusy(true);
    try {
      const saved = await saveSnapshot(data, snapshotNote);
      const behind = saved.lag.total_seconds;
      setSnapshotSaid(
        `Saved ${saved.id} - ${saved.objects} objects, ${saved.plans} plans. ` +
          (behind === 0
            ? `Feed healthy: ${saved.lag.intra_bar_seconds}s into the forming bar, nothing overdue.`
            : `Behind the tape by ${behind}s (${saved.lag.overdue_seconds}s overdue, ${saved.lag.screen_seconds}s on screen).`),
      );
      setSnapshotNote("");
    } catch (cause) {
      setSnapshotSaid(cause instanceof Error ? cause.message : "Snapshot failed.");
    } finally {
      setSnapshotBusy(false);
    }
  }, [data, snapshotNote]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hovered, setHovered] = useState<Candle | null>(null);

  const inflight = useRef<AbortController | null>(null);

  // Live refresh. A counter rather than a timestamp, because a timestamp in the
  // dependency array re-fires on every render.
  const [live, setLive] = useState(false);
  const [tick, setTick] = useState(0);
  // Kept OUT of `candles`. It is drawn and never measured - see the Chart prop.
  //
  // Stamped with WHAT IT IS A BAR OF, not stored bare. A candle outlives the
  // request that fetched it, so switching instrument or timeframe while live is
  // off and then switching live on would paint the previous symbol's bar onto
  // this symbol's chart for the second before the next poll lands. Real prices
  // under the wrong name is the failure this codebase refuses everywhere else.
  const [forming, setForming] = useState<{ key: string; candle: Candle | null } | null>(
    null,
  );

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

  // THE SOURCE FOLLOWS THE SYMBOL, because not every source carries every one.
  //
  // The default moved to Binance on 2026-08-19 - it is the only keyless source
  // here whose gold tracks spot, 1.50 from a spot reference against 51.10 for
  // Yahoo's COMEX futures - and Binance carries exactly three of the fifteen
  // symbols: XAUUSD, BTCUSD and ETHUSD. Picking COPPER left the pair impossible
  // and every draw came back 502. Twelve of fifteen symbols broke that way.
  //
  // DERIVED, not synced. Writing the corrected id back into state with an effect
  // is the same fact stored twice, costs a second render, and eslint's
  // set-state-in-effect refuses it for good reason. `provider` stays the user's
  // choice and this is the one actually used - and it is what the picker
  // displays, so the label can never name a source the request did not use.
  //
  // Order comes from `/api/config`, so the preference is the backend's to state,
  // and `available` is honoured - which is why dukascopy now has a real probe.
  // It reported itself up while every tick file answered 429, and this would have
  // walked straight into it.
  const usable = useMemo(() => {
    const carriers = config?.symbols.find((s) => s.id === symbol)?.providers;
    if (!config || !carriers) return provider;
    // BOTH conditions, not just the first. The old test was `carriers.includes`
    // alone, so a source that carried the symbol was kept even when it had
    // probed DOWN - the comment above claimed `available` was honoured and the
    // early return skipped it. Nothing hit it while the default was binance,
    // which is always up. The default is now the local MT5 terminal, which is
    // down whenever it is simply not running, so the hole became the first
    // thing a machine without one would meet.
    const chosen = config.providers.find((p) => p.id === provider);
    if (chosen?.available && carriers.includes(provider)) return provider;
    return (
      config.providers.find(
        (p) => p.available && p.id !== "synthetic" && carriers.includes(p.id),
      )?.id ?? provider
    );
  }, [config, symbol, provider]);

  // THE MOVING CANDLE, on its own clock and its own endpoint.
  //
  // 1 second here against the 30 above, and the gap is the point: `/api/forming`
  // returns ONE candle and runs no detector, while the live poll redraws
  // everything. Merging the two would recompute every zone against a bar that
  // has not closed, which is the exact thing `drop_forming` was written to stop
  // - measured, 42 zone states changed and changed back inside one bar.
  //
  // Cheap only because the source is local. The backend refuses to poll a
  // metered upstream this hard: `get_forming` serves anything without
  // `local = True` from the ordinary cache window, so pointing this at yahoo
  // re-reads the same candle rather than spending someone's daily quota.
  //
  // BELOW `usable` and not beside the other live effect, because it reads it:
  // a const declared later is in the temporal dead zone when the dependency
  // array is evaluated, and that throws at render rather than misbehaving.
  //
  // Turning live OFF clears nothing. `setForming(null)` here would be a
  // synchronous setState inside an effect, which eslint refuses and which the
  // provider memo above already argues against: state that can be derived is
  // derived. `formingNow` below is that derivation, and it is what the chart
  // sees - so switching live off stops the candle being drawn without a second
  // render and without a second copy of the same fact.
  const formingKey = `${usable}:${symbol}:${interval}`;

  useEffect(() => {
    if (!live) return;
    let alive = true;
    const controller = new AbortController();
    const poll = () =>
      fetchForming({ symbol, interval, provider: usable, signal: controller.signal })
        .then((r) => alive && setForming({ key: formingKey, candle: r.candle }))
        // Silent BY DESIGN. This fires once a second; surfacing a transient
        // failure in the error banner would bury the drawing's own message
        // under a flicker the user can do nothing about. The draw poll is what
        // reports a source that is genuinely down.
        .catch(() => {});
    poll();
    const timer = window.setInterval(poll, 1_000);
    return () => {
      alive = false;
      controller.abort();
      window.clearInterval(timer);
    };
  }, [live, symbol, interval, usable, formingKey]);

  // Drawn only while live is on AND only when the candle belongs to what is on
  // screen right now. Both halves are the guard, not one.
  const formingNow =
    live && forming?.key === formingKey ? (forming.candle ?? null) : null;

  useEffect(() => {
    const timer = setTimeout(() => {
      inflight.current?.abort();
      const controller = new AbortController();
      inflight.current = controller;
      setLoading(true);

      fetchDrawing({
        ...params,
        symbol,
        interval,
        bars,
        provider: usable,
        layers,
        htf: htf === "off" ? null : htf,
        // Anything not a positive number is "no account". The backend rejects
        // 0 outright, so a half-typed field must not reach it.
        equity: Number(equity) > 0 ? Number(equity) : null,
        broker,
        refine,
        session_offset_hours: Number(sessionOffset),
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
  }, [symbol, interval, bars, usable, htf, refine, sessionOffset, params, layers, equity, broker, tick]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ONE patch callback where there were nine. Hoisted out of the JSX because an
  // inline arrow is a new prop on every render, which is all it takes to defeat
  // the memo on Toolbox that the crosshair makes worth having.
  const patchParams = useCallback(
    <K extends keyof LayerParams>(key: K, patch: Partial<LayerParams[K]>) =>
      setParams((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } })),
    [],
  );
  const resetParams = useCallback(() => setParams(DEFAULT_LAYER_PARAMS), []);

  /** A preset lands as ONE state change over both, not two.
   *
   *  Setting layers and params separately would render once with the new layers
   *  and the old params - and for a preset like Clock, that intermediate frame is
   *  a request for the cycle grid with no degrees, which draws nothing and shows
   *  the reader an empty chart on the way to a full one. React batches these, so
   *  one handler is also one fetch rather than two. */
  const applyPresetToState = useCallback(
    (nextLayers: string[], nextParams: LayerParams) => {
      setLayers(nextLayers);
      setParams(nextParams);
    },
    [],
  );

  const allIntervals = config?.intervals ?? [];
  const candles = data?.candles ?? [];
  // The SAME count the price axis uses, from the same function. The readout and
  // the axis describe one candle, and the header saying 4489.62 beside an axis
  // saying 4489.621 is the app quoting two prices for it.
  const decimals = priceDecimals(candles);
  const zones = data?.drawing.zones ?? [];
  const swings = data?.drawing.swings ?? [];
  const events = data?.drawing.structure ?? [];
  const last = candles.at(-1) ?? null;
  const readout = hovered ?? last;
  const hidden = clipped.above + clipped.below;

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
          {/* Read off the server's registry rather than typed here. The subtitle
              said "Supply and demand" for as long as that was the only detector,
              and went on saying it after four more shipped alongside a structure
              overlay - a header that names one fifth of the engine. Counting the
              registry is the one version of this line that cannot go stale the
              next time a layer lands. */}
          <span className="text-[10px] uppercase tracking-[0.16em] text-text-faint">
            {config
              ? `${layers.length} of ${config.layers.length} layers on`
              : "Layers"}
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
          value={usable}
          onChange={setProvider}
          options={(config?.providers ?? [])
            .filter((p) => p.available)
            .map((p) => p.id)}
        />
        <Picker
          label="Bars"
          value={String(bars)}
          onChange={(v) => setBars(Number(v))}
          // 1000 was the ceiling because binance hard-caps a page there. The
          // local terminal has no such wall - 99,999 bars in 0.01s - so the
          // top two are reachable on mt5 and clip to whatever a network source
          // can actually serve on the others.
          options={["200", "500", "1000", "2000", "5000"]}
        />
        {/* WHICH VENUE THE PLAN IS PRICED AT, and until 2026-08-20 there was no
            way to say. The engine has had researched broker profiles all along
            and only the measurement harness could reach them, so every plan on
            screen was charged the generic row - a Dukascopy spread and a
            commission the table's own comment calls unverified - while the
            orders would fill somewhere else. Measured through this picker on
            XAUUSD: the overnight carry goes from 1.00bp to 5.74bp on a long,
            because the generic row has no equivalent of Exness's 4.545bp
            per-night administration fee. "generic" is the empty pick. */}
        {config?.brokers?.length ? (
          <Picker
            label="Broker"
            value={broker || "generic"}
            onChange={(v) => setBroker(v === "generic" ? "" : v)}
            options={["generic", ...config.brokers]}
          />
        ) : null}

        {/* The five-detector strip and the separate Structure button that used
            to sit here are GONE. They were two controls for one idea - "draw
            this" - shaped differently because the request had two fields, and
            they hardcoded five ids the header had no business knowing. Every
            drawing is now switched in the one menu in the left panel, which
            builds itself from the server's registry. */}

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

        {/* THE AUDIT BUTTON. Disabled until there is something to record, because
            a snapshot of a failed draw is a snapshot of an error message. The
            note is optional and inline rather than behind a dialog: a dialog
            would make the act of recording cost more attention than reading the
            chart, and then it would not get used. */}
        <input
          type="text"
          value={snapshotNote}
          onChange={(e) => setSnapshotNote(e.target.value)}
          placeholder="note for the record"
          aria-label="Snapshot note"
          className="num w-40 border border-line-strong bg-transparent px-2 py-1 text-[11px] text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
        />
        <button
          type="button"
          onClick={takeSnapshot}
          disabled={!data || snapshotBusy}
          className="num border border-line-strong px-2 py-1 text-[11px] uppercase tracking-wider text-text-faint transition-colors hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
        >
          {snapshotBusy ? "Saving" : "Snapshot"}
        </button>

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

        {/* LAST of the selects on purpose. `e2e/sweep.mjs` reaches four of them
            by index and says so in its own comment: inserting a control above
            silently shifts every `nth()` there, and an assertion that quietly
            starts driving the wrong picker still passes. */}
        <Picker
          label="Clock"
          value={clock}
          onChange={(v) => setClock(v as ClockZone)}
          options={[...CLOCK_ZONES]}
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
                    {readout[key].toFixed(decimals)}
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

      {/* WHAT THE SNAPSHOT RECORDED, said out loud. A save that reports nothing
          is a save nobody can trust: the whole point of the file is that it can
          be audited later, and the first thing an auditor needs is confidence it
          was written at all. Dismissable, because it is a receipt and not a
          warning - and it names the LAG rather than only the id, because that is
          the number a review weeks from now will actually want. */}
      {snapshotSaid ? (
        <p
          role="status"
          className="shrink-0 border-b border-line-strong bg-panel-2 px-4 py-1 text-[11px] text-text-dim"
        >
          {snapshotSaid}{" "}
          <button
            type="button"
            onClick={() => setSnapshotSaid(null)}
            className="ml-2 uppercase tracking-wider text-text-faint transition-colors hover:text-accent"
          >
            dismiss
          </button>
        </p>
      ) : null}

      {/* A PROVIDER THAT GAVE LESS THAN IT WAS ASKED FOR, said out loud.
          `truncated_by_provider` has been on every response since the field
          existed and was declared in `types.ts`, and nothing ever rendered it -
          so a source that could only supply 400 of the 1000 bars requested drew
          a shorter chart and looked exactly like a quiet market. The counts
          matter more than the flag: "400 of 1000" tells the reader whether a
          missing zone is missing because the formation is not there or because
          the history is not. */}
      {data?.meta?.truncated_by_provider ? (
        <p
          role="status"
          className="shrink-0 border-b border-accent/40 bg-accent/10 px-4 py-1 text-[11px] text-accent"
        >
          {data.provider} returned {data.meta.bars_returned} of the{" "}
          {data.meta.bars_requested} bars requested, so the window is shorter
          than asked. Anything measured over a longer lookback than that is
          measured over history this source does not have.
        </p>
      ) : null}

      {/* A zone the price scale hides is a zone the instrument reported and then
          concealed, and this is the THIRD time in this project that the drawing
          was right and the presentation lied - after borders buried under their
          own candles and left edges anchored to bar centres. A vision audit found
          six zones reported and one drawn on XAUUSD 1h: the axis bottomed out at
          4360.00 while the zones ran down to 4184.30.

          Said rather than fixed by rescaling, on purpose. Extending the range to
          swallow a zone 4% away halves the height the candles get, and this
          project measures ink coverage precisely because a chart that fits
          everything reads nothing. It would also move the geometry every pixel
          measurement in `e2e/` was taken against. So the scale keeps following
          the candles and the reader is told what is off it, in which direction,
          and can scroll or zoom out to go and look. */}
      {hidden > 0 ? (
        <p
          role="status"
          className="shrink-0 border-b border-accent/40 bg-accent/10 px-4 py-1 text-[11px] text-accent"
        >
          {hidden} of {zones.length} drawn{" "}
          {zones.length === 1 ? "zone is" : "zones are"} outside the price range
          on screen
          {clipped.above > 0 && clipped.below > 0
            ? ` (${clipped.above} above, ${clipped.below} below)`
            : clipped.above > 0
              ? " (above it)"
              : " (below it)"}
          . The scale follows the candles, not the zones - zoom out or scroll the
          price axis to reach them. They are all listed in the panel on the right.
        </p>
      ) : null}

      {/* WHICH VENUE, said out loud. One symbol id maps onto a different
          instrument per source - XAUUSD is a COMEX futures contract on yahoo, a
          broker spot CFD on mt5 and a tokenized token on binance - and the
          three do not print the same highs, the same session or the same gaps.
          A zone read from one and traded on another is the quiet kind of wrong,
          so the source picker gets a caption rather than a footnote. */}
      {SOURCE_NOTE[usable] ? (
        <p className="shrink-0 border-b border-line bg-panel px-4 py-1 text-[11px] text-text-faint">
          {SOURCE_NOTE[usable]}
        </p>
      ) : null}

      {/* TWO PANEL WIDTHS, not one. At the `lg` breakpoint itself - 1024px, which
          is an older laptop and every projector - the two panels at their full
          276 and 300 left the chart pane 374px wide, so the instrument got 36%
          of the window and its two annotations got the rest. Measured by
          `e2e/viewports.mjs`, which is also the reason this was found at all:
          every other harness in that directory opens 1680x1000 and nothing
          else. Narrower until `xl`, which puts the pane back over 470px there
          and leaves the roomy case untouched. */}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <aside className="order-2 h-[70dvh] shrink-0 border-t border-line bg-panel lg:order-1 lg:h-auto lg:w-[232px] lg:border-r lg:border-t-0 xl:w-[276px]">
          {/* Eight props where there were twenty-eight. The panel is driven by
              `config.layers` and one keyed params record, so a new layer needs
              nothing here. */}
          <Toolbox
            config={config}
            layers={layers}
            onLayers={setLayers}
            params={params}
            onParams={patchParams}
            onReset={resetParams}
            onPreset={applyPresetToState}
            meta={data?.meta}
            symbol={symbol}
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
                forming={formingNow}
                zones={zones}
                swings={swings}
                structure={events}
                fibonacci={data?.drawing.fibonacci ?? null}
                quarters={data?.drawing.quarters ?? []}
                trueOpens={data?.drawing.true_opens ?? []}
                vortex={data?.drawing.vortex ?? null}
                ssmt={data?.drawing.ssmt ?? []}
                smt={data?.drawing.smt ?? []}
                dfr={data?.drawing.dfr ?? []}
                dfrEquilibrium={params.dfr.equilibrium}
                gaps={data?.drawing.gaps ?? []}
                eventHorizons={data?.drawing.event_horizons ?? []}
                pools={data?.drawing.pools ?? []}
                cisd={data?.drawing.cisd ?? []}
                namedLevels={data?.drawing.levels ?? []}
                projections={data?.drawing.projections ?? []}
                tierHorizons={data?.drawing.tier_horizons ?? []}
                gapStacks={data?.drawing.gap_stacks ?? []}
                news={data?.drawing.news ?? []}
                interval={interval}
                zone={clock}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onHover={setHovered}
                onClipped={setClipped}
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

        {/* The checklist sits ABOVE the zone list, which is the order he works
            in: the five questions decide whether to look for an entry at all,
            and the zones are where one would be. It only appears when asked
            for, so the rail is unchanged for anyone not using it. */}
        <aside className="order-3 flex h-[70dvh] shrink-0 flex-col border-t border-line bg-panel lg:h-auto lg:w-[244px] lg:border-l lg:border-t-0 xl:w-[300px]">
          {data?.checklist ? (
            <ChecklistPanel report={data.checklist} stats={data.meta.checklist} />
          ) : null}
          {/* The two liquidity READINGS. They are numbers rather than shapes, so
              they ride here beside the checklist instead of on the chart - and
              until now they rode nowhere at all: both were computed, shipped and
              switchable while being rendered by nothing. */}
          <LiquidityPanel
            range={data?.range_liquidity ?? null}
            draw={data?.draw_on_liquidity ?? null}
          />
          <PoskoPanel
            symbol={symbol}
            interval={interval}
            bars={bars}
            provider={provider}
          />
          <ZonePanel
                clock={clock}
            zones={zones}
            selectedId={selectedId}
            onSelect={setSelectedId}
            lastPrice={last?.close ?? null}
            chartInterval={interval}
            plans={data?.plans ?? []}
            advice={data?.advice ?? []}
            equity={equity}
            onEquity={(value) => {
              // TYPING CLEARS THE PROVENANCE. Once a human has edited the box,
              // the line saying "read from the terminal at 15:07" is a lie about
              // a number that is no longer the terminal's.
              setEquity(value);
              setEquityFrom(null);
            }}
            equityFrom={equityFrom}
            onReadAccount={readAccount}
            canReadAccount={provider === "mt5"}
            clipped={clipped}
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
        // The wrapping `label` already names this, and the crawler in
        // `e2e/click-everything.mjs` cannot see that: it names a control by its
        // `aria-label` and falls back to "select-3". Same text, said where the
        // instrument reads it - the toggles carry it for the same reason.
        aria-label={label}
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
