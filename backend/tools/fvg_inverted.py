"""Praregistrasi: apakah FVG DI BAWAH gerbang departure positif di 30 menit?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_inverted > ../docs/fvg_inverted.json

Ditulis 2 September 2026, SEBELUM satu angka pun dihitung untuk 30 menit.

===========================================================================
KENAPA PERTANYAANNYA TERBALIK
===========================================================================

`docs/detectors_costed.json` menguji hipotesis "FVG yang LOLOS gerbang departure
2,0 ATR lebih baik daripada yang tidak" dan menjawab TIDAK, negatif dan
signifikan: selisih -0,1005 R dengan Welch t = -4,48 dan hanya 3 dari 17 sel
positif. Artinya gerbangnya TERBALIK untuk FVG.

Yang tidak pernah ditanyakan sesudahnya: sisi mana yang positif SENDIRI. Di file
itu `exp_r_below` untuk fvg adalah +0,0938 R di n=16.200, dan itu SATU-SATUNYA
angka positif di seluruh file, sementara setiap populasi lolos-gerbang di sana
negatif. Tapi ia diukur di 1 jam dan 4 jam, dan tidak pernah diuji lawan nol.

Dan itu penting sekarang karena alasan yang konkret. Pada 2 September 2026 XAU
rally 115,54 poin dan engine tidak bisa ikut: satu-satunya entry long-nya adalah
limit di zona yang belum tersentuh, dan harga tidak pernah kembali ke satu pun.
`tools/continuation_backtest.py` sudah menguji jawaban yang jelas, entry MARKET
searah break atau CISD, dan keempat arm-nya gagal: -0,0921 sampai -0,1602 R di 1
jam, dan LEBIH BURUK di 30 menit, -0,1874 sampai -0,2404 R dengan t lawan nol
sampai -12,21. Placebo jitter-nya juga negatif sebesar itu, jadi yang membunuhnya
biaya, bukan sinyalnya.

FVG kecil adalah kemungkinan ketiga, dan bentuknya berbeda dari keduanya: ia
LIMIT di retracement ke dalam impuls, bukan market di momentumnya, jadi ia tidak
membayar spread untuk mengejar harga. Sebuah rally meninggalkan FVG di
belakangnya, dan FVG yang KECIL adalah yang harganya masih mungkin sentuh.

===========================================================================
HIPOTESIS, DUA, DAN AMBANGNYA MENGHITUNG KEDUANYA
===========================================================================

H1: exp_R FVG di bawah gerbang > 0 di 30 menit, diuji satu sampel lawan nol.
H2: exp_R FVG di bawah gerbang > exp_R di atas gerbang, yaitu pembalikan
    gerbangnya bertahan di 30 menit dan bukan cuma di 1 jam.

Ambang t Bonferroni untuk DUA kelompok. Walk-forward 8 fold, minimal 7 bertanda
sama untuk H2. Dua sel, XAUUSD dan BTCUSD di 30 menit, karena itu dua instrumen
yang ditradingkan; `cells_positive` karena itu bukan kriteria.

===========================================================================
YANG TIDAK DIJANJIKAN
===========================================================================

Bar halus 30 menit adalah 5 menit, rasio 6, terkasar di tabel `FINER`. Kontrol
di `docs/lowtf_resolution.json` menunjukkan rasio kasar MENGGELEMBUNGKAN
ekspektasi di keempat sel yang diuji di sana, jadi angka di sini batas ATAS.
Kalau H1 lolos, kontrol resolusinya wajib dijalankan sebelum satu order pun
dipasang atas dasarnya.

Ini juga bukan pengukuran "apakah FVG kecil menangkap rally hari itu". Satu hari
bukan populasi. Yang diukur populasi penuh; hari itu cuma yang membuat
pertanyaannya diajukan.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, GATE, MIN_CELL, cell_rows, one_sample_t, welch

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
NAME = "fvg"
#: Dua hipotesis yang dinilai, jadi Bonferroni menghitung dua.
T_THRESHOLD = _critical_t(2)
MIN_SIGN_FOLDS = 7


def _walk_below(rows: list[dict]) -> dict:
    """8 fold, dan yang dinilai selisih BAWAH minus ATAS di tiap fold.

    Digabung lintas sel lewat `pos` relatif, koreksi yang sama yang dipaksa
    celah riwayat 5 menit lawan 30 menit di setiap studi lain di sini. Trade yang
    masih hidup saat fold berikutnya mulai dibuang.
    """
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    out = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        below = [r["r"] for r in kept if not r["cleared"]]
        above = [r["r"] for r in kept if r["cleared"]]
        entry: dict = {"fold": k + 1, "n_below": len(below),
                       "n_above": len(above),
                       "purged": len(opened) - len(kept)}
        if len(below) >= 20 and len(above) >= 20:
            entry["difference"] = float(np.mean(below) - np.mean(above))
            entry["readable"] = True
        else:
            entry["readable"] = False
        out.append(entry)
    graded = [e for e in out if e["readable"]]
    return {"folds": out, "graded": len(graded),
            "positive": sum(1 for e in graded if e["difference"] > 0)}


def _walk_h1(rows: list[dict]) -> dict:
    """8 fold, dan yang dinilai TANDA sisi bawah sendiri di tiap fold.

    DITAMBAHKAN SETELAH RUN PERTAMA, dan itu harus dinyatakan. Praregistrasi
    hanya menuliskan walk-forward untuk H2, dan `_walk_below` di atas menilai
    SELISIH bawah-minus-atas, jadi ia butuh 20 trade di KEDUA sisi per fold.
    Sisi atas seluruhnya cuma 129 trade, sehingga run pertama menggradasi 2 dari
    8 fold dan H1 berjalan TANPA walk-forward sama sekali.

    Menambahkannya sekarang hanya bisa membuat H1 GAGAL, tidak pernah lolos:
    ia syarat tambahan di atas syarat yang sudah ditulis. Itu yang membuatnya
    bukan p-hacking, dan kalimat ini ada supaya pembaca bisa memeriksa klaim
    itu sendiri alih-alih mempercayainya.
    """
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    out = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        below = [r["r"] for r in kept if not r["cleared"]]
        entry: dict = {"fold": k + 1, "n_below": len(below),
                       "purged": len(opened) - len(kept)}
        if len(below) >= 20:
            entry["exp_r"] = float(np.mean(below))
            entry["readable"] = True
        else:
            entry["readable"] = False
        out.append(entry)
    graded = [e for e in out if e["readable"]]
    return {"folds": out, "graded": len(graded),
            "positive": sum(1 for e in graded if e["exp_r"] > 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()

    pooled: list[dict] = []
    cells: dict[str, dict] = {}
    for symbol, interval in CELLS:
        label = f"{symbol} {interval}"
        try:
            with contextlib.redirect_stdout(sys.stderr):
                rows, span = cell_rows(NAME, symbol, interval)
        except Exception as exc:
            cells[label] = {"error": str(exc)}
            continue
        pooled.extend(rows)
        below = np.array([r["r"] for r in rows if not r["cleared"]])
        above = np.array([r["r"] for r in rows if r["cleared"]])
        cells[label] = {
            "bars": span,
            "n_below": int(below.size), "n_above": int(above.size),
            "exp_r_below": float(below.mean()) if below.size else None,
            "exp_r_above": float(above.mean()) if above.size else None,
            "t_below_vs_zero": one_sample_t(below) if below.size > 1 else None,
            "readable": below.size >= MIN_CELL,
        }
        print(f"  {label:<14}n bawah {below.size:>6} exp "
              f"{cells[label]['exp_r_below']}  n atas {above.size:>6} exp "
              f"{cells[label]['exp_r_above']}", file=sys.stderr)

    out: dict = {
        "preregistration": {
            "source": "tools/fvg_inverted.py, 2026-09-02",
            "h1": "exp_R fvg di BAWAH gerbang > 0 di 30m",
            "h2": "exp_R di bawah gerbang > exp_R di atas, yaitu gerbangnya "
                  "tetap terbalik di 30m",
            "prior": "1h dan 4h: selisih -0,1005 dengan t=-4,48 dan "
                     "exp_r_below +0,0938 di n=16200, satu-satunya angka "
                     "positif di detectors_costed.json, belum diuji lawan nol",
            "t_threshold_bonferroni_2": T_THRESHOLD,
            "gate_atr": GATE, "folds": FOLDS,
            "min_sign_folds": MIN_SIGN_FOLDS,
            "cells": [f"{s} {i}" for s, i in CELLS],
            "caveat": "bar halus 5m, rasio 6, batas ATAS; kontrol resolusi "
                      "wajib sebelum order",
        },
        "cells": cells,
    }
    if not pooled:
        out["verdict"] = "tidak ada baris"
        json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
        return 0

    below = np.array([r["r"] for r in pooled if not r["cleared"]])
    above = np.array([r["r"] for r in pooled if r["cleared"]])
    wf = _walk_below(pooled)
    got = {
        "n_below": int(below.size), "n_above": int(above.size),
        "exp_r_below": float(below.mean()) if below.size else None,
        "exp_r_above": float(above.mean()) if above.size else None,
        "t_below_vs_zero": one_sample_t(below) if below.size > 1 else None,
        "difference": (float(below.mean() - above.mean())
                       if below.size and above.size else None),
        "welch_t": welch(below, above) if below.size and above.size else None,
    }
    wf_h1 = _walk_h1(pooled)
    out["pooled"] = got
    out["walk_forward_h2_difference"] = wf
    out["walk_forward_h1_below_side"] = wf_h1
    h1, h2, out["verdict"] = judge(got, wf, wf_h1)
    out["h1_below_beats_zero"] = h1
    out["h2_gate_stays_inverted"] = h2
    print(f"  pooled bawah {got['exp_r_below']} (t lawan nol "
          f"{got['t_below_vs_zero']}) atas {got['exp_r_above']} selisih "
          f"{got['difference']} welch {got['welch_t']} wf "
          f"{wf['positive']}/{wf['graded']}", file=sys.stderr)
    print(f"  VERDICT: {out['verdict']}", file=sys.stderr)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


def judge(pooled: dict, wf: dict, wf_h1: dict | None = None) -> tuple[bool, bool, str]:
    """Dua hipotesis dan kalimatnya, dipisah supaya `--selfcheck` bisa menyuntik.

    H1 yang menentukan apakah ia bisa ditradingkan; H2 cuma menyatakan
    gerbangnya tetap terbalik. H2 bisa lolos sementara kedua sisinya negatif,
    dan itu keadaan yang sudah terjadi untuk order_block di 1 jam.
    """
    # NaN DAN None DIPERIKSA, tidak diandalkan kebetulan. `abs(nan) > 2.24`
    # memang False, jadi ia aman tanpa pemeriksaan - tapi aman karena kebetulan
    # adalah cara sebuah gerbang berhenti mengikat saat baris lain berubah.
    raw = pooled.get("t_below_vs_zero")
    t0 = float(raw) if isinstance(raw, (int, float)) else float("nan")
    h1 = bool((pooled.get("exp_r_below") or 0.0) > 0
              and t0 == t0 and abs(t0) > T_THRESHOLD)
    if wf_h1 is not None:
        # Syarat TAMBAHAN, lihat `_walk_h1`. Ia hanya bisa menggagalkan H1.
        h1 = h1 and (wf_h1.get("graded", 0) >= FOLDS
                     and wf_h1.get("positive", 0) >= MIN_SIGN_FOLDS)
    h2 = bool((pooled.get("difference") or 0.0) > 0
              and abs(pooled.get("welch_t") or 0.0) > T_THRESHOLD
              and wf.get("graded", 0) >= FOLDS
              and wf.get("positive", 0) >= MIN_SIGN_FOLDS)
    return h1, h2, (
        "H1 DAN H2 LOLOS, fvg di bawah gerbang layak diukur lebih lanjut"
        if h1 and h2
        else "H1 lolos, H2 tidak: sisi bawah mengalahkan nol tapi bukan karena "
             "gerbangnya" if h1
        else "H2 lolos, H1 tidak: gerbangnya terbalik tapi sisi bawah tidak "
             "mengalahkan nol" if h2
        else "TIDAK LOLOS"
    )


def selfcheck() -> int:
    """Bukti bahwa `judge` bisa MENOLAK, satu syarat per baris."""
    wf_ok = {"graded": FOLDS, "positive": FOLDS}
    strong = {"exp_r_below": 0.09, "t_below_vs_zero": 5.0,
              "difference": 0.10, "welch_t": 5.0}
    assert judge(strong, wf_ok)[:2] == (True, True)
    # Walk-forward H1 hanya bisa MENGGAGALKAN, tidak pernah meloloskan.
    assert judge(strong, wf_ok, wf_ok)[0] is True
    assert judge(strong, wf_ok, {"graded": FOLDS, "positive": 6})[0] is False
    assert judge(strong, wf_ok, {"graded": 2, "positive": 2})[0] is False
    assert judge({**strong, "t_below_vs_zero": 1.9}, wf_ok)[0] is False
    assert judge({**strong, "exp_r_below": -0.09}, wf_ok)[0] is False
    assert judge({**strong, "t_below_vs_zero": float("nan")}, wf_ok)[0] is False
    assert judge({**strong, "t_below_vs_zero": None}, wf_ok)[0] is False
    assert judge({**strong, "welch_t": 1.9}, wf_ok)[1] is False
    assert judge({**strong, "difference": -0.10}, wf_ok)[1] is False
    assert judge(strong, {"graded": 6, "positive": 6})[1] is False
    assert judge(strong, {"graded": FOLDS, "positive": 6})[1] is False
    assert judge({}, {})[:2] == (False, False)
    kalimat = {judge(a, b)[2] for a, b in (
        (strong, wf_ok),
        ({**strong, "welch_t": 1.9}, wf_ok),
        ({**strong, "t_below_vs_zero": 1.9}, wf_ok),
        ({**strong, "welch_t": 1.9, "t_below_vs_zero": 1.9}, wf_ok),
    )}
    assert len(kalimat) == 4, kalimat
    print("selfcheck OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
