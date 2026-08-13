/**
 * Does the box that reaches the SCREEN sit where the API says it does?
 *
 *   node e2e/pixel-truth.mjs <out-dir> [interval] [bars]
 *
 * Everything already in the suite checks numbers against numbers. The contract
 * tests compare the zone record to arithmetic on the candles; `zone-audit.mjs`
 * compares it again, in the browser, to the candles the page fetched. Neither
 * one looks at a single painted pixel, so a rendering bug that puts a correct
 * zone in the wrong place would pass all of them.
 *
 * That is not hypothetical here. Four visual reviewers reported the box padded
 * out onto neighbouring impulse candles; the arithmetic said the padding is
 * 0.0% and the claim was refuted. Both were right about what they measured:
 * the numbers are correct AND the drawing is hard to read, because the border
 * lands on the base candle's own x-position. Eyes cannot separate those two
 * cases and neither can any test written so far.
 *
 * So this reads the canvas back. For each zone it finds the painted borders by
 * their colour coverage, converts those pixel rows back to prices through the
 * chart's own scale, and compares against the zone record. It also measures
 * what the reviewers were actually looking at: how much of the base the box
 * covers horizontally.
 */
import { writeFileSync } from "node:fs";
import { chromium } from "playwright";

const OUT = process.argv[2];
const INTERVAL = process.argv[3] ?? "15m";
const BARS = Number(process.argv[4] ?? 500);
const API = "http://127.0.0.1:8100";

// The border is a 1px stroke at a half-pixel offset and the box is rounded to
// whole pixels, so up to two pixels of disagreement is the rasteriser rather
// than a defect. Anything above that is the drawing being in the wrong place.
const EDGE_TOL_PX = 2.0;

const results = [];
const check = (n, p, d = "") => results.push(`${p ? "PASS" : "FAIL"}  ${n}${d ? ` :: ${d}` : ""}`);

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
// deviceScaleFactor 1 keeps CSS pixels and bitmap pixels the same number, so a
// measured error is in the same unit the renderer reasons in.
const page = await browser.newPage({
  viewport: { width: 1400, height: 800 },
  deviceScaleFactor: 1,
});
await page.goto("http://127.0.0.1:3100/", { waitUntil: "networkidle" });
await page.waitForTimeout(6000);

await page.locator(`div[aria-label="Timeframe"] button:text-is("${INTERVAL}")`).click();
await page.locator("select").nth(2).selectOption(String(BARS));
await page.waitForTimeout(6000);

const drawn = await page.evaluate(
  async ([api, interval, bars]) => {
    const r = await fetch(`${api}/api/draw`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: "XAUUSD", interval, bars, detectors: ["supply_demand"] }),
    });
    return r.json();
  },
  [API, INTERVAL, BARS],
);

const { candles, drawing } = drawn;

// Same guard the zone audit needs: a measurement taken against a series the
// chart is not showing is not a measurement of anything, and it looks normal.
const onScreen = await page.evaluate(() => {
  const range = window.__zonelabChart.chart.timeScale().getVisibleRange();
  return range ? { from: Number(range.from), to: Number(range.to) } : null;
});
if (!onScreen || onScreen.to < candles[0].time || onScreen.from > candles.at(-1).time) {
  console.error(`the chart is not showing the ${INTERVAL} series that was fetched`);
  await browser.close();
  process.exit(2);
}

// Injected once and called per zone. Kept in the page because it needs the
// canvas bitmap, and shipping a 1400x800 ImageData over the bridge per zone is
// the slow way to ask the same question.
await page.evaluate(() => {
  const BG_TOL = 12;

  /** How strongly a pixel reads as this zone's colour. The candle body colours
   *  are the SAME rgb as the zone colours, so this cannot isolate a zone on its
   *  own - it is only ever used through the coverage scan below, which asks for
   *  a line that spans the whole box rather than for any matching pixel. */
  const sideness = (d, i, side) =>
    side === "demand"
      ? Math.min(d[i + 1] - d[i], d[i + 1] - d[i + 2])
      : Math.min(d[i] - d[i + 1], d[i] - d[i + 2]);

  window.__pixelProbe = {
    /** The pane canvas: the one carrying the candles and the zone fills, not
     *  the top layer that carries only crosshair and captions. Picked by which
     *  one actually has paint on it rather than by DOM order, which is an
     *  internal detail of the charting library.
     *
     *  The alpha test is not a detail. The overlay canvases are fully
     *  transparent, and a transparent pixel reads as rgb(0,0,0) - which is
     *  FURTHER from the background than the chart's own paint is, so a
     *  colour-only test scores an empty layer as the busiest one and every
     *  later measurement is taken against a blank bitmap. It scores zero
     *  everywhere, which looks exactly like a drawing that is missing. */
    grab() {
      const canvases = [...document.querySelectorAll("canvas")];
      let best = null;
      for (const c of canvases) {
        if (!c.width || !c.height) continue;
        const ctx = c.getContext("2d", { willReadFrequently: true });
        const img = ctx.getImageData(0, 0, c.width, c.height);
        const d = img.data;
        let painted = 0;
        // Every 40th pixel is plenty to tell a chart from a caption layer.
        for (let i = 0; i < d.length; i += 4 * 40) {
          if (d[i + 3] < 250) continue;
          if (Math.abs(d[i] - 11) + Math.abs(d[i + 1] - 13) + Math.abs(d[i + 2] - 16) > BG_TOL) {
            painted++;
          }
        }
        if (!best || painted > best.painted) best = { img, painted, w: c.width, h: c.height };
      }
      window.__pixelProbe._img = best.img;
      return { w: best.w, h: best.h, painted: best.painted };
    },

    /** Fraction of a row that reaches the border's own colour strength. The
     *  horizontal borders span the whole box and score near 1; the fill rows
     *  between them carry the same hue at a fifth of the opacity and fall below
     *  the threshold; rows outside carry only whatever candles cross them.
     *
     *  A count, never a mean. Price returns into the zone, so most of the box
     *  width is candles, and one opposite-coloured candle body scores strongly
     *  negative - enough to drag the mean of the REAL border row below the mean
     *  of an empty one. That is not a theoretical worry: it is what hid the
     *  bottom border of the first zone measured and reported it as a 6px
     *  drawing error. Counting pixels that reach the border's strength cannot
     *  be cancelled out that way. */
    frac(fixed, from, to, side, minStrength, vertical) {
      const img = window.__pixelProbe._img;
      const limit = vertical ? img.width : img.height;
      if (fixed < 0 || fixed >= limit) return -1;
      const a = Math.max(0, Math.round(from));
      const b = Math.min((vertical ? img.height : img.width) - 1, Math.round(to));
      if (b <= a) return -1;
      let hit = 0;
      for (let i = a; i <= b; i++) {
        const idx = vertical ? (i * img.width + fixed) * 4 : (fixed * img.width + i) * 4;
        if (sideness(img.data, idx, side) >= minStrength) hit++;
      }
      return hit / (b - a + 1);
    },
  };
});

const rows = [];

for (const [n, zone] of drawing.zones.entries()) {
  const a = zone.anatomy;
  const from = candles[Math.max(0, a.leg_in_from - 4)].time;
  const to = candles[Math.min(candles.length - 1, a.leg_out_to + 10)].time;

  await page.evaluate(
    ([f, t]) => window.__zonelabChart.chart.timeScale().setVisibleRange({ from: f, to: t }),
    [from, to],
  );
  await page.waitForTimeout(350);

  const measured = await page.evaluate(
    ([zoneIn, baseFirstTime, baseLastTime]) => {
      const { chart, series } = window.__zonelabChart;
      const ts = chart.timeScale();
      const probe = window.__pixelProbe;
      probe.grab();

      // What the chart's own scales say. These come from the charting library,
      // not from the primitive, so agreeing with them is not the primitive
      // agreeing with itself.
      const expTop = series.priceToCoordinate(zoneIn.top);
      const expBottom = series.priceToCoordinate(zoneIn.bottom);
      const expProximal = series.priceToCoordinate(zoneIn.proximal);
      const barSpacing = ts.options().barSpacing;
      const baseFirstX = ts.timeToCoordinate(baseFirstTime);
      const baseLastX = ts.timeToCoordinate(baseLastTime);
      if (expTop === null || expBottom === null || baseFirstX === null) return null;

      // Where the left edge SHOULD be: the left edge of the first base bar.
      // `timeToCoordinate` gives that bar's centre, so the box has to reach
      // half a bar further left to actually contain the candle it was cut from.
      // Derived from the base bar rather than from `zone.time_from` on purpose,
      // so this stays a statement about the candles even if the two ever drift
      // apart.
      const expLeft = baseFirstX - barSpacing / 2;

      const rightEdge = ts.width();
      const rightRaw = ts.timeToCoordinate(zoneIn.time_to);
      const expRight = rightRaw === null ? rightEdge : Math.min(rightRaw, rightEdge);

      // Search inset from the corners: the vertical borders would otherwise
      // contribute to every row's score and blunt the peak.
      const xa = expLeft + 4;
      const xb = Math.min(expRight, rightEdge) - 4;

      // The NEAREST line to where the edge is supposed to be, not the strongest
      // one in the window. The question being asked is "is there a border
      // here", and on a busy chart the window can hold a second zone's border
      // as well as this one's - a plain argmax then answers a question nobody
      // asked and reports the distance to someone else's box as this box's
      // error. Falls back to the strongest reading when nothing in the window
      // qualifies, so a genuine miss stays a miss rather than becoming a pass.
      const LINE = 0.6;
      const peak = (center, span, score) => {
        let bestAt = null;
        let best = -Infinity;
        for (let d = 0; d <= span; d++) {
          for (const p of d === 0 ? [Math.round(center)] : [Math.round(center - d), Math.round(center + d)]) {
            const s = score(p);
            if (s >= LINE) return { at: p, strength: s };
            if (s > best) {
              best = s;
              bestAt = p;
            }
          }
        }
        return { at: bestAt, strength: best };
      };

      const side = zoneIn.side;
      const boxH = expBottom - expTop;
      const boxW = xb - xa;

      // What a border of this zone's opacity should look like once composited
      // over the background. Mirrors the renderer's own tables deliberately:
      // the threshold has to follow the zone's lifecycle, because a broken
      // zone's border is a quarter the opacity of a fresh one's, and one fixed
      // number is either blind to the faded end or trips on the fill.
      const RGB = { demand: [46, 163, 111], supply: [212, 87, 79] };
      const EDGE_ALPHA = { fresh: 0.9, tested: 0.62, mitigated: 0.4, broken: 0.22 };
      const BG = [11, 13, 16];
      const c = RGB[side].map((v, i) => BG[i] + EDGE_ALPHA[zoneIn.state] * (v - BG[i]));
      const edgeSideness =
        side === "demand" ? Math.min(c[1] - c[0], c[1] - c[2]) : Math.min(c[0] - c[1], c[0] - c[2]);
      // Not the full strength: the stroke is 1px and antialiasing bleeds some
      // of it into the neighbouring row.
      const minStrength = Math.max(3, edgeSideness * 0.45);
      const rowFrac = (y) => probe.frac(y, xa, xb, side, minStrength, false);

      // Search windows stay at +-6px on purpose. The question is whether the
      // border is where the scale says, not where the nearest strong line is;
      // a window as wide as a bar lets the scan walk onto a neighbouring candle
      // and report a 44px error that is really a probe that went looking.
      //
      // The two horizontal borders are 3px apart on a thin zone, so their
      // windows overlap and the bottom scan can lock onto the top border.
      // Halve the window rather than report that as a 6px drawing error.
      const vSpan = Math.max(1, Math.min(6, Math.floor(boxH / 2)));
      const topHit = peak(expTop, vSpan, rowFrac);
      const bottomHit = peak(expBottom, vSpan, rowFrac);
      // Scan the middle of the box only, clear of the horizontal borders which
      // would otherwise contribute to every column equally.
      const inset = Math.min(3, Math.max(1, Math.floor(boxH / 4)));
      const leftHit = peak(expLeft, 6, (x) =>
        probe.frac(x, expTop + inset, expBottom - inset, side, minStrength, true),
      );

      const profile = (center, span, score) =>
        Array.from({ length: 2 * span + 1 }, (_, i) =>
          Math.round(score(Math.round(center - span + i)) * 100) / 100,
        );

      return {
        expTop,
        expBottom,
        expProximal,
        expLeft,
        expRight,
        barSpacing,
        baseFirstX,
        baseLastX,
        boxH,
        boxW,
        topHit,
        bottomHit,
        leftHit,
        // The scan's raw view of each edge, kept in the record. A peak with no
        // profile behind it cannot be told apart from a tie, and a tie is what
        // a broken probe produces.
        topProfile: profile(expTop, vSpan, rowFrac),
        bottomProfile: profile(expBottom, vSpan, rowFrac),
        // When an edge is not where it should be, "not found" is the least
        // useful thing a probe can say: it cannot tell a box drawn in the wrong
        // place from a box drawn correctly and then painted over. Widen the
        // search and report where the line actually is, or that there is none.
        topWide: topHit.strength > 0.6 ? null : peak(expTop, 25, rowFrac),
        bottomWide: bottomHit.strength > 0.6 ? null : peak(expBottom, 25, rowFrac),
        leftWide:
          leftHit.strength > 0.6
            ? null
            : peak(expLeft, 25, (x) =>
                probe.frac(x, expTop + inset, expBottom - inset, side, minStrength, true),
              ),
        // Round-trip: the painted row, read back as a price through the same
        // scale a user's crosshair would use.
        priceAtPaintedTop: series.coordinateToPrice(topHit.at),
        priceAtPaintedBottom: series.coordinateToPrice(bottomHit.at),
      };
    },
    [zone, candles[a.base_from].time, candles[a.base_to].time],
  );

  if (!measured) continue;

  const height = zone.top - zone.bottom;
  rows.push({
    n,
    kind: zone.kind,
    side: zone.side,
    state: zone.state,
    confirmed: zone.confirmed,
    base_bars: a.base_to - a.base_from + 1,
    box_h_px: measured.boxH,
    box_w_px: measured.boxW,
    // Painted position against the chart's own scale, in pixels.
    top_err_px: measured.topHit.at - measured.expTop,
    bottom_err_px: measured.bottomHit.at - measured.expBottom,
    top_cover: measured.topHit.strength,
    bottom_cover: measured.bottomHit.strength,
    left_cover: measured.leftHit.strength,
    top_profile: measured.topProfile,
    bottom_profile: measured.bottomProfile,
    top_wide: measured.topWide,
    bottom_wide: measured.bottomWide,
    left_wide: measured.leftWide,
    // Painted position read back as a price, against the zone record, as a
    // share of the zone's own height. Pixel error means nothing until it is
    // expressed in the units the trader reads.
    top_price_err_frac: Math.abs(measured.priceAtPaintedTop - zone.top) / height,
    bottom_price_err_frac: Math.abs(measured.priceAtPaintedBottom - zone.bottom) / height,
    // What the reviewers were actually looking at, in bar units: how much of
    // the first base bar the painted box fails to cover. Half a bar means the
    // box starts at that candle's centre.
    bar_spacing_px: measured.barSpacing,
    base_left_uncovered_bars:
      (measured.leftHit.at - (measured.baseFirstX - measured.barSpacing / 2)) / measured.barSpacing,
    // The last base bar has the same edge on the other side, but the box runs
    // to `time_to` - the break, or the last candle - so its right edge is
    // nowhere near the base and there is nothing to compare it against.
    base_last_x: measured.baseLastX,
  });
}

await browser.close();

// ---- verdict --------------------------------------------------------------
// Placement and visibility are separate questions and the whole point of this
// harness is that they were being answered as one. An edge can be in exactly
// the right place and still be impossible to see, because the zone body is
// drawn BENEATH the candles on purpose. Every check below is scoped to the
// edges the probe could actually read, and what it could not read is reported
// as its own number rather than as a placement failure.
const visible = (r, edge) => r[`${edge}_cover`] > 0.6;
const seen = (edge) => rows.filter((r) => visible(r, edge));
const worst = (list, key) => list.reduce((m, r) => Math.max(m, Math.abs(r[key])), 0);
const median = (key) => {
  const v = rows.map((r) => Math.abs(r[key])).sort((a, b) => a - b);
  return v.length ? v[Math.floor(v.length / 2)] : 0;
};

check("every drawn zone was located on the canvas", rows.length === drawing.zones.length,
      `${rows.length}/${drawing.zones.length}`);

// If nothing is legible there is nothing to conclude, and a suite that reports
// "0 errors" over 0 measurements is worse than one that fails.
check("enough edges are legible to measure anything at all",
      seen("top").length >= rows.length * 0.8 && seen("bottom").length >= rows.length * 0.5,
      `top ${seen("top").length}/${rows.length}, bottom ${seen("bottom").length}/${rows.length}`);

// Tolerance is 2px, not 1. `strokeRect(x+0.5, y+0.5, w-1, h-1)` puts the last
// painted row at y+h-1, one pixel inside the box's own height, so the bottom
// and right edges are systematically a pixel tighter than the top and left.
// That is the rasteriser drawing an h-pixel-tall box, not a misplaced zone.
check("the painted top is where the price scale puts zone.top",
      worst(seen("top"), "top_err_px") <= EDGE_TOL_PX,
      `worst ${worst(seen("top"), "top_err_px").toFixed(1)}px over ${seen("top").length} zones`);
check("the painted bottom is where the price scale puts zone.bottom",
      worst(seen("bottom"), "bottom_err_px") <= EDGE_TOL_PX,
      `worst ${worst(seen("bottom"), "bottom_err_px").toFixed(1)}px over ${seen("bottom").length} zones`);
// The reviewers' complaint, measured in the unit that makes it a fidelity
// question rather than a pixel one: a box that starts at the centre of its
// first base bar leaves half that bar outside the zone it produced.
check("the box covers the base bars it was cut from",
      worst(seen("left"), "base_left_uncovered_bars") <= 0.1,
      `worst ${worst(seen("left"), "base_left_uncovered_bars").toFixed(2)} bars of the first ` +
        `base bar sits outside the box, over ${seen("left").length} legible edges`);
// Reported, not gated. Reading the painted row back through the price scale
// re-measures the same one-to-two pixel raster inset the checks above already
// bound; on a short box that is a large share of a small number, and gating it
// would be the pixel check a second time in a unit that makes it look worse.
// It is here because pixels are not what a trader reads.
const priceErr = Math.max(
  worst(seen("top"), "top_price_err_frac"),
  worst(seen("bottom"), "bottom_price_err_frac"),
);

// Placement and legibility are not the same property. A border drawn on the
// candle's own x-position is in the right place and still unreadable, because
// the zone body is painted beneath the candles by design.
check("the left border is legible rather than buried under its own base candle",
      seen("left").length === rows.length,
      `${seen("left").length}/${rows.length} zones have a readable left edge ` +
        `(median bar spacing ${median("bar_spacing_px").toFixed(0)}px)`);

writeFileSync(`${OUT}/pixel-truth.json`, JSON.stringify({ interval: INTERVAL, bars: BARS, rows }, null, 1));

console.log(`measured ${rows.length} zones at ${INTERVAL}`);
console.log(results.join("\n"));
console.log(
  `      the painted edge read back as a price is at worst ` +
    `${(priceErr * 100).toFixed(2)}% of the zone's own height away from it`,
);
const failed = results.filter((r) => r.startsWith("FAIL"));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
