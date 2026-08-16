/**
 * Full feature sweep. Drives every control the UI exposes, asserts the app
 * responds, and screenshots the states worth looking at with human eyes.
 *
 *   node .sweep.mjs <screenshot-dir>
 */
import { chromium } from "playwright";

const SHOTS = process.argv[2];
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

const zoneCount = async (page) => {
  const t = await page.locator("text=/\\d+ drawn/").first().textContent();
  return Number(t.match(/(\d+)/)[1]);
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
const providers = await page.locator("select").nth(1).locator("option").allTextContents();
check("only available providers are offered", providers.length >= 3, providers.join(","));

// A provider either draws a chart or says in the upstream's own words why it
// cannot. Asserting that every provider RENDERS asserts that somebody else's
// service is up: this suite failed four checks the day the Aurix bridge
// answered "No OHLCV data for GOLD M15", which is that bridge's problem and is
// exactly the behaviour this app is built to surface rather than swallow.
expectingFailure = true;
for (const p of providers) {
  await page.locator("select").nth(1).selectOption(p);
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
await page.locator("select").nth(1).selectOption("binance");
await settle(page, 3000);

// ================================================================== symbols
const symbols = await page.locator("select").nth(0).locator("option").allTextContents();
expectingFailure = true; // binance carries neither EURUSD nor every alt symbol
for (const s of symbols) {
  await page.locator("select").nth(0).selectOption(s);
  await settle(page, 3500);
  const alerts = await appAlert(page);
  // BTCUSD and EURUSD are not on every provider; a spoken error is the correct
  // outcome there, a silent blank chart is not.
  check(`symbol ${s} either renders or explains itself`,
        (await page.locator("canvas").count()) > 0 || alerts.length > 0,
        alerts.join("|"));
}
await page.locator("select").nth(0).selectOption("XAUUSD");
await settle(page, 3000);
expectingFailure = false;
check("recovering from a provider error clears the banner",
      (await appAlert(page)).length === 0, (await appAlert(page)).join("|"));

// ==================================================================== bars
for (const n of ["200", "500", "1000"]) {
  await page.locator("select").nth(2).selectOption(n);
  await settle(page, 3500);
  const shown = await page.locator("text=/\\d+ bars/").first().textContent();
  // N, or N-1 at the vendor's page limit. Binance caps a klines page at 1000
  // and the newest of those is the bar still forming, which is now dropped
  // before the detector sees it - so only 999 CLOSED bars exist in one page.
  // Asserting a flat 1000 was asserting a count only reachable by drawing on
  // an unclosed bar.
  const got = Number(shown.match(/(\d+)/)[1]);
  check(`bars ${n} honoured`, got === Number(n) || got === Number(n) - 1, shown);
}
await page.locator("select").nth(2).selectOption("500");
await settle(page, 3000);

// ================================================= every slider at both ends
// The exact set, not a count. A count says "twelve things exist" and passes
// happily when one of them is renamed or swapped for another, which is the same
// blindness that let an assertion here drive the wrong slider for weeks.
const EXPECTED_SLIDERS = [
  "ATR period", "Impulse body", "Impulse size", "Max base bars",
  "Max base height", "Max base drift", "Departure gate", "Profit margin",
  "Road ahead", "Mitigation depth", "Zones per side", "Merge overlap",
];
const sliders = page.locator('input[type="range"]');
const sliderCount = await sliders.count();
const labels = [];
for (let i = 0; i < sliderCount; i++) {
  labels.push(
    await sliders.nth(i).evaluate((el) => el.closest("label")?.innerText.split("\n")[0] ?? "?"),
  );
}
const missing = EXPECTED_SLIDERS.filter((l) => !labels.includes(l));
const extra = labels.filter((l) => !EXPECTED_SLIDERS.includes(l));
check(
  "every parameter is exposed, and only those",
  missing.length === 0 && extra.length === 0,
  `missing [${missing}] extra [${extra}]`,
);

for (let i = 0; i < sliderCount; i++) {
  const s = sliders.nth(i);
  const label = labels[i];
  const min = await s.getAttribute("min");
  const max = await s.getAttribute("max");
  for (const v of [min, max]) {
    await s.fill(v);
    await settle(page, 2400);
    const alerts = await appAlert(page);
    check(`${label} at ${v} does not break`, alerts.length === 0, alerts.join("|"));
  }
}
await page.locator("text=Reset parameters").click();
await settle(page, 3000);
check("reset restores a drawable chart", (await zoneCount(page)) > 0);

// ================================================================== toggles
const beforeBroken = await zoneCount(page);
await page.getByRole("switch", { name: "Show broken" }).click();
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
await page.getByRole("switch", { name: "Show mitigated" }).click();
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
const htfSelect = page.locator("select").nth(3);
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
const afterSwitch = await page.locator("select").nth(3).locator("option").allTextContents();
check("htf options re-scope when the chart timeframe changes",
      !afterSwitch.includes("4h"), afterSwitch.join(","));
await page.locator('div[aria-label="Timeframe"] button:text-is("15m")').click();
await settle(page, 3500);
await page.locator("select").nth(3).selectOption("off");
await settle(page, 3000);

// ========================================================= zone inspection
const rail = page.locator("aside").last();
const rows = await rail.locator("button").count();
check("zone list is populated", rows > 0, `${rows} rows`);

let inspected = 0;
for (let i = 0; i < Math.min(rows, 4); i++) {
  await rail.locator("button").nth(i).click();
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
check("the validated gate finding is shown, with the numbers that are true now",
      (await page.locator("text=/85.8%/").count()) === 1
      && (await page.locator("text=/64.4%/").count()) === 1);

await page.screenshot({ path: `${SHOTS}/sweep-02-inspector.png` });

await page.keyboard.press("Escape");
await page.waitForTimeout(400);
check("escape clears the inspector", (await page.locator("text=Bars that formed it").count()) === 0);

// ============================================================== detectors
const detectorButtons = page.locator('div[aria-label="Detectors"] button');
check("all three detectors are offered", (await detectorButtons.count()) === 3);

const sdOnly = await zoneCount(page);
await page.locator('div[aria-label="Detectors"] button:text-is("FVG")').click();
await settle(page, 3000);
check("adding a detector adds drawings", (await zoneCount(page)) > sdOnly,
      `${sdOnly} -> ${await zoneCount(page)}`);
check("detectors compose, they do not replace",
      (await appAlert(page)).length === 0);

await page.locator('div[aria-label="Detectors"] button:text-is("OB")').click();
await settle(page, 3000);
check("a third detector still renders", (await page.locator("canvas").count()) > 0);

// Turning them all off would leave a chart that is empty for a reason no one
// can see, which is the one failure mode this app exists to avoid.
for (const label of ["S&D", "FVG", "OB"]) {
  await page.locator(`div[aria-label="Detectors"] button:text-is("${label}")`).click();
  await settle(page, 1600);
}
check("the last detector cannot be switched off", (await zoneCount(page)) > 0,
      `${await zoneCount(page)} drawn`);

await page.locator('div[aria-label="Detectors"] button:text-is("S&D")').click();
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
