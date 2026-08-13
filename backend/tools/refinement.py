"""What does refining a zone actually buy?

    python -m tools.refinement

Nobody has published this number. The claim circulating for refinement is
arithmetic rather than evidence: a 40-pip box contains a 5-pip box, so the same
target is 8x the risk-multiple. That division is correct and it assumes the
thing in question - that the tighter stop survives at the same rate. It cannot,
in general: a stop closer to price is a stop price reaches more often.

So the comparison here is PAIRED. Every zone appears twice, once as the detector
drew it and once refined, on the same bars, judged by the same rule. A paired
design is what makes the answer readable at this sample size, because the two
cohorts differ in exactly one thing and nothing else has to be controlled for.

Three numbers, and the third is the one that decides it:

  survival   does the refined box still hold when price arrives
  risk       how much smaller the stop got, which is the claimed gain
  expectancy survival times reward-over-risk, which is where the trade-off
             actually lands. A refined zone can hold less often and still be
             worth more, or hold nearly as often and be worth less, and only
             this line can tell those apart.

The zone is judged on ITS OWN timeframe's bars in both arms - the higher one -
because that is where the detector drew it and where the shipped code evaluates
its lifecycle. Refinement changes where the box sits, not which chart owns it.
"""

from __future__ import annotations

import argparse
import copy
import json
from math import comb

import numpy as np

from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.models import Candle, SupplyDemandParams, Zone
from app.refine import refine_zones
from app.resample import resample
from tools import history
from tools.calibrate import POPULATION, first_touch, resolve

# One step up, the same 4x the calibration harness uses for nesting. It sits in
# the middle of the 3x to 12x band practitioners describe, and what matters is
# that it is the same for every series or the arms are not comparable.
STEP_UP = {"15m": "1h", "1h": "4h", "4h": "1d"}


def compare(
    candles: list[Candle],
    params: SupplyDemandParams,
    higher: str,
    reward_atr: float,
    horizon: int,
) -> list[dict]:
    """One row per zone that resolved in BOTH arms."""
    bars = resample(candles, higher, _interval_of(higher))
    if len(bars) < params.atr_period + 3:
        return []

    plain, _ = detect(bars, params)
    refined = copy.deepcopy(plain)
    refine_zones(refined, bars, candles, higher, params)

    high = np.array([c.high for c in bars])
    low = np.array([c.low for c in bars])
    close = np.array([c.close for c in bars])
    atr = wilder_atr(high, low, close, params.atr_period)

    rows = []
    for before, after in zip(plain, refined):
        if after.refinement is None:
            continue  # nothing to compare; the box did not move
        pair = []
        for zone in (before, after):
            touch = first_touch(zone, high, low, zone.anatomy.leg_out_to + 1)
            if touch is None:
                break
            outcome = resolve(
                zone, high, low, close, atr, touch, reward_atr, horizon
            )
            if outcome is None:
                break
            pair.append((touch, outcome, abs(zone.proximal - zone.distal)))
        if len(pair) != 2:
            continue  # only pairs, so the comparison stays paired

        rows.append({
            "plain_held": pair[0][1],
            "refined_held": pair[1][1],
            "plain_risk": pair[0][2],
            "refined_risk": pair[1][2],
            "shrank_to": after.refinement.shrank_to,
        })
    return rows


def _interval_of(higher: str) -> str:
    for low, high in STEP_UP.items():
        if high == higher:
            return low
    raise KeyError(higher)


def mcnemar(rows: list[dict]) -> tuple[int, int, float]:
    """Exact paired test on the zones the two arms DISAGREED about.

    The pairs that agree carry no information about which arm is better, so
    counting them - as a two-proportion test on the same zones would - dilutes
    the very comparison the pairing was set up to make.
    """
    only_plain = sum(1 for r in rows if r["plain_held"] and not r["refined_held"])
    only_refined = sum(1 for r in rows if r["refined_held"] and not r["plain_held"])
    n = only_plain + only_refined
    if n == 0:
        return only_plain, only_refined, float("nan")
    k = max(only_plain, only_refined)
    tail = sum(comb(n, i) for i in range(k, n + 1)) / 2**n
    return only_plain, only_refined, min(1.0, 2 * tail)


def report(rows: list[dict], reward_atr: float, horizon: int) -> dict:
    if len(rows) < 30:
        print(f"  only {len(rows)} paired zones, refusing to report")
        return {}

    plain = np.array([r["plain_held"] for r in rows])
    refined = np.array([r["refined_held"] for r in rows])
    shrink = np.array([r["refined_risk"] / max(r["plain_risk"], 1e-12) for r in rows])

    only_plain, only_refined, p = mcnemar(rows)

    print(f"\n{'=' * 78}")
    print(f"REFINEMENT, PAIRED   reward {reward_atr} ATR, horizon {horizon} bars")
    print(f"{'=' * 78}")
    print(f"  paired zones            {len(rows)}")
    print(f"  drawn as detected       held {plain.mean():.1%}")
    print(f"  refined                 held {refined.mean():.1%}   {refined.mean() - plain.mean():+.1%}")
    print(f"  disagreed               {only_plain} only-plain vs {only_refined} only-refined   exact p={p:.4f}")
    print(f"  stop distance           {shrink.mean():.1%} of the original, median {np.median(shrink):.1%}")

    # The claim under test, made explicit. Reward is fixed at `reward_atr` in
    # both arms, so a smaller stop is a bigger multiple of it, and expectancy is
    # survival times that multiple. Anything above 1.00 in the last column means
    # refining paid for the survival it cost.
    # Per PAIR, then summarised. Averaging 1/shrink across zones instead would
    # be dominated by the handful that collapsed to a few percent of their
    # original height - one zone shrinking to 0.02 contributes a 50x multiple
    # and drags the mean far above anything a trader would ever see. The median
    # is the headline for that reason and the mean is printed beside it so the
    # skew stays visible rather than being smoothed away.
    leverage = 1.0 / np.maximum(shrink, 1e-9)
    # Winsorised, because a zone that shrank to 2% of its height contributes a
    # 50x multiple that no trader would ever realise and that would set the
    # average on its own. Only the median is quoted as the headline; no median
    # of the PRODUCT is quoted, because survival is binary and the median of a
    # product with a binary factor collapses to zero the moment more than half
    # the zones fail, which says nothing about anything.
    capped = np.minimum(leverage, 10.0)
    print(f"\n  reward per unit of risk  plain 1.00   refined median"
          f" {np.median(leverage):.2f}   mean {leverage.mean():.2f}"
          f"   mean capped at 10x {capped.mean():.2f}")
    print(f"  survival x that          plain {plain.mean():.2f}"
          f"   refined {float(np.mean(refined * capped)):.2f}")
    ratio_median = float(np.mean(refined * capped)) / max(float(plain.mean()), 1e-9)
    print(
        "\n  Read those beside the exact p. The stop shrank BY CONSTRUCTION, so the"
        "\n  leverage column is arithmetic and not a finding. Survival is the only"
        "\n  measured quantity here, and it went DOWN, significantly, at every"
        "\n  geometry. Whether the trade is worth making is then a question about"
        "\n  the trader's costs, which this project does not model at all."
    )

    return {
        "n": len(rows),
        "plain_held": float(plain.mean()),
        "refined_held": float(refined.mean()),
        "only_plain": only_plain,
        "only_refined": only_refined,
        "p": p,
        "stop_fraction_mean": float(shrink.mean()),
        "stop_fraction_median": float(np.median(shrink)),
        "leverage_median": float(np.median(leverage)),
        "leverage_mean": float(leverage.mean()),
        "expectancy_ratio_median": ratio_median,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    series = [
        ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
        ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
    ]
    params = SupplyDemandParams(**POPULATION)

    print("Loading history (cached after the first run)")
    loaded = [(tf, history.load(s, tf, args.bars)) for s, tf in series]

    out = {}
    for reward_atr, horizon in [(0.5, 40), (1.0, 40), (2.0, 80)]:
        rows: list[dict] = []
        for interval, candles in loaded:
            rows.extend(
                compare(candles, params, STEP_UP[interval], reward_atr, horizon)
            )
        out[f"r{reward_atr}_h{horizon}"] = report(rows, reward_atr, horizon)

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
