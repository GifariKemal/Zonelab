/**
 * POSKO 618 + FIBONACCI OTE, end to end. The newest surfaces in one harness.
 *
 *   node e2e/posko-fibonacci.mjs [screenshot-dir]
 *
 * Three parts, because the three things being tested fail in three different
 * ways:
 *
 *   1. NETWORK - `/api/triad` has to carry a truth asset, its per-symbol
 *      consolidation scores, a correlation per partner, and a NY/WIB clock.
 *      `/api/draw` has to carry Fibonacci anchors when structure is on and
 *      NOTHING when it is off. These are shapes, checked against the wire.
 *
 *   2. DOM - the PoskoPanel is the triad in the rail: four preset buttons, a
 *      click turns on a live truth asset, and the correlation matrix is the
 *      measured relationship behind it. The ChecklistPanel answers the owner's
 *      FIVE questions, not fifteen, and every row is met/unmet/unknowable - a
 *      three-state answer because "the clock has not got there yet" is not the
 *      same as "failed". This part reads the DOM because a panel that fetches
 *      but does not render is the exact silent-wrong-answer this project refuses.
 *
 *   3. CANVAS - the Fibonacci grid is drawn by a series primitive, so it lives
 *      on the canvas and never in the DOM. The equilibrium (0.5) line is DASHED
 *      and the OTE band (0.618-0.786) is SOLID; the only way to prove that on
 *      screen is to read the pixels back and measure how much of the row the
 *      line covers: a solid line covers the full width, a dashed one about half.
 *
 * Plus a timeframe switch stress: 15m -> 5m -> 1h -> 15m, watched for page
 * errors the whole time. A chart that redraws cleanly four times has not leaked
 * its series, which is the failure a memory leak shows up as first.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const SHOTS = process.argv[2] ?? ".playwright-shots";
const WEB = "http://127.0.0.1:3100/";
const API = "http://127.0.0.1:8100";

const results = [];
const check = (n, p, d = "") =>
  results.push(`${p ? "PASS" : "FAIL"}  ${n}${d ? ` :: ${d}` : ""}`);

await mkdir(SHOTS, { recursive: true });

// ================================================================ NETWORK
// `/api/triad` - the whole point of POSKO is a truth asset plus the correlation
// that backs it. If any of these are missing the panel has nothing honest to
// show, and it must say so rather than invent a number.
{
  const t = await fetch(
    `${API}/api/triad?symbol=XAUUSD&interval=15m&bars=500&triad=monetary`,
  ).then((r) => r.json());
  check("triad names the requested family", t.triad === "monetary", t.triad);
  check("triad names its base", t.base === "XAUUSD", t.base);
  check(
    "triad lists two partners beside the base",
    Array.isArray(t.partners) && t.partners.length === 2,
    JSON.stringify(t.partners),
  );
  const scores = t.truth_asset?.scores ?? {};
  check(
    "triad scores all three members",
    Object.keys(scores).length === 3 &&
      t.base in scores &&
      t.partners.every((p) => p in scores),
    JSON.stringify(scores),
  );
  check(
    "triad picks a truth asset from the three",
    typeof t.truth_asset?.symbol === "string" && t.truth_asset.symbol in scores,
    t.truth_asset?.symbol,
  );
  check(
    "triad carries one correlation per partner",
    Array.isArray(t.correlation) && t.correlation.length === 2,
    JSON.stringify(t.correlation?.map((c) => c.symbol)),
  );
  check(
    "triad carries the NY/WIB clock",
    typeof t.time?.ny === "string" && typeof t.time?.wib === "string",
    `${t.time?.ny} / ${t.time?.wib}`,
  );
}

// `/api/draw` - the Fibonacci anchors are backend-owned now. On with structure,
// off without it, and the "off" case is the one that used to silently draw.
for (const [layers, expectPopulated] of [
  [["structure"], true],
  [[], false],
]) {
  const d = await fetch(`${API}/api/draw`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: "XAUUSD",
      interval: "15m",
      bars: 800,
      provider: "mt5",
      layers,
    }),
  }).then((r) => r.json());
  const fib = d.drawing?.fibonacci ?? null;
  if (expectPopulated) {
    check(
      "fibonacci anchors are present with structure on",
      fib !== null &&
        fib.low !== null &&
        fib.high !== null &&
        fib.low_at !== null &&
        fib.high_at !== null,
      JSON.stringify(fib),
    );
    check(
      "fibonacci low sits below its high",
      fib === null || fib.high === null || fib.low === null || fib.high > fib.low,
      fib === null ? "null" : `${fib.low} -> ${fib.high}`,
    );
  } else {
    check(
      "fibonacci anchors are absent with structure off",
      fib === null,
      JSON.stringify(fib),
    );
  }
}

// ================================================================ BROWSER
const browser = await chromium.launch({ args: ["--no-proxy-server"] });
// deviceScaleFactor 1 keeps CSS pixels and bitmap pixels the same number, the
// same rule pixel-truth needs so a measured row is in the renderer's own units.
const page = await browser.newPage({
  viewport: { width: 1680, height: 1100 },
  deviceScaleFactor: 1,
});
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(e.message));

await page.goto(WEB, { waitUntil: "domcontentloaded" });
await page.waitForFunction(
  () =>
    [...document.querySelectorAll('[role="status"]')].some((el) =>
      /\d+ bars/.test(el.textContent ?? ""),
    ),
  { timeout: 90_000 },
);
await page.waitForTimeout(2500);

// ---- POSKO PANEL: the triad in the rail
{
  const panel = page.getByRole("heading", { name: "POSKO 618" });
  check("the PoskoPanel renders", (await panel.count()) === 1, `${await panel.count()} found`);

  const buttons = ["Monetary", "Commodity", "Risk", "FX"];
  for (const name of buttons) {
    check(
      `the ${name} triad button renders`,
      (await page.getByRole("button", { name, exact: true }).count()) === 1,
      "",
    );
  }

  // Click Monetary. The panel has to go from "pick a triad" to a live reading.
  await page.getByRole("button", { name: "Monetary", exact: true }).click();
  await page.waitForFunction(
    () => document.body.textContent?.includes("Truth Asset") ?? false,
    { timeout: 30_000 },
  );
  const truthText = await page.getByText("Truth Asset", { exact: true }).count();
  check("a triad click reveals the Truth Asset", truthText === 1, `${truthText} rows`);

  // The correlation matrix is the measured relationship, not decoration.
  const pearson = await page.getByText(/Pearson, \d+ pairs/).count();
  check("the correlation matrix renders with its pair count", pearson >= 1, `${pearson} rows`);

  await page.screenshot({ path: `${SHOTS}/posko-monetary.png`, fullPage: false });
}

// ---- CHECKLIST PANEL: five questions, three states, no verdict
{
  // The checklist is a layer. Turn it on by its registry label so a rename in
  // the registry cannot silently break this harness.
  const label = await page.evaluate(async (api) => {
    const cfg = await (await fetch(`${api}/api/config`)).json();
    return cfg.layers.find((l) => l.id === "checklist")?.label ?? null;
  }, API);
  const toggle = page.getByRole("switch", { name: label, exact: true });
  if ((await toggle.getAttribute("aria-checked")) === "false") {
    await toggle.click();
    await page.waitForTimeout(3500);
  }

  const panel = page.getByRole("heading", { name: "Checklist" });
  check("the ChecklistPanel renders", (await panel.count()) === 1, `${await panel.count()} found`);

  // Scope by the heading, not by the word "Checklist": the toolbox also has a
  // "Checklist" row, and matching text alone would read the wrong section.
  const section = page.locator("section", {
    has: page.getByRole("heading", { name: "Checklist" }),
  });

  // The owner's five questions, each its own row. Read as one block of text
  // rather than by exact match, because a met row appends its evidence to the
  // label - "Defining range formed" becomes "Defining range formed4450.09 to
  // ..." - and an exact match would fail the rows that are actually populated.
  const checklistText = await section.innerText();
  const rows = ["Defining range formed", "Cycle profile read", "Manipulation seen", "In discount", "SSMT"];
  for (const row of rows) {
    check(
      `the checklist row "${row}" renders`,
      checklistText.includes(row),
      "",
    );
  }

  // Three states, because absent is not false. The mark column is the ✓ or ·.
  const marks = await section.locator("span[aria-hidden]").count();
  check("the checklist renders its per-row marks", marks >= 5, `${marks} marks`);
  await page.screenshot({ path: `${SHOTS}/posko-checklist.png`, fullPage: false });

  // Leave the chart clean for the canvas test: checklist off, structure on.
  await toggle.click();
  await page.waitForTimeout(800);
}

// ---- CANVAS: the Fibonacci grid, dashed equilibrium vs solid OTE
{
  // Leave exactly structure on so the only "levels"-ink objects on the canvas
  // are the Fibonacci lines. Supply and demand is on by default and its boxes
  // share the canvas; two layers on would put paint in the way of the scan.
  const supplyLabel = await page.evaluate(async (api) => {
    const cfg = await (await fetch(`${api}/api/config`)).json();
    return cfg.layers.find((l) => l.id === "supply_demand")?.label ?? null;
  }, API);
  const supplyToggle = page.getByRole("switch", { name: supplyLabel, exact: true });
  if ((await supplyToggle.getAttribute("aria-checked")) === "true") {
    await supplyToggle.click();
    await page.waitForTimeout(1200);
  }
  const structLabel = await page.evaluate(async (api) => {
    const cfg = await (await fetch(`${api}/api/config`)).json();
    return cfg.layers.find((l) => l.id === "structure")?.label ?? null;
  }, API);
  const structToggle = page.getByRole("switch", { name: structLabel, exact: true });
  if ((await structToggle.getAttribute("aria-checked")) === "false") {
    await structToggle.click();
    await page.waitForTimeout(4000);
  }

  // The anchors the chart is actually drawing, fetched with the same series.
  const fib = await page.evaluate(async (api) => {
    const d = await fetch(`${api}/api/draw`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: "XAUUSD",
        interval: "15m",
        bars: 800,
        provider: "mt5",
        layers: ["structure"],
      }),
    }).then((r) => r.json());
    return d.drawing?.fibonacci ?? null;
  }, API);
  check(
    "the on-screen chart has Fibonacci anchors to draw",
    fib !== null && fib.low !== null && fib.high !== null,
    JSON.stringify(fib),
  );

  // Zoom the time scale to the swing so every Fibonacci level from low to high
  // is on screen. The primitive SKIPS a line whose price maps to a null
  // coordinate - correct behaviour, but it means a level below the visible
  // range cannot be measured, and the chart autofits to the recent price, which
  // routinely leaves the swing midpoint off the bottom.
  await page.evaluate((anchors) => {
    const { chart } = window.__zonelabChart;
    const lo = Math.min(anchors.low_at, anchors.high_at);
    const hi = Math.max(anchors.low_at, anchors.high_at);
    const pad = 3600 * 6; // six hours of margin either side
    chart.timeScale().setVisibleRange({ from: lo - pad, to: hi + pad });
  }, fib);
  await page.waitForTimeout(900);

  const measured = await page.evaluate((anchors) => {
    if (!anchors || anchors.low === null || anchors.high === null) return null;
    const { series } = window.__zonelabChart;
    const toY = (ratio) => series.priceToCoordinate(anchors.low + ratio * (anchors.high - anchors.low));

    const yEq = toY(0.5);
    const yOte = toY(0.618);
    if (yEq === null || yOte === null) return null;

    // Grab the pane canvas: the one carrying candles and primitive paint. Same
    // alpha test as pixel-truth - a fully transparent overlay reads as black
    // and would otherwise win the "busiest canvas" race while painting nothing.
    const canvases = [...document.querySelectorAll("canvas")];
    let best = null;
    for (const c of canvases) {
      if (!c.width || !c.height) continue;
      const ctx = c.getContext("2d", { willReadFrequently: true });
      const img = ctx.getImageData(0, 0, c.width, c.height);
      const d = img.data;
      let painted = 0;
      for (let i = 0; i < d.length; i += 4 * 40) {
        if (d[i + 3] < 250) continue;
        if (Math.abs(d[i] - 11) + Math.abs(d[i + 1] - 13) + Math.abs(d[i + 2] - 16) > 12) painted++;
      }
      if (!best || painted > best.painted) best = { img, painted };
    }
    if (!best) return null;

    // The levels ink is rgb(137,183,207). The equilibrium line draws at alpha
    // 0.5 (about rgb 74,98,111 over the near-black page), the OTE band at 0.95
    // (about rgb 131,175,197). Match on "bluish and bright", and skip the right
    // edge where the label box paints over the line.
    const { img } = best;
    const W = img.width - 70;
    const rowCoverage = (y) => {
      const yy = Math.round(y);
      if (yy < 0 || yy >= img.height) return -1;
      let hit = 0;
      for (let x = 0; x < W; x++) {
        const i = (yy * img.width + x) * 4;
        const r = img.data[i], g = img.data[i + 1], b = img.data[i + 2];
        // The levels ink is the only light blue on the canvas: blue > green >
        // red, and bright enough to be a stroke, not the page. The alpha 0.5
        // equilibrium line composites to about rgb(42,55,64) over the page, so
        // the floor is b > 40, well under the OTE band and well over the
        // background's 16. Structure ink is purple (red > green) and is excluded
        // by the ordering; candles are green or salmon, neither blue-leading.
        if (b > g && g > r && b > 40) hit++;
      }
      return hit / W;
    };

    return { eq: rowCoverage(yEq), ote: rowCoverage(yOte), yEq, yOte };
  }, fib);

  if (measured === null) {
    check("fibonacci lines are measurable on the canvas", false, "no canvas or out of range");
  } else {
    // Dashed equilibrium: about 4px on / 3px off, so ~55-60% of the row. Solid
    // OTE: the whole row. The gap between them is the whole claim.
    check(
      "the equilibrium (0.5) line paints dashed, not solid",
      measured.eq > 0.25 && measured.eq < 0.85,
      `coverage ${(measured.eq * 100).toFixed(0)}%`,
    );
    check(
      "the OTE (0.618) line paints solid",
      measured.ote > 0.8,
      `coverage ${(measured.ote * 100).toFixed(0)}%`,
    );
    check(
      "the dashed line is sparser than the solid band",
      measured.eq < measured.ote,
      `eq ${(measured.eq * 100).toFixed(0)}% vs ote ${(measured.ote * 100).toFixed(0)}%`,
    );
  }

  await page.screenshot({ path: `${SHOTS}/posko-fibonacci.png`, fullPage: false });
}

// ---- TIMEFRAME STRESS: four redraws, no page error, chart still alive
{
  const before = pageErrors.length;
  for (const tf of ["5m", "1h", "15m", "5m", "15m"]) {
    await page.locator('div[aria-label="Timeframe"] button', { hasText: tf }).first().click();
    await page.waitForTimeout(1800);
  }
  const statusStillAlive = await page.waitForFunction(
    () =>
      [...document.querySelectorAll('[role="status"]')].some((el) =>
        /\d+ bars/.test(el.textContent ?? ""),
      ),
    { timeout: 30_000 },
  ).then(() => true).catch(() => false);
  check("timeframe switching leaves the chart alive", statusStillAlive, "");
  check(
    "timeframe switching raises no page error",
    pageErrors.length === before,
    pageErrors.slice(before).join("; "),
  );
}

await page.screenshot({ path: `${SHOTS}/posko-final.png`, fullPage: true });
await browser.close();

console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
