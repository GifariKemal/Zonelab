import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
} from "lightweight-charts";
import type { CanvasRenderingTarget2D } from "fancy-canvas";

import type { VortexDial } from "@/lib/types";
import { claimedLabels } from "./structure-primitive";
import { ink } from "./ink";

/**
 * The 3-6-9 dial: six cycle rings, nine sectors, and where the newest bar sits.
 *
 * WHY IT IS A CORNER DIAL AND NOT A FULL-PANE MANDALA. A ring diagram is polar
 * and this canvas is a time-by-price plane, so there is no honest way to anchor
 * a circle to it - stretched across the pane it would imply the centre is a
 * price and the radius a distance, and it is neither. `cycle-ribbon.tsx` made
 * the same call for the same reason and put the quarter ribbon in its own strip
 * rather than over the candles. This one stays on the canvas because it is
 * small, fixed, and reads as an instrument in the corner rather than as an
 * annotation of any bar.
 *
 * There is a second reason and it is measured: five detectors alone paint 31.6%
 * of this chart, and `app/layers.py` records that past roughly a third the
 * boxes stop annotating price and become its background. A pane-wide dial would
 * spend that budget on an object that reads no price.
 *
 * ONE INK, THE DIMMEST FAMILY. `ink.ts` gives `grid` to time-anchored context -
 * quarter boxes, session shading - and that is exactly what this is. Green and
 * salmon mean demand and supply on this canvas and gold means a control; the
 * dial may not touch any of them, because a lit node in a direction colour
 * would smuggle in a forecast the arithmetic cannot make.
 *
 * WHAT THE SHAPES MEAN, all of it derivable and none of it mystical:
 *
 *  - six circles, innermost the fastest cycle (session) and outermost the year;
 *  - nine spokes, one per sector, sector 1 opening at twelve o'clock and
 *    running clockwise;
 *  - a node where `digital_root(r * k)` is 3, 6 or 9. That happens exactly when
 *    3 divides `r * k`, so rings 1, 2, 4 and 5 carry three nodes at k = 3, 6, 9
 *    and rings 3 and 6 carry nine. The two full rings are drawn as a BRIGHTER
 *    CONTINUOUS CIRCLE rather than as nine dots, so the reader sees that the
 *    whole ring qualifies instead of counting;
 *  - one triangle at the outer edge joining sectors 3, 6 and 9. It is the same
 *    triangle on every ring that has one, so it is drawn once;
 *  - a filled marker per ring at the sector the newest CLOSED bar is in, and a
 *    caption spelling those six positions out, which is the only part of the
 *    dial that changes as the chart moves.
 *
 * NOT A QUARTER. Nine does not divide four, so a sector is not a quarter and
 * must never be read as one - Q2 of a day cycle spans sectors 3, 4 and part of
 * 5. Quarters are read off the ribbon under the chart.
 *
 * MEMORY. State is one reference, replaced whole by `setDial` and nulled by
 * `detached`. Nothing accumulates across redraws and no listener is registered,
 * which is what `e2e/vortex.mjs` measures rather than assumes.
 */

/** Sector 1 opens at twelve o'clock; angles run clockwise. */
const TOP = -Math.PI / 2;

const RING_LINE = ink("grid", 0.3);
/** Rings whose r is a multiple of three: every sector is lit, so the ring is
 *  continuous rather than dotted. */
const RING_FULL = ink("grid", 0.58);
const SPOKE = ink("grid", 0.16);
const NODE = ink("grid", 0.62);
const TRIANGLE = ink("grid", 0.72);
const LIVE = ink("grid", 0.95);
const CAPTION = ink("grid", 0.88);
const SECTOR_NUM = ink("grid", 0.4);
const PLATE = "rgba(11, 13, 16, 0.78)";

/** Below this the dial would be a smudge, so it is not drawn at all. An
 *  illegible instrument in the corner is worse than an absent one: it still
 *  costs ink and still invites a reading. */
const MIN_PANE_W = 320;
const MIN_PANE_H = 220;

/** Outer radius as a share of the smaller pane side, then clamped. The clamp is
 *  what keeps it an instrument: unclamped it would grow into the mandala the
 *  module docstring argues against. */
const RADIUS_SHARE = 0.16;
const RADIUS_MIN = 46;
const RADIUS_MAX = 104;

/** Fraction of the outer radius left empty in the middle. Without a hole the
 *  six rings crowd into the centre and the innermost two are indistinguishable. */
const HOLE = 0.3;

/** Left margin, and the floor the dial must stay above.
 *
 * THE FLOOR IS NOT PADDING, it is a reserved rectangle. `session-primitive.ts`
 * measured the library's own attribution mark at five viewports and two pixel
 * ratios and got the same box every time: `#tv-attr-logo`, 35 x 19 CSS pixels
 * at x = 10, sitting 10 above the canvas floor, with 2 of padding claimed
 * around it. It is a DOM anchor above the canvas, so it wins every overlap it
 * is in and nothing drawn here could see it - a caption underneath it is not a
 * dim caption, it is a missing one with a white glyph on top.
 *
 * 10 gap + 19 mark + 2 pad + 4 clearance = 35. The dial's lowest pixel, which
 * is the bottom of its caption plate, stops there. Found by reading that file
 * before drawing rather than by looking at a screenshot afterwards, which is
 * how the same corner caught a zone caption once already. */
const PAD = 14;
const FLOOR = 35;

/** Centre angle of sector `k`, counted from 1. */
function angleOf(k: number, sectors: number): number {
  return TOP + ((k - 0.5) * 2 * Math.PI) / sectors;
}

class VortexRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly dial: VortexDial | null) {}

  draw(target: CanvasRenderingTarget2D): void {
    const dial = this.dial;
    if (!dial || dial.rings.length === 0 || dial.sectors <= 0) return;

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      // CSS pixels, because every constant above is a CSS pixel and the two
      // ratios are not always equal.
      const paneW = scope.bitmapSize.width / kx;
      const paneH = scope.bitmapSize.height / ky;
      if (paneW < MIN_PANE_W || paneH < MIN_PANE_H) return;

      const sectors = dial.sectors;
      const rings = dial.rings;
      const lit = new Set(dial.lit);

      const capH = 13;
      const outer = Math.min(
        RADIUS_MAX,
        Math.max(RADIUS_MIN, Math.min(paneW, paneH) * RADIUS_SHARE),
      );
      // Room for the sector digits outside the outer ring, and the caption
      // under it.
      const reach = outer + 11;
      const cx = PAD + reach;
      const cy = paneH - FLOOR - capH - reach;
      if (cy - reach < 0 || cx + reach > paneW) return;

      // The dial cannot move, so it claims its footprint rather than yielding
      // it: a zone caption printed across the rings would make both unreadable,
      // and the caption is the one that can go somewhere else. Claimed AFTER
      // the session pass resets the list, which is why this primitive attaches
      // where it does in `chart.tsx`.
      claimedLabels.push({
        x: cx - reach,
        y: cy - reach,
        w: reach * 2,
        h: reach * 2 + capH,
      });

      const X = (v: number) => v * kx;
      const Y = (v: number) => v * ky;
      const px = Math.max(1, Math.round(kx));

      ctx.save();
      ctx.lineWidth = px;

      // ---- spokes, drawn first so every ring crosses on top of them --------
      ctx.strokeStyle = SPOKE;
      ctx.beginPath();
      for (let k = 0; k < sectors; k += 1) {
        const a = TOP + (k * 2 * Math.PI) / sectors;
        const cos = Math.cos(a);
        const sin = Math.sin(a);
        ctx.moveTo(X(cx + cos * outer * HOLE), Y(cy + sin * outer * HOLE));
        ctx.lineTo(X(cx + cos * outer), Y(cy + sin * outer));
      }
      ctx.stroke();

      // ---- the six rings ---------------------------------------------------
      const radiusOf = (row: number) =>
        outer * (HOLE + ((1 - HOLE) * (row + 1)) / rings.length);

      rings.forEach((_ring, row) => {
        const radius = radiusOf(row);
        const row9 = dial.matrix[row] ?? [];
        // Every sector lit means r is a multiple of three. Say it with a
        // continuous brighter circle instead of nine dots the reader has to
        // count.
        const whole = row9.length === sectors && row9.every((v) => lit.has(v));
        ctx.strokeStyle = whole ? RING_FULL : RING_LINE;
        ctx.lineWidth = whole ? Math.max(1, Math.round(1.6 * kx)) : px;
        ctx.beginPath();
        ctx.arc(X(cx), Y(cy), radius * kx, 0, Math.PI * 2);
        ctx.stroke();
        ctx.lineWidth = px;

        if (whole) return;
        ctx.fillStyle = NODE;
        for (let k = 1; k <= sectors; k += 1) {
          if (!lit.has(row9[k - 1])) continue;
          const a = angleOf(k, sectors);
          ctx.beginPath();
          ctx.arc(
            X(cx + Math.cos(a) * radius),
            Y(cy + Math.sin(a) * radius),
            Math.max(1, 1.9 * kx),
            0,
            Math.PI * 2,
          );
          ctx.fill();
        }
      });

      // ---- the triangle ----------------------------------------------------
      // Sectors 3, 6 and 9 on the outer edge. Read off `lit` and the matrix
      // rather than written as the literal 3, 6, 9: if the backend's lit set
      // ever changed, a hardcoded triangle here would keep drawing the old one.
      const first = dial.matrix[0] ?? [];
      const corners: number[] = [];
      for (let k = 1; k <= sectors; k += 1) {
        if (lit.has(first[k - 1])) corners.push(k);
      }
      if (corners.length >= 3) {
        ctx.strokeStyle = TRIANGLE;
        ctx.lineWidth = Math.max(1, Math.round(1.2 * kx));
        ctx.beginPath();
        corners.forEach((k, i) => {
          const a = angleOf(k, sectors);
          const x = X(cx + Math.cos(a) * outer);
          const y = Y(cy + Math.sin(a) * outer);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();
        ctx.stroke();
        ctx.lineWidth = px;
      }

      // ---- where the newest closed bar is ----------------------------------
      ctx.fillStyle = LIVE;
      rings.forEach((ring, row) => {
        const a = angleOf(ring.sector, sectors);
        const radius = radiusOf(row);
        ctx.beginPath();
        ctx.arc(
          X(cx + Math.cos(a) * radius),
          Y(cy + Math.sin(a) * radius),
          Math.max(1, 2.4 * kx),
          0,
          Math.PI * 2,
        );
        ctx.fill();
      });

      // ---- sector digits ---------------------------------------------------
      ctx.font = `${Math.round(8 * ky)}px ui-monospace, monospace`;
      ctx.fillStyle = SECTOR_NUM;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      for (let k = 1; k <= sectors; k += 1) {
        const a = angleOf(k, sectors);
        ctx.fillText(
          String(k),
          X(cx + Math.cos(a) * (outer + 7)),
          Y(cy + Math.sin(a) * (outer + 7)),
        );
      }

      // ---- caption: the six live positions ---------------------------------
      // The initials are distinct across the ladder - Session, Daily, Weekly,
      // Monthly, Quarterly, Yearly - so one letter is enough and the line stays
      // inside the dial's own width. This is the only part that moves.
      const caption = rings.map((r) => `${r.label[0]}${r.sector}`).join(" ");
      ctx.font = `${Math.round(9 * ky)}px ui-monospace, monospace`;
      ctx.textAlign = "left";
      const tw = ctx.measureText(caption).width / kx;
      const bx = cx - tw / 2 - 3;
      const by = cy + reach + 1;
      ctx.fillStyle = PLATE;
      ctx.fillRect(X(bx), Y(by), X(tw + 6), Y(capH));
      ctx.fillStyle = CAPTION;
      ctx.fillText(caption, X(bx + 3), Y(by + capH / 2));

      ctx.restore();
    });
  }
}

export class VortexSeriesPrimitive implements ISeriesPrimitive<Time> {
  private requestUpdate: (() => void) | null = null;
  private dial: VortexDial | null = null;

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      // BEHIND THE CANDLES. The dial is context the bars sit on, like the
      // session shading, and a bar must never be obscured by an object that
      // reads no price.
      zOrder: () => "bottom",
      renderer: () => new VortexRenderer(this.dial),
    },
  ];

  attached(param: SeriesAttachedParameter<Time>): void {
    this.requestUpdate = param.requestUpdate;
  }

  detached(): void {
    this.requestUpdate = null;
    this.dial = null;
  }

  /** Replaces the payload whole. Null switches the dial off, which is what the
   *  layer toggle sends and what an empty series produces upstream. */
  setDial(dial: VortexDial | null): void {
    this.dial = dial;
    this.requestUpdate?.();
  }

  /** Nothing to recompute per frame: the geometry needs the pane size, which is
   *  only known inside `draw`, and the payload is already in wire form. */
  updateAllViews(): void {}

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}

