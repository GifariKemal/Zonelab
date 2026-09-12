"""`replay_lifecycle` was a Python loop and is now numpy. Same verdicts?

The loop lives here, verbatim as it stood before 12 September 2026, and every
case below runs both and compares the whole `Lifecycle` - state, touch count,
penetration, first test time, arrival ATR and break index. A rewrite of this
function is worth nothing unless it can be shown to have changed none of them.

WHY IT WAS REWRITTEN. Profiled on 5,000 bars with eight layers on, it was 0.127s
of a 0.303s draw - 42 percent - because it runs once per zone, there are around
1,700 zones, and each walk was Python.

WHY THE ORDERING CASES ARE WRITTEN OUT SEPARATELY. The bar that breaks a zone is
still counted as a touch. That ordering was backwards until 6 September 2026 and
the correction moved XAUUSD 30m fvg from n=1045 PF 1.943 to n=1657 PF 1.115 -
the old order silently dropped the trades the live path actually takes, and
almost all of them were losers. A vectorised rewrite that resolved the break
first and then counted touches over the bars BEFORE it would reintroduce exactly
that, pass every random-data test, and be wrong in the same expensive direction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from app.detect.supply_demand import (
    EPS,
    Lifecycle,
    ZoneState,
    replay_lifecycle,
)

# `LifecycleParams` is a Protocol, so it is described rather than instantiated:
# the replay only ever reads these two fields off whatever block a caller hands
# it, which is the whole reason it is a Protocol.
@dataclass(frozen=True)
class _Params:
    mitigation_pct: float
    arrival_bars: int


PARAMS = _Params(mitigation_pct=0.5, arrival_bars=10)


def _loop(time, high, low, close, atr, top, bottom, distal, is_demand, start, params):
    """The implementation as it stood before 12 September 2026, verbatim."""
    height = max(top - bottom, EPS)
    touches = 0
    penetration = 0.0
    first_test_time = None
    arrival_atr = None
    break_index = None
    was_inside = False

    for i in range(start, len(close)):
        inside = low[i] <= top and high[i] >= bottom
        if inside:
            if not was_inside:
                touches += 1
                if first_test_time is None:
                    first_test_time = int(time[i])
                    arr_from = max(0, i - params.arrival_bars)
                    if atr[i] > EPS and i > arr_from:
                        arrival_atr = round(
                            abs(close[i] - close[arr_from]) / float(atr[i]), 3
                        )
            depth = (top - low[i]) if is_demand else (high[i] - bottom)
            penetration = max(penetration, min(1.0, depth / height))
        was_inside = inside

        if close[i] < distal if is_demand else close[i] > distal:
            break_index = i
            break

    if break_index is not None:
        state = ZoneState.BROKEN
    elif penetration >= params.mitigation_pct:
        state = ZoneState.MITIGATED
    elif touches > 0:
        state = ZoneState.TESTED
    else:
        state = ZoneState.FRESH
    return Lifecycle(
        state, touches, penetration, first_test_time, arrival_atr, break_index
    )


def _series(n: int, seed: int):
    rng = np.random.default_rng(seed)
    close = np.cumsum(rng.normal(0, 1, n)) + 100.0
    span = np.abs(rng.normal(0, 0.8, n)) + 0.05
    high, low = close + span, close - span
    atr = np.full(n, 1.0) + np.abs(rng.normal(0, 0.2, n))
    time = np.arange(n, dtype=np.int64) * 3600 + 1_700_000_000
    return time, high, low, close, atr


def _both(*args):
    return replay_lifecycle(*args), _loop(*args)


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("is_demand", [True, False])
def test_the_rewrite_changes_no_verdict(seed, is_demand):
    """Boxes placed all over a real-shaped walk, both sides, every field."""
    time, high, low, close, atr = _series(400, seed)
    mid = float(np.median(close))
    scale = float(np.std(close))
    for k in range(-3, 4):
        top = mid + k * scale * 0.4 + 1.0
        bottom = top - max(scale * 0.3, 0.5)
        distal = bottom - 0.5 if is_demand else top + 0.5
        for start in (0, 37, 200, 399):
            mine, theirs = _both(
                time, high, low, close, atr, top, bottom, distal,
                is_demand, start, PARAMS,
            )
            assert mine == theirs, (k, start)


def test_the_breaking_bar_still_counts_as_a_touch():
    """The ordering that cost PF 1.943 -> 1.115 when it was wrong.

    One bar enters the zone AND closes beyond the distal. It must report
    BROKEN with touches=1, not BROKEN with touches=0.
    """
    time = np.arange(4, dtype=np.int64)
    high = np.array([10.0, 10.0, 6.0, 6.0])
    low = np.array([9.0, 9.0, 1.0, 1.0])
    close = np.array([9.5, 9.5, 1.5, 1.5])
    atr = np.ones(4)
    # demand box 4..6, distal 3: bar 2 enters it and closes at 1.5, below distal
    mine, theirs = _both(time, high, low, close, atr, 6.0, 4.0, 3.0, True, 0, PARAMS)
    assert mine == theirs
    assert mine.state is ZoneState.BROKEN
    assert mine.touches == 1, "the bar that broke it was also inside it"
    assert mine.break_index == 2


def test_consecutive_bars_inside_are_one_visit():
    time = np.arange(6, dtype=np.int64)
    high = np.full(6, 6.0)
    low = np.full(6, 4.0)
    close = np.full(6, 5.0)
    atr = np.ones(6)
    mine, theirs = _both(time, high, low, close, atr, 6.0, 4.0, 0.0, True, 0, PARAMS)
    assert mine == theirs
    assert mine.touches == 1


def test_two_separate_visits_count_twice():
    time = np.arange(5, dtype=np.int64)
    high = np.array([6.0, 20.0, 6.0, 20.0, 20.0])
    low = np.array([4.0, 19.0, 4.0, 19.0, 19.0])
    close = np.array([5.0, 19.5, 5.0, 19.5, 19.5])
    atr = np.ones(5)
    mine, theirs = _both(time, high, low, close, atr, 6.0, 4.0, 0.0, True, 0, PARAMS)
    assert mine == theirs
    assert mine.touches == 2


def test_a_start_past_the_end_is_fresh_and_does_not_raise():
    """Refinement can push `start` beyond the series on a very short chart."""
    time, high, low, close, atr = _series(20, 3)
    mine, theirs = _both(
        time, high, low, close, atr, 200.0, 199.0, 198.0, True, 20, PARAMS
    )
    assert mine == theirs
    assert mine.state is ZoneState.FRESH


def test_a_box_price_never_reaches_stays_fresh():
    """Far BELOW price, not above.

    Written the other way round first, and both implementations agreed it was
    BROKEN - correctly. A demand box parked above the market has its distal
    above the market too, so the very first close is already beyond it. The
    only untouched demand box is one price never falls to, which is this one.
    """
    time, high, low, close, atr = _series(200, 9)
    far = float(low.min()) - 1000.0
    mine, theirs = _both(
        time, high, low, close, atr, far + 1, far, far - 1, True, 0, PARAMS
    )
    assert mine == theirs
    assert mine.state is ZoneState.FRESH
    assert mine.touches == 0 and mine.first_test_time is None


def test_arrival_atr_is_read_at_the_first_touch_only():
    """It is a single scalar taken at one bar, and the bar has to be that one."""
    time, high, low, close, atr = _series(300, 4)
    mid = float(np.median(close))
    mine, theirs = _both(
        time, high, low, close, atr, mid + 0.5, mid - 0.5, mid - 50.0,
        True, 0, PARAMS,
    )
    assert mine == theirs
    assert mine.arrival_atr == theirs.arrival_atr
