"""Would the gate have held up on bars nobody had seen yet?

    python -m tools.walkforward

`tools/calibrate.py` measures the departure gate on the whole history at once
and finds it worth +16.3 points against the formations it rejects. That number
is in-sample in the way that matters: the threshold it endorses was chosen after
looking at the same bars. It answers "does this describe the past", which is a
weaker question than the one people actually want answered.

Two questions here, and they are different:

  A. IS THE EFFECT STABLE IN TIME?  Split the history into contiguous slices,
     apply the SHIPPED threshold unchanged, and see whether the gap survives in
     each slice. A gap that lives in one regime and vanishes elsewhere is a
     property of that regime.

  B. COULD THE THRESHOLD HAVE BEEN FOUND FROM THE PAST ALONE?  On each slice,
     pick the threshold using only earlier slices, then apply it to the slice
     that follows. This is the honest form of "does it forecast": the choice is
     made with no knowledge of the bars it is graded on.

PURGING, AND WHY THERE IS NO EMBARGO
An outcome takes up to `horizon` bars to resolve. A training event touched a few
bars before the test slice begins is still resolving INSIDE the test slice, so
its label carries information from the period the threshold is about to be
graded on. Those events are dropped - that is purging, and without it the leak
is invisible and flatters every number below.

Lopez de Prado pairs purging with an embargo, which drops training data
immediately AFTER the test slice. There is none here, and the reason is
structural rather than an omission: this layout is strictly forward, training is
always earlier than test, so no training observation can follow the test slice.
The mirror-image concern - a test event whose zone was FORMED during the
training span - is not leakage at all. That is a trader using the past, which is
the whole idea.

WHAT THIS CANNOT SHOW
Not profitability: there are no costs, no spread and no slippage anywhere in this
project. Not that the threshold is optimal, only that it is not obviously
fitted. Not that the effect persists forward, because one history is one path.
Per-fold significance is not claimed either; with a few dozen events a slice, the
folds are a consistency check and the aggregate sign test is the statistic.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import comb, erfc, sqrt

import numpy as np

from app.models import SupplyDemandParams
from tools import history
from tools.calibrate import POPULATION, SHIPPED_GATE, Observation, evaluate

# Nine slices, so eight are graded. Not a round number chosen by feel: the sign
# test over k slices bottoms out at 2 / 2^k, so five graded slices cannot report
# below 0.0625 even when every one of them agrees. A test whose best possible
# answer is "not significant" is not a test, and at eight the floor is 0.008.
FOLDS = 9

# Two quantities are gated on, and both go through the same mill. `departure`
# ships at 2.0 and has been the only validated gate this project had; the road
# ahead earned its way in here after `tools/calibrate.py` found it the first
# ranking factor to clear 0.5 on both sides with clean intervals. Neither gets a
# default on in-sample evidence alone.
# grid to search, reference threshold for part A, and whether that reference is
# what actually ships. The road's reference is the knee its bucket table shows,
# NOT a shipped value - a gate that is off has no shipped threshold, and pasting
# 0.0 in there makes part A accept everything and print an empty table.
GATES = {
    "departure": ([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0], SHIPPED_GATE, "shipped"),
    "profit_zone_rr": ([0.0, 0.5, 1.0, 1.5, 2.0, 3.0], 1.0, "candidate, OFF by default"),
}


@dataclass
class Marked:
    """An observation plus where in its own series it happened."""

    observation: Observation
    position: float  # 0.0 at the start of the series, 1.0 at the end
    horizon_end: float  # same scale, but where its label finished resolving


def gather(bars: int, reward_atr: float, horizon: int) -> list[Marked]:
    """Every resolved observation across all series, on one shared time axis.

    Position is RELATIVE to each series rather than absolute, so a slice means
    the same stretch of history in all five. Pooling on absolute bar index would
    make the slices mean different dates per series and would quietly weight the
    longest one.
    """
    series = [
        ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
        ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
    ]
    params = SupplyDemandParams(**POPULATION)

    out: list[Marked] = []
    for symbol, interval in series:
        candles = history.load(symbol, interval, bars)
        data = evaluate(candles, params, reward_atr, horizon, symbol, interval)
        n = len(candles)
        # `real` and `rejected` together are the whole population. The split
        # between them is re-derived below from `departure`, because the point
        # of this file is to move the threshold around.
        for observation in data.real + data.rejected:
            out.append(
                Marked(
                    observation,
                    observation.touch_index / n,
                    min(1.0, (observation.touch_index + horizon) / n),
                )
            )
    return out


def value_of(observation: Observation, field: str) -> float:
    """The quantity a gate is applied to. `departure` is its own attribute; the
    road ahead lives in `factors`, recomputed as of the touch by `score_as_of`
    so it never knows about walls that were built later."""
    if field == "departure":
        return observation.departure
    return observation.factors[field]


def split(marked: list[Marked], field: str, threshold: float) -> tuple[list, list]:
    accepted = [m.observation.held for m in marked if value_of(m.observation, field) >= threshold]
    rejected = [m.observation.held for m in marked if value_of(m.observation, field) < threshold]
    return accepted, rejected


def gap(marked: list[Marked], field: str, threshold: float) -> float | None:
    """Accepted hold rate minus rejected hold rate, at this threshold."""
    accepted, rejected = split(marked, field, threshold)
    if len(accepted) < 10 or len(rejected) < 10:
        return None
    return float(np.mean(accepted) - np.mean(rejected))


def two_proportion(a: list[bool], b: list[bool]) -> tuple[float, float]:
    """z and p for two hold rates. Same arithmetic calibrate uses."""
    na, nb = len(a), len(b)
    if na < 10 or nb < 10:
        return (float("nan"), float("nan"))
    pa, pb = float(np.mean(a)), float(np.mean(b))
    pooled = (sum(a) + sum(b)) / (na + nb)
    se = sqrt(pooled * (1 - pooled) * (1 / na + 1 / nb))
    if se == 0:
        return (float("nan"), float("nan"))
    z = (pa - pb) / se
    return z, erfc(abs(z) / sqrt(2))


def sign_test(successes: int, trials: int) -> float:
    """Two-sided binomial p that this many folds agreed by chance."""
    if trials == 0:
        return float("nan")
    k = max(successes, trials - successes)
    tail = sum(comb(trials, i) for i in range(k, trials + 1)) / 2**trials
    return min(1.0, 2 * tail)


def run(marked: list[Marked], reward_atr: float, horizon: int, field: str) -> dict:
    grid, shipped, status = GATES[field]
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    print(f"\n{'=' * 78}")
    print(f"WALK-FORWARD on {field}   reward {reward_atr} ATR, horizon {horizon} bars")
    print(f"{'=' * 78}")

    print(f"\n  A. the gate at {shipped} ({status}), applied unchanged to each slice")
    print(f"  {'slice':<8}{'n acc':>7}{'held':>8}{'n rej':>7}{'held':>8}{'gap':>9}{'z':>8}{'p':>9}")

    stable = []
    agreed = 0
    for i in range(1, FOLDS):
        test = [m for m in marked if edges[i] <= m.position < edges[i + 1]]
        accepted, rejected = split(test, field, shipped)
        if len(accepted) < 10 or len(rejected) < 10:
            print(f"  {i:<8}{len(accepted):>7}{'-':>8}{len(rejected):>7}{'-':>8}{'too few':>9}")
            continue
        difference = float(np.mean(accepted) - np.mean(rejected))
        z, p = two_proportion(accepted, rejected)
        agreed += difference > 0
        print(
            f"  {i:<8}{len(accepted):>7}{np.mean(accepted):>8.1%}{len(rejected):>7}"
            f"{np.mean(rejected):>8.1%}{difference:>+9.1%}{z:>8.2f}{p:>9.4f}"
        )
        stable.append({"slice": i, "n_accepted": len(accepted), "n_rejected": len(rejected),
                       "gap": difference, "z": z, "p": p})

    if stable:
        print(
            f"\n  the gap pointed the right way in {agreed} of {len(stable)} slices"
            f"   sign test p={sign_test(agreed, len(stable)):.4f}"
            f"   (floor {2 / 2 ** len(stable):.4f})"
        )

    print("\n  B. the threshold CHOSEN from earlier slices only, graded on the next")
    print(f"  {'slice':<8}{'chosen':>8}{'train n':>9}{'test n':>8}{'oos gap':>9}{'p':>9}   purged")

    chosen_log = []
    oos_agreed = 0
    for i in range(1, FOLDS):
        start = edges[i]
        # Purge: a training event whose label was still resolving when the test
        # slice opened has already seen part of it.
        train = [m for m in marked if m.position < start and m.horizon_end < start]
        purged = sum(1 for m in marked if m.position < start and m.horizon_end >= start)
        test = [m for m in marked if start <= m.position < edges[i + 1]]
        if len(train) < 60 or len(test) < 20:
            print(f"  {i:<8}{'-':>8}{len(train):>9}{len(test):>8}{'too few':>9}")
            continue

        scored = [(gap(train, field, t), t) for t in grid]
        usable = [(result, t) for result, t in scored if result is not None]
        if not usable:
            print(f"  {i:<8}{'-':>8}{len(train):>9}{len(test):>8}{'no split':>9}")
            continue
        best = max(usable)[1]

        accepted, rejected = split(test, field, best)
        if len(accepted) < 10 or len(rejected) < 10:
            print(f"  {i:<8}{best:>8.1f}{len(train):>9}{len(test):>8}{'too few':>9}")
            continue
        difference = float(np.mean(accepted) - np.mean(rejected))
        _, p = two_proportion(accepted, rejected)
        oos_agreed += difference > 0
        print(
            f"  {i:<8}{best:>8.1f}{len(train):>9}{len(test):>8}{difference:>+9.1%}"
            f"{p:>9.4f}   {purged}"
        )
        chosen_log.append({"slice": i, "threshold": best, "train_n": len(train),
                           "test_n": len(test), "oos_gap": difference, "p": p,
                           "purged": purged})

    if chosen_log:
        print(
            f"\n  chosen out of sample pointed the right way in {oos_agreed} of"
            f" {len(chosen_log)} slices   sign test p={sign_test(oos_agreed, len(chosen_log)):.4f}"
        )
        picks = [c["threshold"] for c in chosen_log]
        print(
            f"  thresholds picked: {picks}   shipped is {shipped}"
            + ("   <- the past kept choosing the shipped value"
               if len(set(picks)) == 1 and picks[0] == shipped else "")
        )

    # The floor. Two proportions near 0.5 need about 15.7 * 0.25 / d^2 per arm.
    per_slice = min((s["n_accepted"] for s in stable), default=0)
    if per_slice:
        floor = sqrt(15.7 * 0.25 / per_slice)
        print(
            f"\n  smallest accepted slice is {per_slice}. At 80% power one slice"
            f" resolves a gap\n  of about {floor:.0%} and nothing finer, which is why"
            f" the sign test across slices\n  is the statistic here and the per-slice"
            f" p values are not."
        )

    return {
        "shipped": stable,
        "shipped_agreement": [agreed, len(stable)],
        "chosen": chosen_log,
        "chosen_agreement": [oos_agreed, len(chosen_log)],
        "detectable_gap": sqrt(15.7 * 0.25 / per_slice) if per_slice else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    everything = {}
    for reward_atr, horizon in [(0.5, 40), (1.0, 40), (2.0, 80)]:
        marked = gather(args.bars, reward_atr, horizon)
        for field in GATES:
            everything[f"{field}_r{reward_atr}_h{horizon}"] = run(
                marked, reward_atr, horizon, field
            )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(everything, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
