"""Praregistrasi: apakah DFR sebuah fase memberi target untuk fase berikutnya.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.phase_targets \
        > ../docs/phase_targets.json

Ditulis 2 September 2026, SEBELUM satu angka pun dihitung. Bagian 1 sampai 8 di
bawah ini adalah praregistrasinya; angkanya keluar di stdout sebagai JSON.

===========================================================================
1. ATURAN YANG DIUJI, DAN DARI MANA IA DATANG
===========================================================================

Diserahkan oleh pemiliknya pada 2 September 2026, dua baris, apa adanya:

    Accumulation/Consolidation DFR  ->  Manipulation Targets
    Manipulation DFR                ->  Distribution Targets

Bukti yang menyertainya satu chart TradingView, BTC 1h Binance, milik Tango618:
grid Quarterly Theory di lane bawah, box DFR di Senin dan Selasa, level TWO di
78.909,6 plus TDO dan TSO, dan tangga deviasi 2 / 0 / -0,5 / -1 / -1,5 di kiri.
Itu SATU chart. Ia bukti bahwa aturannya digambar, bukan bukti bahwa aturannya
bekerja, dan perbedaan itu adalah seluruh alasan file ini ada.

===========================================================================
2. APA YANG ATURAN INI TAMBAHKAN DI ATAS YANG SUDAH ADA
===========================================================================

`app/quarterly.py` sudah menjawab dua pertanyaan pertama checklist pemiliknya -
apakah DFR consolidation sudah terjadi, dan apakah manipulation sudah - dan
BERHENTI di situ, dengan sengaja: dua belas hipotesis arah praregistrasi sudah
mati di project ini dan file itu menolak mengatakan ke mana harga akan pergi.

Aturan baru ini adalah klaim TARGET. Ia mengatakan sebuah harga akan DICAPAI,
di fase yang disebutkan namanya. Itu klaim yang bisa jatuh, jadi ia diukur di
sini alih-alih dikirim.

DAN IA TIDAK SETUJU DENGAN KODE KITA SOAL SATU HAL. `defining_range` mengambil
DFR dari Q1 SELALU, apa pun profilnya. Tapi profilnya menentukan fase mana yang
Q1:

    AMDX  ->  Q1 akumulasi, Q2 manipulasi, Q3 distribusi
    XAMD  ->  Q1 adalah X, Q2 akumulasi, Q3 manipulasi, Q4 distribusi

Jadi di bawah XAMD, "Accumulation DFR" menurut aturan pemiliknya adalah DFR
Q2, sementara kode kita memberikan DFR Q1 - kuarter yang bukan akumulasi. Salah
satu dari dua hal benar dan tidak ada dokumen di sini yang bisa memutuskan yang
mana, jadi KEDUANYA diuji berdampingan sebagai dua arm dan datanya yang
memisahkan.

===========================================================================
3. POPULASI
===========================================================================

| Hal | Nilai |
|---|---|
| Instrumen | `SERIES`, empat, disalin dari `tools/dfr_outcomes.py` |
| Timeframe | 1 jam, 20.000 bar |
| Degree | day dan week, dua-duanya dinilai terpisah |
| Unit | satu DFR per cycle per degree |

Diambil dari `dfr_outcomes.py` apa adanya supaya angka di sini bisa diletakkan
berdampingan dengan angka rig itu tanpa ada yang bertanya populasinya beda atau
tidak.

===========================================================================
4. ARM, daftar tertutup
===========================================================================

| Arm | DFR dari | Target dicari di |
|---|---|---|
| `q1_to_manip` | Q1, apa pun profilnya - aturan kode kita hari ini | kuarter manipulasi |
| `accum_to_manip` | kuarter AKUMULASI: Q1 di AMDX, Q2 di XAMD | kuarter manipulasi |
| `manip_to_distrib` | kuarter MANIPULASI: Q2 di AMDX, Q3 di XAMD | kuarter distribusi |

Dua arm pertama menjawab ketidaksesuaian di Bagian 2. Arm ketiga adalah baris
kedua aturan pemiliknya.

Kuarter distribusi: Q3 di AMDX, Q4 di XAMD. Diturunkan dari profil, bukan
dieja, supaya ia tidak bisa berbeda pendapat dengan `Profile.manipulation`.

===========================================================================
5. OUTCOME, dan kenapa ia jendela FASE dan bukan 96 bar
===========================================================================

Tercapai berarti: harga menyentuh level itu DI DALAM jendela kuarter targetnya.

`tools/dfr_outcomes.py` menanyakan "tercapai dalam 96 bar", horizon tetap tanpa
struktur fase, dan itu pertanyaan yang berbeda. Aturan ini menyebut FASENYA, dan
menguji fase itu membuatnya lebih tajam sekaligus lebih mudah gagal: sebuah
level yang tercapai dua kuarter kemudian TIDAK dihitung tercapai di sini,
walaupun di rig 96 bar ia dihitung.

Jendela kuarternya keluar dari jam, jadi ia knowable tanpa melihat harga.
Levelnya knowable di akhir kuarter sumbernya, yang selalu SEBELUM kuarter
targetnya dimulai - jadi tidak ada lookahead di konstruksinya, dan itu jatuh
dari aturannya alih-alih ditegakkan di atasnya.

DUA LEVEL PER DFR, high dan low, dan keduanya dinilai. Aturannya tidak memberi
arah - ia mengatakan "targets", jamak - jadi memisahkan sisi lalu melaporkan
yang menang adalah menguji aturan yang tidak pernah dinyatakan siapa pun.

===========================================================================
6. KONTROL, dan cacat kontrol yang tidak boleh diulang
===========================================================================

PER-EVENT JITTER, bentuk yang sama dengan `dfr_outcomes.py` dan `projections`,
dan TIDAK ADA shuffling. Kontrol `pools` yang di-shuffle memberi +2,90pp dan
p = 9,2e-05, lalu terbukti cacat: mengacak memutus pasangan antara jarak sebuah
level dan volatilitas bar-nya sendiri, dan di dalam pita jarak yang disamakan
selisihnya berbalik ke -0,68pp.

Untuk tiap level real, satu level placebo dibuat di event yang sama, dari
MIDPOINT DFR yang sama, di sisi yang sama, dengan jendela kuarter target yang
sama, pada jarak `d * f` di mana `d` jarak real dari midpoint dan
`f ~ Uniform(0,6, 1,4)` dengan `|f - 1| >= 0,1`. Jaraknya tetap kelipatan
tinggi DFR itu, jadi pasangan jarak-lawan-volatilitas tidak pernah putus.

`f` di-seed deterministik dari (symbol, degree, cycle_start, arm, side), jadi
re-run memberi angka identik dan tidak ada "coba seed lain".

BIAS KONTROL, disebut di depan karena arahnya penting. E[f] = 1, jadi jarak
placebo sama dengan jarak real secara rata-rata. Tapi probabilitas tercapai
sebagai fungsi jarak itu menurun dan CEMBUNG, sehingga mean-preserving spread
MENAIKKAN reach placebo (Jensen). Kontrol ini condong ke atas, artinya ia
membuat efek positif lebih SULIT ditemukan. Kalau hasilnya positif, bias ini
bukan penjelasannya.

===========================================================================
7. AMBANG LULUS, ditetapkan sekarang
===========================================================================

Sebuah arm di sebuah degree hanya LULUS kalau keempatnya lolos:

1. `n >= 30` DFR di grup itu.
2. Delta point estimate `>= +3,0pp`. Angka yang sama yang dipakai
   `projections` dan `dfr_outcomes`, dan yang `projections` gagal 6,5x di
   bawahnya pada +0,46pp.
3. `|t| >` kritis dua sisi ber-Bonferroni, alpha 0,05 dibagi `K`, dengan `K`
   jumlah grup yang layak dinilai. `K` dihitung dan dicetak SEBELUM satu baris
   pun dilaporkan.
4. Walk-forward 8 fold berurutan waktu, sign test satu sisi p <= 0,05. Dengan
   8 fold itu minimal 7 dari 8 fold delta-nya positif (p = 0,0352); 6 dari 8
   memberi p = 0,1445 dan GAGAL.

`accum_to_manip` lebih baik dari `q1_to_manip` HANYA kalau selisih delta antar
keduanya juga melewati ambang yang sama pada pasangan berpasangan cycle demi
cycle. Dua arm yang keduanya positif tapi tidak terpisah tidak memutuskan
ketidaksesuaian di Bagian 2, dan mengaku begitu lebih berguna daripada memilih
yang angkanya lebih besar.

===========================================================================
8. YANG TIDAK DIJAWAB STUDI INI
===========================================================================

- Ia tidak menguji ARAH. Tercapai adalah tercapai; siapa yang lebih dulu
  tersentuh antara high dan low tidak ditanyakan, karena aturannya tidak
  menyatakannya.
- Ia tidak menguji level ekstensi (0,5 dan 1,0 tinggi DFR). Itu pertanyaan
  `dfr_outcomes.py`, sudah dijalankan, dan mencampur keduanya akan membuat dua
  hipotesis berbagi satu koreksi Bonferroni.
- Ia tidak memverifikasi aturan pertiga itu sendiri. `app/quarterly.py`
  mencatat statusnya SINGLE-SOURCED lewat satu fetch yang merangkum, dikuatkan
  hanya oleh situs penulisnya sendiri: satu suara, dua kali. Studi ini mengukur
  konsekuensi sebuah aturan yang provenance-nya masih lemah, dan itu tidak
  berubah karena angkanya keluar.
- `--selftest` menjalankan penilai pada cycle buatan yang jawabannya diketahui.
  Sebuah rig yang tidak pernah ditunjukkan bisa melaporkan LULUS sedang
  melaporkan diamnya sendiri.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from math import comb, sqrt
from statistics import NormalDist

from app.models import Candle
from app.quarters import quarters
from app.quarterly import profile
from tools.dfr_outcomes import (
    EFFECT_MIN_PP,
    FOLDS,
    JITTER_DEAD,
    JITTER_HI,
    JITTER_LO,
    MIN_N,
    SERIES,
    SIDES,
)
from tools.quant import clean

#: Fase mana yang kuarter mana, per profil. Diturunkan dari `Profile.name`, dan
#: `Profile.manipulation` dipakai sebagai pemeriksaan silang di `_phases` supaya
#: tabel ini tidak bisa diam-diam berbeda pendapat dengan `app/quarterly.py`.
PHASES = {
    "AMDX": {"accumulation": 1, "manipulation": 2, "distribution": 3},
    "XAMD": {"accumulation": 2, "manipulation": 3, "distribution": 4},
}

#: Arm, daftar tertutup. `(nama, kuarter sumber, kuarter target)` di mana
#: kuarter sumber `"Q1"` berarti selalu Q1 dan sebuah nama fase berarti dibaca
#: dari profilnya.
ARMS = (
    ("q1_to_manip", "Q1", "manipulation"),
    ("accum_to_manip", "accumulation", "manipulation"),
    ("manip_to_distrib", "manipulation", "distribution"),
)

#: ARM CURANG, dinyalakan hanya oleh `--oracle`, dan ia ada untuk satu tujuan:
#: menunjukkan bahwa rig ini BISA melaporkan LULUS. Sebuah studi yang melaporkan
#: nol pemenang tanpa pernah menunjukkan pemenang seperti apa yang bisa ia lihat
#: sedang melaporkan diamnya sendiri, bukan diamnya pasar.
#:
#: Ia mengambil "levelnya" dari ekstrem kuarter TARGET, yang berarti ia melihat
#: masa depan, jadi real-nya tercapai secara definisi sementara placebo-nya
#: berada di jarak yang di-jitter dan sering tidak. Ia HARUS lulus keempat
#: ambang di Bagian 7. Kalau tidak, yang rusak penilainya.
ORACLE_ARM = "oracle_lookahead"

DEGREES_JUDGED = ("day", "week")


def _jitter(seed: str) -> float:
    """Faktor jitter deterministik dari identitas level. Lihat Bagian 6."""
    rng = random.Random(seed)
    while True:
        f = rng.uniform(JITTER_LO, JITTER_HI)
        if abs(f - 1.0) >= JITTER_DEAD:
            return f


def _bars_in(candles: list[Candle], start: int, end: int) -> list[Candle]:
    """Bar yang OPEN-nya jatuh di [start, end)."""
    return [c for c in candles if start <= c.time < end]


def _thirds_range(bars: list[Candle]) -> tuple[float, float] | None:
    """Aturan pertiga: buang sepertiga pertama, ambil high dan low sisanya.

    Diterapkan ke kuarter APA PUN, bukan hanya Q1, karena itulah yang aturan
    baru ini minta. Rumusnya identik dengan `quarterly.defining_range`; yang
    berbeda kuarter yang dimasukkan.
    """
    if len(bars) < 3:
        return None
    start, end = bars[0].time, bars[-1].time + 1
    kept_from = start + (end - start) // 3
    kept = [c for c in bars if c.time >= kept_from]
    if not kept:
        return None
    return max(c.high for c in kept), min(c.low for c in kept)


def cycles_of(candles: list[Candle], degree: str) -> list[tuple]:
    """Setiap cycle sebagai empat Quarter Q1..Q4 berurutan, hanya yang lengkap.

    `Quarter` membawa `degree`, `label`, `start` dan `end` DAN TIDAK LEBIH -
    tidak ada `cycle_start`, tidak ada `index`. Versi pertama fungsi ini
    mengarang keduanya; `pyflakes` meloloskannya karena ia tidak memeriksa tipe,
    dan pyright yang menangkapnya sebelum satu baris dijalankan. Jadi cycle-nya
    dikelompokkan dari LABELNYA: sebuah Q1 membuka cycle baru, dan cycle itu
    hanya dipakai kalau keempat labelnya datang berurutan.

    Cycle yang tidak lengkap DIBUANG, bukan ditambal. Waktu yang tidak dimiliki
    kuarter mana pun - Jumat di degree week, pekan kelima di degree month -
    memang tidak menghasilkan apa-apa di `quarters`, jadi sebuah cycle yang
    bolong di tengahnya adalah cycle yang jendela fasenya tidak bisa dinamai.
    """
    if not candles:
        return []
    out: list[tuple] = []
    cur: list = []
    for q in quarters(degree, candles[0].time, candles[-1].time):
        if q.label == "Q1":
            cur = [q]
        elif cur and q.label == f"Q{len(cur) + 1}":
            cur.append(q)
            if len(cur) == 4:
                out.append(tuple(cur))
                cur = []
        else:
            cur = []
    return out


def rows_for(
    symbol: str, interval: str, bars: int, degree: str, oracle: bool = False
) -> list[dict]:
    """Satu baris per (cycle, arm, sisi), dengan reach real dan reach placebo."""
    candles, _, _ = clean(symbol, interval, bars)
    if len(candles) < 100:
        return []

    out: list[dict] = []
    for cycle in cycles_of(candles, degree):
        cycle_start = cycle[0].start
        prof = profile(candles, degree, cycle_start)
        if prof is None:
            continue
        # PEMERIKSAAN SILANG. `PHASES` dan `Profile.manipulation` menamai kuarter
        # manipulasi masing-masing, dan dua tabel yang berbeda pendapat lebih
        # buruk daripada salah satunya salah, karena keduanya terlihat benar
        # sendiri-sendiri. Kalau tidak cocok, cycle-nya dibuang.
        if f"Q{PHASES[prof.name]['manipulation']}" != prof.manipulation:
            continue

        arms = list(ARMS)
        if oracle:
            # Sumbernya kuarter target itu sendiri: lihat catatan di `ORACLE_ARM`.
            arms.append((ORACLE_ARM, "distribution", "distribution"))
        for arm, source, target in arms:
            src_index = 1 if source == "Q1" else PHASES[prof.name][source]
            tgt_index = PHASES[prof.name][target]
            src_q = cycle[src_index - 1]
            tgt_q = cycle[tgt_index - 1]

            src_bars = _bars_in(candles, src_q.start, src_q.end)
            band = _thirds_range(src_bars)
            if band is None:
                continue
            high, low = band
            if high <= low:
                continue
            mid = (high + low) / 2

            tgt_bars = _bars_in(candles, tgt_q.start, tgt_q.end)
            # Kuarter target harus benar-benar TERISI dan benar-benar SELESAI.
            # Sebuah kuarter yang datanya berhenti di tengahnya menurunkan reach
            # untuk real dan placebo sekaligus, tapi ia mengubah pertanyaannya
            # tanpa mengatakannya.
            if not tgt_bars or candles[-1].time < tgt_q.end:
                continue
            top = max(c.high for c in tgt_bars)
            bottom = min(c.low for c in tgt_bars)

            for side in SIDES:
                real = high if side == "above" else low
                distance = abs(real - mid)
                f = _jitter(f"{symbol}|{degree}|{cycle_start}|{arm}|{side}")
                fake = mid + distance * f * (1 if side == "above" else -1)
                out.append(
                    {
                        "symbol": symbol,
                        "degree": degree,
                        "arm": arm,
                        "cycle_start": cycle_start,
                        "knowable_at": src_q.end,
                        "side": side,
                        "profile": prof.name,
                        "real_reached": real <= top if side == "above" else real >= bottom,
                        "fake_reached": fake <= top if side == "above" else fake >= bottom,
                    }
                )
    return out


def _sign_test(positive: int, folds: int) -> float:
    """p satu sisi binomial di 0,5 untuk `positive` dari `folds`."""
    if folds == 0:
        return 1.0
    return sum(comb(folds, k) for k in range(positive, folds + 1)) / 2**folds


def _paired(rows: list[dict]) -> tuple[float, float, int]:
    """Delta pp berpasangan, t-nya, dan n. Unit primer CYCLE, bukan level.

    Dua level dari satu DFR berbagi satu window target dan satu tinggi band,
    jadi menghitungnya sebagai dua pengamatan bebas menggelembungkan n dua kali
    lipat. Nilai per cycle adalah rata-rata selisih berpasangan atas sisinya.
    """
    by_cycle: dict[int, list[float]] = {}
    for r in rows:
        by_cycle.setdefault(r["cycle_start"], []).append(
            (1.0 if r["real_reached"] else 0.0) - (1.0 if r["fake_reached"] else 0.0)
        )
    deltas = [sum(v) / len(v) for v in by_cycle.values()]
    n = len(deltas)
    if n < 2:
        return (deltas[0] * 100 if n else 0.0), 0.0, n
    mean = sum(deltas) / n
    var = sum((d - mean) ** 2 for d in deltas) / (n - 1)
    se = sqrt(var / n)
    return mean * 100, (mean / se if se > 0 else 0.0), n


def _walk(rows: list[dict]) -> dict:
    """8 fold berurutan waktu atas cycle, sign test satu sisi."""
    cycles = sorted({r["cycle_start"] for r in rows})
    if len(cycles) < FOLDS:
        return {"graded": 0, "positive": 0, "p": 1.0, "deltas": []}
    edges = [round(i * len(cycles) / FOLDS) for i in range(FOLDS + 1)]
    deltas: list[float] = []
    for a, b in zip(edges, edges[1:]):
        keep = set(cycles[a:b])
        if not keep:
            continue
        pp, _, n = _paired([r for r in rows if r["cycle_start"] in keep])
        if n >= 2:
            deltas.append(pp)
    positive = sum(1 for d in deltas if d > 0)
    return {
        "graded": len(deltas),
        "positive": positive,
        "p": _sign_test(positive, len(deltas)),
        "deltas": [round(d, 3) for d in deltas],
    }


def study(series, degrees, oracle: bool = False) -> dict:
    rows: list[dict] = []
    for symbol, interval, bars in series:
        for degree in degrees:
            got = rows_for(symbol, interval, bars, degree, oracle)
            rows.extend(got)
            print(f"{symbol} {degree}: {len(got)} level", file=sys.stderr)

    if not rows:
        return {"error": "populasi kosong"}

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["arm"], r["degree"]), []).append(r)

    # `K` DIHITUNG SEBELUM SATU BARIS PUN DILAPORKAN, lihat Bagian 7.
    judged = [
        key for key, rs in groups.items() if len({r["cycle_start"] for r in rs}) >= MIN_N
    ]
    k = max(1, len(judged))
    critical = NormalDist().inv_cdf(1 - (0.05 / k) / 2)

    cells: dict[str, dict] = {}
    for (arm, degree), rs in sorted(groups.items()):
        pp, t, n = _paired(rs)
        wf = _walk(rs)
        passes = bool(
            n >= MIN_N
            and pp >= EFFECT_MIN_PP
            and abs(t) > critical
            and wf["p"] <= 0.05
        )
        cells[f"{arm}|{degree}"] = {
            "arm": arm,
            "degree": degree,
            "n_cycles": n,
            "n_levels": len(rs),
            "delta_pp": pp,
            "t": t,
            "walk_forward": wf,
            "judged": (arm, degree) in judged,
            "passes": passes,
            "profiles": {
                name: len({r["cycle_start"] for r in rs if r["profile"] == name})
                for name in ("AMDX", "XAMD")
            },
        }

    # KETIDAKSESUAIAN BAGIAN 2, dijawab berpasangan per cycle. Dua arm yang
    # keduanya positif tapi tidak terpisah tidak memutuskan apa pun.
    contrast: dict[str, dict] = {}
    for degree in degrees:
        a = {(r["cycle_start"], r["side"]): r for r in groups.get(("q1_to_manip", degree), [])}
        b = {(r["cycle_start"], r["side"]): r for r in groups.get(("accum_to_manip", degree), [])}
        shared = sorted(set(a) & set(b))
        if len(shared) < 2:
            contrast[degree] = {"n": len(shared), "note": "terlalu sedikit untuk dinilai"}
            continue
        diff = [
            (1.0 if b[key]["real_reached"] else 0.0) - (1.0 if a[key]["real_reached"] else 0.0)
            for key in shared
        ]
        by_cycle: dict[int, list[float]] = {}
        for (cycle, _side), d in zip(shared, diff):
            by_cycle.setdefault(cycle, []).append(d)
        per = [sum(v) / len(v) for v in by_cycle.values()]
        mean = sum(per) / len(per)
        var = sum((x - mean) ** 2 for x in per) / (len(per) - 1) if len(per) > 1 else 0.0
        se = sqrt(var / len(per)) if len(per) > 1 else 0.0
        contrast[degree] = {
            "n_cycles": len(per),
            "delta_pp": mean * 100,
            "t": (mean / se if se > 0 else 0.0),
            "differs_at_all": sum(1 for d in diff if d != 0),
            "note": (
                "positif berarti membaca DFR dari kuarter AKUMULASI mengalahkan "
                "membacanya dari Q1 selalu"
            ),
        }

    winners = sorted(key for key, cell in cells.items() if cell["passes"])
    return {
        "preregistered": "tools/phase_targets.py, 2026-09-02",
        "rule": {
            "given_by": "pemiliknya, 2026-09-02",
            "lines": [
                "Accumulation/Consolidation DFR -> Manipulation Targets",
                "Manipulation DFR -> Distribution Targets",
            ],
            "evidence_supplied": "satu chart TradingView, BTC 1h Binance, Tango618",
        },
        "population": {
            "series": [f"{s} {i} {b}" for s, i, b in series],
            "degrees": list(degrees),
            "n_levels": len(rows),
            "n_cycles": len({(r["degree"], r["cycle_start"]) for r in rows}),
        },
        "groups_judged": len(judged),
        "alpha_corrected": 0.05 / k,
        "critical_t": critical,
        "effect_min_pp": EFFECT_MIN_PP,
        "cells": cells,
        "q1_versus_accumulation": contrast,
        "passes": winners,
        "verdict": (
            f"LULUS: {winners}" if winners else "TIDAK ADA ARM YANG LULUS DI DEGREE MANA PUN"
        ),
    }


def _selftest() -> None:
    """Penilai dijalankan pada baris buatan yang jawabannya diketahui.

    Sebuah rig yang tidak pernah ditunjukkan bisa melaporkan LULUS sedang
    melaporkan diamnya sendiri, dan `_paired` adalah tempat kesalahan tanda
    paling mudah bersembunyi.
    """
    # Sepuluh cycle, real selalu tercapai dan placebo tidak: delta harus +100pp.
    perfect = [
        {
            "cycle_start": i,
            "side": "above",
            "real_reached": True,
            "fake_reached": False,
            "arm": "a",
            "degree": "day",
            "profile": "AMDX",
        }
        for i in range(10)
    ]
    pp, t, n = _paired(perfect)
    assert n == 10 and abs(pp - 100.0) < 1e-9, (pp, t, n)

    flipped = [{**r, "real_reached": False, "fake_reached": True} for r in perfect]
    pp2, _, _ = _paired(flipped)
    assert abs(pp2 + 100.0) < 1e-9, pp2

    # DUA SISI SATU CYCLE ADALAH SATU PENGAMATAN. Lihat `_paired`.
    two_sides = [
        {**perfect[0], "side": "above"},
        {**perfect[0], "side": "below", "real_reached": False, "fake_reached": False},
    ]
    pp3, _, n3 = _paired(two_sides)
    assert n3 == 1 and abs(pp3 - 50.0) < 1e-9, (pp3, n3)

    # Aturan pertiga membuang sepertiga PERTAMA.
    bars = [
        Candle(time=i * 60, open=1, high=100 if i == 0 else 10, low=1, close=1, volume=1)
        for i in range(9)
    ]
    band = _thirds_range(bars)
    assert band is not None and band[0] == 10, band

    assert _jitter("x") == _jitter("x")
    assert abs(_jitter("x") - 1.0) >= JITTER_DEAD
    print("selftest OK", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=0)
    parser.add_argument("--degrees", default=",".join(DEGREES_JUDGED))
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument(
        "--oracle",
        action="store_true",
        help="tambahkan arm yang melihat masa depan; ia HARUS lulus",
    )
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    series = SERIES if not args.bars else tuple((s, i, args.bars) for s, i, _ in SERIES)
    degrees = tuple(d.strip() for d in args.degrees.split(",") if d.strip())
    out = study(series, degrees, args.oracle)
    json.dump(out, sys.stdout, indent=2, default=str)
    print()
    return 0 if "error" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
