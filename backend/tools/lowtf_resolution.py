"""Kontrol resolusi untuk `lowtf_costed`: apakah +0,11 R itu artefak rasio 6?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.lowtf_resolution > ../docs/lowtf_resolution.json

KENAPA KONTROL INI WAJIB ADA. `tools/lowtf_costed.py` menemukan kedua detektor
POSITIF di 30 menit, supply_demand +0,1125 R dan order_block +0,0858 R,
sementara di 1 jam keduanya negatif. Dua penjelasan cocok dengan itu dan hanya
satu yang berarti.

  (a) 30 menit memang populasi yang lebih baik.
  (b) Bar halusnya yang berbeda. 1 jam diresolusi dengan 5 menit, rasio 12. 30
      menit diresolusi dengan 5 menit juga, rasio 6, TERKASAR di tabel `FINER`.
      Rasio kasar berarti lebih sedikit titik keputusan di dalam satu bar, dan
      di project ini resolusi sudah pernah membalik jawaban: edge +0,2 R jadi
      -0,0153 R saat diukur halus di 18 sel, karena urutan intrabar menentukan
      mana dari stop dan target yang kena lebih dulu.

Penjelasan (b) memprediksi angkanya TURUN saat 30 menit diresolusi lebih halus.
Kontrol ini menjalankan 30 menit dengan bar 1 MENIT, rasio 30, lebih halus
daripada rig 1 jam, pada populasi yang sama.

BATASNYA DINYATAKAN DI DEPAN. Riwayat 1 menit di mesin ini cuma 103 hari untuk
XAUUSD dan 69 hari untuk BTCUSD, lawan 516 dan 347 hari untuk 5 menit. Karena
itu kedua resolusi dipotong ke rentang bar-kasar yang SAMA di sini, dan kolom
5 menit dihitung ulang di rentang itu alih-alih dikutip dari studi utama. Tanpa
pemotongan itu perbandingannya membandingkan resolusi DAN periode sekaligus,
yang adalah cacat yang sama yang `conditioned_gaps.py` temukan lebih dulu.
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np

from app.providers.base import INTERVALS
from tools.detectors_costed import GATE, one_sample_t, resolved_as, welch

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
NAMES = ("supply_demand", "order_block")
FINES = ("5m", "1m")


def summarise(rows: list[dict]) -> dict:
    above = np.array([r["r"] for r in rows if r["cleared"]])
    below = np.array([r["r"] for r in rows if not r["cleared"]])
    out: dict = {
        "n_above": int(above.size), "n_below": int(below.size),
        "exp_r_above": float(above.mean()) if above.size else None,
        "exp_r_below": float(below.mean()) if below.size else None,
        "t_above_vs_zero": one_sample_t(above) if above.size > 1 else None,
    }
    if above.size and below.size:
        out["difference"] = float(above.mean() - below.mean())
        out["welch_t"] = welch(above, below)
    return out


def _read(cell: dict, fine: str, field: str):
    v = (cell.get(f"fine_{fine}") or {}).get(field)
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def conclude(cells: dict) -> dict:
    """Ringkasan yang MEMISAHKAN dua pertanyaan, karena jawabannya berbeda.

    Versi pertama fungsi ini menjawab satu kalimat, "TIDAK BERTAHAN, resolusi
    halus membalik tandanya", dan kalimat itu SALAH pada datanya sendiri: satu
    dari empat sel berbalik tanda, bukan empat. Ia juga menyatukan dua hal yang
    datanya pisahkan dengan jelas.

      H1, daya pisah gerbang, bertahan. Selisih atas-bawah menyusut sedikit dan
      tetap positif di keempat sel: +0,1981 ke +0,1614, +0,2243 ke +0,1889,
      +0,1571 ke +0,1252, +0,2133 ke +0,1921.

      H2, ekspektasi absolut di atas gerbang, TIDAK. Ia menyusut di keempat sel
      dan arah penyusutannya satu sisi: +0,1110 ke +0,0549, +0,0809 ke +0,0359,
      +0,0701 ke +0,0107, dan +0,0576 ke -0,0031.

    Jadi yang dijawab per detektor, bukan sekali untuk semuanya: supply_demand
    mempertahankan tanda positifnya di rasio 30, order_block tidak.
    """
    out: dict = {"per_detector": {}}
    usable = []
    for label, cell in cells.items():
        name = label.split(" ")[0]
        a, b = _read(cell, "5m", "exp_r_above"), _read(cell, "1m", "exp_r_above")
        d5, d1 = _read(cell, "5m", "difference"), _read(cell, "1m", "difference")
        if a is None or b is None:
            continue
        usable.append((name, a, b, d5, d1))
    out["cells_compared"] = len(usable)
    if not usable:
        out["verdict"] = "tidak terbaca"
        return out
    for name in sorted({n for n, *_ in usable}):
        mine = [r for r in usable if r[0] == name]
        out["per_detector"][name] = {
            "exp_above_keeps_sign_at_ratio_30": all(b > 0 for _, _, b, _, _ in mine),
            "exp_above_shrinks": all(b < a for _, a, b, _, _ in mine),
            "separation_keeps_sign": all(
                d1 is not None and d1 > 0 for *_, d1 in mine),
        }
    out["all_exp_above_shrink"] = all(b < a for _, a, b, _, _ in usable)
    out["separation_survives"] = all(
        d1 is not None and d1 > 0 for *_, d1 in usable)
    out["exp_above_survives"] = all(b > 0 for _, _, b, _, _ in usable)
    keeps = [n for n, v in out["per_detector"].items()
             if v["exp_above_keeps_sign_at_ratio_30"]]
    loses = [n for n, v in out["per_detector"].items()
             if not v["exp_above_keeps_sign_at_ratio_30"]]
    out["verdict"] = (
        ("H1 BERTAHAN di setiap sel" if out["separation_survives"]
         else "H1 TIDAK bertahan")
        + "; H2 menyusut di "
        + ("setiap sel" if out["all_exp_above_shrink"] else "sebagian sel")
        + (f", tanda bertahan untuk {', '.join(keeps)}" if keeps else "")
        + (f", HILANG untuk {', '.join(loses)}" if loses else "")
    )
    return out


def selfcheck() -> int:
    """Bukti bahwa `conclude` membedakan keadaan yang berbeda.

        PYTHONPATH=. .venv/Scripts/python.exe -m tools.lowtf_resolution --selfcheck

    Ini ada karena versi pertama `conclude` MENJAWAB SALAH pada datanya sendiri,
    dan tidak ada apa pun yang menangkapnya. Sebuah ringkasan yang salah lebih
    buruk daripada tidak ada ringkasan: ia dikutip.
    """
    def cell(a, b, d5=0.2, d1=0.15):
        return {"fine_5m": {"exp_r_above": a, "difference": d5},
                "fine_1m": {"exp_r_above": b, "difference": d1}}

    got = conclude({"supply_demand X 30m": cell(0.11, 0.05),
                    "order_block X 30m": cell(0.06, -0.003)})
    assert got["per_detector"]["supply_demand"][
        "exp_above_keeps_sign_at_ratio_30"] is True
    assert got["per_detector"]["order_block"][
        "exp_above_keeps_sign_at_ratio_30"] is False
    assert "bertahan untuk supply_demand" in got["verdict"]
    assert "HILANG untuk order_block" in got["verdict"]
    assert got["separation_survives"] is True and got["all_exp_above_shrink"]

    # Separasi yang ikut mati harus terbaca berbeda.
    got = conclude({"a X 30m": cell(0.11, 0.05, d1=-0.01)})
    assert got["separation_survives"] is False
    assert got["verdict"].startswith("H1 TIDAK bertahan")

    # Tumbuh, bukan menyusut, tidak boleh dilaporkan sebagai menyusut.
    got = conclude({"a X 30m": cell(0.05, 0.11)})
    assert got["all_exp_above_shrink"] is False

    # NaN dan sel kosong tidak boleh terbaca sebagai jawaban.
    assert conclude({})["verdict"] == "tidak terbaca"
    assert conclude({"a X 30m": cell(float("nan"), 0.05)})[
        "cells_compared"] == 0
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    if "--selfcheck" in sys.argv:
        return selfcheck()
    out: dict = {
        "question": "apakah +0,1125 R dan +0,0858 R di 30m bertahan saat "
                    "diresolusi 1 menit (rasio 30) alih-alih 5 menit (rasio 6)",
        "gate_atr": GATE,
        "caveat": "riwayat 1m cuma 103 hari XAUUSD dan 69 hari BTCUSD; kedua "
                  "resolusi dipotong ke rentang bar-kasar yang SAMA sebelum "
                  "dibandingkan",
        "cells": {},
    }
    for name in NAMES:
        for symbol, interval in CELLS:
            got: dict = {}
            rows_by_fine: dict[str, list[dict]] = {}
            for fine in FINES:
                try:
                    rows_by_fine[fine] = resolved_as(name, symbol, interval, fine)
                except Exception as exc:
                    got[f"fine_{fine}"] = {"error": str(exc)}
                    rows_by_fine[fine] = []
            fine_rows = rows_by_fine.get("1m") or []
            if fine_rows:
                lo = min(r["at"] for r in fine_rows)
                hi = max(r["at"] for r in fine_rows)
                got["shared_coarse_bars"] = [int(lo), int(hi)]
                for fine, rows in rows_by_fine.items():
                    kept = [r for r in rows if lo <= r["at"] <= hi]
                    got[f"fine_{fine}"] = {
                        "ratio_fine_per_coarse":
                            INTERVALS[interval] // INTERVALS[fine],
                        **summarise(kept),
                    }
            label = f"{name} {symbol} {interval}"
            out["cells"][label] = got
            a = (got.get("fine_5m") or {}).get("exp_r_above")
            b = (got.get("fine_1m") or {}).get("exp_r_above")
            print(f"{label:34s} 5m {'None' if a is None else round(a, 4):>9}  "
                  f"1m {'None' if b is None else round(b, 4):>9}  "
                  f"n_atas_1m {(got.get('fine_1m') or {}).get('n_above')}",
                  file=sys.stderr)

    out.update(conclude(out["cells"]))
    print(f"VERDICT: {out['verdict']}", file=sys.stderr)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
