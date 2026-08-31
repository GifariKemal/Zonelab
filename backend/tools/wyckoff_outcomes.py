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
significant NEGATIVE t is TERBALIK.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys

import numpy as np

from app.indicators import wilder_atr
from app.wyckoff import phases
from tools.conditioned import _critical_t
from tools.quant import clean

#: The direction each phase claims: +1 up, -1 down.
DIRECTION = {"spring": +1, "sos": +1, "upthrust": -1, "sow": -1}

HORIZON = 96  # bars of forward move, the reach horizon the layers use
K = 4         # four phase kinds judged
MIN_GROUP = 30

SYMBOLS = ("XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
           "AUDUSD", "US30", "USOIL")


def _move(close: np.ndarray, atr: np.ndarray, i: int):
    if i + HORIZON >= len(close) or atr[i] <= 0:
        return None
    return float(close[i + HORIZON] - close[i]) / float(atr[i])


def study(symbols: list[str], interval: str = "1h") -> dict:
    by_kind: dict[str, list[float]] = {k: [] for k in DIRECTION}
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
            # Excess move in the claimed direction, over the symbol's own drift.
            by_kind[p.kind].append(DIRECTION[p.kind] * (m - drift))
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
        "cells": per_symbol,
    }
    for kind in DIRECTION:
        vals = by_kind[kind]
        if len(vals) < MIN_GROUP:
            out["phases"][kind] = {"n": len(vals), "verdict": "n kecil"}
            continue
        a = np.array(vals)
        mean = float(a.mean())
        se = float(a.std(ddof=1) / math.sqrt(len(a)))
        t = float(mean / se) if se > 0 else float("nan")
        verdict = ""
        if abs(t) >= critical:
            verdict = "MEMPREDIKSI" if t > 0 else "TERBALIK"
        out["phases"][kind] = {
            "n": len(a), "mean_excess_move_atr": mean, "t": t,
            "verdict": verdict,
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, args.interval)
    json.dump(out, sys.stdout, indent=2, default=float)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
