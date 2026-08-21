"""Does a third push actually reverse? The counting question behind Three Drives.

    python -m tools.three_pushes --bars 50000 --series "mt5:XAUUSD@15m,mt5:XAUUSD@1h"

WHY THIS EXISTS INSTEAD OF A DETECTOR. "Three Drives" is a harmonic-trading
pattern - Carney's lineage, by way of Pesavento and Dunnigan - and this project
does not draw it, for reasons written down in `docs/ADOPSI.md`. The short version
is that its central number is not published: the two founding sources disagree on
whether the extension is measured from the prior DRIVE or the prior RETRACEMENT,
which places the target roughly two thirds of a leg apart, and no source anywhere
publishes a tolerance or a hit rate. The only implementation that operationalises
it exposes tolerance as a slider.

But the SHAPE underneath it is not exotic, and the claim it makes is testable
without adopting any of the ratios. Three pushes in one direction, each further
than the last; does the next leg reverse more often than a leg picked at random?
That question needs no Fibonacci number, no tolerance, and nothing this repo does
not already compute - `swings()` produces the legs. If the answer is the base
rate, the pattern is closed as a question and nobody has to invent a threshold to
find out.

WHAT IS AND IS NOT MEASURED. A "push" here is a swing-to-swing leg. Three
consecutive same-direction pushes with monotonically extending extremes make a
candidate. The outcome is whether the NEXT confirmed pivot after the third push
reverses - i.e. whether the following leg goes the other way. The base rate is
the same question asked of every leg in the series, which is the only honest
comparison: a market that reverses on two thirds of all legs would make a
"pattern" that reverses on two thirds of its instances look predictive.

Knowability is respected. A pivot enters the sequence at `confirmed_at`, not at
the bar it sits on, so no candidate is assembled from information that had not
arrived - the same rule `test_dealing_range.py` and `test_cisd.py` pin. That is
also the honest answer to why the pattern cannot be traded as drawn: the third
push is only nameable after it has been confirmed, which is after the reaction
has begun.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

import numpy as np

from app.detect.structure import swings
from tools import history

SERIES = [("mt5:XAUUSD", "15m"), ("mt5:XAUUSD", "1h")]

#: Pivot strictness. The structure overlay's own default, so the legs counted
#: here are the legs the chart draws rather than a population invented for this
#: measurement.
SWING_N = 3


@dataclass(frozen=True)
class Tally:
    """Reversals over trials, for one population."""

    reversed_: int = 0
    total: int = 0

    def plus(self, did_reverse: bool) -> "Tally":
        return Tally(self.reversed_ + int(did_reverse), self.total + 1)

    @property
    def rate(self) -> float:
        return self.reversed_ / self.total if self.total else float("nan")


def _legs(high: np.ndarray, low: np.ndarray) -> list[tuple[int, bool, float]]:
    """Alternating pivots as legs: (confirmed_at, is_up_leg, extreme).

    Alternation is enforced rather than assumed. `swings` emits a high and a low
    pivot independently and both can land on one bar; a run of two highs with no
    low between them is not two legs, it is one leg whose end moved. Keeping the
    later extreme of a repeated side is what makes "each push further than the
    last" mean what it says.
    """
    out: list[tuple[int, bool, float]] = []
    for pivot in swings(high, low, SWING_N, SWING_N):
        if out and out[-1][1] == pivot.high:
            previous = out[-1]
            further = pivot.price > previous[2] if pivot.high else pivot.price < previous[2]
            if further:
                out[-1] = (pivot.confirmed_at, pivot.high, pivot.price)
            continue
        out.append((pivot.confirmed_at, pivot.high, pivot.price))
    return out


def measure(high: np.ndarray, low: np.ndarray) -> tuple[Tally, Tally]:
    """(after three extending pushes, every pivot) as REVERSAL tallies.

    THE DIRECTION CONVENTION, because the first version of this got it backwards
    and the inverted number looked like a strong result. The pattern's direction
    is set by the three pushes: three rising highs predict a move DOWN. So the
    reversal test is on the OTHER side - after three rising highs, does the next
    low break BELOW the previous low - and not on the side the pushes are on. A
    test that asked whether the next high failed to exceed the last one is asking
    about the pushes themselves, and it answers 65% on this data while meaning
    the opposite of what it appears to.

    The base rate answers the identical question over every pivot, so the two are
    the same statistic on different populations. Without that, a market whose
    pullbacks break their predecessor half the time would make any subset look
    informative.
    """
    legs = _legs(high, low)
    pattern = Tally()
    base = Tally()

    for i in range(1, len(legs) - 1):
        # `legs[i]` is the last push. `legs[i-1]` and `legs[i+1]` are the pivots
        # on the OPPOSITE side, and a reversal is the second one extending past
        # the first, away from where the pushes were going.
        here, prior_other, next_other = legs[i], legs[i - 1], legs[i + 1]
        if next_other[1] != prior_other[1] or next_other[1] == here[1]:
            continue
        # here[1] True means the push side is highs, so the pushes point UP and a
        # reversal is a LOWER low.
        did_reverse = (
            next_other[2] < prior_other[2] if here[1] else next_other[2] > prior_other[2]
        )
        base = base.plus(did_reverse)

        if i < 4:
            continue
        a, b, c = legs[i - 4], legs[i - 2], legs[i]
        if not (a[1] == b[1] == c[1] == here[1]):
            continue
        extending = (a[2] < b[2] < c[2]) if c[1] else (a[2] > b[2] > c[2])
        if not extending:
            continue
        pattern = pattern.plus(did_reverse)

    return pattern, base


def _binomial_p(hits: int, trials: int, rate: float) -> float:
    """Two-sided normal approximation. Enough for a null; if a real edge ever
    turns up here it earns an exact test and a walk-forward, not a one-liner."""
    if trials == 0 or rate <= 0 or rate >= 1:
        return float("nan")
    from math import erfc, sqrt

    z = (hits - trials * rate) / sqrt(trials * rate * (1 - rate))
    return erfc(abs(z) / sqrt(2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", type=int, default=20_000)
    parser.add_argument("--series", type=str, default="")
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    series = SERIES
    if args.series:
        series = [
            (part.rsplit("@", 1)[0], part.rsplit("@", 1)[1])
            for part in args.series.split(",")
            if part.strip()
        ]

    rows = []
    pooled_pattern = Tally()
    pooled_base = Tally()
    for symbol, interval in series:
        candles = history.load(symbol, interval, args.bars)
        high = np.array([c.high for c in candles])
        low = np.array([c.low for c in candles])
        pattern, base = measure(high, low)
        pooled_pattern = Tally(
            pooled_pattern.reversed_ + pattern.reversed_, pooled_pattern.total + pattern.total
        )
        pooled_base = Tally(
            pooled_base.reversed_ + base.reversed_, pooled_base.total + base.total
        )
        rows.append(
            {
                "symbol": symbol,
                "interval": interval,
                "bars": len(candles),
                "pattern_n": pattern.total,
                "pattern_reversal_rate": pattern.rate,
                "base_n": base.total,
                "base_reversal_rate": base.rate,
                "lift": pattern.rate - base.rate,
            }
        )
        print(
            f"{symbol} {interval:>4}  {len(candles):>6} bars   "
            f"reversal after three pushes {pattern.reversed_:>5}/{pattern.total:<5} "
            f"= {pattern.rate:6.1%}   base {base.reversed_:>6}/{base.total:<6} "
            f"= {base.rate:6.1%}   lift {pattern.rate - base.rate:+.1%}"
        )

    p = _binomial_p(pooled_pattern.reversed_, pooled_pattern.total, pooled_base.rate)
    print(
        f"\nPOOLED  reversal after three pushes {pooled_pattern.rate:.1%} "
        f"(n={pooled_pattern.total})   base {pooled_base.rate:.1%} "
        f"(n={pooled_base.total})   lift {pooled_pattern.rate - pooled_base.rate:+.1%}   "
        f"p={p:.4f}"
    )
    lift = pooled_pattern.rate - pooled_base.rate
    if abs(lift) < 0.02:
        verdict = (
            "A lift of essentially zero closes the question: the shape is common, "
            "what follows it is the market's own reversal rate, and no ratio or "
            "tolerance would change that."
        )
    elif lift < 0:
        verdict = (
            "The lift is NEGATIVE, which is the strongest available answer and "
            "not the one the pattern claims. Three extending pushes are followed "
            "by a reversal LESS often than an average pivot is: the shape selects "
            "for a trending market, so what follows it is more continuation. A "
            "detector built on this as a reversal signal would point the wrong "
            "way, and no choice of tolerance can fix a sign."
        )
    else:
        verdict = (
            "The lift is positive. Before anything is drawn from it, it needs the "
            "walk-forward gate every other threshold in this project went "
            "through: slices, purging, a sign test and a placebo."
        )
    print("\n" + verdict)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "series": rows,
                    "pooled": {
                        "pattern_n": pooled_pattern.total,
                        "pattern_reversal_rate": pooled_pattern.rate,
                        "base_n": pooled_base.total,
                        "base_reversal_rate": pooled_base.rate,
                        "lift": pooled_pattern.rate - pooled_base.rate,
                        "p": p,
                    },
                    "swing_n": SWING_N,
                },
                handle,
                indent=1,
            )


if __name__ == "__main__":
    main()
