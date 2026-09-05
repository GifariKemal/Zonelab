"""Statistik trade-level pure FVG, OLD vs NEW param, XAU + BTC 30m.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_stats_compare > ../docs/fvg_backtest_stats.json

OLD: min_gap_atr=0.1, gate_atr=2.0 (docs/fvg_inverted.json punya arah ini).
NEW: min_gap_atr=0.0, gate_atr=0.25 (baris teratas docs/fvg_sweep.json).
Rig sama dengan tools/fvg_sweep.py: tukar sementara DETECTORS["supply_demand"]
supaya cell_rows menjalankan kode fvg identik dengan studi lain di repo ini.
"""

from __future__ import annotations

import contextlib
import json
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect.imbalance import detect_fvg
from app.models.params import ImbalanceParams
from tools.detectors_costed import cell_rows

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
CONFIGS = {
    "old": {"min_gap_atr": 0.1, "gate_atr": 2.0},
    "new": {"min_gap_atr": 0.0, "gate_atr": 0.25},
}


def get_rows(min_gap: float, symbol: str, interval: str) -> list[dict]:
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True, min_gap_atr=min_gap)
    original = DETECTORS["supply_demand"]
    DETECTORS["supply_demand"] = lambda candles, _ignored: detect_fvg(candles, params)
    try:
        with contextlib.redirect_stdout(sys.stderr):
            rows, _span = cell_rows("supply_demand", symbol, interval)
    finally:
        DETECTORS["supply_demand"] = original
    return rows


def max_consec(flags: list[bool]) -> int:
    """Lari terpanjang True berturut-turut. [] -> 0."""
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def stats_for(r_values: np.ndarray, won: list[bool]) -> dict:
    n = int(r_values.size)
    if n == 0:
        return {"n_trades": 0}
    wins = r_values[r_values > 0]
    losses = r_values[r_values <= 0]
    n_win = int(won.count(True))
    n_loss = n - n_win
    gross_win = float(wins.sum()) if wins.size else 0.0
    gross_loss = float(-losses.sum()) if losses.size else 0.0
    sharpe = float(r_values.mean() / r_values.std(ddof=0)) if r_values.std(ddof=0) > 0 else None
    return {
        "n_trades": n,
        "n_win": n_win,
        "n_loss": n_loss,
        "winrate_pct": round(100.0 * n_win / n, 4),
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else None,
        "expected_r": float(r_values.mean()),
        "max_consec_wins": max_consec(won),
        "max_consec_losses": max_consec([not w for w in won]),
        "sharpe_r": sharpe,
        "best_r": float(r_values.max()),
        "worst_r": float(r_values.min()),
        "avg_win_r": float(wins.mean()) if wins.size else None,
        "avg_loss_r": float(losses.mean()) if losses.size else None,
    }


def kept_rows(rows: list[dict], gate: float) -> list[dict]:
    return [r for r in rows if r["departure"] < gate]


def main() -> int:
    out: dict = {"configs": CONFIGS, "cells": [f"{s} {i}" for s, i in CELLS]}

    for label, cfg in CONFIGS.items():
        print(f"config={label} {cfg}", file=sys.stderr)
        rows_by_cell = {
            f"{symbol} {interval}": get_rows(cfg["min_gap_atr"], symbol, interval)
            for symbol, interval in CELLS
        }
        pooled_kept: list[dict] = []
        per_instrument: dict[str, dict] = {}
        for cell_label, rows in rows_by_cell.items():
            kept = kept_rows(rows, cfg["gate_atr"])
            pooled_kept.extend(kept)
            r_vals = np.array([r["r"] for r in kept])
            won = [bool(r["won"]) for r in kept]
            per_instrument[cell_label] = stats_for(r_vals, won)
            print(f"  {cell_label}: n={len(kept)}", file=sys.stderr)

        pooled_r = np.array([r["r"] for r in pooled_kept])
        pooled_won = [bool(r["won"]) for r in pooled_kept]
        out[label] = {
            "pooled": stats_for(pooled_r, pooled_won),
            "per_instrument": per_instrument,
        }

    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


def _selfcheck() -> None:
    """Bukti kecil: max_consec dan stats_for menghitung benar di kasus tangan."""
    assert max_consec([]) == 0
    assert max_consec([True, True, False, True]) == 2
    assert max_consec([False, False]) == 0

    r = np.array([1.0, -1.0, 2.0, -0.5])
    won = [True, False, True, False]
    s = stats_for(r, won)
    assert s["n_trades"] == 4 and s["n_win"] == 2 and s["n_loss"] == 2
    assert s["winrate_pct"] == 50.0
    assert abs(s["profit_factor"] - (3.0 / 1.5)) < 1e-9
    assert abs(s["expected_r"] - 0.375) < 1e-9
    assert s["best_r"] == 2.0 and s["worst_r"] == -1.0
    assert abs(s["avg_win_r"] - 1.5) < 1e-9
    assert abs(s["avg_loss_r"] - (-0.75)) < 1e-9

    empty = stats_for(np.array([]), [])
    assert empty == {"n_trades": 0}
    print("selfcheck OK", file=sys.stderr)


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
        raise SystemExit(0)
    raise SystemExit(main())
