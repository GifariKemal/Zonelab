/**
 * Frame every drawn zone and screenshot it, so the geometry can be checked by
 * eye against the candles that produced it.
 *
 *   node e2e/zone-audit.mjs <out-dir> [interval] [bars]
 *
 * The statistical calibration answers "do these zones discriminate outcomes".
 * It cannot answer "is this box in the right place", which is a question about
 * whether the drawing matches the method. Only looking answers that.
 *
 * Each crop is written next to a JSON record of what the backend claims the
 * zone is, so the picture and the numbers can be compared directly.
 */
import { writeFileSync } from "node:fs";
import { chromium } from "playwright";

const OUT = process.argv[2];
const INTERVAL = process.argv[3] ?? "15m";
const BARS = Number(process.argv[4] ?? 500);
const API = "http://127.0.0.1:8100";

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1400, height: 800 }, deviceScaleFactor: 2 });
await page.goto("http://127.0.0.1:3100/", { waitUntil: "networkidle" });
await page.waitForTimeout(6000);

// Put the CHART on the interval being audited before fetching anything.
// Without this the page keeps its default series while the script frames
// timestamps from another timeframe, and every screenshot silently shows the
// wrong candles at a meaningless zoom. The arithmetic still passes, which is
// what makes the failure mode dangerous.
await page.locator(`div[aria-label="Timeframe"] button:text-is("${INTERVAL}")`).click();
await page.locator("select").nth(2).selectOption(String(BARS));
await page.waitForTimeout(6000);

// Same request the page made, so the zones framed are the zones on screen.
const drawn = await page.evaluate(
  async ([api, interval, bars]) => {
    const r = await fetch(`${api}/api/draw`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: "XAUUSD", interval, bars, detectors: ["supply_demand"] }),
    });
    return r.json();
  },
  [API, INTERVAL, BARS],
);

const { candles, drawing } = drawn;

// Prove the chart is showing these bars, not merely that the API returned them.
// A frame drawn from timestamps the series does not contain is not a picture of
// anything, and it looks entirely normal.
const onScreen = await page.evaluate(() => {
  const range = window.__zonelabChart.chart.timeScale().getVisibleRange();
  return range ? { from: Number(range.from), to: Number(range.to) } : null;
});
if (!onScreen || onScreen.to < candles[0].time || onScreen.from > candles.at(-1).time) {
  console.error(
    `the chart is not showing the ${INTERVAL} series that was fetched ` +
      `(visible ${JSON.stringify(onScreen)}, data ${candles[0].time}..${candles.at(-1).time})`,
  );
  await browser.close();
  process.exit(2);
}

const records = [];

for (const [n, zone] of drawing.zones.entries()) {
  const a = zone.anatomy;
  // Frame the whole formation plus a few bars either side, so the leg-in, the
  // base and the leg-out are all visible in one picture.
  const from = candles[Math.max(0, a.leg_in_from - 4)].time;
  const to = candles[Math.min(candles.length - 1, a.leg_out_to + 10)].time;

  await page.evaluate(
    ([f, t]) => window.__zonelabChart.chart.timeScale().setVisibleRange({ from: f, to: t }),
    [from, to],
  );
  await page.waitForTimeout(350);

  const name = `zone-${String(n).padStart(2, "0")}-${zone.kind}-${zone.state}`;
  await page.locator("main").screenshot({ path: `${OUT}/${name}.png` });

  // What the picture SHOULD show, from the candles themselves rather than from
  // the zone record. If these disagree with the zone, the detector is wrong.
  const base = candles.slice(a.base_from, a.base_to + 1);
  records.push({
    file: `${name}.png`,
    kind: zone.kind,
    side: zone.side,
    state: zone.state,
    claimed: { top: zone.top, bottom: zone.bottom, proximal: zone.proximal, distal: zone.distal },
    base_bars: base.length,
    base_high_from_candles: Math.max(...base.map((c) => c.high)),
    base_low_from_candles: Math.min(...base.map((c) => c.low)),
    leg_in_bars: a.leg_in_to - a.leg_in_from + 1,
    leg_out_bars: a.leg_out_to - a.leg_out_from + 1,
    departure_atr: zone.departure_atr,
  });
}

writeFileSync(`${OUT}/zone-audit.json`, JSON.stringify(records, null, 1));
await browser.close();

// Independent arithmetic on the candles, not a restatement of the zone record.
//
// With one documented exception, and leaving it out made this check fail on any
// day a thin base happened to land in the window - correct most runs, wrong
// intermittently, which is worse than wrong always. A base shorter than
// `zone_min_atr` ATR is deliberately grown to that floor so it stays visible,
// hoverable and able to register a touch, and it is grown from the PROXIMAL
// side only so the stop never moves into the base. So a grown zone matches its
// candles on the DISTAL edge exactly, and sits outside them on the proximal
// edge by construction.
//
// What still has to hold for a grown zone, and is checked below: the distal is
// exact, and the proximal moved OUTWARD rather than inward. A zone whose
// proximal moved into the base would be a real defect and is still caught.
const exact = (a, b) => Math.abs(a - b) <= 1e-6;
const mismatched = records.filter((r) => {
  const demand = r.side === "demand";
  const distalOk = demand
    ? exact(r.claimed.bottom, r.base_low_from_candles)
    : exact(r.claimed.top, r.base_high_from_candles);
  const proximalOk = demand
    ? r.claimed.top >= r.base_high_from_candles - 1e-6
    : r.claimed.bottom <= r.base_low_from_candles + 1e-6;
  const untouched =
    exact(r.claimed.top, r.base_high_from_candles) &&
    exact(r.claimed.bottom, r.base_low_from_candles);
  r.grown_to_minimum_height = distalOk && proximalOk && !untouched;
  return !(distalOk && proximalOk);
});
const grown = records.filter((r) => r.grown_to_minimum_height).length;
console.log(`framed ${records.length} zones at ${INTERVAL}`);
console.log(
  mismatched.length
    ? `MISMATCH: ${mismatched.length} zone(s) do not match their own base candles\n` +
        JSON.stringify(mismatched, null, 1)
    : `every zone's distal is exactly its base candles' extreme, and no ` +
        `proximal moved inward` +
        (grown
          ? `\n${grown} of ${records.length} were grown to the minimum height, ` +
            `from the proximal side only`
          : ""),
);
process.exit(mismatched.length ? 1 : 0);
