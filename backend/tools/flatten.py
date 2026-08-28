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
from tools.execute import send_ok
from tools.execute import RULE, _terminal


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


def close(mt5, position, price_digits: int = 3) -> tuple[bool, str]:
    """Close one position at market. Returns (closed, reason-if-not)."""
    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        return False, f"no tick for {position.symbol}: {mt5.last_error()}"
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
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": "zonelab flat rollover"[:31],
    }
    # SATU PREDIKAT, DIPAKAI BERSAMA `execute.place`. File ini dulu menguji
    # `retcode != 0` juga, jadi ia akan menutup posisi dengan sukses lalu
    # melaporkannya gagal, dan menulis record penolakan untuk posisi yang sudah
    # tertutup. Alasan lengkapnya di docstring `execute.send_ok`.
    return send_ok(mt5, mt5.order_send(request))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
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

    positions = mt5.positions_get(symbol=args.symbol) or []
    if not positions:
        print("  tidak ada posisi terbuka")
        return

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
