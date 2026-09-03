"""Menjalankan matriks Strategy Tester, dengan input tercatat dan report tersimpan.

    python -m tools.mt5_backtest > ..\\docs\\mt5-backtest.json

KENAPA INI ADA. Sampai 1 September 2026 setiap angka backtest di
`mql5/ZonelabSupplyDemand/README.md` dihasilkan lewat GUI, dan tidak satu pun
input non-default tercatat di mana pun: `tester.ini` di HEAD tidak pernah
memuat satu baris input, tidak ada `.set` file, dan `git ls-files` untuk
`*.htm|*.xml|*.csv|*.set` mengembalikan nol. Ditambah `ReplaceReport=1` dengan
nama report tetap, setiap run baru menghapus bukti run sebelumnya. Tiga report
yang tersisa di mesin ini semuanya run TERAKHIR tiap EA, bukan run yang
menghasilkan angka headline.

Akibatnya bisa diperiksa: dari 20-an klaim angka di README itu, hanya tiga yang
punya artifact, dan ketiganya kebetulan run yang RUGI. Setiap klaim yang
menyuruh jalan - XAU H1 PF 1,71, walk-forward 1,98 - tidak punya satu byte pun.

Tool ini menutupnya dengan tiga hal:
  1. setiap sel menulis `.set`-nya sendiri, jadi input yang dipakai adalah
     input yang tersimpan dan bukan input yang diingat;
  2. nama report unik per sel, jadi tidak ada run yang menimpa run lain;
  3. report `.htm`-nya disalin ke `mql5/ZonelabSupplyDemand/reports/` supaya
     ikut masuk git, dan angkanya diringkas ke stdout sebagai json.

TERMINAL HANYA SATU KLIEN. MT5 satu instance per data folder, jadi sebuah
`terminal64.exe /config:` yang dijalankan saat terminal lain sudah hidup akan
keluar diam-diam tanpa menjalankan apa pun - persis yang terjadi 1 September
2026, ketika `history.load("mt5:...")` dari Python menyalakan terminal lebih
dulu dan launch tester berikutnya langsung exit 0 tanpa satu file pun ditulis.
Tool ini menutup terminal yang hidup sebelum tiap sel, dan MENOLAK jalan kalau
daemon auto-trade menyala.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TERMINAL = Path(r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe")
# `.get` dan bukan `[...]`: file ini diimpor oleh tests/test_mql5_contract.py
# untuk membaca SHIPPED, dan sebuah KeyError di baris module-level akan
# menggagalkan PENGUMPULAN seluruh suite alih-alih satu test.
DATA = Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal" / (
    "53785E099C927DB68A545C249CDBCE06"
)
SETS = DATA / "MQL5" / "Profiles" / "Tester"
REPORTS = REPO / "mql5" / "ZonelabSupplyDemand" / "reports"

#: Default yang DIKIRIM, disalin dari file .mq5 masing-masing. Ditulis di sini
#: supaya sebuah sel bisa menyimpang dari default dengan menyebut satu key, dan
#: supaya `.set` yang dihasilkan lengkap: MT5 memakai compiled default untuk
#: input yang tidak disebut, yang berarti sebuah `.set` parsial menyimpan lebih
#: sedikit dari yang dijalankan.
SHIPPED = {
    "ZonelabSD": {
        "InpAtrPeriod": 14, "InpImpulseBodyRatio": 0.5, "InpImpulseAtr": 1.0,
        "InpBaseMaxBars": 6, "InpBaseMaxAtr": 2.5, "InpDepartureMinAtr": 2.0,
        "InpDepartureLook": 20, "InpProximalBasis": 0,
        "InpMinProfitMargin": 0.0, "InpZoneMinAtr": 0.05,
        "InpMaxBaseDrift": 0.6, "InpMitigationPct": 0.5,
        "InpMergeOverlapPct": 0.6, "InpStopBufferAtr": 0.25,
        "InpStopAtrMode": 0,
        "InpRiskPercent": 1.0, "InpBars": 20000, "InpMagic": 20260831,
    },
    "ZonelabOB": {
        "InpAtrPeriod": 14, "InpDisplacementAtr": 1.5,
        "InpDisplacementBars": 5, "InpMitigationPct": 0.5,
        "InpStopBufferAtr": 0.25, "InpStopAtrMode": 0,
        "InpTargetMode": 0, "InpRewardR": 2.0,
        "InpRiskPercent": 1.0, "InpBars": 3000, "InpMagic": 20260901,
    },
    "ZonelabFVG": {
        "InpAtrPeriod": 14, "InpMinGapAtr": 0.1, "InpMitigationPct": 0.5,
        "InpStopBufferAtr": 0.25, "InpStopAtrMode": 0,
        "InpTargetMode": 0, "InpRewardR": 2.0,
        "InpTargetAtr": 2.0, "InpRiskPercent": 1.0, "InpBars": 3000,
        "InpMagic": 20260901,
    },
    # Jalur trade-nya salinan persis ZonelabFVG, jadi default-nya juga harus
    # sama persis. Satu-satunya yang berbeda adalah magic, supaya order kedua
    # EA ini tidak saling mengaku milik ketika keduanya pernah jalan di
    # terminal yang sama.
    # Jalur trade-nya salinan ZonelabIFVG; yang berbeda cuma detektor induknya,
    # jadi parameternya ikut induk itu (impulse, bukan gap).
    "ZonelabBRK": {
        "InpAtrPeriod": 14, "InpDisplacementAtr": 1.5,
        "InpDisplacementBars": 5, "InpMitigationPct": 0.5,
        "InpStopBufferAtr": 0.25, "InpStopAtrMode": 0,
        "InpTargetMode": 0, "InpRewardR": 2.0, "InpTargetAtr": 2.0,
        "InpRiskPercent": 1.0, "InpBars": 3000, "InpMagic": 20260903,
    },
    "ZonelabIFVG": {
        "InpAtrPeriod": 14, "InpMinGapAtr": 0.1, "InpMitigationPct": 0.5,
        "InpStopBufferAtr": 0.25, "InpStopAtrMode": 0,
        "InpTargetMode": 0, "InpRewardR": 2.0,
        "InpTargetAtr": 2.0, "InpRiskPercent": 1.0, "InpBars": 3000,
        "InpMagic": 20260902,
    },
}

#: Lima detektor lawan dua instrumen lawan lima timeframe, semuanya di config
#: yang DIKIRIM. Bukan sapuan parameter - sapuan mencari angka terbaik, ini
#: memeriksa apakah angka yang sudah diterbitkan bisa diproduksi ulang, dan
#: apakah kesimpulan "H1 sweet spot" bertahan di dua instrumen.
#:
#: Urut dari yang paling murah. Timeframe besar selesai lebih dulu, jadi kalau
#: matriksnya dipotong di tengah yang hilang adalah sel yang paling lama, bukan
#: sel yang acak.
EXPERTS = ("ZonelabSD", "ZonelabOB", "ZonelabFVG", "ZonelabIFVG", "ZonelabBRK")
SYMBOLS = ("XAUUSD", "BTCUSD")
PERIODS = ("H4", "H1", "M30", "M15", "M5")


def matrix(periods, symbols, experts):
    return [
        {"expert": e, "symbol": s, "period": p}
        for p in periods for s in symbols for e in experts
    ]

#: Angka yang diambil dari report. Kuncinya persis label MT5 sendiri supaya
#: tidak ada penerjemahan yang bisa salah diam-diam.
FIELDS = (
    "Total Net Profit", "Profit Factor", "Total Trades", "Expected Payoff",
    "Balance Drawdown Maximal", "Sharpe Ratio", "Recovery Factor",
    "History Quality", "Bars", "Ticks", "Initial Deposit",
    "Profit Trades (% of total)", "Loss Trades (% of total)",
)


def kill_terminal() -> None:
    subprocess.run(
        ["taskkill", "/F", "/IM", "terminal64.exe"],
        capture_output=True, check=False,
    )
    for _ in range(20):
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq terminal64.exe"],
            capture_output=True, text=True, check=False,
        ).stdout
        if "terminal64.exe" not in out:
            return
        time.sleep(0.5)
    raise SystemExit("terminal64.exe menolak ditutup")


#: Tool yang mengemudikan terminal. Dua di antaranya jalan bersamaan berarti
#: satu merebut terminal dari yang lain, dan yang direbut menunggu report yang
#: tidak akan pernah ditulis sampai timeout-nya habis.
MT5_DRIVERS = ("tools.mt5_backtest", "tools.mqh_parity")


def guard_single_client() -> None:
    """Menolak jalan kalau tool lain sedang mengemudikan terminal.

    KENAPA INI ADA, dan tanggalnya 1 September 2026. Sebuah script rantai
    memakai `pgrep -f "tools.mt5_backtest"` untuk memutuskan apakah matriks
    masih jalan. Di Git Bash `pgrep -f` TIDAK melihat command line proses
    Windows, jadi ia menjawab "tidak ada" untuk driver yang jelas-jelas hidup,
    rantainya jalan lebih awal, dan `kill_terminal()` merebut terminal di
    tengah sel yang butuh 25 menit. Sel itu hilang dan drivernya menggantung
    sampai timeout 3600 detik.

    `docs/QA-PRODUKSI.md` sudah mencatat aturannya dengan kalimat lain:
    kecualikan shell sebelum mempercayai hitungan proses. Filter command line
    akan match ke proses yang sedang memfilter, dan di venv ini setiap proses
    muncul DUA kali, shim plus anaknya, jadi yang dikecualikan adalah PID
    sendiri DAN induknya.
    """
    out = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'",
         "get", "ProcessId,CommandLine", "/format:list"],
        capture_output=True, text=True, check=False,
    ).stdout
    mine = {str(os.getpid()), str(os.getppid())}
    command, others = "", []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("CommandLine="):
            command = line
        elif line.startswith("ProcessId="):
            pid = line.split("=", 1)[1]
            if pid not in mine and any(d in command for d in MT5_DRIVERS):
                others.append(f"{pid}: {command[12:][-90:]}")
    if others:
        raise SystemExit(
            "BLOCKER: tool lain sedang memakai terminal MT5, dan terminal ini "
            "satu klien.\n  " + "\n  ".join(others)
        )


def guard_daemon() -> None:
    """Menolak jalan kalau saklar auto-trade menyala.

    `docs/ALUR-ORDER.md` dan `run_backtest.bat` sama-sama memperingatkan ini,
    dan sebuah peringatan di prosa adalah peringatan yang bisa dilewati. Tester
    memakai terminal yang sama dengan daemon live.
    """
    switch = REPO / "backend" / ".autotrade.json"
    if switch.exists():
        try:
            if json.loads(switch.read_text(encoding="utf-8")).get("enabled"):
                raise SystemExit(
                    "BLOCKER: .autotrade.json enabled - matikan daemon dulu"
                )
        except json.JSONDecodeError:
            pass


def write_set(expert: str, overrides: dict) -> str:
    inputs = dict(SHIPPED[expert])
    inputs.update(overrides)
    name = f"zonelab_{expert}.set"
    SETS.mkdir(parents=True, exist_ok=True)
    (SETS / name).write_text(
        "".join(f"{k}={v}\n" for k, v in inputs.items()), encoding="utf-8"
    )
    return name


def parse_report(path: Path) -> dict:
    text = path.read_bytes().decode("utf-16", "ignore")
    text = html.unescape(re.sub(r"<[^>]+>", "|", text))
    # Tag-tag MT5 dipisah newline, jadi meruntuhkan pipa saja menyisakan
    # baris kosong di antara label dan angkanya, dan setiap field terbaca
    # kosong. Runtuhkan spasi di antara pipa juga, sekalian.
    text = re.sub(r"\s*\|[\s|]*", "|", text)
    out: dict[str, str] = {}
    for field in FIELDS:
        # SEMUA kemunculan, bukan yang pertama. Dengan ForwardMode menyala MT5
        # menulis dua blok statistik ke satu file, dan mengambil match pertama
        # akan melaporkan angka in-sample dengan nama out-of-sample - persis
        # cara sebuah split-half bisa terlihat lolos tanpa pernah diuji.
        hits = re.findall(re.escape(field) + r":\|([^|]{0,60})", text)
        if hits:
            out[field] = hits[0].strip()
        if len(hits) > 1:
            out[f"forward {field}"] = hits[1].strip()
    match = re.search(r"Inputs:\|((?:[A-Za-z]\w*=[^|]*\|)+)", text)
    out["inputs_in_report"] = match.group(1).strip("|") if match else ""
    match = re.search(r"Symbol:\|([^|]+)", text)
    out["symbol_in_report"] = match.group(1).strip() if match else ""
    return out


#: Counter yang tiap EA cetak di `OnDeinit`, dan yang sampai 2 September 2026
#: tidak pernah dibaca siapa pun.
#:
#: Ia hilang di dua lapis sekaligus. `Print` tidak masuk ke report `.htm`, jadi
#: 260 file di `reports/` tidak memuat satu pun darinya; dan log agent tester
#: ditulis UTF-16LE di pohon `MetaQuotes\Tester\<id>\Agent-*\logs\`, terpisah
#: dari data folder terminal, jadi ia tidak ikut ke mana-mana.
#:
#: Angkanya yang menjawab pertanyaan yang report tidak bisa jawab: berapa zona
#: yang dilihat EA, berapa yang dilewati karena tidak punya target, dan berapa
#: yang dilewati karena harga sudah lewat. Tanpa itu, selisih jumlah trade
#: antara rig Python dan Strategy Tester - 953 lawan 622 untuk fvg XAUUSD M30 -
#: cuma bisa ditebak.
COUNTERS = ("zones fresh", "orders placed", "orders failed",
            "skipped price", "skipped no-target")
AGENT_LOGS = Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Tester"


def _agent_log_sizes() -> dict[Path, int]:
    """Ukuran tiap log agent sekarang, untuk mengambil DELTA-nya nanti."""
    out: dict[Path, int] = {}
    if not AGENT_LOGS.exists():
        return out
    for path in AGENT_LOGS.glob("*/Agent-*/logs/*.log"):
        try:
            out[path] = path.stat().st_size
        except OSError:
            continue
    return out


def read_counters(before: dict[Path, int]) -> dict:
    """Counter EA dari BAGIAN log yang tumbuh selama sel ini berjalan.

    Delta, bukan seluruh file: log hari ini memuat setiap sel yang sudah jalan
    hari itu, dan membaca semuanya akan melaporkan counter sel lain sebagai
    milik sel ini. Log-nya juga 62 MB, jadi membacanya utuh per sel mahal tanpa
    alasan.

    UTF-16LE dengan fallback UTF-8: MT5 menulis yang pertama, dan sebuah
    `decode` yang salah tebak mengembalikan string kosong tanpa error, yang akan
    terbaca sebagai "EA tidak mencetak apa pun".
    """
    found: dict = {}
    for path in _agent_log_sizes():
        start = before.get(path, 0)
        try:
            with path.open("rb") as fh:
                fh.seek(start)
                raw = fh.read()
        except OSError:
            continue
        if not raw:
            continue
        text = raw.decode("utf-16-le", errors="ignore")
        if not any(name in text for name in COUNTERS):
            text = raw.decode("utf-8", errors="ignore")
        for name in COUNTERS:
            hits = re.findall(rf"{re.escape(name)}: (\d+)", text)
            if hits:
                # Yang TERAKHIR, karena `OnDeinit` mencetak sekali di akhir dan
                # sebuah log yang memuat dua run memuat dua nilai.
                found[name.replace(" ", "_").replace("-", "_")] = int(hits[-1])
    return found


def run_cell(cell: dict, args) -> dict:
    expert = cell["expert"]
    tag = f"{expert}_{cell['symbol']}_{cell['period']}{args.tag_suffix}"
    overrides = dict(cell.get("inputs", {}))
    overrides.update(args.overrides)
    # Sebuah key yang tidak dikenal EA-nya akan ditulis ke .set dan DIABAIKAN
    # MT5 tanpa pesan, jadi run-nya hijau dengan input yang tidak berlaku.
    # Ditolak di sini supaya salah ketik jadi error, bukan jadi hasil.
    unknown = sorted(set(overrides) - set(SHIPPED[expert]))
    if unknown:
        raise SystemExit(f"{expert} tidak punya input {unknown}")
    set_name = write_set(expert, overrides)
    ini = REPO / "mql5" / "ZonelabSupplyDemand" / f".run_{tag}.ini"
    ini.write_text(
        "[Tester]\n"
        f"Expert=ZonelabSupplyDemand\\{expert}\n"
        f"ExpertParameters={set_name}\n"
        f"Symbol={cell['symbol']}\n"
        f"Period={cell['period']}\n"
        f"Model={args.model}\n"
        f"FromDate={args.from_date}\n"
        f"ToDate={args.to_date}\n"
        # ForwardMode 1 memotong rentang jadi dua dan melaporkan paruh kedua
        # TERPISAH. Itu out-of-sample yang dikerjakan tester sendiri, dan
        # `mql5/ZonelabSupplyDemand/README.md` mengklaim split-half PF 1,99 dan
        # 1,98 sambil menyetel `ForwardMode=0` di setiap revisi `tester.ini`
        # yang pernah ada - jadi split itu dikerjakan tangan dan tanggalnya
        # tidak tersimpan di mana pun.
        f"ForwardMode={args.forward}\n"
        f"Deposit={args.deposit}\n"
        "Currency=USD\nLeverage=100\nOptimization=0\n"
        f"Report={tag}\nReplaceReport=1\nShutdownTerminal=1\n",
        encoding="utf-8",
    )

    report = DATA / f"{tag}.htm"
    if report.exists():
        report.unlink()

    kill_terminal()
    before_logs = _agent_log_sizes()
    started = time.time()
    subprocess.run(
        [str(TERMINAL), f"/config:{ini}"],
        capture_output=True, check=False, timeout=args.timeout,
    )
    # `terminal64.exe` melepas diri, jadi exit code-nya tidak mengatakan apa pun
    # tentang tester. Yang mengatakan sesuatu adalah munculnya file report.
    deadline = time.time() + args.timeout
    while time.time() < deadline and not report.exists():
        time.sleep(2)

    elapsed = round(time.time() - started, 1)
    if not report.exists():
        return {"cell": tag, "status": "NO REPORT", "seconds": elapsed}

    REPORTS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(report, REPORTS / f"{tag}.htm")
    shutil.copy2(SETS / set_name, REPORTS / f"{tag}.set")
    return {
        "cell": tag, "status": "ok", "seconds": elapsed,
        "report": f"mql5/ZonelabSupplyDemand/reports/{tag}.htm",
        **parse_report(report),
        "ea_counters": read_counters(before_logs),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="4", help="4 = real ticks")
    parser.add_argument("--from-date", default="2026.01.01")
    parser.add_argument("--to-date", default="2026.08.31")
    parser.add_argument("--deposit", default="10000")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--only", default="", help="substring filter on the tag")
    parser.add_argument(
        "--forward", default="0",
        help="0 mati, 1 potong separuh, 2 sepertiga, 3 seperempat. "
             "Paruh terakhir dilaporkan terpisah sebagai out-of-sample",
    )
    parser.add_argument(
        "--tag-suffix", default="",
        help="ditempel ke nama sel, supaya run forward tidak menimpa run penuh",
    )
    parser.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE",
        help="override satu input EA di SEMUA sel, boleh diulang. Key yang "
             "tidak dikenal EA-nya ditolak di sini dan bukan diam-diam "
             "diabaikan oleh MT5",
    )
    parser.add_argument("--periods", default=",".join(PERIODS))
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--experts", default=",".join(EXPERTS))
    parser.add_argument(
        "--out", default="",
        help="tulis json parsial ke file ini setiap sel selesai, supaya "
             "matriks yang dipotong di tengah tetap meninggalkan hasil",
    )
    args = parser.parse_args()

    args.overrides = {}
    for pair in args.set:
        key, _, value = pair.partition("=")
        args.overrides[key.strip()] = value.strip()

    guard_daemon()
    guard_single_client()
    if not TERMINAL.exists():
        raise SystemExit(f"terminal tidak ada di {TERMINAL}")

    cells = matrix(
        args.periods.split(","), args.symbols.split(","), args.experts.split(",")
    )
    rows = []
    for cell in cells:
        tag = f"{cell['expert']}_{cell['symbol']}_{cell['period']}{args.tag_suffix}"
        if args.only and args.only not in tag:
            continue
        print(f"running {tag} ...", file=sys.stderr, flush=True)
        row = run_cell(cell, args)
        rows.append(row)
        print(
            f"  {row['status']:9s} {row.get('Profit Factor', '-'):>6s} PF  "
            f"{row.get('Total Net Profit', '-'):>12s} net  "
            f"{row.get('Total Trades', '-'):>5s} trades  {row['seconds']}s",
            file=sys.stderr, flush=True,
        )
        if args.out:
            Path(args.out).write_text(json.dumps({
                "model": args.model, "from": args.from_date,
                "to": args.to_date, "deposit": args.deposit, "cells": rows,
            }, indent=2), encoding="utf-8")

    print(json.dumps({
        "model": args.model, "from": args.from_date, "to": args.to_date,
        "deposit": args.deposit, "cells": rows,
    }, indent=2))
    if any(r["status"] != "ok" for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
