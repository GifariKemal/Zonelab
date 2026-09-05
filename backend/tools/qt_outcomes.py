"""Praregistrasi keenam: apakah checklist Quarterly Theory memisahkan hasil.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.qt_outcomes \
        > ../docs/qt_outcomes.json

Ditulis 5 September 2026, SEBELUM satu angka pun dihitung. Bagian 1 sampai 7
di bawah ini adalah praregistrasinya; angkanya keluar di stdout sebagai JSON.

===========================================================================
1. PERTANYAANNYA
===========================================================================

`Pictures/Bang Nas/QT-Auto-Scanner/qt-entry-checklist.html` memberi resep
lengkap: lima gate wajib, sepuluh builder berbobot, skor 0..17, lima tier, dan
tabel ukuran posisi yang MEMBESARKAN lot di tier A dan A+. Yang belum pernah
dijawab di repo ini ada tiga:

  a. Apakah skor QT itu sendiri memisahkan hasil. `docs/checklist_outcomes.json`
     sudah menjawabnya untuk skor `met` versi repo ini - `separates: false`,
     n=1855 - tapi `met` menghitung tujuh belas klausa TANPA BOBOT, sementara
     QT memberi bobot 2 pada SSMT dan sequence dan menuntut lima gate lolos
     sebagai syarat. Skor yang berbeda adalah hipotesis yang berbeda.

  b. Apakah TABEL UKURAN POSISI-nya menambah atau mengurangi. Ini pertanyaan
     yang paling mahal kalau salah: tier A dan A+ memerintahkan 125 persen
     ukuran, tier C memerintahkan 50 persen, dan tier F memerintahkan nol.
     Kalau skornya tidak informatif, aturan itu memperbesar taruhan secara acak
     dan menaikkan varians tanpa menaikkan ekspektansi. Kalau tandanya
     TERBALIK, ia memperbesar taruhan pada kohort terburuk.

  c. Apakah keenam builder yang repo ini tidak punya kolomnya - B2 sequence,
     B3 true opens, B6 Judas, B7 truth asset, B8 volume, B9 news - memisahkan
     satu per satu. Lima dari enam sekarang punya kolom di `app/qt.py`. B9
     tidak bisa punya, dan alasannya di bagian 6.

===========================================================================
2. POPULASI, DAN KENAPA IA DIIMPOR ALIH-ALIH DIBANGUN ULANG
===========================================================================

`rows_for` diimpor dari `tools/checklist_outcomes.py` tanpa satu baris pun
diubah. Rig yang membangun ulang populasinya sendiri sedang menguji dua hal
sekaligus, dan kalau hasilnya berbeda dari studi kelima tidak akan ada yang
tahu apakah penyebabnya skor QT atau populasi baru. Peringatan itu ditulis di
docstring rig kelima sendiri, dan ini mematuhinya.

Jadi: delapan instrumen, 1 jam, resolusi bar 5 menit, first touch zona
`supply_demand` dengan `departure_atr >= 2.0`, R setelah biaya `exness_raw`,
flat di rollover. Identik dengan studi kelima, baris demi baris.

===========================================================================
3. SKOR QT, DISALIN DARI SUMBERNYA
===========================================================================

Rumusnya dari `QT-Auto-Scanner/python/scoring.py`:

    total = (5 if semua_gate_lolos else jumlah_gate_lolos) + skor_builder
    tier  = A+ bila >=15, A bila >=12, B bila >=9, C bila >=5, selain itu F
    ukuran = {F: 0%, C: 50%, B: 100%, A: 125%, A+: 125%}

Pemetaan ke kolom yang repo ini punya, DAFTAR TERTUTUP, ditulis sekarang:

    GATE (masing-masing 1, kelimanya wajib)
      G1 bias HTF          -> `bias_agrees`
      G2 waktu sesi        -> `killzone`
      G3 zona PDA valid    -> `poi_families`
      G4 CISD              -> `cisd_in_band`
      G5 risiko R:R >= 2   -> `min_rr`

    BUILDER (bobot dari tabel HTML-nya, total 12)
      B1 SSMT          +2  -> `ssmt`
      B2 sequence      +2  -> `qt_sequence` (grid repo; lihat varian seq_source)
      B3 true opens    +1  -> `qt_true_opens`
      B4 liq sweep     +1  -> `manipulation_seen`
      B5 DFR           +1  -> `dfr_side`
      B6 Judas         +1  -> `qt_judas_repo`
      B7 truth asset   +1  -> `qt_truth_pair`
      B8 volume        +1  -> `qt_vwap_near` ATAU `qt_vwap_at_open`
      B9 news          +1  -> TIDAK BISA DIUKUR, lihat bagian 6
      B10 HTF nesting  +1  -> `htf_nested`

DIAM TIDAK LOLOS SEBAGAI SETUJU. Kolom yang `None` dihitung TIDAK terpenuhi,
baik di gate maupun di builder. Itu aturan `app/ict.py:Setup.failed_required`
yang sudah berlaku di jalur order, dan memakai aturan yang berbeda di sini akan
membuat skornya bukan skor yang bisa dijalankan.

VARIAN, DIDAFTARKAN SEKARANG SUPAYA BUKAN PENCARIAN. Empat, dan hasil keempatnya
dilaporkan apa pun bunyinya:
  - `b9_zero`   : B9 tidak pernah diberi. HEADLINE, karena B9 tidak terukur.
  - `b9_one`    : B9 selalu diberi, yang adalah persis yang implementasi
                  referensinya lakukan (`scoring.py` menetapkan
                  `news_clear=True` tanpa syarat).
  - `judas_source`: B6 dibaca dari tabel sumbernya (`qt_judas_source`) alih-alih
                  dari `app/judas.py`, karena keduanya BERLAWANAN. Lihat
                  `app/qt.py` divergensi 1.
  - `truth_vol` : B7 dibaca dari argmin stdev return, bacaan implementasi
                  referensinya, alih-alih skor konsolidasi repo ini.
  - `seq_source`: B2 dibaca dari grid kuarter SUMBERNYA (19:30 New York)
                  alih-alih grid repo ini (18:00). Selisihnya 90 menit dan
                  itu divergensi terbesar yang ditemukan; lihat `app/qt.py`
                  divergensi 5. Lengan ini juga yang sebanding dengan venue
                  MT5, karena `QTClock.mqh` memakai grid sumbernya.

===========================================================================
4. HIPOTESIS, DAN AMBANGNYA
===========================================================================

H-QT-A (SKOR), tiga bacaan, bentuknya sama persis dengan studi kelima:
  A1 MONOTON. exp R tidak menurun pada setiap pasangan level skor bertetangga
     yang `n >= MIN_GROUP`. Lolos hanya kalau SEMUA pasangan tidak menurun.
  A2 TREN. Spearman rho antara skor dan R positif, |t| melewati kritis.
  A3 SPLIT MEDIAN. exp R di atas median melebihi di bawahnya, |t| melewati
     kritis, dan tandanya sama di kedua paruh.

H-QT-B (GATE). Kohort yang kelima gate-nya lolos mengalahkan kohort yang tidak.
  Ini bacaan yang paling dekat dengan apa yang checklist itu PERINTAHKAN:
  ia bilang satu gate gagal berarti jangan trade sama sekali.

H-QT-C (UKURAN POSISI). Ekspektansi berbobot ukuran,
  `sum(ukuran * R) / sum(ukuran)`, melebihi ekspektansi rata, `mean(R)`.
  Dilaporkan bersama total R absolut dan jumlah trade yang lolos filter tier F,
  karena aturan ukuran itu SEKALIGUS filter: tier F berukuran nol.
  Lolos kalau selisihnya positif, tandanya sama di kedua paruh, DAN uji
  kovarians `cov(ukuran, R)` melewati ambang varian. Tanpa uji ketiga itu
  kriterianya dilewati derau murni sekitar seperempat waktu, dan itu terukur
  di selftest-nya sendiri.

H-QT-D (PER KOLOM). Kesebelas kolom `qt_` plus kolom turunan `qt_b8`, satu per
  satu lawan sisa populasi. Memisahkan kalau ketiganya lolos, sama dengan H-B
  studi kelima:
    1. `n >= 30` per grup.
    2. `|t|` Welch melewati nilai kritis Bonferroni.
    3. Tanda selisihnya bertahan di kedua paruh sampel.

KOREKSI BANYAK-PERBANDINGAN. Alpha dua sisi 0,05 dibagi K, dengan K jumlah
SELURUH grup yang layak dinilai, dihitung sebelum satu baris pun DILAPORKAN,
lewat `tools/conditioned.py:_critical_t` yang sama.

DUA AMBANG, dan yang kedua lebih ketat. H-QT-D menguji kedua belas kolom sekali,
jadi K menutupinya. H-QT-A, B dan C dilaporkan SEKALI PER VARIAN, jadi vonis
ketiganya dinilai pada `alpha / (K * jumlah varian)`. Bonferroni di atas varian
yang berkorelasi tinggi lebih ketat daripada perlu; ketat adalah arah yang aman
dan itu yang dipilih.

KONTROL INSTRUMEN. Delapan instrumen ini ekspektansi dasarnya berbeda tanda.
Jadi A2, A3, B dan D dihitung DUA KALI dan keduanya dilaporkan: sekali pada R
mentah, sekali pada R yang sudah dikurangi rata-rata instrumennya sendiri.
Kalau keduanya tidak sepakat, yang di-demean yang dipercaya, dan itu ditetapkan
sekarang.

WALK-FORWARD. Delapan fold sama-banyak, urut waktu. Fold yang gagal dilaporkan
dengan namanya.

===========================================================================
5. YANG TIDAK AKAN DILAKUKAN
===========================================================================

  - Tidak menambah instrumen, kolom, atau timeframe setelah melihat hasil.
  - Tidak menyetel ulang bobot builder. Bobotnya dari tabel HTML-nya dan bukan
    dari data ini. Menyetelnya di sini akan memfit noise dengan sebelas
    parameter di atas 1855 baris, dan `formation_score` di repo ini sudah
    memeringkat TERBALIK ketika dibobot (AUC 0,464 dan 0,477).
  - Tidak menggeser ambang tier. Lima batas itu punya sumbernya.
  - Tidak membuang instrumen yang ekspektansinya negatif.

===========================================================================
6. YANG SUDAH DIKETAHUI TIDAK BISA DIJAWAB, DINYATAKAN DI DEPAN
===========================================================================

B9 `news_clear` TIDAK TERUKUR DAN TIDAK AKAN. `app/news.py` menyajikan
`ff_calendar_thisweek.json`, dan `_lastweek`, `_nextweek`, `_thismonth`,
`_thisyear` semuanya HTTP 404. Paket MetaTrader5 5.0.6090 di mesin ini tidak
punya satu pun fungsi kalender. Tidak ada riwayat untuk menilai bar masa lalu,
jadi kolom B9 yang diisi kalender hari ini akan mengukur minggu ini lawan bar
tahun lalu. Ia dilaporkan sebagai konstan di kedua arah dan tidak pernah
sebagai temuan.

CVD, paruh kedua B8, juga absen. Tick MT5 pada CFD FX dan logam tidak membawa
sisi transaksi yang bisa dipercaya, jadi CVD di sini akan jadi INFERENSI aturan
tick Lee-Ready, bukan pengukuran. B8 di bawah adalah paruh lokasinya saja.

TRUTH ASSET DI SINI ADALAH PASANGAN, BUKAN TRIAD. Rig kelima memuat simbol plus
SATU partner `TCISD_PARTNER`, karena partner itu yang dipakai kolom SSMT-nya.
Menambah anggota ketiga akan memuat deret ketiga per simbol dan mengubah
populasi, yang bagian 2 melarang. Jadi B7 di sini menjawab "apakah simbol ini
lebih tenang dari partnernya", dan bukan "apakah ia yang paling tenang dari
tiga". Batas itu dinyatakan, bukan disembunyikan.

===========================================================================
7. APA YANG SUDAH DIKETAHUI SEBELUM RUN INI, SUPAYA HASILNYA TIDAK DIBACA
   SEBAGAI KEJUTAN YANG BUKAN
===========================================================================

Lima dari lima belas item QT sudah punya angka di `docs/checklist_outcomes.json`
dan tak satu pun memisahkan, kecuali `dfr_side` yang memisahkan dengan tanda
TERBALIK: terpenuhi -0,0660 R (n=1141, 8/8 simbol), tidak terpenuhi +0,1481 R
(n=341). `dfr_side` adalah builder B5 di checklist QT. Jadi salah satu dari dua
belas poin builder itu sudah diketahui menunjuk ke arah yang salah sebelum
skornya dijumlahkan, dan kalau skor QT nanti gagal memisahkan, B5 adalah
tersangka yang sudah bernama.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import pathlib
import sys

import numpy as np

from tools.checklist_outcomes import (
    FOLDS,
    QT_COLUMNS,
    SYMBOLS,
    _halves_agree,
    _levels,
    _monotone,
    _spearman,
    _welch,
    rows_for,
)
from tools.conditioned import ALPHA, MIN_GROUP, _critical_t
from tools.intrabar import FINER

#: Gate QT, dan kolom repo ini yang menjawabnya. Kelimanya wajib.
GATES: dict[str, str] = {
    "G1_bias": "bias_agrees",
    "G2_session": "killzone",
    "G3_pda": "poi_families",
    "G4_cisd": "cisd_in_band",
    "G5_risk": "min_rr",
}

#: Builder QT, kolomnya, dan bobotnya. Bobot dari tabel HTML-nya, total 12.
#: B8 dan B9 ditangani terpisah: B8 adalah OR dua kolom, B9 tidak terukur.
BUILDERS: tuple[tuple[str, str, int], ...] = (
    ("B1_ssmt", "ssmt", 2),
    ("B2_sequence", "qt_sequence", 2),
    ("B3_true_opens", "qt_true_opens", 1),
    ("B4_sweep", "manipulation_seen", 1),
    ("B5_dfr", "dfr_side", 1),
    ("B6_judas", "qt_judas_repo", 1),
    ("B7_truth", "qt_truth_pair", 1),
    ("B10_nesting", "htf_nested", 1),
)

#: Tier QT dan pengali ukuran posisinya, dari tabel Bagian C dan Manajemen
#: Risiko di HTML-nya. Batas bawah inklusif, diperiksa dari yang tertinggi.
TIERS: tuple[tuple[int, str, float], ...] = (
    (15, "A+", 1.25),
    (12, "A", 1.25),
    (9, "B", 1.00),
    (5, "C", 0.50),
    (0, "F", 0.00),
)

#: Varian yang didaftarkan di bagian 3. Kunci ke perubahan pemetaan.
VARIANTS: dict[str, dict[str, object]] = {
    "b9_zero": {},
    "b9_one": {"b9": 1},
    "judas_source": {"B6_judas": "qt_judas_source"},
    "truth_vol": {"B7_truth": "qt_truth_volatility"},
    "seq_source": {"B2_sequence": "qt_sequence_src"},
}


def tier_for(total: int) -> tuple[str, float]:
    """Tier dan pengali ukuran untuk sebuah skor. `TIERS` berakhir di 0.

    Dipisah jadi fungsi supaya batasnya ada di satu tempat: sebuah loop yang
    di-`break` menyisakan nama yang, kalau daftarnya suatu hari kehilangan
    baris terakhirnya, akan terbaca dari iterasi sebelumnya tanpa suara.
    """
    for floor, tier, size in TIERS:
        if total >= floor:
            return tier, size
    raise ValueError(f"TIERS tidak menutup skor {total}; baris floor 0 hilang")


def b8(row: dict) -> bool | None:
    """B8 sebagaimana sumbernya mendefinisikannya: OR dua klausa lokasi.

    "Entry dalam 1 ATR dari anchored VWAP" ATAU "VWAP sejajar dengan sebuah
    True Open". Klausa ketiganya, CVD, tidak terukur di feed ini.

    None hanya kalau KEDUANYA tidak terbaca. Satu True lawan satu None tetap
    True, karena OR yang satu lengannya menyala sudah menyala - dan satu False
    lawan satu None adalah None, karena lengan yang tidak terbaca bisa saja
    menyalakannya.
    """
    near, at_open = row.get("qt_vwap_near"), row.get("qt_vwap_at_open")
    if near is True or at_open is True:
        return True
    if near is None or at_open is None:
        return None
    return False


def score(row: dict, variant: dict) -> dict:
    """Skor QT satu baris, plus tier dan pengali ukurannya.

    `variant` menimpa pemetaan kolom per builder, dan `b9` menyetel poin B9.
    Diam dihitung TIDAK terpenuhi, bagian 3.
    """
    gate_hits = {name: row.get(col) is True for name, col in GATES.items()}
    passed = sum(gate_hits.values())
    all_pass = passed == len(GATES)

    points: dict[str, int] = {}
    for name, col, weight in BUILDERS:
        column = variant.get(name, col)
        points[name] = weight if row.get(column) is True else 0
    points["B8_volume"] = 1 if b8(row) is True else 0
    points["B9_news"] = int(variant.get("b9", 0))

    builder = sum(points.values())
    total = (len(GATES) if all_pass else passed) + builder
    tier, size = tier_for(total)
    return {
        "qt_score": total, "qt_tier": tier, "qt_size": size,
        "qt_gates_pass": all_pass, "qt_gates_met": passed,
        "qt_builder": builder, "gate_hits": gate_hits, "points": points,
    }


def _judged_groups(rows: list[dict], columns: tuple[str, ...]) -> int:
    """K, dihitung SEBELUM satu hasil pun dilaporkan."""
    k = 2  # split median skor, plus kontras gate
    for column in columns:
        seen: dict[object, int] = {}
        for row in rows:
            key = row.get(column)
            seen[key] = seen.get(key, 0) + 1
        k += sum(1 for n in seen.values() if n >= MIN_GROUP)
    return k


def _trend(rows: list[dict], key: str, score_key: str = "qt_score") -> dict:
    """A2 dan A3 pada satu kolom outcome, mentah atau di-demean."""
    scores = np.array([r[score_key] for r in rows], dtype=np.float64)
    val = np.array([r[key] for r in rows], dtype=np.float64)
    rho, t = _spearman(scores, val)
    median = float(np.median(scores))
    top, bottom = val[scores > median], val[scores <= median]
    delta, welch = _welch(top, bottom)
    halves, same = _halves_agree(rows, lambda r: r[score_key] > median, key)
    return {
        "spearman_rho": rho, "spearman_t": t, "median_score": median,
        "n_above": int(len(top)), "n_at_or_below": int(len(bottom)),
        "exp_r_above": float(top.mean()) if len(top) else None,
        "exp_r_at_or_below": float(bottom.mean()) if len(bottom) else None,
        "median_split_delta": delta, "median_split_t": welch,
        "halves_delta": halves, "halves_same_sign": same,
    }


def _contrast(rows: list[dict], pick, key: str) -> dict:
    """Satu kohort lawan sisanya, dengan uji paruh. Bentuk H-B studi kelima."""
    inside = np.array([r[key] for r in rows if pick(r)])
    rest = np.array([r[key] for r in rows if not pick(r)])
    if len(inside) < MIN_GROUP or len(rest) < MIN_GROUP:
        return {"n_inside": int(len(inside)), "n_rest": int(len(rest)),
                "judged": False}
    delta, t = _welch(inside, rest)
    halves, same = _halves_agree(rows, pick, key)
    return {
        "n_inside": int(len(inside)), "n_rest": int(len(rest)), "judged": True,
        "exp_r_inside": float(inside.mean()), "exp_r_rest": float(rest.mean()),
        "delta": delta, "t": t,
        "halves_delta": halves, "halves_same_sign": same,
    }


def _sizing(rows: list[dict], critical: float | None = None) -> dict:
    """H-QT-C. Ekspektansi berbobot ukuran lawan ekspektansi rata.

    Aturan ukuran QT adalah SEKALIGUS filter: tier F berukuran nol, jadi
    trade-nya tidak diambil. Maka dua angka dilaporkan dan bukan satu, karena
    "lebih baik per unit risiko" dan "lebih banyak R total" bisa berbeda arah
    ketika sebagian trade tidak diambil sama sekali.

    ADA UJI SIGNIFIKANSINYA, dan versi pertama fungsi ini TIDAK punya. Ia cuma
    menuntut `delta > 0` dan tanda yang sama di kedua paruh, dan itu terpenuhi
    derau murni sekitar seperempat waktu - terukur, bukan diperkirakan: selftest
    dua arah di bawah gagal pada lengan DERAU-nya, dengan seed tetap, karena
    kriteria itu memang lolos di sana.

    Ujinya adalah kovarians. Selisih berbobot dikurangi rata sama dengan
    `cov(ukuran, R) / rata(ukuran)`, jadi menguji selisihnya sama dengan
    menguji apakah ukuran dan hasil bergerak bersama:

        z_i = (ukuran_i - rata(ukuran)) * (R_i - rata(R))
        t   = rata(z) / (sd(z) / akar(n))

    `critical` None berarti TIDAK DINILAI, dan `beats_flat` ikut None. Lipatan
    walk-forward memakainya begitu: masing-masing melaporkan delta-nya, dan
    vonisnya hanya diambil di populasi penuh.
    """
    size = np.array([r["qt_size"] for r in rows], dtype=np.float64)
    val = np.array([r["r"] for r in rows], dtype=np.float64)
    deployed = float(size.sum())
    weighted = float((size * val).sum() / deployed) if deployed > 0 else None
    flat = float(val.mean())

    def per_half(part: list[dict]) -> float:
        s = np.array([r["qt_size"] for r in part], dtype=np.float64)
        v = np.array([r["r"] for r in part], dtype=np.float64)
        if s.sum() <= 0:
            return float("nan")
        return float((s * v).sum() / s.sum() - v.mean())

    ordered = sorted(rows, key=lambda r: r["time"])
    cut = len(ordered) // 2
    halves = [per_half(ordered[:cut]), per_half(ordered[cut:])]
    same = (not any(np.isnan(halves))) and (halves[0] > 0) == (halves[1] > 0)
    delta = None if weighted is None else weighted - flat

    centred = (size - size.mean()) * (val - val.mean())
    if len(centred) > 1 and centred.std(ddof=1) > 0:
        cov_t = float(centred.mean() / (centred.std(ddof=1) / np.sqrt(len(centred))))
    else:
        cov_t = float("nan")
    judged = critical is not None and not np.isnan(cov_t)
    return {
        "n": len(rows),
        "n_taken": int((size > 0).sum()),
        "n_skipped_tier_f": int((size == 0).sum()),
        "exp_r_flat": flat,
        "exp_r_size_weighted": weighted,
        "delta": delta,
        "total_r_flat": float(val.sum()),
        "total_r_sized": float((size * val).sum()),
        "risk_units_deployed": deployed,
        "halves_delta": halves,
        "halves_same_sign": same,
        "covariance_t": cov_t,
        "critical_t": critical,
        "judged": judged,
        "beats_flat": (
            bool(delta is not None and delta > 0 and same
                 and cov_t >= critical)
            if judged else None),
    }


def _tier_table(rows: list[dict]) -> list[dict]:
    """Ekspektansi per tier, dalam urutan tier dan bukan urutan hasil."""
    order = [tier for _, tier, _ in reversed(TIERS)]
    out = []
    for tier in order:
        part = [r for r in rows if r["qt_tier"] == tier]
        if not part:
            out.append({"tier": tier, "n": 0, "judged": False})
            continue
        v = np.array([r["r"] for r in part])
        se = float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else 0.0
        out.append({
            "tier": tier, "n": len(v), "exp_r": float(v.mean()), "se": se,
            "size_multiplier": tier_for(
                next(f for f, name, _ in TIERS if name == tier))[1],
            "judged": len(v) >= MIN_GROUP,
        })
    return out


def _column(rows: list[dict], name: str, critical: float) -> dict:
    """H-QT-D untuk satu kolom: tiap nilai lawan sisa populasi."""
    buckets: dict[object, list[dict]] = {}
    for row in rows:
        buckets.setdefault(row.get(name), []).append(row)
    if len(buckets) == 1:
        only = next(iter(buckets))
        return {"column": name, "constant": True, "value": only,
                "n": len(rows),
                "verdict": f"konstan {only} di seluruh populasi, tidak bisa "
                           f"memisahkan apa pun"}
    groups, separates = [], []
    for key in sorted(buckets, key=lambda k: (k is None, str(k))):
        group = buckets[key]
        raw = _contrast(rows, lambda r, k=key: r.get(name) == k, "r")
        entry = {"value": key, "n": len(group), **raw}
        if raw.get("judged"):
            dm = _contrast(rows, lambda r, k=key: r.get(name) == k, "r_dm")
            agree = per_symbol = 0
            for sym in {r["symbol"] for r in rows}:
                mine = [r for r in rows if r["symbol"] == sym]
                a = np.array([r["r"] for r in mine if r.get(name) == key])
                b = np.array([r["r"] for r in mine if r.get(name) != key])
                if not len(a) or not len(b):
                    continue
                per_symbol += 1
                agree += (a.mean() - b.mean() > 0) == (raw["delta"] > 0)
            passed = abs(raw["t"]) >= critical and raw["halves_same_sign"]
            entry.update({
                "separates": passed,
                "delta_dm": dm.get("delta"), "t_dm": dm.get("t"),
                "symbols_same_sign": f"{agree}/{per_symbol}",
            })
            if passed:
                separates.append(key)
        groups.append(entry)
    judged = [g for g in groups if g.get("judged")]
    return {"column": name, "constant": False, "groups": groups,
            "separates": separates,
            "strongest_t": max((abs(g["t"]) for g in judged), default=None)}


def gather(symbols: list[str], interval: str, fine: str,
           rows_out: str = "") -> dict[str, list[dict]]:
    """Baris mentah per simbol. Ini bagian yang mahal, dan satu satunya.

    Lintasan ini membayar riwayat MT5 plus resolusi intrabar 5 menit untuk
    delapan instrumen, sekitar tiga puluh lima menit terminal. Analisisnya
    sendiri berjalan dalam hitungan detik. `--rows-out` dan `--rows-in` ada
    supaya memperbaiki satu baris statistik tidak berarti membayar lintasan
    itu lagi - dan alasannya bukan hipotetis: sebuah bug urutan penghitungan K
    ditemukan pada 5 September 2026 setelah lintasan ini sudah berjalan tiga
    simbol.

    DITULIS PER SIMBOL, BUKAN DI AKHIR, dan itu juga bukan kehati-hatian
    teoretis. Versi pertama menulis cache-nya sekali setelah kedelapan simbol
    selesai, lalu prosesnya mati di simbol ketiga pada hari yang sama, dan
    tiga simbol yang sudah dibayar hilang seluruhnya. Sekarang tiap simbol
    yang selesai langsung tersimpan, dan `--resume` melanjutkan dari situ.
    """
    per_symbol: dict[str, list[dict]] = {}
    if rows_out and pathlib.Path(rows_out).exists():
        try:
            per_symbol = json.loads(
                pathlib.Path(rows_out).read_text(encoding="utf-8"))
            done = sorted(per_symbol)
            if done:
                print(f"  melanjutkan, sudah ada: {', '.join(done)}",
                      file=sys.stderr)
        except (OSError, ValueError):
            per_symbol = {}

    for symbol in symbols:
        if symbol in per_symbol:
            print(f"  {symbol}: dilewati, sudah di cache "
                  f"({len(per_symbol[symbol])} trade)", file=sys.stderr)
            continue
        rows = rows_for(symbol, interval, fine)
        print(f"  {symbol}: {len(rows)} trade", file=sys.stderr)
        if rows:
            per_symbol[symbol] = rows
        if rows_out:
            pathlib.Path(rows_out).write_text(
                json.dumps(per_symbol, default=str), encoding="utf-8")
    return per_symbol


def load_rows(path: str) -> dict[str, list[dict]]:
    """Baris tersimpan, DIPERIKSA sebelum dipakai.

    Sebuah file kosong atau kehilangan kolom akan menghasilkan studi yang
    berjalan mulus dan melaporkan nol pemisahan, yang terbaca persis sama
    dengan "sudah diukur, tidak ada apa apa". Jadi ia ditolak keras.
    """
    loaded = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not loaded:
        raise SystemExit(f"{path} kosong; tidak ada yang bisa dianalisis")
    wanted = set(QT_COLUMNS) | {"r", "time", "symbol", "met"}
    for symbol, rows in loaded.items():
        if not rows:
            raise SystemExit(f"{path}: {symbol} nol baris")
        missing = wanted - set(rows[0])
        if missing:
            raise SystemExit(f"{path}: {symbol} kehilangan kolom {sorted(missing)}")
    return loaded


def study(per_symbol: dict[str, list[dict]], interval: str, fine: str) -> dict:
    """Satu run penuh. Semua ambang dihitung sebelum satu hasil dilaporkan."""
    pooled = [r for rows in per_symbol.values() for r in rows]
    if not pooled:
        return {"error": "tidak ada trade yang bisa diselesaikan di bar halus"}

    means = {s: float(np.mean([r["r"] for r in rows]))
             for s, rows in per_symbol.items()}
    for row in pooled:
        row["r_dm"] = row["r"] - means[row["symbol"]]
        row["qt_b8"] = b8(row)

    columns = QT_COLUMNS + ("qt_b8",)

    # SKOR DULU, BARU K, DAN URUTAN INI ADALAH BUGNYA YANG SUDAH PERNAH ADA.
    # Versi pertama tool ini memanggil `_judged_groups` sebelum satu baris pun
    # punya `qt_score`, jadi kedua kolom itu terbaca konstan None dan menyumbang
    # DUA grup alih-alih belasan. Terukur pada 1855 baris sintetis: K=17 lawan
    # K=22 yang benar. Ambang Bonferroni jadi terlalu longgar, dan longgar
    # adalah arah yang berbahaya - ia menemukan pemisahan yang tidak ada.
    #
    # Yang dilarang praregistrasi adalah menghitung K setelah HASILNYA terbaca,
    # bukan setelah kolomnya terisi. Skor bukan hasil; ia kolom.
    for row in pooled:
        row.update(score(row, VARIANTS["b9_zero"]))
    k = _judged_groups(pooled, columns + ("qt_score", "qt_tier"))
    critical = _critical_t(k)

    # DUA AMBANG, DAN YANG KEDUA LEBIH KETAT. H-QT-D menguji kedua belas kolom
    # SEKALI, jadi `critical` sudah menutupinya. Tapi H-QT-A, B dan C
    # dilaporkan LIMA KALI, sekali per varian, dan lima keluarga uji yang
    # semuanya dibaca sebagai vonis adalah lima kesempatan untuk menemukan
    # sesuatu. Jadi ambang varian membagi alpha lagi dengan jumlah varian.
    #
    # Ini KONSERVATIF dan tahu diri: varian-varian itu berkorelasi tinggi -
    # masing-masing cuma menukar satu kolom builder - jadi Bonferroni di
    # atasnya lebih ketat daripada perlu. Ketat adalah arah yang aman, dan
    # setelah bug urutan K di atas, arah yang aman adalah yang dipilih.
    critical_variant = _critical_t(k * len(VARIANTS))

    variants: dict[str, dict] = {}
    for label, mapping in VARIANTS.items():
        for row in pooled:
            row.update(score(row, mapping))
        ordered = sorted(pooled, key=lambda r: r["time"])
        size = len(ordered) // FOLDS
        folds = []
        for i in range(FOLDS):
            part = ordered[i * size:(i + 1) * size if i < FOLDS - 1 else len(ordered)]
            sc = np.array([r["qt_score"] for r in part], dtype=np.float64)
            val = np.array([r["r"] for r in part], dtype=np.float64)
            rho, t = _spearman(sc, val)
            median = float(np.median(sc))
            delta, _ = _welch(val[sc > median], val[sc <= median])
            sized = _sizing(part)
            folds.append({
                "fold": i + 1, "n": len(part),
                "from": part[0]["time"], "to": part[-1]["time"],
                "exp_r": float(val.mean()), "spearman_rho": rho,
                "spearman_t": t, "median_split_delta": delta,
                "sizing_delta": sized["delta"],
                "positive": bool(delta > 0) if not np.isnan(delta) else None,
            })

        # `_levels` mengelompokkan pada kunci `met`, jadi skor QT dipinjamkan
        # ke nama itu untuk satu panggilan. Menyalin fungsinya hanya untuk
        # mengganti satu string akan memberi dua definisi monotonisitas.
        for row in pooled:
            row["_met_backup"] = row.get("met")
            row["met"] = row["qt_score"]
        levels = _levels(pooled)
        mono = _monotone(levels)
        for row in pooled:
            row["met"] = row.pop("_met_backup")

        raw = _trend(pooled, "r")
        demeaned = _trend(pooled, "r_dm")
        gates_raw = _contrast(pooled, lambda r: r["qt_gates_pass"], "r")
        gates_dm = _contrast(pooled, lambda r: r["qt_gates_pass"], "r_dm")
        verdict = {
            "A1_monotone": mono["monotone"],
            "A2_trend_raw": bool(abs(raw["spearman_t"]) >= critical_variant
                                 and raw["spearman_rho"] > 0),
            "A2_trend_demeaned": bool(
                abs(demeaned["spearman_t"]) >= critical_variant
                and demeaned["spearman_rho"] > 0),
            "A3_median_split_raw": bool(raw["median_split_t"] >= critical_variant
                                        and raw["halves_same_sign"]),
            "A3_median_split_demeaned": bool(
                demeaned["median_split_t"] >= critical_variant
                and demeaned["halves_same_sign"]),
            "B_gates_pass_beats_fail": bool(
                gates_raw.get("judged")
                and gates_raw.get("t", 0) >= critical_variant
                and gates_raw.get("halves_same_sign")),
        }
        sizing = _sizing(pooled, critical_variant)
        variants[label] = {
            "score_levels": levels, "monotone": mono,
            "tier_table": _tier_table(pooled),
            "raw": raw, "instrument_demeaned": demeaned,
            "gates": {"raw": gates_raw, "instrument_demeaned": gates_dm},
            "sizing": sizing,
            "walk_forward": folds,
            "folds_positive": sum(1 for f in folds if f["positive"]),
            "folds_sizing_positive": sum(
                1 for f in folds
                if f["sizing_delta"] is not None and f["sizing_delta"] > 0),
            "verdict": verdict,
            "separates": any(verdict.values()),
            "score_min": min(r["qt_score"] for r in pooled),
            "score_max": max(r["qt_score"] for r in pooled),
        }

    # Kolom per builder diukur SEKALI, pada baris yang sama, karena nilainya
    # tidak bergantung varian - varian hanya mengubah cara menjumlahkannya.
    for row in pooled:
        row.update(score(row, VARIANTS["b9_zero"]))

    return {
        "preregistered": "docstring tools/qt_outcomes.py, 2026-09-05",
        "population_from": "tools/checklist_outcomes.py:rows_for, tidak diubah",
        "run": {"interval": interval, "fine": fine,
                "symbols": list(per_symbol), "folds": FOLDS},
        "population": {
            "n": len(pooled),
            "exp_r": float(np.mean([r["r"] for r in pooled])),
            "per_symbol": {s: {"n": len(rows), "exp_r": means[s]}
                           for s, rows in per_symbol.items()},
        },
        "threshold": {
            "alpha": ALPHA, "groups_judged": k,
            "alpha_corrected": ALPHA / k, "critical_t": critical,
            "variants": len(VARIANTS),
            "critical_t_variant": critical_variant,
            "min_group": MIN_GROUP,
            "note": ("critical_t menilai kedua belas kolom H-QT-D, yang diuji "
                     "sekali. critical_t_variant menilai vonis H-QT-A, B dan C, "
                     "yang dilaporkan sekali per varian."),
        },
        "mapping": {
            "gates": GATES,
            "builders": {n: {"column": c, "weight": w} for n, c, w in BUILDERS},
            "B8_volume": "qt_vwap_near OR qt_vwap_at_open",
            "B9_news": "TIDAK TERUKUR, lihat app/qt.py:NEWS_CLEAR_BLOCKED",
            "tiers": [{"min_score": f, "tier": t, "size": s} for f, t, s in TIERS],
        },
        "variants": variants,
        "H_QT_D_columns": [_column(pooled, name, critical) for name in columns],
    }


def _selftest() -> None:
    """Cacat yang tool ini ditulis untuk menangkap, disuntikkan lalu diperiksa."""
    full = {c: True for c in
            list(GATES.values()) + [b[1] for b in BUILDERS]}
    full.update({"qt_vwap_near": True, "qt_vwap_at_open": True})
    top = score(full, {})
    # Lima gate plus dua belas builder, dikurangi B9 yang tidak diberi.
    assert top["qt_score"] == 16, top["qt_score"]
    assert top["qt_tier"] == "A+" and top["qt_size"] == 1.25
    # Varian b9_one memberi poin yang tidak terukur itu, dan skornya penuh.
    assert score(full, {"b9": 1})["qt_score"] == 17

    # SATU gate gagal menjatuhkan skor lewat cabang gate, bukan lewat builder.
    one_down = {**full, "killzone": False}
    assert score(one_down, {})["qt_gates_pass"] is False
    assert score(one_down, {})["qt_score"] == 15

    # DIAM TIDAK LOLOS SEBAGAI SETUJU, aturan yang seluruh skor ini bergantung.
    unknown = {**full, "ssmt": None}
    assert score(unknown, {})["points"]["B1_ssmt"] == 0
    empty = score({}, {})
    assert empty["qt_score"] == 0 and empty["qt_tier"] == "F"
    assert empty["qt_size"] == 0.0

    # B8 adalah OR, dan satu lengan menyala sudah cukup.
    assert b8({"qt_vwap_near": True, "qt_vwap_at_open": False}) is True
    assert b8({"qt_vwap_near": False, "qt_vwap_at_open": False}) is False
    # Lengan yang tidak terbaca tidak boleh dilaporkan sebagai False.
    assert b8({"qt_vwap_near": False, "qt_vwap_at_open": None}) is None
    assert b8({"qt_vwap_near": True, "qt_vwap_at_open": None}) is True

    # Tabel tier menghormati batasnya, dari sumbernya.
    for total, want in ((0, "F"), (4, "F"), (5, "C"), (8, "C"), (9, "B"),
                        (11, "B"), (12, "A"), (14, "A"), (15, "A+")):
        assert tier_for(total)[0] == want, (total, tier_for(total), want)

    # Aturan ukuran harus MENGALAHKAN rata hanya ketika skornya informatif.
    # Sinyal: R besar di tier besar. Kontrol: R yang sama, ukuran diacak balik.
    good = [{"qt_size": 1.25, "r": 1.0, "time": 1, "symbol": "X"},
            {"qt_size": 1.25, "r": 1.0, "time": 2, "symbol": "X"},
            {"qt_size": 0.5, "r": -1.0, "time": 3, "symbol": "X"},
            {"qt_size": 0.5, "r": -1.0, "time": 4, "symbol": "X"}]
    bad = [{**r, "qt_size": 1.75 - r["qt_size"]} for r in good]
    assert _sizing(good)["delta"] > 0
    assert _sizing(bad)["delta"] < 0
    # Tier F tidak diambil, dan itu harus terhitung sebagai trade yang dilewati.
    skipped = _sizing(good + [{"qt_size": 0.0, "r": -5.0, "time": 5,
                               "symbol": "X"}])
    assert skipped["n_skipped_tier_f"] == 1 and skipped["n_taken"] == 4

    _selftest_mapping_is_real()
    _selftest_rows_guard()
    _selftest_study_both_ways()
    print("qt_outcomes selftest ok", file=sys.stderr)


def _selftest_mapping_is_real() -> None:
    """Tiap kolom yang dipetakan HARUS benar-benar diproduksi rig-nya.

    Ini kegagalan paling diam di seluruh tool ini. `BUILDERS` dan `GATES`
    memetakan nama builder QT ke nama kolom sebagai STRING, dan `score` membaca
    kolom itu lewat `row.get(...)`. Sebuah salah ketik - "qt_sequnce" - membuat
    `row.get` menjawab None selamanya, builder itu tidak pernah dapat poin,
    skornya bergeser turun untuk SETIAP baris, dan tidak ada satu pun yang
    merah. Tabel tier tetap terisi, walk-forward tetap jalan, verdict tetap
    keluar. Yang hilang cuma satu builder, tanpa jejak.

    Diikat ke sumber kebenarannya: `CLAUSES` di rig kelima untuk klausa ICT,
    `QT_COLUMNS` untuk kolom QT.
    """
    from tools.checklist_outcomes import CLAUSES

    produced = set(CLAUSES) | set(QT_COLUMNS)
    mapped = set(GATES.values()) | {col for _, col, _ in BUILDERS}
    mapped |= {"qt_vwap_near", "qt_vwap_at_open"}  # B8, lewat `b8()`
    for variant in VARIANTS.values():
        mapped |= {v for v in variant.values() if isinstance(v, str)}

    missing = sorted(mapped - produced)
    assert not missing, f"dipetakan tapi tidak pernah diproduksi rig: {missing}"

    # Dan bobot buildernya harus berjumlah dua belas, angka tabel sumbernya.
    # B8 dan B9 masing-masing satu dan ditangani terpisah dari `BUILDERS`.
    assert sum(w for _, _, w in BUILDERS) + 1 + 1 == 12


def _synthetic(seed: int, planted: bool) -> dict[str, list[dict]]:
    """Delapan simbol baris buatan, dengan atau tanpa sinyal yang ditanam."""
    import random

    rng = random.Random(seed)
    clauses = list(GATES.values()) + [c for _, c, _ in BUILDERS]
    symbols = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    per: dict[str, list[dict]] = {}
    stamp = 1_700_000_000
    for index, symbol in enumerate(symbols):
        rows = []
        # 200 per simbol, bukan 60. Kelima gate lolos bersamaan hanya pada
        # sekitar 3 persen baris acak, jadi 480 baris memberi 12 dan kontras
        # gate-nya tidak pernah dinilai - `MIN_GROUP` 30. Ukuran sampel yang
        # membuat sebuah check diam adalah check yang hampa.
        for i in range(200):
            row = {"symbol": symbol, "time": stamp + (index * 200 + i) * 3600,
                   "met": 8, "r": 0.0}
            # DIURUTKAN, DAN ITU BUKAN KERAPIAN. Mengiterasi sebuah `set`
            # memberi urutan yang bergantung hash string, dan Python mengacak
            # hash string per PROSES. Jadi tiap run memberi penugasan nilai
            # yang berbeda dari `rng` yang sama, dan selftest ini kadang lolos
            # kadang tidak di pohon kode yang identik. Terjadi 5 September
            # 2026: lolos, lalu gagal di `beats_flat` beberapa menit kemudian
            # tanpa satu baris berubah. Bentuk kegagalan yang sama dengan
            # `e2e/labels.mjs` sebelum ia dipatok.
            for name in sorted(set(clauses) | set(QT_COLUMNS)):
                row[name] = rng.choice([True, False])
            rows.append(row)
        per[symbol] = rows
    pooled = [r for rows in per.values() for r in rows]
    for row in pooled:
        row.update(score(row, VARIANTS["b9_zero"]))
        row["r"] = (0.30 * (row["qt_score"] - 8) if planted else 0.0)             + rng.gauss(0, 0.6)
    return per


def _selftest_study_both_ways() -> None:
    """Studi ini harus MENEMUKAN sinyal yang ditanam dan MENOLAK derau.

    Satu arah saja tidak cukup, dan itu bukan kehati-hatian teoretis. Sebuah
    rig yang selalu menjawab "tidak memisahkan" lolos setiap pemeriksaan yang
    hanya memberinya derau, dan seluruh isi `docs/` di repo ini adalah vonis
    null. Vonis null dari instrumen yang tidak bisa mengatakan apa pun selain
    null bernilai nol.

    Dua check di `e2e/theme.mjs` lahir dari kegagalan yang persis sama bentuknya
    dan dicatat di CLAUDE.md: versi pertamanya HAMPA sampai ada yang menyuntik
    cacat yang seharusnya ia tangkap.
    """
    noise = study(_synthetic(7, planted=False), "1h", "5m")
    quiet = noise["variants"]["b9_zero"]
    assert quiet["separates"] is False, quiet["verdict"]
    assert quiet["sizing"]["beats_flat"] is False

    signal = study(_synthetic(11, planted=True), "1h", "5m")
    loud = signal["variants"]["b9_zero"]
    assert loud["verdict"]["A1_monotone"] is True, loud["monotone"]
    assert loud["verdict"]["A2_trend_raw"] is True, loud["raw"]
    assert loud["verdict"]["A3_median_split_raw"] is True, loud["raw"]
    assert loud["verdict"]["B_gates_pass_beats_fail"] is True, loud["gates"]
    assert loud["sizing"]["beats_flat"] is True, loud["sizing"]
    # `separates` adalah ringkasan yang dibaca orang duluan, jadi ia diperiksa
    # SENDIRI dan bukan disimpulkan dari kelima kunci di atas. Sebuah suntikan
    # yang memakunya ke False lolos seluruh check ini sampai baris ini ada.
    assert loud["separates"] is True
    # Dan ekspektansi per tier harus naik, karena itu klaim tabel tier-nya.
    judged = [t["exp_r"] for t in loud["tier_table"] if t.get("judged")]
    assert judged == sorted(judged), judged


def _selftest_rows_guard() -> None:
    """Cache baris yang rusak harus DITOLAK, bukan dianalisis diam-diam.

    Sebuah file kosong yang lolos akan menghasilkan studi yang berjalan mulus,
    melaporkan nol pemisahan, dan terbaca persis sama dengan "sudah diukur,
    tidak ada apa apa". Itu cara termahal untuk salah di repo ini.
    """
    import tempfile

    good = {"XAUUSD": [{c: None for c in QT_COLUMNS} |
                       {"r": 0.1, "time": 1, "symbol": "XAUUSD", "met": 5}]}
    with tempfile.TemporaryDirectory() as folder:
        base = pathlib.Path(folder)
        ok = base / "ok.json"
        ok.write_text(json.dumps(good), encoding="utf-8")
        assert load_rows(str(ok)) == good

        for name, payload in (("empty.json", {}),
                              ("no_rows.json", {"XAUUSD": []}),
                              ("short.json", {"XAUUSD": [{"r": 0.1}]})):
            bad = base / name
            bad.write_text(json.dumps(payload), encoding="utf-8")
            try:
                load_rows(str(bad))
            except SystemExit:
                continue
            raise AssertionError(f"{name} diterima padahal harus ditolak")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--fine", default="")
    parser.add_argument("--rows-out", default="",
                        help="simpan baris mentah ke sini SETIAP simbol selesai; "
                             "file yang sudah ada dipakai untuk melanjutkan")
    parser.add_argument("--rows-in", default="",
                        help="analisis ulang dari baris tersimpan, tanpa MT5")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    fine = args.fine or FINER.get(args.interval, "5m")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        # `resolved` mencetak zona yang entry-nya tidak terisi ke stdout, dan
        # stdout di sini adalah file JSON-nya. Dialihkan, tidak dibuang.
        if args.rows_in:
            per_symbol = load_rows(args.rows_in)
            print(f"baris dimuat dari {args.rows_in}", file=sys.stderr)
        else:
            per_symbol = gather(symbols, args.interval, fine, args.rows_out)
            if args.rows_out:
                print(f"baris disimpan ke {args.rows_out}", file=sys.stderr)
        out = study(per_symbol, args.interval, fine)
    json.dump(out, sys.stdout, indent=2, default=str)
    print()
    return 0 if "error" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
