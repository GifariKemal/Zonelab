"""Ukur biaya menahan posisi melewati rollover, jangan mengutipnya.

    python -m tools.carry_probe --open      # buka posisi minimum, butuh market buka
    python -m tools.carry_probe --read      # baca yang dipungut

PERTANYAAN YANG DIJAWAB. `app/costs.py` membawa `admin_bp` 4,545 untuk XAUUSD,
yaitu 200 USD per lot per malam yang Exness pungut pada posisi yang ditahan lewat
21:00 UTC. Angka itu dikutip dari Help Center, dan tiga hal tentangnya belum
pernah diverifikasi di akun ini:

  1. apakah ia benar-benar dipungut di akun Raw Spread ini;
  2. apakah ia berlaku di luar gold. Kalau ya, EURUSD kena 17,1bp per malam dan
     setiap kesimpulan FX di `docs/QA-QUANT.md` berubah tanda;
  3. apakah ia dipungut per malam atau sekali.

TIDAK ADA DI API. `symbol_info` hanya mengekspos `swap_long`, `swap_short`,
`swap_mode` dan `swap_rollover3days`. Admin fee adalah biaya diskresioner broker,
bukan properti simbol, jadi satu-satunya cara mengetahuinya adalah menahan posisi
dan membaca yang didebit.

CARANYA BISA MEMBEDAKAN KEDUANYA, dan itu yang membuat probe ini ada. Untuk 0,01
lot XAUUSD long:

    swap saja        555,7 point x 0,001 x 100 x 0,01  = 0,556 USD
    plus admin fee   ditambah 200 x 0,01               = 2,556 USD

Selisih 4,6 kali, jadi satu malam sudah cukup untuk memutuskan. Sisi LONG yang
dipakai untuk gold karena `swap_short` di akun ini nol, jadi sisi short tidak bisa
membedakan apa pun.

DEMO SAJA. `trade_mode` harus 0, sama seperti `tools/execute.py`, dan tidak ada
flag untuk melewatinya.
"""

from __future__ import annotations

import argparse
import datetime as dt

import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - Windows only
    mt5 = None

#: Instrumen yang diprobe, dan alasannya masing-masing. Gold karena `admin_bp`
#: memang terdokumentasi untuknya; EURUSD karena pertanyaan mahalnya adalah
#: apakah fee itu meluas ke FX; BTCUSD karena crypto sering dikenai aturan
#: pembiayaan yang berbeda lagi.
PROBES = (("XAUUSD", "buy"), ("EURUSD", "buy"), ("BTCUSD", "buy"))

VOLUME = 0.01
COMMENT = "zonelab carry probe"

#: Peluang sebuah probe BERTAHAN sampai rollover, dipakai memilih jarak stop.
#: Bukan angka bulat yang enak: stop yang cukup rapat untuk berarti adalah stop
#: yang bisa mengakhiri pengukuran sebelum ia mengukur apa pun, jadi jaraknya
#: dipilih dari sebaran excursion instrumen itu sendiri.
#:
#: Diukur pada BTCUSD 22 Agustus 2026, 48.280 jendela 19 jam:
#:
#:     stop 5%   terpicu di 7,31% jendela   rugi 4,0% equity
#:     stop 8%   terpicu di 2,53% jendela   rugi 6,4% equity
#:     stop 10%  terpicu di 1,45% jendela   rugi 8,0% equity
#:     terburuk yang pernah terjadi: -59,44%
#:
#: Volume sudah di minimum broker, jadi stop adalah satu-satunya tuas. Yang lebih
#: rapat dipilih karena probe bisa diulang besok kalau kena stop, sementara
#: kerugian tanpa batas tidak bisa diperbaiki.
SURVIVE = 0.95

#: Peluang sebuah probe tidak ditutup oleh TARGET-nya. Jauh lebih tinggi dari
#: SURVIVE karena target yang kena juga menghancurkan pengukuran, dan tidak ada
#: alasan mengejar profit pada posisi yang ada untuk membaca satu biaya.
SURVIVE_UP = 0.995

#: Jam sampai rollover 21:00 UTC berikutnya, dibulatkan naik. Jendela inilah
#: yang harus dilewati posisi probe.
HOURS = 19


def _terminal():
    """Terminal yang terhubung DAN demo, atau None."""
    if mt5 is None or not mt5.initialize():
        print("terminal MetaTrader 5 tidak terhubung")
        return None
    info = mt5.account_info()
    if info is None:
        print("tidak bisa membaca account_info")
        return None
    if info.trade_mode != 0:
        print(f"BUKAN akun demo (trade_mode={info.trade_mode}). Berhenti.")
        return None
    return info


def expected_swap(symbol: str, volume: float, long_side: bool) -> float:
    """Swap yang seharusnya dipungut untuk satu malam, dari `symbol_info`.

    Dalam mode point (`swap_mode == 1`), nilainya adalah point kali nilai satu
    point untuk volume itu: `point * contract_size * volume`.
    """
    info = mt5.symbol_info(symbol)
    if info is None or info.swap_mode != 1:
        return float("nan")
    points = info.swap_long if long_side else info.swap_short
    return points * info.point * info.trade_contract_size * volume


def bracket(symbol: str, hours: int = HOURS) -> tuple[float, float]:
    """Fraksi stop dan target, diukur dari riwayat instrumen itu sendiri.

    Dikembalikan sebagai fraksi harga, bukan persen bulat. 5% adalah jarak yang
    benar untuk BTCUSD dan absurd untuk EURUSD, jadi mengetik satu angka untuk
    keduanya berarti satu dari dua probe akan salah.

    Yang diukur adalah EXCURSION TERBURUK dalam `hours` jam, bukan perubahan
    close: stop dipicu oleh low, dan sebuah jendela yang turun 6% lalu pulih
    ditutup datar sambil tetap mengeluarkan posisi.
    """
    bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 99_999)
    if bars is None or len(bars) < hours + 100:
        # Tanpa riwayat yang cukup, tidak ada angka yang bisa dipertahankan.
        # Nilai bawaan dinyatakan sebagai apa adanya: tebakan, dan dipakai hanya
        # supaya posisi tidak pernah lahir tanpa bracket.
        return 0.05, 0.15
    close = np.array([b["close"] for b in bars], dtype=float)
    low = np.array([b["low"] for b in bars], dtype=float)
    high = np.array([b["high"] for b in bars], dtype=float)
    n = len(close) - hours
    down = np.array([(low[i:i + hours].min() - close[i]) / close[i]
                     for i in range(n)])
    up = np.array([(high[i:i + hours].max() - close[i]) / close[i]
                   for i in range(n)])
    sl = abs(float(np.percentile(down, (1 - SURVIVE) * 100)))
    tp = float(np.percentile(up, SURVIVE_UP * 100))
    return sl, tp


def open_probes() -> int:
    account = _terminal()
    if account is None:
        return 2
    sent = 0
    for symbol, side in PROBES:
        info = mt5.symbol_info(symbol)
        if info is None or not mt5.symbol_select(symbol, True):
            print(f"{symbol}: tidak ada di terminal")
            continue
        info = mt5.symbol_info(symbol)
        # Market tutup terlihat di `trade_mode` simbol, bukan di harga. Sebuah
        # `order_send` pada market tutup menjawab retcode yang tidak menyebut
        # sebabnya, jadi penolakannya dibuat di sini supaya alasannya terbaca.
        if info.trade_mode == 0:
            print(f"{symbol}: trading dinonaktifkan untuk simbol ini")
            continue
        price = info.ask if side == "buy" else info.bid
        if not price:
            print(f"{symbol}: tidak ada harga, market kemungkinan tutup")
            continue
        # BRACKET SELALU ADA, dan probe pertama lahir tanpanya. Dibuka 22
        # Agustus 2026 dengan sl dan tp nol pada notional 787 USD di akun 980
        # USD, yaitu 80% equity tanpa batas kerugian. Itu kelalaian, bukan
        # keputusan: sebuah posisi yang dibuka untuk membaca satu biaya tetap
        # sebuah posisi.
        sl_pct, tp_pct = bracket(symbol)
        long_side = side == "buy"
        sl = round(price * (1 - sl_pct) if long_side else price * (1 + sl_pct),
                   info.digits)
        tp = round(price * (1 + tp_pct) if long_side else price * (1 - tp_pct),
                   info.digits)
        print(f"{symbol}: bracket terukur, stop {sl_pct:.2%} ({sl}) "
              f"target {tp_pct:.2%} ({tp})")
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": VOLUME,
            "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 50,
            "comment": COMMENT,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        check = mt5.order_check(request)
        if check is None or check.retcode != 0:
            print(f"{symbol}: order_check menolak, "
                  f"{getattr(check, 'retcode', '?')} {getattr(check, 'comment', '')}")
            continue
        result = mt5.order_send(request)
        # RETCODE SENDIRI TIDAK CUKUP, dan itu terukur. Dijalankan Sabtu 22
        # Agustus 2026: BTCUSD menjawab retcode 0 dengan comment 'ok' dan
        # POSISINYA BENAR-BENAR TERBUKA, sementara XAUUSD menjawab retcode 0
        # dengan comment 'Done' dan tidak membuka apa pun karena market tutup.
        # Nol yang sama untuk dua hasil yang berlawanan. Jadi yang menentukan
        # adalah apakah posisinya ada, bukan apa yang dikatakan retcode-nya.
        opened = [x for x in (mt5.positions_get(symbol=symbol) or [])
                  if COMMENT in x.comment]
        if not opened:
            print(f"{symbol}: tidak terbuka. retcode "
                  f"{getattr(result, 'retcode', '?')} "
                  f"{getattr(result, 'comment', '')!r}, kemungkinan market tutup")
            continue
        newest = max(opened, key=lambda x: x.time)
        print(f"{symbol}: terbuka tiket {newest.ticket} {newest.volume} lot "
              f"{side} di {newest.price_open} sl={newest.sl} tp={newest.tp}")
        if not (newest.sl and newest.tp):
            print(f"  PERINGATAN: posisi {newest.ticket} tidak membawa bracket. "
                  "Pasang manual atau tutup.")
        sent += 1
    print(f"\n{sent} posisi probe dibuka. Baca lagi SETELAH 21:00 UTC berikutnya "
          "dengan --read.")
    mt5.shutdown()
    return 0 if sent else 1


def read_probes() -> int:
    account = _terminal()
    if account is None:
        return 2
    positions = [p for p in (mt5.positions_get() or []) if COMMENT in p.comment]
    if not positions:
        print("tidak ada posisi probe yang terbuka. Jalankan --open dulu.")
        mt5.shutdown()
        return 1
    now = dt.datetime.now(dt.UTC)
    print(f"sekarang {now:%Y-%m-%d %H:%M} UTC\n")
    print(f"{'symbol':8s} {'tiket':>10s} {'dibuka':>16s} {'malam':>6s} "
          f"{'swap terpungut':>15s} {'swap diharapkan':>16s} {'sisa':>9s}")
    for p in positions:
        opened = dt.datetime.fromtimestamp(p.time, dt.UTC)
        # Rollover yang dilewati, dihitung dari jam 21:00 UTC dan bukan dari
        # kehadiran bar: gold tidak punya bar 21:00 sama sekali karena jam itu
        # ADALAH jeda sesi hariannya.
        nights = 0
        cursor = opened
        while True:
            shift = dt.timedelta(hours=21)
            nxt = (cursor - shift).replace(hour=0, minute=0, second=0,
                                           microsecond=0) + shift + dt.timedelta(days=1)
            if nxt > now:
                break
            nights += 1
            cursor = nxt
        long_side = p.type == mt5.POSITION_TYPE_BUY
        want = expected_swap(p.symbol, p.volume, long_side) * max(nights, 0)
        rest = p.swap - want
        print(f"{p.symbol:8s} {p.ticket:10d} {opened:%m-%d %H:%M} UTC {nights:6d} "
              f"{p.swap:15.4f} {want:16.4f} {rest:+9.4f}")
    print("\nKolom 'sisa' adalah yang dipungut DI LUAR swap. Nol berarti tidak ada "
          "admin fee di akun ini; sekitar -2,00 per 0,01 lot berarti 200 USD per "
          "lot per malam memang berlaku.")
    print("Kalau 'malam' nol, posisinya belum melewati rollover dan barisnya "
          "belum mengukur apa pun.")
    mt5.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true", help="buka posisi probe")
    parser.add_argument("--read", action="store_true", help="baca yang dipungut")
    parser.add_argument("--dry", action="store_true",
                        help="cetak bracket terukur, jangan kirim apa pun")
    args = parser.parse_args()
    if args.dry:
        # SATU CHECK YANG BISA DIJALANKAN. Seluruh logika file ini adalah satu
        # persentil atas data terminal, dan mode ini yang membuatnya bisa
        # diperiksa tanpa membuka posisi apa pun.
        if _terminal() is None:
            return 2
        print(f"{'symbol':9s} {'stop':>8s} {'target':>8s} {'harga':>12s} "
              f"{'stop di':>12s} {'target di':>12s}")
        bad = 0
        for symbol, side in PROBES:
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
            if info is None:
                print(f"{symbol:9s} tidak ada"); bad += 1; continue
            price = info.ask or info.bid or 0.0
            sl_pct, tp_pct = bracket(symbol)
            if not (0 < sl_pct < 0.5 and 0 < tp_pct < 1.0):
                print(f"{symbol:9s} bracket TIDAK MASUK AKAL "
                      f"{sl_pct:.2%}/{tp_pct:.2%}")
                bad += 1
                continue
            print(f"{symbol:9s} {sl_pct:8.2%} {tp_pct:8.2%} {price:12.2f} "
                  f"{price * (1 - sl_pct):12.2f} {price * (1 + tp_pct):12.2f}")
        mt5.shutdown()
        return 1 if bad else 0
    if args.open:
        return open_probes()
    if args.read:
        return read_probes()
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
