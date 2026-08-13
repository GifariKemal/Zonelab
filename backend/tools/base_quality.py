"""How many detected "bases" are actually slow trends?

    python -m tools.base_quality

The visual audit turned up an RBR whose base ran 4341, 4343, 4340, 4342, 4344,
4345 - a staircase, not a pause. The classifier admitted it because no single
candle in it was large enough to be an impulse, which is not the same test as
"price stopped going anywhere".

Two ratios separate a pause from a drift:

    drift  = |close[last] - open[first]| / base_height
             how much of the base's own height was one-way travel.
    overlap = mean fraction of each bar's range that overlaps the previous bar
             a real consolidation revisits the same prices; a staircase does not.

This measures both over the current detector output so the size of the problem
is known before anything is changed.
"""

from __future__ import annotations

import numpy as np

from app.detect.supply_demand import detect
from app.models import SupplyDemandParams
from tools import history

SERIES = [("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"), ("BTCUSDT", "15m"), ("ETHUSDT", "1h")]


def base_metrics(candles, zone) -> tuple[float, float]:
    a = zone.anatomy
    bars = candles[a.base_from : a.base_to + 1]
    height = zone.top - zone.bottom
    if height <= 0 or len(bars) == 0:
        return 0.0, 1.0

    drift = abs(bars[-1].close - bars[0].open) / height

    if len(bars) == 1:
        return drift, 1.0  # a single bar trivially overlaps itself
    overlaps = []
    for prev, cur in zip(bars, bars[1:]):
        span = max(cur.high, prev.high) - min(cur.low, prev.low)
        shared = min(cur.high, prev.high) - max(cur.low, prev.low)
        overlaps.append(max(0.0, shared) / span if span > 0 else 1.0)
    return drift, float(np.mean(overlaps))


def main() -> None:
    drifts, overlaps, rows = [], [], []
    for symbol, interval in SERIES:
        candles = history.load(symbol, interval, 20000)
        zones, _ = detect(
            candles,
            SupplyDemandParams(merge_overlap_pct=1.0, max_zones_per_side=100, show_broken=True),
        )
        for zone in zones:
            d, o = base_metrics(candles, zone)
            drifts.append(d)
            overlaps.append(o)
            rows.append((f"{symbol}-{interval}", zone.kind.value, len(candles), d, o))
        print(f"  {symbol}-{interval}: {len(zones)} zones")

    drifts, overlaps = np.array(drifts), np.array(overlaps)
    print(f"\nn = {len(drifts)} zones\n")

    print("drift, one-way travel as a fraction of the base's own height")
    for q in (10, 25, 50, 75, 90, 99):
        print(f"  p{q:<3} {np.percentile(drifts, q):.2f}")
    for t in (0.5, 0.7, 0.9):
        print(f"  drift > {t}: {(drifts > t).mean():.1%} of zones")

    print("\noverlap, mean shared range between consecutive base bars")
    for q in (1, 10, 25, 50, 75, 90):
        print(f"  p{q:<3} {np.percentile(overlaps, q):.2f}")
    for t in (0.2, 0.35, 0.5):
        print(f"  overlap < {t}: {(overlaps < t).mean():.1%} of zones")

    staircase = (drifts > 0.7) & (overlaps < 0.35)
    print(f"\nboth signals agree it is a staircase, not a base: {staircase.mean():.1%}")

    multi = np.array([r for r in rows if True])
    by_bars = {}
    for label, kind, _, d, o in rows:
        by_bars.setdefault(kind, []).append(d)
    print("\nmedian drift by formation")
    for kind, values in sorted(by_bars.items()):
        print(f"  {kind}  n={len(values):<5} median drift {np.median(values):.2f}")
    del multi


if __name__ == "__main__":
    main()
