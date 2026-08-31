"""Gerbang departure 2,0 ATR, dijalankan pada populasi `fvg` dan `order_block`.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.detectors_costed > ../docs/detectors_costed.json

`tools/execute.py:161` hanya boleh memasang order dari `DETECTORS["supply_demand"]`.
`app/layers.py` menyatakan `fvg` "+10 to +25 points against placebo, and it passed
walk-forward 8 of 8 on two geometries" dan `order_block` "same result". Kalau itu
benar pada standar yang sama dengan `supply_demand`, dua detector terkunci di luar
jalur order tanpa alasan terukur. File ini menguji itu, dan hanya itu.

RIG-NYA SAMA, DAN ITU SELURUH MAKSUDNYA
Bukan implementasi ulang. `resolved_as` menukar entri `DETECTORS["supply_demand"]`
lalu memanggil `tools.intrabar.resolved` yang sudah ada, jadi entry, stop, target,
biaya per instrumen, exit flat di rollover, dan penyelesaian di bar halus adalah
KODE YANG SAMA yang menghasilkan angka `supply_demand` di `docs/QA-QUANT.md`
bagian 6. Dua angka yang hanya berbeda di satu hal bisa dibandingkan; dua yang
berbeda di dua tidak.

18 sel, sama persis dengan QA-QUANT bagian 6: 12 instrumen di 1 jam, 6 sel 4 jam.
Bar halus 5m untuk zona 1 jam, 15m untuk zona 4 jam.

===============================================================================
PRAREGISTRASI, ditulis sebelum satu angka pun dihitung untuk kedua populasi ini
===============================================================================

APA YANG SUDAH DIKETAHUI, dan karena itu bukan hipotesis di sini:
  supply_demand, resolusi halus, 18 sel: atas gerbang -0,0153 R (n=3.928),
  bawah gerbang -0,1258 R (n=10.885), selisih +0,1105 R, Welch t = +7,19,
  tanda positif di 17 dari 18 sel.

H1  Pada populasi `fvg`, gerbang departure >= 2,0 ATR memisahkan ekspektasi R
    setelah biaya: exp_R(atas) - exp_R(bawah) > 0.
H2  Sama untuk populasi `order_block`.

PERINGATAN YANG DITULIS DI DEPAN, BUKAN SESUDAH ANGKANYA KELUAR. `departure_atr`
TIDAK mengukur besaran yang sama di ketiga detector:
  supply_demand   excursion leg-out dibagi ATR di base  (app/detect/supply_demand.py:489)
  fvg             TINGGI GAP itu sendiri dibagi ATR     (app/detect/imbalance.py:325,268)
  order_block     besar impulse 5 bar dibagi ATR        (app/detect/imbalance.py:434,268)
Jadi "gerbang 2,0 ATR" pada `fvg` berarti "gap lebih tinggi dari 2 ATR", dan itu
konstruk lain. Ia juga terikat pada tinggi box, yang menentukan jarak stop, yang
menentukan satuan R dan `cost_r` sekaligus. Selisih positif pada `fvg` karena itu
punya penjelasan mekanis yang tidak dimiliki `supply_demand`, dan harus dibaca
begitu apa pun hasilnya.

AMBANG, DITETAPKAN DI DEPAN
  - statistik primer: Welch t dua sisi atas lawan bawah gerbang, pooled 18 sel.
  - koreksi Bonferroni untuk 2 detector: alpha 0,05 / 2 = 0,025, jadi |t| > 2,24.
  - peta tanda per sel: 18 sel, ambang Bonferroni per sel |t| > 2,88, angka yang
    sama yang dipakai QA-QUANT bagian 6.
  - sel dengan n < 20 di atas gerbang dilaporkan "terlalu sedikit" dan TIDAK
    dihitung di peta tanda. Batas ini ditulis sekarang, bukan setelah melihat n.
  - walk-forward 8 fold, sign test p = 2 / 2^8 = 0,0078, jadi hanya 8 dari 8 yang
    lolos. Fold dengan n < 20 di salah satu sisi dilaporkan tak terbaca dan
    menurunkan jumlah fold yang dinilai, yang MENAIKKAN p.
  - purging: baris dari `intrabar.resolved` membawa `exit == at`, jadi bar exit
    kasarnya tidak ada. Ia diperkirakan dari `fine_bars_held` dikali rasio step,
    dan trade yang masih hidup saat fold berikutnya mulai dibuang. Perkiraan,
    dan dilaporkan sebagai perkiraan.

VERDICT, ATURANNYA DITULIS SEBELUM ANGKANYA ADA
  PASS  hanya kalau KEEMPATNYA: selisih > 0, |Welch t| > 2,24, >= 14 dari 18 sel
        positif, dan walk-forward 8 dari 8.
  NULL  kalau selisihnya tidak beda dari nol pada ambang itu.
  FAIL  kalau selisihnya negatif dan |t| > 2,24.
Tidak ada kategori keempat, dan tidak ada yang dinaikkan kelasnya sesudahnya.
"""

from __future__ import annotations

import contextlib
import json
import math
import sys

import numpy as np

from app.detect import DETECTORS
from app.providers.base import INTERVALS
from tools import intrabar
from tools.costed import _params
from tools.intrabar import FINER
from tools.quant import clean

#: 18 sel, sama dengan QA-QUANT bagian 6.
CELLS = [(s, "1h") for s in (
    "XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
    "GBPJPY", "AUDUSD", "USDCAD", "BTCUSD", "US30", "USOIL",
)] + [(s, "4h") for s in (
    "XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "BTCUSD", "USOIL",
)]

GATE = 2.0
MIN_CELL = 20        # praregistrasi
MIN_FOLD = 20        # praregistrasi
T_POOLED = 2.24      # Bonferroni 2 detector
T_CELL = 2.88        # Bonferroni 18 sel
FOLDS = 8


def resolved_as(name: str, symbol: str, interval: str, fine: str) -> list[dict]:
    """`intrabar.resolved`, tapi zonanya dari `name`.

    ponytail: entri dict global ditukar sementara, bukan 150 baris resolusi
    disalin ulang. Batasnya: satu proses, satu thread, dan `finally` yang
    mengembalikannya. Kalau tool ini pernah dipakai bersamaan dengan sesuatu
    yang membaca `DETECTORS` di thread lain, ini yang harus diganti dulu.
    """
    # `intrabar.resolved` mencetak baris "entry tidak terisi" ke stdout, dan
    # stdout di sini adalah file JSON. Tanpa pengalihan ini output-nya bukan
    # JSON yang bisa di-parse, dan itu baru ketahuan setelah run selesai.
    with contextlib.redirect_stdout(sys.stderr):
        if name == "supply_demand":
            return intrabar.resolved(symbol, interval, fine)
        real, params = DETECTORS[name], _params(name)
        original = DETECTORS["supply_demand"]
        DETECTORS["supply_demand"] = lambda candles, _ignored: real(candles, params)
        try:
            return intrabar.resolved(symbol, interval, fine)
        finally:
            DETECTORS["supply_demand"] = original


def welch(a: np.ndarray, b: np.ndarray) -> float:
    """t Welch untuk dua varians yang tidak diasumsikan sama."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else float("nan")


def one_sample_t(x: np.ndarray) -> float:
    if len(x) < 2:
        return float("nan")
    se = x.std(ddof=1) / math.sqrt(len(x))
    return float(x.mean() / se) if se > 0 else float("nan")


def cell_rows(name: str, symbol: str, interval: str) -> tuple[list[dict], int]:
    fine = FINER[interval]
    rows = resolved_as(name, symbol, interval, fine)
    span = len(clean(symbol, interval)[0])
    ratio = INTERVALS[interval] // INTERVALS[fine]
    for r in rows:
        # Perkiraan bar kasar tempat trade selesai, untuk purging fold. Baris
        # dari `intrabar.resolved` tidak membawanya.
        r["exit_est"] = r["at"] + math.ceil(r["fine_bars_held"] / ratio)
        r["cell"] = f"{symbol} {interval}"
    # POSISI RELATIF DIUKUR PADA RENTANG YANG BISA DINILAI, BUKAN PADA SELURUH
    # DERET KASAR. Ditemukan 30 Agustus 2026 oleh `tools/conditioned_gaps.py`,
    # yang kena cacat yang sama dan memperbaikinya lebih dulu: riwayat 5 menit
    # menutup sekitar 347 hari sementara deret 1 jam-nya jauh lebih panjang,
    # jadi SETIAP trade yang bisa diselesaikan di bar halus duduk di bagian
    # akhir deret kasar. Dengan `at / len(candles)`, fold 1 dan 2 kosong secara
    # struktural dan fold 7 plus 8 memegang 80 persen trade: fvg terbaca
    # 0/0, 0/0, 15/329, 35/697, 54/1020, 36/1117, 220/5806, 329/7223. Itu
    # terbaca seperti walk-forward delapan potong dan sebenarnya dua.
    if rows:
        lo = min(r["at"] for r in rows)
        width = max(max(r["exit_est"] for r in rows) - lo, 1)
        for r in rows:
            r["pos"] = (r["at"] - lo) / width
            r["exit_pos"] = (r["exit_est"] - lo) / width
    return rows, span


def summarise(rows: list[dict]) -> dict:
    above = np.array([r["r"] for r in rows if r["cleared"]])
    below = np.array([r["r"] for r in rows if not r["cleared"]])
    out = {
        "n_above": len(above), "n_below": len(below),
        "exp_r_above": float(above.mean()) if len(above) else None,
        "exp_r_below": float(below.mean()) if len(below) else None,
        "t_above": one_sample_t(above) if len(above) else None,
    }
    if len(above) and len(below):
        out["difference"] = float(above.mean() - below.mean())
        out["welch_t"] = welch(above, below)
    else:
        out["difference"] = None
        out["welch_t"] = None
    return out


def walk_forward(rows: list[dict]) -> dict:
    """8 potongan waktu, digabung lintas sel lewat posisi relatif tiap sel.

    Digabung lewat `pos` (0,0 di awal deret sel itu, 1,0 di akhirnya) karena
    indeks bar dari dua instrumen bukan sumbu yang sama. Trade yang masih hidup
    saat potongan berikutnya mulai dibuang, memakai perkiraan exit di atas.
    """
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    folds, purged_total = [], 0
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        purged_total += len(opened) - len(kept)
        above = np.array([r["r"] for r in kept if r["cleared"]])
        below = np.array([r["r"] for r in kept if not r["cleared"]])
        entry = {"fold": k + 1, "n_above": len(above), "n_below": len(below),
                 "purged": len(opened) - len(kept)}
        if len(above) < MIN_FOLD or len(below) < MIN_FOLD:
            entry["readable"] = False
            entry["difference"] = None
        else:
            entry["readable"] = True
            entry["exp_r_above"] = float(above.mean())
            entry["exp_r_below"] = float(below.mean())
            entry["difference"] = float(above.mean() - below.mean())
            entry["welch_t"] = welch(above, below)
        folds.append(entry)
    graded = [f for f in folds if f["readable"]]
    positive = [f for f in graded if f["difference"] > 0]
    p = (2 / 2 ** len(graded)) if graded and (
        len(positive) in (0, len(graded))) else None
    return {
        "folds": folds,
        "graded": len(graded),
        "positive": len(positive),
        "failed": [f["fold"] for f in graded if f["difference"] <= 0],
        "sign_test_p": p,
        "purged": purged_total,
    }


def verdict(pooled: dict, cells_positive: int, cells_graded: int,
            wf: dict) -> str:
    """Aturan ditulis di docstring modul sebelum angkanya ada."""
    diff, t = pooled["difference"], pooled["welch_t"]
    if diff is None or t is None or math.isnan(t):
        return "NULL, tidak cukup data untuk membacanya"
    if diff < 0 and abs(t) > T_POOLED:
        return "FAIL, selisihnya negatif dan signifikan"
    if (diff > 0 and abs(t) > T_POOLED and cells_positive >= 14
            and wf["graded"] == FOLDS and wf["positive"] == FOLDS):
        return "PASS"
    return (f"NULL, gagal salah satu dari empat syarat "
            f"(t={t:+.2f} lawan {T_POOLED}, sel {cells_positive}/{cells_graded} "
            f"lawan 14/18, walk-forward {wf['positive']}/{wf['graded']} lawan 8/8)")


def run(name: str, log) -> dict:
    print(f"\n{'=' * 78}", file=log)
    print(f"{name}   gerbang departure >= {GATE} ATR, resolusi bar halus, "
          f"biaya terukur", file=log)
    print(f"{'=' * 78}", file=log)
    print(f"  {'sel':<14}{'n atas':>8}{'n bawah':>9}{'exp atas':>10}"
          f"{'exp bawah':>11}{'selisih':>10}{'welch t':>9}", file=log)

    pooled_rows: list[dict] = []
    cells: dict[str, dict] = {}
    for symbol, interval in CELLS:
        label = f"{symbol} {interval}"
        try:
            rows, span = cell_rows(name, symbol, interval)
        except Exception as exc:                      # provider bisa gagal
            print(f"  {label:<14}GAGAL: {exc}", file=log)
            cells[label] = {"error": str(exc)}
            continue
        pooled_rows.extend(rows)
        summary = summarise(rows)
        summary["bars"] = span
        if summary["n_above"] < MIN_CELL:
            summary["readable"] = False
            print(f"  {label:<14}{summary['n_above']:>8}"
                  f"{summary['n_below']:>9}   terlalu sedikit di atas gerbang "
                  f"(praregistrasi n >= {MIN_CELL})", file=log)
        else:
            summary["readable"] = True
            print(f"  {label:<14}{summary['n_above']:>8}{summary['n_below']:>9}"
                  f"{summary['exp_r_above']:>+10.4f}"
                  f"{summary['exp_r_below']:>+11.4f}"
                  f"{summary['difference']:>+10.4f}"
                  f"{summary['welch_t']:>+9.2f}", file=log)
        cells[label] = summary

    readable = [label for label, c in cells.items() if c.get("readable")]
    positive = [label for label in readable if cells[label]["difference"] > 0]
    beat_bonferroni = [
        label for label in readable
        if cells[label]["welch_t"] is not None
        and abs(cells[label]["welch_t"]) > T_CELL
    ]
    pooled = summarise(pooled_rows)
    wf = walk_forward(pooled_rows)

    print(f"\n  POOLED   atas {pooled['n_above']} trade "
          f"exp {pooled['exp_r_above']:+.4f} R, bawah {pooled['n_below']} trade "
          f"exp {pooled['exp_r_below']:+.4f} R", file=log)
    print(f"           selisih {pooled['difference']:+.4f} R, "
          f"Welch t = {pooled['welch_t']:+.2f}, ambang Bonferroni {T_POOLED}",
          file=log)
    print(f"           tanda positif di {len(positive)} dari {len(readable)} "
          f"sel yang terbaca ({len(cells)} sel dijalankan)", file=log)
    print(f"           sel yang lewat |t| > {T_CELL}: {beat_bonferroni}",
          file=log)

    print(f"\n  WALK-FORWARD, {FOLDS} potongan waktu, purged", file=log)
    for f in wf["folds"]:
        if f["readable"]:
            print(f"    fold {f['fold']}: atas n={f['n_above']:>4} "
                  f"bawah n={f['n_below']:>5}  selisih {f['difference']:>+8.4f} R"
                  f"  t={f['welch_t']:>+6.2f}  purged {f['purged']}", file=log)
        else:
            print(f"    fold {f['fold']}: atas n={f['n_above']:>4} "
                  f"bawah n={f['n_below']:>5}  TIDAK TERBACA "
                  f"(praregistrasi n >= {MIN_FOLD})  purged {f['purged']}",
                  file=log)
    print(f"    {wf['positive']} dari {wf['graded']} fold positif"
          + (f", sign test p={wf['sign_test_p']:.4f}"
             if wf["sign_test_p"] is not None else ", sign test tidak berlaku")
          + (f", fold yang GAGAL: {wf['failed']}" if wf["failed"] else ""),
          file=log)

    call = verdict(pooled, len(positive), len(readable), wf)
    print(f"\n  VERDICT {name}: {call}", file=log)

    return {
        "gate_atr": GATE,
        "cells": cells,
        "pooled": pooled,
        "cells_positive": len(positive),
        "cells_readable": len(readable),
        "cells_beating_bonferroni": beat_bonferroni,
        "walk_forward": wf,
        "verdict": call,
    }


def selfcheck() -> int:
    """Bukti bahwa gerbang di file ini tidak kosong.

        PYTHONPATH=. .venv/Scripts/python.exe -m tools.detectors_costed --selfcheck

    Tiga cacat disuntikkan ke aritmetika yang menghakimi, dan ketiganya harus
    membuatnya menolak. Tanpa ini `verdict` yang selalu menjawab PASS akan lolos
    tanpa suara, yang persis cara project ini pernah tertipu instrumennya
    sendiri.
    """
    lifted = {"difference": 0.5, "welch_t": 9.0}
    good_wf = {"graded": 8, "positive": 8, "failed": []}
    assert verdict(lifted, 18, 18, good_wf) == "PASS"
    # satu syarat dilanggar sekali per baris, dan tak satu pun boleh PASS
    assert verdict({"difference": 0.5, "welch_t": 1.9}, 18, 18, good_wf) != "PASS"
    assert verdict(lifted, 13, 18, good_wf) != "PASS"
    assert verdict(lifted, 18, 18,
                   {"graded": 8, "positive": 7, "failed": [3]}) != "PASS"
    assert verdict(lifted, 18, 18,
                   {"graded": 6, "positive": 6, "failed": []}) != "PASS"
    assert verdict({"difference": -0.5, "welch_t": -9.0}, 18, 18,
                   good_wf).startswith("FAIL")

    # Fold yang tidak terbaca tidak boleh diam-diam dihitung sebagai lolos.
    rows = [{"r": 1.0, "cleared": True, "pos": 0.01, "exit_pos": 0.02},
            {"r": -1.0, "cleared": False, "pos": 0.02, "exit_pos": 0.03}]
    wf = walk_forward(rows)
    assert wf["graded"] == 0 and wf["positive"] == 0, wf

    # Penukaran detector benar-benar menukar, dan mengembalikannya.
    before = DETECTORS["supply_demand"]
    try:
        resolved_as("fvg", "__tidak_ada__", "1h", "5m")
    except Exception:
        pass
    assert DETECTORS["supply_demand"] is before
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    if "--selfcheck" in sys.argv:
        return selfcheck()
    log = sys.stderr           # prosa ke stderr, JSON ke stdout
    out = {
        "preregistration": {
            "hypotheses": [
                "H1 fvg: exp_R(departure >= 2.0 ATR) - exp_R(below) > 0",
                "H2 order_block: same",
            ],
            "cells": len(CELLS),
            "gate_atr": GATE,
            "t_threshold_pooled_bonferroni_2": T_POOLED,
            "t_threshold_per_cell_bonferroni_18": T_CELL,
            "min_n_per_cell": MIN_CELL,
            "min_n_per_fold": MIN_FOLD,
            "folds": FOLDS,
            "sign_test_p_for_8_of_8": 2 / 2 ** FOLDS,
            "pass_rule": ("difference > 0 AND |welch t| > 2.24 AND cells "
                          "positive >= 14 AND walk-forward 8 of 8"),
            "caveat": ("departure_atr is NOT the same quantity across "
                       "detectors: leg-out excursion for supply_demand, gap "
                       "height for fvg, 5-bar impulse for order_block"),
            "reference_supply_demand": {
                "source": "docs/QA-QUANT.md section 6",
                "exp_r_above": -0.0153, "n_above": 3928,
                "exp_r_below": -0.1258, "n_below": 10885,
                "difference": 0.1105, "welch_t": 7.19,
                "cells_positive": "17 of 18",
            },
        },
        "detectors": {},
    }
    for name in ("fvg", "order_block"):
        out["detectors"][name] = run(name, log)
    json.dump(out, sys.stdout, indent=1, default=float)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
