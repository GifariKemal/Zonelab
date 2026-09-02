/**
 * THE COLLISION MAP, checked as arithmetic instead of by eye.
 *
 *   node e2e/labels.mjs [screenshot-dir]
 *
 * Every primitive that writes a word on the canvas asks `labelFree` first and
 * drops the word rather than overprinting. That mechanism is the only thing
 * standing between nine simultaneous layers and a right-hand column of mush -
 * and until this harness existed there was no way to check it actually held.
 * The other visual harnesses screenshot; a human then has to notice that "PDH"
 * and "NWOG" are sharing four pixels in one corner of one frame.
 *
 * So the assertions here are about the CLAIM LIST, not about pixels:
 *
 *   - it is not empty, because an empty list is what a broken reset looks like
 *     and it would make every other assertion below pass vacuously;
 *   - no two claimed rectangles intersect, which is the property the whole
 *     mechanism exists to provide;
 *   - every claim sits inside the pane, so nothing was placed off-screen and
 *     counted as placed;
 *   - the DFR layer contributes claims when it is on, which is the wiring
 *     defect this file was written for: its tags were being claimed BEFORE the
 *     frame's reset ran, so they were invisible to the map and every later pass
 *     printed over them. Nothing about the picture looked wrong.
 *
 * A console warning from `resetLabels` is a hard failure here. That warning
 * fires exactly when a pass claims before the frame's first pass, which is the
 * attach-order bug above, and it is silent in every healthy frame.
 *
 * Nine layers on purpose: a thin chart would exercise nothing. The density is
 * printed on every run rather than quoted from one, because a quoted number
 * goes stale the moment the input changes - which is exactly what happened when
 * this file moved off the live feed. It was calibrated at 98 price-anchored
 * objects, 86 pairs within 12px and 27 within 1px on live MT5; read the line the
 * run prints for what the pinned input gives today.
 *
 * PINNED TO THE SYNTHETIC PROVIDER, AND THAT IS THE POINT OF THIS PARAGRAPH.
 * Until 1 September 2026 this harness read the live MT5 tail, and a harness
 * whose input moves is a harness whose verdict moves. Measured that day: five
 * runs, two of them on the committed tree through `git stash`, gave 7/9, 8/9,
 * 8/9, 7/9 and 9/9 without one line of code changing between them. The
 * straddling box it reported at `{x:3, y:-9}` appeared on a tree that did not
 * contain the branch it was being blamed on. A gate that flips between runs
 * cannot convict anything, and it nearly convicted the wrong change.
 *
 * The cause is not subtle once stated: labels land where price is, new bars
 * arrive between runs, and `claimedLabels` is first-come-first-served - so a
 * geometry that shifts by one bar changes which label wins its claim and
 * whether any of them lands across a pane edge. The fix is to stop asking the
 * market, and `provider: "synthetic"` is that fix.
 *
 * HOW FAR THAT FIX GOES, CORRECTED THE SAME DAY IT WAS WRITTEN. The paragraph
 * here used to say synthetic "returns the same bars every call, verified
 * byte-identical across two requests". The verification is real and the
 * conclusion was too strong, and the two can be told apart by measuring: two
 * calls in a row ARE byte-identical, and a third one seventy seconds later had
 * moved a full fifteen minute bar, first bar 1787629500 to 1787630400. The
 * provider anchors its grid to the wall clock, which `app/providers/synthetic.py`
 * has always said in `generate()`'s own docstring, and two requests in a row
 * always land in the same bar - so that check could not fail for the reason it
 * existed. The pin narrowed the window from every run to every fifteen minutes.
 * It did not close it.
 *
 * A RUN THAT HAS TO BE REPRODUCIBLE pins the clock outright, which
 * `generate()` has always supported and the API path did not until now:
 *
 *     ZONELAB_SYNTHETIC_NOW=1788256800 .venv/Scripts/python.exe \
 *         -m uvicorn app.main:app --host 127.0.0.1 --port 8100
 *
 * The banner below reports which of the two applied, so a red run can be
 * repeated instead of argued about. This file is about LABEL GEOMETRY rather
 * than about market truth either way.
 *
 * WHAT THAT COSTS, stated rather than glossed: a collision that only occurs on
 * one particular real-data configuration is no longer caught here. The live
 * feed is still exercised by `e2e/sweep.mjs`, `e2e/wiring.mjs` and
 * `e2e/zone-audit.mjs`, none of which assert on exact geometry.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const SHOTS = process.argv[2] ?? ".playwright-shots";
const URL = "http://127.0.0.1:3100/";

// Every layer that writes a word, plus the two that only draw. `session` is in
// because it owns the frame's reset and must run whether or not a grid is asked
// for, and a run without it would pass while proving nothing.
const LAYERS = [
  "supply_demand",
  "fvg",
  "order_block",
  "structure",
  "session",
  "gaps",
  "cisd",
  "dfr",
  "pools",
  "liquidity",
  "projections",
];

const results = [];
// Reported lines that are NOT checks. Kept out of `results` because the summary
// counts that array, so a note pushed into it becomes a passing assertion: the
// density line below read "10/10 passed" for one edit, on nine actual checks.
const notes = [];
const check = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

await mkdir(SHOTS, { recursive: true });
const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1680, height: 1000 } });

page.on("pageerror", (e) => check("no page error", false, e.message));

// EVERY console warning, not only ours, and every failed request. The other
// harnesses assert zero console ERRORS and stop there, so a browser warning
// could sit on every page load unread - which is how a warning stops being a
// signal. Measured on this config with thirteen layers on: zero warnings, zero
// errors, zero failed requests, and the only console output at all is React's
// dev-mode DevTools suggestion at `info`.
//
// Collected rather than asserted inline so one warning does not hide a second,
// different one.
const warnings = [];
const failures = [];
page.on("console", (m) => {
  if (m.type() === "warning" || m.type() === "error") {
    warnings.push(`[${m.type()}] ${m.text().slice(0, 200)}`);
  }
});
page.on("requestfailed", (r) => {
  // `net::ERR_ABORTED` is what a navigation away from an in-flight request looks
  // like, and this harness navigates. Anything else is a real failure.
  const why = r.failure()?.errorText ?? "";
  if (!why.includes("ERR_ABORTED")) failures.push(`${r.url().slice(0, 120)} :: ${why}`);
});

// Driving eleven layer toggles through the menu would test the menu. Patched on
// the way out instead, the same seam `e2e/ribbon.mjs` uses.
await page.addInitScript((layers) => {
  const real = window.fetch;
  window.fetch = (url, init) => {
    if (typeof url === "string" && url.includes("/api/draw") && init?.body) {
      const body = JSON.parse(init.body);
      body.layers = [...new Set([...(body.layers ?? []), ...layers])].filter(
        (l) => !(l === "dfr" && window.__zonelabNoDfr),
      );
      body.session = { ...(body.session ?? {}), quarters: ["week", "day"], max_quarters: 0 };
      body.dfr = { ...(body.dfr ?? {}), degrees: ["week", "day"], max_ranges: 6 };
      // The three inputs that decide the geometry, pinned here rather than
      // inherited from whatever the picker happens to hold. Symbol and bars
      // matter because a different window is a different set of labels; the
      // provider matters because it is the only one that answers the same way
      // twice.
      body.provider = "synthetic";
      body.symbol = "XAUUSD";
      body.bars = 500;
      init = { ...init, body: JSON.stringify(body) };
    }
    return real(url, init);
  };
}, LAYERS);

await page.goto(URL, { waitUntil: "domcontentloaded" });
// THE READOUT, not the body text. `document.body.innerText` includes every layer
// note and every opened explanation, and the structure layer's evidence says
// "3000 bars of XAUUSD 15m" - so a gate on the body would report "loaded" off
// prose that is present before any candle arrives. The readout carries
// `role="status"`.
await page.waitForFunction(
  () =>
    [...document.querySelectorAll('[role="status"]')].some((el) =>
      /\d+ bars/.test(el.textContent ?? ""),
    ),
  { timeout: 60_000 },
);
await page.waitForFunction(() => window.__zonelabChart?.labels, { timeout: 30_000 });

// One mouse move first. The library repaints the TOP canvas alone when the
// crosshair moves, and a claim list that only survives a full repaint would
// look healthy in a static frame and collide the moment the pointer entered the
// pane - which is the state a reader is always in.
await page.mouse.move(840, 500);
await page.waitForTimeout(400);
await page.mouse.move(1100, 420);
await page.waitForTimeout(600);

const { labels, pane } = await page.evaluate(() => ({
  labels: window.__zonelabChart.labels(),
  pane: window.__zonelabChart.chart.paneSize(),
}));

check("the claim list is populated", labels.length > 0, `${labels.length} labels`);

// HOW CROWDED THIS CHART ACTUALLY IS, reported rather than asserted, because it
// is the reason the assertions below mean anything. A collision map on a thin
// chart passes without exercising the mechanism, so the density belongs in the
// output where a reader can see it fall.
let near12 = 0;
let near1 = 0;
for (let i = 0; i < labels.length; i++) {
  for (let j = i + 1; j < labels.length; j++) {
    const gap = Math.abs(labels[i].y - labels[j].y);
    if (gap < 12) near12 += 1;
    if (gap < 1) near1 += 1;
  }
}
notes.push(
  `note  density :: ${labels.length} claims, ${near12} pairs within 12px vertically, ${near1} within 1px`,
);

// THE ONE THAT MATTERS. Same predicate as `labelFree`, restated here on purpose:
// a harness that imported the function under test would agree with it by
// construction.
const hits = [];
for (let i = 0; i < labels.length; i++) {
  for (let j = i + 1; j < labels.length; j++) {
    const a = labels[i];
    const b = labels[j];
    if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) {
      hits.push(
        `(${Math.round(a.x)},${Math.round(a.y)},${Math.round(a.w)}x${Math.round(a.h)})` +
          ` vs (${Math.round(b.x)},${Math.round(b.y)},${Math.round(b.w)}x${Math.round(b.h)})`,
      );
    }
  }
}
check(
  "no two claimed labels intersect",
  hits.length === 0,
  hits.length ? `${hits.length} overlapping pairs, e.g. ${hits[0]}` : `${labels.length} checked`,
);

// A claim that STRADDLES a pane edge is the readability defect: half a word is
// unreadable and the reader cannot tell which half is missing. A claim wholly
// outside is merely wasted - the canvas clips it - so it is counted and not
// failed, because time-anchored captions on quarters that scrolled off the left
// legitimately land there.
const straddle = labels.filter(
  (r) =>
    (r.x < 0 && r.x + r.w > 0) ||
    (r.y < 0 && r.y + r.h > 0) ||
    (r.x < pane.width && r.x + r.w > pane.width) ||
    (r.y < pane.height && r.y + r.h > pane.height),
);
const outside = labels.filter(
  (r) => r.x + r.w <= 0 || r.y + r.h <= 0 || r.x >= pane.width || r.y >= pane.height,
);
check(
  "no claim is cut in half by a pane edge",
  straddle.length === 0,
  straddle.length
    ? `${straddle.length} straddling, e.g. ${JSON.stringify(straddle[0])}`
    : `${outside.length} of ${labels.length} wholly off-pane (clipped, harmless)`,
);

// The gutter is one column for every pass. A claim to the LEFT of it is a
// caption in the price area, which is legal for zone captions and for nothing
// else - so this is reported rather than asserted, and the number is the thing
// worth watching if the column ever starts moving.
const GUTTER = 46;
const inGutter = labels.filter((r) => r.x >= pane.width - GUTTER - 8).length;
check(
  "labels reach the right-hand gutter",
  inGutter > 0,
  `${inGutter} of ${labels.length} in the ray-name column`,
);

check(
  "no console warning or error from the chart",
  warnings.length === 0,
  warnings.length ? `${warnings.length}: ${warnings[0]}` : "none",
);
check(
  "no failed request",
  failures.length === 0,
  failures.length ? `${failures.length}: ${failures[0]}` : "none",
);

// DFR specifically: it has to be ON the map, not merely on the canvas. Checked
// by differencing against a run with the layer off rather than by tagging the
// claims, because a claim carries no owner and giving it one would be a field
// that exists only for this test.
// A FLAG the one patch reads, not a second wrapper around `fetch`. Wrapping it
// again put the original patch downstream, so the layer this block had just
// stripped was added straight back and the comparison read 105 against 105.
await page.evaluate(() => {
  window.__zonelabNoDfr = true;
});
// The Bars picker, purely to force one refetch through the patched fetch above.
// Timeframe is a button group rather than a combobox, and driving it would also
// change how many objects exist - which is the quantity being compared.
const bars = page.getByRole("combobox", { name: "Bars" });
const before = await bars.inputValue();
const other = (await bars.locator("option").allTextContents()).find((o) => o !== before);
await bars.selectOption(other);
await page.waitForTimeout(3000);
await bars.selectOption(before);
await page.waitForTimeout(3500);
await page.mouse.move(1100, 420);
await page.waitForTimeout(600);
const without = await page.evaluate(() => window.__zonelabChart.labels().length);
check(
  "the dfr layer contributes claims",
  without < labels.length,
  `${labels.length} with dfr, ${without} without`,
);

// --- the one rectangle nothing may paint under -------------------------------
// The library's attribution mark is a DOM anchor sitting ABOVE the canvas, so it
// wins every overlap it is in and nothing in the renderer can see it. The cycle
// grid claims its rectangle in the shared label map to keep captions off it, and
// that claim was WRONG TWICE: pushed in CSS pixels into a map that holds bitmap
// pixels, and anchored flush to the canvas floor when the mark actually sits 10
// CSS pixels above it. At devicePixelRatio 2 it covered less than half the mark.
//
// Checked against the DOM rather than against the constants, so the assertion
// fails if the library moves its own mark - which is the case no comment can
// protect against.
{
  const geometry = await page.evaluate(() => {
    const mark = document.querySelector("#tv-attr-logo");
    const canvas = document.querySelector("main canvas");
    if (!mark || !canvas) return null;
    const m = mark.getBoundingClientRect();
    const c = canvas.getBoundingClientRect();
    const claims = window.__zonelabChart?.labels?.() ?? [];
    const k = window.devicePixelRatio || 1;
    // Claims are bitmap pixels; the DOM is CSS pixels.
    return {
      mark: { x: m.x - c.x, y: m.y - c.y, w: m.width, h: m.height },
      claims: claims.map((r) => ({ x: r.x / k, y: r.y / k, w: r.w / k, h: r.h / k })),
    };
  });
  check("the attribution mark is present to be claimed", geometry !== null);
  if (geometry) {
    const { mark, claims } = geometry;
    const covered = claims.some(
      (r) =>
        r.x <= mark.x + 0.5 &&
        r.y <= mark.y + 0.5 &&
        r.x + r.w >= mark.x + mark.w - 0.5 &&
        r.y + r.h >= mark.y + mark.h - 0.5,
    );
    check(
      "some claim fully covers the attribution mark, so no caption can land on it",
      covered,
      `mark at ${mark.x.toFixed(0)},${mark.y.toFixed(0)} ${mark.w}x${mark.h} against ${claims.length} claims`,
    );
  }
}

await page.screenshot({ path: `${SHOTS}/labels-eleven-layers.png` });
await browser.close();

// WHICH CLOCK THIS RUN SAW, printed above the verdicts because it decides
// whether a red run can be repeated. At 0 the synthetic grid follows the wall
// clock and moves one bar every time a bar closes, so two runs either side of
// a boundary are two different charts and only one of them can be reproduced.
const pin = Number(
  (await (await fetch("http://127.0.0.1:8100/api/config")).json()).synthetic_now,
);
console.log(
  pin
    ? `clock PINNED at ${pin}, this run is reproducible`
    : "clock LIVE, the grid moves one bar every 15m - set ZONELAB_SYNTHETIC_NOW " +
      "to repeat a red run exactly",
);

console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
