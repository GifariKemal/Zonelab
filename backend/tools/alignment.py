"""Does a zone do better when structure already points its way?

    python -m tools.alignment

H7, and the only claim the doctrine actually makes that nobody has measured.

It is not "zones predict direction" - six hypotheses have now failed that. It is
narrower and it is the thing ICT and SMC say in nearly every source: **the higher
timeframe sets the BIAS, the lower timeframe sets the ENTRY.** A demand zone
touched while structure is bullish is supposed to be a different object from the
same zone touched while structure is bearish. Nobody has published a number for
it. The zones and the structure both exist here already, so the question is one
join away.

THE ESTIMAND, AND WHY IT IS WITHIN-SIDE
The obvious split - aligned against opposed - leaks drift straight into the
answer. Aligned means demand-in-a-bull plus supply-in-a-bear, and this sample
spends more bars bullish than bearish, so the aligned group holds more demand
zones than the opposed group does. In a rising sample that difference alone
produces an effect.

So the comparison is made INSIDE each side, where the zone type is held fixed
and only the bias differs:

    demand:   mean(forward | bias bull)  -  mean(forward | bias bear)
    supply:   mean(forward | bias bear)  -  mean(forward | bias bull)

Both are signed so positive means "aligned did better". Drift enters both cells
of each comparison identically and cancels. And the two sides are independent
readings of the same claim: a real effect has to show on BOTH, because a
doctrine that only works for demand is not the doctrine.

FIXED BEFORE ANY NUMBER EXISTED
  - swing widths 2 and 25, both reported, because no published rule gives an N
    and sweeping it would be choosing the answer;
  - horizons 1, 3, 6, 12, 24, 48, primary 12, the same grid as every other
    directional test here so none of them gets a horizon that flatters it;
  - the bar: t >= 3.0 at the primary horizon, the same sign on both sides, and
    the same sign in both halves of the sample.

Two outcomes are reported, because they are different questions. The signed
forward return asks whether price GOES the zone's way. The bracket hold rate
asks whether the zone SURVIVES being tested, which is what the shipped gate is
about and the only thing this project has ever validated.

WHAT IT FOUND, AND WHAT KILLED IT
FVG at N=25 cleared all three criteria - demand +0.405 (t=4.63), supply +0.266
(t=3.06), both halves positive, hold rate +4.0pp. The first hypothesis here to
pass anything.

Then bias_only ran. Random bars carrying only the bias, with no box anywhere,
separate by +0.271 and +0.184. The difference in differences - what the ZONE
adds once the bias is removed - is +0.134 (t=1.25) and +0.082 (t=0.78) for FVG,
and NEGATIVE for both supply_demand and order_block. The zone adds nothing
measurable. What H7 measured is the bias, and the bias is momentum.

The control's own t is optimistic: 4000 draws per series on 20000 bars overlap
heavily, so its variance is understated. That makes the null STRONGER, not
weaker - a difference that fails to reach significance even against an
understated error bar is a null that will not improve.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.detect import DETECTORS
from app.detect.structure import bias_series
from app.indicators import wilder_atr
from app.models import ImbalanceParams, SupplyDemandParams, ZoneSide
from tools import history
from tools.calibrate import POPULATION, resolve

HORIZONS = (1, 3, 6, 12, 24, 48)
PRIMARY = 12
REWARD, HORIZON_BRACKET = 2.0, 80
SERIES = [
    ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
]


def events(name: str, candles, left: int, right: int) -> list[dict]:
    params = (
        SupplyDemandParams(**POPULATION)
        if name == "supply_demand"
        else ImbalanceParams(max_zones_per_side=0, show_broken=True)
    )
    zones, _ = DETECTORS[name](candles, params)

    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, params.atr_period)
    # Causal by construction: the value at bar i uses only breaks that had
    # already happened at i, and every break used only swings already confirmed.
    bias = bias_series(candles, left, right)
    index_of = {c.time: i for i, c in enumerate(candles)}

    out = []
    for zone in zones:
        if zone.first_test_time is None:
            continue
        touch = index_of.get(zone.first_test_time)
        if touch is None or touch < 1 or touch + max(HORIZONS) >= len(close):
            continue
        scale = float(atr[touch - 1])
        if scale <= 0 or bias[touch] == 0:
            continue  # no bias yet means nothing to be aligned with

        demand = zone.side is ZoneSide.DEMAND
        row = {
            "demand": demand,
            "bull": bool(bias[touch] > 0),
            "index": touch,
            "held": resolve(
                zone, high, low, close, atr, touch, REWARD, HORIZON_BRACKET, "atr"
            ),
        }
        for h in HORIZONS:
            # RAW, up-positive. Signing happens in the comparison, because the
            # whole point is to hold the side fixed and vary only the bias.
            row[f"h{h}"] = (float(close[touch + h]) - float(close[touch])) / scale
        out.append(row)
    return out


def bias_only(candles, left: int, right: int, rng) -> list[dict]:
    """The same measurement at RANDOM bars, carrying only the bias.

    This is the control that decides whether H7 is a finding or a restatement.
    "Demand zone while structure is bullish" is also just "a pullback in an
    uptrend", and buying that is time-series momentum - a real, established,
    peer-reviewed effect that has nothing to do with any box.

    So the same within-side contrast is computed on bars picked at random,
    labelled with the same bias and given the same fake side. If those bars show
    the same separation, the bias is doing all the work and the zone is
    decoration. The zone only earns a claim by beating this.
    """
    close = np.array([c.close for c in candles], dtype=np.float64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, 14)
    bias = bias_series(candles, left, right)

    out = []
    picks = rng.integers(1, len(close) - max(HORIZONS) - 1, 4000)
    for i in picks:
        i = int(i)
        if bias[i] == 0 or atr[i - 1] <= 0:
            continue
        scale = float(atr[i - 1])
        # A fake side drawn independently of the bias, so the four cells fill
        # the same way they do for real zones and the contrast is comparable.
        row = {
            "demand": bool(rng.integers(0, 2)),
            "bull": bool(bias[i] > 0),
            "index": i,
            "held": None,
        }
        for h in HORIZONS:
            row[f"h{h}"] = (float(close[i + h]) - float(close[i])) / scale
        out.append(row)
    return out


def contrast(rows: list[dict], demand: bool) -> tuple[float, float]:
    """Aligned minus opposed within one side. Returns the diff and its variance.

    Supply is signed the other way, because for a supply zone "its way" is DOWN.
    """
    way = 1.0 if demand else -1.0
    bull = demand  # aligned means bull for demand, bear for supply
    a = way * np.array([r[f"h{PRIMARY}"] for r in rows
                        if r["demand"] is demand and r["bull"] is bull])
    b = way * np.array([r[f"h{PRIMARY}"] for r in rows
                        if r["demand"] is demand and r["bull"] is not bull])
    return float(a.mean() - b.mean()), float(
        a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))


def difference_in_differences(rows: list[dict], control: list[dict], title: str,
                              out: dict) -> None:
    """What the ZONE adds over the bias alone. The number H7 turns on.

    The alignment contrast and the bias-only contrast are both "aligned minus
    opposed"; subtracting them removes everything the bias explains and leaves
    only what the box contributed. Zero here means the zone is decoration.
    """
    print(f"\n  {title}: what the ZONE adds over bias alone")
    record: dict = {}
    for demand in (True, False):
        zone, var_zone = contrast(rows, demand)
        bias, var_bias = contrast(control, demand)
        adds = zone - bias
        se = float(np.sqrt(var_zone + var_bias))
        t = adds / se if se > 0 else float("nan")
        label = "demand" if demand else "supply"
        print(f"  {label:<10}zone {zone:>+8.4f}   bias {bias:>+8.4f}"
              f"   ADDS {adds:>+8.4f}   t={t:>6.2f}")
        record[label] = {"zone": zone, "bias_only": bias, "adds": adds, "t": t}
    out[title] = record


def compare(rows: list[dict], title: str, out: dict) -> None:
    """Within each side, aligned minus opposed. Drift cancels inside each."""
    cells = {
        (d, b): [r for r in rows if r["demand"] is d and r["bull"] is b]
        for d in (True, False)
        for b in (True, False)
    }
    if min(len(v) for v in cells.values()) < 60:
        sizes = {f"{'D' if d else 'S'}{'+' if b else '-'}": len(v)
                 for (d, b), v in cells.items()}
        print(f"  {title}: too few, {sizes}")
        return

    print(f"\n  {title}")
    print(f"  {'':<10}{'aligned':>10}{'opposed':>10}{'diff':>9}{'t':>7}"
          f"{'  n aligned':>12}{'n opposed':>11}")

    record: dict = {}
    for label, aligned, opposed in (
        ("demand", cells[(True, True)], cells[(True, False)]),
        ("supply", cells[(False, False)], cells[(False, True)]),
    ):
        # Supply is signed the other way: for a supply zone "its way" is DOWN.
        way = 1.0 if label == "demand" else -1.0
        a = way * np.array([r[f"h{PRIMARY}"] for r in aligned])
        b = way * np.array([r[f"h{PRIMARY}"] for r in opposed])
        diff = float(a.mean() - b.mean())
        se = float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
        t = diff / se if se > 0 else float("nan")
        print(
            f"  {label:<10}{a.mean():>10.4f}{b.mean():>10.4f}{diff:>9.4f}{t:>7.2f}"
            f"{len(a):>12}{len(b):>11}"
        )
        record[label] = {"aligned": float(a.mean()), "opposed": float(b.mean()),
                         "diff": diff, "t": t, "n_aligned": len(a),
                         "n_opposed": len(b)}

    # The bracket question, which is the only one this project has ever
    # validated for anything. Pooled across sides because "held" is already
    # side-relative and carries no drift.
    aligned_held = [r["held"] for r in rows
                    if r["held"] is not None and r["demand"] == r["bull"]]
    opposed_held = [r["held"] for r in rows
                    if r["held"] is not None and r["demand"] != r["bull"]]
    if len(aligned_held) > 60 and len(opposed_held) > 60:
        pa, pb = float(np.mean(aligned_held)), float(np.mean(opposed_held))
        pooled = (sum(aligned_held) + sum(opposed_held)) / (
            len(aligned_held) + len(opposed_held))
        se = float(np.sqrt(pooled * (1 - pooled) * (
            1 / len(aligned_held) + 1 / len(opposed_held))))
        z = (pa - pb) / se if se > 0 else float("nan")
        print(f"  {'held':<10}{pa:>10.1%}{pb:>10.1%}{pa - pb:>+9.1%}{z:>7.2f}"
              f"{len(aligned_held):>12}{len(opposed_held):>11}")
        record["held"] = {"aligned": pa, "opposed": pb, "diff": pa - pb, "z": z}

    out[title] = record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    loaded = [history.load(s, tf, args.bars) for s, tf in SERIES]
    out: dict = {}

    for left, right, width in ((2, 2, "N=2"), (25, 25, "N=25")):
        print(f"\n{'=' * 78}")
        print(f"ZONE ALIGNED WITH STRUCTURE   {width}   reward {REWARD} ATR")
        print(f"{'=' * 78}")
        print("  Compared INSIDE each side, so the zone type is fixed and only")
        print("  the bias differs. Positive means aligned did better.")

        # The control comes FIRST, because every detector below is scored
        # against it. If random bars carrying only the bias separate as much as
        # zone touches do, the zone adds nothing and what was measured is
        # time-series momentum with extra steps.
        rng = np.random.default_rng(20260816)
        control: list[dict] = []
        for candles in loaded:
            control.extend(bias_only(candles, left, right, rng))
        compare(control, f"{width} BIAS ONLY, no zone", out)

        for name in ("supply_demand", "fvg", "order_block"):
            rows: list[dict] = []
            for candles in loaded:
                rows.extend(events(name, candles, left, right))
            compare(rows, f"{width} {name}", out)
            difference_in_differences(rows, control, f"{width} {name} DiD", out)

            mid = np.median([r["index"] for r in rows]) if rows else 0
            compare([r for r in rows if r["index"] <= mid],
                    f"{width} {name} first half", out)
            compare([r for r in rows if r["index"] > mid],
                    f"{width} {name} second half", out)

    print(
        "\n  The bar, fixed in advance: t >= 3.0 at the primary horizon, the same"
        "\n  sign on BOTH sides, and the same sign in both halves. A doctrine that"
        "\n  only works for demand is not the doctrine, and an effect that lives"
        "\n  in one half is a window fit - this project has caught that twice."
    )
    print(
        "\n  And then read the DiD lines, which are the ones that decide it. The"
        "\n  raw alignment numbers clear the bar; the bias-only control reproduces"
        "\n  most of them with no box anywhere on the chart. Only what the zone"
        "\n  ADDS over that control is a claim about the drawing."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
