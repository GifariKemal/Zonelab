"""Does any layer state separate the gate's expectancy? The pre-registered run.

    python -m tools.conditioned --symbol mt5:XAUUSD --interval 1h --bars 50000

THE COLUMN LIST IS CLOSED and lives in `docs/PRAREGISTRASI-KONDISI.md`, written
before this file produced a number. `COLUMNS` below is that list; adding to it
means writing a new pre-registration with a new date, not editing this tuple.

THE THRESHOLD IS COMPUTED, NOT CHOSEN. With `K` groups large enough to judge, a
two-sided alpha of 0.05 is divided by `K` and the critical `t` printed alongside
every row. That ordering matters: the tool counts the groups before it reports
any of them, so the bar cannot be lowered after a row looks interesting. This
project has already shipped one composite that ranked BACKWARDS - AUC 0.464 and
0.477 - and it got there by looking first.

WHAT A PASS MEANS. Three conditions, all stated up front: n >= 30, |t| past the
corrected critical value, and the same sign in both halves of the sample. A row
that clears all three earns a walk-forward run on its subpopulation. It does not
earn a place in `app/plan.py`.
"""

from __future__ import annotations

import argparse
from math import erfc, sqrt

import numpy as np

from app.cisd import cisds
from app.conditions import at_bar
from app.confluence import mark_nesting
from app.detect import DETECTORS
from app.ict import Rules, evaluate
from app.models import SupplyDemandParams
from app.poi import confluence, other_boxes
from app.resample import STEP_UP, resample
from tools import history
from tools.costed import POPULATION, trades
from tools.execute import POI_SLACK_BARS

#: The pre-registered columns. See the doc named in the module docstring.
COLUMNS = (
    "weekday",
    "hour_utc",
    "quarter_day",
    "quarter_session",
    "amd_profile",
    "in_manipulation_quarter",
    "manipulation_done",
    "range_band",
    "dfr_band",
    "bias_1d",
    "bias_4h",
    "bias_1h",
)

#: The ICT checklist's own clauses, added as a SECOND pre-registration on
#: 2026-08-21. They are listed separately from `COLUMNS` because they were
#: registered later, and merging the two lists would hide which questions were
#: asked before any number existed for them.
#:
#: Every one of these is a clause `app/ict.py` can be told to REQUIRE. This is
#: what turns that switch from a preference into a decision with a figure behind
#: it: a clause that separates earns its place in `--require`, and one that does
#: not stays reported and unenforced.
ICT_COLUMNS = (
    "killzone",
    "discount_or_premium",
    "manipulation_quarter",
    "manipulation_seen",
    "poi_families",
    "poi_clean",
    "cisd_in_band",
    "dfr_side",
    "bias_agrees",
    "htf_nested",
    "poi_family_count",
    "ict_met",
)

MIN_GROUP = 30
ALPHA = 0.05


def _critical_t(groups: int) -> float:
    """The two-sided normal critical value at `ALPHA / groups`.

    Normal rather than Student, and that is the honest simplification: every
    group here has n >= 30 by construction, where the two differ in the third
    decimal. Solved by bisection on `erfc` so this file keeps its no-scipy rule.
    """
    if groups <= 0:
        return float("inf")
    target = ALPHA / groups
    lo, hi = 0.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if erfc(mid / sqrt(2)) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _dfr_band(value: float | None) -> str | None:
    """`dfr_pos` cut into named thirds rather than reported raw.

    A continuous column cannot be grouped, and quartiles of the POPULATION would
    make the bands a function of the sample - so the cuts are the range's own
    geometry: inside it, above it, below it.
    """
    if value is None:
        return None
    if value > 1.0:
        return "above_range"
    if value < 0.0:
        return "below_range"
    return "inside_range"


def rows_with_state(symbol: str, interval: str, bars: int, flat: bool) -> list[dict]:
    """Every gate-clearing trade, with layer state AND the ICT checklist attached.

    The checklist is evaluated at the TOUCH bar, not at the last bar, and the POI
    stack is capped at that instant. A study that scored the clauses with today's
    boxes would be grading the method on information the trade never had.
    """
    candles = history.load(symbol, interval, bars)
    base = [
        r for r in trades("supply_demand", candles, interval, True,
                          symbol=symbol.split(":")[-1], broker="exness_raw",
                          flat_by_rollover=flat)
        if not r["skipped"] and r["cleared"]
    ]
    # The zone objects, indexed by the id the trade rows carry. Re-detected with
    # the same POPULATION params `trades` used, or the ids would not match.
    zones, _ = DETECTORS["supply_demand"](
        candles, SupplyDemandParams(**{**POPULATION, "show_broken": True})
    )
    by_id = {z.id: z for z in zones}
    # NESTING, STAMPED THE SAME WAY THE LIVE SCAN STAMPS IT. The first run of
    # this study measured `htf_nested` False on all 953 trades, which reads as
    # "gold never nests" and was the harness skipping the step: `candidates()`
    # resamples one degree up, detects there, and calls `mark_nesting`, and this
    # file did none of it. Second time the same class of bug has produced a column
    # of False here, after `cisd_levels`.
    #
    # NOT A LOOKAHEAD. `mark_nesting` requires the higher zone to have formed
    # strictly before the local zone's own birth and to still be alive at that
    # bar, so nothing about the future of the trade enters the stamp.
    higher_name = STEP_UP.get(interval)
    if higher_name:
        higher_bars = resample(candles, higher_name, interval)
        higher_zones, _ = DETECTORS["supply_demand"](
            higher_bars, SupplyDemandParams(**{**POPULATION, "show_broken": True})
        )
        for hz in higher_zones:
            hz.timeframe = higher_name
        mark_nesting(zones, higher_zones)
    others = other_boxes(candles)
    times = [c.time for c in candles]
    rules = Rules()
    # CISD LEVELS, and the first run of this study forgot to pass them. The
    # column came back False for all 953 trades, which reads as a market fact and
    # was a harness fact: `confluence` counts what it is given and it was given
    # nothing. Each event carries the bar it became knowable on, so the filter
    # below is a real anti-lookahead cut rather than a formality.
    events, _ = cisds(candles)
    cisd_by_time = sorted((int(e.time), float(e.level)) for e in events)

    out = []
    for row in base:
        touch = int(row["at"])
        state = at_bar(candles, touch, interval)
        state["dfr_band"] = _dfr_band(state.get("dfr_pos"))
        zone = by_id.get(row["zone_id"])
        if zone is not None:
            anatomy = zone.anatomy
            born_from = times[max(0, anatomy.leg_in_from - POI_SLACK_BARS)]
            born_to = times[min(len(times) - 1, anatomy.leg_out_to + POI_SLACK_BARS)]
            levels = [level for when, level in cisd_by_time if when <= times[touch]]
            stack = confluence(zone, others, times[touch], born_from, born_to,
                               cisd_levels=levels)
            checklist = evaluate(zone, state, stack, rules, at=times[touch])
            for condition in checklist:
                state[condition.name] = condition.met
            state["poi_family_count"] = stack.families
            # Bucketed, because "how much of the method was satisfied" is the
            # question a reader asks, and 11 separate counts would each be too
            # thin to judge.
            met = sum(1 for c in checklist if c.met is True)
            state["ict_met"] = f"{met // 2 * 2}-{met // 2 * 2 + 1}"
        out.append({**row, "state": state})
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--bars", type=int, default=50000)
    parser.add_argument("--hold", action="store_true",
                        help="grade on the 80-bar horizon instead of the flat "
                             "rule. The flat rule is the shipped one")
    args = parser.parse_args()

    rows = rows_with_state(args.symbol, args.interval, args.bars, not args.hold)
    if not rows:
        print("no gate-clearing trades in this window")
        return
    everything = np.array([r["r"] for r in rows])
    half = len(rows) // 2
    print(f"{args.symbol} {args.interval} {args.bars} bar, exit "
          f"{'hold 80 bar' if args.hold else 'flat di rollover'}")
    print(f"populasi n={len(rows)}  exp R {everything.mean():+.3f}")

    # COUNTED BEFORE ANYTHING IS REPORTED. The critical value depends on how many
    # groups are judged, so the count has to happen in a first pass or the
    # threshold becomes a function of what the reader has already seen.
    judged = 0
    for column in COLUMNS + ICT_COLUMNS:
        seen: dict[object, int] = {}
        for row in rows:
            key = row["state"].get(column)
            seen[key] = seen.get(key, 0) + 1
        judged += sum(1 for count in seen.values() if count >= MIN_GROUP)
    critical = _critical_t(judged)
    print(f"{judged} grup layak dinilai, alpha {ALPHA}/{judged} = "
          f"{ALPHA / judged:.5f}, |t| kritis {critical:.2f}\n")

    for column in COLUMNS + ICT_COLUMNS:
        buckets: dict[object, list[dict]] = {}
        for row in rows:
            buckets.setdefault(row["state"].get(column), []).append(row)
        print(f"-- {column}")
        for key in sorted(buckets, key=lambda k: (k is None, str(k))):
            group = buckets[key]
            values = np.array([r["r"] for r in group])
            if len(group) < MIN_GROUP:
                print(f"   {str(key):18s} n={len(group):4d}  terlalu kecil")
                continue
            # AGAINST THE REST OF THE POPULATION, not against zero. Testing a
            # group against zero answers "is this group profitable", and with the
            # whole population at +0.221 every large group answers yes - the
            # first run of this tool printed LOLOS on BOTH sides of `bias_1d`,
            # which cannot be a separation by anybody's reading. The question in
            # the pre-registration is whether the column SEPARATES, so the null
            # is the complement of the group. Welch, because the two arms have no
            # reason to share a variance.
            rest = np.array([r["r"] for r in rows if r["state"].get(column) != key])
            if len(rest) < MIN_GROUP:
                print(f"   {str(key):18s} n={len(group):4d}  sisanya terlalu kecil")
                continue
            se = sqrt(
                values.var(ddof=1) / len(values) + rest.var(ddof=1) / len(rest)
            )
            delta = values.mean() - rest.mean()
            t = delta / se if se > 0 else float("nan")
            # The halves check is on the DELTA too, for the same reason: a group
            # whose advantage over the rest flips sign between halves has not
            # separated anything, it has taken turns.
            cut = rows[half]["at"]
            deltas = []
            for lo, hi in ((None, cut), (cut, None)):
                inside = np.array([
                    r["r"] for r in group
                    if (lo is None or r["at"] >= lo) and (hi is None or r["at"] < hi)
                ])
                outside = np.array([
                    r["r"] for r in rows
                    if r["state"].get(column) != key
                    and (lo is None or r["at"] >= lo) and (hi is None or r["at"] < hi)
                ])
                deltas.append(
                    inside.mean() - outside.mean()
                    if len(inside) and len(outside) else float("nan")
                )
            halves = (
                f"{deltas[0]:+.3f}/{deltas[1]:+.3f}"
                if not any(np.isnan(deltas)) else "  n/a  "
            )
            same_sign = (
                not any(np.isnan(deltas)) and (deltas[0] > 0) == (deltas[1] > 0)
            )
            verdict = "MEMISAHKAN" if abs(t) >= critical and same_sign else ""
            print(f"   {str(key):18s} n={len(group):4d}  exp R {values.mean():+.3f}"
                  f"  delta {delta:+.3f}  t={t:+6.2f}  paruh {halves}  {verdict}")
        print()


if __name__ == "__main__":
    main()
