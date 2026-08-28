"""The daemon the UI switch arms. Nothing else trades unattended.

    python -m tools.autotrade --symbol mt5:XAUUSD --interval 1h --risk-pct 0.03
    python -m tools.autotrade --send        # the same, and it really sends

WHY THE SWITCH IS NOT THE THING THAT TRADES. `app/` is a read-only drawing engine
reachable from a web server. If a button placed orders, every HTTP request that
reached the server could trade. So the button writes a flag in
`app/autotrade.py`, this process reads it, and the server keeps its inability to
send anything as a property of the layout.

Two consequences the operator has to know, and the UI is built to say both:

  1. ARMING WITH NO DAEMON DOES NOTHING. That is the safe direction, and it is
     why this process stamps a heartbeat every cycle: a switch reading ON over a
     dead daemon is the exact failure this project keeps a list of.
  2. STOPPING THIS PROCESS STOPS TRADING, immediately and without touching the
     switch. Pending orders already at the broker stay there with their stop and
     target - the broker holds those, not this loop.

ONE DECISION PASS, SHARED. The entry logic is `execute.cycle` and the exit logic
is `flatten.close`, both imported. A daemon with its own copy of either would be a
second engine, and the one that disagrees would be the one holding the account.

WHAT IT DOES EACH CYCLE
  heartbeat, read the switch, and if armed: run one entry pass, then close any
  position of ours that has crossed a rollover. Then sleep. Every guard from the
  one-shot tools still applies - demo only, blockers, idempotency, sizing - because
  it is the same code.
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time

from app import autotrade, journal
from tools.costed import rollovers
from app.ict import Rules
from tools.execute import RULE, _terminal, cycle, lot_specs, sizing
from tools.flatten import close, why_closed

#: Seconds between cycles. `app/autotrade.STALE_AFTER` is three of these, so one
#: slow cycle does not read as a dead daemon.
CYCLE_SECONDS = 20


def exits(mt5, symbol: str, send: bool, rule: dict) -> int:
    """Close any position of OURS that has crossed a rollover. Returns how many.

    Ours means the journal has a `placed` line for its ticket. A position put on
    by hand has an exit rule this loop has no record of, and closing it because it
    happens to be on the same symbol would be overruling a decision it cannot see.
    """
    closed = 0
    now = int(time.time())
    for position in (mt5.positions_get(symbol=symbol) or []):
        placed = [e for e in journal.for_ticket(int(position.ticket))
                  if e["event"] == "placed"]
        if not placed:
            continue
        nights = rollovers(int(position.time), now)
        if nights < 1:
            continue
        if not send:
            print(f"  DRY RUN: ticket {position.ticket} sudah menyeberang "
                  f"{nights} rollover, akan ditutup")
            continue
        done, why_not = close(mt5, position)
        if not done:
            print(f"  GAGAL menutup {position.ticket}: {why_not}")
            journal.record("refused", why=why_closed(nights, int(position.time)),
                           rule=rule, zone_id=placed[0].get("zone_id"),
                           ticket=int(position.ticket), blockers=[why_not])
            continue
        journal.record("closed", why=why_closed(nights, int(position.time)),
                       rule=rule, zone_id=placed[0].get("zone_id"),
                       ticket=int(position.ticket),
                       extra={"profit_at_close": position.profit,
                              "swap_at_close": position.swap, "nights": nights})
        print(f"  DITUTUP ticket {position.ticket}, {nights} rollover")
        closed += 1
    return closed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--bars", type=int, default=3000)
    parser.add_argument("--max-orders", type=int, default=2)
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--max-total-risk-pct", type=float, default=0.06)
    parser.add_argument("--max-correlation", type=float, default=0.70)
    parser.add_argument("--cycle", type=int, default=CYCLE_SECONDS)
    parser.add_argument("--once", action="store_true",
                        help="one cycle and exit, for a smoke test")
    parser.add_argument("--send", action="store_true",
                        help="really place and close. Without it every cycle runs "
                             "the same decisions and sends nothing")
    # PERMUKAAN TUNING CHECKLIST, SAMA SEPERTI `tools/execute.py`. Tanpa empat
    # flag ini daemon adalah satu-satunya jalur order yang TIDAK BISA menegakkan
    # satu pun klausa doctrine: `Rules.required` default kosong, jadi killzone,
    # discount/premium, OTE, CISD, dan SSMT dua tahap semuanya dihitung dan
    # dilaporkan sambil tidak menghalangi apa pun. Jalur manual punya pilihan
    # itu sejak awal; jalur tak-ditunggui tidak, dan asimetri itu adalah kelas
    # cacat yang sama dengan drift signature 27 Agustus.
    parser.add_argument("--partners", default="",
                        help="comma list simbol yang DIBACA sebagai partner SSMT "
                             "dan korelasi tapi TIDAK ditradingkan, misal "
                             "mt5:XAGUSD,mt5:XPTUSD")
    parser.add_argument("--require", default="",
                        help="comma list klausa checklist yang WAJIB lolos, "
                             "misal killzone,discount_or_premium,poi_families. "
                             "Kosong berarti checklist melaporkan tanpa memblokir")
    parser.add_argument("--killzones", default="",
                        help="comma list killzone yang dihitung, misal ny_am,london. "
                             "Kosong berarti semuanya")
    parser.add_argument("--min-families", type=int, default=2,
                        help="famili PD array yang harus menumpuk untuk poi_families")
    parser.add_argument("--max-conflicts", type=int, default=0,
                        help="box sisi lawan yang ditoleransi di dalam band")
    # PENGAMAN, BUKAN FILTER. Cap portofolio membatasi yang SEDANG
    # dipertaruhkan dan buta terhadap yang sudah HILANG: delapan kekalahan
    # berturut dalam satu hari tidak melanggar cap sama sekali, karena tiap
    # kerugian mengosongkan kembali ruangnya. Default 0 mematikannya, jadi
    # tidak ada perilaku yang berubah tanpa operator memintanya.
    parser.add_argument("--daily-loss-pct", type=float, default=0.0,
                        help="berhenti mengirim order kalau kerugian terealisasi "
                             "hari ini sudah mencapai persen equity ini, misal "
                             "0.02. Nol mematikan pengaman")
    args = parser.parse_args()
    # LINE BUFFERED, or this daemon's log does not exist until it dies. Python
    # block-buffers stdout whenever it is not a terminal, so redirected to a file -
    # which is how a daemon is always run - the log stayed at 0 bytes while the
    # process was demonstrably alive and heartbeating. A supervisor that cannot
    # read what its daemon is doing is a supervisor in name only. Measured on
    # 2026-08-21: 0 bytes after two full cycles.
    sys.stdout.reconfigure(line_buffering=True)
    rule = {**RULE, "risk_pct": args.risk_pct, "surface": "tools/autotrade.py"}
    rules = Rules(
        required=tuple(x.strip() for x in args.require.split(",") if x.strip()),
        min_families=args.min_families,
        max_conflicts=args.max_conflicts,
        **({"killzones": tuple(x.strip() for x in args.killzones.split(",")
                               if x.strip())} if args.killzones else {}),
    )
    # SATU BASKET, BUKAN SATU SIMBOL. `args.symbol.split(":")[-1]` pada
    # `mt5:XAUUSD,mt5:XAGUSD` menghasilkan string 'XAUUSD,mt5:XAGUSD', yaitu
    # cacat yang sama yang dicabut dari `execute.main` pada 27 Agustus 2026.
    symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
    intervals = [i.strip() for i in args.interval.split(",") if i.strip()]
    bare = [s.split(":")[-1] for s in symbols]
    partners = [s.strip() for s in args.partners.split(",") if s.strip()]

    print(f"daemon auto-trade: {args.symbol} {args.interval} risk "
          f"{args.risk_pct:.1%} cycle {args.cycle}s "
          f"{'SEND' if args.send else 'DRY RUN'}")
    # DICETAK TIAP START, karena "klausa mana yang mengikat" adalah hal yang
    # paling mudah dikira operator sudah menyala padahal tidak.
    print(f"klausa wajib: {', '.join(rules.required) if rules.required else 'TIDAK ADA, checklist hanya melaporkan'}")
    if partners:
        print(f"partner (dibaca, TIDAK ditradingkan): {', '.join(partners)}")
    if len(symbols) + len(partners) < 2:
        # SSMT BUTUH PARTNER. `execute.candidates` menjaga dirinya dengan
        # `len(partners) > 1`, jadi satu simbol berarti klausa ssmt dan
        # two_stage_confirmed tidak pernah dievaluasi sama sekali.
        print("CATATAN: satu deret saja, jadi klausa ssmt dan "
              "two_stage_confirmed tidak dievaluasi. Beri partner, misal "
              "--partners mt5:XAGUSD")
    print(f"saklar ada di {autotrade.STATE}; nyalakan dari UI atau "
          "POST /api/autotrade")

    was_enabled: bool | None = None
    while True:
        # HEARTBEAT FIRST, and before the switch is even read. A cycle that dies
        # inside the decision pass must still have said "I was here", or the UI
        # cannot tell a crashed daemon from a daemon that found nothing to do.
        autotrade.beat(args.symbol, args.interval, args.risk_pct)
        state = autotrade.read()
        stamp = datetime.datetime.now(datetime.UTC).strftime("%m-%d %H:%M:%S")

        if state["enabled"] != was_enabled:
            # Printed on CHANGE only. A line every twenty seconds is a log nobody
            # reads, and the transition is the thing worth seeing.
            print(f"[{stamp}] saklar: "
                  f"{'MENYALA' if state['enabled'] else 'MATI'}")
            was_enabled = state["enabled"]

        if state["enabled"]:
            terminal, why_not = _terminal()
            if terminal is None:
                print(f"[{stamp}] BLOCKER: {why_not}")
                journal.record("refused", why=["daemon cycle attempted"], rule=rule,
                               blockers=[why_not])
            else:
                mt5, account = terminal
                # SATU LotSpec PER SIMBOL, sama seperti `execute.main`. Satu spec
                # yang di-broadcast adalah error 50x antara XAUUSD (100) dan
                # XAGUSD (5000).
                lot, missing = lot_specs(symbols)
                if missing:
                    print(f"[{stamp}] CATATAN: terminal tidak membawa "
                          f"{', '.join(missing)}, kandidat pada simbol itu tidak "
                          f"akan disizing dan tidak akan dikirim")
                equity = sizing(account, lot or {}, args.risk_pct)
                cycle(mt5, symbols, intervals,
                      args.bars, args.risk_pct, args.max_orders, args.send,
                      equity, lot, rules, args.max_total_risk_pct,
                      args.max_correlation, partners, args.daily_loss_pct)
                for name in bare:
                    exits(mt5, name, args.send, rule)

        if args.once:
            return 0
        time.sleep(args.cycle)


if __name__ == "__main__":
    raise SystemExit(main())
