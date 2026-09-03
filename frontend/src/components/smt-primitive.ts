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

import type { SMTDivergence } from "@/lib/types";
import { claimedLabels, labelFree } from "./structure-primitive";
import { ink, plateInk } from "./ink";

/**
 * Regular SMT marker — a diamond at the quarter where one instrument took
 * the running extreme and the other failed.
 *
 * Unlike sequential SSMT which draws a segment between two quarters, regular
 * SMT draws a single marker at the divergence point. The marker is a diamond
 * shape, distinct from the segment line used for sequential SSMT.
 *
 * Regular SMT is a liquidity reading: "Regular SMT mengandungi liquiditas
 * yang sangat besar yang tinggi kemungkinan di akan di-purge." It means the
 * level is a DOL target, not a trend confirmation.
 */

const INK = ink("ssmt", 0.85);
const INK_FAINT = ink("ssmt", 0.55);

interface Marker {
  x: number;
  y: number;
  tag: string;
  took: boolean;
}

class SMTRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly markers: readonly Marker[]) {}

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

      for (const m of this.markers) {
        const x = Math.round(m.x * kx);
        const y = Math.round(m.y * ky);
        const size = Math.round(4 * ky);

        // Diamond marker
        ctx.strokeStyle = m.took ? INK : INK_FAINT;
        ctx.fillStyle = m.took ? INK : INK_FAINT;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(x, y - size);
        ctx.lineTo(x + size, y);
        ctx.lineTo(x, y + size);
        ctx.lineTo(x - size, y);
        ctx.closePath();
        ctx.stroke();

        // Tag: partner + degree, anchored to the right of the diamond
        const pad = Math.round(3 * kx);
        const w = ctx.measureText(m.tag).width + pad * 2;
        const h = Math.round(13 * ky);
        const lx = Math.min(Math.max(x + size + pad, 0), Math.max(width - w, 0));
        const box = { x: lx / kx, y: (y - h / 2) / ky, w: w / kx, h: h / ky };
        if (!labelFree(box, claimedLabels)) continue;
        claimedLabels.push(box);

        ctx.fillStyle = plateInk(0.78);
        ctx.fillRect(lx, y - h / 2, w, h);
        ctx.fillStyle = INK;
        ctx.fillText(m.tag, lx + pad, y);
      }
      ctx.restore();
    });
  }
}

export class SMTSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private divergences: readonly SMTDivergence[] = [];
  private markers: Marker[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      zOrder: () => "normal",
      renderer: () => new SMTRenderer(this.markers),
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
    this.markers = [];
  }

  setDivergences(divergences: readonly SMTDivergence[]): void {
    this.divergences = divergences;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    if (!chart || !series) {
      this.markers = [];
      return;
    }
    const scale = chart.timeScale();

    const found: Marker[] = [];
    for (const d of this.divergences) {
      const x = scale.timeToCoordinate(d.time_at as Time);
      const y = series.priceToCoordinate(d.price_at);
      if (x === null || y === null) continue;
      found.push({
        x,
        y,
        tag: `${d.degree} ${d.side === "high" ? "H" : "L"} ${d.partner}`,
        took: d.self_took,
      });
    }
    this.markers = found;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}