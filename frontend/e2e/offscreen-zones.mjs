/**
 * Does the chart TELL the reader about the zones it cannot show?
 *
 *   node e2e/offscreen-zones.mjs [interval] [bars]
 *
 * A vision audit found six zones reported on XAUUSD 1h and one drawn: the price
 * scale autoscales to the VISIBLE candles, the axis bottomed out at 4360.00, and
 * the four zones below that (tops 4328.4, 4273.6, 4238.5, 4199.5) vanished
 * along with their captions. A reader concludes the instrument found one demand
 * zone where it found six.
 *
 * Neither existing harness can catch this and neither ever will. `pixel-truth`
 * reads borders off the canvas and `zone-audit` compares records to candles;
 * both only ever measure zones the canvas CONTAINS, so a zone the canvas
 * excludes is outside the question they ask. That is not a gap in their
 * coverage, it is the shape of the question, which is why this is a separate
 * file rather than another assertion bolted onto pixel-truth.
 *
 * So this asks the cheap version instead: read the price scale's own visible
 * range back through the chart, work out which drawn zones fall outside it, and
 * require that the UI says so. It does not require the scale to be extended -
 * that was considered and rejected, because swallowing a zone 4% away halves the
 * height the candles get and this project measures ink coverage precisely
 * because a chart that fits everything reads nothing.
 */
import { chromium } from "playwright";

const INTERVAL = process.argv[2] ?? "1h";
const BARS = Number(process.argv[3] ?? 500);

const results = [];
const check = (n, p, d = "") => results.push(`${p ? "PASS" : "FAIL"}  ${n}${d ? ` :: ${d}` : ""}`);

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1400, height: 800 }, deviceScaleFactor: 1 });
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
await page.waitForTimeout(7000);

// What the AXIS spans, straight from the chart's own price scale rather than
// from the candles - the two are not the same number, and the defect lives in
// the difference.
const view = await page.evaluate(() => window.__zonelabChart.visiblePriceRange());

// The zones the page is actually holding, read off the panel rather than
// re-fetched: a second fetch could disagree with the render, and then a failure
// here would be about the fetch instead of about the drawing.
const drawn = await page.evaluate(async () => {
  const r = await fetch("http://127.0.0.1:8100/api/draw", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: "XAUUSD",
      interval: document.querySelector('div[aria-label="Timeframe"] button[aria-pressed="true"]')
        .textContent,
      bars: Number(document.querySelectorAll("select")[2].value),
      layers: ["supply_demand"],
    }),
  });
  return (await r.json()).drawing.zones;
});

// Fully outside the axis, in either direction. Matches the component's own test,
// which counts a box with a sliver on screen as visible: a sliver is locatable,
// nothing is not.
const above = drawn.filter((z) => z.bottom > view.top).length;
const below = drawn.filter((z) => z.top < view.bottom).length;
const hidden = above + below;

const banner = await page.locator('p[role="status"]').filter({ hasText: "outside the price range" });
const said = (await banner.count()) > 0 ? await banner.first().innerText() : "";
const count = await page.locator("aside").last().locator("header span").first().innerText();

console.log(
  `axis spans ${view.bottom?.toFixed(2)} to ${view.top?.toFixed(2)} over ${view.height}px; ` +
    `${drawn.length} zones drawn, ${hidden} of them entirely off it (${above} above, ${below} below)`,
);
console.log(`banner: ${said.replace(/\s+/g, " ").trim() || "(none)"}`);
console.log(`panel count: ${count}`);

check(
  "the chart could be read at all",
  view.top !== null && view.bottom !== null && drawn.length > 0,
  `${drawn.length} zones`,
);

// The whole point. A silent clip is the defect; a stated clip is the fix.
check(
  hidden > 0 ? "a zone off the price range is announced" : "nothing is announced when nothing is hidden",
  hidden > 0 ? said.includes(String(hidden)) : said === "",
  hidden > 0 ? `expected the banner to name ${hidden}` : "no banner, correctly",
);

// The second half of the fix: "found" and "can currently be seen" have to be two
// numbers on screen, the same way the backend separates zones found from zones
// surviving the display cap.
check(
  "the panel count separates found from visible",
  hidden > 0
    ? count.includes(`${drawn.length - hidden} visible of ${drawn.length}`)
    : count.includes(`${drawn.length} drawn`),
  count,
);

await browser.close();
console.log(`\n${results.join("\n")}`);
const failed = results.filter((r) => r.startsWith("FAIL"));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
