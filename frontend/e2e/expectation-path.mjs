/**
 * DOES THE EXPECTED PATH LINE ACTUALLY DRAW?
 *
 *   node e2e/expectation-path.mjs [screenshot-dir]
 *
 * WHY THIS FILE EXISTS. Between 31 August and 1 September 2026 the expectation
 * layer shipped a toggle called "Expected path line", a params block behind it, a
 * note in the toolbox describing the line it drew, a docstring in the primitive
 * describing the same line, and an assertion in `e2e/wiring.mjs` that the knob's
 * LABEL was on screen. `showPath` was assigned to a field and read by nothing.
 * Not one pixel of a path was ever painted, and every gate was green the whole
 * time - because every gate asked about the control, and none asked about the
 * canvas.
 *
 * So this one counts pixels. It reads the levels ink off the busiest canvas with
 * the path off, switches it on, and counts again. A dead knob leaves the two
 * counts equal, and equal fails here.
 *
 * It also checks the payload the line is drawn FROM, because a line drawn out of
 * an empty table would be a line drawn out of nothing: `drawing.expectation.path`
 * has to carry more than one point before the pixel test means anything.
 *
 * AND IT CHECKS THE INTERVAL, which the first working version got wrong. `h`
 * counts BARS, and the table is measured on 1h bars, so the same 96 points drawn
 * on a 15m chart lay a four-day median move across one day. The first screenshot
 * of the working line was taken on the default 15m chart and looked perfectly
 * plausible. The backend now publishes the path on 1h only, and both halves of
 * that are asserted below: empty off the measured interval, drawn on it.
 */

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const WEB = "http://127.0.0.1:3100/";
const API = "http://127.0.0.1:8100";
const SHOTS = process.argv[2] ?? ".playwright-shots";

/** THE INK IS MATCHED BY HUE, NOT BY VALUE, and it has to be. `INKS.levels` is
 *  [137, 183, 207], but nothing on the canvas is ever that colour: the fan draws
 *  it at alpha 0.40 and 0.85 and the path at 0.65, each blended over a near-black
 *  pane, so an exact-RGB match with a tolerance found five pixels on a chart with
 *  a fan on it. What survives the blend is the RATIO between channels. Levels are
 *  green-of-red +46 and blue-of-green +24; `grid` [95,105,117] is +10 and `dfr`
 *  [118,126,178] is +8.
 *
 *  CALIBRATED AGAINST THE DEFECT, and the numbers below are the reason each one
 *  is where it is. Switching the path on also widens the right margin, which
 *  rescales the pane and moves the grid and the fan, so a loose rule measures
 *  that move rather than the line. With the renderer deliberately disabled the
 *  counts were: whole canvas 55, band 0.25-0.85 47, band 0.34-0.66 at the loose
 *  hue 156, and only the tight hue below reached 0. Live it reads 197. So the
 *  gate now separates 197 from 0 instead of 134 from 55. */
const HUE = { greenOverRed: 22, blueOverGreen: 11, blueFloor: 70, from: 0.34, to: 0.66 };

let failures = 0;
function check(what, ok, detail = "") {
  console.log(`${ok ? "  ok  " : "  FAIL"}  ${what}${detail ? `  ${detail}` : ""}`);
  if (!ok) failures += 1;
}

await mkdir(SHOTS, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
page.on("console", (m) => {
  if (m.type() === "error") console.log(`  [console] ${m.text()}`);
});

await page.goto(WEB, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000);

const label = await page.evaluate(async (api) => {
  const cfg = await (await fetch(`${api}/api/config`)).json();
  return cfg.layers.find((l) => l.id === "expectation")?.label ?? null;
}, API);
check("the expectation layer has a registry label", label !== null, `${label}`);
if (label === null) {
  await browser.close();
  process.exit(1);
}

const toggle = page.getByRole("switch", { name: label, exact: true });
check("the layer toggle exists", (await toggle.count()) === 1);
if ((await toggle.getAttribute("aria-checked")) === "false") await toggle.click();
await page.waitForTimeout(4000);

/** The `drawing.expectation` block for one interval, straight off the API. */
const fanAt = (interval) =>
  page.evaluate(
    async ([api, tf]) => {
      const res = await fetch(`${api}/api/draw`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: "XAUUSD",
          interval: tf,
          bars: 1500,
          layers: ["expectation"],
        }),
      });
      return (await res.json())?.drawing?.expectation ?? null;
    },
    [API, interval],
  );

const off = await fanAt("15m");
check(
  "off the measured interval the path is not published",
  Array.isArray(off?.path) && off.path.length === 0,
  `15m -> ${off?.path?.length ?? "no fan"} points`,
);

// The table behind the line. A path of one point is not a path.
const payload = await fanAt("1h");
check("the draw payload carries an expectation fan", payload !== null);
check(
  "the fan carries a measured forward path",
  Array.isArray(payload?.path) && payload.path.length > 1,
  `${payload?.path?.length ?? 0} points`,
);
check(
  "the path reaches its full horizon",
  payload?.path?.[payload.path.length - 1]?.h >= 96,
  `h=${payload?.path?.[payload.path.length - 1]?.h}`,
);

/** Pixels of the levels ink on the busiest canvas, counted the same way twice so
 *  the two are subtractable. Only the middle third: the fan's ticks and its
 *  caption sit near the right gutter, outside it, so what the delta counts is
 *  the path. */
const scan = () =>
  page.evaluate((h) => {
    let best = 0;
    for (const c of document.querySelectorAll("canvas")) {
      if (!c.width || !c.height) continue;
      const ctx = c.getContext("2d", { willReadFrequently: true });
      const x0 = Math.round(c.width * h.from);
      const x1 = Math.round(c.width * h.to);
      const img = ctx.getImageData(x0, 0, x1 - x0, c.height).data;
      let hits = 0;
      for (let i = 0; i < img.length; i += 4) {
        if (img[i + 3] < 24) continue;
        const r = img[i];
        const g = img[i + 1];
        const b = img[i + 2];
        if (g - r >= h.greenOverRed && b - g >= h.blueOverGreen && b >= h.blueFloor) {
          hits += 1;
        }
      }
      if (hits > best) best = hits;
    }
    return best;
  }, HUE);

// THE CHART ITSELF must be on the measured interval, or the pixel halves below
// compare a path that the backend refuses to send.
await page.getByRole("button", { name: "1h", exact: true }).click();
await page.waitForTimeout(5000);

const before = await scan();
await page.screenshot({ path: `${SHOTS}/expectation-path-off.png` });

const pathToggle = page.getByRole("switch", { name: "Expected path line", exact: true });
check("the path toggle exists", (await pathToggle.count()) === 1);
check("the path is off by default", (await pathToggle.getAttribute("aria-checked")) === "false");
await pathToggle.click();
await page.waitForTimeout(4000);

const after = await scan();
await page.screenshot({ path: `${SHOTS}/expectation-path-on.png` });

check(
  "switching the path on paints ink that was not there",
  after - before >= 100,
  `${before} -> ${after} (delta ${after - before})`,
);

// And switching it back off takes the ink away again, so the delta above is the
// path and not a repaint that happened to land on the same frame.
await pathToggle.click();
await page.waitForTimeout(4000);
const restored = await scan();
check(
  "switching it back off removes the same ink",
  Math.abs(restored - before) < Math.max(100, (after - before) / 2),
  `${after} -> ${restored} (was ${before})`,
);

await browser.close();
console.log(failures ? `\n${failures} FAILED` : "\nall checks passed");
process.exit(failures ? 1 : 0);
