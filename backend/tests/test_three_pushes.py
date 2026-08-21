"""The polarity of `tools/three_pushes.py`, pinned on a zigzag with one answer.

This test exists because the first version of that tool had the sign backwards
and the wrong number looked like a strong finding: it reported 65% where the
honest figure was 35%, because it asked whether the next HIGH failed to extend
after three rising highs instead of whether the next LOW broke. Both readings
produce a large, consistent, highly significant lift. Only one of them is about
the pattern's claim, and a number that is confidently backwards is worse than no
number.

So the fixture is a hand-built zigzag whose turning points are chosen by hand and
whose expected answer is arithmetic: three rising highs, then a low below the
previous low, is one reversal. The same shape with a higher low is zero.
"""

from __future__ import annotations

import numpy as np

from tools.three_pushes import measure


def zigzag(turns: list[float], run: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Bars walking straight between each turning price and the next.

    `run` is comfortably above the tool's `SWING_N` of 3 so every turn produces
    exactly one confirmed pivot: a leg shorter than the fractal width would fail
    to register and the fixture would be testing the pivot finder instead.
    """
    path: list[float] = []
    for start, end in zip(turns, turns[1:]):
        path.extend(np.linspace(start, end, run, endpoint=False))
    path.append(turns[-1])
    mid = np.array(path)
    # A hair of range on each bar, so a pivot is a pivot rather than a tie.
    return mid + 0.01, mid - 0.01


def test_three_rising_highs_then_a_lower_low_counts_as_one_reversal():
    # highs at 110, 120, 130 - each beyond the last - then a low at 95, which is
    # below the previous low of 105. That is the reversal the pattern claims.
    high, low = zigzag([100, 110, 105, 120, 108, 130, 95, 140])
    pattern, base = measure(high, low)
    assert pattern.total == 1, f"expected one candidate, got {pattern.total}"
    assert pattern.reversed_ == 1, "a lower low after three rising highs IS the reversal"
    assert base.total > pattern.total, "the base population must be the wider one"


def test_the_same_shape_with_a_higher_low_counts_as_no_reversal():
    """The polarity check. Everything is identical except the pullback holds, and
    a tool with the sign inverted scores this as a reversal."""
    high, low = zigzag([100, 110, 105, 120, 108, 130, 118, 140])
    pattern, _ = measure(high, low)
    assert pattern.total == 1, f"expected one candidate, got {pattern.total}"
    assert pattern.reversed_ == 0, "a higher low is continuation, not reversal"


def test_pushes_that_do_not_extend_are_not_candidates():
    """Three highs that fail to make progress are not three drives in any
    reading, and the monotonic test is the only thing excluding them."""
    high, low = zigzag([100, 130, 105, 120, 108, 110, 95, 140])
    pattern, base = measure(high, low)
    assert pattern.total == 0, "110 < 120 < 130 is descending, not extending"
    assert base.total > 0, "the base rate still has to count these pivots"


def test_the_mirror_case_is_counted_the_same_way():
    """Three FALLING lows predict a move up, so the reversal is a higher high.
    Written out rather than assumed symmetric, because the sign that was wrong in
    the tool was wrong in exactly one branch of exactly this conditional."""
    high, low = zigzag([140, 130, 135, 120, 132, 110, 145, 100])
    pattern, _ = measure(high, low)
    assert pattern.total == 1, f"expected one candidate, got {pattern.total}"
    assert pattern.reversed_ == 1, "a higher high after three falling lows IS the reversal"
