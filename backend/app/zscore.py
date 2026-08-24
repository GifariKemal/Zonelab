"""Z-Score Cointegration — institutional correlation fracture detection.

Visual SSMT divergence is necessary but not sufficient. A true institutional
correlation fracture occurs when the spread between two correlated assets
deviates beyond statistical norms. This module computes the Z-Score of the
spread and only validates an SSMT when the Z-Score breaches the ±2.0
threshold.

FORMULA:
    spread = log(price_A) - log(price_B)   (log spread, scale-invariant)
    Z = (spread - rolling_mean) / rolling_std

    Valid SSMT requires |Z| >= 2.0 — the spread is at least 2 standard
    deviations from its rolling mean, proving the divergence is statistically
    significant and not just noise.

USAGE:
    from app.zscore import zscore, validate
    z = zscore(prices_a, prices_b, lookback=50)
    if validate(z[-1]):
        # correlation fracture confirmed
"""

from __future__ import annotations

import numpy as np


def spread(prices_a: np.ndarray, prices_b: np.ndarray) -> np.ndarray:
    """Log spread between two price series. Scale-invariant."""
    return np.log(prices_a) - np.log(prices_b)


def zscore(
    prices_a: np.ndarray,
    prices_b: np.ndarray,
    lookback: int = 50,
) -> np.ndarray:
    """Rolling Z-Score of the log spread between two assets.

    Returns an array the same length as the inputs. The first `lookback-1`
    values are NaN (warm-up). The Z-Score measures how many standard
    deviations the current spread is from its rolling mean.

    A Z-Score of +2.0 means asset A is overvalued relative to B by 2σ.
    A Z-Score of -2.0 means asset A is undervalued relative to B by 2σ.
    """
    s = spread(prices_a, prices_b)
    z = np.full_like(s, np.nan)
    for i in range(lookback, len(s) + 1):
        window = s[i - lookback : i]
        mu = window.mean()
        sigma = window.std(ddof=1)
        if sigma > 0:
            z[i - 1] = (s[i - 1] - mu) / sigma
    return z


def validate(z_value: float, threshold: float = 2.0) -> bool:
    """Whether the Z-Score indicates a statistically significant divergence.

    True when |Z| >= threshold, meaning the spread is at least `threshold`
    standard deviations from its rolling mean.
    """
    if np.isnan(z_value):
        return False
    return abs(z_value) >= threshold


def direction(z_value: float) -> str:
    """The direction of the divergence.

    'up' means asset A is overvalued relative to B (A should fall).
    'down' means asset A is undervalued relative to B (A should rise).
    'neutral' means no significant divergence.
    """
    if np.isnan(z_value) or abs(z_value) < 2.0:
        return "neutral"
    return "up" if z_value > 0 else "down"