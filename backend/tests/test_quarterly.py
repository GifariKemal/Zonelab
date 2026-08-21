"""The first two checklist items, on bars whose right answer is arithmetic.

Every fixture here is hand-built and dated. `providers.synthetic.generate`
anchors its bars to `now`, so it cannot be used for anything that has to land on
a particular New York quarter boundary, and all of this does.

Two tests carry more weight than the rest:

  - the DISCARDED FIRST THIRD. The fixture puts both extremes of Q1 inside the
    first third, so an implementation that forgets to drop it returns 3500/3300
    instead of 3420/3370 and the test fails loudly. Without that placement the
    thirds rule would be untested, because most windows give the same answer
    either way.

  - the ANTI-LOOKAHEAD pair, asserted by TRUNCATION rather than by intent. The
    answer computed from the bars available at the knowable instant must equal
    the answer computed from the whole series, and one bar earlier it must be
    None. Reading a docstring that promises no lookahead proves nothing.

Nothing here asserts that any of these objects predicts anything.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_quarterly.py -q
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.clock import NY
from app.models import Candle
from app.quarterly import (
    defining_range,
    defining_ranges,
    manipulation_done,
    profile,
)

HOUR = 3600

# Every fixture is hourly bars from this instant, which is 12:00 New York on a
# plain Tuesday in EDT - no DST transition anywhere near it. Bar `i` is therefore
# hour `i` from noon, which makes the quarter boundaries countable:
#
#   i = 0    12:00  previous cycle's Q4 opens
#   i = 6    18:00  this cycle's Q1 opens, and the cycle with it
#   i = 8    20:00  the kept two thirds of Q1 open
#   i = 12   00:00  Q2
#   i = 18   06:00  Q3
#   i = 24   12:00  Q4
NOON = int(datetime(2025, 6, 10, 12, tzinfo=NY).timestamp())
CYCLE = NOON + 6 * HOUR

# A quiet bar. Overridden per index by the fixtures below, so anything a test
# does NOT name is deliberately uneventful.
QUIET = (3405.0, 3395.0, 3400.0)


def ny(year: int, month: int, day: int, hour: int = 0) -> int:
    """Epoch of a New York wall clock time, built from the calendar, not the code."""
    return int(datetime(year, month, day, hour, tzinfo=NY).timestamp())


def bars(
    count: int, at: dict[int, tuple[float, float, float]], start: int = NOON
) -> list[Candle]:
    """`count` hourly bars from `start`; `at[i]` sets (high, low, close) of bar i."""
    out = []
    for i in range(count):
        high, low, close = at.get(i, QUIET)
        out.append(
            Candle(time=start + i * HOUR, open=close, high=high, low=low, close=close)
        )
    return out


def upto(candles: list[Candle], when: int) -> list[Candle]:
    """The bars that had OPENED at or before `when`."""
    return [c for c in candles if c.time <= when]


# The manipulation fixture, shared by the conjunction tests.
#
#   i=0,1    previous cycle's Q4 puts its high at 3450 and its low at 3350
#   i=7,8    Q1 sits inside that, 3440 to 3360, so the profile is AMDX
#   i=14     a swing high at 3412, confirmed two bars later at i=16
#   i=17     a wick to 3455 that closes back at 3405: the SWEEP, inside Q2, and
#            above Q1's 3440 high, so it takes the previous quarter's extreme
AMDX = {
    0: (3450.0, 3395.0, 3400.0),
    1: (3405.0, 3350.0, 3400.0),
    7: (3440.0, 3395.0, 3400.0),
    8: (3405.0, 3360.0, 3400.0),
    14: (3412.0, 3395.0, 3400.0),
    17: (3455.0, 3395.0, 3405.0),
}
# One number changed: Q1's high now clears the previous Q4's, so Q1 is no longer
# contained and the profile flips. Nothing else about the series moves.
XAMD = AMDX | {7: (3460.0, 3395.0, 3400.0)}

SWEEP_AT = NOON + 17 * HOUR


# --------------------------------------------------------------------------
# 1. The defining range


def test_the_discarded_first_third_of_q1_really_does_change_the_defining_range():
    # 18:00 and 19:00 hold both extremes of Q1 and both are thrown away.
    candles = bars(
        12,
        {
            0: (3500.0, 3300.0, 3400.0),
            3: (3420.0, 3395.0, 3400.0),
            4: (3405.0, 3370.0, 3400.0),
        },
        start=CYCLE,
    )

    dfr = defining_range(candles, "day", CYCLE)

    assert dfr is not None
    assert (dfr.high, dfr.low) == (3420.0, 3370.0)
    assert dfr.high != 3500.0 and dfr.low != 3300.0


def test_the_kept_window_opens_20_00_new_york_on_the_daily_cycle():
    # Bucko's own worked example: Q1 is 18:00 to midnight, so 20:00 to midnight
    # is what survives.
    dfr = defining_range(bars(12, {}, start=CYCLE), "day", CYCLE)

    assert dfr is not None
    assert dfr.start == ny(2025, 6, 10, 20)
    assert dfr.end == ny(2025, 6, 11, 0)
    assert dfr.cycle_start == ny(2025, 6, 10, 18)


def test_a_cycle_with_no_bars_in_the_kept_window_has_no_defining_range():
    # 18:00 and 19:00 print, then the feed goes out until midnight. The first
    # third is not the DFR, so there is nothing to measure and nothing is
    # carried forward from the cycle before.
    candles = [
        c
        for c in bars(12, {}, start=CYCLE)
        if not (ny(2025, 6, 10, 20) <= c.time < ny(2025, 6, 11, 0))
    ]

    assert defining_range(candles, "day", CYCLE) is None


def test_the_walker_skips_the_cycle_whose_window_is_empty_rather_than_filling_it():
    # Through 00:00 on the 12th, so the SECOND cycle's Q1 has provably closed
    # too - one bar less and the walker is right to withhold it.
    two = bars(31, {}, start=CYCLE)
    holed = [
        c
        for c in two
        if not (ny(2025, 6, 11, 20) <= c.time < ny(2025, 6, 12, 0))
    ]

    assert [d.cycle_start for d in defining_ranges(two, "day")] == [
        ny(2025, 6, 10, 18),
        ny(2025, 6, 11, 18),
    ]
    assert [d.cycle_start for d in defining_ranges(holed, "day")] == [
        ny(2025, 6, 10, 18)
    ]


def test_a_defining_range_is_not_knowable_before_q1_closes():
    candles = bars(12, {3: (3420.0, 3395.0, 3400.0)}, start=CYCLE)
    whole = defining_range(candles, "day", CYCLE)

    assert whole is not None
    # Q1 closes at midnight, and at that instant the answer is already final.
    assert defining_range(upto(candles, whole.end), "day", CYCLE) == whole
    # One bar earlier it does not exist at all.
    assert defining_range(upto(candles, whole.end - HOUR), "day", CYCLE) is None


# --------------------------------------------------------------------------
# 2. The cycle profile


def test_q1_contained_inside_the_previous_q4_range_reads_amdx_and_manipulates_in_q2():
    shape = profile(bars(26, AMDX), "day", CYCLE)

    assert shape is not None
    assert (shape.name, shape.manipulation) == ("AMDX", "Q2")
    assert (shape.prev_q4_high, shape.prev_q4_low) == (3450.0, 3350.0)
    assert (shape.q1_high, shape.q1_low) == (3440.0, 3360.0)


def test_q1_breaking_outside_the_previous_q4_range_reads_xamd_and_manipulates_in_q3():
    shape = profile(bars(26, XAMD), "day", CYCLE)

    assert shape is not None
    assert (shape.name, shape.manipulation) == ("XAMD", "Q3")
    assert shape.q1_high == 3460.0 > shape.prev_q4_high


def test_a_cycle_whose_q1_is_still_forming_has_no_profile_rather_than_a_guess():
    # Bars stop at 23:00, one hour inside Q1.
    assert profile(bars(12, AMDX), "day", CYCLE) is None
    # Q1's last bar has closed once the midnight bar opens, and only then.
    assert profile(bars(13, AMDX), "day", CYCLE) is not None


def test_a_profile_is_not_knowable_before_q1_closes():
    candles = bars(26, AMDX)
    shape = profile(candles, "day", CYCLE)

    assert shape is not None
    assert shape.knowable_at == ny(2025, 6, 11, 0)
    assert profile(upto(candles, shape.knowable_at), "day", CYCLE) == shape
    assert profile(upto(candles, shape.knowable_at - HOUR), "day", CYCLE) is None


def test_a_cycle_whose_previous_q4_has_no_bars_has_no_profile():
    # The series starts at 18:00, so the previous cycle's Q4 was never recorded.
    assert profile(bars(20, {}, start=CYCLE), "day", CYCLE) is None


# --------------------------------------------------------------------------
# 3. Manipulation, which is both halves or neither


def test_manipulation_needs_the_manipulation_quarter_and_a_sweep_inside_it():
    found = manipulation_done(bars(26, AMDX), "day", CYCLE)

    assert found is not None
    assert found.profile == "AMDX"
    assert found.quarter.label == "Q2"
    assert found.sweep_time == SWEEP_AT
    assert found.direction == 1
    # The level taken is Q1's high - the previous quarter's extreme, which is
    # the decision this module makes and names.
    assert (found.swept.label, found.level) == ("Q1", 3440.0)
    # And it is NOT the swing the sweep detector itself fired on.
    assert found.swing_level == 3412.0


def test_a_sweep_in_the_wrong_quarter_is_not_manipulation():
    # Same sweep, same bar, same everything - but Q1 broke out of the previous
    # Q4, so the profile is XAMD and the manipulation quarter is Q3. A sweep in
    # Q2 is then just a sweep.
    candles = bars(26, XAMD)

    assert profile(candles, "day", CYCLE).manipulation == "Q3"
    assert manipulation_done(candles, "day", CYCLE) is None


def test_the_manipulation_quarter_without_a_sweep_is_not_manipulation_either():
    # The time half alone: AMDX, so Q2 is the quarter, and nothing sweeps in it.
    quiet = {k: v for k, v in AMDX.items() if k != 17}
    candles = bars(26, quiet)

    assert profile(candles, "day", CYCLE).manipulation == "Q2"
    assert manipulation_done(candles, "day", CYCLE) is None


def test_a_sweep_that_does_not_take_the_previous_quarters_extreme_is_not_manipulation():
    # The wick clears the confirmed swing at 3412 - so `structure.breaks` still
    # calls it a SWEEP - but stops short of Q1's 3440 high. This is the level
    # decision doing its work, and it is the piece a reader is most likely to
    # drop as redundant.
    short = AMDX | {17: (3435.0, 3395.0, 3405.0)}

    assert manipulation_done(bars(26, short), "day", CYCLE) is None


def test_under_xamd_the_sweep_that_counts_is_in_q3_and_takes_q2s_extreme():
    moved = XAMD | {17: QUIET, 20: (3455.0, 3395.0, 3405.0)}

    found = manipulation_done(bars(26, moved), "day", CYCLE)

    assert found is not None
    assert found.profile == "XAMD"
    assert found.quarter.label == "Q3"
    assert (found.swept.label, found.level) == ("Q2", 3412.0)
    assert found.sweep_time == NOON + 20 * HOUR


def test_manipulation_is_not_knowable_before_the_sweep_bar_closes():
    candles = bars(26, AMDX)
    found = manipulation_done(candles, "day", CYCLE)

    assert found is not None
    # Knowable at the close of the bar that swept, which is the instant the next
    # bar opens - and not one bar before that.
    assert manipulation_done(upto(candles, found.sweep_time), "day", CYCLE) == found
    assert (
        manipulation_done(upto(candles, found.sweep_time - HOUR), "day", CYCLE)
        is None
    )


def test_asking_for_a_cycle_that_does_not_start_where_you_said_is_an_error():
    # None is reserved for "the bars are not there". A caller pointing at 20:00
    # instead of 18:00 has made a mistake, and silence would hide it.
    with pytest.raises(ValueError):
        defining_range(bars(12, {}, start=CYCLE), "day", CYCLE + 2 * HOUR)
