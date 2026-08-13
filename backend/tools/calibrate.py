"""Does the strength score actually predict anything?

    python -m tools.calibrate

The question, stated before any measurement so the answer cannot be moved
afterwards: **when price returns to a zone for the first time, does the zone
hold, and does `strength` separate the ones that hold from the ones that do
not?**

Three rules make the answer honest rather than flattering.

1. **Scores are taken as of the touch, never after it.** The `strength` a zone
   carries in a finished chart already knows how many times price came back and
   how deep it went. Ranking first-touch outcomes by that number is circular. At
   first touch a zone is fresh by definition, and its departure is only known up
   to that bar, so both are recomputed here.

2. **The comparison is against a base rate, not against zero.** The outcome is a
   bracket, and bracket geometry alone fixes a hit rate for a driftless series.
   "68% of zones held" means nothing until you know what a coin flipped at the
   same geometry scores. Every table prints the base rate beside the result.

3. **There are two controls, one easy and one hard.**
   - *Placebo*: each zone paired with a fake one of identical size, side and
     age, moved to a random price. Beating this only proves a zone is better
     than an arbitrary level, which is a low bar.
   - *Rejected*: real formations that failed the departure gate. Both cohorts
     are genuine consolidations at genuine structure, and the only difference
     is the filter. If accepted zones do not beat rejected ones, the gate is
     decoration.

Nothing here is a trading result. It measures whether the drawing is
informative, which is the only claim the app makes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field

import numpy as np

from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.models import Candle, SupplyDemandParams, Zone, ZoneSide
from tools import history

# Population settings: every gate that exists to keep a chart readable is turned
# off, because a display cap would silently bias the sample toward recent zones.
# The departure gate is set to zero so the rejected cohort exists at all; the
# split back into accepted and rejected happens on the as-of departure below.
POPULATION = dict(
    merge_overlap_pct=1.0, max_zones_per_side=100, show_broken=True, departure_min_atr=0.0
)
SHIPPED_GATE = SupplyDemandParams().departure_min_atr

RNG = np.random.default_rng(20260813)


@dataclass
class Observation:
    """One zone, scored as of its first touch, with what happened next."""

    side: str
    kind: str
    touch_index: int
    held: bool
    factors: dict[str, float]
    strength: float  # the composite under test; today that is formation_score
    departure: float  # raw ATR multiple, kept out of the composite on purpose


@dataclass
class Dataset:
    label: str
    real: list[Observation] = field(default_factory=list)
    placebo: list[Observation] = field(default_factory=list)
    rejected: list[Observation] = field(default_factory=list)


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Mann-Whitney U as a rank AUC. 0.5 is no discrimination at all."""
    pos, neg = labels.sum(), (~labels).sum()
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    # Average ranks within ties, otherwise a factor with few distinct values
    # (compactness takes six) scores an AUC that depends on sort order.
    _, inverse, counts = np.unique(scores, return_inverse=True, return_counts=True)
    sums = np.zeros(len(counts))
    np.add.at(sums, inverse, ranks)
    ranks = (sums / counts)[inverse]
    return float((ranks[labels].sum() - pos * (pos + 1) / 2) / (pos * neg))


def _two_proportion(a: np.ndarray, b: np.ndarray) -> str:
    """Two-proportion z-test, reported as a readable verdict.

    Written out rather than pulled from scipy because scipy is not a dependency
    and this is nine lines of arithmetic.
    """
    na, nb = len(a), len(b)
    if na < 10 or nb < 10:
        return "n too small to test"
    pa, pb = a.mean(), b.mean()
    pooled = (a.sum() + b.sum()) / (na + nb)
    se = float(np.sqrt(pooled * (1 - pooled) * (1 / na + 1 / nb)))
    if se == 0:
        return "no variance"
    z = (pa - pb) / se
    # Normal tail via erf, which is in the standard library's math module.
    from math import erfc, sqrt

    p = erfc(abs(z) / sqrt(2))
    return f"z={z:+.2f} p={p:.4f} {'SIGNIFICANT' if p < 0.05 else 'not significant'}"


def bootstrap_auc(scores: np.ndarray, labels: np.ndarray, n: int = 2000) -> tuple[float, float]:
    """Percentile CI. An AUC of 0.58 on n=40 is not evidence of anything."""
    if len(scores) < 20:
        return (float("nan"), float("nan"))
    draws = []
    for _ in range(n):
        pick = RNG.integers(0, len(scores), len(scores))
        value = auc(scores[pick], labels[pick])
        if not np.isnan(value):
            draws.append(value)
    if not draws:
        return (float("nan"), float("nan"))
    return (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)))


def evaluate(
    candles: list[Candle],
    params: SupplyDemandParams,
    reward_atr: float,
    horizon: int,
    label: str,
) -> Dataset:
    zones, _ = detect(candles, params)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)
    index_of = {c.time: i for i, c in enumerate(candles)}

    data = Dataset(label=label)
    for zone in zones:
        if zone.first_test_time is None:
            continue  # never revisited, so there is no outcome to score
        touch = index_of.get(zone.first_test_time)
        if touch is None or touch <= zone.anatomy.leg_out_to:
            continue

        scored = score_as_of(zone, high, low, atr, touch, params)
        if scored is None:
            continue  # no measurable leg-out before the touch

        outcome = resolve(zone, high, low, close, atr, touch, reward_atr, horizon)
        if outcome is None:
            continue  # neither side of the bracket reached inside the horizon

        strength, factors, departure = scored
        observation = Observation(
            zone.side.value, zone.kind.value, touch, outcome, factors, strength, departure
        )

        if departure < SHIPPED_GATE:
            # The formation was real but the shipped gate would have discarded
            # it. This is the control that tells us whether the gate earns its
            # place, so it is kept rather than dropped.
            data.rejected.append(observation)
            continue
        data.real.append(observation)

        placebo = shift(zone, atr[zone.anatomy.base_to])
        p_touch = first_touch(placebo, high, low, zone.anatomy.leg_out_to + 1)
        if p_touch is not None:
            p_outcome = resolve(
                placebo, high, low, close, atr, p_touch, reward_atr, horizon
            )
            if p_outcome is not None:
                data.placebo.append(
                    Observation(
                        zone.side.value, zone.kind.value, p_touch, p_outcome,
                        factors, strength, departure,
                    )
                )
    return data


def score_as_of(
    zone: Zone,
    high: np.ndarray,
    low: np.ndarray,
    atr: np.ndarray,
    touch: int,
    params: SupplyDemandParams,
) -> tuple[float, dict[str, float], float] | None:
    """Recompute the score using only what was knowable before `touch`.

    Geometry, base tightness, compactness and leg volume are all fixed at
    formation, so they carry over unchanged. Only two components move:
    freshness, which is 1.0 because an untouched zone is fresh by construction,
    and departure, whose lookahead window has to be clipped at the touch.
    """
    atr_base = float(atr[max(0, zone.anatomy.base_from - 1)])
    if atr_base <= 0:
        return None

    stop = min(zone.anatomy.leg_out_from + params.departure_lookahead, touch)
    if stop <= zone.anatomy.leg_out_from:
        return None

    window = slice(zone.anatomy.leg_out_from, stop)
    if zone.side is ZoneSide.DEMAND:
        excursion = float(high[window].max()) - zone.proximal
    else:
        excursion = zone.proximal - float(low[window].min())
    departure = max(0.0, excursion) / atr_base

    # The shipped factors are all fixed at formation, so they need no
    # adjustment. Departure is returned separately: it is the gate's input and
    # the bucket table's x-axis, and deliberately no longer part of the score.
    factors = dict(zone.factors)
    formation = round(float(np.clip(sum(factors.values()), 0.0, 1.0)), 4)
    return formation, factors, departure


def resolve(
    zone: Zone,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    touch: int,
    reward_atr: float,
    horizon: int,
) -> bool | None:
    """Held or failed, from the touch bar forward.

    When a single bar reaches both the target and the stop, it is scored as a
    failure. Bar data cannot say which came first, and guessing in the
    favourable direction is how backtests flatter themselves.
    """
    atr_t = float(atr[touch])
    if atr_t <= 0:
        return None

    demand = zone.side is ZoneSide.DEMAND
    target = (
        zone.proximal + reward_atr * atr_t if demand else zone.proximal - reward_atr * atr_t
    )

    for i in range(touch, min(len(close), touch + horizon)):
        broke = close[i] < zone.distal if demand else close[i] > zone.distal
        reached = high[i] >= target if demand else low[i] <= target
        if broke:
            return False
        if reached:
            return True
    return None


def shift(zone: Zone, atr_base: float) -> Zone:
    """A same-size, same-side zone at a deliberately wrong price."""
    offset = float(RNG.choice([-1, 1])) * float(RNG.uniform(1.5, 5.0)) * max(atr_base, 1e-9)
    moved = zone.model_copy(deep=True)
    moved.top += offset
    moved.bottom += offset
    moved.proximal += offset
    moved.distal += offset
    return moved


def first_touch(zone: Zone, high: np.ndarray, low: np.ndarray, start: int) -> int | None:
    for i in range(start, len(high)):
        if low[i] <= zone.top and high[i] >= zone.bottom:
            return i
    return None


def report(datasets: list[Dataset], reward_atr: float, horizon: int) -> dict:
    real = [o for d in datasets for o in d.real]
    placebo = [o for d in datasets for o in d.placebo]
    rejected = [o for d in datasets for o in d.rejected]
    if len(real) < 30:
        print(f"  only {len(real)} resolved zones, refusing to report")
        return {}

    labels = np.array([o.held for o in real])
    base = labels.mean()
    p_labels = np.array([o.held for o in placebo]) if placebo else np.array([], dtype=bool)
    r_labels = np.array([o.held for o in rejected]) if rejected else np.array([], dtype=bool)

    print(f"\n{'=' * 78}")
    print(f"REWARD {reward_atr} ATR, HORIZON {horizon} bars")
    print(f"{'=' * 78}")
    print(f"  drawn zones         n={len(real)}   held={base:.1%}   <- the base rate")
    if len(p_labels):
        print(
            f"  placebo levels      n={len(p_labels)}   held={p_labels.mean():.1%}"
            f"   drawn beats placebo by {base - p_labels.mean():+.1%}"
        )
    if len(r_labels):
        print(
            f"  gate-rejected       n={len(r_labels)}   held={r_labels.mean():.1%}"
            f"   drawn beats rejected by {base - r_labels.mean():+.1%}"
            f"   {_two_proportion(labels, r_labels)}"
        )

    print(f"\n  {'factor':<14}{'AUC':>8}{'95% CI':>18}   reading")
    factor_names = list(real[0].factors)
    out: dict = {
        "n": len(real),
        "base_rate": base,
        "placebo_rate": float(p_labels.mean()) if len(p_labels) else None,
        "rejected_rate": float(r_labels.mean()) if len(r_labels) else None,
        "rejected_n": len(r_labels),
        "gate_test": _two_proportion(labels, r_labels) if len(r_labels) else None,
        "factors": {},
    }

    for name in [*factor_names, "strength"]:
        values = np.array(
            [o.strength if name == "strength" else o.factors[name] for o in real]
        )
        if values.std() < 1e-12:
            print(f"  {name:<14}{'constant':>8}{'':>18}   carries no information here")
            out["factors"][name] = {"auc": None, "note": "constant"}
            continue
        value = auc(values, labels)
        lo, hi = bootstrap_auc(values, labels)
        verdict = (
            "discriminates" if lo > 0.5 else "inverted" if hi < 0.5 else "indistinguishable"
        )
        print(f"  {name:<14}{value:>8.3f}{f'[{lo:.3f}, {hi:.3f}]':>18}   {verdict}")
        out["factors"][name] = {"auc": value, "ci": [lo, hi], "verdict": verdict}

    # Is departure a threshold or a gradient? The gate treats it as a
    # threshold while the score treats it as a gradient, and only one of those
    # can be right. Bucketed over the FULL population, rejected included.
    everything = rejected + real
    if everything:
        print(f"\n  departure (ATR)     n     held     <- gate sits at {SHIPPED_GATE}")
        raw = np.array([o.departure for o in everything])
        held_all = np.array([o.held for o in everything])
        edges = [0, 1, 2, 3, 4, 5, 99]
        buckets = []
        for lo_e, hi_e in zip(edges, edges[1:]):
            pick = (raw >= lo_e) & (raw < hi_e)
            if pick.sum() < 10:
                continue
            print(
                f"  {lo_e:>3} to {hi_e:<3}      {pick.sum():>5}   "
                f"{held_all[pick].mean():>6.1%}"
            )
            buckets.append(
                {"from": lo_e, "to": hi_e, "n": int(pick.sum()),
                 "held": float(held_all[pick].mean())}
            )
        out["departure_buckets"] = buckets

    # Split-half on time. A factor that only works in one half is a window fit.
    print(f"\n  {'factor':<14}{'AUC 1st half':>14}{'AUC 2nd half':>14}   stable?")
    mid = len(datasets[0].real) and np.median([o.touch_index for o in real])
    first = np.array([o.touch_index <= mid for o in real])
    for name in [*factor_names, "strength"]:
        values = np.array(
            [o.strength if name == "strength" else o.factors[name] for o in real]
        )
        if values.std() < 1e-12:
            continue
        a = auc(values[first], labels[first])
        b = auc(values[~first], labels[~first])
        same_side = (a - 0.5) * (b - 0.5) > 0
        print(
            f"  {name:<14}{a:>14.3f}{b:>14.3f}   "
            f"{'same sign' if same_side else 'SIGN FLIPS'}"
        )
        out["factors"][name]["halves"] = [a, b]

    # Decile lift on the composite. If the top decile does not beat the base
    # rate, the composite is not usable as a ranking however good its AUC.
    strengths = np.array([o.strength for o in real])
    print(f"\n  strength quintile   n     held      lift vs base")
    edges = np.quantile(strengths, [0, 0.2, 0.4, 0.6, 0.8, 1.0])
    quintiles = []
    for i in range(5):
        lo_e, hi_e = edges[i], edges[i + 1]
        pick = (strengths >= lo_e) & (strengths <= hi_e if i == 4 else strengths < hi_e)
        if pick.sum() == 0:
            continue
        rate = labels[pick].mean()
        print(
            f"  Q{i + 1} {lo_e:.3f}-{hi_e:.3f}  {pick.sum():>4}   {rate:>6.1%}"
            f"    {rate - base:+.1%}"
        )
        quintiles.append({"q": i + 1, "n": int(pick.sum()), "held": float(rate)})
    out["quintiles"] = quintiles
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    # Several instruments and timeframes. A conclusion drawn from one series on
    # one timeframe is a property of that window, not of the detector.
    series = [
        ("PAXGUSDT", "15m"),
        ("PAXGUSDT", "1h"),
        ("BTCUSDT", "15m"),
        ("BTCUSDT", "1h"),
        ("ETHUSDT", "1h"),
    ]
    params = SupplyDemandParams(**POPULATION)

    print("Loading history (cached after the first run)")
    loaded = [(s, tf, history.load(s, tf, args.bars)) for s, tf in series]

    everything: dict = {}
    for reward_atr, horizon in [(0.5, 40), (1.0, 40), (2.0, 80)]:
        datasets = [
            evaluate(candles, params, reward_atr, horizon, f"{s}-{tf}")
            for s, tf, candles in loaded
        ]
        for d in datasets:
            held = [o.held for o in d.real]
            print(
                f"  {d.label:<14} n={len(d.real):<5} held="
                f"{np.mean(held) if held else float('nan'):.1%}"
            )
        everything[f"r{reward_atr}_h{horizon}"] = report(datasets, reward_atr, horizon)

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(everything, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
