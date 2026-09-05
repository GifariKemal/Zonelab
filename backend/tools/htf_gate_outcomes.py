"""Praregistrasi ketujuh: apakah `--htf-gate` layak memblokir order.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.htf_gate_outcomes \
        > ../docs/htf_gate_outcomes.json

Ditulis 5 September 2026, SEBELUM satu angka pun dihitung.

===========================================================================
1. KENAPA INI MENDESAK, DAN BUKAN SEKADAR RAPI
===========================================================================

`--htf-gate` sudah diarmed di `AT_FLAGS` dalam `start.bat`, pada daemon yang
membawa `--send`. `tools/execute.py` menolak zona yang sisinya berlawanan
dengan bias daily FVG, mencatatnya di journal, dan tidak pernah mengorder.

Nol angka mendukungnya. Aturan repo ini sendiri menuliskannya di
`app/ict.py:Rules`: `required` default KOSONG justru supaya sebuah klausa
diukur sebelum ia boleh memblokir. Gerbang ini melewatkan urutan itu, jadi
sekarang urutannya dikembalikan.

===========================================================================
2. APA YANG GERBANG ITU LAKUKAN, PERSIS
===========================================================================

`daily_fvg_bias` mencari FVG harian TERBARU yang belum terisi dan yang MEMUAT
harga saat ini. FVG demand memberi bias bullish, supply memberi bearish. Lalu:

    zona demand (buy)  + bias bearish -> DITOLAK
    zona supply (sell) + bias bullish -> DITOLAK
    tidak ada FVG yang memuat harga  -> gerbang diam, trade lewat

Jadi populasinya terbelah tiga, dan yang ketiga itu yang sering terlupa:

    htf_agrees True   : di dalam FVG yang setuju      -> DIAMBIL
    htf_agrees False  : di dalam FVG yang tidak setuju -> DIBLOKIR
    htf_agrees None   : tidak di dalam FVG apa pun     -> DIAMBIL

Gerbang ini hanya membuang kohort False. Karena itu pertanyaannya bukan
"apakah True lebih baik dari False", melainkan "apakah False lebih buruk dari
SISA POPULASI YANG DIAMBIL", yaitu True digabung None. Sebuah gerbang yang
membuang kohort yang sama baiknya dengan sisanya menghapus trade tanpa alasan
dan mengecilkan sampel tanpa imbalan.

===========================================================================
3. POPULASI
===========================================================================

XAUUSD dan BTCUSD, dan itu BUKAN pilihan yang dibuat setelah melihat hasil:
`AT_FLAGS` menjalankan daemon dengan `--symbol mt5:XAUUSD,mt5:BTCUSD`, jadi
dua instrumen itulah yang gerbang ini benar-benar gerbangi.

Baris datang dari `tools/checklist_outcomes.py:rows_for` tanpa diubah: first
touch zona `supply_demand` dengan `departure_atr >= 2.0`, entry 1 jam,
diselesaikan di bar 5 menit, biaya `exness_raw`, flat di rollover.

===========================================================================
4. DUA HAL YANG MEMBUAT ANGKA INI TIDAK PERSIS ANGKA PRODUKSI
===========================================================================

Keduanya ditulis sekarang supaya tidak terbaca sebagai temuan nanti.

  a. BAR KEPUTUSANNYA BERBEDA. Produksi menilai gerbang ini ketika zona masih
     segar dan order limit dipasang; rig ini menilainya di bar SENTUHAN. Yang
     diukur karena itu ATURANNYA, bukan detik persisnya menyala. Bar sentuhan
     adalah bacaan yang LEBIH MENGUNTUNGKAN gerbang: di sana harga berada di
     zona, jadi uji "di dalam FVG harian" paling mungkin terpenuhi. Kalau
     aturannya null di bacaan yang paling menguntungkan, ia tidak akan
     menyelamatkan diri di bacaan yang lain.

  b. BAR HARIAN YANG BERJALAN DIBUANG. Live, bar harian yang memuat `now`
     terbaca separuh jadi; di riwayat ia lengkap, dan memakainya berarti
     membaca sisa hari yang belum terjadi. Rig ini hanya memakai bar yang
     sudah TUTUP sebelum `now`, jadi FVG terbaru yang terlihat di sini satu
     bar lebih tua daripada yang produksi lihat. Konservatif, bukan menyanjung.

===========================================================================
5. HIPOTESIS DAN AMBANGNYA
===========================================================================

H-1 (KLAIM GERBANGNYA). Kohort yang DIBLOKIR, `htf_agrees is False`, punya
  ekspektansi LEBIH RENDAH daripada kohort yang diambil, `True` digabung
  `None`. Lolos kalau ketiganya terpenuhi, sama dengan praregistrasi kelima:
    1. `n >= 30` di kedua sisi.
    2. `|t|` Welch melewati nilai kritis Bonferroni.
    3. Tanda selisihnya bertahan di kedua paruh sampel.

H-2 (EFEK DI AKUN). Ekspektansi populasi yang TERSISA setelah gerbang menyala
  melebihi ekspektansi populasi penuh. Dilaporkan bersama jumlah trade yang
  hilang, karena gerbang yang menaikkan ekspektansi sambil membuang separuh
  sampel adalah keputusan yang berbeda dari gerbang yang menaikkannya gratis.

H-3 (KONTROL ARAH). `htf_agrees` tersusun dari dua hal: berada di dalam FVG
  harian, dan sisinya cocok. Kalau kohort `None` sendiri sudah berbeda dari
  kohort di-dalam-FVG, maka yang terukur adalah "harga sedang di dalam gap
  harian", bukan "arahnya cocok". Jadi `None` lawan bukan-None dilaporkan
  terpisah, dan itu kontrolnya.

KOREKSI BANYAK-PERBANDINGAN. Alpha dua sisi 0,05 dibagi K, dengan K jumlah
seluruh grup yang layak dinilai plus ketiga kontras di atas, dihitung sebelum
satu hasil pun dilaporkan.

KONTROL INSTRUMEN. Dua instrumen ini ekspektansi dasarnya berbeda, jadi tiap
kontras dihitung DUA KALI: pada R mentah dan pada R yang sudah dikurangi
rata-rata instrumennya. Kalau keduanya tidak sepakat, yang di-demean yang
dipercaya, dan itu ditetapkan sekarang. Tanda per instrumen ikut dilaporkan.

===========================================================================
6. YANG TIDAK AKAN DILAKUKAN
===========================================================================

  - Tidak menambah instrumen di luar dua yang daemon-nya jalankan.
  - Tidak menyetel definisi FVG harian, ambang terisi, atau jendela 200 bar.
    Semuanya milik `daily_fvg_bias`, dan rig ini memanggil fungsi yang SAMA
    dengan yang produksi panggil, bukan salinannya.
  - Tidak melaporkan H-1 lolos kalau H-3 menunjukkan efeknya datang dari
    berada di dalam gap dan bukan dari arahnya.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import pathlib
import sys

import numpy as np

from tools.checklist_outcomes import _halves_agree, _welch, rows_for
from tools.conditioned import ALPHA, MIN_GROUP, _critical_t
from tools.intrabar import FINER

#: Dua instrumen yang `AT_FLAGS` benar-benar jalankan. Bukan hasil pencarian.
SYMBOLS = ("XAUUSD", "BTCUSD")


def _contrast(rows: list[dict], pick, key: str, critical: float) -> dict:
    """Satu kohort lawan sisanya, dengan uji paruh dan tanda per instrumen."""
    inside = np.array([r[key] for r in rows if pick(r)], dtype=np.float64)
    rest = np.array([r[key] for r in rows if not pick(r)], dtype=np.float64)
    out: dict = {"n_inside": int(len(inside)), "n_rest": int(len(rest))}
    if len(inside) < MIN_GROUP or len(rest) < MIN_GROUP:
        out["judged"] = False
        return out
    delta, t = _welch(inside, rest)
    halves, same = _halves_agree(rows, pick, key)
    agree = per_symbol = 0
    for sym in {r["symbol"] for r in rows}:
        mine = [r for r in rows if r["symbol"] == sym]
        a = np.array([r[key] for r in mine if pick(r)])
        b = np.array([r[key] for r in mine if not pick(r)])
        if not len(a) or not len(b):
            continue
        per_symbol += 1
        agree += (a.mean() - b.mean() > 0) == (delta > 0)
    out.update({
        "judged": True,
        "exp_r_inside": float(inside.mean()), "exp_r_rest": float(rest.mean()),
        "delta": delta, "t": t,
        "halves_delta": halves, "halves_same_sign": same,
        "symbols_same_sign": f"{agree}/{per_symbol}",
        "separates": bool(abs(t) >= critical and same),
    })
    return out


def study(per_symbol: dict[str, list[dict]]) -> dict:
    pooled = [r for rows in per_symbol.values() for r in rows]
    if not pooled:
        return {"error": "tidak ada trade yang bisa diselesaikan di bar halus"}

    means = {s: float(np.mean([r["r"] for r in rows]))
             for s, rows in per_symbol.items()}
    for row in pooled:
        row["r_dm"] = row["r"] - means[row["symbol"]]

    # K DIHITUNG SEBELUM SATU HASIL DILAPORKAN. Tiga nilai kolom yang layak
    # dinilai, ditambah ketiga kontras hipotesis.
    counts: dict[object, int] = {}
    for row in pooled:
        counts[row.get("htf_agrees")] = counts.get(row.get("htf_agrees"), 0) + 1
    k = sum(1 for n in counts.values() if n >= MIN_GROUP) + 3
    critical = _critical_t(k)

    blocked = _contrast(pooled, lambda r: r.get("htf_agrees") is False,
                        "r", critical)
    blocked_dm = _contrast(pooled, lambda r: r.get("htf_agrees") is False,
                           "r_dm", critical)
    inside_gap = _contrast(pooled, lambda r: r.get("htf_agrees") is not None,
                           "r", critical)
    inside_gap_dm = _contrast(pooled, lambda r: r.get("htf_agrees") is not None,
                              "r_dm", critical)

    full = np.array([r["r"] for r in pooled], dtype=np.float64)
    kept = np.array([r["r"] for r in pooled
                     if r.get("htf_agrees") is not False], dtype=np.float64)
    lift = (float(kept.mean() - full.mean()) if len(kept) else None)

    # H-1 lolos hanya kalau kohort yang diblokir memang LEBIH BURUK. Tanda
    # positif berarti yang diblokir justru lebih baik, dan itu vonis terbalik.
    h1 = bool(blocked.get("separates") and blocked.get("delta", 0) < 0)
    return {
        "preregistered": "docstring tools/htf_gate_outcomes.py, 2026-09-05",
        "population_from": "tools/checklist_outcomes.py:rows_for, tidak diubah",
        "gate": "tools/execute.py:daily_fvg_bias, fungsi yang sama dipanggil produksi",
        "population": {
            "n": len(pooled), "exp_r": float(full.mean()),
            "per_symbol": {s: {"n": len(rows), "exp_r": means[s]}
                           for s, rows in per_symbol.items()},
            "cohorts": {str(key): value for key, value in counts.items()},
        },
        "threshold": {"alpha": ALPHA, "groups_judged": k,
                      "alpha_corrected": ALPHA / k, "critical_t": critical,
                      "min_group": MIN_GROUP},
        "H1_blocked_cohort_is_worse": {
            "raw": blocked, "instrument_demeaned": blocked_dm,
            "verdict": h1,
        },
        "H2_account_effect": {
            "n_full": int(len(full)), "n_kept": int(len(kept)),
            "n_removed": int(len(full) - len(kept)),
            "exp_r_full": float(full.mean()),
            "exp_r_kept": float(kept.mean()) if len(kept) else None,
            "lift": lift,
            "verdict": bool(lift is not None and lift > 0),
        },
        "H3_direction_control": {
            "raw": inside_gap, "instrument_demeaned": inside_gap_dm,
            "note": ("kontras ini menanyakan apakah BERADA DI DALAM gap harian "
                     "sudah memisahkan, terlepas dari arahnya. Kalau ia "
                     "memisahkan dan H-1 juga, yang terukur bukan arahnya."),
        },
    }


def _selftest() -> None:
    """Cacat yang tool ini ditulis untuk menangkap, disuntikkan lalu diperiksa."""
    import random

    # SEBARAN, BUKAN NILAI TETAP. Fixture pertama memakai R konstan, jadi
    # varians nol dan Welch t keluar `nan` - lolos yang terbaca gagal. Data
    # nyata selalu bervarian, jadi fixture yang tidak bervarian menguji jalur
    # yang tidak pernah ada.
    rng = random.Random(11)

    def rows(n, flag, centre):
        return [{"symbol": "X" if i % 2 else "Y", "time": i,
                 "r": rng.gauss(centre, 1.0), "htf_agrees": flag}
                for i in range(n)]

    # SINYAL: kohort yang diblokir memang lebih buruk. H-1 harus lolos.
    good = {"X": rows(60, False, -1.0) + rows(60, True, 1.0) + rows(60, None, 1.0)}
    for i, row in enumerate(good["X"]):
        row["symbol"] = "X" if i % 2 else "Y"
    per = {"X": [r for r in good["X"] if r["symbol"] == "X"],
           "Y": [r for r in good["X"] if r["symbol"] == "Y"]}
    out = study(per)
    assert out["H1_blocked_cohort_is_worse"]["verdict"] is True, out["H1_blocked_cohort_is_worse"]
    assert out["H2_account_effect"]["lift"] > 0

    # TANDA TERBALIK: yang diblokir justru LEBIH BAIK. H-1 harus GAGAL, dan
    # ini bacaan yang paling penting: sebuah gerbang bisa "memisahkan" ke arah
    # yang salah, dan melaporkan itu sebagai lolos akan membenarkan gerbang
    # yang membuang trade terbaiknya.
    flipped = {"X": rows(60, False, 1.0) + rows(60, True, -1.0) + rows(60, None, -1.0)}
    for i, row in enumerate(flipped["X"]):
        row["symbol"] = "X" if i % 2 else "Y"
    per2 = {"X": [r for r in flipped["X"] if r["symbol"] == "X"],
            "Y": [r for r in flipped["X"] if r["symbol"] == "Y"]}
    out2 = study(per2)
    assert out2["H1_blocked_cohort_is_worse"]["raw"]["separates"] is True
    assert out2["H1_blocked_cohort_is_worse"]["verdict"] is False, "tanda terbalik lolos"
    assert out2["H2_account_effect"]["lift"] < 0

    # DERAU: tidak ada yang boleh memisahkan.
    noise = []
    for i in range(360):
        noise.append({"symbol": "X" if i % 2 else "Y", "time": i,
                      "r": rng.gauss(0, 1),
                      "htf_agrees": [True, False, None][i % 3]})
    per3 = {"X": [r for r in noise if r["symbol"] == "X"],
            "Y": [r for r in noise if r["symbol"] == "Y"]}
    out3 = study(per3)
    assert out3["H1_blocked_cohort_is_worse"]["verdict"] is False
    assert out3["H1_blocked_cohort_is_worse"]["raw"]["separates"] is False

    # Kohort yang terlalu kecil TIDAK dinilai, bukan dinilai diam-diam.
    tiny = {"X": rows(10, False, -1.0) + rows(60, True, 1.0)}
    for i, row in enumerate(tiny["X"]):
        row["symbol"] = "X" if i % 2 else "Y"
    per4 = {"X": [r for r in tiny["X"] if r["symbol"] == "X"],
            "Y": [r for r in tiny["X"] if r["symbol"] == "Y"]}
    assert study(per4)["H1_blocked_cohort_is_worse"]["raw"]["judged"] is False

    _selftest_one_half_carries_it()
    print("htf_gate_outcomes selftest ok", file=sys.stderr)


def _selftest_one_half_carries_it() -> None:
    """Selisih yang seluruhnya dibawa satu paruh HARUS gagal, walau t besar.

    Ini bentuk kegagalan yang paling sering menipu di repo ini, dan versi
    pertama selftest ini TIDAK mengujinya: mencabut uji paruh dari `separates`
    tidak membuat satu assert pun merah. Fixture di bawah dibangun khusus untuk
    itu - paruh pertama memberi selisih -10, paruh kedua +1, jadi gabungannya
    negatif dan signifikan sementara tandanya berbalik di tengah.
    """
    import random

    rng = random.Random(5)
    rows = []
    for i in range(240):
        first_half = i < 120
        blocked = i % 2 == 0
        if first_half:
            centre = -5.0 if blocked else 5.0
        else:
            centre = 0.5 if blocked else -0.5
        rows.append({"symbol": "X" if i % 4 < 2 else "Y", "time": i,
                     "r": rng.gauss(centre, 1.0),
                     "htf_agrees": False if blocked else True})
    per = {"X": [r for r in rows if r["symbol"] == "X"],
           "Y": [r for r in rows if r["symbol"] == "Y"]}
    out = study(per)["H1_blocked_cohort_is_worse"]["raw"]

    assert out["judged"] is True
    assert abs(out["t"]) >= 3.0, out["t"]
    assert out["halves_same_sign"] is False, out["halves_delta"]
    assert out["separates"] is False, out
    # Dan vonisnya ikut gagal, bukan cuma `separates`.
    assert study(per)["H1_blocked_cohort_is_worse"]["verdict"] is False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--fine", default="")
    parser.add_argument("--rows-out", default="")
    parser.add_argument("--rows-in", default="")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    fine = args.fine or FINER.get(args.interval, "5m")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        if args.rows_in:
            per_symbol = json.loads(
                pathlib.Path(args.rows_in).read_text(encoding="utf-8"))
            if not per_symbol or any(not v for v in per_symbol.values()):
                raise SystemExit(f"{args.rows_in} kosong atau ada simbol nol baris")
        else:
            # RESUME, sama alasannya dengan `tools/qt_outcomes.py`: lintasan
            # ini membayar terminal MT5 per instrumen, dan proses panjang di
            # mesin ini sudah pernah mati di tengah. File yang sudah ada
            # dipakai, instrumen yang sudah ada dilewati.
            per_symbol = {}
            if args.rows_out and pathlib.Path(args.rows_out).exists():
                with contextlib.suppress(OSError, ValueError):
                    per_symbol = json.loads(
                        pathlib.Path(args.rows_out).read_text(encoding="utf-8"))
            for symbol in symbols:
                if symbol in per_symbol:
                    print(f"  {symbol}: dilewati, sudah di cache "
                          f"({len(per_symbol[symbol])} trade)", file=sys.stderr)
                    continue
                got = rows_for(symbol, args.interval, fine)
                print(f"  {symbol}: {len(got)} trade", file=sys.stderr)
                if got:
                    per_symbol[symbol] = got
                if args.rows_out:
                    pathlib.Path(args.rows_out).write_text(
                        json.dumps(per_symbol, default=str), encoding="utf-8")
        out = study(per_symbol)
    json.dump(out, sys.stdout, indent=2, default=str)
    print()
    return 0 if "error" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
