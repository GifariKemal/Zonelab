"""FVG gate (min_gap=0.0, gate=0.25) di luar 30m: 15m, 1h, 4h, 1d, XAU dan BTC.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_multi_tf_sweep > ../docs/fvg_multi_tf.json

`docs/fvg_sweep.json` menemukan (min_gap=0.0, gate=0.25) di 30m lewat grid
exhaustive. File ini TIDAK re-grid; ia mengambil tiga titik yang sudah punya
arti (rekomendasi, baseline tanpa gerbang, produksi lama) dan mengecek apakah
sinyalnya bertahan di timeframe lain, memakai rig yang sama
(`tools/detectors_costed.py:cell_rows`) supaya angkanya sebanding dengan
setiap studi FVG lain di repo ini.

`FINER` (`tools/intrabar.py:71`) tidak punya entri untuk `1d`; ditambahkan
sementara di proses ini (`24 jam` -> bar halus `1h`, rasio 24, sebanding
dengan rasio 12-16 pada sel yang sudah ada) supaya `cell_rows("1d")` tidak
KeyError. Tidak menyentuh file `tools/intrabar.py`.
"""

from __future__ import annotations

import contextlib
import json
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect.imbalance import detect_fvg
from app.models.params import ImbalanceParams
from tools import intrabar
from tools.detectors_costed import cell_rows, one_sample_t, welch

intrabar.FINER.setdefault("1d", "1h")

SYMBOLS = ["XAUUSD", "BTCUSD"]
TIMEFRAMES = ["15m", "1h", "4h", "1d"]
#: (label, min_gap_atr, gate_atr) - rekomendasi, baseline tanpa gerbang, produksi lama.
CONFIGS = [
    ("recommended", 0.0, 0.25),
    ("no_gate_baseline", 0.0, 0.0),
    ("old_production", 0.1, 2.0),
]


def rows_for(symbol: str, interval: str, min_gap: float) -> list[dict]:
    """Baris satu sel untuk satu `min_gap_atr`. Pola swap `DETECTORS` sama dengan
    `fvg_sweep.py` supaya resolusi bar halus tetap kode yang sama."""
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True,
                              min_gap_atr=min_gap)
    original = DETECTORS["supply_demand"]
    DETECTORS["supply_demand"] = lambda candles, _ignored: detect_fvg(candles, params)
    try:
        with contextlib.redirect_stdout(sys.stderr):
            rows, _span = cell_rows("supply_demand", symbol, interval)
    finally:
        DETECTORS["supply_demand"] = original
    return rows


def split(rows: list[dict], gate: float) -> tuple[np.ndarray, np.ndarray]:
    if gate > 0:
        below = np.array([r["r"] for r in rows if r["departure"] < gate])
        above = np.array([r["r"] for r in rows if r["departure"] >= gate])
    else:
        below = np.array([r["r"] for r in rows])
        above = np.array([])
    return below, above


def main() -> int:
    results: dict[str, dict] = {}
    for interval in TIMEFRAMES:
        for symbol in SYMBOLS:
            cell = f"{symbol} {interval}"
            print(f"=== {cell} ===", file=sys.stderr)
            rows_by_min_gap: dict[float, list[dict] | Exception] = {}
            for min_gap in sorted({c[1] for c in CONFIGS}):
                try:
                    rows_by_min_gap[min_gap] = rows_for(symbol, interval, min_gap)
                except Exception as exc:  # provider/data bisa gagal per TF
                    rows_by_min_gap[min_gap] = exc
                    print(f"  min_gap={min_gap} GAGAL: {exc}", file=sys.stderr)

            cell_out = {}
            for label, min_gap, gate in CONFIGS:
                rows = rows_by_min_gap[min_gap]
                if isinstance(rows, Exception):
                    cell_out[label] = {"error": str(rows)}
                    continue
                below, above = split(rows, gate)
                entry = {
                    "min_gap_atr": min_gap, "gate_atr": gate,
                    "n_below": int(below.size), "n_above": int(above.size),
                    "exp_r_below": float(below.mean()) if below.size else None,
                    "exp_r_above": float(above.mean()) if above.size else None,
                    "t_below_vs_zero": (one_sample_t(below)
                                        if below.size > 1 else None),
                    "welch_t": (welch(below, above)
                                if below.size > 1 and above.size > 1 else None),
                }
                cell_out[label] = entry
                print(f"  {label:<18} n_below={entry['n_below']:>5} "
                      f"exp_r={entry['exp_r_below']} "
                      f"t={entry['t_below_vs_zero']}", file=sys.stderr)
            results[cell] = cell_out

    out = {"symbols": SYMBOLS, "timeframes": TIMEFRAMES, "configs": CONFIGS,
           "results": results}
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


def _selfcheck() -> None:
    """Bukti kecil bahwa `split` memilah dengan benar dan config unik terurai."""
    rows = [{"r": 0.1 * i, "departure": float(i % 5)} for i in range(20)]
    below, above = split(rows, 2.0)
    assert below.size + above.size == 20
    below0, above0 = split(rows, 0.0)
    assert above0.size == 0 and below0.size == 20
    assert sorted({c[1] for c in CONFIGS}) == [0.0, 0.1]
    print("selfcheck OK", file=sys.stderr)


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
        raise SystemExit(0)
    raise SystemExit(main())
