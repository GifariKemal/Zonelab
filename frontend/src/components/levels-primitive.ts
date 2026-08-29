import type {
  IChartApi,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
} from "lightweight-charts";
import type { CanvasRenderingTarget2D } from "fancy-canvas";

import type {
  CISDEvent,
  EventHorizonLevel,
  GapStack,
  LiquidityPool,
  NamedLevel,
  OpeningGap,
  RangeProjection,
  TierHorizon,
} from "@/lib/types";
import { LABEL_GUTTER, claimedLabels, labelFree } from "./structure-primitive";
import { INKS } from "./ink";

/**
 * Four price-anchored overlays in one primitive: opening gaps, event horizons,
 * CISD levels and liquidity pools.
 *
 * ONE FILE because they are one visual family. The cycle grid next door is
 * anchored to TIME - a quarter box has no price - while every object here is a
 * price the reader is meant to compare against the candles. Splitting them into
 * four primitives would give four independent label-collision maps, and the
 * labels are the only thing that types these objects apart, because colour
 * deliberately does not.
 *
 * THE DESIGN COMES FROM THE OWNER'S OWN 51 ANNOTATED CHARTS, the same reading
 * that decided the cycle grid:
 *
 * 1. A NAMED HORIZONTAL RAY WITH ITS LABEL AT THE RIGHT EDGE is on 24 of 24 of
 *    his price charts. So event horizons and pools are named rays, and the name
 *    is not decoration - it is the only thing distinguishing an EH from an Asian
 *    high, and he reads by label.
 * 2. A SHADED BOX WITH A DASHED MIDLINE is on 23 of 25. So an opening gap is a
 *    band that draws its own midline, and that midline is the consequent
 *    encroachment: a real measurement in the doctrine rather than a decoration.
 *    The geometry his charts already use happens to be exactly the right one.
 * 3. COLOUR CANNOT TYPE THE OBJECT, which is his inconsistency and not a
 *    preference of mine - pink means a session box on some charts and a quarter
 *    box on others. One neutral ink here, which also keeps green and red
 *    reserved for the only thing they are allowed to mean.
 *
 * AND NOTHING HERE IS A SIGNAL. Twelve pre-registered directional hypotheses
 * have failed in this project. No arrows, no fills that read as buy or sell. A
 * CISD's `direction` decides which side of its own level the tick sits on and
 * nothing else.
 *
 * INK BUDGET. The chart is a measured quantity here: five detectors already paint
 * 31.6% of it, and past roughly a third boxes stop annotating price and become
 * the background. So these four are off by default, every fill is under 0.05,
 * and a gap band is the only filled shape - the other three are single strokes.
 */

/** Neutral, matching the structure overlay rather than the quieter grid: these
 *  are events and levels, not context. */
const INK = INKS.levels;

function ink(alpha: number): string {
  return `rgba(${INK[0]}, ${INK[1]}, ${INK[2]}, ${alpha})`;
}

/**
 * THE TWO ALPHAS EVERYTHING HERE IS DRAWN AT, and they are contrast floors
 * rather than taste.
 *
 * Measured as WCAG contrast of this ink composited over #0b0d10: 0.30 is
 * 1.82:1, 0.50 is 3.03:1, 0.60 is 3.87:1, 0.85 is 6.74:1, 1.00 is 9.02:1.
 *
 * THIS FILE WAS UNDERSTATING ITSELF. The line above used to read 1.60 / 2.45 /
 * 3.02 / 4.96 / 6.49, which were the ratios of the grey-blue every primitive
 * held its own copy of. `ink.ts` gave the levels family the brightest rung of
 * its L* ladder, rgb(137, 183, 207), on the argument that named price rays are
 * the objects a reader compares a candle against - so every figure here went UP
 * and the comment kept quoting the dimmer ink. Recomputed, the two tiers in use
 * are 6.74:1 for the standing line and 3.87:1 for the faded one, and the labels
 * that sit on them are 9.02:1 and 6.08:1. Every one clears its floor, and the
 * two labels clear 4.5:1 for small text with room to spare.
 *
 * The old alphas are kept above because the argument for moving them was made
 * against those numbers: the standing tier used to be 0.70 line / 0.95 label and
 * the faded tier 0.30 line / 0.50 label, which put the faded LINE at 1.82:1 -
 * under the ratio at which a 1px stroke is visible at all once the room has any
 * light in it - and the faded LABEL at 3.03:1, which fails AA for 10px text.
 *
 * "Faded" has to keep meaning something, because a taken pool is history and
 * history is why an idea is dead. It still does: 6.74 against 3.87 is a factor
 * of 1.74 in contrast, which is a plainly visible step. What it no longer means
 * is "gone".
 */
const STANDING = { line: 0.85, label: 1 };
const FADED = { line: 0.6, label: 0.8 };

/** Padding a label's COLLISION RECT spends, in CSS pixels.
 *
 *  The whole pad, not half of it: the rect is `{x: gutter, w: text + LABEL_PAD}`
 *  and it has to fit inside `LABEL_GUTTER`, while the TEXT is drawn at half the
 *  pad in from the gutter. Getting that wrong by two pixels is what let an
 *  8-character name claim 48px of a 46px column, and `e2e/labels.mjs` fails such
 *  a claim as one the pane edge cuts in half. The same arithmetic is asserted from
 *  Python in `test_every_level_name_fits_the_canvas_label_column`, which reads
 *  `LABEL_GUTTER` out of this codebase rather than restating it. */
const LABEL_PAD = 4;

/** His own vocabulary, short enough to sit beside a price axis. */
const POOL_TAG: Record<string, string> = { asia: "AS", london: "LDN" };

interface GapBand {
  gap: OpeningGap;
  x: number;
  yTop: number;
  yBottom: number;
  yCe: number;
}

/** A gap stack: the OVERLAP of two gaps of different kinds, and how much of the
 *  smaller band it covers.
 *
 *  Adopted from the reference indicator, which renders it as `EV STACK W+D` with
 *  a percentage - and it was computed and shipped on every gaps response for a
 *  while with nothing on the frontend able to read it. `grep gap_stacks
 *  frontend/src` returned nothing at all: the backend was measuring a construct
 *  the chart could not show.
 *
 *  The tag carries no kind letters, unlike the reference. There are exactly two
 *  gap kinds here, NDOG and NWOG, and a stack requires them to differ - so
 *  "W+D" is the only pair that can ever occur and printing it would be spending
 *  three characters to say nothing. */
interface Stack {
  x: number;
  yTop: number;
  yBottom: number;
  tag: string;
}

interface Ray {
  y: number;
  x: number;
  tag: string;
  /** Dimmed rather than hidden: a taken pool is history, and history is why an
   *  idea is dead. */
  faded: boolean;
  dashed: boolean;
}

/** A projection level: a SHORT segment beside its own range rather than a ray.
 *  His own geometry on image 27, and the reason two stacks can sit on one chart
 *  without either reading as a standing level. */
interface Segment {
  x1: number;
  x2: number;
  y: number;
  tag: string;
  faded: boolean;
}

interface CisdMark {
  event: CISDEvent;
  x1: number;
  x2: number;
  y: number;
}

/**
 * One name per label ROW, with coincident names joined by a slash.
 *
 * WHAT THIS REPLACES. Every ray drew its own name and the collision map dropped
 * any that overlapped one already claimed. So two levels a few points apart both
 * drew a line and only one kept its name - and in a file whose own docstring says
 * the label is the only thing that types these objects apart, a nameless ray is
 * one the reader cannot identify. The reference charts join them instead: `PDH/PWH`
 * is one row of ink carrying two facts.
 *
 * BOUNDED BY THE COLUMN, not by a character count typed here. `LABEL_GUTTER` is
 * how wide the name column is and the text is drawn left-aligned from it with no
 * clamp, so anything wider is cut off by the edge of the canvas - silently, which
 * is the defect four shipped level names had. Tags are added while the MEASURED
 * width still fits, and whatever is left over becomes `+n` if that fits too.
 * A merged label that would not fit at all keeps just the first tag.
 *
 * Returns a map from index in `rays` to the label that index should draw, with no
 * entry for a ray whose name went into a neighbour's. Every ray still draws its
 * LINE either way; this decides only who writes the name.
 */
function mergedTags(
  rays: readonly Ray[],
  ctx: CanvasRenderingContext2D,
  ky: number,
  budget: number,
): Map<number, string> {
  // One label row, which is the same 12px box the collision rects use.
  const row = 12 * ky;
  const order = rays
    .map((ray, index) => ({ ray, index }))
    .sort((a, b) => a.ray.y - b.ray.y);

  const out = new Map<number, string>();
  let group: { ray: Ray; index: number }[] = [];

  const flush = () => {
    if (!group.length) return;
    // The FIRST tag always survives, so a group can never end up nameless.
    let text = group[0].ray.tag;
    let taken = 1;
    for (const member of group.slice(1)) {
      const candidate = `${text}/${member.ray.tag}`;
      if (ctx.measureText(candidate).width > budget) break;
      text = candidate;
      taken += 1;
    }
    const left = group.length - taken;
    if (left > 0) {
      const withCount = `${text}+${left}`;
      // `+n` is worth a tag's worth of room only if it fits; a reader who cannot
      // see it is no worse off than before, and an overflowing one is worse.
      if (ctx.measureText(withCount).width <= budget) text = withCount;
    }
    out.set(group[0].index, text);
    group = [];
  };

  for (const entry of order) {
    if (group.length && Math.abs(entry.ray.y - group[0].ray.y) * ky >= row) flush();
    group.push(entry);
  }
  flush();
  return out;
}


class LevelsRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly bands: readonly GapBand[],
    private readonly stacks: readonly Stack[],
    private readonly rays: readonly Ray[],
    private readonly marks: readonly CisdMark[],
    private readonly segments: readonly Segment[],
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const width = scope.bitmapSize.width;
      const height = scope.bitmapSize.height;

      ctx.save();
      ctx.font = `${Math.round(10 * ky)}px ui-monospace, monospace`;
      ctx.textBaseline = "middle";
      const stroke = Math.max(1, Math.round(kx));
      // The right-hand column that belongs to names. EVERY horizontal line in
      // this file stops here, including the gap band's own frame and midline,
      // which used to run to `width` and therefore straight through whatever
      // name sat at that price. See LABEL_GUTTER.
      const gutter = width - LABEL_GUTTER * kx;

      // --- opening gaps: a band, extended right, with its midline -------------
      for (const band of this.bands) {
        const left = Math.round(band.x * kx);
        const top = Math.round(band.yTop * ky);
        const bottom = Math.round(band.yBottom * ky);
        const height = Math.max(1, bottom - top);

        ctx.fillStyle = ink(0.045);
        ctx.fillRect(left, top, Math.max(0, width - left), height);

        // AN APPROXIMATE BAND GETS A DASHED FRAME. The flag is not a footnote:
        // read off 4-hour bars, the edge is the nearest price the feed could
        // offer and not the last price that traded before 17:00, so the band is
        // in the right neighbourhood and its edges are not the definition's. A
        // solid frame would claim a precision the bars cannot support.
        ctx.setLineDash(band.gap.approximate ? [3 * kx, 3 * kx] : []);
        ctx.strokeStyle = ink(band.gap.approximate ? FADED.line : STANDING.line);
        ctx.lineWidth = stroke;
        ctx.beginPath();
        ctx.moveTo(left, top + 0.5);
        ctx.lineTo(gutter, top + 0.5);
        ctx.moveTo(left, bottom + 0.5);
        ctx.lineTo(gutter, bottom + 0.5);
        ctx.stroke();

        // The consequent encroachment. Dashed, and the same visual move the
        // quarter box makes with its own 50% for the same reason: the midline is
        // the measurement, the frame is only the container.
        const ce = Math.round(band.yCe * ky) + 0.5;
        ctx.setLineDash([2 * kx, 4 * kx]);
        ctx.strokeStyle = ink(STANDING.line);
        ctx.beginPath();
        ctx.moveTo(left, ce);
        ctx.lineTo(gutter, ce);
        ctx.stroke();
        ctx.setLineDash([]);

        // The label sits at the band's own left edge, not at the right, because
        // unlike a ray a gap has a birthplace worth pointing at.
        //
        // AND IT IS NEVER SUPPRESSED FOR BEING TOO THIN, which the first version
        // did. Most real opening gaps are small - five NDOGs on 15m gold measured
        // 0.2 to 2.2 points against a 140-point screen - so the "only label a
        // band tall enough to hold it" rule silently unlabelled almost all of
        // them, and an unlabelled band is unreadable here BY DESIGN: colour
        // deliberately types nothing, so the tag is the only thing separating a
        // gap from the event-horizon lines beside it. A thin band puts its tag
        // just above its top edge instead.
        const tag = band.gap.kind + (band.gap.approximate ? "~" : "");
        const tw = ctx.measureText(tag).width;
        const pad = 3 * kx;
        const roomy = height > 14 * ky;
        const ly = roomy ? ce : top - 7 * ky;
        // Clamped to the viewport. A gap formed before the leftmost visible bar
        // still paints its band across the whole screen, but its birthplace is
        // off-canvas - so an unclamped label drew at a negative x and vanished,
        // leaving exactly the widest, most prominent bands unnamed.
        const lx = Math.max(left, 0) + pad;
        const rect = { x: lx, y: ly - 6 * ky, w: tw + pad, h: 12 * ky };
        if (labelFree(rect, claimedLabels)) {
          claimedLabels.push(rect);
          // A plate, for the same reason the structure captions have one: this
          // tag sits at the band's birthplace, which is on top of the candles
          // that made it, and grey text on a candle body is not quiet, it is
          // unreadable.
          ctx.fillStyle = "rgba(11, 13, 16, 0.85)";
          ctx.fillRect(rect.x - 2 * kx, rect.y, rect.w + 2 * kx, rect.h);
          ctx.fillStyle = ink(STANDING.label);
          ctx.fillText(tag, lx, ly);
        }
      }

      // --- gap stacks: the overlap of two gaps, framed and named --------------
      //
      // AFTER the bands, so it draws over them, and framed on all four sides
      // rather than extended right: a stack is a REGION where two gaps agree,
      // and a ray to the edge would claim the agreement continues past the point
      // where one of the two bands ends. No fill - the two bands underneath
      // already supply two washes at 0.045, and a third would put the stack at
      // the ink budget's ceiling for the one thing that is meant to stand out.
      for (const stack of this.stacks) {
        const left = Math.round(stack.x * kx);
        const top = Math.round(stack.yTop * ky);
        const bottom = Math.round(stack.yBottom * ky);
        const right = Math.min(gutter, left + 90 * kx);
        ctx.setLineDash([]);
        ctx.strokeStyle = ink(STANDING.line);
        ctx.lineWidth = stroke;
        ctx.strokeRect(left, top, Math.max(1, right - left), Math.max(1, bottom - top));

        const tw = ctx.measureText(stack.tag).width;
        const pad = 3 * kx;
        const lx = Math.max(left, 0) + pad;
        // Below the frame, not inside it: the overlap is by definition the
        // thinnest of the three bands on this price, and a tag inside it would
        // sit on the very edges the frame is drawing.
        const ly = bottom + 8 * ky;
        const rect = { x: lx, y: ly - 6 * ky, w: tw + pad, h: 12 * ky };
        if (labelFree(rect, claimedLabels)) {
          claimedLabels.push(rect);
          ctx.fillStyle = "rgba(11, 13, 16, 0.85)";
          ctx.fillRect(rect.x - 2 * kx, rect.y, rect.w + 2 * kx, rect.h);
          ctx.fillStyle = ink(STANDING.label);
          ctx.fillText(stack.tag, lx, ly);
        }
      }

      // --- event horizons and pools: named rays to the right edge -------------
      //
      // COINCIDENT NAMES ARE MERGED, and they used to be DROPPED. Two levels at
      // nearly the same price both drew their line and only one kept its name,
      // because the second label lost the collision test and was skipped. In a
      // file whose own docstring says the label is the only thing that types these
      // objects, that leaves a ray a reader cannot identify - and a nameless ray
      // is indistinguishable from a ray that should not be there. The reference
      // charts join them with a slash instead, which is one row of ink for two
      // facts, and this does the same.
      // THE BUDGET IS THE COLUMN, not the chart. This was `gutter - 4 * kx`,
      // which is the whole width up TO the column rather than the column itself -
      // a few hundred pixels instead of forty - so the merge accepted names far
      // too wide and the canvas edge cut them mid-word: `RNG H/PD`, `PDH/MON`,
      // `AS L/RNG`. Caught by looking at a screenshot after writing it. The label
      // is drawn at `gutter + pad / 2`, so what is actually available is the
      // gutter minus that offset.
      const merged = mergedTags(this.rays, ctx, ky, (LABEL_GUTTER - LABEL_PAD) * kx);
      for (const [index, ray] of this.rays.entries()) {
        const tag = merged.get(index);
        // A ray whose name went into a neighbour's merged label still draws its
        // line; it just does not draw a second name for the same row.
        const y = Math.round(ray.y * ky) + 0.5;
        const x = Math.round(ray.x * kx);
        const tw = tag ? ctx.measureText(tag).width : 0;
        const pad = LABEL_PAD * kx;
        // ONE stop for every ray, not one per tag. Per-tag stops are what let a
        // short-tagged ray outrun a long-tagged one and print through its name.
        const stop = gutter;
        const alpha = ray.faded ? FADED.line : STANDING.line;

        ctx.setLineDash(ray.dashed ? [4 * kx, 3 * kx] : []);
        ctx.strokeStyle = ink(alpha);
        ctx.lineWidth = stroke;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(Math.max(x, stop), y);
        ctx.stroke();
        ctx.setLineDash([]);

        if (!tag) continue;
        // CLAMPED INTO THE PANE VERTICALLY, the same fix the horizontal clamp
        // already carried and for the same reason. A ray whose price sits within
        // half a row of the pane floor drew its name half below it: measured at
        // eleven layers on a 724px pane, a claim at y 723.5 with a 12px row ran to
        // 735.5. Half a word is unreadable and the reader cannot tell which half
        // is missing, so `e2e/labels.mjs` fails exactly this - it caught it here.
        //
        // The label moves rather than the line. A name sitting half a row above
        // its own ray still names that ray; a name cut by the pane edge names
        // nothing. Same trade the zone caption makes when its box starts
        // off-screen to the left.
        const half = 6 * ky;
        const ty = Math.min(Math.max(y, half), height - half);
        const rect = { x: stop, y: ty - half, w: tw + pad, h: 12 * ky };
        if (labelFree(rect, claimedLabels)) {
          claimedLabels.push(rect);
          ctx.fillStyle = ink(ray.faded ? FADED.label : STANDING.label);
          ctx.fillText(tag, stop + pad / 2, ty);
        }
      }

      // --- deviation projections: short segments with their multiple ----------
      for (const seg of this.segments) {
        const y = Math.round(seg.y * ky) + 0.5;
        const x1 = Math.round(seg.x1 * kx);
        // Kept out of the name column like everything else, and the label with
        // it. A projection stack sits beside its own range, which on a live
        // chart is the right-hand end - so without this clamp it is exactly the
        // stack that lands in the gutter and prints over the ray names.
        const tw = ctx.measureText(seg.tag).width;
        const x2 = Math.min(Math.round(seg.x2 * kx), gutter - tw - 6 * kx);
        if (x2 <= x1) continue;
        const alpha = seg.faded ? FADED.line : STANDING.line;

        ctx.strokeStyle = ink(alpha);
        ctx.lineWidth = stroke;
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();

        // The number is the object. An unlabelled segment here is
        // indistinguishable from a CISD level, and the whole point of the stack
        // is reading which multiple price stopped at.
        //
        // A PLATE UNDER IT, which it did not have. These segments are short and
        // they land inside whatever zone fill is at that price, so "-1.5" was
        // being painted grey-on-green at 0.6 alpha: present in the bitmap and
        // not readable by anyone. Visible in
        // `.playwright-shots/colour-before/04-zoom40.png` at the FVG box.
        const rect = { x: x2 + 3 * kx, y: y - 6 * ky, w: tw + 3 * kx, h: 12 * ky };
        if (labelFree(rect, claimedLabels)) {
          claimedLabels.push(rect);
          ctx.fillStyle = "rgba(11, 13, 16, 0.85)";
          ctx.fillRect(rect.x - 2 * kx, rect.y, rect.w + 2 * kx, rect.h);
          ctx.fillStyle = ink(seg.faded ? FADED.label : STANDING.label);
          ctx.fillText(seg.tag, x2 + 3 * kx, y);
        }
      }

      // --- CISD: the run's own level, and a tick on the bar that broke it -----
      for (const mark of this.marks) {
        const y = Math.round(mark.y * ky) + 0.5;
        const x1 = Math.round(mark.x1 * kx);
        const x2 = Math.round(mark.x2 * kx);

        // Bounded to the run rather than extended right, and that is the whole
        // point of drawing it this way: the level is the open of the run's FIRST
        // candle, so a segment spanning the run shows WHICH run armed it. A ray
        // running off to the right would look like a standing level and hide the
        // one fact most implementations get wrong.
        ctx.strokeStyle = ink(STANDING.line);
        ctx.lineWidth = stroke;
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();

        // A tick on the breaking bar, on the side the close landed. Not an
        // arrow: an arrow is a direction claim and this project has eleven of
        // those already refuted.
        const reach = 5 * ky * (mark.event.direction > 0 ? -1 : 1);
        ctx.beginPath();
        ctx.moveTo(x2, y);
        ctx.lineTo(x2, y + reach);
        ctx.stroke();
      }

      ctx.restore();
    });
  }
}

/**
 * Attached after the cycle grid and before the zone primitive. These are levels
 * to compare candles against, so they must sit above the grid's context wash and
 * below a zone border whose position is verified to the pixel.
 */
export class LevelsSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private gaps: readonly OpeningGap[] = [];
  private horizons: readonly EventHorizonLevel[] = [];
  private pools: readonly LiquidityPool[] = [];
  private events: readonly CISDEvent[] = [];
  private named: readonly NamedLevel[] = [];
  private stacks: readonly RangeProjection[] = [];
  private tiers: readonly TierHorizon[] = [];
  private gapStacks: readonly GapStack[] = [];

  private bands: GapBand[] = [];
  private stackBoxes: Stack[] = [];
  private rays: Ray[] = [];
  private marks: CisdMark[] = [];
  private segments: Segment[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      zOrder: () => "normal",
      renderer: () =>
        new LevelsRenderer(
          this.bands,
          this.stackBoxes,
          this.rays,
          this.marks,
          this.segments,
        ),
    },
  ];

  attached(param: SeriesAttachedParameter<Time>): void {
    this.chart = param.chart;
    this.series = param.series as ISeriesApi<"Candlestick", Time>;
    this.requestUpdate = param.requestUpdate;
  }

  detached(): void {
    this.chart = null;
    this.series = null;
    this.requestUpdate = null;
    this.bands = [];
    this.stackBoxes = [];
    this.rays = [];
    this.marks = [];
    this.segments = [];
  }

  setLevels(
    gaps: readonly OpeningGap[],
    horizons: readonly EventHorizonLevel[],
    pools: readonly LiquidityPool[],
    events: readonly CISDEvent[],
    named: readonly NamedLevel[],
    stacks: readonly RangeProjection[],
    tiers: readonly TierHorizon[],
    gapStacks: readonly GapStack[],
  ): void {
    this.gaps = gaps;
    this.horizons = horizons;
    this.pools = pools;
    this.events = events;
    this.named = named;
    this.stacks = stacks;
    this.tiers = tiers;
    this.gapStacks = gapStacks;
    this.requestUpdate?.();
  }

  /** Recomputed on every pan, zoom and data change. A cached pixel position is a
   *  level detached from the price it describes. */
  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    if (!chart || !series) {
      this.bands = [];
      this.stackBoxes = [];
      this.rays = [];
      this.marks = [];
      this.segments = [];
      this.tiers = [];
      return;
    }
    const scale = chart.timeScale();

    // Push loops rather than map-then-filter throughout. `timeToCoordinate` and
    // `priceToCoordinate` return a branded `Coordinate`, and a type predicate
    // over the nullable union does not narrow back to the plain `number` these
    // interfaces declare - the compiler is right about that.
    this.bands = [];
    for (const gap of this.gaps) {
      const x = scale.timeToCoordinate(gap.close_time as Time);
      const yTop = series.priceToCoordinate(gap.top);
      const yBottom = series.priceToCoordinate(gap.bottom);
      const yCe = series.priceToCoordinate(gap.ce);
      if (x !== null && yTop !== null && yBottom !== null && yCe !== null) {
        this.bands.push({ gap, x, yTop, yBottom, yCe });
      }
    }

    // Anchored at the LATER of the two gaps, because that is when the stack
    // became knowable - the field the model carries for exactly this reason.
    this.stackBoxes = [];
    for (const stack of this.gapStacks) {
      const x = scale.timeToCoordinate(stack.knowable_at as Time);
      const yTop = series.priceToCoordinate(stack.top);
      const yBottom = series.priceToCoordinate(stack.bottom);
      if (x === null || yTop === null || yBottom === null) continue;
      this.stackBoxes.push({
        x,
        yTop,
        yBottom,
        tag: `STACK ${Math.round(stack.fraction * 100)}%`,
      });
    }

    this.rays = [];
    for (const level of this.horizons) {
      const x = scale.timeToCoordinate(level.knowable_at as Time);
      const y = series.priceToCoordinate(level.price);
      if (x !== null && y !== null) {
        this.rays.push({ x, y, tag: "EH", faded: false, dashed: false });
      }
    }
    for (const pool of this.pools) {
      // From the bar that proved the session closed, which is where the level
      // becomes knowable. Drawing it from the window's start would put ink on
      // bars that could not have known it yet.
      const x = scale.timeToCoordinate(pool.knowable_at as Time);
      const y = series.priceToCoordinate(pool.price);
      if (x === null || y === null) continue;
      const side = pool.side === "BSL" ? "H" : "L";
      // A partial window earns a question mark rather than a silent level: its
      // high is not the session high, and the tag is where a reader will look.
      const tag = `${POOL_TAG[pool.session] ?? pool.session} ${side}${pool.covered ? "" : "?"}`;
      this.rays.push({ x, y, tag, faded: pool.taken_at !== null, dashed: !pool.covered });
    }

    // Named previous-period levels join the SAME ray family as the pools, on
    // purpose: PDH and the Asian high are the same kind of object in his method,
    // and giving them two shapes would invent a distinction he does not make.
    //
    // THE DEALING-RANGE FRAME CLAIMS ITS NAMES FIRST, and this ordering is the
    // fix for a real defect rather than a preference. The label column is a
    // shared collision map and the first claim wins, so with the frame appended
    // last it lost every tie - and the line that lost was the EQUILIBRIUM,
    // measured on a live gold chart: its dashed line drew at 4428 with no name at
    // all, because a previous day high sat six points above it and had already
    // claimed the row. Five lines that frame the whole window outrank up to
    // sixteen period extremes, and the equilibrium is the one a reader is reading
    // premium and discount against.
    //
    // `boundary === "range"` is the right predicate HERE even though it was the
    // wrong one for dashing: this is a question about which range object a level
    // belongs to, which is exactly what `boundary` says, rather than a question
    // about whether its price was printed or computed.
    const named = [
      ...this.named.filter((l) => l.boundary === "range"),
      ...this.named.filter((l) => l.boundary !== "range"),
    ];
    for (const level of named) {
      const x = scale.timeToCoordinate(level.knowable_at as Time);
      const y = series.priceToCoordinate(level.price);
      if (x === null || y === null) continue;
      this.rays.push({
        x,
        y,
        tag: level.name,
        faded: level.taken_at !== null,
        // DASHED WHERE THE LEVEL IS DERIVED RATHER THAN PRINTED. A previous day
        // high is a price the market actually traded and where orders rest; a
        // dealing range's equilibrium is arithmetic on two of those. The reference
        // set draws exactly this line: a dashed 50% inside a range appears on 36 of
        // its 51 charts while the named period extremes are solid.
        //
        // Read off `derived` and NOT off `boundary === "range"`, which was the
        // first version of this and was wrong: the range's own high and low carry
        // `range` too, and they are printed prices. `boundary` means which day
        // boundary the period was measured on, and giving it a second meaning here
        // would have dashed two lines that should be solid.
        dashed: level.derived,
      });
    }

    // The deviation stacks. Short segments rather than rays, and that is his own
    // geometry: on image 27 they sit BESIDE the range they came from rather than
    // running across the chart, which is what lets two stacks coexist without
    // either being mistaken for a standing level.
    this.segments = [];
    for (const stack of this.stacks) {
      const x1 = scale.timeToCoordinate(stack.time_from as Time);
      const x2 = scale.timeToCoordinate(stack.time_to as Time);
      if (x1 === null || x2 === null) continue;
      const span = Math.max(28, x2 - x1);
      for (const level of stack.levels) {
        const y = series.priceToCoordinate(level.price);
        if (y === null) continue;
        this.segments.push({
          x1: x2,
          x2: x2 + span,
          y,
          tag: String(level.multiple),
          faded: level.taken_at !== null,
        });
      }
    }

    // One zone per kind, drawn as two edges and a dashed midpoint - the same
    // shape a gap band uses, because a tier IS a gap band at a coarser degree.
    // Labelled with the kind and the reduction that made it, because the
    // reduction is unresolved and a band whose rule is unstated would read as
    // settled when it is not.
    for (const tier of this.tiers) {
      const yTop = series.priceToCoordinate(tier.top);
      const yBottom = series.priceToCoordinate(tier.bottom);
      const yCe = series.priceToCoordinate(tier.ce);
      const x = scale.timeToCoordinate(tier.knowable_at as Time);
      if (yTop === null || yBottom === null || yCe === null) continue;
      const short = tier.kind === "NDOG" ? "D" : "W";
      this.rays.push({
        x: x ?? 0, y: yTop, tag: `EV-${short}`, faded: false, dashed: true,
      });
      this.rays.push({
        x: x ?? 0, y: yBottom, tag: `EV-${short}`, faded: true, dashed: true,
      });
      this.rays.push({
        x: x ?? 0, y: yCe, tag: `CE-${short}`, faded: true, dashed: true,
      });
    }

    this.marks = [];
    for (const event of this.events) {
      const x1 = scale.timeToCoordinate(event.run_from as Time);
      const x2 = scale.timeToCoordinate(event.time as Time);
      const y = series.priceToCoordinate(event.level);
      if (x1 !== null && x2 !== null && y !== null) {
        this.marks.push({ event, x1, x2, y });
      }
    }
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
