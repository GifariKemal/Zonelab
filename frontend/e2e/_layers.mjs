/**
 * Put a layer in a known state on the timeframe that is on screen.
 *
 * WHY THIS IS SHARED and not another twenty lines pasted into each harness.
 * Layers became per-timeframe on 2026-09-10: a set switched on at 1h no longer
 * follows the reader to M15, because the boxes it draws there are a different
 * set of boxes. Every harness that clicks a timeframe button therefore lands on
 * a rail with nothing on, and six of them used to rely on the boot default
 * coming with them.
 *
 * The trap that makes a helper worth it: `click()` is a TOGGLE. A harness that
 * clicks "supply and demand" to turn it OFF, on a timeframe where it was never
 * on, turns it ON - and then measures the wrong chart while every assertion
 * about the app still passes. That is the same shape as the argv mix-up in
 * `docs/CALIBRATION.md`, where a harness graded the default layer for a run
 * labelled as another one. So this reads `aria-checked` and clicks only when
 * the state has to change.
 */

const API = "http://127.0.0.1:8100";

/** The registry's own caption for a layer id, memoised per page.
 *
 *  Read from `/api/config` rather than typed, because the menu is built from
 *  the registry and a caption spelled out in a harness is a second copy that
 *  goes stale the day the registry is edited. */
const labels = new WeakMap();

async function labelFor(page, id, api = API) {
  let known = labels.get(page);
  if (!known) {
    known = await page.evaluate(async (base) => {
      const cfg = await (await fetch(`${base}/api/config`)).json();
      return Object.fromEntries(cfg.layers.map((l) => [l.id, l.label]));
    }, api);
    labels.set(page, known);
  }
  const label = known[id];
  if (!label) throw new Error(`no layer "${id}" in the registry the API serves`);
  return label;
}

/** Switch one layer on or off ON THE TIMEFRAME SHOWING, and report whether it
 *  had to move. Returns false when it was already there, so a caller can skip
 *  its settle. */
export async function setLayer(page, id, want = true, { api = API, settle = 3500 } = {}) {
  const label = await labelFor(page, id, api);
  const control = page.getByRole("switch", { name: label, exact: true });
  const now = (await control.getAttribute("aria-checked")) === "true";
  if (now === want) return false;
  await control.click();
  if (settle) await page.waitForTimeout(settle);
  return true;
}

/** Exactly this set on, everything else off, on the timeframe showing.
 *
 *  For the harnesses that need the canvas to hold ONE detector's boxes: with
 *  two on, every box from the other is paint the record cannot account for. */
export async function onlyLayers(page, ids, { api = API, settle = 3500 } = {}) {
  const known = await labelFor(page, ids[0] ?? "supply_demand", api).then(
    () => labels.get(page),
  );
  const want = new Set(ids);
  let moved = false;
  for (const id of Object.keys(known)) {
    moved = (await setLayer(page, id, want.has(id), { api, settle: 0 })) || moved;
  }
  if (moved && settle) await page.waitForTimeout(settle);
  return moved;
}

/** Click a timeframe and leave the layers this caller needs switched on there.
 *
 *  One call, because "change the timeframe" and "the rail is now empty" are one
 *  fact since layers became per-timeframe, and a harness that does the first
 *  without the second measures a chart with nothing on it. */
export async function pickTimeframe(page, interval, ids = [], opts = {}) {
  await page.locator(`div[aria-label="Timeframe"] button:text-is("${interval}")`).click();
  await page.waitForTimeout(opts.settle ?? 3000);
  for (const id of ids) await setLayer(page, id, true, { ...opts, settle: 0 });
  if (ids.length) await page.waitForTimeout(opts.settle ?? 3000);
}

/** Set one `Chips`/`Degrees` button to `on`, clicking only when it has to.
 *
 *  WHY THIS IS NOT `.click()`. Those buttons are TOGGLES carrying
 *  `aria-pressed`, so a blind click sets the state the caller wanted only when
 *  the state was already the opposite - and turns it OFF whenever it was
 *  already on. `setLayer` above was written for exactly this hazard on layer
 *  switches; the chips were left clicking blind, and the failure they produce
 *  is silent and state-dependent: `qt-az-ink.mjs` deselected the SSMT partner
 *  it meant to select, measured a layer with no partner, and reported 0 px
 *  moved for a body pass that paints 927 when driven correctly.
 *
 *  Returns whether anything was clicked, so a caller can skip its settle. */
export async function setPressed(page, group, value, on = true, opts = {}) {
  const button = page.locator(
    `div[role="group"][aria-label="${group}"] button:text-is("${value}")`,
  );
  const now = (await button.getAttribute("aria-pressed")) === "true";
  if (now === on) return false;
  await button.click();
  await page.waitForTimeout(opts.settle ?? 3500);
  return true;
}

/** Leave exactly `values` pressed in one group, and nothing else.
 *
 *  The whole group rather than the named buttons, because a degree left over
 *  from an earlier case is indistinguishable in the output from one this case
 *  asked for. */
export async function onlyPressed(page, group, values, opts = {}) {
  const buttons = page.locator(`div[role="group"][aria-label="${group}"] button`);
  const labels = await buttons.allInnerTexts();
  const want = new Set(values);
  let moved = false;
  for (const label of labels.map((t) => t.trim())) {
    moved = (await setPressed(page, group, label, want.has(label), { settle: 0 })) || moved;
  }
  if (moved) await page.waitForTimeout(opts.settle ?? 3500);
  return moved;
}
