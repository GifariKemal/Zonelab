/**
 * The quarter ribbon's PATH LABELS, asserted against the degrees they name.
 *
 *   node e2e/ribbon.mjs [screenshot-dir]
 *
 * Daye's quarterly theory names a quarter by its whole path - not "Q1" but "the
 * Q1 of the Q3 of the Q3", written 3-3-1. The failure this guards is the one a
 * screenshot cannot catch: a path with the right SHAPE and the wrong degrees.
 * Drop one ancestor and 3-3-1 still reads as a valid label, still lines up under
 * its neighbours, and now says month-week-day where it means month-day-session.
 * Nothing about the picture would look wrong.
 *
 * So the assertions are about structure, not pixels:
 *
 *   - the root row, whichever degree is coarsest on screen, stays a bare Q3
 *   - each row below it carries exactly one more component than the row above
 *   - a child's path is its parent's path plus one digit, for the parent that
 *     actually contains it in time
 *
 * Canvas has no DOM to read, so this goes through `window.__zonelabRibbon`, the
 * same dev-only seam pattern `e2e/zone-audit.mjs` uses on the chart.
 */
import { chromium } from "playwright";

const SHOTS = process.argv[2] ?? ".playwright-shots";
const URL = "http://127.0.0.1:3100/";
const DEGREES = ["month", "week", "day"];

const results = [];
const check = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1680, height: 1000 } });
page.on("pageerror", (e) => check("no page error", false, e.message));

// The ribbon degrees are a params block, and driving the layer menu to set them
// would test the menu rather than the labels. Patched on the way out instead.
await page.addInitScript((degrees) => {
  const real = window.fetch;
  window.fetch = (url, init) => {
    if (typeof url === "string" && url.includes("/api/draw") && init?.body) {
      const body = JSON.parse(init.body);
      body.layers = [...new Set([...(body.layers ?? []), "session"])];
      body.session = { ...(body.session ?? {}), quarters: degrees, max_quarters: 0 };
      init = { ...init, body: JSON.stringify(body) };
    }
    return real(url, init);
  };
}, DEGREES);

await page.goto(URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => /\d+ bars/.test(document.body.innerText), {
  timeout: 60_000,
});
await page.waitForFunction(() => window.__zonelabRibbon?.hierarchy?.length > 1, {
  timeout: 30_000,
});

// HIERARCHY order, coarsest first. The rows are PAINTED in the opposite order -
// finest at the top, the toodegrees layout - and the two must not be confused:
// every assertion below is about the path hierarchy, none is about which row
// sits where on screen.
const { paths, hierarchy: degrees } = await page.evaluate(() => window.__zonelabRibbon);

check("more than one degree is on the ribbon", degrees.length > 1, degrees.join(","));

// The seam must stay in hierarchy order even though the panel is drawn upside
// down relative to it. If a future edit reverses this too, every path assertion
// below would still pass while naming the degrees backwards - so the direction
// is pinned here rather than inferred.
const RANK = ["year", "month", "week", "day", "session", "micro", "nano"];
check(
  "the seam is coarsest-first, not paint order",
  degrees.every((d, i) => i === 0 || RANK.indexOf(degrees[i - 1]) < RANK.indexOf(d)),
  degrees.join(" > "),
);

// Keys are `<degree>@<time_from>`, which is enough to check every structural
// claim without needing the quarter objects themselves.
const byDegree = new Map(degrees.map((d) => [d, []]));
for (const [key, path] of Object.entries(paths)) {
  const [degree, from] = key.split("@");
  byDegree.get(degree)?.push({ from: Number(from), path });
}

const root = degrees[0];
check(
  `the root row (${root}) carries no path`,
  !byDegree.get(root)?.length,
  `${byDegree.get(root)?.length ?? 0} path labels found on it`,
);

degrees.slice(1).forEach((degree, i) => {
  const rows = byDegree.get(degree) ?? [];
  const want = i + 2; // root is 1 component and gets no entry, so depth 1 is 2
  const wrong = rows.filter((r) => r.path.split("-").length !== want);
  check(
    `${degree} paths have ${want} components`,
    rows.length > 0 && wrong.length === 0,
    rows.length === 0
      ? "no quarters at this degree"
      : `${wrong.length} wrong, e.g. ${wrong[0]?.path ?? "-"} (sample ${rows[0].path})`,
  );
  // Every component must be a quarter index, never a stray character.
  const bad = rows.filter((r) => !/^[1-4](-[1-4])*$/.test(r.path));
  check(`${degree} paths are quarter indices only`, bad.length === 0, bad[0]?.path ?? "");
});

// THE ONE THAT MATTERS: a child's path must extend its own container's, not
// some neighbour's. Checked by prefix against the coarser row, using the time
// each label is keyed by.
degrees.slice(2).forEach((degree, i) => {
  const parentDegree = degrees[i + 1];
  const parents = (byDegree.get(parentDegree) ?? []).sort((a, b) => a.from - b.from);
  const rows = byDegree.get(degree) ?? [];
  let mismatched = 0;
  let example = "";
  for (const row of rows) {
    // The parent containing this child is the newest one that started no later.
    let holder = null;
    for (const p of parents) if (p.from <= row.from) holder = p;
    if (!holder) continue;
    if (!row.path.startsWith(`${holder.path}-`)) {
      mismatched += 1;
      example ||= `${degree} ${row.path} under ${parentDegree} ${holder.path}`;
    }
  }
  check(
    `${degree} paths extend the ${parentDegree} quarter that contains them`,
    mismatched === 0,
    example,
  );
});

await page.screenshot({ path: `${SHOTS}/ribbon.png` });
await browser.close();

console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL"));
if (failed.length) {
  console.log(`\n${failed.length} of ${results.length} checks failed`);
  process.exit(1);
}
console.log(`\nall ${results.length} checks passed`);
