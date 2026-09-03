/**
 * Click every control on the workstation and report what happened.
 *
 *   node e2e/click-everything.mjs [out-dir]
 *
 * The other harnesses each ask ONE precise question: does the box sit where the
 * record says (pixel-truth), is a zone off the price scale announced
 * (offscreen-zones), does the app survive its API dying (resilience). This one
 * asks the crude question none of them do - press everything, and see whether
 * anything breaks. It is the check that finds the control nobody wired up, the
 * option that 500s, and the combination that was never tried.
 *
 * A failure here is a console error, a failed request, an app-level alert, or a
 * chart that stopped rendering. It deliberately does NOT assert on values: this
 * harness is about survival, and the precise checks live in their own files.
 */
import { writeFileSync } from "node:fs";
import { chromium } from "playwright";

const OUT = process.argv[2] ?? ".playwright-shots";
const URL = "http://127.0.0.1:3100/";

const results = [];
const record = (name, ok, detail = "") =>
  results.push({ name, ok, detail: String(detail).slice(0, 220) });

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });

let consoleErrors = [];
let failedRequests = [];
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("requestfailed", (r) => {
  const why = r.failure()?.errorText ?? "";
  // ERR_ABORTED is the app working, not failing. page.tsx keeps an
  // AbortController per draw and cancels the in-flight request the moment a
  // control changes, so walking a panel of sliders produces a cancelled fetch
  // per step by design. Counting those as failures made this harness report 34
  // problems on a healthy app, which is worse than reporting none: it buries
  // the real ones. Every other failure reason still counts.
  if (r.url().includes("favicon") || why.includes("ERR_ABORTED")) return;
  failedRequests.push(`${r.url()} ${why}`);
});

const settle = (ms = 2200) => page.waitForTimeout(ms);
const alerts = () =>
  page.locator('[role="alert"]:not(#__next-route-announcer__)').allTextContents();

/** Everything that must still be true after any interaction. */
async function healthy(label) {
  const errs = consoleErrors.splice(0);
  const reqs = failedRequests.splice(0);
  const canvases = await page.locator("canvas").count();
  const ok = errs.length === 0 && reqs.length === 0 && canvases > 0;
  record(
    label,
    ok,
    [
      errs.length ? `console: ${errs[0]}` : "",
      reqs.length ? `request: ${reqs[0]}` : "",
      canvases ? "" : "no canvas",
    ]
      .filter(Boolean)
      .join(" | "),
  );
  return ok;
}

await page.goto(URL, { waitUntil: "networkidle" });
await settle(7000);
await healthy("app loads clean");

// ---------------------------------------------------------------- selects
// Symbol x provider is the matrix nothing has ever walked. Most cells are
// legitimate failures - Binance carries no silver - and the requirement is that
// the app SAYS so rather than showing an empty chart, so an alert here is a
// pass as long as nothing crashed.
const selects = page.locator("select");
const selectCount = await selects.count();
for (let i = 0; i < selectCount; i++) {
  const sel = selects.nth(i);
  const options = await sel.locator("option").allTextContents();
  const name = (await sel.getAttribute("aria-label")) || `select-${i}`;
  for (const opt of options) {
    try {
      await sel.selectOption({ label: opt });
      await settle(2600);
      const spoke = (await alerts()).length > 0;
      await healthy(`${name} = ${opt}${spoke ? " (spoke)" : ""}`);
    } catch (e) {
      record(`${name} = ${opt}`, false, e.message);
    }
  }
  // Leave the select on its first option so later steps start from a known place.
  if (options.length) await sel.selectOption({ label: options[0] });
  await settle(2600);
}

// ------------------------------------------------------------- toggles etc
// Visible buttons only, which is also the honest definition of "every control":
// a user can press what they can see. The filter matters in dev, where Next.js
// injects its own hidden issues-overlay button (aria-label "Open issues
// overlay") that no click can reach - it failed this crawler for two runs as a
// mystery control labelled "-10" before it was identified as tooling.
// FALLING BACK TO `aria-label` IS THE WHOLE POINT OF THIS LINE. Every switch in
// this app renders as a button whose only content is a sliding span - its name
// lives in `aria-label` and its `innerText` is empty. With an innerText-only
// label this loop skipped ALL of them, so a harness called "click everything"
// had never once clicked a toggle: not the structure overlay, not the checklist,
// not the four newer ones. It reported 97 of 97 while covering none of them,
// which is the failure mode this project keeps finding in its own instruments
// rather than in its code. A screen reader would have read these controls
// correctly all along; only the crawler could not see them.
// BY INDEX ON A LIVE LOCATOR, never a pre-collected handle list.
//
// `locator("button").all()` snapshots handles. Every switch in this menu
// re-renders the panel when it is pressed - turning a layer on inserts its
// knobs - so React replaces the DOM nodes and every remaining handle detaches.
// `isVisible()` then throws, the catch turns that into false, and the loop
// `continue`s. Silently. The crawl stopped dead after the first switch that
// injected controls and still reported every check it HAD run as a pass: six
// layer switches including the economic calendar were never pressed while the
// harness said 92 of 92.
//
// That is the same failure this file already carries a comment about - it once
// skipped every switch in the app because they have no innerText - and it is
// the reason this loop re-resolves. `nth(i)` binds at use time, and the count is
// re-read each pass so controls that appear mid-crawl are reached too.
const buttons = page.locator("button");
for (let i = 0; i < (await buttons.count()); i++) {
  const btn = buttons.nth(i);
  if (!(await btn.isVisible().catch(() => false))) continue;
  const text = ((await btn.innerText()) || "").trim();
  const aria = ((await btn.getAttribute("aria-label")) || "").trim();
  const label = (text || aria).replace(/\s+/g, " ").slice(0, 40);
  if (!label) continue;
  // Skip the zone rows: there are many, they are covered below by clicking one.
  if (/^(RBR|DBR|RBD|DBD|FVG|OB|IFVG|BRK)\b/.test(label)) continue;
  // DAN LEWATI KEDUA SAKLAR RAIL, karena mengkliknya MENYEMBUNYIKAN panel yang
  // sisa harness ini cari isinya. Itu penyebab dua kegagalan yang berdiri di
  // file ini: "reset button is reachable :: no button matched
  // /reset parameters/i" dan "zone row opens the inspector :: panel says
  // (no header)". Keduanya melaporkan panel yang rusak; panelnya baik, crawler
  // ini yang baru saja menutupnya.
  //
  // Bukan cacat app, dan bukan pula alasan untuk berhenti mengujinya: kedua
  // saklar itu punya harness sendiri di `e2e/rails.mjs`, 9/9, yang memang
  // memeriksa panel hilang lalu kembali.
  if (/^Panel (kiri|kanan)$/.test(label)) continue;
  // A DISABLED BUTTON IS A LEGITIMATE STATE, not a broken one, and clicking it
  // times out after five seconds with a message about a locator - which reads as
  // a broken control. This app disables deliberately in two places and both are
  // right: `Snapshot` until there is a drawing to record, and the preset `Save`
  // until the set has a name. Recorded as a pass rather than skipped silently,
  // so a button that becomes permanently disabled by accident still appears in
  // the census instead of vanishing from it.
  if (await btn.isDisabled().catch(() => false)) {
    record(`button ${label} is disabled rather than broken`, true, "disabled");
    continue;
  }
  try {
    await btn.click({ timeout: 5000 });
    await settle(2000);
    await healthy(`button ${label}`);
  } catch (e) {
    record(`button ${label}`, false, e.message);
  }
}

// ------------------------------------------------------------------ sliders
const sliders = await page.locator('input[type="range"]').all();
for (const [i, s] of sliders.entries()) {
  const label = await s.evaluate(
    (el) => el.closest("label")?.innerText.split("\n")[0] ?? "?",
  );
  for (const spot of ["min", "max"]) {
    try {
      const v = await s.getAttribute(spot);
      await s.fill(v);
      await settle(2200);
      await healthy(`slider ${label} ${spot}=${v}`);
    } catch (e) {
      record(`slider ${label} ${spot}`, false, e.message);
    }
  }
  if (i % 4 === 3) await settle(1200);
}

// ----------------------------------------------------------------- details
const details = await page.locator("details").all();
for (const [i, d] of details.entries()) {
  try {
    await d.locator("summary").click({ timeout: 4000 });
    await settle(400);
  } catch (e) {
    record(`details ${i}`, false, e.message);
  }
}
await healthy("every explanation opens");

// -------------------------------------------------------------- a zone row
// Back to a known-good state first. By this point the crawler has toggled every
// detector and dragged every slider to a limit, so "no zones" here would say
// more about the walk than about the panel.
await page.locator('div[aria-label="Timeframe"] button:text-is("15m")').click();
await settle(1500);
// Matched case-insensitively by ROLE, not by `text-is`. The button's DOM text is
// "Reset parameters" and CSS uppercases it, so `text-is("RESET PARAMETERS")`
// matches nothing - Playwright compares text content, not rendered text. Guarded
// by an if-count, that mismatch made the reset a silent no-op, the sliders stayed
// at the maximum this crawler had just dragged them to, and the run reported "no
// zone rows found" as though the panel were broken. The panel was fine.
const reset = page.getByRole("button", { name: /reset parameters/i });
if (await reset.count()) {
  await reset.click();
  await settle(3000);
} else {
  record("reset button is reachable", false, "no button matched /reset parameters/i");
}
await healthy("reset returns the app to a drawing state");

const row = page.locator('button:has-text("Demand"), button:has-text("Supply")').first();
if (await row.count()) {
  await row.click();
  await settle(1500);
  await healthy("zone row opens the inspector");
  const tabs = await page.locator('button:text-is("Zone"), button:text-is("Plan")').all();
  for (const t of tabs) {
    const name = (await t.innerText()).trim();
    await t.click();
    await settle(1200);
    await healthy(`inspector tab ${name}`);
  }
  await page.keyboard.press("Escape");
  await settle(600);
  await healthy("escape closes the inspector");
} else {
  // Say WHAT the panel holds instead of only that a locator missed. A crawler
  // that has just switched every layer and dragged every slider to a limit can
  // legitimately leave the chart with nothing to list, and "no zone rows found"
  // cannot tell that apart from a broken panel.
  //
  // Read off the SWITCHES rather than a detector strip that no longer exists.
  // Every drawing is now one row in one menu, so the honest diagnostic is which
  // switches are on - and it stays correct when a layer is added, because
  // nothing here names one.
  const header = await page
    .locator('header:has(h2:text-is("Zones")) span.num')
    .first()
    .textContent()
    .catch(() => "(no header)");
  const live = await page
    .getByRole("switch")
    .evaluateAll((els) =>
      els
        .filter((e) => e.getAttribute("aria-checked") === "true")
        .map((e) => e.getAttribute("aria-label"))
        .join(" "),
    )
    .catch(() => "(unknown)");
  record(
    "zone row opens the inspector",
    false,
    `panel says "${header}", switched on: ${live}`,
  );
}

await page.screenshot({ path: `${OUT}/click-everything.png` });
writeFileSync(`${OUT}/click-everything.json`, JSON.stringify(results, null, 1));

const failed = results.filter((r) => !r.ok);
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail ? ` :: ${r.detail}` : ""}`);
}
console.log(`\n${results.length - failed.length}/${results.length} passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);
