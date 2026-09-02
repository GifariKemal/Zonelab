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
PORTED_EVENTS = {
    "cisd": "zonelab_parity_cisd.csv",
}

#: Layer ICT yang SENGAJA belum diport, dengan alasannya masing-masing.
#: `tests/test_mql5_contract.py` menuntut ketiga dict ini bersama-sama menutup
#: setiap layer berkeluarga ICT di `app.layers.LAYERS`, jadi layer baru harus
#: mendarat di salah satunya. Yang dicegah bukan penambahan layer, melainkan
#: penambahan yang presisinya tidak pernah diukur tanpa ada yang menuliskan
#: bahwa ia tidak diukur - karena "belum diukur" dan "diukur dan lolos" tidak
#: boleh terlihat sama dari luar.
UNPORTED: dict[str, str] = {
    "structure": (
        "murni OHLC dan berikutnya dalam antrean. Ia juga menutup satu cacat "
        "di detektor yang SUDAH diport: OrderBlockDetector.mqh tidak punya "
        "satu baris kode swing pun, jadi require_structure_break tidak bisa "
        "diekspresikan di MQL5 dan order block yang parity-nya terbukti hanya "
        "jalur default-nya"
    ),
    "pools": (
        "butuh jam dinding New York yang sadar DST, yang tidak dipunyai MQL5 "
        "dan harus ditulis sendiri; infrastruktur bersama untuk liquidity, "
        "projections dan gaps"
    ),
    "liquidity": "menunggu jam New York dari pools; previous_period_levels dulu",
    "projections": "menunggu jam New York; sisanya satu baris aritmetika",
    "gaps": (
        "jam New York PLUS grid quarter PLUS window lebih panjang dari chart, "
        "dan level-levelnya TIDAK beku saat lahir - satu-satunya di survei ini "
        "yang melanggar asumsi birth-settled yang dipakai setiap harness di "
        "repo ini"
    ),
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

    print(f"\nTOTAL MISMATCH: {total}")
    if unported:
        print(f"tidak diukur ({len(unported)} detektor tanpa port): {unported}")
    print("MQH PARITY OK" if total == 0 else "MQH PARITY FAIL")
    raise SystemExit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
