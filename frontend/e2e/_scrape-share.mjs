/**
 * Render a public share URL with the browser this repo already installs, and
 * write its visible text out.
 *
 *   node e2e/_scrape-share.mjs <url> <outfile>
 *
 * Plain HTTP returns Gemini's app shell: 826 KB with zero occurrences of the
 * conversation's own words. The transcript arrives from a second request the
 * page makes itself, so it needs a real engine, not a fetch.
 *
 * Underscore-prefixed and not in package.json on purpose: this is a one-off
 * reader for a link the operator pasted, not a gate.
 */
import { writeFileSync } from "node:fs";
import { chromium } from "playwright";

const [url, out] = process.argv.slice(2);
if (!url || !out) {
  console.error("usage: node e2e/_scrape-share.mjs <url> <outfile>");
  process.exit(2);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 2400 } });
try {
  await page.goto(url, { waitUntil: "networkidle", timeout: 120_000 });
  // The transcript streams in after the shell paints. Poll the body length
  // until it stops growing rather than trusting a fixed sleep.
  let last = 0;
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(1500);
    const now = (await page.evaluate(() => document.body.innerText)).length;
    if (now === last && now > 0) break;
    last = now;
  }
  // Scroll to the bottom, because long shares lazy-render.
  for (let i = 0; i < 30; i++) {
    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 3));
    await page.waitForTimeout(400);
  }
  const text = await page.evaluate(() => document.body.innerText);
  writeFileSync(out, text, "utf8");
  console.log(`title: ${await page.title()}`);
  console.log(`bytes: ${text.length}`);
  console.log(`first 400: ${text.slice(0, 400).replace(/\n/g, " | ")}`);
} finally {
  await browser.close();
}
