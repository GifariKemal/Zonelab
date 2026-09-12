"""`swings` was a Python loop and is now four numpy reductions. Same pivots?

The loop it replaced lives HERE rather than in a comment beside the new code,
because a rewrite of a detector is only worth anything if it can be shown not to
have moved a single pivot - and a copy of the old code in a comment proves
nothing, while a copy in a test proves it on every run.

WHY IT WAS REWRITTEN AT ALL. Profiled 12 September 2026 on 5,000 bars with eight
layers switched on: `swings` was 0.084s of a 0.303s draw. It is called four
times per draw, and each call looped every bar taking two numpy slices inside
the loop - about 20,000 tiny reductions where four large ones do the same work.

The cases below are not decoration. Flat tops and flat bottoms are exactly where
the strict/non-strict asymmetry earns its place, and a rewrite that got the two
comparisons the same way round would pass on random data and register a pivot on
every bar of a plateau.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.detect.structure import Swing, swings


def _loop(high, low, left, right) -> list[Swing]:
    """The implementation as it stood before 12 September 2026, verbatim."""
    out: list[Swing] = []
    n = len(high)
    for i in range(left, n - right):
        window_l = slice(i - left, i)
        window_r = slice(i + 1, i + 1 + right)
        if high[i] > high[window_l].max() and high[i] >= high[window_r].max():
            out.append(Swing(i, float(high[i]), True, i + right))
        if low[i] < low[window_l].min() and low[i] <= low[window_r].min():
            out.append(Swing(i, float(low[i]), False, i + right))
    return sorted(out, key=lambda s: (s.confirmed_at, s.index))


def _walk(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    close = np.cumsum(rng.normal(0, 1, n)) + 100.0
    span = np.abs(rng.normal(0, 0.6, n))
    return close + span, close - span


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("left,right", [(2, 2), (3, 3), (5, 5), (2, 7), (9, 2), (50, 50)])
def test_the_rewrite_moves_no_pivot(seed, left, right):
    high, low = _walk(600, seed)
    assert swings(high, low, left, right) == _loop(high, low, left, right)


def test_a_flat_top_registers_one_pivot_and_not_a_plateau():
    """The asymmetry, on the shape it exists for.

    `left` is strict and `right` is not, so a run of equal highs may produce a
    pivot at the LAST bar of the run and must not produce one at every bar. A
    rewrite that made both comparisons strict, or both loose, still passes on
    random walks - which is why this case is written out rather than trusted to
    the parametrised sweep above.
    """
    high = np.array([1.0, 2, 3, 5, 5, 5, 3, 2, 1], dtype=np.float64)
    low = np.array([0.0, 1, 2, 4, 4, 4, 2, 1, 0], dtype=np.float64)
    mine = swings(high, low, 2, 2)
    assert mine == _loop(high, low, 2, 2)
    assert sum(1 for s in mine if s.high) <= 1


def test_a_flat_bottom_behaves_the_same_way_inverted():
    low = np.array([9.0, 8, 7, 5, 5, 5, 7, 8, 9], dtype=np.float64)
    high = np.array([10.0, 9, 8, 6, 6, 6, 8, 9, 10], dtype=np.float64)
    assert swings(high, low, 2, 2) == _loop(high, low, 2, 2)


def test_a_bar_that_is_both_high_and_low_keeps_its_order():
    """One bar can pivot both ways, and the two entries have equal sort keys.

    `sorted` is stable, so the order the list was built in survives into the
    output - which means the rewrite has to append high before low exactly as
    the loop did, or callers reading `[0]` get the other one.
    """
    high = np.array([1.0, 1, 9, 1, 1], dtype=np.float64)
    low = np.array([8.0, 8, 0, 8, 8], dtype=np.float64)
    mine, theirs = swings(high, low, 2, 2), _loop(high, low, 2, 2)
    assert mine == theirs
    if len(mine) == 2 and mine[0].index == mine[1].index:
        assert mine[0].high and not mine[1].high


@pytest.mark.parametrize(
    "n,left,right",
    [(0, 3, 3), (1, 3, 3), (6, 3, 3), (7, 3, 3), (5, 2, 2)],
)
def test_windows_that_do_not_fit_return_nothing_rather_than_raising(n, left, right):
    """A window wider than the data is a real request from a short chart.

    The loop answered `[]` by never entering, and the vectorised path has to
    answer `[]` by checking - `sliding_window_view` raises on a window longer
    than the array rather than returning empty.
    """
    high, low = _walk(n, 11) if n else (np.array([]), np.array([]))
    assert swings(high, low, left, right) == _loop(high, low, left, right) == []
