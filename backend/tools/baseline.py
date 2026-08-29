"""Apakah kotaknya lebih baik daripada TIDAK ADA KOTAK SAMA SEKALI.

    python -m tools.baseline --cells XAUUSD:1h,EURUSD:1h --json ../docs/baseline.json

SATU-SATUNYA KONTROL YANG BELUM PERNAH DIJALANKAN DI SINI, dan `docs/CALIBRATION.md`
menamainya sendiri. Setiap kontrol yang sudah ada di proyek ini adalah KOTAK YANG
DIPINDAH: placebo acak menggeser kotak sejauh kelipatan tingginya sendiri,
placebo berjangkar membangun ulang kotak di sekitar swing yang tidak berhubungan.
Keduanya menjawab "kotak di sini lebih baik daripada kotak di sana". Tidak satu
pun menjawab "kotak lebih baik daripada TANPA kotak".

Huang dkk. menunjukkan laba momentum disamai baseline bebas-sinyal. Yang
digeneralisasi: sistem yang labanya bisa direproduksi baseline bebas-sinyal belum
membuktikan keunggulan. Baseline itu yang dibangun di file ini.

EMPAT HAL YANG HARUS SAMA, ATAU INI BUKAN KONTROL
  frekuensi   satu draw per trade nyata, di deret dan jendela yang sama. Arm yang
              trading sepuluh kali lebih sering bukan kontrol, ia strategi lain.
  geometri    pasangan (tinggi zona dalam ATR, reward multiple) diambil UTUH dari
              trade nyata, bukan dari dua distribusi marginal terpisah - keduanya
              berkorelasi, dan mengambilnya terpisah akan mengarang bracket yang
              tidak pernah digambar.
  resolver    `tools.intrabar.resolved` ITU SENDIRI, bukan salinannya. Lihat
              `_inject` di bawah untuk caranya.
  biaya       `app/costs.py` lewat jalur yang sama, karena resolver-nya sama.

CARA "RESOLVER YANG SAMA" DICAPAI, DAN INI KEPUTUSAN DESAIN UTAMANYA.
`resolved` mengambil zona dari `DETECTORS["supply_demand"]` dan jalan raya
targetnya dari `profit_zone_at`. Dua nama itu adalah SATU-SATUNYA tempat sinyal
masuk ke dalamnya. `_inject` menukar keduanya untuk satu panggilan: detektor
mengembalikan zona sintetis yang sudah digambar di file ini, dan `profit_zone_at`
mengembalikan reward multiple yang sudah ditempelkan ke zona itu. Selebihnya
(fill di bar halus, urutan stop lawan target, friction, hitungan rollover, biaya
admin) dijalankan oleh kode yang sama persis, baris yang sama, jadi selisih
antara kedua arm tidak bisa berasal dari dua resolver.

Ditulis begitu karena alternatifnya menyalin walk-nya ke sini, dan proyek ini
sudah punya satu insiden di mana dua gerbang bernama sama hidup berdampingan
berbulan-bulan dengan aturan berbeda (`docs/CALIBRATION.md`, KOREKSI 2026-08-17).

TIGA KEPUTUSAN YANG HARUS DINYATAKAN, LENGKAP DENGAN YANG TIDAK DIKENDALIKANNYA.

1. WAKTU ENTRY. Dua kebijakan dijalankan berdampingan, karena satu saja tidak
   cukup jujur.

   `uniform` menarik bar entry seragam dari seluruh bar yang memenuhi syarat.
   Yang ia kendalikan: lokasi harga. Yang TIDAK ia kendalikan: komposisi sesi dan
   clustering volatilitas. Arm nyata hanya trading saat harga TIBA di sebuah
   level, dan kedatangan itu tidak seragam dalam waktu - ia menumpuk di jam
   London dan New York, dan di bar yang sedang bergerak. Jadi arm `uniform` bisa
   kalah semata karena ia juga trading di jam Asia yang sepi.

   `hour` menambal persis satu dari dua lubang itu: jam UTC ditarik dari
   histogram jam entry arm nyata, lalu bar ditarik seragam DI DALAM jam itu. Yang
   masih TIDAK dikendalikan sesudahnya: clustering volatilitas di dalam jam yang
   sama, dan fakta bahwa arm nyata masuk saat harga sedang bergerak MENUJU sebuah
   level. Baseline yang mengendalikan itu juga akan mulai memakai informasi harga
   lokal, dan pada titik itu ia berhenti menjadi baseline bebas-sinyal.

   Yang KEDUANYA tidak kendalikan: arm nyata memasang limit di garis proximal
   yang harganya sudah pernah berbalik di sana. Baseline memasang limit di CLOSE
   BAR SEBELUMNYA. Itu level yang knowable pada awal bar entry (memakai close bar
   entry sendiri akan lookahead: fill di bar halus bisa terjadi sebelum bar besar
   itu ditutup), tetapi ia bukan ekstrem wick. Placebo berjangkar di
   `tools/costed.py` yang menguji sisi itu, dan file ini tidak mengulanginya.

2. ARAH. Sisi TIDAK dilempar koin. Ia ditarik dari pasangan geometri yang sama
   dengan tinggi dan reward-nya, jadi campuran demand/supply baseline sama dengan
   campuran arm nyata.

   Alasannya biaya, dan ini terukur: swap XAUUSD long -1,20bp per malam, short
   NOL (`app/costs.py`). Koin 50/50 di atas arm nyata yang mayoritas long akan
   membayar tagihan swap yang berbeda, dan syarat keempat di atas menuntut biaya
   yang sama. Arah juga bukan yang sedang diuji: dua belas hipotesis arah
   praregistrasi sudah gagal di proyek ini.

   Yang TIDAK dikendalikan karenanya: pertanyaan "apakah demand-long mengalahkan
   supply-short" tidak dijawab file ini. Baseline ini menguji LOKASI, bukan sisi.

3. JUMLAH DRAW DAN SEED. `SEED` konstanta modul, eksplisit, tanpa `hash()` dan
   tanpa jam. Proyek ini punya insiden provider yang tidak reproducible karena
   randomisasi `hash()`, jadi seed di sini adalah angka tanggal yang ditulis di
   sumber dan dicetak di setiap laporan. `DRAWS` menaikkan presisi titik estimasi
   saja: t utamanya dibaca dari sampel TIDAK BERTUMPANG TINDIH, dan penipisan itu
   memilih satu kandidat per jendela, jadi menambah draw tidak menggelembungkan n
   yang dilaporkan.

SAMPEL TIDAK BERTUMPANG TINDIH, dan ini bukan hiasan. `docs/CALIBRATION.md` H10
mencatat t menggelembung sampai tujuh kali lipat semata karena jendela maju
bertumpang tindih: t=5,46 menjadi 2,17. `spaced` menipis dengan aturan yang sama
untuk KEDUA arm, dan ia menipis memakai JENDELA MAKSIMUM sebuah trade, bukan exit
yang benar-benar terjadi. Bedanya penting: memilih berdasarkan exit nyata adalah
menyeleksi berdasarkan hasil, dan itu bias yang tidak kelihatan.
"""

from __future__ import annotations

import argparse
import contextlib
import json

import numpy as np

from app.indicators import wilder_atr
from app.models import SupplyDemandParams, ZoneSide, ZoneState
from tools import history, intrabar
from tools.calibrate import POPULATION
from tools.costed import HORIZON, ROLLOVER_HOUR_UTC
from tools.intrabar import FINER, resolved
from tools.quant import clean, metrics
from tools.true_open_matrix import welch

#: Tanggal run pertama, ditulis di sumber dan dicetak di laporan. Bukan turunan
#: jam mesin dan bukan `hash()`: dua run dengan argumen sama harus memberi baris
#: yang sama, dan proyek ini sudah pernah kehilangan sifat itu sekali.
SEED = 20260829

#: Berapa kali populasi baseline digambar ulang. Sama dengan `PLACEBO_DRAWS` di
#: `tools/costed.py` supaya kontrol lama dan kontrol ini dibaca pada tingkat
#: kehalusan yang sama.
DRAWS = 3


@contextlib.contextmanager
def _spy(store: dict):
    """Rekam geometri setiap plan yang dibangun arm nyata, tanpa menghitungnya ulang.

    `resolved` tidak mengembalikan tinggi zona maupun reward multiple-nya, dan
    menghitung ulang keduanya di sini berarti menyalin filter kelayakannya juga.
    Menyadap `build` mengambil angka yang PERSIS dipakai, dari panggilan yang
    sama, jadi geometri baseline tidak bisa menyimpang dari geometri arm nyata
    karena dua pembacaan berbeda.
    """
    original = intrabar.build

    def spy(zone, atr, now, step, spread=None):
        plan = original(zone, atr, now, step, spread=spread)
        if plan is not None and plan.target is not None:
            store[zone.id] = (zone, float(atr))
        return plan

    intrabar.build = spy
    try:
        yield
    finally:
        intrabar.build = original


@contextlib.contextmanager
def _inject(zones: list):
    """Jalankan `resolved` di atas zona sintetis, dengan resolver yang tidak disentuh.

    Dua nama modul yang ditukar adalah satu-satunya pintu masuk sinyal ke dalam
    `resolved`. Dikembalikan di `finally` karena kebocoran patch akan membuat
    setiap pengukuran berikutnya di proses yang sama membaca zona baseline dan
    melaporkannya sebagai hasil arm nyata, yaitu kegagalan senyap.
    """
    detectors, road = intrabar.DETECTORS, intrabar.profit_zone_at
    intrabar.DETECTORS = {**detectors,
                          "supply_demand": lambda candles, params: (zones, None)}
    intrabar.profit_zone_at = lambda zone, others, when: zone.profit_zone_rr
    try:
        yield
    finally:
        intrabar.DETECTORS, intrabar.profit_zone_at = detectors, road


def window_end(at: int, time: np.ndarray) -> int:
    """Bar TERAKHIR yang masih bisa disentuh walk sebuah trade yang dibuka di `at`.

    Aturan yang sama dengan `costed.trades` di bawah `flat_by_rollover`: horizon
    80 bar, dipotong bar pertama pada atau sesudah rollover 21:00 UTC. Dihitung
    dari `at` saja dan bukan dari exit yang terjadi, karena `spaced` memakainya
    untuk memilih trade dan memilih berdasarkan exit nyata adalah menyeleksi
    berdasarkan hasil.
    """
    shift = ROLLOVER_HOUR_UTC * 3600
    cut = ((int(time[at]) - shift) // 86_400 + 1) * 86_400 + shift
    last = min(at + HORIZON, len(time) - 1)
    for j in range(at + 1, last + 1):
        if int(time[j]) >= cut:
            return j
    return last


def spaced(rows: list[dict], time: np.ndarray) -> list[dict]:
    """Trade yang jendela majunya tidak beririsan sama sekali, urut waktu.

    Serakah dari yang paling awal: sebuah trade diterima kalau ia dibuka SESUDAH
    jendela trade yang terakhir diterima berakhir. Aturan yang sama dipakai untuk
    kedua arm, karena kontrol yang ditipis dengan aturan berbeda dari yang
    dikontrolnya bukan kontrol.
    """
    kept: list[dict] = []
    guard = -1
    for row in sorted(rows, key=lambda r: r["at"]):
        if row["at"] <= guard:
            continue
        kept.append(row)
        guard = window_end(row["at"], time)
    return kept


def draw(candles, geometry: list[dict], eligible: np.ndarray, rng, policy: str,
         template, hours: np.ndarray | None = None) -> list:
    """Populasi zona sintetis: geometri arm nyata, tempat yang tidak dipilih sinyal."""
    time = np.array([c.time for c in candles], dtype=np.int64)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    params = SupplyDemandParams(**{**POPULATION, "show_broken": True})
    atr = wilder_atr(high, low, close, params.atr_period)

    if policy == "hour":
        # Jam UTC ditarik dari histogram jam entry arm nyata, lalu bar ditarik
        # seragam DI DALAM jam itu. Bucket yang kosong tidak bisa terjadi karena
        # histogramnya dibangun dari bar yang ada di `eligible` juga.
        buckets: dict[int, np.ndarray] = {}
        stamp = (time[eligible] // 3600) % 24
        for hour in np.unique(hours):
            pick = eligible[stamp == hour]
            if len(pick):
                buckets[int(hour)] = pick
        wanted = np.array([h for h in hours if int(h) in buckets])
    else:
        buckets, wanted = {}, np.array([])

    zones = []
    for i in range(len(geometry)):
        if policy == "hour":
            pool = buckets[int(wanted[rng.integers(len(wanted))])]
        else:
            pool = eligible
        k = int(pool[rng.integers(len(pool))])
        g = geometry[int(rng.integers(len(geometry)))]

        scale = float(atr[k - 1])
        if scale <= 0:
            continue
        height = g["height_atr"] * scale
        # Limit dipasang di close bar SEBELUMNYA. Level itu knowable pada awal
        # bar entry; close bar entry sendiri tidak, dan memakainya akan
        # membolehkan fill di bar halus yang terjadi sebelum harga itu ada.
        price = float(close[k - 1])
        demand = g["side"] is ZoneSide.DEMAND
        top = price if demand else price + height
        bottom = price - height if demand else price
        zones.append(template.model_copy(update={
            "id": f"baseline-{policy}-{i}",
            "side": g["side"],
            "state": ZoneState.FRESH,
            "top": top, "bottom": bottom,
            "proximal": price, "distal": bottom if demand else top,
            "time_from": int(time[k - 1]), "time_to": int(time[-1]),
            "first_test_time": int(time[k]),
            "profit_zone_rr": g["rr"],
            # LABEL, bukan properti terukur. Sebuah kotak yang tidak digambar
            # tidak punya kaki keluar. Ia diikutkan supaya kohort gerbang punya
            # kontrol dengan FREKUENSI yang cocok; ia tidak mengklaim baseline
            # ini "lolos gerbang" apa pun.
            "departure_atr": g["departure"],
            "crowded_at": None, "inverted_at": None,
        }))
    return zones


def arms(symbol: str, interval: str, fine: str, draws: int = DRAWS,
         seed: int = SEED) -> dict:
    """Arm nyata dan dua arm baseline, di deret dan jendela yang sama."""
    store: dict = {}
    with _spy(store):
        real = resolved(symbol, interval, fine)
    if not real:
        return {}

    candles, _, _ = clean(symbol, interval)
    time = np.array([c.time for c in candles], dtype=np.int64)
    small = history.load(f"mt5:{symbol}", fine, 99_999)
    first_fine = small[0].time if small else time[-1]

    # Bar yang memenuhi SYARAT KELAYAKAN YANG SAMA dengan yang dipakai `resolved`
    # untuk memilih trade nyata: punya bar sebelumnya, punya horizon penuh di
    # depannya, dan berada di dalam rentang riwayat halus.
    index = np.arange(len(candles))
    eligible = index[(index >= 1) & (index + HORIZON < len(candles))
                     & (time >= first_fine)]
    if len(eligible) == 0:
        return {}

    geometry = []
    for row in real:
        zone, atr = store[row["zone_id"]]
        geometry.append({
            "height_atr": (zone.top - zone.bottom) / atr,
            "rr": zone.profit_zone_rr,
            "side": zone.side,
            "departure": zone.departure_atr,
        })
    hours = np.array([(int(time[r["at"]]) // 3600) % 24 for r in real])
    template = store[real[0]["zone_id"]][0]

    out = {"real": sorted(real, key=lambda r: r["at"]), "time": time,
           "eligible": len(eligible), "attempts": len(geometry) * draws}
    for policy in ("uniform", "hour"):
        rng = np.random.default_rng(seed)
        rows: list[dict] = []
        for _ in range(draws):
            zones = draw(candles, geometry, eligible, rng, policy, template, hours)
            with _inject(zones):
                rows.extend(resolved(symbol, interval, fine))
        out[policy] = sorted(rows, key=lambda r: r["at"])
    return out


def line(title: str, rows: list[dict], against: list[dict] | None) -> dict:
    m = metrics(rows)
    if not m["n"]:
        print(f"  {title:<28}{'0':>6}")
        return {"n": 0}
    # ARAHNYA: nyata dikurangi baseline, jadi t positif berarti arm nyata di
    # ATAS baseline. Ditulis begini karena kolomnya dicetak di baris baseline,
    # dan tanda yang terbalik di sana adalah cara termudah salah membaca putusan.
    t = welch(np.array([r["r"] for r in against]),
              np.array([r["r"] for r in rows])) if against else float("nan")
    print(f"  {title:<28}{m['n']:>6}{m['exp_r']:>+10.4f}{m['t']:>+8.2f}"
          f"{m['win_rate']:>8.1%}{m['total_r']:>+10.1f}"
          + (f"{t:>+18.2f}" if against else f"{'-':>18}"))
    return {"n": m["n"], "exp_r": m["exp_r"], "t": m["t"],
            "win_rate": m["win_rate"], "total_r": m["total_r"],
            "welch_real_minus_baseline": None if against is None else t}


def report(symbol: str, interval: str, fine: str, draws: int, seed: int,
           out: dict) -> dict:
    """Cetak satu sel, dan kembalikan baris TIPISNYA supaya bisa digabung."""
    got = arms(symbol, interval, fine, draws, seed)
    if not got:
        print(f"{symbol} {interval}: tidak ada trade yang bisa diselesaikan di {fine}")
        return {}
    time = got["time"]
    thin: dict[str, list[dict]] = {}
    key = f"{symbol} {interval}"
    cell: dict = {"fine": fine, "seed": seed, "draws": draws,
                  "eligible_bars": got["eligible"], "attempts": got["attempts"]}

    print(f"\n{'=' * 84}")
    print(f"{key}, diselesaikan di bar {fine}, seed {seed}, {draws} draw")
    print(f"{'=' * 84}")
    print(f"  {'arm':<28}{'n':>6}{'exp R':>10}{'t':>8}{'win':>8}"
          f"{'total R':>10}{'t nyata-baseline':>18}")

    for label, cohort in (("semua trade", lambda r: True),
                          ("kohort gerbang", lambda r: r["cleared"])):
        real = [r for r in got["real"] if cohort(r)]
        print(f"  -- {label}, BERTUMPANG TINDIH (t di sini menggelembung)")
        cell[f"{label} real overlap"] = line("nyata", real, None)
        for policy in ("uniform", "hour"):
            rows = [r for r in got[policy] if cohort(r)]
            cell[f"{label} {policy} overlap"] = line(f"baseline {policy}", rows, real)

        thin_real = spaced(real, time)
        print(f"  -- {label}, TIDAK BERTUMPANG TINDIH (ini yang dibaca)")
        cell[f"{label} real"] = line("nyata", thin_real, None)
        thin[f"{label} nyata"] = thin_real
        for policy in ("uniform", "hour"):
            rows = spaced([r for r in got[policy] if cohort(r)], time)
            cell[f"{label} {policy}"] = line(f"baseline {policy}", rows, thin_real)
            thin[f"{label} {policy}"] = rows

    filled = {p: len(got[p]) / max(got["attempts"], 1) for p in ("uniform", "hour")}
    cell["fill_rate"] = filled
    print(f"\n  limit terisi: uniform {filled['uniform']:.1%}, "
          f"hour {filled['hour']:.1%} dari {got['attempts']} draw. "
          f"Frekuensi cocok kalau angka ini dekat 100%.")
    out[key] = cell
    return thin


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells", default="XAUUSD:1h",
                        help="daftar SIMBOL:INTERVAL dipisah koma")
    parser.add_argument("--fine", default="", help="kosong berarti tabel FINER")
    parser.add_argument("--draws", type=int, default=DRAWS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    out: dict = {}
    pool: dict[str, list[dict]] = {}
    for cell in args.cells.split(","):
        symbol, _, interval = cell.strip().partition(":")
        interval = interval or "1h"
        fine = args.fine or FINER.get(interval, "5m")
        for name, rows in report(symbol, interval, fine, args.draws,
                                 args.seed, out).items():
            pool.setdefault(name, []).extend(rows)

    if len(pool) and len(args.cells.split(",")) > 1:
        # GABUNGAN, dengan satu peringatan yang harus ikut terbaca: trade di
        # instrumen berbeda pada jam yang sama TIDAK independen (emas dan perak
        # bergerak bersama), jadi n gabungan melebih-lebihkan jumlah pengamatan
        # bebas. Penipisan `spaced` hanya menjamin ketidaktumpangtindihan DI
        # DALAM satu deret. Yang digabung karenanya dibaca sebagai titik
        # estimasi yang lebih stabil, bukan sebagai t yang lebih kuat.
        print(f"\n{'=' * 84}")
        print("GABUNGAN semua sel, tidak bertumpang tindih di dalam tiap deret")
        print(f"{'=' * 84}")
        print(f"  {'arm':<28}{'n':>6}{'exp R':>10}{'t':>8}{'win':>8}"
              f"{'total R':>10}{'t nyata-baseline':>18}")
        merged: dict = {}
        for label in ("semua trade", "kohort gerbang"):
            real = pool.get(f"{label} nyata", [])
            if not real:
                continue
            print(f"  -- {label}")
            merged[f"{label} real"] = line("nyata", real, None)
            for policy in ("uniform", "hour"):
                merged[f"{label} {policy}"] = line(
                    f"baseline {policy}", pool.get(f"{label} {policy}", []), real)
        out["GABUNGAN"] = merged

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
