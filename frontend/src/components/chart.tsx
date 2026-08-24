"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  createSeriesMarkers,
  TickMarkType,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import type {
  Candle,
  DefiningRangeBand,
  SSMTDivergence,
  SMTDivergence,
  CISDEvent,
  EventHorizonLevel,
  GapStack,
  LiquidityPool,
  NamedLevel,
  OpeningGap,
  NewsEvent,
  RangeProjection,
  TierHorizon,
  SessionQuarter,
  StructureEvent,
  SwingPoint,
  TrueOpenLevel,
  Zone,
} from "@/lib/types";
import { clockStamp, clockTick, ZONE_TAG, type ClockZone, type TickKind } from "@/lib/clock";
import { priceDecimals } from "@/lib/price";
import { BreakSeriesPrimitive } from "./break-primitive";
import { CycleRibbon } from "./cycle-ribbon";
import { DFRSeriesPrimitive } from "./dfr-primitive";
import { LevelsSeriesPrimitive } from "./levels-primitive";
import { SessionSeriesPrimitive } from "./session-primitive";
import { SSMTSeriesPrimitive } from "./ssmt-primitive";
import { SMTSeriesPrimitive } from "./smt-primitive";
import { claimedLabels, StructureSeriesPrimitive } from "./structure-primitive";
import { ZoneSeriesPrimitive } from "./zone-primitive";

interface Props {
  /** CLOSED bars only. Every measurement in this app was taken on these, and
   *  `lastClose` and the zone proximity budget below read them - so the forming
   *  bar must never be merged into this array. */
  candles: Candle[];
  /** The bar still being built, or null. DRAWN ONLY: it reaches `update()` and
   *  nothing else, so no detector and no proximity read can see it. */
  forming: Candle | null;
  zones: Zone[];
  /** Structure overlay. Empty arrays when it is off, which is the default. */
  swings: SwingPoint[];
  structure: StructureEvent[];
  /** The cycle grid. Empty arrays when no degree was requested, the default. */
  quarters: SessionQuarter[];
  trueOpens: TrueOpenLevel[];
  /** Cross-instrument divergences, already positioned on THIS symbol's price.
   *  Empty unless the ssmt layer is on - the only overlay that costs a provider
   *  call, because a divergence needs a second instrument. */
  ssmt: SSMTDivergence[];
  smt: SMTDivergence[];
  /** Defining ranges with their equilibrium and projections. Empty unless the
   *  dfr layer is on. Single-sourced and unverified, and drawn fainter for it. */
  dfr: DefiningRangeBand[];
  dfrEquilibrium: boolean;
  /** The four price-anchored overlays. Empty arrays when off, which is default. */
  gaps: OpeningGap[];
  eventHorizons: EventHorizonLevel[];
  pools: LiquidityPool[];
  cisd: CISDEvent[];
  namedLevels: NamedLevel[];
  projections: RangeProjection[];
  tierHorizons: TierHorizon[];
  /** Overlaps between two gaps of different kinds. Rides on the gaps layer
   *  rather than a toggle of its own: a stack is two gaps agreeing, so it
   *  cannot exist without them and a second switch would be a switch that only
   *  works when another one is on. */
  gapStacks: GapStack[];
  news: NewsEvent[];
  /** The chart's own timeframe. Zones stamped with anything else came from a
   *  higher timeframe and are drawn heavier. */
  interval: string;
  /** Which clock the TIME AXIS is labelled in. It labels only: the epochs the
   *  series and every primitive receive are untouched UTC, because the ribbon
   *  and both pixel harnesses read coordinates back through this scale. */
  zone: ClockZone;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onHover: (candle: Candle | null) => void;
  /** How many drawn zones fall entirely outside the price range on screen. The
   *  chart is the only thing that knows this, because the price scale autoscales
   *  to the VISIBLE candles and nothing upstream can predict where it lands. */
  onClipped: (clipped: { above: number; below: number }) => void;
}

/** The library's own tick classification, translated to the clock module's
 *  words. It is the library that decides which marks are dates and which are
 *  times, and it decides that on the UTC calendar - see the caveat on
 *  `clockTick`. This map only carries the decision across. */
const TICK_KIND: Record<TickMarkType, TickKind> = {
  [TickMarkType.Year]: "year",
  [TickMarkType.Month]: "month",
  [TickMarkType.DayOfMonth]: "day",
  [TickMarkType.Time]: "time",
  [TickMarkType.TimeWithSeconds]: "seconds",
};

/** Zones the reader cannot see. Counted as fully outside the pane rather than
 *  merely cut off: a box with a sliver on screen is still locatable, a box with
 *  nothing on screen is a zone the instrument reported and then hid.
 *
 *  ponytail: a sliver-thin box whose CAPTION is off-screen is still misread, and
 *  this does not count it. Tighten to "less than N pixels visible" if that turns
 *  out to matter; the whole-box test is the case the audit actually found. */
function countClipped(
  zones: readonly Zone[],
  series: ISeriesApi<"Candlestick", Time>,
  paneHeight: number,
): { above: number; below: number } {
  let above = 0;
  let below = 0;
  for (const zone of zones) {
    // y grows downward, so the box occupies [topY, bottomY].
    const topY = series.priceToCoordinate(zone.top);
    const bottomY = series.priceToCoordinate(zone.bottom);
    if (topY === null || bottomY === null) continue;
    if (bottomY < 0) above++;
    else if (topY > paneHeight) below++;
  }
  return { above, below };
}

/** The zone the pointer is on, or null. Zones stack, so a point on the canvas
 *  has to resolve to ONE of them: prefer the tightest box, because the small
 *  zone is the precise level and the big one stays reachable by pointing where
 *  they do not overlap. Shared by click and hover so the box that lights up
 *  under the cursor is the box a click would open - two hit tests that drift
 *  apart would be a chart that lies about what it is about to do. */
function zoneAt(
  zones: readonly Zone[],
  time: number,
  price: number,
): Zone | null {
  return (
    zones
      .filter(
        (z) => time >= z.time_from && time <= z.time_to && price <= z.top && price >= z.bottom,
      )
      .sort((a, b) => a.top - a.bottom - (b.top - b.bottom))[0] ?? null
  );
}

export function Chart({
  candles,
  forming,
  zones,
  swings,
  structure,
  quarters,
  trueOpens,
  ssmt,
  smt,
  dfr,
  dfrEquilibrium,
  gaps,
  eventHorizons,
  pools,
  cisd,
  namedLevels,
  projections,
  tierHorizons,
  gapStacks,
  news,
  interval,
  zone,
  selectedId,
  onSelect,
  onHover,
  onClipped,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Candlestick", Time> | null>(null);
  const primitive = useRef<ZoneSeriesPrimitive | null>(null);
  const structurePrimitive = useRef<StructureSeriesPrimitive | null>(null);
  const sessionPrimitive = useRef<SessionSeriesPrimitive | null>(null);
  const breakPrimitive = useRef<BreakSeriesPrimitive | null>(null);
  const ssmtPrimitive = useRef<SSMTSeriesPrimitive | null>(null);
  const smtPrimitive = useRef<SMTSeriesPrimitive | null>(null);
  const dfrPrimitive = useRef<DFRSeriesPrimitive | null>(null);
  const levelsPrimitive = useRef<LevelsSeriesPrimitive | null>(null);

  /** Structure on the bar under the crosshair. A bar can carry TWO events - an
   *  MSS is emitted alongside the break it was carved from - so this is a list
   *  and every entry is printed. It also carries `confirmed_at`, which is the
   *  only place a reader can learn when a pivot actually became knowable. */
  // The chart instance in STATE, not just in the ref, purely so the ribbon below
  // can be handed a real time scale. The ref alone cannot do it twice over: it
  // would not re-render when the chart appears, and reading `.current` during
  // render is exactly what React forbids, because a render may be discarded.
  const [chartApi, setChartApi] = useState<IChartApi | null>(null);
  const [atBar, setAtBar] = useState<{
    swings: SwingPoint[];
    events: StructureEvent[];
  } | null>(null);

  // Handlers are subscribed once for the chart's lifetime, so they read the
  // latest props through refs instead of forcing a chart teardown per render.
  const zonesRef = useRef(zones);
  const candlesRef = useRef(candles);
  const swingsRef = useRef(swings);
  const structureRef = useRef(structure);
  const onSelectRef = useRef(onSelect);
  const onHoverRef = useRef(onHover);
  const onClippedRef = useRef(onClipped);
  /** Last reported figure, so a repaint that changes nothing does not push state
   *  back into React and start the paint over. */
  const clippedRef = useRef({ above: -1, below: -1 });

  // Written after commit, never during render. React may discard a render, and
  // a ref assigned in the render body would then hold a value from a pass that
  // never happened. No dependency array: this must run on every commit.
  useEffect(() => {
    zonesRef.current = zones;
    candlesRef.current = candles;
    swingsRef.current = swings;
    structureRef.current = structure;
    onSelectRef.current = onSelect;
    onHoverRef.current = onHover;
    onClippedRef.current = onClipped;
  });

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
        // DENSER THAN THE DEFAULT 2.5, where the number is spacing and not a
        // count: lower means labels sit closer, so more of them fit.
        //
        // 2.0 and not lower, and the number was looked at rather than reasoned
        // about. 1.4 was tried first and screenshotted: on a 950px pane it
        // labelled every 4 dollars, roughly 55 marks running edge to edge with
        // no gap between them at 11px type. Denser stopped meaning more legible
        // somewhere before that, so this backs off to a step that still adds
        // marks over the default without printing a wall of numbers.
        tickMarkDensity: 2.0,
        // The label alone floats beside the scale and has to be traced back to
        // its gridline. The tick ties the two together, which is the whole
        // complaint about reading a price off this axis.
        ticksVisible: true,
        // Without this the top and bottom of the visible range - which is where
        // the extremes of the move are - are the two prices the axis never
        // names.
        ensureEdgeTickMarksVisible: true,
      },
      timeScale: {
        borderColor: "#1c222b",
        timeVisible: true,
        // Bars open on the interval grid, so the seconds are always :00 and
        // saying so costs axis width for no information.
        secondsVisible: false,
        rightOffset: 6,
        ticksVisible: true,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#3b4653", width: 1, style: 2, labelBackgroundColor: "#2a323e" },
        horzLine: { color: "#3b4653", width: 1, style: 2, labelBackgroundColor: "#2a323e" },
      },
    });

    const candleSeries = instance.addSeries(CandlestickSeries, {
      // `--demand` and `--supply` from globals.css, spelled out because the
      // charting library takes strings and not CSS variables. The pair differs
      // in lightness as well as hue so it survives greyscale and a red-green
      // deficiency; globals.css carries the measurement and the list of the
      // five files that must change together. A candle in one red and a zone
      // in another is the failure that list exists to prevent.
      upColor: "#1f8f5f",
      downColor: "#ef8f86",
      borderUpColor: "#1f8f5f",
      borderDownColor: "#ef8f86",
      wickUpColor: "#1f8f5f99",
      wickDownColor: "#ef8f8699",
    });

    // ATTACH ORDER IS LOAD-BEARING. Structure and zone borders both paint at
    // `normal` z-order and the library paints a z-order pass in attach order, so
    // structure first means zone borders and captions land ON TOP of structure
    // ink. `e2e/pixel-truth.mjs` reads those borders back off the bitmap and
    // asserts every one is legible; a grey level line drawn over a border would
    // break that, and in a colour the probe's own side test cannot even see.
    // The session grid goes FIRST and paints at `bottom`, beneath the candles.
    // It is context about the clock, not a reading of price, so a quarter
    // divider crossing a zone border must lose: the border's position is
    // verified to the pixel and the divider's is not load-bearing.
    // Then the price-anchored levels, between the grid and structure: they are
    // prices to compare candles against, so they must clear the grid's context
    // wash, but a zone border still wins over them for the reason above.
    // FIRST OF ALL, and always on. The session breaks are the only thing here
    // that describes the X AXIS rather than a price, and this axis is indexed by
    // bar - so without them Friday's candle sits flush against Sunday's and a
    // 49-hour weekend leaves no mark at all. Everything else in this list is a
    // layer the user switches on; a chart that hides a weekend is misreporting
    // itself, so this one is not optional.
    const breakPrim = new BreakSeriesPrimitive();
    candleSeries.attachPrimitive(breakPrim);
    // SESSION FIRST, and this order is load-bearing rather than tidy: the grid
    // pass is where `resetLabels` runs, so any pass that claims a label before
    // it has that claim thrown away and is then overprinted by every later
    // pass. DFR was attached above this line for exactly one commit and its
    // projection tags were invisible to the collision map the whole time.
    // `resetLabels` now says so out loud in development.
    const sessionPrim = new SessionSeriesPrimitive();
    candleSeries.attachPrimitive(sessionPrim);
    // With the cycle grid, at `bottom`: a defining range is a window of the
    // clock's own Q1, so it is context the candles sit on.
    const dfrPrim = new DFRSeriesPrimitive();
    candleSeries.attachPrimitive(dfrPrim);
    const levelsPrim = new LevelsSeriesPrimitive();
    candleSeries.attachPrimitive(levelsPrim);
    // After the levels and before structure: a divergence is a reading to
    // compare candles against, like a level, and a zone border still wins.
    const ssmtPrim = new SSMTSeriesPrimitive();
    candleSeries.attachPrimitive(ssmtPrim);
    const smtPrim = new SMTSeriesPrimitive();
    candleSeries.attachPrimitive(smtPrim);
    const structurePrim = new StructureSeriesPrimitive();
    candleSeries.attachPrimitive(structurePrim);
    const zonePrimitive = new ZoneSeriesPrimitive();
    candleSeries.attachPrimitive(zonePrimitive);

    /** How many zones the price scale is currently hiding.
     *
     *  Recomputed from the chart rather than derived upstream, because the price
     *  scale autoscales to the candles that are VISIBLE - not to the series that
     *  was fetched - so the answer changes on every pan and zoom and nothing
     *  outside this component can know it. A vision audit found six zones
     *  reported and one drawn on XAUUSD 1h: the axis bottomed out at 4360 while
     *  the zones ran down to 4184.3. Both pixel harnesses were structurally
     *  blind to it, because both only measure zones the canvas CONTAINS. */
    const reportClipped = () => {
      if (!series.current || !chart.current) return;
      const next = countClipped(
        zonesRef.current,
        series.current,
        chart.current.paneSize().height,
      );
      if (next.above === clippedRef.current.above && next.below === clippedRef.current.below) {
        return;
      }
      clippedRef.current = next;
      onClippedRef.current(next);
    };

    instance.subscribeClick((param) => {
      if (!param.point || param.time === undefined) {
        onSelectRef.current(null);
        return;
      }
      const price = candleSeries.coordinateToPrice(param.point.y);
      if (price === null) return;
      onSelectRef.current(zoneAt(zonesRef.current, param.time as number, price)?.id ?? null);
    });

    instance.subscribeCrosshairMove((param) => {
      if (param.time === undefined) {
        onHoverRef.current(null);
        zonePrimitive.setHovered(null);
        setAtBar(null);
        return;
      }
      const time = param.time as number;
      onHoverRef.current(candlesRef.current.find((c) => c.time === time) ?? null);

      // Pointing at a box is how a reader asks for the one that lost its fill
      // and its caption to the ink budget: it comes back to full opacity and
      // gets named. Opacity and text only - this is an instrument, and a box
      // that moves or grows under the cursor would be a box the reader cannot
      // trust to be where it says it is.
      const price = param.point ? candleSeries.coordinateToPrice(param.point.y) : null;
      zonePrimitive.setHovered(
        price === null ? null : (zoneAt(zonesRef.current, time, price)?.id ?? null),
      );

      const hitSwings = swingsRef.current.filter((s) => s.time === time);
      const hitEvents = structureRef.current.filter((e) => e.time === time);
      setAtBar(hitSwings.length || hitEvents.length ? { swings: hitSwings, events: hitEvents } : null);

      // Dragging the PRICE axis rescales without touching the time range, so no
      // range event fires for it. The mouse has to move to drag, so this covers
      // the case the subscription below cannot.
      reportClipped();
    });

    // Fires on new data, pan and zoom - every way the autoscaled price range can
    // move on its own.
    instance.timeScale().subscribeVisibleLogicalRangeChange(reportClipped);

    chart.current = instance;
    setChartApi(instance);
    series.current = candleSeries;
    primitive.current = zonePrimitive;
    structurePrimitive.current = structurePrim;
    sessionPrimitive.current = sessionPrim;
    breakPrimitive.current = breakPrim;
    ssmtPrimitive.current = ssmtPrim;
    smtPrimitive.current = smtPrim;
    dfrPrimitive.current = dfrPrim;
    levelsPrimitive.current = levelsPrim;

    if (process.env.NODE_ENV !== "production") {
      // Test seam. The zone audit drives the visible range to frame one
      // formation at a time so its edges can be checked against the candles
      // that produced them. Reaching that through UI gestures would be far
      // more code than exposing the handle a driver already needs.
      //
      // `markBars` is what makes the audit answerable by eye rather than by
      // guesswork: without seeing WHICH candles the engine called the base, a
      // reviewer can only judge whether the box looks plausible, not whether
      // the classification behind it was right.
      //
      // `visiblePriceRange` is the seam for the defect above: it lets a driver
      // ask what the axis actually spans, which is the one question both pixel
      // harnesses cannot express. See `e2e/offscreen-zones.mjs`.
      const markers = createSeriesMarkers(candleSeries, []);
      (window as unknown as Record<string, unknown>).__zonelabChart = {
        chart: instance,
        series: candleSeries,
        visiblePriceRange: () => ({
          top: candleSeries.coordinateToPrice(0),
          bottom: candleSeries.coordinateToPrice(instance.paneSize().height),
          height: instance.paneSize().height,
        }),
        // Every caption any primitive placed on the last painted frame, in
        // PANE pixels. The shared claim list is the mechanism that keeps text
        // off other text - each primitive asks `labelFree` before it draws and
        // drops the word rather than overprinting - and until this seam existed
        // there was no way to check the mechanism actually held. A screenshot
        // shows two words touching only if a human looks at the right corner of
        // the right frame; this makes it arithmetic. See `e2e/labels.mjs`.
        labels: () => claimedLabels.map((r) => ({ ...r })),
        markBars: (marks: { time: number; text: string; color: string }[]) =>
          markers.setMarkers(
            marks.map((m) => ({
              time: m.time as UTCTimestamp,
              position: "belowBar" as const,
              shape: "arrowUp" as const,
              color: m.color,
              text: m.text,
            })),
          ),
      };
    }

    return () => {
      instance.remove();
      setChartApi(null);
      chart.current = null;
      series.current = null;
      primitive.current = null;
      structurePrimitive.current = null;
      sessionPrimitive.current = null;
      breakPrimitive.current = null;
      ssmtPrimitive.current = null;
      smtPrimitive.current = null;
      dfrPrimitive.current = null;
      levelsPrimitive.current = null;
    };
  }, []);

  // THE AXIS IS LABELLED, NOT SHIFTED. `lightweight-charts` v5 has no timezone
  // option and formats a raw epoch as UTC, which is how an axis reading 22:00
  // came to describe a bar the owner traded at 05:00 the next morning - and
  // misreading the hour by seven is misreading which session it happened in.
  // The two formatters below are the supported route. Adding an offset to the
  // epochs instead would move every coordinate the primitives and the ribbon
  // look up, and both pixel harnesses assume those are true.
  useEffect(() => {
    if (!chartApi) return;
    chartApi.applyOptions({
      localization: { timeFormatter: (time: Time) => clockStamp(time as number, zone) },
      // Through the chart rather than `timeScale().applyOptions`, which types as
      // the horizontal-scale options and does not carry this formatter.
      timeScale: {
        tickMarkFormatter: (time: Time, type: TickMarkType) =>
          clockTick(time as number, zone, TICK_KIND[type] ?? "time"),
      },
    });
  }, [chartApi, zone]);

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
    // Fed from the CLOSED bars only, and deliberately not from `forming`: a
    // break is the absence of bars between two that exist, and the forming bar
    // sits at the right edge with nothing after it to be absent from.
    breakPrimitive.current?.setBreaks(candles);
  }, [candles]);

  // THE UNCLOSED BAR, drawn and drawn only.
  //
  // Its own effect and its own `update()` rather than being concatenated into
  // the array above, for two reasons that are both load-bearing:
  //
  //  * `setData` rebuilds the whole series. This arrives once a second while
  //    live is on, and rebuilding 500 bars at 1Hz to move one candle is work
  //    nobody asked for.
  //  * `candles` stays the closed-bar series that every measurement in this app
  //    was taken on. `lastClose` below, the zone proximity budget, and every
  //    detector upstream read it and never see this bar. That is the whole
  //    reason the forming candle is safe to show: it is pixels, not evidence.
  //
  // Depends on `candles` as well as on `forming`, because a fresh `setData`
  // wipes the appended bar and it has to be put back.
  useEffect(() => {
    if (!series.current || !forming || candles.length === 0) return;
    // `update()` THROWS on a bar older than the series, so this is a guard and
    // not a tidiness check. The two calls race by construction - the drawing
    // arrives every 30s and the forming bar every second - so a poll answered
    // just before a fresh, longer series lands can carry a bar the new data
    // already contains as closed. Skipping is right: the closed one is better.
    if (forming.time <= candles[candles.length - 1].time) return;
    series.current.update({
      time: forming.time as UTCTimestamp,
      open: forming.open,
      high: forming.high,
      low: forming.low,
      close: forming.close,
    });
  }, [candles, forming]);

  // HOW MANY DECIMALS THIS INSTRUMENT ACTUALLY QUOTES.
  //
  // The series used to carry no `priceFormat` at all, which means the library's
  // default of `precision: 2, minMove: 0.01` - and that default is not a
  // rounding nicety, it is the axis being unable to EXPRESS the price. MT5
  // quotes gold to three decimals, so 4489.621 was labelled 4489.62 and every
  // gridline snapped to a whole cent; on a 5-decimal pair like EURUSD the same
  // default collapses 1.09234 to 1.09 and the scale becomes unusable.
  //
  // The rule itself lives in `lib/price.ts` because the header's OHLC readout
  // needs the identical answer - two decimal counts for one candle is the bug
  // this replaced, not a smaller version of it.
  const precision = useMemo(() => priceDecimals(candles), [candles]);

  useEffect(() => {
    series.current?.applyOptions({
      priceFormat: { type: "price", precision, minMove: 10 ** -precision },
    });
  }, [precision]);

  // Which zones are near price, and so which ones keep a fill and a caption, is
  // measured from the last close. Read here rather than inside the primitive
  // because the chart holds candles as coordinates and the budget needs a price.
  const lastClose = candles.length ? candles[candles.length - 1].close : null;

  useEffect(() => {
    primitive.current?.setZones(zones, interval, lastClose);
    // One frame later, because the price scale recomputes its range while
    // painting: read synchronously here and the first response of a session is
    // measured against the range the PREVIOUS one left behind.
    const frame = requestAnimationFrame(() => {
      if (!series.current || !chart.current) return;
      const next = countClipped(zones, series.current, chart.current.paneSize().height);
      if (next.above === clippedRef.current.above && next.below === clippedRef.current.below) {
        return;
      }
      clippedRef.current = next;
      onClippedRef.current(next);
    });
    return () => cancelAnimationFrame(frame);
  }, [zones, interval, lastClose, onClipped]);

  useEffect(() => {
    structurePrimitive.current?.setStructure(swings, structure);
  }, [swings, structure]);

  useEffect(() => {
    sessionPrimitive.current?.setSession(quarters, trueOpens, news);
  }, [quarters, trueOpens, news]);

  useEffect(() => {
    levelsPrimitive.current?.setLevels(
      gaps, eventHorizons, pools, cisd, namedLevels, projections, tierHorizons,
      gapStacks,
    );
  }, [
    gaps,
    eventHorizons,
    pools,
    cisd,
    namedLevels,
    projections,
    tierHorizons,
    gapStacks,
  ]);

  // Its own effect and not folded into the call above, because it is fed from a
  // different place: everything in `setLevels` is read off the bars already
  // fetched, and a divergence needs a second instrument and therefore a second
  // provider call. Keeping them apart is what stops a cheap overlay's update
  // from being gated on an expensive one's arrival.
  useEffect(() => {
    ssmtPrimitive.current?.setDivergences(ssmt);
  }, [ssmt]);

  useEffect(() => {
    smtPrimitive.current?.setDivergences(smt);
  }, [smt]);

  useEffect(() => {
    dfrPrimitive.current?.setRanges(dfr, dfrEquilibrium);
  }, [dfr, dfrEquilibrium]);

  useEffect(() => {
    primitive.current?.setSelected(selectedId);
  }, [selectedId]);

  // The ribbon lives INSIDE this component rather than beside it in the page,
  // because it has to stay pinned to the chart's own time scale through every
  // pan and zoom - and that scale is this component's private handle. Lifting
  // the chart instance up to the page just to draw a strip would export the one
  // object everything else here is careful to keep encapsulated.
  return (
    <div className="flex h-full w-full flex-col">
      <div className="relative min-h-0 flex-1">
        <div ref={host} className="h-full w-full" />
        {atBar ? <StructureReadout at={atBar} zone={zone} /> : null}
        {/* WHICH CLOCK THE AXIS IS IN, on the axis. The picker in the header
            says it too, but a reader looking at a time is looking down here,
            and an unlabelled 05:00 is the whole hazard. Bottom right is the
            corner where the time axis meets the price scale, which the library
            leaves empty. */}
        <span
          role="status"
          aria-label={`Time axis clock: ${zone}`}
          className="num pointer-events-none absolute bottom-0 right-0 z-10 bg-bg/80 px-1 text-[10px] leading-4 text-text-faint"
        >
          {ZONE_TAG[zone]}
        </span>
      </div>
      <CycleRibbon
        chart={chartApi}
        quarters={quarters}
        now={candles.length ? candles[candles.length - 1].time : null}
      />
    </div>
  );
}

/**
 * What the bar under the crosshair carries, in words.
 *
 * This exists for one reason above all the others: `confirmed_at`. A swing high
 * at bar i is not knowable at bar i, only once enough bars have printed beside
 * it, and the marker is drawn at `time` because that is where the price is. Take
 * that pairing away and the overlay silently claims a pivot was available the
 * moment it printed, which is the lookahead the whole module was built to avoid.
 *
 * It is a readout, not a verdict. No arrow, no bias, no "bullish". Direction is
 * stated as the bar's own fact - which way it closed through the level - because
 * H6 and H9 tested exactly these objects for direction and both were null.
 */
function StructureReadout({
  at,
  zone,
}: {
  at: { swings: SwingPoint[]; events: StructureEvent[] };
  /** Same clock as the axis. Printing UTC here while the axis showed WIB would
   *  put two clocks on one screen with nothing saying which was which. */
  zone: ClockZone;
}) {

  return (
    // `z-10` is not decoration. The charting library's canvases are absolutely
    // positioned with their own stacking, and without a z-index this panel sits
    // in the DOM with a correct bounding box and a correct innerText and is
    // painted over by the pane canvas - present to a test that queries the DOM
    // and invisible to the reader, which is the same class of defect as the
    // borders that were buried under their own candles.
    <div className="pointer-events-none absolute left-2 top-2 z-10 max-w-[300px] border border-line-strong bg-bg/90 px-2 py-1.5">
      {at.swings.map((swing) => (
        <p key={`s-${swing.time}-${swing.high}`} className="num text-[10px] leading-snug text-text-dim">
          <span className="text-text-faint">
            {swing.scale === "swing" ? "swing" : "internal"}
          </span>{" "}
          {swing.high ? "high" : "low"} {swing.price.toFixed(2)}
          <br />
          {/* The whole point of this panel. Stated as "knowable", not "confirmed",
              because a reader can take "confirmed" for a quality grade. */}
          <span className="text-text-faint">knowable only from</span>{" "}
          {clockStamp(swing.confirmed_at, zone)}
        </p>
      ))}
      {at.events.map((event, i) => (
        // Index keys: one bar can carry a BOS and the MSS carved out of it, and
        // both must be listed rather than one hiding the other.
        <p key={`e-${i}`} className="num mt-1 text-[10px] leading-snug text-text-dim">
          <span className="text-text-faint">
            {event.scale === "swing" ? "swing" : "internal"}
          </span>{" "}
          <span className="text-text">{event.kind}</span> at {event.level.toFixed(2)},
          closed {event.direction > 0 ? "above" : "below"} it
          {event.kind === "SWEEP" ? (
            <>
              <br />
              {/* Liquidity taken, versus taken AND rejected. The sources only
                  describe the second one as a sweep, so the absence of a
                  reversal is printed rather than left blank. */}
              {event.reversed_within === null
                ? "never closed back inside: taken, not rejected"
                : `closed back inside after ${event.reversed_within} bar`}
            </>
          ) : null}
          {event.kind === "MSS" && event.swept_at !== null ? (
            <>
              <br />
              after the sweep at {clockStamp(event.swept_at, zone)}
            </>
          ) : null}
          {event.scale === "internal" ? (
            <>
              <br />
              {/* Three-valued, and null is rendered as "no answer" rather than as
                  false. False means the major structure pointed the OTHER way;
                  null means there is no major structure to agree with yet. */}
              <span className="text-text-faint">major structure:</span>{" "}
              {event.aligned_with_swing === null
                ? "no answer yet"
                : event.aligned_with_swing
                  ? "pointed the same way"
                  : "pointed the other way"}
            </>
          ) : null}
        </p>
      ))}
    </div>
  );
}
