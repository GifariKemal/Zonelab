"""Standard deviation projections: multiples of a range's own height, beyond it.

WHY THIS EXISTS, and what the evidence actually was. Across the owner's own
annotated charts this object appears more often than almost anything else: a
stack of short horizontal segments to the right of a range, each labelled with a
number. `analisis lama/27.jpeg` (Gold 15m, 2026-08-11) carries TWO of them in one
screenshot - one stack anchored to that day's Asia box, a second anchored to the
London box - and both carry the same six labels: `0`, `-0.5`, `-1`, `-1.5`, `2`,
`2.5`. `22.jpeg` (same instrument, same day, mobile) carries a third stack with a
`-0.5` on it. It is a RULER. It says where a multiple of a range falls, and it
says nothing whatsoever about whether price will go there.

--------------------------------------------------------------------------------
THE CONSTRUCT, and the two things about it that had to be READ OFF A PICTURE.

Take a range - a session box, a quarter, a defining range, a manipulation leg -
and a DIRECTION OF TRAVEL. Then:

    origin      the range edge that lies in the direction of travel: the LOW when
                travel is down, the HIGH when travel is up. `0` is that edge.
    unit        the range's own height, high minus low.
    multiple m  price = origin - direction * m * height

so that NEGATIVE multiples fall BEYOND the origin, further in the direction of
travel, and POSITIVE multiples fall back across the range and out the other side.
`+1` is therefore the range's opposite edge, which is why his charts never label
it: the box already draws it.

THE ANCHOR AND THE SIGN ARE BOTH CHOSEN, NOT CITED. Nobody handed this project a
rule; the reading below is arithmetic recovered from 27.jpeg's pixels against its
own price axis, and it is stated here so that a later edit cannot mirror it in
silence. On that chart the axis reads 2.4 pixels per dollar, and:

  the ASIA stack, price travelling DOWN out of the box
      `0` sits on the box LOW, ~4455.4. The half-step measured between labels is
      ~20.2, so the unit is ~40.4 and the box is ~40 tall. `2` lands at 4536,
      measured at 4535.8. `2.5` lands at 4556, measured at 4556.3. The negative
      labels run DOWNWARD from the low: -0.5, -1, -1.5 at ~4435, ~4415, ~4395.

  the LONDON stack, price travelling UP out of the box
      `0` sits on the box HIGH, and the chart's own price marker puts it at
      4443.0. `-1` sits at 4468.2, which is a second price marker on the same
      chart, giving a unit of 25.2. The negative labels run UPWARD this time, and
      `2` / `2.5` run downward through the box and out the bottom, landing on
      ~4392 / ~4380 against the $/DOL line at 4375.

Two stacks, opposite travel, one formula. That is the whole evidence, and it is a
picture rather than a source. GETTING THE SIGN BACKWARDS WOULD MIRROR EVERY LEVEL
HE DRAWS, so `test_projections.py` asserts it explicitly rather than trusting the
arithmetic to stay put.

THE DEFAULT LEVEL SET IS COPIED OFF THAT CHART AND IS NOT A CITATION OF ANY RULE.
`LEVELS` is exactly the six labels 27.jpeg shows. The set is strange - it skips
-2, and it has no +0.5 or +1 - and the honest reading is that +1 is the box edge
and +0.5 the box midpoint, both already drawn, while -2 simply was not on that
screenshot. Whether he draws -2 elsewhere is NOT KNOWN here. So the set is a
parameter, the default is a transcription, and a caller who has a real level set
should pass it.

--------------------------------------------------------------------------------
FIXED AT BIRTH, which is the question a projection off a live range raises.

A projection taken off a range that is still forming moves every time the range
extends - the same class of problem as this project's event horizons, the only
object here whose value is not fixed at birth. This one is FIXED AT BIRTH, and it
is fixed by refusing the situation rather than by handling it: the range arrives
as four arguments, so the height cannot change underneath the levels, and the
object is withheld until a bar exists at or after `time_to` to prove the range's
last bar has closed. Before that instant there is no Projection, not a
provisional one.

`at` is how you ask "what were the levels as of bar N". The prices do not move
with it - they cannot - but `taken_at` and the object's very existence do, so a
replay at bar N sees exactly what was visible at bar N and nothing later.

--------------------------------------------------------------------------------
HOUSE RULES, all asserted in tests/test_projections.py:

A PROJECTION IS NOT A FORECAST. It is a level, drawn by arithmetic, and price
reaching it is a fact recorded after the bar closed. NOBODY HAS PUBLISHED A
MEASURED HIT RATE FOR THESE LEVELS AND NEITHER HAS THIS PROJECT - not for the
default set, not for any level in it, not for either direction. Twelve
pre-registered directional hypotheses have already failed here. No field on any
object below ranks, scores or forecasts anything, and none ever should.

NO BAR, NO OBJECT. A range window holding no bars produces None, the same rule
`quarters.true_opens`, `quarterly.defining_range` and `pools.liquidity_pools`
follow. Nothing is interpolated and the window is never widened to find a bar.

REACHED IS `taken_at`, AND IT IS THE FIRST BAR. The vocabulary is `pools.py`'s and
so is the code: `_taken` and `_bars` are imported from that module rather than
rewritten, because a second definition of "traded through" is how two parts of one
engine start disagreeing about the same chart. Strictly through, never a touch.

NO DEGREE IS CONSULTED. The range is four arguments, so nothing here reads the
quarter grid, `DEGREES`, or any detector. A caller with a `Quarter` passes
`q.start, q.end`; with a `DFR`, `dfr.start, dfr.end`; with a manipulation leg, the
two bar times. That is deliberate: this file cannot disagree with the objects that
were drawn, because it never draws one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import Candle
from .pools import _bars, _taken

# The six labels on 27.jpeg, in the order they read off the chart. A
# TRANSCRIPTION, not a rule - see the module docstring.
LEVELS: tuple[float, ...] = (0.0, -0.5, -1.0, -1.5, 2.0, 2.5)


@dataclass(frozen=True)
class Level:
    """One projected level: its label, its price, and whether price got there.

    `taken_at` is the open time of the FIRST bar that traded strictly through the
    price, or None while the level still stands. It is a record of bars that have
    printed and is not a claim that any other level will be reached.
    """

    multiple: float  # the label as drawn: 0, -0.5, -1.0, ...
    price: float
    taken_at: int | None


@dataclass(frozen=True)
class Projection:
    """A closed range, and the multiples of its own height projected off it.

    `origin` is the edge the multiples are measured from - the low when travel is
    down, the high when travel is up - and it is the price of multiple 0.
    `height` can be 0.0 for a range that never moved, in which case every level
    collapses onto `origin`; nothing here divides by it.
    """

    time_from: int  # range open, inclusive
    time_to: int  # range close, exclusive
    high: float
    low: float
    height: float  # high - low, the unit every multiple is counted in
    direction: int  # +1 travel up, -1 travel down. Not a forecast.
    origin: float  # the edge multiple 0 sits on
    bars: int  # bars inside the range window; there is no object without one
    knowable_at: int  # open time of the first bar proving the range closed
    at: int  # open time of the last bar this reading was taken on
    levels: tuple[Level, ...]  # in the order asked for, not sorted by price


def projection(
    candles: list[Candle],
    time_from: int,
    time_to: int,
    high: float,
    low: float,
    direction: int,
    levels: Sequence[float] = LEVELS,
    at: int | None = None,
) -> Projection | None:
    """Multiples of a range's own height, projected off the edge price is leaving by.

    The range is four arguments - `time_from` inclusive, `time_to` exclusive, and
    its two prices - so that no detector is run and the height cannot move
    underneath the levels. `direction` is +1 when price is travelling up out of
    the range and -1 when down; it selects which edge is the origin and which way
    the negative labels point, and it is a description of the leg being measured
    rather than a prediction about the next one.

    `levels` defaults to the six labels transcribed off the owner's own chart.
    That default is a transcription and not a citation of any published rule, and
    no hit rate has ever been measured for it here or anywhere this project can
    point to.

    `at` reads the series as of that bar, so the levels a replay sees at bar N are
    the levels that were visible at bar N. The prices never move with it.

    None when there are no bars, when the range window holds no bars, or when no
    bar yet exists at or after `time_to` to prove the range has closed. A closed
    range with no height still produces an object: every level sits on `origin`,
    which is the honest answer rather than a division.
    """
    if direction not in (1, -1):
        raise ValueError(f"direction must be +1 (up) or -1 (down), got {direction!r}")
    if high < low:
        raise ValueError(f"high {high} is below low {low}")
    if time_to <= time_from:
        raise ValueError(f"the range {time_from}..{time_to} opens after it closes")
    if not candles:
        return None

    seen = _bars(candles, candles[0].time, (candles[-1].time if at is None else at) + 1)
    inside = _bars(seen, time_from, time_to)
    after = _bars(seen, time_to, seen[-1].time + 1) if seen else []
    if not inside or not after:
        return None

    height = high - low
    origin = low if direction < 0 else high

    return Projection(
        time_from=time_from,
        time_to=time_to,
        high=high,
        low=low,
        height=height,
        direction=direction,
        origin=origin,
        bars=len(inside),
        knowable_at=after[0].time,
        at=seen[-1].time,
        levels=tuple(
            Level(
                multiple=multiple,
                price=origin - direction * multiple * height,
                # A multiple at or below 0 lies on the travel side of the origin,
                # so it is below when travel is down and above when travel is up;
                # a positive multiple lies on the other side. Decided from the
                # sign rather than by comparing prices, so a flat range - every
                # level on the origin - still asks the right question.
                taken_at=_taken(
                    after,
                    origin - direction * multiple * height,
                    (multiple > 0) if direction < 0 else (multiple <= 0),
                ),
            )
            for multiple in levels
        ),
    )
