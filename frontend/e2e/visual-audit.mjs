/**
 * Frame every zone on every timeframe, mark the candles the engine used, and
 * write a dossier a human (or an agent) can judge by eye.
 *
 *   node e2e/visual-audit.mjs <out-dir>
 *
 * The arithmetic checks already prove the box matches the numbers. They cannot
 * prove the numbers describe a supply or demand formation at all: a detector
 * can be perfectly self-consistent and still be marking the wrong candles.
 * Only looking answers that, and looking is only useful if the picture shows
 * WHICH candles were classified as what. Hence the markers.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const OUT = process.argv[2];
const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"];
const BARS = 500;
const API = "http://127.0.0.1:8100";

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1500, height: 820 }, deviceScaleFactor: 2 });
await page.goto("http://127.0.0.1:3100/", { waitUntil: "networkidle" });
await page.waitForTimeout(6000);
await page.locator("select").nth(2).selectOption(String(BARS));
await page.waitForTimeout(3000);

const summary = [];

for (const tf of TIMEFRAMES) {
  const dir = `${OUT}/${tf}`;
  mkdirSync(dir, { recursive: true });

  await page.locator(`div[aria-label="Timeframe"] button:text-is("${tf}")`).click();
  await page.waitForTimeout(5000);

  const drawn = await page.evaluate(
    async ([api, interval, bars]) => {
      const r = await fetch(`${api}/api/draw`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: "XAUUSD", interval, bars, detectors: ["supply_demand"] }),
      });
      return r.json();
    },
    [API, tf, BARS],
  );

  const { candles, drawing } = drawn;
  // Refuse to photograph a chart that is not showing these bars. A frame built
  // from timestamps the series does not contain is a picture of nothing, and it
  // looks entirely normal.
  const visible = await page.evaluate(() => {
    const r = window.__zonelabChart.chart.timeScale().getVisibleRange();
    return r ? { from: Number(r.from), to: Number(r.to) } : null;
  });
  if (!visible || visible.to < candles[0].time || visible.from > candles.at(-1).time) {
    console.error(`${tf}: chart is not showing the fetched series, skipping`);
    continue;
  }

  const lines = [
    `# ${tf} — ${drawing.zones.length} zones`,
    "",
    "Markers under the candles: `I` leg-in, `B` base, `O` leg-out.",
    "The shaded box is the zone. The brighter horizontal rule inside it is the",
    "proximal line, the edge price meets first on the way back.",
    "",
  ];

  for (const [n, z] of drawing.zones.entries()) {
    const a = z.anatomy;
    const marks = [];
    for (let i = a.leg_in_from; i <= a.leg_in_to; i++)
      marks.push({ time: candles[i].time, text: "I", color: "#8d99a8" });
    for (let i = a.base_from; i <= a.base_to; i++)
      marks.push({ time: candles[i].time, text: "B", color: "#d9a441" });
    for (let i = a.leg_out_from; i <= a.leg_out_to; i++)
      marks.push({ time: candles[i].time, text: "O", color: "#e4e8ed" });

    await page.evaluate((m) => window.__zonelabChart.markBars(m), marks);

    const pad = Math.max(3, Math.round((a.leg_out_to - a.leg_in_from) * 0.4));
    const from = candles[Math.max(0, a.leg_in_from - pad)].time;
    const to = candles[Math.min(candles.length - 1, a.leg_out_to + pad * 3)].time;
    await page.evaluate(
      ([f, t]) => window.__zonelabChart.chart.timeScale().setVisibleRange({ from: f, to: t }),
      [from, to],
    );
    await page.waitForTimeout(320);

    const file = `${String(n).padStart(2, "0")}-${z.kind}-${z.side}-${z.state}.png`;
    await page.locator("main").screenshot({ path: `${dir}/${file}` });

    const base = candles.slice(a.base_from, a.base_to + 1);
    lines.push(
      `## ${file}`,
      "",
      `- formation **${z.kind}**, side **${z.side}**, state **${z.state}**` +
        `${z.confirmed ? "" : ", still forming"}`,
      `- box ${z.bottom.toFixed(2)} to ${z.top.toFixed(2)}` +
        `, proximal ${z.proximal.toFixed(2)}, distal ${z.distal.toFixed(2)}`,
      `- bars: leg-in ${a.leg_in_to - a.leg_in_from + 1}, base ${base.length},` +
        ` leg-out ${a.leg_out_to - a.leg_out_from + 1}`,
      `- departure ${z.departure_atr} ATR, profit margin ${z.profit_margin}x zone`,
      `- base drift ${z.base_drift}, base overlap ${z.base_overlap}`,
      `- curve ${(z.curve * 100).toFixed(0)}%${z.curve_favourable ? " (favourable)" : ""}`,
      `- tests ${z.touches}, eaten ${(z.penetration_pct * 100).toFixed(0)}%` +
        `${z.arrival_atr === null ? "" : `, arrival ${z.arrival_atr} ATR`}`,
      "",
    );

    summary.push({ tf, file, kind: z.kind, side: z.side, state: z.state, drift: z.base_drift });
  }

  await page.evaluate(() => window.__zonelabChart.markBars([]));
  writeFileSync(`${dir}/DOSSIER.md`, lines.join("\n"));
  console.log(`${tf}: ${drawing.zones.length} zones`);
}

writeFileSync(`${OUT}/summary.json`, JSON.stringify(summary, null, 1));
await browser.close();
console.log(`\ntotal ${summary.length} zones across ${TIMEFRAMES.length} timeframes`);
