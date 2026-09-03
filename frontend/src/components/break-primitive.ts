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

import type { Candle } from "@/lib/types";
import { ink, plateInk } from "./ink";
import { claimedLabels, labelFree, resetLabels } from "./structure-primitive";

/**
 * WHERE THE MARKET WAS SHUT. A vertical mark between two bars that are
 * neighbours on this axis and hours or days apart on the clock.
 *
 * THE DEFECT THIS EXISTS FOR. The time axis of this chart - of every
 * lightweight-charts chart - is indexed by BAR, not by time. So Friday's last
 * candle sits flush against Sunday's first, 49 hours vanish with no mark on the
 * screen, and the jump between them looks exactly like an ordinary
 * candle-to-candle move. Measured on MT5 gold to 2026-08-19, the last three
 * weekends jumped 29.2, 5.3 and 3.6 dollars across that invisible seam, against
 * a typical 15m range near 2. The owner reported it as "the drawing cannot show
 * the gap", and he was right twice over: the band was missing from the data for
 * short windows, and even with the band there was nothing on the axis to say a
 * weekend had happened.
 *
 * THIS IS NOT THE OPENING GAP, and the two must not be confused. An NDOG or
 * NWOG is a PRICE band with doctrine behind it, drawn by `levels-primitive`
 * and switched on with the gaps layer. This is a fact about the CLOCK: it says
 * only "no bar exists between these two", carries no direction and no claim,
 * and is therefore always on, like the axis labels. A chart that hides a
 * weekend is misreporting its own x axis.
 *
 * BREAKS ARE READ OFF THE BARS, not off a session calendar. A calendar would
 * have to know each broker's hours, each holiday and each feed outage; the bars
 * already carry the answer, and an outage is worth marking for the same reason
 * a weekend is.
 */

/** Below this many pixels of separation the marks stop being readable and start
 *  being a picket fence. Same reasoning as the ribbon's readability floor: at a
 *  zoom where 30 session breaks share 1000 pixels, drawing them all annotates
 *  nothing. The long breaks still draw - a weekend is worth a line at any zoom -
 *  and the one-hour daily ones drop out first. */
const CROWDED_PX = 26;

/** Four hours. Longer than any daily maintenance break and shorter than any
 *  weekend, so it separates "the broker rolled over" from "the market was shut
 *  for days" without needing a calendar. */
const LONG_BREAK = 4 * 3600;

interface BreakMark {
  x: number;
  /** Seconds of wall clock with no bar in them. */
  span: number;
  /** Close before the break against open after it. The number a trader wants. */
  jump: number;
  long: boolean;
}

function label(mark: BreakMark): string {
  const hours = mark.span / 3600;
  const when = hours >= 24 ? `${Math.round(hours / 24)}d` : `${Math.round(hours)}h`;
  const move = `${mark.jump >= 0 ? "+" : ""}${mark.jump.toFixed(2)}`;
  return `${when} ${move}`;
}

class BreakRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly marks: readonly BreakMark[],
    private readonly labelled: boolean,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const height = scope.bitmapSize.height;
      const width = scope.bitmapSize.width;

      // THE FRAME'S LABEL MAP STARTS HERE, because this pass is the frame's
      // first one. The library paints `bottom` views, then the series, then
      // `normal`, then `top`, and within one z-order pass it paints in ATTACH
      // ORDER - and `chart.tsx` attaches this primitive before every other,
      // ahead of the cycle grid it used to sit behind.
      //
      // It lived in `session-primitive.ts` until now, and that was wrong by one
      // pass in exactly the direction that hides itself: the weekend caption
      // below claimed its rectangle, the grid pass then ran `resetLabels` and
      // threw the claim away, and every later pass saw a list that had never
      // heard of it. The comment on that claim asserted the opposite - "attached
      // FIRST, so it claims before anyone else" - which is true about attach
      // order and false about the reset, and being attached first is precisely
      // what made it the victim. This is the DFR incident a second time, and the
      // codebase already documents that one twice.
      //
      // MOVED RATHER THAN REORDERED, and the choice matters. Attaching break
      // after the grid would fix the claim and change the picture: both draw at
      // `bottom`, so the clock marks would then paint over the quarter washes
      // instead of under them, and `e2e/pixel-truth.mjs` reads that pane back
      // off the bitmap. Having break claim later is not available either - it
      // has one pass and this is it. The reset belongs to whichever pass runs
      // first, so it follows the attach order rather than the attach order
      // bending to it.
      //
      // Unconditional, and this primitive is the right owner for that too: the
      // grid is a layer the reader switches off, while a chart that hides a
      // weekend is misreporting its own axis, so this one is always attached and
      // always draws. A frame can no longer start without its map being cleared.
      resetLabels();

      ctx.save();
      ctx.font = `${Math.round(9 * ky)}px ui-monospace, monospace`;
      ctx.textBaseline = "top";

      for (const mark of this.marks) {
        const x = Math.round(mark.x * kx);
        // A weekend earns a solid, brighter stroke; a rollover a faint dash.
        // Both stay well under the ink a zone border carries, because this is
        // context and a zone edge is a measurement.
        ctx.strokeStyle = mark.long
          ? ink("grid", 0.52)
          : ink("grid", 0.20);
        ctx.setLineDash(mark.long ? [] : [2 * ky, 4 * ky]);
        ctx.lineWidth = Math.max(1, Math.round(kx));
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();

        // Only the long ones are named, and only when they are not crowded. A
        // daily rollover happens every day and its label would be noise; a
        // weekend is the one a reader is looking for.
        if (mark.long && this.labelled) {
          ctx.setLineDash([]);
          const text = label(mark);
          const pad = Math.round(3 * kx);
          const w = ctx.measureText(text).width;
          // CLAIMED LIKE EVERY OTHER LABEL, and it was the only one that was
          // not. `e2e/labels.mjs` proves labels do not overlap by differencing
          // the shared claim list, so a caption that never enters the list is a
          // caption that harness is structurally unable to see: "intersections
          // zero" only ever meant zero among those that registered.
          //
          // This claim now SURVIVES the frame, which is a second thing from
          // being made. It is made first because this primitive is attached
          // first and paints at `bottom`; it survives because the reset above
          // runs in this same pass, ahead of it. Until that moved here the claim
          // was made and then wiped a few microseconds later by the grid, so the
          // list this checks against was always empty and every later pass drew
          // over the weekend caption as if it were not there.
          const plate = w + pad * 2;
          // OFF-PANE MARKS GET NO CAPTION, and marks near an edge get a clamped
          // one. Both halves of that became load-bearing the moment this claim
          // started surviving the frame, and neither could be seen before.
          //
          // The x axis is indexed by bar, so at 4h with 500 bars twelve of the
          // sixteen weekends in the window sit at a NEGATIVE x - measured, from
          // -1968 to 810 on a 1030px pane. A caption for one of those names a
          // line nobody can see and takes a slot in the collision map from a
          // caption that IS visible, which is the same argument
          // `structure-primitive.ts` already makes for skipping wholly off-pane
          // segments rather than clamping them.
          //
          // And a mark that lands between `-plate` and 0 straddles the edge, so
          // half the word is unreadable in the way a missing word is not -
          // `e2e/labels.mjs` fails exactly that shape. None of the sixteen
          // happened to land there, which is the kind of luck this project has
          // learnt not to leave a harness resting on.
          if (x < 0 || x > width) continue;
          const lx = Math.min(Math.max(x + pad, 0), Math.max(width - plate, 0));
          const rect = {
            x: lx,
            y: Math.round(2 * ky),
            w: plate,
            h: Math.round(12 * ky),
          };
          if (labelFree(rect, claimedLabels)) {
            claimedLabels.push(rect);
            ctx.fillStyle = plateInk(0.82);
            ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
            ctx.fillStyle = ink("grid", 0.95);
            // From the PLATE, not from the mark. The plate is what moved when
            // the clamp bit, and text drawn off its own plate is the defect
            // `structure-primitive.ts` carried for a release.
            ctx.fillText(text, rect.x + pad, Math.round(4 * ky));
          }
        }
      }
      ctx.restore();
    });
  }
}

export class BreakSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private candles: readonly Candle[] = [];
  private step = 0;
  private marks: BreakMark[] = [];
  private labelled = true;

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      // BENEATH the candles and everything price-anchored. It is context about
      // the clock; a mark that covered a wick would be answering a question
      // nobody asked with ink that belongs to the price.
      zOrder: () => "bottom",
      renderer: () => new BreakRenderer(this.marks, this.labelled),
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
    this.marks = [];
  }

  /** A break is any pair of adjacent bars further apart than one interval, and
   *  the interval is READ OFF THE BARS rather than passed in.
   *
   *  Deriving it here avoids a second interval table in the frontend that would
   *  have to be kept in step with `INTERVALS` in the backend, and it is the same
   *  method `app/gaps.py` uses to decide whether an instrument ever closes - the
   *  smallest spacing present IS the grid, because a break can only ever make
   *  two bars further apart, never closer. */
  setBreaks(candles: readonly Candle[]): void {
    this.candles = candles;
    let step = 0;
    for (let i = 1; i < candles.length; i += 1) {
      const d = candles[i].time - candles[i - 1].time;
      if (d > 0 && (step === 0 || d < step)) step = d;
    }
    this.step = step;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const chart = this.chart;
    if (!chart || this.step <= 0 || this.candles.length < 2) {
      this.marks = [];
      return;
    }
    const scale = chart.timeScale();

    const found: BreakMark[] = [];
    for (let i = 1; i < this.candles.length; i += 1) {
      const before = this.candles[i - 1];
      const after = this.candles[i];
      const span = after.time - before.time;
      if (span <= this.step) continue;
      const a = scale.timeToCoordinate(before.time as Time);
      const b = scale.timeToCoordinate(after.time as Time);
      // Both ends must resolve. Clamping an unresolved edge to the pane border
      // is how the ribbon once painted a wash of false segments across the whole
      // panel; a break with no position is simply not drawn.
      if (a === null || b === null) continue;
      found.push({
        x: (a + b) / 2,
        span,
        jump: after.open - before.close,
        long: span >= LONG_BREAK,
      });
    }

    // Decided once for the whole pane from the CLOSEST pair, never per mark:
    // per-mark would label some weekends and not their neighbours, which reads
    // as missing data rather than as a zoom too tight for text.
    const gaps: number[] = [];
    for (let i = 1; i < found.length; i += 1) gaps.push(found[i].x - found[i - 1].x);
    this.labelled = gaps.length === 0 || Math.min(...gaps) >= CROWDED_PX;
    this.marks = found;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
