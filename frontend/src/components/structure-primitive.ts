import type { CanvasRenderingTarget2D } from "fancy-canvas";
import type {
  IChartApi,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
} from "lightweight-charts";

import type { StructureEvent, StructureScale, SwingPoint } from "@/lib/types";
import { INKS } from "./ink";

/**
 * Market structure, drawn as annotation and never as a call.
 *
 * This is an OVERLAY, not a detector: it paints no boxes, so it is not capped
 * per side and it does not belong in the detector toggles. It exists for
 * FIDELITY - ICT puts directional bias in structure and uses zones only to
 * refine the entry, so a chart that cannot show structure at two scales cannot
 * show the method at all.
 *
 * The direction claim itself was tested and died twice. H6 took BOS, CHoCH and
 * SWEEP as three separate cohorts and none survived; H9 took the
 * sweep-then-MSS conjunction drawn here at t = -0.79 and -0.12 against a
 * pre-registered bar of 3.0, with the sign REVERSING between halves. So there
 * are no arrows in this file, no bias badge, and no colour that means "up".
 * Everything is one neutral ink, because red and green already mean "demand"
 * and "supply" on this canvas and lending them to structure would smuggle a
 * forecast in through the palette.
 *
 * WHY IT IS ATTACHED BEFORE THE ZONE PRIMITIVE. Both draw at `normal` z-order,
 * which the library paints after the candles, and within one z-order pass it
 * paints primitives in attach order. Attaching this one first means zone
 * borders and captions paint OVER structure rather than under it. That is not
 * cosmetic: `e2e/pixel-truth.mjs` reads those borders back off the bitmap and
 * asserts all of them are legible, and coverage went from 0.909 to 1.000 by
 * getting the border above the candles. Structure ink laid on top would undo
 * that measurement with a line the harness cannot even see the colour of.
 */

/** One ink for everything here. `--text-dim`, the colour the rest of the UI
 *  uses for "secondary text", which is what structure is on this chart. */
const INK = INKS.structure;

/** The two fractal widths must not read alike, or the crossing the backend just
 *  built is invisible. Three properties differ at once - stroke width, alpha and
 *  type size - because any one of them alone survives a bad monitor.
 *
 *  BOTH ROWS WERE RAISED, and the minor one was raised a long way, because
 *  "quiet" had gone past quiet into invisible. Measured against #0b0d10 as WCAG
 *  contrast: the minor line at 0.26 came out at 1.57:1 and its caption at 0.50
 *  came out at 2.77:1. 1.57:1 is below the ratio at which a 1px line can be seen
 *  at all on a desk with any ambient light, and 2.77:1 fails AA for 9px text by
 *  a wide margin. The numbers now are 3.11:1 for the minor line, 5.36:1 for its
 *  caption, 5.87:1 for the major line and 7.18:1 for its caption - every one of
 *  them over the 3:1 floor for a graphical object, and both captions over the
 *  4.5:1 floor for small text.
 *
 *  The separation the two scales exist for survives that: 5.87 against 3.11 is
 *  still close to a factor of two in contrast, on top of a 1.5x stroke width and
 *  a 10px against 9px type size. What changed is that the small one is now a
 *  quiet line rather than a rumour of one.
 *
 *  The plates went up with them for a reason the old comment already stated
 *  without following through: a caption's contrast is against WHAT IS BEHIND IT,
 *  and at plate 0.5 what is behind it is half a candle. A plate that does not
 *  reach the background makes the measured text ratio a fiction. */
const SCALE: Record<
  StructureScale,
  { line: number; alpha: number; text: number; font: number; plate: number; mark: number }
> = {
  swing: { line: 1.5, alpha: 0.85, text: 1, font: 10, plate: 0.92, mark: 3 },
  internal: { line: 1, alpha: 0.55, text: 0.8, font: 9, plate: 0.85, mark: 1.5 },
};

/** Below this a label has no room to be read, so it is dropped rather than
 *  overprinted. Same guard, same number as the zone caption's own width test. */
const LABEL_MIN_WIDTH = 34;

interface LabelRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Where the structure captions ended up, in bitmap pixels, PUBLISHED for the
 * zone primitive to route around.
 *
 * It has to be one list across both files. Each primitive resolving only its own
 * collisions is a fix that looks finished in each file and is visibly broken on
 * the chart: "SWEEP back in 1" printed straight through "RBD unsettled" in the
 * top right of the five-detector screenshot.
 *
 * STRUCTURE CLAIMS FIRST and zones yield, which is the right way round: a
 * structure label is anchored to the bar that broke and cannot move without
 * pointing at a different bar, while a zone caption already has a documented
 * fallback of walking upward and then being dropped.
 *
 * Rewritten at the start of every pass of THIS renderer rather than emptied by
 * the zone one, and that is not tidiness. The library keeps two canvases: the
 * pane (bottom, series, normal) and the top layer. Moving the crosshair repaints
 * the top layer ALONE, so the zone caption pass runs on frames where this one
 * does not - and a list the zone pass emptied would then be empty exactly when
 * the structure captions are still on screen, so captions would jump onto them
 * for as long as the mouse kept moving. Publishing from the pass that owns the
 * ink keeps the two in step whichever canvas repaints.
 */
export const claimedLabels: LabelRect[] = [];

/**
 * Emptied ONCE PER FRAME, by the FIRST pass that draws - which is the cycle
 * grid, not this file.
 *
 * It used to be emptied here, at the top of this renderer, and that was wrong by
 * one whole z-order. The library paints `bottom` views, then the series, then
 * `normal`, then `top`; the primitives are attached session, levels, structure,
 * zone. So the real order per frame is: session (bottom) claims its true opens
 * and its news marks - and this file then THREW THOSE AWAY - levels (normal,
 * attached before this one) claims its rays and gap tags, and this file threw
 * those away too. Everything downstream saw a list holding structure captions
 * and nothing else, which is why a zone caption printed straight over "PDH" and
 * over "DBR unsettled" in the five-layer screenshot while never once colliding
 * with a "CHoCH".
 *
 * Measured on XAUUSD 15m at 500 bars with nine layers on: 98 price-anchored
 * horizontal objects on screen, 86 neighbouring pairs closer than 12px and 27
 * closer than 1px. At that density a label map that discards three quarters of
 * its own entries is not a collision map at all.
 *
 * The reset stays a function rather than moving to a `useEffect` or a frame
 * counter because the pass that goes first is a fact about ATTACH ORDER, and
 * attach order is stated in one place - `chart.tsx` - where a reader can see it.
 * Called from `session-primitive.ts`, which is that first pass, and which draws
 * every frame whether or not the grid is switched on.
 */
export function resetLabels(): void {
  // No guard here, and the reason is worth writing down because the obvious one
  // does not work. A non-empty list at this point looks like "somebody claimed
  // before the frame's first pass" - the attach-order bug that made the DFR tags
  // invisible to the map for one commit - but it is also exactly what a HEALTHY
  // frame looks like, because the list is never emptied at the END of a frame:
  // at the top of frame N it always holds frame N-1's claims. The two states are
  // indistinguishable from here, and a warning that fires on every frame is
  // worse than none. Catching it needs a single claim entry point that can ask
  // whether the reset has run yet, and there is no such function - each pass
  // pushes onto the list directly. `e2e/labels.mjs` catches it instead, by
  // differencing the claim count against a run with the layer switched off.
  claimedLabels.length = 0;
}

/**
 * How much of the right edge belongs to ray names rather than to ray lines, in
 * CSS pixels.
 *
 * ONE gutter for every pass, which is the whole point. Each renderer used to
 * stop its own ray at `width - measureText(itsOwnTag) - padding`, so a ray with
 * a short tag stopped further right than a ray with a long one - and any ray
 * whose label lost the collision test still drew its line to that stop. The
 * result is in `.playwright-shots/colour-before/02-zoom80.png`: the dashed tier
 * ray at 4418 runs clean through the "AS H" it collided with, and "CE-D" and
 * "NDOG" are struck through the same way. A line through a name is worse than
 * either object alone, because the reader cannot tell which of the two is lying.
 *
 * 46 rather than a measured-per-frame maximum, and it is sized from a
 * measurement rather than chosen: the tags these two files can produce are at
 * most six characters ("LDN L?", "T90mO", "EV-D", "NWOG"), and 10px
 * ui-monospace measures 5.5px per character on this machine - 33px, plus 8px of
 * padding on the two sides. A per-frame maximum would move the whole column
 * every time a pool went partial, and a column that moves is a column the eye
 * has to find again.
 */
export const LABEL_GUTTER = 46;

export function labelFree(box: LabelRect, placed: readonly LabelRect[]): boolean {
  return !placed.some(
    (p) => box.x < p.x + p.w && p.x < box.x + box.w && box.y < p.y + p.h && p.y < box.y + box.h,
  );
}

function ink(alpha: number): string {
  return `rgba(${INK[0]}, ${INK[1]}, ${INK[2]}, ${alpha})`;
}

/** What a structure event says, in words, with no claim about what comes next.
 *
 *  A sweep carries its own qualifier because `reversed_within` is the whole
 *  difference between liquidity taken and liquidity taken AND rejected, and the
 *  sources only describe the second one as a sweep. Null there is not a missing
 *  number: it is price never closing back inside, which is the case the doctrine
 *  does not actually cover. */
function caption(event: StructureEvent): string {
  if (event.kind !== "SWEEP") return event.kind;
  return event.reversed_within === null
    ? "SWEEP unrejected"
    : `SWEEP back in ${event.reversed_within}`;
}

interface Segment {
  event: StructureEvent;
  /** Where the level line starts: the swing that gave way, or for an MSS the
   *  sweep that qualified it. */
  x1: number;
  /** The bar that broke or swept. */
  x2: number;
  y: number;
}

interface Pivot {
  swing: SwingPoint;
  x: number;
  y: number;
  /** x of `confirmed_at`, which is LATER than x. Null when that bar is not on
   *  the loaded series. */
  confirmedX: number | null;
}

class StructureRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly segments: readonly Segment[],
    private readonly pivots: readonly Pivot[],
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const width = scope.bitmapSize.width;

      // Pivots first, so a level line crossing one stays readable over it.
      for (const pivot of this.pivots) {
        const s = SCALE[pivot.swing.scale];
        const x = Math.round(pivot.x * kx);
        const y = Math.round(pivot.y * ky);

        // A swing high at bar i is not knowable at bar i. The leader runs from
        // the pivot to the bar it became knowable on, which is the one thing
        // that keeps this overlay from reading as hindsight - a marker with no
        // leader silently claims the pivot was available the moment it printed.
        // Major scale only: at 50-odd internal pivots per screen these lines
        // become a hairball, and the hover readout carries `confirmed_at` for
        // every pivot regardless of scale.
        if (pivot.swing.scale === "swing" && pivot.confirmedX !== null) {
          ctx.save();
          ctx.strokeStyle = ink(0.3);
          ctx.lineWidth = 1 * ky;
          ctx.setLineDash([1 * kx, 3 * kx]);
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(Math.round(pivot.confirmedX * kx), y);
          ctx.stroke();
          ctx.restore();
        }

        ctx.save();
        ctx.strokeStyle = ink(s.alpha + 0.15);
        ctx.lineWidth = 1 * ky;
        // Hollow for the major scale, a filled dot for the minor. A pivot is a
        // price, so the marker sits ON the price rather than beside the bar.
        if (pivot.swing.scale === "swing") {
          ctx.strokeRect(x - s.mark * kx, y - s.mark * ky, 2 * s.mark * kx, 2 * s.mark * ky);
        } else {
          ctx.fillStyle = ink(s.alpha + 0.15);
          ctx.fillRect(x - s.mark * kx, y - s.mark * ky, 2 * s.mark * kx, 2 * s.mark * ky);
        }
        ctx.restore();
      }

      // Lines first, every one of them, then labels. Two passes because a label
      // may have to move to stay readable and a level line may not: the line is
      // a price and moving it would be a drawing that lies, while a caption is
      // free to sit anywhere near the thing it names.
      for (const segment of this.segments) {
        const { event } = segment;
        const s = SCALE[event.scale];
        const y = Math.round(segment.y * ky) + 0.5;
        const x1 = Math.round(segment.x1 * kx);
        const x2 = Math.round(segment.x2 * kx);

        ctx.save();
        ctx.strokeStyle = ink(s.alpha);
        ctx.lineWidth = s.line * ky;
        // A sweep is not a break and must not look like one: a break is a CLOSE
        // beyond the level, a sweep is a wick through it. Dashing is the whole
        // distinction, because merging the two is exactly the failure the
        // backend's own docstring warns the detector cannot recover from.
        if (event.kind === "SWEEP") ctx.setLineDash([3 * kx, 3 * kx]);
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
        ctx.restore();

        // The bar that broke or swept, marked across the level so the event can
        // be told from the line that leads to it.
        ctx.save();
        ctx.strokeStyle = ink(Math.min(1, s.alpha + 0.2));
        ctx.lineWidth = s.line * ky;
        ctx.beginPath();
        ctx.moveTo(x2, y - (s.mark + 2) * ky);
        ctx.lineTo(x2, y + (s.mark + 2) * ky);
        ctx.stroke();
        ctx.restore();
      }

      // Boxes already claimed, in bitmap pixels. A first version stacked labels
      // only when two events shared a BAR - which is the MSS case - and left
      // events on nearby bars at similar prices to overprint each other. A crop
      // of the result read "GWEEP back in 1": a sweep and a CHoCH four bars
      // apart, garbled into one unreadable word. Collision is the general case
      // and the same-bar case falls out of it, so there is one mechanism here
      // rather than two - and since `claimedLabels`, one list across both
      // primitives rather than one each. NOT emptied here any more: this pass is
      // third of four, so emptying it here discarded the cycle grid's claims and
      // the levels overlay's claims before anything could route around them. See
      // `resetLabels`, which the first pass of the frame calls.
      const placed = claimedLabels;
      const free = (box: LabelRect) => labelFree(box, placed);

      // Major scale claims its space FIRST. When the pane runs out of room it has
      // to be the minor scale that loses the caption, because the whole point of
      // running two widths is that the large one is the structure and the small
      // one is the refinement.
      const ordered = [
        ...this.segments.filter((s) => s.event.scale === "swing"),
        ...this.segments.filter((s) => s.event.scale === "internal"),
      ];

      for (const segment of ordered) {
        const { event } = segment;
        const s = SCALE[event.scale];
        const y = Math.round(segment.y * ky) + 0.5;
        const x1 = Math.round(segment.x1 * kx);
        const x2 = Math.round(segment.x2 * kx);
        if (x2 - x1 < LABEL_MIN_WIDTH) continue;
        // WHOLLY OFF-PANE SEGMENTS ARE SKIPPED, not clamped. The clamp below is
        // right for a segment that is PARTLY visible - the caption then sits at
        // the left end of the part a reader can see, the same thing a gap band's
        // tag does when its birthplace scrolled off. It is wrong for a segment
        // that is entirely off-screen: that caption would sit at the pane edge
        // naming a line nobody can see, and it would take a slot in the
        // collision map from a caption that IS visible.
        if (x2 <= 0 || x1 >= width) continue;

        ctx.save();
        ctx.font = `500 ${s.font * ky}px "IBM Plex Mono", ui-monospace, monospace`;
        ctx.textBaseline = "middle";

        const text = caption(event);
        const w = ctx.measureText(text).width + 6 * kx;
        const h = (s.font + 4) * ky;
        // CLAMPED TO THE PANE. `x1` is the break's own bar, and after a pan that
        // bar can sit off the left edge - so the caption was drawn at a negative
        // x and half a word is unreadable in a way a missing word is not. The
        // LAST unclamped claim site: the gap band's tag, the quarter box's label
        // and the SSMT tag all carry this already, and `e2e/labels.mjs` failed
        // this one as "SWEEP back in 1" hanging 12px past the edge.
        //
        // The offset it replaces was `x1 + 3 * kx - 3 * kx`, which is `x1` with
        // two steps that cancel - a leftover from moving the plate's padding into
        // `w`, and it read as a deliberate nudge that does nothing.
        const x = Math.min(Math.max(x1, 0), Math.max(width - w, 0));

        // Walked upward until the caption has room. Six steps is roughly 80px of
        // headroom, which covers an MSS sitting on the break it was carved from
        // plus a cluster of internal events at one level. Past that the caption
        // is DROPPED rather than overprinted: an unreadable word is worse than a
        // missing one, and the hover readout still names every event on the bar.
        let ty = y - 6 * ky - h / 2;
        let box = { x, y: ty - h / 2, w, h };
        for (let step = 0; step < 6 && !free(box); step++) {
          ty -= h;
          box = { x, y: ty - h / 2, w, h };
        }
        if (!free(box)) {
          ctx.restore();
          continue;
        }
        placed.push(box);

        // A plate on BOTH scales, weaker on the minor one. The minor scale first
        // shipped with no plate at all, to keep it quiet - and a crop showed why
        // that fails: grey text at half alpha over a green candle body is not
        // quiet, it is unreadable, and an unreadable caption is not restraint. So
        // the plate carries the quietness instead of the absence of one.
        ctx.fillStyle = `rgba(11, 13, 16, ${s.plate})`;
        ctx.fillRect(box.x, box.y, box.w, box.h);
        ctx.fillStyle = ink(s.text);
        ctx.fillText(text, x1 + 3 * kx, ty);
        ctx.restore();
      }
    });
  }
}

/**
 * Swings, breaks and sweeps on the candlestick series.
 *
 * Same shape as `ZoneSeriesPrimitive` on purpose, including recomputing every
 * coordinate in `updateAllViews`: the library calls that on every pan, zoom and
 * data change, and a cached pixel position is a level line detached from the
 * bar it describes.
 */
export class StructureSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;
  private swings: readonly SwingPoint[] = [];
  private events: readonly StructureEvent[] = [];
  private segments: Segment[] = [];
  private pivots: Pivot[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      // Above the candles, and - because this primitive is attached FIRST -
      // beneath the zone borders and captions that the pixel harness reads.
      zOrder: () => "normal",
      renderer: () => new StructureRenderer(this.segments, this.pivots),
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
    this.segments = [];
    this.pivots = [];
  }

  setStructure(swings: readonly SwingPoint[], events: readonly StructureEvent[]): void {
    this.swings = swings;
    this.events = events;
    this.requestUpdate?.();
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }

  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    if (!chart || !series) {
      this.segments = [];
      this.pivots = [];
      return;
    }

    const timeScale = chart.timeScale();

    this.pivots = this.swings.flatMap((swing) => {
      const x = timeScale.timeToCoordinate(swing.time as Time);
      const y = series.priceToCoordinate(swing.price);
      if (x === null || y === null) return [];
      return [{ swing, x, y, confirmedX: timeScale.timeToCoordinate(swing.confirmed_at as Time) }];
    });

    this.segments = this.events.flatMap((event) => {
      // An MSS is a break with a preceding opposite sweep, and it shares its bar
      // and its level with that break. Drawing a second identical line would be
      // ink for nothing, so the MSS line spans the PAIRING - sweep to break -
      // which is the one piece of geometry only it has.
      const from = event.kind === "MSS" && event.swept_at !== null ? event.swept_at : event.swing_time;
      const x1 = timeScale.timeToCoordinate(from as Time);
      const x2 = timeScale.timeToCoordinate(event.time as Time);
      const y = series.priceToCoordinate(event.level);
      if (x1 === null || x2 === null || y === null) return [];
      return [{ event, x1, x2, y }];
    });
  }
}
