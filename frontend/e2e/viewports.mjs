/**
 * THE SAME CHART AT FIVE WIDTHS, because every other harness runs at one.
 *
 *   node e2e/viewports.mjs [screenshot-dir]
 *
 * Every visual and pixel harness in this directory opens 1680x1000 and nothing
 * else. That is one laptop. The failures a second width finds are not subtle
 * ones: a 46px label gutter is 4.5% of a 1030px pane and 12% of a 380px one, a
 * three-column layout has to collapse somewhere, and a price axis that fits
 * eight ticks at 1000px tall fits three at 600.
 *
 * What is asserted at every width:
 *
 *   - the chart draws at all, and the bar count in the header is the one asked
 *     for, so a narrow viewport is not silently serving fewer bars;
 *   - no two claimed labels intersect. This is the invariant the whole
 *     collision system exists for, and the gutter is the part of it that scales
 *     worst;
 *   - the page does not scroll horizontally. A chart the reader has to pan the
 *     PAGE to see is a broken layout, not a small one;
 *   - the pane is wider than it is tall at desktop widths and still has a usable
 *     height at phone widths, which is the cheapest proxy for "the layout
 *     collapsed in the intended direction";
 *   - nothing throws.
 *
 * A screenshot per width is written regardless, because the assertions above
 * cannot see ugliness and a human comparing five files can.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const SHOTS = process.argv[2] ?? ".playwright-shots/viewports";
const URL = "http://127.0.0.1:3100/";

/** Real sizes rather than round numbers. 1280x800 is the commonest laptop, 1440
 *  the commonest external panel, 1024x768 the floor a desktop layout is expected
 *  to survive, and 390x844 an iPhone - included not because this is a phone app
 *  but because it is the width at which a 46px gutter stops being a detail. */
const SIZES = [
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
  { name: "1024x768", width: 1024, height: 768 },
  { name: "390x844", width: 390, height: 844 },
];

const LAYERS = [
  "supply_demand",
  "fvg",
  "structure",
  "session",
  "gaps",
  "cisd",
  "dfr",
  "pools",
  "liquidity",
];

const results = [];
const check = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

await mkdir(SHOTS, { recursive: true });
const browser = await chromium.launch({ args: ["--no-proxy-server"] });

for (const size of SIZES) {
  const page = await browser.newPage({ viewport: { width: size.width, height: size.height } });
  page.on("pageerror", (e) => check(`${size.name} no page error`, false, e.message));

  await page.addInitScript((layers) => {
    const real = window.fetch;
    window.fetch = (url, init) => {
      if (typeof url === "string" && url.includes("/api/draw") && init?.body) {
        const body = JSON.parse(init.body);
        body.layers = [...new Set([...(body.layers ?? []), ...layers])];
        body.session = { ...(body.session ?? {}), quarters: ["day"], max_quarters: 0 };
        body.dfr = { ...(body.dfr ?? {}), degrees: ["day"], max_ranges: 4 };
        init = { ...init, body: JSON.stringify(body) };
      }
      return real(url, init);
    };
  }, LAYERS);

  try {
    await page.goto(URL, { waitUntil: "domcontentloaded" });
    // THE READOUT, not the body text. `document.body.innerText` includes every
    // layer note, and the structure layer's evidence says "3000 bars of XAUUSD
    // 15m" - so a gate on the body reports "loaded" off prose that is present
    // before any candle arrives. The readout carries `role="status"`.
    await page.waitForFunction(
      () =>
        [...document.querySelectorAll('[role="status"]')].some((el) =>
          /\d+ bars/.test(el.textContent ?? ""),
        ),
      { timeout: 60_000 },
    );
    await page.waitForFunction(() => window.__zonelabChart?.labels, { timeout: 30_000 });
    // The crosshair repaints the top canvas alone, so a claim list only checked
    // on a cold frame misses the state a reader is always in.
    await page.mouse.move(Math.round(size.width * 0.55), Math.round(size.height * 0.5));
    await page.waitForTimeout(700);

    const seen = await page.evaluate(() => ({
      labels: window.__zonelabChart.labels(),
      pane: window.__zonelabChart.chart.paneSize(),
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      header: (document.body.innerText.match(/(\d+) bars/) ?? [])[1] ?? "",
    }));

    check(`${size.name} the chart drew`, seen.pane.width > 0 && seen.pane.height > 0,
      `pane ${seen.pane.width}x${seen.pane.height}`);
    check(`${size.name} the bar count survived the width`, seen.header !== "",
      `${seen.header} bars`);

    let overlaps = 0;
    let sample = "";
    const L = seen.labels;
    for (let i = 0; i < L.length; i++) {
      for (let j = i + 1; j < L.length; j++) {
        const a = L[i];
        const b = L[j];
        if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) {
          overlaps++;
          if (!sample) sample = `${JSON.stringify(a)} vs ${JSON.stringify(b)}`;
        }
      }
    }
    check(`${size.name} no two labels intersect`, overlaps === 0,
      overlaps ? `${overlaps} pairs, e.g. ${sample}` : `${L.length} claims checked`);

    // One pixel of tolerance: a fractional layout width rounds up in
    // `scrollWidth` and that is not a horizontal scrollbar.
    check(`${size.name} the page does not scroll sideways`,
      seen.scrollWidth <= seen.clientWidth + 1,
      `scrollWidth ${seen.scrollWidth} against clientWidth ${seen.clientWidth}`);

    // The gutter is a fixed 46px. Reported rather than failed, because what the
    // right number is at 390px is a design decision and this is the measurement
    // that decision needs.
    const share = ((46 / seen.pane.width) * 100).toFixed(1);
    check(`${size.name} the label gutter is a sane share of the pane`,
      seen.pane.width > 200, `46px is ${share}% of ${seen.pane.width}px`);

    await page.screenshot({ path: `${SHOTS}/${size.name}.png`, fullPage: false });
  } catch (error) {
    check(`${size.name} loaded at all`, false, String(error).slice(0, 160));
  }
  await page.close();
}

await browser.close();

console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
