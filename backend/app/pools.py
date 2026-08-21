"""The two checklist items that need a clock: time-defined premium/discount, and
the liquidity pools of the named sessions.

They share this file because they share the only thing they have in common: a
window whose edges come from the New York wall clock rather than from a swing.
Neither one says anything about which way price will go.

================================================================================
PART ONE. THE TIME-DEFINED PREMIUM AND DISCOUNT.

THIS PROJECT NOW HAS THREE PREMIUM/DISCOUNT READINGS AND THEY ARE DIFFERENT
QUANTITIES. Read this before using any of them, because picking the wrong one
gives an answer that looks right and measures something else:

  `Zone.curve` (detect/, see models/zone.py)
      The Seiden reading. A 200-bar ROLLING window split in thirds, measured on
      the bars before the base and FROZEN when the zone was born. Anchored to a
      bar count.

  `Zone.dealing_range_pos` (app/dealing_range.py)
      The ICT reading. A range anchored to the last confirmed SWING high and
      low, read at the moment price ARRIVES at the zone. Anchored to structure.

  `premium_discount` HERE
      Anchored to a CLOCK. The range of the cycle at the degree one above the
      one being traded, measured from that cycle's open to the latest bar, with
      the 50% of that range as the line: below it is discount, above it is
      premium. No swing is consulted at all, and that is the entire point - the
      window's edges are calendar facts, so the reading changes when the clock
      says so and not when a pivot confirms.

This is the reading the owner's own procedure uses ("In discount?"), which is why
it exists beside the other two rather than replacing either.

THE ANCHOR IS A CHOICE AND THE ITEM IS SINGLE-SOURCED. "One degree above the one
being traded" reached this project through one voice. It is the part a second
source could contradict, so it is an explicit parameter, the default is stated
here as a JUDGEMENT and not as a citation, and every candidate anchor is
returned rather than only the chosen one:

  parent_cycle       DEFAULT. The parent-degree cycle holding the bar, from its
                     open to the bar being read. Still running, so its high and
                     low can still move. This is the anchor the procedure
                     describes.
  parent_previous    The previous parent-degree cycle, whole and closed. Cannot
                     move any more, and is stale by up to one full cycle.
  previous_quarter   The last quarter of the parent grid that has provably
                     closed. The freshest window that is finished.

A reader who can see that `parent_cycle` says discount while `previous_quarter`
says premium has learned something a single boolean would have hidden, and
`disagree` says so on the object. That disclosure is the house style here, not
decoration.

`position` is deliberately NOT clipped to 0..1. On a closed window price can sit
outside the range it is being measured against, and clipping it to 1.0 would
report "at the high" for a bar that is well above it.

AND ONE CONSEQUENCE OF ANCHORING TO THE GRID, because it is visible to a user
rather than only to a reader: time that belongs to no cycle produces NO reading.
Friday is not a quarter of the week (see `quarters.py` - the week has four
quarters, Monday to Thursday, and that is the doctrine rather than an off-by-one),
so a Friday bar traded at the `day` degree has no week-degree cycle to be measured
against and every anchor is reported absent. It is not folded into Thursday's
cycle and Friday is not extended into a fifth quarter.

================================================================================
PART TWO. LIQUIDITY POOLS.

The extremes of two named sessions, as candidate targets:

  asia     19:00 to 00:00 New York. ICT's own window in his own transcript. The
           window STRADDLES midnight, so it opens on one calendar date and
           closes on the next - get that wrong and every Asian pool is wrong.
  london   02:00 to 05:00 New York, the London killzone.

A session high is buy-side liquidity (BSL), a session low is sell-side (SSL).
Every pool carries its price, its side, the session, the window it was measured
over, and `taken_at`: the open time of the FIRST bar that traded through it, or
None while it still stands. An untaken pool is a candidate target; a taken one is
history and is still reported, because "London high already got taken" is the
fact that kills a trade idea, and a pool list that silently dropped it would be
answering a different question.

Zones are accepted as an argument and reported the same way by `zone_targets`, so
a fair value gap can be a target exactly as a session high can. No detector is
imported or run here; a zone's own `first_test_time` is the touch record, so this
pass cannot disagree with the rest of the engine about whether a box was hit.

THE 02:00 HOLE, stated because the London window opens exactly on it. US DST
transitions happen at 02:00 New York, so on the spring-forward day 02:00 does not
exist: `zoneinfo` with fold=0 maps it to the pre-transition offset, which is
03:00 EDT, and the killzone is therefore two real hours that day instead of
three. That is the honest consequence of a wall-clock window and it is asserted
in tests/test_pools.py rather than left to be discovered on a chart. Nothing here
does its own timezone arithmetic; every boundary comes from `app/clock.py`.

================================================================================
HOUSE RULES, all asserted in tests/test_pools.py:

NO BAR, NO POOL. A window with no bars in it - a holiday, a feed that starts
mid-session - produces NOTHING. The window is never widened to find a bar and no
price is ever interpolated or carried forward, the same rule
`quarters.true_opens` and `Candle.spread` follow: absent means not measured.

ANTI-LOOKAHEAD. A session's extreme is knowable only once that session has
CLOSED, and the proof is readable from the data alone: a bar opening at or after
the window's end cannot exist until the window's last bar has closed. That bar's
open time is `knowable_at`, and a session with no such bar yet produces no pool
at all rather than a provisional one. `taken_at` is the FIRST bar that traded
through the level, never the last.

A PARTIAL WINDOW IS NOT A SESSION. If the feed only covers 21:00 to 00:00, the
high of those bars is not the Asian high. The pool is still emitted - dropping it
would hide the bars that do exist - but `covered` is False and `first_bar`,
`last_bar` and `bars` say exactly what was measured.

NO DIRECTION CLAIM. Twelve pre-registered directional hypotheses have failed in
this project. "Price is in discount" is a statement about where price sits in a
range and is NOT a reason to buy; an untaken session high is a level that has not
been traded through, and nothing more. Neither of these two items has ever been
measured against outcomes here, so there is no field on any object below that
ranks, scores or forecasts anything.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from . import clock
from .models import Candle, Zone
from .quarters import DEGREES, quarters

ANCHORS = ("parent_cycle", "parent_previous", "previous_quarter")

# (open hour, close hour, calendar days from open date to close date). Asia's
# third field is what carries it across midnight.
SESSIONS: dict[str, tuple[int, int, int]] = {
    "asia": (19, 0, 1),
    "london": (2, 5, 0),
}


@dataclass(frozen=True)
class RangeReading:
    """One anchor's window, and where price sits inside it.

    `complete` is False while the window can still grow, which is the normal
    state of the default anchor: the parent cycle is still running, so its high
    and low are provisional in exactly the way a closed window's are not.
    """

    anchor: str
    degree: str  # the degree the window was taken at, one above the traded one
    time_from: int  # window open, inclusive
    time_to: int  # open time of the last bar included, inclusive
    complete: bool  # a bar at or after the window's end proves it closed
    bars: int
    high: float
    low: float
    equilibrium: float  # the 50% line, which is what discount is measured from
    position: float  # 0 at the low, 1 at the high, NOT clipped
    reading: Literal["premium", "discount", "equilibrium"]


@dataclass(frozen=True)
class PremiumDiscount:
    """Where price sits in a clock-anchored range, under every candidate anchor.

    `chosen` is the reading for the requested anchor and may be None when that
    one anchor had no bars while another did. `disagree` is True when the
    candidates do not all give the same word, which is the case worth seeing.
    """

    degree: str  # the degree being traded; the windows are one degree above it
    anchor: str  # the requested anchor - a choice, see the module docstring
    at: int  # open time of the bar the reading was taken on
    price: float  # that bar's close
    chosen: RangeReading | None
    readings: tuple[RangeReading, ...]
    absent: tuple[str, ...]  # anchor, and why it produced no reading
    disagree: bool


@dataclass(frozen=True)
class Pool:
    """A session extreme, and whether price has been through it.

    Not a target recommendation. It is the highest high or lowest low of a named
    window, plus the coverage that window actually had.
    """

    session: str
    side: Literal["BSL", "SSL"]  # buy-side at the high, sell-side at the low
    price: float
    window_from: int  # session open, New York wall clock
    window_to: int  # session close, exclusive
    first_bar: int  # open time of the first bar actually inside the window
    last_bar: int
    bars: int
    covered: bool  # the bars spanned the whole window at the feed's own step
    knowable_at: int  # first bar proving the session closed
    taken_at: int | None  # first bar that traded through, None while it stands


@dataclass(frozen=True)
class ZoneTarget:
    """An already-detected zone as a candidate target, with its own touch record.

    `price` is the PROXIMAL line - the edge price meets first - for the same
    reason `dealing_range.py` measures there: it is the price a fill would
    happen at. `taken_at` is the zone's own `first_test_time`, not a second
    opinion computed here.
    """

    zone_id: str
    kind: str
    side: str  # demand or supply, which is where the zone sits, not a direction
    state: str
    price: float
    formed_at: int
    taken_at: int | None


def _bars(candles: list[Candle], start: int, end: int) -> list[Candle]:
    """Bars whose OPEN time falls in [start, end). Assumes time order, as the feed is."""
    return candles[
        bisect_left(candles, start, key=lambda c: c.time) : bisect_left(
            candles, end, key=lambda c: c.time
        )
    ]


def _step(candles: list[Candle]) -> int:
    """The feed's bar interval, taken as the MODAL gap between two bars.

    This was the smallest gap, on the reasoning that missing bars only ever make
    gaps larger so the minimum survives them, and that under-reporting the step
    would only make `Pool.covered` stricter - the safe direction.

    It is not the safe direction, because "stricter" here means WRONG on a
    user-visible flag. On 500 bars of Yahoo 15m gold the gap is 900 seconds 493
    times, 4500 four times over session breaks, and **899 exactly once**. The
    minimum took that single one-second irregularity as the feed's interval, so a
    fully covered five-hour Asian window measured 20 x 899 = 17.980 against 18.000
    and every pool on the chart came back partial. The flag exists to say "this
    high is not the session high"; firing it on a complete session says the
    opposite of the truth about every ray at once.

    The modal gap survives both failure modes: missing bars are outnumbered by
    present ones, and a single off-by-one timestamp cannot outvote 493 correct
    ones. This is the same correction `tools/validate_api.py` already carries for
    its own bar-spacing check, which failed on correct data for the same reason -
    the second time in this project that a spacing rule read one pair of bars and
    believed it.
    """
    gaps = [b.time - a.time for a, b in zip(candles, candles[1:]) if b.time > a.time]
    return Counter(gaps).most_common(1)[0][0] if gaps else 0


def _parent(degree: str) -> str:
    """The degree one above `degree`, which is where the anchor window comes from."""
    if degree not in DEGREES:
        raise ValueError(f"unknown degree {degree!r}, expected one of {DEGREES}")
    if degree == DEGREES[0]:
        raise ValueError(f"{degree} has no degree above it, so it has no time anchor")
    return DEGREES[DEGREES.index(degree) - 1]


def _cycles(degree: str, at: int) -> list[tuple[int, int]]:
    """(open, close) of the `degree` cycles around `at`, oldest first.

    Paired by walking the quarter grid - a cycle opens at a Q1 and closes at the
    Q4 that follows it - rather than by arithmetic on a span. Cycles are not all
    the same length (a DST day is 23 or 25 hours), and at the week and month
    degrees there is real time after Q4 that belongs to no quarter at all, so
    stepping back a fixed amount would land in a cycle that does not exist.

    Empty when `at` itself belongs to no quarter, which is a real answer: Friday
    at the week degree and a fifth week at the month degree are not in any cycle.
    """
    here = quarters(degree, at, at)
    if not here:
        return []

    span = here[0].end - here[0].start
    out: list[tuple[int, int]] = []
    opened: int | None = None
    for quarter in quarters(degree, here[0].start - 8 * span, here[0].start + 8 * span):
        if quarter.label == "Q1":
            opened = quarter.start
        elif quarter.label == "Q4" and opened is not None:
            out.append((opened, quarter.end))
            opened = None
    return out


def _window(anchor: str, parent: str, at: int) -> tuple[int, int] | None:
    """The [open, close) window `anchor` names, at the `parent` degree.

    None when the grid has no such window: `at` in time that belongs to no
    cycle, or a previous cycle/quarter that the grid does not reach.
    """
    grid = _cycles(parent, at)
    holding = [i for i, (open_, close) in enumerate(grid) if open_ <= at < close]
    if not holding:
        return None
    here = holding[0]

    if anchor == "parent_cycle":
        return grid[here]
    if anchor == "parent_previous":
        return grid[here - 1] if here else None

    # previous_quarter: the last quarter of the parent grid that has closed by
    # `at`. Its end being at or before `at` is the same knowability proof the
    # rest of this file uses.
    closed = [
        q for q in quarters(parent, grid[max(here - 1, 0)][0], at) if q.end <= at
    ]
    return (closed[-1].start, closed[-1].end) if closed else None


def premium_discount(
    candles: list[Candle],
    degree: str = "session",
    anchor: str = "parent_cycle",
    at: int | None = None,
) -> PremiumDiscount | None:
    """Where price sits in a range the CLOCK defined, under every candidate anchor.

    `degree` is the degree being TRADED; every window is taken one degree above
    it, which is the rule as it reached this project. It defaults to `session`
    because the checklist this serves is applied intraday, so the anchor cycle is
    the day - and that default, like the anchor itself, is a judgement rather than
    a citation. `year` is rejected: it has no degree above it.

    `anchor` selects which window `chosen` reports, and every other candidate is
    reported beside it in `readings`. See the module docstring for why: the anchor
    is the single-sourced part of this item, so the alternatives are disclosed
    rather than hidden behind a default.

    `at` is the bar to read, defaulting to the last one. The bar at or before it
    supplies the price, which is that bar's CLOSE. None when there are no bars, or
    when `at` precedes the series.

    An anchor whose window holds no bars, or whose window has no height, produces
    no reading and an entry in `absent` saying so. Nothing is interpolated and no
    neighbouring window is substituted.

    This is a statement about where price sits in a range. It is not a reason to
    buy or to sell, and no part of this project has measured whether it predicts
    anything.
    """
    parent = _parent(degree)
    if anchor not in ANCHORS:
        raise ValueError(f"unknown anchor {anchor!r}, expected one of {ANCHORS}")
    if not candles:
        return None

    when = candles[-1].time if at is None else at
    index = bisect_right(candles, when, key=lambda c: c.time) - 1
    if index < 0:
        return None
    bar = candles[index]
    price = bar.close

    readings: list[RangeReading] = []
    absent: list[str] = []
    for name in ANCHORS:
        window = _window(name, parent, bar.time)
        if window is None:
            absent.append(f"{name}: no {parent} cycle in the grid for this bar")
            continue

        start, close = window
        inside = _bars(candles, start, min(close, bar.time + 1))
        if not inside:
            absent.append(f"{name}: no bars in the window {start}..{close}")
            continue

        high = max(c.high for c in inside)
        low = min(c.low for c in inside)
        if high <= low:
            absent.append(f"{name}: the window {start}..{close} has no height")
            continue

        equilibrium = (high + low) / 2.0
        readings.append(
            RangeReading(
                anchor=name,
                degree=parent,
                time_from=start,
                time_to=inside[-1].time,
                complete=bar.time >= close,
                bars=len(inside),
                high=high,
                low=low,
                equilibrium=equilibrium,
                position=round((price - low) / (high - low), 4),
                reading=(
                    "discount"
                    if price < equilibrium
                    else "premium" if price > equilibrium else "equilibrium"
                ),
            )
        )

    return PremiumDiscount(
        degree=degree,
        anchor=anchor,
        at=bar.time,
        price=price,
        chosen=next((r for r in readings if r.anchor == anchor), None),
        readings=tuple(readings),
        absent=tuple(absent),
        disagree=len({r.reading for r in readings}) > 1,
    )


def _taken(after: list[Candle], price: float, above: bool) -> int | None:
    """Open time of the FIRST bar to trade through `price`, or None if it stands.

    Strictly through: an equal high touches the level without taking it, which
    matters because the session's own bar made that high in the first place.
    """
    return next(
        (c.time for c in after if (c.high > price if above else c.low < price)), None
    )


def liquidity_pools(
    candles: list[Candle], sessions: Sequence[str] = ("asia", "london")
) -> list[Pool]:
    """The high and low of each named session, and whether price has been through.

    Two pools per session that had bars: BSL at the high, SSL at the low. In time
    order, oldest window first.

    A session produces NOTHING when its window holds no bars, and nothing until a
    bar exists at or after the window's end to prove the session closed. A session
    whose bars only partly cover the window still produces its pools, with
    `covered` False - see the module docstring, and the coverage fields.

    An untaken pool is a candidate target. It is not a forecast that price will
    reach it, and nothing here has been measured against outcomes.
    """
    for name in sessions:
        if name not in SESSIONS:
            raise ValueError(
                f"unknown session {name!r}, expected one of {tuple(SESSIONS)}"
            )
    if not candles:
        return []

    step = _step(candles)
    last_day = clock.to_ny(candles[-1].time).date()
    out: list[Pool] = []

    for name in sessions:
        open_hour, close_hour, close_days = SESSIONS[name]
        day = clock.to_ny(candles[0].time).date()
        while day <= last_day:
            shuts = day + timedelta(days=close_days)
            start = clock.ny_wall(day.year, day.month, day.day, open_hour)
            close = clock.ny_wall(shuts.year, shuts.month, shuts.day, close_hour)
            day += timedelta(days=1)

            inside = _bars(candles, start, close)
            after = _bars(candles, close, candles[-1].time + 1)
            if not inside or not after:
                continue

            high = max(c.high for c in inside)
            low = min(c.low for c in inside)
            covered = (
                inside[0].time - start < step and inside[-1].time + step >= close
            )
            # Spelled out rather than built in a loop over strings, so the two
            # side names stay the narrowed Literal the dataclass declares.
            both: tuple[tuple[Literal["BSL", "SSL"], float], ...] = (
                ("BSL", high),
                ("SSL", low),
            )
            for side, price in both:
                out.append(
                    Pool(
                        session=name,
                        side=side,
                        price=price,
                        window_from=start,
                        window_to=close,
                        first_bar=inside[0].time,
                        last_bar=inside[-1].time,
                        bars=len(inside),
                        covered=covered,
                        knowable_at=after[0].time,
                        taken_at=_taken(after, price, side == "BSL"),
                    )
                )

    return sorted(out, key=lambda p: (p.window_from, p.session, p.side))


def zone_targets(zones: Sequence[Zone]) -> list[ZoneTarget]:
    """Every given zone as a candidate target, keeping its own touch record.

    `taken_at is None` is the untouched set - the zones that can still be
    reached, so a fair value gap reads as a target the same way a session high
    does. Touched zones are kept for the same reason taken pools are: a target
    that has already been visited is a fact about the chart, not noise to drop.

    Reads the zones it is given and computes no geometry. No detector is invoked
    here, so nothing in this list can disagree with the boxes that were drawn.
    """
    return [
        ZoneTarget(
            zone_id=zone.id,
            kind=zone.kind.value,
            side=zone.side.value,
            state=zone.state.value,
            price=zone.proximal,
            formed_at=zone.time_from,
            taken_at=zone.first_test_time,
        )
        for zone in zones
    ]
