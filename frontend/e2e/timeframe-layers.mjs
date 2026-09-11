/**
 * Layers belong to the timeframe they are read off, and this is the check.
 *
 *   node e2e/timeframe-layers.mjs [screenshot-dir]
 *
 * THE COMPLAINT THIS EXISTS FOR: a supply and demand box switched on at 1h
 * stayed switched on at M1, M15 and H4. The boxes themselves were never stale -
 * `docs/TIMEFRAME-AUDIT.md` measured all 24 layers at all eight intervals on two
 * instruments and not one returned the same price set twice, against a control
 * where the same request twice at one interval was identical 24 times out of 24
 * - so what followed the reader around was the SWITCH, and a switch that means
 * "supply and demand" on one timeframe and a different set of boxes on the next
 * is a switch that answers a question nobody asked.
 *
 * Both halves are asserted here: the switch stays behind, AND the boxes that
 * two timeframes draw are genuinely different sets rather than one set
 * reprinted. The second half is read off the API inside the page, because the
 * panel rounds prices for display and a rounded comparison would pass on two
 * sets that differ by less than a tick.
 */
import { chromium } from "playwright";

const SHOTS = process.argv[2] ?? ".playwright-shots";
const URL = "http://127.0.0.1:3100/";
const API = "http://127.0.0.1:8100";
const results = [];
const check = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1680, height: 950 } });
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));

const settle = (ms = 3000) => page.waitForTimeout(ms);
const zoneCount = async () => {
  const t = await page
    .locator('header:has(h2:text-is("Zones")) span.num')
    .first()
    .textContent();
  const split = t.match(/(\d+)\s+visible of\s+(\d+)/);
  return Number(split ? split[2] : (t.match(/(\d+)\s+drawn/)?.[1] ?? 0));
};
const tf = async (name) => {
  await page.locator(`div[aria-label="Timeframe"] button:text-is("${name}")`).click();
  await settle();
};

await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForTimeout(6000);

// BY THE LABEL THE REGISTRY GIVES IT, not one typed here. The menu is built
// from `/api/config`, so a caption typed in this file is a second copy that
// goes stale the day the registry is edited.
const sdLabel = await page.evaluate(
  async (api) => {
    const cfg = await (await fetch(`${api}/api/config`)).json();
    return cfg.layers.find((l) => l.id === "supply_demand")?.label ?? null;
  },
  API,
);
if (!sdLabel) {
  console.error('no layer "supply_demand" in the registry the API serves');
  await browser.close();
  process.exit(2);
}
const sdSwitch = () => page.getByRole("switch", { name: sdLabel, exact: true });
const sdOn = async () => (await sdSwitch().getAttribute("aria-checked")) === "true";

// ============================================================ the boot state
const boot = await zoneCount();
check("15m boots with supply and demand on", await sdOn());
check("15m boots with zones drawn", boot > 0, `${boot}`);
check(
  "the header names the timeframe the count belongs to",
  (await page.locator("header").first().textContent()).includes("layers on 15m"),
);

// ================================================ the switch does not follow
await tf("1h");
check("1h starts with supply and demand off", !(await sdOn()));
const at1h = await zoneCount();
check("1h starts with nothing drawn", at1h === 0, `${at1h}`);
const empty = await page.locator("aside").first().textContent();
check("the empty state names the timeframe that is empty", empty.includes("1h"));
await page.screenshot({ path: `${SHOTS}/tf-layers-1h-empty.png` });

// =========================================== and switching on here is local
await sdSwitch().click();
await settle(4000);
const drew1h = await zoneCount();
check("switching it on at 1h draws", drew1h > 0, `${drew1h}`);

await tf("15m");
check("15m still has its own set", await sdOn());
const back = await zoneCount();
check("15m draws what it drew before", back === boot, `${boot} -> ${back}`);

await tf("30m");
check("a timeframe never configured is still empty", !(await sdOn()));

// ==================================================== the copy affordance
// The only way across without twenty-four clicks, and it must land on THIS
// timeframe alone - a copy that shared one array would put 30m's later edits
// into 1h's set.
const copy = page.locator('aside button:text-is("1h (1)")');
check("the empty state offers the set from a timeframe that has one", await copy.count() > 0);
if (await copy.count()) {
  await copy.first().click();
  await settle(4000);
  check("the copied set is on here", await sdOn());
  check("and it draws", (await zoneCount()) > 0);
  await sdSwitch().click();
  await settle(3500);
  check("turning it off here leaves it off here", !(await sdOn()));
  await tf("1h");
  check("and the timeframe it was copied FROM is untouched", await sdOn());
}
await page.screenshot({ path: `${SHOTS}/tf-layers-1h-drawn.png` });

// ============================================ the boxes are the timeframe's
// The other half of the claim. Same layer, same symbol, same bar count, two
// intervals: if the price sets match, the switch was the only thing that was
// ever per-timeframe and the drawing was not.
const geometry = await page.evaluate(
  async (api) => {
    const draw = async (interval) => {
      const r = await fetch(`${api}/api/draw`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          symbol: "XAUUSD",
          interval,
          bars: 500,
          layers: ["supply_demand"],
        }),
      });
      const got = await r.json();
      return (got.drawing.zones ?? [])
        .map((z) => `${z.top}/${z.bottom}`)
        .sort()
        .join(",");
    };
    const [a, b, again] = await Promise.all([draw("15m"), draw("1h"), draw("15m")]);
    return { a, b, again };
  },
  API,
);
check(
  "the same request twice is the same set - the control",
  geometry.a === geometry.again,
);
check(
  "15m and 1h draw different boxes",
  geometry.a !== geometry.b,
  `${geometry.a.split(",").length} vs ${geometry.b.split(",").length} boxes`,
);

// ================================ the knobs travel with the switch, and last
// A layer set without the thresholds it was tuned with is a different drawing,
// so `params` is keyed by interval too - and both halves have to SURVIVE a
// reload, because a per-timeframe setup wiped on every refresh leaves the
// reader eight of them to rebuild instead of one.
const STORE = "zonelab.timeframes";
const slider = () => page.getByRole("slider", { name: "Zones per side" });
const stored = () =>
  page.evaluate((k) => JSON.parse(localStorage.getItem(k) ?? "null"), STORE);

await tf("15m");
await slider().fill("7");
await slider().dispatchEvent("change");
await settle(4000);
check("a knob moves on the timeframe it was dragged on",
      (await slider().inputValue()) === "7", await slider().inputValue());

await tf("1h");
check("the same knob is at its default on another timeframe",
      (await slider().inputValue()) !== "7", await slider().inputValue());

await tf("15m");
check("and the tuned value is still there when we come back",
      (await slider().inputValue()) === "7", await slider().inputValue());

const saved = await stored();
check("the whole map is written to storage",
      saved && saved["15m"] && saved["1h"], JSON.stringify(Object.keys(saved ?? {})));
check("storage keeps the knob with the timeframe that owns it",
      saved?.["15m"]?.params?.supply_demand?.max_zones_per_side === 7,
      `${saved?.["15m"]?.params?.supply_demand?.max_zones_per_side}`);
check("and the other timeframe keeps its own",
      saved?.["1h"]?.params?.supply_demand?.max_zones_per_side !== 7,
      `${saved?.["1h"]?.params?.supply_demand?.max_zones_per_side}`);

await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(7000);
check("a reload restores the timeframe's own layers", await sdOn());
check("a reload restores its knobs too",
      (await slider().inputValue()) === "7", await slider().inputValue());

// A HOSTILE STORE MUST NOT BREAK THE CHART. `localStorage` is editable by hand
// and survives every deploy, so a renamed params key would otherwise reach the
// request body as undefined and the backend would 422 a chart nobody
// misconfigured. The store merges over the defaults instead.
await page.evaluate(
  (k) =>
    localStorage.setItem(
      k,
      JSON.stringify({ "15m": { layers: ["supply_demand", 42], params: { supply_demand: { max_zones_per_side: "nonsense", gone: 1 } } } }),
    ),
  STORE,
);
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(7000);
check("a corrupt store still renders a chart",
      (await page.locator("canvas").count()) > 0);
check("a corrupt store raises no error banner",
      (await page.locator('[role="alert"]:not(#__next-route-announcer__)').count()) === 0);

check("no uncaught error on the page", errors.length === 0, errors.join(" | "));

await browser.close();
const failed = results.filter((r) => r.startsWith("FAIL"));
console.log(results.join("\n"));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
if (failed.length) {
  console.log("GAGAL");
  process.exit(1);
}
