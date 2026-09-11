/**
 * Do the four QT A-Z adoptions actually PAINT, or only arrive?
 *
 *   node e2e/qt-az-ink.mjs [screenshot-dir]
 *
 * WHY THIS IS SEPARATE FROM `wiring.mjs`. That harness proves each layer fills
 * its response array and owns a swatch and a knob - all three true of a layer
 * whose canvas pass was never written. `ink-budget.mjs` measures ink but only
 * with DEFAULT params, and three of these four draw nothing on defaults by
 * design: the killzone and premium/discount overlays need a degree named, and
 * the fill layer needs partners. So between them the two harnesses can report a
 * fully wired layer that paints nothing, which is the exact failure this repo
 * has already shipped once - "backend hijau TIDAK berarti UI-nya ada".
 *
 * The method is the one `ink-budget.mjs` uses: grab the canvas bitmap with the
 * overlay off, grab it again with the overlay on, and count pixels that moved.
 * A layer that paints is one where that number is not zero.
 */
import { chromium } from "playwright";

import { onlyLayers, onlyPressed, setLayer, setPressed } from "./_layers.mjs";

const SHOTS = process.argv[2] ?? ".playwright-shots";
const results = [];
const check = (n, p, d = "") =>
  results.push(`${p ? "PASS" : "FAIL"}  ${n}${d ? ` :: ${d}` : ""}`);

/** Each adoption, and the least it needs before it can paint anything. */
const CASES = [
  {
    id: "killzones",
    label: "QT killzone bands",
    layers: ["session"],
    turnOn: [["Killzones", ["day", "session"]]],
  },
  {
    id: "time_pd",
    label: "time-based premium/discount",
    layers: ["session"],
    turnOn: [["Premium / discount", ["session"]]],
  },
  {
    id: "smt_fill",
    label: "SMT fill bands",
    layers: ["smt_fill"],
    // The partner picker now lives in this layer's own panel, which is the
    // whole reason this case can be driven from the rail at all - and no SSMT
    // stage is picked, because a gap-fill divergence has no quarter degree.
    // Needing one was a defect this probe found.
    turnOn: [["chip", ["SMT fill against", "XAGUSD"]]],
  },
  {
    id: "hidden_ssmt",
    label: "hidden SSMT, dotted",
    layers: ["ssmt"],
    // The wick pass is already on in the baseline, so the question is whether
    // the body pass adds ink on top of it.
    before: [
      ["chip", ["SSMT against", "XAGUSD"]],
      ["SSMT stages", ["day"]],
    ],
    turnOn: [["toggle", ["Hidden SSMT (bodies)"]]],
  },
];

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({
  viewport: { width: 1400, height: 800 },
  deviceScaleFactor: 1,
});
await page.goto("http://127.0.0.1:3100/", { waitUntil: "networkidle" });
await page.waitForTimeout(6000);

// Bitmap helpers injected once. Sending a 1400x800 ImageData over the bridge
// per grab would be a slow way to ask the same question.
await page.evaluate(() => {
  const surface = () =>
    [...document.querySelectorAll("canvas")].sort(
      (a, b) => b.width * b.height - a.width * a.height,
    )[0];
  window.__grab = () => {
    const cv = surface();
    const ctx = cv.getContext("2d", { willReadFrequently: true });
    return { data: [...ctx.getImageData(0, 0, cv.width, cv.height).data], w: cv.width, h: cv.height };
  };
  window.__moved = (a, b) => {
    let changed = 0;
    for (let i = 0; i < a.data.length; i += 4) {
      if (
        Math.abs(a.data[i] - b.data[i]) > 8 ||
        Math.abs(a.data[i + 1] - b.data[i + 1]) > 8 ||
        Math.abs(a.data[i + 2] - b.data[i + 2]) > 8
      ) {
        changed += 1;
      }
    }
    return changed;
  };
});

/** Leave exactly these degrees pressed in one `Degrees` group.
 *
 *  `onlyPressed` and not a loop of clicks: these are toggles, and clicking one
 *  that is already on turns it off. That is not hypothetical here - it is what
 *  made this file report 0 px for a body pass that paints 927. */
const pickDegrees = (group, degrees) => onlyPressed(page, group, degrees);

/** Press one chip in a `Chips` group, if it is not pressed already. */
const pickChip = (group, value) => setPressed(page, group, value, true);

const grab = () => page.evaluate(() => window.__grab());
const moved = async (a, b) =>
  page.evaluate(([x, y]) => window.__moved(x, y), [a, b]);

// EVERY LAYER OFF FIRST. A baseline still carrying a layer subtracts that
// layer's ink from every measurement below and the numbers look reasonable.
await onlyLayers(page, []);
await page.waitForTimeout(3000);

for (const c of CASES) {
  await onlyLayers(page, c.layers);
  for (const [group, values] of c.before ?? []) {
    if (group === "chip") await pickChip(values[0], values[1]);
    else await pickDegrees(group, values);
  }
  await page.waitForTimeout(3500);
  const before = await grab();

  for (const [group, values] of c.turnOn) {
    if (group === "chip") await pickChip(values[0], values[1]);
    else if (group === "switch") await setLayer(page, values[0], true);
    else if (group === "toggle") {
      await page.getByRole("switch", { name: values[0], exact: true }).click();
      await page.waitForTimeout(3500);
    } else await pickDegrees(group, values);
  }
  await page.waitForTimeout(4000);
  const after = await grab();
  const px = await moved(before, after);

  check(
    `${c.label}: switching it on moves pixels`,
    px > 0,
    `${px} px moved`,
  );
  await page.screenshot({ path: `${SHOTS}/qt-az-${c.id}.png` });
}

await browser.close();
console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL"));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
if (failed.length) {
  console.log("GAGAL");
  process.exit(1);
}
