"""Close what has crossed a rollover, because that is the rule that measured better.

    python -m tools.flatten                 # dry run
    python -m tools.flatten --send          # actually close

THE RULE, AND THE NUMBER BEHIND IT. `tools/costed.py --flat` closes every trade
at the 21:00 UTC rollover instead of letting it run to the 80-bar horizon, and on
50,000 bars of broker gold that is +0.221 R against +0.198 R, 8 of 8 folds
positive either way. The whole of that difference comes from ONE cohort: trades
filled on a FRIDAY read +0.128 R held (t=1.55, the weakest weekday and not
significant on its own) against +0.218 R flat (t=3.12). Monday to Thursday barely
move. Average nights held on a Friday fill drops from 0.98 to 0.58 and the
maximum from 34 to 3.

WHY IT IS NOT "CLOSE AT 21:00". Gold has no 21:00 bar - that hour is the daily
session break - so the first price at or after the rollover is the reopen. On a
Friday the reopen is Sunday, 50 hours later, measured on the last four weekends
of this feed. The rule therefore reads "closed on the first available price at or
after the rollover it crossed", and this tool implements exactly that by closing
anything whose fill is on the far side of a rollover instant from now.

WHY IT REFUSES TO CLOSE WHAT IT DID NOT OPEN. A position with no `placed` line in
the journal was put on by hand or by something else, and its exit is somebody
else's rule. Closing it because it happens to be on the same symbol would be this
tool overruling a decision it has no record of.
"""

from __future__ import annotations

import argparse
import datetime

from app import journal
from tools.costed import ROLLOVER_HOUR_UTC, rollovers
from tools.broker import MAGIC, RULE, _terminal, send_ok


def why_closed(nights: int, opened_at: int) -> list[str]:
    """The grounds, each carrying its number, for the journal."""
    return [
        f"position crossed {nights} rollover instant(s) since it filled at "
        f"{datetime.datetime.fromtimestamp(opened_at, datetime.UTC):%Y-%m-%d %H:%M} UTC",
        "flat at rollover measured +0.221 R against +0.198 R holding to the "
        "80-bar horizon, 8/8 folds either way",
        "on Friday fills specifically, +0.218 R (t=3.12) against +0.128 R "
        "(t=1.55), which is where the whole difference lives",
    ]


#: Slippage maksimum yang diterima untuk penutupan market, dalam point.
#:
#: KENAPA ADA ANGKANYA SAMA SEKALI. Versi sebelumnya mengirim
#: `TRADE_ACTION_DEAL` TANPA field `deviation`, sementara `tools/live_ping.py`
#: menyetel 20 untuk probe market-nya. Penutupan rollover terjadi tepat di
#: pergantian sesi, yaitu saat spread paling lebar dan requote paling mungkin,
#: dan tanpa deviation broker berhak menolak alih alih mengisi. Posisi yang
#: GAGAL ditutup di rollover adalah persis hal yang daemon ini ada untuk
#: mencegah. 20 point menyamai probe yang sudah terbukti diterima terminal ini.
CLOSE_DEVIATION = 20


def close(mt5, position, price_digits: int | None = None) -> tuple[bool, str]:
    """Close one position at market. Returns (closed, reason-if-not).

    DIGIT DIBACA DARI SIMBOLNYA, dan default 3 yang lama adalah cacat yang sama
    dengan yang ada di `execute.place` sampai 29 Agustus 2026. Tiga desimal
    kebetulan benar untuk XAUUSD dan salah untuk tiap pasangan FX lima desimal,
    dan `tools/autotrade.py` memanggil fungsi ini TANPA argumen, jadi jalur
    penutupan otomatis memakai default itu untuk simbol apa pun.

    `price_digits` masih bisa dioper karena `live_ping` sudah melakukannya, tapi
    None sekarang berarti "tanyakan terminalnya", bukan "pakai tiga".
    """
    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        return False, f"no tick for {position.symbol}: {mt5.last_error()}"
    if price_digits is None:
        info = mt5.symbol_info(position.symbol)
        if info is None:
            return False, (f"symbol_info tidak terbaca untuk {position.symbol}, "
                           f"jadi digit harganya tidak diketahui: "
                           f"{mt5.last_error()}")
        price_digits = int(info.digits)
    long_side = position.type == mt5.POSITION_TYPE_BUY
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        # The OPPOSITE side, and filled at the side of the book that closes it:
        # a long is closed by a sell at the bid.
        "type": mt5.ORDER_TYPE_SELL if long_side else mt5.ORDER_TYPE_BUY,
        "position": position.ticket,
        "price": round(tick.bid if long_side else tick.ask, price_digits),
        "deviation": CLOSE_DEVIATION,
        "type_time": mt5.ORDER_TIME_GTC,
        # IOC untuk penutupan market: isi yang bisa diisi sekarang, batalkan
        # sisanya. Bedanya dengan RETURN di `execute.place` disengaja, karena
        # yang di sana pending dan yang ini deal.
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": "zonelab flat rollover"[:31],
    }
    # SATU PREDIKAT, DIPAKAI BERSAMA `execute.place`. File ini dulu menguji
    # `retcode != 0` juga, jadi ia akan menutup posisi dengan sukses lalu
    # melaporkannya gagal, dan menulis record penolakan untuk posisi yang sudah
    # tertutup. Alasan lengkapnya di docstring `execute.send_ok`.
    return send_ok(mt5, mt5.order_send(request))


#: Berapa lama sebuah pending order kita boleh menganggur sebelum dibatalkan,
#: dalam detik. Tiga hari.
#:
#: KENAPA PEMBATALAN PERLU ADA SAMA SEKALI. Tiap order dikirim sebagai
#: `ORDER_TIME_GTC`, dan sampai 29 Agustus 2026 `TRADE_ACTION_REMOVE` hanya
#: muncul di `tools/live_ping.py`. Artinya tidak ada apa pun di jalur normal
#: yang pernah membatalkan apa pun: sebuah pending yang tidak pernah terisi
#: hidup selamanya, terus memakan cap portofolio, dan terus mengunci zonanya
#: lewat gerbang idempotency yang membaca journal. Satu zona yang order-nya
#: kedaluwarsa tanpa terisi jadi pensiun permanen, dan `docs/ALUR-ORDER.md`
#: sudah menamai konsekuensi itu tanpa ada yang menutupnya.
#:
#: ANGKANYA TIDAK PUNYA PENGUKURAN, dan itu dinyatakan alih alih disamarkan.
#: Ia dipilih dari horizon 80 bar yang dipakai tiap pengukuran di proyek ini,
#: yang pada chart satu jam kira kira 3,3 hari. Ia berhak ada tanpa angka
#: dengan alasan yang sama seperti pengaman kerugian harian: ia tidak pernah
#: MELOLOSKAN trade yang ditolak gerbang lain, ia hanya melepas paparan.
STALE_PENDING_SECONDS = 3 * 24 * 3600


def stale_pendings(mt5, now: int, max_age: int = STALE_PENDING_SECONDS) -> list:
    """Pending milik KITA yang sudah menganggur lebih lama dari `max_age`.

    KEPEMILIKAN DIBACA DARI `magic`, bukan dari journal. Journal-nya lokal,
    gitignored, dan tidak pernah direkonsiliasi dengan broker, jadi ia bukan
    sumber yang aman untuk memutuskan order mana yang boleh dibatalkan. Sejak
    `broker.MAGIC` diset, broker sendiri membawa jawabannya, dan order tangan
    di terminal yang sama tidak akan pernah ikut tersapu.
    """
    out = []
    for order in (mt5.orders_get() or []):
        if int(getattr(order, "magic", 0)) != MAGIC:
            continue
        setup = int(getattr(order, "time_setup", 0))
        if setup and now - setup >= max_age:
            out.append(order)
    return out


def cancel(mt5, order) -> tuple[bool, str]:
    """Batalkan satu pending. Predikat suksesnya sama dengan `close`."""
    sent = mt5.order_send({
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": int(order.ticket),
    })
    return send_ok(mt5, sent)


def wanted_symbols(arg: str) -> list[str]:
    """Simbol yang harus diperiksa, dari satu argumen.

    SATU SIMBOL PER RUN ADALAH SETENGAH PERBAIKAN YANG DIAM. Sampai 3 September
    2026 `--symbol` hanya menerima satu nama dan defaultnya XAUUSD, sementara
    `tools/execute.py --symbol` sudah lama menerima daftar koma dan buku hari itu
    memegang XAUUSD DAN BTCUSD sekaligus. Menjalankan alat ini apa adanya
    menutup posisi emas, mencetak "tidak ada posisi terbuka" untuk sisanya, dan
    keluar dengan status nol - laporan yang benar untuk simbol yang ditanyakan
    dan menyesatkan untuk pertanyaan yang sebenarnya diajukan operator.

    Prefix venue dibuang, karena journal dan switch menyimpan `mt5:XAUUSD`
    sementara `positions_get` mau `XAUUSD` telanjang.
    """
    return [part.strip().split(":")[-1] for part in arg.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD",
                        help="satu simbol, atau daftar dipisah koma, "
                             "sama seperti tools/execute.py")
    parser.add_argument("--send", action="store_true",
                        help="actually close. Without it nothing is sent and "
                             "nothing is journalled")
    args = parser.parse_args()

    terminal, why_not = _terminal()
    if terminal is None:
        print(f"BLOCKER: {why_not}")
        return
    mt5, account = terminal
    now = int(datetime.datetime.now(datetime.UTC).timestamp())
    print(f"akun {account.login} trade_mode={account.trade_mode} (0=DEMO)  "
          f"sekarang {datetime.datetime.fromtimestamp(now, datetime.UTC):%m-%d %H:%M} UTC, "
          f"rollover {ROLLOVER_HOUR_UTC}:00 UTC")

    for symbol in wanted_symbols(args.symbol):
        positions = mt5.positions_get(symbol=symbol) or []
        if not positions:
            print(f"  {symbol}: tidak ada posisi terbuka")
            continue

        for position in positions:
            placed = [e for e in journal.for_ticket(int(position.ticket))
                      if e["event"] == "placed"]
            head = (f"  ticket {position.ticket} {position.symbol} vol {position.volume} "
                    f"open {position.price_open} profit {position.profit}")
            if not placed:
                print(f"{head}\n      BUKAN milik journal ini, tidak disentuh")
                continue
            nights = rollovers(int(position.time), now)
            if nights < 1:
                print(f"{head}\n      belum menyeberang rollover, dibiarkan")
                continue
            if not args.send:
                print(f"{head}\n      DRY RUN: sudah menyeberang {nights} rollover, "
                      "akan ditutup")
                continue
            done, reason = close(mt5, position)
            if not done:
                print(f"{head}\n      GAGAL menutup: {reason}")
                journal.record("refused", why=why_closed(nights, int(position.time)),
                               rule=RULE, zone_id=placed[0].get("zone_id"),
                               ticket=int(position.ticket), blockers=[reason])
                continue
            journal.record("closed", why=why_closed(nights, int(position.time)),
                           rule=RULE, zone_id=placed[0].get("zone_id"),
                           ticket=int(position.ticket),
                           extra={"profit_at_close": position.profit,
                                  "swap_at_close": position.swap,
                                  "nights": nights})
            print(f"{head}\n      DITUTUP, {nights} rollover")


if __name__ == "__main__":
    main()
