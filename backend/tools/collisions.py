"""Do the drawn boxes collide with each other?

    python -m tools.collisions

Every fidelity check in this project so far asks the same question: is THIS box
in the right place? `drawing_accuracy` compares each zone against the base
candles it was cut from, and the pixel audit compares the painted rectangle
against the price scale. Both are per-zone. Neither has ever looked at two
zones at once.

That leaves a whole class of defect unmeasured, and it is the class a user
actually sees. A chart can be perfectly accurate box by box and still be
unreadable, or worse, incoherent:

  SAME-SIDE OVERLAP     two demand zones covering the same prices at the same
                        time. Ugly and redundant, but not a contradiction: the
                        doctrine really does allow nested demand.

  OPPOSITE-SIDE OVERLAP a demand zone and a supply zone covering the same
                        prices at the same time. This one IS a contradiction.
                        The same price cannot be where buyers overwhelm sellers
                        and where sellers overwhelm buyers. Either the drawing
                        is wrong or the concept does not survive contact with
                        the data, and the user deserves to know which.

  INK                   what fraction of the visible chart is painted. Past
                        roughly a third the boxes stop being annotation and
                        start being the background.

  STACK DEPTH           the worst point on the chart: how many boxes cover it.

MEASURED AT SHIPPED DEFAULTS, ON PURPOSE
Every other tool here sets max_zones_per_side=0 to defeat the display cap,
because a cap that selects the NEWEST zones would bias a measurement. This tool
does the opposite and keeps the shipped cap of 12, because the question is not
"what did the detector find" but "what does the user see". The cap is part of
the answer here, not a bug to route around.

All three detectors are run together, the way the workstation runs them when
every toggle is on, since that is the worst case the user can produce.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.detect import DETECTORS
from app.layers import PARAMS_BY_ID
from app.models import ImbalanceParams, SupplyDemandParams, ZoneSide
from tools import history

SERIES = [
    ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
]
GRID_PRICE = 400  # price rows used to measure ink; finer than any eye needs


def draw(candles, cap: int | None = None) -> list:
    """Every detector at once, at SHIPPED defaults. The worst case a user can
    produce from the panel, not a measurement population.

    Note what the cap actually caps: it is applied PER DETECTOR and PER SIDE, so
    the shipped 6 permits 5 x 2 x 6 = 60 boxes on one chart, not 6.

    Driven off the registry rather than a literal list of names, and that is a
    correction rather than a tidy-up: this function named three detectors while
    the registry grew to five, so `ifvg` and `breaker` were absent from the one
    measurement in the repo that asks what the user actually sees. app/drawing.py
    had the identical defect and its comment says why it matters - a detector
    wired into one place and forgotten in the other fails silently, which is the
    only kind of failure this project treats as unacceptable.
    """
    zones = []
    for name, detect in DETECTORS.items():
        extra = {} if cap is None else {"max_zones_per_side": cap}
        params = (
            SupplyDemandParams(**extra) if PARAMS_BY_ID[name] == "supply_demand"
            else ImbalanceParams(**extra)
        )
        found, _ = detect(candles, params)
        zones.extend(found)
    return zones


def overlaps(a, b) -> bool:
    """True when the two rectangles share both a price band and a moment.

    Touching edges do not count. Two zones that meet exactly at one price are
    adjacent, not stacked, and calling that a collision would report the normal
    case as a defect - the same mistake the zone audit made when it demanded
    exact equality with base extremes.
    """
    return (
        min(a.top, b.top) > max(a.bottom, b.bottom)
        and min(a.time_to, b.time_to) > max(a.time_from, b.time_from)
    )


def detector_of(zone) -> str:
    """Which detector drew it. FVG and OB are their own kinds; everything else
    is one of the four supply and demand formations."""
    return zone.kind.value if zone.kind.value in ("FVG", "OB") else "supply_demand"


def measure(zones, candles) -> dict:
    same = opposite = redundant = 0
    pairs = 0
    for i, a in enumerate(zones):
        for b in zones[i + 1:]:
            pairs += 1
            if not overlaps(a, b):
                continue
            if a.side is b.side:
                same += 1
                # Overlap BETWEEN detectors is confluence and is the point of
                # running them together - an FVG inside a demand zone is two
                # methods agreeing. Overlap WITHIN one detector is redundancy:
                # the same observation drawn twice. Only the second is a defect,
                # and supply_demand already merges its own at 60% while
                # ImbalanceParams has no merge at all.
                if detector_of(a) == detector_of(b):
                    redundant += 1
            else:
                opposite += 1

    # Ink and depth on a grid over the visible window. Time is measured in
    # bars rather than seconds so a gap in the feed cannot inflate coverage.
    times = np.array([c.time for c in candles], dtype=np.int64)
    lo = min(c.low for c in candles)
    hi = max(c.high for c in candles)
    rows = np.linspace(lo, hi, GRID_PRICE)
    depth = np.zeros((GRID_PRICE, len(times)), dtype=np.int16)
    for z in zones:
        band = (rows >= z.bottom) & (rows <= z.top)
        span = (times >= z.time_from) & (times <= z.time_to)
        if band.any() and span.any():
            depth[np.ix_(band, span)] += 1

    painted = depth > 0
    return {
        "zones": len(zones),
        "pairs": pairs,
        "same_side_overlaps": same,
        "redundant_same_detector": redundant,
        "opposite_side_overlaps": opposite,
        "ink": float(painted.mean()),
        "max_depth": int(depth.max()),
        "median_depth_where_painted": float(np.median(depth[painted]))
        if painted.any() else 0.0,
        "demand": sum(1 for z in zones if z.side is ZoneSide.DEMAND),
        "supply": sum(1 for z in zones if z.side is ZoneSide.SUPPLY),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=500,
                        help="a chart's worth, not a calibration population")
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    print(f"\n{'=' * 78}")
    print(f"ZONE COLLISIONS   {args.bars} bars, every detector on, SHIPPED caps")
    print(f"{'=' * 78}")
    print(f"  {'series':<16}{'zones':>7}{'same':>7}{'redun':>7}{'opp':>6}"
          f"{'ink':>8}{'deep':>6}")

    out: dict = {}
    totals = {"zones": 0, "same": 0, "opposite": 0, "pairs": 0}
    for symbol, tf in SERIES:
        candles = history.load(symbol, tf, args.bars)
        zones = draw(candles)
        m = measure(zones, candles)
        out[f"{symbol} {tf}"] = m
        totals["zones"] += m["zones"]
        totals["same"] += m["same_side_overlaps"]
        totals["opposite"] += m["opposite_side_overlaps"]
        totals["pairs"] += m["pairs"]
        print(f"  {symbol + ' ' + tf:<16}{m['zones']:>7}"
              f"{m['same_side_overlaps']:>7}{m['redundant_same_detector']:>7}"
              f"{m['opposite_side_overlaps']:>6}"
              f"{m['ink']:>8.1%}{m['max_depth']:>6}")

    print(f"\n  TOTAL {totals['zones']} zones, {totals['pairs']} pairs, "
          f"{totals['same']} same-side and {totals['opposite']} opposite-side "
          f"overlaps")
    print(
        "\n  Same-side overlap is not a defect. Nested demand is in the doctrine"
        "\n  and the detectors are allowed to find it. Opposite-side overlap IS a"
        "\n  contradiction: one price cannot be both where buyers overwhelm"
        "\n  sellers and where sellers overwhelm buyers at the same moment."
    )
    print(
        "\n  Ink is the readability number. Past about a third of the chart the"
        "\n  boxes have stopped annotating the price and become its background."
    )

    # What the display cap actually buys. Readability is a DISPLAY decision, not
    # a predictive gate, so it is settled by measuring ink rather than by
    # arguing taste - and unlike a gate, lowering it cannot bias a forecast
    # because there is no forecast to bias.
    print(f"\n{'=' * 78}")
    print("  INK AGAINST THE DISPLAY CAP   (cap is per detector AND per side)")
    print(f"{'=' * 78}")
    print(f"  {'cap':<6}{'boxes':>8}{'ink':>9}{'max depth':>12}{'opp overlaps':>15}")
    sweep: dict = {}
    for cap in (3, 4, 6, 8, 12):
        boxes = ink = deep = opp = 0
        for symbol, tf in SERIES:
            candles = history.load(symbol, tf, args.bars)
            m = measure(draw(candles, cap), candles)
            boxes += m["zones"]
            ink += m["ink"]
            deep = max(deep, m["max_depth"])
            opp += m["opposite_side_overlaps"]
        mark = "  <- shipped" if cap == 6 else ""
        print(f"  {cap:<6}{boxes:>8}{ink / len(SERIES):>9.1%}{deep:>12}"
              f"{opp:>15}{mark}")
        sweep[cap] = {"boxes": boxes, "ink": ink / len(SERIES),
                      "max_depth": deep, "opposite": opp}
    out["cap_sweep"] = sweep

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
