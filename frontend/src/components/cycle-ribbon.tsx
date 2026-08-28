"use client";

import { useEffect, useMemo, useRef } from "react";
import type { IChartApi, Time } from "lightweight-charts";

import { DEGREES, type SessionQuarter } from "@/lib/types";
import { ink } from "./ink";

/**
 * The quarter ribbon, in its own strip beneath the chart.
 *
 * TAKEN DIRECTLY FROM THE OWNER'S OWN DIAGRAM, not designed here. Image 21 in
 * `Referensi grup dan Bg Nas` is a teaching diagram he drew himself, and the middle of it is
 * exactly this object: a full-width horizontal band split into phases, dusty red
 * for manipulation and sage green for distribution, with a SECOND smaller band
 * nested above it labelled "LTF nested" to show the fractal. His notes name the
 * nesting as seven levels - Yearly, Monthly, Weekly, Daily, 90M, Micro, Nano -
 * and describe it as a panel below the chart. So: one row per degree, and the
 * nesting is read vertically.
 *
 * ROWS RUN FINEST AT THE TOP, coarsest at the bottom. That is the toodegrees
 * layout, asked for explicitly on 2026-08-19, and it REPLACES the
 * outermost-at-top order this file shipped with - which came from his own
 * teaching diagram, so the change is a preference overriding a source, not a
 * correction of one. Worth knowing which way round it is before reading any
 * screenshot taken before that date.
 *
 * THE PAINT ORDER IS NOT THE HIERARCHY. `quarterPaths` still walks coarsest to
 * finest, because a path's root is the coarsest degree on the ribbon no matter
 * which end of the panel its row sits at. Reversing one and not the other is
 * the whole trick: flipping the hierarchy too would silently relabel every
 * quarter, and 3-3-1 would still look like a valid path while naming the
 * degrees backwards.
 *
 * WHY IT IS A SEPARATE STRIP AND NOT AN OVERLAY. This project reserves green and
 * red for exactly one meaning on the price canvas: demand and supply. His phase
 * colours are also green and red and mean something else entirely. Painting them
 * over the candles would put two incompatible colour languages on one surface -
 * so the ribbon lives below the chart, where there is no zone to confuse it with,
 * which is also where he puts it. The separation is what makes adopting his
 * palette safe rather than reckless.
 *
 * THE ROLES ARE POSITIONAL, AND THAT IS NOT THE SAME AS THE PROFILE. Q1
 * accumulation, Q2 manipulation, Q3 distribution, Q4 continuation or reversal is
 * a statement about a quarter's POSITION in its cycle - it is true by definition
 * and knowable from the clock alone. The engine also computes an OBSERVED profile
 * (AMDX or XAMD) which says where the manipulation actually fell, and under XAMD
 * it falls somewhere else. They disagree, routinely. This strip shows the
 * positional reading only, and the checklist panel shows the observed one; a
 * reader who takes this ribbon for a measurement has been misled by the layout.
 *
 * AND NOTHING HERE IS A FORECAST. "Q2 is the manipulation quarter" is a label on
 * a clock, not a claim that price will manipulate. Twelve pre-registered
 * directional hypotheses have failed in this project.
 */

/** His four, in his words. Q4 carries TWO readings in his own notes and neither
 *  is marked as the primary, so both are kept and the tooltip says so rather
 *  than the label silently picking one. */
const ROLE: Record<string, { short: string; full: string; ink: string }> = {
  Q1: { short: "ACC", full: "accumulation", ink: "168, 162, 148" },
  Q2: { short: "MAN", full: "manipulation", ink: "192, 138, 130" },
  Q3: { short: "DIS", full: "distribution", ink: "156, 184, 156" },
  Q4: { short: "CON", full: "continuation or reversal", ink: "134, 152, 176" },
};

/** Row labels. `session` is 90 minutes and he calls it 90M, so the ribbon uses
 *  his name rather than the code's - the engine's word for it is an internal
 *  detail and this strip is read by him. */
const ROW: Record<string, string> = {
  year: "YEARLY",
  month: "MONTHLY",
  week: "WEEKLY",
  day: "DAILY",
  session: "90M",
  micro: "MICRO",
  nano: "NANO",
};

/** Each quarter's position spelled as its full path through the degrees, which
 *  is how Daye's quarterly theory names one: not "Q1" but "the Q1 of the Q3 of
 *  the Q3", written 3-3-1.
 *
 *  THE ROOT IS THE COARSEST DEGREE ACTUALLY DRAWN, not a fixed depth. Turning on
 *  the yearly row therefore lengthens every label below it by one component, and
 *  that is correct rather than unfortunate: the path is only meaningful relative
 *  to a stated root, so the row at the top IS the statement. That row keeps a
 *  bare Q3, because a path from itself to itself is one component.
 *
 *  A MISSING ANCESTOR PRODUCES NO PATH AT ALL. The window can open mid-cycle, so
 *  a quarter can be on screen while the quarter that contains it is not in the
 *  data. Emitting the components that were found would silently close the gap
 *  and shift every remaining digit one degree - 3-3-1 would be read as month,
 *  week, day when it was really month, day, session. That is a wrong label
 *  wearing a right one's shape, so the segment falls back to its bare `Q1`,
 *  which is true at every depth. */
function quarterPaths(quarters: SessionQuarter[]): Map<string, string> {
  const key = (q: SessionQuarter) => `${q.degree}@${q.time_from}`;
  const present = DEGREES.filter((d) => quarters.some((q) => q.degree === d));
  const byDegree = new Map(
    present.map((d) => [d, quarters.filter((q) => q.degree === d)]),
  );

  const paths = new Map<string, string>();
  present.forEach((degree, depth) => {
    // The root row is skipped so it keeps its `Q3` rather than becoming a bare
    // `3`. Both say the same thing, and the Q is what makes a one-component
    // label readable as a quarter instead of as a truncated path.
    if (depth === 0) return;
    for (const q of byDegree.get(degree) ?? []) {
      const parts: string[] = [];
      for (const above of present.slice(0, depth)) {
        const ancestor = (byDegree.get(above) ?? []).find(
          (a) => a.time_from <= q.time_from && q.time_from < a.time_to,
        );
        if (!ancestor) {
          parts.length = 0;
          break;
        }
        parts.push(ancestor.label[1]);
      }
      // Length check, not a truthiness one: the root row has depth 0, so its
      // `parts` is legitimately empty and it must still get a label.
      if (parts.length === depth) paths.set(key(q), [...parts, q.label[1]].join("-"));
    }
  });
  return paths;
}

/** Hierarchy order (coarsest first) turned into PAINT order (finest first).
 *
 *  One function rather than a `.reverse()` at each of the three call sites,
 *  because the two orders are not interchangeable and a bare reverse does not
 *  say which one it is producing. `quarterPaths` must never see this. */
function rowOrder<T>(hierarchy: readonly T[]): T[] {
  return [...hierarchy].reverse();
}

const ROW_H = 18;
const GUTTER = 52;
/** Below this, a row stops being a ribbon and becomes a smear. Seven days of
 *  micro quarters is 672 segments across about a thousand pixels, and drawing
 *  them produces alternating noise that LOOKS like detail while carrying none -
 *  the same failure the zone ink budget already measured on the price canvas,
 *  where past about a third coverage the boxes stop annotating and become the
 *  background. A row under the threshold says how many it is hiding instead.
 *
 *  10, not 4. The first attempt used 4 and the screenshot settled it: micro
 *  quarters came out about 8.8 pixels wide, cleared that bar, and painted a flat
 *  band in which no boundary could be seen at all. Four adjacent phase colours
 *  at similar luminance need roughly ten pixels each before the eye reads them
 *  as separate. Measured off the rendering, not chosen from taste. */
const READABLE_PX = 10;

export function CycleRibbon({
  chart,
  quarters,
  now,
}: {
  chart: IChartApi | null;
  quarters: SessionQuarter[];
  /** Open time of the newest bar, so the live quarter at each degree can be
   *  marked. Without it every quarter looks equally current, which is the one
   *  thing this strip is meant to answer at a glance. */
  now: number | null;
}) {
  const host = useRef<HTMLCanvasElement>(null);
  // Held in a ref so the paint callback can read the latest data without the
  // effect re-subscribing on every render. Written in an effect rather than in
  // the render body: React may discard a render, and a ref assigned during one
  // would then hold a value from a pass that never happened. No dependency
  // array, so it runs on every commit - the same rule chart.tsx follows.
  // Derived once per data change, NOT inside `paint`. Paint fires on every
  // scroll and every zoom, and the path walk is a containment search per
  // quarter per degree above it - cheap once, wasteful sixty times a second.
  const paths = useMemo(() => quarterPaths(quarters), [quarters]);

  const data = useRef({ quarters, now, paths });
  useEffect(() => {
    data.current = { quarters, now, paths };
    if (process.env.NODE_ENV !== "production") {
      // Test seam, the same dev-only pattern and the same reason as
      // `__zonelabChart` in chart.tsx: the labels are painted to a canvas, so
      // there is no DOM for a driver to read them out of, and the one thing
      // worth asserting about a path label - that its components name the right
      // degrees - is invisible to a pixel harness. See `e2e/ribbon.mjs`.
      (window as unknown as Record<string, unknown>).__zonelabRibbon = {
        paths: Object.fromEntries(paths),
        // HIERARCHY order, coarsest first - deliberately not the paint order.
        // The path root is `hierarchy[0]`, and that stays true after the rows
        // were flipped to finest-at-top, which is exactly why this is not
        // called `degrees`: a driver reading rows off the screen and a driver
        // reading path components need opposite orders.
        hierarchy: DEGREES.filter((d) => quarters.some((q) => q.degree === d)),
      };
    }
  });

  const rows = rowOrder(DEGREES.filter((d) => quarters.some((q) => q.degree === d)));

  useEffect(() => {
    const canvas = host.current;
    if (!canvas || !chart) return;

    const paint = () => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (canvas.width !== width * ratio || canvas.height !== height * ratio) {
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
      }
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.font = "9px ui-monospace, monospace";
      ctx.textBaseline = "middle";

      const scale = chart.timeScale();
      const { quarters: qs, now: at, paths } = data.current;
      // Painted finest-first. `paths` was already computed against the
      // hierarchy, so reversing here moves the rows and nothing else.
      const present = rowOrder(DEGREES.filter((d) => qs.some((q) => q.degree === d)));

      present.forEach((degree, row) => {
        const y = row * ROW_H;

        ctx.fillStyle = "rgba(124, 134, 148, 0.75)";
        ctx.fillText(ROW[degree] ?? degree.toUpperCase(), 4, y + ROW_H / 2);

        // Resolve every segment BEFORE drawing any of it, because a row can fail
        // in two different ways and they need different answers.
        //
        // FAILURE ONE, AND IT IS NOT A ZOOM PROBLEM. The chart's x axis is
        // indexed by BAR, not by time, so `timeToCoordinate` answers only for
        // times that are actually bars. A micro quarter is 1350 seconds and a 15m
        // bar is 900, so micro boundaries land between bars and simply have no
        // position on this axis. The first version of this row clamped an
        // unresolved edge to the panel edge, which painted every one of those
        // quarters across the full width and stacked them into a solid wash - a
        // row that looked like dense data and was pure artefact. A boundary with
        // no coordinate is not drawn, and the row says how many it lost, because
        // "this grid is not addressable on this timeframe" is a fact worth
        // reading rather than a smear to squint at.
        const mine = qs.filter((q) => q.degree === degree);
        const boxes: { q: SessionQuarter; left: number; right: number }[] = [];
        for (const q of mine) {
          const a = scale.timeToCoordinate(q.time_from as Time);
          if (a === null) continue;
          const b = scale.timeToCoordinate(q.time_to as Time);
          // The one clamp that survives, and only for the quarter that is still
          // running: its close is in the future, so it has no bar by definition.
          const right = b ?? (at !== null && q.time_to > at ? width : null);
          if (right === null) continue;
          // Off-screen quarters are DROPPED, not clamped, and the order of these
          // two steps is the bug this line fixes. Clamping first turned every
          // quarter left of the viewport into a sliver pinned to the gutter, and
          // those slivers then dominated the median width - so a daily row of
          // eight perfectly readable segments reported itself "too dense to
          // read" because thirteen invisible ones had been measured alongside
          // them. Measure what is on screen, clamp only what will be painted.
          if (right < GUTTER || a > width) continue;
          boxes.push({ q, left: Math.max(a, GUTTER), right: Math.min(right, width) });
        }

        const lost = mine.length - boxes.length;
        if (!boxes.length) {
          ctx.fillStyle = "rgba(124, 134, 148, 0.8)";
          ctx.fillText(
            `${mine.length} quarters, none of them land on a bar of this timeframe`,
            GUTTER + 5,
            y + ROW_H / 2,
          );
          return;
        }

        // FAILURE TWO, which IS a zoom problem: everything resolved and the
        // segments are too narrow to tell apart.
        const spans = boxes.map((b) => b.right - b.left).sort((a, b) => a - b);
        const median = spans[Math.floor(spans.length / 2)];
        if (median < READABLE_PX) {
          ctx.fillStyle = ink("grid", 0.12);
          ctx.fillRect(GUTTER, y + 1, width - GUTTER, ROW_H - 3);
          ctx.fillStyle = "rgba(124, 134, 148, 0.8)";
          ctx.fillText(
            `${boxes.length} quarters, too dense to read at this zoom`,
            GUTTER + 5,
            y + ROW_H / 2,
          );
          return;
        }
        // Measured off the row's OWN WIDEST label, not off a fixed "Q4 CON".
        // Path labels grow one component per degree, so the deepest row can
        // carry "3-3-3-1 CON" where the top row carries "Q3 DIS" - a constant
        // string would have decided the narrow rows by the width of the wide
        // ones. Still decided once per row, never per segment: that is the
        // ragged-mix bug the comment below records.
        const tagOf = (q: SessionQuarter) =>
          `${paths.get(`${q.degree}@${q.time_from}`) ?? q.label} ${ROLE[q.label].short}`;
        const widest = Math.max(...boxes.map((b) => ctx.measureText(tagOf(b.q)).width));
        const labelled = median > widest + 10;

        for (const { q, left, right } of boxes) {
          if (right - left < 1) continue;
          const role = ROLE[q.label];
          const live = at !== null && q.time_from <= at && at < q.time_to;
          ctx.fillStyle = `rgba(${role.ink}, ${live ? 0.62 : 0.26})`;
          ctx.fillRect(left, y + 1, right - left - 1, ROW_H - 3);

          // The label is the only thing that types the segment. Colour cannot:
          // his own charts use the same colour for different objects, which is
          // why every drawing in this app is read by its label.
          // Labelled or not is decided ONCE PER ROW, from the median segment,
          // never per segment. Deciding it per segment produced the ragged mix
          // in the first screenshot: a few wide quarters carried text while
          // their neighbours did not, which reads as missing data rather than as
          // a scale too small for names. A row that cannot label them all shows
          // colour only - which is exactly what his own diagram does with the
          // nested band above the main one.
          if (labelled) {
            ctx.fillStyle = `rgba(228, 232, 237, ${live ? 0.95 : 0.6})`;
            ctx.fillText(tagOf(q), left + 4, y + ROW_H / 2);
          }
        }

        // Said at the end of the row it belongs to, not in a footnote. A grid
        // whose boundaries mostly miss this timeframe's bars is drawing a
        // fraction of itself, and a reader counting segments would otherwise
        // count wrong.
        if (lost) {
          ctx.fillStyle = "rgba(217, 164, 65, 0.85)";
          const note = `${lost} off-bar`;
          ctx.fillText(note, width - ctx.measureText(note).width - 4, y + ROW_H / 2);
        }
      });
    };

    paint();
    const scale = chart.timeScale();
    scale.subscribeVisibleLogicalRangeChange(paint);
    const observer = new ResizeObserver(paint);
    observer.observe(canvas);
    return () => {
      scale.unsubscribeVisibleLogicalRangeChange(paint);
      observer.disconnect();
    };
  }, [chart, quarters, now]);

  if (!rows.length) return null;

  return (
    <div className="border-t border-line bg-panel">
      <div className="flex items-baseline justify-between px-3 py-1">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Cycle phase
        </h2>
        {/* The legend is not decoration. Four words on a strip of coloured bars
            is the difference between a diagram and a mood ring, and Q4's two
            readings are shown as two because his own note gives two. */}
        <div className="flex gap-2">
          {(["Q1", "Q2", "Q3", "Q4"] as const).map((q) => (
            <span key={q} className="flex items-center gap-1 text-[10px] text-text-faint">
              <span
                className="inline-block h-2 w-2"
                style={{ background: `rgba(${ROLE[q].ink}, 0.62)` }}
                aria-hidden
              />
              {ROLE[q].full}
            </span>
          ))}
        </div>
      </div>
      <canvas
        ref={host}
        className="block w-full"
        style={{ height: rows.length * ROW_H }}
        role="img"
        aria-label={`Cycle phase ribbon, ${rows.length} nesting levels: ${rows
          .map((d) => ROW[d] ?? d)
          .join(", ")}`}
      />
      {/* THE ROOT IS NAMED, because a path label is meaningless without it and
          the root is not fixed. "Quarters kept" is a display cap that evicts the
          OLDEST boundaries first, and the coarsest degree has the oldest ones -
          so at the shipped 200, adding the micro row pushed the monthly row off
          the ribbon entirely and re-rooted every label. Measured on 2026-08-19,
          same instrument, same minute, one slider apart: a daily quarter read
          3-2-1 under a week root and 2-3-2 under a month root. Both are correct
          relative to their own root and neither carries it, which is why the
          caption has to. */}
      <p className="px-3 pb-2 pt-1 text-[11px] leading-relaxed text-text-faint">
        Paths are read from the{" "}
        <span className="text-accent">{ROW[rows[rows.length - 1]] ?? "bottom"}</span>{" "}
        row down: 3-3-1 is the Q1 of the Q3 of the Q3. The root is whichever
        degree is coarsest ON THIS RIBBON, so a row lost to the quarters-kept cap
        shortens and re-roots every label above it. Set that cap to 0 to keep the
        root fixed.
        {" "}
        Positional roles, read off the clock. Not the measured profile: the engine
        also computes whether a cycle ran AMDX or XAMD, and under XAMD the
        manipulation lands somewhere other than Q2. That reading is in the
        checklist, and it is the one with evidence behind it.
        {" "}
        <span className="text-accent">Off-bar</span> counts quarters whose
        boundary falls between two candles and therefore has no place on this
        chart at all. It is not a rounding detail: a micro quarter is 1350
        seconds and a 15-minute candle is 900, so on that timeframe almost the
        whole micro grid is unplaceable. Trade it on a timeframe that divides it.
      </p>
    </div>
  );
}
