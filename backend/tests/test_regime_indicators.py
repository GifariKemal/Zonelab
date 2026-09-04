"""Smoke tests for ADX and BB Width indicators."""

import numpy as np
import pytest

from app.indicators import wilder_adx, bb_width


@pytest.fixture
def trending_series():
    """Steady uptrend: high ADX expected."""
    n = 200
    close = np.linspace(100, 200, n)
    noise = np.random.default_rng(42).normal(0, 0.5, n)
    close = close + noise
    high = close + np.abs(noise) + 1
    low = close - np.abs(noise) - 1
    return high, low, close


@pytest.fixture
def ranging_series():
    """Sine wave: low ADX expected."""
    n = 200
    t = np.linspace(0, 8 * np.pi, n)
    close = 100 + 5 * np.sin(t)
    high = close + 1
    low = close - 1
    return high, low, close


class TestWilderAdx:
    def test_shape(self, trending_series):
        h, l, c = trending_series
        adx = wilder_adx(h, l, c, 14)
        assert adx.shape == c.shape

    def test_range_0_100(self, trending_series):
        h, l, c = trending_series
        adx = wilder_adx(h, l, c, 14)
        assert np.all(adx >= 0)
        assert np.all(adx <= 100)

    def test_trending_higher_than_ranging(self, trending_series, ranging_series):
        adx_trend = wilder_adx(*trending_series, 14)
        adx_range = wilder_adx(*ranging_series, 14)
        assert adx_trend[-1] > adx_range[-1]

    def test_short_input(self):
        c = np.array([100.0, 101.0])
        h = c + 1
        l = c - 1
        adx = wilder_adx(h, l, c, 14)
        assert adx.shape == (2,)
        assert np.all(adx == 0)


class TestBbWidth:
    def test_shape(self, trending_series):
        _, _, c = trending_series
        w = bb_width(c, 20, 2.0)
        assert w.shape == c.shape

    def test_positive(self, trending_series):
        _, _, c = trending_series
        w = bb_width(c, 20, 2.0)
        assert np.all(w >= 0)

    def test_constant_close_zero_width(self):
        c = np.full(50, 100.0)
        w = bb_width(c, 20, 2.0)
        assert w[-1] == pytest.approx(0.0)

    def test_volatile_wider(self):
        rng = np.random.default_rng(42)
        calm = np.full(100, 100.0) + rng.normal(0, 0.1, 100)
        wild = np.full(100, 100.0) + rng.normal(0, 5.0, 100)
        assert bb_width(calm, 20, 2.0)[-1] < bb_width(wild, 20, 2.0)[-1]
