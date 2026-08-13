"""Build higher-timeframe candles from lower-timeframe ones.

Supply and demand is a top-down method: the zone belongs to the higher
timeframe, the entry belongs to the lower one. Drawing an H4 zone on an M15
chart therefore means computing it from H4 bars, not from M15 bars, and the
only honest way to get H4 bars here is to aggregate the M15 series the chart is
already showing.

Three things make that correct rather than merely plausible.

1. **The aggregate is anchored to the epoch, not to the first bar in view.**
   Bucketing by `time // step * step` puts every H4 bar on the same boundary
   regardless of where the requested window happens to start. Anchoring to the
   first bar instead would move every HTF zone whenever the user changed the
   bar count, which looks exactly like a detector bug.

2. **The final bucket is dropped unless it is complete.** A forming H4 bar has
   a high and low that will still change. A zone built on it would move under
   the user, and would also be a look-ahead if anyone measured it later.

3. **Buckets with no bars simply do not exist.** Weekends and holidays leave
   gaps in gold and FX. Emitting a flat bar to fill the gap would invent a
   consolidation that never happened, which is precisely the shape this
   detector looks for.
"""

from __future__ import annotations

from .models import Candle
from .providers.base import INTERVALS


def resample(
    candles: list[Candle], target: str, source: str, session_offset_hours: float = 0.0
) -> list[Candle]:
    """Aggregate `candles` up to the `target` interval.

    `session_offset_hours` shifts the grid off UTC midnight. This is not a
    nicety: a broker whose trading day starts at 22:00 or 01:00 puts its H4 and
    D1 candles on a different grid than a UTC-anchored aggregate, and the result
    is a zone drawn one candle away from where the same zone appears in the
    trading terminal. It is the most common cause of "the H4 zone is off by
    one" and it is invisible unless you compare the two charts side by side.

    Returns an empty list when the target is not strictly higher than the
    source; callers treat that as "no higher timeframe available" rather than
    as an error, because it happens naturally when the user picks 1d on a
    chart already showing 1d.
    """
    step = INTERVALS[target]
    if step <= INTERVALS[source] or not candles:
        return []

    # Floor-divide handles negative offsets correctly in Python, so a broker day
    # starting at 22:00 the previous evening can be written as -2.
    shift = int(session_offset_hours * 3600)
    buckets: dict[int, list[Candle]] = {}
    for candle in candles:
        start = ((candle.time - shift) // step) * step + shift
        buckets.setdefault(start, []).append(candle)

    out: list[Candle] = []
    for start in sorted(buckets):
        group = buckets[start]
        out.append(
            Candle(
                time=start,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
            )
        )

    # The last bucket is complete only if the source series actually runs past
    # its end. A bucket that merely contains "enough" bars is not enough: a
    # session can close early and leave a short but genuinely finished bar,
    # while a live bar can be full-length and still be forming.
    if out and candles[-1].time + INTERVALS[source] < out[-1].time + step:
        out.pop()

    return out


def bucket_close(bucket_open: int, target: str) -> int:
    """When the HTF bar opening at `bucket_open` finishes.

    This is the instant its zone becomes knowable. Anything drawn earlier is a
    zone the trader could not have seen.
    """
    return bucket_open + INTERVALS[target]
