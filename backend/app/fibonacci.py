"""Fibonacci / OTE (Optimal Trade Entry) matrix for POSKO 618.

The "618" in POSKO 618 is the golden ratio. This module computes the ICT
Fibonacci levels over the current institutional structural swing and
classifies where a zone's entry sits relative to the OTE sweet spot.

THE RATIOS (absolute, as the practitioner writes them):
    Equilibrium            0.500
    OTE Zone               0.618, 0.705, 0.786   (the sweet spot)
    Invalidation           1.000                 (stop beyond the swing)
    Extensions (DOL)       -0.270, -0.618, -1.000

For a BULLISH swing (swing low -> swing high), the retracement is measured
DOWNWARD from the high: a level of 0.618 means price pulled back to 61.8%
of the way from the high back to the low. A zone whose proximal sits inside
0.618-0.786 is a deep discount — the OTE sweet spot.

For a BEARISH swing (swing high -> swing low), the retracement is measured
UPWARD from the low: 0.618 means price rallied to 61.8% of the way back up.
A supply zone whose proximal sits inside 0.618-0.786 is a deep premium.

WHAT THIS IS NOT. It is not a direction claim. It answers "is this entry
deep enough in the discount/premium to be worth the risk", and nothing about
where price goes next.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The OTE sweet-spot bounds, in retracement ratio. A zone entry inside
#: [OTE_LOW, OTE_HIGH] is "deep in the discount/premium".
OTE_LOW = 0.618
OTE_HIGH = 0.786

#: Equilibrium, and the "no man's land" threshold: an entry at or above 0.5
#: (bullish, retracing shallow) is NOT deep enough to be the OTE.
EQUILIBRIUM = 0.5

#: Extensions below/above the swing, quoted as the source writes them.
EXTENSIONS = (-1.0, -0.618, -0.27)


@dataclass(frozen=True)
class FibLevels:
    """One structural swing and the Fibonacci levels over it."""

    #: The swing anchor. For bullish: swing_low is 0.0, swing_high is 1.0.
    #: For bearish: swing_high is 0.0, swing_low is 1.0.
    swing_low: float
    swing_high: float
    #: True when the swing is bullish (low -> high), the OTE is a discount.
    bullish: bool
    #: The retracement ratio of the current price (0..1, or negative past
    #: the swing for extensions). None when the swing has no height.
    position: float | None


def levels(swing_low: float, swing_high: float, price: float) -> FibLevels:
    """Fibonacci levels and current position over one swing.

    `swing_low` and `swing_high` are the two anchors. The swing is bullish
    when the high is more recent (price is retracing down from it); bearish
    when the low is more recent. The caller determines direction from the
    zone's own side, not from the anchor ordering.

    `position` is the retracement ratio: 0.0 at the low, 1.0 at the high.
    For a bullish pullback, price retraces DOWN from 1.0 toward 0.0, and the
    OTE is the 0.618-0.786 band (price near the low). For a bearish rally,
    price retraces UP from 0.0 toward 1.0, and the OTE is the same band but
    read as price near the high.
    """
    height = swing_high - swing_low
    if height <= 0:
        return FibLevels(swing_low=swing_low, swing_high=swing_high,
                         bullish=swing_high > swing_low, position=None)
    pos = (price - swing_low) / height
    return FibLevels(
        swing_low=swing_low,
        swing_high=swing_high,
        bullish=swing_high > swing_low,
        position=float(pos),
    )


def price_at(swing_low: float, swing_high: float, ratio: float) -> float:
    """The absolute price at a Fibonacci ratio over the swing.

    `ratio` 0.0 is the low, 1.0 is the high, 0.618 is 61.8% up from the low,
    -0.27 is 27% below the low (an extension).
    """
    return swing_low + ratio * (swing_high - swing_low)


def ote_bounds(swing_low: float, swing_high: float) -> tuple[float, float]:
    """The absolute OTE band: (price at 0.786, price at 0.618)."""
    return (
        price_at(swing_low, swing_high, OTE_HIGH),
        price_at(swing_low, swing_high, OTE_LOW),
    )


def in_ote(position: float | None) -> bool:
    """Whether the price sits inside the OTE sweet spot.

    `position` is (price - swing_low) / height, so 0.0 is the swing low and
    1.0 is the swing high. The OTE retracement band (0.618-0.786 measured
    DOWN from the high) maps to position [1-0.786, 1-0.618] = [0.214, 0.382]:
    price near the swing low, deep in the discount.
    """
    if position is None:
        return False
    return (1.0 - OTE_HIGH) <= position <= (1.0 - OTE_LOW)


def in_no_mans_land(position: float | None) -> bool:
    """Whether the price sits in the shallow zone around equilibrium.

    `position` near 0.5 (retracement 0.5) is equilibrium — neither deep
    discount nor deep premium. A shallow pullback that has not travelled
    into the OTE band is the no-man's-land where the entry risk is not
    compensated by depth.
    """
    if position is None:
        return False
    return abs(position - EQUILIBRIUM) <= 0.12