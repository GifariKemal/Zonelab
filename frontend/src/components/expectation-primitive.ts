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

import type { ExpectationFan, QuantileSet } from "@/lib/types";
import { ink } from "./ink";
import { claimedLabels, labelFree, LABEL_GUTTER } from "./structure-primitive";

/**
 * THE EXPECTATION FAN: the measured distribution of resolved R for this symbol,
 * drawn at the right edge.
 *
 * A MEASUREMENT, never a forecast, and the ink says so. The base rate is the
 * unconditional distribution of resolved R over the first-touch population, and
 * the matched fan is the same distribution conditioned on `dfr_side` - the one
 * clause that separated, with its sign INVERTED. Where the two fans part, the
 * gap is a warning, not an edge, and the verdict is printed beside it.
 *
 * R maps to price through one R equals one ATR, the plan's own stop scale. The
 * backend sends `anchor` (the last close) and `atr` so this primitive places the
 * quantiles as prices without computing an ATR itself, and without a second copy
 * of the R-to-price rule drifting out of step.
 *
 * The `show_path` median line is the "forecast" the owner asked to keep separate:
 * it draws the median as a single line and is OFF by default, because a lone line
 * reads as a prediction and this engine does not predict.
 */

const INK = "levels";
const FAN_W = 56; // px the forward fan reaches left of the label gutter
const QS = ["q5", "q25", "q50", "q75", "q95"] as const;

interface Row {
  y: number;
  value: number;
  tag: string;
  bold: boolean;
}

class ExpectationRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly rows: readonly Row[],
    private readonly caption: string | null,
    private readonly captionY: number | null,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const width = scope.bitmapSize.width;
      const height = scope.bitmapSize.height;
      const gutter = LABEL_GUTTER * kx;
      const x1 = width - gutter - FAN_W * kx;
      const x2 = width - gutter;

      ctx.save();
      ctx.font = `${Math.round(9 * ky)}px ui-monospace, monospace`;
      ctx.textBaseline = "middle";
      ctx.lineWidth = Math.max(1, Math.round(kx));

      for (const row of this.rows) {
        if (row.y < 0 || row.y * ky > height) continue;
        const y = Math.round(row.y * ky) + 0.5;
        const alpha = row.bold ? 0.85 : 0.40;
        ctx.strokeStyle = ink(INK, alpha);
        ctx.setLineDash(row.bold ? [] : [2 * kx, 3 * kx]);
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // One caption, against the shared claim map so it cannot sit on another
      // layer's name. Dropped rather than overprinted.
      if (this.caption && this.captionY !== null) {
        const pad = Math.round(3 * kx);
        const w = ctx.measureText(this.caption).width + pad * 2;
        const h = Math.round(12 * ky);
        const x = width - gutter + pad;
        const box = { x: x / kx, y: (this.captionY * ky - h / 2) / ky, w: w / kx, h: h / ky };
        if (labelFree(box, claimedLabels)) {
          claimedLabels.push(box);
          ctx.fillStyle = "rgba(11, 13, 16, 0.78)";
          ctx.fillRect(x, Math.round(this.captionY * ky) - h / 2, w, h);
          ctx.fillStyle = ink(INK, 0.95);
          ctx.fillText(this.caption, x + pad, Math.round(this.captionY * ky));
        }
      }
      ctx.restore();
    });
  }
}

export class ExpectationSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private source: ExpectationFan | null = null;
  private showPath = false;
  private rows: Row[] = [];
  private caption: string | null = null;
  private captionY: number | null = null;

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      zOrder: () => "normal",
      renderer: () => new ExpectationRenderer(this.rows, this.caption, this.captionY),
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
    this.rows = [];
    this.caption = null;
    this.captionY = null;
  }

  setFan(fan: ExpectationFan | null, showPath: boolean): void {
    this.source = fan;
    this.showPath = showPath;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const series = this.series;
    const fan = this.source;
    this.rows = [];
    this.caption = null;
    this.captionY = null;
    if (!series || !fan || fan.anchor == null || fan.atr == null) return;

    const price = (q: number) => fan.anchor! + q * fan.atr!;
    const rows: Row[] = [];
    for (const key of QS) {
      const q = fan.base_rate[key as keyof QuantileSet] as number;
      const y = series.priceToCoordinate(price(q));
      if (y === null) continue;
      rows.push({ y, value: q, tag: `R ${q >= 0 ? "+" : ""}${q.toFixed(2)}`, bold: false });
    }
    if (fan.matched) {
      for (const key of QS) {
        const q = fan.matched[key as keyof QuantileSet] as number;
        const y = series.priceToCoordinate(price(q));
        if (y === null) continue;
        rows.push({ y, value: q, tag: `R ${q >= 0 ? "+" : ""}${q.toFixed(2)}`, bold: true });
      }
    }
    this.rows = rows;

    const median = fan.matched?.q50 ?? fan.base_rate.q50;
    const medianY = series.priceToCoordinate(price(median));
    this.captionY = medianY;
    const n = fan.matched ? fan.matched.n : fan.base_rate.n;
    const tag = fan.matched_key
      ? `${fan.matched_key} n=${n}`
      : `base n=${n}`;
    this.caption = `E[R] ${median >= 0 ? "+" : ""}${median.toFixed(2)} · ${tag}`;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
