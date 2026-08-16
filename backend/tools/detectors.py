"""Three detectors, one rig, the same controls.

    python -m tools.detectors

Adding a detector is easy and proves nothing. This file exists so that the two
new ones cannot enter on a softer standard than the one that has already killed
four plausible findings on the old one.

Every detector is put through the identical mill:

  drawn      the boxes it produces
  placebo    the same boxes, same size and side and age, at a random PRICE

and judged on the identical outcome, under BOTH bracket geometries - reward in
ATR, where a tall box is graded on an easier test, and reward in box heights,
where every box is graded at the same reward-to-risk. A detector whose result
appears under one and vanishes under the other has produced geometry, not a
finding. That check is what caught most of the doctrine's odds enhancers.

ONE CONTROL, NOT TWO, AND WHY
A random-TIME control was written and then removed, because on this outcome it
is degenerate. The bracket starts at whatever price the random bar happens to
sit at; if that price is already past the target the bracket resolves as a win
on its first bar. It scored 50 to 52 per cent for every detector under every
geometry, which is the signature of a coin flip rather than of a control. It
works in `tools/reaction.py` only because the outcome there is displacement from
the TOUCH price, which has no meaning without a touch.

So `placebo` carries the whole load here: same box, same size, same side, same
age, wrong price. It answers the question this file is for - is the box marking a
place, or would any box do.

WHAT A GOOD RESULT LOOKS LIKE, stated before the numbers exist
  - beats placebo, which means it beats an arbitrary level;
  - holds under BOTH brackets, because a result that appears under one and
    vanishes under the other is the bracket's geometry and not the detector's;
  - on a sample large enough for the difference to mean something, printed
    rather than assumed.

Anything less is reported as what it is.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.detect import DETECTORS
from app.indicators import wilder_atr
from app.models import Candle, ImbalanceParams, SupplyDemandParams, Zone
from tools import history
from tools.calibrate import POPULATION, _two_proportion, first_touch, resolve, shift

SERIES = [
    ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
]

# Every display cap off, for the reason recorded in `tools/calibrate.py`: the
# cap selects the NEWEST boxes, so a measurement taken through it is a
# measurement of the tail of the history wearing the whole history's name.
SETTINGS = {
    "supply_demand": SupplyDemandParams(**POPULATION),
    "fvg": ImbalanceParams(max_zones_per_side=0, show_broken=True),
    "order_block": ImbalanceParams(max_zones_per_side=0, show_broken=True),
}


def cohorts(
    name: str, candles: list[Candle], reward: float, horizon: int, mode: str
) -> dict[str, list[bool]]:
    """Outcomes for one detector on one series, across the three cohorts."""
    params = SETTINGS[name]
    zones, _ = DETECTORS[name](candles, params)

    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)
    index_of = {c.time: i for i, c in enumerate(candles)}

    out: dict[str, list[bool]] = {"drawn": [], "placebo": []}
    for zone in zones:
        if zone.first_test_time is None:
            continue
        touch = index_of.get(zone.first_test_time)
        if touch is None or touch <= zone.anatomy.leg_out_to:
            continue

        outcome = resolve(zone, high, low, close, atr, touch, reward, horizon, mode)
        if outcome is None:
            continue
        out["drawn"].append(outcome)

        moved = shift(zone, float(atr[min(zone.anatomy.base_to, len(atr) - 1)]))
        p_touch = first_touch(moved, high, low, zone.anatomy.leg_out_to + 1)
        if p_touch is not None:
            p_outcome = resolve(
                moved, high, low, close, atr, p_touch, reward, horizon, mode
            )
            if p_outcome is not None:
                out["placebo"].append(p_outcome)


    return out


def run(reward: float, horizon: int, mode: str, loaded: list) -> dict:
    unit = "ATR" if mode == "atr" else "x the box's own height"
    print(f"\n{'=' * 78}")
    print(f"DETECTORS   reward {reward} {unit}, horizon {horizon} bars")
    print(f"{'=' * 78}")
    print(f"  {'detector':<16}{'n':>7}{'held':>8}{'placebo':>10}{'vs placebo':>12}"
          f"   test")

    out = {}
    for name in DETECTORS:
        pooled: dict[str, list[bool]] = {"drawn": [], "placebo": []}
        for candles in loaded:
            for key, values in cohorts(name, candles, reward, horizon, mode).items():
                pooled[key].extend(values)

        drawn = np.array(pooled["drawn"])
        if len(drawn) < 100:
            print(f"  {name:<16}{len(drawn):>7}   too few to report")
            continue
        placebo = np.array(pooled["placebo"])
        print(
            f"  {name:<16}{len(drawn):>7}{drawn.mean():>8.1%}"
            f"{placebo.mean() if len(placebo) else float('nan'):>10.1%}"
            f"{drawn.mean() - placebo.mean():>+12.1%}"
            f"   {_two_proportion(drawn, placebo)}"
        )
        out[name] = {
            "n": len(drawn), "held": float(drawn.mean()),
            "placebo": float(placebo.mean()) if len(placebo) else None,
            "vs_placebo": _two_proportion(drawn, placebo),
        }
    return out


def sweep(loaded: list, reward: float = 2.0, horizon: int = 80) -> dict:
    """How much does the answer depend on the numbers we invented?

    Two of the three thresholds in `ImbalanceParams` have no source at all:
    nothing published gives a minimum gap size, and nothing published quantifies
    "impulsive". Calling them swept parameters in the documentation while never
    sweeping them would be the same class of claim this project exists to catch,
    so here they are swept.

    What matters is not whether the gap-versus-placebo number moves - it will -
    but whether the CONCLUSION moves. A threshold that changes the size of the
    effect is a knob; one that changes its sign is a result that was really
    about the knob.
    """
    print(f"\n{'=' * 78}")
    print(f"PARAMETER SWEEP   reward {reward} equal-R, horizon {horizon} bars")
    print(f"{'=' * 78}")
    out: dict = {}

    def measure(name: str) -> tuple[int, float, float]:
        drawn: list[bool] = []
        placebo: list[bool] = []
        for candles in loaded:
            got = cohorts(name, candles, reward, horizon, "r")
            drawn.extend(got["drawn"])
            placebo.extend(got["placebo"])
        if len(drawn) < 100 or len(placebo) < 100:
            return len(drawn), float("nan"), float("nan")
        return len(drawn), float(np.mean(drawn)), float(np.mean(placebo))

    shipped_fvg = SETTINGS["fvg"]
    print(f"\n  fvg, min_gap_atr           n     held  placebo     diff")
    out["min_gap_atr"] = []
    for value in (0.0, 0.05, 0.1, 0.25, 0.5, 1.0):
        SETTINGS["fvg"] = ImbalanceParams(
            max_zones_per_side=0, show_broken=True, min_gap_atr=value
        )
        n, held, plac = measure("fvg")
        mark = "  <- shipped" if abs(value - 0.1) < 1e-9 else ""
        print(f"  {value:<22.2f}{n:>6}{held:>9.1%}{plac:>9.1%}{held - plac:>+9.1%}{mark}")
        out["min_gap_atr"].append(
            {"value": value, "n": n, "held": held, "placebo": plac}
        )
    SETTINGS["fvg"] = shipped_fvg

    shipped_ob = SETTINGS["order_block"]
    print(f"\n  order_block, impulse       n     held  placebo     diff")
    out["displacement"] = []
    for atr_mult, bars in ((0.5, 5), (1.0, 5), (1.5, 5), (2.5, 5), (1.5, 3), (1.5, 10)):
        SETTINGS["order_block"] = ImbalanceParams(
            max_zones_per_side=0, show_broken=True,
            displacement_atr=atr_mult, displacement_bars=bars,
        )
        n, held, plac = measure("order_block")
        mark = "  <- shipped" if (atr_mult, bars) == (1.5, 5) else ""
        label = f"{atr_mult} ATR over {bars} bars"
        print(f"  {label:<22}{n:>6}{held:>9.1%}{plac:>9.1%}{held - plac:>+9.1%}{mark}")
        out["displacement"].append(
            {"atr": atr_mult, "bars": bars, "n": n, "held": held, "placebo": plac}
        )
    SETTINGS["order_block"] = shipped_ob

    print(
        "\n  Read the DIFF column, not the held column. Every threshold moves the"
        "\n  hold rate, because a stricter one keeps fewer and better boxes. What"
        "\n  would matter is a threshold that changed the SIGN, because that would"
        "\n  be a result about the knob rather than about the pattern."
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="also sweep the thresholds this project invented, since two of "
        "them have no source and calling them swept without sweeping them "
        "would be the same class of claim this rig exists to catch",
    )
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    loaded = [history.load(s, tf, args.bars) for s, tf in SERIES]

    everything = {}
    for mode, reward, horizon in [("atr", 1.0, 40), ("atr", 2.0, 80), ("r", 2.0, 80)]:
        everything[f"{mode}{reward}_h{horizon}"] = run(reward, horizon, mode, loaded)

    if args.sweep:
        everything["sweep"] = sweep(loaded)

    print(
        "\n  Beating PLACEBO means the box beat an arbitrary box at an arbitrary"
        "\n  price, which is a LOW bar and is all this rig can offer the two new"
        "\n  detectors - the harder control, real formations the gate threw out,"
        "\n  exists only for supply_demand because only it has a gate."
        "\n  Doing it under BOTH brackets means the result is not the geometry of"
        "\n  the test. None of it says the box predicts DIRECTION; that was"
        "\n  measured separately, and it does not."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(everything, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
