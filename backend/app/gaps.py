"""Opening gaps between one session's last price and the next session's first.

Two bands and one level, all three doctrine and none of them measured. There is
no disclosed study on opening gaps by anyone - the research pass found no
analogue to the two published fair-value-gap studies this repo already leans
on - so everything in this file is a drawing rule, and nothing here says which
way price goes next. Twelve pre-registered directional hypotheses have failed in
this project; this module reports WHERE bands and levels sit and stops there.

**NDOG, the new day opening gap.** The band between the last traded price of the
session ending at 17:00 New York and the first traded price of the session
opening at 18:00 New York. `top` is the higher of the two prices, `bottom` the
lower, `ce` their average - the consequent encroachment. Monday, Tuesday,
Wednesday and Thursday 18:00 opens only: Friday has no 18:00 open, and the gap
across the weekend is an NWOG rather than an NDOG.

**NWOG, the new week opening gap.** The same geometry across the weekend:
Friday's 17:00 close against the Sunday 18:00 open. This is the "actual" variant
and it is a CHOICE, made by the owner - it is also what every third-party
codification uses. ICT ships a second variant that measures Friday's close
against Monday 09:30, the New York equity open; that is the road not taken here
and it is deliberately not implemented. If it is ever wanted it is a second
`kind`, not an edit to this one.

**Bar size is part of the definition, not a detail.** ICT states the requirement
explicitly: read these off 1-minute or 5-minute bars, and never off a daily
chart, because a daily bar's close is the SETTLEMENT price and the settlement
price is a different number from the last price that actually traded before
17:00. Reading the band off dailies therefore produces a band whose edge nothing
ever traded at. This module cannot refuse the bars it is handed, so it does the
honest thing instead: it uses the last bar that opens BEFORE 17:00 and the first
bar that opens AT OR AFTER 18:00, and every gap carries `approximate`, which is
False only when the closing bar provably ends exactly at 17:00 and the opening
bar opens exactly at 18:00. Coarse bars get a gap with `approximate=True` rather
than a gap pretending to be exact. Anything that displays or measures these must
read that flag.

**EVENT HORIZON.** The average of one gap's top and the bottom of the next gap
up. Two things about it are easy to get wrong and both are settled here:

*It is a LEVEL - one price - not a band.* That is ICT's own reading and the
owner's choice. The name collides: the reference script the owner works from
(Tango618's, closed source) uses "event horizon" for the gap ZONE instead, and
on real gold data the two readings produced non-overlapping bands whose widths
differed nine times over. So the collision is real and this file is on the level
side of it. A caller that wants the zone reading wants the gap itself, which is
right there as `EventHorizon.lower` / `.upper`.

*Adjacency is in PRICE space, not time.* The gaps are sorted by their own
midpoint and each is paired with its neighbour above, so N retained gaps give
exactly N-1 levels and the pairing has nothing to do with which gap formed
first.

TWO PROPERTIES THAT WILL BITE ANYTHING BUILT ON TOP OF THIS:

1. **The level set is not stable under how many gaps you keep.** Dropping one
   gap does not shrink the level set by one edge case, it DELETES a level and
   re-pairs its neighbours. ICT says a minimum of four gaps and prefers five and
   caps the lookback at 60 days; a widely used third-party port keeps ten. Those
   are three different pictures of the same market. So the count is a parameter,
   `keep`, and its default of 5 is a stated choice - ICT's stated preference -
   and not a citation of a measured result, because there is no measured result.
   The 60-day cap is not a second parameter: five gaps span about a week and ten
   span about two, both far inside 60 days, so `keep` already bounds the window.

2. **This is the first object in this project whose value is NOT FIXED AT
   BIRTH.** Every zone elsewhere here is settled the moment it forms - its edges
   are prices that already printed and they never move again. An Event Horizon
   level is not: a new gap appearing between two existing ones re-sorts the
   pairing and MOVES a level that was already on the chart, without a single
   price changing. Every measurement harness in this repo assumes birth-settled
   objects, so any harness that touches these must ask for the level set as of a
   bar rather than as of now. `event_horizons(..., as_of=bar_time)` is that
   question; `tests/test_gaps.py` asserts the movement directly, because it is
   the property most likely to be forgotten.

House rules that show up as behaviour rather than as prose:

- **No bar, no object.** A boundary with no bar in its own session - a holiday,
  a feed that starts mid-week - produces nothing. Nothing is interpolated and no
  price is carried forward, for the same reason `Candle.spread` is None rather
  than 0 when unmeasured: absent means not measured, never zero.

MEASURED ON LIVE DATA, because two of these were checked rather than assumed:

*The 17:00 boundary is exclusive and that word is load-bearing.* COMEX gold on
Yahoo emits a bar that OPENS at 17:00 New York on a Friday, the hour the market
is shut. On 2026-08-14 it read C4437.30 while the 16:00 bar closed at 4432.10 and
the Sunday reopen printed 4433.70 - so "opens before 17:00" gives 4432.10..4433.70
and "opens at or before" gives 4433.70..4437.30. The two bands do not overlap and
the consequent encroachment moves 2.60 points. Nothing else in the suite would
catch a one-word change there: the count, the kinds and the anti-lookahead
property all survive it. `tests/test_gaps.py` pins it with those prices.

*Weekend reopens are clean; the volume field at a boundary is not.* Across 1500
hourly gold bars all 13 NWOGs opened on a bar with real volume, and the weekend
window held no bars at all on 16 of 17 weekends. But bars at these boundaries
frequently report volume 0 or 1 while carrying a full OHLC range - 2026-08-12
18:00 reported volume 0 across 13.8 points - and Yahoo's spot EURUSD reports 0
for EVERY bar it serves. So volume cannot be used to judge whether a gap edge is
trustworthy, on either feed, and this module deliberately does not try. An
earlier reading of these counts as "stub bars" was wrong, and the arithmetic that
seemed to support it was measuring how far gold moves in an hour.
- **Nothing is reported before it is knowable.** A gap is knowable when its
  second price prints, which is its 18:00 bar - so `knowable_at` is that bar's
  time, and a gap whose opening bar is not in the data does not exist yet. A
  level is knowable when the LATER of its two gaps is.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from itertools import combinations
from typing import Literal

from . import clock
from .models import Candle
from .quarters import quarters

# ICT prefers five. A choice, restated here so the number is not mistaken for a
# measurement - see property 1 in the module docstring.
KEEP_DEFAULT = 5

# Which 18:00 New York open starts which kind of gap, by NY weekday. Monday
# through Thursday evening are the four NDOGs; Sunday evening is the NWOG.
# Friday 18:00 opens nothing and Saturday has no session at all, so both are
# absent rather than mapped to a kind.
_KIND: dict[int, Literal["NDOG", "NWOG"]] = {
    0: "NDOG",
    1: "NDOG",
    2: "NDOG",
    3: "NDOG",
    6: "NWOG",
}


@dataclass(frozen=True)
class OpeningGap:
    """One session's last traded price against the next session's first."""

    kind: Literal["NDOG", "NWOG"]
    top: float
    bottom: float
    # Open time of the bar each price was read off, so the provenance of the
    # band is on the object rather than in the caller's head. `close_time` is
    # the bar whose CLOSE gave one edge, `open_time` the bar whose OPEN gave
    # the other.
    close_time: int
    open_time: int
    # False only when the closing bar provably ends at 17:00 and the opening bar
    # opens at 18:00. True says the band's edges are the nearest prices this
    # feed could offer, not the ones ICT's definition asks for.
    approximate: bool

    @property
    def ce(self) -> float:
        """Consequent encroachment: the midpoint of the band."""
        return (self.top + self.bottom) / 2

    @property
    def knowable_at(self) -> int:
        """When the second of the two prices printed. Nothing before this."""
        return self.open_time


@dataclass(frozen=True)
class EventHorizon:
    """One price: the average of `lower.top` and `upper.bottom`.

    A level, not a band - see the module docstring for the name collision. Both
    gaps are kept rather than just the number, because the number alone cannot
    say which two gaps produced it, and after a re-sort that is the first thing
    anyone will want to know.
    """

    price: float
    lower: OpeningGap  # the gap below in PRICE, not in time
    upper: OpeningGap

    @property
    def knowable_at(self) -> int:
        """The later of the two gaps: both must exist before the level does."""
        return max(self.lower.knowable_at, self.upper.knowable_at)


def _gap_at(
    candles: Sequence[Candle],
    times: Sequence[int],
    open_at: int,
    kind: Literal["NDOG", "NWOG"],
    stats: dict[str, int] | None = None,
) -> OpeningGap | None:
    """The gap whose 18:00 open is `open_at`, or None if either bar is missing.

    `stats`, when given, records WHY a boundary produced nothing, because the
    two reasons are not the same fact and a caller that sees only an empty list
    cannot tell them apart. `no_bars` is a hole in the window - ask for more
    history. `traded_through` is the market having been open across the
    boundary, which means there is no gap to draw and more history will not
    conjure one.
    """
    # The closing session for an NDOG ended at 17:00 the same day; for an NWOG it
    # ended at 17:00 on the Friday, two days before the Sunday open.
    close_off = 0 if kind == "NDOG" else -2
    close_at = clock.at_ny_hour(open_at, 17, days=close_off)
    # Both bars are bounded to their OWN session, which is what makes a holiday
    # return nothing instead of reaching backwards or forwards for a price that
    # belongs to some other day.
    close_from = clock.at_ny_hour(open_at, 18, days=close_off - 1)
    open_to = clock.at_ny_hour(open_at, 17, days=1)

    i_close = bisect_left(times, close_at) - 1  # last bar opening before 17:00
    if i_close < 0 or times[i_close] < close_from:
        if stats is not None:
            stats["no_bars"] = stats.get("no_bars", 0) + 1
        return None
    i_open = bisect_left(times, open_at)  # first bar opening at or after 18:00
    if i_open >= len(times) or times[i_open] >= open_to:
        if stats is not None:
            stats["no_bars"] = stats.get("no_bars", 0) + 1
        return None

    # Exactness has to be proven, not assumed. The closing bar's own width is
    # read off its predecessor - the bar AFTER it is the 18:00 bar, because no
    # bar trades between 17:00 and 18:00, so the step cannot be measured
    # forwards. A hole in the feed before the closing bar makes the inferred
    # step too wide and the gap reports approximate, which is the safe way to be
    # wrong here.
    step = times[i_close] - times[i_close - 1] if i_close > 0 else 0
    exact = (
        step > 0 and times[i_close] + step == close_at and times[i_open] == open_at
    )

    last = candles[i_close].close
    first = candles[i_open].open
    return OpeningGap(
        kind=kind,
        top=max(last, first),
        bottom=min(last, first),
        close_time=times[i_close],
        open_time=times[i_open],
        approximate=not exact,
    )


def opening_gaps(
    candles: Sequence[Candle], stats: dict[str, int] | None = None
) -> list[OpeningGap]:
    """Every NDOG and NWOG the bars can support, in time order.

    `candles` must be sorted by time, which is the invariant every other reader
    in this package already relies on.

    A gap appears here only once BOTH its prices are in the data, so a series
    truncated before an 18:00 bar yields no gap for that boundary - the
    anti-lookahead rule falls out of the definition rather than being enforced
    on top of it. A zero-width gap (the two prices equal) is still a gap and
    still returned: "no gap today" is a fact about the market, and dropping it
    would silently change the Event Horizon pairing.
    """
    if not candles:
        return []

    times = [candle.time for candle in candles]

    # DOES THIS INSTRUMENT EVER CLOSE? Asked once about the series, not once per
    # boundary, and nothing asked it at all until 2026-08-19.
    #
    # An opening gap is the distance across an interval in which NOTHING TRADED.
    # A continuously-traded series has no such interval, so it has no opening
    # gaps - and yet the two lookups in `_gap_at` will happily find a bar before
    # 17:00 and a bar at 18:00 on a 24/7 feed and report the distance between
    # them. It was worse than a wrong number: on clean hourly bars the exactness
    # test then PASSES, because 16:00 plus one hour is 17:00 and the 18:00 bar
    # does open at 18:00, so the fabricated band shipped flagged
    # `approximate=False`. Measured 2026-08-19 on binance BTCUSDT 1h: 29 such
    # bands, every one of them exact-flagged. Binance PAXGUSDT and BTCUSDT are
    # the series most of docs/CALIBRATION.md is measured on.
    #
    # WHY THIS IS A PROPERTY OF THE SERIES AND NOT OF THE BOUNDARY. The obvious
    # per-boundary test - "is the 18:00 bar the next one after the 17:00 close" -
    # is wrong, and the suite already contains the counterexample that proves it.
    # COMEX gold on Yahoo emits a stub bar OPENING at 17:00 on a Friday, volume
    # 1, in the hour the market is shut; see
    # `test_the_bar_that_opens_exactly_at_seventeen_hundred_is_excluded`. Under a
    # bar-adjacency rule that stub makes a REAL weekend gap look traded-through
    # and deletes it. At hourly resolution the shut-market artefact and the
    # genuinely traded hour are the same shape, so the boundary cannot tell them
    # apart. The series can: a market that closes leaves a hole in its own bar
    # grid somewhere, and one that never closes never does.
    #
    # Consequence worth stating plainly: on a 24/7 instrument this layer now
    # draws nothing, and that is the correct drawing. It is COUNTED rather than
    # silently skipped, so an empty gaps layer can be told from a broken one.
    # AND ONLY WHERE THE BARS COULD SEE THE HOLE. The daily shut window is one
    # hour wide, so on bars of an hour or less its absence is evidence and on
    # anything coarser it is nothing at all: a 4-hour grid running 06:00, 10:00,
    # 14:00, 18:00 is seamless whether or not the market shut at 17:00. Above
    # the threshold the old behaviour stands - the band is returned flagged
    # `approximate`, which is this module's existing answer for bars too coarse
    # to resolve the boundary, and `test_four_hour_bars_report_the_boundary_as_
    # approximate` pins it.
    if len(times) > 2:
        step = min(b - a for a, b in zip(times, times[1:]))
        seamless = all(b - a <= step for a, b in zip(times, times[1:]))
        if 0 < step <= 3600 and seamless:
            if stats is not None:
                stats["traded_through"] = stats.get("traded_through", 0) + 1
            return []

    out: list[OpeningGap] = []
    day = clock.to_ny(times[0]).date()
    last_day = clock.to_ny(times[-1]).date()
    while day <= last_day:
        kind = _KIND.get(day.weekday())
        if kind is not None:
            gap = _gap_at(
                candles,
                times,
                clock.ny_wall(day.year, day.month, day.day, 18),
                kind,
                stats,
            )
            if gap is not None:
                out.append(gap)
        day += timedelta(days=1)
    return out


def event_horizons(
    gaps: Sequence[OpeningGap],
    keep: int = KEEP_DEFAULT,
    as_of: int | None = None,
) -> list[EventHorizon]:
    """The N-1 levels between the N retained gaps, sorted by price.

    `as_of` is the whole point of this signature: pass a bar time and you get
    the level set as it stood at that bar, which is the only honest way to
    measure anything against an object that moves after birth. Left None it
    answers "what are the levels now", which is the chart's question and not a
    measurement's.

    `keep` retains the most recent gaps by `knowable_at` and drops the rest, and
    changing it changes WHICH levels exist, not merely how many - see property 1
    in the module docstring. `keep=0` keeps everything, matching the convention
    the display caps in this project already use.

    ICT's "minimum four gaps" is guidance about what is worth drawing, not a
    precondition, so three gaps give two levels rather than nothing. Gaps that
    overlap in price still produce a level; the average of a top and a lower
    bottom is a defined number and refusing to report it would hide the overlap
    instead of showing it.
    """
    live = [g for g in gaps if as_of is None or g.knowable_at <= as_of]
    if keep > 0:
        live = sorted(live, key=lambda g: g.knowable_at)[-keep:]
    by_price = sorted(live, key=lambda g: g.ce)
    return [
        EventHorizon(price=(lower.top + upper.bottom) / 2, lower=lower, upper=upper)
        for lower, upper in zip(by_price, by_price[1:])
    ]


# --------------------------------------------------------------------------
# READINGS TAKEN FROM GAPS, AND WHERE THEIR DEFINITIONS COME FROM
#
# The four things below were DECODED ARITHMETICALLY from the RENDERED OUTPUT of
# a closed-source TradingView indicator - "Event Horizon - Multi-Tier Opening
# Gaps" by Tango618 - and were NEVER READ FROM ITS SOURCE, which is protected.
# The whole evidence is one published preview chart: a data table and one label.
# NASDAQ 100 E-mini futures, 1h, with price at 28164.00:
#
#     EV   Top       Bot       Dist
#     W    29206.75  28580.75  -730
#     D    28768.00  28561.50  -501
#
#     EV STACK W+D  91%
#
# The arithmetic in each docstring below reproduces those numbers, which is
# evidence and not verification: a different definition that happens to agree on
# this one chart would be indistinguishable from here. Anyone changing these
# should know they are editing a reconstruction.
#
# NONE OF IT IS MEASURED AGAINST OUTCOMES - not in this repo, and not by the
# indicator's author, who publishes no study. A distance is geometry, an overlap
# is geometry. Twelve pre-registered directional hypotheses have failed in this
# project, so nothing below says which way price goes next, and nothing below
# reports how often any of it preceded anything.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GapDistance:
    """Where one price sits relative to one gap's consequent encroachment.

    DELIBERATELY NOT A FIELD ON `OpeningGap`. A gap is fixed at birth - both its
    prices already printed and neither ever moves again - and a distance changes
    on every tick. A `distance` attribute on the band would put a live number on
    a settled object, and the next reader would cache the object and serve a
    stale distance without ever seeing a stale price. So the reading is a
    separate thing, carrying the `price` it was taken against, because a signed
    number with no stated reference price is not interpretable later.
    """

    gap: OpeningGap
    price: float
    # price - gap.ce. Negative means price is BELOW the encroachment. It says
    # nothing about what happens next; see the section comment above.
    distance: float


def distances_to_ce(gaps: Sequence[OpeningGap], price: float) -> list[GapDistance]:
    """`price` minus each gap's `ce`, one reading per gap, in the given order.

    Reverse-engineered from the indicator's rendered `Dist` column rather than
    read from its source. That column measures to the CONSEQUENT ENCROACHMENT
    and not to either edge, which its own two rows prove:

        W: (29206.75 + 28580.75) / 2 = 28893.75, 28164.00 - 28893.75 = -729.75
        D: (28768.00 + 28561.50) / 2 = 28664.75, 28164.00 - 28664.75 = -500.75

    displayed as -730 and -501. Both match to the rounding shown, and no edge of
    either band gives those numbers. The rounding is the display's business and
    is not done here.
    """
    return [GapDistance(gap=gap, price=price, distance=price - gap.ce) for gap in gaps]


@dataclass(frozen=True)
class GapOrdinal:
    """Which gap of its own kind this is, counting back from the newest.

    1 is the most recent gap OF THAT KIND, 2 the one before it, and so on -
    the indicator's `D-1`, `D-2`, `W-1`.

    THE ORDINAL IS A POSITION IN A LIST, NOT A PROPERTY OF THE GAP. It renumbers
    every time a newer gap of that kind forms: today's `D-1` is tomorrow's `D-2`
    without a single price changing. That is the same not-fixed-at-birth hazard
    the Event Horizon carries (property 2 in the module docstring) and it is here
    for the same reason - the number describes the list, not the band. Anything
    measuring against an ordinal must recompute it as of the bar it is measuring
    at, by passing only the gaps knowable then.
    """

    gap: OpeningGap
    ordinal: int

    @property
    def label(self) -> str:
        """`D-1`, `W-2` - the indicator's own spelling, kind initial and ordinal."""
        return f"{'D' if self.gap.kind == 'NDOG' else 'W'}-{self.ordinal}"


def gap_ordinals(gaps: Sequence[OpeningGap]) -> list[GapOrdinal]:
    """One ordinal per gap, counted WITHIN its kind, in the order given.

    Counting is per kind and by `knowable_at`: the newest NDOG is D-1 and the
    newest NWOG is W-1, and the two counts never interleave. Counting across the
    whole list instead would make the newest NWOG something like D-3 and would
    be a different construct.

    Definition reverse-engineered from the indicator's rendered labels, not from
    its source.
    """
    at: dict[int, int] = {}
    for kind in ("NDOG", "NWOG"):
        same = [i for i, gap in enumerate(gaps) if gap.kind == kind]
        same.sort(key=lambda i: gaps[i].knowable_at, reverse=True)
        at.update({i: n for n, i in enumerate(same, 1)})
    return [GapOrdinal(gap=gap, ordinal=at[i]) for i, gap in enumerate(gaps)]


@dataclass(frozen=True)
class GapStack:
    """Two gaps of DIFFERENT kinds whose bands overlap, and by how much.

    `top` and `bottom` are the overlap band itself. `fraction` is its height
    over the height of the SMALLER of the two gaps, so it is at most 1.0.

    THE DENOMINATOR IS A CHOICE, NOT A MEASUREMENT. The decoded 91% fits the
    smaller zone and pins only that one number; dividing by the larger zone or
    by the union of the two would have produced different percentages that the
    single published label cannot rule out. It is written here because it fits
    the evidence available, and it is the first thing to re-examine if a second
    labelled chart ever disagrees.
    """

    gaps: tuple[OpeningGap, OpeningGap]
    top: float
    bottom: float
    fraction: float

    @property
    def knowable_at(self) -> int:
        """The later of the two gaps: both must exist before the overlap does."""
        return max(gap.knowable_at for gap in self.gaps)


def gap_stacks(gaps: Sequence[OpeningGap]) -> list[GapStack]:
    """Every overlapping pair of DIFFERENT kinds, with its overlap band.

    Two gaps of the SAME kind overlapping is not a stack and is not returned:
    the construct is about a lower degree confirming a higher one, and two NDOGs
    sitting on each other say nothing about degree.

    Touching is not overlapping. One band's top exactly on another's bottom
    gives an overlap of zero height and no stack, which also keeps the fraction
    a real number - an overlap with height has height in both bands, so the
    denominator can never be zero here, including for the zero-width gaps
    `opening_gaps` deliberately keeps.

    Decoded from the indicator's `EV STACK W+D 91%` label, not from its source:
    overlap of W 28580.75..29206.75 with D 28561.50..28768.00 is
    28580.75..28768.00, height 187.25, over the smaller zone D at 206.50, giving
    0.9068. An overlap is geometry and is not evidence of anything; see the
    section comment above.
    """
    out: list[GapStack] = []
    for lower, upper in combinations(gaps, 2):
        if lower.kind == upper.kind:
            continue
        top = min(lower.top, upper.top)
        bottom = max(lower.bottom, upper.bottom)
        if top <= bottom:
            continue
        smaller = min(lower.top - lower.bottom, upper.top - upper.bottom)
        out.append(
            GapStack(
                gaps=(lower, upper),
                top=top,
                bottom=bottom,
                fraction=(top - bottom) / smaller,
            )
        )
    return out


def weekend_degree(gap: OpeningGap) -> Literal["year", "month"] | None:
    """The highest cycle degree whose Q2 this NWOG opens - or None.

    A LABEL, NOT A FIFTH KIND OF GAP. There is no separate "new month opening
    gap" geometry to build: the owner's own time board puts the monthly cycle's
    open at the Sunday 18:00 New York that begins the second full week of the
    month, `quarters.py` implements exactly that as the month degree's Q2, and
    measured on real data 3 of 4 calendar month boundaries have no session break
    at all because the market trades straight through midnight midweek. So a
    monthly opening gap, when it exists, IS an NWOG - this function only says
    which weekend gap matters at which degree.

    `quarters.py` is the single grid. No second one is defined here.

    A gap opens a Q2 when that Q2 boundary falls inside the gap's own dead
    window - after the Friday 17:00 close, at or before the Sunday 18:00 open -
    because then the Sunday open is the first price the quarter ever traded at.
    Month Q2 IS a Sunday 18:00 and so lands on the window's closing edge; year
    Q2 is April 1 00:00 New York and lands inside the window only when April 1
    falls on a weekend. Year outranks month and is checked first. Week and below
    are not checked: the week degree's Q2 is Monday 18:00, which is an NDOG
    boundary and never a weekend one, so a weekend gap can only ever be monthly,
    yearly or unlabelled.

    NDOGs get None. The degree of a weekday gap is not this question.

    Like everything else in this section this is a drawing rule decoded from
    rendered output and doctrine, never read from the indicator's source, and
    no degree here has been measured against outcomes.
    """
    if gap.kind != "NWOG":
        return None
    # The Friday 17:00 the weekend window opens at - the same boundary `_gap_at`
    # uses for an NWOG's closing session, computed the same way.
    closed_at = clock.at_ny_hour(gap.open_time, 17, days=-2)
    # Spelled with the narrow type rather than as a plain tuple of str, the way
    # `quarters.quarters` spells its labels: the narrowing is set once, here.
    degrees: tuple[Literal["year", "month"], ...] = ("year", "month")
    for degree in degrees:
        for quarter in quarters(degree, closed_at, gap.open_time):
            if quarter.label == "Q2" and closed_at < quarter.start <= gap.open_time:
                return degree
    return None


# --------------------------------------------------------------- tier horizons
# The reference indicator draws ONE zone per tier rather than one per gap: a
# `D` row built from the three latest NDOGs and a `W` row from the three latest
# NWOGs. The owner confirmed that retention directly, so `TIER_KEEP` is HIS
# number and not a reconstruction.
#
# HOW THE THREE BECOME ONE TOP AND ONE BOTTOM IS UNRESOLVED, and this module
# says so rather than picking quietly. The reference's own published table, on
# NASDAQ 100 E-mini 1h with price at 28164.00, reads:
#
#     D  top 28768.00  bottom 28561.50
#     W  top 29206.75  bottom 28580.75
#
# Our data for that instrument and instant agrees on price to 5 points
# (28169.25 against 28164.00), so the comparison is like for like rather than a
# feed mismatch. Every reduction below was computed on the same three gaps and
# NONE of them reproduces those numbers:
#
#     reduction   our D                    our W
#     envelope    28700.25 .. 29310.75     28282.25 .. 30032.25
#     ce_span     28719.75 .. 29300.25     28438.38 .. 29963.25
#     newest      28700.25 .. 28739.25     28282.25 .. 28594.50
#     eh_span     28919.63 .. 29227.38     -
#
# 28561.50 and 28768.00 are not an edge of any gap we detect in that window, so
# either the reduction is an operation not tried here, or the reference detects
# its gaps at different boundaries than 17:00/18:00 New York. Those two cannot
# be separated from one screenshot, so both remain open.
#
# `envelope` is the default because it is the plainest reading of "a zone
# spanning these gaps". It is a CHOICE that is known NOT to match the reference,
# which is a stronger statement than an untested default and is why the failed
# candidates are kept in code rather than in a commit message.

#: His number, confirmed directly rather than reverse-engineered.
TIER_KEEP = 3

REDUCTIONS = ("envelope", "ce_span", "newest", "eh_span")


@dataclass(frozen=True)
class TierHorizon:
    """One zone per gap kind, reduced from the `keep` latest gaps of that kind."""

    kind: Literal["NDOG", "NWOG"]
    reduction: str
    top: float
    bottom: float
    #: Gaps the reduction consumed, oldest first. Kept so a reader can check the
    #: zone against its own inputs, which is the only way to tell the four
    #: reductions apart on a chart.
    gaps: tuple[OpeningGap, ...]

    @property
    def ce(self) -> float:
        """The zone's own midpoint. `Dist` in the reference is measured to this."""
        return (self.top + self.bottom) / 2

    @property
    def knowable_at(self) -> int:
        """The latest of its inputs: a tier is knowable when its newest gap is."""
        return max(g.knowable_at for g in self.gaps)


def _reduce(gaps: Sequence[OpeningGap], how: str) -> tuple[float, float] | None:
    """Top and bottom from several gaps, or None when the reading needs more."""
    if not gaps:
        return None
    if how == "envelope":
        return max(g.top for g in gaps), min(g.bottom for g in gaps)
    if how == "ce_span":
        return max(g.ce for g in gaps), min(g.ce for g in gaps)
    if how == "newest":
        newest = max(gaps, key=lambda g: g.knowable_at)
        return newest.top, newest.bottom
    if how == "eh_span":
        # The span between the ICT event-horizon levels these gaps produce.
        # Needs at least three gaps, because two give one level and a single
        # level has no span.
        levels = [level.price for level in event_horizons(gaps, keep=0)]
        if len(levels) < 2:
            return None
        return max(levels), min(levels)
    raise ValueError(f"unknown reduction {how!r}, expected one of {REDUCTIONS}")


def tier_horizons(
    gaps: Sequence[OpeningGap],
    keep: int = TIER_KEEP,
    reduction: str = "envelope",
    as_of: int | None = None,
) -> list[TierHorizon]:
    """One zone per kind, from the `keep` latest gaps of that kind.

    `as_of` filters by `knowable_at` first, for the same reason
    `event_horizons` takes it: these zones are NOT fixed at birth. A new gap of
    a kind pushes the oldest out of the retained set and the whole zone moves,
    without a single price changing.

    Returns nothing for a kind that has fewer gaps than the reduction needs,
    rather than reducing over a short set and calling it a tier.
    """
    live = [g for g in gaps if as_of is None or g.knowable_at <= as_of]
    out: list[TierHorizon] = []
    for kind in ("NDOG", "NWOG"):
        of_kind = sorted(
            (g for g in live if g.kind == kind), key=lambda g: g.knowable_at
        )
        if keep > 0:
            of_kind = of_kind[-keep:]
        if len(of_kind) < keep:
            continue
        band = _reduce(of_kind, reduction)
        if band is None:
            continue
        top, bottom = band
        out.append(
            TierHorizon(
                kind=kind,
                reduction=reduction,
                top=top,
                bottom=bottom,
                gaps=tuple(of_kind),
            )
        )
    return out
