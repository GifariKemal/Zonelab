"""The quarter grid, and the true opens it makes drawable.

WHY THIS EXISTS. A study of the owner's own source material found the method is
built on Quarterly Theory and on named horizontal levels rather than on the
boxes this engine already draws: across 51 annotated charts a named horizontal
level appears on 100% of them and Fibonacci on 12%. The cheapest and most-used
object in the whole practice is therefore a set of correctly-timed horizontal
lines, and none of them can be drawn without a session clock.

THE GRID. Q1 18:00, Q2 00:00, Q3 06:00, Q4 12:00, all America/New_York and
DST-aware. This is settled and is not swept: six independent codifications agree
on it exactly, and the originator's own published statement that "True Day Open
is Midnight's Open" entails it, because a cycle's true open is by construction
its Q2 open - midnight is Q2 only if the cycle opened at 18:00. 18:00 New York is
also the CME open, so the anchor is a market fact rather than a preference.

THE SAME QUARTERING RULE AT EVERY DEGREE:

  year     calendar year -> Jan / Apr / Jul / Oct. True year open is April.
  month    four week-cycles from the month's first Monday. See the CHOICE below.
  week     Sunday 18:00 -> Q1 Monday, Q2 Tuesday, Q3 Wednesday, Q4 Thursday.
  day      18:00 -> Q1 18:00, Q2 00:00, Q3 06:00, Q4 12:00. True day open is Q2.
  session  one 6-hour day quarter -> four 90-minute quarters.
  micro    one 90-minute quarter -> four 22.5-minute quarters.
  nano     one 22.5-minute quarter -> four 337.5-second quarters.

Below `day` a quarter is one fourth of its parent's ACTUAL span, not a fixed
5400 or 1350 seconds. 90 and 22.5 minutes are the nominal figures and they hold
on all but two days a year; on the transition days the parent 6-hour quarter is
really 5 or 7 hours, because its ends are nailed to the wall clock, and its
fourths stretch with it. Quartering the parent is what keeps the nesting exact -
no gaps, no overlap - and a fixed 5400 would either overrun the parent or leave
a hole in it. 22.5 minutes is 1350 whole SECONDS, so the half minute needs no
rounding anywhere: boundaries land on :22:30 and :67:30 and the code never sees
a fraction.

NANO, AND THE HALF SECOND THAT DOES NOT DIVIDE. A nano is the quarter of a micro
quarter exactly as a micro is the quarter of a session quarter, so it is the same
mechanism one level down and not a second one: it quarters its PARENT'S ACTUAL
span, and on a transition day that parent is 1125 seconds rather than 1350 and
its nanos shrink with it. Nothing is hardcoded to 337.5 anywhere.

337.5 is where the arithmetic stops being whole, and it is handled by never
dividing. `_fourths` computes `start + span * i // 4`, multiplying before the
floor, so the four edges are whole seconds that add back to the parent's exact
span. A 1350-second parent therefore yields parts of 337, 338, 337 and 338
seconds, and a 1125-second one yields 281, 281, 281 and 282. The parts are not
equal - they differ by at most one second - and that is the deliberate trade,
because four EQUAL parts of 337.5 seconds cannot be whole seconds and tile a
1350-second parent at the same time. Tiling is the property the accuracy harness
asserts and the property the whole nesting rests on; a half second of equality is
not. Rounding each boundary independently would have kept the parts closer to
equal and left a gap or an overlap at the parent's close, on every micro cycle
rather than on two days a year.

NANO IS NOT LISTED IN `DEGREES`, which is a compatibility choice and not a
statement that it is a lesser degree. `DEGREES` is read elsewhere as more than a
spelling list: `pools.py` treats it as an ordered parent chain, and
`tools/session_accuracy.py` loops over it and requires every degree outside its
own CONTIGUOUS list to have an entry in its table of documented holes. Appending
to `DEGREES` would change the behaviour of both files from inside this one. So
the seventh degree ships in `ALL_DEGREES`, which is what `quarters` validates
against, and moving it into `DEGREES` is a decision for those two files.

FRIDAY IS NOT A FIFTH QUARTER. The week has four quarters, Monday to Thursday,
and the Friday day-cycle belongs to none of them. This looks like an off-by-one
to anyone reading `range(4)` over Mon..Thu, and it is not: it is the doctrine.
Friday still exists at the `day` degree, it simply is not a week quarter. The
leftover week at the end of a month is left out for the same reason.

THE MONTH/WEEK-OF-MONTH CHOICE, stated as a choice and not as a citation. Two
published rules conflict and neither is dominant, so this module implements one
and names the other:
  - IMPLEMENTED: the monthly cycle is the four week-cycles beginning at the
    month's first Monday, so a monthly quarter is exactly a week and the month
    degree nests inside the week degree the same way every other pair does. Days
    before that first Monday, and a fifth week after it, belong to no monthly
    quarter.
  - NOT IMPLEMENTED: the calendar-day rule, which splits the month into days
    1-7, 8-14, 15-21 and 22-to-end regardless of weekday. It keeps whole months
    covered at the cost of quarters that are not weeks and that start midweek.
This is a judgement, not a source.

NO LEVEL WITHOUT A BAR. `true_opens` returns a price only when a candle opens
EXACTLY on the boundary. Weekends, holidays, gaps and feeds that start
mid-session mean the bar frequently is not there, and in that case the level does
not exist and nothing is returned for it. Nothing is interpolated, nothing is
carried forward. This is the same rule `Candle.spread` follows by being None
rather than 0 when unmeasured: absent means not measured, never zero.

THE TRUE OPENS THE NOTES NAME, AND THE ONES THIS MODULE REFUSES TO NAME. A true
open is a cycle's Q2 open, so a name is definable here only when it names a CYCLE
this grid already has. Five names in the owner's notes are not new degrees:

  - TLO, the true London open, IS TDO. The source marks the London session's
    opening at 00:00 New York ("Q2 - London -- kita marking pembukaan session ini
    di 0000", chat.txt), and 00:00 is the day cycle's Q2 open, which is the true
    day open. Same instant, same bar, same price. So nothing is added for it:
    asking for degree "day" is asking for TLO, and shipping a second object with
    a second name would have put two lines on one price and invited someone
    downstream to count them as two agreeing levels.
  - TNYO, the true New York open, is NOT ADDED. The same note marks New York AM
    at 06:00, and 06:00 is the day cycle's Q3 open. A Q3 open is a quarter
    boundary, not a true open, and no cycle in this grid has its Q2 at 06:00 - a
    midnight-anchored 24-hour cycle would, and this grid anchors the day at
    18:00. The level is still drawable, as the Q3 start of `quarters("day", ...)`,
    it simply is not a true open, and shipping it as one would put a false type
    on a real line.
  - TNO, the true nano open. The level exists: it is the nano degree's Q2 and is
    returned by `true_opens(candles, ("nano",))`. What it IS is the true open of
    the 22.5-minute MICRO cycle, because a degree's Q2 is the true open of the
    cycle that degree quarters - that is exactly why the micro degree's level is
    tagged T90mO in the frontend and not something with "micro" in it. The notes
    list "True micro" and "True nano" as two separate lines, and under that same
    convention a true NANO open would be the Q2 of a nano cycle, which needs an
    eighth degree that the owner's own seven-level nesting list (Yearly, Monthly,
    Weekly, Daily, 90M, Micro, Nano) does not contain. So the level ships and the
    tag does not: this module emits `degree="nano"` and leaves labelling to the
    layer that draws labels.
  - T4Y and "old two" are NOT DEFINED. Neither string occurs anywhere in the
    text sources in this repository - the chat transcripts contain neither, and
    the 51 annotated charts are images that were not read as text - so there is
    nothing to expand them from, and neither can be derived from this grid
    without choosing what it means. Downstream an invented level is
    indistinguishable from a sourced one, so the absence is the safer answer,
    and it is recorded here rather than left as a silent omission.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from datetime import date, timedelta

from . import clock
from .models import Candle

DEGREES = ("year", "month", "week", "day", "session", "micro")

#: THE QUADRENNIAL CYCLE: four years, one year per quarter, and Q2 is the United
#: States presidential election year.
#:
#: Added because a practitioner named the omission directly: "True open masih
#: missing quartery cycle sm quadrennial cycle", followed by the rule itself -
#: "Quadrennial: 1 taun = satu cycle. Paling gampang ingat, q2 = PILPRES
#: Amerika". The quarterly cycle he named alongside it was already here: the
#: `year` degree cuts at 1 January, 1 April, 1 July and 1 October, which IS
#: Q1 Jan-Mar, Q2 Apr-Jun, Q3 Jul-Sep, Q4 Oct-Dec. Only the four-year cycle
#: above it was absent, and with it the one true open nothing could reach.
#:
#: THE ANCHOR IS A FACT, not a fitted parameter, and that is why this is
#: buildable at all. US presidential elections fall on years divisible by four -
#: 2016, 2020, 2024, 2028 - so `year % 4 == 0` names Q2 and the rest follow:
#: Q1 is the year before the election, Q3 the year after, Q4 two years after.
#: The cycle containing 2026 is therefore Q1 2023, Q2 2024, Q3 2025, Q4 2026.
#: Nothing here is chosen, so there is nothing here to fit.
#:
#: NOT IN `DEGREES`, for the same reason `nano` is not, mirrored. `pools.py`
#: reads `DEGREES` as an ordered PARENT chain and treats `DEGREES[0]` as the root
#: with no parent; prepending here would silently give the `year` degree a parent
#: and change that file's behaviour from inside this one. `tools/session_accuracy.py`
#: loops over `DEGREES` and demands a documented-holes entry per degree. Both are
#: decisions for those files. `ALL_DEGREES` is what `quarters` validates against,
#: so the grid, the true opens and the defining range can all read this degree
#: today.
QUADRENNIAL = "quadrennial"

#: Floor on how far past a boundary the approximate true open may reach, in
#: seconds. The reach actually used is this OR the chart's own bar interval,
#: whichever is larger - see `_reach`.
#:
#: MEASURED, not chosen. The longest real closure in the feed this project trades
#: is 96 hours: on ten years of hourly broker gold the largest bar-to-bar gaps are
#: the Christmas and New Year weeks of 2016 and 2017 and Easter 2019, all of them
#: exactly 96h, with the ordinary Easter closure at 74h and the ordinary weekend
#: at 65h. 120 hours clears every one of them with a margin and still refuses the
#: case that made this constant necessary - a boundary seven months before the
#: first bar the feed carries.
#:
#: A crypto feed never closes at all (the same measurement on PAXGUSDT tops out
#: at a 5-hour gap), so this floor only ever binds on an instrument that shuts.
_APPROX_REACH_SECONDS = 120 * 3600


def _reach(times: list[int]) -> int:
    """How far past a boundary the fallback may look, for THIS series.

    The floor above was measured from market closures, and on an intraday chart
    that is the only thing standing between a boundary and its next bar. On a
    coarse chart it is not: weekly bars open once every 168 hours, so a boundary
    can sit five days from the next open with the market never having shut at
    all. A fixed 120-hour bound then rejects levels for a reason that has nothing
    to do with the reason it was measured for - and it did, on the first weekly
    chart it met.

    So the reach is the larger of the two: the measured closure, or one bar of
    whatever is being drawn. The bar interval is the SMALLEST gap in the series
    rather than the difference between any chosen pair, because any particular
    pair can straddle a hole.
    """
    if len(times) < 2:
        return _APPROX_REACH_SECONDS
    step = min(b - a for a, b in zip(times, times[1:]))
    return max(_APPROX_REACH_SECONDS, step)

# The eighth degree and the seventh, both kept out of `DEGREES` on purpose - see
# the docstring and the note above. This is what `quarters` accepts; `DEGREES`
# stays the six-tuple its other readers already depend on.
ALL_DEGREES = (QUADRENNIAL,) + DEGREES + ("nano",)


@dataclass(frozen=True)
class Quarter:
    degree: str
    # Narrowed to the four names this module can emit, so a typo cannot reach
    # the wire model that also only permits four. `structure.Break.kind` is
    # narrowed for the same reason: a plain `str` here made the API layer's
    # `SessionQuarter(label=...)` a type hole that nothing would have caught
    # until a chart drew a quarter called "Q5".
    label: Literal["Q1", "Q2", "Q3", "Q4"]
    start: int  # epoch seconds, inclusive
    end: int  # epoch seconds, exclusive


@dataclass(frozen=True)
class TrueOpen:
    """The open of a cycle's Q2, read off a bar that exists.

    `time` is the quarter BOUNDARY. `bar` is the open time of the bar the price
    was read from. They are equal whenever `approximate` is False, which is the
    default and the only behaviour this module had for a long time: a boundary
    with no bar on it produced no level, nothing carried forward, nothing
    interpolated.

    `approximate` exists because one boundary can NEVER have a bar on it. The
    quadrennial cycle's Q2 opens on 1 January, and 1 January is a market holiday
    every single time: measured on ten years of hourly gold, all three
    quadrennial Q2 boundaries in the window (2016, 2020, 2024) had no bar, so the
    level the practitioner asked for came back empty by construction rather than
    by omission. The `year` degree has the same problem intermittently - its Q2 is
    1 April, and 1 April 2023 was a Saturday.

    So the fallback is the first bar at or AFTER the boundary, it is opt-in, and
    it is flagged all the way to the canvas, where it draws dashed with a `~`.
    That is the convention `gaps.py` already established for an edge the bars
    cannot give exactly, and the reason it is a flag rather than a silent
    substitution is that an approximate level and a measured one must never look
    alike.
    """

    degree: str
    time: int
    price: float
    bar: int = 0
    approximate: bool = False

    def __post_init__(self) -> None:
        # `bar` defaults to the boundary so every existing construction site -
        # and every test that builds one positionally - keeps meaning exactly
        # what it meant before this field existed.
        if not self.bar:
            object.__setattr__(self, "bar", self.time)


def _day_cycle_start(epoch: int) -> int:
    """The 18:00 New York boundary at or before `epoch`."""
    start = clock.at_ny_hour(epoch, 18)
    return start if start <= epoch else clock.at_ny_hour(epoch, 18, days=-1)


def _week_cycle_start(epoch: int) -> int:
    """The Sunday 18:00 New York that opens this week's Q1 (Monday)."""
    day = _day_cycle_start(epoch)
    # `day` is an 18:00 boundary, and the cycle it opens is the NEXT calendar
    # day's - 18:00 Sunday opens Monday. Step back to the Sunday evening.
    return clock.add_ny_days(day, -((clock.to_ny(day).weekday() + 1) % 7))


def _month_cycle_start_for(year: int, month: int) -> int:
    """Week-cycle start of that month's first Monday."""
    first = date(year, month, 1)
    monday = first + timedelta(days=(7 - first.weekday()) % 7)
    sunday = monday - timedelta(days=1)
    return clock.ny_wall(sunday.year, sunday.month, sunday.day, 18)


def _monday_of(week_start: int) -> date:
    return clock.to_ny(clock.add_ny_days(week_start, 1)).date()


def _fourths(start: int, end: int) -> list[int]:
    span = end - start
    return [start + span * i // 4 for i in range(5)]


def _containing(edges: list[int], epoch: int) -> tuple[int, int]:
    for i in range(4):
        if edges[i] <= epoch < edges[i + 1]:
            return edges[i], edges[i + 1]
    return edges[3], edges[4]


def _cycle(degree: str, epoch: int) -> tuple[list[int], int]:
    """Five boundary edges of the cycle holding `epoch`, and the next cycle's start.

    `epoch` can sit OUTSIDE every returned quarter: Friday at the week degree and
    the fifth week at the month degree are real time that belongs to no quarter.
    """
    if degree == QUADRENNIAL:
        # Q2 is the election year, so the cycle opens the year BEFORE it. Integer
        # arithmetic rather than a table: `(year + 1) // 4 * 4` is the election
        # year at or after `year - 1`, and subtracting one lands on Q1.
        year = clock.to_ny(epoch).year
        q1 = ((year + 1) // 4) * 4 - 1
        edges = [clock.ny_wall(q1 + i, 1, 1) for i in range(4)]
        edges.append(clock.ny_wall(q1 + 4, 1, 1))
        return edges, edges[4]

    if degree == "year":
        year = clock.to_ny(epoch).year
        edges = [clock.ny_wall(year, m, 1) for m in (1, 4, 7, 10)]
        edges.append(clock.ny_wall(year + 1, 1, 1))
        return edges, edges[4]

    if degree == "month":
        monday = _monday_of(_week_cycle_start(epoch))
        start = _month_cycle_start_for(monday.year, monday.month)
        edges = [clock.add_ny_days(start, 7 * i) for i in range(5)]
        nxt = _month_cycle_start_for(
            monday.year + monday.month // 12, monday.month % 12 + 1
        )
        return edges, nxt

    if degree == "week":
        start = _week_cycle_start(epoch)
        # Five edges over FOUR day-cycles: Monday through Thursday. Friday, which
        # begins at edges[4], is deliberately not a quarter (see module docstring).
        edges = [clock.add_ny_days(start, i) for i in range(5)]
        return edges, clock.add_ny_days(start, 7)

    if degree == "day":
        start = _day_cycle_start(epoch)
        day = clock.to_ny(start).date() + timedelta(days=1)
        edges = [start] + [
            clock.ny_wall(day.year, day.month, day.day, h) for h in (0, 6, 12, 18)
        ]
        return edges, edges[4]

    if degree == "session":
        day_edges, _ = _cycle("day", epoch)
        start, end = _containing(day_edges, epoch)
        return _fourths(start, end), end

    if degree == "micro":
        session_edges, _ = _cycle("session", epoch)
        start, end = _containing(session_edges, epoch)
        return _fourths(start, end), end

    if degree == "nano":
        micro_edges, _ = _cycle("micro", epoch)
        start, end = _containing(micro_edges, epoch)
        return _fourths(start, end), end

    raise ValueError(f"unknown degree {degree!r}, expected one of {ALL_DEGREES}")


def quarters(degree: str, time_from: int, time_to: int) -> list[Quarter]:
    """Every quarter of `degree` overlapping [`time_from`, `time_to`], in time order.

    Time that belongs to no quarter - Friday at the week degree, a fifth week at
    the month degree - simply produces nothing there rather than a synthetic Q5.
    """
    if degree not in ALL_DEGREES:
        raise ValueError(f"unknown degree {degree!r}, expected one of {ALL_DEGREES}")

    # Written out rather than built with an f-string, because `f"Q{i+1}"` is a
    # plain `str` and the label is narrowed to four names. Spelling them keeps
    # the narrowing real instead of casting it away at the one place it is set.
    labels: tuple[Literal["Q1", "Q2", "Q3", "Q4"], ...] = ("Q1", "Q2", "Q3", "Q4")

    out: list[Quarter] = []
    edges, nxt = _cycle(degree, time_from)
    while True:
        for i in range(4):
            start, end = edges[i], edges[i + 1]
            if start <= time_to and end > time_from:
                out.append(Quarter(degree, labels[i], start, end))
        if nxt > time_to:
            return out
        edges, nxt = _cycle(degree, nxt)


def true_opens(
    candles: list[Candle],
    degrees: Sequence[str] = ("day",),
    approximate: bool = False,
) -> list[TrueOpen]:
    """The price at each cycle's Q2 open, for every requested degree.

    Q2 because that is the definition in use: the true open of a cycle is its Q2
    open, which is why the daily true open is midnight New York and not 18:00.

    A boundary with no bar opening exactly on it yields NO level, and that is the
    default. Returned in the order the degrees were requested, by time within
    each degree.

    `approximate` relaxes the exact-bar rule to "the first bar at or after the
    boundary", and every level it adds is flagged. Off by default because turning
    it on changes what a drawn line MEANS, and because the strict rule is the one
    every existing measurement in this project was taken under. It exists for the
    coarse degrees, where the strict rule can be structurally unsatisfiable: the
    quadrennial Q2 boundary is 1 January and the market is shut on 1 January every
    year, so on ten years of hourly gold the strict rule returned nothing at all
    for that degree. A level that can never exist is not a conservative choice,
    it is a missing feature - but a level quietly moved to the next open would be
    worse, which is why it arrives flagged rather than substituted.

    The fallback never reaches BACKWARD. Taking the last bar before the boundary
    would read a price from the previous cycle and label it as this one's open,
    which is the one error the strict rule exists to prevent.
    """
    if not candles:
        return []

    at = {candle.time: candle for candle in candles}
    times = [candle.time for candle in candles]
    reach = _reach(times)
    out: list[TrueOpen] = []
    for degree in degrees:
        for quarter in quarters(degree, candles[0].time, candles[-1].time):
            if quarter.label != "Q2":
                continue
            exact = at.get(quarter.start)
            if exact is not None:
                out.append(
                    TrueOpen(degree, quarter.start, exact.open, exact.time, False)
                )
                continue
            if not approximate:
                continue
            # THE BOUNDARY MUST BE INSIDE THE WINDOW, and this guard is the
            # difference between a level and a REPAINT. I removed it once, because
            # a test I had written demanded a window starting the day AFTER the
            # boundary - and that test was the bug: a boundary before the first
            # bar is the one case where "no bar opened here" cannot be
            # distinguished from "this window does not reach back that far".
            #
            # Measured cost of getting it wrong: on 20,000 hourly bars of gold,
            # SEVEN levels changed when the window was extended leftward. A week
            # true open read 4827.589 marked approximate at 2,000 bars and
            # 4827.612 marked EXACT at 20,000 - same named level, two prices,
            # because the boundary's own bar was outside the shorter window and
            # the fallback reached forward past it. The reader would have seen a
            # drawn line move under them for changing one dropdown.
            #
            # The real feature is untouched: the quadrennial Q2 boundaries this
            # flag exists for - 1 January 2020 and 2024 - sit well inside a ten
            # year window, and the 2016 one it must refuse is refused here as
            # well as by the reach below.
            if quarter.start < candles[0].time:
                continue
            index = bisect_left(times, quarter.start)
            if index >= len(candles):
                continue
            bar = candles[index]
            if bar.time - quarter.start > reach:
                continue
            out.append(TrueOpen(degree, quarter.start, bar.open, bar.time, True))
    return out


@dataclass(frozen=True)
class Stack:
    """Which of a set of true opens price is above, and which it is below.

    `above` holds the levels sitting ABOVE the price, `below` the ones sitting
    below it. A level whose price equals the price exactly is in neither: price
    is not on a side of a line it is standing on.
    """

    above: tuple[TrueOpen, ...]
    below: tuple[TrueOpen, ...]


def stacked_opens(price: float, levels: Sequence[TrueOpen]) -> Stack:
    """How many of `levels` price is on the same side of, and which ones.

    A statement about where price sits relative to lines that already exist, and
    nothing more. It does not say what to do about it, and the count it reports
    is not evidence that anything follows: Twelve pre-registered directional
    hypotheses have failed in this project, and none of them was refuted by
    counting lines.

    NO THRESHOLD LIVES HERE. The owner's stated precondition is a minimum of two
    true opens pointing the same way before he acts ("true opens harus pake dua
    minimal", with "True Open Week - di bawah / True Month Open - di bawah" as
    the worked example), so the caller compares `len(...)` against its own
    number. Two is his figure and it is unmeasured; putting it inside this
    function would turn an arithmetic report into a verdict, and would hide
    which side, and which levels, produced it.

    The levels are whatever the caller passes. `true_opens` only ever returns
    levels whose bar has already opened, so passing its output cannot look ahead;
    passing hand-built levels can, and this function cannot tell.
    """
    return Stack(
        above=tuple(level for level in levels if level.price > price),
        below=tuple(level for level in levels if level.price < price),
    )
