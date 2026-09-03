"""Apakah rig Python dan Strategy Tester MQL5 setuju di periode yang sama?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.mt5_python_parity > ../docs/mt5_python_parity.json

===========================================================================
KENAPA INI ADA
===========================================================================

Dua rig menjawab pertanyaan yang sama untuk detektor yang sama, dan pada 2
September 2026 keduanya menjawab BERLAWANAN di 30 menit.

  rig Python, `docs/fvg_inverted.json`   fvg +0,2188 R, t lawan nol +8,53, 8/8 fold
  rig Python, `docs/lowtf_costed.json`   supply_demand +0,1125 R
  Strategy Tester, `docs/mt5-backtest.json`
                                         ZonelabFVG XAUUSD M30 PF 0,86, 622 trade
                                         ZonelabSD  XAUUSD M30 PF 1,34, 209 trade

Jadi Python bilang fvg menang dan supply_demand menang lebih kecil; MQL5 bilang
fvg KALAH dan supply_demand menang. Salah satu dari dua rig itu keliru, atau
keduanya benar tentang populasi yang berbeda, dan tidak ada gunanya menebak yang
mana.

===========================================================================
YANG DISAMAKAN, DAN YANG TIDAK BISA
===========================================================================

Satu perbedaan bisa dihapus dengan murah: PERIODE. Run MQL5 menutup
2026.01.01 sampai 2026.08.31, delapan bulan. Rig Python memakai deret penuh,
sekitar 62.000 bar 30 menit atau 3,5 tahun. Fold walk-forward fvg sendiri
berkisar +0,0997 sampai +0,3179, jadi delapan bulan bisa saja satu fold lemah,
dan membandingkan 8 bulan ke 3,5 tahun tidak membandingkan apa pun.

File ini memotong baris rig Python ke jendela tanggal MQL5 dan melaporkan
keduanya berdampingan.

TIGA PERBEDAAN YANG TERSISA, dinyatakan bukan disembunyikan:

  resolusi   MQL5 memakai real tick (`History Quality: 100% real ticks`), rig
             Python memakai bar 5 menit. MQL5 LEBIH HALUS, dan kontrol resolusi
             di `docs/fvg_resolution.json` sudah menunjukkan resolusi yang lebih
             halus MENYUSUTKAN angkanya: +0,1869 ke +0,1354 saat 5m diganti 1m.
             Real tick adalah kelanjutan arah itu, jadi angka MQL5 yang lebih
             rendah TIDAK OTOMATIS berarti salah satu rig keliru.
  biaya      MQL5 memakai spread dan komisi terminal apa adanya; Python memakai
             jadwal `exness_raw`.
  lookback   EA memakai `InpBars = 3000` untuk mencari zona; Python memakai
             deret penuh, jadi zona yang lahir lebih dari 3.000 bar sebelum
             sebuah sentuhan tidak ada di sisi MQL5.

SATUANNYA JUGA BERBEDA dan tidak dipaksa sama. Python melaporkan ekspektasi R
per trade; MQL5 melaporkan Profit Factor dan Expected Payoff dalam mata uang.
Yang dibandingkan karena itu TANDA dan URUTAN, bukan besarnya: apakah kedua rig
setuju detektor mana yang menang, dan apakah keduanya setuju tandanya positif.
Memaksa satu angka jadi satuan yang lain akan mengarang konversi yang tidak ada.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

from tools.detectors_costed import one_sample_t, resolved_as
from tools.quant import clean

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
NAMES = ("supply_demand", "fvg", "order_block", "ifvg")
FINE = "5m"
#: Jendela run MQL5, dibaca dari `docs/mt5-backtest.json` dan dipatok di sini
#: supaya perbandingannya tidak bergeser saat file itu di-regenerate.
WINDOW = ("2026.01.01", "2026.08.31")
REPORT = Path(__file__).resolve().parent.parent.parent / "docs" / "mt5-backtest.json"
#: Nama EA per detektor. `breaker` tidak punya sel M30 di matriks itu.
EXPERT = {"supply_demand": "ZonelabSD", "fvg": "ZonelabFVG",
          "order_block": "ZonelabOB", "ifvg": "ZonelabIFVG"}
PERIOD = {"30m": "M30", "15m": "M15", "1h": "H1", "4h": "H4"}


def _epoch(stamp: str) -> int:
    return int(dt.datetime.strptime(stamp, "%Y.%m.%d")
               .replace(tzinfo=dt.timezone.utc).timestamp())


def python_side(name: str, symbol: str, interval: str) -> dict:
    """Ekspektasi R rig Python, penuh dan dipotong ke jendela MQL5."""
    rows = resolved_as(name, symbol, interval, FINE)
    candles, _, _ = clean(symbol, interval)
    times = [c.time for c in candles]
    lo, hi = _epoch(WINDOW[0]), _epoch(WINDOW[1]) + 86_400

    def stats(subset: list[dict]) -> dict:
        vals = np.array([r["r"] for r in subset], dtype=np.float64)
        if vals.size < 2:
            return {"n": int(vals.size), "exp_r": None, "t_vs_zero": None,
                    "win_rate": None}
        return {"n": int(vals.size), "exp_r": float(vals.mean()),
                "t_vs_zero": one_sample_t(vals),
                "win_rate": float((vals > 0).mean())}

    inside = [r for r in rows
              if 0 <= int(r["at"]) < len(times) and lo <= times[int(r["at"])] < hi]
    return {"full_series": stats(rows), "mql5_window": stats(inside),
            "window": list(WINDOW)}


def mql5_side(name: str, symbol: str, interval: str) -> dict:
    """Sel Strategy Tester yang sepadan, dibaca dari report yang tersimpan."""
    if not REPORT.exists():
        return {"error": f"{REPORT} tidak ada"}
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    want = f"{EXPERT[name]}_{symbol}_{PERIOD[interval]}"
    for cell in data.get("cells", []):
        if cell.get("cell") == want:
            return {k: cell.get(k) for k in (
                "cell", "status", "Profit Factor", "Total Trades",
                "Expected Payoff", "Total Net Profit", "History Quality",
                "Profit Trades (% of total)")}
    return {"error": f"sel {want} tidak ada di {REPORT.name}"}


def _pf_sign(cell: dict) -> int | None:
    """+1 kalau PF di atas 1, -1 kalau di bawah, None kalau tidak terbaca."""
    raw = cell.get("Profit Factor")
    try:
        pf = float(str(raw).replace(" ", "").replace(",", ""))
    except (TypeError, ValueError):
        return None
    return 0 if pf == 1.0 else (1 if pf > 1.0 else -1)


def _r_sign(stats: dict) -> int | None:
    exp = stats.get("exp_r")
    if exp is None:
        return None
    return 0 if exp == 0 else (1 if exp > 0 else -1)


def compare(py: dict, mq: dict) -> dict:
    """Bandingkan TANDA, bukan besarnya. Lihat docstring modul."""
    a = _r_sign(py.get("mql5_window") or {})
    b = _pf_sign(mq)
    return {
        "python_sign_in_window": a,
        "mql5_sign": b,
        "agree": None if a is None or b is None else a == b,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()

    out: dict = {
        "question": "apakah rig Python dan Strategy Tester MQL5 setuju TANDA-nya "
                    "di periode yang sama",
        "window": list(WINDOW),
        "matched": "periode saja",
        "not_matched": {
            "resolution": "MQL5 real tick, Python bar 5m; kontrol resolusi "
                          "sudah menunjukkan yang lebih halus menyusutkan",
            "costs": "MQL5 spread terminal, Python jadwal exness_raw",
            "lookback": "EA InpBars=3000, Python deret penuh",
            "units": "R per trade lawan Profit Factor; yang dibandingkan tanda",
        },
        "cells": {},
    }
    for name in NAMES:
        for symbol, interval in CELLS:
            label = f"{name} {symbol} {interval}"
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    py = python_side(name, symbol, interval)
            except Exception as exc:
                out["cells"][label] = {"error": str(exc)}
                print(f"  {label}: GAGAL {exc}", file=sys.stderr)
                continue
            mq = mql5_side(name, symbol, interval)
            out["cells"][label] = {"python": py, "mql5": mq,
                                   "comparison": compare(py, mq)}
            w = py["mql5_window"]
            print(f"  {label}: python penuh {py['full_series']['exp_r']} "
                  f"(n {py['full_series']['n']}), jendela {w['exp_r']} "
                  f"(n {w['n']}, t {w['t_vs_zero']}) | mql5 PF "
                  f"{mq.get('Profit Factor')} trade {mq.get('Total Trades')} "
                  f"-> setuju {out['cells'][label]['comparison']['agree']}",
                  file=sys.stderr)

    agree = [k for k, v in out["cells"].items()
             if (v.get("comparison") or {}).get("agree") is True]
    disagree = [k for k, v in out["cells"].items()
                if (v.get("comparison") or {}).get("agree") is False]
    out["agree"] = agree
    out["disagree"] = disagree
    out["verdict"] = (
        f"{len(agree)} sel setuju tandanya, {len(disagree)} tidak"
        if agree or disagree else "tidak ada sel yang terbaca"
    )
    print(f"  VERDICT: {out['verdict']}", file=sys.stderr)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


def selfcheck() -> int:
    """Pembacaan tanda harus benar, karena seluruh file ini bergantung padanya."""
    assert _pf_sign({"Profit Factor": "1.34"}) == 1
    assert _pf_sign({"Profit Factor": "0.86"}) == -1
    assert _pf_sign({"Profit Factor": "1.00"}) == 0
    assert _pf_sign({"Profit Factor": "1 234.5"}) == 1, "spasi ribuan MT5"
    assert _pf_sign({"Profit Factor": None}) is None
    assert _pf_sign({}) is None
    assert _pf_sign({"Profit Factor": "n/a"}) is None
    assert _r_sign({"exp_r": 0.2}) == 1
    assert _r_sign({"exp_r": -0.2}) == -1
    assert _r_sign({"exp_r": None}) is None
    # Ketidaksepakatan HARUS terbaca sebagai ketidaksepakatan, bukan None.
    got = compare({"mql5_window": {"exp_r": 0.21}}, {"Profit Factor": "0.86"})
    assert got["agree"] is False, got
    got = compare({"mql5_window": {"exp_r": 0.11}}, {"Profit Factor": "1.34"})
    assert got["agree"] is True, got
    # Dan sel yang tidak terbaca tidak boleh dihitung sebagai setuju.
    assert compare({"mql5_window": {"exp_r": None}},
                   {"Profit Factor": "1.34"})["agree"] is None
    assert compare({"mql5_window": {}}, {"error": "x"})["agree"] is None
    assert _epoch("2026.01.01") == 1767225600
    print("selfcheck OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
