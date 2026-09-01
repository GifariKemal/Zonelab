"""Does a Wyckoff phase precede the directional move it names? (praregistrasi)

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.wyckoff_outcomes > ../docs/wyckoff_outcomes.json

The four determinable Wyckoff phases claim a direction: spring and sign-of-
strength are bullish (swept low / broke up), upthrust and sign-of-weakness are
bearish. This measures whether the forward move after each phase actually carries
the claimed sign, against the instrument's own drift.

PRIOR. These phases map onto the structure primitives (sweep, break) that H6 and
H9 already measured NULL as direction claims, so the prior is low, and it is
stated rather than hidden.

OUTCOME. Forward move in ATR at a fixed horizon, signed by the phase's claimed
direction. A DIRECTION study, like `tools/mss.py`, not a trade-plan study: a
phase claims where price goes, not whether a target beats a stop, so the resolved
R multiple is the wrong instrument. Coarse 1h bars are sufficient for a forward
move (no target/stop ambiguity), which is why this runs in seconds.

HYPOTHESIS, two-sided. The mean EXCESS forward move after a phase - forward move
minus the symbol's own drift - differs from zero, in the phase's claimed
direction. Two-sided because a phase that predicts the OPPOSITE direction is the
inverted result `dfr_side` produced, and it is a finding, not a null.

WHY THE DRIFT CONTROL, and it is the whole point. These instruments trend: the
first run of this harness tested the signed move against ZERO and reported
spring MEMPREDIKSI at t=+6.6 while the base rate sat at +0.51 ATR - so the phase
was being credited for an upward drift it did not cause. A phase must beat its
symbol's drift, not zero. The excess move is that difference, and the first run
was a defect, corrected here.

SYARAT LOLOS. n >= 30 per kind, |t| past the Bonferroni bar for four kinds
(`tools.conditioned._critical_t`). A significant POSITIVE t is MEMPREDIKSI; a
significant NEGATIVE t is TERBALIK. The t that is judged is the CLUSTERED one,
for the reason below.

TWO DEFECTS FOUND AND CLOSED 1 SEPTEMBER 2026, both of which would have mattered
only when a result came out positive - which is exactly when an instrument has to
be right.

  1. THE STANDARD ERROR ASSUMED INDEPENDENT EVENTS AND THEY OVERLAP. The forward
     window is 96 bars and events fire on about one bar in five, so consecutive
     events share more than 90 of their 96 forward bars. Measured on this data
     the variance inflation is about 6,5x: `sos` read t=-2,43 naive against
     t=-0,95 clustered, and its effective n is near 3000, not 19 667. Both are
     reported now and the verdict reads the clustered one.

  2. THE WALK-FORWARD FOLDS MIXED SYMBOLS WITH TIME. The folds were cut from all
     nine symbols pooled and sorted by wall clock, and the histories do not begin
     together: USOIL starts 2017 and everything else 2020-12, so fold 0 was 60
     per cent USOIL (5170 of 8684) over 2017-2021 while fold 3 was nine symbols
     over ten months. The folds are cut INSIDE each symbol now and the verdicts
     summed, so one fold means one thing.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys

import numpy as np

from collections import defaultdict

from app.indicators import wilder_atr
from app.wyckoff import phases
from tools.conditioned import _critical_t
from tools.quant import clean

#: The direction each phase claims: +1 up, -1 down.
DIRECTION = {"spring": +1, "sos": +1, "upthrust": -1, "sow": -1}

HORIZON = 96  # bars of forward move, the reach horizon the layers use
K = 4         # four phase kinds judged
MIN_GROUP = 30
FOLDS = 4     # walk-forward time folds, cut inside each symbol
MIN_FOLD = 20

SYMBOLS = ("XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
           "AUDUSD", "US30", "USOIL")


def _move(close: np.ndarray, atr: np.ndarray, i: int):
    if i + HORIZON >= len(close) or atr[i] <= 0:
        return None
    return float(close[i + HORIZON] - close[i]) / float(atr[i])


def clustered_t(values, clusters):
    """`t` for the mean and the effective n, with overlapping windows clustered.

    A cluster is one symbol and one block of `HORIZON` bars, so two events whose
    forward windows overlap land in the same cluster and cannot both count as
    independent evidence. Standard CR0 sandwich for the sample mean with the
    usual g/(g-1) correction. Returns (t, n_effective), where n_effective is the
    nominal n divided by the variance inflation the clustering exposes.
    """
    a = np.asarray(values, dtype=np.float64)
    mean = float(a.mean())
    naive_se = float(a.std(ddof=1) / math.sqrt(len(a)))
    groups = defaultdict(float)
    for key, v in zip(clusters, values):
        groups[key] += v - mean
    g = len(groups)
    if g < 2 or naive_se <= 0:
        return float("nan"), float(len(a))
    resid = np.fromiter(groups.values(), dtype=np.float64, count=g)
    se = math.sqrt(float((resid ** 2).sum()) / len(a) ** 2) * math.sqrt(g / (g - 1))
    if se <= 0:
        return float("nan"), float(len(a))
    inflation = (se / naive_se) ** 2
    return mean / se, (len(a) / inflation if inflation > 0 else float(len(a)))


def study(symbols: list[str], interval: str = "1h") -> dict:
    # (symbol, bar index, excess move) per phase kind.
    by_kind: dict[str, list[tuple[str, int, float]]] = {k: [] for k in DIRECTION}
    per_symbol: dict[str, dict] = {}
    for symbol in symbols:
        try:
            candles, _, _ = clean(symbol, interval)
        except Exception as exc:
            per_symbol[symbol] = {"error": str(exc)}
            continue
        if not candles:
            per_symbol[symbol] = {"n": 0}
            continue
        high = np.array([c.high for c in candles], dtype=np.float64)
        low = np.array([c.low for c in candles], dtype=np.float64)
        close = np.array([c.close for c in candles], dtype=np.float64)
        atr = wilder_atr(high, low, close, 14)

        # The symbol's own drift, from a sparse sample of bars.
        sample = [i for i in range(0, len(candles), max(1, len(candles) // 2000))]
        moves = [m for m in (_move(close, atr, i) for i in sample) if m is not None]
        drift = float(np.mean(moves)) if moves else 0.0

        events = phases(candles, lookback=20)
        for p in events:
            m = _move(close, atr, p.at)
            if m is None:
                continue
            # Excess move in the claimed direction, over the symbol's own drift,
            # tagged with symbol and bar index: the symbol so the folds can be cut
            # inside it, the index so overlapping forward windows can be clustered.
            by_kind[p.kind].append(
                (symbol, p.at, DIRECTION[p.kind] * (m - drift)))
        per_symbol[symbol] = {"n_events": len(events), "drift_atr": drift}

    critical = _critical_t(K)
    out: dict = {
        "preregistered": "tools/wyckoff_outcomes.py, 2026-08-31",
        "question": "apakah fase Wyckoff mendahului move arah yang ia namai, di atas drift",
        "horizon_bars": HORIZON,
        "critical_t": critical,
        "min_group": MIN_GROUP,
        "control": "excess move = forward move - symbol drift",
        "phases": {},
        "walk_forward": {},
        "cells": per_symbol,
    }
    for kind in DIRECTION:
        rows = by_kind[kind]
        vals = [v for _, _, v in rows]
        if len(vals) < MIN_GROUP:
            out["phases"][kind] = {"n": len(vals), "verdict": "n kecil"}
            continue
        a = np.array(vals)
        mean = float(a.mean())
        se = float(a.std(ddof=1) / math.sqrt(len(a)))
        t_naive = float(mean / se) if se > 0 else float("nan")
        t_cl, n_eff = clustered_t(vals, [(sym, i // HORIZON) for sym, i, _ in rows])
        verdict = ""
        if not math.isnan(t_cl) and abs(t_cl) >= critical:
            verdict = "MEMPREDIKSI" if t_cl > 0 else "TERBALIK"
        out["phases"][kind] = {
            "n": len(a), "mean_excess_move_atr": mean,
            "t_naive": t_naive, "t": t_cl, "n_effective": n_eff,
            "verdict": verdict,
        }
        # Walk-forward: folds cut INSIDE each symbol, so a fold is one stretch of
        # one instrument and never a mixture of whichever histories reach back
        # furthest. The headline is how many carry the claimed sign.
        per_symbol = {}
        positive = graded = 0
        for symbol in symbols:
            mine = sorted([r for r in rows if r[0] == symbol], key=lambda r: r[1])
            if len(mine) < MIN_FOLD * FOLDS:
                continue
            size = len(mine) // FOLDS
            signs = []
            for f in range(FOLDS):
                part = mine[f * size:(f + 1) * size if f < FOLDS - 1 else len(mine)]
                if len(part) < MIN_FOLD:
                    signs.append(None)
                    continue
                signs.append(float(np.mean([v for _, _, v in part])))
            per_symbol[symbol] = signs
            positive += sum(1 for x in signs if x is not None and x > 0)
            graded += sum(1 for x in signs if x is not None)
        out["walk_forward"][kind] = {
            "folds_per_symbol": per_symbol,
            "positive_folds": positive,
            "graded_folds": graded,
        }
    return out


def selfcheck() -> int:
    """The clustering arithmetic, on data whose answer is known in advance.

    Two cases, and the second is the one that matters. Independent draws must
    leave the clustered t roughly where the naive t already was. The SAME draws
    duplicated k times inside their cluster carry no new information, so the
    naive t must rise by about sqrt(k) while the clustered t stays put and the
    effective n falls back to the number of distinct draws. That is exactly the
    shape of the overlapping-window defect this function was written to close.
    """
    rng = np.random.default_rng(7)
    base = list(rng.normal(0.05, 1.0, 2000))

    # One event per cluster: nothing to correct.
    solo = [(i, 0) for i in range(len(base))]
    t_solo, n_solo = clustered_t(base, solo)
    naive = float(np.mean(base) / (np.std(base, ddof=1) / math.sqrt(len(base))))
    assert abs(t_solo - naive) < 0.15 * abs(naive), (t_solo, naive)
    assert abs(n_solo - len(base)) < 0.25 * len(base), (n_solo, len(base))

    # Each draw repeated eight times inside its own cluster: no new information.
    k = 8
    dup = [v for v in base for _ in range(k)]
    keys = [(i, 0) for i in range(len(base)) for _ in range(k)]
    t_dup_naive = float(np.mean(dup) / (np.std(dup, ddof=1) / math.sqrt(len(dup))))
    t_dup, n_dup = clustered_t(dup, keys)
    assert t_dup_naive > 2.2 * abs(t_solo), (t_dup_naive, t_solo)
    assert abs(t_dup - t_solo) < 0.15 * abs(t_solo), (t_dup, t_solo)
    assert abs(n_dup - len(base)) < 0.25 * len(base), (n_dup, len(base))
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()
    if args.selfcheck:
        return selfcheck()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, args.interval)
    json.dump(out, sys.stdout, indent=2, default=float)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
