"""What shape are the formations, per timeframe?

    python -m tools.anatomy_shape

Every zone in the 4h dossier read "leg-in 1, base 1, leg-out 1". A single-bar
base is legitimate, the doctrine names it explicitly, but if EVERY formation on
a timeframe is one bar of each then the classifier is alternating
exciting/base/exciting on every candle, and the runs it compresses are not runs
at all. That would mean the impulse threshold is mis-scaled for that timeframe
rather than that the market produced 8 identical formations.

The tell is the distribution, not any single zone: a healthy one has a spread
of base lengths. A spike at exactly 1 everywhere is the classifier, not the
market.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from app.detect.supply_demand import detect
from app.indicators import classify_candles, wilder_atr
from app.models import SupplyDemandParams
from tools import history

TIMEFRAMES = ["15m", "1h", "4h", "1d"]


def main() -> None:
    params = SupplyDemandParams(merge_overlap_pct=1.0, max_zones_per_side=100, show_broken=True)

    print(f"{'tf':<6}{'zones':>7}{'base=1':>9}{'base med':>10}{'legout=1':>10}{'exciting':>10}{'runs/bar':>10}")
    for tf in TIMEFRAMES:
        candles = history.load("PAXGUSDT", tf, 20000)
        zones, _ = detect(candles, params)
        if not zones:
            continue

        base_len = [z.anatomy.base_to - z.anatomy.base_from + 1 for z in zones]
        out_len = [z.anatomy.leg_out_to - z.anatomy.leg_out_from + 1 for z in zones]

        # What fraction of bars the classifier calls exciting, and how often the
        # label flips. A flip rate near 1 means every bar starts a new run.
        arrays = [
            np.array([getattr(c, f) for c in candles], dtype=np.float64)
            for f in ("open", "high", "low", "close")
        ]
        atr = wilder_atr(arrays[1], arrays[2], arrays[3], params.atr_period)
        labels = classify_candles(
            *arrays, atr, params.impulse_body_ratio, params.impulse_atr
        )
        exciting = float((labels != 0).mean())
        flips = float((labels[1:] != labels[:-1]).mean())

        print(
            f"{tf:<6}{len(zones):>7}{Counter(base_len)[1] / len(base_len):>8.0%}"
            f"{np.median(base_len):>10.0f}{Counter(out_len)[1] / len(out_len):>9.0%}"
            f"{exciting:>10.0%}{flips:>10.2f}"
        )

    print(
        "\nbase=1 near 100% together with a high flip rate means the classifier is\n"
        "alternating every candle, so the 'runs' it compresses are single bars."
    )


if __name__ == "__main__":
    main()
