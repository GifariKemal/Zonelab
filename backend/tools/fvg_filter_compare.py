"""Compare FVG filter variants on the same rig as fvg_sweep.py.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_filter_compare

Each variant runs with gate_atr=0.25 (the ceiling gate from recalibration).
Output: JSON array of variant results, sorted by exp_r.
"""

from __future__ import annotations

import contextlib
import json
import sys

from app.detect import DETECTORS
from app.detect.imbalance import detect_fvg
from app.models.params import ImbalanceParams
from tools.detectors_costed import cell_rows, one_sample_t, welch
from tools.execute import MEASURED_INTERVALS
from tools.fvg_sweep import split, walk_forward

#: SEL DITURUNKAN DARI REGISTRY, bukan diketik. Baris ini berbunyi
#: `[("XAUUSD","30m"), ("BTCUSD","30m")]` sampai 6 September 2026 - dua sel yang
#: hari itu juga diukur TIDAK punya edge sama sekali (PF 0,985 dan 0,820 dengan
#: biaya, `docs/QA-FVG-TV.md`). Sebuah filter yang tidak menolong di sana tidak
#: memberi tahu apa pun tentang filter itu, cuma tentang selnya, dan file ini
#: dipakai untuk memutuskan default. Menurunkannya dari `measured_intervals`
#: membuat alat ukur dan klaim yang ter-ship tidak bisa lagi menunjuk timeframe
#: yang berbeda tanpa ada yang menyadarinya.
CELLS = [
    (symbol, interval)
    for interval in MEASURED_INTERVALS["fvg"]
    for symbol in ("XAUUSD", "BTCUSD")
]
GATE = 0.25

# VARIAN F DIHAPUS 6 September 2026 bersama knob `body_gap`-nya. Ia adalah yang
# terburuk dari tujuh di `docs/fvg_filter_compare.json` - exp_r 0,1399 lawan
# baseline 0,4263, Welch t 0,67, dan satu-satunya yang gagal walk-forward (6
# dari 8) - dan alasannya struktural, bukan kebetulan sampel: tepi body
# MELEBARKAN kotak, jadi gerbang ceiling membuang hampir semuanya. Hurufnya
# tidak dinomori ulang supaya JSON lama tetap bisa dibaca.
VARIANTS: list[dict] = [
    {"name": "A: baseline (no filter)",
     "params": {"filter_mother": False, "min_gap_atr": 0.0,
                "min_body_ratio": 0.0}},
    {"name": "B: mother candle",
     "params": {"filter_mother": True, "min_gap_atr": 0.0,
                "min_body_ratio": 0.0}},
    {"name": "C: mother + min_gap 0.05",
     "params": {"filter_mother": True, "min_gap_atr": 0.05,
                "min_body_ratio": 0.0}},
    {"name": "D: mother + min_gap 0.1",
     "params": {"filter_mother": True, "min_gap_atr": 0.1,
                "min_body_ratio": 0.0}},
    {"name": "E: mother + body ratio 0.3",
     "params": {"filter_mother": True, "min_gap_atr": 0.0,
                "min_body_ratio": 0.3}},
    {"name": "G: mother + body ratio 0.3 + min_gap 0.05",
     "params": {"filter_mother": True, "min_gap_atr": 0.05,
                "min_body_ratio": 0.3}},
]


def run_variant(v: dict) -> dict:
    name = v["name"]
    p = v["params"]
    params = ImbalanceParams(
        max_zones_per_side=0, show_broken=True,
        filter_mother=p["filter_mother"],
        min_gap_atr=p["min_gap_atr"],
        min_body_ratio=p["min_body_ratio"],
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
