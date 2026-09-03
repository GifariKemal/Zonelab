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

import type { ChartGap } from "@/lib/types";
import { ink, plateInk } from "./ink";
import { claimedLabels, labelFree, LABEL_GUTTER } from "./structure-primitive";

/**
 * BREAKAWAY AND MEASURING GAPS: the unfilled band at the bar that gapped, plus
 * the measuring projection drawn as a dashed target to the right.
 *
 * Unmeasured doctrine. The band is geometry on two bars; the classification and
 * the halfway projection are rules stated by the module, not results. Drawn in
 * the levels family but fainter, because nothing here has walked forward.
 */

const INK = "levels";

interface Row {
  x: number;
  yTop: number;
  yBottom: number;
  //: null for a breakaway gap, which publishes no halfway projection.
  yTarget: number | null;
  tag: string;
}

class ChartGapRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly rows: readonly Row[]) {}

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

      for (const row of this.rows) {
        const x = Math.round(row.x * kx);
        const top = Math.round(Math.min(row.yTop, row.yBottom) * ky);
        const bottom = Math.round(Math.max(row.yTop, row.yBottom) * ky);
        const bandH = Math.max(2, bottom - top);
        const bandW = Math.max(4, Math.round(4 * kx));

        // The unfilled band at the gap bar.
        ctx.fillStyle = ink(INK, 0.22);
        ctx.fillRect(x - bandW / 2, top, bandW, bandH);
        ctx.strokeStyle = ink(INK, 0.55);
        ctx.strokeRect(x - bandW / 2, top, bandW, bandH);

        // The measuring target, dashed, to the label gutter. A breakaway gap
        // sends none, and then nothing is drawn.
        const yT =
          row.yTarget === null ? null : Math.round(row.yTarget * ky) + 0.5;
        if (yT !== null && yT >= 0 && yT <= height) {
          ctx.setLineDash([2 * kx, 3 * kx]);
          ctx.strokeStyle = ink(INK, 0.40);
          ctx.beginPath();
          ctx.moveTo(x, yT);
          ctx.lineTo(width - gutter, yT);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // A short tag, against the shared claim map so it cannot sit on another
        // layer's name.
        const pad = Math.round(3 * kx);
        const w = ctx.measureText(row.tag).width + pad * 2;
        const h = Math.round(12 * ky);
        // With no target the tag rides the band itself rather than vanishing.
        const tagY = row.yTarget === null ? (top + bottom) / 2 / ky : row.yTarget;
        const box = { x: x / kx, y: (tagY * ky - h / 2) / ky, w: w / kx, h: h / ky };
        if (tagY * ky >= 0 && tagY * ky <= height && labelFree(box, claimedLabels)) {
          claimedLabels.push(box);
          ctx.fillStyle = plateInk(0.78);
          ctx.fillRect(x, Math.round(tagY * ky) - h / 2, w, h);
          ctx.fillStyle = ink(INK, 0.9);
          ctx.fillText(row.tag, x + pad, Math.round(tagY * ky));
        }
      }
      ctx.restore();
    });
  }
}

export class ChartGapSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private source: readonly ChartGap[] = [];
  private rows: Row[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    { zOrder: () => "normal", renderer: () => new ChartGapRenderer(this.rows) },
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
    this.rows = [];
  }

  setGaps(gaps: readonly ChartGap[]): void {
    this.source = gaps;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    this.rows = [];
    if (!chart || !series) return;
    const scale = chart.timeScale();
    for (const g of this.source) {
      const x = scale.timeToCoordinate(g.at as Time);
      const yTop = series.priceToCoordinate(g.top);
      const yBottom = series.priceToCoordinate(g.bottom);
      // A breakaway gap publishes no target, so none is drawn: the halfway rule
      // is a measuring gap's claim, and inventing the line for the other kind
      // put a projection on the chart that no doctrine asked for.
      const yTarget =
        g.target == null ? null : series.priceToCoordinate(g.target);
      if (x === null || yTop === null || yBottom === null) continue;
      this.rows.push({
        x,
        yTop,
        yBottom,
        yTarget,
        tag: g.kind === "breakaway" ? "BK" : "MG",
      });
    }
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
