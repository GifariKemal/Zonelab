"""The standard deviation projection: multiples of a range's height, drawn beyond it.

Two tests here earn the file on their own.

The first is the SIGN CONVENTION test. The anchor and the sign were both read off
a picture - `analisis lama/27.jpeg`, whose Asia stack runs its negative labels
DOWNWARD off the box low while its London stack runs them UPWARD off the box high
- and arithmetic that mirrors is arithmetic that fails silently. So the side each
label falls on is asserted directly, in both directions, rather than being left
implicit in a list of expected prices.

The second is the ANTI-LOOKAHEAD test. A projection is knowable when its range is
complete and never before, so the series is truncated one bar short of the range's
end and the answer must be None, then extended to the first bar at or after that
end and the answer must appear with the SAME prices it has on the whole series.
That equality is what "fixed at birth" means here.

Nothing in this file asserts that any level is reached more often than chance. No
hit rate has been measured for these levels, here or anywhere this project can
point to, and a test that implied one would be inventing the very number the
module refuses to claim.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_projections.py -q
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.models import Candle
from app.projections import LEVELS, projection

HOUR = 3600
T = 1_700_000_000  # an arbitrary instant; nothing here reads a wall clock


def bar(t: int, high: float, low: float) -> Candle:
    return Candle(time=t, open=(high + low) / 2, high=high, low=low,
                  close=(high + low) / 2)


# Three bars inside the range window, then three after it. The range's own high
# and low are ARGUMENTS, not measured off these bars, so the bars inside only
# have to exist - "no bar, no object" is the only thing they are asked for.
INSIDE = [bar(T + i * HOUR, 108.0, 102.0) for i in range(3)]
AFTER = [
    bar(T + 3 * HOUR, 105.0, 96.0),  # first bar past the range's end
    bar(T + 4 * HOUR, 104.0, 94.0),
    bar(T + 5 * HOUR, 103.0, 90.0),  # equal to the -1 level, never through it
]
CANDLES = INSIDE + AFTER

# The range every test below projects from: ten wide, closed at T + 3h.
FROM, TO, HIGH, LOW = T, T + 3 * HOUR, 110.0, 100.0


def prices(direction: int, levels: Sequence[float] = LEVELS) -> dict[float, float]:
    """{multiple: price} for the standard range, so the arithmetic reads plainly."""
    result = projection(CANDLES, FROM, TO, HIGH, LOW, direction, levels)
    assert result is not None
    return {level.multiple: level.price for level in result.levels}


def test_every_projected_price_off_a_downward_leg_is_a_multiple_of_the_range_height():
    # Travel down: the origin is the LOW, 100, and one unit is the height, 10.
    assert prices(-1) == {
        0.0: 100.0,  # the low itself
        -0.5: 95.0,  # half a range below it
        -1.0: 90.0,
        -1.5: 85.0,
        2.0: 120.0,  # back across the range and one full range past the high
        2.5: 125.0,
    }


def test_the_same_range_travelled_upward_mirrors_every_level_around_the_other_edge():
    # Travel up: the origin is the HIGH, 110, and the negatives run above it.
    assert prices(1) == {
        0.0: 110.0,
        -0.5: 115.0,
        -1.0: 120.0,
        -1.5: 125.0,
        2.0: 90.0,
        2.5: 85.0,
    }


def test_the_negative_labels_fall_on_the_side_price_is_travelling_towards():
    # The whole reading off 27.jpeg, stated as the relation rather than as
    # numbers, so an edit that mirrors the formula cannot pass this file.
    down = projection(CANDLES, FROM, TO, HIGH, LOW, -1)
    up = projection(CANDLES, FROM, TO, HIGH, LOW, 1)
    assert down is not None and up is not None

    assert down.origin == LOW and up.origin == HIGH
    assert down.height == 10.0 and up.height == 10.0

    below = {level.multiple: level.price for level in down.levels}
    above = {level.multiple: level.price for level in up.levels}

    # Negative multiples: beyond the origin, further in the direction of travel.
    for multiple in (-0.5, -1.0, -1.5):
        assert below[multiple] < LOW, "a downward leg projects negatives DOWN"
        assert above[multiple] > HIGH, "an upward leg projects negatives UP"

    # Positive multiples: back across the range and out the far side, so +1 is
    # the opposite edge exactly - which is why his chart never labels it.
    assert prices(-1, levels=(1.0,))[1.0] == HIGH
    assert prices(1, levels=(1.0,))[1.0] == LOW
    assert below[2.0] > HIGH and above[2.0] < LOW


def test_a_level_is_taken_by_the_first_bar_that_traded_through_it_and_not_a_later_one():
    result = projection(CANDLES, FROM, TO, HIGH, LOW, -1)
    assert result is not None
    taken = {level.multiple: level.taken_at for level in result.levels}

    # 95 is pierced by the 94 low at T+4h. T+5h goes lower still and must not win.
    assert taken[-0.5] == T + 4 * HOUR
    # 100 is pierced by the very first bar past the range, at T+3h.
    assert taken[0.0] == T + 3 * HOUR


def test_a_level_price_never_traded_through_still_stands_and_reports_none():
    result = projection(CANDLES, FROM, TO, HIGH, LOW, -1)
    assert result is not None
    taken = {level.multiple: level.taken_at for level in result.levels}

    assert taken[-1.5] is None  # 85, never approached
    assert taken[-1.0] is None  # 90, and the lowest low is exactly 90: a touch
    assert taken[2.0] is None and taken[2.5] is None  # 120 and 125, above


def test_a_custom_level_set_replaces_the_transcribed_default_entirely():
    default = projection(CANDLES, FROM, TO, HIGH, LOW, -1)
    custom = projection(CANDLES, FROM, TO, HIGH, LOW, -1, levels=(-3.0, 0.25))
    assert default is not None and custom is not None

    assert tuple(level.multiple for level in default.levels) == LEVELS
    assert [(level.multiple, level.price) for level in custom.levels] == [
        (-3.0, 70.0),
        (0.25, 102.5),
    ]


def test_a_projection_is_not_knowable_before_a_bar_proves_the_range_closed():
    # One bar short of the range's end there is no object at all, not a
    # provisional one; the first bar at or after the end is the proof.
    assert projection(INSIDE, FROM, TO, HIGH, LOW, -1) is None

    at_knowable = projection(INSIDE + AFTER[:1], FROM, TO, HIGH, LOW, -1)
    whole = projection(CANDLES, FROM, TO, HIGH, LOW, -1)
    assert at_knowable is not None and whole is not None
    assert at_knowable.knowable_at == T + 3 * HOUR == whole.knowable_at

    # Fixed at birth: the prices computed at the knowable instant are the prices
    # the whole series gives. Only the touch record grows.
    assert [level.price for level in at_knowable.levels] == [
        level.price for level in whole.levels
    ]


def test_reading_the_series_as_of_an_earlier_bar_moves_the_touches_not_the_levels():
    early = projection(CANDLES, FROM, TO, HIGH, LOW, -1, at=T + 3 * HOUR)
    whole = projection(CANDLES, FROM, TO, HIGH, LOW, -1)
    assert early is not None and whole is not None

    assert early.at == T + 3 * HOUR and whole.at == T + 5 * HOUR
    assert [le.price for le in early.levels] == [le.price for le in whole.levels]
    assert {le.multiple: le.taken_at for le in early.levels}[-0.5] is None
    assert projection(CANDLES, FROM, TO, HIGH, LOW, -1, at=T + 2 * HOUR) is None


def test_a_range_with_no_height_puts_every_level_on_the_origin_without_dividing():
    flat = projection(CANDLES, FROM, TO, 100.0, 100.0, -1)
    assert flat is not None
    assert flat.height == 0.0 and flat.origin == 100.0
    assert {level.price for level in flat.levels} == {100.0}
    # Still a real touch record: 100 was traded through downward at T+3h.
    assert {le.multiple: le.taken_at for le in flat.levels}[0.0] == T + 3 * HOUR


def test_a_range_window_holding_no_bars_produces_no_projection():
    assert projection(CANDLES, T - 2 * HOUR, T - HOUR, HIGH, LOW, -1) is None


def test_no_candles_produce_no_projection():
    assert projection([], FROM, TO, HIGH, LOW, -1) is None


def test_a_bad_direction_a_backwards_range_and_an_inverted_high_are_all_rejected():
    with pytest.raises(ValueError, match="direction"):
        projection(CANDLES, FROM, TO, HIGH, LOW, 0)
    with pytest.raises(ValueError, match="below low"):
        projection(CANDLES, FROM, TO, LOW, HIGH, -1)
    with pytest.raises(ValueError, match="opens after it closes"):
        projection(CANDLES, TO, FROM, HIGH, LOW, -1)
