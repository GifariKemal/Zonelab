"""Parity NYATA: kode MQL5 yang dieksekusi terminal lawan detektor numpy.

    python -m tools.mqh_parity

APA YANG DITUTUP TOOL INI. Tiga gate lama, `tools/ea_parity.py`,
`ea_parity_ob.py` dan `ea_parity_fvg.py`, membandingkan detektor numpy dengan
PORT REFERENSI PYTHON yang tinggal di file gate itu sendiri. Ketiganya hijau,
dan `mql5/ZonelabSupplyDemand/README.md` menyebut hasilnya "port faithful" dan
"parity-proven". Yang dibuktikan sebenarnya Python cocok dengan Python: tidak
satu baris pun `.mqh` pernah dijalankan oleh gate mana pun. Kalau `.mqh` bergeser
dari port referensinya besok, ketiga gate itu tetap hijau.

CARA KERJANYA. `mql5/ZonelabSupplyDemand/ZonelabParityDump.mq5` dijalankan di
Strategy Tester, memanggil `SDDetect`, `SDDedupe`, `DetectOrderBlock` dan
`DetectFVG` yang sesungguhnya, lalu menulis DUA hal ke folder Common: zona yang
dihasilkan, DAN bar yang dipakai menghasilkannya. Tool ini membaca bar itu,
bukan membaca MT5 sendiri. Jadi window-nya tidak ditebak dan selisih apa pun
yang muncul adalah selisih logika detektor, bukan selisih data.

Itu juga yang membuatnya deterministik. Gate lama membaca ekor MT5 hidup, jadi
hitungannya bergeser antar-run di tree yang sama (1033 order block di README,
1032 hari ini) - masalah yang sama yang sudah memakan `e2e/labels.mjs`.

MENJALANKAN ULANG DUMP-NYA:

    "C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe" \\
        /config:"...\\mql5\\ZonelabSupplyDemand\\parity.ini"

DIBUKTIKAN TIDAK KOSONG: dengan test "last" dicabut dari port referensi order
block, gate lama melaporkan 414 dari 415 mismatch - tapi tetap exit 0 sampai
1 September 2026. Yang ini exit 1.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import time
from pathlib import Path

from app.detect.imbalance import detect_fvg, detect_order_block
from app.detect.inversion import detect_breaker, detect_ifvg
from app.detect.supply_demand import detect
from app.models import Candle, ImbalanceParams, SupplyDemandParams, ZoneState

#: Folder Common terminal MT5. Dump memakai FILE_COMMON supaya hasilnya tidak
#: terkubur di direktori agent tester yang namanya berubah tiap konfigurasi.
COMMON = Path(
    os.environ.get("APPDATA", "")
) / "MetaQuotes" / "Terminal" / "Common" / "Files"

#: Layer ICT yang punya port MQL5 berbentuk ZONA, dipetakan ke file dump-nya.
PORTED = {
    "supply_demand": "zonelab_parity_sd.csv",
    "order_block": "zonelab_parity_ob.csv",
    "fvg": "zonelab_parity_fvg.csv",
    "ifvg": "zonelab_parity_ifvg.csv",
    "breaker": "zonelab_parity_brk.csv",
}

#: Layer ICT yang punya port MQL5 berbentuk EVENT. Bentuk kedua, dan ia ada
#: karena tidak satu pun layer ICT sisanya menghasilkan box: cisd, structure
#: dan psp menghasilkan EVENT, pools, liquidity dan projections menghasilkan
#: LEVEL, ssmt menghasilkan SPAN. Menulis sebuah event sebagai zona dengan
#: `top == bottom` akan membuatnya LOLOS pemeriksaan geometri secara hampa,
#: yang lebih buruk daripada tidak diperiksa sama sekali.
PORTED_LEVELS = {
    "pools": "zonelab_parity_pools.csv",
    "liquidity": "zonelab_parity_liquidity.csv",
    "projections": "zonelab_parity_projections.csv",
}

PORTED_EVENTS = {
    "cisd": "zonelab_parity_cisd.csv",
    "structure": "zonelab_parity_structure.csv",
}

#: Bentuk KEENAM, dan satu-satunya yang tidak beku saat lahir. Sebuah gap beku:
#: kedua harganya tetap begitu kedua bar-nya ada. Sebuah event horizon tidak, ia
#: rata-rata antara dua gap yang bertetangga MENURUT HARGA, jadi gap baru yang
#: menyisip di antara dua gap lama menggeser level yang sudah tergambar tanpa
#: satu harga pun berubah. Karena itu file keduanya dibandingkan dengan
#: pertanyaan yang berbeda: bukan "apakah nilainya sama", tapi "apakah nilainya
#: sama PADA BAR YANG SAMA".
PORTED_GAPS = {
    "gaps": ("zonelab_parity_gaps.csv", "zonelab_parity_horizons.csv"),
}

#: Jarak antar-bar sampel `as_of`, dan ia HARUS sama dengan `InpHorizonEvery`
#: di ZonelabParityDump.mq5. Sisi Python membangun daftar sampelnya sendiri dari
#: bar alih-alih membaca kolom `as_of` milik MQL5, supaya dump yang kehilangan
#: separuh sampelnya kelihatan sebagai count mismatch dan bukan sebagai
#: kecocokan sempurna atas sisa yang kebetulan tertulis.
HORIZON_EVERY = 200

#: Layer ICT yang SENGAJA belum diport, dengan alasannya masing-masing.
#: `tests/test_mql5_contract.py` menuntut ketiga dict ini bersama-sama menutup
#: setiap layer berkeluarga ICT di `app.layers.LAYERS`, jadi layer baru harus
#: mendarat di salah satunya. Yang dicegah bukan penambahan layer, melainkan
#: penambahan yang presisinya tidak pernah diukur tanpa ada yang menuliskan
#: bahwa ia tidak diukur - karena "belum diukur" dan "diukur dan lolos" tidak
#: boleh terlihat sama dari luar.
UNPORTED: dict[str, str] = {
    "ssmt": (
        "500 sampai 700 baris untuk grid quarter dan intersection multi-symbol, "
        "di atas objek yang sudah diukur NULL di 0 dari 24 sel dengan tanda "
        "terbagi 12 lawan 12 (docs/ssmt_outcomes.json)"
    ),
    "psp": (
        "TIDAK AKAN DIPORT. 48 dari 48 sel null, |z| terbesar 2,104 lawan bar "
        "Bonferroni 3,279 (docs/psp_outcomes.json), dan triad_crack_rate "
        "identik 0,2644 untuk psp-sesudah-ssmt dan psp-sendirian, jadi premis "
        "pairing-nya tidak berdiri di data ini. Ia juga dilarang menyentuh "
        "jalur keputusan oleh tests/test_psp_not_wired_to_decisions.py"
    ),
}

_STATE = {
    "0": ZoneState.FRESH,
    "1": ZoneState.TESTED,
    "2": ZoneState.MITIGATED,
    "3": ZoneState.BROKEN,
}


def read_bars(path: Path) -> list[Candle]:
    with path.open(newline="", encoding="ascii") as handle:
        return [
            Candle(
                time=int(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=0.0,
            )
            for row in csv.DictReader(handle)
        ]


def read_zones(path: Path) -> list[dict]:
    with path.open(newline="", encoding="ascii") as handle:
        return list(csv.DictReader(handle))


def compare(name: str, zones_py, zones_mq: list[dict]) -> int:
    """Return the mismatch count, and print the first ten in full."""
    # `base_from` ikut jadi kunci urut, dan bukan kerapian. Sebuah box inversi
    # memakai bar inversinya sebagai `time_from`, jadi empat belas breaker bisa
    # berbagi satu stempel waktu dan hanya origin induknya yang membedakan -
    # `inversion.py` mencatat persis kasus itu. Mengurutkan tanpa `base_from`
    # akan memasangkan zona yang salah dan melaporkan mismatch palsu, atau
    # lebih buruk, menyembunyikan yang asli.
    py = sorted(
        zones_py,
        key=lambda z: (z.time_from, z.anatomy.base_from, z.kind.value, z.side.value),
    )
    mq = sorted(
        zones_mq,
        key=lambda z: (
            int(z["time_from"]), int(z["base_from"]), z["kind"], z["side"]
        ),
    )

    print(f"\n=== {name} ===")
    print(f"  numpy (Python) : {len(py)}")
    print(f"  MQL5 (terminal): {len(mq)}")

    mismatches = 0
    if len(py) != len(mq):
        print(f"  COUNT MISMATCH: {len(py)} != {len(mq)}")
        mismatches += 1

    for zn, zr in zip(py, mq):
        problems = []
        if zn.kind.value != zr["kind"]:
            problems.append(f"kind {zn.kind.value} != {zr['kind']}")
        if zn.side.value != zr["side"]:
            problems.append(f"side {zn.side.value} != {zr['side']}")
        if _STATE[zr["state"]] is not zn.state:
            problems.append(f"state {zn.state.name} != {_STATE[zr['state']].name}")
        if zn.time_from != int(zr["time_from"]):
            problems.append(f"time_from {zn.time_from} != {zr['time_from']}")
        if zn.time_to != int(zr["time_to"]):
            problems.append(f"time_to {zn.time_to} != {zr['time_to']}")
        if zn.anatomy.base_from != int(zr["base_from"]):
            problems.append(
                f"base_from {zn.anatomy.base_from} != {zr['base_from']}"
            )
        for field in ("top", "bottom", "proximal", "distal"):
            a, b = getattr(zn, field), float(zr[field])
            # Harga broker sudah dibulatkan ke digit simbol sebelum sampai ke
            # kedua sisi, jadi toleransinya relatif dan ketat: yang dicari
            # selisih logika, bukan selisih representasi.
            if abs(a - b) > 1e-9 * max(1.0, abs(a)):
                problems.append(f"{field} {a} != {b}")
        # `departure_atr` DIBULATKAN ke 3 desimal di Python (`_finish` dan
        # `detect`), tidak di MQL5. Ambangnya diambil dari situ, bukan dari
        # kesamaan bit.
        if abs(zn.departure_atr - float(zr["departure_atr"])) > 0.0011:
            problems.append(
                f"departure_atr {zn.departure_atr} != {zr['departure_atr']}"
            )
        if problems:
            mismatches += 1
            if mismatches <= 10:
                print(f"  MISMATCH #{mismatches} {zn.kind.value}-{zn.time_from}:")
                for problem in problems:
                    print(f"    {problem}")
    if mismatches == 0:
        print("  OK")
    return mismatches



def compare_events(name: str, events_py, events_mq: list[dict]) -> int:
    """Komparator BENTUK KEDUA: satu bar, satu arah, satu level.

    Terpisah dari `compare` dan bukan generalisasi darinya, karena yang
    dibandingkan berbeda seluruhnya. Sebuah zona diperiksa pada empat harga dan
    sebuah state; sebuah event diperiksa pada bar mana ia terjadi, ke arah mana,
    dan level run mana yang ia tembus. Memaksa keduanya lewat satu fungsi berarti
    salah satunya diperiksa dengan pertanyaan yang bukan miliknya.
    """
    py = sorted(events_py, key=lambda e: (e.index, e.direction))
    mq = sorted(events_mq, key=lambda e: (int(e["index"]), int(e["direction"])))

    print(f"\n=== {name} ===")
    print(f"  Python  : {len(py)}")
    print(f"  MQL5    : {len(mq)}")

    mismatches = 0
    if len(py) != len(mq):
        print(f"  COUNT MISMATCH: {len(py)} != {len(mq)}")
        mismatches += 1

    for ep, em in zip(py, mq):
        problems = []
        for field in ("index", "direction", "run_start", "run_end", "run_length"):
            a, b = getattr(ep, field), int(em[field])
            if a != b:
                problems.append(f"{field} {a} != {b}")
        if ep.time != int(em["time"]):
            problems.append(f"time {ep.time} != {em['time']}")
        # Level sebuah CISD adalah OPEN sebuah bar apa adanya, tanpa aritmetika
        # dan tanpa pembulatan di kedua sisi, jadi toleransinya boleh seketat
        # representasi double-nya sendiri.
        if abs(ep.level - float(em["level"])) > 1e-9 * max(1.0, abs(ep.level)):
            problems.append(f"level {ep.level} != {em['level']}")
        if problems:
            mismatches += 1
            if mismatches <= 10:
                print(f"  MISMATCH #{mismatches} bar {ep.index}:")
                for problem in problems:
                    print(f"    {problem}")
    if mismatches == 0:
        print("  OK")
    return mismatches



def compare_breaks(name: str, breaks_py, breaks_mq: list[dict], scale: str) -> int:
    """Komparator untuk break dan sweep: event plus level plus sebuah NAMA.

    Bentuk ketiga, dan `kind` yang membuatnya bentuk sendiri. BOS, CHoCH dan
    SWEEP dibedakan oleh `bias` yang berjalan dan oleh close lawan wick, jadi
    dua sisi yang setuju soal bar dan level tapi berbeda soal nama sedang tidak
    setuju tentang hal yang paling penting di objek ini. Membandingkan tanpa
    `kind` akan meloloskan persis kesalahan itu.
    """
    rows = [r for r in breaks_mq if r["scale"] == scale]
    py = sorted(breaks_py, key=lambda b: (b.index, b.direction, b.kind))
    mq = sorted(rows, key=lambda r: (int(r["index"]), int(r["direction"]), r["kind"]))

    print(f"\n=== {name} ===")
    print(f"  Python  : {len(py)}")
    print(f"  MQL5    : {len(mq)}")

    mismatches = 0
    if len(py) != len(mq):
        print(f"  COUNT MISMATCH: {len(py)} != {len(mq)}")
        mismatches += 1

    for bp, bm in zip(py, mq):
        problems = []
        if bp.kind != bm["kind"]:
            problems.append(f"kind {bp.kind} != {bm['kind']}")
        for field in ("index", "direction", "swing_index", "bias_before"):
            a, b = getattr(bp, field), int(bm[field])
            if a != b:
                problems.append(f"{field} {a} != {b}")
        if bp.time != int(bm["time"]):
            problems.append(f"time {bp.time} != {bm['time']}")
        # Level sebuah break adalah harga swing apa adanya, tanpa aritmetika.
        if abs(bp.level - float(bm["level"])) > 1e-9 * max(1.0, abs(bp.level)):
            problems.append(f"level {bp.level} != {bm['level']}")
        if problems:
            mismatches += 1
            if mismatches <= 10:
                print(f"  MISMATCH #{mismatches} bar {bp.index} {bp.kind}:")
                for problem in problems:
                    print(f"    {problem}")
    if mismatches == 0:
        print("  OK")
    return mismatches



def compare_clock(path: Path) -> int:
    """Jam New York MQL5 lawan `zoneinfo`, dibandingkan sebagai EPOCH.

    Integer lawan integer, bukan tanggal terformat. Dua string tanggal bisa
    terlihat sama dan menunjuk dua instant berbeda; dua epoch tidak bisa.

    Ini bukan pengujian kenyamanan. Empat layer ICT yang tersisa - pools,
    liquidity, projections, gaps - menyatakan setiap batasnya dalam waktu lokal
    New York, jadi jam yang meleset satu jam menggeser SETIAP level di
    keempatnya tanpa satu pun pesan. Dan waktu server broker bukan
    penggantinya: Exness memakai tanggal transisi EU, yang berbeda dari US dua
    sampai tiga minggu tiap tahun.

    Probe-nya memuat kedua hari transisi tiap tahun beserta tetangganya, dan
    khususnya pukul 02:00 - waktu yang pada hari spring forward TIDAK ADA, dan
    tempat `app/pools.py` justru memulai sesi London.
    """
    from app.clock import ny_wall

    rows = read_zones(path)
    print("\n=== jam New York ===")
    print(f"  baris probe : {len(rows)}")

    mismatches = 0
    for row in rows:
        want = ny_wall(
            int(row["year"]), int(row["month"]), int(row["day"]),
            int(row["hour"]),
        )
        got = int(row["epoch"])
        if want != got:
            mismatches += 1
            if mismatches <= 10:
                delta = (got - want) / 3600
                print(
                    f"  MISMATCH #{mismatches} "
                    f"{row['year']}-{row['month']}-{row['day']} "
                    f"{row['hour']}:00 python {want} mql5 {got} "
                    f"selisih {delta:+.2f} jam"
                )
    if mismatches == 0:
        print("  OK")
    return mismatches


def compare_levels(name: str, pools_py, pools_mq: list[dict],
                   extra: tuple[str, ...] = ("covered",)) -> int:
    """Komparator BENTUK KEEMPAT: satu harga plus jendela waktu.

    `covered` dan `taken_at` ikut dibandingkan dan itu bukan kelengkapan.
    `covered` adalah flag yang mengatakan "high ini bukan high sesinya", dan
    `pools.py` mencatat bahwa flag itu pernah menyala di SETIAP pool sekaligus
    karena satu timestamp 899 detik membuat interval feed terbaca salah. Dua
    sisi yang setuju soal harga tapi berbeda soal covered sedang tidak setuju
    tentang apakah levelnya boleh dipercaya.

    `taken_at` forward-looking BY DESIGN: ia memindai maju sampai akhir deret.
    Ia aman hanya karena consumer membandingkannya dengan waktu keputusan
    (`liquidity.py:625`). Dibandingkan di sini supaya kedua sisi setuju soal
    nilainya, bukan supaya ada yang membacanya live.
    """
    py = sorted(pools_py, key=lambda p: (p.window_from, p.session, p.side))
    # `session` di CSV memuat nama periode untuk level, jadi satu bentuk
    # melayani keduanya dan tidak ada dua skema yang harus dijaga sinkron.
    mq = sorted(
        pools_mq, key=lambda r: (int(r["window_from"]), r["session"], r["side"])
    )

    print("\n=== " + name + " ===")
    print(f"  Python  : {len(py)}")
    print(f"  MQL5    : {len(mq)}")

    mismatches = 0
    if len(py) != len(mq):
        print(f"  COUNT MISMATCH: {len(py)} != {len(mq)}")
        mismatches += 1

    for pp, pm in zip(py, mq):
        problems = []
        if pp.session != pm["session"]:
            problems.append(f"session {pp.session} != {pm['session']}")
        if pp.side != pm["side"]:
            problems.append(f"side {pp.side} != {pm['side']}")
        for field in ("window_from", "window_to", "first_bar", "last_bar", "bars"):
            a, b = getattr(pp, field), int(pm[field])
            if a != b:
                problems.append(f"{field} {a} != {b}")
        for field in extra:
            want = getattr(pp, field)
            got = (pm[field] == "1") if isinstance(want, bool) else int(pm[field])
            if want != got:
                problems.append(f"{field} {want} != {got}")
        if pp.knowable_at != int(pm["knowable_at"]):
            problems.append(f"knowable_at {pp.knowable_at} != {pm['knowable_at']}")
        # 0 di sisi MQL5 berarti belum diambil, None di sisi Python.
        taken_mq = int(pm["taken_at"]) or None
        if pp.taken_at != taken_mq:
            problems.append(f"taken_at {pp.taken_at} != {taken_mq}")
        if abs(pp.price - float(pm["price"])) > 1e-9 * max(1.0, abs(pp.price)):
            problems.append(f"price {pp.price} != {pm['price']}")
        if problems:
            mismatches += 1
            if mismatches <= 10:
                print(f"  MISMATCH #{mismatches} {pp.session} {pp.side} {pp.window_from}:")
                for problem in problems:
                    print(f"    {problem}")
    if mismatches == 0:
        print("  OK")
    return mismatches


def compare_projections(name: str, rows_py, rows_mq: list[dict]) -> int:
    """Komparator BENTUK KELIMA: satu harga plus aritmetika yang membuatnya.

    `multiple`, `origin` dan `height` ikut dibandingkan, bukan hanya `price`.
    Harga saja tidak bisa membedakan dua sisi yang tiba di angka yang sama
    lewat jalan berbeda: origin di tepi yang salah DENGAN tanda yang juga
    salah menghasilkan harga yang benar untuk kelipatan simetris dan salah
    untuk sisanya, jadi memeriksa harga saja akan meloloskan separuhnya.

    Tiap baris Python adalah tuple, dibaca lewat indeks dan bukan di-unpack,
    supaya urutan field-nya terlihat di tempat ia dipakai.
    """
    py = sorted(rows_py, key=lambda r: (r[0], r[1], r[2], r[3]))
    mq = sorted(
        rows_mq,
        key=lambda r: (
            int(r["window_from"]), r["session"], int(r["direction"]),
            float(r["multiple"]),
        ),
    )

    print("\n=== " + name + " ===")
    print(f"  Python  : {len(py)}")
    print(f"  MQL5    : {len(mq)}")

    mismatches = 0
    if len(py) != len(mq):
        print(f"  COUNT MISMATCH: {len(py)} != {len(mq)}")
        mismatches += 1

    ints = (
        ("window_from", 0), ("window_to", 10), ("direction", 2),
        ("bars", 7), ("knowable_at", 8),
    )
    floats = (("multiple", 3), ("price", 4), ("origin", 5), ("height", 6))
    for rp, rm in zip(py, mq):
        problems = []
        if rp[1] != rm["session"]:
            problems.append(f"session {rp[1]} != {rm['session']}")
        for label, idx in ints:
            if rp[idx] != int(rm[label]):
                problems.append(f"{label} {rp[idx]} != {rm[label]}")
        taken = int(rm["taken_at"]) or None
        if rp[9] != taken:
            problems.append(f"taken_at {rp[9]} != {taken}")
        for label, idx in floats:
            want, got = rp[idx], float(rm[label])
            if abs(want - got) > 1e-9 * max(1.0, abs(want)):
                problems.append(f"{label} {want} != {got}")
        if problems:
            mismatches += 1
            if mismatches <= 10:
                print(f"  MISMATCH #{mismatches} {rp[1]} {rp[0]} "
                      f"dir {rp[2]} x{rp[3]}:")
                for problem in problems:
                    print(f"    {problem}")
    if mismatches == 0:
        print("  OK")
    return mismatches

def compare_gaps(name: str, gaps_py, gaps_mq: list[dict]) -> int:
    """Komparator BENTUK KEENAM: pita antara dua sesi, plus klaim ketepatan.

    `approximate` ikut dibandingkan dan itu field terpenting di baris ini. Ia
    yang membedakan "pita ini tepi-tepinya bar 17:00 dan bar 18:00 yang
    sesungguhnya" dari "pita ini bar terdekat yang bisa saya temukan", dan
    `gaps.py` mencatat kasus di mana pita KARANGAN terkirim berflag exact: 29
    pita di binance BTCUSDT 1h pada 19 Agustus 2026, semuanya lolos uji
    ketepatan karena 16:00 tambah satu jam memang 17:00. Dua sisi yang setuju
    soal harga tapi berbeda soal flag ini sedang tidak setuju tentang apakah
    pitanya boleh dipercaya sama sekali.
    """
    py = sorted(gaps_py, key=lambda g: (g.open_time, g.kind))
    mq = sorted(gaps_mq, key=lambda r: (int(r["open_time"]), r["kind"]))

    print("\n=== " + name + " ===")
    print(f"  Python  : {len(py)}")
    print(f"  MQL5    : {len(mq)}")

    mismatches = 0
    if len(py) != len(mq):
        print(f"  COUNT MISMATCH: {len(py)} != {len(mq)}")
        mismatches += 1

    for gp, gm in zip(py, mq):
        problems = []
        if gp.kind != gm["kind"]:
            problems.append(f"kind {gp.kind} != {gm['kind']}")
        for field in ("close_time", "open_time"):
            a, b = getattr(gp, field), int(gm[field])
            if a != b:
                problems.append(f"{field} {a} != {b}")
        if gp.approximate != (gm["approximate"] == "1"):
            problems.append(f"approximate {gp.approximate} != {gm['approximate']}")
        for field in ("top", "bottom"):
            want, got = getattr(gp, field), float(gm[field])
            if abs(want - got) > 1e-9 * max(1.0, abs(want)):
                problems.append(f"{field} {want} != {got}")
        if problems:
            mismatches += 1
            if mismatches <= 10:
                print(f"  MISMATCH #{mismatches} {gp.kind} {gp.open_time}:")
                for problem in problems:
                    print(f"    {problem}")
    if mismatches == 0:
        print("  OK")
    return mismatches


def compare_horizons(name: str, candles, gaps_py, rows_mq: list[dict],
                     keep: int, every: int) -> int:
    """Komparator BENTUK KETUJUH: level yang BERGERAK setelah lahir.

    Setiap harness lain di repo ini menanyakan "apakah nilainya sama", dan
    boleh, karena setiap objek lain beku begitu bar-bar yang membuatnya ada.
    Event horizon tidak. Ia rata-rata antara dua gap yang bertetangga MENURUT
    HARGA, jadi gap baru yang menyisip di antara dua gap lama memindahkan level
    yang sudah tergambar tanpa satu harga pun berubah - dan `keep` membuang gap
    tertua di saat yang sama, sehingga sebuah level bisa lenyap tanpa harganya
    pernah disentuh.

    Konsekuensinya untuk pengukuran: dua sisi bisa sepakat sempurna soal
    HIMPUNAN AKHIR level dan tetap berbeda pendapat di setiap bar sebelumnya.
    Membandingkan satu daftar akhir akan meloloskan itu tanpa suara, jadi yang
    dibandingkan di sini adalah level SEBAGAIMANA IA BERDIRI di tiap bar
    sampel, satu himpunan per `as_of`.

    Daftar sampelnya dibangun ulang dari bar, bukan dibaca dari kolom `as_of`
    milik MQL5. Membaca sampel dari sisi yang sedang diuji akan membuat dump
    yang berhenti menulis di tengah jalan terlihat sebagai kecocokan sempurna
    atas apa pun yang sempat tertulis.
    """
    from app.gaps import event_horizons

    at = [candles[i].time for i in range(0, len(candles), max(1, every))]
    py: dict[int, list] = {}
    for as_of in at:
        found = event_horizons(gaps_py, keep=keep, as_of=as_of)
        if found:
            py[as_of] = sorted(found, key=lambda h: h.price)

    mq: dict[int, list[dict]] = {}
    for row in rows_mq:
        mq.setdefault(int(row["as_of"]), []).append(row)
    for rows in mq.values():
        rows.sort(key=lambda r: float(r["price"]))

    n_py = sum(len(v) for v in py.values())
    print("\n=== " + name + " ===")
    print(f"  Python  : {n_py} level di {len(py)} bar sampel (tiap {every} bar)")
    print(f"  MQL5    : {len(rows_mq)} level di {len(mq)} bar sampel")

    mismatches = 0
    # Bar sampel yang hanya dipunyai salah satu sisi adalah bar di mana yang
    # satu menggambar sesuatu dan yang lain tidak menggambar apa-apa, yang
    # merupakan ketidaksepakatan terbesar yang mungkin dan bukan yang terkecil.
    only_py = sorted(set(py) - set(mq))
    only_mq = sorted(set(mq) - set(py))
    for label, missing in (("hanya Python", only_py), ("hanya MQL5", only_mq)):
        if missing:
            mismatches += len(missing)
            print(f"  {len(missing)} bar sampel {label}: {missing[:5]}")

    for as_of in sorted(set(py) & set(mq)):
        hp, hm = py[as_of], mq[as_of]
        if len(hp) != len(hm):
            mismatches += 1
            if mismatches <= 10:
                print(f"  MISMATCH #{mismatches} as_of {as_of}: "
                      f"{len(hp)} level != {len(hm)}")
            continue
        for a, b in zip(hp, hm):
            problems = []
            if abs(a.price - float(b["price"])) > 1e-9 * max(1.0, abs(a.price)):
                problems.append(f"price {a.price} != {b['price']}")
            # Kedua gap induk ikut dibandingkan, karena harga saja tidak bisa
            # membedakan level yang benar dari level yang kebetulan tiba di
            # angka yang sama dari pasangan gap yang berbeda - dan setelah
            # sebuah re-sort, pasangan mana itulah pertanyaan pertamanya.
            if a.lower.open_time != int(b["lower_open_time"]):
                problems.append(
                    f"lower {a.lower.open_time} != {b['lower_open_time']}"
                )
            if a.upper.open_time != int(b["upper_open_time"]):
                problems.append(
                    f"upper {a.upper.open_time} != {b['upper_open_time']}"
                )
            if problems:
                mismatches += 1
                if mismatches <= 10:
                    print(f"  MISMATCH #{mismatches} as_of {as_of}:")
                    for problem in problems:
                        print(f"    {problem}")
    if mismatches == 0:
        print("  OK")
    return mismatches


def dump(symbol: str, period: str) -> None:
    """Jalankan ZonelabParityDump di terminal untuk satu simbol dan timeframe.

    Menumpang `tools.mt5_backtest` untuk menutup terminal yang hidup, karena
    aturannya sama dan menulis ulang aturan itu di sini adalah cara kedua
    salinannya nanti berbeda pendapat tentang apakah terminal boleh dua.
    """
    from tools.mt5_backtest import DATA, REPO, TERMINAL, kill_terminal

    ini = REPO / "mql5" / "ZonelabSupplyDemand" / ".run_parity.ini"
    ini.write_text(
        "[Tester]\n"
        "Expert=ZonelabSupplyDemand\\ZonelabParityDump\n"
        f"Symbol={symbol}\nPeriod={period}\n"
        # Model 2, open prices. Tidak ada trade di dump ini, kerjanya selesai
        # di OnInit, jadi membayar real tick berarti membayar 66 juta tick
        # untuk sebuah penulisan file.
        "Model=2\nFromDate=2026.08.28\nToDate=2026.08.29\n"
        "ForwardMode=0\nDeposit=10000\nCurrency=USD\nLeverage=100\n"
        "Optimization=0\nShutdownTerminal=1\n",
        encoding="utf-8",
    )
    for stale in COMMON.glob("zonelab_parity_*.csv"):
        stale.unlink()
    kill_terminal()
    subprocess.run([str(TERMINAL), f"/config:{ini}"], check=False, timeout=600)
    deadline = time.time() + 600
    target = COMMON / "zonelab_parity_bars.csv"
    while time.time() < deadline and not target.exists():
        time.sleep(2)
    if not target.exists():
        raise SystemExit(f"dump {symbol} {period} tidak menghasilkan file di {DATA}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=str(COMMON))
    parser.add_argument(
        "--run", default="",
        help="SYMBOL:PERIOD, jalankan dump-nya dulu lewat terminal "
             "(contoh: XAUUSD:H1). Kosong berarti pakai dump yang sudah ada",
    )
    args = parser.parse_args()
    root = Path(args.dir)

    if args.run:
        symbol, _, period = args.run.partition(":")
        dump(symbol, period or "H1")

    bars_path = root / "zonelab_parity_bars.csv"
    if not bars_path.exists():
        raise SystemExit(
            f"tidak ada dump di {root}\n"
            "jalankan dulu ZonelabParityDump lewat "
            "mql5/ZonelabSupplyDemand/parity.ini, atau pakai --run SYMBOL:PERIOD"
        )

    candles = read_bars(bars_path)
    print(f"bar dari terminal: {len(candles)} "
          f"({candles[0].time} .. {candles[-1].time})")

    # Konfigurasi yang SAMA dengan yang dipasang dump EA. `max_zones_per_side=0`
    # dan `show_broken=True` mematikan filter tampilan, yang memang tidak ada di
    # sisi MQL5 - detektornya mengembalikan semuanya dan EA yang menyaring saat
    # trade. Membandingkan lewat cap akan mengukur cap-nya, bukan detektornya.
    sd_raw = SupplyDemandParams(
        merge_overlap_pct=1.0, max_zones_per_side=0,
        show_broken=True, show_mitigated=True,
    )
    sd_dedup = SupplyDemandParams(
        merge_overlap_pct=0.6, max_zones_per_side=0,
        show_broken=True, show_mitigated=True,
    )
    imb = ImbalanceParams(
        max_zones_per_side=0, show_broken=True, show_mitigated=True,
    )

    # SETIAP DETEKTOR DI REGISTRY HARUS PUNYA DUMP, dan yang tidak punya harus
    # menyebut dirinya. Daftar di bawah ini ditulis tangan, jadi sebuah detektor
    # keenam yang masuk `app/detect/__init__.py` akan diam-diam tidak pernah
    # dibandingkan dengan MQL5 - persis bentuk drift yang docstring registry itu
    # sendiri peringatkan, dan yang sudah memakan project ini dua kali di
    # `e2e/wiring.mjs` dan di sensus slider `e2e/sweep.mjs`.
    #
    # Ini BUKAN mengklaim detektor tanpa port itu salah. Ia menyatakan bahwa
    # presisinya BELUM DIUKUR, yang berbeda dari terukur dan lolos, dan
    # perbedaan itu tidak boleh hilang hanya karena tidak ada yang menuliskannya.
    from app.detect import DETECTORS

    dumped = PORTED
    unported = sorted(set(DETECTORS) - set(dumped))
    if unported:
        print(f"\nBELUM DIPORT ke MQL5, presisinya belum diukur: {unported}")
    absent = sorted(n for n, f in dumped.items() if not (root / f).exists())
    if absent:
        raise SystemExit(
            f"dump hilang untuk detektor yang punya port: {absent}. "
            "Jalankan ulang ZonelabParityDump."
        )

    total = 0
    total += compare("supply_demand (tanpa dedupe)",
                     detect(candles, sd_raw)[0],
                     read_zones(root / "zonelab_parity_sd.csv"))
    total += compare("supply_demand (dedupe 0,6, jalur yang dikirim)",
                     detect(candles, sd_dedup)[0],
                     read_zones(root / "zonelab_parity_sd_dedup.csv"))
    total += compare("order_block",
                     detect_order_block(candles, imb)[0],
                     read_zones(root / "zonelab_parity_ob.csv"))
    total += compare("fvg",
                     detect_fvg(candles, imb)[0],
                     read_zones(root / "zonelab_parity_fvg.csv"))
    total += compare("ifvg",
                     detect_ifvg(candles, imb)[0],
                     read_zones(root / "zonelab_parity_ifvg.csv"))
    total += compare("breaker",
                     detect_breaker(candles, imb)[0],
                     read_zones(root / "zonelab_parity_brk.csv"))

    # Bentuk kedua. `cisds` mengembalikan (events, runs); run-nya tidak
    # dibandingkan karena ia populasi TIDAK terfilter yang dipakai untuk
    # mengarmkan level, bukan objek yang digambar.
    from app.cisd import cisds
    from app.models import CISDParams

    cp = CISDParams()
    total += compare_events(
        "cisd",
        cisds(candles, cp.min_run, cp.interrupt_tolerance)[0],
        read_zones(root / "zonelab_parity_cisd.csv"),
    )

    # Bentuk ketiga. Dua skala dari satu file, karena `overlay` di Python
    # menjalankan keduanya berdampingan dan gerbang order block memakai skala
    # internal-nya sendiri lewat `ImbalanceParams.structure_n`.
    from app.detect.structure import breaks as structure_breaks
    from app.models import StructureParams

    sp = StructureParams()
    rows = read_zones(root / "zonelab_parity_structure.csv")
    for scale, width in (("swing", sp.swing_n), ("internal", sp.internal_n)):
        total += compare_breaks(
            f"structure ({scale}, n={width})",
            structure_breaks(candles, width, width)[0],
            rows,
            scale,
        )

    total += compare_clock(root / "zonelab_parity_clock.csv")

    from app.pools import liquidity_pools

    total += compare_levels(
        "pools (empat sesi)",
        liquidity_pools(candles, ("asia", "london", "ny_am", "london_close")),
        read_zones(root / "zonelab_parity_pools.csv"),
    )

    from app.liquidity import previous_period_levels

    # `PeriodLevel` menamai periodenya `period` dan levelnya `name`, jadi kedua
    # atribut itu dipetakan ke `session` dan `side` yang dipakai CSV bersama.
    class _AsLevel:
        __slots__ = (
            "session", "side", "price", "window_from", "window_to",
            "first_bar", "last_bar", "bars", "gap_at_open", "gap_at_close",
            "knowable_at", "taken_at",
        )

        def __init__(self, level):
            self.session = level.period
            self.side = level.name
            for field in self.__slots__[2:]:
                setattr(self, field, getattr(level, field))

    total += compare_levels(
        "liquidity (day, week, friday, monday; boundary cycle)",
        [
            _AsLevel(x)
            for x in previous_period_levels(
                candles, ("day", "week", "friday", "monday"), "cycle"
            )
        ],
        read_zones(root / "zonelab_parity_liquidity.csv"),
        extra=("gap_at_open", "gap_at_close"),
    )

    from app.pools import liquidity_pools as _pools
    from app.projections import LEVELS, projection

    # SETIAP session range, bukan hanya yang terbaru. UI Python menggambar
    # satu karena enam level kali dua arah kali dua sesi adalah 24 garis; yang
    # diuji di sini aritmetikanya di seluruh deret, bukan keputusan tampilan.
    paired: dict = {}
    for pool in _pools(candles, ("asia", "london", "ny_am", "london_close")):
        paired.setdefault((pool.session, pool.window_from), {})[pool.side] = pool
    flat = []
    for (session, _), sides in paired.items():
        hi, lo = sides.get("BSL"), sides.get("SSL")
        if hi is None or lo is None:
            continue
        for direction in (1, -1):
            found = projection(
                candles, hi.window_from, hi.window_to, hi.price, lo.price,
                direction, LEVELS,
            )
            if found is None:
                continue
            for level in found.levels:
                flat.append((
                    found.time_from, session, direction, level.multiple,
                    level.price, found.origin, found.height, found.bars,
                    found.knowable_at, level.taken_at, found.time_to,
                ))
    total += compare_projections(
        "projections (empat sesi, dua arah, enam level)",
        flat,
        read_zones(root / "zonelab_parity_projections.csv"),
    )

    from app.gaps import KEEP_DEFAULT, opening_gaps

    gaps_py = opening_gaps(candles)
    total += compare_gaps(
        "gaps (NDOG dan NWOG)",
        gaps_py,
        read_zones(root / "zonelab_parity_gaps.csv"),
    )
    total += compare_horizons(
        f"event horizons (keep={KEEP_DEFAULT}, per bar sampel)",
        candles,
        gaps_py,
        read_zones(root / "zonelab_parity_horizons.csv"),
        KEEP_DEFAULT,
        HORIZON_EVERY,
    )

    print(f"\nTOTAL MISMATCH: {total}")
    if unported:
        print(f"tidak diukur ({len(unported)} detektor tanpa port): {unported}")
    print("MQH PARITY OK" if total == 0 else "MQH PARITY FAIL")
    raise SystemExit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
