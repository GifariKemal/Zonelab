"""Is it really supply and demand? An event study around the first touch.

    python -m tools.reaction

`tools/calibrate.py` asks whether a bracket placed at the zone resolves
favourably. That is a question about an exit rule as much as about the zone. This
asks the prior question, and the one the name of the thing actually claims:
**when price arrives at the zone, does it turn?**

THE TRAP THIS WHOLE FILE IS BUILT AROUND
In a series that drifted upward, demand zones will "react upward" for no reason
at all. Every naive statistic here - mean move after the touch, win rate, path
asymmetry - reads that drift as evidence. The sample this project calibrates on
is crypto over a rising window, so the trap is not hypothetical, and one variable
(`curve_position`) has already been caught by it once.

The escape is the estimand, not a correction bolted on afterwards. Write the mean
post-touch move for each side as

    demand:  mu + delta_demand
    supply:  mu - delta_supply

where `mu` is whatever the market was doing anyway and `delta` is the zone
effect. Drift enters BOTH sides with the same sign; a real zone effect enters
with OPPOSITE signs. So the difference

    DELTA = mean(move | demand) - mean(move | supply)

cancels `mu` exactly, with no model of the drift and no assumption about it. That
is the headline number here. It is the same shape as a difference-in-differences
estimator, and it is the strongest evidence available from price data alone: no
common-mode confound can fake it. Anything that survives it has to be correlated
with the SIDE of the zone, which is a far narrower alternative than "the market
went up".

The per-side means are reported too, because a real detector has to satisfy the
stronger claim - each side pointing its own way against its own control - and not
merely the difference. A DELTA carried entirely by one side is a one-sided result
and is printed as one.

FOUR NULLS, NOT ONE
  drawn      the zones the engine ships
  placebo    same size, same side, same age, moved to a random PRICE  -> controls WHERE
  matched    same side, same count, at random TIMES                   -> controls WHEN
  rejected   real formations the departure gate threw out             -> controls the FILTER

`placebo` and `matched` are not redundant. A level in the wrong place and a level
at the wrong time fail differently, and drift is a `when` confound that a `where`
control cannot touch.

WHAT IS DELIBERATELY NOT CLAIMED
No costs, no spread, no slippage, no position sizing. A displacement is not a
trade. The horizon is fixed rather than chosen per event, because choosing it
from the path being measured is how a statistic reads its own answer.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

import numpy as np

from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.models import Candle, SupplyDemandParams, ZoneSide
from tools import history
from tools.calibrate import POPULATION, SHIPPED_GATE, first_touch, shift

PRE = 20  # bars of approach measured before the touch
POST = 40  # bars of reaction measured after it
RNG = np.random.default_rng(20260813)
PERMUTATIONS = 10_000


@dataclass
class Event:
    """One arrival at a level, and what price did on either side of it."""

    cohort: str
    side: str
    touch: int
    move: float  # raw post-touch displacement, UP-POSITIVE, in ATR
    turn: float  # slope after minus slope before, UP-POSITIVE, in ATR per bar
    path: np.ndarray  # displacement from the touch price, tau = -PRE..+POST


def collect(candles: list[Candle], params: SupplyDemandParams, label: str) -> list[Event]:
    """Every event in one series, across all four cohorts."""
    zones, _ = detect(candles, params)

    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)
    index_of = {c.time: i for i, c in enumerate(candles)}

    # Per-bar drift, estimated once over the whole series. It is subtracted from
    # every cohort alike, so it cannot create a difference between them; it is
    # here so the PER-SIDE numbers mean something on their own, which is exactly
    # where a raw mean would be unreadable.
    logs = np.diff(np.log(np.maximum(close, 1e-12)))
    drift = float(logs.mean()) if len(logs) else 0.0

    events: list[Event] = []
    for zone in zones:
        if zone.first_test_time is None:
            continue
        touch = index_of.get(zone.first_test_time)
        if touch is None or touch <= zone.anatomy.leg_out_to:
            continue

        # The gate is re-derived as of the touch, exactly as calibrate does it,
        # so the rejected cohort here is the same population as the one there.
        departure = _departure_as_of(zone, high, low, atr, touch, params)
        if departure is None:
            continue
        cohort = "drawn" if departure >= SHIPPED_GATE else "rejected"

        event = _measure(cohort, zone.side.value, touch, close, atr, drift)
        if event is not None:
            events.append(event)

        moved = shift(zone, float(atr[zone.anatomy.base_to]))
        p_touch = first_touch(moved, high, low, zone.anatomy.leg_out_to + 1)
        if p_touch is not None:
            placebo = _measure(
                "placebo", zone.side.value, p_touch, close, atr, drift
            )
            if placebo is not None:
                events.append(placebo)

    # `matched`: the same number of arrivals per side, at times drawn at random
    # from the same series. This is the control the placebo cannot be, because
    # moving a level to a random PRICE leaves it touched at a moment the market
    # chose, and drift is a property of the moment.
    for side in ("demand", "supply"):
        want = sum(1 for e in events if e.cohort == "drawn" and e.side == side)
        picked = RNG.integers(PRE + 1, max(PRE + 2, len(close) - POST - 1), want)
        for index in picked:
            control = _measure("matched", side, int(index), close, atr, drift)
            if control is not None:
                events.append(control)

    counted = {c: sum(1 for e in events if e.cohort == c) for c in COHORTS}
    print(f"  {label:<16} " + "  ".join(f"{c}={counted[c]}" for c in COHORTS))
    return events


COHORTS = ("drawn", "placebo", "matched", "rejected")


def _departure_as_of(zone, high, low, atr, touch, params) -> float | None:
    """The leg-out measured only up to the touch, never past it."""
    atr_base = float(atr[max(0, zone.anatomy.base_from - 1)])
    stop = min(zone.anatomy.leg_out_from + params.departure_lookahead, touch)
    if atr_base <= 0 or stop <= zone.anatomy.leg_out_from:
        return None
    window = slice(zone.anatomy.leg_out_from, stop)
    excursion = (
        float(high[window].max()) - zone.proximal
        if zone.side is ZoneSide.DEMAND
        else zone.proximal - float(low[window].min())
    )
    return max(0.0, excursion) / atr_base


def _measure(
    cohort: str,
    side: str,
    touch: int,
    close: np.ndarray,
    atr: np.ndarray,
    drift: float,
) -> Event | None:
    """Displacement and turn around one arrival, in units of PRE-touch ATR.

    The scale is read from `atr[touch - 1]`. Using `atr[touch]` would put the
    touch bar's own range into the denominator, and the touch bar is often the
    violent one - the measurement would shrink exactly where the reaction is
    biggest, which is a bias pointing at the answer.
    """
    if touch - PRE < 1 or touch + POST >= len(close):
        return None
    scale = float(atr[touch - 1])
    if scale <= 0:
        return None

    anchor = float(close[touch])
    expected = drift * anchor  # per bar, in price units

    path = (close[touch - PRE : touch + POST + 1] - anchor) / scale
    taus = np.arange(-PRE, POST + 1)
    path = path - (expected * taus) / scale  # drift removed along the whole path

    before = np.polyfit(taus[: PRE + 1], path[: PRE + 1], 1)[0]
    after = np.polyfit(taus[PRE:], path[PRE:], 1)[0]

    return Event(cohort, side, touch, float(path[-1]), float(after - before), path)


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------


def contrast(events: list[Event], field: str) -> float:
    """mean(demand) - mean(supply). Drift cancels; nothing else does."""
    demand = [getattr(e, field) for e in events if e.side == "demand"]
    supply = [getattr(e, field) for e in events if e.side == "supply"]
    if not demand or not supply:
        return float("nan")
    return float(np.mean(demand) - np.mean(supply))


def permutation_p(events: list[Event], field: str) -> float:
    """How often does relabelling the sides produce a contrast this large?

    The price paths are never touched, so every kind of dependence in them -
    autocorrelation, volatility clustering, the drift itself - is carried into
    the null unchanged. Only the thing under test is destroyed: which side of
    the market each arrival was supposed to be.
    """
    if len(events) < 20:
        return float("nan")
    values = np.array([getattr(e, field) for e in events])
    is_demand = np.array([e.side == "demand" for e in events])
    if is_demand.all() or not is_demand.any():
        return float("nan")

    observed = abs(values[is_demand].mean() - values[~is_demand].mean())
    hits = 0
    for _ in range(PERMUTATIONS):
        shuffled = RNG.permutation(is_demand)
        if abs(values[shuffled].mean() - values[~shuffled].mean()) >= observed:
            hits += 1
    # Add-one so a p of exactly zero is never reported from a finite number of
    # draws. With 10,000 permutations the floor is 1e-4, and claiming anything
    # smaller would be claiming precision the method does not have.
    return (hits + 1) / (PERMUTATIONS + 1)


def block_ci(events: list[Event], field: str, blocks: int = 20) -> tuple[float, float]:
    """Percentile CI from a moving-block bootstrap over event ORDER.

    Zones cluster: several form on one swing and are touched within a few bars
    of each other, so they are nowhere near independent draws. Resampling single
    events would treat them as if they were and return an interval far too
    narrow. Resampling contiguous blocks keeps neighbours together.
    """
    if len(events) < 40:
        return (float("nan"), float("nan"))
    ordered = sorted(events, key=lambda e: e.touch)
    values = np.array([getattr(e, field) for e in ordered])
    is_demand = np.array([e.side == "demand" for e in ordered])

    n = len(ordered)
    size = max(2, n // blocks)
    count = -(-n // size)  # blocks needed to cover the sample
    starts = np.arange(0, n - size + 1)
    offsets = np.arange(size)

    # One vectorised draw per row: pick `count` block starts, expand each into
    # its bar indices, then trim back to the original length.
    picks = RNG.choice(starts, size=(2000, count))
    index = (picks[:, :, None] + offsets[None, None, :]).reshape(2000, -1)[:, :n]

    taken, demand = values[index], is_demand[index]
    counts = demand.sum(axis=1)
    usable = (counts > 0) & (counts < n)
    if not usable.any():
        return (float("nan"), float("nan"))

    hi_sum = np.where(demand, taken, 0.0).sum(axis=1)
    lo_sum = np.where(demand, 0.0, taken).sum(axis=1)
    draws = (hi_sum / np.maximum(counts, 1)) - (lo_sum / np.maximum(n - counts, 1))
    draws = draws[usable]
    return (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)))


def signed(events: list[Event], field: str) -> np.ndarray:
    """The value flipped so that "the zone worked" is positive on both sides.

    Safe to average ACROSS sides only while the two counts are close, because
    the drift that cancels in `contrast` merely shrinks here, in proportion to
    how unbalanced the cohort is. The imbalance is printed next to every use.
    """
    return np.array(
        [getattr(e, field) * (1.0 if e.side == "demand" else -1.0) for e in events]
    )


def cohort_p(a: list[Event], b: list[Event], field: str) -> float:
    """Permutation test on the difference of two cohorts' signed means."""
    x, y = signed(a, field), signed(b, field)
    if len(x) < 20 or len(y) < 20:
        return float("nan")
    pool = np.concatenate([x, y])
    observed = abs(x.mean() - y.mean())
    hits = 0
    for _ in range(PERMUTATIONS):
        picked = RNG.permutation(pool)
        if abs(picked[: len(x)].mean() - picked[len(x) :].mean()) >= observed:
            hits += 1
    return (hits + 1) / (PERMUTATIONS + 1)


def _cohort_table(events: list[Event], field: str, out: dict) -> None:
    """Drawn against each control, on the signed statistic.

    The per-side table answers "do the two sides behave differently". This one
    answers the question that actually decides whether the DETECTOR earns its
    place: does a drawn zone behave differently from a formation the gate threw
    away, on the same bars, measured the same way. That is the hard control, and
    it is the one `tools/calibrate.py` already found the gate passing on a
    different metric.
    """
    drawn = [e for e in events if e.cohort == "drawn"]
    if len(drawn) < 20:
        return
    base = signed(drawn, field)
    balance = sum(1 for e in drawn if e.side == "demand") / len(drawn)
    print(
        f"\n  {field} against each control, signed so positive = the zone worked"
        f"   (drawn is {balance:.0%} demand)"
    )
    print(f"  {'cohort':<10}{'n':>6}{'signed mean':>14}{'vs drawn':>11}{'p':>9}")
    print(f"  {'drawn':<10}{len(base):>6}{base.mean():>14.4f}{'-':>11}{'-':>9}")
    out.setdefault(f"{field}_cohorts", {})["drawn"] = {
        "n": len(base), "signed_mean": float(base.mean()), "demand_share": balance
    }
    for cohort in ("placebo", "matched", "rejected"):
        other = [e for e in events if e.cohort == cohort]
        if len(other) < 20:
            continue
        values = signed(other, field)
        p = cohort_p(drawn, other, field)
        print(
            f"  {cohort:<10}{len(values):>6}{values.mean():>14.4f}"
            f"{base.mean() - values.mean():>+11.4f}{p:>9.4f}"
        )
        out[f"{field}_cohorts"][cohort] = {
            "n": len(values), "signed_mean": float(values.mean()),
            "vs_drawn": float(base.mean() - values.mean()), "p": p,
        }


def report(events: list[Event]) -> dict:
    out: dict = {}
    print(f"\n{'=' * 78}")
    print(f"REACTION AT THE FIRST TOUCH   pre {PRE} bars, post {POST} bars")
    print(f"{'=' * 78}")
    print("  Displacement and turn are UP-POSITIVE and measured in ATR, so a")
    print("  working detector wants demand POSITIVE and supply NEGATIVE.\n")

    for field, unit in (("move", "ATR"), ("turn", "ATR/bar")):
        print(f"  {field} ({unit})")
        print(f"  {'cohort':<10}{'n dem':>7}{'mean dem':>11}{'n sup':>7}{'mean sup':>11}{'DELTA':>10}   verdict")
        out[field] = {}
        for cohort in COHORTS:
            picked = [e for e in events if e.cohort == cohort]
            demand = [getattr(e, field) for e in picked if e.side == "demand"]
            supply = [getattr(e, field) for e in picked if e.side == "supply"]
            if len(demand) < 10 or len(supply) < 10:
                print(f"  {cohort:<10}{len(demand):>7}{'-':>11}{len(supply):>7}{'-':>11}{'-':>10}   too few")
                continue
            delta = float(np.mean(demand) - np.mean(supply))
            p = permutation_p(picked, field)
            lo, hi = block_ci(picked, field)
            # The pre-registered reading, stated as a rule rather than chosen
            # after seeing the numbers: a real effect needs the difference to
            # clear chance AND each side to point its own way.
            if np.isnan(p) or p >= 0.05:
                verdict = "no difference between the sides"
            elif np.mean(demand) > 0 > np.mean(supply):
                verdict = "SEPARATES, and both sides point the right way"
            elif np.mean(demand) < 0 < np.mean(supply):
                verdict = "separates BACKWARDS: both sides point the wrong way"
            else:
                verdict = "separates, but one side carries it"
            print(
                f"  {cohort:<10}{len(demand):>7}{np.mean(demand):>11.3f}"
                f"{len(supply):>7}{np.mean(supply):>11.3f}{delta:>10.3f}   {verdict}"
            )
            print(f"  {'':<10}p={p:.4f}  95% CI [{lo:.3f}, {hi:.3f}]")
            out[field][cohort] = {
                "n_demand": len(demand), "n_supply": len(supply),
                "mean_demand": float(np.mean(demand)),
                "mean_supply": float(np.mean(supply)),
                "delta": delta, "p": p, "ci": [lo, hi], "verdict": verdict,
            }
        _cohort_table(events, field, out)

    # The shape is the evidence. A zone that works turns price AT the touch; a
    # number that is really drift slopes straight through tau = 0 without
    # noticing it happened.
    print(f"\n  Average path, drawn zones, displacement from the touch price in ATR")
    print(f"  {'tau':>6}{'demand':>10}{'supply':>10}{'DELTA':>10}")
    drawn = [e for e in events if e.cohort == "drawn"]
    profile = []
    if drawn:
        demand = np.array([e.path for e in drawn if e.side == "demand"])
        supply = np.array([e.path for e in drawn if e.side == "supply"])
        if len(demand) and len(supply):
            for tau in (-PRE, -10, -5, -1, 0, 1, 5, 10, 20, POST):
                i = tau + PRE
                d, s = float(demand[:, i].mean()), float(supply[:, i].mean())
                print(f"  {tau:>6}{d:>10.3f}{s:>10.3f}{d - s:>10.3f}")
                profile.append({"tau": tau, "demand": d, "supply": s, "delta": d - s})
    out["profile"] = profile

    print(
        "\n  Reading: a DELTA that is already large at tau = -1 was there before"
        "\n  the touch and is approach, not reaction. What the zone can claim is"
        "\n  the part that OPENS after tau = 0."
    )

    # Every p above came out of the same run, so reading the smallest one at
    # face value is picking the winner out of a field and then reporting its
    # margin. Bonferroni is crude - these tests are correlated, so it is
    # conservative - but a stated crude correction beats an unstated none.
    trials = 2 * (len(COHORTS) + 3)  # side contrast + cohort comparison, per field
    print(
        f"\n  {trials} tests were run here. A p below {0.05 / trials:.4f} survives"
        f"\n  Bonferroni at 0.05; anything between that and 0.05 is suggestive only."
    )
    out["trials"] = trials
    out["bonferroni_alpha"] = 0.05 / trials

    # The floor, stated as a number so that "we found nothing" is a measurement
    # rather than an admission. n per arm ~ 16 / d^2 at 80% power.
    smallest = min(
        (len([e for e in events if e.cohort == c]) for c in COHORTS), default=0
    )
    if smallest:
        print(
            f"  Smallest cohort is {smallest}. At 80% power that resolves an effect"
            f"\n  of about {np.sqrt(16 / smallest):.2f} standard deviations and nothing finer."
        )
        out["detectable_d"] = float(np.sqrt(16 / smallest))
    return out


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
    events: list[Event] = []
    for symbol, interval in series:
        candles = history.load(symbol, interval, args.bars)
        events.extend(collect(candles, params, f"{symbol}-{interval}"))

    out = report(events)
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
