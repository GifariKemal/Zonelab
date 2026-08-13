import type { CanvasRenderingTarget2D } from "fancy-canvas";
import type {
  IChartApi,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
} from "lightweight-charts";

import type { Zone, ZoneState } from "@/lib/types";

/** Opacity carries the zone's lifecycle. A fresh zone should read at a glance
 *  from across the desk; a broken one should be almost gone but still locatable
 *  when the user asks to see it. */
const FILL_ALPHA: Record<ZoneState, number> = {
  fresh: 0.18,
  tested: 0.12,
  mitigated: 0.07,
  broken: 0.035,
};

const EDGE_ALPHA: Record<ZoneState, number> = {
  fresh: 0.9,
  tested: 0.62,
  mitigated: 0.4,
  broken: 0.22,
};

const RGB = {
  demand: [46, 163, 111],
  supply: [212, 87, 79],
} as const;

const LABEL_MIN_HEIGHT = 15; // below this the box cannot hold legible text

function rgba(side: Zone["side"], alpha: number): string {
  const [r, g, b] = RGB[side];
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

interface Box {
  zone: Zone;
  left: number;
  right: number;
  top: number;
  bottom: number;
  proximalY: number;
}

/** Fills, borders and the proximal rule. Drawn beneath the candles so the price
 *  action stays the thing you read first. */
class ZoneBodyRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly boxes: readonly Box[],
    private readonly selectedId: string | null,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;

      for (const box of this.boxes) {
        const { zone } = box;
        const selected = zone.id === this.selectedId;

        const x = Math.round(box.left * kx);
        const w = Math.max(Math.round((box.right - box.left) * kx), 2);
        const y = Math.round(box.top * ky);
        const h = Math.max(Math.round((box.bottom - box.top) * ky), 2);

        ctx.fillStyle = rgba(
          zone.side,
          FILL_ALPHA[zone.state] * (selected ? 1.9 : 1),
        );
        ctx.fillRect(x, y, w, h);

        // An unconfirmed zone can still move as the leg-out extends, so it is
        // drawn dashed. The user should never mistake provisional for settled.
        ctx.save();
        ctx.strokeStyle = rgba(
          zone.side,
          selected ? 1 : EDGE_ALPHA[zone.state],
        );
        ctx.lineWidth = (selected ? 2 : 1) * ky;
        if (!zone.confirmed) ctx.setLineDash([4 * kx, 3 * kx]);
        ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
        ctx.restore();

        // The proximal edge is the only price in the box a trader acts on, so
        // it gets its own brighter rule rather than being one of two identical
        // borders.
        const py = Math.round(box.proximalY * ky);
        ctx.save();
        ctx.strokeStyle = rgba(zone.side, Math.min(1, EDGE_ALPHA[zone.state] + 0.1));
        ctx.lineWidth = 1.5 * ky;
        ctx.beginPath();
        ctx.moveTo(x, py);
        ctx.lineTo(x + w, py);
        ctx.stroke();
        ctx.restore();

      }
    });
  }
}

/**
 * Zone captions. These need their own pane view at `top` z-order.
 *
 * The caption sits at the zone's left edge, which is by definition where the
 * base candles are. Drawn with the fills at `bottom` z-order the candles paint
 * straight over it, and "RBR 0.74" reaches the screen as "BR 0.74". Splitting
 * the renderer is the only way to put fills under the candles and text above
 * them, since a pane view carries one z-order for everything it draws.
 */
class ZoneLabelRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly boxes: readonly Box[],
    private readonly selectedId: string | null,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;

      ctx.save();
      ctx.font = `500 ${10 * ky}px "IBM Plex Mono", ui-monospace, monospace`;
      ctx.textBaseline = "middle";

      for (const box of this.boxes) {
        const { zone } = box;
        const h = box.bottom - box.top;
        if (h < LABEL_MIN_HEIGHT || box.right - box.left < 46) continue;

        const text = `${zone.kind} ${zone.strength.toFixed(2)}`;
        // Clamped into view so a zone whose origin is scrolled off the left
        // stays identifiable.
        const x = Math.max(Math.round(box.left * kx), 0) + 5 * kx;
        const y = Math.round((box.top + h / 2) * ky);
        const width = ctx.measureText(text).width;

        // A plate behind the text. Candles, grid lines and neighbouring zone
        // borders all pass through here; without it the caption is legible
        // against some of them and not others.
        ctx.fillStyle = "rgba(11, 13, 16, 0.72)";
        ctx.fillRect(x - 3 * kx, y - 7 * ky, width + 6 * kx, 14 * ky);

        ctx.fillStyle = rgba(zone.side, zone.id === this.selectedId ? 1 : 0.9);
        ctx.fillText(text, x, y);
      }

      ctx.restore();
    });
  }
}

/**
 * Draws supply and demand zones onto the candlestick series.
 *
 * Coordinates are recomputed in `updateAllViews`, which the library calls on
 * every pan, zoom and data change. Caching pixel positions anywhere else would
 * leave boxes detached from the candles they describe.
 */
export class ZoneSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;
  private zones: readonly Zone[] = [];
  private selectedId: string | null = null;
  private boxes: Box[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      zOrder: () => "bottom", // candles must stay legible on top of the fill
      renderer: () => new ZoneBodyRenderer(this.boxes, this.selectedId),
    },
    {
      zOrder: () => "top", // captions must survive the candles they sit behind
      renderer: () => new ZoneLabelRenderer(this.boxes, this.selectedId),
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
    this.boxes = [];
  }

  /** New data or a new selection only reaches the canvas once the library is
   *  told to repaint; nothing else in the chart changed to trigger it. */
  setZones(zones: readonly Zone[]): void {
    this.zones = zones;
    this.requestUpdate?.();
  }

  setSelected(id: string | null): void {
    if (this.selectedId === id) return;
    this.selectedId = id;
    this.requestUpdate?.();
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }

  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    if (!chart || !series) {
      this.boxes = [];
      return;
    }

    const timeScale = chart.timeScale();
    const rightEdge = timeScale.width();
    const boxes: Box[] = [];

    for (const zone of this.zones) {
      const top = series.priceToCoordinate(zone.top);
      const bottom = series.priceToCoordinate(zone.bottom);
      const proximal = series.priceToCoordinate(zone.proximal);
      if (top === null || bottom === null || proximal === null) continue;

      const left = timeScale.timeToCoordinate(zone.time_from as Time);
      if (left === null) continue;

      // A live zone runs to the last bar, and the chart may be scrolled so that
      // bar sits past the right edge. Clamp rather than drop it: a zone that
      // vanishes when you scroll looks like a bug.
      const rightRaw = timeScale.timeToCoordinate(zone.time_to as Time);
      const right = rightRaw === null ? rightEdge : Math.min(rightRaw, rightEdge);
      if (right <= left) continue;

      boxes.push({ zone, left, right, top, bottom, proximalY: proximal });
    }

    this.boxes = boxes;
  }
}
