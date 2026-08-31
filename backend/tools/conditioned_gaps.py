"""Apakah `gaps` dan `liquidity` MENGKONDISIKAN ekspektansi kohort zona?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.conditioned_gaps > ../docs/conditioned_gaps.json

PERTANYAAN INI BEDA DARI YANG SUDAH DIJAWAB. `app/layers.py` sudah mencatat
kedua layer ini NULL sebagai prediktor berdiri sendiri: gaps -0,58 ATR pada
n=1955 dengan t=-2,54 dan walk-forward 2 dari 8, liquidity -1,59pp pada n=4152
dengan walk-forward 3 dari 8. Itu mengukur apakah objeknya sendiri meramal.
File ini menanyakan yang lain: apakah KEBERADAAN objek itu di sekitar sebuah
zona memisahkan hasil zona tersebut. `tools/conditioned.py` sudah menguji 29
kolom sebagai pengkondisi dan nol lolos, dan tak satu pun dari 29 nama itu
menyentuh gaps atau liquidity.

PRIOR-NYA RENDAH DAN ITU DINYATAKAN DI DEPAN. 29 kolom nol lolos, dan
`docs/reality_check.json` (White's Reality Check, Hansen's SPA, Romano-Wolf
StepM) memastikan itu bukan artefak Bonferroni yang terlalu ketat. Hasil null
di sini adalah hasil yang paling mungkin, dan ia akan dilaporkan sebagai null.

=============================== PRAREGISTRASI ===============================
Ditulis 30 Agustus 2026, SEBELUM satu angka pun dihitung dari file ini.

HIPOTESIS. Untuk setiap kolom di `COLUMNS` dan setiap nilai kolom itu,
ekspektansi R kelompok berbeda dari ekspektansi R SISA populasi. Null-nya:
tidak berbeda. Dua sisi, karena tidak ada arah doktrinal yang bisa
dipertahankan: doktrin ICT mengatakan zona yang bertumpuk dengan gap atau level
bernama lebih "berkualitas", tapi kedua layer sudah terukur NEGATIF berdiri
sendiri, jadi menetapkan arah di depan berarti memilih tanda setelah melihat
data yang lain.

KOLOM, DAFTAR TERTUTUP. Tujuh, di `COLUMNS`. Menambah kolom berarti menulis
praregistrasi baru dengan tanggal baru, bukan menyunting tuple itu.

  ndog_in_band          NDOG yang masih digambar overlap band zona
  nwog_in_band          NWOG yang masih digambar overlap band zona
  atr_to_nearest_gap    jarak proximal zona ke CE gap terdekat, dalam ATR, pita
  pdh_pdl_in_band       PDH atau PDL yang berlaku ada di dalam band zona
  pwh_pwl_in_band       PWH atau PWL yang berlaku ada di dalam band zona
  atr_to_nearest_level  jarak proximal ke PDH/PDL/PWH/PWL terdekat, pita
  zone_side_vs_erl_irl  zona di dalam dealing range (IRL) atau di luarnya (ERL)

AMBANG, DIHITUNG BUKAN DIPILIH. K adalah jumlah kelompok dengan n >= 30, dan ia
DIHITUNG DI JALUR PERTAMA sebelum satu baris pun dilaporkan, persis seperti
`tools/conditioned.py`. Alpha dua sisi 0,05 dibagi K, dan |t| kritisnya dicetak
di atas tabel. K terbatas di 22 secara konstruksi (2+2+5+2+2+5+4).

SYARAT LOLOS, EMPAT, SEMUANYA DI DEPAN:
  1. n >= 30 di kelompok DAN di sisanya.
  2. |t| Welch lawan sisa populasi >= |t| kritis terkoreksi.
  3. Tanda delta yang sama di kedua paruh sampel.
  4. Walk-forward: 8 fold, dan tanda delta yang sama di >= 7 dari 8 fold yang
     terbaca. Sign test dua sisi untuk 7 dari 8 memberi p = 0,070 dan untuk 8
     dari 8 memberi p = 0,0078; ambangnya 7 karena itu titik di mana
     walk-forward membawa informasi tanpa menuntut kesempurnaan yang tidak
     dituntut gerbang mana pun di repo ini. Fold dengan n < 20 di salah satu
     lengan TIDAK TERBACA dan tidak dihitung lolos. Fold yang gagal dilaporkan
     per nomor.

POPULASI. Trade yang lolos gerbang departure >= 2,0 ATR, diselesaikan di bar
halus lewat `tools/intrabar.resolved`. Bukan pilihan kenyamanan:
`docs/QA-QUANT.md` mengukur +0,2021 R berubah jadi -0,0590 R kalau urutan
intrabar tidak dibayar, jadi angka apa pun di resolusi kasar akan menjawab
pertanyaan yang salah. Konsekuensinya populasi menyusut ke rentang yang punya
riwayat 5 menit, dan itu dinyatakan alih-alih disembunyikan.

INSTRUMEN. 12 sel di `CELLS`, 1 jam, sama dengan `tools/detectors_costed.py`.
Sel yang provider-nya gagal dilaporkan per nama, bukan didiamkan.

ANTI-LOOKAHEAD. Gap hanya masuk kalau `knowable_at <= waktu bar sentuhan`;
period level hanya masuk kalau `knowable_at <= waktu bar sentuhan`, dan
`knowable_at` sebuah PeriodLevel adalah bar pertama SESUDAH window-nya tutup;
`range_liquidity` memotong swing di `confirmed_at` sendiri. Tidak ada kolom yang
membaca `taken_at`, karena `taken_at` adalah bar masa depan.

KOLOM DEGENERAT MEMBATALKAN RUN. Kalau sebuah kolom hanya punya satu nilai
berbeda di seluruh populasi gabungan, tool ini keluar dengan exit code 1 dan
tidak melaporkan verdict apa pun. `tools/conditioned.py` sudah dua kali
menerbitkan kolom berisi False untuk 953 trade karena harness-nya lupa
menyalakan satu langkah, dan kedua kali itu terbaca sebagai fakta pasar. Kolom
yang tidak bervariasi bukan hasil null, ia harness yang rusak.
=============================================================================
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from bisect import bisect_right

import numpy as np

from app.detect import DETECTORS
from app.gaps import KEEP_DEFAULT, opening_gaps
from app.indicators import wilder_atr
from app.liquidity import previous_period_levels, range_liquidity
from app.models import SupplyDemandParams
from app.providers.base import INTERVALS
from tools import intrabar
from tools.calibrate import POPULATION
# ALPHA, MIN_GROUP dan nilai kritisnya DIPINJAM, bukan ditulis ulang. Dua
# implementasi ambang yang seharusnya sama adalah cara ambang berpisah diam-diam.
from tools.conditioned import ALPHA, MIN_GROUP, _critical_t
from tools.intrabar import FINER
from tools.quant import MT5_MAX_BARS, clean

#: Daftar tertutup, lihat praregistrasi di docstring modul.
COLUMNS = (
    "ndog_in_band",
    "nwog_in_band",
    "atr_to_nearest_gap",
    "pdh_pdl_in_band",
    "pwh_pwl_in_band",
    "atr_to_nearest_level",
    "zone_side_vs_erl_irl",
)

#: 12 sel 1 jam, sama dengan `tools/detectors_costed.py`. Sel 4 jam ditinggalkan
#: karena bar halusnya 15 menit dan populasi yang tersisa per sel terlalu tipis
#: untuk lantai n >= 30 per kelompok.
CELLS = [(s, "1h") for s in (
    "XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
    "GBPJPY", "AUDUSD", "USDCAD", "BTCUSD", "US30", "USOIL",
)]

FOLDS = 8
MIN_FOLD = 20         # praregistrasi, sama dengan detectors_costed
MIN_FOLDS_SAME = 7    # praregistrasi, sign test dua sisi p = 0,070

#: Potongan jarak ATR, dan keduanya angka yang SUDAH ada di repo ini: 0,25 ATR
#: adalah `app/plan.py:DEFAULT_STOP_BUFFER_ATR`, jarak stop dipasang di luar
#: distal, dan 2,0 ATR adalah gerbang departure yang mendefinisikan populasi ini.
#: 1,0 ATR adalah pembagi yang dinyatakan, bukan hasil pencarian. Memakai
#: kuartil populasi akan membuat pita jadi fungsi dari sampel.
CUTS = ((0.25, "<0.25"), (1.0, "0.25-1"), (2.0, "1-2"))


def _band(distance: float | None) -> str:
    """Jarak dalam ATR dipotong di `CUTS`. `None` adalah pita tersendiri.

    "none" berarti tidak ada objek untuk diukur jaraknya di bar itu, dan itu
    fakta yang berbeda dari "jauh". Menggabungkannya ke pita terjauh akan
    mencampur dua keadaan yang tidak sama.
    """
    if distance is None:
        return "none"
    for edge, name in CUTS:
        if distance < edge:
            return name
    return ">=2"


def _overlaps(low_a: float, high_a: float, low_b: float, high_b: float) -> bool:
    return low_a <= high_b and low_b <= high_a


def _latest_period(rows: list[tuple[int, int, float, float]], at: int):
    """Level periode yang BERLAKU di `at`: window tutup terakhir yang knowable.

    `rows` adalah `(knowable_at, window_to, high, low)` terurut menaik menurut
    `knowable_at`. `bisect_right` di situlah anti-lookahead-nya: bar sesudah
    `at` tidak pernah masuk walaupun deretnya dipanjangkan.
    """
    end = bisect_right(rows, at, key=lambda r: r[0])
    return rows[end - 1] if end else None


def cell_rows(symbol: str, interval: str) -> tuple[list[dict], int]:
    """Trade satu sel yang lolos gerbang, dengan state gaps dan liquidity.

    Resolusi trade TIDAK diimplementasi ulang: `intrabar.resolved` yang
    memanggilnya, dan bar-nya dimuat dengan `bars` yang sama supaya indeks `at`
    yang ia kembalikan menunjuk ke bar yang sama dengan yang dibaca di sini.
    """
    fine = FINER[interval]
    # `intrabar.resolved` mencetak baris "entry tidak terisi" ke stdout, dan
    # stdout di sini adalah file JSON.
    with contextlib.redirect_stdout(sys.stderr):
        base = [r for r in intrabar.resolved(symbol, interval, fine)
                if r["cleared"]]
    candles, _, _ = clean(symbol, interval, MT5_MAX_BARS)
    if not base or not candles:
        return [], len(candles)

    params = SupplyDemandParams(**{**POPULATION, "show_broken": True})
    zones, _ = DETECTORS["supply_demand"](candles, params)
    by_id = {z.id: z for z in zones}

    times = [c.time for c in candles]
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, params.atr_period)

    # GAP YANG MASIH DIGAMBAR, bukan seluruh riwayat. `KEEP_DEFAULT` = 5 adalah
    # angka yang `app/overlays.py` sudah pakai untuk memangkas band yang
    # ditampilkan, jadi kolom ini menanyakan tentang objek yang benar-benar ada
    # di layar. Memakai 1.462 band historis akan membuat "gap terdekat" jadi
    # artefak kepadatan, bukan pernyataan tentang bar itu.
    gaps = sorted(opening_gaps(candles), key=lambda g: g.knowable_at)
    gap_keys = [g.knowable_at for g in gaps]

    pairs: dict[tuple[str, int], dict] = {}
    for level in previous_period_levels(candles, ("day", "week")):
        slot = pairs.setdefault((level.period, level.window_from),
                                {"knowable_at": level.knowable_at,
                                 "window_to": level.window_to})
        slot["high" if level.side == "BSL" else "low"] = level.price
    day_rows: list[tuple[int, int, float, float]] = []
    week_rows: list[tuple[int, int, float, float]] = []
    for (period, _), slot in pairs.items():
        if "high" not in slot or "low" not in slot:
            continue
        target = day_rows if period == "day" else week_rows
        target.append((slot["knowable_at"], slot["window_to"],
                       slot["high"], slot["low"]))
    day_rows.sort()
    week_rows.sort()

    ratio = INTERVALS[interval] // INTERVALS[fine]
    out = []
    for row in base:
        touch = int(row["at"])
        zone = by_id.get(row["zone_id"])
        if zone is None or touch < 1:
            continue
        scale = float(atr[touch - 1])
        if scale <= 0:
            continue
        now = times[touch]
        state: dict[str, object] = {}

        end = bisect_right(gap_keys, now)
        drawn = gaps[max(0, end - KEEP_DEFAULT):end]
        for kind in ("NDOG", "NWOG"):
            state[f"{kind.lower()}_in_band"] = any(
                _overlaps(g.bottom, g.top, zone.bottom, zone.top)
                for g in drawn if g.kind == kind
            )
        state["atr_to_nearest_gap"] = _band(
            min((abs(zone.proximal - g.ce) / scale for g in drawn), default=None)
        )

        levels: list[float] = []
        for name, period_rows in (("pdh_pdl_in_band", day_rows),
                                  ("pwh_pwl_in_band", week_rows)):
            found = _latest_period(period_rows, now)
            if found is None:
                state[name] = False
                continue
            _, _, top, bottom = found
            levels += [top, bottom]
            state[name] = any(zone.bottom <= p <= zone.top for p in (top, bottom))
        state["atr_to_nearest_level"] = _band(
            min((abs(zone.proximal - p) / scale for p in levels), default=None)
        )

        found_range = range_liquidity(candles, (), at=now)
        if found_range is None:
            state["zone_side_vs_erl_irl"] = "no_range"
        elif zone.proximal > found_range.high:
            state["zone_side_vs_erl_irl"] = "above_erl"
        elif zone.proximal < found_range.low:
            state["zone_side_vs_erl_irl"] = "below_erl"
        else:
            state["zone_side_vs_erl_irl"] = "irl"

        out.append({
            "r": row["r"], "at": touch, "cell": f"{symbol} {interval}",
            "exit_est": touch + math.ceil(row["fine_bars_held"] / ratio),
            "state": state,
        })

    # POSISI RELATIF DIUKUR PADA RENTANG YANG BISA DINILAI, BUKAN PADA SELURUH
    # DERET, dan itu koreksi terhadap run pertama file ini pada 30 Agustus 2026.
    # Riwayat 5 menit terbatas di 99.999 bar, sekitar 347 hari, sedangkan deret
    # 1 jam-nya 1.400 hari; jadi SETIAP trade yang bisa diselesaikan di bar halus
    # duduk di seperempat terakhir deret kasar. Dengan `at / len(candles)` ke-457
    # trade run pertama jatuh di dua fold saja, dan tool melaporkan wf 2/2 untuk
    # hampir semua kelompok, yang terbaca seperti walk-forward yang lolos dan
    # sebenarnya walk-forward yang tidak pernah dijalankan.
    #
    # `tools/detectors_costed.py` memakai `at / len(candles)` yang sama pada
    # populasi `intrabar` yang sama. Cacat itu ada di sana juga dan TIDAK
    # diperbaiki dari sini.
    if out:
        lo = min(r["at"] for r in out)
        span = max(max(r["exit_est"] for r in out) - lo, 1)
        for r in out:
            r["pos"] = (r["at"] - lo) / span
            r["exit_pos"] = (r["exit_est"] - lo) / span
    return out, len(candles)


def welch(a: np.ndarray, b: np.ndarray) -> float:
    """t Welch untuk dua varians yang tidak diasumsikan sama."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else float("nan")


def walk_forward(rows: list[dict], column: str, key: object,
                 sign: float) -> dict:
    """8 potongan waktu, digabung lintas sel lewat posisi relatif tiap sel.

    Digabung lewat `pos` (0,0 di trade pertama sel itu, 1,0 di trade terakhir)
    karena indeks bar dua instrumen bukan sumbu yang sama. Lihat `cell_rows`
    untuk kenapa penyebutnya rentang yang bisa dinilai dan bukan panjang deret.
    Trade yang masih hidup saat potongan berikutnya mulai dibuang.
    """
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    graded, same, failed, deltas = 0, 0, [], []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        kept = [r for r in rows if lo <= r["pos"] < hi and r["exit_pos"] < hi]
        inside = [r["r"] for r in kept if r["state"].get(column) == key]
        outside = [r["r"] for r in kept if r["state"].get(column) != key]
        if len(inside) < MIN_FOLD or len(outside) < MIN_FOLD:
            deltas.append(None)
            continue
        graded += 1
        d = float(np.mean(inside) - np.mean(outside))
        deltas.append(d)
        if (d > 0) == (sign > 0):
            same += 1
        else:
            failed.append(k)
    return {"graded": graded, "same_sign": same, "failed_folds": failed,
            "deltas": deltas}


def _sign_p(same: int, graded: int) -> float:
    """p dua sisi sign test untuk `same` dari `graded`."""
    if graded == 0:
        return 1.0
    tail = sum(math.comb(graded, j) for j in range(same, graded + 1))
    return min(1.0, 2 * tail / 2 ** graded)


def verdict(n: int, n_rest: int, t: float, critical: float,
            same_halves: bool, wf: dict) -> str:
    """Empat syarat praregistrasi, dan tidak ada yang kelima.

    Dipisah jadi fungsi murni supaya `--selfcheck` bisa menyuntikkan cacat ke
    aritmetika yang menghakimi tanpa menjalankan provider apa pun.
    """
    if n < MIN_GROUP or n_rest < MIN_GROUP:
        return "n kecil"
    if not abs(t) >= critical:          # NaN jatuh ke sini, dan itu benar
        return ""
    if not same_halves:
        return ""
    if wf["graded"] < FOLDS or wf["same_sign"] < MIN_FOLDS_SAME:
        return ""
    return "MEMISAHKAN"


def selfcheck() -> int:
    """Bukti bahwa gerbang di file ini tidak kosong.

        PYTHONPATH=. .venv/Scripts/python.exe -m tools.conditioned_gaps --selfcheck

    Setiap syarat praregistrasi dilanggar sekali, dan tak satu pun boleh
    MEMISAHKAN. Tanpa ini sebuah `verdict` yang selalu menjawab kosong akan
    melaporkan null untuk SETIAP kolom selamanya, dan null yang datang dari
    aritmetika mati tidak bisa dibedakan dari null yang datang dari pasar.
    """
    full = {"graded": 8, "same_sign": 8, "failed_folds": [], "deltas": []}
    assert verdict(200, 900, 4.0, 3.4, True, full) == "MEMISAHKAN"
    assert verdict(29, 900, 4.0, 3.4, True, full) == "n kecil"
    assert verdict(200, 29, 4.0, 3.4, True, full) == "n kecil"
    assert verdict(200, 900, 3.0, 3.4, True, full) == ""
    assert verdict(200, 900, float("nan"), 3.4, True, full) == ""
    assert verdict(200, 900, 4.0, 3.4, False, full) == ""
    assert verdict(200, 900, 4.0, 3.4, True, {**full, "same_sign": 6}) == ""
    assert verdict(200, 900, 4.0, 3.4, True,
                   {"graded": 6, "same_sign": 6, "failed_folds": [],
                    "deltas": []}) == ""
    # Tanda negatif memisahkan juga: hipotesisnya dua sisi.
    assert verdict(200, 900, -4.0, 3.4, True, full) == "MEMISAHKAN"

    # Fold yang tidak terbaca tidak boleh diam-diam dihitung lolos.
    thin = [{"r": 1.0, "pos": 0.01, "exit_pos": 0.02, "state": {"c": True}},
            {"r": -1.0, "pos": 0.02, "exit_pos": 0.03, "state": {"c": False}}]
    assert walk_forward(thin, "c", True, 1.0)["graded"] == 0

    # EFEK YANG DISUNTIK HARUS TERBACA, kalau tidak seluruh rig ini buta dan
    # setiap kolom akan melaporkan null apa pun isinya.
    rows = []
    for i in range(1600):
        flag = i % 2 == 0
        rows.append({"r": 0.9 if flag else -0.9, "pos": i / 1600,
                     "exit_pos": (i + 1) / 1600, "state": {"c": flag}})
    values = np.array([r["r"] for r in rows if r["state"]["c"]])
    rest = np.array([r["r"] for r in rows if not r["state"]["c"]])
    wf = walk_forward(rows, "c", True, 1.0)
    assert verdict(len(values), len(rest), welch(values, rest),
                   _critical_t(22), True, wf) == "MEMISAHKAN"

    assert _band(None) == "none" and _band(0.1) == "<0.25"
    assert _band(0.25) == "0.25-1" and _band(1.0) == "1-2"
    assert _band(2.0) == ">=2"
    assert _sign_p(8, 8) < 0.01 and _sign_p(4, 8) > 0.5
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selfcheck", action="store_true")
    parser.add_argument("--cells", default="",
                        help="daftar SYMBOL@INTERVAL, koma; default 12 sel 1h")
    args = parser.parse_args()
    if args.selfcheck:
        return selfcheck()

    log = sys.stderr           # prosa ke stderr, JSON ke stdout
    cells = ([tuple(c.split("@")) for c in args.cells.split(",")]
             if args.cells else CELLS)

    rows: list[dict] = []
    per_cell: dict[str, dict] = {}
    for symbol, interval in cells:
        label = f"{symbol} {interval}"
        try:
            got, span = cell_rows(symbol, interval)
        except Exception as exc:                      # provider bisa gagal
            print(f"  {label:<14} GAGAL: {exc}", file=log)
            per_cell[label] = {"error": str(exc)}
            continue
        rows += got
        per_cell[label] = {
            "n": len(got), "bars": span,
            "exp_r": float(np.mean([r["r"] for r in got])) if got else None,
        }
        print(f"  {label:<14} n={len(got):4d} bar={span:6d}", file=log)

    out: dict[str, object] = {
        "preregistration": {
            "written": "2026-08-30, sebelum satu angka pun dihitung",
            "question": ("apakah gaps dan liquidity MENGKONDISIKAN ekspektansi "
                         "kohort zona, bukan apakah keduanya meramal sendiri"),
            "columns": list(COLUMNS),
            "two_sided": True,
            "alpha": ALPHA,
            "min_group": MIN_GROUP,
            "folds": FOLDS,
            "min_n_per_fold": MIN_FOLD,
            "min_folds_same_sign": MIN_FOLDS_SAME,
            "sign_test_p_for_7_of_8": _sign_p(7, 8),
            "sign_test_p_for_8_of_8": _sign_p(8, 8),
            "pass_rule": ("n >= 30 di kedua lengan DAN |t| Welch >= kritis "
                          "terkoreksi DAN tanda sama di kedua paruh DAN "
                          "8 fold terbaca dengan >= 7 bertanda sama"),
            "population": ("gerbang departure >= 2,0 ATR, diselesaikan di bar "
                           "halus lewat tools.intrabar.resolved"),
            "prior": ("rendah: 29 kolom sudah diuji di tools/conditioned.py dan "
                      "nol lolos, dan docs/reality_check.json memastikan itu "
                      "bukan artefak Bonferroni yang terlalu ketat"),
        },
        "cells": per_cell,
    }

    if not rows:
        print("tidak ada trade yang bisa dinilai", file=log)
        out["error"] = "populasi kosong"
        json.dump(out, sys.stdout, indent=1, default=float)
        print(file=sys.stdout)
        return 1

    everything = np.array([r["r"] for r in rows])
    out["population"] = {
        "n": len(rows), "exp_r": float(everything.mean()),
        "cells_used": sum(1 for c in per_cell.values() if "error" not in c),
    }
    print(f"\npopulasi gabungan n={len(rows)}  exp R {everything.mean():+.4f}",
          file=log)

    # KOLOM DEGENERAT MEMBATALKAN RUN, lihat praregistrasi.
    degenerate = [c for c in COLUMNS
                  if len({r["state"].get(c) for r in rows}) < 2]
    out["degenerate_columns"] = degenerate
    if degenerate:
        print(f"\nBLOCKER: kolom tidak bervariasi di seluruh populasi "
              f"gabungan: {degenerate}. Itu harness yang rusak, bukan hasil "
              f"null, jadi tidak ada verdict yang dilaporkan.", file=log)
        json.dump(out, sys.stdout, indent=1, default=float)
        print(file=sys.stdout)
        return 1

    # DIHITUNG SEBELUM SATU BARIS PUN DILAPORKAN. Ambangnya bergantung pada
    # berapa kelompok yang dinilai, jadi hitungannya harus di jalur pertama atau
    # ambang jadi fungsi dari apa yang sudah dilihat pembaca.
    judged = 0
    for column in COLUMNS:
        seen: dict[object, int] = {}
        for row in rows:
            key = row["state"].get(column)
            seen[key] = seen.get(key, 0) + 1
        judged += sum(1 for count in seen.values() if count >= MIN_GROUP)
    critical = _critical_t(judged)
    out["groups_judged"] = judged
    out["alpha_corrected"] = ALPHA / judged
    out["critical_t"] = critical
    print(f"{judged} grup layak dinilai, alpha {ALPHA}/{judged} = "
          f"{ALPHA / judged:.5f}, |t| kritis {critical:.2f}\n", file=log)

    # Paruh dipotong di POSISI RELATIF, bukan di indeks bar: 12 sel punya
    # panjang deret yang berbeda, jadi indeks bar bukan sumbu yang sama.
    cut = float(np.median([r["pos"] for r in rows]))
    results: dict[str, dict] = {}
    for column in COLUMNS:
        buckets: dict[object, list[dict]] = {}
        for row in rows:
            buckets.setdefault(row["state"].get(column), []).append(row)
        print(f"-- {column}", file=log)
        per_key: dict[str, dict] = {}
        for key in sorted(buckets, key=lambda k: (k is None, str(k))):
            group = buckets[key]
            values = np.array([r["r"] for r in group])
            rest = np.array([r["r"] for r in rows
                             if r["state"].get(column) != key])
            entry: dict[str, object] = {
                "n": len(group), "n_rest": len(rest),
                "exp_r": float(values.mean()) if len(values) else None,
            }
            if len(group) < MIN_GROUP or len(rest) < MIN_GROUP:
                entry["verdict"] = "n kecil"
                per_key[str(key)] = entry
                print(f"   {str(key):18s} n={len(group):4d}  terlalu kecil",
                      file=log)
                continue
            delta = float(values.mean() - rest.mean())
            t = welch(values, rest)
            se = math.sqrt(values.var(ddof=1) / len(values)
                           + rest.var(ddof=1) / len(rest))
            halves = []
            for lo, hi in ((None, cut), (cut, None)):
                sub = [r for r in rows
                       if (lo is None or r["pos"] >= lo)
                       and (hi is None or r["pos"] < hi)]
                a = [r["r"] for r in sub if r["state"].get(column) == key]
                b = [r["r"] for r in sub if r["state"].get(column) != key]
                halves.append(float(np.mean(a) - np.mean(b))
                              if a and b else float("nan"))
            same_halves = (not any(math.isnan(d) for d in halves)
                           and (halves[0] > 0) == (halves[1] > 0))
            wf = walk_forward(rows, column, key, delta)
            entry.update({
                "delta": delta,
                "ci95": [delta - 1.96 * se, delta + 1.96 * se],
                "t": t,
                "halves": halves,
                "same_sign_halves": same_halves,
                "walk_forward": wf,
                "sign_test_p": _sign_p(wf["same_sign"], wf["graded"]),
                "verdict": verdict(len(group), len(rest), t, critical,
                                   same_halves, wf),
            })
            per_key[str(key)] = entry
            print(f"   {str(key):18s} n={len(group):4d}  exp R "
                  f"{values.mean():+.4f}  delta {delta:+.4f} "
                  f"[{delta - 1.96 * se:+.3f},{delta + 1.96 * se:+.3f}]  "
                  f"t={t:+6.2f}  paruh {halves[0]:+.3f}/{halves[1]:+.3f}  "
                  f"wf {wf['same_sign']}/{wf['graded']} gagal "
                  f"{wf['failed_folds']}  {entry['verdict']}", file=log)
        results[column] = per_key
        print(file=log)

    out["columns"] = results
    passed = [f"{c}={k}" for c, keys in results.items()
              for k, e in keys.items() if e.get("verdict") == "MEMISAHKAN"]
    out["separating"] = passed
    print(f"lolos: {passed or f'NIHIL, nol dari {judged} grup'}", file=log)
    json.dump(out, sys.stdout, indent=1, default=float)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
