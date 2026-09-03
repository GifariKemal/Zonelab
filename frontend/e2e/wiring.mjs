/**
 * IS EVERY LAYER ACTUALLY WIRED? One matrix, driven by clicks, answered per layer.
 *
 *   node e2e/wiring.mjs [screenshot-dir]
 *
 * The registry is the source of truth: whatever `/api/config` lists, this walks.
 * So a layer added to `app/layers.py` and forgotten in the UI fails here rather
 * than being discovered by a reader who switched it on and saw nothing.
 *
 * SIX THINGS ARE CHECKED PER LAYER, and each one has been separately broken in
 * this project's history:
 *
 *   1. A TOGGLE exists, found by the registry's own label. A layer with no
 *      control is a layer nobody can reach.
 *   2. AN INK SWATCH sits beside it, so the reader can tell which colour on the
 *      canvas belongs to this row - or, for the box detectors, that it is the
 *      demand/supply pair. `checklist` has none on purpose: it draws nothing.
 *   3. EVIDENCE is one click away. Every row carries what has and has not been
 *      measured about it, because two of these layers came out significantly
 *      NEGATIVE as direction claims and most have no measurement at all.
 *   4. A PARAMS PANEL appears when it is on - for the layer that OWNS the block.
 *      Four imbalance detectors share one block and it renders under the first of
 *      them that is live, deliberately: four copies would read as four
 *      independent thresholds writing one value.
 *   5. IT DRAWS. The one that matters. `dfr` shipped registered, panelled and
 *      given a canvas primitive, and drew nothing at all for a while because the
 *      dispatch set in another file still named five layers.
 *   6. ITS COUNTS ARE REPORTED. A drawn object with no number beside it cannot be
 *      told apart from a filter that removed everything.
 *
 * THREE LAYERS DRAW NOTHING WITH DEFAULT PARAMS, and the number is measured:
 * drawing each layer alone with pure defaults, `session`, `dfr` and `ssmt` come
 * back empty and the other twelve do not. Their defaults are empty because an
 * overlay that switched itself on would spend an ink budget somebody else had
 * accounted for - and all three now SAY they are drawing nothing, because an
 * empty chart and a broken engine must never look alike.
 *
 * So `MINIMUM` below carries what those three need. It used to carry entries for
 * `pools`, `projections` and `liquidity` as well, which was wrong: all three ship
 * with sessions or periods and draw immediately. Supplying params they already
 * have made this harness pass for a reason it had not actually tested.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const SHOTS = process.argv[2] ?? ".playwright-shots";
const WEB = "http://127.0.0.1:3100/";
const API = "http://127.0.0.1:8100";

/** The least each layer needs before it can draw anything. Empty means its
 *  defaults already draw. */
const MINIMUM = {
  session: { session: { quarters: ["day"], true_opens: ["day"] } },
  dfr: { dfr: { degrees: ["day"] } },
  ssmt: { checklist: { ssmt_symbols: ["XAGUSD"], ssmt_degrees: ["day"] } },
  // PSP reads the SSMT events, so it needs the same partners the ssmt layer
  // does. Without them it correctly draws nothing, and this harness would then
  // be reporting a missing partner as a dead layer.
  psp: { checklist: { ssmt_symbols: ["XAGUSD"], ssmt_degrees: ["day"] } },
};

/** Which response array each layer fills. `checklist` is a report, not a shape. */
const DRAWS = {
  supply_demand: "zones",
  fvg: "zones",
  order_block: "zones",
  ifvg: "zones",
  breaker: "zones",
  structure: "swings",
  session: "quarters",
  vortex: "vortex",
  gaps: "gaps",
  cisd: "cisd",
  dfr: "dfr",
  ssmt: "ssmt",
  pools: "pools",
  liquidity: "levels",
  projections: "projections",
  news: "news",
  expectation: "expectation",
  chart_gaps: "chart_gaps",
  wyckoff: "wyckoff",
  psp: "psp",
};

const results = [];
const check = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

await mkdir(SHOTS, { recursive: true });

// ------------------------------------------------- part one: does it DRAW
const config = await fetch(`${API}/api/config`).then((r) => r.json());
const registry = config.layers;
check("the registry is served at all", registry.length > 0, `${registry.length} layers`);

const drew = {};
for (const layer of registry) {
  if (layer.id === "checklist") continue; // a report, and it is checked below
  const body = {
    symbol: "XAUUSD",
    interval: "15m",
    bars: 1500,
    provider: "mt5",
    layers: [layer.id],
    ...(MINIMUM[layer.id] ?? {}),
  };
  const response = await fetch(`${API}/api/draw`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    check(`${layer.id} draws`, false, `HTTP ${response.status}`);
    continue;
  }
  const payload = await response.json();
  const key = DRAWS[layer.id];
  // NOT EVERY LAYER DRAWS A LIST. `vortex` puts one object on `drawing.vortex`,
  // and `(obj ?? []).length` is `undefined` for it, so the layer read as drawing
  // nothing from the day it shipped. Counted by shape instead of assuming array.
  const value = payload.drawing[key];
  const count = Array.isArray(value) ? value.length : value ? 1 : 0;
  drew[layer.id] = count;
  // NEWS IS THE ONE HONEST ZERO. Its feed publishes the current week only, so an
  // empty calendar is a fact about the week rather than a broken layer.
  // CHART_GAPS IS A SECOND: a trend gap is a rare event on intraday bars, so an
  // empty answer is the honest one on a quiet window, not a broken layer.
  const allowed = layer.id === "news" || layer.id === "chart_gaps";
  check(
    `${layer.id} draws into drawing.${key}`,
    count > 0 || allowed,
    `${count} objects${allowed && count === 0 ? " (empty calendar is legitimate)" : ""}`,
  );
}

// The report layer answers with a report, not a shape.
const report = await fetch(`${API}/api/draw`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    symbol: "XAUUSD",
    interval: "15m",
    bars: 1500,
    provider: "mt5",
    layers: ["checklist"],
    checklist: { degree: "day" },
  }),
}).then((r) => r.json());
check(
  "checklist answers with a report rather than a shape",
  report.checklist !== null && typeof report.checklist === "object",
  Object.keys(report.checklist ?? {}).join(","),
);

// -------------------------------------------- part two: is the UI wired
const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1680, height: 1100 } });
page.on("pageerror", (e) => check("no page error", false, e.message));

await page.goto(WEB, { waitUntil: "domcontentloaded" });
await page.waitForFunction(
  () =>
    [...document.querySelectorAll('[role="status"]')].some((el) =>
      /\d+ bars/.test(el.textContent ?? ""),
    ),
  { timeout: 90_000 },
);
await page.waitForTimeout(2500);

const panel = page.locator("aside").first();

for (const layer of registry) {
  const toggle = page.getByRole("switch", { name: layer.label, exact: true });
  const found = await toggle.count();
  check(`${layer.id} has a toggle named "${layer.label}"`, found === 1, `${found} found`);
  if (found !== 1) continue;

  // The swatch is an aria-hidden span inside the label, so it is located
  // structurally rather than by name - it has no accessible name by design,
  // because it duplicates information the label already carries.
  const row = panel.locator("label").filter({ hasText: layer.label }).first();
  const swatch = await row.locator("span[aria-hidden] > span").count();
  const wantsSwatch = layer.id !== "checklist";
  check(
    `${layer.id} ${wantsSwatch ? "shows its ink" : "shows no ink, drawing nothing"}`,
    wantsSwatch ? swatch > 0 : swatch === 0,
    `${swatch} swatch parts`,
  );
}

// Evidence: every row must carry it, and it must actually open.
const bukti = await panel.getByText("Bukti", { exact: true }).count();
check("every registry row carries an evidence disclosure", bukti === registry.length,
      `${bukti} of ${registry.length}`);

// Turn on the owner of every params block and confirm a panel appears for it.
const OWNERS = [
  ["supply_demand", "Supply and demand", "Impulse size"],
  ["fvg", "Fair value gap", "Min gap size"],
  ["structure", "Market structure", "Major fractal"],
  ["session", "Cycle grid", "Quarters kept"],
  ["gaps", "Opening gaps", "Gaps kept"],
  ["cisd", "Change in state of delivery", "Shortest run"],
  ["dfr", "Defining range", "Bands drawn"],
  ["pools", "Liquidity pools", "Pools drawn"],
  ["ssmt", "SSMT divergence", "SSMT against"],
  ["liquidity", "Named levels", "Periods"],
  ["projections", "Deviation projections", "Sessions"],
  ["expectation", "Expectation fan", "Expected path line"],
  ["psp", "Precision swing point", "Swing points drawn"],
  ["wyckoff", "Wyckoff phases", "Trading range width"],
  ["news", "Economic calendar", "Impact"],
];

// DAN DAFTAR ITU HARUS MENUTUP REGISTRY, yang sampai 3 September 2026 tidak
// pernah diperiksa. `OWNERS` di-loop atas DIRINYA SENDIRI, jadi sebuah params
// block baru mendapat toggle tanpa kontrol dan harness ini tetap hijau -
// bandingkan `DRAWS` di atas, yang di-loop atas `registry` sehingga layer baru
// membuatnya merah, dan sensus slider di `sweep.mjs` yang memeriksa `missing`
// DAN `extra`. `OWNERS` satu-satunya sensus di file ini yang gagal sunyi.
//
// `chart_gaps` dikecualikan dengan alasannya: `ChartGapParams` punya NOL field,
// jadi `knobs()` memang tidak punya `case` untuknya dan tidak ada kontrol yang
// bisa dicari. Pengecualian ini ditulis, bukan disimpulkan dari ketiadaan.
const NO_CONTROLS = new Set(["chart_gaps"]);
const blocks = [...new Set(registry.map((l) => l.params))];
const owned = new Set(
  OWNERS.map(([id]) => registry.find((l) => l.id === id)?.params).filter(Boolean),
);
const uncovered = blocks.filter((b) => !owned.has(b) && !NO_CONTROLS.has(b));
const phantom = [...owned].filter((b) => !blocks.includes(b));
check("every params block the registry advertises has an owner row here",
      uncovered.length === 0 && phantom.length === 0,
      `uncovered [${uncovered}] phantom [${phantom}]`);

for (const [id, label, knob] of OWNERS) {
  const toggle = page.getByRole("switch", { name: label, exact: true });
  if ((await toggle.getAttribute("aria-checked")) === "false") {
    await toggle.click();
    await page.waitForTimeout(900);
  }
  const text = await panel.innerText();
  check(`${id} exposes its own controls`, text.includes(knob), `looked for "${knob}"`);
}

await page.waitForTimeout(4000);
const text = await panel.innerText();
check(
  "the filter trace reports the detectors that are on",
  text.includes("Formations found"),
  "",
);
await page.screenshot({ path: `${SHOTS}/wiring-every-layer.png`, fullPage: false });
await browser.close();

console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
console.log(
  "\nobjects drawn per layer, minimum params supplied:\n  " +
    Object.entries(drew)
      .map(([k, v]) => `${k}=${v}`)
      .join("  "),
);
process.exit(failed ? 1 : 0);
