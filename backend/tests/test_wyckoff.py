"""Wyckoff phase readings: spring, upthrust, SOS, SOW over a rolling range."""

from app.models import Candle
from app.wyckoff import phases


def _c(time, o, h, l, c):
    return Candle(time=time, open=o, high=h, low=l, close=c, volume=0.0)


def _range_run(n, low=100.0, high=101.0):
    """`n` bars oscillating in a tight range, so the rolling range is stable."""
    return [
        _c(1000 + i * 60, low + 0.5, high, low, low + 0.5) for i in range(n)
    ]


def test_a_sweep_below_the_range_low_that_closes_back_is_a_spring():
    # A stable range, then one bar that sweeps below it and closes back inside.
    bars = _range_run(25)
    bars.append(_c(1000 + 25 * 60, 100.0, 100.2, 99.0, 100.5))  # low 99 < range low 100
    out = [p for p in phases(bars, lookback=20) if p.kind == "spring"]
    assert any(p.at == 25 for p in out)


def test_a_close_above_the_range_high_is_a_sos():
    bars = _range_run(25)
    bars.append(_c(1000 + 25 * 60, 100.5, 102.0, 100.3, 101.8))  # close 101.8 > high 101
    out = [p for p in phases(bars, lookback=20) if p.kind == "sos"]
    assert any(p.at == 25 for p in out)


def test_a_close_below_the_range_low_is_a_sow():
    bars = _range_run(25)
    bars.append(_c(1000 + 25 * 60, 100.0, 100.3, 98.0, 98.5))  # close 98.5 < low 100
    out = [p for p in phases(bars, lookback=20) if p.kind == "sow"]
    assert any(p.at == 25 for p in out)


def test_a_sweep_above_the_range_high_that_closes_back_is_an_upthrust():
    bars = _range_run(25)
    bars.append(_c(1000 + 25 * 60, 100.5, 102.0, 100.0, 100.8))  # high 102 > high 101, closes back
    out = [p for p in phases(bars, lookback=20) if p.kind == "upthrust"]
    assert any(p.at == 25 for p in out)


def test_no_phase_before_the_warm_up():
    bars = _range_run(10)
    assert phases(bars, lookback=20) == []
