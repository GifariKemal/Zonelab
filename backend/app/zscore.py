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


#: Below this, the rolling sigma is floating-point noise rather than a spread
#: that moves. A real log-spread's sigma runs 1e-3 to 1e-1; a spread that is
#: algebraically constant still scatters by about 1e-16, and dividing by that
#: turned two perfectly co-moving series into a 2.55 sigma "divergence".
SIGMA_FLOOR = 1e-9


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
        # `> SIGMA_FLOOR`, NOT `> 0`, and the difference is a divergence this
        # module used to invent. Two series that move perfectly together have an
        # algebraically CONSTANT log spread, but in floating point that constant
        # still scatters by about 1e-16 - so sigma came out at 4e-16, the
        # deviation was divided by it, and a perfectly correlated pair reported
        # Z = -2.55. `tools/quant.py` treats |Z| >= 2.0 as a correlation
        # fracture, so the one input that most clearly means "no fracture"
        # produced one. In log space a real spread's sigma runs 1e-3 to 1e-1,
        # six orders of magnitude above this floor, so nothing real is lost.
        if sigma > SIGMA_FLOOR:
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


def direction(z_value: float, threshold: float = 2.0) -> str:
    """The direction of the divergence.

    'up' means asset A is overvalued relative to B (A should fall).
    'down' means asset A is undervalued relative to B (A should rise).
    'neutral' means no significant divergence.

    THE THRESHOLD IS A PARAMETER HERE TOO, and it was not. `validate` took one
    and this function hardcoded 2.0, so a caller lowering the bar to 1.5 got a
    value `validate` called significant and this function called neutral - two
    functions in one file disagreeing about the same reading. Same default, one
    definition of the comparison.
    """
    if np.isnan(z_value) or not validate(z_value, threshold):
        return "neutral"
    return "up" if z_value > 0 else "down"