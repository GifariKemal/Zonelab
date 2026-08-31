"""PSP: the 3-candle window is honoured, and the harness arithmetic is sound."""

from app.models import Candle
from app.psp import detect


def _c(time, o, h, l, c):
    return Candle(time=time, open=o, high=h, low=l, close=c, volume=0.0)


def test_a_sweep_beyond_the_third_bar_is_not_a_psp():
    # An SSMT at index 0, then four quiet bars, and only on the FIFTH bar a sweep
    # and rejection. With lookback=3 that fifth bar is outside the window, so no
    # PSP. The default lookback changed from 10 to 3 to match "the last 3
    # candles", and this pins that the window is what it says.
    candles = [
        _c(1000 + i * 60, 100.0, 100.5, 99.5, 100.0) for i in range(6)
    ]
    # The sweep-and-rejection happens at index 5, four bars after the SSMT at 0.
    candles[5] = _c(1000 + 5 * 60, 100.0, 100.2, 98.0, 100.5)  # sweeps below 99, closes back
    # A level at 99.0, which the sweep at index 5 would take. But index 5 is
    # outside lookback=3 (indices 1..3 only).
    psp = detect(candles, ssmt_candle_idx=0, levels=[99.0], lookback=3)
    assert psp is None


def test_a_sweep_inside_the_window_is_a_psp():
    candles = [
        _c(1000 + i * 60, 100.0, 100.5, 99.5, 100.0) for i in range(4)
    ]
    # The sweep-and-rejection at index 2, inside lookback=3 (1..3).
    candles[2] = _c(1000 + 2 * 60, 100.0, 100.2, 98.0, 100.5)
    psp = detect(candles, ssmt_candle_idx=0, levels=[99.0], lookback=3)
    assert psp is not None
    assert psp.direction == "buy"
    assert psp.at == 2
