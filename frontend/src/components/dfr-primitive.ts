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

import type { DefiningRangeBand } from "@/lib/types";
import { claimedLabels, labelFree, LABEL_GUTTER } from "./structure-primitive";
import { INKS } from "./ink";

/**
 * THE DEFINING RANGE: the band, its 50% line, and its projections.
 *
 * Q1 split in thirds, the first third discarded, the extremes of the rest. The
 * band is bounded in TIME as well as price - unlike a gap band or a named level
 * it describes one window and does not outlive it - so it is drawn as a closed
 * rectangle over its own two thirds of Q1, and only the projections extend
 * right, because a target is a price to travel to and has to be reachable from
 * where price is now.
 *
 * SINGLE-SOURCED AND UNVERIFIED, and the ink says so. This is the one object on
 * the canvas whose rule reached the project from a single description of a
 * closed-source indicator, never checked against the course material it came
 * from and never against outcomes. So it draws thinner and fainter than the
 * measured objects beside it: a band whose evidence is one paragraph must not
 * look like a zone whose gate cleared p<0.0001.
 *
 * BOTH SIDES OF EVERY MULTIPLE. The source gives -0.5 and -1 and no direction -
 * they "often function as manipulation or reversal targets" - so the backend
 * computes both sides and each level carries its own. Drawing one side would be
 * inventing the half nobody published, and the reader could not tell which half
 * was invented.
 */

/** Neutral, and deliberately not the demand/supply pair. A defining range is a
 *  window of price, not a side: colouring it green or red would make a clock
 *  reading look like a directional call, and this canvas already spends those
 *  two hues on demand and supply. */
const INK = INKS.dfr.join(", ");

/** Below this the band is a line, not a rectangle, and its label has nowhere to
 *  sit inside it. */
const MIN_BOX_PX = 8;

/** One letter per degree, because the gutter is 46px and it is sized from a
 *  stated budget: at most six characters at 5.5px each plus 8px of padding.
 *  `DFR week` measures 45.6px and `DFR session` more, so the first version of
 *  this tag ran 2.6px past the pane edge and `e2e/labels.mjs` failed it as a
 *  word cut in half - the exact defect the single shared gutter exists to
 *  prevent. `u` for micro rather than M, which month already has; taking the
 *  first letter twice would make the two degrees indistinguishable, and the
 *  whole point of the tag is which clock the band was read on. */
const DEGREE_TAG: Record<string, string> = {
  year: "Y",
  month: "M",
  week: "W",
  day: "D",
  session: "S",
  micro: "u",
  nano: "n",
};

interface Band {
  band: DefiningRangeBand;
  x1: number;
  x2: number;
  yHigh: number;
  yLow: number;
  yEq: number | null;
  /** Extension levels resolved to pixels, with the text each one carries. */
  levels: { y: number; tag: string }[];
}

class DFRRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly bands: readonly Band[],
    private readonly showEquilibrium: boolean,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const width = scope.bitmapSize.width;
      const height = scope.bitmapSize.height;
      const gutter = LABEL_GUTTER * kx;

      ctx.save();
      ctx.font = `${Math.round(9 * ky)}px ui-monospace, monospace`;
      ctx.textBaseline = "middle";
      ctx.lineWidth = Math.max(1, Math.round(kx));

      for (const b of this.bands) {
        const x1 = Math.round(b.x1 * kx);
        const x2 = Math.round(b.x2 * kx);
        const top = Math.round(Math.min(b.yHigh, b.yLow) * ky);
        const bottom = Math.round(Math.max(b.yHigh, b.yLow) * ky);

        // The band itself: a faint wash and a solid outline, CLOSED on the right
        // because the window it describes ended.
        ctx.fillStyle = `rgba(${INK}, 0.05)`;
        ctx.fillRect(x1, top, Math.max(1, x2 - x1), Math.max(1, bottom - top));
        ctx.strokeStyle = `rgba(${INK}, 0.55)`;
        ctx.setLineDash([]);
        ctx.strokeRect(x1, top, Math.max(1, x2 - x1), Math.max(1, bottom - top));

        if (this.showEquilibrium && b.yEq !== null && bottom - top >= MIN_BOX_PX * ky) {
          const y = Math.round(b.yEq * ky) + 0.5;
          ctx.strokeStyle = `rgba(${INK}, 0.45)`;
          ctx.setLineDash([3 * kx, 3 * kx]);
          ctx.beginPath();
          ctx.moveTo(x1, y);
          ctx.lineTo(x2, y);
          ctx.stroke();
        }

        // Projections. These DO extend right, to the label gutter and no
        // further: a target has to be reachable from where price is now, and the
        // gutter is the one column every pass leaves for names so a level cannot
        // run through a name that belongs to another layer.
        //
        // OFF-PANE LEVELS ARE SKIPPED ENTIRELY, line and name together. A full
        // extension is one band-height beyond the band, so on any chart zoomed
        // to the candles a good half of them sit above or below the price axis -
        // measured at 25 claims from six bands, of which several landed at y=935
        // in a 734px pane. The line was clipped by the canvas and cost nothing,
        // but the NAME was still claimed against the shared collision map, so an
        // invisible target could push a visible one out.
        ctx.setLineDash([1 * kx, 4 * kx]);
        ctx.strokeStyle = `rgba(${INK}, 0.40)`;
        const onPane = b.levels.filter((l) => l.y >= 0 && l.y * ky <= height);
        for (const level of onPane) {
          const y = Math.round(level.y * ky) + 0.5;
          ctx.beginPath();
          ctx.moveTo(x1, y);
          ctx.lineTo(width - gutter, y);
          ctx.stroke();
        }

        // Labels last, and each against the SHARED claim list, so a projection
        // tag cannot land on a PDH or on a zone caption. Dropped rather than
        // overprinted: an unreadable word is worse than a missing one.
        ctx.setLineDash([]);
        const pad = Math.round(3 * kx);
        const rows: { y: number; tag: string }[] = [
          ...onPane,
          { y: b.yHigh, tag: `DR ${DEGREE_TAG[b.band.degree] ?? b.band.degree}` },
        ].filter((r) => r.y >= 0 && r.y * ky <= height);
        for (const row of rows) {
          const w = ctx.measureText(row.tag).width + pad * 2;
          const h = Math.round(12 * ky);
          const x = width - gutter + pad;
          // CENTRED ON THE ROW, so the filter above is half a row too generous:
          // it keeps a row whose CENTRE is on the pane, and then this box puts
          // h/2 of itself above or below that centre. A row at y = 5 passes
          // `r.y >= 0` and starts its plate at -1.
          //
          // Measured 1 September 2026 at a pinned bar grid: a claim at
          // y = -0.73 with a 12px row, reported by `e2e/labels.mjs` as one
          // straddling box, at 1 of 8 pinned grids swept. It was mistaken twice
          // before being found - first for a zone caption, then for the
          // projections tag in `levels-primitive.ts` - because dropping either
          // layer changes which label wins its claim, and `claimedLabels` is
          // first-come-first-served. Identified in the end by stack trace.
          //
          // Same clamp as the ray names in `levels-primitive.ts`, and the label
          // moves rather than the line: a tag half a row off its own level still
          // names that level, and a tag cut by the pane edge names nothing.
          const cy = Math.min(Math.max(row.y * ky, h / 2), height - h / 2);
          const box = { x: x / kx, y: (cy - h / 2) / ky, w: w / kx, h: h / ky };
          if (!labelFree(box, claimedLabels)) continue;
          claimedLabels.push(box);
          ctx.fillStyle = "rgba(11, 13, 16, 0.78)";
          ctx.fillRect(x, Math.round(cy) - h / 2, w, h);
          ctx.fillStyle = `rgba(${INK}, 0.95)`;
          ctx.fillText(row.tag, x + pad, Math.round(cy));
        }
      }
      ctx.restore();
    });
  }
}

export class DFRSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private source: readonly DefiningRangeBand[] = [];
  private showEquilibrium = true;
  private bands: Band[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      // `bottom`, with the cycle grid. The defining range is a window of the
      // clock's own Q1, so it is context the candles sit ON rather than a level
      // to compare them against - and its evidence is one paragraph, which is
      // not enough to earn ink over a wick.
      zOrder: () => "bottom",
      renderer: () => new DFRRenderer(this.bands, this.showEquilibrium),
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
  }

  setRanges(bands: readonly DefiningRangeBand[], showEquilibrium: boolean): void {
    this.source = bands;
    this.showEquilibrium = showEquilibrium;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    if (!chart || !series) {
      this.bands = [];
      return;
    }
    const scale = chart.timeScale();

    // HALF A BAR EACH SIDE. Same correction as `zone-primitive.ts` and the
    // quarter box in `session-primitive.ts`: `timeToCoordinate` returns a bar's
    // CENTRE, so an uncorrected band starts and ends mid-bar, and its left
    // border is painted under the candle that defines it.
    const halfBar = scale.options().barSpacing / 2;
    const out: Band[] = [];
    for (const band of this.source) {
      const left = scale.timeToCoordinate(band.time_from as Time);
      const yHigh = series.priceToCoordinate(band.high);
      const yLow = series.priceToCoordinate(band.low);
      if (left === null || yHigh === null || yLow === null) continue;
      const x1 = left - halfBar;
      // The right edge is the window's close, which is a real bar in almost
      // every case. When it is not - the newest cycle, or a hole in the feed -
      // the band is left OPEN to the pane edge rather than dropped: the window
      // it describes did close, and a rectangle with one unresolved corner is
      // still a readable rectangle. That is not true of an unresolved LEFT edge,
      // which is why the guard above drops those.
      const right = scale.timeToCoordinate(band.time_to as Time);
      const x2 = right === null ? x1 + MIN_BOX_PX : right + halfBar;

      const levels: { y: number; tag: string }[] = [];
      for (const ext of band.extensions) {
        const y = series.priceToCoordinate(ext.price);
        if (y === null) continue;
        levels.push({ y, tag: `${ext.multiple}` });
      }
      out.push({
        band,
        x1,
        x2,
        yHigh,
        yLow,
        yEq: series.priceToCoordinate(band.equilibrium),
        levels,
      });
    }
    this.bands = out;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
