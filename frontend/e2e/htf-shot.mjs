import { chromium } from "playwright";

const OUT = process.argv[2];
const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1680, height: 950 } });
await page.goto("http://127.0.0.1:3100/", { waitUntil: "networkidle" });
await page.waitForTimeout(5500);

await page.locator("select").nth(2).selectOption("1000"); // more bars, more HTF history
await page.waitForTimeout(3500);
await page.locator("select").nth(3).selectOption("4h"); // the HTF picker
await page.waitForTimeout(4500);

const rows = await page.locator("aside").last().locator("button").allTextContents();
console.log(`zone rows: ${rows.length}`);
console.log(rows.slice(0, 10).map((r) => r.replace(/\s+/g, " ").trim()).join("\n"));

await page.screenshot({ path: `${OUT}/htf-4h-on-15m.png` });
await browser.close();
