"""The named horizontal levels the engine still lacked: previous-period
extremes, the two sides of a dealing range, and the untaken liquidity sitting on
each side of price.

Same family as `pools.py` and deliberately the same shape, because a reviewer
will read the two side by side. A level here is a price some window or some
swing made, plus the record of whether price has been through it: `knowable_at`
is the bar it could first be drawn on, `taken_at` is the FIRST bar that traded
strictly through it, and a taken level is still reported because "yesterday's
high already got taken" is the fact that kills a trade idea. Nothing here says
which way price will go, and nothing here has been measured against outcomes.

================================================================================
PART ONE. PREVIOUS-PERIOD EXTREMES, AND THE BOUNDARY THAT DECIDES THEM.

  PDH / PDL          previous day high and low
  PWH / PWL          previous week high and low
  FRI H / FRI L      the same day window, named separately
  MON H / MON L      the same day window, named separately

Friday and Monday are day windows under a different name rather than a different
measurement. They are named apart because the owner names them apart - they
carry their own meaning in his week profile - so asking for `("day", "friday")`
returns the Friday window TWICE, once as PDH/PDL and once as FRI H / FRI L.
That duplication is the point; it is not deduplicated behind the reader's back.

THE BOUNDARY IS A CHOICE AND IT CHANGES THE NUMBER. This is the whole trap of
this module, so it is a parameter, the default is stated as a judgement, and
EVERY object carries the `boundary` it was measured under:

  cycle      DEFAULT. The day runs 18:00 New York to 18:00 New York, and the
             cycle is labelled by the calendar date it ENDS on - 18:00 Monday
             opens Tuesday's cycle, exactly as `quarters.py` has it. The week
             runs Sunday 18:00 to Sunday 18:00. Chosen because it is the grid
             the rest of this engine already draws: `quarters.py`, its true
             opens and `pools.premium_discount` all measure the day cycle from
             18:00, and 18:00 New York is the CME open, so a PDH measured any
             other way is the high of no cycle this engine draws.
  midnight   The day runs 00:00 to 00:00 New York and the week Monday 00:00 to
             Monday 00:00. This is how a calendar day reads, and it is what most
             charting platforms outside the futures session show.

A previous-day high measured 18:00-to-18:00 is a DIFFERENT NUMBER from one
measured midnight-to-midnight, not a rounding of it: an evening spike between
18:00 and 00:00 belongs to tomorrow's cycle under one rule and to today under
the other, so the two readings can disagree about the level AND about which day
owns it. tests/test_liquidity.py asserts that disagreement directly on one hand
built series, because a reader who is not shown it will assume the two agree.

Both boundaries are New York wall clock. No timezone arithmetic happens here;
every edge comes from `app/clock.py`, which is DST-aware, so a period is 23 or
25 hours on the two transition days and the edges stay nailed to the wall clock.

================================================================================
PART TWO. ERL AND IRL, EXTERNAL AND INTERNAL RANGE LIQUIDITY.

Given a dealing range - the last confirmed swing high and the last confirmed
swing low as of a bar, which is the range `app/dealing_range.py` reads its
premium/discount position against - external range liquidity is what rests
OUTSIDE the range at its extremes, and internal range liquidity is what sits
INSIDE it: the unfilled inefficiencies. The procedure alternates between them.

The range is built from `detect.structure.swings` at `swing_n` on both sides,
the same primitive and the same default width `dealing_range.mark_dealing_range`
uses, so the range behind these levels and the range behind `dealing_range_pos`
cannot drift apart. Only swings whose `confirmed_at` is at or before the bar
being read are eligible, and the range's `knowable_at` is the LATER of the two
confirmations - a swing high at bar i is not knowable at bar i.

The internal side takes already-detected zones as an ARGUMENT. No detector is
imported and none is run: a zone's own `first_test_time` is its touch record, so
this pass cannot disagree with the boxes the engine drew, which is the same rule
`pools.zone_targets` follows.

================================================================================
PART THREE. DOL, DRAW ON LIQUIDITY - AND WHAT IS DELIBERATELY NOT HERE.

A draw on liquidity names where price is going, which makes it a FORECAST. This
project has had twelve pre-registered directional hypotheses fail, market
structure three times, so this module does not pick one level and call it the
draw. `dol_candidates` reports the untaken liquidity ABOVE and the untaken
liquidity BELOW with their distances, and there is no field called draw, target
or bias for either list to be read as.

THE SYMMETRY IS THE POINT. On any normal bar both lists are populated: there is
untaken liquidity above price and untaken liquidity below it at all times, and a
procedure that "identifies the draw" is choosing between two sets that both
always exist. NOTHING IN THIS PROJECT HAS MEASURED WHICH OF THE TWO PRICE
ACTUALLY REACHES, or reaches first, or reaches more often than a coin. The
distances are geometry. They are not evidence, and the ordering of a list is
nearness in price and nothing else.

INDUCEMENT IS NOT SHIPPED, and that absence is the finding rather than a gap.
An inducement is a high or low placed so that it will be taken BEFORE the real
move, which means identifying one requires knowing what the move afterwards was.
A retrospective label with `knowable_at` set to the bar it became identifiable on
would have been acceptable, and it was designed before being dropped, for two
reasons that are both about the definition rather than about effort:

  1. Every candidate definition needs a WINDOW - how long after the level was
     taken the "real move" is allowed to arrive - and no source publishes one.
     Left unbounded the label is trivially true of almost every swept level,
     because price eventually goes the other way from everywhere, so the field
     would measure nothing while looking like a reading. Any bounded value is a
     number this project invented, and invented gates here get measured before
     they get shipped, not after.
  2. The narrowest definition that needs no invented number - liquidity taken,
     then structure giving way the other way - is an object the engine ALREADY
     emits: `StructureEvent` of kind MSS carries `swept_at`, the level that was
     taken before the break. A second object over the same event is how two
     parts of an engine come to disagree about the same bar.

And the fact that survives both: it is identifiable only at the break that comes
after the take, so it is NEVER available at decision time. An honest absence
beats a field that quietly reads the future, and this repo has caught lookahead
in its own code before.

================================================================================
HOUSE RULES, all asserted in tests/test_liquidity.py:

NO BAR, NO OBJECT. A window with no bars in it - a holiday, a feed that starts
mid-period - produces NOTHING. The window is never widened to find a bar and no
price is interpolated or carried forward, the same rule `quarters.true_opens`,
`pools.liquidity_pools` and `Candle.spread` follow: absent means not measured.

ANTI-LOOKAHEAD. A period's extreme is knowable only once that period has CLOSED,
and the proof is readable from the data alone: a bar opening at or after the
window's end cannot exist until the window's last bar has closed. That bar's
open time is `knowable_at`, and a period with no such bar yet produces no level
at all rather than a provisional one. `taken_at` is the FIRST bar that traded
through, never a later one, and `dol_candidates` drops a level whose
`knowable_at` is after the bar being read.

STRICTLY THROUGH, NEVER A TOUCH. An equal high touches a level without taking
it. Imported from `pools` rather than restated, along with the bar slicing and
the modal bar step: a second copy of the take rule is exactly how two files come
to disagree about whether a level is still standing.

COVERAGE IS TWO NUMBERS HERE, NOT A FLAG, and this is the one place the shape
departs from `pools.py`. Its `covered` asks for a bar within one step of each
edge, which is right for a session sitting inside a trading day and wrong for
every window whose edge lands on a market CLOSURE - and both of these windows
close on one. Measured on three weeks of 15-minute bars shaped like a gold
trading week (Sunday 18:00 open, the 17:00-to-18:00 daily break, Friday 17:00
close): all 14 day cycles end with 3600 unbarred seconds at the close, because
18:00 falls on the far side of the maintenance break, and both week cycles end
with 176.400 - the 49 hours from Friday 17:00 to Sunday 18:00. That flag would
therefore have read False on 14 of 14 correct PDHs and on 2 of 2 correct PWHs,
and a flag that is False on everything is a bug rather than a reading, which this
project has already shipped once and had to correct (see `pools._step`). So
`gap_at_open` and `gap_at_close` are reported as seconds, 0 when the bars reach
the edge, and the reader decides what a closure is worth rather than being handed
a verdict that cannot tell a closed market from a short feed. The figures are
pinned in tests/test_liquidity.py so the reasoning cannot rot.

NO DIRECTION CLAIM. Every level here is a price that exists and a record of
whether price has been through it. There is no field that ranks, scores or
forecasts anything, and none of these objects has been measured against outcomes.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import numpy as np

from . import clock
from .dealing_range import DISCOUNT_TO, PREMIUM_FROM
from .detect.structure import Swing, swings
from .indicators import wilder_atr
from .models import Candle, Zone

# Imported rather than restated. `_taken` is the strict-pierce rule (an equal
# high is a touch), `_step` is the modal bar interval that one stray timestamp
# cannot outvote, and `_bars` is the half-open slice. All three are decisions
# `pools.py` already made and documented; a second copy here would be a second
# opinion, which is the failure this engine keeps catching in itself.
from .pools import Pool, _bars, _step, _taken

BOUNDARIES = ("cycle", "midnight")
PERIODS = ("day", "week", "friday", "monday")

# (high name, low name) per period. Spelled out rather than derived, because
# these are the owner's own names and PDH is not "day high".
#
# EVERY NAME HERE FITS THE CANVAS LABEL COLUMN, and that is a hard constraint
# rather than a preference. The column is `LABEL_GUTTER` wide - 46px in
# `frontend/src/components/structure-primitive.ts` - and the ray label is drawn
# left-aligned from it with no clamp, so a wider name is simply cut off by the
# edge of the canvas. Silently: nothing warns, nothing logs.
#
# These were `FRIDAY_HIGH`, `FRIDAY_LOW`, `MONDAY_HIGH` and `MONDAY_LOW`, at 10
# and 11 characters against a budget of 8, and they had been shipping truncated
# on every chart where a reader selected the friday or monday period. Measured at
# the real font - 10px ui-monospace, whose advance is exactly 5.5px per character
# - `FRIDAY_HIGH` needs 60.5px of a 44px column. `test_liquidity.py` now pins the
# budget so the next name cannot repeat it.
NAMES: dict[str, tuple[str, str]] = {
    "day": ("PDH", "PDL"),
    "week": ("PWH", "PWL"),
    "friday": ("FRI H", "FRI L"),
    "monday": ("MON H", "MON L"),
}


@dataclass(frozen=True)
class Level:
    """One named price, and whether price has been through it.

    The common currency of this module: a period extreme, a range extreme and a
    zone resting inside a range are all one of these, which is what lets
    `dol_candidates` take them in one list without knowing where each came from.
    """

    name: str
    price: float
    knowable_at: int  # first bar this level could be drawn on
    taken_at: int | None  # first bar that traded strictly through, else None


@dataclass(frozen=True)
class PeriodLevel(Level):
    """A previous-period extreme, with the boundary it was measured under.

    `boundary` is on every object on purpose: the same series measured 18:00 to
    18:00 and midnight to midnight gives DIFFERENT numbers, so a level that did
    not say which rule produced it would be unusable.
    """

    period: str  # day, week, friday or monday
    side: Literal["BSL", "SSL"]  # buy-side at the high, sell-side at the low
    boundary: str  # cycle (18:00) or midnight - see the module docstring
    window_from: int  # period open, New York wall clock, inclusive
    window_to: int  # period close, exclusive
    first_bar: int  # open time of the first bar actually inside the window
    last_bar: int
    bars: int
    # Unbarred window, in seconds, at each edge: from the window open to the
    # first bar's open, and from the last bar's CLOSE (its open plus the feed's
    # modal step) to the window close. 0 at an edge the bars reach. A positive
    # value at a market closure is normal - see the module docstring.
    gap_at_open: int
    gap_at_close: int


@dataclass(frozen=True)
class RangeLiquidity:
    """A dealing range, the liquidity outside it and the zones inside it.

    `external` is ERL: the two range extremes. `internal` is IRL: the zones
    handed in that rest strictly between them. Neither list is ranked.
    """

    at: int  # open time of the bar the range was read on
    high: float
    low: float
    high_time: int  # open time of the bar that made the swing high
    low_time: int
    knowable_at: int  # the LATER of the two swings' confirmations
    external: tuple[Level, ...]
    internal: tuple[Level, ...]


@dataclass(frozen=True)
class Candidate:
    """One untaken level, and how far price is from it. Not a forecast."""

    name: str
    price: float
    distance: float  # absolute distance from the reading price, price units
    knowable_at: int


@dataclass(frozen=True)
class LiquidityCandidates:
    """The untaken liquidity above price and below it, read at one bar.

    Both lists, always. See PART THREE of the module docstring: naming one of
    them the draw would be a forecast, and nothing here has measured which one
    price reaches.
    """

    at: int
    price: float
    above: tuple[Candidate, ...]  # nearest first
    below: tuple[Candidate, ...]  # nearest first


def _day_window(boundary: str, day: date) -> tuple[int, int]:
    """[open, close) of the day cycle LABELLED `day`, on the New York clock.

    Under `cycle` that is the previous evening's 18:00 to this date's 18:00,
    which is the labelling `quarters.py` uses: 18:00 Monday opens Tuesday.
    """
    if boundary == "cycle":
        before = day - timedelta(days=1)
        return (
            clock.ny_wall(before.year, before.month, before.day, 18),
            clock.ny_wall(day.year, day.month, day.day, 18),
        )
    after = day + timedelta(days=1)
    return (
        clock.ny_wall(day.year, day.month, day.day),
        clock.ny_wall(after.year, after.month, after.day),
    )


def _week_window(boundary: str, monday: date) -> tuple[int, int]:
    """[open, close) of the week cycle whose Monday is `monday`.

    Seven whole days either way, built from the day windows so the two
    boundaries cannot drift apart: the week opens where its Monday opens and
    closes where the next Monday opens.
    """
    return _day_window(boundary, monday)[0], _day_window(
        boundary, monday + timedelta(days=7)
    )[0]


def previous_period_levels(
    candles: list[Candle],
    periods: Sequence[str] = ("day", "week"),
    boundary: str = "cycle",
) -> list[PeriodLevel]:
    """The high and low of each completed period, and whether price went through.

    Two levels per period that had bars: BSL at the high, SSL at the low, in time
    order with the oldest window first. Each is the PREVIOUS period's extreme for
    any bar after its `window_to`, which is why the window edges are on the
    object rather than the word "previous" being trusted.

    `boundary` decides everything and is reported on every level: `cycle` runs
    the day 18:00 to 18:00 New York and the week Sunday 18:00 to Sunday 18:00,
    `midnight` runs both from 00:00. The two give DIFFERENT numbers on the same
    series - see the module docstring - and the default is a judgement about
    matching the grid this engine already draws, not a citation.

    `friday` and `monday` are day windows under their own names, so requesting
    them beside `day` reports those windows twice on purpose.

    A period produces NOTHING when its window holds no bars, and nothing until a
    bar exists at or after the window's end to prove the period closed. A period
    the feed only partly covers still produces its levels - dropping them would
    hide the bars that do exist - with `gap_at_open` and `gap_at_close` saying in
    seconds how much of the window had no bars in it.

    An untaken level is a price that has not been traded through. It is not a
    forecast that price will reach it, and nothing here has been measured against
    outcomes.
    """
    for name in periods:
        if name not in PERIODS:
            raise ValueError(f"unknown period {name!r}, expected one of {PERIODS}")
    if boundary not in BOUNDARIES:
        raise ValueError(f"unknown boundary {boundary!r}, expected one of {BOUNDARIES}")
    if not candles:
        return []

    step = _step(candles)
    last_day = clock.to_ny(candles[-1].time).date()
    out: list[PeriodLevel] = []

    # Starts a week early so a period the feed opens in the middle of is still
    # measured and reported as partial, rather than vanishing because its Monday
    # fell before the first bar.
    day = clock.to_ny(candles[0].time).date() - timedelta(days=7)
    while day <= last_day:
        for period in periods:
            if period in ("week", "monday") and day.weekday() != 0:
                continue
            if period == "friday" and day.weekday() != 4:
                continue

            start, close = (
                _week_window(boundary, day)
                if period == "week"
                else _day_window(boundary, day)
            )
            inside = _bars(candles, start, close)
            after = _bars(candles, close, candles[-1].time + 1)
            if not inside or not after:
                continue

            high = max(c.high for c in inside)
            low = min(c.low for c in inside)
            high_name, low_name = NAMES[period]
            # Spelled out rather than built in a loop over strings, so the two
            # side names stay the narrowed Literal the dataclass declares - the
            # same reason `pools.liquidity_pools` writes them out.
            both: tuple[tuple[Literal["BSL", "SSL"], float, str], ...] = (
                ("BSL", high, high_name),
                ("SSL", low, low_name),
            )
            for side, price, name in both:
                out.append(
                    PeriodLevel(
                        name=name,
                        price=price,
                        knowable_at=after[0].time,
                        taken_at=_taken(after, price, side == "BSL"),
                        period=period,
                        side=side,
                        boundary=boundary,
                        window_from=start,
                        window_to=close,
                        first_bar=inside[0].time,
                        last_bar=inside[-1].time,
                        bars=len(inside),
                        gap_at_open=max(0, inside[0].time - start),
                        gap_at_close=max(0, close - inside[-1].time - step),
                    )
                )
        day += timedelta(days=1)

    return sorted(out, key=lambda level: (level.window_from, level.period, level.side))


def range_liquidity(
    candles: list[Candle],
    zones: Sequence[Zone] = (),
    at: int | None = None,
    swing_n: int = 50,
) -> RangeLiquidity | None:
    """The dealing range at one bar, its external liquidity and its internal.

    ERL is the range's own two extremes, the liquidity resting outside it: the
    swing high is buy-side, the swing low sell-side, and each carries the first
    bar that traded strictly through it or None while it stands.

    IRL is the zones YOU pass in whose proximal line rests strictly between the
    two extremes - the unfilled inefficiencies inside the range. No detector is
    imported or run here and no geometry is recomputed: a zone keeps its own
    `first_test_time` as its `taken_at`, so this list cannot disagree with the
    boxes the engine drew. A zone's `knowable_at` is the later of the range's
    confirmation and the zone's own left edge, and that left edge is its BASE
    OPEN rather than the bar a detector could have drawn it on - this module did
    not draw it and will not claim to know, so a caller who needs a strict answer
    must pass only the zones it was entitled to have at `at`.

    `at` is the bar to read, defaulting to the last one. `swing_n` is the fractal
    width on both sides and defaults to 50 to match
    `dealing_range.mark_dealing_range` and `StructureParams.swing_n`; no primary
    source publishes an N, and it is stated here as a choice.

    None when there are no bars, when `at` precedes the series, when either side
    of the range has not confirmed yet, or when the two prices leave no height.
    Never a substituted range: an invented one is indistinguishable from a
    measured one.
    """
    if not candles:
        return None

    when = candles[-1].time if at is None else at
    index = bisect_right(candles, when, key=lambda c: c.time) - 1
    if index < 0:
        return None

    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    # `swings` returns them ordered by `confirmed_at`, so walking until one
    # confirms after this bar leaves the last pair that was knowable here. A
    # swing high at bar i is not knowable at i, and reading one that confirmed
    # later would build the range out of hindsight.
    top = bottom = None
    for swing in swings(high, low, swing_n, swing_n):
        if swing.confirmed_at > index:
            break
        if swing.high:
            top = swing
        else:
            bottom = swing
    if top is None or bottom is None or top.price <= bottom.price:
        return None

    # Each extreme is scanned from ITS OWN confirmation, not from the range's.
    # The two swings confirm at different bars, and scanning both from the later
    # one would skip the bars in between and report a level as standing that had
    # already been taken there.
    knowable_at = candles[max(top.confirmed_at, bottom.confirmed_at)].time
    external = (
        Level(
            name="RNG H",
            price=top.price,
            knowable_at=candles[top.confirmed_at].time,
            taken_at=_taken(candles[top.confirmed_at : index + 1], top.price, True),
        ),
        Level(
            name="RNG L",
            price=bottom.price,
            knowable_at=candles[bottom.confirmed_at].time,
            taken_at=_taken(
                candles[bottom.confirmed_at : index + 1], bottom.price, False
            ),
        ),
    )
    internal = tuple(
        Level(
            # The zone's KIND, not its id. This was `zone.id`, which reads
            # `DBD-1787015700-4487.39990` - fine while nothing rendered these,
            # and obviously a bug the moment the liquidity panel put them on
            # screen beside `PDH` and `RNG H`. A name is a name; the
            # identity is already carried by the zone itself in `drawing.zones`,
            # and the price locates it there unambiguously.
            name=zone.kind.value,
            price=zone.proximal,
            knowable_at=max(knowable_at, zone.time_from),
            taken_at=zone.first_test_time,
        )
        for zone in zones
        if zone.time_from <= when and bottom.price < zone.proximal < top.price
    )

    return RangeLiquidity(
        at=candles[index].time,
        high=top.price,
        low=bottom.price,
        high_time=candles[top.index].time,
        low_time=candles[bottom.index].time,
        knowable_at=knowable_at,
        external=external,
        internal=internal,
    )


def range_frame(found: RangeLiquidity) -> tuple[Level, ...]:
    """The dealing range's own three derived lines: equilibrium and both quartiles.

    THE FRAME WAS COMPUTED AND NEVER DRAWN, and that was the largest drawing gap
    in the engine. `range_liquidity` above has returned a correct, anti-lookahead
    dealing range for a long time, `dealing_range.mark_dealing_range` stamps every
    box with its position inside it, and the zone panel prints that position as a
    percentage - but the range itself reached no canvas. It went to a side panel as
    two numbers. Premium and discount is the most-used framing in this method:
    across the 51 reference charts a dashed 50% line inside a range appears on 36,
    and one of them draws the 0.25 / 0.5 / 0.75 ladder explicitly.
    The reader could not see the frame their zones were being judged against.

    THE THRESHOLDS ARE IMPORTED FROM `dealing_range.py`, which is what makes this
    a calibration rather than a decoration: the 0.75 line drawn here is the SAME
    constant `deduce.py` tests `range_pos` against, so the boundary on screen and
    the boundary in the verdict cannot drift apart.

    `knowable_at` is the range's own - the LATER of the two swing confirmations -
    for all three. A derived line is knowable exactly when both extremes are, not
    when the arithmetic could first be performed on one of them.

    `taken_at` is None on all three and that is deliberate rather than missing. An
    equilibrium is not resting liquidity; there is no order there to be taken, so
    "price traded through the midpoint" is not the same event as "the previous day
    high got swept". Marking them taken would fade the frame the moment price
    crossed it, which is precisely when a reader needs it.
    """
    height = found.high - found.low
    return (
        Level(
            name="EQ 50",
            price=found.low + height / 2,
            knowable_at=found.knowable_at,
            taken_at=None,
        ),
        Level(
            name=f"PREM {PREMIUM_FROM * 100:.0f}",
            price=found.low + height * PREMIUM_FROM,
            knowable_at=found.knowable_at,
            taken_at=None,
        ),
        Level(
            name=f"DISC {DISCOUNT_TO * 100:.0f}",
            price=found.low + height * DISCOUNT_TO,
            knowable_at=found.knowable_at,
            taken_at=None,
        ),
    )


def pool_levels(pools: Sequence[Pool]) -> list[Level]:
    """Session pools as levels, so they can be fed to `dol_candidates` too.

    A rename and nothing else: every decision - the window, the strict pierce,
    the session that closed - was made in `pools.py` and is carried across
    untouched.
    """
    return [
        Level(
            name=f"{pool.session} {pool.side}",
            price=pool.price,
            knowable_at=pool.knowable_at,
            taken_at=pool.taken_at,
        )
        for pool in pools
    ]


def dol_candidates(
    levels: Sequence[Level], price: float, at: int
) -> LiquidityCandidates:
    """The untaken liquidity above `price` and below it, as of bar `at`.

    THIS IS NOT A DRAW ON LIQUIDITY AND MUST NOT BE READ AS ONE. A draw names
    where price is going, which is a forecast, and this project has had twelve
    pre-registered directional hypotheses fail. So both sides are reported and
    neither is chosen: `above` and `below`, nearest first, with the distance in
    price units. There is no field here called draw, target or bias.

    THE SYMMETRY IS THE POINT. On any normal bar both lists are populated -
    there is untaken liquidity above price and untaken liquidity below it at all
    times - so "identifying the draw" is choosing between two sets that both
    always exist. NOTHING IN THIS PROJECT HAS MEASURED WHICH OF THE TWO PRICE
    ACTUALLY REACHES, or reaches first, or reaches more often than a coin. The
    ordering is nearness in price and is not a ranking of anything else.

    A level counts as a candidate only if it was knowable at or before `at` and
    was not already taken at or before `at`. A level taken LATER still stands
    here, because at `at` it had not been taken yet - reading its future
    `taken_at` as if it were the present is the lookahead this rule exists to
    prevent. Levels exactly at `price` belong to neither side and are dropped.
    """
    standing = [
        level
        for level in levels
        if level.knowable_at <= at and (level.taken_at is None or level.taken_at > at)
    ]

    def candidates(above: bool) -> tuple[Candidate, ...]:
        picked = [
            Candidate(
                name=level.name,
                price=level.price,
                distance=abs(level.price - price),
                knowable_at=level.knowable_at,
            )
            for level in standing
            if (level.price > price if above else level.price < price)
        ]
        return tuple(sorted(picked, key=lambda c: (c.distance, c.name)))

    return LiquidityCandidates(
        at=at, price=price, above=candidates(True), below=candidates(False)
    )


# ==============================================================================
# PART FOUR. RELATIVE EQUAL HIGHS AND LOWS.
#
# Two or more swings that printed at ALMOST the same price. The shelf they make
# is where stops rest, and the practitioner rule this engine already quotes names
# them beside the objects it does draw: "FVG/OB/REQL/REQH/CISD semuanya harus
# dalam premium kalo mau sell, harus dalam discount kalo mau buy" - see
# `models/cycle.py`. So the checklist has been asking for an object nothing drew.
#
# THE TOLERANCE IS ATR-RELATIVE, and the alternative was measured and rejected.
# A survey of the open-source implementations found exactly two rules in
# circulation:
#
#   0.1 x ATR(200)                     scale-free, moves with volatility
#   0.01 x (dataset high - dataset low) a fraction of the LOADED WINDOW
#
# The second is unshippable here whatever its merits, and not because it is
# wrong on average: it makes the tolerance a function of how many bars the reader
# happened to load. Change the Bars picker from 500 to 5000 and the same two
# swings stop being equal, or start being equal, with no candle having moved.
# That is the prefix dependence `test_no_repaint.py` exists to forbid, and it
# would be invisible - both charts look correct.
#
# WHAT IS NOT CLAIMED. Nothing here has been measured against outcomes. This is
# fidelity, the same footing `detect.structure` ships on: the method reads these
# shelves, so a chart that cannot show one cannot show the method, and that is
# the whole argument for drawing it. It carries no direction, and there is no
# score field for one to be read as.
# ==============================================================================

#: Fraction of ATR inside which two swings count as the same price.
#:
#: 0.1 x ATR is the figure the surveyed implementations use, adopted rather than
#: invented - and adopted with its provenance stated, because nothing in this
#: project has measured whether 0.1 separates shelves that matter from shelves
#: that do not. A reader who wants it tighter or looser has the slider.
EQUAL_ATR = 0.1

#: ATR window behind the tolerance. Long on purpose: the tolerance should describe
#: the instrument's normal range rather than this week's, or a quiet fortnight
#: would fuse shelves that a busy one keeps apart.
EQUAL_ATR_PERIOD = 200

#: How many same-side swings back a shelf will still accept a new member.
#:
#: A JUDGEMENT, and no source publishes one. Without a bound a level revisited a
#: year later joins the same shelf: the geometry stays still, so it is not a
#: repaint, but the touch count stops describing resting liquidity and starts
#: describing how much history the reader loaded. Ten same-side swings is roughly
#: a session to a few days at the shipped fractal width.
EQUAL_LOOKBACK = 10


def equal_levels(
    candles: list[Candle],
    swing_n: int = 50,
    tolerance_atr: float = EQUAL_ATR,
    min_touches: int = 2,
) -> list[Level]:
    """Shelves of near-equal swing highs and lows, oldest first.

    A shelf is a CLUSTER of same-side swings whose prices all sit within
    `tolerance_atr` ATR of the first one, and cluster rather than consecutive RUN
    is the whole correctness of this function. The first version grouped
    consecutive swings and broke a run the moment one fell outside the band, which
    misses the ordinary case: highs at 100.00, then a lower high at 95.00, then
    100.05. A reader sees one two-touch shelf at 100; that version found NOTHING,
    proved on a constructed series before this was rewritten.

    Anchoring to the FIRST member rather than to the running mean is what keeps
    the drawn price still: a mean moves every time another swing joins, which
    would be a line sliding under the reader as bars arrive.

    The band is the ANCHOR's ATR, not the joining swing's, so a pair is judged the
    same way whenever it is evaluated and the shelf's tolerance is fixed at birth.

    The count MAY grow after the level is drawn, and that is allowed under the same
    rule a zone's lifecycle advances by: nothing already drawn moves. Price, left
    edge and side are fixed at birth; only the touch count and `taken_at` change,
    and both only ever move forward.

    `knowable_at` is the LATER of the first `min_touches` confirmations - a shelf
    is not a shelf until its second member has confirmed. Same rule the dealing
    range follows, and stated for the same reason: a swing high at bar i is not
    knowable at i.

    Empty when there are too few bars for the ATR window to mean anything. Never a
    substituted tolerance: a shelf found with an invented threshold is
    indistinguishable from one found with a measured one.
    """
    if len(candles) < EQUAL_ATR_PERIOD + swing_n * 2 + 2:
        return []

    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, EQUAL_ATR_PERIOD)

    # Time order, not confirmation order: a shelf is a set of swings at one price
    # and the FIRST of them anchors it, so which one is first has to mean first in
    # time. `swings` returns them sorted by `confirmed_at`, which is the same order
    # only while the two fractal widths are equal - and this must not depend on
    # that.
    found = sorted(swings(high, low, swing_n, swing_n), key=lambda s: s.index)

    out: list[Level] = []
    for is_high in (True, False):
        side = [s for s in found if s.high is is_high]
        # (anchor swing, members, position of the last member in `side`)
        clusters: list[tuple[Swing, list[Swing], int]] = []
        for position, swing in enumerate(side):
            joined = False
            # Newest cluster first, so a swing joins the most recent shelf it fits
            # rather than the oldest one that happens to be at the same price.
            for index in range(len(clusters) - 1, -1, -1):
                anchor, members, last = clusters[index]
                if position - last > EQUAL_LOOKBACK:
                    continue
                if abs(swing.price - anchor.price) <= atr[anchor.index] * tolerance_atr:
                    members.append(swing)
                    clusters[index] = (anchor, members, position)
                    joined = True
                    break
            if not joined:
                clusters.append((swing, [swing], position))

        for anchor, members, _ in clusters:
            out.extend(_shelf(anchor, members, candles, is_high, min_touches))

    return sorted(out, key=lambda level: level.knowable_at)


def _shelf(
    anchor: Swing,
    members: list[Swing],
    candles: list[Candle],
    is_high: bool,
    min_touches: int,
) -> list[Level]:
    """One cluster as a level, or nothing if it never reached `min_touches`.

    A single swing is not a shelf; it is a swing, and `detect.structure` already
    draws those. The name carries the touch count because a five-touch shelf and a
    two-touch shelf are different amounts of resting liquidity, and CLAMPED at two
    digits because the canvas label column holds eight characters - `REQH 99+` is
    exactly eight and `REQH 100x` would be silently cut in half. That budget is not
    a guess: `test_every_level_name_fits_the_canvas_label_column` reads
    `LABEL_GUTTER` out of the TypeScript and fails if a name outgrows it.
    """
    if len(members) < min_touches:
        return []

    # The LATER confirmation of the first `min_touches`, so the shelf is not
    # knowable before the member that proved it was one.
    confirmed = max(s.confirmed_at for s in members[:min_touches])
    if confirmed >= len(candles):
        return []
    touches = len(members)
    count = f"{touches}x" if touches < 100 else "99+"
    return [
        Level(
            name=f"{'REQH' if is_high else 'REQL'} {count}",
            price=anchor.price,
            knowable_at=candles[confirmed].time,
            taken_at=_taken(candles[confirmed:], anchor.price, is_high),
        )
    ]
