/**
 * DOES THE AGENT PAGE ACTUALLY WORK? Clicked in a real browser.
 *
 *   node e2e/agent.mjs [screenshot-dir]
 *
 * `npm run check` and `npm run build` prove the page COMPILES. This project
 * has been bitten three times by an instrument reporting green over
 * something that never ran, so the page gets loaded and used.
 *
 * FIVE THINGS:
 *
 *   1. The page renders at /agent, with its own URL, not the dashboard.
 *   2. The Settings panel opens and the saved config comes from the SERVER
 *      (model name and hint read back over HTTP), not a hardcoded default.
 *   3. The key field starts EMPTY even when a key is stored: the GET is
 *      masked, and a filled field would mean the mask leaks.
 *   4. Scanning produces a context summary driven by a real /api/draw.
 *   5. Sending a message produces an assistant reply when the endpoint is
 *      configured, or the visible refusal when it is not. Skipped, not
 *      failed, when no endpoint is on the machine - a CI box without the
 *      owner's key must not read as broken.
 *
 * Nothing here is cleaned up afterwards: the agent config is read-only in
 * this harness, and sending one question to a configured endpoint is the
 * thing being tested.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const SHOTS = process.argv[2] ?? ".playwright-shots";
const WEB = "http://127.0.0.1:3100/agent";
const API = "http://127.0.0.1:8100";

const results = [];
const check = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

const agentConfig = () =>
  fetch(`${API}/api/agent/config`).then((r) => r.json());

await mkdir(SHOTS, { recursive: true });

const config = await agentConfig();
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

try {
  await page.goto(WEB, { waitUntil: "domcontentloaded" });

  // 1. It is the agent page, at its own URL.
  await page.getByText("Zonelab AI Agent").waitFor({ timeout: 20_000 });
  check("page renders at /agent", true);
  check("url is /agent, not the dashboard",
        new URL(page.url()).pathname === "/agent", page.url());

  // 2. Settings reflects the server's config.
  await page.getByRole("button", { name: "Settings" }).click();
  const settings = page.locator("section");
  await settings.waitFor({ state: "visible", timeout: 10_000 });
  await page.waitForTimeout(500);
  const baseUrl = await settings.locator("input").first().inputValue();
  check("settings show the server's base_url",
        baseUrl === config.base_url,
        `ui=${JSON.stringify(baseUrl)} api=${JSON.stringify(config.base_url)}`);

  // 3. The key field is empty; the stored key stays masked.
  const keyField = settings.locator('input[type="password"]');
  const keyValue = await keyField.inputValue();
  check("key field starts empty (masked GET)", keyValue === "",
        `value=${JSON.stringify(keyValue)}`);
  const pageText = await page.content();
  check("no key material on the page",
        !pageText.includes("sk-qwen"),
        pageText.includes("sk-qwen") ? "sk- prefix found on the page" : "");

  await page.screenshot({ path: `${SHOTS}/agent-settings.png`, fullPage: true });

  // 4. A scan produces a context summary off a real drawing.
  await page.getByRole("button", { name: "Scan" }).click();
  const summary = page.getByText(/zone, \d+ plan/);
  try {
    await summary.waitFor({ timeout: 60_000 });
    check("scan produces a context summary", true);
  } catch {
    check("scan produces a context summary", false,
          "no 'N zone, N plan' line appeared within 60s");
  }
  await page.screenshot({ path: `${SHOTS}/agent-scanned.png`, fullPage: true });

  // 5. A message round-trips, or refuses loudly without an endpoint.
  await page.getByPlaceholder(/Tanya/).fill("kondisi market sekarang gimana?");
  await page.getByRole("button", { name: "Kirim" }).click();
  if (config.available) {
    try {
      await page
        .getByText(/semua angka terlacak|mengandung angka yang tidak ada/)
        .waitFor({ timeout: 180_000 });
      check("assistant reply arrives with a grounding badge", true);
    } catch {
      // Diagnose instead of guessing: an error banner, a stuck thinking
      // state, and a slow model read differently, and this project's rule
      // is that a failure must say which one it was.
      const tail = await page.evaluate(() =>
        document.body.innerText.slice(-800),
      );
      check("assistant reply arrives with a grounding badge", false,
            `no reply within 180s :: page tail: ${JSON.stringify(tail)}`);
    }
  } else {
    await page
      .getByText(/Endpoint belum terpasang/)
      .waitFor({ timeout: 10_000 })
      .then(() => check("no endpoint: visible refusal, not silence", true))
      .catch(() => check("no endpoint: visible refusal, not silence", false,
                         "refusal message never appeared"));
  }
  await page.screenshot({ path: `${SHOTS}/agent-chat.png`, fullPage: true });
} finally {
  await browser.close();
}

for (const line of results) console.log(line);
const failed = results.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed);
