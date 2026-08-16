"""H8. When a zone breaks, does it start working the other way?

    python -m tools.inversion

Seven directional hypotheses have failed here. Every one of them asked a
DIFFERENT QUESTION OF THE SAME SAMPLE: change the conditioning variable, keep
the population. This one is the first that changes the population, and that is
the whole reason it is worth running after seven nulls.

docs/CALIBRATION.md said so itself before this tool existed: all 11,469 first
touches approach the box from the near side and ZERO come through it, so the
subsample that could separate continuation from reversal has never been in any
sample here. It has to be built.

THE CLAIM
An inversion fair value gap is a gap price closed through, whose role then
flips: broken support becomes resistance. A breaker block is the order block
version. Both are ICT constructs with an explicit DIRECTIONAL claim, unlike
almost everything else this project has drawn.

WHAT THE INVERTED BOX IS
The same rectangle, read from the other side. A demand zone price closed below
becomes a supply zone: price now returns from underneath, so the edge it meets
first is the old BOTTOM, and the protective edge is the old TOP. The lifecycle
replay already takes exactly these arguments, so no new geometry is invented -
the box is re-entered with `is_demand` flipped and distal swapped.

THE ESTIMAND, AND WHY IT IS A DIFFERENCE
This sample drifts upward, so "price fell after an inverted-supply touch" proves
nothing on its own. Writing the mean forward return under each inverted side as
mu + delta and mu - delta, the difference

    DELTA = mean(forward | now demand) - mean(forward | now supply)

cancels the drift exactly, with no model of it. Same estimand as every other
directional test here, for the same reason.

THE CONTROL, WHICH IS NOT OPTIONAL
A broken demand zone means price fell through it. Betting it keeps falling is
betting on momentum, which is real, established, peer-reviewed, and needs no
box. H7 passed all three of its criteria and then died to exactly this control,
so it runs here from the start rather than being added after a good number
appears. Random bars are given a FAKE inverted side taken from the sign of the
trailing move alone, and the same contrast is computed. Whatever the zone adds
over that is the only thing this test may claim.

FIXED BEFORE ANY NUMBER EXISTED
  - horizons 1, 3, 6, 12, 24, 48, primary 12, the same grid as every other
    directional test here so none of them gets a horizon chosen to flatter it;
  - trailing window for the control: 20 bars, one value, stated not swept;
  - the bar: t >= 3.0 at the primary horizon on the difference, the same sign in
    both halves of the sample, and the zone must beat its own control.

HONEST PRIOR: LOW. Huddart, Lang and Yetman (Management Science 2009) found
breaking the 52-week LOW gave the same positive subsequent return as breaking
the high - the event has magnitude and no sign. An inversion is that same event
class. A null here is expected; it is worth running because it is a NEW null and
it closes the one gap this project has named as open.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.detect import DETECTORS
from app.detect.supply_demand import replay_lifecycle
from app.indicators import wilder_atr
from app.models import ImbalanceParams, SupplyDemandParams, ZoneSide
from tools import history
from tools.calibrate import POPULATION, resolve

HORIZONS = (1, 3, 6, 12, 24, 48)
PRIMARY = 12
TRAIL = 20
REWARD, HORIZON_BRACKET = 2.0, 80
SERIES = [
    ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
]


def _params(name: str):
    base = dict(max_zones_per_side=0, show_broken=True)
    if name == "supply_demand":
        return SupplyDemandParams(**{**POPULATION, **base})
    return ImbalanceParams(**base)


def events(name: str, candles) -> list[dict]:
    """Every zone that broke, re-entered from the other side."""
    params = _params(name)
    zones, _ = DETECTORS[name](candles, params)

    time = np.array([c.time for c in candles], dtype=np.int64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, params.atr_period)
    index_of = {int(t): i for i, t in enumerate(time)}

    out = []
    for zone in zones:
        born = index_of.get(zone.time_from)
        if born is None:
            continue
        was_demand = zone.side is ZoneSide.DEMAND

        # Pass one: find the bar the box died on. This is the number
        # replay_lifecycle has always computed and every caller has thrown away.
        first = replay_lifecycle(
            time, high, low, close, atr, zone.top, zone.bottom, zone.distal,
            was_demand, born + 1, params,
        )
        if first.break_index is None:
            continue

        # Pass two: the SAME rectangle, entered from the other side. A demand
        # zone price closed below is now resistance, so the far edge it must
        # close back through to be finished is the old top.
        inverted_distal = zone.top if was_demand else zone.bottom
        second = replay_lifecycle(
            time, high, low, close, atr, zone.top, zone.bottom,
            inverted_distal, not was_demand, first.break_index + 1, params,
        )
        if second.first_test_time is None:
            continue
        touch = index_of.get(second.first_test_time)
        if touch is None or touch < 1 or touch + max(HORIZONS) >= len(close):
            continue
        scale = float(atr[touch - 1])
        if scale <= 0:
            continue

        now_demand = not was_demand
        row = {
            "now_demand": now_demand,
            "index": touch,
            "held": resolve(
                _flip(zone, inverted_distal, now_demand),
                high, low, close, atr, touch, REWARD, HORIZON_BRACKET, "atr",
            ),
        }
        for h in HORIZONS:
            # RAW, up-positive. Signing happens in the contrast, because the
            # estimand is a difference and signing first would hide the drift
            # the difference exists to cancel.
            row[f"h{h}"] = (float(close[touch + h]) - float(close[touch])) / scale
        out.append(row)
    return out


def _flip(zone, inverted_distal: float, now_demand: bool):
    """The zone as the bracket resolver must see it after inversion."""
    return zone.model_copy(update={
        "side": ZoneSide.DEMAND if now_demand else ZoneSide.SUPPLY,
        "distal": inverted_distal,
        "proximal": zone.bottom if not now_demand else zone.top,
    })


def control(candles, rng) -> list[dict]:
    """The same contrast at random bars, carrying only the trailing move.

    A broken demand zone means price fell through it, so "inverted supply" and
    "recent downtrend" are nearly the same statement. This assigns the fake
    inverted side from the trailing move ALONE, with no box anywhere. If these
    bars separate as much as real post-inversion touches do, the inversion adds
    nothing and what was measured is momentum wearing an ICT name.
    """
    close = np.array([c.close for c in candles], dtype=np.float64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, 14)

    out = []
    picks = rng.integers(TRAIL + 1, len(close) - max(HORIZONS) - 1, 4000)
    for i in picks:
        i = int(i)
        scale = float(atr[i - 1])
        if scale <= 0:
            continue
        moved = close[i] - close[i - TRAIL]
        if moved == 0:
            continue
        # Price fell into here, so the box above would now be resistance: the
        # same mapping the real events get.
        row = {"now_demand": bool(moved > 0), "index": i, "held": None}
        for h in HORIZONS:
            row[f"h{h}"] = (float(close[i + h]) - float(close[i])) / scale
        out.append(row)
    return out


def contrast(rows: list[dict]) -> tuple[float, float, int, int]:
    a = np.array([r[f"h{PRIMARY}"] for r in rows if r["now_demand"]])
    b = np.array([r[f"h{PRIMARY}"] for r in rows if not r["now_demand"]])
    if len(a) < 30 or len(b) < 30:
        return float("nan"), float("nan"), len(a), len(b)
    return (
        float(a.mean() - b.mean()),
        float(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)),
        len(a), len(b),
    )


def report(rows: list[dict], title: str, out: dict) -> None:
    delta, var, na, nb = contrast(rows)
    if np.isnan(delta):
        print(f"  {title}: too few, {na} now-demand and {nb} now-supply")
        return
    t = delta / np.sqrt(var) if var > 0 else float("nan")
    a = np.mean([r[f"h{PRIMARY}"] for r in rows if r["now_demand"]])
    b = np.mean([r[f"h{PRIMARY}"] for r in rows if not r["now_demand"]])
    print(f"  {title:<34}{a:>9.4f}{b:>10.4f}{delta:>9.4f}{t:>7.2f}"
          f"{na:>8}{nb:>8}")
    out[title] = {"now_demand": float(a), "now_supply": float(b),
                  "delta": delta, "t": float(t), "n_demand": na, "n_supply": nb}

    held_d = [r["held"] for r in rows if r["held"] is not None and r["now_demand"]]
    held_s = [r["held"] for r in rows
              if r["held"] is not None and not r["now_demand"]]
    if len(held_d) > 30 and len(held_s) > 30:
        pooled = (sum(held_d) + sum(held_s)) / (len(held_d) + len(held_s))
        print(f"    held {np.mean(held_d):>6.1%} demand, "
              f"{np.mean(held_s):>6.1%} supply, pooled {pooled:.1%}")
        out[title]["held"] = {"demand": float(np.mean(held_d)),
                              "supply": float(np.mean(held_s))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    loaded = [history.load(s, tf, args.bars) for s, tf in SERIES]
    out: dict = {}

    print(f"\n{'=' * 84}")
    print("H8  POST-INVERSION TOUCH   forward return in ATR, primary horizon 12")
    print(f"{'=' * 84}")
    print("  A broken box re-entered from the other side. DELTA is now-demand")
    print("  minus now-supply, which cancels this sample's drift exactly.")
    print(f"  {'':<34}{'now dem':>9}{'now sup':>10}{'DELTA':>9}{'t':>7}"
          f"{'n dem':>8}{'n sup':>8}")

    rng = np.random.default_rng(20260816)
    ctrl: list[dict] = []
    for candles in loaded:
        ctrl.extend(control(candles, rng))
    report(ctrl, "TRAILING MOVE ONLY, no zone", out)

    for name in ("supply_demand", "fvg", "order_block"):
        rows: list[dict] = []
        for candles in loaded:
            rows.extend(events(name, candles))
        report(rows, name, out)
        if len(rows) > 120:
            mid = np.median([r["index"] for r in rows])
            report([r for r in rows if r["index"] <= mid],
                   f"{name} first half", out)
            report([r for r in rows if r["index"] > mid],
                   f"{name} second half", out)

        # What the ZONE adds once the trailing move is removed. This is the line
        # that decides H8, exactly as it decided H7.
        dz, vz, _, _ = contrast(rows)
        dc, vc, _, _ = contrast(ctrl)
        if not np.isnan(dz) and not np.isnan(dc):
            adds = dz - dc
            se = float(np.sqrt(vz + vc))
            print(f"    ZONE ADDS over the control: {adds:+.4f}   "
                  f"t={adds / se if se > 0 else float('nan'):.2f}")
            out[f"{name} DiD"] = {"adds": adds, "t": adds / se if se > 0 else None}

    print(
        "\n  The bar, fixed in advance: t >= 3.0 on DELTA at the primary horizon,"
        "\n  the same sign in both halves, and the zone must beat its own control."
        "\n  A number that clears the first two and not the third is H7 again."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
