"""Gate parity: apakah jam QT di MQL5 dan di Python menjawab hal yang sama.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.qt_clock_parity

KENAPA GATE INI ADA, DAN APA YANG IA TANGKAP YANG TEST TEKS TIDAK BISA.

`tests/test_mql5_contract.py` mengikat KONSTANTA di `QTClock.mqh` ke
`app/qt.py` dengan membaca teks source-nya. Itu menangkap batas sesi yang
digeser dan rantai high-prob yang berubah. Ia TIDAK menyentuh aritmetikanya,
dan di situlah dua sisi paling mungkin menyimpang tanpa suara:

  1. DST. MQL5 memakai `SDNyIsDst` yang ditulis tangan di `NYClock.mqh`;
     Python memakai `zoneinfo`. Selisih satu jam di akhir Maret atau awal
     November menggeser SETIAP kuarter di sekitar transisi, dan kedua venue
     tetap mengeluarkan angka yang kelihatan wajar.
  2. Hari dalam minggu. `MqlDateTime.day_of_week` menghitung Minggu sebagai 0;
     `datetime.weekday()` menghitung Senin sebagai 0. Salah satu off-by-one di
     sana menggeser seluruh kuarter mingguan satu hari, yang berarti "Rabu"
     mengukur Selasa.
  3. Pembungkusan Asia lewat tengah malam. Sesi Asia buka 19:30 dan tutup
     01:30, jadi menit ke dalam sesinya melewati batas hari. Dua implementasi
     yang menangani itu berbeda akan sepakat sepanjang sore dan berbeda tiap
     pagi.

Ketiganya sudah punya preseden di repo ini: `docs/mt5_python_parity.json`
mencatat 6 dari 8 sel tidak sepakat, dan itu baru ketahuan setelah ada yang
membandingkan.

CARA PAKAI. Jalankan `ZonelabQTDump` sekali lewat Strategy Tester; ia menulis
`zonelab_qt_clock.csv` ke folder Common MT5. Lalu jalankan tool ini. Ia
membandingkan tiap baris dan keluar dengan exit code, karena vonis yang
dicetak tanpa exit code melaporkan merah sebagai hijau.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from app.qt import source_chain, sequence_listed_source

#: Folder Common MT5, tempat `FILE_COMMON` menulis.
COMMON = Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal" / (
    "Common"
) / "Files"

DUMP = "zonelab_qt_clock.csv"

#: Berapa ketidaksepakatan pertama yang dicetak lengkap. Sisanya dihitung.
#: Sepuluh, karena kalau ada seribu, sepuluh sudah cukup untuk melihat polanya
#: dan seribu baris di terminal menyembunyikan vonisnya.
SHOW = 10


def compare(path: Path) -> dict:
    """Tiap baris dump lawan jawaban Python, dan di mana keduanya berbeda."""
    rows = mismatch_weekly = mismatch_daily = mismatch_q90 = 0
    mismatch_listed = 0
    examples: list[dict] = []
    with path.open(encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows += 1
            at = int(row["utc"])
            weekly, daily, q90 = source_chain(at)
            mine = {
                "weekly": weekly, "daily": daily, "q90": q90,
                # MQL5 HARUS menjawab False dari Jumat sampai Minggu, karena EA
                # wajib memutuskan; Python menjawab None di sana. Perbedaan itu
                # DISENGAJA dan dinormalkan di sini, bukan dilaporkan sebagai
                # ketidaksepakatan - lihat `app/qt.py` divergensi.
                "highprob": bool(sequence_listed_source(at)),
            }
            theirs = {
                "weekly": int(row["weekly"]), "daily": int(row["daily"]),
                "q90": int(row["q90"]), "highprob": row["highprob"] == "1",
            }
            bad = {k for k in mine if mine[k] != theirs[k]}
            if not bad:
                continue
            mismatch_weekly += "weekly" in bad
            mismatch_daily += "daily" in bad
            mismatch_q90 += "q90" in bad
            mismatch_listed += "highprob" in bad
            if len(examples) < SHOW:
                examples.append({"utc": at, "fields": sorted(bad),
                                 "python": mine, "mql5": theirs})
    total = mismatch_weekly + mismatch_daily + mismatch_q90 + mismatch_listed
    return {
        "rows": rows,
        "mismatch_weekly": mismatch_weekly,
        "mismatch_daily": mismatch_daily,
        "mismatch_q90": mismatch_q90,
        "mismatch_highprob": mismatch_listed,
        "mismatch_total": total,
        "examples": examples,
        "agree": rows > 0 and total == 0,
    }


def _selftest() -> None:
    """Cacat yang gate ini ditulis untuk menangkap, disuntikkan lalu diperiksa."""
    import tempfile

    from app import clock

    grid = [clock.ny_wall(2026, 3, 1, 0) + i * 1800 for i in range(2000)]

    def dump(path: Path, shift: int = 0, break_weekly: bool = False) -> None:
        with path.open("w", encoding="ascii", newline="") as handle:
            out = csv.writer(handle, lineterminator="\n")
            out.writerow(["utc", "weekly", "daily", "q90", "highprob"])
            for at in grid:
                weekly, daily, q90 = source_chain(at + shift)
                if break_weekly:
                    weekly = (weekly % 4) + 1
                out.writerow([at, weekly, daily, q90,
                              1 if sequence_listed_source(at + shift) else 0])

    with tempfile.TemporaryDirectory() as folder:
        clean = Path(folder) / "clean.csv"
        dump(clean)
        assert compare(clean)["agree"] is True

        # SATU JAM, yang adalah persis besar sebuah salah-baca DST.
        drifted = Path(folder) / "dst.csv"
        dump(drifted, shift=3600)
        result = compare(drifted)
        assert result["agree"] is False and result["mismatch_daily"] > 0

        # Kuarter mingguan digeser satu hari, bentuk off-by-one day_of_week.
        wrong_day = Path(folder) / "weekday.csv"
        dump(wrong_day, break_weekly=True)
        assert compare(wrong_day)["mismatch_weekly"] > 0

        # File kosong bukan kesepakatan. Nol baris harus GAGAL, karena
        # "tidak ada yang berbeda" dan "tidak ada yang diperiksa" terbaca sama
        # di setiap ringkasan yang tidak menghitung barisnya.
        empty = Path(folder) / "empty.csv"
        empty.write_text("utc,weekly,daily,q90,highprob\n", encoding="ascii")
        assert compare(empty)["agree"] is False

    print("qt_clock_parity selftest ok", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=str(COMMON / DUMP))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0

    path = Path(args.dump)
    if not path.exists():
        raise SystemExit(
            f"QT CLOCK PARITY FAIL: {path} tidak ada. Jalankan ZonelabQTDump "
            f"lewat Strategy Tester dulu; ia menulis {DUMP} ke folder Common."
        )
    result = compare(path)
    json.dump(result, sys.stdout, indent=2)
    print()
    if not result["agree"]:
        raise SystemExit(
            f"QT CLOCK PARITY FAIL: {result['mismatch_total']} ketidaksepakatan "
            f"pada {result['rows']} baris. Dua venue tidak mengukur jam yang sama."
        )
    print(f"QT clock parity ok: {result['rows']} baris sepakat", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
