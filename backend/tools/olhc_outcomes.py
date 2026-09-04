"""Does a candle's rejection shape say which extreme it visited first?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.olhc_outcomes > ../docs/olhc_outcomes.json

WHY THIS ONE AND NOT THE OTHER FIVE. `docs/PRAREGISTRASI-YATIM.md` measured the
orphan modules on 28 August 2026 and every one of them has a number already:
`in_judas_window` t=0,27, `judas_template` |t| at most 0,23, `psp_before_touch`
t=0,09, and tCISD, z-score and regime were answered before that document and
excluded from its list for exactly that reason. `app/ladder.py` was declared not testable as a signal (lookup table, no market
input) and was removed on 4 September 2026 after confirming zero callers outside
its own test file.

`app/olhc.py` is the one that was never on that list. It has no column in
`tools/conditioned.py`'s closed list, no evidence file, and one unit test.

EVERYTHING BELOW THIS LINE WAS FIXED BEFORE A NUMBER WAS COMPUTED.

## 1. The claim, in the module's own words

"OHLC bars cannot say the ORDER a candle visited its extremes in - that needs
tick data. What a bar CAN say is which side it REJECTED, from the close position
and the wick split: accumulation, closed in the upper half with a longer lower
wick - swept down and was bought, THE SHAPE BEHIND THE OLHC READING."

That is a falsifiable claim about visit order, and it is checkable without tick
data: five-minute bars inside the hour say which extreme printed first. The
module says it cannot know the order and then names a shape that implies one.
This asks whether the shape is right.

## 2. Two hypotheses, and section 3 withdraws the first

H_ORDER: on a bar classified `accumulation`, did the LOW print before the HIGH
more often than on a bar that is not classified accumulation? Mirror for
`distribution` and the high.

H_DIRECTION: does the forward move in the claimed direction - accumulation up,
distribution down - beat the instrument's own drift?

## 3. The control, and the naive one is reported but not judged

CLOSE POSITION ALONE NEARLY ANSWERS H_ORDER, so comparing against neutral bars
would measure something close to a tautology. A bar that closes near its high
ends near that high, so the high is more likely the last extreme it visited,
whichever wick is longer. `accumulation` requires a close in the upper half BY
DEFINITION, so an unmatched comparison hands it that advantage for free.

The judged control is therefore STRATIFIED ON CLOSE POSITION: each accumulation
bar is compared against the non-accumulation bars in its own close-position
decile, and the per-stratum differences are pooled weighted by the event count.
What that isolates is the WICK's contribution, which is the only part of the
rule that is not already in the close.

The unmatched comparison against every other bar is still computed and reported
as `order_unmatched`, never judged, so the size of the confound is visible
rather than asserted.

## 4. Independence

H_ORDER needs no clustering: the answer for a bar is settled inside that bar and
no two observations share a window. H_DIRECTION reads 96 bars forward from every
event, which overlaps heavily, so it uses
`tools.wyckoff_outcomes.clustered_t` for the same reason that file does.

## 5. Fixed parameters, no search

  coarse      1h, the bar being classified
  fine        5m, the bars that settle the order, 12 per hour
  instruments XAUUSD XAGUSD XPTUSD EURUSD GBPUSD USDJPY AUDUSD US30 USOIL
  horizon     96 bars for H_DIRECTION
  strata      close position in deciles
  min group   30 per judged cell, and 10 per stratum before it contributes
  ties        an hour whose high and low print in the SAME 5m bar is DROPPED and
              counted: the finer bars cannot order it either

## 6. Pass conditions

  1. n >= 30 in the event arm.
  2. |t| past the Bonferroni bar for K, computed before one result line. K counts
     the DIRECTION cells only, because section 3 withdrew the order question and
     an unjudged number must not spend the budget.
  3. Reported per instrument, so a pooled result that is one instrument wearing
     a general name can be seen for what it is.

## 7. What is not promised

Five-minute bars are not ticks. An hour whose extremes fall in the same 5m bar
is unorderable here and is dropped rather than guessed, and that drop is not
random: it is more common on quiet hours. Nine instruments, one broker, about
seventeen months of 5m history.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from statistics import NormalDist

import numpy as np

from app.indicators import wilder_atr
from app.olhc import classify
from tools import history
from tools.wyckoff_outcomes import clustered_t

COARSE = "1h"
FINE = "5m"
FINE_PER_COARSE = 12
HORIZON = 96
STRATA = 10          # close-position deciles
MIN_GROUP = 30
MIN_STRATUM = 10
ALPHA = 0.05
_NORM = NormalDist()

SYMBOLS = ("XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
           "AUDUSD", "US30", "USOIL")

#: The direction each kind claims: accumulation was bought, distribution sold.
DIRECTION = {"accumulation": +1, "distribution": -1}


def first_extreme(fine: list) -> str | None:
    """Which of the two extremes printed first inside this hour.

    "low", "high", or None when both fall in the same 5m bar - the finer bars
    cannot order those either, so they are dropped rather than guessed.
    """
    if len(fine) < 2:
        return None
    lo = min(range(len(fine)), key=lambda i: fine[i].low)
    hi = max(range(len(fine)), key=lambda i: fine[i].high)
    if lo == hi:
        return None
    return "low" if lo < hi else "high"


def stratified(events: list[tuple[int, bool]], controls: list[tuple[int, bool]]):
    """Weighted within-stratum difference of two rates, and its z.

    Each entry is (stratum index, outcome). Strata with fewer than
    `MIN_STRATUM` on either side are skipped and counted, because a stratum
    holding two bars states nothing and would swing the weighted mean.
    """
    e_by: dict[int, list[bool]] = {}
    c_by: dict[int, list[bool]] = {}
    for s, v in events:
        e_by.setdefault(s, []).append(v)
    for s, v in controls:
        c_by.setdefault(s, []).append(v)

    used = weight_sum = diff_sum = var_sum = 0
    skipped = 0
    for s, evals in e_by.items():
        cvals = c_by.get(s, [])
        if len(evals) < MIN_STRATUM or len(cvals) < MIN_STRATUM:
            skipped += len(evals)
            continue
        pe = sum(evals) / len(evals)
        pc = sum(cvals) / len(cvals)
        w = len(evals)
        used += w
        weight_sum += w
        diff_sum += w * (pe - pc)
        var_sum += (w ** 2) * (
            pe * (1 - pe) / len(evals) + pc * (1 - pc) / len(cvals)
        )
    if weight_sum == 0:
        return None, None, 0, skipped
    delta = diff_sum / weight_sum
    se = math.sqrt(var_sum) / weight_sum
    return delta, (delta / se if se > 0 else float("nan")), used, skipped


def study(symbols: list[str], bars: int) -> dict:
    order_rows: dict[str, dict[str, list]] = {
        k: {"event": [], "control": [], "event_flat": [], "control_flat": []}
        for k in DIRECTION
    }
    dir_rows: dict[str, list] = {k: [] for k in DIRECTION}
    per_symbol: dict[str, dict] = {}

    for symbol in symbols:
        try:
            coarse = history.load(f"mt5:{symbol}", COARSE, bars)
            fine = history.load(f"mt5:{symbol}", FINE, 99_999)
        except Exception as exc:  # noqa: BLE001
            per_symbol[symbol] = {"error": str(exc)}
            continue
        if len(coarse) < HORIZON * 4 or len(fine) < 1000:
            per_symbol[symbol] = {"note": "too short"}
            continue

        # The 5m bars of each hour, by the hour's own open time.
        step = 3600
        buckets: dict[int, list] = {}
        for bar in fine:
            buckets.setdefault(bar.time - (bar.time % step), []).append(bar)

        close = np.array([c.close for c in coarse], dtype=np.float64)
        high = np.array([c.high for c in coarse], dtype=np.float64)
        low = np.array([c.low for c in coarse], dtype=np.float64)
        atr = wilder_atr(high, low, close, 14)
        sample = [
            float(close[i + HORIZON] - close[i]) / float(atr[i])
            for i in range(0, len(coarse) - HORIZON, max(1, len(coarse) // 2000))
            if atr[i] > 0
        ]
        drift = float(np.mean(sample)) if sample else 0.0

        counts = {"accumulation": 0, "distribution": 0, "neutral": 0,
                  "orderable": 0, "unorderable": 0}
        for i, bar in enumerate(coarse):
            kind, close_pos, _, _ = classify(bar)
            counts[kind] += 1

            # H_DIRECTION: every classified bar with a full forward window.
            if kind in DIRECTION and i + HORIZON < len(coarse) and atr[i] > 0:
                move = float(close[i + HORIZON] - close[i]) / float(atr[i])
                dir_rows[kind].append(
                    (symbol, i, DIRECTION[kind] * (move - drift))
                )

            # H_ORDER: only hours the finer bars can actually order.
            inside = buckets.get(bar.time - (bar.time % step), [])
            if len(inside) < FINE_PER_COARSE // 2:
                continue
            first = first_extreme(inside)
            if first is None:
                counts["unorderable"] += 1
                continue
            counts["orderable"] += 1
            stratum = min(STRATA - 1, int(close_pos * STRATA))
            for claim, wanted in (("accumulation", "low"), ("distribution", "high")):
                hit = first == wanted
                arm = "event" if kind == claim else "control"
                order_rows[claim][arm].append((stratum, hit))
                order_rows[claim][f"{arm}_flat"].append(hit)
        per_symbol[symbol] = {"bars": len(coarse), "drift_atr": drift, **counts}

    # K BEFORE ONE RESULT LINE.
    k = 0
    for kind in DIRECTION:
        if len(dir_rows[kind]) >= MIN_GROUP:
            k += 1
    critical_z = _NORM.inv_cdf(1 - ALPHA / max(k, 1) / 2) if k else float("inf")

    out: dict = {
        "preregistered": "tools/olhc_outcomes.py, 2026-09-01",
        "identity": (
            "classify() is a deterministic relabelling of (open_pos, "
            "close_pos): lower_wick/R = min(o,c) and upper_wick/R = 1-max(o,c), "
            "so no control can hold both fixed and still vary the class. The "
            "order question is withdrawn, see section 3."
        ),
        "question": "apakah bentuk penolakan lilin menyatakan ekstrem mana yang lebih dulu",
        "coarse": COARSE, "fine": FINE, "horizon_bars": HORIZON,
        "strata": STRATA, "cells_judged": k,
        "critical_z": round(critical_z, 4),
        "kinds": {},
        "cells": per_symbol,
    }
    for kind in DIRECTION:
        block: dict = {}
        ev = order_rows[kind]["event"]
        ct = order_rows[kind]["control"]
        if len(ev) >= MIN_GROUP:
            delta, z, used, skipped = stratified(ev, ct)
            block["order_close_only"] = {
                "n_event": len(ev), "n_control": len(ct),
                "n_used": used, "n_skipped_thin_stratum": skipped,
                "delta": None if delta is None else round(delta, 4),
                "z": None if z is None else round(z, 3),
                "verdict": "TIDAK DINILAI, open position belum dikontrol dan "
                           "tidak bisa dikontrol tanpa mengosongkan kontrasnya",
            }
            # The unmatched comparison, reported so the confound has a size.
            e = order_rows[kind]["event_flat"]
            c = order_rows[kind]["control_flat"]
            pe, pc = sum(e) / len(e), sum(c) / len(c)
            block["order_unmatched"] = {
                "event_rate": round(pe, 4), "control_rate": round(pc, 4),
                "delta": round(pe - pc, 4),
                "verdict": "TIDAK DINILAI, close position belum dikontrol",
            }
        else:
            block["order_close_only"] = {"n_event": len(ev), "verdict": "n kecil"}

        recs = dir_rows[kind]
        if len(recs) >= MIN_GROUP:
            vals = [v for _, _, v in recs]
            t, n_eff = clustered_t(vals, [(s, i // HORIZON) for s, i, _ in recs])
            verdict = "null"
            if not math.isnan(t) and abs(t) >= critical_z:
                verdict = "MEMISAHKAN" if t > 0 else "MEMISAHKAN, TANDA TERBALIK"
            block["direction"] = {
                "n": len(vals), "mean_excess_move_atr": round(float(np.mean(vals)), 4),
                "t": round(t, 3), "n_effective": round(n_eff, 0),
                "verdict": verdict,
            }
        else:
            block["direction"] = {"n": len(recs), "verdict": "n kecil"}
        out["kinds"][kind] = block
    return out


def selfcheck() -> int:
    """The two primitives, on bars whose answer is known in advance."""
    from app.models import Candle

    def bar(o, h, low_, c, t=0):
        return Candle(time=t, open=o, high=h, low=low_, close=c, volume=0.0)

    # The low is in bar 0, the high in bar 2, so the low printed first.
    assert first_extreme([bar(10, 11, 8, 10), bar(10, 11, 9, 10),
                          bar(10, 15, 10, 14)]) == "low"
    assert first_extreme([bar(10, 15, 10, 14), bar(10, 11, 9, 10),
                          bar(10, 11, 8, 10)]) == "high"
    # Both extremes in ONE bar cannot be ordered and must be dropped.
    assert first_extreme([bar(10, 20, 1, 15), bar(10, 11, 9, 10)]) is None
    assert first_extreme([bar(10, 11, 9, 10)]) is None

    # The stratified difference: a control that is identical inside every
    # stratum must give exactly zero, even when the RAW rates differ because the
    # two arms sit in different strata. That is the confound the design exists
    # to remove, so it is the case the gate has to hold.
    events = [(0, True)] * 20 + [(1, False)] * 20
    controls = [(0, True)] * 20 + [(1, False)] * 20
    delta, _z, used, _ = stratified(events, controls)
    assert delta == 0.0, delta
    assert used == 40
    # And a real within-stratum difference survives.
    events2 = [(0, True)] * 20 + [(0, False)] * 0
    controls2 = [(0, False)] * 20
    delta2, _z2, _, _ = stratified(events2, controls2)
    assert delta2 == 1.0, delta2
    # A stratum too thin on either side is skipped, not counted.
    thin = [(5, True)] * 3
    d3, _, used3, skipped3 = stratified(thin, [(5, False)] * 50)
    assert used3 == 0 and skipped3 == 3 and d3 is None
    # THE IDENTITY THIS STUDY TURNS ON, checked rather than argued. If
    # `classify` ever stops being a function of (open_pos, close_pos) alone,
    # section 3 is wrong and the order question comes back.
    rng = np.random.default_rng(11)
    for _ in range(20_000):
        o = float(rng.uniform())
        c = float(rng.uniform())
        kind, _, lw, uw = classify(bar(o, 1.0, 0.0, c))
        closed_form = (
            "accumulation" if c >= 0.5 and min(o, c) > 1 - max(o, c)
            else "distribution" if c < 0.5 and 1 - max(o, c) > min(o, c)
            else "neutral"
        )
        assert kind == closed_form, (o, c, kind, closed_form)
        assert abs(lw - min(o, c)) < 1e-12 and abs(uw - (1 - max(o, c))) < 1e-12
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--bars", type=int, default=20_000)
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()
    if args.selfcheck:
        return selfcheck()
    selfcheck()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, args.bars)
    json.dump(out, sys.stdout, indent=2, default=float)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
