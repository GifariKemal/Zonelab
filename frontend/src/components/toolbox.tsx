"use client";

import Link from "next/link";
import { memo, useEffect, useRef, useState, useSyncExternalStore } from "react";

import type {
  DrawResponse,
  LayerParams,
  ServerConfig,
} from "@/lib/types";
import {
  DAY_BOUNDARIES,
  DEGREES,
  DISCOUNT_ANCHORS,
  LIQUIDITY_PERIODS,
  NEWS_IMPACTS,
  POOL_SESSIONS,
  TIER_REDUCTIONS,
} from "@/lib/types";
import { AutoTradePanel } from "./autotrade-panel";
import { ink } from "./ink";
import {
  PRESETS,
  applyPreset,
  removeSaved,
  saveCurrent,
  savedServerSnapshot,
  savedSnapshot,
  subscribeSaved,
} from "@/lib/presets";

interface Props {
  /** The registry. `config.layers` IS the menu - see `Toolbox` below. */
  config: ServerConfig | null;
  /** Which layers are on. Membership is the only enable there is. */
  layers: string[];
  onLayers: (next: string[]) => void;
  /** Every layer's knobs, keyed by the registry's own `params` name. */
  params: LayerParams;
  onParams: <K extends keyof LayerParams>(
    key: K,
    patch: Partial<LayerParams[K]>,
  ) => void;
  onReset: () => void;
  /** Applies a whole layer set in one step. Separate from `onLayers` because a
   *  preset also carries the params its layers need in order to draw anything -
   *  THREE of the seventeen draw nothing with their default params, on purpose, and
   *  the number is measured: drawing each layer alone with pure defaults leaves
   *  `session`, `dfr` and `ssmt` empty and the other twelve drawing. This comment
   *  said six for a while, which was my own count rather than a measurement. */
  onPreset: (layers: string[], params: LayerParams) => void;
  /** The whole `meta` block, not six sliced props. Each layer's knobs pick the
   *  counters that belong to it, which is also where they are readable: a
   *  combined counts panel could not say which drawing a number came from. */
  meta?: DrawResponse["meta"];
  /** The chart's own instrument, so it is excluded from the SSMT partner list -
   *  a divergence against itself is not a divergence, and the backend adds it to
   *  the set on its own anyway. */
  symbol: string;
}

const NO_TRACE =
  "Nothing to trace: these counters come from the box detectors, and none of them is in the layer menu above.";

/** What each rejection counter is called on screen. The engine names five box
 *  detectors' worth of them and the trace used to read ONE detector's, so a user
 *  with the fair value gap on and supply and demand off was told there was
 *  nothing to trace on a request where the server had explained the empty chart
 *  in four numbers.
 *
 *  A counter this table has never heard of still shows, under its own key with
 *  the prefix stripped: unlabelled beats invisible, and a detector added to the
 *  backend then needs no edit here to get a readable trace. */
const TRACE_LABELS: Record<string, string> = {
  rejected_base_too_tall: "Base too tall",
  rejected_base_drifted: "Base drifted",
  rejected_weak_departure: "Weak departure",
  rejected_thin_profit_margin: "Thin profit margin",
  rejected_overlap: "Merged as duplicate",
  rejected_state_filter: "Hidden by state",
  rejected_crowded: "Road shut",
  rejected_too_small: "Gap too small",
  rejected_weak_move: "Move too weak",
  rejected_not_last: "Not the last opposing candle",
  rejected_no_structure_break: "No structure break",
  rejected_never_broke: "Never closed through",
};

/** ONE MENU, BUILT FROM `config.layers`.
 *
 *  THE PROPERTY THIS BUYS, and the reason the shape looks indirect: a layer
 *  added to `backend/app/layers.py` shows up here - in draw order, grouped by
 *  its own kind, with its label, its one-line note and its evidence - with NO
 *  EDIT TO THIS FILE. There is no id union, no detector list, no overlay list
 *  and no per-id label table left in the frontend to drift out of step with the
 *  engine. The one thing still written by hand is each `params` block's knobs,
 *  below in `knobs()`, and a layer that reuses an existing block (as the four
 *  imbalance detectors do) needs nothing even there.
 *
 *  It replaces two mechanisms that meant the same thing: a `detectors` string
 *  array for the five box detectors, and an `enabled` boolean buried in each of
 *  seven overlays' own params. Same intent, two spellings, thirteen ids
 *  duplicated in this file, and seven `<Group>`s that each had to be found by
 *  scrolling.
 *
 *  Memoised: the crosshair sets hovered state on every mouse move over the
 *  chart, and none of these props change while that happens. */
export const Toolbox = memo(function Toolbox({
  config,
  layers,
  onLayers,
  params,
  onParams,
  onReset,
  onPreset,
  meta,
  symbol,
}: Props) {
  const overlayStats = meta?.overlays;
  /** The one overlay that talks to the network, which is why its counters sit at
   *  the top of `meta` rather than inside `overlays`: it runs in the async
   *  handler, after the synchronous build has already returned. */
  const news = meta?.news;
  const on = (id: string) => layers.includes(id);
  const toggle = (id: string) =>
    onLayers(on(id) ? layers.filter((l) => l !== id) : [...layers, id]);

  // HOW OLD THE NEWEST BAR IS. One bar's length is read off the two stamps the
  // server sends rather than from the interval picker, which this panel is not
  // given: `bar_closed_at` is `as_of` plus exactly one interval. The lag is
  // computed on every request for exactly this purpose and was rendered nowhere -
  // a live call came back 3531 seconds behind, which is a chart describing an
  // hour-old bar while looking identical to a current one.
  const step = (meta?.bar_closed_at ?? 0) - (meta?.as_of ?? 0);
  const lag = meta?.feed_lag_seconds ?? 0;

  /** One layer's knobs, chosen by its registry `params` name rather than by its
   *  id, because several layers share a block. Unknown key returns null, so a
   *  layer the backend adds is switchable here before its controls exist. */
  function knobs(key: string) {
    switch (key) {
      case "supply_demand":
        return (
          <>
            <Segmented
              label="Proximal line"
              hint="Only the entry edge moves. The distal always covers the base's extreme, because the stop sits beyond it."
              note="Wick is aggressive, body is conservative. The distal never moves."
              value={params.supply_demand.proximal_basis}
              options={[
                ["wick", "Wick"],
                ["body", "Body"],
              ]}
              onChange={(v) =>
                onParams("supply_demand", {
                  proximal_basis: v as "wick" | "body",
                })
              }
            />
            <Slider
              label="Impulse size"
              hint="A leg candle's range must exceed this many ATR. Lower finds more, weaker legs."
              suffix="ATR"
              min={0.3}
              max={3}
              step={0.1}
              value={params.supply_demand.impulse_atr}
              onChange={(v) => onParams("supply_demand", { impulse_atr: v })}
            />
            <Slider
              label="Impulse body"
              hint="Body as a share of the candle's own range. Separates decisive candles from dojis."
              min={0.2}
              max={0.9}
              step={0.05}
              value={params.supply_demand.impulse_body_ratio}
              onChange={(v) => onParams("supply_demand", { impulse_body_ratio: v })}
            />
            {/* The one control on this panel that a reader must not have to click
                to distrust the others, so its finding stays on screen while the
                numbers behind it fold away. */}
            <Slider
              label="Departure gate"
              hint="How far the leg-out must run from the zone."
              flag="The one gate with evidence behind it, and the only one that survived walk-forward."
              // THE FIGURES ARE NOT REPEATED HERE, deliberately. The layer's own
              // evidence above carries the held rate, the sample and the
              // walk-forward, and it comes from the engine's registry. This
              // string used to carry the same numbers typed by hand, and a
              // shipped claim that no longer matches the evidence is worse than
              // no claim: an assertion in `e2e/sweep.mjs` held a stale 84.6% for
              // two days after the calibration was recomputed. One source.
              evidence="Read the layer's evidence above for the measured figures. What is specific to this knob: the effect is FLAT above 2 ATR, so raising it past the shipped value only removes zones without improving the cohort it selects."
              suffix="ATR"
              min={0}
              max={6}
              step={0.25}
              value={params.supply_demand.departure_min_atr}
              onChange={(v) => onParams("supply_demand", { departure_min_atr: v })}
            />
            <Slider
              label="Profit margin"
              hint="Leg-out travel as a multiple of the zone's own height. Off at 0."
              note="The method asks for 3. Measured, the effect flattens near 2 and adds nothing over the ATR gate, so it ships off."
              suffix="x zone"
              min={0}
              max={6}
              step={0.5}
              value={params.supply_demand.min_profit_margin}
              onChange={(v) => onParams("supply_demand", { min_profit_margin: v })}
            />
            <Slider
              label="Road ahead"
              hint="Clear distance to the nearest live opposing zone, in units of this zone's own height. Off at 0."
              note="The first factor here that ever ranked: zones with a longer road held more often, on both sides, at every geometry (AUC 0.56 to 0.57, CI clear of 0.5). It still ships off, because as a gate it held up in only 7 of 8 unseen time slices where the ATR gate held up in 8 of 8. Above 0 it also stamps zones a newly formed opposing zone has boxed in, which is the one check driven by other zones rather than by price."
              suffix="x zone"
              min={0}
              max={4}
              step={0.5}
              value={params.supply_demand.min_profit_zone_rr}
              onChange={(v) => onParams("supply_demand", { min_profit_zone_rr: v })}
            />
            <Slider
              label="Max base bars"
              hint="Longer consolidations are clipped to the bars the move actually left from."
              min={1}
              max={20}
              step={1}
              value={params.supply_demand.base_max_bars}
              onChange={(v) => onParams("supply_demand", { base_max_bars: v })}
            />
            <Slider
              label="Max base height"
              hint="Measured against the volatility before the base, so a tall base cannot excuse itself."
              suffix="ATR"
              min={0.5}
              max={6}
              step={0.25}
              value={params.supply_demand.base_max_atr}
              onChange={(v) => onParams("supply_demand", { base_max_atr: v })}
            />
            <Slider
              label="Max base drift"
              hint="One-way travel across the base as a share of its own height. 1.0 disables the check."
              note="A base is where price paused. Candles that are each small but walk steadily one way are a staircase, and four independent visual audits named that the most common drawing defect."
              min={0.2}
              max={1}
              step={0.05}
              value={params.supply_demand.max_base_drift}
              onChange={(v) => onParams("supply_demand", { max_base_drift: v })}
            />
            <Slider
              label="ATR period"
              hint="Candles behind the ATR every threshold on this panel is measured in; 14 matches MetaTrader and TradingView."
              min={5}
              max={50}
              step={1}
              value={params.supply_demand.atr_period}
              onChange={(v) => onParams("supply_demand", { atr_period: v })}
            />
            <Slider
              label="Mitigation depth"
              hint="Share of the zone price must eat before it counts as used up."
              min={0.1}
              max={1}
              step={0.05}
              value={params.supply_demand.mitigation_pct}
              onChange={(v) => onParams("supply_demand", { mitigation_pct: v })}
            />
            <Toggle
              label="Show mitigated"
              value={params.supply_demand.show_mitigated}
              onChange={(v) => onParams("supply_demand", { show_mitigated: v })}
            />
            <Toggle
              label="Show broken"
              value={params.supply_demand.show_broken}
              onChange={(v) => onParams("supply_demand", { show_broken: v })}
            />
            <Slider
              label="Zones per side"
              hint="Applied per detector AND per side, so with the four imbalance boxes on as well it permits five times what the number says."
              note="0 lifts the cap, and measurement code must pass 0: at any finite value this keeps only the most RECENT zones, which silently confines a sample to the tail of the history. That mistake has already cost this project one full round of calibration."
              min={0}
              max={40}
              step={1}
              value={params.supply_demand.max_zones_per_side}
              onChange={(v) => onParams("supply_demand", { max_zones_per_side: v })}
            />
            <Slider
              label="Merge overlap"
              hint="Two zones overlapping more than this collapse into the stronger one."
              min={0.2}
              max={1}
              step={0.05}
              value={params.supply_demand.merge_overlap_pct}
              onChange={(v) => onParams("supply_demand", { merge_overlap_pct: v })}
            />
          </>
        );

      // ONE block for four detectors, which is why it is rendered under the
      // first of them that is on rather than repeated under each. Four copies
      // of a slider that writes one value is a control that appears to be four
      // independent thresholds and is not.
      case "imbalance":
        return (
          <>
            <Hint
              k="imbalance"
              note="Shared by the fair value gap, the order block and the two inverted kinds. An IFVG is an FVG plus one more event, so giving them separate gap thresholds would let the two populations drift apart."
            />
            <Slider
              label="Min gap size"
              hint="How wide the untraded band must be before it counts as a gap."
              suffix="ATR"
              min={0}
              max={1}
              step={0.05}
              value={params.imbalance.min_gap_atr}
              onChange={(v) => onParams("imbalance", { min_gap_atr: v })}
            />
            <Slider
              label="Displacement size"
              hint="How hard the leg that made the box had to run."
              note="Reported as an object on every box rather than reduced to the threshold it passed, because ICT states displacement structurally and this engine has only ever tested it as a size."
              suffix="ATR"
              min={0}
              max={5}
              step={0.25}
              value={params.imbalance.displacement_atr}
              onChange={(v) => onParams("imbalance", { displacement_atr: v })}
            />
            <Slider
              label="Displacement window"
              hint="Bars the leg is measured over."
              suffix="bars"
              min={1}
              max={20}
              step={1}
              value={params.imbalance.displacement_bars}
              onChange={(v) => onParams("imbalance", { displacement_bars: v })}
            />
            {/* THE ONLY CONTROL HERE THAT IS A DOCTRINE ARGUMENT rather than a
                threshold, and until now the panel did not offer it at all while
                the zone panel already told the reader in Indonesian that the
                gate was off. Naming a switch and not shipping it is worse than
                shipping neither. Order block only: the other three detectors
                have no block candle to test. */}
            <Toggle
              label="Require structure break"
              value={params.imbalance.require_structure_break}
              onChange={(v) =>
                onParams("imbalance", { require_structure_break: v })
              }
            />
            <Hint
              k="require-structure-break"
              hint="Order block only: the impulse must CLOSE beyond a confirmed swing, not merely travel the displacement size."
              note="Ships off, and that is this engine's biggest departure from ICT. The figures usually quoted to justify requiring it - 52% against 65-68% on 2,400 setups - are untraceable, so neither camp has evidence to hand. On costs a second pass over the bars: fractal swings plus a forward walk."
              evidence="On 600 hourly gold bars it cut the order block from 23 boxes to 10 and rejected 84 candidates - two thirds of the drawing. WHAT THE REMAINING THIRD IS WORTH is unmeasured, here as everywhere else: a stricter gate is not a better one until something has been measured against outcomes."
            />
            {/* Hidden rather than greyed while the gate is off, because the
                engine does not read either of them then - a slider that moves
                and changes nothing is the same lie the stage picker used to
                tell. */}
            {params.imbalance.require_structure_break ? (
              <>
                <Slider
                  label="Break window"
                  hint="Bars after the block candle in which the qualifying break must happen."
                  note="Defaults to the same window the size test uses, so switching the gate on changes the TEST and not the window it is measured over."
                  suffix="bars"
                  min={1}
                  max={50}
                  step={1}
                  value={params.imbalance.structure_break_bars}
                  onChange={(v) =>
                    onParams("imbalance", { structure_break_bars: v })
                  }
                />
                <Slider
                  label="Break fractal"
                  hint="Fractal width of the swings the break is tested against."
                  note="5 is the internal-structure default in the most-installed public codification, the same number the structure overlay's minor scale takes. No primary source publishes one."
                  suffix="bars"
                  min={1}
                  max={100}
                  step={1}
                  value={params.imbalance.structure_n}
                  onChange={(v) => onParams("imbalance", { structure_n: v })}
                />
              </>
            ) : null}
            <Slider
              label="Gap mitigation depth"
              hint="Share of the band price must eat before it counts as used up. Separate from the supply and demand knob of the same name, because these are different populations."
              min={0.1}
              max={1}
              step={0.05}
              value={params.imbalance.mitigation_pct}
              onChange={(v) => onParams("imbalance", { mitigation_pct: v })}
            />
            <Toggle
              label="Show mitigated boxes"
              value={params.imbalance.show_mitigated}
              onChange={(v) => onParams("imbalance", { show_mitigated: v })}
            />
            <Toggle
              label="Show broken boxes"
              value={params.imbalance.show_broken}
              onChange={(v) => onParams("imbalance", { show_broken: v })}
            />
            <Slider
              label="Boxes per side"
              hint="Applied per detector AND per side, so with all four of these on it permits four times what the number says."
              note="0 lifts the cap, and measurement code must pass 0: a finite value keeps only the newest boxes, which confines a sample to the tail of the history."
              min={0}
              max={40}
              step={1}
              value={params.imbalance.max_zones_per_side}
              onChange={(v) => onParams("imbalance", { max_zones_per_side: v })}
            />
          </>
        );

      case "structure":
        return (
          <>
            <Slider
              label="Major fractal"
              hint="Bars a swing pivot must dominate on each side. The major scale: this is the structure, and the minor one is the refinement."
              suffix="bars"
              min={2}
              max={80}
              step={1}
              value={params.structure.swing_n}
              onChange={(v) => onParams("structure", { swing_n: v })}
            />
            <Slider
              label="Minor fractal"
              hint="Same test at a smaller width. Drawn quieter on purpose - it is subordinate to the major scale, and drawing both alike would hide which is which."
              note="50 and 5 are the defaults in the most-installed public codification of these ideas. No primary source publishes a number, and sweeping one would be choosing the answer, so they are taken rather than tuned."
              suffix="bars"
              min={2}
              max={40}
              step={1}
              value={params.structure.internal_n}
              onChange={(v) => onParams("structure", { internal_n: v })}
            />
            <Slider
              label="Sweep reversal"
              hint="Bars in which price must close back inside a swept level for the sweep to be marked as rejected."
              note={`Reported, never required. The sources describe a sweep as liquidity taken AND rejected; this engine only ever coded the taking, so a sweep that never closed back inside is drawn and labelled "unrejected" instead of being dropped.`}
              suffix="bars"
              min={1}
              max={20}
              step={1}
              value={params.structure.sweep_reversal_bars}
              onChange={(v) => onParams("structure", { sweep_reversal_bars: v })}
            />
            <Slider
              label="MSS window"
              hint="Bars between a sweep and the opposite break for the pair to count as a Market Structure Shift."
              suffix="bars"
              min={1}
              max={40}
              step={1}
              value={params.structure.mss_window}
              onChange={(v) => onParams("structure", { mss_window: v })}
            />
            <Slider
              label="Events kept"
              hint="Newest events drawn. 0 draws them all."
              note="A recency cap confines what you see to the tail of the history. Fine for reading a chart, wrong for measuring one - that mistake has already cost this project a full round of calibration - so anything being measured must run at 0."
              min={0}
              max={200}
              step={5}
              value={params.structure.max_events}
              onChange={(v) => onParams("structure", { max_events: v })}
            />
            {meta?.structure ? (
              <div className="border-t border-line pt-2">
                <Hint
                  k="structure-counts"
                  note="What the overlay found. Counted per kind, because an MSS is emitted ALONGSIDE the break it was carved out of - the same bar carries both - and one total would count that pair twice."
                />
                <Stat label="Major pivots" value={meta.structure["swings.swing"]} muted />
                <Stat label="Minor pivots" value={meta.structure["swings.internal"]} muted />
                <div className="mt-2 border-t border-line pt-2" />
                <Stat label="BOS" value={meta.structure["kind.BOS"]} muted />
                <Stat label="CHoCH" value={meta.structure["kind.CHoCH"]} muted />
                <Stat label="Sweeps" value={meta.structure["kind.SWEEP"]} muted />
                <Stat
                  label="of those, rejected"
                  value={meta.structure["sweeps.reversed"]}
                  muted
                />
                <Stat
                  label="MSS, inside the above"
                  value={meta.structure["kind.MSS"]}
                  muted
                />
                <div className="mt-2 border-t border-line pt-2" />
                <Stat
                  label="Minor agreeing with major"
                  value={meta.structure["internal.aligned_with_swing"]}
                  muted
                />
                {meta.structure["events.dropped_by_cap"] ? (
                  <Stat
                    label="Hidden by the cap"
                    value={meta.structure["events.dropped_by_cap"]}
                    muted
                  />
                ) : null}
              </div>
            ) : null}
          </>
        );

      case "session":
        return (
          <>
            {/* Named levels are the most-used object in the method this serves:
                they appear on 24 of 24 of the owner's own annotated price charts,
                where Fibonacci appears on 12%. Listed first for that reason.
                An EMPTY list here now means the layer is on and drawing nothing,
                which is a state the old design could not express - it used a
                non-empty list as its own switch. */}
            <Degrees
              label="True opens"
              selected={params.session.true_opens}
              onChange={(v) => onParams("session", { true_opens: v })}
            />
            {/* The one degree whose level CANNOT exist under the strict rule, so
                the toggle below is not a preference for it - it is the
                difference between a line and nothing. Said here rather than in
                the note, because a reader who picks quadrennial and sees an
                empty chart will otherwise conclude the degree is broken. */}
            <Toggle
              label="Allow approximate opens"
              value={params.session.approximate_true_opens}
              onChange={(v) => onParams("session", { approximate_true_opens: v })}
            />
            {params.session.true_opens.includes("quadrennial") &&
            !params.session.approximate_true_opens ? (
              <p className="text-[11px] leading-relaxed text-accent">
                The quadrennial true open is 1 January, and the market is shut on
                1 January every year - so under the strict rule this degree draws
                nothing at all. Measured on ten years of hourly gold: zero
                levels strict, two approximate. Switch the toggle above on to see
                them, dashed and tagged with a ~.
              </p>
            ) : null}
            <Note>
              A true open is a cycle&apos;s Q2 open, which is why the daily one is
              midnight New York and not 18:00. Strictly it needs a bar that opened
              on the boundary; approximate takes the first bar after it, within
              120 hours or one bar of this chart, whichever is longer. 120 comes
              from the longest real closure in this feed, the 96-hour Christmas
              and New Year weeks; the bar interval is in there because a weekly
              bar opens once every 168 hours, so on a coarse chart a boundary can
              sit five days from the next open without the market ever having
              shut. Approximate levels draw dashed and never look like measured
              ones.
            </Note>
            <Degrees
              label="Quarter boxes"
              selected={params.session.quarters}
              onChange={(v) => onParams("session", { quarters: v })}
            />
            {/* THE LAYER IS ON AND DRAWING NOTHING, SAID OUT LOUD. Both lists
                above are empty by default - deliberately, because an overlay that
                switched itself on would spend an ink budget somebody else had
                accounted for - so switching this layer on and picking no degree
                produces a completely blank result. Measured: `session`, `dfr` and
                `ssmt` are the only three layers of seventeen that do this, and the
                other two already said so. This one did not, and the reader's
                report was exactly the predictable one: "the quarters do not
                appear". An empty chart and a broken engine must never look alike.

                Split into three messages rather than one, because the two lists
                draw different objects: `quarters` are the boxes on the price pane
                AND the phase rows in the ribbon below it, `true_opens` are the
                named rays at the right edge. Losing one is not losing the
                other. */}
            {!params.session.quarters.length && !params.session.true_opens.length ? (
              <p className="text-[11px] leading-relaxed text-accent">
                This layer is on and drawing nothing. Pick a degree above: the
                quarter boxes and the phase ribbon come from{" "}
                <b>Quarter boxes</b>, and the named rays at the right edge come
                from <b>True opens</b>. Both start empty on purpose, because a
                grid that switched itself on would spend ink you had not asked
                for.
              </p>
            ) : !params.session.quarters.length ? (
              <p className="text-[11px] leading-relaxed text-text-faint">
                No quarter boxes and no phase ribbon: those need a degree here.
                The true opens above are drawing.
              </p>
            ) : !params.session.true_opens.length ? (
              <p className="text-[11px] leading-relaxed text-text-faint">
                No true opens: those need a degree above. The quarter boxes and
                the ribbon are drawing.
              </p>
            ) : null}
            <Slider
              label="Quarters kept"
              hint="Newest quarters drawn, for readability. A month of micro quarters is nearly two thousand objects."
              note="0 draws them all. A recency cap has already cost this project one full round of calibration, so measurement code must pass 0 - but a chart is not measurement, and this one is a display limit."
              min={0}
              max={1000}
              step={50}
              value={params.session.max_quarters}
              onChange={(v) => onParams("session", { max_quarters: v })}
            />
            {meta?.session ? (
              <div className="border-t border-line pt-2">
                <Stat label="Quarters found" value={meta.session.quarters_found} muted />
                <Stat label="Quarters drawn" value={meta.session.quarters_drawn} muted />
                <Stat label="True opens" value={meta.session.true_opens} muted />
                {/* Split out, because an approximate level and a measured one
                    are not the same object and this count is the only way a
                    reader of the panel can tell how much of the set is which. */}
                {meta.session.true_opens_approximate ? (
                  <Stat
                    label="Of those, approximate"
                    value={meta.session.true_opens_approximate}
                    muted
                  />
                ) : null}
                {/* The number that separates "the feed had no bar there" from
                    "the engine forgot to draw it". Over a fortnight of gold,
                    eight of about twenty-four daily true opens are genuinely
                    absent, because no bar opened on the boundary across weekends
                    and holidays. Nothing is carried forward to fill them. */}
                {Object.entries(meta.session.true_opens_missing ?? {}).map(
                  ([degree, n]) =>
                    n ? (
                      <Stat
                        key={degree}
                        label={`${degree}: no bar on the boundary`}
                        value={n}
                        muted
                      />
                    ) : null,
                )}
                {meta.session.unknown_degrees?.length ? (
                  <p className="mt-2 text-[11px] leading-relaxed text-accent">
                    Not a degree this engine has:{" "}
                    {meta.session.unknown_degrees.join(", ")}.
                  </p>
                ) : null}
              </div>
            ) : null}
          </>
        );

      case "gaps":
        return (
          <>
            <Toggle
              label="Event horizons"
              value={params.gaps.event_horizons}
              onChange={(v) => onParams("gaps", { event_horizons: v })}
            />
            <Slider
              label="Gaps kept"
              hint="Newest gaps retained before the levels are paired."
              note="Not a display cap. Adjacency is in PRICE order, so dropping a gap DELETES a level and re-pairs its neighbours: two values give different level sets rather than nested ones. ICT prefers five, a widely used port keeps ten, and 5 here is a choice rather than a measurement. 0 keeps everything."
              min={0}
              max={20}
              step={1}
              value={params.gaps.keep}
              onChange={(v) => onParams("gaps", { keep: v })}
            />
            <Slider
              label="Gaps per tier"
              hint="Gaps of one kind behind each tier zone."
              note="THREE IS THE OWNER'S OWN NUMBER, confirmed directly rather than reverse-engineered - which makes it the one part of this construct that is sourced. 0 uses every gap of the kind."
              min={0}
              max={10}
              step={1}
              value={params.gaps.tier_keep}
              onChange={(v) => onParams("gaps", { tier_keep: v })}
            />
            {/* The reduction is UNRESOLVED, so it is a visible control rather
                than a constant: none of the four reproduces the reference
                indicator's published table on data that agrees with it on price
                to five points, and shipping one silently would present a guess
                as a match. */}
            <Chips
              label="Tier reduction"
              options={[...TIER_REDUCTIONS]}
              selected={[params.gaps.tier_reduction]}
              onChange={(next) =>
                onParams("gaps", {
                  tier_reduction:
                    next.filter((r) => r !== params.gaps.tier_reduction)[0] ??
                    params.gaps.tier_reduction,
                })
              }
            />
            <Note>
              How the retained gaps become one zone is not settled. None of these
              four matches the reference indicator, so the drawn band is this
              engine&apos;s reading and not a reproduction of its.
            </Note>
            {overlayStats ? (
              <div className="border-t border-line pt-2">
                {/* Found against drawn. `keep` trims the BANDS as well as the
                    levels, because 53 bands beside 4 levels derived from five of
                    them is a picture that cannot be read back to its inputs. */}
                <Stat label="Gaps found" value={overlayStats.gaps_found} muted />
                <Stat label="Gaps drawn" value={overlayStats.gaps} muted />
                {/* HOW FAR BACK THE GAPS ACTUALLY LOOKED, which is not the
                    chart's own bar count. A gap's closing price routinely sits
                    outside the window while the gap it produced is the leftmost
                    thing on screen: measured 2026-08-19 on MT5 gold 15m, at 300
                    bars the Friday close was in range and the weekend band drew,
                    at 250, 200 and 150 it was not and the layer drew nothing at
                    all. This layer therefore fetches its own history, and the
                    number it read is worth seeing beside the counts above. */}
                <Stat
                  label="History read"
                  value={overlayStats.gap_history_bars}
                  muted
                />
                {/* AN EMPTY LAYER TOLD FROM A BROKEN ONE. `traded_through` means
                    the market never shut across those boundaries, so there is no
                    gap to find - the whole and correct answer on a 24/7
                    instrument. `no_bars` is the other reason and has the opposite
                    remedy: the window still does not reach the closing session.
                    Before this was counted, both looked like silence. */}
                {overlayStats.gaps_traded_through ? (
                  <p className="mt-1 text-[11px] leading-relaxed text-text-faint">
                    This instrument never closed across{" "}
                    {overlayStats.gaps_traded_through} boundary
                    {overlayStats.gaps_traded_through === 1 ? "" : "ies"}, so
                    there is no opening gap to draw there. An opening gap is the
                    distance across an interval in which nothing traded.
                  </p>
                ) : null}
                {overlayStats.gaps_no_bars ? (
                  <Stat
                    label="Boundaries out of window"
                    value={overlayStats.gaps_no_bars}
                    muted
                  />
                ) : null}
                {/* The one count that changes how a band should be READ. ICT
                    requires 1m or 5m bars because a daily close is the SETTLEMENT
                    price, not the last price that traded before 17:00 - so on
                    coarse bars the band's edges are the nearest the feed could
                    offer. Hourly bars come out exact; 4-hour bars never do. Those
                    bands are framed dashed and tagged with a ~. */}
                {overlayStats.gaps_approximate ? (
                  <Stat
                    label="Approximate edges"
                    value={overlayStats.gaps_approximate}
                    muted
                  />
                ) : null}
                {/* Two gaps of different kinds agreeing on one price. Reported
                    even at zero, because zero is the answer most windows give
                    and a missing row reads as a missing feature. */}
                <Stat label="Gap stacks" value={overlayStats.gap_stacks} muted />
                <Stat label="Event horizons" value={overlayStats.event_horizons} muted />
              </div>
            ) : null}
          </>
        );

      case "cisd":
        return (
          <>
            <Slider
              label="Shortest run"
              hint="Runs shorter than this cannot arm a level. They still exist and are still counted."
              note="1 makes almost every bar a CISD, so 2 is the floor that excludes the degenerate case. Chosen, not measured."
              min={1}
              max={8}
              step={1}
              value={params.cisd.min_run}
              onChange={(v) => onParams("cisd", { min_run: v })}
            />
            <Slider
              label="Interruptions absorbed"
              hint="Opposing closes a run swallows before it ends."
              note="0 is the literal reading of 'consecutive'. Raising it merges runs, which moves both the level AND the bar the event lands on, so the count is not stable under this knob."
              min={0}
              max={5}
              step={1}
              value={params.cisd.interrupt_tolerance}
              onChange={(v) => onParams("cisd", { interrupt_tolerance: v })}
            />
            <Slider
              label="Events drawn"
              hint="Newest events kept, for readability."
              note="At the shipped floor, 1200 bars of hourly gold produce 131 of these - one on every ninth bar. The same display limit the structure overlay applies to its own events, because they are the same class of object. 0 draws them all."
              min={0}
              max={200}
              step={10}
              value={params.cisd.max_events}
              onChange={(v) => onParams("cisd", { max_events: v })}
            />
            {overlayStats ? (
              <div className="border-t border-line pt-2">
                <Stat label="CISD found" value={overlayStats.cisd_found} muted />
                <Stat label="CISD drawn" value={overlayStats.cisd} muted />
                {/* The population the events were selected FROM. The ratio is
                    what a chosen-not-measured floor owes its reader. */}
                <Stat label="Delivery runs" value={overlayStats.delivery_runs} muted />
              </div>
            ) : null}
          </>
        );

      case "news":
        return (
          <>
            <Chips
              label="Impact"
              options={[...NEWS_IMPACTS]}
              selected={params.news.impacts}
              onChange={(v) => onParams("news", { impacts: v })}
            />
            <Chips
              label="Currency"
              options={["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CNY"]}
              selected={params.news.currencies}
              onChange={(v) => onParams("news", { currencies: v })}
            />
            <Note>
              None selected keeps every currency. Impact is the feed&apos;s own
              label for how much attention a release draws, not a measured effect
              on price, and this source publishes only the current week so
              nobody can turn it into one.
            </Note>
            {news ? (
              <div className="border-t border-line pt-2">
                <Stat label="Releases in the feed" value={news.news_found} muted />
                <Stat label="Drawn on this chart" value={news.news} muted />
                {/* Dropped rather than nailed to the last bar before them, which
                    is what a weekend or holiday row would otherwise do: place a
                    release on a bar that closed hours earlier. */}
                {news.news_market_shut ? (
                  <Stat
                    label="Fell while the market was shut"
                    value={news.news_market_shut}
                    muted
                  />
                ) : null}
                {news.news_window ? (
                  <p className="mt-1 text-[11px] leading-relaxed text-text-faint">
                    The feed covers {news.news_window}, read from the response
                    rather than assumed to be a week.
                  </p>
                ) : null}
                {/* THE ONLY LAYER THAT CAN FAIL for a reason outside this
                    machine, and the failure looked exactly like a quiet
                    calendar: no events, no message. Same treatment as the pools
                    overlay's unknown sessions. */}
                {news.news_error ? (
                  <p className="mt-2 text-[11px] leading-relaxed text-accent">
                    The calendar feed failed, so nothing was drawn:{" "}
                    {news.news_error}
                  </p>
                ) : null}
              </div>
            ) : null}
          </>
        );
      case "pools":
        return (
          <>
            <Chips
              label="Sessions"
              options={[...POOL_SESSIONS]}
              selected={params.pools.sessions}
              onChange={(v) => onParams("pools", { sessions: v })}
            />
            <Slider
              label="Pools drawn"
              hint="Newest pools kept, for readability."
              note="Two sessions over 50 days of hourly gold is 212 named rays, which is no longer a chart. Recency is the right axis because that is what the fact is worth: a London high taken this morning kills an idea, the same fact from seven weeks ago does not. At equal age a standing pool outranks a taken one. 0 draws them all."
              min={0}
              max={80}
              step={4}
              value={params.pools.max_pools}
              onChange={(v) => onParams("pools", { max_pools: v })}
            />
            {overlayStats ? (
              <div className="border-t border-line pt-2">
                <Stat label="Pools found" value={overlayStats.pools_found} muted />
                <Stat label="Pools drawn" value={overlayStats.pools} muted />
                <Stat label="Still standing" value={overlayStats.pools_standing} muted />
                {/* A fact about the FEED, not the market: a partial window's high
                    is not the session high. Kept apart from "taken" for that
                    reason, and those rays are dashed and tagged with a ?. */}
                {overlayStats.pools_partial ? (
                  <Stat
                    label="Window not fully covered"
                    value={overlayStats.pools_partial}
                    muted
                  />
                ) : null}
                {overlayStats.unknown_sessions?.length ? (
                  <p className="mt-2 text-[11px] leading-relaxed text-accent">
                    Not a session this engine has:{" "}
                    {overlayStats.unknown_sessions.join(", ")}.
                  </p>
                ) : null}
              </div>
            ) : null}
          </>
        );

      case "liquidity":
        return (
          <>
            <Chips
              label="Periods"
              options={[...LIQUIDITY_PERIODS]}
              selected={params.liquidity.periods}
              onChange={(v) => onParams("liquidity", { periods: v })}
            />
            {/* The one control here that changes the NUMBERS rather than which
                numbers are shown. A previous-day high measured 18:00 to 18:00 is
                a different price from one measured midnight to midnight, and no
                source says which one his own PDH is read on. */}
            <Chips
              label="Day boundary"
              options={[...DAY_BOUNDARIES]}
              selected={[params.liquidity.boundary]}
              onChange={(next) =>
                onParams("liquidity", {
                  boundary:
                    next.filter((b) => b !== params.liquidity.boundary)[0] ??
                    params.liquidity.boundary,
                })
              }
            />
            <Toggle
              label="Range frame"
              value={params.liquidity.range_frame}
              onChange={(v) => onParams("liquidity", { range_frame: v })}
            />
            <Note>
              The dealing range on the chart: both extremes, the 50% equilibrium
              and the two quartiles. The engine has always read every box against
              this range - that is the percentage in the zone panel - and until now
              the frame itself only reached a side panel as two numbers. The
              quartiles are the same constants the decision engine tests, so the
              line and the verdict cannot disagree.
            </Note>
            <Toggle
              label="Equal highs and lows"
              value={params.liquidity.equal_levels}
              onChange={(v) => onParams("liquidity", { equal_levels: v })}
            />
            {params.liquidity.equal_levels ? (
              <>
                <Slider
                  label="Equal within"
                  hint="How far apart two swings may be and still count as equal."
                  note="In ATR. 0.1 is what the surveyed open-source implementations use, adopted with its provenance rather than invented. The other rule in circulation is a fraction of the loaded window's range, and that one is refused here: it makes the tolerance depend on how many bars you picked, so the same two swings stop being equal when you change Bars and no candle has moved."
                  min={0}
                  max={1}
                  step={0.01}
                  suffix=" ATR"
                  value={params.liquidity.equal_tolerance_atr}
                  onChange={(v) => onParams("liquidity", { equal_tolerance_atr: v })}
                />
                <Note>
                  Drawn as REQH and REQL with their touch count. The fractal width
                  comes from Market structure, not from a second knob, so a shelf
                  can never sit between two swings that overlay does not consider
                  swings - and that width is what decides how many you see.
                  Measured on 2000 bars of 15m gold: the shipped 50 finds 1 shelf,
                  20 finds 4, 10 finds 12 and 3 finds 53. One faded line at the
                  default is the fractal being coarse, not the layer being broken.
                  Fidelity only: nothing here has been measured against outcomes.
                </Note>
              </>
            ) : null}
            <Toggle
              label="Range liquidity"
              value={params.liquidity.range_liquidity}
              onChange={(v) => onParams("liquidity", { range_liquidity: v })}
            />
            <Toggle
              label="Draw candidates"
              value={params.liquidity.draw_candidates}
              onChange={(v) => onParams("liquidity", { draw_candidates: v })}
            />
            <Note>
              Candidates are reported on BOTH sides and never resolved to one.
              Naming the draw is a forecast, and twelve of those have failed here.
            </Note>
            {overlayStats ? (
              <div className="border-t border-line pt-2">
                <Stat label="Named levels" value={overlayStats.levels} muted />
                <Stat label="Levels standing" value={overlayStats.levels_standing} muted />
                {/* The two readings' own counts. Both switches produce numbers
                    rather than shapes and both are now rendered in the right
                    rail; these say how many the engine found. */}
                {params.liquidity.range_liquidity ? (
                  <>
                    <Stat label="External (ERL)" value={overlayStats.external} muted />
                    <Stat label="Internal (IRL)" value={overlayStats.internal} muted />
                  </>
                ) : null}
                {/* A range needs a confirmed swing on BOTH sides, so a short
                    window or a one-directional run legitimately has none - and the
                    engine says which of the two it is rather than drawing nothing
                    and leaving the reader to guess. */}
                {params.liquidity.equal_levels ? (
                  <>
                    <Stat label="Shelves" value={overlayStats.equal_levels} muted />
                    <Stat
                      label="Still standing"
                      value={overlayStats.equal_levels_standing}
                      muted
                    />
                  </>
                ) : null}
                {params.liquidity.range_frame ? (
                  typeof overlayStats.range_frame === "number" ? (
                    <>
                      <Stat label="Range lines" value={overlayStats.range_frame} muted />
                      <Stat label="Range height" value={overlayStats.range_height} muted />
                    </>
                  ) : (
                    <p className="text-[11px] leading-relaxed text-text-dim">
                      No range frame: {String(overlayStats.range_frame ?? "not reported")}
                    </p>
                  )
                ) : null}
              </div>
            ) : null}
          </>
        );

      case "projections":
        return (
          <>
            <Chips
              label="From session"
              options={[...POOL_SESSIONS]}
              selected={params.projections.sessions}
              onChange={(v) => onParams("projections", { sessions: v })}
            />
            <Chips
              label="Direction"
              options={["both", "up", "down"]}
              selected={[
                params.projections.direction === 0
                  ? "both"
                  : params.projections.direction > 0
                    ? "up"
                    : "down",
              ]}
              onChange={(next) => {
                const current =
                  params.projections.direction === 0
                    ? "both"
                    : params.projections.direction > 0
                      ? "up"
                      : "down";
                const pick = next.find((d) => d !== current);
                if (!pick) return;
                onParams("projections", {
                  direction: pick === "up" ? 1 : pick === "down" ? -1 : 0,
                });
              }}
            />
            <Note>
              Both by default. On his own charts the direction is read from where
              price went after the range, which is hindsight - so the engine draws
              both ways rather than guessing one.
            </Note>
            {overlayStats ? (
              <div className="border-t border-line pt-2">
                <Stat label="Projections" value={overlayStats.projection_levels} muted />
              </div>
            ) : null}
          </>
        );

      case "checklist":
        return (
          <>
            <Degrees
              label="Cycle degree"
              selected={[params.checklist.degree]}
              onChange={(next) =>
                // One degree, not a set: the defining range, the profile and
                // manipulation are all read at a single cycle. The last click
                // wins rather than accumulating.
                onParams("checklist", {
                  degree:
                    next.filter((d) => d !== params.checklist.degree)[0] ??
                    params.checklist.degree,
                })
              }
            />
            {/* "In discount?" is measured against a CLOCK, not a swing, and that
                is what separates it from the two premium/discount readings the
                zones already carry. The anchor is single-sourced, so this picks
                only which reading is `chosen`: all three are computed either way,
                and the panel names them when they disagree. */}
            <Chips
              label="In discount, measured against"
              options={[...DISCOUNT_ANCHORS]}
              selected={[params.checklist.discount_anchor]}
              onChange={(next) =>
                onParams("checklist", {
                  discount_anchor:
                    next.filter((a) => a !== params.checklist.discount_anchor)[0] ??
                    params.checklist.discount_anchor,
                })
              }
            />
            {/* TRIAD PRESETS — one click fills the two partner symbols. The
                base is the chart's own symbol, which is always excluded from
                the partner list, so the triad works with any instrument. */}
            <Chips
              label="Triad"
              options={["monetary", "commodity", "risk", "fx"]}
              selected={[]}
              onChange={(v) => {
                const partners: Record<string, string[]> = {
                  monetary: ["DXY", "EURUSD"],
                  commodity: ["WTI", "XAGUSD"],
                  risk: ["NAS100", "US30"],
                  fx: ["USDJPY", "XPTUSD"],
                };
                const picked = v[v.length - 1];
                if (!picked || !partners[picked]) return;
                onParams("checklist", {
                  ssmt_symbols: partners[picked].filter(
                    (p) => p !== symbol,
                  ),
                });
              }}
            />
            {/* Instruments FIRST, because stages alone do nothing: the backend
                needs both, and a stage picker on its own was a control that
                looked like it worked and silently did not. */}
            <Chips
              label="SSMT against"
              options={(config?.symbols ?? [])
                .map((s) => s.id)
                .filter((id) => id !== symbol)}
              selected={params.checklist.ssmt_symbols}
              onChange={(v) => onParams("checklist", { ssmt_symbols: v })}
            />
            <Degrees
              label="SSMT stages"
              selected={params.checklist.ssmt_degrees}
              onChange={(v) => onParams("checklist", { ssmt_degrees: v })}
            />
            {params.checklist.ssmt_symbols.length &&
            !params.checklist.ssmt_degrees.length ? (
              <p className="text-[11px] leading-relaxed text-accent">
                Pick at least one stage as well. A stage IS a degree, and nothing
                requires two.
              </p>
            ) : null}
            {params.checklist.ssmt_degrees.length &&
            !params.checklist.ssmt_symbols.length ? (
              <p className="text-[11px] leading-relaxed text-accent">
                Pick an instrument to read against. A divergence needs two.
              </p>
            ) : null}
            {/* The number that decides whether an SSMT means anything. Measured
                at day degree on 2000 hourly bars: gold against silver diverges
                on 14,9% of readings, platinum 21,0%, NASDAQ 36,0%, BTC 43,3% and
                DXY 59,5%. The rate tracks correlation, so an inversely
                correlated instrument disagrees on nearly every quarter by
                construction - that is a category error, not a rich seam. */}
            {/* MEASURED, not guessed. This was a hardcoded list of three tickers -
                DXY, US10Y, US30Y - and it was wrong in both directions: two of
                the three are unreachable on the terminal anyway, and it named
                neither WTI nor USDJPY, which measure -0.33 and -0.28 against gold
                on 1067 paired hourly returns. A number per partner replaces it.
                Before the first draw there is nothing to report, and the panel
                says that rather than falling back to the guess. */}
            {meta?.ssmt?.correlation?.length ? (
              <div className="border-t border-line pt-2">
                <p className="mb-1 text-[11px] text-text-dim">
                  Correlation of log returns, {meta.ssmt.correlation[0].pairs} paired
                  bars
                </p>
                {meta.ssmt.correlation.map((c) => (
                  <div key={c.symbol} className="flex items-baseline justify-between gap-2">
                    <span className="num text-[11px] text-text-dim">{c.symbol}</span>
                    <span className="num text-[11px] text-text">
                      {c.full === null ? "not measurable" : c.full.toFixed(3)}
                      {c.recent !== null && c.full !== null ? (
                        <span className="text-text-faint"> / {c.recent.toFixed(3)}</span>
                      ) : null}
                    </span>
                  </div>
                ))}
                <p className="mt-1 text-[11px] leading-relaxed text-text-faint">
                  Whole window / its last quarter. A negative partner is not invalid,
                  it is one whose divergences read the other way round - and it
                  disagrees on most readings by construction, so the layer says less
                  there. Nothing here predicts anything.
                </p>
                {meta.ssmt.correlation.some((c) => c.sign_changed) ? (
                  <p className="mt-1 text-[11px] leading-relaxed text-accent">
                    {meta.ssmt.correlation
                      .filter((c) => c.sign_changed)
                      .map((c) => c.symbol)
                      .join(", ")}{" "}
                    changed sign inside this window, so the single figure above is
                    the average of two different relationships.
                  </p>
                ) : null}
              </div>
            ) : null}
            {/* A partner that never loaded is not a partner that agreed. */}
            {meta?.ssmt?.skipped?.length ? (
              <p className="text-[11px] leading-relaxed text-accent">
                Not loaded: {meta.ssmt.skipped.join("; ")}
              </p>
            ) : null}
            {/* THE BASKET'S VENUE, which the chart's own picker cannot decide.
                One symbol id is a different instrument per source - XAUUSD is a
                COMEX contract on yahoo and a broker spot CFD on mt5, and the
                two sat 56 dollars apart when this was written - so charting the
                terminal you trade would otherwise drag silver and copper onto
                that broker's CFDs too. Offered only once there is a basket to
                have an opinion about, and only for sources that carry EVERY
                instrument in it, because a source missing one leg fails the
                whole read with a message about that leg rather than about this
                control. */}
            {params.checklist.ssmt_symbols.length ? (
              <>
                <Chips
                  label="SSMT source"
                  options={[
                    "chart",
                    ...(config?.providers ?? [])
                      .filter((p) => p.available && p.id !== "synthetic")
                      .map((p) => p.id)
                      .filter((id) =>
                        [symbol, ...params.checklist.ssmt_symbols].every((s) =>
                          config?.symbols
                            .find((entry) => entry.id === s)
                            ?.providers.includes(id),
                        ),
                      ),
                  ]}
                  selected={[params.checklist.ssmt_provider ?? "chart"]}
                  onChange={(next) => {
                    const current = params.checklist.ssmt_provider ?? "chart";
                    const picked = next.filter((p) => p !== current)[0] ?? current;
                    onParams("checklist", {
                      ssmt_provider: picked === "chart" ? null : picked,
                    });
                  }}
                />
                <p className="text-[11px] leading-relaxed text-text-faint">
                  {params.checklist.ssmt_provider
                    ? `The whole basket, gold included, is read from ${params.checklist.ssmt_provider} and refetched from it rather than reused from the chart. The divergences are a statement about ${params.checklist.ssmt_provider}; the levels on screen are not.`
                    : "Follows the Source picker at the top. Choose yahoo to read the basket as the COMEX complex - GC=F, SI=F, HG=F, PL=F, PA=F - while the chart stays on the venue you trade."}
                </p>
                {/* The one cap that fills faster than any other overlay's,
                    because the count is multiplicative: partners times degrees
                    times two sides. Measured on the first run of the drawn
                    layer - XAUUSD 1h, 2000 bars, two partners, two degrees -
                    1312 segments, which is not a chart. */}
                <Slider
                  label="Divergences drawn"
                  hint="Newest kept, for readability. Partners x degrees x two sides fills this fast."
                  note="0 draws them all, and a measurement must pass 0. A display limit only: it never changes which divergences exist, and the checklist's own count is taken before it."
                  min={0}
                  max={400}
                  step={10}
                  value={params.checklist.ssmt_max}
                  onChange={(v) => onParams("checklist", { ssmt_max: v })}
                />
              </>
            ) : null}
            {/* EMPTY IS WHY THE PANEL'S CHAIN BLOCK NEVER APPEARED. The field
                existed on both sides of the wire with nothing to fill it, so
                `ChecklistReport.chain` came back null on every request and a
                whole block of the checklist was unreachable. Outermost first,
                and the order you click IS the order it is read in: his examples
                are three digits and never name the degrees, so there is no
                default worth inventing. Empty skips it and costs nothing. */}
            <Degrees
              label="Quarter chain"
              selected={params.checklist.chain_degrees}
              onChange={(v) => onParams("checklist", { chain_degrees: v })}
            />
            <Timeframes
              label="Bias timeframes"
              selected={params.checklist.bias_timeframes}
              onChange={(v) => onParams("checklist", { bias_timeframes: v })}
            />
            {meta?.checklist?.extra_fetches ? (
              <Stat
                label="Extra provider calls"
                value={meta.checklist.extra_fetches}
                muted
              />
            ) : null}
            {/* THE SSMT LAYER'S OWN COUNTERS, shown here because its controls
                are here: it shares this params block, so it has no panel of its
                own. Nothing rendered them for a while - the backend has assigned
                `meta["ssmt"]` since the layer shipped and the frontend declared
                no shape for it, so the one overlay that can fail for an external
                reason was the one overlay whose failure the panel could not
                show. */}
            {meta?.ssmt ? (
              <div className="border-t border-line pt-2">
                {meta.ssmt.error ? (
                  <p className="mb-1 text-[11px] leading-relaxed text-accent">
                    {meta.ssmt.error}
                  </p>
                ) : null}
                <Stat label="Divergences found" value={meta.ssmt.found} muted />
                <Stat label="Drawn on this chart" value={meta.ssmt.drawn} muted />
                {/* The cost of the intersection, stated rather than hidden. Four
                    partners discard about 30% of the window. */}
                <Stat label="Bars the basket shares" value={meta.ssmt.grid} muted />
                {meta.ssmt.range ? (
                  <>
                    <Stat
                      label="In premium"
                      value={meta.ssmt.range.premium}
                      muted
                    />
                    <Stat
                      label="In equilibrium"
                      value={meta.ssmt.range.equilibrium}
                      muted
                    />
                    <Stat
                      label="In discount"
                      value={meta.ssmt.range.discount}
                      muted
                    />
                    {meta.ssmt.range.unknown ? (
                      <Stat
                        label="Range not yet confirmed"
                        value={meta.ssmt.range.unknown}
                        muted
                      />
                    ) : null}
                    <Note>
                      Where each divergence&apos;s own extreme sat in the dealing
                      range knowable when it printed. The rule this serves is that
                      a divergence in premium and one in discount mean opposite
                      things, and one outside either zone is evidence about where
                      the draw is rather than a trade. Reported and never scored:
                      the raw range position looked like this project&apos;s
                      strongest finding until it was split by side, and then it
                      was upward drift in the sample.
                    </Note>
                  </>
                ) : null}
              </div>
            ) : null}
          </>
        );

      case "dfr":
        return (
          <>
            <Degrees
              label="Cycle degree"
              selected={params.dfr.degrees}
              onChange={(v) => onParams("dfr", { degrees: v })}
            />
            {!params.dfr.degrees.length ? (
              <p className="text-[11px] leading-relaxed text-accent">
                Pick a degree. A defining range is a window inside ONE quarter,
                so without a degree there is no window to read.
              </p>
            ) : null}
            {/* Dashed and drawn INSIDE the band only, unlike the projections
                which reach right: the midpoint describes the window, it is not
                a level to travel to. */}
            <Toggle
              label="Draw the 50% line"
              value={params.dfr.equilibrium}
              onChange={(v) => onParams("dfr", { equilibrium: v })}
            />
            <Slider
              label="Bands drawn"
              hint="Newest windows kept, for readability."
              note="This cap MULTIPLIES: every band also draws its projection levels, so two multiples on both sides is five objects per band. 0 draws them all, and any measurement must use 0."
              min={0}
              max={40}
              step={1}
              value={params.dfr.max_ranges}
              onChange={(v) => onParams("dfr", { max_ranges: v })}
            />
            <Note>
              Q1 of the chosen degree, split in thirds, the first third dropped,
              the high and low of the rest. Its projections are drawn on BOTH
              sides of every multiple because the one source that describes them
              gives no direction. This is the single most weakly evidenced object
              on the canvas - one description of a closed-source indicator,
              unverified against outcomes - and it is drawn fainter and thinner
              than everything measured beside it for exactly that reason.
            </Note>
            {overlayStats ? (
              <div className="border-t border-line pt-2">
                <Stat label="Ranges found" value={overlayStats.dfr_found} muted />
                <Stat label="Ranges drawn" value={overlayStats.dfr} muted />
                {/* A degree the cycle module does not carry silently produced
                    nothing before this counter existed. */}
                {overlayStats.dfr_unknown_degrees ? (
                  <p className="mt-1 text-[11px] leading-relaxed text-accent">
                    {overlayStats.dfr_unknown_degrees} of the degrees picked have
                    no quarters on this window, so they drew nothing.
                  </p>
                ) : null}
              </div>
            ) : null}
          </>
        );

      case "expectation":
        return (
          <>
            <Toggle
              label="Expected path line"
              value={params.expectation.show_path}
              onChange={(v) => onParams("expectation", { show_path: v })}
            />
            <Note>
              The fan is a measurement of resolved R and is on with the layer. The
              path is the median forward move of this symbol drawn as one line,
              and it is off by default because a lone line reads as a forecast,
              and this engine does not forecast - it draws the median historical
              trajectory, labelled as such. One R is one ATR, the plan&apos;s own
              stop scale. The path counts BARS, so it is measured and drawn on
              the 1h chart only; on any other timeframe the backend sends none
              rather than stretching a four-day median across one day.
            </Note>
          </>
        );

      case "wyckoff":
        return (
          <>
            <Slider
              label="Trading range width"
              hint="Bars in the rolling range a phase is read against."
              note="20 is a chosen number, not a measured one - the Wyckoff method names no window, so this is stated rather than fitted."
              suffix="bars"
              min={5}
              max={200}
              step={5}
              value={params.wyckoff.lookback}
              onChange={(v) => onParams("wyckoff", { lookback: v })}
            />
            <Note>
              Spring, upthrust, sign of strength and weakness over a rolling
              trading range. The full Wyckoff schematic needs volume and
              discretion, so only these four determinable readings are here - and
              they map onto the structure primitives (sweep, break) that this
              project already measured null. A reading, never a bias.
            </Note>
          </>
        );

      default:
        return null;
    }
  }

  // Which `params` blocks the menu has already drawn. The four imbalance
  // detectors name the same block, and it belongs under the first of them that
  // is on - not four times.
  const drawn = new Set<string>();
  const menu = config?.layers ?? [];
  // Whatever kinds the server sent, in the order it sent them. NOT a list of
  // three typed here: a new kind groups itself.
  const kinds = [...new Set(menu.map((l) => l.kind))];

  // Every LIVE detector's counters, found by the layer's own registry id because
  // that is the key the backend writes them under. Driven by `config.layers` for
  // the same reason the menu is: a detector added to the engine gets its trace
  // here without an edit, and the five ids stay out of this file.
  const detectors = menu.filter((layer) => layer.kind === "detector" && on(layer.id));
  const traces = detectors.flatMap((layer) => {
    const stats = meta?.[layer.id] as Record<string, number> | undefined;
    return stats ? [{ layer, stats }] : [];
  });

  return (
    <div className="scroll-thin flex h-full flex-col overflow-y-auto">
      {/* WHICH BAR ALL OF THIS DESCRIBES, and only when that is no longer the
          current one. Above the menu rather than inside a layer's knobs, because
          it is true of every drawing on the chart at once. Shown only past a
          whole bar of lag: a feed a few seconds behind its own close is normal,
          and a banner that is always up is read as furniture. */}
      {/* Sticky, because this panel scrolls and the warning is about every
          drawing in it: a reader four groups down is exactly the one who has
          forgotten which bar the numbers came from. `bg-panel`, the rail's own
          opaque background, rather than the translucent accent wash the banner
          below uses - controls scrolling under a see-through warning read as
          both at once. */}
      {step > 0 && lag > step ? (
        <p className="sticky top-0 z-10 border-b border-accent/40 bg-panel px-3 py-2 text-[11px] leading-relaxed text-accent">
          The newest bar closed <span className="num">{elapsed(lag)}</span> ago and
          one bar here is <span className="num">{elapsed(step)}</span>, so
          everything below describes that bar rather than the price now.
        </p>
      ) : null}

      {/* FIRST IN THE RAIL, above every drawing knob, because it is the only
          control here that spends money. Everything below it changes what is
          drawn; this one changes whether a daemon acts on it. It owns its own
          polling rather than taking props, so the Toolbox's contract stays about
          layers and this stays about the account. */}
      <AutoTradePanel />

      {menu.length === 0 ? (
        <Group title="Layers">
          <Note>Waiting for the engine&apos;s layer registry.</Note>
        </Group>
      ) : null}

      {layers.length === 0 && menu.length ? (
        <p className="border-b border-accent/40 bg-accent/10 px-3 py-2 text-[11px] leading-relaxed text-accent">
          No layer is on, so the chart is candles only. That is a valid view and
          not a failure - switch one on below.
        </p>
      ) : null}

      {/* PRESETS FIRST, above the seventeen toggles they exist to replace.
          Sixteen layers is a data advantage and a focus problem at the same
          time, and this is the honest way to solve the second: the reader picks
          a named set, the engine infers nothing. An automatic switch driven by
          the detected market phase would hide layers by inference, and a layer
          hidden by an inference cannot be told apart from a layer that found
          nothing - which is the one property this whole engine protects. */}
      {menu.length ? (
        <Presets
          layers={layers}
          params={params}
          onPreset={onPreset}
        />
      ) : null}

      {kinds.map((kind) => (
        // ponytail: `${kind}s` rather than a kind-to-heading map. Three kinds
        // ship and all three pluralise this way; a map would be one more list
        // that has to be edited when the backend grows a fourth.
        <Group key={kind} title={`${kind}s`}>
          {menu
            .filter((layer) => layer.kind === kind)
            .map((layer) => {
              const live = on(layer.id);
              const own = live && !drawn.has(layer.params) ? knobs(layer.params) : null;
              if (live) drawn.add(layer.params);
              return (
                <div
                  key={layer.id}
                  className={live ? "border-l border-accent/40 pl-2" : ""}
                >
                  <Toggle
                    label={layer.label}
                    value={live}
                    onChange={() => toggle(layer.id)}
                    swatch={LAYER_SWATCH[layer.id]}
                  />
                  <p className="mt-0.5 text-[11px] leading-relaxed text-text-dim">
                    {layer.note}
                  </p>
                  {/* EVERY row carries this, and the summary says "Bukti" rather
                      than "Apa ini" so the reader can tell there is a measurement
                      statement to read. Two of these layers came out
                      significantly NEGATIVE as direction claims and most have no
                      measurement at all; a row reduced to a bare switch would
                      present all thirteen as equally endorsed. */}
                  <Hint k={`layer.${layer.id}`} summary="Bukti" evidence={layer.evidence} />
                  {own ? <div className="mt-3 space-y-3">{own}</div> : null}
                </div>
              );
            })}
        </Group>
      ))}

      {/* ONE BLOCK PER LIVE DETECTOR. The counters on screen can outlive the run
          that produced them by one debounce, so a detector's block goes the
          moment it leaves the menu rather than standing as the last true count -
          and with no detector on at all the group says so instead of vanishing
          while the zone panel still points at it. */}
      <Group title="Filter trace" inert={!detectors.length && NO_TRACE}>
        {traces.length ? (
          <Hint
            k="trace"
            note="Why the chart looks the way it does. An empty chart and an over-filtered one are not the same problem."
          />
        ) : null}
        {traces.map(({ layer, stats }) => (
          <div
            key={layer.id}
            className="border-t border-line pt-2 first:border-0 first:pt-0"
          >
            <p className="mb-1 text-[11px] text-text-dim">{layer.label}</p>
            <Stat label="Formations found" value={stats.candidates} />
            {/* Whatever this detector rejected on, in the order it wrote the
                counters. Zeros stay: a gate that turned nothing away is a fact
                about this window, and dropping it would make the same gate look
                absent on one chart and present on the next. */}
            {Object.entries(stats)
              .filter(([key]) => key.startsWith("rejected_"))
              .map(([key, count]) => (
                <Stat
                  key={key}
                  label={TRACE_LABELS[key] ?? key.replace("rejected_", "").replace(/_/g, " ")}
                  value={count}
                  muted
                />
              ))}
            <div className="mt-2 border-t border-line pt-2">
              <Stat label="Drawn" value={stats.zones} strong />
            </div>
          </div>
        ))}
        {/* THE TOP-DOWN PASS, and it reports per layer now.
            Five box detectors can be read on a higher timeframe; before, only
            supply and demand was wired to it, so an HTF selection with any other
            detector on drew nothing and said nothing. Each row is that layer's
            own count from up there, so a reader can tell "no 4h gaps exist" from
            "the 4h pass never ran". */}
        {meta?.htf ? (
          <div className="border-t border-line pt-2">
            <p className="mb-1 text-[11px] text-text-dim">
              Higher timeframe {meta.htf.interval ?? ""}
            </p>
            {meta.htf.note ? (
              <p className="text-[11px] leading-relaxed text-accent">{meta.htf.note}</p>
            ) : null}
            {Object.entries(meta.htf.layers ?? {}).map(([id, stats]) => {
              /* From the registry, like every other label in this panel, so a
                 detector added to the engine names itself here too. */
              const label =
                menu.find((l) => l.id === id)?.label ?? id.replace(/_/g, " ");
              /* A COUNT AND A REASON ARE NOT THE SAME KIND OF THING, so they do
                 not share a row. `Stat` is numeric on purpose - forcing "not
                 enough higher-timeframe bars in this window" into the slot that
                 usually holds 7 would make prose read as a measurement. */
              return typeof stats.zones === "number" ? (
                <Stat key={id} label={label} value={stats.zones} muted />
              ) : (
                <p key={id} className="text-[11px] leading-relaxed text-text-dim">
                  {label}: {String(stats.note ?? stats.error ?? "nothing reported")}
                </p>
              );
            })}
            {/* Refinement is supply and demand's alone: `refine.py` shrinks a box
                to the pause inside it, and a fair value gap has no base to shrink
                to. */}
            {(() => {
              const sd = meta.htf.layers?.supply_demand;
              if (typeof sd?.refine_candidates !== "number") return null;
              const count = (key: string) =>
                typeof sd[key] === "number" ? (sd[key] as number) : undefined;
              return (
                <div className="mt-2 border-t border-line pt-2">
                  <Stat label="Refined" value={count("refined")} muted />
                  <Stat label="No inner base" value={count("refine_no_inner_base")} muted />
                  <Stat label="Already tight" value={count("refine_no_gain")} muted />
                </div>
              );
            })()}
          </div>
        ) : null}
      </Group>

      <div className="mt-auto flex flex-col gap-2 border-t border-line p-3">
        <button
          onClick={onReset}
          className="w-full border border-line-strong px-3 py-2 text-[11px] uppercase tracking-wider text-text-dim transition-colors hover:border-accent hover:text-accent"
        >
          Reset parameters
        </button>
        {/* Twelve sliders and only two of them are backed by evidence. That is
            not something a hint under each control can say, so the handbook
            says it, and the link sits under the panel it explains. */}
        <Link
          href="/docs"
          className="w-full border border-line px-3 py-2 text-center text-[11px] uppercase tracking-wider text-text-faint transition-colors hover:border-accent hover:text-accent"
        >
          Buku panduan
        </Link>
      </div>
    </div>
  );
});

/** The one line under a control that is NOT folded away.
 *
 *  The bar for one of these is that a reader who never opens a disclosure would
 *  otherwise trust the drawing wrongly. Everything else is reference material
 *  and lives behind "Apa ini".
 *
 *  It used to be twelve of these, always open, and at 1000px roughly 40% of the
 *  panel was prose - the reader scrolled past explanations to reach the next
 *  control, which is the definition of an essay with sliders in it. */
/** The preset row: shipped sets, saved sets, and a box to add one.
 *
 *  ACTIVE IS COMPUTED, NOT REMEMBERED. A preset is highlighted when the layers
 *  currently on are exactly its own - so toggling one layer afterwards drops the
 *  highlight, which is true. Storing "the last preset clicked" would leave a set
 *  looking active after the reader had changed it, and then the highlight would
 *  be describing history rather than the chart. */
function Presets({
  layers,
  params,
  onPreset,
}: {
  layers: string[];
  params: LayerParams;
  onPreset: (layers: string[], params: LayerParams) => void;
}) {
  const [name, setName] = useState("");

  // READ THROUGH THE STORE, not copied into state on mount. `localStorage` does
  // not exist during the server render, and pulling it in with an effect is the
  // hydration mismatch `react-hooks/set-state-in-effect` refuses - see the long
  // note in `lib/presets.ts`. This also picks up a write from another tab.
  const saved = useSyncExternalStore(
    subscribeSaved,
    savedSnapshot,
    savedServerSnapshot,
  );

  const all = [...PRESETS, ...saved];
  const same = (a: string[]) =>
    a.length === layers.length && a.every((l) => layers.includes(l));
  const active = all.find((p) => same(p.layers)) ?? null;

  return (
    <Group title="Presets">
      <div className="flex flex-wrap gap-1">
        {all.map((preset) => (
          <button
            key={preset.id}
            type="button"
            aria-pressed={active?.id === preset.id}
            onClick={() => {
              const next = applyPreset(preset, params);
              onPreset(next.layers, next.params);
            }}
            className={`border px-1.5 py-0.5 text-[11px] transition-colors ${
              active?.id === preset.id
                ? "border-accent text-accent"
                : "border-line-strong text-text-faint hover:text-text-dim"
            }`}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {active ? (
        <p className="text-[11px] leading-relaxed text-text-faint">{active.note}</p>
      ) : (
        <p className="text-[11px] leading-relaxed text-text-faint">
          {layers.length} layer{layers.length === 1 ? "" : "s"} on, matching no
          preset. Name it below to keep this set.
        </p>
      )}

      <div className="flex gap-1">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="name this set"
          aria-label="Preset name"
          className="min-w-0 flex-1 border border-line-strong bg-transparent px-1.5 py-0.5 text-[11px] text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
        />
        <button
          type="button"
          disabled={!name.trim()}
          onClick={() => {
            // The store notifies its own subscribers, so nothing local needs
            // setting: the row re-renders because the store changed, not because
            // this handler told it to.
            saveCurrent(name, layers, params);
            setName("");
          }}
          className="border border-line-strong px-1.5 py-0.5 text-[11px] text-text-faint transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
        >
          Save
        </button>
      </div>

      {saved.length ? (
        <div className="flex flex-wrap gap-1">
          {saved.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => removeSaved(preset.label)}
              className="border border-line px-1.5 py-0.5 text-[11px] text-text-faint transition-colors hover:border-supply hover:text-supply"
            >
              forget {preset.label}
            </button>
          ))}
        </div>
      ) : null}

      <Note>
        A preset sets which layers are on and the minimum each needs to draw
        anything - three of the seventeen are deliberately empty by default and
        would otherwise switch on and show nothing. It never touches a threshold
        you have tuned, and it never decides anything from the market.
      </Note>
    </Group>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] leading-relaxed text-text-dim">{children}</p>
  );
}

/** A span of seconds, coarse on purpose. The one reading taken off it is whether
 *  the chart is worth trusting right now, and "3531 seconds" answers that no
 *  better than "59m" while being harder to read at a glance. */
function elapsed(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return `${seconds}s`;
  if (minutes < 120) return `${minutes}m`;
  return `${Math.round(minutes / 60)}h`;
}

function Group({
  title,
  inert,
  children,
}: {
  title: string;
  /** Why this group cannot do anything right now. A `fieldset` rather than a
   *  class, because greying controls out while they still take the keyboard is
   *  the same lie in a quieter colour. */
  inert?: string | false;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-line px-3 py-3">
      <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
        {title}
      </h3>
      {inert ? (
        <p className="mb-3 border-l border-line-strong pl-2 text-[11px] leading-relaxed text-text-faint">
          {inert}
        </p>
      ) : null}
      <fieldset
        disabled={Boolean(inert)}
        className={`space-y-3 ${inert ? "opacity-40" : ""}`}
      >
        {children}
      </fieldset>
    </section>
  );
}

function Slider({
  label,
  hint,
  note,
  evidence,
  flag,
  suffix,
  min,
  max,
  step,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  note?: string;
  evidence?: string;
  /** The rare line that stays visible. See `Note`. */
  flag?: string;
  suffix?: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <label className="block">
        <div className="mb-1 flex items-baseline justify-between gap-2">
          <span className="text-[12px] text-text-dim">{label}</span>
          <span className="num text-[12px] text-text">
            {step < 1 ? value.toFixed(2) : value}
            {suffix ? <span className="ml-1 text-text-faint">{suffix}</span> : null}
          </span>
        </div>
        {/* NAMED EXPLICITLY, because without this the accessible name is
            computed from the wrapping label - which carries the live VALUE, so
            the control announced itself as "Impulse size 1.00 ATR" and its own
            NAME changed on every drag. A range input already publishes its value
            through `aria-valuenow`; the name is meant to be the stable half.
            It also makes the control addressable: `getByRole("slider", { name })`
            survives a value change, where an index into
            `input[type="range"]` does not - and an index is what broke
            `e2e/sweep.mjs` once already when a picker was inserted above it. */}
        <input
          type="range"
          aria-label={label}
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-1 w-full cursor-pointer appearance-none rounded bg-line-strong"
        />
      </label>
      {flag ? (
        <div className="mt-1">
          <Note>{flag}</Note>
        </div>
      ) : null}
      <Hint k={label} hint={hint} note={note} evidence={evidence} />
    </div>
  );
}

const OPEN_KEY = "zonelab.hint.";

/** Everything a control has to say, on demand: what it does, why it ships the
 *  way it does, and what was measured.
 *
 *  These used to be `title` attributes, which is a tooltip on a mouse and
 *  nothing at all on a phone or a keyboard - the hint was invisible to everyone
 *  who most needed it. `details` is focusable, operable with Enter, and taps
 *  open on touch.
 *
 *  The prose that used to sit UNDER each control, always open, now lives in here
 *  too. It is the reason to trust a knob and none of it is deleted; it is simply
 *  no longer the default reading. Which ones the reader opened is remembered for
 *  the tab, because progressive disclosure that re-folds on every reload just
 *  makes the same person hunt for the same paragraph every session. */
function Hint({
  k,
  hint,
  note,
  evidence,
  summary = "Apa ini",
}: {
  /** Storage key. Unique on this panel. */
  k: string;
  hint?: string;
  note?: string;
  evidence?: string;
  /** What the fold says it holds. Layer rows say "Bukti", because on those the
   *  content is a measurement result rather than a description, and several of
   *  those results are negative. */
  summary?: string;
}) {
  const ref = useRef<HTMLDetailsElement>(null);

  // Restored onto the DOM node after mount, not held in React state. The server
  // has no sessionStorage, so a first paint driven by it is a hydration error
  // rather than a preference - and `details` already owns this bit of state, so
  // mirroring it into React would be a second copy to keep in sync.
  useEffect(() => {
    if (ref.current) {
      ref.current.open = sessionStorage.getItem(OPEN_KEY + k) === "1";
    }
  }, [k]);

  if (!hint && !note && !evidence) return null;

  return (
    <details
      ref={ref}
      className="mt-1"
      onToggle={(e) =>
        sessionStorage.setItem(OPEN_KEY + k, e.currentTarget.open ? "1" : "0")
      }
    >
      <summary className="w-fit cursor-pointer text-[11px] text-text-faint transition-colors hover:text-text-dim">
        {summary}
      </summary>
      {hint ? <Prose>{hint}</Prose> : null}
      {note ? <Prose>{note}</Prose> : null}
      {/* Brighter, and labelled. Most of the knobs here are unmeasured and two
          are not, and a panel that does not say which is which invites the user
          to trust them equally. This marker used to be a gold left border, which
          spent the accent on a value: the accent now means "the setting you
          chose" and nothing else. */}
      {evidence ? (
        <Prose bright>
          <span className="mr-1.5 uppercase tracking-[0.12em] text-text-faint">
            Diukur
          </span>
          {evidence}
        </Prose>
      ) : null}
    </details>
  );
}

function Prose({
  children,
  bright,
}: {
  children: React.ReactNode;
  bright?: boolean;
}) {
  return (
    <p
      className={`mt-1 border-l border-line-strong pl-2 text-[11px] leading-relaxed ${
        bright ? "text-text-dim" : "text-text-faint"
      }`}
    >
      {children}
    </p>
  );
}

/** A multi-select over the seven cycle degrees.
 *
 *  Chips rather than seven toggles or a multi-select box, because the degrees are
 *  a nested SCALE - year contains month contains week - and reading them in
 *  order left to right is how the method itself talks about them. A vertical
 *  stack of switches would lose that ordering, and a native multi-select hides
 *  the choice behind a click. */
function Degrees({
  label,
  selected,
  onChange,
}: {
  label: string;
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div>
      <div className="mb-1 text-[12px] text-text-dim">{label}</div>
      <div className="flex flex-wrap gap-1" role="group" aria-label={label}>
        {DEGREES.map((degree) => {
          const on = selected.includes(degree);
          return (
            <button
              key={degree}
              type="button"
              aria-pressed={on}
              onClick={() =>
                onChange(
                  on ? selected.filter((d) => d !== degree) : [...selected, degree],
                )
              }
              className={`border px-1.5 py-0.5 text-[11px] transition-colors ${
                on
                  ? "border-accent text-accent"
                  : "border-line-strong text-text-faint hover:text-text-dim"
              }`}
            >
              {degree}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** His four bias timeframes, in his own checking order.
 *
 *  Fixed rather than free-form: his rule names Daily, H4, H1 and M15 and reads
 *  them in that order, the Daily first because it is the one that decides whether
 *  the others are being checked for continuation or for a reversal. Offering
 *  every interval would invite a set nobody has a rule for. */
const BIAS_TIMEFRAMES = ["1d", "4h", "1h", "15m"] as const;

/** A generic chip row. `Degrees` and `Timeframes` are the same widget over fixed
 *  vocabularies; this one takes its options from the server, so a symbol added to
 *  the registry shows up here without an edit. */
function Chips({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  if (!options.length) return null;
  return (
    <div>
      <div className="mb-1 text-[12px] text-text-dim">{label}</div>
      <div className="flex flex-wrap gap-1" role="group" aria-label={label}>
        {options.map((option) => {
          const on = selected.includes(option);
          return (
            <button
              key={option}
              type="button"
              aria-pressed={on}
              onClick={() =>
                onChange(
                  on ? selected.filter((s) => s !== option) : [...selected, option],
                )
              }
              className={`num border px-1.5 py-0.5 text-[11px] transition-colors ${
                on
                  ? "border-accent text-accent"
                  : "border-line-strong text-text-faint hover:text-text-dim"
              }`}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Timeframes({
  label,
  selected,
  onChange,
}: {
  label: string;
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div>
      <div className="mb-1 text-[12px] text-text-dim">{label}</div>
      <div className="flex flex-wrap gap-1" role="group" aria-label={label}>
        {BIAS_TIMEFRAMES.map((tf) => {
          const on = selected.includes(tf);
          return (
            <button
              key={tf}
              type="button"
              aria-pressed={on}
              onClick={() =>
                onChange(
                  on
                    ? selected.filter((t) => t !== tf)
                    : BIAS_TIMEFRAMES.filter((t) => t === tf || selected.includes(t)),
                )
              }
              className={`num border px-1.5 py-0.5 text-[11px] transition-colors ${
                on
                  ? "border-accent text-accent"
                  : "border-line-strong text-text-faint hover:text-text-dim"
              }`}
            >
              {tf}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** ALWAYS carries `aria-label`, and never any inner text. The switch is a button
 *  whose only content is a sliding span, so `innerText` is empty and the name
 *  lives entirely in the label - an end-to-end crawler that matched on visible
 *  text alone silently skipped every one of these and still reported 97 of 97. */
function Toggle({
  label,
  value,
  onChange,
  swatch,
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  /** CSS colours this layer actually draws in, newest-family first. Shown as a
   *  bar beside the name so the palette is documented where the layer is
   *  switched on, rather than in a legend nobody opens. Two colours for the box
   *  detectors, because they draw two: demand and supply are the one place in
   *  this app where colour carries meaning rather than identity. */
  swatch?: readonly string[];
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-2">
      <span className="flex min-w-0 items-center gap-1.5">
        {swatch?.length ? (
          <span
            aria-hidden
            className="flex h-2.5 w-2.5 shrink-0 flex-col overflow-hidden rounded-[1px]"
          >
            {swatch.map((c) => (
              <span key={c} className="flex-1" style={{ backgroundColor: c }} />
            ))}
          </span>
        ) : null}
        <span className="truncate text-[12px] text-text-dim">{label}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        aria-label={label}
        onClick={() => onChange(!value)}
        className={`h-4 w-8 shrink-0 border transition-colors ${
          value ? "border-accent bg-accent/25" : "border-line-strong bg-transparent"
        }`}
      >
        <span
          className={`block h-3 w-3 transition-transform ${
            value ? "translate-x-4 bg-accent" : "translate-x-0.5 bg-text-faint"
          }`}
        />
      </button>
    </label>
  );
}

/** Which ink each layer draws in, for the swatch beside its switch.
 *
 *  Keyed by layer id and kept beside the menu that renders it, because it is a
 *  fact about the CANVAS and the canvas states it in `components/ink.ts`. The
 *  five box detectors share the demand/supply pair - the two colours that mean
 *  something - and `checklist` has no entry at all because it draws nothing; a
 *  swatch on a report would be a promise of ink that never arrives. */
const LAYER_SWATCH: Record<string, readonly string[]> = {
  supply_demand: ["var(--demand)", "var(--supply)"],
  fvg: ["var(--demand)", "var(--supply)"],
  order_block: ["var(--demand)", "var(--supply)"],
  ifvg: ["var(--demand)", "var(--supply)"],
  breaker: ["var(--demand)", "var(--supply)"],
  structure: [ink("structure", 0.95)],
  session: [ink("grid", 0.95)],
  gaps: [ink("levels", 0.95)],
  cisd: [ink("levels", 0.95)],
  pools: [ink("levels", 0.95)],
  liquidity: [ink("levels", 0.95)],
  vortex: [ink("grid", 0.72)],
  projections: [ink("levels", 0.95)],
  ssmt: [ink("ssmt", 0.95)],
  dfr: [ink("dfr", 0.95)],
  expectation: [ink("levels", 0.95)],
  chart_gaps: [ink("levels", 0.95)],
  wyckoff: [ink("structure", 0.85)],
  news: ["var(--accent)"],
};

function Segmented({
  label,
  hint,
  note,
  value,
  options,
  onChange,
}: {
  label: string;
  hint?: string;
  note?: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <div className="mb-1 text-[12px] text-text-dim">{label}</div>
      <div className="flex border border-line-strong">
        {options.map(([id, text]) => (
          <button
            key={id}
            onClick={() => onChange(id)}
            aria-pressed={value === id}
            className={`flex-1 px-2 py-1 text-[11px] transition-colors ${
              value === id
                ? "bg-accent/15 text-accent"
                : "text-text-faint hover:text-text-dim"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
      <Hint k={label} hint={hint} note={note} />
    </div>
  );
}

function Stat({
  label,
  value,
  muted,
  strong,
}: {
  label: string;
  value: number | undefined;
  muted?: boolean;
  strong?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-0.5">
      <span
        className={`text-[12px] ${muted ? "text-text-faint" : strong ? "text-text" : "text-text-dim"}`}
      >
        {label}
      </span>
      <span
        className={`num text-[12px] ${strong ? "text-accent" : muted ? "text-text-faint" : "text-text-dim"}`}
      >
        {value ?? 0}
      </span>
    </div>
  );
}
