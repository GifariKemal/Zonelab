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
import { ink } from "./ink";
import { claimedLabels, labelFree } from "./structure-primitive";

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
          // zero" only ever meant zero among those that registered. This
          // primitive is attached FIRST and paints at `bottom`, so it claims
          // before anyone else and a later pass now moves out of its way.
          const rect = {
            x: x + pad,
            y: Math.round(2 * ky),
            w: w + pad * 2,
            h: Math.round(12 * ky),
          };
          if (labelFree(rect, claimedLabels)) {
            claimedLabels.push(rect);
            ctx.fillStyle = "rgba(11, 13, 16, 0.82)";
            ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
            ctx.fillStyle = ink("grid", 0.95);
            ctx.fillText(text, x + pad * 2, Math.round(4 * ky));
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
