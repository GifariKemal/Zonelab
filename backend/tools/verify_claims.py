"""Settle the visual audit's claims with arithmetic.

    python -m tools.verify_claims

Three reviewers independently reported the same three defects. Two of them
contradict contract assertions that pass, so at most one side can be right and
guessing which is not an option. Each claim below is checked against the candle
data rather than against pixels or against the engine's own restatement.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from app.detect.supply_demand import detect
from app.models import SupplyDemandParams, ZoneSide
from tools import history

# Cached series only. Downloading four more timeframes to answer a structural
# question the cached ones already answer is a slow way to learn nothing new.
SERIES = [("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"), ("BTCUSDT", "15m"), ("ETHUSDT", "1h")]


def main() -> None:
    params = SupplyDemandParams()
    gap_hist: Counter[int] = Counter()
    pad_rows = []
    total = 0

    for symbol, interval in SERIES:
        candles = history.load(symbol, interval, 20000)[-500:]
        zones, _ = detect(candles, params)
        high = np.array([c.high for c in candles])
        low = np.array([c.low for c in candles])
        total += len(zones)

        gaps = 0
        pads = []
        for z in zones:
            a = z.anatomy
            # CLAIM 1: the formation must read as one contiguous sequence.
            #
            # Measured against `base_run_from`, the start of the WHOLE
            # consolidation, not against `base_from`, which is deliberately
            # clipped so the box sits on the bars the move left from. The gap
            # to `base_from` is by design; a gap to `base_run_from` would mean
            # the leg-in really is describing a different part of the chart.
            gap = a.base_run_from - a.leg_in_to - 1
            gap_hist[gap] += 1
            if gap != 0:
                gaps += 1

            # CLAIM 2: the box should be exactly the base's own extremes, with
            # nothing padded on from the neighbouring legs.
            span = slice(a.base_from, a.base_to + 1)
            base_hi, base_lo = float(high[span].max()), float(low[span].min())
            pad_top = z.top - base_hi
            pad_bottom = base_lo - z.bottom
            height = z.top - z.bottom
            if height > 0:
                pads.append((pad_top + pad_bottom) / height)

        pad_rows.append((f"{symbol}-{interval}", len(zones), gaps, np.mean(pads) if pads else 0.0,
                         max(pads) if pads else 0.0))

    print("CLAIM 1: the leg-in is detached from the consolidation")
    print(f"  gap over {total} zones (bars between leg-in end and the FULL base run):")
    for gap in sorted(gap_hist):
        print(f"    {gap:>3} bars: {gap_hist[gap]:>4}  {gap_hist[gap] / total:>6.1%}")
    detached = sum(n for g, n in gap_hist.items() if g > 0)
    print(f"  -> {detached}/{total} ({detached / total:.1%}) have a gap\n")

    print("CLAIM 2: the box is padded beyond the base's own extremes")
    print(f"  {'series':<18}{'zones':>6}{'gaps':>6}{'mean pad':>10}{'max pad':>10}")
    for label, n, gaps, mean_pad, max_pad in pad_rows:
        print(f"  {label:<18}{n:>6}{gaps:>6}{mean_pad:>9.1%}{max_pad:>10.1%}")
    print("  pad = (top - base high) + (base low - bottom), as a share of box height")
    print("  -> anything above 0 means the box is not the base\n")


if __name__ == "__main__":
    main()
