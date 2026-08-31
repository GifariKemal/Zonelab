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

THREE THINGS THIS LOOP LEARNED THE HARD WAY, all three measured on this machine:

  1. A RAISE USED TO END IT. There was no try around the per-cycle work, so one
     exception from `history.load` or anywhere inside `cycle` returned from
     `main` while the switch kept reading ON for `STALE_AFTER = 60` seconds. On
     27 August 2026 a signature drift in `execute.sizing` killed the daemon one
     second after it was armed and 861 tests passed, because not one of them
     called `main`. See `MAX_CONSECUTIVE_FAILURES` for why the fix is not simply
     "swallow everything and keep going".
  2. TWO DAEMONS RAN AT ONCE. 29 August 2026, PIDs 12948 and 19912, same symbol
     and same risk. The switch names one PID, so the second was invisible to
     both the UI and the monitor. `app/autotrade.owner` is the guard and
     `--allow-second-daemon` is the way past it.
  3. THE SHIPPED RISK DEFAULT IS NOT THE ONE IN USE. Default here is 1%, both
     live daemons ran 3%, and `docs/QA-QUANT.md` section 8 puts 3% at 40,97%
     probability of losing half the account in 500 trades under the zero-mean
     assumption section 6 shows applies. `risk_warning` says so at startup and
     changes nothing: the operator's number is the operator's decision.
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time
import traceback

from app import autotrade, journal
from tools.costed import rollovers
from app.ict import BIAS_DEGREES, Rules
from tools.broker import RULE, _terminal, lot_specs, sizing
from tools.execute import cycle
from tools.flatten import cancel, close, stale_pendings, why_closed

#: Seconds between cycles. `app/autotrade.STALE_AFTER` is three of these, so one
#: slow cycle does not read as a dead daemon.
CYCLE_SECONDS = 20

#: Cycle gagal BERTURUT sebelum daemon menyerah dan keluar.
#:
#: KENAPA MENYERAH SAMA SEKALI, dan kenapa ini bukan "telan semua, jalan terus".
#: Heartbeat distempel di AWAL cycle, sebelum switch dibaca dan sebelum pass
#: keputusan dijalankan. Sebuah loop yang gagal DI DALAM pass tetap berdetak,
#: jadi `daemon_alive` terbaca hijau selamanya sambil nol order dianalisa. Itu
#: persis bentuk kegagalan yang dikejar seluruh modul ini: instrumen melaporkan
#: hijau di atas proses yang tidak bekerja. Keluar mengubahnya jadi kegagalan
#: yang SUDAH punya alarm - heartbeat berhenti, `daemon_alive` jadi False dalam
#: `STALE_AFTER = 60` detik, dan `tools/monitor.py` membunyikan "saklar MENYALA
#: tapi daemon tidak berdetak".
#:
#: KENAPA LIMA. Pada `--cycle 20` lima cycle adalah 100 detik toleransi, lebih
#: panjang dari satu jendela `STALE_AFTER` penuh. Kegagalan transient di jalur
#: ini punya durasi yang terukur: jeda harian broker yang menahan `as_of`
#: tercatat 28 Agustus 2026 selama dua cycle, dan reconnect terminal satu.
#: Angkanya belum dikalibrasi ke sebaran kegagalan yang lebih panjang - belum
#: ada cukup insiden untuk itu - jadi lima adalah batas atas dari yang terukur
#: ditambah margin, bukan hasil optimisasi.
MAX_CONSECUTIVE_FAILURES = 5

#: Exit code, karena inilah yang dibaca supervisor dan operator.
EXIT_TOO_MANY_FAILURES = 3
EXIT_ALREADY_RUNNING = 4

#: `docs/QA-QUANT.md` bagian 8, kolom "P(ruin) kalau edge NOL": peluang
#: kehilangan SEPARUH akun dalam 500 trade, fixed fractional, 20.000 path
#: bootstrap. Kolom itu adalah deret R yang sama digeser ke mean nol - bentuk
#: sebarannya utuh, edge-nya hilang - dan bagian 6 menunjukkan kolom itulah yang
#: berlaku, karena ekspektasi di resolusi intrabar jujur +0,0214 R dengan CI95
#: yang memuat nol.
RUIN_ZERO_EDGE = {0.005: 0.0000, 0.01: 0.0024, 0.02: 0.1620,
                  0.03: 0.4097, 0.05: 0.7069, 0.10: 0.9383}

#: Bagian 10 "Setel": risk per trade 3% jadi 1%, dengan alasan berangka
#: "P(ruin) edge-nol 40,97% jadi 0,24%".
RECOMMENDED_RISK_PCT = 0.01


def _pct(value: float, places: int = 2) -> str:
    """Persen dengan koma desimal, supaya angkanya cocok VERBATIM dengan tabel.

    Operator yang membaca "40,97%" di log harus bisa mencari string itu di
    `docs/QA-QUANT.md` dan menemukan baris yang sama. "40.97%" tidak akan
    ketemu, dan angka yang tidak bisa ditelusuri kembali ke pengukurannya adalah
    angka yang akhirnya diperlakukan sebagai adjektif.
    """
    return f"{value * 100:.{places}f}".replace(".", ",") + "%"


def risk_warning(risk_pct: float) -> list[str]:
    """Baris peringatan kalau `risk_pct` di atas angka yang didokumentasikan.

    Kosong kalau tidak. TIDAK PERNAH MENGUBAH `risk_pct`, dan itu disengaja:
    clamp diam-diam berarti operator mengetik 3% lalu diperdagangkan pada 1%,
    dan seluruh journal-nya kemudian menjawab pertanyaan yang berbeda dari yang
    ia kira ia tanyakan. Sizing adalah keputusan operator; yang kurang selama
    ini adalah catatannya, bukan pagarnya.

    Angkanya dikutip dari tabel, bukan diadjektifkan. `docs/QA-QUANT.md`
    bagian 8 menghitung 3% pada 40,97% peluang kehilangan separuh akun dalam 500
    trade kalau edge-nya nol, dan kedua daemon yang hidup 29 Agustus 2026
    berjalan pada 3%. Untuk risk di antara dua baris tabel, baris yang dikutip
    adalah baris DI BAWAHNYA, jadi angka yang dicetak selalu lantai dan tidak
    pernah melebih-lebihkan.
    """
    if risk_pct <= RECOMMENDED_RISK_PCT:
        return []
    tabled = max(r for r in RUIN_ZERO_EDGE if r <= risk_pct)
    ruin = RUIN_ZERO_EDGE[tabled]
    exact = "" if tabled == risk_pct else (
        f" dan {_pct(risk_pct)} ada DI ATAS baris itu")
    return [
        "!!!!! RISK DI ATAS ANGKA YANG DIDOKUMENTASIKAN !!!!!",
        f"      --risk-pct {_pct(risk_pct)}, rekomendasi terukur "
        f"{_pct(RECOMMENDED_RISK_PCT)} (docs/QA-QUANT.md bagian 10, 'Setel').",
        f"      Bagian 8: pada risk {_pct(tabled, 1)}, peluang kehilangan "
        f"SEPARUH akun dalam 500 trade adalah {_pct(ruin)} kalau edge-nya "
        f"nol{exact}.",
        "      Bagian 6 menunjukkan kolom edge-nol adalah kolom yang berlaku: "
        "ekspektasi +0,0214 R dengan CI95 memuat nol.",
        "      Angkanya TIDAK diubah. Ini keputusan operator, dan ini catatannya.",
    ]


def sweep(mt5, send: bool, rule: dict) -> int:
    """Batalkan pending KITA yang sudah menganggur terlalu lama. Kembalikan
    berapa yang dibatalkan.

    KENAPA INI PERLU ADA. Tiap order dikirim `ORDER_TIME_GTC`, dan sampai 29
    Agustus 2026 `TRADE_ACTION_REMOVE` hanya muncul di `tools/live_ping.py`.
    Artinya tidak ada apa pun di jalur normal yang pernah membatalkan apa pun.
    Sebuah pending yang tidak pernah terisi hidup selamanya dan membayar dua
    kali: ia terus memakan cap portofolio, dan ia terus mengunci zonanya lewat
    gerbang idempotency, yang membaca journal dan menolak zona yang pernah
    dipesan. `docs/ALUR-ORDER.md` sudah menamai konsekuensi itu, yaitu zona
    yang order-nya kedaluwarsa tanpa terisi jadi pensiun permanen.

    KEPEMILIKAN DARI `magic`, BUKAN DARI JOURNAL, dan bedanya penting justru di
    sini. `exits` di atas memakai journal karena ia menutup POSISI, dan sebuah
    posisi yang tidak ada di journal adalah posisi yang aturan keluarnya tidak
    kita ketahui. Untuk membatalkan pending, journal adalah sumber yang lebih
    lemah: ia lokal, gitignored, dan tidak pernah direkonsiliasi dengan broker,
    jadi satu file yang terhapus akan membuat sapuan ini buta atau, lebih
    buruk, membuatnya menyentuh order tangan. `magic` dibawa broker sendiri.
    """
    if not mt5:
        return 0
    stale = stale_pendings(mt5, int(time.time()))
    cancelled = 0
    for order in stale:
        if not send:
            print(f"  DRY RUN: pending {order.ticket} sudah menganggur lebih "
                  f"dari batas, akan dibatalkan")
            continue
        ok, why_not = cancel(mt5, order)
        if not ok:
            print(f"  GAGAL membatalkan {order.ticket}: {why_not}")
            journal.record("refused", why=["sapuan pending basi"], rule=rule,
                           ticket=int(order.ticket), blockers=[why_not])
            continue
        print(f"  dibatalkan: pending {order.ticket}")
        journal.record("cancelled", why=["pending menganggur melewati batas"],
                       rule=rule, ticket=int(order.ticket))
        cancelled += 1
    return cancelled


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
    parser.add_argument("--allow-second-daemon", action="store_true",
                        help="START ANYWAY meskipun saklar sudah menamai PID "
                             "daemon lain yang hidup. ADA KARENA 29 Agustus 2026 "
                             "dua daemon identik jalan bersamaan, PID 12948 dan "
                             "19912: saklar cuma punya satu field daemon_pid jadi "
                             "yang kedua tak terlihat, dan kalau --send dipakai "
                             "keduanya akan balapan di idempotency check journal "
                             "dan cap --max-orders yang sama. Flag ini untuk kasus "
                             "PID daur ulang di bawah satu menit, yang tidak bisa "
                             "dibedakan dari daemon hidup tanpa operator melihat "
                             "sendiri")
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
    parser.add_argument("--bias-degree", default="bias_4h", choices=BIAS_DEGREES,
                        help="derajat bias yang dibaca klausa bias_agrees. "
                             "DEFAULTNYA 4 JAM UNTUK SETIAP TIMEFRAME, dan itu "
                             "yang menolak 19 kandidat demand di 15m dan 30m "
                             "pada 30 Agustus 2026 sementara bias_1h dan "
                             "bias_1d keduanya +1 dan BTCUSD naik 1,36 persen "
                             "dalam 24 jam. Menurunkannya BUKAN perbaikan yang "
                             "terbukti: H7 mengukur kontribusi zona di atas "
                             "bias ini NOL, jadi derajat mana pun yang dipilih "
                             "adalah pilihan operator, bukan temuan")
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

    # SATU DAEMON PER SAKLAR, diperiksa SEBELUM apa pun dibangun. Detailnya di
    # `app/autotrade.owner`: tiga fakta, dan PID basi dari daemon yang crash
    # bukan salah satunya, jadi start ulang setelah crash tetap bebas.
    held = autotrade.owner()
    if held and not args.allow_second_daemon:
        print(f"MENOLAK START: saklar {autotrade.STATE} sudah dipegang PID "
              f"{held['pid']} yang masih hidup, berdetak "
              f"{held['heartbeat_age_seconds']}s lalu pada "
              f"{held['symbol']} {held['interval']}.")
        print("Dua daemon pada saklar yang sama akan balapan di idempotency "
              "check journal dan cap --max-orders yang sama. Hentikan yang lama, "
              "atau pakai --allow-second-daemon kalau PID itu memang bukan "
              "daemon (PID bisa didaur ulang).")
        return EXIT_ALREADY_RUNNING
    if held:
        print(f"PERINGATAN: start dipaksakan di samping PID {held['pid']} yang "
              "masih berdetak, atas permintaan --allow-second-daemon")

    rule = {**RULE, "risk_pct": args.risk_pct, "surface": "tools/autotrade.py"}
    rules = Rules(
        required=tuple(x.strip() for x in args.require.split(",") if x.strip()),
        min_families=args.min_families,
        max_conflicts=args.max_conflicts,
        bias_degree=args.bias_degree,
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
    # DICETAK SETELAH BANNER, bukan sebelum, supaya baris pertama log tetap
    # "apa yang di-start" dan peringatan ini duduk persis di sebelah angkanya.
    for line in risk_warning(args.risk_pct):
        print(line)

    was_enabled: bool | None = None
    failures = 0
    try:
        while True:
            # SELURUH CYCLE ADA DI DALAM try, termasuk heartbeat dan pembacaan
            # saklar. Sebelum 29 Agustus 2026 tidak ada try sama sekali, jadi
            # satu raise dari `history.load` atau dari mana pun di dalam `cycle`
            # mengembalikan `main` sementara saklar terus terbaca ON selama
            # `STALE_AFTER` detik.
            try:
                # HEARTBEAT FIRST, and before the switch is even read. A cycle
                # that dies inside the decision pass must still have said "I was
                # here", or the UI cannot tell a crashed daemon from a daemon
                # that found nothing to do.
                autotrade.beat(args.symbol, args.interval, args.risk_pct)
                state = autotrade.read()
                stamp = datetime.datetime.now(datetime.UTC).strftime(
                    "%m-%d %H:%M:%S")

                if state["enabled"] != was_enabled:
                    # Printed on CHANGE only. A line every twenty seconds is a
                    # log nobody reads, and the transition is the thing worth
                    # seeing.
                    print(f"[{stamp}] saklar: "
                          f"{'MENYALA' if state['enabled'] else 'MATI'}")
                    was_enabled = state["enabled"]

                if state["enabled"]:
                    terminal, why_not = _terminal()
                    if terminal is None:
                        print(f"[{stamp}] BLOCKER: {why_not}")
                        journal.record("refused", why=["daemon cycle attempted"],
                                       rule=rule, blockers=[why_not])
                    else:
                        mt5, account = terminal
                        # SATU LotSpec PER SIMBOL, sama seperti `execute.main`.
                        # Satu spec yang di-broadcast adalah error 50x antara
                        # XAUUSD (100) dan XAGUSD (5000).
                        lot, missing = lot_specs(symbols)
                        if missing:
                            print(f"[{stamp}] CATATAN: terminal tidak membawa "
                                  f"{', '.join(missing)}, kandidat pada simbol "
                                  f"itu tidak akan disizing dan tidak akan "
                                  f"dikirim")
                        equity = sizing(account, lot or {}, args.risk_pct)
                        cycle(mt5, symbols, intervals,
                              args.bars, args.risk_pct, args.max_orders, args.send,
                              equity, lot, rules, args.max_total_risk_pct,
                              args.max_correlation, partners, args.daily_loss_pct)
                        for name in bare:
                            exits(mt5, name, args.send, rule)
                        sweep(mt5, args.send, rule)
            # SENGAJA SELEBAR `Exception`. Daftar tipe yang "diharapkan" adalah
            # justru daftar yang gagal 27 Agustus: yang membunuh daemon itu
            # TypeError dari drift signature, bukan error jaringan yang bisa
            # ditebak siapa pun. KeyboardInterrupt dan SystemExit turunan
            # BaseException, jadi keduanya lewat dan ditangani di luar.
            except Exception as exc:
                failures += 1
                stamp = datetime.datetime.now(datetime.UTC).strftime(
                    "%m-%d %H:%M:%S")
                # Kata "GAGAL" bukan hiasan: `tools/monitor.py` memindai log
                # daemon untuk "BLOCKER" dan "GAGAL", jadi baris ini menaikkan
                # exit code monitor tanpa gerbang baru di sisi sana.
                print(f"[{stamp}] CYCLE GAGAL "
                      f"{failures}/{MAX_CONSECUTIVE_FAILURES}: "
                      f"{type(exc).__name__}: {exc}")
                print(traceback.format_exc().rstrip())
                try:
                    journal.record("refused", why=["daemon cycle raised"],
                                   rule=rule,
                                   blockers=[f"{type(exc).__name__}: {exc}"])
                except Exception as note:
                    # Journal adalah catatan, bukan gerbang. Kalau disk penuh,
                    # kegagalan mencatat kegagalan tidak boleh jadi jalan kedua
                    # untuk membunuh loop yang baru saja diperbaiki.
                    print(f"  (journal tidak bisa mencatat ini: {note})")
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"[{stamp}] MENYERAH setelah {failures} cycle gagal "
                          f"berturut. Heartbeat berhenti di sini, jadi "
                          f"daemon_alive jadi False dalam "
                          f"{autotrade.STALE_AFTER}s dan monitor membunyikan "
                          f"'saklar MENYALA tapi daemon tidak berdetak'.")
                    return EXIT_TOO_MANY_FAILURES
            else:
                if failures:
                    print(f"[{stamp}] pulih setelah {failures} cycle gagal "
                          f"berturut, hitungan dinolkan")
                    failures = 0

            if args.once:
                # Smoke test yang satu-satunya cycle-nya melempar tidak boleh
                # menjawab 0. Itu persis instrumen-hijau-di-atas-crash lagi.
                return 1 if failures else 0
            time.sleep(args.cycle)
    except KeyboardInterrupt:
        # Ctrl-C adalah cara mematikan yang didokumentasikan, jadi ia keluar
        # bersih dan bukan lewat traceback. Menghentikan proses ini menghentikan
        # trading; order yang sudah ada di broker tetap di sana dengan stop dan
        # target-nya, karena broker yang memegangnya, bukan loop ini.
        print("\nberhenti atas Ctrl-C. Saklar TIDAK disentuh; order yang sudah "
              "di broker tetap di sana dengan stop dan target-nya.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
