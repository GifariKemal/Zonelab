"""Apakah anomali `true_opens_in_zone` bertahan di luar emas, atau cuma di sana.

    python -m tools.true_open_matrix
    python -m tools.true_open_matrix --intervals 1h,4h --bars 20000

PERTANYAAN YANG DIJAWAB, dan hanya ini. `docs/PRAREGISTRASI-YATIM.md` Bagian 7
mencatat satu grup yang nyaris lolos di XAUUSD 1 jam: zona yang TIDAK memuat
satu pun True Open terbaca +0,290 R lawan populasi -0,021 R, dengan tanda yang
sama di kedua paruh, tapi |t| 2,35 lawan kritis 3,44. Dokumen itu menutupnya
dengan satu kalimat: itu satu sel, dan nol di satu sel bukan nol di mana-mana.

File ini menjalankan kolom yang SAMA, definisi bucket yang SAMA, dan ambang
yang SAMA, ke seluruh dua belas instrumen yang punya baris biaya terukur. Ia
tidak menambah kolom, tidak menggeser bucket, dan tidak melonggarkan ambang.
Menambah salah satunya akan mengubah ini dari replikasi jadi pencarian.

BONFERRONI DIHITUNG ATAS SELURUH SEL, bukan per instrumen. Menjalankan satu uji
dua puluh empat kali lalu melaporkan yang terbaik dengan ambang satu uji adalah
cara paling umum menghasilkan temuan palsu, dan repo ini sudah pernah kena
sekali lewat `formation_score`. Jumlah grup dihitung di pass pertama, sebelum
satu baris pun dicetak.

SATU ARAH YANG DIPRAREGISTRASI. Yang diuji adalah grup "0", karena itu satu-
satunya yang nyaris lolos di sel pertama. Grup lain tetap dicetak apa adanya
supaya monotonisitasnya terbaca, tapi yang dinilai lulus atau gagal hanya "0".
"""

from __future__ import annotations

import argparse

import numpy as np

from app.costs import BROKERS
from tools.conditioned import (
    ALPHA,
    MIN_GROUP,
    _critical_t,
    rows_with_state,
)

COLUMN = "true_opens_in_zone"
#: Grup yang dipraregistrasi. Lihat docstring.
TARGET = "0"
#: Urutan cetak, supaya monotonisitas terbaca dari kiri ke kanan.
ORDER = ("0", "1-3", "4-9", "10+")


def cells(symbols: list[str], intervals: list[str], bars: int, flat: bool):
    """Baris per sel, dengan kegagalan satu sel yang tidak membatalkan sisanya.

    Aturan yang sama dengan `execute.gather` dan dengan matrix di
    `tools/quant.py`: satu deret yang tidak terbaca menghentikan deret itu dan
    bukan run-nya. Sel yang gagal dicetak, tidak disembunyikan, karena matrix
    yang kehilangan sel tanpa mengatakannya terbaca sebagai universe yang lebih
    kecil.
    """
    total = len(symbols) * len(intervals)
    done = 0
    for symbol in symbols:
        for interval in intervals:
            done += 1
            # DICETAK SAAT MULAI, BUKAN SAAT SELESAI. Versi pertama file ini
            # diam sepanjang pengumpulan, karena sel yang berhasil di-yield
            # tanpa mencetak apa pun. Dua puluh menit tanpa satu baris tidak
            # bisa dibedakan dari proses yang hang, dan itu persis keluhan yang
            # membuat run pertama dihentikan sebelum selesai.
            print(f"[{done}/{total}] {symbol} {interval} ...", flush=True)
            try:
                rows = rows_with_state(f"mt5:{symbol}", interval, bars, flat)
            except Exception as exc:  # noqa: BLE001 - satu sel, bukan run
                print(f"{symbol:8s} {interval:3s} GAGAL: {str(exc)[:70]}")
                continue
            if not rows:
                print(f"{symbol:8s} {interval:3s} tanpa trade yang lolos gerbang")
                continue
            print(f"[{done}/{total}] {symbol} {interval} {len(rows)} trade",
                  flush=True)
            yield symbol, interval, rows


def welch(a: np.ndarray, b: np.ndarray) -> float:
    """t Welch, varians tidak diasumsikan sama. Nol kalau tidak terdefinisi."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    if va + vb <= 0:
        return 0.0
    return float((a.mean() - b.mean()) / np.sqrt(va + vb))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intervals", default="1h,4h")
    parser.add_argument("--bars", type=int, default=20_000)
    parser.add_argument("--hold", action="store_true",
                        help="nilai pada horizon 80 bar alih-alih aturan flat")
    args = parser.parse_args()

    symbols = sorted(BROKERS["exness_raw"])
    intervals = [x.strip() for x in args.intervals.split(",") if x.strip()]
    flat = not args.hold

    print(f"kolom {COLUMN}, grup yang dipraregistrasi \"{TARGET}\"")
    print(f"{len(symbols)} instrumen x {len(intervals)} timeframe, "
          f"{args.bars} bar, exit {'hold 80 bar' if args.hold else 'flat di rollover'}")
    print(f"instrumen: {', '.join(symbols)}\n")

    # PASS PERTAMA: kumpulkan, lalu hitung berapa grup layak dinilai. Ambangnya
    # bergantung pada hitungan itu, jadi ia harus selesai sebelum satu baris pun
    # dilaporkan.
    collected = list(cells(symbols, intervals, args.bars, flat))
    judged = 0
    for _, _, rows in collected:
        seen: dict[object, int] = {}
        for row in rows:
            key = row["state"].get(COLUMN)
            seen[key] = seen.get(key, 0) + 1
        judged += sum(1 for n in seen.values() if n >= MIN_GROUP)
    if not judged:
        print("nol grup layak dinilai")
        return 1
    critical = _critical_t(judged)
    print(f"{len(collected)} sel terbaca, {judged} grup layak dinilai, "
          f"alpha {ALPHA}/{judged} = {ALPHA / judged:.6f}, "
          f"|t| kritis {critical:.2f}\n")

    header = (f"{'sel':13s} {'n':>5s} {'expR':>7s} "
              + " ".join(f"{g:>8s}" for g in ORDER)
              + f" {'t(0)':>7s} {'paruh(0)':>17s} {'lulus':>6s}")
    print(header)
    print("-" * len(header))

    passed: list[str] = []
    for symbol, interval, rows in collected:
        everything = np.array([r["r"] for r in rows])
        buckets: dict[object, list[dict]] = {}
        for row in rows:
            buckets.setdefault(row["state"].get(COLUMN), []).append(row)

        cellname = f"{symbol} {interval}"
        means = []
        for g in ORDER:
            grp = buckets.get(g, [])
            means.append(f"{np.mean([r['r'] for r in grp]):+8.3f}"
                         if len(grp) >= MIN_GROUP else f"{'n<30':>8s}")

        target = buckets.get(TARGET, [])
        if len(target) < MIN_GROUP:
            print(f"{cellname:13s} {len(rows):5d} {everything.mean():+7.3f} "
                  + " ".join(means) + f" {'-':>7s} {'-':>17s} {'-':>6s}")
            continue

        values = np.array([r["r"] for r in target])
        rest = np.array([r["r"] for r in rows
                         if row_key(r) != TARGET])
        t = welch(values, rest)
        # PARUH DIPOTONG PADA WAKTU, PERSIS SEPERTI `conditioned.py`, yang
        # memakai `cut = rows[len(rows)//2]["at"]` atas SELURUH populasi.
        #
        # Versi pertama file ini memotong grup targetnya sendiri jadi dua
        # berdasarkan jumlah anggota, dan itu kriteria yang BERBEDA: ia bertanya
        # "apakah efeknya bertahan di separuh anggota pertama", bukan "apakah ia
        # bertahan di separuh sejarah pertama". Yang kedua lebih keras dan itu
        # yang dipraregistrasi. Memakai yang pertama berarti melonggarkan
        # ambang, yang docstring file ini sendiri berjanji tidak dilakukan.
        cut = rows[len(rows) // 2]["at"]
        early = np.array([r["r"] for r in target if r["at"] < cut])
        late = np.array([r["r"] for r in target if r["at"] >= cut])
        first = float(early.mean()) if len(early) else 0.0
        second = float(late.mean()) if len(late) else 0.0
        same_sign = bool(len(early) and len(late)) and (first > 0) == (second > 0)
        ok = len(target) >= MIN_GROUP and abs(t) > critical and same_sign
        if ok:
            passed.append(cellname)
        print(f"{cellname:13s} {len(rows):5d} {everything.mean():+7.3f} "
              + " ".join(means)
              + f" {t:+7.2f} {first:+8.3f}/{second:+8.3f} "
              + f"{'YA' if ok else 'tidak':>6s}")

    print()
    print(f"sel yang LULUS ketiga syarat: {len(passed)} dari {len(collected)}"
          + (f" -> {', '.join(passed)}" if passed else ""))
    return 0


def row_key(row: dict) -> object:
    return row["state"].get(COLUMN)


if __name__ == "__main__":
    raise SystemExit(main())
