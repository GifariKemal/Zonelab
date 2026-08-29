"""Segala yang menyentuh terminal, di satu file.

KENAPA FILE INI DIPISAH DARI `tools/execute.py`, 29 Agustus 2026. Tiga tool
lain sudah mengimpor primitif broker DARI `execute`:

    tools/flatten.py    MAGIC, send_ok, RULE, _terminal
    tools/live_ping.py  RULE, _terminal, send_ok
    tools/autotrade.py  RULE, _terminal, lot_specs, sizing

Sebuah tool yang MENUTUP posisi mengimpor dari tool yang MEMBUKA posisi, dan
itu bukan hubungan yang masuk akal di antara keduanya. Yang sebenarnya terjadi
adalah permukaan broker memang dipakai bersama dan kebetulan tinggal di file
yang salah; `execute.py` sendiri jadi 1050 baris yang mencampur dua urusan,
yaitu memilih kandidat dan berbicara dengan terminal.

Pemisahannya murni pemindahan. Tidak ada satu baris logika yang berubah di
commit yang memindahkannya, supaya suite yang sudah hijau sebelum pemindahan
adalah verifikasi sesudahnya.

APA YANG MASUK KE SINI: admission terminal, predikat sukses retcode, pengiriman
satu order, pembacaan lot rules dan equity, dan pembacaan hasil harian. Semua
yang jawabannya datang dari MetaTrader.

APA YANG TIDAK: memilih zona, menyusun rencana, menerapkan gerbang, dan
mengurutkan kandidat. Itu keputusan, dan keputusan tetap di `execute.py`.
"""

from __future__ import annotations

from datetime import datetime

from app.clock import NY
from app.models import LotSpec, ZoneSide
from app.plan import DEPARTURE_GATE_ATR
from tools.costed import HORIZON


#: Penanda kepemilikan di sisi broker. Angkanya arbitrer dan itu tidak apa apa;
#: yang penting ia STABIL dan bukan nol, karena nol berarti "tidak ditandai" dan
#: itu persis keadaan yang membuat order Zonelab tidak bisa dibedakan dari order
#: tangan di terminal yang sama. 618 diambil dari POSKO 618.
#:
#: Dibaca juga oleh `tools/flatten.stale_pendings`, yang memakainya untuk
#: memutuskan pending mana yang boleh dibatalkan. Journal lokal tidak dipakai
#: untuk keputusan itu: ia gitignored dan tidak pernah direkonsiliasi dengan
#: broker, jadi ia bukan sumber yang aman untuk menyentuh order orang lain.
MAGIC = 618

#: MetaTrader truncates silently past this and `order_check` answers
#: `Invalid "comment" argument` without saying which argument or why. Measured on
#: the connected terminal 2026-08-21: 31 characters is accepted, 32 is not.
COMMENT_MAX = 31

#: What decision procedure produced a record. Stored on every journal line, so a
#: review months later can tell a change of market from a change of rule.
RULE = {
    "population": "first touch of a gate-clearing supply_demand zone, both sides",
    "gate": f"departure_atr >= {DEPARTURE_GATE_ATR}",
    "entry": "proximal, spread charged to the fill",
    "stop": "distal plus 0.25 ATR buffer",
    "target": "nearest live opposing zone (plan.target)",
    "exit_rule": "flat at the 21:00 UTC rollover",
    "horizon_bars": HORIZON,
}





def realised_today(mt5) -> float | None:
    """Hasil yang SUDAH terealisasi hari ini di akun, atau None kalau tak terbaca.

    Dibaca dari `history_deals_get` sejak tengah malam waktu NY, bukan dari
    journal: journal cuma tahu order yang tool ini kirim, sementara pengaman
    kerugian harian harus melihat SELURUH akun. Sebuah posisi yang dibuka
    dengan tangan lalu kena stop tetap mengosongkan equity yang sama.

    None, bukan nol, ketika terminal tidak menjawab. `Book.admits` menolak pada
    None: sebuah pengaman yang tidak bisa membaca harus berhenti, bukan
    menganggap hari ini bersih.
    """
    if mt5 is None:
        return None
    midnight = datetime.now(NY).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        deals = mt5.history_deals_get(midnight, datetime.now(NY))
    except Exception:  # noqa: BLE001 - terminal apa pun kesalahannya, jawabannya None
        return None
    if deals is None:
        return None
    # Profit sudah bersih dari commission dan swap pada deal penutup, dan
    # keduanya dijumlahkan terpisah karena deal pembuka membawa commission-nya
    # sendiri dengan profit nol.
    return float(sum(d.profit + d.commission + d.swap for d in deals))


def _terminal():
    """The connected terminal, or a refusal naming what is wrong.

    Imported here rather than at module scope so the rest of this file - and its
    tests - can be read on a machine with no MetaTrader installed.
    """
    import MetaTrader5 as mt5

    if not mt5.initialize():
        return None, f"cannot reach a MetaTrader 5 terminal: {mt5.last_error()}"
    account = mt5.account_info()
    if account is None:
        return None, f"terminal answered no account: {mt5.last_error()}"
    if account.trade_mode != 0:
        return None, (
            f"account {account.login} reports trade_mode={account.trade_mode}, "
            "and this tool sends orders to DEMO accounts only (0)"
        )
    if not account.trade_allowed:
        return None, f"account {account.login} has trading disabled in the terminal"
    return (mt5, account), ""


def send_ok(mt5, sent) -> tuple[bool, str]:
    """Apakah `order_send` berhasil. SATU tempat, karena dua tool salah sama.

    RETCODE 0 BERARTI DUA HAL BERLAWANAN DI DUA CALL BERBEDA:

      `order_check` sukses pada retcode 0 (TRADE_RETCODE_OK).
      `order_send`  sukses pada 10009 TRADE_RETCODE_DONE, atau 10008 PLACED
                    untuk pending. Retcode 0 dari `order_send` BUKAN sukses.

    Sampai 27 Agustus 2026 `execute.place` DAN `flatten.close` sama-sama menguji
    `sent.retcode != 0`. Akibatnya diukur, bukan dibayangkan: run 27 Agustus
    mengirim dua pending XAUUSD yang BERHASIL (ticket 4609944538 dan
    4609944542, keduanya ada di broker), mencetak
    `GAGAL: order_send retcode=10009 'ok'`, dan menulis dua record `refused`
    untuk order yang hidup. Yang lebih buruk, `book.held.append` cuma ada di
    jalur sukses, jadi cap portofolio tidak pernah melihat 21,61 USD risiko yang
    baru dikirim: satu cacat mematikan dua gate.

    10010 DONE_PARTIAL sengaja BUKAN sukses. Untuk pending order ia tidak
    seharusnya muncul, dan menghitungnya sukses akan menyembunyikan fill yang
    lebih kecil dari yang disizing.
    """
    if sent is None:
        return False, f"order_send answered nothing: {mt5.last_error()}"
    if sent.retcode not in {mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED}:
        return False, (f"order_send retcode={sent.retcode} "
                       f"{getattr(sent, 'comment', '')!r}")
    return True, ""


def place(mt5, zone, plan, symbol: str, volume: float) -> tuple[int | None, str]:
    """Send one pending order and return its ticket, or None and the reason.

    HARGA DIBULATKAN KE DIGIT SIMBOLNYA, dan sampai 29 Agustus 2026 tidak.
    Ketiga harga di-`round(..., 3)` mati, yang kebetulan benar untuk XAUUSD dan
    salah untuk tiap pasangan FX lima desimal di tabel biaya: EURUSD, GBPUSD,
    AUDUSD dan USDCAD semuanya terjangkau lewat `--symbol`. Entry 1,08234 jadi
    1,082, yaitu geseran 3,4 pip pada entry DAN stop sekaligus, jadi risk dan
    R-multiple rencananya berubah diam diam setelah gerbang menyetujuinya.

    Test penjaganya bernama `test_prices_are_rounded_to_the_symbol_s_digits` dan
    hanya menjalankan XAUUSD, jadi fixture-nya menyandi cacatnya. `live_ping.py`
    sudah melakukannya benar lewat `info.digits` sejak awal; jalur order tidak.

    SIMBOL YANG TIDAK TERBACA MENOLAK, tidak memakai default. Tanpa `digits`
    tidak ada cara membulatkan dengan benar, dan mengirim harga mentah ke
    terminal adalah cara lain untuk mendarat satu tick dari garis yang
    direncanakan.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        return None, (f"symbol_info tidak terbaca untuk {symbol}, jadi jumlah "
                      f"digit harganya tidak diketahui: {mt5.last_error()}")
    digits = int(info.digits)
    long_side = plan.side is ZoneSide.DEMAND
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY_LIMIT if long_side else mt5.ORDER_TYPE_SELL_LIMIT,
        "price": round(plan.entry, digits),
        "sl": round(plan.stop, digits),
        "tp": round(plan.target, digits),
        "type_time": mt5.ORDER_TIME_GTC,
        # RETURN, dan sengaja tidak dipilih dari `info.filling_mode`. Untuk
        # PENDING order inilah mode yang benar, dan jalur ini sudah terbukti
        # diterima broker (ticket 4609944538 dan 4609944542, 27 Agustus). Yang
        # dulu memilih buta adalah jalur MARKET di `tools/flatten.py`, dan itu
        # yang diperbaiki, bukan yang ini.
        "type_filling": mt5.ORDER_FILLING_RETURN,
        # KEPEMILIKAN DITANDAI DI SISI BROKER, bukan hanya di journal lokal.
        # Sampai sekarang `magic` tidak pernah diset, jadi satu satunya catatan
        # bahwa sebuah order milik Zonelab ada di `.journal/`, yang gitignored
        # dan tidak pernah direkonsiliasi. Hapus direktori itu dan tidak ada
        # yang tersisa yang bisa membedakan order kita dari order tangan.
        "magic": MAGIC,
        # Truncated here rather than at the call site: the terminal's own error
        # for an over-long comment does not mention length, and one debugging
        # session per caller is one too many.
        "comment": f"zonelab {zone.id}"[:COMMENT_MAX],
    }
    # `order_check` sukses pada 0, `order_send` TIDAK. Lihat `send_ok`.
    checked = mt5.order_check(request)
    if checked is None:
        return None, f"order_check refused to answer: {mt5.last_error()}"
    if checked.retcode != 0:
        return None, f"order_check retcode={checked.retcode} {checked.comment!r}"
    sent = mt5.order_send(request)
    ok, why_not = send_ok(mt5, sent)
    if not ok:
        return None, why_not
    return int(sent.order), ""


def sizing(account, lots: dict[str, LotSpec], risk_pct: float) -> float:
    """Equity dari terminal, dan cetak lot rules TIAP simbol apa adanya.

    Tidak lagi mengembalikan LotSpec. Itu tugas `lot_specs`, per simbol, karena
    satu spec untuk seluruh run adalah error 50x - lihat docstring di sana.
    """
    print(f"akun {account.login} {account.server} trade_mode={account.trade_mode} "
          f"(0=DEMO) equity {account.equity} risk {risk_pct:.1%}")
    for name, spec_ in sorted(lots.items()):
        print(f"  {name}: contract {spec_.contract_size} "
              f"min {spec_.volume_min} step {spec_.volume_step}")
    return float(account.equity)


def lot_specs(symbols: list[str]) -> tuple[dict[str, LotSpec], list[str]]:
    """Lot rules PER SIMBOL dari terminal, dan simbol mana yang tak terbaca.

    SATU CONTRACT SIZE UNTUK SELURUH RUN ADALAH ERROR 50x, dan itu hidup sampai
    27 Agustus 2026. `sizing` dipanggil sekali dengan
    `args.symbol.split(":")[-1]`, yang pada `mt5:XAUUSD,mt5:XAGUSD` menghasilkan
    string 'XAUUSD,mt5:XAGUSD', lalu satu LotSpec-nya di-broadcast ke semua
    simbol di baris 479. XAUUSD 100 unit per lot, XAGUSD 5000, jadi ke arah mana
    pun broadcast-nya jatuh, salah satunya salah 50x.

    Di dry run ia jatuh ke arah yang berbahaya. Silver dengan stop 0,651 dan
    0,01 lot terbaca 0,65 USD; angka sebenarnya 32,53. Gate risiko meloloskan
    tiga order silver yang, kalau terkirim, mempertaruhkan 3,3x anggarannya.

    READ ONLY. Handle terminal-nya TIDAK dikembalikan, jadi dry run dapat
    contract size yang benar tanpa ikut mendapat kemampuan mengirim apa pun.
    """
    bare = [s.split(":")[-1] for s in symbols]
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return {}, bare
    if not mt5.initialize():
        return {}, bare
    out: dict[str, LotSpec] = {}
    missing: list[str] = []
    for raw in symbols:
        name = raw.split(":")[-1]
        info = mt5.symbol_info(name)
        if info is None:
            missing.append(name)
            continue
        out[name] = LotSpec(contract_size=info.trade_contract_size,
                            volume_min=info.volume_min,
                            volume_max=info.volume_max,
                            volume_step=info.volume_step)
    return out, missing


