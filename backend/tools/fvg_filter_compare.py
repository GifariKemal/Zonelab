"""Compare FVG filter variants on the same rig as fvg_sweep.py.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_filter_compare

Each variant runs with gate_atr=0.25 (the ceiling gate from recalibration).
Output: JSON array of variant results, sorted by exp_r.
"""

from __future__ import annotations

import contextlib
import json
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect.imbalance import detect_fvg
from app.models.params import ImbalanceParams
from tools.detectors_costed import FOLDS, cell_rows, one_sample_t, welch
from tools.fvg_sweep import split, walk_forward

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
GATE = 0.25

VARIANTS: list[dict] = [
    {"name": "A: baseline (no filter)",
     "params": {"filter_mother": False, "min_gap_atr": 0.0,
                "min_body_ratio": 0.0, "body_gap": False}},
    {"name": "B: mother candle",
     "params": {"filter_mother": True, "min_gap_atr": 0.0,
                "min_body_ratio": 0.0, "body_gap": False}},
    {"name": "C: mother + min_gap 0.05",
     "params": {"filter_mother": True, "min_gap_atr": 0.05,
                "min_body_ratio": 0.0, "body_gap": False}},
    {"name": "D: mother + min_gap 0.1",
     "params": {"filter_mother": True, "min_gap_atr": 0.1,
                "min_body_ratio": 0.0, "body_gap": False}},
    {"name": "E: mother + body ratio 0.3",
     "params": {"filter_mother": True, "min_gap_atr": 0.0,
                "min_body_ratio": 0.3, "body_gap": False}},
    {"name": "F: body-based gap edges",
     "params": {"filter_mother": False, "min_gap_atr": 0.0,
                "min_body_ratio": 0.0, "body_gap": True}},
    {"name": "G: mother + body ratio 0.3 + min_gap 0.05",
     "params": {"filter_mother": True, "min_gap_atr": 0.05,
                "min_body_ratio": 0.3, "body_gap": False}},
]


def run_variant(v: dict) -> dict:
    name = v["name"]
    p = v["params"]
    params = ImbalanceParams(
        max_zones_per_side=0, show_broken=True,
        filter_mother=p["filter_mother"],
        min_gap_atr=p["min_gap_atr"],
        min_body_ratio=p["min_body_ratio"],
        body_gap=p["body_gap"],
    )
    original = DETECTORS["supply_demand"]
    DETECTORS["supply_demand"] = lambda candles, _: detect_fvg(candles, params)
    try:
        all_rows: list[dict] = []
        cells_out = {}
        for symbol, interval in CELLS:
            with contextlib.redirect_stdout(sys.stderr):
                rows, _span = cell_rows("supply_demand", symbol, interval)
            all_rows.extend(rows)
            below, above = split(rows, GATE)
            cells_out[f"{symbol} {interval}"] = {
                "n_below": int(below.size), "n_above": int(above.size),
                "exp_r_below": float(below.mean()) if below.size else None,
                "exp_r_above": float(above.mean()) if above.size else None,
            }
    finally:
        DETECTORS["supply_demand"] = original

    below, above = split(all_rows, GATE)
    wf = walk_forward(all_rows, GATE)

    wins = sum(1 for r in all_rows if r["r"] > 0 and r["departure"] < GATE)
    losses = sum(1 for r in all_rows if r["r"] <= 0 and r["departure"] < GATE)
    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
    gross_profit = sum(r["r"] for r in all_rows
                       if r["r"] > 0 and r["departure"] < GATE)
    gross_loss = abs(sum(r["r"] for r in all_rows
                         if r["r"] <= 0 and r["departure"] < GATE))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    return {
        "variant": name,
        "n_total": len(all_rows),
        "n_below_gate": int(below.size),
        "n_above_gate": int(above.size),
        "exp_r": float(below.mean()) if below.size else None,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(pf, 3),
        "welch_t": welch(below, above) if below.size > 1 and above.size > 1 else None,
        "t_vs_zero": one_sample_t(below) if below.size > 1 else None,
        "wf_positive": wf["positive"],
        "wf_graded": wf["graded"],
        "cells": cells_out,
    }


def main() -> int:
    results = []
    for v in VARIANTS:
        print(f"  {v['name']}...", file=sys.stderr)
        r = run_variant(v)
        print(f"    n={r['n_below_gate']} exp_r={r['exp_r']:.4f} "
              f"WR={r['win_rate']:.1%} PF={r['profit_factor']:.3f} "
              f"wf={r['wf_positive']}/{r['wf_graded']}", file=sys.stderr)
        results.append(r)

    results.sort(key=lambda e: (
        e["wf_positive"],
        e["exp_r"] if e["exp_r"] is not None else -999.0,
    ), reverse=True)

    json.dump({"gate_atr": GATE, "variants": results},
              sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
