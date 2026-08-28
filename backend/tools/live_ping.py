"""Apa yang SEBENARNYA dijawab broker, tanpa perantara dry run.

    python -m tools.live_ping                # cuma order_check, nol order
    python -m tools.live_ping --send         # benar-benar kirim, lalu batalkan
    python -m tools.live_ping --send --market  # plus satu market 0,01 lot

KENAPA INI ADA. Dry run menjalankan seluruh pass keputusan dan berhenti tepat
sebelum satu-satunya bagian yang bisa ditolak broker. Ia membuktikan mesin
memilih dengan benar dan tidak membuktikan apa pun tentang apakah pilihannya
diterima. Retcode, requote, stop yang ditolak, filling mode yang tidak
didukung, semuanya hidup di sisi yang tidak pernah disentuh dry run.

TIGA PROBE, DAN TIAP SATUNYA BISA DIKEMBALIKAN.

  1. `order_check` atas limit yang sah, jauh dari harga. Nol order dibuat.
     Sukses di sini adalah retcode 0, dan itu KEBALIKAN dari `order_send`
     yang sukses di 10009 atau 10008. Perbedaan itu pernah membuat dua tool di
     repo ini melaporkan GAGAL atas order yang benar-benar terkirim.
  2. `order_send` limit jauh dari harga, lalu dibatalkan. Membuktikan jalur
     terima ujung ke ujung. Jauh dari harga supaya tidak ada risiko terisi.
  3. `order_send` dengan stop di SISI YANG SALAH. Membuktikan jalur tolak.
     Nol order dibuat karena broker menolaknya, jadi tidak ada yang perlu
     dibersihkan. Dipakai stop terbalik dan bukan stop terlalu rapat, karena
     `trade_stops_level` di akun ini terbaca 0 sehingga tidak ada jarak minimum
     yang bisa dilanggar.

Probe keempat opsional, `--market`, mengukur slippage: harga fill dikurangi ask
saat kirim. Ia satu-satunya yang benar-benar terisi, jadi ia bawa bracket dan
langsung ditutup lewat `flatten.close`, bukan lewat salinan kedua.

DEMO SAJA. `execute._terminal` menolak `trade_mode != 0`, dan file ini tidak
punya jalan lain ke terminal.
"""

from __future__ import annotations

import argparse

from app import journal
from tools.execute import RULE, _terminal, send_ok
from tools.flatten import close

#: Sejauh apa limit ditaruh dari harga, dalam persen. Cukup jauh sehingga tidak
#: ada kemungkinan terisi selama detik-detik ia hidup, dan masih di dalam
#: rentang harga yang broker terima.
AWAY_PCT = 0.10

VOLUME = 0.01


def names(mt5) -> dict[int, str]:
    """Peta retcode ke namanya, dibaca dari modul dan bukan diketik ulang.

    NOL DITAMBAHKAN DENGAN TANGAN, dan itu bukan kelalaian modul. Diperiksa
    pada paket MetaTrader5 di mesin ini: ia mendefinisikan 40 konstanta
    `TRADE_RETCODE_*` dan nilai terkecilnya 10004, jadi `TRADE_RETCODE_OK`
    tidak ada sama sekali. Tanpa baris ini jawaban sukses `order_check`
    tercetak "0 (tak dikenal)", yang membaca seperti kegagalan justru pada
    satu-satunya call yang sukses di nol.
    """
    table = {getattr(mt5, n): n for n in dir(mt5) if n.startswith("TRADE_RETCODE_")}
    table.setdefault(0, "TRADE_RETCODE_OK (order_check)")
    return table


def show(mt5, label: str, result) -> int:
    """Cetak satu jawaban broker apa adanya, dan kembalikan retcode-nya."""
    table = names(mt5)
    if result is None:
        print(f"  {label:34s} TIDAK ADA JAWABAN, last_error {mt5.last_error()}")
        return -1
    code = int(result.retcode)
    print(f"  {label:34s} retcode {code} {table.get(code, '(tak dikenal)')}"
          f"  comment {getattr(result, 'comment', '') or '-'}")
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--send", action="store_true",
                        help="benar-benar kirim probe 2 dan 3. Tanpa ini cuma "
                             "order_check yang jalan dan nol order dibuat")
    parser.add_argument("--market", action="store_true",
                        help="tambah probe market 0,01 lot yang langsung "
                             "ditutup, untuk mengukur slippage")
    args = parser.parse_args()

    terminal, why_not = _terminal()
    if terminal is None:
        print(f"BLOCKER: {why_not}")
        return 1
    mt5, account = terminal
    rule = {**RULE, "surface": "tools/live_ping.py"}

    info = mt5.symbol_info(args.symbol)
    tick = mt5.symbol_info_tick(args.symbol)
    if info is None or tick is None:
        print(f"BLOCKER: terminal tidak membawa {args.symbol}")
        return 1

    digits = info.digits
    print(f"akun {account.login} {account.server} trade_mode={account.trade_mode} "
          f"(0=DEMO) equity {account.equity}")
    print(f"{args.symbol}: bid {tick.bid} ask {tick.ask} "
          f"spread {round((tick.ask - tick.bid) / info.point)} poin, "
          f"stops_level {info.trade_stops_level}, filling_mode {info.filling_mode}")
    print(f"mode: {'SEND' if args.send else 'order_check saja, nol order'}"
          f"{', plus market' if args.market else ''}\n")

    entry = round(tick.ask * (1 - AWAY_PCT), digits)
    stop = round(entry * 0.98, digits)
    target = round(entry * 1.04, digits)
    base = {
        "symbol": args.symbol,
        "volume": VOLUME,
        "type": mt5.ORDER_TYPE_BUY_LIMIT,
        "price": entry,
        "sl": stop,
        "tp": target,
        "deviation": 20,
        "magic": 0,
        "comment": "zonelab live_ping",
        "type_time": mt5.ORDER_TIME_GTC,
    }

    # ---- Probe 1: order_check, nol order dibuat -------------------------
    print(f"PROBE 1  order_check, buy limit {entry} sl {stop} tp {target}")
    checked = mt5.order_check({**base, "action": mt5.TRADE_ACTION_PENDING})
    code1 = show(mt5, "order_check", checked)
    print(f"  {'sukses' if code1 == 0 else 'DITOLAK'}: order_check sukses pada 0, "
          f"berbeda dari order_send\n")

    if not args.send:
        print("Berhenti di sini. Jalankan dengan --send untuk probe 2 dan 3.")
        mt5.shutdown()
        return 0

    # ---- Probe 2: kirim sungguhan, lalu batalkan -----------------------
    print(f"PROBE 2  order_send buy limit {entry}, lalu dibatalkan")
    sent = mt5.order_send({**base, "action": mt5.TRADE_ACTION_PENDING})
    show(mt5, "order_send pending", sent)
    ok, why = send_ok(mt5, sent)
    print(f"  send_ok membaca: {'DITERIMA' if ok else 'ditolak'}  {why}")
    if ok:
        ticket = int(sent.order)
        journal.record("placed", why=["live_ping probe 2, limit jauh dari harga"],
                       rule=rule, symbol=f"mt5:{args.symbol}", ticket=ticket)
        removed = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE,
                                  "order": ticket})
        code_rm = show(mt5, f"batalkan ticket {ticket}", removed)
        rm_ok, rm_why = send_ok(mt5, removed)
        print(f"  pembatalan: {'BERHASIL' if rm_ok else 'GAGAL'}  {rm_why}")
        journal.record("cancelled" if rm_ok else "refused",
                       why=[f"live_ping probe 2 selesai, retcode {code_rm}"],
                       rule=rule, symbol=f"mt5:{args.symbol}", ticket=ticket,
                       blockers=[] if rm_ok else [rm_why])
    print()

    # ---- Probe 3: stop di sisi yang salah, harus DITOLAK ----------------
    bad_stop = round(entry * 1.02, digits)
    print(f"PROBE 3  order_send buy limit {entry} dengan sl {bad_stop} DI ATAS "
          f"entry, harus ditolak")
    bad = mt5.order_send({**base, "action": mt5.TRADE_ACTION_PENDING,
                          "sl": bad_stop})
    code3 = show(mt5, "order_send stop terbalik", bad)
    bad_ok, bad_why = send_ok(mt5, bad)
    if bad_ok:
        # BROKER MENERIMA YANG SEHARUSNYA DITOLAK. Itu temuan, bukan sukses,
        # dan ordernya harus dibersihkan.
        print("  PERHATIAN: broker MENERIMA order dengan stop terbalik. "
              "Dibatalkan sekarang.")
        mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE,
                        "order": int(bad.order)})
    else:
        print(f"  ditolak sebagaimana mestinya: {bad_why}")
    journal.record("refused", why=["live_ping probe 3, stop terbalik"],
                   rule=rule, symbol=f"mt5:{args.symbol}",
                   blockers=[f"retcode {code3}"])
    print()

    # ---- Probe 4 opsional: market, ukur slippage ------------------------
    if args.market:
        fresh = mt5.symbol_info_tick(args.symbol)
        want = fresh.ask
        print(f"PROBE 4  market buy {VOLUME} lot, ask saat kirim {want}")
        deal = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": args.symbol,
            "volume": VOLUME,
            "type": mt5.ORDER_TYPE_BUY,
            "price": want,
            "sl": round(want * 0.98, digits),
            "tp": round(want * 1.02, digits),
            "deviation": 20,
            "magic": 0,
            "comment": "zonelab live_ping market",
            "type_time": mt5.ORDER_TIME_GTC,
        })
        show(mt5, "order_send market", deal)
        deal_ok, deal_why = send_ok(mt5, deal)
        if deal_ok:
            filled = float(deal.price)
            slip = filled - want
            print(f"  terisi di {filled}, slippage {slip:+.{digits}f} "
                  f"({slip / info.point:+.0f} poin)")
            journal.record("placed", why=[f"live_ping probe 4 market, "
                                          f"slippage {slip:+.{digits}f}"],
                           rule=rule, symbol=f"mt5:{args.symbol}",
                           ticket=int(deal.order))
            for position in (mt5.positions_get(symbol=args.symbol) or []):
                if position.comment and "live_ping" in position.comment:
                    done, why_not_closed = close(mt5, position, digits)
                    print(f"  penutupan ticket {position.ticket}: "
                          f"{'BERHASIL' if done else 'GAGAL ' + why_not_closed}")
                    journal.record("closed" if done else "refused",
                                   why=["live_ping probe 4 ditutup"], rule=rule,
                                   symbol=f"mt5:{args.symbol}",
                                   ticket=int(position.ticket),
                                   blockers=[] if done else [why_not_closed])
        else:
            print(f"  ditolak: {deal_why}")
        print()

    left = mt5.positions_get(symbol=args.symbol) or []
    pending = mt5.orders_get(symbol=args.symbol) or []
    print(f"SESUDAH: {len(left)} posisi, {len(pending)} pending pada "
          f"{args.symbol}")
    if left or pending:
        print("  PERHATIAN: ada yang tertinggal, periksa terminal")
    mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
