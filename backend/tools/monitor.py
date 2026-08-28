"""Satu tarikan napas: apa yang berubah sejak pemeriksaan terakhir, dan apa yang mati.

    python -m tools.monitor            # delta sejak watermark, lalu majukan watermark
    python -m tools.monitor --all      # semua event tercatat, watermark tidak digeser

DUA FAKTA YANG TIDAK BOLEH DIGABUNG. Saklar auto-trade `enabled` dan daemon
`daemon_alive` adalah dua hal berbeda, dan seluruh `app/autotrade.py` ada karena
itu. Monitor ini mewarisi aturan yang sama: ARMED TANPA DAEMON dilaporkan
sebagai kondisi yang perlu dilihat, bukan sebagai "auto-trade menyala".

KENAPA DELTA, BUKAN RINGKASAN PENUH. Sebuah cron yang mencetak keadaan lengkap
tiap sepuluh menit menghasilkan log yang tidak dibaca siapa pun, dan order yang
terkirim jam 03:14 tenggelam di antara empat puluh laporan "tidak ada apa-apa".
Watermark di `.monitor.json` membuat tiap event dilaporkan tepat sekali.

EXIT CODE ADALAH GERBANGNYA, karena itu yang dibaca cron:
  0  sehat, dan tidak ada yang baru
  1  ada yang perlu dilihat: order/fill/penutupan baru, atau sesuatu mati

Yang TIDAK dilakukan file ini: menempatkan order, membatalkan order, menyentuh
saklar. Ia read-only terhadap trading, persis seperti `app/`.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app import autotrade, journal

WATERMARK = Path(__file__).resolve().parent.parent / ".monitor.json"
#: Log daemon. Journal mencatat KEPUTUSAN yang menghasilkan order atau penolakan;
#: di dry run tidak ada satu pun dari keduanya, jadi tanpa file ini "setiap
#: analisa yang terjadi" tidak termonitor sama sekali dan monitor akan melaporkan
#: nol event pada daemon yang sedang bekerja penuh.
DAEMON_LOG = Path(__file__).resolve().parent.parent / ".autotrade.log"
API = "http://127.0.0.1:8100"
WEB = "http://127.0.0.1:3100"

#: Event yang selalu berarti "lihat ini". `refused` sengaja TIDAK di sini: ia
#: normal, satu cycle bisa menghasilkan belasan, dan menaikkannya jadi alarm
#: membuat alarm berhenti berarti apa-apa.
LOUD = ("placed", "filled", "closed", "cancelled", "armed", "disarmed")


def _probe(url: str, timeout: float = 8.0) -> tuple[bool, str]:
    """Hidup atau tidak, plus alasannya. Tidak pernah melempar."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200, f"HTTP {response.status}"
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return False, str(exc)


def _account() -> dict[str, Any]:
    """Equity, posisi, dan pending dari terminal. READ ONLY.

    Tidak memakai `execute._terminal`: itu menolak akun non-demo, yang benar
    untuk pengirim order dan salah untuk pembaca. Monitor harus tetap bisa
    melaporkan akun yang justru tidak boleh ditradingkan.
    """
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return {"reachable": False, "why": "MetaTrader5 tidak terpasang"}
    if not mt5.initialize():
        return {"reachable": False,
                "why": f"terminal tidak terjangkau: {mt5.last_error()}"}
    account = mt5.account_info()
    if account is None:
        return {"reachable": False, "why": f"tidak ada akun: {mt5.last_error()}"}
    positions = mt5.positions_get() or []
    orders = mt5.orders_get() or []
    return {
        "reachable": True,
        "login": account.login,
        "server": account.server,
        "trade_mode": account.trade_mode,
        "equity": account.equity,
        "balance": account.balance,
        "positions": [(p.ticket, p.symbol, p.volume, p.profit) for p in positions],
        "orders": [(o.ticket, o.symbol, o.volume_current, o.price_open)
                   for o in orders],
    }


def _seen() -> tuple[int, int]:
    """Watermark terakhir: (detik, offset log). Rusak atau hilang berarti (0, 0).

    Bukan exception, karena file ini ditulis tiap sepuluh menit oleh sebuah cron
    dan sebuah cron yang mati gara-gara satu byte rusak adalah monitoring yang
    berhenti tepat saat ia dibutuhkan.
    """
    if not WATERMARK.exists():
        return 0, 0
    try:
        raw = json.loads(WATERMARK.read_text(encoding="utf-8"))
        return int(raw.get("seen_at") or 0), int(raw.get("log_offset") or 0)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return 0, 0


def _cycles(offset: int) -> tuple[list[str], list[str], int, int]:
    """Baris baru dari log daemon: alarm, catatan, jumlah cycle, offset berikutnya.

    ALARM DAN CATATAN DIPISAH, dan pemisahan itu adalah perbaikan sebuah cacat
    nyata. Versi pertama mencetak baris BLOCKER lalu tidak memasukkannya ke
    `attention`, jadi monitor menjawab `exit 0, tidak ada yang perlu dilihat`
    selama 14 cycle berturut ketika engine menolak bertindak atas feed yang
    dianggapnya basi. Sebuah monitor yang mencetak sebuah masalah tapi
    mengembalikan exit code sehat lebih buruk daripada monitor yang diam, karena
    ia mengajari pembacanya bahwa exit code-nya bisa dipercaya.

    SATU BARIS RINGKAS PER CYCLE, dan itu yang dihitung. Mencetak semua baris
    akan mengirim ratusan baris kandidat tiap sepuluh menit, yang adalah cara
    tercepat membuat sebuah alarm berhenti dibaca.

    File yang MENGECIL berarti daemon di-restart dan log-nya ditulis ulang dari
    nol. Offset lama akan melewati awal file yang baru, jadi ia direset - kalau
    tidak, sebuah restart membuat monitor diam-diam buta sampai log tumbuh
    melewati panjang yang lama.
    """
    if not DAEMON_LOG.exists():
        return [], [], 0, 0
    size = DAEMON_LOG.stat().st_size
    if size < offset:
        offset = 0
    with DAEMON_LOG.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(offset)
        fresh = handle.read()
    lines = fresh.splitlines()
    # CYCLE YANG BERAKHIR DI BLOCKER TETAP SEBUAH CYCLE. Daemon mencetak
    # `tidak ada kandidat` alih-alih `ringkas:` ketika tidak ada yang lolos,
    # jadi menghitung `ringkas:` saja membuat satu jam jeda harian broker
    # terbaca sebagai daemon yang berhenti bekerja.
    cycles = [x.strip() for x in lines
              if x.lstrip().startswith("ringkas:")
              or x.strip() == "tidak ada kandidat"]
    summaries = [x for x in cycles if x.startswith("ringkas:")]
    # ALARM: engine menolak bertindak, atau sebuah pengiriman gagal. Keduanya
    # harus menaikkan exit code. Di-dedup karena satu penyebab yang bertahan
    # menghasilkan satu baris per cycle, dan tiga puluh salinan kalimat yang sama
    # bukan tiga puluh informasi.
    alarms: list[str] = []
    shapes: set[str] = set()
    for line in lines:
        if "BLOCKER" not in line and "GAGAL" not in line:
            continue
        text = line.strip()
        # DEDUP PADA BENTUK KALIMAT, BUKAN PADA TEKS PERSIS. Satu penyebab yang
        # bertahan mencetak `feed is 3809s behind`, lalu `3830s`, lalu `3850s`:
        # tiga puluh baris yang angkanya bergerak dan artinya satu. Angkanya
        # dibuang untuk kunci dedup saja; baris pertama tetap dilaporkan utuh
        # supaya besarannya tidak hilang.
        shape = "".join("#" if ch.isdigit() else ch for ch in text)
        if shape not in shapes:
            shapes.add(shape)
            alarms.append(text)
    notes = [x.strip() for x in lines
             if "DITUTUP" in x or x.lstrip().startswith("saklar:")]
    if summaries:
        notes.append(f"terakhir: {summaries[-1]}")
    return alarms, notes, len(cycles), offset + len(fresh.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true",
                        help="semua event tercatat, dan JANGAN geser watermark")
    args = parser.parse_args()

    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    seen_at, offset = _seen()
    since = 0 if args.all else seen_at
    if args.all:
        offset = 0
    attention: list[str] = []

    print(f"== zonelab monitor {stamp}")

    api_up, api_why = _probe(f"{API}/api/health")
    web_up, web_why = _probe(WEB)
    print(f"  api  {'UP' if api_up else 'DOWN'}  {api_why}")
    print(f"  web  {'UP' if web_up else 'DOWN'}  {web_why}")
    if not api_up:
        attention.append(f"API mati: {api_why}")
    if not web_up:
        attention.append(f"web mati: {web_why}")

    switch = autotrade.read()
    age = switch["heartbeat_age_seconds"]
    beat = f" (heartbeat {age}s lalu)" if age is not None else " (tak pernah)"
    print(f"  saklar {'MENYALA' if switch['enabled'] else 'MATI'}  "
          f"daemon {'hidup' if switch['daemon_alive'] else 'mati'}{beat}  "
          f"{switch['symbol']} {switch['interval']} risk {switch['risk_pct']}")
    # ARMED TANPA DAEMON. Ini kondisi yang paling mungkin salah dibaca seorang
    # operator, jadi ia disebut dengan kalimat penuh, bukan lewat sebuah flag.
    if switch["enabled"] and not switch["daemon_alive"]:
        attention.append("saklar MENYALA tapi daemon tidak berdetak: tidak ada "
                         "yang trading, dan UI bisa terbaca seolah ada")

    account = _account()
    if not account["reachable"]:
        print(f"  akun tidak terbaca: {account['why']}")
        if switch["enabled"]:
            attention.append(
                f"akun tidak terbaca saat saklar menyala: {account['why']}")
    else:
        print(f"  akun {account['login']} {account['server']} "
              f"trade_mode={account['trade_mode']} (0=DEMO) "
              f"equity {account['equity']} balance {account['balance']}")
        for ticket, symbol, volume, profit in account["positions"]:
            print(f"    posisi {ticket} {symbol} {volume} lot  pnl {profit}")
        for ticket, symbol, volume, price in account["orders"]:
            print(f"    pending {ticket} {symbol} {volume} lot @ {price}")
        if account["trade_mode"] != 0 and switch["enabled"]:
            attention.append(f"akun {account['login']} BUKAN demo "
                             f"(trade_mode={account['trade_mode']}) "
                             f"dan saklar menyala")

    alarms, notes, cycles, offset = _cycles(offset)
    print(f"  analisa: {cycles} cycle daemon sejak cek terakhir")
    for line in notes:
        print(f"    {line}")
    for line in alarms:
        print(f"    {line}")
    # ENGINE MENOLAK BERTINDAK ADALAH SESUATU YANG PERLU DILIHAT. Mencetaknya
    # lalu mengembalikan exit 0 adalah bagaimana sebuah monitor mengajari
    # pembacanya untuk berhenti mempercayai exit code-nya.
    attention.extend(alarms)
    # DAEMON HIDUP TAPI NOL CYCLE adalah kondisi tersendiri, dan ia tidak sama
    # dengan daemon mati: heartbeat tetap berdetak sementara pass keputusannya
    # tidak pernah selesai. Tanpa baris ini, monitor melaporkan "daemon hidup"
    # di atas mesin yang tidak menganalisa apa pun.
    #
    # DIIKAT KE WAKTU BERLALU, bukan cuma ke jumlah cycle. Dua pemeriksaan
    # berturut dalam dua puluh detik selalu melihat nol cycle baru, dan alarm
    # yang menyala pada operasi normal adalah alarm yang akan diabaikan saat ia
    # benar. QUIET adalah dua cycle default (20s) plus margin.
    QUIET = 120
    elapsed = int(time.time()) - seen_at
    if (switch["enabled"] and switch["daemon_alive"] and cycles == 0
            and not args.all and seen_at and elapsed >= QUIET):
        attention.append(f"daemon berdetak tapi nol cycle selesai dalam "
                         f"{elapsed} detik terakhir: pass keputusannya tidak "
                         f"sampai ke ringkas")

    fresh = [e for e in journal.entries() if int(e.get("at") or 0) > since]
    counts: dict[str, int] = {}
    for entry in fresh:
        counts[entry["event"]] = counts.get(entry["event"], 0) + 1
    tally = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    print(f"  journal: {len(fresh)} event baru" + (f" ({tally})" if tally else ""))
    for entry in fresh:
        if entry["event"] not in LOUD:
            continue
        when = time.strftime("%H:%M:%S", time.localtime(int(entry.get("at") or 0)))
        print(f"    [{when}] {entry['event'].upper()} "
              f"{entry.get('symbol') or ''} zone {entry.get('zone_id')} "
              f"ticket {entry.get('ticket')}")
        for line in entry.get("why") or []:
            print(f"        why: {line}")
        for line in entry.get("blockers") or []:
            print(f"        blocker: {line}")
        attention.append(f"{entry['event']} {entry.get('symbol') or ''} "
                         f"ticket {entry.get('ticket')}")

    if attention:
        print("  PERHATIAN:")
        for line in attention:
            print(f"    - {line}")
    else:
        print("  tidak ada yang perlu dilihat")

    if not args.all:
        WATERMARK.write_text(
            json.dumps({"seen_at": int(time.time()), "log_offset": offset},
                       indent=1),
            encoding="utf-8")
    return 1 if attention else 0


if __name__ == "__main__":
    raise SystemExit(main())
