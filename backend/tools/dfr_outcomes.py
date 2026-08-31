"""Apakah level ekstensi DFR -0,5 dan -1 dicapai lebih sering daripada placebo?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.dfr_outcomes > ../docs/dfr_outcomes.json
    PYTHONPATH=. .venv/Scripts/python.exe -m tools.dfr_outcomes --selfcheck

================================================================================
PRAREGISTRASI, ditulis SEBELUM satu angka dihitung
================================================================================

Praregistrasi keempat di repo ini, mengikuti PRAREGISTRASI-KONDISI.md (21
Agustus), PRAREGISTRASI-KORELASI.md, dan PRAREGISTRASI-YATIM.md (28 Agustus).
Formatnya sengaja sama: hipotesis dulu, ambang dulu, jumlah grup dihitung tool
dan dicetak, walk-forward per fold termasuk fold yang gagal.

--------------------------------------------------------------------------------
1. KENAPA layer ini, dan kenapa pertanyaan ini

`app/layers.py` menyebut `dfr` sebagai satu-satunya layer yang evidence-nya
berbunyi "SINGLE-SOURCED AND UNVERIFIED ... has never been checked against
outcomes". Aturan pertiga sampai ke project ini dari satu deskripsi indicator
closed-source, dan empat property test yang lolos hanya membuktikan
implementation CONSISTENCY, bukan bahwa objeknya berarti apa-apa.

HIPOTESIS INI HARUS BERBEDA DARI YANG SUDAH GAGAL. `dfr_pos` dan `dfr_band`
sudah diuji sebagai kolom pengkondisi ekspektansi di `tools/conditioned.py` dan
gagal, 0 dari 52 dan 0 dari 58 grup. Mengulang bentuk uji itu adalah cara lain
menghasilkan temuan palsu. Jadi yang diuji di sini adalah OBJEK YANG DIGAMBAR,
bukan posisi harga di dalamnya: level ekstensi -0,5 dan -1 yang dibawa
`app/overlays.py` ke chart, diukur dengan bentuk uji yang sama seperti
`liquidity` dan `projections` - reach dalam horizon tetap lawan kontrol.

--------------------------------------------------------------------------------
2. HIPOTESIS, satu kalimat

H-DFR-1: sebuah level ekstensi DFR pada multiple m (0,5 atau 1,0 dari tinggi
band, diproyeksikan ke luar band di kedua sisi) DICAPAI dalam 96 bar sejak band
itu knowable, LEBIH SERING daripada level placebo yang di-jitter per event pada
jarak sebanding dari anchor yang sama, di event yang sama.

Satu arah. Klaim sumbernya adalah level itu "often function as manipulation or
reversal targets", jadi yang diprediksi adalah reach yang LEBIH TINGGI. Delta
negatif dicatat sebagai negatif dan tidak dibalik jadi temuan.

--------------------------------------------------------------------------------
3. POPULASI, dan instan yang dipakai

| Hal | Nilai |
|---|---|
| Instrumen | mt5:XAUUSD, mt5:BTCUSD, mt5:ETHUSD, mt5:EURUSD |
| Timeframe | 1 jam |
| Bar | 20.000, dengan irregular prefix dipotong (lihat Bagian 8) |
| Degree | day, Q1 = 18:00-00:00 New York |
| Band | tiap DFR dari `quarterly.defining_ranges`, aturan pertiga apa adanya |
| Knowable at | `dfr.end`, yaitu Q1 close; scan mulai bar pertama yang time >= itu |
| Horizon | 96 bar, angka yang sama yang dipakai pools, liquidity, projections |
| Level | high + m*height (above) dan low - m*height (below), m di {0,5, 1,0} |
| Reach | above kalau ada bar high >= level; below kalau ada bar low <= level |

Band yang window 96 bar-nya tidak utuh (mepet ujung kanan deret) DIBUANG, bukan
dinilai dengan window pendek. Window pendek menurunkan reach untuk real dan
placebo sekaligus, tapi ia mengubah pertanyaan tanpa mengatakannya.

--------------------------------------------------------------------------------
4. KONTROL, dan cacat kontrol yang TIDAK boleh diulang

Kontrol `pools` terbukti cacat: shuffling memutus pasangan antara jarak sebuah
level dan volatility bar-nya sendiri, dan setelah dipasangkan kembali di dalam
matched distance band gap-nya berbalik dari +2,90pp ke -0,68pp. Jadi TIDAK ADA
shuffling di sini.

Kontrol yang dipakai adalah PER-EVENT JITTER, bentuk yang sama yang dipakai
`projections`. Untuk tiap level real, satu level placebo dibuat di event yang
sama, anchor yang sama, sisi yang sama, window 96 bar yang sama, dengan multiple
`m * f`, `f ~ Uniform(0,6, 1,4)` dan `|f - 1| >= 0,1` supaya placebo tidak jatuh
di angka doktrinnya sendiri. Jaraknya tetap kelipatan tinggi band ITU, jadi
pasangan jarak-lawan-volatility tidak pernah putus.

`f` di-seed deterministik dari (symbol, cycle_start, multiple, side), jadi
re-run menghasilkan angka yang identik dan tidak ada "coba seed lain".

BIAS KONTROL, disebut di depan karena arahnya penting. E[f] = 1, jadi jarak
placebo sama dengan jarak real secara rata-rata. Tapi probabilitas reach sebagai
fungsi jarak itu menurun dan CEMBUNG, sehingga mean-preserving spread MENAIKKAN
reach placebo (Jensen). Kontrol ini karena itu condong ke atas, yang berarti ia
membuat efek positif lebih sulit ditemukan, bukan lebih mudah. Kalau hasilnya
positif, bias ini bukan penjelasannya.

--------------------------------------------------------------------------------
5. UNIT PENGAMATAN, dan kenapa bukan level

Unit primer adalah BAND per multiple, nilainya rata-rata selisih berpasangan
(real dikurangi placebo) atas sisi-sisinya. Bukan level, karena dua level di
band yang sama (above dan below, multiple yang sama) berbagi satu window dan
satu tinggi band, jadi menghitungnya sebagai dua pengamatan bebas menggelembungkan
n dua kali lipat.

SISI TIDAK DIPISAH. Sumbernya tidak memberi arah untuk -0,5 dan -1, dan
`app/overlays.py` menggambar keduanya karena itu. Memisah sisi lalu melaporkan
yang menang adalah menguji aturan yang tidak pernah dinyatakan siapa pun. Reach
per sisi tetap DICETAK untuk transparansi dan DINYATAKAN SEKARANG tidak dinilai.

--------------------------------------------------------------------------------
6. AMBANG LULUS, ditetapkan sekarang

Sebuah grup hanya lulus kalau KEEMPATNYA lolos:

1. `n >= 30` band di grup itu.
2. Delta point estimate `>= +3,0pp`. Angka ini bukan pilihan baru: itu ambang
   praregistrasi yang sama yang dipakai `projections`, yang gagal 6,5x di
   bawahnya pada +0,46pp.
3. `|t| >` nilai kritis dua sisi ber-Bonferroni, alpha 0,05 dibagi `K`, dengan
   `K` = jumlah grup yang layak dinilai (`n >= 30`). `K` dihitung dan dicetak
   tool SEBELUM satu baris pun dilaporkan.
4. Walk-forward 8 fold berurutan waktu, sign test SATU SISI `p <= 0,05`. Dengan
   8 fold itu berarti minimal 7 dari 8 fold delta-nya positif (p=0,0352); 6 dari
   8 memberi p=0,1445 dan GAGAL.

Grup yang dinilai: 4 instrumen x 2 multiple = 8, ditambah 2 baris pooled lintas
instrumen per multiple. Sepuluh baris, dan kesepuluhnya masuk hitungan `K`.
Baris per sisi tidak dinilai dan tidak masuk `K`, sesuai Bagian 5.

VERDICT per grup:
    LULUS    keempat syarat lolos
    NEGATIF  delta negatif dan CI 95 persen lepas dari nol ke bawah
    NULL     selebihnya

AMANDEMEN 30 Agustus 2026, ditulis SESUDAH run pertama dan disebut amandemen.
Bagian ini mendefinisikan verdict per grup dan LUPA mendefinisikan cara
menggabungkan sepuluh grup menjadi satu headline. Kode versi pertama memakai
"ada satu grup NEGATIF berarti headline NEGATIF", dan itu menyerahkan headline
seluruh pengukuran kepada satu sel yang |t|-nya 2,72 lawan bar Bonferroni 2,807
yang ditetapkan di depan - artinya sel yang justru GAGAL melewati koreksi.
Headline sekarang menuntut bar yang sama dengan LULUS. Verdict per grup tidak
diubah dan `negative` tetap dicetak apa adanya. Perubahan ini melemahkan
headline, bukan menguatkannya; catatan ini ada supaya arah itu bisa diperiksa
dan bukan dipercaya.

--------------------------------------------------------------------------------
7. APA YANG TERJADI PADA HASIL APA PUN

Lulus: dicatat dengan angkanya, dan evidence `dfr` di `app/layers.py` boleh
diperbarui oleh sesi berikutnya. Gagal: dicatat dengan angkanya juga, dan
layer-nya tetap digambar sebagai doctrine. Tidak ada baris yang dihapus dari
laporan karena hasilnya mengecewakan, dan tidak ada grup yang ditambahkan
setelah melihat hasil.

--------------------------------------------------------------------------------
8. BATAS YANG SUDAH DIKETAHUI, ditulis di depan

- Window 96 bar band yang berurutan SALING TUMPANG TINDIH (96 jam kira-kira 4
  hari, band harian lahir tiap hari kerja), jadi pengamatan berkorelasi serial
  dan `t` di sini optimistis. Fold walk-forward adalah pertahanan yang nyata,
  bukan `t`-nya.
- `history.irregular_prefix` mencatat bahwa deret MT5 bisa punya bar berjarak
  satu HARI yang dilabeli satu jam. Di situ "96 bar" berarti 96 hari. Prefix itu
  dipotong dan jumlahnya dilaporkan per deret.
- Satu degree, satu timeframe, satu venue. Nol di sini bukan nol di mana-mana.
"""

from __future__ import annotations

import argparse
import json
import random
from bisect import bisect_left
from math import comb, sqrt

from app.models import Candle
from app.quarterly import defining_ranges
from tools import history
from tools.stats import norm_ppf

SERIES: tuple[tuple[str, str, int], ...] = (
    ("mt5:XAUUSD", "1h", 20000),
    ("mt5:BTCUSD", "1h", 20000),
    ("mt5:ETHUSD", "1h", 20000),
    ("mt5:EURUSD", "1h", 20000),
)

#: Angka sumbernya sendiri, `DFRParams.extensions` default, dipakai sebagai
#: besaran positif persis seperti `app/overlays.py` memakainya.
MULTIPLES: tuple[float, ...] = (0.5, 1.0)

HORIZON = 96          # bar, sama dengan pools, liquidity, projections
JITTER_LO = 0.6
JITTER_HI = 1.4
JITTER_DEAD = 0.1     # placebo tidak boleh jatuh di angka doktrinnya sendiri
EFFECT_MIN_PP = 3.0   # ambang praregistrasi, sama dengan projections
FOLDS = 8
SIGN_ALPHA = 0.05
MIN_N = 30
SIDES = ("above", "below")


def _jitter(symbol: str, cycle_start: int, multiple: float, side: str) -> float:
    """Faktor jitter untuk satu level, deterministik dari identitasnya.

    Seed dari string supaya re-run identik dan tidak ada seed yang bisa dipilih
    setelah melihat hasil. Undian diulang selama `f` jatuh di zona mati sekitar
    1,0, sehingga placebo tidak pernah menjadi level real-nya sendiri.
    """
    rng = random.Random(f"{symbol}|{cycle_start}|{multiple}|{side}")
    while True:
        f = rng.uniform(JITTER_LO, JITTER_HI)
        if abs(f - 1.0) >= JITTER_DEAD:
            return f


def _reached(side: str, level: float, top: float, bottom: float) -> bool:
    """Apakah `level` tersentuh oleh window yang ekstremnya `top` dan `bottom`."""
    return level <= top if side == "above" else level >= bottom


def bands_of(
    candles: list[Candle], symbol: str, degree: str
) -> list[dict]:
    """Satu baris per band per multiple: reach real, reach placebo, selisihnya.

    Band yang window 96 bar-nya tidak utuh dibuang, sesuai Bagian 3.
    """
    times = [c.time for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]

    rows: list[dict] = []
    for dfr in defining_ranges(candles, degree):
        height = dfr.high - dfr.low
        if height <= 0.0:
            continue
        start = bisect_left(times, dfr.end)
        if start + HORIZON > len(candles):
            continue
        top = max(highs[start : start + HORIZON])
        bottom = min(lows[start : start + HORIZON])

        for m in MULTIPLES:
            per_side: dict[str, dict] = {}
            for side in SIDES:
                anchor = dfr.high if side == "above" else dfr.low
                sign = 1.0 if side == "above" else -1.0
                f = _jitter(symbol, dfr.cycle_start, m, side)
                real = anchor + sign * m * height
                placebo = anchor + sign * m * f * height
                per_side[side] = {
                    "jitter": f,
                    "real": _reached(side, real, top, bottom),
                    "placebo": _reached(side, placebo, top, bottom),
                }
            diffs = [
                float(v["real"]) - float(v["placebo"]) for v in per_side.values()
            ]
            rows.append({
                "at": dfr.end,
                "multiple": m,
                "height": height,
                "diff": sum(diffs) / len(diffs),
                "sides": per_side,
            })
    return rows


def _mean_sd(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, sqrt(var)


def _sign_test(positive: int, folds: int) -> float:
    """p satu sisi untuk `positive` dari `folds` fold di bawah H0 p=0,5."""
    return sum(comb(folds, k) for k in range(positive, folds + 1)) / 2**folds


def summarise(rows: list[dict]) -> dict:
    """Statistik satu grup. Tidak menilai lulus atau tidak: itu butuh `K`."""
    ordered = sorted(rows, key=lambda r: r["at"])
    diffs = [r["diff"] for r in ordered]
    n = len(diffs)
    out: dict = {"n": n}
    if n == 0:
        return out

    mean, sd = _mean_sd(diffs)
    se = sd / sqrt(n) if n > 1 else 0.0
    out["delta_pp"] = 100.0 * mean
    out["ci95_pp"] = [
        100.0 * (mean - 1.96 * se),
        100.0 * (mean + 1.96 * se),
    ]
    out["t"] = mean / se if se > 0 else 0.0

    levels = [side for r in ordered for side in r["sides"].values()]
    out["levels"] = len(levels)
    out["reach_real_pct"] = 100.0 * sum(s["real"] for s in levels) / len(levels)
    out["reach_placebo_pct"] = (
        100.0 * sum(s["placebo"] for s in levels) / len(levels)
    )
    out["jitter_mean"] = sum(s["jitter"] for s in levels) / len(levels)

    # Per sisi, DICETAK dan TIDAK DINILAI - Bagian 5.
    out["by_side_not_judged"] = {
        side: {
            "n": len(picked),
            "reach_real_pct": 100.0 * sum(s["real"] for s in picked) / len(picked),
            "reach_placebo_pct": (
                100.0 * sum(s["placebo"] for s in picked) / len(picked)
            ),
        }
        for side in SIDES
        if (picked := [r["sides"][side] for r in ordered])
    }

    half = n // 2
    out["halves_pp"] = [
        100.0 * _mean_sd(diffs[:half])[0] if half else None,
        100.0 * _mean_sd(diffs[half:])[0] if n - half else None,
    ]

    # Walk-forward: 8 fold berurutan waktu, ukuran hampir sama. Fold yang gagal
    # ikut dicetak, sesuai standar repo ini.
    folds: list[dict] = []
    for i in range(FOLDS):
        lo = i * n // FOLDS
        hi = (i + 1) * n // FOLDS
        chunk = diffs[lo:hi]
        folds.append({
            "fold": i + 1,
            "n": len(chunk),
            "delta_pp": 100.0 * _mean_sd(chunk)[0] if chunk else None,
        })
    positive = sum(1 for f in folds if f["delta_pp"] is not None and f["delta_pp"] > 0)
    out["folds"] = folds
    out["folds_positive"] = positive
    out["sign_test_p_one_sided"] = _sign_test(positive, FOLDS)
    return out


def verdict(group: dict, t_critical: float) -> tuple[str, dict]:
    """Empat syarat Bagian 6, masing-masing dilaporkan lolos atau tidak."""
    if group["n"] < MIN_N:
        return "TIDAK DINILAI", {"n": False}
    checks = {
        "n": True,
        "effect": group["delta_pp"] >= EFFECT_MIN_PP,
        "t": abs(group["t"]) > t_critical,
        "walkforward": group["sign_test_p_one_sided"] <= SIGN_ALPHA,
    }
    if all(checks.values()) and group["delta_pp"] > 0:
        return "LULUS", checks
    if group["ci95_pp"][1] < 0:
        return "NEGATIF", checks
    return "NULL", checks


def run(series: tuple[tuple[str, str, int], ...], degree: str) -> dict:
    per_series: list[dict] = []
    rows_by_group: dict[tuple[str, float], list[dict]] = {}
    pooled_by_multiple: dict[float, list[dict]] = {m: [] for m in MULTIPLES}

    for symbol, interval, bars in series:
        candles = history.load(symbol, interval, bars)
        cut = history.irregular_prefix(candles, interval)
        candles = candles[cut:]
        rows = bands_of(candles, symbol, degree)
        per_series.append({
            "symbol": symbol,
            "interval": interval,
            "bars_requested": bars,
            "bars_used": len(candles),
            "irregular_prefix_trimmed": cut,
            "first_bar": candles[0].time if candles else None,
            "last_bar": candles[-1].time if candles else None,
            "band_multiple_rows": len(rows),
        })
        for m in MULTIPLES:
            picked = [r for r in rows if r["multiple"] == m]
            rows_by_group[(symbol, m)] = picked
            pooled_by_multiple[m].extend(picked)

    groups: dict[str, dict] = {}
    for (symbol, m), rows in rows_by_group.items():
        groups[f"{symbol} m={m}"] = {"symbol": symbol, "multiple": m, **summarise(rows)}
    for m, rows in pooled_by_multiple.items():
        groups[f"POOLED m={m}"] = {"symbol": "POOLED", "multiple": m, **summarise(rows)}

    # `K` DIHITUNG SEBELUM SATU BARIS PUN DINILAI, janji Bagian 6.
    eligible = [name for name, g in groups.items() if g["n"] >= MIN_N]
    k = len(eligible)
    alpha = SIGN_ALPHA / k if k else SIGN_ALPHA
    t_critical = norm_ppf(1.0 - alpha / 2.0) if k else float("inf")

    for group in groups.values():
        group["verdict"], group["checks"] = verdict(group, t_critical)

    passed = [name for name, g in groups.items() if g["verdict"] == "LULUS"]
    negative = [name for name, g in groups.items() if g["verdict"] == "NEGATIF"]
    # AMANDEMEN, 30 Agustus 2026, ditulis SESUDAH run dan dicatat sebagai
    # amandemen alih-alih diselipkan. Bagian 6 mendefinisikan verdict PER GRUP
    # dan tidak pernah mendefinisikan cara menggabungkan sepuluh grup menjadi
    # satu headline. Versi pertama file ini menggabungkan dengan "ada satu grup
    # NEGATIF berarti headline NEGATIF", dan pada run pertama itu membuat SATU
    # sel dari sepuluh, yang |t|-nya 2,72 dan karena itu ADA DI BAWAH bar
    # Bonferroni 2,807 yang sudah ditetapkan di depan, menulis headline untuk
    # seluruh pengukuran. Headline sekarang menuntut bar yang sama dengan LULUS.
    #
    # Verdict PER GRUP tidak diubah satu pun, dan `negative` di bawah tetap
    # daftar apa adanya sesuai Bagian 6, supaya amandemen ini tidak menghapus
    # angka yang sudah dicetak.
    negative_past_bar = [n for n in negative if abs(groups[n]["t"]) > t_critical]
    return {
        "preregistration": "tools/dfr_outcomes.py docstring, Bagian 1 sampai 8",
        "hypothesis": (
            "H-DFR-1: level ekstensi DFR pada multiple 0.5 dan 1.0 dicapai dalam "
            "96 bar lebih sering daripada placebo per-event jitter pada jarak "
            "sebanding dari anchor yang sama"
        ),
        "degree": degree,
        "horizon_bars": HORIZON,
        "multiples": list(MULTIPLES),
        "thresholds": {
            "min_n": MIN_N,
            "effect_min_pp": EFFECT_MIN_PP,
            "groups_eligible_K": k,
            "bonferroni_alpha": alpha,
            "t_critical_two_sided": t_critical,
            "walkforward_folds": FOLDS,
            "sign_test_alpha_one_sided": SIGN_ALPHA,
            "folds_positive_required": min(
                p for p in range(FOLDS + 1) if _sign_test(p, FOLDS) <= SIGN_ALPHA
            ),
        },
        "series": per_series,
        "groups": groups,
        "passed": passed,
        "negative": negative,
        "negative_past_bonferroni": negative_past_bar,
        "headline_rule": (
            "Amandemen 30 Agustus 2026: headline NEGATIF menuntut bar Bonferroni "
            "yang sama dengan LULUS. Verdict per grup tidak diubah."
        ),
        "verdict": (
            "LULUS" if passed else "NEGATIF" if negative_past_bar else "NULL"
        ),
    }


def _selfcheck() -> None:
    """Satu pemeriksaan yang gagal kalau logika reach atau jitter rusak.

    Deret buatan tangan dengan satu DFR harian yang tingginya diketahui, lalu
    reach dijawab dengan tangan untuk dua level: satu yang jelas tercapai dan
    satu yang jelas tidak.
    """
    assert _reached("above", 10.0, 12.0, 5.0)
    assert not _reached("above", 13.0, 12.0, 5.0)
    assert _reached("below", 6.0, 12.0, 5.0)
    assert not _reached("below", 4.0, 12.0, 5.0)

    # Jitter deterministik, di dalam rentang, dan tidak pernah di zona mati.
    a = _jitter("mt5:XAUUSD", 1700000000, 0.5, "above")
    assert a == _jitter("mt5:XAUUSD", 1700000000, 0.5, "above")
    assert a != _jitter("mt5:XAUUSD", 1700000000, 0.5, "below")
    for seed in range(400):
        f = _jitter("S", seed, 1.0, "above")
        assert JITTER_LO <= f <= JITTER_HI and abs(f - 1.0) >= JITTER_DEAD

    assert _sign_test(8, 8) == 1 / 256
    assert abs(_sign_test(7, 8) - 9 / 256) < 1e-12

    # Satu band, tinggi 10, dan 96 bar sesudahnya yang naik ke +7 lalu turun ke
    # -3 relatif band. m=0.5 above (+5) tercapai, m=1.0 above (+10) tidak.
    step = 3600
    q1_start = 1704063600  # batas Q1 harian yang nyata, dari app.quarters
    rows: list[Candle] = []
    t = q1_start
    for _ in range(6):  # Q1 penuh, 18:00 sampai 00:00
        rows.append(Candle(time=t, open=100, high=110, low=100, close=105))
        t += step
    for i in range(HORIZON + 2):
        top = 117.0 if i == 10 else 111.0
        bottom = 97.0 if i == 20 else 105.0
        rows.append(Candle(time=t, open=108, high=top, low=bottom, close=108))
        t += step
    got = bands_of(rows, "TEST", "day")
    assert got, "band harian tidak terbentuk pada deret selfcheck"
    by_multiple = {r["multiple"]: r for r in got}
    assert by_multiple[0.5]["sides"]["above"]["real"] is True
    assert by_multiple[1.0]["sides"]["above"]["real"] is False
    assert by_multiple[0.5]["sides"]["below"]["real"] is False
    print("selfcheck ok")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--degree", default="day")
    ap.add_argument("--bars", type=int, default=0, help="override jumlah bar")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        _selfcheck()
        return

    series = SERIES
    if args.bars:
        series = tuple((s, i, args.bars) for s, i, _ in SERIES)
    print(json.dumps(run(series, args.degree), indent=1))


if __name__ == "__main__":
    main()
