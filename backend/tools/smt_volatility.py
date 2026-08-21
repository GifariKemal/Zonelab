"""Is SSMT worse in high volatility? Somebody claimed it. This measures it.

    python -m tools.smt_volatility --bars 50000 --degree day \\
        --pairs "mt5:XAUUSD|XAGUSD,mt5:XAUUSD|DXY,PAXGUSDT|BTCUSDT"

THE CLAIM, as put to this project: "SMT Divergence pada pasar dengan volatilitas
rendah sangat akurat, tapi pada pasar dengan volatilitas ekstrem, SMT sering kali
menjadi false signal karena slippage atau lonjakan harga." Attached to it was a
proposed gate at "ATR > 2.5x the 30-day average".

WHY THIS IS A MEASUREMENT AND NOT THE GATE. The number 2.5 came with no
measurement, and a threshold nobody has measured is the one thing this project
refuses to ship - `params.py` says so at four separate knobs. But the claim
underneath it is empirical and cheap to test: there are tens of thousands of
divergences in the MT5 history and the volatility at each one is arithmetic. So
the honest order is to test the claim first. If the effect is real the threshold
is born from data; if it is not, a filter was avoided.

WHAT "ACCURATE" IS TAKEN TO MEAN, stated because the claim does not say. A
bearish SSMT is the chart taking the previous quarter's HIGH while the partner
fails to. If that reading carries information, price should travel DOWN more often
than up from the bar the divergence became knowable. So the outcome is a
SYMMETRIC bracket, `k` ATR either way from the close at `knowable_at`, and the
question is which side is reached first.

Symmetric on purpose: under a random walk it resolves to 50% by construction, so
the null needs no separate estimate and any deviation is the effect. An
asymmetric target would need its own baseline and would let the bracket masquerade
as a finding - which is exactly the mistake `calibrate.resolve` documents at
length about zone height.

TIES ARE DISCARDED, NOT SCORED. When one bar reaches both levels, bar data cannot
say which came first. Counting them as failures would bias against the claim and
as successes would flatter it; the bracket is symmetric so the ambiguity is
symmetric too, and dropping them is the only choice that does not put a thumb on
either scale. The count is reported.

NO LOOKAHEAD ANYWHERE. A divergence enters at `knowable_at`, which is the close
of its second quarter and the first instant the reading exists. Volatility is the
ATR at that bar against a TRAILING window only. The bracket walks forward from
that bar, never before it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass

import numpy as np

from app.aligned import load_aligned
from app.indicators import wilder_atr
from app.ssmt import ssmt

#: Pairs as `chart|partner`. The chart symbol is the one the bracket is measured
#: on, because a divergence is positioned on one instrument's price and drawing
#: the partner's on it would be the most confidently wrong line a chart can
#: carry.
PAIRS = [
    ("XAUUSD", "XAGUSD"),
    ("XAUUSD", "DXY"),
]

#: Bars of trailing ATR the current ATR is compared against, per interval. Thirty
#: days is the window the claim named, converted to bars rather than guessed.
TRAILING_DAYS = 30

#: Symmetric bracket width in ATR, and the horizon in bars. Three widths because
#: an effect that exists at one distance and vanishes at the others is a bracket
#: artefact, which is the failure mode `calibrate.py` was rewritten to catch.
WIDTHS = (0.5, 1.0, 2.0)
HORIZON = 40


@dataclass
class Observation:
    """One divergence, its volatility, and whether the claimed direction won."""

    ratio: float  # ATR at the event over the trailing mean ATR
    down_first: bool  # the claimed direction was reached first


def _bars_per_day(interval: str) -> int:
    from app.providers import INTERVALS

    step = INTERVALS[interval]
    return max(1, 86_400 // step)


def _resolve(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    at: int,
    unit: float,
    width: float,
) -> bool | None:
    """Which side of a symmetric bracket is reached first from bar `at`.

    True when the DOWN side goes first, which is the direction a bearish SSMT
    claims. None when neither side is reached inside the horizon, and None when a
    single bar reaches both - see the module docstring on ties.
    """
    reach = width * unit
    down = close[at] - reach
    up = close[at] + reach
    for i in range(at + 1, min(len(close), at + 1 + HORIZON)):
        hit_down = low[i] <= down
        hit_up = high[i] >= up
        if hit_down and hit_up:
            return None
        if hit_down:
            return True
        if hit_up:
            return False
    return None


def gather(
    chart: str, partner: str, interval: str, bars: int, degree: str, provider: str
):
    """Every knowable bearish divergence on `chart` against `partner`.

    ONE PROVIDER FOR THE WHOLE BASKET, and it matters: a symbol id names a
    different instrument per source - XAUUSD is a COMEX contract on yahoo and a
    broker spot CFD on mt5, and the two sat 56 dollars apart when this was
    written. Reading the two legs from different venues would measure the basis
    rather than the divergence.
    """
    series, _ = asyncio.run(load_aligned([chart, partner], interval, bars, provider))
    events, _ = ssmt(series, degree)

    rows = series[chart]
    high = np.array([c.high for c in rows], dtype=np.float64)
    low = np.array([c.low for c in rows], dtype=np.float64)
    close = np.array([c.close for c in rows], dtype=np.float64)
    atr = wilder_atr(high, low, close, 14)
    index_of = {c.time: i for i, c in enumerate(rows)}
    trailing = _bars_per_day(interval) * TRAILING_DAYS

    out: dict[float, list[Observation]] = {w: [] for w in WIDTHS}
    ties = 0
    unresolved = 0
    for event in events:
        # BEARISH ONLY, and it is a shape rather than "a divergence exists": the
        # chart symbol took the high and the partner failed. The mirror is a
        # different reading and mixing the two would average two claims into one
        # number that describes neither.
        if event.side != "high" or event.took != chart:
            continue
        at = index_of.get(event.knowable_at)
        if at is None or at < trailing or at + 2 >= len(close):
            continue
        window = atr[at - trailing : at]
        mean = float(window.mean())
        unit = float(atr[at])
        if mean <= 0 or unit <= 0:
            continue
        ratio = unit / mean
        for width in WIDTHS:
            verdict = _resolve(high, low, close, at, unit, width)
            if verdict is None:
                unresolved += 1
                continue
            out[width].append(Observation(ratio=ratio, down_first=verdict))
    return out, ties, unresolved


def _report(label: str, observations: list[Observation]) -> dict:
    """Rate by volatility quartile, and the whole-sample rate beside it."""
    if len(observations) < 40:
        print(f"  {label}: {len(observations)} observations, too few to split")
        return {"n": len(observations), "insufficient": True}

    overall = sum(o.down_first for o in observations) / len(observations)
    ratios = sorted(o.ratio for o in observations)
    cuts = [ratios[int(len(ratios) * q)] for q in (0.25, 0.5, 0.75)]

    buckets: list[list[Observation]] = [[], [], [], []]
    for o in observations:
        i = sum(o.ratio > c for c in cuts)
        buckets[i].append(o)

    print(f"  {label}: n={len(observations)}  whole sample {overall:6.1%}")
    rows = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        rate = sum(o.down_first for o in bucket) / len(bucket)
        lo = min(o.ratio for o in bucket)
        hi = max(o.ratio for o in bucket)
        name = ["calmest", "quiet", "busy", "wildest"][i]
        print(
            f"    Q{i + 1} {name:8} ATR ratio {lo:4.2f}-{hi:4.2f}  "
            f"n={len(bucket):5}  down-first {rate:6.1%}  "
            f"vs sample {rate - overall:+.1%}"
        )
        rows.append(
            {
                "quartile": i + 1,
                "name": name,
                "ratio_from": round(lo, 3),
                "ratio_to": round(hi, 3),
                "n": len(bucket),
                "down_first": round(rate, 4),
                "vs_sample": round(rate - overall, 4),
            }
        )
    # The claim's own threshold, reported directly rather than only by quartile.
    extreme = [o for o in observations if o.ratio > 2.5]
    if extreme:
        rate = sum(o.down_first for o in extreme) / len(extreme)
        print(
            f"    the claim's own cut, ATR > 2.5x: n={len(extreme)}  "
            f"down-first {rate:6.1%}  vs sample {rate - overall:+.1%}"
        )
    else:
        print("    the claim's own cut, ATR > 2.5x: NEVER OCCURS in this sample")
    return {
        "n": len(observations),
        "whole_sample": round(overall, 4),
        "quartiles": rows,
        "above_2_5x": (
            None
            if not extreme
            else {
                "n": len(extreme),
                "down_first": round(
                    sum(o.down_first for o in extreme) / len(extreme), 4
                ),
            }
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", type=int, default=20_000)
    parser.add_argument("--interval", type=str, default="1h")
    parser.add_argument("--degree", type=str, default="day")
    parser.add_argument("--pairs", type=str, default="")
    parser.add_argument("--provider", type=str, default="mt5")
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    pairs = PAIRS
    if args.pairs:
        pairs = [
            (part.split("|")[0], part.split("|")[1])
            for part in args.pairs.split(",")
            if "|" in part
        ]

    print(
        f"Bearish SSMT at {args.degree} degree, {args.interval}, {args.bars} bars, "
        f"symmetric {WIDTHS} ATR bracket over {HORIZON} bars.\n"
        "A symmetric bracket resolves to 50% under a random walk, so 50% IS the "
        "null and any deviation is the effect.\n"
    )
    everything: dict[str, dict] = {}
    pooled: dict[float, list[Observation]] = {w: [] for w in WIDTHS}
    for chart, partner in pairs:
        print(f"{chart} vs {partner}")
        try:
            got, _, unresolved = gather(
                chart, partner, args.interval, args.bars, args.degree, args.provider
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  skipped: {exc}")
            continue
        for width in WIDTHS:
            everything[f"{chart}|{partner}|{width}"] = _report(
                f"{width} ATR", got[width]
            )
            pooled[width].extend(got[width])
        print(f"  ({unresolved} event-widths reached neither side or both)")
        print()

    print("POOLED ACROSS PAIRS")
    for width in WIDTHS:
        everything[f"pooled|{width}"] = _report(f"{width} ATR", pooled[width])

    # THE VERDICT IS STATED, not left for a reader to infer from a table. The
    # claim is directional and specific, so it can be wrong in a specific way.
    print()
    interesting = []
    for width in WIDTHS:
        rows = everything.get(f"pooled|{width}", {}).get("quartiles") or []
        if len(rows) == 4:
            spread = rows[3]["down_first"] - rows[0]["down_first"]
            interesting.append((width, spread))
    if interesting and max(abs(s) for _, s in interesting) < 0.05:
        print(
            "The claim is NOT supported. Calmest and wildest quartiles differ by "
            f"under 5 points at every bracket width (largest {max(abs(s) for _, s in interesting):.1%}), "
            "so volatility does not separate these readings and a filter on it "
            "would discard events for no measured gain."
        )
    elif interesting:
        worst = max(interesting, key=lambda x: abs(x[1]))
        print(
            f"A spread of {worst[1]:+.1%} between the calmest and wildest quartile "
            f"at {worst[0]} ATR. Before anything is gated on it: this is ONE "
            "in-sample split with no walk-forward, no purging and no placebo, and "
            "every threshold in this project that skipped those steps was later "
            "retracted."
        )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "claim": (
                        "SSMT is accurate in low volatility and a false signal in "
                        "extreme volatility; proposed gate ATR > 2.5x 30-day mean"
                    ),
                    "bracket": {"widths": list(WIDTHS), "horizon": HORIZON,
                                "symmetric": True, "null": 0.5},
                    "degree": args.degree,
                    "interval": args.interval,
                    "bars": args.bars,
                    "results": everything,
                },
                handle,
                indent=1,
            )

if __name__ == "__main__":
    main()
