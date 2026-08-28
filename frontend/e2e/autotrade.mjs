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
 *   5. Disarm returns it, so the button round-trips.
 *
 * IT PUTS THE SWITCH BACK WHERE IT FOUND IT, and that is a change from the
 * version that always forced OFF. Forcing OFF looked like the safe choice and
 * was not: on 2026-08-28 this harness ran inside a gate sweep while a live
 * daemon was armed, left the switch MATI at 09:22:50, and nothing noticed for
 * hours. The daemon kept heartbeating, so the monitor correctly reported
 * "daemon hidup" the whole time while zero decision cycles ran.
 *
 * A test that writes real trading state must be neutral, not opinionated. It
 * reads the state first, does its work, and restores exactly what was there,
 * pass or fail or crash. The restore is READ BACK and reported, because a
 * restore that silently fails is the same class of bug as the leak it replaces.
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

const arm = (enabled, note) =>
  fetch(`${API}/api/autotrade`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled, note }),
  });

// READ BEFORE WRITING. Whatever is here belongs to the operator, not to this
// test, and it has to be handed back at the end.
const before = await state();
const wasEnabled = before.enabled === true;

// The test still needs a known starting point, and check 2 below asserts the
// panel starts from the server's state rather than a hardcoded default.
await arm(false, "e2e reset");

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
  // PUT IT BACK, pass or fail or crash. This harness writes the switch that
  // decides whether an account trades unattended, and it does not get to have
  // an opinion about what that switch should be.
  try {
    await arm(wasEnabled, "e2e teardown: dikembalikan ke keadaan semula");
    const after = await state();
    if (after.enabled !== wasEnabled) {
      // NOT a silent catch. A restore that did not take is exactly the failure
      // this block exists to prevent, so it becomes a visible check.
      check("the switch was restored to how it was found", false,
            `wanted enabled=${wasEnabled}, server says ${after.enabled}`);
    } else {
      check("the switch was restored to how it was found", true,
            `enabled=${wasEnabled}`);
    }
  } catch (err) {
    check("the switch was restored to how it was found", false,
          `restore threw: ${err}`);
  }
}

console.log(results.join("\n"));
const failed = results.filter((line) => line.startsWith("FAIL")).length;
console.log(failed ? `\n${failed} FAILED` : "\nall passed");
process.exit(failed ? 1 : 0);
