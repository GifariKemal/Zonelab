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

import type { WyckoffPhase } from "@/lib/types";
import { ink, monoFont, plateInk } from "./ink";
import { claimedLabels, labelFree } from "./structure-primitive";

/**
 * WYCKOFF PHASE READINGS: a letter at the bar where each phase printed.
 *
 * A reading, never a bias. The four phases map onto the structure primitives
 * (sweep, break) that H6 and H9 already measured null, so these are drawn in the
 * structure family and labelled, not scored. The full schematic needs volume and
 * discretion and is out of scope - see the spec.
 */

const INK = "structure";
const TAG: Record<string, string> = {
  spring: "SPR",
  upthrust: "UT",
  sos: "SOS",
  sow: "SOW",
};

interface Row {
  x: number;
  y: number;
  tag: string;
}

class WyckoffRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly rows: readonly Row[]) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const height = scope.bitmapSize.height;

      ctx.save();
      ctx.font = monoFont(9, ky);
      ctx.textBaseline = "middle";

      for (const row of this.rows) {
        if (row.y < 0 || row.y * ky > height) continue;
        const x = Math.round(row.x * kx);
        const y = Math.round(row.y * ky);
        const pad = Math.round(3 * kx);
        const w = ctx.measureText(row.tag).width + pad * 2;
        const h = Math.round(12 * ky);
        const box = { x: x / kx, y: (y - h / 2) / ky, w: w / kx, h: h / ky };
        if (!labelFree(box, claimedLabels)) continue;
        claimedLabels.push(box);
        ctx.fillStyle = plateInk(0.78);
        ctx.fillRect(x, y - h / 2, w, h);
        ctx.fillStyle = ink(INK, 0.85);
        ctx.fillText(row.tag, x + pad, y);
      }
      ctx.restore();
    });
  }
}

export class WyckoffSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private source: readonly WyckoffPhase[] = [];
  private rows: Row[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    { zOrder: () => "normal", renderer: () => new WyckoffRenderer(this.rows) },
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

  setPhases(phases: readonly WyckoffPhase[]): void {
    this.source = phases;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    this.rows = [];
    if (!chart || !series) return;
    const scale = chart.timeScale();
    for (const p of this.source) {
      const x = scale.timeToCoordinate(p.at as Time);
      const y = series.priceToCoordinate(p.level);
      if (x === null || y === null) continue;
      this.rows.push({ x, y, tag: TAG[p.kind] ?? p.kind });
    }
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
