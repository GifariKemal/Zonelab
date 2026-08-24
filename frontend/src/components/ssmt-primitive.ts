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

import type { SSMTDivergence } from "@/lib/types";
import { claimedLabels, labelFree } from "./structure-primitive";
import { ink } from "./ink";

/**
 * THE CROSS-INSTRUMENT DIVERGENCE, drawn where the method actually draws it.
 *
 * A segment from this symbol's extreme in the prior quarter to its extreme in
 * the current one, tagged with the degree and the partner - `day / XAGUSD` -
 * which is the annotation on roughly 33 of the 51 reference charts and the most
 * frequent object in them. The engine has computed these for months and the
 * only place they surfaced was a number in the checklist panel.
 *
 * ONE PRICE SCALE, ONE INSTRUMENT. The partner's two prices ride on the object
 * as evidence and are deliberately NOT plotted: they belong to a different
 * instrument's axis, and a silver price drawn on a gold chart is the most
 * confidently wrong line a chart can carry. They are readable in the checklist
 * panel, where both sides are named.
 *
 * NO DIRECTION CLAIM, and the styling has to carry that. Twelve pre-registered
 * directional hypotheses have failed in this project and nothing connects a
 * divergence to an outcome. So this draws in ONE neutral ink whether the chart's
 * symbol took the extreme or failed it - the fact is in the tag, not in a colour
 * that would read as bullish or bearish. Green and red on this canvas mean
 * demand and supply and nothing else.
 */

/** Dashed when the chart's own symbol FAILED to take the extreme, solid when it
 *  took it. A texture rather than a hue, for the reason in the header: the
 *  colour language on this canvas is already spoken for. */
const INK = ink("ssmt", 0.85);
const INK_FAINT = ink("ssmt", 0.55);

/** Segments shorter than this carry no label: there is nowhere to put one that
 *  does not sit further from the segment than the segment is long. */
const LABEL_MIN_WIDTH = 18;

interface Segment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  tag: string;
  took: boolean;
  /** False when the candle direction breaks the practitioner's rule. */
  candleValid: boolean | null;
}

class SSMTRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly segments: readonly Segment[]) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const width = scope.bitmapSize.width;

      ctx.save();
      ctx.font = `${Math.round(9 * ky)}px ui-monospace, monospace`;
      ctx.textBaseline = "middle";
      ctx.lineWidth = Math.max(1, Math.round(kx));

      for (const s of this.segments) {
        const x1 = Math.round(s.x1 * kx);
        const y1 = Math.round(s.y1 * ky);
        const x2 = Math.round(s.x2 * kx);
        const y2 = Math.round(s.y2 * ky);

        ctx.strokeStyle = s.took ? INK : INK_FAINT;
        // Candle validation: if the practitioner's rule is explicitly
        // contradicted, downgrade the line to faint even when the chart
        // symbol took the extreme. The divergence exists, but the candle
        // direction does not confirm it.
        if (s.candleValid === false) {
          ctx.strokeStyle = INK_FAINT;
        }
        ctx.setLineDash(s.took ? [] : [4 * kx, 3 * kx]);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // A tick at each end, so the two prices being compared are visible as
        // points rather than inferred from where a line happens to stop.
        ctx.setLineDash([]);
        for (const [x, y] of [[x1, y1], [x2, y2]] as const) {
          ctx.beginPath();
          ctx.moveTo(x, y - 3 * ky);
          ctx.lineTo(x, y + 3 * ky);
          ctx.stroke();
        }

        // PER SEGMENT, against the shared claim list, and NOT a pane-wide
        // on-or-off switch. The ribbon decides labelling once per row because
        // its rows are uniform and a ragged mix there reads as missing data.
        // These are scattered annotations, and a pane-wide rule measured on the
        // closest pair muted ALL of them the moment two segments landed 8px
        // apart - three divergences on screen, zero partner names, which is the
        // one thing the object is for. `claimedLabels` is the same list the
        // cycle grid, the levels overlay and the structure captions already
        // route around, so an SSMT tag cannot land on a PDH either.
        if (x2 - x1 < LABEL_MIN_WIDTH * kx) continue;
        const pad = Math.round(3 * kx);
        const w = ctx.measureText(s.tag).width + pad * 2;
        const h = Math.round(13 * ky);
        // CLAMPED TO BOTH EDGES. A divergence's line ends where its extreme
        // printed, which can be off-screen left after a pan, or close enough to
        // the right edge that the tag runs past it - and half a word is
        // unreadable in a way a missing word is not. The same clamp a gap band's
        // tag and a quarter box's label already carry.
        //
        // The tag grew when the premium/discount letter was appended to it, and
        // that is how this surfaced: a wider box crosses an edge more often, and
        // `e2e/labels.mjs` failed four of them in one frame.
        const lx = Math.min(Math.max(x2 + pad, 0), Math.max(width - w, 0));
        const box = { x: lx / kx, y: (y2 - h / 2) / ky, w: w / kx, h: h / ky };
        if (!labelFree(box, claimedLabels)) continue;
        claimedLabels.push(box);
        // Plated, because these sit on top of candles and an unplated 9px
        // label over a wick is unreadable at any contrast.
        ctx.fillStyle = "rgba(11, 13, 16, 0.78)";
        ctx.fillRect(lx, y2 - h / 2, w, h);
        ctx.fillStyle = INK;
        ctx.fillText(s.tag, lx + pad, y2);
      }
      ctx.restore();
    });
  }
}

export class SSMTSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private divergences: readonly SSMTDivergence[] = [];
  private segments: Segment[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      // `normal`, beside the price-anchored levels: a divergence is a reading
      // to compare candles against, so it must clear the cycle grid's context
      // wash. A zone border still wins, because a border's position is verified
      // to the pixel and this one is not load-bearing.
      zOrder: () => "normal",
      renderer: () => new SSMTRenderer(this.segments),
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
  }

  setDivergences(divergences: readonly SSMTDivergence[]): void {
    this.divergences = divergences;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    if (!chart || !series) {
      this.segments = [];
      return;
    }
    const scale = chart.timeScale();

    const found: Segment[] = [];
    for (const d of this.divergences) {
      const x1 = scale.timeToCoordinate(d.time_from as Time);
      const x2 = scale.timeToCoordinate(d.time_to as Time);
      const y1 = series.priceToCoordinate(d.price_from);
      const y2 = series.priceToCoordinate(d.price_to);
      // All four or none. An unresolved end clamped to the pane edge is how the
      // ribbon once painted a wash of segments that were pure artefact.
      if (x1 === null || x2 === null || y1 === null || y2 === null) continue;
      found.push({
        x1,
        y1,
        x2,
        y2,
        // PREMIUM OR DISCOUNT IN THE TAG, because without it the reading is
        // incomplete rather than merely terse: the same divergence means
        // opposite things in the top and the bottom of the range. One letter,
        // and it is the quartile rather than a bare above/below halfway -
        // `EQ` for the middle two quartiles is a real state in this method and
        // not a rounding of the other two.
        //
        // Absent rather than guessed when `range_pos` is null, which is the
        // warm-up: both sides of the range must have confirmed, and at the
        // shipped swing width that takes about a hundred bars. Measured on 2000
        // hourly bars of gold against silver at day degree, 88 of 99
        // divergences carried a position and the first 11 did not.
        tag:
          `${d.degree} ${d.side === "high" ? "H" : "L"} ${d.partner}` +
          (d.range_pos === null
            ? ""
            : d.range_pos >= 0.75
              ? " P"
              : d.range_pos <= 0.25
                ? " D"
                : " EQ") +
          // Session: one compact letter, so a reader can weigh it. Asia
          // is weaker than London or NY per the practitioner. Absent
          // when the session is unknown or the tag is already long.
          // Lowercase = weaker, uppercase = stronger.
          (d.session
            ? d.session === "asia"
              ? " a"
              : d.session === "london"
                ? " L"
                : d.session === "ny_am"
                  ? " N"
                  : d.session === "london_close"
                    ? " LC"
                    : d.session === "ny_pm"
                      ? " NP"
                      : d.session === "silver_bullet"
                        ? " SB"
                        : ""
            : ""),
        took: d.self_took,
        candleValid: d.candle_valid,
      });
    }

    this.segments = found;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
