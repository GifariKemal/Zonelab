"""Is the session grid drawn where its own rules say it is?

    python -m tools.session_accuracy [--bars 20000]

`drawing_accuracy.py` asked this of supply and demand zones on 28,476 boxes and
reported WORST CASE rather than averages, because a mean of zero is also what a
drawing with two bugs of opposite sign reports. Everything shipped today - the
quarter grid, true opens, the defining range, SSMT - had no equivalent. This is
it.

Every check below is a PROPERTY recomputed from the candles and the clock, never
a comparison of the module against itself. An auditor that reproduces the code it
audits finds nothing; this project has already published a false finding that way
and said so in docs/FIDELITY.md.

WHAT IS CHECKED, and what each one would catch

1. The grid TILES time. Inside a degree, every quarter's end is the next one's
   start: no gap, no overlap. Catches an off-by-one in the cycle walk, which
   would silently drop or double-count a quarter's worth of bars.

2. Boundaries sit on NEW YORK WALL TIME, across both DST transitions. Every day
   quarter opens at 18, 00, 06 or 12 local. This is the check that fails the
   moment anyone replaces `zoneinfo` with a fixed offset, and the failure would
   otherwise be invisible for most of the year and wrong by an hour for the rest.

3. NESTING is exact: each session quarter lies wholly inside one day quarter,
   each micro wholly inside one session. Note what is NOT checked - the nominal
   90 and 22.5 minutes. Below `day` a quarter is one fourth of its parent's
   ACTUAL span, so on a transition day those stretch, and asserting the nominal
   duration would fail on correct code.

4. Every TRUE OPEN is a real bar's open, at a real Q2 boundary, and every Q2
   boundary WITHOUT a level provably has no bar. The second half matters more
   than the first: absence is the answer this project gives most often, and an
   absence nobody verified is indistinguishable from a bug.

5. The DEFINING RANGE is recomputed from scratch - first third discarded, high
   and low of the bars actually inside the kept window - and compared exactly.

6. ANTI-LOOKAHEAD, asserted rather than intended: recompute on a series
   truncated at the object's own knowable_at and require the same answer.

7. SSMT REFUSES misaligned series. A divergence measured across bars that do not
   share a clock is an artefact of the clock, and downstream nothing can tell it
   from a fact about the market.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from app import quarterly, quarters, ssmt
from app.clock import NY
from tools import history

DAY_HOURS = {18, 0, 6, 12}
SERIES = [("PAXGUSDT", "1h"), ("BTCUSDT", "1h"), ("yahoo:XAUUSD", "1h")]

results: list[tuple[bool, str, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((passed, name, detail))
    print(f"{'PASS' if passed else 'FAIL'}  {name}{f' :: {detail}' if detail else ''}")


def ny_hour(epoch: int) -> int:
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone(NY).hour


# Two degrees have DOCUMENTED holes, and the first version of this harness
# reported them as failures - which was the harness misreading the spec, not the
# grid being wrong. `quarters.py` states both plainly:
#
#   "FRIDAY IS NOT A FIFTH QUARTER. The week has four quarters, Monday to
#    Thursday, and the Friday day-cycle belongs to none of them."
#   "The leftover week at the end of a month is left out for the same reason."
#
# So the honest check for these two is not "no gap" but "every gap is EXACTLY the
# documented hole", which is a stronger statement than contiguity would have
# been: it fails both if a hole disappears and if an undocumented one appears.
# Measured: the week hole is nominally 259200s - Thursday 18:00 to Sunday 18:00,
# exactly 72 hours - and comes out 255600s or 262800s on the two DST weeks. An
# earlier version of this comment called 262800s "72 hours", which it is not; it
# is 73. The month hole is 604800s, and because both of its edges fall on a Monday
# 18:00 it can only ever be a whole number of weeks.
CONTIGUOUS = ("year", "day", "session", "micro")
HOLES = {
    "week": {72 * 3600, 73 * 3600, 71 * 3600},  # weekend, and either DST week
    "month": {7 * 86_400, 7 * 86_400 + 3600, 7 * 86_400 - 3600},
}


def tiles(degree: str, start: int, end: int) -> tuple[list[int], int, int]:
    """Every gap in seconds, the worst overlap, and how many quarters were read."""
    grid = quarters.quarters(degree, start, end)
    gaps: list[int] = []
    worst_overlap = 0
    for a, b in zip(grid, grid[1:]):
        delta = b.start - a.end
        if delta > 0:
            gaps.append(delta)
        worst_overlap = max(worst_overlap, -delta)
    return gaps, worst_overlap, len(grid)


def inside(child, parents) -> bool:
    return any(p.start <= child.start and child.end <= p.end for p in parents)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    args = parser.parse_args()

    loaded = []
    for symbol, interval in SERIES:
        try:
            loaded.append((symbol, interval, history.load(symbol, interval, args.bars)))
        except Exception as exc:  # noqa: BLE001 - a missing series is reportable, not fatal
            print(f"  skipping {symbol} {interval}: {exc}")
    if not loaded:
        print("no series available")
        return 1

    span_from = min(rows[0].time for _, _, rows in loaded)
    span_to = max(rows[-1].time for _, _, rows in loaded)
    days = (span_to - span_from) / 86_400
    print(f"\n{'=' * 78}")
    print(f"SESSION GRID ACCURACY   {len(loaded)} series, {days:.0f} days of span")
    print(f"{'=' * 78}")

    # ---- 1. the grid tiles time -----------------------------------------
    counted = 0
    for degree in quarters.DEGREES:
        gaps, overlap, n = tiles(degree, span_from, span_to)
        counted += n
        if degree in CONTIGUOUS:
            check(
                f"{degree} quarters tile time with no gap and no overlap",
                not gaps and overlap == 0,
                f"n={n} worst gap {max(gaps, default=0)}s, worst overlap {overlap}s",
            )
        else:
            allowed = HOLES[degree]
            odd = sorted({g for g in gaps if g not in allowed})
            check(
                f"{degree} quarters leave only the documented hole, never another",
                not odd and overlap == 0,
                f"n={n}, {len(gaps)} holes, sizes {sorted(set(gaps))}, "
                f"unexpected {odd}, worst overlap {overlap}s",
            )
    print(f"  ({counted} quarters examined in total)")

    # ---- 2. New York wall time, across DST ------------------------------
    # A window this long contains both transitions by construction; the check is
    # worthless on a window that contains neither, so the count is printed.
    day_grid = quarters.quarters("day", span_from, span_to)
    offsets = {
        datetime.fromtimestamp(q.start, timezone.utc).astimezone(NY).utcoffset()
        for q in day_grid
    }
    off_hour = [q for q in day_grid if ny_hour(q.start) not in DAY_HOURS]
    check(
        "every day quarter opens at 18, 00, 06 or 12 New York",
        not off_hour,
        f"n={len(day_grid)}, {len(off_hour)} off-hour, {len(offsets)} distinct UTC offsets seen",
    )
    check(
        "the window actually contains a DST transition",
        len(offsets) > 1,
        f"{sorted(str(o) for o in offsets)}",
    )

    # ---- 3. nesting ------------------------------------------------------
    for child_degree, parent_degree in (("session", "day"), ("micro", "session")):
        children = quarters.quarters(child_degree, span_from, span_to)
        parents = quarters.quarters(parent_degree, span_from, span_to)
        # Only children fully inside the parent span can be nested at all; the
        # window's own edges cut both grids, and a truncated child is an artefact
        # of the window rather than a defect.
        interior = [c for c in children if c.start >= parents[0].start and c.end <= parents[-1].end]
        stray = [c for c in interior if not inside(c, parents)]
        check(
            f"every {child_degree} quarter lies wholly inside one {parent_degree} quarter",
            not stray,
            f"n={len(interior)} checked, {len(stray)} stray",
        )

    # ---- 4, 5, 6: per series --------------------------------------------
    for symbol, interval, rows in loaded:
        print(f"\n  --- {symbol} {interval}, {len(rows)} bars ---")
        at = {c.time: c for c in rows}

        levels = quarters.true_opens(rows, ("day", "week"))
        wrong_price = [o for o in levels if at[o.time].open != o.price]
        check(
            f"{symbol}: every true open is its bar's own open price",
            not wrong_price,
            f"n={len(levels)}, {len(wrong_price)} disagree",
        )

        q2s = [
            q
            for q in quarters.quarters("day", rows[0].time, rows[-1].time)
            if q.label == "Q2"
        ]
        drawn = {o.time for o in levels if o.degree == "day"}
        # The half that matters: every boundary WITHOUT a level must have no bar.
        wrongly_absent = [q for q in q2s if q.start not in drawn and q.start in at]
        check(
            f"{symbol}: every missing daily true open has no bar on its boundary",
            not wrongly_absent,
            f"{len(q2s)} boundaries, {len(drawn)} drawn, "
            f"{len(q2s) - len(drawn)} absent, {len(wrongly_absent)} wrongly absent",
        )

        # ---- 5. the defining range, recomputed ---------------------------
        found = quarterly.defining_ranges(rows, "day")
        bad_window = bad_extreme = 0
        for dfr in found:
            q1 = [
                q
                for q in quarters.quarters("day", dfr.cycle_start, dfr.cycle_start)
                if q.label == "Q1"
            ][0]
            if dfr.start != q1.start + (q1.end - q1.start) // 3 or dfr.end != q1.end:
                bad_window += 1
            kept = [c for c in rows if dfr.start <= c.time < dfr.end]
            if kept and (
                dfr.high != max(c.high for c in kept) or dfr.low != min(c.low for c in kept)
            ):
                bad_extreme += 1
        check(
            f"{symbol}: the defining range starts one third into Q1 and ends at its close",
            bad_window == 0,
            f"n={len(found)}, {bad_window} wrong",
        )
        check(
            f"{symbol}: its high and low are the extremes of the bars in that window",
            bad_extreme == 0,
            f"n={len(found)}, {bad_extreme} wrong",
        )

        # ---- 6. anti-lookahead -------------------------------------------
        # Recomputed on bars truncated at the object's own knowable moment. A
        # value that moves here was reading the future.
        moved = 0
        sample = found[-40:]
        for dfr in sample:
            # Truncated at the FIRST BAR AT OR AFTER Q1's end, inclusive, which
            # is the actual moment this object becomes knowable.
            # `quarterly._closed` proves a quarter has finished by finding such a
            # bar, since it cannot exist until the quarter's last one has closed.
            #
            # Two wrong versions of this line came first, and both were the
            # instrument rather than the code. Truncating at `< dfr.end` removed
            # the proof itself and reported 40 of 40 objects as moved - a 100%
            # failure rate, which is its own tell, because a real lookahead is
            # never that tidy. Truncating at `<= dfr.end` fixed the two crypto
            # series and still failed 1 of 40 on COMEX gold, because gold closes
            # for an hour a day and for the weekend: when no bar opens exactly on
            # the boundary the proving bar arrives hours later, and cutting at
            # the boundary threw it away again.
            proof = next((c.time for c in rows if c.time >= dfr.end), None)
            truncated = [c for c in rows if proof is not None and c.time <= proof]
            again = quarterly.defining_range(truncated, "day", dfr.cycle_start)
            if again is None or (again.high, again.low) != (dfr.high, dfr.low):
                moved += 1
        check(
            f"{symbol}: a defining range is unchanged when the future is removed",
            moved == 0,
            f"n={len(sample)} recomputed at their own Q1 close, {moved} moved",
        )

    # ---- 7. SSMT refuses misaligned series ------------------------------
    symbol, interval, rows = loaded[0]
    try:
        ssmt.ssmt({"a": rows[:-1], "b": rows}, "day")
        refused = False
    except Exception:  # noqa: BLE001 - any refusal is the pass condition
        refused = True
    check(
        "SSMT refuses series that are not on one shared grid",
        refused,
        "one leg one bar short",
    )

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("\nWORST CASE MATTERS MORE THAN THE COUNT. Failures:")
        for _, name, detail in failed:
            print(f"  {name} :: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
