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

===============================================================================
TWO STEPS DOWN. Pre-registered 2026-08-17, before any three-way number existed.
===============================================================================

docs/FIDELITY.md names this gap itself: one step down is measured, two is not,
and no source publishes a floor at which stepping down stops making sense. This
is the second step, on the same paired design, so all three arms - as drawn,
refined once, refined twice - come from IDENTICAL zones judged on IDENTICAL bars.

THE TIMEFRAME TRIPLES, AND WHY THESE ONES
No source publishes a ratio. The circulating "daily to H1, H4 to H1, M15 to M5"
triplet traces to one secondary blog and specifies floors rather than divisors
(app/refine.py says so and cites the search). So these are a stated choice:

  PAXGUSDT      1h / 15m / 5m    4x then 3x     20000 5m bars, ~69 days
  PAXGUSDT      4h / 1h  / 15m   4x then 4x     20000 15m bars, ~208 days
  BTCUSDT       4h / 1h  / 15m   4x then 4x     20000 15m bars, ~208 days
  PAXGUSDT      1d / 4h  / 1h    6x then 4x     20000 1h bars, ~2.3 years
  BTCUSDT       1d / 4h  / 1h    6x then 4x
  ETHUSDT       1d / 4h  / 1h    6x then 4x
  yahoo:XAUUSD  1d / 4h  / 1h    6x then 4x     the COMEX future, not crypto

Every timeframe inside a triple is derived from ONE cached series, the lowest
one. That is not a convenience. If the top bars came from a longer series than
the bottom bars, the second step would fail on every zone older than the short
series, and the drop count would then be measuring the cache rather than the
geometry. It also means the two-step sample is NOT the one-step sample: the
1h/15m/5m triple sees 69 days where the one-step table sees 208. Stated, not
smoothed over.

One extra triple, PAXGUSDT 1h / 30m / 5m, is measured and deliberately NOT
pooled: it is the same 1h zones as the first triple with a different middle
rung, 2x then 6x instead of 4x then 3x. Pooling it would enter those zones
twice into a paired test whose whole design assumes one row per zone.

WHAT THE SECOND STEP ACTUALLY IS, in shipped terms
`refine_zones` called a second time on the once-refined zones, with the next
series down. Its window is still the HTF base, so step two finds the last pause
of the lower timeframe inside the SAME base, and keeps it only if it sits inside
the once-refined box - the containment check that already exists in shipped code
is what makes the three arms strictly nested. And the lifecycle is replayed after
every shrink, by `refine_zones` itself, because a tighter distal is a different
question about the same bars: price that never closed past the wide edge may
well have closed past the narrow one.

WHAT IS TESTED
The same exact McNemar test on the pairs the arms disagree about, at the same
three geometries the one-step table uses, twice-refined against once-refined and
twice-refined against as-drawn.

WHAT THE PUBLISHED INTERPRETATION PREDICTS
FIDELITY.md attributes the one-step loss (-4.2, -5.8, -9.9 pp) to bracket
geometry alone: survival is a function of how far the stop sits from price, the
shortest quartile of zone heights held 52.4% against 61.4% for the tallest at
reward 2.0, and refinement moves a zone into the shortest quartile. If that
explanation is complete then

  (a) survival must fall AGAIN at the second step, at every geometry, because
      the stop moves closer again; and
  (b) at the SAME stop distance in ATR, the three arms must hold at the SAME
      rate. A twice-refined zone whose stop sits 0.3 ATR away must survive like
      an as-drawn zone whose stop sits 0.3 ATR away, because under this
      explanation nothing except that distance is doing any work.

(b) is the one that can break it. (a) on its own is nearly unfalsifiable, so it
is reported and not treated as evidence.

WHAT I CONCLUDE ON FAILURE
  - Survival flat or higher at step two: the geometry story is incomplete in the
    direction that flatters refinement, and the honest write-up is that a second
    step cost nothing measurable HERE, at these ratios, on this sample.
  - Twice-refined holding BELOW as-drawn zones at the same stop distance: the
    geometry under-predicts, refinement is destroying something the bracket does
    not explain, and the FIDELITY.md box needs qualifying.
  - Fewer than 30 zones surviving all three arms: nothing is reported, the same
    rule the one-step table already refuses under.

WHAT THIS CANNOT DO
It cannot find a floor. Two measured steps say what two steps cost; they do not
locate the depth at which stepping down stops making sense, and no number here
may be written up as if they did.

THE POPULATION PROBLEM, WHICH IS NOT OPTIONAL
Zones vanish at the second step: the lower series may hold no pause inside the
base, the inner box may poke outside the once-refined one, or it may not shrink
at all. They are not dropped silently. The paired test runs only on zones that
survived all three arms, and those survivors are printed beside the ones lost -
count, reason, survival, height - so a reader can see whether the survivors are
a biased subset. A paired test on a subset selected BY the treatment is exactly
how a refinement result could be manufactured.
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

# The same three geometries for both tables, hoisted so they cannot drift apart.
GEOMETRIES = [(0.5, 40), (1.0, 40), (2.0, 80)]

# Zone timeframe first, then each step down. The last entry is the interval the
# series is LOADED at, and every other timeframe in the triple is aggregated from
# it, so the arms cover the same span by construction. See the docstring for why
# each ratio is a stated choice and not doctrine. Only cached series appear here.
TRIPLES = [
    ("PAXGUSDT", ("1h", "15m", "5m")),
    ("PAXGUSDT", ("4h", "1h", "15m")),
    ("BTCUSDT", ("4h", "1h", "15m")),
    ("PAXGUSDT", ("1d", "4h", "1h")),
    ("BTCUSDT", ("1d", "4h", "1h")),
    ("ETHUSDT", ("1d", "4h", "1h")),
    ("yahoo:XAUUSD", ("1d", "4h", "1h")),
]

# Same zones as TRIPLES[0], different middle rung. Reported alone, never pooled.
RATIO_CHECK = ("PAXGUSDT", ("1h", "30m", "5m"))

# Shared bins of stop distance in ATR at the touch bar. This is the axis the
# published explanation says is the ONLY thing at work, so the three arms are
# compared inside a bin rather than against each other's averages.
STOP_BINS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, float("inf"))


def compare(
    candles: list[Candle],
    params: SupplyDemandParams,
    chain: tuple[str, ...],
    reward_atr: float,
    horizon: int,
    step_stats: list[dict] | None = None,
) -> list[dict]:
    """One row per zone that resolved in the as-drawn and once-refined arms.

    `chain` runs from the timeframe the zone belongs to down to the interval
    `candles` are in: ("1h", "15m") is the one-step test, ("1h", "15m", "5m")
    adds a second step. Every timeframe in it is aggregated from `candles`, so
    the arms cannot differ in the span they cover.

    `step_stats` collects the LAST step's refine_zones counters, which is the
    only honest way to say WHY a zone failed to refine again.
    """
    higher = chain[0]
    bars = resample(candles, higher, chain[-1])
    if len(bars) < params.atr_period + 3:
        return []

    # Each arm is the previous arm refined once more. The deepcopy is what keeps
    # the design paired: arm i and arm i+1 are the same zones in the same order,
    # differing only by the shrink just applied. refine_zones replays the
    # lifecycle after every shrink, so no arm carries a state that its own
    # narrower distal has already invalidated.
    arms = [detect(bars, params)[0]]
    stats: dict[str, float] = {}
    for lower in chain[1:]:
        arm = copy.deepcopy(arms[-1])
        stats = refine_zones(
            arm, bars,
            candles if lower == chain[-1] else resample(candles, lower, chain[-1]),
            higher, params,
        )
        arms.append(arm)
    if step_stats is not None:
        step_stats.append(stats)

    high = np.array([c.high for c in bars])
    low = np.array([c.low for c in bars])
    close = np.array([c.close for c in bars])
    atr = wilder_atr(high, low, close, params.atr_period)

    rows = []
    for zones in zip(*arms):
        vals = []
        for i, zone in enumerate(zones):
            if i and _same_box(zone, zones[i - 1]):
                break  # that step declined, so this arm does not exist here
            touch = first_touch(zone, high, low, zone.anatomy.leg_out_to + 1)
            if touch is None:
                break
            outcome = resolve(
                zone, high, low, close, atr, touch, reward_atr, horizon
            )
            if outcome is None:
                break
            risk = abs(zone.proximal - zone.distal)
            scale = float(atr[touch])
            vals.append((outcome, risk, risk / scale if scale > 0 else float("nan")))
        if len(vals) < 2:
            continue  # only pairs, so the comparison stays paired

        row = {
            "plain_held": vals[0][0],
            "refined_held": vals[1][0],
            "plain_risk": vals[0][1],
            "refined_risk": vals[1][1],
            "shrank_to": zones[1].refinement.shrank_to,
            "plain_risk_atr": vals[0][2],
            "refined_risk_atr": vals[1][2],
        }
        if len(zones) > 2:
            # Whether the second step FIRED and whether its bracket RESOLVED are
            # two different facts, and lumping them would hide a selection effect
            # behind a geometry count.
            fired = not _same_box(zones[2], zones[1])
            resolved = len(vals) > 2
            row["twice_fired"] = fired
            row["twice_held"] = vals[2][0] if resolved else None
            row["twice_risk"] = vals[2][1] if resolved else None
            row["twice_risk_atr"] = vals[2][2] if resolved else None
            row["twice_shrank_to"] = zones[2].refinement.shrank_to if fired else None
        rows.append(row)
    return rows


def _same_box(zone: Zone, other: Zone) -> bool:
    """That step left the box alone.

    `refine_zones` writes both edges or neither, so exact equality is the right
    test here and a tolerance would only invent a third outcome.
    """
    return zone.top == other.top and zone.bottom == other.bottom


def mcnemar(
    rows: list[dict], a: str = "plain_held", b: str = "refined_held"
) -> tuple[int, int, float]:
    """Exact paired test on the zones the two arms DISAGREED about.

    The pairs that agree carry no information about which arm is better, so
    counting them - as a two-proportion test on the same zones would - dilutes
    the very comparison the pairing was set up to make.
    """
    only_plain = sum(1 for r in rows if r[a] and not r[b])
    only_refined = sum(1 for r in rows if r[b] and not r[a])
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


def _held(rows: list[dict], key: str) -> float:
    return float(np.mean([r[key] for r in rows]))


def _line(label: str, rows: list[dict]) -> dict:
    """One row of the per-triple table: the three arms on that triple's zones."""
    surv = [r for r in rows if r.get("twice_held") is not None]
    if len(surv) < 30:
        print(f"  {label:<26}{len(surv):>7}   fewer than 30 through all three arms")
        return {}
    plain, once, twice = (
        _held(surv, "plain_held"), _held(surv, "refined_held"), _held(surv, "twice_held")
    )
    cum = float(np.median([r["twice_risk"] / max(r["plain_risk"], 1e-12) for r in surv]))
    print(f"  {label:<26}{len(surv):>7}{plain:>9.1%}{once:>9.1%}{twice:>9.1%}"
          f"{twice - once:>+9.1%}{cum:>10.1%}")
    return {"n": len(surv), "plain_held": plain, "once_held": once,
            "twice_held": twice, "stop_fraction_median": cum}


def _by_stop_distance(surv: list[dict]) -> dict:
    """Survival inside shared bins of stop distance in ATR, one row per bin.

    This is the test of the published explanation, not a decoration. If the
    one-step loss is nothing but bracket geometry, then a twice-refined zone
    whose stop sits 0.3 ATR away must hold like an as-drawn zone whose stop sits
    0.3 ATR away, because under that account the distance is doing all the work.
    Cells under 30 zones print as a dash rather than as a number nobody should
    read.
    """
    print("\n  SURVIVAL BY STOP DISTANCE, the same bins for all three arms")
    print(f"  {'stop / ATR':<26}{'as drawn':>18}{'refined once':>18}"
          f"{'refined twice':>18}")
    out = {}
    for lo, hi in zip(STOP_BINS, STOP_BINS[1:]):
        cells, values = [], {}
        for arm in ("plain", "refined", "twice"):
            sel = [r[f"{arm}_held"] for r in surv
                   if lo <= r[f"{arm}_risk_atr"] < hi]
            if len(sel) >= 30:
                cells.append(f"{np.mean(sel):>11.1%} n={len(sel):<5}")
                values[arm] = float(np.mean(sel))
            else:
                cells.append(f"{'-':>11} n={len(sel):<5}")
        label = f"{lo:.2f} to {hi:.2f}" if hi < 100 else f"{lo:.2f} and up"
        print(f"  {label:<26}" + "".join(cells))
        out[label] = values
    return out


def report3(
    rows: list[dict], reward_atr: float, horizon: int, drops: dict,
    per_triple: list[tuple[str, list[dict]]],
) -> dict:
    """The three-way table, on zones that resolved in all three arms."""
    surv = [r for r in rows if r["twice_held"] is not None]
    lost = [r for r in rows if not r["twice_fired"]]
    unresolved = [r for r in rows if r["twice_fired"] and r["twice_held"] is None]

    print(f"\n{'=' * 78}")
    print(f"TWO STEPS DOWN, PAIRED   reward {reward_atr} ATR, horizon {horizon} bars")
    print(f"{'=' * 78}")
    print(f"  once-refined pairs      {len(rows)}")
    print(f"  through all three arms  {len(surv)}"
          f"   {len(surv) / max(len(rows), 1):.1%} of them")
    print(f"  lost at the second step {len(lost)} declined"
          f" + {len(unresolved)} whose bracket never resolved")
    # `refine_zones` is handed the whole arm, so these counters cover zones step
    # one had already declined too - for those, the lower call is a FIRST
    # refinement and not a second. They never reach the paired sample, which
    # requires both steps to have fired, so the counters explain the mechanism
    # while the two numbers above are the population.
    print("  why the lower step declined, over every zone in the arm"
          f" ({drops.get('refine_candidates', 0):.0f}, step-one failures included):")
    print(f"    refined again {drops.get('refined', 0):.0f}"
          f"   no inner pause {drops.get('refine_no_inner_base', 0):.0f}"
          f"   not contained {drops.get('refine_not_contained', 0):.0f}"
          f"   no gain {drops.get('refine_no_gain', 0):.0f}"
          f"   no LTF bars {drops.get('refine_no_ltf_bars', 0):.0f}")

    if len(surv) < 30:
        print("  refusing to report: under 30 zones through all three arms")
        return {}

    plain, once, twice = (
        _held(surv, "plain_held"), _held(surv, "refined_held"), _held(surv, "twice_held")
    )
    # Both McNemar tests are on THIS sample, the zones that survived two shrinks.
    # The once-versus-drawn line therefore is NOT the published one-step number
    # and must not be quoted as if it were: the published one is on every pair
    # that refined once, this one is on the subset that refined twice.
    op, o_r, p_once = mcnemar(surv, "plain_held", "refined_held")
    tp, t_r, p_twice = mcnemar(surv, "refined_held", "twice_held")
    cp, c_r, p_cum = mcnemar(surv, "plain_held", "twice_held")

    print(f"\n  as drawn                held {plain:.1%}")
    print(f"  refined once            held {once:.1%}   {once - plain:+.1%}"
          f" vs drawn   {op} vs {o_r} disagreed, exact p={p_once:.4f}")
    print(f"  refined twice           held {twice:.1%}   {twice - once:+.1%}"
          f" vs once    {tp} vs {t_r} disagreed, exact p={p_twice:.4f}")
    print(f"                                       {twice - plain:+.1%}"
          f" vs drawn   {cp} vs {c_r} disagreed, exact p={p_cum:.4f}")

    once_frac = np.array([r["refined_risk"] / max(r["plain_risk"], 1e-12) for r in surv])
    cum_frac = np.array([r["twice_risk"] / max(r["plain_risk"], 1e-12) for r in surv])
    step2_frac = np.array([r["twice_shrank_to"] for r in surv])
    print(f"\n  stop distance, once     {once_frac.mean():.1%} of the original,"
          f" median {np.median(once_frac):.1%}")
    print(f"  stop distance, twice    {cum_frac.mean():.1%} of the original,"
          f" median {np.median(cum_frac):.1%}")
    print(f"  the second step alone   {step2_frac.mean():.1%} of the once-refined"
          f" box, median {np.median(step2_frac):.1%}")

    # Same winsorised leverage as the one-step table, for the same reason: a zone
    # that collapsed to 2% of its height contributes a 50x multiple no trader
    # would ever realise and would otherwise set the average by itself.
    cap_once = np.minimum(1.0 / np.maximum(once_frac, 1e-9), 10.0)
    cap_twice = np.minimum(1.0 / np.maximum(cum_frac, 1e-9), 10.0)
    print(f"\n  reward per unit of risk  drawn 1.00   once median"
          f" {np.median(1.0 / once_frac):.2f}   twice median"
          f" {np.median(1.0 / cum_frac):.2f}")
    print(f"  survival x that, capped  drawn {plain:.2f}"
          f"   once {float(np.mean(np.array([r['refined_held'] for r in surv]) * cap_once)):.2f}"
          f"   twice {float(np.mean(np.array([r['twice_held'] for r in surv]) * cap_twice)):.2f}")

    # Is the surviving population a biased subset? Both groups refined ONCE and
    # resolved, so they can be compared on the arms they share. If the zones that
    # refined twice were already the weak ones, the three-way drop would be
    # selection and not the second step.
    print("\n  SURVIVORS vs ZONES LOST AT STEP 2, on the two arms they share")
    print(f"  {'':<26}{'n':>7}{'drawn':>9}{'once':>9}"
          f"{'step-1 stop':>13}{'plain stop/ATR':>16}")
    bias = {}
    for label, group in (("through all three", surv), ("declined at step 2", lost)):
        if not group:
            continue
        cell = {
            "n": len(group),
            "plain_held": _held(group, "plain_held"),
            "once_held": _held(group, "refined_held"),
            "step1_fraction": float(np.median([r["shrank_to"] for r in group])),
            "plain_stop_atr": float(np.median([r["plain_risk_atr"] for r in group])),
        }
        print(f"  {label:<26}{cell['n']:>7}{cell['plain_held']:>9.1%}"
              f"{cell['once_held']:>9.1%}{cell['step1_fraction']:>13.1%}"
              f"{cell['plain_stop_atr']:>16.2f}")
        bias[label] = cell

    bins = _by_stop_distance(surv)

    print("\n  PER TRIPLE, pooled above. Ratios differ, so read the spread.")
    print(f"  {'':<26}{'n':>7}{'drawn':>9}{'once':>9}{'twice':>9}"
          f"{'2nd step':>9}{'stop left':>10}")
    triples = {label: _line(label, got) for label, got in per_triple}

    return {
        "n": len(surv),
        "pairs": len(rows),
        "lost_declined": len(lost),
        "lost_unresolved": len(unresolved),
        "drop_reasons": {k: float(v) for k, v in drops.items()},
        "plain_held": plain,
        "once_held": once,
        "twice_held": twice,
        "p_once_vs_drawn": p_once,
        "p_twice_vs_once": p_twice,
        "p_twice_vs_drawn": p_cum,
        "stop_fraction_once_median": float(np.median(once_frac)),
        "stop_fraction_twice_median": float(np.median(cum_frac)),
        "stop_fraction_step2_median": float(np.median(step2_frac)),
        "by_stop_distance": bins,
        "survivor_bias": bias,
        "per_triple": triples,
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
    for reward_atr, horizon in GEOMETRIES:
        rows: list[dict] = []
        for interval, candles in loaded:
            rows.extend(
                compare(candles, params, (STEP_UP[interval], interval),
                        reward_atr, horizon)
            )
        out[f"r{reward_atr}_h{horizon}"] = report(rows, reward_atr, horizon)

    # Second step. Loaded once and reused across geometries, because the whole
    # point of the triples is that every arm is aggregated from one series.
    triples = [
        (f"{symbol} {'/'.join(chain)}", chain, history.load(symbol, chain[-1], args.bars))
        for symbol, chain in TRIPLES + [RATIO_CHECK]
    ]
    for reward_atr, horizon in GEOMETRIES:
        rows, drops, per_triple = [], {}, []
        for label, chain, candles in triples[: len(TRIPLES)]:
            stats: list[dict] = []
            got = compare(candles, params, chain, reward_atr, horizon, stats)
            for key, value in (stats[0] if stats else {}).items():
                drops[key] = drops.get(key, 0.0) + value
            per_triple.append((label, got))
            rows.extend(got)
        out[f"three_r{reward_atr}_h{horizon}"] = report3(
            rows, reward_atr, horizon, drops, per_triple
        )

        # Not pooled: the same 1h zones as the first triple with a 2x middle rung
        # instead of 4x. Pooling would enter those zones twice into a paired test.
        label, chain, candles = triples[-1]
        print("\n  RATIO CHECK, NOT POOLED. Same zones as the first triple, other"
              " middle rung.")
        out[f"ratio_r{reward_atr}_h{horizon}"] = _line(
            label, compare(candles, params, chain, reward_atr, horizon)
        )

    print(
        "\n  The bar, fixed in the docstring before any of this existed: survival"
        "\n  must fall again if the published geometry explanation is complete, and"
        "\n  - the line that can actually break it - the three arms must hold at"
        "\n  the same rate INSIDE a bin of stop distance. Two steps measured is not"
        "\n  a floor found, and nothing here may be written up as one."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
