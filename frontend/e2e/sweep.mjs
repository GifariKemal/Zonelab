/**
 * Full feature sweep. Drives every control the UI exposes, asserts the app
 * responds, and screenshots the states worth looking at with human eyes.
 *
 *   node .sweep.mjs <screenshot-dir>
 */
import { chromium } from "playwright";

// Defaulted, never left undefined: the artifacts used to land in a directory
// literally named "undefined" whenever the gate ran the harness without an
// argument, which is how the gate always runs it.
const SHOTS = process.argv[2] ?? ".playwright-shots";
const URL = "http://127.0.0.1:3100/";
const results = [];
const errors = [];
const bad = [];

const check = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

// Some steps deliberately provoke an error, and a spoken 502 is the correct
// answer there. Only failures outside those windows count against the app.
let expectingFailure = false;

const browser = await chromium.launch({ args: ["--no-proxy-server"] });

async function newPage(opts = {}) {
  const page = await browser.newPage({ viewport: { width: 1680, height: 950 }, ...opts });
  page.on("console", (m) => {
    if (m.type() === "error" && !expectingFailure) errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    if (r.status() >= 400 && !r.url().includes("favicon") && !expectingFailure) {
      bad.push(`${r.status()} ${r.url()}`);
    }
  });
  return page;
}

/** How many zones the engine DREW, read off the panel header.
 *
 *  The header now says either "N drawn" or, when the price scale hides some,
 *  "N visible of M". This used to match /\d+ drawn/ anywhere on the page, and
 *  the moment an off-screen banner appeared - its text is "2 of 6 drawn zones
 *  are outside the price range" - the bare match started reading the HIDDEN
 *  count instead. It reported "3 -> 3" for a step that really went 3 to 9, so
 *  the harness said a detector had drawn nothing when it had drawn six boxes.
 *  Scoped to the header, and it returns the TOTAL in both wordings, because the
 *  question these assertions ask is what the engine drew.
 */
const zoneCount = async (page) => {
  const t = await page
    .locator('header:has(h2:text-is("Zones")) span.num')
    .first()
    .textContent();
  const split = t.match(/(\d+)\s+visible of\s+(\d+)/);
  return Number(split ? split[2] : t.match(/(\d+)\s+drawn/)[1]);
};
const settle = (page, ms = 2600) => page.waitForTimeout(ms);

/** Height of the tallest chart canvas.
 *
 *  "A canvas exists" is not the same as "the chart is visible". A collapsed
 *  chart renders a bare time axis and still satisfies every element count,
 *  which is exactly how it shipped to the mobile screenshot unnoticed. */
const chartHeight = (page) =>
  page.evaluate(() =>
    Math.max(0, ...[...document.querySelectorAll("canvas")].map((c) => c.getBoundingClientRect().height)),
  );
const appAlert = (page) =>
  page.locator('[role="alert"]:not(#__next-route-announcer__)').allTextContents();

// ===================================================================== load
const page = await newPage();
await page.goto(URL, { waitUntil: "networkidle" });
await settle(page, 5000);

check("app loads with zones", (await zoneCount(page)) > 0, `${await zoneCount(page)}`);
check("chart canvas present", (await page.locator("canvas").count()) > 0);
check("chart is actually tall enough to read", (await chartHeight(page)) > 400,
      `${await chartHeight(page)}px`);
check("no error banner on load", (await appAlert(page)).length === 0);
await page.screenshot({ path: `${SHOTS}/sweep-01-load.png` });

// ============================================================== timeframes
const tfButtons = await page.locator('div[aria-label="Timeframe"] button').allTextContents();
check("all backend intervals are offered", tfButtons.length === 8, tfButtons.join(","));
for (const tf of tfButtons) {
  await page.locator(`div[aria-label="Timeframe"] button:text-is("${tf}")`).click();
  await settle(page, 3000);
  const ok = (await page.locator("canvas").count()) > 0 && (await appAlert(page)).length === 0;
  check(`timeframe ${tf} loads`, ok, (await appAlert(page)).join("|"));
}
await page.locator('div[aria-label="Timeframe"] button:text-is("15m")').click();
await settle(page, 3000);

// ================================================================ providers
// BY NAME, NOT BY POSITION. `select").nth(3)` was the HTF picker until a
// Broker picker landed beside it on 2026-08-20 and every index after Source
// shifted by one - the sweep then timed out waiting for a combobox that had
// moved, which reads as a broken app rather than as a moved control. Each
// `<select>` carries an `aria-label`, so the accessible name is the stable
// handle and a new picker cannot break this again.
const providers = await page.getByRole("combobox", { name: "Source" }).locator("option").allTextContents();
check("only available providers are offered", providers.length >= 3, providers.join(","));

// A provider either draws a chart or says in the upstream's own words why it
// cannot. Asserting that every provider RENDERS asserts that somebody else's
// service is up: this suite failed four checks the day the Aurix bridge
// answered "No OHLCV data for GOLD M15", which is that bridge's problem and is
// exactly the behaviour this app is built to surface rather than swallow.
expectingFailure = true;
for (const p of providers) {
  await page.getByRole("combobox", { name: "Source" }).selectOption(p);
  await settle(page, 3500);
  const alerts = await appAlert(page);
  const drew = (await page.locator("canvas").count()) > 0 && alerts.length === 0;
  check(`provider ${p} either renders or explains itself`, drew || alerts.length > 0,
        alerts.join("|"));
  if (!drew && alerts.length) {
    check(`provider ${p} names the upstream cause`,
          /upstream|API key|not set|HTTP \d{3}/i.test(alerts.join(" ")),
          alerts.join("|"));
  }
}
expectingFailure = false;
await page.getByRole("combobox", { name: "Source" }).selectOption("binance");
await settle(page, 3000);

// ================================================================== symbols
const symbols = await page.getByRole("combobox", { name: "Symbol" }).locator("option").allTextContents();
expectingFailure = true; // binance carries neither EURUSD nor every alt symbol
for (const s of symbols) {
  await page.getByRole("combobox", { name: "Symbol" }).selectOption(s);
  await settle(page, 3500);
  const alerts = await appAlert(page);
  // BTCUSD and EURUSD are not on every provider; a spoken error is the correct
  // outcome there, a silent blank chart is not.
  check(`symbol ${s} either renders or explains itself`,
        (await page.locator("canvas").count()) > 0 || alerts.length > 0,
        alerts.join("|"));
}
await page.getByRole("combobox", { name: "Symbol" }).selectOption("XAUUSD");
await settle(page, 3000);
expectingFailure = false;
check("recovering from a provider error clears the banner",
      (await appAlert(page)).length === 0, (await appAlert(page)).join("|"));

// ==================================================================== bars
for (const n of ["200", "500", "1000"]) {
  await page.getByRole("combobox", { name: "Bars" }).selectOption(n);
  await settle(page, 3500);
  // THE READOUT, by its role, not by a free-text regex. `text=/\d+ bars/` also
  // matches PROSE: the structure layer's evidence says "3000 bars of XAUUSD 15m",
  // and once the sweep has opened every explanation that string is in the DOM -
  // `.first()` then returned an essay about sweep counts, and the assertion
  // failed on three bar counts in a row for a reason that had nothing to do with
  // bars. The readout carries `role="status"` and `aria-live`, so it is
  // addressable exactly.
  const shown = await page
    .getByRole("status")
    .filter({ hasText: /\d+ bars/ })
    .first()
    .textContent();
  // N, or N-1 at the vendor's page limit. Binance caps a klines page at 1000
  // and the newest of those is the bar still forming, which is now dropped
  // before the detector sees it - so only 999 CLOSED bars exist in one page.
  // Asserting a flat 1000 was asserting a count only reachable by drawing on
  // an unclosed bar.
  const got = Number(shown.match(/(\d+)/)[1]);
  check(`bars ${n} honoured`, got === Number(n) || got === Number(n) - 1, shown);
}
await page.getByRole("combobox", { name: "Bars" }).selectOption("500");
await settle(page, 3000);

// ==================================================================== layers
// The whole menu is built from `/api/config`'s `layers`, so everything below
// asks the registry what to expect instead of holding its own copy of the
// thirteen ids. That is the property the refactor was for: a layer added to the
// backend must appear here with no edit to the frontend OR to this file.
const registry = await page.evaluate(async () =>
  (await (await fetch("http://127.0.0.1:8100/api/config")).json()).layers);
// EXACT names. Substring is Playwright's default and "Show mitigated" is a
// prefix of "Show mitigated boxes", so a loose match goes ambiguous the moment
// both a supply-demand and an imbalance layer are on.
const switchNamed = (name) => page.getByRole("switch", { name, exact: true });
const layerSwitch = (id) =>
  switchNamed(registry.find((l) => l.id === id).label);
const setLayer = async (id, want) => {
  const sw = layerSwitch(id);
  if ((await sw.getAttribute("aria-checked")) !== String(want)) await sw.click();
};

check("the API advertises a layer registry", registry.length > 0, `${registry.length}`);

// Every row offered, in the ORDER THE SERVER SENT, which is the draw order and
// is load-bearing: supply and demand runs first because it owns two passes
// nothing else has. A menu that sorted alphabetically would look identical and
// would be lying about what paints over what.
const registryLabels = registry.map((l) => l.label);
// Every switch on the page in DOM order, then narrowed to the layer rows. A
// live layer nests its own knobs - which include switches of their own - INSIDE
// its row, so the raw list interleaves them and only this filter compares like
// with like.
const allSwitchLabels = () =>
  page.getByRole("switch").evaluateAll((els) =>
    els.map((e) => e.getAttribute("aria-label")));
const menuLabels = (await allSwitchLabels()).filter((l) =>
  registryLabels.includes(l));
check(
  "every layer the API advertises is offered, in draw order",
  menuLabels.length === registryLabels.length &&
    registryLabels.every((l, i) => menuLabels[i] === l),
  `menu [${menuLabels}] registry [${registryLabels}]`,
);

// Every row can be asked what is known about it. Several of these have measured
// NEGATIVE results and most have none at all, so a switch with no reachable
// evidence would present all thirteen as equally endorsed.
const evidenceFolds = await page.locator('summary:text-is("Bukti")').count();
check("every layer exposes its evidence", evidenceFolds === registry.length,
      `${evidenceFolds} folds, ${registry.length} layers`);

// Only supply and demand on load. Chart ink is a measured quantity here: five
// detectors alone paint 31.6% of the chart, and past about a third the boxes
// stop annotating price and become its background.
const onByDefault = (
  await page.getByRole("switch").evaluateAll((els) =>
    els.filter((e) => e.getAttribute("aria-checked") === "true")
       .map((e) => e.getAttribute("aria-label")))
).filter((l) => registryLabels.includes(l));
check("only supply and demand ships on",
      onByDefault.length === 1 && onByDefault[0] === registryLabels[0],
      onByDefault.join(","));

// ================================================= every slider at both ends
// The exact set, not a count. A count says "twelve things exist" and passes
// happily when one of them is renamed or swapped for another, which is the same
// blindness that let an assertion here drive the wrong slider for weeks.
//
// It is now asserted TWICE, because a layer's knobs exist only while the layer
// is on: once on the default chart, and once with every layer switched on. The
// second census is what stops a parameter drifting unchecked behind a switch,
// and it covers four blocks - imbalance, pools, liquidity and the checklist -
// that no census reached at all while each overlay carried its own `enabled`.
const SD_SLIDERS = [
  "ATR period", "Impulse body", "Impulse size", "Max base bars",
  "Max base height", "Max base drift", "Departure gate", "Profit margin",
  "Road ahead", "Mitigation depth", "Zones per side", "Merge overlap",
];
const REVEALED_SLIDERS = [
  // The imbalance block, shared by the fair value gap, the order block and the
  // two inverted kinds, and rendered ONCE under the first of them that is on.
  // Four copies would read as four independent thresholds writing one value.
  "Min gap size", "Displacement size", "Displacement window",
  "Gap mitigation depth", "Boxes per side",
  // The structure overlay. It draws no boxes and cannot be capped per side.
  "Major fractal", "Minor fractal", "Sweep reversal", "MSS window", "Events kept",
  // The cycle grid's only slider. Its two degree pickers are chips rather than
  // sliders, deliberately: the degrees are a nested scale (year contains month
  // contains week) and reading them in order left to right is how the method
  // talks about them, which a stack of switches would lose.
  "Quarters kept",
  // Two gap sliders, not one, and they answer different questions: "Gaps kept"
  // is a display cap on the bands, while "Gaps per tier" is the retention the
  // tier zone is DEFINED by - three per kind, which is the owner's own number.
  "Gaps kept", "Gaps per tier",
  "Shortest run", "Interruptions absorbed", "Events drawn",
  // The defining range's only slider, and the cap it sets MULTIPLIES: every
  // band also draws its projection levels, so two multiples on both sides is
  // five objects per band. Its degrees and its extension multiples are not
  // sliders - the degrees for the same reason the cycle grid's are chips, and
  // the multiples because they are the source's own two numbers and inventing a
  // third is exactly what this layer is not allowed to do.
  "Bands drawn",
  "Pools drawn",
  // The Wyckoff layer's only slider, and it arrived without this line. The
  // layer shipped on 31 August 2026 in a6577e0 and this list was last touched on
  // 28 August, so this census read "extra [Trading range width]" and `sweep.mjs`
  // exited 1 from that commit onward - through every commit after it - while the
  // four gates named at the top of CLAUDE.md stayed green. That is the second
  // time a new layer has been added to the registry and left a browser harness
  // red: the first was 29 August, named in CLAUDE.md, and the lesson written
  // there did not reach this file.
  "Trading range width",
  // The PSP layer's only slider, added with the layer on 1 September 2026 and in
  // the same commit, which is the whole lesson of the line above it.
  "Swing points drawn",
];
const sliders = page.locator('input[type="range"]');
const sliderLabels = async () =>
  sliders.evaluateAll((els) =>
    els.map((el) => el.closest("label")?.innerText.split("\n")[0] ?? "?"));

const census = (labels, expected) => {
  const missing = expected.filter((l) => !labels.includes(l));
  const extra = labels.filter((l) => !expected.includes(l));
  return { ok: missing.length === 0 && extra.length === 0, missing, extra };
};

const defaultCensus = census(await sliderLabels(), SD_SLIDERS);
check(
  "the default chart exposes the supply and demand parameters, and only those",
  defaultCensus.ok,
  `missing [${defaultCensus.missing}] extra [${defaultCensus.extra}]`,
);

for (const layer of registry) await setLayer(layer.id, true);
await settle(page, 4000);
const allCensus = census(await sliderLabels(), [...SD_SLIDERS, ...REVEALED_SLIDERS]);
check(
  "with every layer on, every parameter is exposed, and only those",
  allCensus.ok,
  `missing [${allCensus.missing}] extra [${allCensus.extra}]`,
);
check("thirteen layers at once still renders", (await appAlert(page)).length === 0,
      (await appAlert(page)).join("|"));

// Drive them all while they are reachable. This is the one place every knob in
// the app gets pushed to both of its ends.
//
// BY NAME, RE-RESOLVED EACH TIME, not by an index captured before the loop. The
// index version drove 62 fill-and-settle cycles against positions it had read
// once, so anything that re-rendered the panel mid-loop - a dev server reload,
// or a knob whose value changes which blocks are shown - turned into a 30-second
// `locator.fill` timeout naming an ordinal, which says nothing about what broke.
// It happened. An index into this panel has misled this harness before, too:
// inserting the Broker picker shifted `locator("select").nth(3)`.
//
// The names come from `aria-label` on each input, which is stable because the
// wrapping label carries the live value and the input does not.
const allLabels = await sliderLabels();
for (const label of allLabels) {
  const s = page.getByRole("slider", { name: label, exact: true });
  if ((await s.count()) !== 1) {
    check(`slider ${label} is addressable`, false, `${await s.count()} matches`);
    continue;
  }
  const min = await s.getAttribute("min");
  const max = await s.getAttribute("max");
  for (const v of [min, max]) {
    await s.fill(v);
    await settle(page, 2400);
    const alerts = await appAlert(page);
    check(`${label} at ${v} does not break`, alerts.length === 0, alerts.join("|"));
  }
}

for (const layer of registry.slice(1)) await setLayer(layer.id, false);
await settle(page, 3000);
check(
  "switching them back off hides their parameters again",
  census(await sliderLabels(), SD_SLIDERS).ok,
  (await sliderLabels()).join(","),
);

await page.locator("text=Reset parameters").click();
await settle(page, 3000);
check("reset restores a drawable chart", (await zoneCount(page)) > 0);

// ================================================================== toggles
const beforeBroken = await zoneCount(page);
await switchNamed("Show broken").click();
await settle(page);
check("show broken adds zones", (await zoneCount(page)) >= beforeBroken,
      `${beforeBroken} -> ${await zoneCount(page)}`);

// Raise the per-side cap first. At the default 12 the cap binds and freed slots
// refill from the hidden pool, so the total would not move.
// Located by label rather than by index. Inserting a control used to silently
// shift every nth() in this file, and an assertion that quietly starts driving
// the wrong slider still passes.
const sliderByLabel = (name) =>
  page.locator("label").filter({ hasText: name }).locator('input[type="range"]');
await sliderByLabel("Zones per side").fill("40");
await settle(page);

// Assert the invariant, not the arithmetic. Counting zones before and after
// depends on the live window happening to contain a mitigated one right now,
// which is a coin flip that turns green or red with the market rather than
// with the code. "No mitigated rows remain" is true whether there were nine or
// none.
const mitigatedRows = () => page.locator("aside").last().locator("text=Mitigated").count();
const hadMitigated = await mitigatedRows();
await switchNamed("Show mitigated").click();
await settle(page);
check("hiding mitigated leaves no mitigated zones", (await mitigatedRows()) === 0,
      `${hadMitigated} before`);

await page.locator("text=Reset parameters").click();
await settle(page, 3000);

// ============================================================ proximal line
await page.locator('button:text-is("Body")').click();
await settle(page);
check("conservative proximal renders", (await appAlert(page)).length === 0);
await page.locator('button:text-is("Wick")').click();
await settle(page);

// ======================================================= higher timeframe
const htfSelect = page.getByRole("combobox", { name: "HTF" });
const htfOptions = await htfSelect.locator("option").allTextContents();
check("htf offers only higher timeframes", !htfOptions.slice(1).includes("15m"),
      htfOptions.join(","));
check("htf can be switched off", htfOptions[0] === "off", htfOptions[0]);

await htfSelect.selectOption("4h");
await settle(page, 4000);
const withHtf = await zoneCount(page);
// NOT "the count went up". Whether a 4h zone exists in the visible window is a
// property of the market that day, not of this code: measured on XAUUSD, 500
// bars yields 31 four-hour buckets and ZERO surviving zones, while 1000 yields
// 62 and one. This project has already been bitten by exactly this class of
// test - a contract check asserting a live-market property passed at 16 against
// 15 and failed the next day at 17 against 17. Assert the invariant instead:
// asking for a higher timeframe must not lose the local zones or error.
check("switching on a higher timeframe keeps the local zones", withHtf >= 1,
      `${withHtf} zones with htf on`);
// Same reasoning: a 4h zone may genuinely not exist in the window. What must
// hold is that IF one is drawn it carries its own timeframe, never the chart's -
// which timeframe drew a zone is part of what the zone means here, not metadata.
const badges = await page.locator("aside").last().locator("text=/^4h$/").count();
const localBadges = await page.locator("aside").last().locator("text=/^15m$/").count();
// Written once as `badges === 0 || localBadges === 0 || badges > 0`, which is a
// tautology and can never fail. A test that cannot fail is worse than none,
// because it looks like a guard. The real invariant: with a higher timeframe
// selected, every zone on screen carries a timeframe badge, and the only badges
// possible are the chart's own interval and the projected one.
const otherBadges = await page
  .locator("aside").last()
  .locator("text=/^(1m|5m|30m|1h|1d|1w)$/").count();
// A badge means "this zone came from somewhere else", so it appears if and
// only if the zone's timeframe differs from the chart's. Two ways that can
// break, and both are caught here: badging the chart's OWN interval, which is
// noise on every row, and badging a timeframe that was never requested.
check("only projected zones are badged, and only with the chosen timeframe",
      localBadges === 0 && otherBadges === 0,
      `${badges} badged 4h, ${localBadges} badged 15m, ${otherBadges} other`);
check("no error from the higher timeframe pass", (await appAlert(page)).length === 0);
await page.screenshot({ path: `${SHOTS}/sweep-04-htf.png` });

// The picker must re-scope when the chart timeframe changes, or it will offer
// a "higher" timeframe that is now lower than the chart.
await page.locator('div[aria-label="Timeframe"] button:text-is("1d")').click();
await settle(page, 3500);
const afterSwitch = await page.getByRole("combobox", { name: "HTF" }).locator("option").allTextContents();
check("htf options re-scope when the chart timeframe changes",
      !afterSwitch.includes("4h"), afterSwitch.join(","));
await page.locator('div[aria-label="Timeframe"] button:text-is("15m")').click();
await settle(page, 3500);
await page.getByRole("combobox", { name: "HTF" }).selectOption("off");
await settle(page, 3000);

// ========================================================= zone inspection
// BY TESTID, NOT BY POSITION. `aside`.last() plus button index 0..3 was correct
// until PoskoPanel was inserted above ZonePanel in the same aside, and then the
// four clicks landed on triad chips instead of zone rows. Both assertions below
// went red and were read as "pre-existing unrelated"; they were neither.
const zoneRows = page.locator('[data-testid="zone-row"]');
const rows = await zoneRows.count();
check("zone list is populated with ZONE rows", rows > 0, `${rows} rows`);

let inspected = 0;
for (let i = 0; i < Math.min(rows, 4); i++) {
  await zoneRows.nth(i).click();
  await page.waitForTimeout(400);
  const hasBreakdown = (await page.locator("text=Formation").count()) > 0;
  const hasBars = (await page.locator("text=Bars that formed it").count()) === 1;
  if (hasBreakdown && hasBars) inspected++;
}
check("every inspected zone shows formation and provenance", inspected === Math.min(rows, 4),
      `${inspected}/${Math.min(rows, 4)}`);

check("the retired score is gone from the inspector",
      (await page.locator("text=/^Strength$/").count()) === 0);
check("the honest caveat is shown",
      (await page.locator("text=/does not predict them/").count()) === 1);
// Pinned to the CURRENT measured numbers on purpose. This assertion held a
// stale 84.6% for two days after the calibration was recomputed, because it
// checked that a number was on screen rather than that the RIGHT one was, and a
// shipped claim that no longer matches the evidence is worse than no claim.
//
// EXACTLY ONE, and the count is the point. The figures now reach the screen from
// the engine's own layer registry; the departure-gate knob used to repeat them
// as a string typed into the panel, so the same claim had two homes and only one
// of them moved when the calibration did. Two matches here means the second home
// is back.
// UPDATED 26 August 2026, and the reason matters more than the numbers. This
// assertion pinned 85.8% and 64.4% and passed every run - while `app/plan.py`
// had already replaced that pair with 0.430 and 0.402, stating in its own
// comment that the old figures were measured on Binance crypto and were being
// printed as the reason for gold orders. So the code had moved population and
// the screen had not, and the guard held the screen to the population the code
// abandoned. Exactly the failure this comment block was written about, one level
// up: the assertion was right that A number must be on screen, and wrong about
// which.
check("the validated gate finding is shown, with the numbers that are true now",
      (await page.locator("text=/43.0%/").count()) === 1
      && (await page.locator("text=/40.2%/").count()) === 1);

await page.screenshot({ path: `${SHOTS}/sweep-02-inspector.png` });

await page.keyboard.press("Escape");
await page.waitForTimeout(400);
check("escape clears the inspector", (await page.locator("text=Bars that formed it").count()) === 0);

// ============================================================== composition
// The three box detectors that draw ordinary zones. Taken from the registry by
// kind rather than by id, so this reads "the first three detectors" and not a
// list of names copied out of the backend.
const boxDetectors = registry.filter((l) => l.kind === "detector").slice(0, 3);

const sdOnly = await zoneCount(page);
await setLayer(boxDetectors[1].id, true);
await settle(page, 3000);
check("adding a layer adds drawings", (await zoneCount(page)) > sdOnly,
      `${sdOnly} -> ${await zoneCount(page)}`);
check("layers compose, they do not replace", (await appAlert(page)).length === 0);

await setLayer(boxDetectors[2].id, true);
await settle(page, 3000);
check("a third detector still renders", (await page.locator("canvas").count()) > 0);

// Everything off is now a LEGAL state and says so. It used to be unreachable -
// the last detector refused to switch off, because an empty drawing was
// indistinguishable from a broken one. In a menu that shows every switch, an
// empty chart is legible: the panel says nothing is on rather than a control
// silently ignoring a click, which is the worse of the two lies.
for (const layer of boxDetectors) await setLayer(layer.id, false);
await settle(page, 3000);
check("everything off still renders candles",
      (await page.locator("canvas").count()) > 0 && (await appAlert(page)).length === 0,
      (await appAlert(page)).join("|"));
check("everything off says so rather than looking broken",
      (await page.locator("text=/chart is candles only/").count()) === 1);

await setLayer(boxDetectors[0].id, true);
await settle(page, 3000);

// ================================================================ handbook
// The panel is the one part of this app that cannot be understood by looking at
// it, so the way out of it is load-bearing, not decoration.
await page.locator('a:text-is("Buku panduan")').click();
await page.waitForURL("**/docs");
await settle(page, 1200);

const docsText = await page.locator("main").innerText();
check("the handbook opens from the panel", page.url().endsWith("/docs"), page.url());
check("it explains the three acts", docsText.includes("kaki masuk"));
check("it names every slider the panel shows",
      ["Departure gate", "Max base drift", "Road ahead", "Zones per side"]
        .every((s) => docsText.includes(s)),
      docsText.length + " chars");
// The page is long, and the workstation used to lock `body { overflow: hidden }`
// for every route on wide screens. That made the handbook unscrollable past its
// first viewport while looking perfectly fine in a screenshot.
const scrolled = await page.evaluate(async () => {
  window.scrollTo(0, 4000);
  await new Promise((r) => setTimeout(r, 250));
  return window.scrollY;
});
check("a long document can actually be scrolled", scrolled > 1000, `${scrolled}px`);
check("no console errors on the handbook", errors.length === 0, errors.slice(0, 2).join("|"));

await page.screenshot({ path: `${SHOTS}/sweep-06-handbook.png`, fullPage: false });
await page.goto(URL, { waitUntil: "networkidle" });
await settle(page, 3000);

// ================================================================ no NaN
const body = await page.locator("body").innerText();
check("no NaN rendered anywhere", !body.includes("NaN"), body.match(/.{0,30}NaN.{0,30}/)?.[0] ?? "");
check("no undefined rendered anywhere", !body.includes("undefined"));

// ============================================================== keyboard
await page.keyboard.press("Tab");
const focused = await page.evaluate(() => document.activeElement?.tagName);
check("tab reaches an interactive element", ["SELECT", "BUTTON", "INPUT", "A"].includes(focused),
      String(focused));

// ============================================================ filter trace
check("filter trace explains rejections",
      (await page.locator("text=Formations found").count()) === 1);
const traceText = await page.locator("text=Formations found").locator("..").innerText();
check("formations found is a real number", /\d/.test(traceText), traceText.replace(/\n/g, " "));

await page.close();

// ============================================================ mobile layout
const mobile = await newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto(URL, { waitUntil: "networkidle" });
await settle(mobile, 5000);
const overflow = await mobile.evaluate(
  () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
);
check("mobile does not scroll horizontally", overflow <= 1, `${overflow}px overflow`);
check("mobile still renders the chart", (await mobile.locator("canvas").count()) > 0);
check("mobile chart is not collapsed", (await chartHeight(mobile)) > 300,
      `${await chartHeight(mobile)}px`);
await mobile.screenshot({ path: `${SHOTS}/sweep-03-mobile.png`, fullPage: true });
await mobile.close();

// ========================================================= reduced motion
const rm = await newPage({ reducedMotion: "reduce" });
await rm.goto(URL, { waitUntil: "networkidle" });
await settle(rm, 4500);
check("reduced motion still renders", (await rm.locator("canvas").count()) > 0);
await rm.close();

// ============================================================== contrast
const contrast = await newPage();
await contrast.goto(URL, { waitUntil: "networkidle" });
await settle(contrast, 4500);
const lowContrast = await contrast.evaluate(() => {
  const lum = (c) => {
    const [r, g, b] = c.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number);
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const bg = lum(getComputedStyle(document.body).backgroundColor) || 0.008;
  const out = [];
  for (const el of document.querySelectorAll("button, label, h2, h3, h4, dt, dd, p, span")) {
    const text = el.textContent?.trim();
    if (!text || el.children.length || text.length < 2) continue;
    const style = getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none") continue;
    const size = parseFloat(style.fontSize);
    const ratio = (Math.max(lum(style.color), bg) + 0.05) / (Math.min(lum(style.color), bg) + 0.05);
    const required = size >= 18 || (size >= 14 && Number(style.fontWeight) >= 700) ? 3 : 4.5;
    if (ratio < required) out.push(`${text.slice(0, 28)} ${ratio.toFixed(2)}:1 @${size}px`);
  }
  return out;
});
check("all body text meets WCAG AA contrast", lowContrast.length === 0,
      lowContrast.slice(0, 6).join(" | "));
await contrast.close();

await browser.close();

check("zero console errors across the whole sweep", errors.length === 0, errors.slice(0, 3).join(" | "));
check("zero failed requests across the whole sweep", bad.length === 0, bad.slice(0, 3).join(" | "));

console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL"));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
