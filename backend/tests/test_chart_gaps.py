"""Breakaway and measuring gaps: detection geometry and the classification."""

from app.chart_gaps import _atr, chart_gaps
from app.models import Candle


def _c(time, o, h, l, c):
    return Candle(time=time, open=o, high=h, low=l, close=c, volume=0.0)


def _flat_run(n, base=100.0, step=0.0):
    """A quiet window of `n` bars, each a small doji around `base`."""
    return [
        _c(1000 + i * 60, base, base + 0.5, base - 0.5, base)
        for i in range(n)
    ]


def test_a_gap_up_is_detected_and_classified_breakaway_when_flat_before():
    # A quiet window, then a bar that gaps up out of the range. The window must
    # exceed the lookback floor (lookback + 2 bars) or the detector answers empty.
    bars = _flat_run(25)
    bars.append(_c(1000 + 25 * 60, 105.0, 106.0, 104.5, 105.5))
    gaps = chart_gaps(bars)
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.up is True
    assert gap.kind == "breakaway"


def test_a_gap_down_is_detected():
    bars = _flat_run(25)
    bars.append(_c(1000 + 25 * 60, 95.0, 95.5, 94.0, 94.5))
    gaps = chart_gaps(bars)
    assert len(gaps) == 1
    assert gaps[0].up is False
    assert gaps[0].kind == "breakaway"


def test_a_gap_inside_a_trend_is_measuring():
    # A rising run where each bar OVERLAPS the previous (so no spurious gap), then
    # one bar that clearly gaps up and continues the move. Prior bars trend, so it
    # is measuring, not breakaway.
    bars = [
        _c(1000 + i * 60, 100.0 + i, 100.0 + i + 1.0, 100.0 + i - 0.5, 100.0 + i + 0.8)
        for i in range(25)
    ]
    bars.append(_c(1000 + 25 * 60, 130.0, 131.0, 129.5, 130.5))
    gaps = chart_gaps(bars)
    assert len(gaps) == 1
    assert gaps[0].kind == "measuring"


def test_no_gap_when_bars_overlap():
    # Two overlapping bars leave no price hole.
    bars = [
        _c(1000, 100.0, 101.0, 99.0, 100.5),
        _c(1060, 100.5, 100.8, 99.5, 100.2),
    ]
    # A short window below the lookback floor returns nothing, so pad it.
    bars = _flat_run(20) + bars
    gaps = chart_gaps(bars)
    assert all(g.at != len(bars) - 1 for g in gaps)


def test_atr_is_zero_for_one_bar():
    assert _atr([_c(1000, 100, 101, 99, 100)]) == 0.0


def test_a_gap_down_band_is_the_hole_not_the_previous_bar():
    # THE HOLE, AND ONLY THE HOLE. Until 1 September 2026 a gap down published
    # `top=prev.high`, which folded the whole previous bar's range into the band
    # and drew it that tall on the chart. Four tests passed over it because none
    # of them read `top` or `bottom`.
    bars = _flat_run(25)                     # each bar 99.5 .. 100.5
    bars.append(_c(1000 + 25 * 60, 95.0, 95.5, 94.0, 94.5))
    gap = chart_gaps(bars)[0]
    assert gap.up is False
    assert gap.bottom == 95.5                # the gap bar's high
    assert gap.top == 99.5                   # the previous bar's LOW
    assert gap.top - gap.bottom == 4.0       # not 5.0, the previous range


def test_a_gap_up_band_is_the_hole():
    bars = _flat_run(25)
    bars.append(_c(1000 + 25 * 60, 105.0, 106.0, 104.5, 105.5))
    gap = chart_gaps(bars)[0]
    assert gap.up is True
    assert gap.bottom == 100.5               # the previous bar's high
    assert gap.top == 104.5                  # the gap bar's low


def test_a_breakaway_gap_publishes_no_measuring_target():
    # The halfway rule is a measuring gap's claim. Drawing it on a breakaway put
    # a dashed projection on the chart that no source publishes.
    bars = _flat_run(25)
    bars.append(_c(1000 + 25 * 60, 105.0, 106.0, 104.5, 105.5))
    gap = chart_gaps(bars)[0]
    assert gap.kind == "breakaway"
    assert gap.target is None


def test_a_measuring_gap_keeps_its_halfway_target():
    bars = [
        _c(1000 + i * 60, 100.0 + i, 100.0 + i + 1.0, 100.0 + i - 0.5, 100.0 + i + 0.8)
        for i in range(25)
    ]
    bars.append(_c(1000 + 25 * 60, 130.0, 131.0, 129.5, 130.5))
    gap = chart_gaps(bars)[0]
    assert gap.kind == "measuring"
    assert gap.target == gap.move_start + 2 * (129.5 - gap.move_start)
