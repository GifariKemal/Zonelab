"""Does a zone get worse each time price tests it?

    python -m tools.touches

The doctrine's freshness claim, and the largest documented gap in this project's
measurements: everything else here stops at the FIRST touch, so "a fresh zone
beats a tested one" has never been checked. It is also the claim most often
stated as settled.

THE TRAP, AND IT IS THE WHOLE DIFFICULTY
A zone that breaks on its first touch has no second touch. So the set of zones
reaching touch 2 is selected on having survived touch 1, and the set reaching
touch 3 on having survived twice. Comparing "hold rate at touch 1" against "hold
rate at touch 2" across all zones therefore compares two different populations
and can show a decay that is pure selection, or hide a real one.

Three views, and only the second and third are safe to read as evidence:

  UNCONDITIONAL   hold rate by touch number over every zone that got that far.
                  Printed because it is what everyone quotes, and labelled as
                  selected so it cannot be quoted from here innocently.

  PAIRED          among zones that reached touch 2, the SAME zones at touch 1
                  and at touch 2. One population, two occasions, McNemar on the
                  pairs that disagreed. This is the comparison the claim
                  actually makes.

  HAZARD          P(this touch is the one that breaks it | it survived to here).
                  A decay claim is a claim about this curve, and it is defined
                  on the survivors by construction rather than in spite of it.

A touch is one visit, not one bar: consecutive bars sitting inside the zone are
the same test. That definition is the shipped one, and the published sources are
vague enough that any choice here has to be stated rather than assumed.
"""

from __future__ import annotations

import argparse
import json
from math import comb

import numpy as np

from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.models import Candle, SupplyDemandParams, Zone, ZoneSide
from tools import history
from tools.calibrate import POPULATION, SHIPPED_GATE, resolve

MAX_TOUCH = 5  # beyond this the counts stop meaning anything


def visits(
    zone: Zone, high: np.ndarray, low: np.ndarray, close: np.ndarray
) -> list[int]:
    """Bar index of every distinct visit, until the zone dies."""
    is_demand = zone.side is ZoneSide.DEMAND
    out: list[int] = []
    inside_before = False
    for i in range(zone.anatomy.leg_out_to + 1, len(close)):
        if close[i] < zone.distal if is_demand else close[i] > zone.distal:
            break  # a close beyond the distal ends the zone, and the visits
        inside = low[i] <= zone.top and high[i] >= zone.bottom
        if inside and not inside_before:
            out.append(i)
        inside_before = inside
    return out


def collect(
    candles: list[Candle],
    params: SupplyDemandParams,
    reward: float,
    horizon: int,
    mode: str,
) -> list[list[bool]]:
    """One list of per-touch outcomes per zone, in order."""
    zones, _ = detect(candles, params)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)

    out = []
    for zone in zones:
        # Only zones the shipped gate would have kept. Freshness is a claim
        # about the zones a trader is looking at, not about the ones already
        # filtered away, and mixing the two would answer a question nobody asked.
        atr_base = float(atr[max(0, zone.anatomy.base_from - 1)])
        if atr_base <= 0 or zone.departure_atr < SHIPPED_GATE:
            continue

        sequence = []
        for touch in visits(zone, high, low, close)[:MAX_TOUCH]:
            outcome = resolve(
                zone, high, low, close, atr, touch, reward, horizon, mode
            )
            if outcome is None:
                break  # unresolved inside the horizon; the rest would be too
            sequence.append(outcome)
        if sequence:
            out.append(sequence)
    return out


def collect_distal_free(
    candles: list[Candle],
    params: SupplyDemandParams,
    reward: float,
    horizon: int,
) -> list[list[bool]]:
    """The same touches, scored WITHOUT reference to the zone's own death.

    This exists because the obvious measurement is a tautology waiting to
    happen. `resolve` fails a touch when a bar closes past the DISTAL, and the
    distal is also what ends the zone - so the last touch before a zone dies is
    guaranteed to score as a failure, and "later touches fail more often" partly
    restates "the touch nearest the death is the one that dies".

    Here the outcome is only: did price travel `reward` units away from the
    proximal, in the zone's own direction, within `horizon` bars. No stop, no
    distal, no reference to the zone surviving. A decay that survives this is a
    decay in what price DOES at the level, not an artefact of how the level's
    death was defined.
    """
    zones, _ = detect(candles, params)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)

    out = []
    for zone in zones:
        if zone.departure_atr < SHIPPED_GATE:
            continue
        is_demand = zone.side is ZoneSide.DEMAND
        sequence = []
        for touch in visits(zone, high, low, close)[:MAX_TOUCH]:
            unit = float(atr[touch])
            if unit <= 0 or touch + horizon >= len(close):
                break
            target = (
                zone.proximal + reward * unit if is_demand
                else zone.proximal - reward * unit
            )
            window = slice(touch, touch + horizon)
            reached = (
                bool(high[window].max() >= target) if is_demand
                else bool(low[window].min() <= target)
            )
            sequence.append((reached, touch - zone.anatomy.leg_out_to))
        if sequence:
            out.append(sequence)
    return out


def by_age(aged: list[list[tuple[bool, int]]]) -> None:
    """Touch number against zone AGE, because the two are confounded.

    The published literature measures level decay in TIME (Chung and Bellotti
    2021 fit it against elapsed time; Osler's levels persist for days). Retail
    supply and demand measures it in TOUCHES. In any real series the two move
    together - the fifth touch happens later than the first - so a naive
    touch-decay table reports time decay wearing a touch label.

    The split below is the whole test. If touch number still separates INSIDE a
    band of equal age, it is the touching that costs something. If the columns
    go flat, this was the clock all along.
    """
    flat = [(ok, age, k + 1) for seq in aged for k, (ok, age) in enumerate(seq)]
    ages = np.array([a for _, a, _ in flat])
    if not len(ages):
        return
    edges = np.quantile(ages, [0, 1 / 3, 2 / 3, 1.0])

    print("\n  SUCCESS RATE BY TOUCH NUMBER, INSIDE BANDS OF EQUAL AGE")
    print(f"  {'age at touch':<22}" + "".join(f"{f'touch {k}':>11}" for k in (1, 2, 3)))
    for i in range(3):
        lo, hi = edges[i], edges[i + 1]
        cells, counts = [], []
        for k in (1, 2, 3):
            picked = [
                ok for ok, a, kk in flat
                if kk == k and lo <= a and (a <= hi if i == 2 else a < hi)
            ]
            cells.append(float(np.mean(picked)) if len(picked) >= 40 else float("nan"))
            counts.append(len(picked))
        shown = "".join("      -    " if np.isnan(c) else f"{c:>11.1%}" for c in cells)
        print(f"  {f'{int(lo)} to {int(hi)} bars':<22}{shown}   n={counts}")


def mcnemar(pairs: list[tuple[bool, bool]]) -> tuple[int, int, float]:
    """Exact paired test on the occasions the two touches disagreed."""
    only_first = sum(1 for a, b in pairs if a and not b)
    only_later = sum(1 for a, b in pairs if b and not a)
    n = only_first + only_later
    if n == 0:
        return only_first, only_later, float("nan")
    k = max(only_first, only_later)
    tail = sum(comb(n, i) for i in range(k, n + 1)) / 2**n
    return only_first, only_later, min(1.0, 2 * tail)


def report(sequences: list[list[bool]], reward: float, horizon: int, mode: str) -> dict:
    if len(sequences) < 100:
        print(f"  only {len(sequences)} zones, refusing to report")
        return {}

    unit = {"atr": "ATR", "r": "x the zone's own height"}.get(
        mode, "ATR, NO STOP: reached the target or did not"
    )
    print(f"\n{'=' * 78}")
    print(f"TOUCH DECAY   reward {reward} {unit}, horizon {horizon} bars")
    print(f"{'=' * 78}")

    out: dict = {"zones": len(sequences)}

    # ---- unconditional, and labelled as the selected thing it is ------------
    print(f"\n  UNCONDITIONAL, and this population SHRINKS AND CHANGES each row")
    print(f"  {'touch':<8}{'n':>7}{'held':>9}")
    rows = []
    for k in range(MAX_TOUCH):
        at_k = [s[k] for s in sequences if len(s) > k]
        if len(at_k) < 30:
            continue
        rate = float(np.mean(at_k))
        print(f"  {k + 1:<8}{len(at_k):>7}{rate:>9.1%}")
        rows.append({"touch": k + 1, "n": len(at_k), "held": rate})
    out["unconditional"] = rows

    # ---- paired: the same zones, twice -------------------------------------
    print(f"\n  PAIRED, same zones at touch 1 and at touch k")
    print(f"  {'vs touch':<10}{'pairs':>7}{'touch 1':>10}{'touch k':>10}{'diff':>9}{'exact p':>10}")
    paired = []
    for k in range(1, MAX_TOUCH):
        pairs = [(s[0], s[k]) for s in sequences if len(s) > k]
        if len(pairs) < 40:
            continue
        first = float(np.mean([a for a, _ in pairs]))
        later = float(np.mean([b for _, b in pairs]))
        a_only, b_only, p = mcnemar(pairs)
        print(
            f"  {k + 1:<10}{len(pairs):>7}{first:>10.1%}{later:>10.1%}"
            f"{later - first:>+9.1%}{p:>10.4f}"
        )
        paired.append({
            "touch": k + 1, "pairs": len(pairs), "first": first, "later": later,
            "diff": later - first, "only_first": a_only, "only_later": b_only, "p": p,
        })
    out["paired"] = paired

    # ---- hazard -------------------------------------------------------------
    print(f"\n  HAZARD, share failing AT this touch given it reached it")
    print(f"  {'touch':<8}{'reached':>9}{'failed':>9}{'hazard':>9}")
    hazard = []
    for k in range(MAX_TOUCH):
        reached = [s for s in sequences if len(s) > k]
        if len(reached) < 30:
            continue
        failed = sum(1 for s in reached if not s[k])
        rate = failed / len(reached)
        print(f"  {k + 1:<8}{len(reached):>9}{failed:>9}{rate:>9.1%}")
        hazard.append({"touch": k + 1, "reached": len(reached), "failed": failed,
                       "hazard": rate})
    out["hazard"] = hazard

    print(
        "\n  Read the PAIRED block. The unconditional one compares a different"
        "\n  population in every row - a zone that failed at touch 1 is absent"
        "\n  from touch 2 by construction, so a decay there can be pure"
        "\n  selection and so can its absence."
    )
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
    loaded = [history.load(s, tf, args.bars) for s, tf in series]

    everything = {}
    # Both brackets, for the same reason calibrate runs both: zone height is
    # graded oppositely by the two, so an effect that only appears under one of
    # them is the geometry rather than the zone.
    for mode, reward, horizon in [("atr", 1.0, 40), ("atr", 2.0, 80), ("r", 2.0, 80)]:
        sequences: list[list[bool]] = []
        for candles in loaded:
            sequences.extend(collect(candles, params, reward, horizon, mode))
        everything[f"{mode}{reward}_h{horizon}"] = report(
            sequences, reward, horizon, mode
        )

    # The same question with the tautology removed. If the decay is real it has
    # to survive an outcome that never mentions the zone's distal.
    for reward, horizon in [(1.0, 40), (2.0, 80)]:
        aged = []
        for candles in loaded:
            aged.extend(collect_distal_free(candles, params, reward, horizon))
        free = [[ok for ok, _ in seq] for seq in aged]
        everything[f"free{reward}_h{horizon}"] = report(
            free, reward, horizon, "free"
        )
        by_age(aged)

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(everything, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
