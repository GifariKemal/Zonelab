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

import { LABEL_GUTTER, claimedLabels, labelFree } from "./structure-primitive";
import { ink } from "./ink";

/**
 * Fibonacci / OTE grid over one structural swing.
 *
 * The "618" in POSKO 618. Levels are drawn over the active swing high-to-low:
 *   0.500  equilibrium (dashed)
 *   0.618 / 0.705 / 0.786  the OTE sweet spot (solid band)
 *   1.000  invalidation
 *   -0.27 / -0.618 / -1.0  extensions (DOL targets)
 *
 * NO DIRECTION CLAIM. One neutral ink for every level; the label names it.
 * Red and green on this canvas mean demand and supply, and lending them to a
 * Fibonacci line would smuggle a forecast in through the palette.
 *
 * EVERY RAY STOPS AT `LABEL_GUTTER`, like every other ray on this canvas. This
 * file used to draw `moveTo(0, y)` to `lineTo(width, y)` and never imported the
 * constant at all, so all nine levels ran the full width of the pane and
 * straight through the reserved name column - and nine is the worst possible
 * number to do it with, because the grid is dense enough that one of them lands
 * near almost any ray name on screen. That is the exact defect the gutter was
 * introduced for, written down in `structure-primitive.ts`: a line through a
 * name is worse than either object alone, since the reader cannot tell which of
 * the two is lying. `levels-primitive.ts`, `session-primitive.ts`,
 * `dfr-primitive.ts` and `zone-primitive.ts` all already honoured it.
 */

const INK = ink("levels", 0.8);
const INK_OTE = ink("levels", 0.95);
const INK_EQ = ink("levels", 0.5);

/** Retracement ratios, in draw order (outermost first). */
const LEVELS: { ratio: number; label: string; kind: "eq" | "ote" | "ext" }[] = [
  { ratio: 1.0, label: "1.000", kind: "ote" },
  { ratio: 0.786, label: "0.786", kind: "ote" },
  { ratio: 0.705, label: "0.705", kind: "ote" },
  { ratio: 0.618, label: "0.618", kind: "ote" },
  { ratio: 0.5, label: "0.500", kind: "eq" },
  { ratio: 0.0, label: "0.000", kind: "ote" },
  { ratio: -0.27, label: "-0.27", kind: "ext" },
  { ratio: -0.618, label: "-0.618", kind: "ext" },
  { ratio: -1.0, label: "-1.000", kind: "ext" },
];

interface FibLine {
  y: number;
  label: string;
  kind: "eq" | "ote" | "ext";
}

class FibRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly lines: readonly FibLine[]) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const ky = scope.verticalPixelRatio;
      const kx = scope.horizontalPixelRatio;
      const width = scope.bitmapSize.width;

      ctx.save();
      ctx.font = `${Math.round(9 * ky)}px ui-monospace, monospace`;
      ctx.textBaseline = "middle";
      ctx.lineWidth = Math.max(1, Math.round(kx));
      // Where the pane stops belonging to lines and starts belonging to names.
      // One column for every pass, so the stop is the shared constant rather
      // than this file's own measurement of its own label.
      const gutter = width - LABEL_GUTTER * kx;

      for (const line of this.lines) {
        const y = Math.round(line.y * ky);
        const style = line.kind === "eq" ? INK_EQ : line.kind === "ote" ? INK_OTE : INK;
        ctx.strokeStyle = style;
        // Equilibrium is dashed; everything else is solid.
        ctx.setLineDash(line.kind === "eq" ? [4 * kx, 3 * kx] : []);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(gutter, y);
        ctx.stroke();

        // Label, clamped to the right edge - which is INSIDE the gutter the ray
        // just stopped at, so the plate sits in the column rather than over the
        // line. The widest tag here is "-1.000" at 9px ui-monospace, about 33px
        // with its padding, so it fits the 46px column with room to spare.
        // Reuses the shared claim list so a Fibonacci label cannot land on a PDH
        // or a zone caption.
        const pad = Math.round(3 * kx);
        const w = ctx.measureText(line.label).width + pad * 2;
        const h = Math.round(12 * ky);
        const lx = Math.max(width - w, 0);
        const box = { x: lx / kx, y: (y - h / 2) / ky, w: w / kx, h: h / ky };
        if (!labelFree(box, claimedLabels)) continue;
        claimedLabels.push(box);
        ctx.setLineDash([]);
        ctx.fillStyle = "rgba(11, 13, 16, 0.78)";
        ctx.fillRect(lx, y - h / 2, w, h);
        ctx.fillStyle = style;
        ctx.fillText(line.label, lx + pad, y);
      }
      ctx.restore();
    });
  }
}

export class FibonacciSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private swingLow: number | null = null;
  private swingHigh: number | null = null;
  private lines: FibLine[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      zOrder: () => "normal",
      renderer: () => new FibRenderer(this.lines),
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
    this.lines = [];
  }

  setSwing(low: number | null, high: number | null): void {
    this.swingLow = low;
    this.swingHigh = high;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const series = this.series;
    if (!series || this.swingLow === null || this.swingHigh === null) {
      this.lines = [];
      return;
    }
    const found: FibLine[] = [];
    for (const level of LEVELS) {
      const price = this.swingLow! + level.ratio * (this.swingHigh! - this.swingLow!);
      const y = series.priceToCoordinate(price);
      if (y === null) continue;
      found.push({ y, label: level.label, kind: level.kind });
    }
    this.lines = found;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}