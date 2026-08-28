/**
 * The 3-6-9 dial: does it draw, does it stay in its corner, does it leak.
 *
 *   npm run e2e:vortex
 *
 * THREE QUESTIONS, and the third is the one that needed a harness rather than a
 * unit test.
 *
 * 1. THE WIRE. Off by default, six rings and a 6x9 matrix when on, and `root`
 *    agreeing with the cell of `matrix` it claims to be. Two fields that can
 *    drift, and a dial that highlights one node while labelling it another is
 *    wrong in a way no screenshot would show.
 *
 * 2. THE PIXELS, measured as a DIFFERENCE rather than as an absolute. The dial
 *    is painted in the `grid` ink, which is also what the session shading and
 *    the weekend break markers use, so counting greyish pixels in the corner
 *    cannot tell whose they are. The same corner is therefore scanned twice,
 *    layer off and layer on, and the delta is the dial. That also makes the
 *    check survive a move: the dial can shift inside the corner and this still
 *    measures it, while it disappearing still fails.
 *
 *    The scan also asks where the paint ISN'T. A regression that stretched the
 *    dial across the pane would add pixels in the corner and pass a corner-only
 *    test, so the rest of the canvas is differenced too and has to stay quiet.
 *
 * 3. THE HEAP. `setDial` replaces one reference and `detached` nulls it, so
 *    there is nothing here that should accumulate - but "should" is what the
 *    claim would rest on without a number. The dial is toggled through repeated
 *    timeframe redraws, the heap is collected through CDP rather than hoped
 *    about, and the growth is REPORTED as bytes. A threshold with no printed
 *    figure behind it is an adjective.
 *
 * The dial also claims a label footprint, and a claim is exactly the kind of
 * thing that grows forever if the frame's reset ever stops running. The claim
 * count is differenced too.
 */
import { chromium } from "playwright";

const WEB = "http://127.0.0.1:3100/";
const API = "http://127.0.0.1:8100";

const results = [];
const check = (name, pass, detail = "") =>
  results.push({ name, pass, detail: String(detail) });

// ============================================================ THE WIRE
const draw = async (layers) => {
  const res = await fetch(`${API}/api/draw`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ symbol: "XAUUSD", interval: "1h", bars: 400, layers }),
  });
  if (!res.ok) throw new Error(`/api/draw ${res.status}: ${await res.text()}`);
  return res.json();
};

{
  const off = await draw(["supply_demand"]);
  check(
    "the dial is absent when its layer is off",
    off.drawing.vortex === null,
    JSON.stringify(off.drawing.vortex),
  );

  const on = await draw(["vortex"]);
  const dial = on.drawing.vortex;
  check("the dial arrives when its layer is on", dial !== null && dial !== undefined);

  if (dial) {
    check("six rings", dial.rings.length === 6, `${dial.rings.length}`);
    check("nine sectors", dial.sectors === 9, `${dial.sectors}`);
    check(
      "the lit set is 3, 6 and 9 and nothing else",
      JSON.stringify(dial.lit) === "[3,6,9]",
      JSON.stringify(dial.lit),
    );
    check(
      "the matrix is six rows of nine",
      dial.matrix.length === 6 && dial.matrix.every((r) => r.length === 9),
      dial.matrix.map((r) => r.length).join(","),
    );

    // Every cell is a digital root, so 1..9 and nothing outside.
    const outside = dial.matrix.flat().filter((v) => v < 1 || v > 9);
    check("every cell is a digital root", outside.length === 0, outside.join(","));

    // The claim the module docstring makes, checked on the wire: a cell is lit
    // exactly when 3 divides r * k. Rings 3 and 6 light everywhere, the rest at
    // k = 3, 6, 9.
    let wrongRings = [];
    dial.rings.forEach((ring, row) => {
      const litAt = dial.matrix[row]
        .map((v, i) => (dial.lit.includes(v) ? i + 1 : 0))
        .filter(Boolean);
      const want = ring.r % 3 === 0 ? [1, 2, 3, 4, 5, 6, 7, 8, 9] : [3, 6, 9];
      if (JSON.stringify(litAt) !== JSON.stringify(want)) {
        wrongRings.push(`${ring.label}:${litAt.join("/")}`);
      }
    });
    check(
      "lit cells are exactly the multiples of three",
      wrongRings.length === 0,
      wrongRings.join(" "),
    );

    const mismatched = dial.rings
      .map((r, row) => (r.root === dial.matrix[row][r.sector - 1] ? null : r.id))
      .filter(Boolean);
    check(
      "each ring's live root agrees with its own matrix cell",
      mismatched.length === 0,
      mismatched.join(","),
    );

    const badSpan = dial.rings.filter((r) => !(r.cycle_start < r.cycle_end));
    check(
      "every ring's cycle actually spans forward",
      badSpan.length === 0,
      badSpan.map((r) => r.id).join(","),
    );

    // NO PRICE ANYWHERE IN THE PAYLOAD. The dial's whole licence to exist is
    // that it carries none, so the wire is searched for one rather than
    // trusted to have none. Every number here is a sector, a root, a ring
    // index or an epoch.
    const epochish = (v) => v > 1_000_000_000 && v < 4_000_000_000;
    const suspicious = dial.rings.flatMap((r) =>
      [
        ["sector", r.sector, r.sector >= 1 && r.sector <= 9],
        ["root", r.root, r.root >= 1 && r.root <= 9],
        ["r", r.r, r.r >= 1 && r.r <= 6],
        ["cycle_start", r.cycle_start, epochish(r.cycle_start)],
        ["cycle_end", r.cycle_end, epochish(r.cycle_end)],
      ]
        .filter(([, , ok]) => !ok)
        .map(([f, v]) => `${r.id}.${f}=${v}`),
    );
    check(
      "no field on the wire is outside its own range",
      suspicious.length === 0,
      suspicious.join(" "),
    );
  }
}

// ============================================================ BROWSER
// deviceScaleFactor 1 so CSS pixels and bitmap pixels are the same number, the
// rule the other pixel harnesses in this directory follow.
const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({
  viewport: { width: 1680, height: 1100 },
  deviceScaleFactor: 1,
});
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(e.message));

// CANVAS CONTEXT LOSS, watched from before the first canvas exists. Installed
// as an init script rather than after load because the chart builds its
// canvases during hydration, and a listener attached afterwards would miss a
// loss that happened while it was being attached. The observer picks up
// canvases the library adds later too.
await page.addInitScript(() => {
  window.__ctxLost = [];
  const attach = (c) => {
    if (c.__zlWatched) return;
    c.__zlWatched = true;
    c.addEventListener("contextlost", () => window.__ctxLost.push("2d contextlost"));
    c.addEventListener("webglcontextlost", () => window.__ctxLost.push("webgl contextlost"));
  };
  const sweep = () => document.querySelectorAll("canvas").forEach(attach);
  // OBSERVE `document`, not `document.documentElement`. An init script runs at
  // document_start, where `documentElement` is still null and `observe` throws
  // "parameter 1 is not of type Node" - which this harness then recorded as a
  // page error and blamed on the app. `document` is a Node from the beginning
  // and subtree:true reaches every canvas added under it.
  new MutationObserver(sweep).observe(document, { childList: true, subtree: true });
  sweep();
});

try {
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll('[role="status"]')].some((el) =>
        /\d+ bars/.test(el.textContent ?? ""),
      ),
    { timeout: 90_000 },
  );

  // The toggle is found by its REGISTRY label, so a rename in `app/layers.py`
  // moves this harness with it instead of leaving it clicking nothing.
  const label = await page.evaluate(async () => {
    const cfg = await (await fetch("http://127.0.0.1:8100/api/config")).json();
    return cfg.layers.find((l) => l.id === "vortex")?.label ?? null;
  });
  check("the dial has a registry label to switch on", label !== null, `${label}`);
  const toggle = page.getByRole("switch", { name: label, exact: true });
  check("the toggle exists in the toolbox", (await toggle.count()) === 1);

  /** Painted pixels inside the bottom-left corner, and outside it, on the
   *  busiest canvas. Counted the same way both times so the two are
   *  subtractable. */
  const scan = () =>
    page.evaluate(() => {
      const canvases = [...document.querySelectorAll("canvas")];
      let best = null;
      for (const c of canvases) {
        if (!c.width || !c.height) continue;
        const ctx = c.getContext("2d", { willReadFrequently: true });
        const img = ctx.getImageData(0, 0, c.width, c.height);
        const d = img.data;
        let painted = 0;
        for (let i = 0; i < d.length; i += 4 * 40) {
          if (d[i + 3] < 250) continue;
          if (Math.abs(d[i] - 11) + Math.abs(d[i + 1] - 13) + Math.abs(d[i + 2] - 16) > 12)
            painted++;
        }
        if (!best || painted > best.painted) best = { img, painted };
      }
      if (!best) return null;

      const { img } = best;
      const W = img.width;
      const H = img.height;
      // The corner the dial is anchored to: left third, bottom 40%. Wider than
      // the dial on purpose, so the measurement survives the dial moving inside
      // its corner and only fails if it stops drawing.
      const cornerW = Math.round(W / 3);
      const cornerTop = Math.round(H * 0.6);

      // `grid` ink is rgb(95,105,117): neutral, and blue above red. Composited
      // on the #0b0d10 page at any alpha it keeps b > r and stays neutral, which
      // is what separates it from a demand-green or supply-salmon candle.
      const isGrey = (r, g, b) =>
        b > r && b - r < 46 && g >= r && g <= b + 4 && r > 18 && r < 200;

      let corner = 0;
      let elsewhere = 0;
      const d = img.data;
      for (let y = 0; y < H; y += 2) {
        for (let x = 0; x < W; x += 2) {
          const i = (y * W + x) * 4;
          if (d[i + 3] < 250) continue;
          if (!isGrey(d[i], d[i + 1], d[i + 2])) continue;
          if (x < cornerW && y > cornerTop) corner++;
          else elsewhere++;
        }
      }
      return { corner, elsewhere, W, H };
    });

  const claimCount = () =>
    page.evaluate(() => window.__zonelabChart?.labels?.().length ?? -1);

  const isOn = async () => (await toggle.getAttribute("aria-checked")) === "true";
  const setLayer = async (want) => {
    if ((await isOn()) !== want) await toggle.click();
    await page.waitForTimeout(1400);
  };

  await setLayer(false);
  const before = await scan();
  const claimsOff = await claimCount();
  await setLayer(true);
  const after = await scan();
  const claimsOn = await claimCount();

  check("both scans read a canvas", before !== null && after !== null);

  if (before && after) {
    const gained = after.corner - before.corner;
    const spilled = after.elsewhere - before.elsewhere;
    // The dial is roughly 230 CSS px across at this viewport, sampled every
    // second pixel in both axes, and it is rings, spokes, nodes and a caption -
    // hundreds of samples, not thousands. 150 is a floor that a blank corner
    // cannot reach and a drawn dial clears easily.
    check(
      "the dial paints in the bottom-left corner",
      gained > 150,
      `corner ${before.corner} -> ${after.corner} (+${gained})`,
    );
    // The rest of the canvas may move a little: turning a layer on re-fits the
    // price scale, so candles shift by a pixel or two. What it must not do is
    // gain dial-sized paint, which is what a pane-wide mandala regression looks
    // like.
    check(
      "the dial stays in its corner and does not cover the pane",
      spilled < gained,
      `elsewhere ${before.elsewhere} -> ${after.elsewhere} (${spilled >= 0 ? "+" : ""}${spilled}), corner +${gained}`,
    );
  }

  // The dial claims a label footprint so no caption prints across the rings.
  // One rectangle, not one per frame: if the frame's reset ever stopped running
  // this would climb without limit, which is the leak a heap number alone would
  // not name.
  check(
    "the dial claims exactly one label rectangle",
    claimsOn - claimsOff === 1,
    `claims ${claimsOff} -> ${claimsOn}`,
  );

  // ---------------------------------------------------------------- HEAP
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Performance.enable");
  const heap = async () => {
    await cdp.send("HeapProfiler.enable");
    await cdp.send("HeapProfiler.collectGarbage");
    const { metrics } = await cdp.send("Performance.getMetrics");
    return metrics.find((m) => m.name === "JSHeapUsedSize")?.value ?? 0;
  };

  const intervalButton = async (name) => {
    const b = page.getByRole("button", { name, exact: true });
    if ((await b.count()) === 1) {
      await b.click();
      await page.waitForTimeout(1200);
      return true;
    }
    return false;
  };

  // Warm up first: the first few redraws allocate caches that never come back,
  // and counting those as a leak would make any threshold meaningless.
  for (const tf of ["4h", "1h"]) await intervalButton(tf);
  await setLayer(true);
  await setLayer(false);
  const baseline = await heap();

  const CYCLES = 8;
  let redraws = 0;
  for (let i = 0; i < CYCLES; i += 1) {
    await setLayer(true);
    if (await intervalButton(i % 2 === 0 ? "4h" : "1h")) redraws += 1;
    await setLayer(false);
    if (await intervalButton(i % 2 === 0 ? "1h" : "4h")) redraws += 1;
  }
  const ended = await heap();
  const growthMB = (ended - baseline) / (1024 * 1024);

  check(
    "toggling the dial across timeframe redraws does not grow the heap",
    growthMB < 4,
    `${CYCLES} on/off cycles, ${redraws} redraws, heap ${(baseline / 1048576).toFixed(2)} -> ${(ended / 1048576).toFixed(2)} MB (${growthMB >= 0 ? "+" : ""}${growthMB.toFixed(2)} MB)`,
  );

  // And the claim list must still be one rectangle after all of that, not N.
  await setLayer(true);
  const claimsEnd = await claimCount();
  check(
    "the claim count is unchanged after the cycles",
    claimsEnd - claimsOff === 1,
    `claims ${claimsOff} -> ${claimsEnd}`,
  );

  check("no page error", pageErrors.length === 0, pageErrors.join(" | "));
  check(
    "no canvas context was lost",
    (await page.evaluate(() => window.__ctxLost.length)) === 0,
    (await page.evaluate(() => window.__ctxLost.join(", "))) || "none",
  );

  // ======================================================== THE STORM
  // Opt-in, because it takes minutes and the checks above are the ones worth
  // running on every change.
  if (process.argv.includes("--storm")) {
    const TIMEFRAMES = ["15m", "1h", "4h", "1d"];
    const CYCLES = 50;
    // TWO PHASES PER CYCLE, because the two things being asked for pull in
    // opposite directions.
    //
    // BURST is the storm proper: clicks faster than the app can answer, so
    // every draw is aborted by the next one. That is the path that once left
    // the worker burning 5.33 seconds of CPU per 5 seconds after every client
    // had given up, and it is where a crash or a lost context would surface.
    //
    // SETTLE exists because burst alone proved nothing about the dial. Measured
    // on this machine: at 120 ms between clicks `setDial` fired ZERO times
    // across 100 toggles, because no /api/draw round trip ever completed while
    // the layer was on. The harness passed 27 of 27 without the dial ever
    // reaching the canvas. So each cycle ends with a dwell long enough for a
    // payload to land, and a sample every tenth cycle has to SEE it.
    const BURST_MS = 120;
    const SETTLE_MS = 1300;

    /** One pass of the storm. `withDial` false is the CONTROL: the same
     *  timeframe churn with the layer never switched on.
     *
     *  THE CONTROL IS THE POINT. "The heap grew 1.4 MB after 50 cycles" says
     *  nothing about the dial on its own - a Next.js page under 50 redraws
     *  allocates caches, route data and canvas buffers whatever is switched on.
     *  Only the DIFFERENCE between the two passes is attributable, and this
     *  harness already learned that lesson once today: the backend health probe
     *  read 259 ms until it was moved off the loop generating the load. */
    /** Corner paint right now, so the storm can PROVE the dial was live. */
    const cornerNow = async () => (await scan())?.corner ?? -1;

    const storm = async (withDial) => {
      await setLayer(false);
      await page.evaluate(() => {
        window.__ctxLost.length = 0;
      });
      const dark = await cornerNow();
      const errorsBefore = pageErrors.length;
      const before = await heap();
      const started = Date.now();
      let clicks = 0;
      let sampled = 0;
      let dialSeen = 0;
      const samples = [];

      for (let i = 0; i < CYCLES; i += 1) {
        // ---- burst: faster than the app can answer ----------------------
        for (const tf of [TIMEFRAMES[i % 4], TIMEFRAMES[(i + 2) % 4]]) {
          if (withDial) {
            await toggle.click();
            clicks += 1;
          }
          await page.getByRole("button", { name: tf, exact: true }).click();
          clicks += 1;
          await page.waitForTimeout(BURST_MS);
        }

        // ---- settle: long enough for a draw to land ---------------------
        if (withDial && (await toggle.getAttribute("aria-checked")) === "false") {
          await toggle.click();
          clicks += 1;
        }
        await page.waitForTimeout(SETTLE_MS);
        if (withDial && i % 10 === 0) {
          // PAIRED, AND ON THE SAME TIMEFRAME. The first version compared each
          // sample against one `dark` reading taken before the pass, and that
          // is invalid: the corner's grey count moves with the candles, so the
          // baseline came from one timeframe and the samples from three others.
          // It read dark 3434 against lit 3572/2777/3572/2777/3572 and scored
          // zero - not because the dial was absent, but because the comparison
          // crossed a variable nobody was controlling for. Off and on are now
          // read back to back without touching anything else.
          sampled += 1;
          const lit = await cornerNow();
          await toggle.click();
          clicks += 1;
          await page.waitForTimeout(SETTLE_MS);
          const off = await cornerNow();
          await toggle.click();
          clicks += 1;
          await page.waitForTimeout(SETTLE_MS);
          samples.push(`${off}+${lit - off}`);
          if (lit - off > 150) dialSeen += 1;
        }
        if (withDial) {
          await toggle.click();
          clicks += 1;
          await page.waitForTimeout(BURST_MS);
        }
      }

      // Let the last redraws land before collecting, or the reading counts work
      // still in flight as retained.
      await page.waitForTimeout(3000);
      const after = await heap();
      return {
        clicks,
        sampled,
        dialSeen,
        dark,
        samples,
        seconds: (Date.now() - started) / 1000,
        mb: (after - before) / (1024 * 1024),
        before,
        after,
        errors: pageErrors.length - errorsBefore,
        lost: await page.evaluate(() => window.__ctxLost.length),
      };
    };

    const control = await storm(false);
    const withDial = await storm(true);
    const attributable = withDial.mb - control.mb;

    check(
      "the control storm survives without errors",
      control.errors === 0 && control.lost === 0,
      `${control.clicks} clicks in ${control.seconds.toFixed(0)}s, ${control.mb >= 0 ? "+" : ""}${control.mb.toFixed(2)} MB`,
    );
    check(
      "the storm actually rendered the dial rather than out-racing it",
      withDial.dialSeen >= Math.ceil(withDial.sampled * 0.6),
      `dial visible on ${withDial.dialSeen} of ${withDial.sampled} paired samples (off+gain): ${withDial.samples.join(", ")}`,
    );
    check(
      "50 dial toggles across 50 redraws raise no page error",
      withDial.errors === 0,
      `${withDial.clicks} clicks in ${withDial.seconds.toFixed(0)}s`,
    );
    check(
      "no canvas context is lost during the storm",
      withDial.lost === 0,
      `${withDial.lost} events`,
    );
    check(
      "heap growth attributable to the dial stays under 2 MB",
      attributable < 2,
      `dial storm ${withDial.mb >= 0 ? "+" : ""}${withDial.mb.toFixed(2)} MB, control ${control.mb >= 0 ? "+" : ""}${control.mb.toFixed(2)} MB, attributable ${attributable >= 0 ? "+" : ""}${attributable.toFixed(2)} MB`,
    );
    check(
      "the whole dial storm stays under 2 MB on its own too",
      withDial.mb < 2,
      `${(withDial.before / 1048576).toFixed(2)} -> ${(withDial.after / 1048576).toFixed(2)} MB`,
    );
    check(
      "the claim list is still one rectangle after the storm",
      (await (async () => {
        await setLayer(true);
        return claimCount();
      })()) - claimsOff === 1,
    );
  }
} finally {
  await browser.close();
}

// ============================================================ REPORT
const failed = results.filter((r) => !r.pass);
for (const r of results) {
  console.log(`${r.pass ? "PASS" : "FAIL"}  ${r.name}${r.detail ? ` :: ${r.detail}` : ""}`);
}
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
