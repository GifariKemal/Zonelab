"""Apakah gerbang departure memisahkan di 30 menit, timeframe yang kita pakai?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.lowtf_costed > ../docs/lowtf_costed.json

===============================================================================
PRAREGISTRASI, ditulis sebelum satu angka pun dihitung
===============================================================================

KENAPA STUDI INI ADA. Setiap sel di `docs/detectors_costed.json` diukur di 1 jam
dan 4 jam. Daftarnya: 12 instrumen di 1h dan 6 di 4h, dan tidak satu pun di 30
menit atau 15 menit. Order hidup di akun ini dipasang di 30m dan 15m, jadi
SETIAP angka yang dipakai untuk membenarkannya diukur pada populasi yang berbeda
dari populasi yang ditradingkan. Itu bukan detail: gerbang biaya di
`tools/execute.py` sudah menyatakan bahwa instrumen yang sama lolos di 4 jam dan
gagal di 1 jam karena stop 4 jam lebih lebar sementara biayanya sama, dan 30
menit lebih sempit lagi.

DUA HIPOTESIS PER DETEKTOR, keduanya dipraregistrasi.

H1, pemisahan. exp_R(departure >= 2,0 ATR) - exp_R(di bawah) > 0. Ini pertanyaan
yang sama yang `detectors_costed.py` tanyakan, dipindah ke 30m.

H2, DAN INI YANG SEBENARNYA MENENTUKAN APAKAH BOLEH DITRADINGKAN. exp_R di atas
gerbang > 0, diuji satu sampel lawan nol. H1 bisa lolos sementara kedua sisinya
negatif, dan itu persis yang terjadi di 1 jam: order_block pooled memisahkan
dengan t=+6,95 sementara populasi di atas gerbangnya sendiri -0,0429 R dengan
t=-6,21, yaitu negatif signifikan. Sebuah gerbang yang memisahkan dua populasi
yang keduanya kalah tidak memberi trade, ia cuma memberi urutan kekalahan.

EMPAT KELOMPOK YANG DINILAI: dua detektor kali dua hipotesis. Ambang t
Bonferroni untuk 4, dari `tools.conditioned._critical_t`.

DUA SEL SAJA, XAUUSD dan BTCUSD di 30m, karena itu dua instrumen yang
ditradingkan. Ini menurunkan daya dibanding 18 sel dan itu dinyatakan di sini,
bukan ditutupi: `cells_positive` tidak bisa jadi kriteria pada dua sel, jadi
aturan lolosnya memakai walk-forward dan t pooled saja.

ATURAN LOLOS, per detektor:
  H1 lolos bila selisih > 0 DAN |welch t| > ambang Bonferroni DAN walk-forward
     minimal 7 dari 8 fold bertanda sama (uji tanda, p = 0,0352).
  H2 lolos bila exp_R di atas gerbang > 0 DAN |t satu sampel| > ambang yang sama.

RESOLUSI, dan ia dipilih untuk span bukan untuk presisi. Bar halus 30m adalah
5m, rasio 6 bar halus per bar kasar, terkasar di tabel `FINER`. Riwayat 1 menit
di mesin ini cuma 103 hari (XAUUSD) dan 69 hari (BTCUSD), sementara 5 menit
memberi 516 dan 347 hari. Resolusi mengubah jawaban di repo ini, edge +0,2 R
jadi -0,0153 R saat diukur halus, jadi angka di sini TIDAK sebanding langsung
dengan angka 1 jam yang rasionya 12.

YANG TIDAK DIJANJIKAN. Studi ini tidak mengukur 15 menit. Riwayat 1 menit BTCUSD
69 hari dibagi 8 fold adalah 8,6 hari per fold, dan `MIN_FOLD` 20 trade tidak
akan terpenuhi dengan jujur di sana.
"""

from __future__ import annotations

import contextlib
import json
import math
import sys

import numpy as np

from tools.conditioned import _critical_t
from tools.detectors_costed import (
    FOLDS,
    GATE,
    MIN_CELL,
    cell_rows,
    one_sample_t,
    summarise,
    walk_forward,
)

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
DETECTORS_TESTED = ("supply_demand", "order_block")
#: Empat kelompok dinilai: 2 detektor kali 2 hipotesis.
T_THRESHOLD = _critical_t(4)
MIN_SIGN_FOLDS = 7


def judge(pooled: dict, wf: dict) -> tuple[bool, bool, str]:
    """Dua hipotesis dan kalimat verdict-nya, dipisah supaya bisa dites.

    Inline sebelumnya, dan inline berarti tidak ada cara membuktikan bahwa
    penghakimannya bisa MENOLAK. `--selfcheck` di bawah menyuntik satu
    pelanggaran per baris ke fungsi ini.
    """
    same = wf.get("positive", 0)
    graded = wf.get("graded", 0)
    h1 = ((pooled.get("difference") or 0.0) > 0
          and abs(pooled.get("welch_t") or 0.0) > T_THRESHOLD
          and graded >= FOLDS and same >= MIN_SIGN_FOLDS)
    t_zero = pooled.get("t_above_vs_zero")
    h2 = ((pooled.get("exp_r_above") or 0.0) > 0
          and t_zero is not None and not math.isnan(t_zero)
          and abs(t_zero) > T_THRESHOLD)
    return h1, h2, (
        "H1 DAN H2 LOLOS, boleh ditradingkan di 30m" if h1 and h2
        else "H1 lolos, H2 TIDAK: gerbangnya memisahkan dua populasi yang "
             "keduanya kalah" if h1
        else "H2 lolos, H1 TIDAK: di atas gerbang menang tapi gerbangnya "
             "bukan yang memisahkannya" if h2
        else "TIDAK LOLOS"
    )


def selfcheck() -> int:
    """Bukti bahwa penghakiman di file ini tidak kosong.

        PYTHONPATH=. .venv/Scripts/python.exe -m tools.lowtf_costed --selfcheck

    Satu syarat dilanggar per baris, dan tak satu pun boleh menghasilkan lolos.
    Tanpa ini sebuah `judge` yang selalu menjawab LOLOS akan lewat tanpa suara,
    yang persis cara project ini pernah tertipu instrumennya sendiri.
    """
    good_wf = {"graded": FOLDS, "positive": FOLDS}
    strong = {"difference": 0.5, "welch_t": 9.0, "exp_r_above": 0.2,
              "t_above_vs_zero": 9.0}
    assert judge(strong, good_wf)[:2] == (True, True)

    # H1 gugur satu per satu
    assert judge({**strong, "welch_t": 1.9}, good_wf)[0] is False
    assert judge({**strong, "difference": -0.5}, good_wf)[0] is False
    assert judge(strong, {"graded": 6, "positive": 6})[0] is False
    assert judge(strong, {"graded": FOLDS,
                          "positive": MIN_SIGN_FOLDS - 1})[0] is False
    # H2 gugur satu per satu, dan H1 tidak boleh menyelamatkannya
    assert judge({**strong, "exp_r_above": -0.2}, good_wf)[1] is False
    assert judge({**strong, "t_above_vs_zero": 1.9}, good_wf)[1] is False
    assert judge({**strong, "t_above_vs_zero": float("nan")},
                 good_wf)[1] is False
    assert judge({**strong, "t_above_vs_zero": None}, good_wf)[1] is False
    # Dan kalimatnya harus membedakan keempat keadaan
    kalimat = {judge(a, b)[2] for a, b in (
        (strong, good_wf),
        ({**strong, "t_above_vs_zero": 1.9}, good_wf),
        ({**strong, "welch_t": 1.9}, good_wf),
        ({**strong, "welch_t": 1.9, "t_above_vs_zero": 1.9}, good_wf),
    )}
    assert len(kalimat) == 4, kalimat
    # Nol baris tidak boleh terbaca sebagai lolos.
    assert judge({}, {})[:2] == (False, False)
    print("selfcheck OK", file=sys.stderr)
    return 0


def _f(v) -> str:
    """None dicetak sebagai None, bukan meledak di format spec."""
    return "None" if v is None else f"{v:+.4f}"


def run_one(name: str, log) -> dict:
    print(f"\n{'=' * 78}\n{name}   30m, gerbang {GATE} ATR, bar halus 5m, "
          f"biaya terukur\n{'=' * 78}", file=log)
    pooled: list[dict] = []
    cells: dict[str, dict] = {}
    for symbol, interval in CELLS:
        label = f"{symbol} {interval}"
        try:
            rows, span = cell_rows(name, symbol, interval)
        except Exception as exc:
            print(f"  {label:<14}GAGAL: {exc}", file=log)
            cells[label] = {"error": str(exc)}
            continue
        pooled.extend(rows)
        got = summarise(rows)
        got["bars"] = span
        got["readable"] = got["n_above"] >= MIN_CELL
        cells[label] = got
        print(f"  {label:<14}n atas {got['n_above']:>6}  n bawah "
              f"{got['n_below']:>6}  exp atas {_f(got['exp_r_above'])}  "
              f"exp bawah {_f(got['exp_r_below'])}  selisih "
              f"{_f(got['difference'])}  welch t {_f(got['welch_t'])}",
              file=log)

    out: dict = {"cells": cells, "gate_atr": GATE, "fine": "5m"}
    if not pooled:
        out["verdict"] = "tidak ada baris"
        return out

    got = summarise(pooled)
    # `cleared`, nama field yang `summarise` pakai untuk sisi atas gerbang.
    above = np.array([r["r"] for r in pooled if r["cleared"]])
    got["t_above_vs_zero"] = one_sample_t(above) if above.size else float("nan")
    out["pooled"] = got
    out["walk_forward"] = wf = walk_forward(pooled)

    h1, h2, out["verdict"] = judge(got, wf)
    out["h1_gate_separates"] = h1
    out["h2_above_gate_beats_zero"] = h2
    same = wf.get("positive", 0)
    graded = wf.get("graded", 0)
    print(f"  pooled  exp atas {_f(got['exp_r_above'])} (t lawan nol "
          f"{_f(got['t_above_vs_zero'])})  selisih {_f(got['difference'])} "
          f"(welch t {_f(got['welch_t'])})  walk-forward {same}/{graded}",
          file=log)
    print(f"  ambang t Bonferroni 4 kelompok: {T_THRESHOLD:.3f}", file=log)
    print(f"  VERDICT: {out['verdict']}", file=log)
    return out


def main() -> int:
    if "--selfcheck" in sys.argv:
        return selfcheck()
    log = sys.stderr
    out = {
        "preregistration": {
            "source": "tools/lowtf_costed.py",
            "question": "apakah gerbang departure memisahkan di 30m, dan apakah "
                        "populasi di atasnya mengalahkan nol",
            "cells": [f"{s} {i}" for s, i in CELLS],
            "detectors": list(DETECTORS_TESTED),
            "judged_groups": 2 * len(DETECTORS_TESTED),
            "t_threshold_bonferroni_4": T_THRESHOLD,
            "folds": FOLDS,
            "min_sign_folds": MIN_SIGN_FOLDS,
            "sign_test_p_for_7_of_8": 0.0352,
            "fine_bars": "5m, rasio 6 per bar kasar, TERKASAR di tabel FINER",
            "why": "setiap sel di detectors_costed.json diukur di 1h dan 4h; "
                   "order hidup dipasang di 30m dan 15m",
            "not_measured": "15m, karena riwayat 1m cuma 103 hari XAUUSD dan "
                            "69 hari BTCUSD",
        },
        "detectors": {},
    }
    for name in DETECTORS_TESTED:
        with contextlib.redirect_stdout(sys.stderr):
            out["detectors"][name] = run_one(name, log)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
