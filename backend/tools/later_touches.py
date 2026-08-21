"""Does the SHIPPED GATE still separate anything at the second touch?

    python -m tools.later_touches --bars 20000

docs/CALIBRATION.md and docs/FIDELITY.md end with the same admission, first line
of "Yang tidak diukur": *"Sentuhan kedua dan seterusnya. Semua di atas hanya
sentuhan pertama."* Every outcome number in this project - the +14.8 to +21.4 pp
gate edge, the nine walk-forward slices, all 14 factor AUCs, the placebo and the
rejected cohort - is measured on the FIRST touch and nowhere else. The chart does
not stop there. A zone with `state=TESTED` and `touches=3` is still drawn, still
carries `departure_atr`, and the only filter behind it was fitted and validated
on an occasion that has already passed.

HOW THIS DIFFERS FROM tools/touches.py, WHICH IS NOT THE SAME TOOL
`touches.py` runs H1: does a zone get WORSE each time price tests it. Its unit is
a zone, its estimand is a decay in hold rate across touch numbers, and it answers
with a paired McNemar and a hazard curve. Its verdict is already published - not
confirmed, the decay was age wearing a touch label (93.6% -> 77.2% at the SAME
touch number, 16 pp from age alone).

This tool asks a different question of the same bars, and about the FILTER rather
than about the zone:

  touches.py  "is touch 5 worse than touch 1, for the same zone?"      -> answered
  here        "at touch 5, is a GATED zone still better than a rejected
               one, and does touch number tell a trader anything at the
               moment they are looking at the chart?"                  -> new

The unit here is a TOUCH EVENT, not a zone, and the population is split by the
gate rather than paired across occasions. That difference is not cosmetic: the
paired test conditions on a fact from the future (this zone will reach touch 2),
while a trader at a touch knows only how many touches have already happened. The
second table below is the decision-time form of the freshness claim; the first
table is the one nothing here has ever measured at all.

WHAT IS READ AS OF WHICH BAR
  `gated` is `zone.departure_atr`, and it needs no clipping because the detector
  already clips it: `look_to = max(leg_out+1, min(look_to, first_touch))`, so the
  window ends before the FIRST touch bar prints and the value is knowable at
  every later touch by construction. It is also the exact number the product
  gates on, since 2026-08 when the measured gate and the shipped gate were found
  to be two different gates. Widening the window to each later touch would be
  equally causal and strictly worse: the cohorts would stop being the same
  population from row to row, which is the one thing this table must not do.
  `age` and `touch number` are counted up to the touch bar. Nothing else is read.

A touch is one VISIT, not one bar: consecutive bars inside the zone are the same
test, and a close past the distal ends both the zone and the count. That is
`replay_lifecycle`'s definition, already extracted as `touches.visits`, and it is
imported rather than rewritten so these numbers stay comparable with H1's.

FIXED BEFORE ANY NUMBER WAS LOOKED AT
  Geometries: reward 0.5, 1.0 and 2.0 ATR from the proximal, stop at the distal,
    80-bar bracket horizon. Three, because one geometry can be picked to flatter.
  Series: the five cached crypto/PAXG series calibrate.py uses, plus Yahoo's gold
    future at 1h - a different vendor, instrument and exchange.
  Population: POPULATION, so `max_zones_per_side=0` (a recency cap has already
    invalidated one whole round of calibration here) and `departure_min_atr=0.0`
    so the rejected cohort exists to compare against.

  PRIMARY PASS, the gate at later touches, needs ALL FOUR:
    1. at touch >= 2, kept minus cut >= +5 pp at BOTH reward 1.0 and 2.0 ATR;
    2. p < 0.05 two-proportion at both, with >= 100 events in each cohort;
    3. the edge survives inside at least 2 of the 3 age terciles at touch >= 2,
       each cell >= 100 per cohort;
    4. demand and supply BOTH positive. The gate is side-blind by construction -
       it reads the size of the leg-out and nothing directional - so unlike a
       doctrine claim the two sides MUST agree here. A one-sided edge is the
       check that killed the strongest result this project ever measured.
  PRIMARY FAIL means: the departure gate is validated at the FIRST TOUCH ONLY,
  and every later-touch zone on the chart carries no measured filter. That is a
  documentation change, not a code change.

  SECONDARY PASS, touch number as a decision-time variable, needs: gated zones at
  touch 1 beating touch >= 2 by >= 5 pp INSIDE EVERY age tercile with >= 100
  events per cell, at both reward 1.0 and 2.0 ATR, same sign on both sides.
  SECONDARY FAIL means the freshness doctrine has no decision-time content here
  either, reached by a different route than H1's.

  HONEST PRIOR: low for the secondary, because H1 already found the touch effect
  was the clock. NONE STATED for the primary - nothing in this repo has measured
  it, in either direction, and a prior would be invented.

  A SELF-CHECK THAT COMES FREE: the touch-1 row of the first table is the
  published first-touch table, reached through a different code path. It reads
  97.7 / 85.8 / 57.0% kept against 83.2 / 64.5 / 45.5% cut, where
  docs/CALIBRATION.md has 97.9 / 85.8 / 57.0% against 83.1 / 64.4 / 45.3%. If
  those two columns had disagreed, nothing below them would have been worth
  reading. n is larger here (3086 against 2707) because this tool does not
  require `score_as_of` to resolve and uses the 80-bar horizon at every geometry.

ADDED AFTER THE FIRST TABLES WERE READ, AND LABELLED AS POST-HOC FOR THAT REASON
A fourth block runs the equal-R bracket (`mode="r"`, target 2.0 zone heights,
stop at the distal), and it was NOT in the bar above. It is here because the
primary tables came out INVERTED - gated zones doing worse than rejected ones at
touch 2 and later - and this repo's own instrument for telling a real effect from
bracket geometry is the two-bracket cross-check in `calibrate.cross_mode`: zone
height is graded oppositely by the two modes (0.537 against 0.391), so anything
that is really height wearing another name must flip between them. `departure_atr`
is an excursion divided by ATR while the bracket's stop is the zone's own height,
so the two are not independent and the check is not optional for reading an
inversion. It is excluded from the verdict block, which scores only the three
geometries fixed in advance.

THE TAUTOLOGY, NAMED BECAUSE IT IS NOT REMOVED HERE
`resolve` fails a touch when a bar closes past the distal, and the distal is also
what kills the zone, so the last touch before a death scores as a failure by
construction. H1 removed this with a distal-free outcome and its decay survived
(88.2% -> 79.0% -> 75.5%), which is why it is not re-run here: it would duplicate
a published measurement rather than add one. It bites the SECONDARY table and is
neutral-to-adverse for the PRIMARY one, where both cohorts are scored by the same
rule and the rejected cohort dies sooner.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.models import Candle, SupplyDemandParams
from tools import history
# `_two_proportion` is private, and imported anyway for the same reason `resolve`
# is: a second z-test in this repo would drift from the first one, and every
# published significance claim here came out of that function.
from tools.calibrate import POPULATION, SHIPPED_GATE, _two_proportion, resolve
from tools.touches import MAX_TOUCH, visits

SERIES = [
    ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
    ("yahoo:XAUUSD", "1h"),
]
PLAN = [("atr", 0.5, 80), ("atr", 1.0, 80), ("atr", 2.0, 80), ("r", 2.0, 80)]

# Two thresholds, both fixed above and both printed beside every cell. 40 is the
# floor for SHOWING a rate, matching `touches.by_age`; 100 per cohort is the floor
# for CONCLUDING from a difference. This repo has killed a 0.206 AUC that rested
# on 5 failures out of 234, so a cell that cannot support a claim says so in the
# table rather than in a footnote.
MIN_SHOW = 40
MIN_CONCLUDE = 100


def collect(
    candles: list[Candle],
    params: SupplyDemandParams,
    reward: float,
    horizon: int,
    label: str,
    mode: str,
) -> list[dict]:
    """One row per TOUCH EVENT: which visit, how old, which side, gated or cut."""
    zones, _ = detect(candles, params)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)

    rows: list[dict] = []
    for zone in zones:
        if float(atr[max(0, zone.anatomy.base_from - 1)]) <= 0:
            continue
        for k, touch in enumerate(visits(zone, high, low, close)[:MAX_TOUCH], 1):
            outcome = resolve(
                zone, high, low, close, atr, touch, reward, horizon, mode
            )
            if outcome is None:
                # Unresolved inside the horizon; the later visits sit inside the
                # same window and would be too. Same rule as tools/touches.py,
                # kept identical so the two tools' counts can be compared.
                break
            rows.append({
                "series": label,
                "side": zone.side.value,
                "touch": k,
                "age": touch - zone.anatomy.leg_out_to,
                "held": outcome,
                "gated": zone.departure_atr >= SHIPPED_GATE,
                "index": touch,
            })
    return rows


def split(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    kept = np.array([r["held"] for r in rows if r["gated"]], dtype=bool)
    cut = np.array([r["held"] for r in rows if not r["gated"]], dtype=bool)
    return kept, cut


def gate_line(name: str, rows: list[dict]) -> dict:
    """One gate row, printed with both cohort counts whatever they are."""
    kept, cut = split(rows)
    edge = (
        float(kept.mean() - cut.mean())
        if len(kept) >= MIN_SHOW and len(cut) >= MIN_SHOW
        else float("nan")
    )
    usable = len(kept) >= MIN_CONCLUDE and len(cut) >= MIN_CONCLUDE
    test = _two_proportion(kept, cut) if len(kept) and len(cut) else "no cohort"
    print(
        f"  {name:<12}{len(kept):>8}{_pct(kept):>10}{len(cut):>8}{_pct(cut):>10}"
        f"{'   -   ' if np.isnan(edge) else f'{edge:+7.1%}'}"
        f"   {test}{'' if usable else '   <- TOO SMALL TO CONCLUDE FROM'}"
    )
    return {
        "kept_n": len(kept), "kept_held": _f(kept),
        "cut_n": len(cut), "cut_held": _f(cut),
        "edge": edge, "test": test, "usable": usable,
    }


def _pct(values: np.ndarray) -> str:
    return "   -  " if len(values) < MIN_SHOW else f"{values.mean():.1%}"


def _f(values: np.ndarray) -> float | None:
    return float(values.mean()) if len(values) else None


def report(rows: list[dict], reward: float, horizon: int, mode: str = "atr") -> dict:
    if len(rows) < 200:
        print(f"  only {len(rows)} touch events, refusing to report")
        return {}

    ages = np.array([r["age"] for r in rows])
    edges = np.quantile(ages, [0, 1 / 3, 2 / 3, 1.0])
    bands = [(edges[i], edges[i + 1], i == 2) for i in range(3)]

    def in_band(row: dict, band: tuple[float, float, bool]) -> bool:
        lo, hi, last = band
        return lo <= row["age"] and (row["age"] <= hi if last else row["age"] < hi)

    later = [r for r in rows if r["touch"] >= 2]
    out: dict = {"events": len(rows), "later_events": len(later),
                 "age_terciles": [float(e) for e in edges]}

    unit = "ATR" if mode == "atr" else "x ZONE HEIGHT, equal R, POST-HOC"
    print(f"\n{'=' * 96}")
    print(f"REWARD {reward} {unit}, HORIZON {horizon} BARS   {len(rows)} touch"
          f" events, {len(later)} of them at touch >= 2")
    print(f"{'=' * 96}")

    # --- PRIMARY: the shipped gate, read at each touch ------------------------
    print("\n  THE SHIPPED GATE AT EACH TOUCH   kept = departure >= "
          f"{SHIPPED_GATE} ATR as the product ships it")
    print(f"  {'touch':<12}{'kept n':>8}{'kept':>10}{'cut n':>8}{'cut':>10}"
          f"{'edge':>7}   two-proportion test")
    out["gate_by_touch"] = {}
    for k in range(1, MAX_TOUCH + 1):
        at_k = [r for r in rows if r["touch"] == k]
        if len(at_k) < MIN_SHOW:
            continue
        out["gate_by_touch"][k] = gate_line(str(k), at_k)
    out["gate_later"] = gate_line("2+ pooled", later)

    # --- THE CONTROL, and it is the whole reason this table is readable -------
    # Later touches happen later. H1 measured what age alone is worth on this
    # exact population - 93.6% to 77.2% at the SAME touch number, 16 pp - and age
    # then turned out to be the departure gate in disguise. So a gate edge that
    # only exists across age bands is the gate ranking the clock, and a touch
    # effect that only exists across them is the same mistake H1 made.
    print("\n  AGE CONTROL   the same gate edge INSIDE bands of equal age at the"
          " touch")
    print(f"  {'age at touch':<20}{'touch 1 edge':>14}{'kept/cut':>16}"
          f"{'touch 2+ edge':>14}{'kept/cut':>16}   ! = under "
          f"{MIN_CONCLUDE} a cohort")
    out["gate_by_age"] = []
    for lo, hi, last in bands:
        cells = []
        for pick in (
            [r for r in rows if r["touch"] == 1 and in_band(r, (lo, hi, last))],
            [r for r in later if in_band(r, (lo, hi, last))],
        ):
            kept, cut = split(pick)
            edge = (
                float(kept.mean() - cut.mean())
                if len(kept) >= MIN_SHOW and len(cut) >= MIN_SHOW
                else float("nan")
            )
            cells.append({
                "edge": edge, "kept_n": len(kept), "cut_n": len(cut),
                "usable": len(kept) >= MIN_CONCLUDE and len(cut) >= MIN_CONCLUDE,
            })
        shown = ""
        for cell in cells:
            edge = cell["edge"]
            # The marker sits on the CELL, not on the row. It has to: the
            # rejected cohort at touch 1 nearly vanishes in the oldest age band
            # (20 events against 1126), so a row-level flag would tar a
            # touch-2+ cell holding 8000 events with its neighbour's problem.
            counts = f"{cell['kept_n']}/{cell['cut_n']}{'' if cell['usable'] else ' !'}"
            drawn = "      -       " if np.isnan(edge) else f"{edge:+13.1%} "
            shown += f"{drawn}{counts:>16}"
        print(f"  {f'{int(lo)} to {int(hi)} bars':<20}{shown}")
        out["gate_by_age"].append({"from": float(lo), "to": float(hi),
                                   "touch1": cells[0], "later": cells[1]})

    # --- SECONDARY: touch number at decision time, inside equal age -----------
    print("\n  TOUCH NUMBER INSIDE EQUAL AGE, gated zones only   (the freshness"
          " claim, read at the moment of the touch)")
    print(f"  {'age at touch':<20}" + "".join(
        f"{f'touch {k}':>11}" for k in (1, 2, 3)) + f"{'touch 4+':>11}    n per cell")
    out["touch_by_age"] = []
    for lo, hi, last in bands:
        cells, counts = [], []
        for want in (1, 2, 3, 4):
            picked = [
                r["held"] for r in rows
                if r["gated"] and in_band(r, (lo, hi, last))
                and (r["touch"] == want if want < 4 else r["touch"] >= 4)
            ]
            counts.append(len(picked))
            cells.append(
                float(np.mean(picked)) if len(picked) >= MIN_SHOW else float("nan")
            )
        shown = "".join(
            "      -    " if np.isnan(c) else f"{c:>11.1%}" for c in cells
        )
        print(f"  {f'{int(lo)} to {int(hi)} bars':<20}{shown}   n={counts}")
        out["touch_by_age"].append({"from": float(lo), "to": float(hi),
                                    "held": cells, "n": counts})

    # --- BY SIDE, pooled and at later touches --------------------------------
    # Demand and supply separately, because the gate is side-blind and therefore
    # MUST agree across sides. This is where a real filter and an artefact of a
    # drifting sample part company.
    print("\n  BY SIDE   the gate is side-blind, so both sides must move together")
    print(f"  {'':<12}{'kept n':>8}{'kept':>10}{'cut n':>8}{'cut':>10}"
          f"{'edge':>7}   two-proportion test")
    out["by_side"] = {}
    for side in ("demand", "supply"):
        for name, picked in (
            (f"{side} t1", [r for r in rows if r["side"] == side and r["touch"] == 1]),
            (f"{side} t2+", [r for r in later if r["side"] == side]),
        ):
            out["by_side"][name] = gate_line(name, picked)

    # --- BY SERIES, because a pooled result can live in one instrument --------
    print("\n  BY SERIES at touch >= 2")
    print(f"  {'':<12}{'kept n':>8}{'kept':>10}{'cut n':>8}{'cut':>10}"
          f"{'edge':>7}   two-proportion test")
    out["by_series"] = {}
    for label in dict.fromkeys(r["series"] for r in rows):
        picked = [r for r in later if r["series"] == label]
        if len(picked) < MIN_SHOW:
            continue
        out["by_series"][label] = gate_line(label.replace("yahoo:", "y:"), picked)

    return out


def verdict(everything: dict) -> None:
    """The four primary criteria and the secondary one, scored as written above.

    Printed by the tool rather than read off the tables by a human, because the
    bar was fixed in the docstring before any of these numbers existed and this
    is the only way the reader can see it was not moved afterwards.
    """
    print(f"\n{'=' * 96}")
    print("VERDICT AGAINST THE PRE-REGISTERED BAR")
    print(f"{'=' * 96}")

    primary = []
    for reward in (1.0, 2.0):
        block = everything.get(f"atr{reward}_h80") or {}
        later = block.get("gate_later") or {}
        edge, usable = later.get("edge", float("nan")), later.get("usable", False)
        ok_1 = not np.isnan(edge) and edge >= 0.05
        ok_2 = usable and "SIGNIFICANT" in str(later.get("test"))
        surviving = sum(
            1 for band in block.get("gate_by_age", [])
            if band["later"]["usable"] and band["later"]["edge"] >= 0.05
        )
        ok_3 = surviving >= 2
        sides = [
            (block.get("by_side") or {}).get(f"{s} t2+", {}).get("edge", float("nan"))
            for s in ("demand", "supply")
        ]
        ok_4 = all(not np.isnan(s) and s > 0 for s in sides)
        primary.append(all((ok_1, ok_2, ok_3, ok_4)))
        print(
            f"  reward {reward} ATR   edge {edge:+.1%} ({'>=5pp' if ok_1 else 'under 5pp'})"
            f", {'significant' if ok_2 else 'not significant or cohort too small'}"
            f", {surviving}/3 age bands, sides "
            f"{'agree' if ok_4 else 'DISAGREE or one is unmeasurable'}"
        )
    print(f"  -> PRIMARY: the departure gate {'STILL SEPARATES' if all(primary) else 'does NOT clear the bar'}"
          " at touch 2 and later.")

    secondary = []
    for reward in (1.0, 2.0):
        block = everything.get(f"atr{reward}_h80") or {}
        drops = []
        for band in block.get("touch_by_age", []):
            first, second = band["held"][0], band["held"][1]
            n_ok = band["n"][0] >= MIN_CONCLUDE and band["n"][1] >= MIN_CONCLUDE
            drops.append(
                n_ok and not np.isnan(first) and not np.isnan(second)
                and first - second >= 0.05
            )
        secondary.append(bool(drops) and all(drops))
        print(f"  reward {reward} ATR   touch 1 beats touch 2 by >=5pp in "
              f"{sum(drops)}/{len(drops)} age bands")
    print(f"  -> SECONDARY: freshness at decision time "
          f"{'CONFIRMED' if all(secondary) else 'NOT CONFIRMED'}"
          " once age is held fixed.")

    # POST-HOC, and only readable as a diagnostic. If the sign of the later-touch
    # gate edge FLIPS between the ATR bracket and the equal-R one, the edge is
    # the zone's height being graded two different ways, not the gate.
    pair = [
        ((everything.get(key) or {}).get("gate_later") or {}).get("edge", float("nan"))
        for key in ("atr2.0_h80", "r2.0_h80")
    ]
    if not any(np.isnan(v) for v in pair):
        flips = pair[0] * pair[1] < 0
        print(
            f"\n  POST-HOC, two brackets at touch >= 2: ATR {pair[0]:+.1%},"
            f" equal-R {pair[1]:+.1%} -> "
            + ("SIGN FLIPS, so this is zone height and not the gate"
               if flips else "same sign under both brackets, so not height alone")
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    params = SupplyDemandParams(**POPULATION)
    print("Loading history (cached; this machine cannot reach Binance or Dukascopy)")
    loaded = [(f"{s}-{tf}", history.load(s, tf, args.bars)) for s, tf in SERIES]
    for label, candles in loaded:
        print(f"  {label:<18}{len(candles)} bars")

    everything: dict = {}
    for mode, reward, horizon in PLAN:
        rows: list[dict] = []
        for label, candles in loaded:
            rows.extend(collect(candles, params, reward, horizon, label, mode))
        everything[f"{mode}{reward}_h{horizon}"] = report(
            rows, reward, horizon, mode
        )

    verdict(everything)

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(everything, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


def demo() -> None:
    """One runnable check on the only logic here that can silently lie.

    The cells are the whole tool, so what has to be true is that a row lands in
    the band and column it belongs to, and that a cohort under the floor is
    refused rather than printed. Two synthetic rows do that.
    """
    rows = [
        {"series": "x", "side": "demand", "touch": 1, "age": 5, "held": True,
         "gated": True, "index": 10}
    ] * 300
    rows += [
        {"series": "x", "side": "supply", "touch": 3, "age": 500, "held": False,
         "gated": False, "index": 900}
    ] * 300
    out = report(rows, 1.0, 80)
    assert out["gate_by_touch"][1]["kept_n"] == 300, out["gate_by_touch"]
    assert out["gate_by_touch"][1]["cut_n"] == 0
    # A cell with one empty cohort must not produce an edge.
    assert np.isnan(out["gate_by_touch"][1]["edge"])
    assert out["gate_by_touch"][1]["usable"] is False
    # The touch-3 rows are all ungated, so the gated-only touch table is empty
    # for them and every cell there is refused.
    assert all(np.isnan(c) for band in out["touch_by_age"] for c in band["held"][1:])
    print("demo ok")


if __name__ == "__main__":
    main()
