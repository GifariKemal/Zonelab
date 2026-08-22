"""A series labelled 1h may not be spaced a day apart without saying so.

Found through a symptom that looked like something else entirely: a trade
reporting 42 nights held on an 80-bar horizon. Impossible at one bar an hour,
ordinary at one bar a day - and the oldest 1,314 bars of a 35,192-bar hourly
request from the terminal are exactly that, because it has no deep intraday
history and serves what it has.
"""

from __future__ import annotations

from app.models import Candle
from tools.history import irregular_prefix

STEP = 3600


def bars(gaps: list[int], start: int = 1_700_000_000) -> list[Candle]:
    """One more candle than there are gaps, spaced by `gaps` in order."""
    times, cursor = [start], start
    for gap in gaps:
        cursor += gap
        times.append(cursor)
    return [
        Candle(time=t, open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)
        for t in times
    ]


def test_a_clean_hourly_series_has_no_irregular_prefix():
    assert irregular_prefix(bars([STEP] * 200), "1h") == 0


def test_weekend_holes_do_not_make_a_series_irregular():
    """A market shuts. Two-day gaps every 120 bars are gold, not corruption, and
    a check that flagged them would fire on every real series."""
    gaps = []
    for block in range(4):
        gaps += [STEP] * 120 + [2 * 86400]
    assert irregular_prefix(bars(gaps), "1h") == 0


def test_a_daily_prefix_is_counted():
    """The real shape: a stretch at one bar a day, then the genuine hourly
    history."""
    gaps = [86400] * 80 + [STEP] * 200
    assert irregular_prefix(bars(gaps), "1h") == 80


def test_a_series_that_is_daily_throughout_is_entirely_irregular():
    """No hourly stretch anywhere means no honest answer to a 1h question, and
    the count says so rather than returning a comfortable 0."""
    got = irregular_prefix(bars([86400] * 200), "1h")
    assert got == 201, got


def test_a_series_too_short_to_judge_returns_zero_rather_than_a_guess():
    """Under one window there is nothing to compare against. Zero here means
    unknown, and the caller cannot act on it either way."""
    assert irregular_prefix(bars([STEP] * 10), "1h") == 0


def test_the_check_is_about_the_interval_asked_for():
    """The same bars are a clean daily series and an irregular hourly one."""
    daily = bars([86400] * 200)
    assert irregular_prefix(daily, "1d") == 0
    assert irregular_prefix(daily, "1h") > 0
