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

from app.confluence import mark_nesting
from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.profit_zone import profit_zone_at
from app.resample import resample
from app.models import Candle, SupplyDemandParams, Zone, ZoneSide
from tools import history

# Population settings: every gate that exists to keep a chart readable is turned
# off, because a display cap would silently bias the sample toward recent zones.
# The departure gate is set to zero so the rejected cohort exists at all; the
# split back into accepted and rejected happens on the as-of departure below.
#
# `max_zones_per_side=0` means NO CAP, and it has to be zero rather than a big
# number. Until 2026-08-13 this said 100 - the schema maximum, which reads like
# "off" and is not. The detector was finding 2030 zones per series and returning
# 200, the newest, so every number in docs/CALIBRATION.md was computed on the
# last 10% of each series while claiming 20,000 bars. That is the same display
# cap that had already flattened three earlier measurements, caught a fourth
# time, and it is the reason the cap can now be switched off outright.
POPULATION = dict(
    merge_overlap_pct=1.0, max_zones_per_side=0, show_broken=True, departure_min_atr=0.0
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
    nested: bool = False  # sits inside a higher-timeframe zone of the same side


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
    reward: float,
    horizon: int,
    label: str,
    interval: str = "",
    mode: str = "atr",
) -> Dataset:
    zones, _ = detect(candles, params)

    # Stamp higher-timeframe nesting so it can be measured alongside everything
    # else. The step up is 4x, which sits in the middle of the 3x to 12x band
    # practitioners actually use, and matters only in that it must be the same
    # for every series or the cohorts are not comparable.
    step_up = {"15m": "1h", "1h": "4h", "4h": "1d"}.get(interval)
    if step_up:
        higher_bars = resample(candles, step_up, interval)
        if len(higher_bars) >= params.atr_period + 3:
            higher_zones, _ = detect(higher_bars, params)
            for hz in higher_zones:
                hz.timeframe = step_up
            mark_nesting(zones, higher_zones)
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

        scored = score_as_of(zone, high, low, atr, touch, params, zones, candles)
        if scored is None:
            continue  # no measurable leg-out before the touch

        outcome = resolve(zone, high, low, close, atr, touch, reward, horizon, mode)
        if outcome is None:
            continue  # neither side of the bracket reached inside the horizon

        strength, factors, departure = scored
        observation = Observation(
            zone.side.value, zone.kind.value, touch, outcome, factors, strength,
            departure, bool(zone.nested_in),
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
                placebo, high, low, close, atr, p_touch, reward, horizon, mode
            )
            if p_outcome is not None:
                data.placebo.append(
                    Observation(
                        zone.side.value, zone.kind.value, p_touch, p_outcome,
                        factors, strength, departure, bool(zone.nested_in),
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
    all_zones: list[Zone],
    candles: list[Candle],
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
    # The doctrine's 1:3 rule, recomputed as of the touch for the same reason
    # departure is: the finished chart's value knows more than the trader did.
    height = max(zone.top - zone.bottom, 1e-9)
    profit_margin = max(0.0, excursion) / height

    # The shipped factors are all fixed at formation, so they need no
    # adjustment. Departure is returned separately: it is the gate's input and
    # the bucket table's x-axis, and deliberately no longer part of the score.
    factors = dict(zone.factors)
    formation = round(float(np.clip(sum(factors.values()), 0.0, 1.0)), 4)

    # Candidates under evaluation, measured but NOT in the composite. The
    # visual audit found bases that were slow staircases rather than pauses;
    # these two say how much, and the AUC table says whether it matters.
    factors["base_drift"] = zone.base_drift
    factors["base_overlap"] = zone.base_overlap
    factors["profit_margin"] = min(profit_margin, 20.0)  # capped so one outlier cannot dominate a rank

    # Curve is causal by construction: the detector reads only bars before the
    # base, so this is already the as-of value.
    factors["curve_position"] = zone.curve
    factors["curve_favourable"] = float(zone.curve_favourable)

    # Arrival is recorded AT the first touch, which is exactly the decision
    # moment, so it needs no adjustment either.
    factors["arrival_atr"] = min(zone.arrival_atr or 0.0, 10.0)

    # The profit zone does NOT come for free. The shipped value is computed
    # against the last bar and therefore knows about opposing zones that formed
    # after the touch. Recompute it against what stood in the way at the time.
    forward = profit_zone_at(zone, all_zones, candles[touch].time)
    # `None` means NO opposing zone stands in the way, which is the longest road
    # there is, not the shortest. Folding it to 0.0 - which `or` does silently -
    # ranks a completely clear road below a wall sitting on the entry, i.e. it
    # inverts the best case into the worst one. Capped rather than infinite so a
    # single unbounded value cannot dominate a rank statistic.
    factors["profit_zone_rr"] = 30.0 if forward is None else min(forward, 30.0)
    factors["road_is_clear"] = float(forward is None)

    # The zone's own height, and it is here as a SUSPECT rather than as a
    # candidate. The outcome is a bracket whose target is `reward` ATR from the
    # proximal but whose stop is the distal, i.e. the zone's own height. So the
    # risk leg varies from zone to zone while the reward leg does not, and a
    # short zone is graded on a tighter bracket than a tall one. If height
    # predicts `held`, then every factor correlated with height inherits that
    # prediction for free and none of them is telling us anything about supply
    # or demand. `tightness` is almost the negative of this number by
    # construction, and it reads inverted.
    factors["zone_height_atr"] = min(height / atr_base, 10.0)

    # --- aspects nothing here had looked at yet -------------------------------
    # All four are knowable strictly before the touch bar closes, which is the
    # only bar on which any of this is actionable.
    base_from = zone.anatomy.base_from

    # How long the zone waited. The doctrine says a level decays with age and
    # never says how fast, so it is measured rather than assumed. Capped because
    # a handful of zones wait thousands of bars and would own the rank.
    factors["age_bars"] = float(min(touch - zone.anatomy.leg_out_to, 500))

    # Hour of the session the touch landed in. Reported in the per-hour table
    # rather than ranked: an AUC on a CYCLIC variable is meaningless, because
    # the rank statistic puts hour 23 and hour 0 at opposite ends when they are
    # adjacent. Ranked, it read 0.540 to 0.545 and looked like a finding.
    factors["_touch_hour"] = float((candles[touch].time // 3600) % 24)

    # Volatility at formation against the 200 bars before it. A zone born in a
    # quiet stretch and touched in a violent one is a different object from one
    # born and touched in the same regime, and nothing so far separates them.
    prior = atr[max(0, base_from - 200) : base_from]
    factors["vol_regime"] = (
        min(atr_base / float(prior.mean()), 5.0)
        if len(prior) and prior.mean() > 0 else 1.0
    )

    # A trend proxy, and the framing matters. docs/FIDELITY.md refuses to
    # implement the doctrine's "big picture" enhancer because the doctrine never
    # defines how to measure trend, and inventing one and calling it doctrine
    # would be borrowing authority. This is not that: it is ONE explicitly
    # stated proxy - where price sat relative to 200 bars earlier, in ATR, at
    # the moment the zone formed - measured so the result can be reported as a
    # fact about this proxy and nothing more.
    back = max(0, base_from - 200)
    drift = candles[base_from].close - candles[back].close
    signed = drift if zone.side is ZoneSide.DEMAND else -drift
    factors["with_trend_atr"] = float(np.clip(signed / atr_base, -10.0, 10.0))

    return formation, factors, departure


def resolve(
    zone: Zone,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    touch: int,
    reward: float,
    horizon: int,
    mode: str = "atr",
) -> bool | None:
    """Held or failed, from the touch bar forward.

    Two ways to place the target, and they answer different questions.

    `atr`  the target sits `reward` ATR from the proximal while the stop sits at
           the distal. The reward leg is therefore the same for every zone and
           the risk leg is not, so a tall zone is graded on an easier bracket.
           Measured, that is worth nine points of hold rate between the shortest
           and tallest quartile - which means any factor correlated with zone
           height predicts for free.

    `r`    the target sits `reward` ZONE HEIGHTS from the proximal. Now both
           legs scale together and every zone is graded at the same
           reward-to-risk, so a difference between two zones cannot be their
           geometry. This is the mode to read factor rankings in.

    Neither is more correct in the abstract. `atr` asks "does price travel a
    fixed distance", which is what a trader with a fixed target wants; `r` asks
    "does this zone beat that zone", which is what a ranking needs. Running both
    is the only way to tell an effect apart from the bracket.

    When a single bar reaches both the target and the stop, it is scored as a
    failure. Bar data cannot say which came first, and guessing in the
    favourable direction is how backtests flatter themselves.
    """
    unit = (
        float(atr[touch]) if mode == "atr" else abs(zone.proximal - zone.distal)
    )
    if unit <= 0:
        return None

    demand = zone.side is ZoneSide.DEMAND
    target = (
        zone.proximal + reward * unit if demand else zone.proximal - reward * unit
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


def report(datasets: list[Dataset], reward: float, horizon: int, mode: str) -> dict:
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

    out: dict = {
        "n": len(real),
        "base_rate": base,
        "placebo_rate": float(p_labels.mean()) if len(p_labels) else None,
        "rejected_rate": float(r_labels.mean()) if len(r_labels) else None,
        "rejected_n": len(r_labels),
        "gate_test": _two_proportion(labels, r_labels) if len(r_labels) else None,
        "factors": {},
    }

    print(f"\n{'=' * 78}")
    unit = "ATR" if mode == "atr" else "x the zone's own height (equal R for every zone)"
    print(f"REWARD {reward} {unit}, HORIZON {horizon} bars")
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

    # The one multi-timeframe rule every school agrees on, and one the published
    # record never puts a number to. Both cohorts are drawn zones from the same
    # detector on the same bars; the only difference is whether a
    # higher-timeframe zone of the same side already enclosed them.
    nested = np.array([o.held for o in real if o.nested])
    alone = np.array([o.held for o in real if not o.nested])
    if len(nested) and len(alone):
        print(
            f"\n  nested in an HTF zone   n={len(nested):<4} held={nested.mean():.1%}"
            f"\n  standing alone          n={len(alone):<4} held={alone.mean():.1%}"
            f"\n  difference              {nested.mean() - alone.mean():+.1%}"
            f"   {_two_proportion(nested, alone)}"
        )
        out["nesting"] = {
            "nested_n": len(nested),
            "nested_held": float(nested.mean()),
            "alone_n": len(alone),
            "alone_held": float(alone.mean()),
            "test": _two_proportion(nested, alone),
        }

    # An AUC needs both classes to mean anything. At tight geometries the hold
    # rate is so high that a handful of failures carry every negative, and the
    # bootstrap happily reports a narrow interval around a number computed from
    # five points. Printing the minority count next to the table is the only
    # thing that stops that being read as a result.
    minority = int(min(labels.sum(), (~labels).sum()))
    warning = "  <- TOO FEW TO RANK ON" if minority < 30 else ""
    print(f"\n  smaller class: {minority} of {len(real)}{warning}")

    # Session, as a table rather than a rank. Six four-hour blocks so each has
    # enough zones to mean anything.
    hours = np.array([o.factors["_touch_hour"] for o in real])
    print("\n  touch session (UTC)   n     held    vs base")
    sessions = []
    for start in range(0, 24, 4):
        pick = (hours >= start) & (hours < start + 4)
        if pick.sum() < 30:
            continue
        rate = float(labels[pick].mean())
        print(f"  {start:02d}:00 to {start + 4:02d}:00      {pick.sum():>5}   {rate:>6.1%}   {rate - base:+.1%}")
        sessions.append({"from": start, "n": int(pick.sum()), "held": rate})
    out["sessions"] = sessions

    print(f"\n  {'factor':<14}{'AUC':>8}{'95% CI':>18}   reading")
    # Leading underscore marks a value carried for a table rather than for the
    # rank test, so it never silently becomes a "finding".
    factor_names = [n for n in real[0].factors if not n.startswith("_")]
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
        if minority < 30:
            verdict = "unusable, minority class too small"
        elif lo > 0.5:
            verdict = "discriminates"
        elif hi < 0.5:
            verdict = "inverted"
        else:
            verdict = "indistinguishable"
        print(f"  {name:<14}{value:>8.3f}{f'[{lo:.3f}, {hi:.3f}]':>18}   {verdict}")
        out["factors"][name] = {"auc": value, "ci": [lo, hi], "verdict": verdict}

    # Is departure a threshold or a gradient? The gate treats it as a
    # threshold while the score treats it as a gradient, and only one of those
    # can be right. Bucketed over the FULL population, rejected included.
    everything = rejected + real
    if everything:
        held_all = np.array([o.held for o in everything])
        # An AUC is a rank test and is blind to a pure threshold: departure
        # turned out to climb to 2 ATR and then go flat, which an AUC near 0.5
        # cannot distinguish from "no effect at all". Bucketing shows the shape.
        for name, values, edges, note in (
            (
                "departure (ATR)",
                np.array([o.departure for o in everything]),
                [0, 1, 2, 3, 4, 5, 99],
                f"gate sits at {SHIPPED_GATE}",
            ),
            (
                "profit margin (x zone)",
                np.array([o.factors["profit_margin"] for o in everything]),
                [0, 1, 2, 3, 4, 6, 99],
                "doctrine asks for 3",
            ),
            (
                "profit zone (x zone)",
                np.array([o.factors["profit_zone_rr"] for o in everything]),
                [0, 1, 2, 3, 4, 6, 30.01],
                "road ahead; 30 is 'no wall at all'",
            ),
        ):
            print(f"\n  {name:<22}  n     held     <- {note}")
            buckets = []
            for lo_e, hi_e in zip(edges, edges[1:]):
                pick = (values >= lo_e) & (values < hi_e)
                if pick.sum() < 10:
                    continue
                print(f"  {lo_e:>3} to {hi_e:<3}          {pick.sum():>5}   {held_all[pick].mean():>6.1%}")
                buckets.append(
                    {"from": lo_e, "to": hi_e, "n": int(pick.sum()),
                     "held": float(held_all[pick].mean())}
                )
            out[f"{name.split()[0]}_buckets"] = buckets

    # Curve, split by side. This is the check that tells a real curve effect
    # apart from a trend artefact, and without it the raw AUC is unreadable.
    #
    # The doctrine says demand is strong LOW in the range and supply strong
    # HIGH, so a genuine curve effect must point in OPPOSITE raw directions for
    # the two sides: AUC below 0.5 for demand, above 0.5 for supply. If both
    # sides point the same way, the variable is tracking drift in a trending
    # sample and has nothing to do with the curve.
    #
    # `profit_zone_rr` needs the same split for the opposite reason, and getting
    # the expectation backwards would be easy. A long road for DEMAND means no
    # supply above it, which on a rising sample is simply "price is at its
    # highs" - a description of the drift. A long road for SUPPLY means no
    # demand below, which is the opposite location. So a mechanical road effect
    # must show up as high-is-better on BOTH sides; a drift artefact shows up on
    # one side and dies or inverts on the other.
    for factor, expectation in (
        ("curve_position", "opposed"),
        ("profit_zone_rr", "same"),
    ):
        print(f"\n  {factor} by side   n     AUC    reading")
        sides = {}
        for side in ("demand", "supply"):
            picked = [o for o in real if o.side == side]
            if len(picked) < 30:
                print(f"  {side:<18}{len(picked):>5}      -    too few")
                continue
            values = np.array([o.factors[factor] for o in picked])
            marks = np.array([o.held for o in picked])
            if values.std() < 1e-12 or marks.all() or not marks.any():
                print(f"  {side:<18}{len(picked):>5}      -    no contrast")
                continue
            value = auc(values, marks)
            lo, hi = bootstrap_auc(values, marks)
            sides[side] = value
            if factor == "curve_position":
                want = "low is better" if side == "demand" else "high is better"
            else:
                want = "high is better"
            got = "low is better" if value < 0.5 else "high is better"
            clean = "CI clear of 0.5" if lo > 0.5 or hi < 0.5 else "CI crosses 0.5"
            print(
                f"  {side:<18}{len(picked):>5}  {value:>6.3f}   {got}, wanted {want}"
                f"   [{lo:.3f}, {hi:.3f}] {clean}"
            )
        if len(sides) == 2:
            opposed = (sides["demand"] - 0.5) * (sides["supply"] - 0.5) < 0
            if expectation == "opposed":
                print(
                    "  -> sides point in opposite directions, consistent with a real effect"
                    if opposed
                    else "  -> BOTH SIDES POINT THE SAME WAY: this is drift, not the curve"
                )
                verdict = opposed
            else:
                both_up = sides["demand"] > 0.5 and sides["supply"] > 0.5
                print(
                    "  -> both sides say a longer road is better, which drift alone"
                    " cannot produce"
                    if both_up
                    else "  -> ONE SIDE CARRIES IT: consistent with drift, not with the road"
                )
                verdict = both_up
            out[f"{factor}_by_side"] = {**sides, "as_expected": bool(verdict)}
    curve_sides = out.get("curve_position_by_side", {})
    out["curve_by_side"] = curve_sides  # kept: docs/CALIBRATION.md cites this key

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

    # THE STOP-DISTANCE CONFOUND, and the check every other AUC on this page
    # depends on. The outcome is a bracket whose reward leg is `reward` ATR from
    # the proximal but whose risk leg is the zone's own height, so zones are not
    # graded on the same bracket as each other: a tall zone has a distant stop
    # and is harder to break for reasons of geometry alone.
    #
    # `zone_height_atr` measures that directly. If it predicts, then anything
    # correlated with height predicts too, for free, and says nothing about
    # supply or demand. `tightness` is nearly the negative of height by
    # construction and reads inverted, which is what a pure artefact looks like.
    heights = np.array([o.factors["zone_height_atr"] for o in real])
    if heights.std() > 1e-12:
        print("\n  stop-distance confound")
        edges = np.quantile(heights, [0, 0.25, 0.5, 0.75, 1.0])
        print("  {'zone height':<20}{'n':>7}{'held':>9}   <- taller means a further stop")
        for i in range(4):
            lo_e, hi_e = edges[i], edges[i + 1]
            pick = (heights >= lo_e) & (heights <= hi_e if i == 3 else heights < hi_e)
            if pick.sum() < 30:
                continue
            print(f"  {f'{lo_e:.2f} to {hi_e:.2f} ATR':<20}{pick.sum():>7}{labels[pick].mean():>9.1%}")

        # And the question that decides whether the road finding survives:
        # does it still rank INSIDE a band of equal stop distance? Note which
        # way this one can only cut. profit_zone_rr is gap divided by height, so
        # a short zone inflates it while ALSO holding less often - the confound
        # pushes this factor's apparent effect DOWN, not up.
        # Two stratifiers, because two different mechanisms can manufacture a
        # ranking here and they need separating.
        #
        # `departure` is the second, and the mechanism is subtle enough to be
        # worth spelling out. It is measured from the leg-out up to the TOUCH,
        # so a zone price returned to after two bars has its departure measured
        # over two bars and is small by arithmetic rather than by weakness. That
        # ties `age_bars` to `departure` by construction, and a factor that only
        # ranks across departure bands is re-running the gate under a new name.
        for stratifier, values_of in (
            ("height", heights),
            ("departure", np.array([o.departure for o in real])),
        ):
            bands = np.quantile(values_of, [0, 0.25, 0.5, 0.75, 1.0])
            print(f"\n  {'factor':<16}{'AUC overall':>13}   AUC within each {stratifier} quartile")
            confounded = {}
            for name in (
                "profit_zone_rr", "age_bars", "tightness", "zone_height_atr"
            ):
                values = np.array([o.factors[name] for o in real])
                if values.std() < 1e-12:
                    continue
                inner = []
                for i in range(4):
                    lo_e, hi_e = bands[i], bands[i + 1]
                    pick = (values_of >= lo_e) & (
                        values_of <= hi_e if i == 3 else values_of < hi_e
                    )
                    marks = labels[pick]
                    if pick.sum() < 60 or marks.all() or not marks.any():
                        inner.append(float("nan"))
                        continue
                    inner.append(auc(values[pick], marks))
                shown = "  ".join("  -  " if np.isnan(v) else f"{v:.3f}" for v in inner)
                print(f"  {name:<16}{auc(values, labels):>13.3f}   {shown}")
                confounded[name] = inner
            out[f"within_{stratifier}_quartiles"] = confounded
        print(
            "  -> a factor that only ranks ACROSS bands and not inside them was"
            "\n     ranking the stratifier, not whatever it claims to measure."
        )

    # What a road gate would actually cost and buy, on DRAWN zones only. The
    # bucket table above mixes in the gate-rejected cohort and so answers a
    # different question; this one answers "if `min_profit_zone_rr` shipped at
    # this value, what changes on the chart the user is looking at".
    roads = np.array([o.factors["profit_zone_rr"] for o in real])
    print("\n  road gate      kept    held kept   held cut     test")
    gates = []
    for threshold in (0.5, 1.0, 1.5, 2.0, 3.0):
        keep = roads >= threshold
        if keep.sum() < 30 or (~keep).sum() < 30:
            continue
        print(
            f"  >= {threshold:<10.1f}{keep.mean():>6.1%}{labels[keep].mean():>11.1%}"
            f"{labels[~keep].mean():>11.1%}     {_two_proportion(labels[keep], labels[~keep])}"
        )
        gates.append({
            "threshold": threshold, "kept": float(keep.mean()),
            "held_kept": float(labels[keep].mean()),
            "held_cut": float(labels[~keep].mean()),
            "test": _two_proportion(labels[keep], labels[~keep]),
        })
    out["road_gates"] = gates

    # Decile lift on the composite. If the top decile does not beat the base
    # rate, the composite is not usable as a ranking however good its AUC.
    strengths = np.array([o.strength for o in real])
    print("\n  strength quintile   n     held      lift vs base")
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
    # Both bracket modes, every time. `atr` is the shipped question and `r`
    # is the one that holds every zone to the same reward-to-risk, and the pair
    # is the only way to tell a real effect from the bracket's own geometry.
    plan = [("atr", 0.5, 40), ("atr", 1.0, 40), ("atr", 2.0, 80),
            ("r", 1.0, 40), ("r", 2.0, 80), ("r", 3.0, 80)]
    for mode, reward, horizon in plan:
        datasets = [
            evaluate(candles, params, reward, horizon, f"{sym}-{tf}", tf, mode)
            for sym, tf, candles in loaded
        ]
        # Per series, so a pooled result that lives in one instrument cannot
        # hide inside the total. Same split the gate is judged on.
        for d in datasets:
            held = [o.held for o in d.real]
            cut = [o.held for o in d.rejected]
            gap = (np.mean(held) - np.mean(cut)) if held and cut else float("nan")
            print(
                f"  {d.label:<14} n={len(d.real):<5} held="
                f"{np.mean(held) if held else float('nan'):.1%}"
                f"   vs rejected {gap:+.1%}"
            )
        everything[f"{mode}{reward}_h{horizon}"] = report(
            datasets, reward, horizon, mode
        )

    cross_mode(everything)

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(everything, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


def cross_mode(everything: dict) -> None:
    """The sharpest test on this page, and it needs both brackets to exist.

    Zone height confounds BOTH modes, in OPPOSITE directions. Under an ATR
    target a tall zone has a distant stop and holds more often; under an equal-R
    target a tall zone needs price to travel a large absolute distance and holds
    less often. Measured: `zone_height_atr` scores 0.537 one way and 0.391 the
    other.

    So the modes disagree about height by construction, and that turns into a
    free diagnostic. **Any factor that is really height wearing another name
    must flip sign between the two modes. A factor that keeps its sign in both
    cannot be a height proxy**, because no single relationship with height can
    point the same way under two brackets that grade height oppositely.

    This is not a substitute for the within-height stratification; it is a
    second, independent route to the same question, and a factor that passes
    only one of them has not passed.
    """
    modes: dict[str, dict[str, list[float]]] = {"atr": {}, "r": {}}
    for key, value in everything.items():
        if not value or "factors" not in value:
            continue
        family = "atr" if key.startswith("atr") else "r"
        for name, stat in value["factors"].items():
            if stat.get("auc") is not None:
                modes[family].setdefault(name, []).append(stat["auc"])

    shared = sorted(set(modes["atr"]) & set(modes["r"]))
    if not shared:
        return

    print(f"\n{'=' * 78}")
    print("SAME FACTOR, TWO BRACKETS: which survive a change of geometry")
    print(f"{'=' * 78}")
    print("  Height is graded oppositely by the two modes, so a factor that is")
    print("  really height in disguise MUST flip. One that does not, is not.\n")
    print(f"  {'factor':<18}{'AUC, ATR target':>17}{'AUC, equal R':>15}   verdict")

    for name in shared:
        a = float(np.mean(modes["atr"][name]))
        b = float(np.mean(modes["r"][name]))
        flips = (a - 0.5) * (b - 0.5) < 0
        # "Weak in both" has to be tested BEFORE the flip, or a factor sitting
        # on 0.500 in one mode gets called a height proxy on the strength of
        # rounding noise. `base_drift` read 0.506 and 0.500 and was labelled a
        # height artefact by the first version of this table, which is a claim
        # about a variable that did nothing at all.
        if max(abs(a - 0.5), abs(b - 0.5)) <= 0.02:
            verdict = "no effect under either bracket"
        elif flips:
            verdict = "FLIPS: this is zone height, not a property of the zone"
        elif min(abs(a - 0.5), abs(b - 0.5)) > 0.02:
            verdict = "SURVIVES both brackets"
        else:
            verdict = "same sign but weak in one, unproven"
        print(f"  {name:<18}{a:>17.3f}{b:>15.3f}   {verdict}")
        everything.setdefault("cross_mode", {})[name] = {
            "atr": a, "r": b, "flips": bool(flips), "verdict": verdict
        }


if __name__ == "__main__":
    main()
