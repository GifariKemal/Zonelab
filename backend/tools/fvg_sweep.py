"""Grid sweep FVG: 7 `min_gap_atr` x 6 `gate_atr`, 30 menit, XAU dan BTC.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_sweep > ../docs/fvg_sweep.json

`docs/fvg_inverted.json` mengukur SATU kombinasi (min_gap default, gerbang
2,0 ATR terbalik) dan menemukan sisi BAWAH gerbang positif di 30 menit. File
ini mencari kombinasi min_gap/gate yang benar-benar optimal lewat grid
exhaustive, memakai rig yang sama (`tools/detectors_costed.py:cell_rows`)
supaya angkanya dari kode identik dengan setiap studi FVG lain di repo ini.

Deteksi FVG dijalankan SEKALI per `min_gap_atr` (7 kali per sel, bukan 42),
karena gerbang `gate_atr` cuma memilah baris `departure` yang sudah ada,
tidak butuh deteksi ulang. Itu yang membuat sweep 42 sel selesai dalam waktu
yang sama dengan 14 pemanggilan `cell_rows`, bukan 42.
"""

from __future__ import annotations

import contextlib
import json
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect.imbalance import detect_fvg
from app.models.params import ImbalanceParams
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, cell_rows, one_sample_t, welch

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
MIN_GAP_GRID = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5]
GATE_GRID = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0]
MIN_FOLD = 20
#: Bonferroni atas seluruh 42 sel grid, bukan cuma dua hipotesis.
T_THRESHOLD = _critical_t(len(MIN_GAP_GRID) * len(GATE_GRID))


def _rows_for(min_gap: float) -> dict[str, list[dict]]:
    """Baris tiap sel untuk satu `min_gap_atr`.

    Pola yang sama dengan `detectors_costed.py:resolved_as`: entri
    `DETECTORS["supply_demand"]` ditukar sementara supaya `cell_rows` (dan
    resolusi bar halus di dalamnya) tetap kode yang sama untuk `fvg`.
    """
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True,
                              min_gap_atr=min_gap)
    original = DETECTORS["supply_demand"]
    DETECTORS["supply_demand"] = lambda candles, _ignored: detect_fvg(candles, params)
    out: dict[str, list[dict]] = {}
    try:
        for symbol, interval in CELLS:
            with contextlib.redirect_stdout(sys.stderr):
                rows, _span = cell_rows("supply_demand", symbol, interval)
            out[f"{symbol} {interval}"] = rows
    finally:
        DETECTORS["supply_demand"] = original
    return out


def split(rows: list[dict], gate: float) -> tuple[np.ndarray, np.ndarray]:
    """Baris di bawah/atas `gate_atr`. Gate 0 berarti semua FVG, tanpa gerbang."""
    if gate > 0:
        below = np.array([r["r"] for r in rows if r["departure"] < gate])
        above = np.array([r["r"] for r in rows if r["departure"] >= gate])
    else:
        below = np.array([r["r"] for r in rows])
        above = np.array([])
    return below, above


def walk_forward(rows: list[dict], gate: float) -> dict:
    """8 fold posisi relatif, tanda exp_R sisi bawah gerbang di tiap fold."""
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    folds = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        below, _above = split(kept, gate)
        entry: dict = {"fold": k + 1, "n_below": int(below.size),
                       "purged": len(opened) - len(kept)}
        if below.size >= MIN_FOLD:
            entry["exp_r"] = float(below.mean())
            entry["readable"] = True
        else:
            entry["readable"] = False
        folds.append(entry)
    graded = [f for f in folds if f["readable"]]
    return {"folds": folds, "graded": len(graded),
            "positive": sum(1 for f in graded if f["exp_r"] > 0)}


def main() -> int:
    results = []
    for min_gap in MIN_GAP_GRID:
        print(f"min_gap_atr={min_gap}", file=sys.stderr)
        rows_by_cell = _rows_for(min_gap)
        pooled = [r for rows in rows_by_cell.values() for r in rows]
        for gate in GATE_GRID:
            below, above = split(pooled, gate)
            wf = walk_forward(pooled, gate)
            cells_out = {}
            for label, rows in rows_by_cell.items():
                cb, ca = split(rows, gate)
                cells_out[label] = {
                    "n_below": int(cb.size), "n_above": int(ca.size),
                    "exp_r_below": float(cb.mean()) if cb.size else None,
                    "exp_r_above": float(ca.mean()) if ca.size else None,
                }
            entry = {
                "min_gap_atr": min_gap, "gate_atr": gate,
                "n_below": int(below.size), "n_above": int(above.size),
                "exp_r_below": float(below.mean()) if below.size else None,
                "exp_r_above": float(above.mean()) if above.size else None,
                "t_below_vs_zero": (one_sample_t(below) if below.size > 1
                                     else None),
                "welch_t": (welch(below, above)
                            if below.size > 1 and above.size > 1 else None),
                "walk_forward": wf,
                "cells": cells_out,
            }
            results.append(entry)
            print(f"  gate={gate:>4} n_below={below.size:>6} "
                  f"exp_r_below={entry['exp_r_below']} "
                  f"wf {wf['positive']}/{wf['graded']}", file=sys.stderr)

    results.sort(key=lambda e: (
        e["walk_forward"]["positive"],
        e["exp_r_below"] if e["exp_r_below"] is not None else -999.0,
    ), reverse=True)

    out = {
        "grid": {"min_gap_atr": MIN_GAP_GRID, "gate_atr": GATE_GRID},
        "cells": [f"{s} {i}" for s, i in CELLS],
        "t_threshold_bonferroni": T_THRESHOLD,
        "folds": FOLDS,
        "results": results,
    }
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


def _selfcheck() -> None:
    """Bukti kecil bahwa `split` dan `walk_forward` memilah dengan benar."""
    rows = [{"r": 0.1 * i, "departure": float(i % 5), "pos": i / 20,
             "exit_pos": i / 20} for i in range(20)]
    below, above = split(rows, 2.0)
    assert below.size + above.size == 20
    assert all(r["departure"] < 2.0 for r in rows if r["r"] in below)
    below0, above0 = split(rows, 0.0)
    assert above0.size == 0 and below0.size == 20

    wf = walk_forward(rows, 0.0)
    assert wf["graded"] <= FOLDS
    print("selfcheck OK", file=sys.stderr)


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
        raise SystemExit(0)
    raise SystemExit(main())
