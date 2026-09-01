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

import type { PSPReading } from "@/lib/types";
import { ink } from "./ink";
import { claimedLabels, labelFree } from "./structure-primitive";

/**
 * PRECISION SWING POINTS: the swept level, and a tick at the bar that rejected it.
 *
 * A READING, NEVER A BIAS, and here the null is measured rather than assumed.
 * `docs/psp_outcomes.json` graded 48 cells - four pairs, three bracket widths,
 * both directions, two hypotheses - and not one separated. The largest |z| was
 * 2,10 against a Bonferroni bar of 3,28, on a run powered to about 10,6 points
 * of hit rate. H1 asked whether a PSP after an SSMT beats a bar with no PSP on
 * it; H2 asked whether the SSMT in front of it adds anything over a PSP
 * standing alone. Both null, and `tests/test_psp_not_wired_to_decisions.py`
 * keeps the object out of anything that decides, sizes or sends.
 *
 * Drawn in the SSMT ink because that is what it belongs to: a PSP only exists
 * inside the three bars after a divergence settles, and colouring it in its own
 * family would claim it stands alone.
 */

const INK = "ssmt";

interface Row {
  x: number;
  xFrom: number;
  y: number;
  tag: string;
  crack: boolean;
}

class PSPRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly rows: readonly Row[]) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const height = scope.bitmapSize.height;

      ctx.save();
      ctx.font = `${Math.round(9 * ky)}px ui-monospace, monospace`;
      ctx.textBaseline = "middle";
      ctx.lineWidth = Math.max(1, Math.round(kx));

      for (const row of this.rows) {
        if (row.y < 0 || row.y * ky > height) continue;
        const x = Math.round(row.x * kx);
        const y = Math.round(row.y * ky) + 0.5;
        // The swept level, from the bar it was the open of to the bar that
        // swept it. That span IS the object: a level with no reach drawn is a
        // dot the reader cannot place in time.
        ctx.strokeStyle = ink(INK, 0.6);
        ctx.setLineDash([2 * kx, 2 * kx]);
        ctx.beginPath();
        ctx.moveTo(Math.round(row.xFrom * kx), y);
        ctx.lineTo(x, y);
        ctx.stroke();
        ctx.setLineDash([]);

        // A solid tick at the rejecting bar, so the sweep is findable when the
        // dashed level is short.
        const tick = Math.round(4 * ky);
        ctx.strokeStyle = ink(INK, 0.9);
        ctx.beginPath();
        ctx.moveTo(x, y - tick);
        ctx.lineTo(x, y + tick);
        ctx.stroke();

        const pad = Math.round(3 * kx);
        const w = ctx.measureText(row.tag).width + pad * 2;
        const h = Math.round(12 * ky);
        // THE WHOLE BOX INSIDE THE PANE, not just its centre. A tag whose
        // centre is two pixels below the top edge is a tag cut in half, and
        // `e2e/labels.mjs` fails on exactly that - it caught this one.
        if (y - h / 2 < 0 || y + h / 2 > height) continue;
        const box = { x: x / kx, y: (y - h / 2) / ky, w: w / kx, h: h / ky };
        if (!labelFree(box, claimedLabels)) continue;
        claimedLabels.push(box);
        ctx.fillStyle = "rgba(11, 13, 16, 0.78)";
        ctx.fillRect(x, y - h / 2, w, h);
        // The triad crack is REPORTED, never filtered on: a brighter tag, not a
        // different object. Its rate is the same in both arms of the
        // measurement, so it earns emphasis and nothing more.
        ctx.fillStyle = ink(INK, row.crack ? 0.95 : 0.7);
        ctx.fillText(row.tag, x + pad, y);
      }
      ctx.restore();
    });
  }
}

export class PSPSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private source: readonly PSPReading[] = [];
  private rows: Row[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    { zOrder: () => "normal", renderer: () => new PSPRenderer(this.rows) },
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

  setEvents(events: readonly PSPReading[]): void {
    this.source = events;
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
      const from = scale.timeToCoordinate(p.ssmt_at as Time);
      const y = series.priceToCoordinate(p.level);
      if (x === null || y === null) continue;
      this.rows.push({
        x,
        xFrom: from ?? x,
        y,
        tag: p.direction === "buy" ? "PSP+" : "PSP-",
        crack: p.triad_crack,
      });
    }
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
