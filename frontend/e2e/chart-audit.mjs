/**
 * Show a rendered chart to a model and print what it says it sees.
 *
 *   node e2e/chart-audit.mjs <out-dir> [interval] [bars] [detector]
 *
 * Every other harness here measures something somebody thought of first.
 * `pixel-truth.mjs` reads the painted borders back through the price scale
 * because four reviewers complained about padding; `zone-audit.mjs` re-derives
 * the record from the candles the page fetched. Both are checks against a
 * predicted defect, and neither can report the defect nobody predicted - a
 * caption cut off at the pane edge, two boxes stacked into an unreadable smear,
 * a zone floating over a gap with no candles under it. Those were all found by
 * a human looking, and a human is not in the loop on every run.
 *
 * So this puts eyes in the loop. It draws the chart, screenshots the canvas,
 * takes the exact list of shapes the engine says it drew, and hands both to
 * `app.llm`'s CHART_AUDITOR. The model may look and may describe. It may not
 * produce a number: every numeral in its reply is checked against the shape
 * list on the Python side, and a fabricated one comes back marked unusable.
 *
 * WHAT AN EXIT CODE HERE MEANS
 * Non-zero means the HARNESS failed - no browser, the chart showing a series
 * that was not fetched, nothing visible to audit, the auditor unreachable.
 * A model FINDING never fails this script. A finding is a claim to be verified
 * by a person against the shape list printed beside it, not a test result: the
 * model has no access to the truth, only to the picture, and it will phrase a
 * guess exactly as confidently as an observation. Read both columns.
 *
 * AN UNUSABLE VERDICT IS NOT A FAILED RUN EITHER, AND IT IS COMMON HERE
 * The grounding check and the vision job pull against each other, which was not
 * obvious until this was first run. Every other caller feeds the model numbers
 * and gets prose back, so every numeral in the reply came from the payload. A
 * model looking at a PICTURE reads numbers off the price axis - "the top visible
 * label is 4480" - and that is an honest observation of a number the engine
 * never produced, so the check rejects it, correctly by its own rule. The first
 * two real audits both came back UNUSABLE, and both were still worth reading.
 * Treat the verdict as "does this reply contain any number you may quote", not
 * as "is this reply any good".
 */
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

// RESOLVED TO AN ABSOLUTE PATH, because it crosses a process boundary into a
// DIFFERENT working directory. The screenshot is written relative to this
// harness's cwd (frontend) and then handed to `app.llm`, which is spawned with
// `cwd: BACKEND` - so `.playwright-shots/chart-audit-15m-supply_demand.png`
// resolved against the backend, where nothing of that name exists. The harness
// drew the chart, listed four zones, wrote both files, printed their paths, and
// then died with a FileNotFoundError naming the file it had just created.
const OUT = process.argv[2] ? resolve(process.argv[2]) : undefined;
const INTERVAL = process.argv[3] ?? "15m";
const BARS = Number(process.argv[4] ?? 500);
const DETECTOR = process.argv[5] ?? "supply_demand";
const API = "http://127.0.0.1:8100";
const BACKEND = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "backend");

if (!OUT) {
  console.error("usage: node e2e/chart-audit.mjs <out-dir> [interval] [bars] [detector]");
  process.exit(2);
}
mkdirSync(OUT, { recursive: true });

const die = async (why, browser) => {
  console.error(`harness failure: ${why}`);
  if (browser) await browser.close();
  process.exit(2);
};

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
// deviceScaleFactor 2 for the model's benefit, not the probe's: a 10px caption
// at scale 1 is the thing most likely to be misread, and misreading the picture
// is the one failure mode of this harness that produces confident nonsense.
const page = await browser.newPage({
  viewport: { width: 1500, height: 820 },
  deviceScaleFactor: 2,
});
await page.goto("http://127.0.0.1:3100/", { waitUntil: "networkidle" });
await page.waitForTimeout(6000);

await page.locator(`div[aria-label="Timeframe"] button:text-is("${INTERVAL}")`).click();
// BY NAME, NOT BY POSITION. `select").nth(3)` was the HTF picker until a
// Broker picker landed beside it on 2026-08-20 and every index after Source
// shifted by one - the sweep then timed out waiting for a combobox that had
// moved, which reads as a broken app rather than as a moved control. Each
// `<select>` carries an `aria-label`, so the accessible name is the stable
// handle and a new picker cannot break this again.
await page.getByRole("combobox", { name: "Bars" }).selectOption(String(BARS));
await page.waitForTimeout(6000);

/** The switch for one layer, found by the label the REGISTRY gives it, never by
 *  a caption typed here - the menu is built from `/api/config`'s `layers`, and a
 *  second copy of those names in this file is what the registry exists to end. */
const layerSwitch = async (id) => {
  const label = await page.evaluate(
    async ([api, want]) => {
      const cfg = await (await fetch(`${api}/api/config`)).json();
      return cfg.layers.find((l) => l.id === want)?.label ?? null;
    },
    [API, id],
  );
  if (!label) await die(`no layer "${id}" in the registry the API serves`, browser);
  return page.getByRole("switch", { name: label, exact: true });
};

// Exactly one detector on, same reason as pixel-truth: with two on, the boxes on
// the canvas are a superset of the list, and the model correctly reports paint
// the record cannot account for - a finding about the harness, not the drawing.
if (DETECTOR !== "supply_demand") {
  await (await layerSwitch(DETECTOR)).click();
  await page.waitForTimeout(2500);
  await (await layerSwitch("supply_demand")).click();
  await page.waitForTimeout(6000);
}

const drawn = await page.evaluate(
  async ([api, interval, bars, detector]) => {
    const r = await fetch(`${api}/api/draw`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: "XAUUSD", interval, bars, layers: [detector] }),
    });
    return r.json();
  },
  [API, INTERVAL, BARS, DETECTOR],
);
const { candles, drawing } = drawn;
if (!candles?.length) await die("the API returned no candles", browser);

// The same guard every harness here needs. A picture built from a series the
// chart is not showing is a picture of nothing, and it looks entirely normal.
const view = await page.evaluate(() => {
  const r = window.__zonelabChart.chart.timeScale().getVisibleRange();
  return r ? { from: Number(r.from), to: Number(r.to) } : null;
});
if (!view || view.to < candles[0].time || view.from > candles.at(-1).time) {
  await die(`the chart is not showing the ${INTERVAL} series that was fetched`, browser);
}

const shot = `${OUT}/chart-audit-${INTERVAL}-${DETECTOR}.png`;
await page.locator("main").screenshot({ path: shot });
await browser.close();

// Only the zones whose box actually reaches the screen. Listing the rest would
// make the model report every off-screen zone as a drawing that went missing,
// which is a true statement about a payload nobody should have sent.
const onScreen = drawing.zones.filter((z) => z.time_to >= view.from && z.time_from <= view.to);
if (!onScreen.length) {
  console.error(`harness failure: none of the ${drawing.zones.length} zones are in view`);
  process.exit(2);
}

// What the model is told, and the only numbers it is permitted to repeat. Only
// properties that are actually PAINTED: geometry, lifecycle, and the caption
// text. Scores and anatomy indices are in the record but not on the canvas, and
// a model asked to check the picture against facts the picture cannot carry
// answers about the ones it can.
// Two decimals, the way the chart's own axis and panel show them. Not cosmetic:
// the records carry float32 tails (4476.2998046875), grounding treats a tail
// longer than six places as no decimals at all, and the first real audit came
// back UNUSABLE for quoting nine of its own payload's prices back verbatim. The
// number a reader can check against the price axis is the two-decimal one, so
// that is the number the model is held to.
const px = (v) => Number(v.toFixed(2));

const shapes = {
  chart: `XAUUSD ${INTERVAL}, ${DETECTOR}, ${candles.length} bars fetched`,
  visible_window: view,
  legend: {
    box: "each zone is a filled rectangle with a 1px border of its own colour",
    demand: "green, drawn at the bottom of a move price left from",
    supply: "red, drawn at the top of a move price left from",
    // NOT "brightest when fresh": measured against #0b0d10, adjacent lifecycle
    // states differ by 1.03:1 to 1.10:1 in the FILL and by 1.33:1 to 1.82:1 in
    // the BORDER. The auditor was told to read freshness off the fill and
    // correctly reported it could not. The signal is the stroke.
    fill_opacity: "says a level is here; it does NOT usably encode lifecycle",
    border_opacity: "this is where lifecycle reads: strongest fresh, faintest broken",
    // NOT "inside the box". `supply_demand.py` sets proximal = top for a demand
    // zone and bottom for a supply one, so it is ALWAYS an edge of the box unless
    // refinement moved it. Telling the auditor to look for an interior line made
    // it report a missing line on five correct charts.
    proximal_line: "the edge price meets first, drawn as a brighter rule ON that border - the TOP of a demand box and the BOTTOM of a supply box - and its dash pattern names the detector",
    caption: "the formation name at the box's left edge, on a dark plate",
    z_order: "box fills are painted BENEATH the candles, captions above them",
  },
  zones: onScreen.map((z) => ({
    caption: z.kind + (z.confirmed && !z.settled ? " unsettled" : ""),
    side: z.side,
    state: z.state,
    top: px(z.top),
    bottom: px(z.bottom),
    proximal: px(z.proximal),
    time_from: z.time_from,
    time_to: z.time_to,
  })),
};
const payload = `${OUT}/chart-audit-shapes.json`;
writeFileSync(payload, JSON.stringify(shapes, null, 1));

// Shelled out rather than fetched: there is no endpoint for the auditor and
// adding one would put an unauthenticated model call on the API surface. This
// also keeps the grounding check on the Python side, where the caller cannot
// skip it.
const python = join(BACKEND, ".venv", "Scripts", "python.exe");
const run = spawnSync(
  python,
  ["-m", "app.llm", "audit", "--image", shot, "--payload", payload],
  { cwd: BACKEND, encoding: "utf8", env: { ...process.env, ZONELAB_LLM_BACKEND: "cli" } },
);

console.log(`\n=== the shapes the engine says it drew (${shapes.zones.length} of ` +
            `${drawing.zones.length} zones in view) ===`);
for (const [n, z] of shapes.zones.entries()) {
  console.log(
    `  ${String(n).padStart(2)}  ${z.side.padEnd(6)} ${z.state.padEnd(10)} ` +
      `${z.caption.padEnd(20)} box ${z.bottom} .. ${z.top}  proximal ${z.proximal}`,
  );
}
console.log(`\n  image   ${shot}\n  payload ${payload}`);

if (run.error || run.status !== 0) {
  console.error(`\nharness failure: the chart auditor could not run`);
  console.error((run.stderr || String(run.error)).trim());
  process.exit(2);
}

let reply;
try {
  reply = JSON.parse(run.stdout);
} catch {
  console.error(`\nharness failure: the auditor printed something unreadable:\n${run.stdout}`);
  process.exit(2);
}

console.log(`\n=== what the model says it SEES - claims to verify, not results ===\n`);
console.log(reply.text.trim());
console.log(`\n=== grounding: ${reply.grounded ? "USABLE" : "UNUSABLE"} ===`);
console.log(reply.reason);
if (!reply.grounded) {
  // Not an exit code. The model inventing a number is the grounding check doing
  // its job, and this harness reporting it is the check being visible. Only a
  // harness that cannot look at all has failed.
  console.log(
    "\nThe prose above is quoted so it can be read, NOT because it is trusted: " +
      "it carries at least one number the engine never produced.",
  );
}
console.log(
  `\nEvery line the model wrote is a claim. Check each one against the shape ` +
    `list above and the image on disk before believing it.`,
);
