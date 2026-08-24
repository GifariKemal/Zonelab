"""Volume Delta Filter — reject low-volume FVG zones.

An FVG without volume is a vacuum, not an institutional footprint. The
practitioner's rule: if the volume during the FVG creation is below the
20-period moving average of volume, the zone is a LOW_VOLUME_VOID and
must be HARD REJECTED from the execution pipeline.

The Proximal limit order must only be placed on high-volume structural
shifts — where institutions actually left footprints.

MEASUREMENT. The volume of the three candles that create the FVG is
compared to the trailing 20-bar average volume. If the total volume of
the three FVG candles is below the average, the zone is tagged as
LOW_VOLUME_VOID.
"""

from __future__ import annotations

import numpy as np

from .models import Candle, Zone

VOLUME_LOOKBACK = 20


def volume_ratio(candles: list[Candle], idx: int) -> float | None:
    """The volume ratio at bar `idx` relative to the trailing average.

    Returns the ratio of the current bar's volume to the trailing 20-bar
    average volume. > 1.0 means above average (institutional). < 1.0 means
    below average (retail noise).

    Returns None when there aren't enough bars for the lookback.
    """
    if idx < VOLUME_LOOKBACK:
        return None
    window = [c.volume for c in candles[idx - VOLUME_LOOKBACK : idx]]
    avg = np.mean(window)
    if avg <= 0:
        return None
    return float(candles[idx].volume / avg)


def fvg_volume_ok(zone: Zone, candles: list[Candle]) -> bool:
    """Whether the zone's formation volume is sufficient.

    For FVG zones: checks the three candles that create the gap.
    For supply/demand zones: checks the leg-out candles (the impulse).

    Returns True when the volume is above the trailing average, meaning
    the zone was created by institutional volume.
    """
    if zone.anatomy is None:
        return True  # no anatomy, can't check, allow

    # Check the leg-out volume: the candles that created the move
    from_idx = zone.anatomy.leg_out_from
    to_idx = zone.anatomy.leg_out_to
    if from_idx >= len(candles) or to_idx >= len(candles):
        return True

    # Average volume during the leg-out
    vols = [c.volume for c in candles[from_idx : to_idx + 1]]
    if not vols:
        return True

    leg_vol = np.mean(vols)

    # Trailing average before the leg-out
    if from_idx < VOLUME_LOOKBACK:
        return True  # not enough history, allow
    trailing = [c.volume for c in candles[from_idx - VOLUME_LOOKBACK : from_idx]]
    avg = np.mean(trailing)
    if avg <= 0:
        return True

    return leg_vol >= avg