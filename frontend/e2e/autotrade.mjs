/**
 * DOES THE AUTO-TRADE BUTTON ACTUALLY DO ANYTHING? Clicked in a real browser.
 *
 *   node e2e/autotrade.mjs [screenshot-dir]
 *
 * `npm run check` and `npm run build` passing prove the panel COMPILES. They say
 * nothing about whether it renders, whether the button is reachable, or whether
 * clicking it changes the switch the daemon reads. This project has been bitten
 * three times by an instrument reporting green over something that never ran, so
 * the button gets clicked.
 *
 * FIVE THINGS, and the third is the one worth the harness:
 *
 *   1. The panel renders at all.
 *   2. It starts from whatever the API says, not from a hardcoded default.
 *   3. Clicking Arm changes the SERVER's state, read back over HTTP. A button
 *      that only changes its own colour is the exact failure mode here.
 *   4. Armed with no daemon shows the loud warning rather than a calm ON. A
 *      switch that reads armed while nothing trades is worse than one that is off.
 *   5. Disarm returns it, so the test leaves the account switched off.
 *
 * The switch is restored to OFF at the end even when a check fails, because this
 * harness writes real trading state on a real machine.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const SHOTS = process.argv[2] ?? ".playwright-shots";
const WEB = "http://127.0.0.1:3100/";
const API = "http://127.0.0.1:8100";

const results = [];
const check = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

const state = () => fetch(`${API}/api/autotrade`).then((r) => r.json());

await mkdir(SHOTS, { recursive: true });

// Start from a known place rather than from whatever the last run left.
await fetch(`${API}/api/autotrade`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ enabled: false, note: "e2e reset" }),
});

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

try {
  await page.goto(WEB, { waitUntil: "domcontentloaded" });

  const panel = page.locator("section", { has: page.getByText("Auto trade") }).first();
  await panel.waitFor({ state: "visible", timeout: 20_000 });
  check("the panel renders", await panel.isVisible());

  const button = panel.getByRole("button");
  await button.waitFor({ state: "visible", timeout: 10_000 });

  // The label is driven by the API's answer, so it has to settle before it is
  // read: the first paint is the pre-fetch state.
  await page.waitForFunction(
    () => !document.querySelector("section:has-text('Auto trade') button")?.disabled,
    null,
    { timeout: 15_000 },
  ).catch(() => {});

  check(
    "it starts from the server's state, which is off",
    (await button.textContent())?.trim() === "Arm",
    `button said ${JSON.stringify((await button.textContent())?.trim())}`,
  );
  check("no daemon claim while off", !(await state()).enabled);

  await button.click();
  await page.waitForTimeout(600);

  const armed = await state();
  check("clicking Arm changed the SERVER state", armed.enabled === true,
        `api says enabled=${armed.enabled}`);
  check("the button now offers Disarm",
        (await button.textContent())?.trim() === "Disarm",
        `button said ${JSON.stringify((await button.textContent())?.trim())}`);

  const warning = panel.getByText("nothing is trading");
  const shouted = await warning.isVisible().catch(() => false);
  check("armed with no daemon shows the loud warning", shouted === !armed.daemon_alive,
        `daemon_alive=${armed.daemon_alive}, warning shown=${shouted}`);

  await panel.screenshot({ path: `${SHOTS}/autotrade-armed.png` });

  await button.click();
  await page.waitForTimeout(600);
  const off = await state();
  check("clicking Disarm changed the server back", off.enabled === false);
  check("the button offers Arm again",
        (await button.textContent())?.trim() === "Arm");

  await panel.screenshot({ path: `${SHOTS}/autotrade-off.png` });
} finally {
  await browser.close();
  // ALWAYS OFF ON THE WAY OUT, pass or fail. This harness writes the switch that
  // decides whether an account trades unattended.
  await fetch(`${API}/api/autotrade`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled: false, note: "e2e teardown" }),
  }).catch(() => {});
}

console.log(results.join("\n"));
const failed = results.filter((line) => line.startsWith("FAIL")).length;
console.log(failed ? `\n${failed} FAILED` : "\nall passed");
process.exit(failed ? 1 : 0);
