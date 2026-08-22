"""Layer state at one bar, and the one property the whole thing rests on.

If `at_bar` can see a single bar past `index`, every conditioning study built on
it reports the answer read off the back of the paper. That is asserted directly
below rather than argued: the state computed from the full series must equal the
state computed from the series truncated at that bar.
"""

from __future__ import annotations

import asyncio

import pytest

from app.conditions import _band, at_bar
from app.providers import get_candles


@pytest.fixture(scope="module")
def series():
    return asyncio.run(get_candles("XAUUSD", "1h", 1200, "synthetic"))[0]


@pytest.mark.parametrize("index", [400, 700, 1100])
def test_no_field_can_see_past_its_own_bar(series, index):
    """The anti-lookahead property, stated as an equality.

    Truncating the series after `index` must change nothing, because nothing
    after `index` was allowed to enter the answer. A single field that reads
    `candles[-1]` instead of `past[-1]` fails this and fails it loudly.
    """
    full = at_bar(series, index, "1h")
    truncated = at_bar(series[: index + 1], index, "1h")
    assert full == truncated, {
        key: (full.get(key), truncated.get(key))
        for key in set(full) | set(truncated)
        if full.get(key) != truncated.get(key)
    }


def test_every_column_is_present_even_when_it_is_unknown(series):
    """A study groups by these keys. A key that vanishes when its layer has
    nothing to say turns a group-by into a silent row filter, and the row that
    disappears is exactly the warm-up case worth knowing about."""
    early = at_bar(series, 30, "1h")  # too early for most layers
    late = at_bar(series, 1100, "1h")
    assert set(early) == set(late), set(early) ^ set(late)


def test_an_index_outside_the_series_is_empty_and_not_a_guess(series):
    assert at_bar(series, len(series), "1h") == {}
    assert at_bar(series, -1, "1h") == {}
    assert at_bar([], 0, "1h") == {}


def test_the_bar_reported_is_the_bar_asked_for(series):
    got = at_bar(series, 500, "1h")
    assert got["at"] == series[500].time
    assert got["close"] == series[500].close


def test_a_degree_the_series_cannot_build_reads_unknown(series):
    """15m cannot be aggregated from hourly bars - resampling only goes upward -
    so its bias is None. Asserted so the limitation stays visible instead of
    being mistaken for a market with no short-term structure."""
    assert at_bar(series, 1100, "1h")["bias_15m"] is None


# ------------------------------------------------------------------- the bands


def test_a_saturated_range_position_is_not_called_premium():
    """`position_at` clips to 0..1, so 1.0 means "at or above the high" and can
    equally mean six range heights above it. Folding that into `premium` is what
    made 40 of 40 divergences read premium in this project's own analysis."""
    assert _band(1.0) == "at_or_above_high"
    assert _band(0.0) == "at_or_below_low"


def test_the_bands_between_the_extremes():
    assert _band(0.9) == "premium"
    assert _band(0.75) == "premium"
    assert _band(0.5) == "equilibrium"
    assert _band(0.25) == "discount"
    assert _band(0.1) == "discount"
    assert _band(None) is None
