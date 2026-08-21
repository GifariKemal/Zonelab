/**
 * Every clock this app shows, checked in BOTH daylight-saving states.
 *
 *   node e2e/clock.mjs [out-dir]
 *
 * Two readings are taken off the same UTC epochs and both are wrong in the same
 * way if they are done with an offset instead of a zone:
 *
 *   - the NAME of a session true open, fixed to New York wall time. The owner's
 *     own time board names four - Asia 19:30, London 01:30, NY AM 07:30,
 *     NY PM 13:30 - and the chart prints those instead of a generic TSO.
 *   - the TIME AXIS, which the reader picks: UTC, New York or WIB.
 *
 * THE TRAP IS THE SAME FOR BOTH AND NOTHING ELSE IN THIS SUITE CAN SEE IT. New
 * York is UTC-5 in winter and UTC-4 in summer, so an offset constant is exactly
 * right for half the year and silently wrong for the other half. Every other
 * harness runs on today's date, and today contains only one of the two offsets.
 * Meanwhile the browser sits on Asia/Jakarta, which never shifts, so a naive
 * `getHours()` is not a fallback either - it is a third clock again.
 *
 * Three sections, and they fail for different reasons:
 *
 *   1. THE FUNCTIONS, on fixed timestamps in January AND July, with the process
 *      pinned to Asia/Jakarta so a local reading is detectable. This is where
 *      the DST states are covered, because a live app can only ever be in the
 *      one it is in today.
 *
 *   2. THE CHART'S NAMES, live. Canvas text cannot be read out of the DOM, so
 *      `fillText` is wrapped and every painted string recorded. That is the real
 *      code path - the same primitive, the same timestamps off the API - rather
 *      than the logic re-implemented in the test.
 *
 *   3. THE CHART'S AXIS, live, read the same way: one hovered bar, three zones,
 *      and the crosshair stamp that must carry the zone with the time.
 *
 * Sections 2 and 3 need the app on :3100 and the API on :8100. Section 1 needs
 * neither and runs first, so a broken clock is never reported as a browser
 * problem.
 */
import { writeFileSync } from "node:fs";
import { chromium } from "playwright";

import { clockStamp, clockTick, sessionOpenName } from "../src/lib/clock.ts";

// Set after the imports because ESM hoists them anyway, and it changes nothing
// that matters: every reading below names its zone, so the only thing this pins
// is what a NAIVE reading would return - which is the point of pinning it.
process.env.TZ = "Asia/Jakarta";

const OUT = process.argv[2] ?? ".playwright-shots";
const URL = "http://127.0.0.1:3100/";
const NAMES = ["Asia", "London", "NY AM", "NY PM"];

const results = [];
const record = (name, ok, detail = "") =>
  results.push({ name, ok, detail: String(detail).slice(0, 220) });
const check = (name, got, want) =>
  record(name, got === want, got === want ? "" : `got ${got}, want ${want}`);

const utc = (y, m, d, h, min) => Date.UTC(y, m, d, h, min) / 1000;

// =========================================================== 1. the functions
// The zone the process is standing in, stated rather than assumed: Jakarta is
// UTC+7 all year, so a naive local reading of 12:30 UTC is hour 19 and would
// call this instant Asia instead of NY AM.
record(
  "the test itself stands in a zone with no daylight saving",
  new Date(utc(2026, 0, 15, 12, 30) * 1000).getHours() === 19,
  `local hour of 12:30 UTC is ${new Date(utc(2026, 0, 15, 12, 30) * 1000).getHours()}`,
);

// ---- session names, EST: New York five hours behind UTC.
check("winter: 00:30 UTC is Asia", sessionOpenName(utc(2026, 0, 16, 0, 30)), "Asia");
check("winter: 06:30 UTC is London", sessionOpenName(utc(2026, 0, 15, 6, 30)), "London");
check("winter: 12:30 UTC is NY AM", sessionOpenName(utc(2026, 0, 15, 12, 30)), "NY AM");
check("winter: 18:30 UTC is NY PM", sessionOpenName(utc(2026, 0, 15, 18, 30)), "NY PM");

// ---- session names, EDT: four hours behind, so every one of them moves an
// hour in UTC while staying on the same New York wall clock.
check("summer: 23:30 UTC is Asia", sessionOpenName(utc(2026, 6, 14, 23, 30)), "Asia");
check("summer: 05:30 UTC is London", sessionOpenName(utc(2026, 6, 15, 5, 30)), "London");
check("summer: 11:30 UTC is NY AM", sessionOpenName(utc(2026, 6, 15, 11, 30)), "NY AM");
check("summer: 17:30 UTC is NY PM", sessionOpenName(utc(2026, 6, 15, 17, 30)), "NY PM");

// THE PAIR THAT KILLS AN OFFSET CONSTANT. Whichever offset were hardcoded, one
// of these two would come back named: -5 names the July instant, -4 names the
// January one. Only a real zone leaves both unnamed.
check("an offset of -5 would misname July", sessionOpenName(utc(2026, 6, 15, 12, 30)), null);
check("an offset of -4 would misname January", sessionOpenName(utc(2026, 0, 15, 11, 30)), null);
check("08:30 New York is left unnamed", sessionOpenName(utc(2026, 0, 15, 13, 30)), null);

// ---- axis ticks, one known epoch through all three clocks.
const winter = utc(2026, 0, 15, 12, 30);
const summer = utc(2026, 6, 15, 12, 30);
check("winter tick, UTC", clockTick(winter, "UTC", "time"), "12:30");
check("winter tick, New York", clockTick(winter, "New York", "time"), "07:30");
check("winter tick, WIB", clockTick(winter, "WIB", "time"), "19:30");
// The same UTC time of day in July. UTC and WIB do not move; New York does, and
// an offset constant is exactly what would keep it at 07:30 here.
check("summer tick, UTC", clockTick(summer, "UTC", "time"), "12:30");
check("summer tick, New York moved an hour", clockTick(summer, "New York", "time"), "08:30");
check("summer tick, WIB", clockTick(summer, "WIB", "time"), "19:30");

// The date caveat, pinned rather than left to be rediscovered: a tick at 02:00
// UTC on the first of January is still the previous year in New York, and the
// label says so.
check("a date tick reads the chosen zone's own date",
      clockTick(utc(2026, 0, 1, 2, 0), "New York", "day"), "31");
check("and its own year with it",
      clockTick(utc(2026, 0, 1, 2, 0), "New York", "year"), "2025");

// The stamp always names its clock, because an unlabelled 05:00 is the whole
// hazard this control exists to remove.
check("the stamp carries the zone", clockStamp(winter, "New York"), "15 Jan 07:30 NY");
check("and says UTC when it is UTC", clockStamp(winter, "UTC"), "15 Jan 12:30 UTC");

// ============================================================== 2 and 3, live
const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({
  viewport: { width: 1600, height: 1000 },
  // Pinned, so the trap is present on any machine that runs this and not only
  // on the one it was written on.
  timezoneId: "Asia/Jakarta",
});

// Every string the renderer paints, captured at the only place it exists: the
// canvas. `fillText` is wrapped before any page script runs.
await page.addInitScript(() => {
  window.__painted = [];
  const original = CanvasRenderingContext2D.prototype.fillText;
  CanvasRenderingContext2D.prototype.fillText = function (text, ...rest) {
    window.__painted.push(String(text));
    return original.call(this, text, ...rest);
  };
});

const consoleErrors = [];
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});

const settle = (ms = 2500) => page.waitForTimeout(ms);
const painted = () => page.evaluate(() => window.__painted ?? []);
const clearPainted = () => page.evaluate(() => (window.__painted.length = 0));

await page.goto(URL, { waitUntil: "networkidle" });
await settle(7000);

// ------------------------------------------------------- 2. the session names
// `aria-label` is the only name these controls have - the switch is a button
// whose sole content is a sliding span - which is the same reason the crawler in
// click-everything.mjs has to fall back to it.
await page.getByRole("switch", { name: "Cycle grid" }).click();
await settle(1500);
await page
  .locator('[role="group"][aria-label="True opens"] button:text-is("session")')
  .click();
await settle(4000);
// Quarter boxes too, only so the ribbon under the chart has rows to draw: it is
// built from the quarters, and with none it renders nothing and cannot be
// checked for having survived anything.
await page
  .locator('[role="group"][aria-label="Quarter boxes"] button:text-is("day")')
  .click();
await settle(5000);

const withGrid = await painted();
for (const name of NAMES) {
  record(
    `the chart paints ${name}`,
    withGrid.includes(name),
    withGrid.includes(name) ? "" : `painted: ${[...new Set(withGrid)].join(" ")}`,
  );
}
// The generic tag is the fallback for a session level on none of the four
// instants. Seeing it means either the grid moved or the naming stopped working,
// and both are worth a failure rather than a shrug.
record(
  "no session open falls back to TSO",
  !withGrid.includes("TSO"),
  withGrid.includes("TSO") ? "a session level landed off the four instants" : "",
);

// ------------------------------------------------------------- 3. the axis
// ONE BAR, three clocks. The crosshair is parked on the same pixel each time, so
// the three readings describe the same instant and can only differ by the zone.
// Moving away and back first: a mouse that is already there does not move.
const box = await page.locator("canvas").first().boundingBox();
const at = { x: Math.round(box.x + box.width * 0.6), y: Math.round(box.y + box.height * 0.5) };

/** "16 Aug 19:00 NY" -> { minutes, tag }. Compared as minutes past midnight so a
 *  month boundary cannot break the arithmetic; every offset in play is well
 *  inside twelve hours, which is what makes that safe. */
const parseStamp = (text) => {
  const m = /^\d{2} \w{3} (\d{2}):(\d{2}) (UTC|NY|WIB)$/.exec(text);
  return m ? { minutes: Number(m[1]) * 60 + Number(m[2]), tag: m[3], text } : null;
};

const readZone = async (zone) => {
  // By its own `aria-label`, and exactly: the corner tag beside the axis carries
  // one too, which is the point of it.
  // CLEAR BEFORE THE CHANGE, not after. Selecting a zone is what makes the
  // library repaint the whole time axis, so clearing afterwards threw away the
  // only frame that carries the new tick labels - the crosshair move that
  // followed repaints the stamp and little else. This read "0 ticks" for New
  // York and WIB while a screenshot of the same axis showed them correctly
  // relabelled (UTC 13 14 16 18 19 against New York 12 13 16 17 18), so the
  // harness was wrong and the app was not.
  await clearPainted();
  await page.locator('select[aria-label="Clock"]').selectOption(zone);
  await settle(1800);
  // A scale nudge was tried here to force the repaint and had to come out: it
  // moved the view by a bar, so the crosshair below no longer landed on the
  // SAME bar in each zone and the offset comparisons drifted by 15 and 30
  // minutes. Clearing before the change is enough on its own, and it leaves the
  // view untouched - which the offset assertions depend on.
  await page.mouse.move(at.x, at.y - 60);
  await page.mouse.move(at.x, at.y);
  await settle(900);
  const strings = await painted();
  return {
    stamp: strings.map(parseStamp).filter(Boolean).at(-1),
    ticks: strings.filter((s) => /^\d{2}:\d{2}$/.test(s)),
    corner: await page.locator('[aria-label^="Time axis clock"]').textContent(),
    // The ribbon shares the chart's time scale and reads coordinates rather
    // than formatting times, so relabelling the axis must leave it exactly
    // where it was. Checked rather than assumed.
    ribbon: await page
      .locator('[role="img"][aria-label^="Cycle phase ribbon"]')
      .boundingBox(),
  };
};

// UTC IS READ LAST, and the order is the whole point. The app starts on UTC, so
// selecting UTC first sets the value it already had: React fires no change, the
// library repaints nothing, and the reader collects zero tick labels from a
// perfectly correct axis. It reported "0 ticks" that way, which then took the
// UTC-versus-WIB comparison down with it - a harness failure wearing an app
// failure's clothes, and the second time this file has produced one.
//
// Every read below now follows a zone that actually changed.
const asNy = await readZone("New York");
const asWib = await readZone("WIB");
const asUtc = await readZone("UTC");

for (const [zone, read, tag] of [
  ["UTC", asUtc, "UTC"],
  ["New York", asNy, "NY"],
  ["WIB", asWib, "WIB"],
]) {
  record(
    `the axis says which clock it is in on ${zone}`,
    read.stamp?.tag === tag,
    read.stamp ? read.stamp.text : "no crosshair stamp was painted",
  );
  record(`${zone} labels its ticks`, read.ticks.length > 0, `${read.ticks.length} ticks`);
  // Not only inside the picker: the reader looking at a time is looking at the
  // axis, and this is what tells them which clock it is without moving the eye.
  record(`the corner beside the axis says ${tag}`, read.corner === tag, `corner reads ${read.corner}`);
}

// The offsets themselves, off ONE instant. WIB is the fixed one and is the
// ground truth here: seven hours, all year, which is why it is the safe thing to
// assert exactly.
const delta = (a, b) => (((a.stamp.minutes - b.stamp.minutes) % 1440) + 2160) % 1440 - 720;
if (asUtc.stamp && asNy.stamp && asWib.stamp) {
  check("WIB is seven hours ahead of UTC on the same bar", delta(asWib, asUtc), 420);
  const ny = delta(asNy, asUtc);
  record(
    "New York is four or five hours behind UTC on the same bar",
    ny === -240 || ny === -300,
    `${ny / 60} hours, ${asNy.stamp.text} against ${asUtc.stamp.text}`,
  );
  record(
    "the three clocks are not the same clock",
    new Set([asUtc.stamp.minutes, asNy.stamp.minutes, asWib.stamp.minutes]).size === 3,
    `${asUtc.stamp.text} / ${asNy.stamp.text} / ${asWib.stamp.text}`,
  );
}

// The tick labels move with the stamp, which is the check that the AXIS itself
// was reformatted rather than only the crosshair. Subset rather than equality:
// which epochs get a tick is the library's decision and label widths feed into
// it, so a zone can legitimately end up with one mark fewer.
const shifted = new Set(
  asUtc.ticks.map((t) => {
    const [h, m] = t.split(":").map(Number);
    return `${String((h + 7) % 24).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  }),
);
const strays = asWib.ticks.filter((t) => !shifted.has(t));
record(
  "every WIB tick is a UTC tick plus seven hours",
  asWib.ticks.length > 0 && strays.length === 0,
  strays.length ? `unexplained: ${[...new Set(strays)].join(" ")}` : "",
);

const box3 = [asUtc.ribbon, asNy.ribbon, asWib.ribbon];
record(
  "the cycle ribbon stays where it was through all three clocks",
  box3.every((b) => b && b.height > 0) &&
    new Set(box3.map((b) => `${b.x},${b.y},${b.width},${b.height}`)).size === 1,
  box3.map((b) => (b ? `${b.width}x${b.height}@${b.x},${b.y}` : "missing")).join(" | "),
);

record(
  "no console errors while the clock was changed",
  consoleErrors.length === 0,
  consoleErrors[0] ?? "",
);

await page.screenshot({ path: `${OUT}/clock.png` });
writeFileSync(`${OUT}/clock.json`, JSON.stringify(results, null, 1));

const failed = results.filter((r) => !r.ok);
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail ? ` :: ${r.detail}` : ""}`);
}
console.log(`\n${results.length - failed.length}/${results.length} passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);
