"""Turunkan tabel biaya per instrumen dari terminal, jangan mengarangnya.

    python -m tools.broker_costs            # cetak blok dict siap tempel
    python -m tools.broker_costs --check    # bandingkan tabel di app/costs.py

KENAPA FILE INI ADA, DAN INI TEMUAN YANG MAHAL. Sampai 22 Agustus 2026 hanya
XAUUSD punya baris biaya. Sebelas instrumen lain jatuh ke `_default`, yang
merupakan jadwal fee spot Binance: 20bp komisi plus 2bp slippage. Dibebankan ke
EURUSD, itu 22bp round turn untuk pair yang sebenarnya membayar sekitar 1,1bp.

Akibatnya bukan angka yang agak salah. Matrix pertama melaporkan EURUSD 1 jam
pada -0,422 R dengan t = -28,9 di 1.019 trade dan menyimpulkan "aturan ini gagal
di FX". Yang gagal adalah tabel biayanya. `row_for` sudah ada di `app/costs.py`
justru untuk membuat fallback ini kelihatan, dan harness barunya tidak pernah
mencetaknya.

APA YANG DIUKUR DAN APA YANG DIASUMSIKAN, dinyatakan karena keduanya bercampur:

  DIUKUR dari terminal
    contract size, point, harga, currency_profit  -> notional dalam USD
    swap_long dan swap_short dalam point          -> bp per malam
    spread median dari 20.000 bar 1 jam           -> bp, fallback saja

  DIUKUR dari deal yang benar-benar terjadi
    komisi XAUUSD: 0,07 USD pada 0,01 lot di harga 4604,221, jadi 7 USD per lot
    round turn, yaitu 0,152bp. Tabel lama menulis 0,25bp dengan alasan Exness
    Zero memungut 5,50 per sisi; akun ini memungut 3,50 per sisi.

  DIASUMSIKAN, dan ini satu-satunya asumsi
    7 USD per lot round turn berlaku sama untuk instrumen lain. Exness memungut
    komisi sebagai jumlah USD tetap per lot, jadi bentuknya benar; besarannya
    hanya terverifikasi di gold. Instrumen yang komisinya berbeda akan bergeser
    sebanding, dan `--check` yang akan menangkapnya begitu ada deal nyata.

  TIDAK DIBAWA
    `admin_bp`. Exness memungut 200 USD per lot per malam pada XAUUSD yang
    ditahan lewat 21:00 UTC, dan itu 4,545bp. Tidak ada bukti angka itu berlaku
    untuk FX atau indeks, jadi ia tetap hanya di baris gold. Kalau ternyata
    berlaku, EURUSD akan kena 17,1bp per malam dan setiap kesimpulan di
    QA-QUANT.md untuk FX berubah tanda. Itu lubang yang dinyatakan, bukan yang
    ditutup dengan dugaan.

SPREAD DARI HISTORI, BUKAN DARI JAM INI. `symbol_info.spread` pada hari Sabtu
adalah spread market tutup: XPTUSD terbaca 64,7bp saat tutup lawan 17,7bp median
histori. Angka yang dipakai untuk menghitung biaya sebuah trade harus datang dari
jam ketika trade itu mungkin terjadi.
"""

from __future__ import annotations

import argparse

import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - Windows only
    mt5 = None

from app.costs import BROKERS

#: Terukur di gold, diasumsikan untuk sisanya. Lihat docstring modul.
COMMISSION_USD_PER_LOT = 7.0

#: Terukur pada tick Dukascopy, bukan dikutip: mid bergerak 0,17bp pada median
#: round trip retail 250ms dan 0,79bp di p90. Sebuah stop adalah market order
#: begitu tersentuh DAN dipicu oleh gerakan searah, jadi angka sebenarnya
#: berbias merugikan di atas lantai tak bertanda itu. 0,5bp estimasi tengah.
SLIPPAGE_BP = 0.5

SYMBOLS = (
    "XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
    "GBPJPY", "AUDUSD", "USDCAD", "BTCUSD", "US30", "USOIL",
)


def usd_rate(currency: str) -> float | None:
    """Nilai satu unit `currency` dalam USD, dari pair mana pun yang ada.

    Dibutuhkan karena notional sebuah lot dihitung dalam QUOTE currency, dan
    komisi dibayar dalam USD. GBPJPY dengan contract 100.000 dan harga 216,95
    memberi 21,7 juta JPY, yang adalah 136.461 USD dan bukan 21,7 juta.
    """
    if currency == "USD":
        return 1.0
    for name in (f"{currency}USD", f"USD{currency}"):
        info = mt5.symbol_info(name)
        if info and (info.ask or info.bid):
            price = info.ask or info.bid
            return price if name.startswith(currency) else 1.0 / price
    return None


def row(symbol: str, spread_bars: int = 20_000) -> dict | None:
    """Baris biaya untuk satu simbol, seluruhnya dari terminal."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    if not info.visible:
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
    price = info.ask or info.bid
    if not price:
        return None
    rate = usd_rate(info.currency_profit)
    if rate is None:
        return None
    notional = info.trade_contract_size * price * rate
    bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, spread_bars)
    median_points = (
        float(np.median([b["spread"] for b in bars])) if bars is not None and len(bars)
        else 0.0
    )
    to_bp = info.point / price * 10_000
    return {
        "commission_bp": round(COMMISSION_USD_PER_LOT / notional * 10_000, 3),
        "slippage_bp": SLIPPAGE_BP,
        "spread_bp": round(median_points * to_bp, 3),
        "swap_bp": round(abs(info.swap_long) * to_bp, 3),
        "swap_bp_short": round(abs(info.swap_short) * to_bp, 3),
        "_notional_usd": round(notional, 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="bandingkan app/costs.py dengan terminal")
    parser.add_argument("--broker", default="exness_raw")
    args = parser.parse_args()

    if mt5 is None or not mt5.initialize():
        print("terminal MetaTrader 5 tidak terhubung")
        return 2

    rows = {s: row(s) for s in SYMBOLS}
    rows = {s: r for s, r in rows.items() if r}

    # Validasi terhadap satu angka yang benar-benar terukur dari deal nyata.
    # Kalau baris ini gagal, aritmetika notional-nya salah dan seluruh tabel
    # salah dengan cara yang tidak akan terlihat di angka mana pun.
    gold = rows.get("XAUUSD", {}).get("commission_bp")
    if gold is None or abs(gold - 0.152) > 0.002:
        print(f"VALIDASI GAGAL: komisi gold terhitung {gold}, deal nyata 0,152 bp. "
              "Aritmetika notional-nya salah, tabel di bawah tidak boleh dipakai.")
        mt5.shutdown()
        return 1
    print(f"validasi: komisi gold {gold:.3f} bp cocok dengan deal nyata 0,152 bp\n")

    if args.check:
        table = BROKERS.get(args.broker, {})
        print(f"{'symbol':9s} {'field':16s} {'app/costs.py':>13s} {'terminal':>10s} "
              f"{'selisih':>9s}")
        drift = 0
        for symbol, fresh in rows.items():
            have = table.get(symbol)
            if have is None:
                print(f"{symbol:9s} {'(tidak ada baris)':16s} "
                      f"{'-':>13s} {'-':>10s} {'JATUH KE _default':>9s}")
                drift += 1
                continue
            for field, value in fresh.items():
                if field.startswith("_"):
                    continue
                old = have.get(field)
                if old is None:
                    print(f"{symbol:9s} {field:16s} {'-':>13s} {value:10.3f}  baru")
                    drift += 1
                elif abs(old - value) > max(0.05, abs(value) * 0.2):
                    print(f"{symbol:9s} {field:16s} {old:13.3f} {value:10.3f} "
                          f"{value - old:+9.3f}")
                    drift += 1
        print(f"\n{drift} selisih di luar toleransi 20% atau 0,05bp")
        mt5.shutdown()
        return 1 if drift else 0

    print(f'    "{args.broker}": {{')
    for symbol, r in rows.items():
        print(f'        # notional 1 lot = {r["_notional_usd"]:,.0f} USD')
        body = ", ".join(f'"{k}": {v}' for k, v in r.items() if not k.startswith("_"))
        print(f'        "{symbol}": {{{body}}},')
    print("    },")
    mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
