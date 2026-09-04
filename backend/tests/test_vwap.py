"""VWAP and volume profile, tested against hand-computed values.

Three bars is enough to prove the cumulative formula is right.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.indicators import vwap, volume_profile


# ---- VWAP ----


def test_vwap_three_bars():
    """Manual: TP = (H+L+C)/3, then cum(TP*V) / cum(V)."""
    high = np.array([12.0, 14.0, 13.0])
    low = np.array([10.0, 11.0, 11.0])
    close = np.array([11.0, 13.0, 12.0])
    volume = np.array([100.0, 200.0, 150.0])

    # tp = (H+L+C)/3 -> [11.0, 12.667, 12.0]
    # bar 0: cum_tpv = 11*100 = 1100,    cum_vol = 100,   vwap = 11.0
    # bar 1: cum_tpv = 1100 + 12.667*200 = 3633.33, cum_vol = 300, vwap = 12.111
    # bar 2: cum_tpv = 3633.33 + 12*150 = 5433.33,  cum_vol = 450, vwap = 12.074

    result = vwap(high, low, close, volume)
    assert result[0] == pytest.approx(11.0, abs=1e-6)
    assert result[1] == pytest.approx(3633.333333 / 300, abs=1e-4)
    assert result[2] == pytest.approx(5433.333333 / 450, abs=1e-4)


def test_vwap_with_anchor():
    """Bars before anchor_idx are NaN."""
    high = np.array([12.0, 14.0, 13.0, 15.0])
    low = np.array([10.0, 11.0, 11.0, 12.0])
    close = np.array([11.0, 13.0, 12.0, 14.0])
    volume = np.array([100.0, 200.0, 150.0, 300.0])

    result = vwap(high, low, close, volume, anchor_idx=2)
    assert np.isnan(result[0])
    assert np.isnan(result[1])
    assert not np.isnan(result[2])
    # Bar 2 is the anchor, so VWAP there is just TP of bar 2
    tp2 = (13.0 + 11.0 + 12.0) / 3.0
    assert result[2] == pytest.approx(tp2, abs=1e-6)


def test_vwap_single_bar():
    """One bar: VWAP = typical price."""
    high = np.array([10.0])
    low = np.array([8.0])
    close = np.array([9.0])
    volume = np.array([500.0])
    result = vwap(high, low, close, volume)
    assert result[0] == pytest.approx(9.0, abs=1e-6)


def test_vwap_zero_volume():
    """Zero volume across all bars: falls back to TP (guarded by EPS)."""
    high = np.array([10.0, 11.0])
    low = np.array([8.0, 9.0])
    close = np.array([9.0, 10.0])
    volume = np.array([0.0, 0.0])
    result = vwap(high, low, close, volume)
    # Should not be NaN or inf
    assert np.isfinite(result[0])
    assert np.isfinite(result[1])


def test_vwap_empty():
    result = vwap(
        np.array([]), np.array([]), np.array([]), np.array([])
    )
    assert len(result) == 0


# ---- Volume profile ----


def test_volume_profile_poc():
    """POC should be at the bin where the most volume concentrates."""
    # Three bars, all volume at the high end
    high = np.array([100.0, 100.0, 100.0])
    low = np.array([90.0, 98.0, 98.0])
    close = np.array([95.0, 99.0, 99.0])
    volume = np.array([10.0, 1000.0, 1000.0])

    vp = volume_profile(high, low, close, volume, bins=10)
    # POC should be near 99 (top of range), not near 95
    assert vp["poc"] > 95.0
    assert vp["vah"] >= vp["poc"]
    assert vp["val"] <= vp["poc"]


def test_volume_profile_value_area():
    """VAH >= POC >= VAL always."""
    high = np.array([50.0, 55.0, 45.0, 52.0])
    low = np.array([40.0, 48.0, 40.0, 46.0])
    close = np.array([45.0, 52.0, 43.0, 50.0])
    volume = np.array([100.0, 200.0, 100.0, 150.0])

    vp = volume_profile(high, low, close, volume, bins=20)
    assert vp["vah"] >= vp["poc"]
    assert vp["val"] <= vp["poc"]
    assert len(vp["bins"]) == 20


def test_volume_profile_single_bar():
    """Single bar, flat range (high == low): POC = VAH = VAL."""
    high = np.array([100.0])
    low = np.array([100.0])
    close = np.array([100.0])
    volume = np.array([500.0])

    vp = volume_profile(high, low, close, volume)
    assert vp["poc"] == pytest.approx(100.0, abs=1e-6)
    assert vp["vah"] == vp["poc"]
    assert vp["val"] == vp["poc"]


def test_volume_profile_zero_volume():
    """All zero volume: POC still computable, no crash."""
    high = np.array([10.0, 12.0])
    low = np.array([8.0, 9.0])
    close = np.array([9.0, 11.0])
    volume = np.array([0.0, 0.0])

    vp = volume_profile(high, low, close, volume, bins=5)
    assert "poc" in vp
    assert "bins" in vp


def test_volume_profile_empty():
    vp = volume_profile(
        np.array([]), np.array([]), np.array([]), np.array([])
    )
    assert vp["bins"] == []
