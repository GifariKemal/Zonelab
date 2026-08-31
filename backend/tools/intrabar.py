"""Selesaikan trade di bar yang lebih halus, jangan menebak urutan di dalam bar.

    python -m tools.intrabar --symbol XAUUSD --interval 1h --fine 5m

MASALAH YANG DIJAWAB FILE INI, DAN INI MASALAH TERBESAR YANG DITEMUKAN 22
AGUSTUS 2026. Sebuah backtest yang membaca OHLC 1 jam tidak bisa tahu urutan
kejadian di dalam satu bar. Bar yang low-nya menyentuh proximal sebuah demand
zone DAN high-nya mencapai target bisa berarti dua hal yang berlawanan:

  naik dulu lalu jatuh   -> target tercapai SEBELUM entry terisi, jadi bukan menang
  jatuh dulu lalu naik   -> entry terisi lalu target tercapai, jadi menang

`tools/costed.py` memilih yang kedua secara implisit, dan diukur pada 6.569
trade di 8 sel: 62% sampai 68% PEMENANG diselesaikan di bar entry sendiri lawan
hanya 20% sampai 40% yang KALAH. Asimetri sebesar itu bukan sifat pasar, itu
sifat asumsi. Mematikan pembayaran di bar entry membalik ekspektasi gabungan
dari +0,2021 R menjadi -0,0590 R.

Dua-duanya salah, dan itu sebabnya file ini ada. Mengizinkan target di bar entry
mengarang kemenangan; melarangnya membuang kemenangan yang benar-benar terjadi.
Yang bisa memutuskan hanya data yang lebih halus, dan terminal ini punya:

    XAUUSD  M5  99.999 bar, 514 hari      M1  99.999 bar, 101 hari
    EURUSD  M5  99.999 bar, 488 hari      M1  99.999 bar,  96 hari

CARA KERJANYA. Zona tetap dideteksi di timeframe aslinya, jadi gambarnya tidak
berubah. Yang berubah hanya penyelesaiannya: dari bar entry ke depan, harga
dibaca di bar halus, entry diisi di bar halus pertama yang menyentuh proximal,
dan stop atau target diputuskan oleh bar halus mana yang lebih dulu. Ambiguitas
tidak hilang, ia menyusut dari 60 menit menjadi 5.

YANG MASIH DIASUMSIKAN, dinyatakan. Di dalam satu bar 5 menit yang memuat stop
dan target sekaligus, stop tetap dianggap lebih dulu. Itu arah konservatif dan
sama dengan konvensi `costed.py`.
"""

from __future__ import annotations

import argparse

import numpy as np

from app.costs import cost_to_risk, schedule
from app.detect import DETECTORS
from app.indicators import wilder_atr
from app.models import ZoneSide
from app.plan import build
from app.profit_zone import profit_zone_at
from app.providers.base import INTERVALS
from tools import history
from tools.calibrate import POPULATION
from tools.costed import HORIZON, ROLLOVER_HOUR_UTC, rollovers, trades
from tools.quant import BROKER, clean, metrics

#: Timeframe halus yang dipakai menyelesaikan, per timeframe zona. Bukan pilihan
#: gaya: makin halus makin sedikit riwayatnya, jadi ini titik seimbang antara
#: presisi dan jumlah trade yang bisa dinilai.
FINER = {"1h": "5m", "4h": "15m", "15m": "1m"}


def _venue(symbol: str, source: str) -> str:
    """`symbol` dengan prefix venue.

    `source` ADALAH PREFIX `history.load`, bukan nama venue bebas. Yang dikenal
    cuma `mt5` dan `yahoo`; Binance dan Dukascopy adalah routing untuk simbol
    TELANJANG, jadi keduanya dipilih dengan `source=""`. Menamainya "binance"
    akan terbaca benar dan menghasilkan `binance:BTCUSDT`, yang dijawab
    Binance dengan HTTP 400.
    """
    if ":" in symbol or not source:
        return symbol
    return f"{source}:{symbol}"


def resolved(symbol: str, interval: str, fine: str, bars: int = 99_999,
             flat: bool = True, entry_depth: float = 0.0,
             breakeven_at: float | None = None,
             source: str = "mt5") -> list[dict]:
    """Trade yang sama, diselesaikan di bar `fine`.

    Zona, entry, stop, target dan biaya dihitung persis seperti `costed.trades`.
    Satu-satunya perbedaan adalah walk-nya berjalan di bar halus, dan itu memang
    seluruh maksudnya: dua angka yang hanya berbeda di satu aturan bisa
    dibandingkan, tiga yang berbeda tidak.
    """
    candles, _, _ = clean(symbol, interval, bars, source)
    # SUMBER YANG SAMA UNTUK BAR KASAR DAN BAR HALUS, selalu. `quant.clean`
    # di atas juga memakai prefix ini, dan itu bukan kebetulan: `tools/history.py`
    # sudah mencatat bahwa `mt5:XAUUSD`, `yahoo:XAUUSD` dan `XAUUSD` telanjang
    # adalah tiga INSTRUMEN berbeda, terukur 56 dolar berjarak pada menit yang
    # sama. Menyelesaikan trade venue A memakai bar halus venue B adalah cacat
    # itu, cuma di dalam satu fungsi.
    #
    # `source` DEFAULT `mt5` supaya setiap pemanggil yang sudah ada menjawab
    # angka yang persis sama. Ia ada untuk satu hal: mereplikasi sebuah hasil di
    # venue kedua, yang `docs/walkforward.json` lawan `docs/walkforward-mt5.json`
    # lakukan untuk `supply_demand` dan belum pernah dilakukan untuk detector
    # lain.
    small = history.load(_venue(symbol, source), fine, 99_999)
    if not small:
        return []
    # Hanya rentang yang dipunyai KEDUANYA. Bar halus jauh lebih pendek
    # riwayatnya, jadi trade yang lebih tua dari itu tidak bisa dinilai dan
    # dibuang alih-alih diselesaikan dengan aturan lama secara diam-diam.
    first_fine = small[0].time
    fees = schedule(symbol, False, BROKER)
    params = POPULATION
    from app.models import SupplyDemandParams
    p = SupplyDemandParams(**{**params, "show_broken": True})
    zones, _ = DETECTORS["supply_demand"](candles, p)

    time = np.array([c.time for c in candles], dtype=np.int64)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, p.atr_period)
    index_of = {int(t): i for i, t in enumerate(time)}
    step = INTERVALS[interval]

    ft = np.array([c.time for c in small], dtype=np.int64)
    fhigh = np.array([c.high for c in small])
    flow = np.array([c.low for c in small])
    fclose = np.array([c.close for c in small])

    out: list[dict] = []
    unfilled: list[str] = []
    for zone in zones:
        if zone.first_test_time is None:
            continue
        touch = index_of.get(zone.first_test_time)
        if touch is None or touch < 1 or touch + HORIZON >= len(close):
            continue
        if int(time[touch]) < first_fine:
            continue
        scale = float(atr[touch - 1])
        if scale <= 0:
            continue
        at_touch = zone.model_copy(update={
            "profit_zone_rr": profit_zone_at(zone, zones, int(time[touch]))
        })
        spread = candles[touch].spread
        if spread is None and fees.get("spread_bp") is not None:
            spread = float(close[touch]) * fees["spread_bp"] / 10_000
        plan = build(at_touch, scale, int(time[touch]), step, spread=spread)
        if plan is None or plan.target is None:
            continue

        long_side = zone.side is ZoneSide.DEMAND

        # ATURAN A, praregistrasi 22 Agustus 2026. Entry dipindah ke dalam zona
        # sebagai fraksi tingginya: 0,0 adalah proximal (baseline) dan 0,5 adalah
        # ekuilibrium zona. Stop tidak bergerak, jadi risk per unit MENYUSUT dan
        # satuan R berubah. Itu sebabnya total R ikut dilaporkan: R yang lebih
        # kecil bisa menaikkan ekspektasi tanpa menaikkan uang.
        entry_price = plan.entry
        if entry_depth > 0:
            entry_price = plan.entry + entry_depth * (plan.stop - plan.entry) * (
                abs(zone.proximal - zone.distal)
                / max(abs(plan.stop - plan.entry), 1e-12)
            )
            # Ditulis lewat tinggi ZONA dan bukan lewat jarak ke stop, karena
            # stop membawa buffer 0,25 ATR di luar zona: memakai jarak ke stop
            # akan membuat "50%" berarti sesuatu yang berbeda untuk tiap zona.
        risk_leg = abs(entry_price - plan.stop)
        if risk_leg <= 0:
            continue

        nights = (HORIZON * step) / 86_400
        swap_bp = fees.get("swap_bp", 0.0)
        if plan.side is ZoneSide.SUPPLY and "swap_bp_short" in fees:
            swap_bp = fees["swap_bp_short"]
        ratio, friction = cost_to_risk(float(close[touch]), risk_leg,
                                       spread or 0.0, fees, nights, swap_bp=swap_bp)
        risk = risk_leg + friction
        if risk <= 0:
            continue

        # Jendela waktu yang sama dengan arm 1 jam: dari bar entry sampai
        # horizon, dipotong rollover kalau aturannya flat.
        start_at = int(time[touch])
        end_at = int(time[min(touch + HORIZON, len(time) - 1)]) + step
        if flat:
            shift = ROLLOVER_HOUR_UTC * 3600
            cut = ((start_at - shift) // 86_400 + 1) * 86_400 + shift
            end_at = min(end_at, cut)
        lo = int(np.searchsorted(ft, start_at, "left"))
        hi = int(np.searchsorted(ft, end_at, "left"))
        if hi <= lo:
            continue

        # ENTRY DIISI DI BAR HALUS, bukan diasumsikan terisi di awal bar besar.
        fill = None
        for j in range(lo, hi):
            reached = flow[j] <= entry_price if long_side else fhigh[j] >= entry_price
            if reached:
                fill = j
                break
        if fill is None:
            # DUA SEBAB, dan keduanya harus dihitung. Kalau `entry_depth` nol,
            # ini berarti riwayat halus punya lubang di jam itu. Kalau tidak, ini
            # berarti harga menyentuh proximal dan berbalik tanpa pernah mencapai
            # entry yang lebih dalam, yaitu limit yang TIDAK TERISI. Limit yang
            # tidak terisi bukan trade, dan menghitungnya sebagai nol adalah cara
            # backtest mencuri, jadi ia dicatat sebagai baris tersendiri.
            unfilled.append(zone.id)
            continue

        result = None
        exit_j = hi - 1
        stop_now = plan.stop
        best_r = 0.0
        moved = False
        for j in range(fill, hi):
            # ATURAN B, praregistrasi 22 Agustus 2026. Excursion menguntungkan
            # dihitung SEBELUM memeriksa stop, karena kalau satu bar halus memuat
            # keduanya maka urutannya kembali tidak diketahui, dan arah
            # konservatifnya adalah stop yang menang. Jadi breakeven hanya
            # dipasang oleh bar yang SUDAH lewat, bukan oleh bar yang sedang
            # menutup posisi ini.
            hit_stop = flow[j] <= stop_now if long_side else fhigh[j] >= stop_now
            hit_target = (fhigh[j] >= plan.target if long_side
                          else flow[j] <= plan.target)
            if hit_stop:
                # SATU RUMUS UNTUK KEDUA KASUS. Gerakan bertanda dari entry ke
                # stop yang sedang berlaku, dikurangi friction, dibagi risk.
                # Untuk stop yang belum dipindah, gerakannya persis -risk_leg,
                # jadi hasilnya -1,0 dengan sendirinya; untuk stop di breakeven,
                # gerakannya nol dan yang tersisa hanya biayanya. Versi pertama
                # menuliskan tiga cabang untuk aritmetika yang satu ini, dan dua
                # di antaranya tidak pernah benar untuk sisi short.
                move = ((stop_now - entry_price) if long_side
                        else (entry_price - stop_now))
                result = (move - friction) / risk
                exit_j = j
                break
            if hit_target:
                result = (abs(plan.target - entry_price) - friction) / risk
                exit_j = j
                break
            up = (fhigh[j] - entry_price) if long_side else (entry_price - flow[j])
            best_r = max(best_r, up / risk)
            if breakeven_at is not None and not moved and best_r >= breakeven_at:
                stop_now = entry_price
                moved = True
        if result is None:
            exit_at = float(fclose[hi - 1])
            move = (exit_at - entry_price) if long_side else (entry_price - exit_at)
            result = (move - friction) / risk

        nights_held = int(rollovers(int(ft[fill]), int(ft[exit_j])))
        admin = float(close[touch]) * fees.get("admin_bp", 0.0) / 10_000
        if admin and nights_held:
            result -= admin * nights_held / risk

        out.append({
            "skipped": False, "at": touch, "exit": touch,
            "zone_id": zone.id, "kind": zone.kind.value, "side": zone.side.value,
            "r": result, "nights": nights_held, "cost_r": ratio,
            "won": result > 0, "cleared": zone.departure_atr >= 2.0,
            "departure": zone.departure_atr,
            "fine_bars_to_fill": fill - lo,
            "fine_bars_held": exit_j - fill,
            "entry_depth": entry_depth,
            "breakeven_moved": moved,
            "mfe_r": best_r,
        })
    if unfilled:
        print(f"  {len(unfilled)} zona tersentuh proximal tapi entry-nya tidak "
              f"terisi (depth {entry_depth})")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--fine", default="")
    args = parser.parse_args()
    fine = args.fine or FINER.get(args.interval, "5m")

    fine_rows = [r for r in resolved(args.symbol, args.interval, fine)
                 if r["cleared"]]
    if not fine_rows:
        print("tidak ada trade yang bisa diselesaikan di bar halus")
        return 1
    ids = {r["zone_id"] for r in fine_rows}

    candles, _, _ = clean(args.symbol, args.interval)
    arms = {}
    for label, same in (("izinkan bar entry", True), ("tunda bar entry", False)):
        rows = [x for x in trades("supply_demand", candles, args.interval, True,
                                  symbol=args.symbol, broker=BROKER,
                                  flat_by_rollover=True, same_bar_target=same)
                if not x["skipped"] and x["cleared"] and x["zone_id"] in ids]
        arms[label] = rows

    print(f"{args.symbol} {args.interval}, diselesaikan di {fine}. "
          f"{len(fine_rows)} trade yang riwayat halusnya ada.\n")
    print(f"{'aturan penyelesaian':22s} {'n':>5s} {'exp R':>8s} {'t':>7s} "
          f"{'win':>7s} {'total R':>9s}")
    for label, rows in arms.items():
        m = metrics(rows)
        print(f"{label:22s} {m['n']:5d} {m['exp_r']:+8.3f} {m['t']:+7.2f} "
              f"{m['win_rate']:6.1%} {m['total_r']:+9.1f}")
    m = metrics(fine_rows)
    print(f"{'bar ' + fine + ' (kebenaran)':22s} {m['n']:5d} {m['exp_r']:+8.3f} "
          f"{m['t']:+7.2f} {m['win_rate']:6.1%} {m['total_r']:+9.1f}")

    fills = np.array([r["fine_bars_to_fill"] for r in fine_rows])
    held = np.array([r["fine_bars_held"] for r in fine_rows])
    print(f"\nentry terisi setelah median {np.median(fills):.0f} bar {fine} "
          f"dari awal bar {args.interval} (p90 {np.percentile(fills, 90):.0f})")
    print(f"trade selesai setelah median {np.median(held):.0f} bar {fine} "
          f"(p90 {np.percentile(held, 90):.0f})")
    same_big_bar = (held < INTERVALS[args.interval] // INTERVALS[fine]).mean()
    print(f"{same_big_bar:.1%} selesai masih di dalam bar {args.interval} yang sama")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
