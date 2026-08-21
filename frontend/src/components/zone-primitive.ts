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

import type { Zone, ZoneKind, ZoneState } from "@/lib/types";
import { LABEL_GUTTER, claimedLabels, labelFree } from "./structure-primitive";

/** Lifecycle as a SHARE of the ink budget rather than as an absolute alpha.
 *  A fresh zone should still read at a glance from across the desk and a broken
 *  one should still be almost gone but locatable; what changed is that the
 *  number this multiplies now comes from `--zone-fill-near`, so the budget is
 *  tuned in one place. These are the old table (0.18 / 0.12 / 0.07 / 0.035)
 *  divided by its own fresh row, so the ordering is the one that shipped. */
const LIFECYCLE: Record<ZoneState, number> = {
  fresh: 1,
  tested: 0.67,
  mitigated: 0.39,
  broken: 0.19,
};

/** Border opacity by lifecycle. Kept ABSOLUTE and kept at these exact numbers:
 *  `e2e/pixel-truth.mjs` mirrors this table to work out how strong a border of
 *  a given state should read once composited over the background, and asserts
 *  every left border reaches 45% of it. The tier below is applied as a CEILING
 *  on these, never as a replacement, so a decayed zone can never get louder
 *  than its state allows. */
const EDGE_ALPHA: Record<ZoneState, number> = {
  fresh: 0.9,
  tested: 0.62,
  mitigated: 0.4,
  broken: 0.22,
};

/**
 * How many zones keep a FILL.
 *
 * Twelve is one detector's worth of boxes: the shipped display cap is 6 per
 * side, so twelve is the most any single detector can put on screen - which is
 * the density the fill alpha was tuned against, back when three detectors could
 * draw 36 boxes. Five detectors draw up to 60 and the result was measured, on
 * XAUUSD with all five on plus structure: filling every box paints 57.9% of the
 * pane at 15m and 50.9% at 1h, six deep at the worst point. Filling the nearest
 * twelve paints 20.5% and 20.3%. The rest drop to an outline, which still says
 * "a level is here" and costs a 1px stroke.
 *
 * It is also the number that keeps `e2e/pixel-truth.mjs` measuring what it was
 * written to measure: that harness runs ONE detector, so it never draws more
 * than twelve boxes and every zone it reads back is in the near tier - a box,
 * with all four edges. The far tier is a single stroke and that harness asks
 * rectangle questions, so it cannot score the far tier at all; checked rather
 * than assumed, by setting this to 0 to push every zone into the far tier:
 *
 *   - the far PROXIMAL stroke reads 0.95 to 1.00 on tested and mitigated zones,
 *     so the tier is legible where the probe's own model allows it to be;
 *   - it reads 0.05 on FRESH zones, because the probe scales its threshold to
 *     `EDGE_ALPHA[state]` and 0.9 is the loudest row in that table. A 1.5px rule
 *     centred on the pixel grid spreads its alpha over two rows, ~0.75 each, so
 *     `--zone-edge-far` at 0.38 lands at an effective 0.36 against a 0.435 floor;
 *   - at `--zone-edge-far: 0.50` those same fresh zones read 0.98 to 0.99. That
 *     is the token value that would make this tier measurable, and one stroke
 *     per zone can carry 0.50 for less ink than five strokes carried 0.38. The
 *     token belongs to `globals.css`, so this is a measurement and a
 *     recommendation, not a change made here;
 *   - the box checks (left border, distal edge) go unanswered by construction,
 *     because a far zone is deliberately not a box.
 *
 * ponytail: one global list, not a quota per side. Price sitting inside a
 * demand cluster can spend all twelve on demand and leave the nearest supply as
 * an outline. Split it 6/6 by side if that turns out to matter; the global list
 * is the one that answers "what is price nearest to", which is the question.
 */
const FILLED_NEAR_PRICE = 12;

/** The same pair as `--demand` and `--supply` in globals.css, in channels
 *  because this paints to a canvas and needs alpha per stroke. Chosen so the
 *  two differ in LIGHTNESS as well as hue - L* 52.7 against 69.3, a greyscale
 *  contrast of 1.74:1 where the old pair managed 1.25:1 and was effectively one
 *  colour to a red-green deficient reader. See globals.css for the measurement
 *  and for the five files that hold this pair and must move together. */
const RGB = {
  demand: [31, 143, 95],
  supply: [239, 143, 134],
} as const;

const LABEL_MIN_HEIGHT = 15; // below this the box cannot hold legible text

/**
 * The ink budget and the detector patterns live in `globals.css`, so they are
 * read from there rather than restated here - one place to tune, and the
 * reasoning sits next to the numbers.
 *
 * Read once and cached: `getComputedStyle` is a layout read and these are used
 * inside renderers the library calls on every pan and zoom. The consequence is
 * that editing the token at runtime needs a reload, which is the right trade
 * for a value that changes once a quarter.
 *
 * The fallbacks are for a document-less environment (server render, a unit
 * test) only. In the browser the stylesheet is the authority.
 */
const TOKENS = new Map<string, string>();
function cssToken(name: string): string {
  let raw = TOKENS.get(name);
  if (raw === undefined) {
    raw =
      typeof document === "undefined"
        ? ""
        : getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    TOKENS.set(name, raw);
  }
  return raw;
}

function tokenAlpha(name: string, fallback: number): number {
  const n = Number(cssToken(name));
  return Number.isFinite(n) && cssToken(name) !== "" ? n : fallback;
}

/** `--dash-sd: 0` is solid and `--dash-fvg: 1 3` is dotted. Zeroes are dropped,
 *  so the empty array canvas wants for a solid line falls straight out of the
 *  token instead of needing a special case. */
function tokenDash(name: string): number[] {
  return cssToken(name)
    .split(/\s+/)
    .map(Number)
    .filter((n) => n > 0);
}

/**
 * WHICH DETECTOR DREW THIS BOX, and it is on the proximal rule rather than on
 * the border.
 *
 * Hue is not available: green is demand and red is supply, forced by the domain
 * and by the accessibility rule, since hue alone is unreadable to exactly the
 * red-green pair this chart depends on. So it has to be line style - and the
 * border cannot carry it, for two measured reasons:
 *
 *  1. `e2e/pixel-truth.mjs` reads legibility as painted COVERAGE of the line:
 *     every zone's left border must reach 0.6 and at least 80% of tops must.
 *     A dotted [1 3] border covers 25% of its own row, so drawing FVG boxes the
 *     way `--dash-fvg` asks would take the fvg run from 6/6 to 4/6 - not
 *     because a box moved, but because the harness could no longer see it. The
 *     one dashed border in the sample measures 0.70 (the single unconfirmed
 *     zone in .playwright-shots/pixel-before/fvg), which is the margin [4 3]
 *     has and [1 3] does not.
 *  2. The border's dash is already spent: it means "this box may still move as
 *     the leg-out extends", and that meaning was left alone.
 *
 * The proximal rule is the other long stroke on every box, it is drawn ON TOP
 * of a border that stays solid, and it is the only price in the box a trader
 * acts on - so the detector rides on the line the reader is already looking at,
 * and the harness reads the solid border underneath it exactly as before.
 *
 * IFVG and BRK take the pattern of the geometry they were cut from, because a
 * gap read backwards is still a gap. That they were read backwards is the inner
 * stroke further down, which already carries precisely that claim and was
 * chosen for it. So `--dash-ifvg` and `--dash-brk` ([4 3]) go unused ON PURPOSE:
 * [4 3] is what the border spends on "may still move", and one pattern cannot
 * mean two things on one box.
 *
 * What this does NOT separate: an S&D base from an order block. Both are real
 * traded ranges and the tokens give both `0`, solid - the collapse is in the
 * mapping, not in this file. The near-set caption, the hover and the inspector
 * name the detector exactly.
 */
const KIND_DASH: Record<ZoneKind, string> = {
  RBR: "--dash-sd",
  DBR: "--dash-sd",
  DBD: "--dash-sd",
  RBD: "--dash-sd",
  FVG: "--dash-fvg",
  IFVG: "--dash-fvg",
  OB: "--dash-ob",
  BRK: "--dash-ob",
};

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
  /** True when the zone came from a higher timeframe than the chart. Those are
   *  drawn heavier because in a top-down method they are the structure and the
   *  local zones are the refinement, not the other way round. */
  projected: boolean;
  /** One of the `FILLED_NEAR_PRICE` zones nearest the last close. Carries the
   *  fill and the caption; everything else is an outline. */
  near: boolean;
  /** Under the cursor or open in the inspector. Always gets the full treatment,
   *  near or not. */
  lit: boolean;
  /** Distance from the last close to this zone's proximal line, in price. Used
   *  to order captions, so the nearest zone claims its space first. */
  dist: number;
}

/** The box in bitmap pixels. Rounded in one place, because the fill and the
 *  border are painted in separate passes and a half-pixel disagreement between
 *  them reads as an edge drawn in the wrong place. */
function rect(box: Box, kx: number, ky: number) {
  return {
    x: Math.round(box.left * kx),
    y: Math.round(box.top * ky),
    w: Math.max(Math.round((box.right - box.left) * kx), 2),
    h: Math.max(Math.round((box.bottom - box.top) * ky), 2),
  };
}

/**
 * Fills. Drawn beneath the candles so the price action stays the thing you read
 * first - and now only under the few boxes nearest price, which is the ink
 * budget's whole mechanism.
 *
 * A fill is the expensive half of a zone: it paints an area, and area is what
 * turned five detectors into a green mesh with price inside it. An outline
 * costs a 1px stroke and still says "a level is here", so distance from price
 * decides which boxes get the expensive half.
 */
class ZoneFillRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly boxes: readonly Box[]) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const near = tokenAlpha("--zone-fill-near", 0.16);
      const far = tokenAlpha("--zone-fill-far", 0);

      for (const box of this.boxes) {
        const { zone } = box;

        // A zone whose road has been shut is still a real zone - price may well
        // turn there - but the trade it offered is gone, and a wall built by
        // some LATER zone is invisible in this box's own geometry. Halving the
        // fill is the whole treatment: dimmer than its neighbours, still
        // clickable, still carrying its evidence in the inspector.
        const crowded = zone.crowded_at !== null;
        const alpha =
          (box.near || box.lit ? near : far) * LIFECYCLE[zone.state] * (crowded ? 0.45 : 1);
        // `--zone-fill-far` ships at 0, so this is the far tier costing nothing
        // at all rather than costing a transparent fillRect per box per frame.
        if (alpha <= 0) continue;

        const { x, y, w, h } = rect(box, scope.horizontalPixelRatio, scope.verticalPixelRatio);
        ctx.fillStyle = rgba(zone.side, alpha);
        ctx.fillRect(x, y, w, h);
      }
    });
  }
}

/**
 * Borders and the proximal rule, on the same canvas as the candles but painted
 * AFTER them.
 *
 * Widening the box to whole bars fixed the multi-bar case, and it is the reason
 * this renderer cannot fix its own problem by moving anything: an order block
 * box is the range of ONE candle, so its left border sits half a bar spacing
 * from its own candle - the tightest geometry any detector produces.
 * `e2e/pixel-truth.mjs` read that border on 23 of 24 order blocks and the
 * assertion wants all of them; the box itself is right (0.5px top, 1.8px
 * bottom, 0.01 bars of the first base bar outside it), one border simply lost to
 * the neighbouring candle drawn over it.
 *
 * So the stroke moves above the candles instead of the box moving sideways. The
 * fill stays beneath them, which is the half that has to read dimmer than the
 * price action; a 1px border does not. `normal` z-order is what keeps this on
 * the pane canvas rather than the overlay - the library draws bottom views, then
 * the series, then normal views, all onto the same bitmap.
 */
class ZoneEdgeRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly boxes: readonly Box[],
    private readonly selectedId: string | null,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;

      // The ink budget, on the half of the zone that costs almost nothing. A far
      // box keeps its border - that is the point of dropping the fill rather
      // than dropping the box - but it keeps it quieter.
      const nearAlpha = tokenAlpha("--zone-edge-near", 0.85);
      const farAlpha = tokenAlpha("--zone-edge-far", 0.38);
      const hoverAlpha = tokenAlpha("--zone-edge-hover", 1);

      for (const box of this.boxes) {
        const { zone } = box;
        const selected = zone.id === this.selectedId;
        const { x, y, w, h } = rect(box, kx, ky);
        const crowded = zone.crowded_at !== null;

        // The tier is a CEILING on the lifecycle alpha, not a replacement for
        // it. A mitigated zone that happens to be near price must not come back
        // louder than a mitigated zone is allowed to be - the lifecycle ordering
        // is the one thing on this box that survived measurement - so near price
        // can only ever take opacity away, never add it. The hovered box is the
        // exception and is the one place opacity is added, because the reader
        // asked for that box by pointing at it.
        const edge = box.lit
          ? hoverAlpha
          : Math.min(EDGE_ALPHA[zone.state], box.near ? nearAlpha : farAlpha);

        // A FAR ZONE IS NOT DRAWN AS A BOX AT ALL. It gets the proximal stroke
        // below and nothing else.
        //
        // Dropping the fill left 23 far rectangles as outlines, and the result
        // read as a ladder: two horizontal edges per zone plus two verticals,
        // near-parallel, at which point telling which top belongs to which
        // bottom is guesswork. The distal edge is what the box adds over a line,
        // and distal is the STOP - it only matters once the trade is on, which by
        // definition is a zone price has reached, which is the near set. So the
        // far tier says the one thing it is for: a level is here, at this price.
        // One stroke per zone instead of five.
        //
        // What goes with the box: the unconfirmed dash and the inverted inner
        // stroke are both claims ABOUT THE BOX, so they are not drawn when there
        // is no box. Pointing at the level brings all of it back - that is the
        // hover state, and it is the only thing hover is for.
        if (box.near || box.lit) {
          // An unconfirmed zone can still move as the leg-out extends, so it is
          // drawn dashed. Dashed says the BOX may shift, and nothing else: a
          // confirmed zone whose gate verdict is still open is marked in the
          // caption instead, because a second line style would read as a second
          // degree of the same thing. Detector identity did NOT take this over -
          // it is on the proximal rule below, see KIND_DASH.
          ctx.save();
          ctx.strokeStyle = rgba(zone.side, edge * (crowded ? 0.5 : 1));
          ctx.lineWidth = (selected ? 2.5 : box.projected ? 2 : 1) * ky;
          if (!zone.confirmed) ctx.setLineDash([4 * kx, 3 * kx]);
          ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);

          // An INVERTED box gets a second stroke set inside the first. An IFVG or
          // a BRK is not new geometry: it is an existing box read from the other
          // side after price closed through it, and "a box inside a box" is the
          // only cue here that survives a box three pixels tall, where the caption
          // is dropped for want of room. Deliberately NOT a colour of its own and
          // deliberately not heavier: H8 measured the forward move after a
          // post-inversion touch against a control that knows only the trailing
          // 20-bar move and all three detectors came out significantly negative
          // (-0.179, -0.165, -0.274), so an inverted box drawn as a STRONGER box
          // would be stating the opposite of the measurement. It says "this band
          // changed role", which is a fact about the drawing, and nothing else.
          if (zone.inverted_at !== null && w > 8 && h > 8) {
            ctx.strokeRect(x + 3.5, y + 3.5, w - 7, h - 7);
          }
          ctx.restore();
        }

        // The proximal edge is the only price in the box a trader acts on, so it
        // is stroked brighter than the box - and for a far zone it IS the
        // drawing, which is why it is outside the branch above.
        //
        // It is NOT a third line inside the box, and a legend that says so is
        // wrong: proximal is the edge price MEETS FIRST, so on a demand zone it
        // is `top` and on a supply zone it is `bottom`, by construction. Checked
        // rather than assumed - 34 zones across all seven kinds on XAUUSD 1h, and
        // `proximal` equalled `top` on every demand zone and `bottom` on every
        // supply zone, with no exceptions. So this rule always lands ON one of
        // the two borders and its only visible effect is that the entry edge
        // reads brighter than the stop edge. That is the intended effect; the
        // line is right and the description was what needed fixing.
        //
        // It is also where the DETECTOR is written, as a dash pattern - see
        // KIND_DASH for why it is here and not on the border. Because this rule
        // lands on the top or bottom border by construction, dotting it removes
        // ink from a row that still carries a solid border underneath, which is
        // what keeps `pixel-truth.mjs` reading the same edges it always did.
        const py = Math.round(box.proximalY * ky);
        ctx.save();
        ctx.strokeStyle = rgba(zone.side, Math.min(1, edge + 0.1));
        ctx.lineWidth = 1.5 * ky;
        ctx.setLineDash(tokenDash(KIND_DASH[zone.kind]).map((n) => n * kx));
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
 *
 * WHO GETS ONE. The near set, plus the box under the cursor or in the
 * inspector, and nobody else. A caption used to be how a reader told an FVG
 * from an order block, so every box needed one, so at five detectors they
 * collided into "BRK flipped" four times over a stack of boxes. Detector
 * identity is now on the proximal rule (KIND_DASH), which every box carries at
 * any size, so the caption is free to be what it should have been: the label on
 * the handful of boxes price is actually near. For the rest the outline IS the
 * annotation, and pointing at one names it.
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

      // Nearest first, with the pointed-at box ahead of everything. When the
      // pane runs out of room it has to be the FURTHEST caption that is lost,
      // for the same reason the structure overlay lets its minor scale lose one
      // first: the near box is the one being priced against.
      const captioned = [...this.boxes]
        .filter((b) => b.lit || b.near)
        .sort((a, b) => (a.lit === b.lit ? a.dist - b.dist : a.lit ? -1 : 1));

      // Same collision mechanism as `structure-primitive.ts` and now the same
      // LIST: claim a rectangle, walk upward while the space is taken, drop the
      // caption rather than overprint it. Four steps rather than that file's
      // six, because a zone caption names the box it sits in - past about four
      // rows it is closer to a neighbouring box than to its own and a caption on
      // the wrong box is worse than no caption. What is dropped is still drawn,
      // still clickable and still named on hover.
      //
      // Seeded with the structure captions, which are already on screen: they
      // paint at `normal` and this paints at `top`, so structure has claimed its
      // space by the time this runs. Zones yield to structure and not the other
      // way round - a structure label is anchored to the bar that broke, while
      // this one may walk or be dropped. A COPY, because the crosshair repaints
      // the top canvas on its own and this pass therefore runs on frames the
      // structure pass does not; writing into the shared list would let zone
      // captions from one mouse move block zone captions on the next.
      const placed = claimedLabels.slice();
      const free = (b: { x: number; y: number; w: number; h: number }) => labelFree(b, placed);

      for (const box of captioned) {
        const { zone } = box;
        const h = box.bottom - box.top;
        if (h < LABEL_MIN_HEIGHT || box.right - box.left < 34) continue;

        // Formation name only. The caption used to carry the composite score,
        // which reads as a quality rating on a chart; calibration showed it
        // does not predict the outcome, so putting it here was a claim the
        // number cannot support.
        //
        // LIFECYCLE IS CARRIED BY THE BORDER, NOT BY THE FILL, and this comment
        // said the fill for a long time. The vision audit in `e2e/chart-audit.mjs`
        // reported that it could not tell a mitigated box from a fresh one by eye,
        // so the two channels were measured against `--bg` #0b0d10:
        //
        //   FILL   at `--zone-fill-near` 0.16 times LIFECYCLE
        //          demand: fresh/tested 1.064:1, tested/mitigated 1.046:1,
        //          mitigated/broken 1.028:1, and fresh/broken - three steps apart -
        //          only 1.144:1.
        //   BORDER at EDGE_ALPHA
        //          demand: 1.62 / 1.48 / 1.33 adjacent, and 3.20:1 across the whole
        //          range. Supply: 1.82 / 1.70 / 1.54, and 4.75:1 across.
        //
        // Twenty to sixty times the separation, so the signal is real and it is in
        // the stroke. The auditor was right and the sentence was wrong: it read the
        // legend, looked at the fills, and reported the mismatch. Nothing about the
        // painting changed here - the fill's job is to say a level is present at a
        // glance and it does that - only the claim about which channel a reader
        // should be reading. The panel still carries the state as a word.
        // A projected zone says which timeframe drew it. Two boxes at the same
        // price mean different things when one is H4 and one is M15, and the
        // chart cannot show that with colour alone.
        // `settled` is the other half of the story `confirmed` was carrying
        // alone. A confirmed zone's box no longer shifts, but its gate verdict
        // still can: an audit measured a confirmed zone's departure_atr growing
        // on 101 of 599 bar formations and its state changing 24 times, so a box
        // drawn as passing can still end up failing. Said in a word, not in a
        // line style: dashed already means "the box may move", and one visual
        // vocabulary cannot carry two different claims.
        // "flipped" for an inverted box, because IFVG and BRK are acronyms and
        // the one thing they mean that FVG and OB do not is that this band's ROLE
        // changed on some bar. The word is about the drawing and stops there: it
        // does not say the flip makes the box stronger or points anywhere, and it
        // must not, because H8 measured a post-inversion touch as significantly
        // WORSE than a control with no box at all.
        const text =
          (box.projected ? `${zone.timeframe} ${zone.kind}` : zone.kind) +
          (zone.inverted_at !== null ? " flipped" : "") +
          (zone.confirmed && !zone.settled ? " unsettled" : "");
        // CLAMPED AT BOTH EDGES, and the right one was missing.
        //
        // A zone whose origin is scrolled off the left needs the first clamp to
        // stay identifiable, and that one has been here a while. Nothing held the
        // other end, so a caption on a box near the right edge ran off the plot
        // into the price scale and lost its last characters - `RBR unsettled`
        // rendering as `RBR unsettle`, which reads as a word somebody misspelled
        // rather than a plate that did not fit. Found by the vision audit in
        // `e2e/chart-audit.mjs` looking at a screenshot, which is the only
        // instrument here that could have: every pixel assertion in the suite
        // checks where a BOX is, and this is about where its NAME is.
        //
        // The plate is pushed left to fit rather than the text being truncated,
        // because a caption is either readable or it is noise, and a caption
        // sitting slightly left of its own left edge still names the right box.
        const width = ctx.measureText(text).width;
        const plateWidth = width + 6 * kx;
        // `LABEL_GUTTER` is the name column every other primitive keeps clear, so
        // a zone caption stops where a level's name begins instead of printing
        // through it.
        const limit = scope.bitmapSize.width - LABEL_GUTTER * kx - plateWidth;
        const x =
          Math.min(Math.max(Math.round(box.left * kx), 0), Math.max(limit, 0)) + 5 * kx;
        const plate = { x: x - 3 * kx, y: 0, w: plateWidth, h: 14 * ky };

        let y = Math.round((box.top + h / 2) * ky);
        plate.y = y - 7 * ky;
        for (let step = 0; step < 4 && !free(plate); step++) {
          y -= plate.h;
          plate.y = y - 7 * ky;
        }
        if (!free(plate)) continue;
        placed.push({ ...plate });

        // A plate behind the text. Candles, grid lines and neighbouring zone
        // borders all pass through here; without it the caption is legible
        // against some of them and not others.
        //
        // 0.92 rather than 0.72, and it is the same correction the structure
        // plates needed: a caption's contrast is against WHAT IS BEHIND IT, and
        // at 0.72 what is behind it is still a quarter of a candle body. The
        // caption ink measures 6.1:1 for demand and 4.9:1 for supply against
        // #0b0d10 - both fine - and none of that survives a plate that does not
        // reach the background.
        ctx.fillStyle = "rgba(11, 13, 16, 0.92)";
        ctx.fillRect(plate.x, plate.y, plate.w, plate.h);

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
  private hoveredId: string | null = null;
  private chartInterval = "";
  /** Last close of the loaded series, which is what "near price" is measured
   *  from. Null before any candle has arrived, and then nothing is near. */
  private lastClose: number | null = null;
  private boxes: Box[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      zOrder: () => "bottom", // candles must stay legible on top of the fill
      renderer: () => new ZoneFillRenderer(this.boxes),
    },
    {
      zOrder: () => "normal", // borders must survive the candle they were cut from
      renderer: () => new ZoneEdgeRenderer(this.boxes, this.selectedId),
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
   *  told to repaint; nothing else in the chart changed to trigger it.
   *
   *  `lastClose` comes in from the component rather than being read off the
   *  series, because the chart holds the candles as coordinates and this needs
   *  the price. It is only ever used for "how far is price from this zone". */
  setZones(zones: readonly Zone[], chartInterval: string, lastClose: number | null): void {
    this.zones = zones;
    this.chartInterval = chartInterval;
    this.lastClose = lastClose;
    this.requestUpdate?.();
  }

  setSelected(id: string | null): void {
    if (this.selectedId === id) return;
    this.selectedId = id;
    this.requestUpdate?.();
  }

  /** The box under the pointer. Guarded because the crosshair fires on every
   *  mouse move and a repaint per pixel of travel is a repaint for nothing. */
  setHovered(id: string | null): void {
    if (this.hoveredId === id) return;
    this.hoveredId = id;
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
    // `timeToCoordinate` returns a bar's CENTRE. Anchoring the box to those
    // coordinates draws it from the middle of the first base bar to the middle
    // of the last, which is wrong twice over: half of the first base bar hangs
    // outside the box that was cut from it, and the left border lands on that
    // candle's own x-position, where the candle - drawn on top - hides it.
    //
    // Both were measured before this line existed. `e2e/pixel-truth.mjs` reads
    // the canvas back and found the left border legible on 2 of 8 zones at 15m
    // and 2 of 9 at 1h, with a median of ~20px of the first base bar outside
    // its own box. It is also the reason four visual reviewers agreed the box
    // was padded onto neighbouring impulse candles when the arithmetic says the
    // padding is 0.0%: they could not see where the box actually ended.
    const halfBar = timeScale.options().barSpacing / 2;
    const boxes: Box[] = [];

    // THE INK BUDGET. Which boxes are near price, measured from the last close
    // to the PROXIMAL line - the edge price meets first, and so the edge the
    // trade is priced from. Distal would rank a tall zone as far away while
    // price sits on its entry.
    //
    // Deliberately a property of the DATA and not of the view: it must not
    // change as the reader pans, or the same zone would gain and lose its fill
    // by scrolling and the chart would look like it was reporting something.
    const near = new Set(
      this.lastClose === null
        ? []
        : [...this.zones]
            .sort(
              (a, b) =>
                Math.abs(this.lastClose! - a.proximal) - Math.abs(this.lastClose! - b.proximal),
            )
            .slice(0, FILLED_NEAR_PRICE)
            .map((z) => z.id),
    );

    for (const zone of this.zones) {
      const top = series.priceToCoordinate(zone.top);
      const bottom = series.priceToCoordinate(zone.bottom);
      const proximal = series.priceToCoordinate(zone.proximal);
      if (top === null || bottom === null || proximal === null) continue;

      const leftCentre = timeScale.timeToCoordinate(zone.time_from as Time);
      if (leftCentre === null) continue;
      const left = leftCentre - halfBar;

      // A live zone runs to the last bar, and the chart may be scrolled so that
      // bar sits past the right edge. Clamp rather than drop it: a zone that
      // vanishes when you scroll looks like a bug.
      const rightRaw = timeScale.timeToCoordinate(zone.time_to as Time);
      const right =
        rightRaw === null ? rightEdge : Math.min(rightRaw + halfBar, rightEdge);
      if (right <= left) continue;

      boxes.push({
        zone,
        left,
        right,
        top,
        bottom,
        proximalY: proximal,
        projected: Boolean(zone.timeframe) && zone.timeframe !== this.chartInterval,
        near: near.has(zone.id),
        lit: zone.id === this.selectedId || zone.id === this.hoveredId,
        dist: this.lastClose === null ? Infinity : Math.abs(this.lastClose - zone.proximal),
      });
    }

    this.boxes = boxes;
  }
}
