"""Is the box in the right place, and is it in the right place EVERY time?

    python -m tools.drawing_accuracy

Two different questions that get muddled together, and a drawing can pass one
while failing the other:

  ACCURACY   does the box sit where the base is, on average - no systematic
             bias up or down
  PRECISION  does it sit there on EVERY zone - no scatter, no occasional
             outlier that a mean would hide

The existing checks cover neither at scale. `tests/` asserts exact geometry on
hand-built fixtures where the answer is known by construction; `validate_api`
asserts it on a few dozen real zones; `e2e/pixel-truth.mjs` reads back painted
pixels for the seven zones one screenshot happens to contain. None of them says
what happens across thousands of zones on every timeframe, and "it was right on
the ones we looked at" is exactly the claim a rare defect survives.

So this measures the WORST case, not the average. A mean deviation of zero is
what a drawing with two opposite-signed bugs also reports.

Everything here is arithmetic against the candles. Whether those numbers reach
the screen intact is a separate question and a separate harness - the canvas is
read back by `e2e/pixel-truth.mjs`, because numbers matching numbers cannot
catch a renderer that puts a correct zone in the wrong place.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.models import Candle, SupplyDemandParams, ZoneSide
from tools import history
from tools.calibrate import POPULATION

SERIES = [
    ("PAXGUSDT", "5m"), ("PAXGUSDT", "15m"), ("PAXGUSDT", "30m"),
    ("PAXGUSDT", "1h"), ("BTCUSDT", "15m"), ("BTCUSDT", "1h"),
    ("ETHUSDT", "1h"),
]


def audit(candles: list[Candle], params: SupplyDemandParams, label: str) -> dict:
    zones, _ = detect(candles, params)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    open_ = np.array([c.open for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)

    exact = 0
    grown = 0
    violations: list[str] = []
    top_err: list[float] = []
    bottom_err: list[float] = []
    pad_bars: list[int] = []

    for zone in zones:
        a = zone.anatomy
        span = slice(a.base_from, a.base_to + 1)
        base_hi = float(high[span].max())
        base_lo = float(low[span].min())
        height = zone.top - zone.bottom
        is_demand = zone.side is ZoneSide.DEMAND

        # The expected box, rebuilt by the detector's own rules rather than
        # assumed. The first version of this file compared against the WICK span
        # in both variants and then reported dozens of "proximal off by" defects
        # that were the minimum-height growth doing exactly what it should. An
        # auditor that does not reproduce the rule it is auditing invents
        # findings, and this one invented 33 before it found any.
        if params.proximal_basis == "body":
            body_hi = float(np.maximum(open_[span], close[span]).max())
            body_lo = float(np.minimum(open_[span], close[span]).min())
        else:
            body_hi, body_lo = base_hi, base_lo
        want_top, want_bottom = (
            (body_hi, base_lo) if is_demand else (base_hi, body_lo)
        )

        # A base thinner than the floor is deliberately grown, from the proximal
        # side only. Measured on the height AFTER the basis is applied, because
        # that is what the detector measures.
        floor = params.zone_min_atr * float(atr[max(0, a.base_from - 1)])
        was_grown = want_top - want_bottom < floor - 1e-12
        if was_grown:
            if is_demand:
                want_top = want_bottom + floor
            else:
                want_bottom = want_top - floor

        # THE RULE THE WHOLE METHOD RESTS ON: the distal is the wick extreme.
        # A stop sits beyond it, so a distal inside the base puts the stop
        # inside the thing it protects.
        distal_target = base_lo if is_demand else base_hi
        if abs(zone.distal - distal_target) > 1e-9:
            violations.append(
                f"{label} {zone.id}: distal {zone.distal:.6f} != wick {distal_target:.6f}"
            )

        # Scale-free, so 5-minute gold and hourly bitcoin are comparable.
        top_err.append(abs(zone.top - want_top) / max(height, 1e-12))
        bottom_err.append(abs(zone.bottom - want_bottom) / max(height, 1e-12))
        if was_grown:
            grown += 1
        else:
            exact += 1
            # Growth aside, the box may never reach past the base's extremes.
            if zone.top > base_hi + 1e-9 or zone.bottom < base_lo - 1e-9:
                violations.append(
                    f"{label} {zone.id}: box {zone.bottom:.6f}-{zone.top:.6f} "
                    f"outside base {base_lo:.6f}-{base_hi:.6f}"
                )

        # How many IMPULSE bars the box swallowed. Walking back from
        # `base_from` was wrong: when a long consolidation is clipped, the bars
        # before `base_from` are the rest of that same pause, and of course they
        # sit inside the box's price range. Counting them reported 4325 padded
        # zones that were nothing of the kind. The leg-in starts at
        # `base_run_from`, so that is where the walk has to start.
        pad = 0
        first = a.base_run_from if a.base_run_from >= 0 else a.base_from
        for i in range(first - 1, max(a.leg_in_from - 1, -1), -1):
            if low[i] >= zone.bottom - 1e-9 and high[i] <= zone.top + 1e-9:
                pad += 1
            else:
                break
        pad_bars.append(pad)

        # The proximal must be the box edge price meets first, and the distal
        # the far one. Stated separately from the geometry above because it is
        # the invariant a stop depends on.
        want_proximal = want_top if is_demand else want_bottom
        if abs(zone.proximal - want_proximal) > 1e-9:
            violations.append(
                f"{label} {zone.id}: proximal off by {zone.proximal - want_proximal:.9f}"
            )

    return {
        "label": label,
        "zones": len(zones),
        "exact": exact,
        "grown_to_floor": grown,
        "violations": violations,
        "top_worst": max(top_err) if top_err else 0.0,
        "bottom_worst": max(bottom_err) if bottom_err else 0.0,
        "top_mean": float(np.mean(top_err)) if top_err else 0.0,
        "pad_worst": max(pad_bars) if pad_bars else 0,
        "pad_any": sum(1 for p in pad_bars if p > 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    out = []
    for basis in ("wick", "body"):
        params = SupplyDemandParams(**POPULATION, proximal_basis=basis)
        print(f"\n{'=' * 78}")
        print(f"DRAWING ACCURACY, proximal_basis = {basis}")
        print(f"{'=' * 78}")
        print(f"  {'series':<16}{'zones':>7}{'exact':>7}{'grown':>7}"
              f"{'top worst':>11}{'bot worst':>11}{'pad':>6}{'bad':>6}")
        for symbol, interval in SERIES:
            try:
                candles = history.load(symbol, interval, args.bars)
            except Exception as exc:  # a missing cache file is not a drawing bug
                print(f"  {symbol}-{interval:<10} skipped: {exc}")
                continue
            row = audit(candles, params, f"{symbol}-{interval}")
            out.append({**row, "basis": basis})
            print(
                f"  {row['label']:<16}{row['zones']:>7}{row['exact']:>7}"
                f"{row['grown_to_floor']:>7}{row['top_worst']:>11.2e}"
                f"{row['bottom_worst']:>11.2e}{row['pad_worst']:>6}"
                f"{len(row['violations']):>6}"
            )

    total = sum(r["zones"] for r in out)
    bad = [v for r in out for v in r["violations"]]
    worst_top = max((r["top_worst"] for r in out), default=0.0)
    worst_bottom = max((r["bottom_worst"] for r in out), default=0.0)
    padded = sum(r["pad_any"] for r in out)

    print(f"\n  {total} zones across {len(SERIES)} series x 2 proximal variants")
    print(f"  worst top edge error      {worst_top:.3e} of the zone's own height")
    print(f"  worst bottom edge error   {worst_bottom:.3e} of the zone's own height")
    print(f"  zones padded onto a neighbouring impulse candle   {padded}")
    print(f"  rule violations           {len(bad)}")
    for line in bad[:20]:
        print(f"    {line}")

    print(
        "\n  Worst case, not mean. A mean of zero is also what a drawing with two"
        "\n  opposite-signed errors reports, and the point of this file is to be"
        "\n  unable to report that."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
