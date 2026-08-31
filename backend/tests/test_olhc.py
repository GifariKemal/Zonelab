"""Single-candle rejection structure: accumulation, distribution, neutral."""

from app.models import Candle
from app.olhc import classify


def _c(o, h, l, c):
    return Candle(time=0, open=o, high=h, low=l, close=c, volume=0.0)


def test_a_lower_wick_with_a_high_close_is_accumulation():
    kind, pos, lw, uw = classify(_c(100.0, 102.0, 98.0, 101.5))
    assert kind == "accumulation"
    assert pos > 0.5
    assert lw > uw


def test_an_upper_wick_with_a_low_close_is_distribution():
    kind, pos, lw, uw = classify(_c(101.0, 103.0, 99.0, 99.5))
    assert kind == "distribution"
    assert pos < 0.5
    assert uw > lw


def test_a_clean_trend_candle_with_no_wick_is_neutral():
    # A candle that went straight up and closed on its high rejected nothing.
    kind, *_ = classify(_c(100.0, 102.0, 100.0, 102.0))
    assert kind == "neutral"


def test_a_middle_doji_is_neutral():
    kind, *_ = classify(_c(100.0, 101.0, 99.0, 100.0))
    assert kind == "neutral"


def test_a_zero_range_candle_is_neutral():
    kind, *_ = classify(_c(100.0, 100.0, 100.0, 100.0))
    assert kind == "neutral"
