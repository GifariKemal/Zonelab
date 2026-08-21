"""ICT premium/discount: where the zone sat in the dealing range on arrival.

The engine already reports a range position and it is a DIFFERENT one. `curve` is
the Seiden reading: a 200-bar rolling window split in thirds, measured on the bars
before the base and frozen the moment the zone was born. docs/FIDELITY.md lists
the mismatch as a deviation, and the three halves of it are all real - the range
is rolling rather than swing-to-swing, the cut is thirds rather than quartiles
around the 50% equilibrium, and the reading is taken at BIRTH while ICT takes it
when price ARRIVES.

So this is not a fix to `curve` and must never be confused for one. Both readings
are legitimate descriptions of different quantities, they disagree by
construction, and `curve` keeps its own lineage untouched.

Like app/profit_zone.py this is a pass over the finished set rather than anything
a detector can compute: the dealing range is a fact about the chart around the
zone, not about the formation, and it cannot be read until the zone has been
touched - which is knowledge the detector does not have when it draws the box.

THE ONE THING THAT MAKES OR BREAKS IT
The range has to be knowable at the touch bar. A swing high at bar `i` is not
knowable at `i`; it is knowable at `i + right`, which is what `Swing.confirmed_at`
carries. Reading the range off swings that confirmed after the touch would produce
a beautiful reading made entirely of hindsight, and this project has already
caught itself doing exactly that once. The rule is asserted in
tests/test_dealing_range.py rather than trusted.
"""

from __future__ import annotations

from bisect import bisect_right

import numpy as np

from .detect.structure import swings
from .models import Candle, Zone

#: The two bands, and they live HERE so that one number cannot mean two things.
#:
#: They were defined in `app/deduce.py`, which is the module that TESTS them - and
#: the module that draws them is `app/liquidity.py`. Two copies of 0.75 in two
#: files is how the line a reader sees stops being the line the deduction uses,
#: and that divergence would be invisible: both charts look right, and only a
#: disagreement between the drawn boundary and the printed verdict would ever
#: reveal it. `deduce.py` imports these now.
#:
#: The values themselves are a JUDGEMENT and not a citation, and a survey of the
#: open-source implementations makes that sharper rather than softer: THREE
#: different answers are in circulation and no two agree.
#:
#:   above 0.50   the textbook reading - ICT's premium is simply "above the
#:                equilibrium", which is the `EQ 50` line the range frame draws
#:   above 0.95   `Smart Money Concepts (SMC) [LuxAlgo]`, the most-installed open
#:                SMC indicator, read from its own source: it draws Premium as
#:                `0.95*top + 0.05*bottom` to `top` and Equilibrium as
#:                `0.525/0.475` - 5% bands at the extremes and the middle, not
#:                quartiles at all
#:   above 0.75   this engine
#:
#: Zero open-source implementation surveyed draws a 0.25 / 0.5 / 0.75 ladder. One
#: of the reference charts does, which is why the frame draws it - but that is one
#: practitioner's chart rather than a standard, and a reader comparing this engine
#: against a LuxAlgo chart will see the bands in different places for this reason.
#:
#: So the frame draws BOTH boundaries a reader might mean: `EQ 50` is the textbook
#: line and `PREM 75` is this engine's stricter one. Neither has been measured
#: against outcomes here, and nothing in this project reads either as a direction.
PREMIUM_FROM = 0.75
DISCOUNT_TO = 0.25


def range_at(
    candles: list[Candle], swing_n: int = 50
) -> tuple[list[int], list[tuple[float | None, float | None]]]:
    """Bar times, and the (high, low) of the dealing range KNOWABLE at each bar.

    Extracted from `mark_dealing_range` rather than duplicated, because a second
    forward walk over the same swings is a second chance to get the knowability
    rule wrong - and that rule is the only thing standing between this reading
    and hindsight. Both callers now share one walk and one cursor.

    The pair is (None, None) until both sides have confirmed, and stays whatever
    was last confirmed after that. Nothing is interpolated and no midpoint is
    invented.
    """
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    times = [c.time for c in candles]
    found = swings(high, low, swing_n, swing_n)

    # One forward walk rather than a search per query. `swings` returns them
    # ordered by `confirmed_at`, so a single cursor yields the pair that was
    # knowable at each bar - the same shape `breaks` uses, and for the same
    # reason: a cursor that only moves forward cannot read a swing early.
    # Recency by `confirmed_at` and recency by bar index agree here because
    # `right` is the same for every swing, so "last confirmed" is unambiguous.
    knowable: list[tuple[float | None, float | None]] = []
    hi: float | None = None
    lo: float | None = None
    cursor = 0
    for i in range(len(candles)):
        while cursor < len(found) and found[cursor].confirmed_at <= i:
            swing = found[cursor]
            if swing.high:
                hi = swing.price
            else:
                lo = swing.price
            cursor += 1
        knowable.append((hi, lo))
    return times, knowable


def position_at(
    price: float,
    at: int,
    times: list[int],
    knowable: list[tuple[float | None, float | None]],
) -> float | None:
    """Where `price` sat in the dealing range knowable at bar time `at`.

    0 at the range low, 1 at the high, clipped. None when either side of the
    range had not confirmed yet, when the range has no height, or when `at`
    precedes the series - never a substituted 0.5, for the same reason
    `mark_dealing_range` refuses one: an invented midpoint is indistinguishable
    from a measured one.
    """
    bar = bisect_right(times, at) - 1
    if bar < 0 or bar >= len(knowable):
        return None
    hi_at, lo_at = knowable[bar]
    if hi_at is None or lo_at is None or hi_at - lo_at <= 0.0:
        return None
    return round(min(max((price - lo_at) / (hi_at - lo_at), 0.0), 1.0), 3)


def mark_dealing_range(
    zones: list[Zone], candles: list[Candle], swing_n: int = 50
) -> dict[str, float]:
    """Stamp every zone with its position in the dealing range. Mutates in place.

    For each zone the answer is read AT `first_test_time`, the bar price first
    arrived at the zone, because that is the moment ICT reads premium/discount.
    A zone that has never been touched has no arrival, so it gets None; any other
    bar would be measuring a different thing.

    The range is the last confirmed swing HIGH and the last confirmed swing LOW as
    of that bar, from `structure.swings` at width `swing_n` on both sides - the
    same primitive and the same width the structure overlay uses, so the drawn
    swings and the range behind this number cannot drift apart. Only swings whose
    `confirmed_at` is at or before the touch bar are eligible.

    None when either side of the range is missing, or when the two prices leave no
    height. Never a substituted 0.5: an invented midpoint is indistinguishable
    from a measured one, and `curve` already falls back to 0.5 for its own range,
    which is one place too many.

    0 sits at the range low and 1 at the high, clipped to that interval, measured
    on the zone's PROXIMAL line - the edge price actually meets and the price a
    trade would be filled at. The distal is where the stop goes, so measuring it
    would answer "where in the range does the stop sit", a different question.

    `swing_n` defaults to 50 to match `StructureParams.swing_n`. No primary source
    publishes an N for the dealing range; 50 is the swing default in the
    most-installed public codification of these ideas, and it is stated here as a
    choice rather than a finding.

    REPORTED, NEVER SCORED - and if anyone later scores it, SPLIT BY SIDE FIRST.
    The doctrine demands demand be strong in DISCOUNT and supply strong in
    PREMIUM, so a real effect must point in OPPOSITE directions for the two sides.
    The Seiden verdict `curve_favourable` measured unproven (AUC 0.547 and 0.518),
    and the raw `curve` value looked like the strongest finding in this project
    (AUC 0.648 and 0.581, CI clear of 0.5, same sign in both halves) until it was
    split by side: high-is-better on BOTH sides at all three reward geometries,
    which is upward drift in the sample and not curve position at all. Demand came
    out backwards from its own doctrine. See docs/FIDELITY.md, "The Curve, dan
    artefak yang hampir saya laporkan sebagai temuan". That is why this ships as a
    bare position with no boolean verdict beside it.

    Returns counts, so a caller can see at a glance whether the field is mostly
    absent - a field that is None for nearly everything is a bug, not a reading.
    """
    stats: dict[str, float] = {
        "zones": float(len(zones)),
        "marked": 0.0,
        "marked.demand": 0.0,
        "marked.supply": 0.0,
        "untouched": 0.0,
        "no_range": 0.0,
        "off_series": 0.0,
    }

    times, knowable = range_at(candles, swing_n)

    for zone in zones:
        zone.dealing_range_pos = None
        if zone.first_test_time is None:
            stats["untouched"] += 1.0
            continue

        # `first_test_time` is a bar open time taken from these same candles, so
        # this is normally an exact hit; bisect covers the caller who pairs zones
        # with a different grid, where the touch falls inside a bar instead of on
        # its open. A touch before the first bar means the zones and the candles
        # do not belong together, which is counted rather than averaged over.
        bar = bisect_right(times, zone.first_test_time) - 1
        if bar < 0:
            stats["off_series"] += 1.0
            continue

        hi_at, lo_at = knowable[bar]
        if hi_at is None or lo_at is None or hi_at - lo_at <= 0.0:
            stats["no_range"] += 1.0
            continue

        pos = (zone.proximal - lo_at) / (hi_at - lo_at)
        zone.dealing_range_pos = round(min(max(pos, 0.0), 1.0), 3)
        stats["marked"] += 1.0
        stats[f"marked.{zone.side.value}"] += 1.0

    return stats
