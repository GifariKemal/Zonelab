"""Does a CISD inside an order block predict the block's direction? (praregistrasi)

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.csid_ob_outcomes > ../docs/csid_ob_outcomes.json

The owner's first ask: "RETEST CSID korelasi ke OB". This measures whether an
order block whose band contains a CISD level resolves in the block's own
direction more than an order block without one, over the symbol's drift.

PRIOR, and it is strong. `cisd_in_band` is already measured NULL for the
supply/demand box (t=-1.29, `docs/checklist_outcomes.json`), and a CISD as a
standalone direction claim is NULL (t=-0.53, `app/layers.py`). So the prior for
an order block with a CISD inside adding signal is low, and it is stated.

OUTCOME. Forward move in ATR at a fixed horizon, signed by the block's side, minus
the symbol's own drift. A DIRECTION study, not a trade-plan study: the block
claims which way price leaves it, so the resolved R multiple is the wrong
instrument. Forward move from the block's right edge (`time_to`) is the origin.

HYPOTHESIS, two-sided. The mean excess signed move of blocks WITH a CISD inside
differs from blocks WITHOUT one. Two-sided because a CISD inside a block could
read as confirmation or as the block already being mitigated.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys

import numpy as np

from app.cisd import cisds
from app.detect import DETECTORS
from app.indicators import wilder_atr
from app.models import ImbalanceParams, ZoneSide
from tools.conditioned import _critical_t
from tools.quant import clean

HORIZON = 96
MIN_GROUP = 30
SYMBOLS = ("XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
           "AUDUSD", "US30", "USOIL")


def study(symbols: list[str], interval: str = "1h") -> dict:
    inside: list[float] = []
    outside: list[float] = []
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
        times = [c.time for c in candles]
        close = np.array([c.close for c in candles], dtype=np.float64)
        high = np.array([c.high for c in candles], dtype=np.float64)
        low = np.array([c.low for c in candles], dtype=np.float64)
        atr = wilder_atr(high, low, close, 14)

        # Symbol drift, from a sparse sample.
        sample = [i for i in range(0, len(candles), max(1, len(candles) // 2000))]
        moves = [(close[i + HORIZON] - close[i]) / atr[i]
                 for i in sample if i + HORIZON < len(candles) and atr[i] > 0]
        drift = float(np.mean(moves)) if moves else 0.0

        blocks, _ = DETECTORS["order_block"](
            candles, ImbalanceParams(show_broken=True, max_zones_per_side=0))
        events, _ = cisds(candles)

        for b in blocks:
            # Find the block's right edge index, to measure the forward move from.
            if b.time_to not in times:
                continue
            i = times.index(b.time_to)
            if i + HORIZON >= len(candles) or atr[i] <= 0:
                continue
            side = +1 if b.side is ZoneSide.DEMAND else -1
            move = (close[i + HORIZON] - close[i]) / atr[i]
            excess = side * (move - drift)
            in_band = any(
                b.bottom <= e.level <= b.top and e.time <= b.time_to
                for e in events
            )
            (inside if in_band else outside).append(excess)

        per_symbol[symbol] = {
            "n_blocks": len(blocks),
            "drift_atr": drift,
            "n_cisd_inside": sum(
                1 for b in blocks if any(b.bottom <= e.level <= b.top and e.time <= b.time_to for e in events)
            ),
        }

    out: dict = {
        "preregistered": "tools/csid_ob_outcomes.py, 2026-08-31",
        "question": "apakah CISD di dalam order block memprediksi arah block, di atas drift",
        "horizon_bars": HORIZON,
        "critical_t": _critical_t(2),
        "min_group": MIN_GROUP,
        "cells": per_symbol,
    }
    n_in, n_out = len(inside), len(outside)
    out["population"] = {"n_cisd_inside": n_in, "n_no_cisd": n_out}
    if n_in < MIN_GROUP or n_out < MIN_GROUP:
        out["verdict"] = "n kecil"
        return out
    a, b = np.array(inside), np.array(outside)
    delta = float(a.mean() - b.mean())
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    t = float(delta / se) if se > 0 else float("nan")
    out["result"] = {
        "exp_excess_in_band": float(a.mean()),
        "exp_excess_no_cisd": float(b.mean()),
        "delta": delta, "t": t,
    }
    out["verdict"] = (
        "MEMISAHKAN" if abs(t) >= _critical_t(2) else ""
    )
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
