"""Apakah confluence (S&D + OB/FVG di harga yang sama) menaikkan hold rate?

    python -m tools.confluence_test --bars 20000 --interval 1h

Pertanyaan yang diuji: zona supply/demand yang punya OB atau FVG di harga yang
sama (confluence) - apakah bertahan lebih sering daripada zona sendirian?

Ini langkah terakhir dari roadmap "independen dulu, baru dikombinasikan".
"""

from __future__ import annotations

import argparse

import numpy as np

from app.detect.imbalance import detect_fvg, detect_order_block
from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.models import ImbalanceParams, SupplyDemandParams
from tools import history
from tools.calibrate import resolve

# No display cap, no state filter: the whole population.
SD_POP = dict(merge_overlap_pct=1.0, max_zones_per_side=0, show_broken=True)


def overlap(a_top, a_bottom, b_top, b_bottom) -> float:
    """Overlap between two boxes, positive if they share price."""
    return min(a_top, b_top) - max(a_bottom, b_bottom)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    args = parser.parse_args()

    candles = history.load(args.symbol, args.interval, args.bars)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, 14)

    sd_params = SupplyDemandParams(**SD_POP)
    zones, _ = detect(candles, sd_params)

    imb_params = ImbalanceParams(max_zones_per_side=0, show_broken=True)
    gaps, _ = detect_fvg(candles, imb_params)
    blocks, _ = detect_order_block(candles, imb_params)

    # Confluence pool = FVG + OB boxes.
    pool = list(gaps) + list(blocks)
    print(f"S&D zones: {len(zones)}, OB blocks: {len(blocks)}, FVG gaps: {len(gaps)}")

    confluent = 0
    alone = 0
    held_conf = 0
    held_alone = 0
    for z in zones:
        if z.first_test_time is None:
            continue
        # Tight confluence: an OB/FVG proximal within 0.3 ATR of this zone's proximal.
        tol = 0.3 * float(atr[max(0, z.anatomy.base_from - 1)])
        hit = any(
            abs(o.proximal - z.proximal) <= tol for o in pool
        )
        touch = next(i for i, c in enumerate(candles) if c.time == z.first_test_time)
        out = resolve(z, high, low, close, atr, touch, 2.0, 80, "r")
        if out is None:
            continue
        if hit:
            confluent += 1
            held_conf += out
        else:
            alone += 1
            held_alone += out

    print(f"\nconfluence (OB/FVG proximal dalam 0.3 ATR): n={confluent}  held={held_conf/max(confluent,1):.1%}")
    print(f"alone (S&D only):                          n={alone}  held={held_alone/max(alone,1):.1%}")
    if confluent and alone:
        d = held_conf/confluent - held_alone/alone
        print(f"difference: {d:+.1%}  ({'confluence HELPS' if d > 0 else 'confluence HURTS / no help'})")


if __name__ == "__main__":
    main()
