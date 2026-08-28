"""Di kuarter mana objek-objek itu LAHIR, dan di kuarter mana ekstrem terbentuk.

    python -m tools.quarter_placement
    python -m tools.quarter_placement --degree week

PERTANYAAN YANG DIJAWABNYA, dan keempatnya diambil dari materi referensi apa
adanya. Dari `Referensi grup dan Bg Nas/Whatsapp/chat.md`, 10 dan 13 Agustus
2026:

    "liat di quarter apa OB/breaker block itu terjadi? Diantara Q3-Q4."
    "Gap itu terjadinya kapan? Di Q1."
    "IFVG itu terjadi dalam Q2(manipulation) - high probability"
    "Highs/Lows biasanya terbentuk di Q3"

Empat klaim penempatan, dan engine ini sudah punya seluruh bahannya: grid
kuarter, lima detektor, dan opening gap. Tidak satu pun pernah diukur di sini.

INI BASE RATE, BUKAN EDGE. Tidak ada bracket, tidak ada biaya, tidak ada outcome.
Yang ditanya cuma "di mana benda ini lahir", dan itu disengaja: pertanyaan
penempatan bisa dijawab tanpa satu pun asumsi tentang urutan di dalam bar, yaitu
asumsi yang membatalkan angka utama project ini pada 22 Agustus. Kalau sebuah
penempatan ternyata timpang, langkah BERIKUTNYA yang mengukur apakah itu
berbayar, dan itu butuh pre-registrasi sendiri.

BASELINE-NYA BUKAN 25 PERSEN, dan ini satu-satunya keputusan metodologis di file
ini. Kuarter tidak sama panjang dalam jumlah BAR: pasar tutup memotong kuarter
harian secara tidak merata, akhir pekan menghapus sebagian, dan Jumat tidak
termasuk kuarter mingguan mana pun. Jadi "Q1 punya gap terbanyak" bisa berarti
tidak lebih dari "Q1 punya bar terbanyak". Setiap tabel di bawah karena itu
mencetak share bar di sebelah share objek, dan kolom `delta` adalah selisihnya.
Tanpa kolom itu, tiga dari empat klaim di atas akan terlihat terbukti pada data
yang sebenarnya cuma tidak seimbang.

CAP HARUS NOL. `max_zones_per_side` bawaannya 6 dan memilih zona TERBARU, jadi
mengukur dengan bawaan akan menjawab pertanyaan ini pada 9,6 persen terakhir tiap
deret. Lihat memory `zonelab-display-cap-hazard`; ini sudah merusak empat
pengukuran di repo ini.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from app.detect import imbalance, inversion, supply_demand
from app.gaps import opening_gaps
from app.models import Candle, ImbalanceParams, SupplyDemandParams
from app.quarters import quarters
from tools import history

#: Deret yang ada di cache dan tidak butuh network.
#:
#: LIMA PERTAMA CRYPTO, EMPAT TERAKHIR TUTUP SESI, dan pembagian itu wajib ada
#: untuk satu dari empat klaim. Sebuah instrumen 24/7 TIDAK BISA punya opening
#: gap: diukur di sini, spacing PAXGUSDT dan BTCUSDT seragam 3600 detik tanpa satu
#: jeda pun, dan `opening_gaps` benar mengembalikan nol. Menjawab "gap terjadi di
#: Q1" dari deret crypto berarti menjawabnya dari populasi kosong. Emas, EURUSD
#: dan NAS100 punya jeda harian dan akhir pekan, jadi di sanalah klaim itu bisa
#: diuji.
SERIES: tuple[tuple[str, str, int], ...] = (
    ("PAXGUSDT", "15m", 20000),
    ("PAXGUSDT", "1h", 20000),
    ("BTCUSDT", "15m", 20000),
    ("BTCUSDT", "1h", 20000),
    ("ETHUSDT", "1h", 20000),
    ("yahoo:XAUUSD", "1h", 13725),
    ("XAUUSD", "15m", 5000),  # bare = Dukascopy spot, lihat tools/history.py
    ("yahoo:EURUSD", "1h", 1500),
    ("yahoo:NAS100", "1h", 2000),
)

LABELS = ("Q1", "Q2", "Q3", "Q4")


def _quarter_of(qs: list, time: int) -> str | None:
    """Label kuarter yang memuat `time`, atau None kalau tidak ada.

    None bukan kegagalan: Jumat tidak termasuk kuarter mingguan mana pun dan
    minggu kelima sebuah bulan juga tidak. Itu doktrinnya, bukan lubang, dan
    objek yang lahir di sana memang tidak punya kuarter untuk dilaporkan.
    """
    for q in qs:
        if q.start <= time < q.end:
            return q.label
    return None


def _share(counts: Counter[str], total: int) -> dict[str, float]:
    return {lab: (100.0 * counts.get(lab, 0) / total if total else 0.0) for lab in LABELS}


def measure(candles: list[Candle], degree: str) -> dict:
    """Penempatan setiap objek plus baseline share bar, untuk satu deret."""
    lo, hi = candles[0].time, candles[-1].time
    qs = quarters(degree, lo, hi)

    # BASELINE. Share bar per label kuarter, dihitung dari bar yang sama yang
    # dipakai detektor, jadi bar yang tidak masuk kuarter mana pun keluar dari
    # penyebut di kedua sisi.
    bar_counts: Counter[str] = Counter()
    for c in candles:
        lab = _quarter_of(qs, c.time)
        if lab:
            bar_counts[lab] += 1
    bar_total = sum(bar_counts.values())

    sd_params = SupplyDemandParams(max_zones_per_side=0, show_broken=True)
    imb_params = ImbalanceParams(max_zones_per_side=0, show_broken=True)

    # KAPAN SEBUAH OBJEK "LAHIR". Untuk box, `time_from` adalah bar paling kiri
    # yang membentuknya, dan itu yang dipakai. Memakai bar sentuh akan menjawab
    # pertanyaan yang berbeda ("kapan ia dipakai"), dan pertanyaannya di sini
    # adalah kapan ia terbentuk.
    objects: dict[str, list[int]] = {}
    for name, rows in (
        ("supply_demand", supply_demand.detect(candles, sd_params)[0]),
        ("fvg", imbalance.detect_fvg(candles, imb_params)[0]),
        ("order_block", imbalance.detect_order_block(candles, imb_params)[0]),
        ("ifvg", inversion.detect_ifvg(candles, imb_params)[0]),
        ("breaker", inversion.detect_breaker(candles, imb_params)[0]),
    ):
        objects[name] = [z.time_from for z in rows]
    # `open_time`, bukan `close_time`: sebuah gap LAHIR di bar pembuka sesudah
    # jeda, dan itu yang ditanya. `close_time` adalah bar terakhir sebelum jeda,
    # yang hampir selalu jatuh di kuarter yang berbeda. Versi pertama file ini
    # memakai `g.at`, field yang tidak ada pada `OpeningGap`, dan seluruh baris
    # gap keluar n=0 di kelima deret - kolom nol yang terbaca seperti fakta pasar,
    # persis kelas cacat yang repo ini punya daftarnya.
    objects["gap"] = [g.open_time for g in opening_gaps(candles)]

    placement = {}
    for name, times in objects.items():
        counts: Counter[str] = Counter()
        outside = 0
        for t in times:
            lab = _quarter_of(qs, t)
            if lab:
                counts[lab] += 1
            else:
                outside += 1
        total = sum(counts.values())
        placement[name] = {
            "n": total,
            "outside_any_quarter": outside,
            "share": _share(counts, total),
        }

    # EKSTREM SIKLUS. Satu siklus adalah empat kuarter berlabel Q1..Q4 secara
    # berurutan; siklus yang tidak lengkap di kedua ujung window dibuang, karena
    # ekstremnya bisa jatuh di kuarter yang tidak ikut terlihat.
    cycles: list[list] = []
    current: list = []
    for q in qs:
        if q.label == "Q1":
            if len(current) == 4:
                cycles.append(current)
            current = [q]
        elif current:
            current.append(q)
    if len(current) == 4:
        cycles.append(current)

    high_at: Counter[str] = Counter()
    low_at: Counter[str] = Counter()
    complete = 0
    for cycle in cycles:
        per_label: dict[str, tuple[float, float]] = {}
        for q in cycle:
            inside = [c for c in candles if q.start <= c.time < q.end]
            if not inside:
                break
            per_label[q.label] = (
                max(c.high for c in inside),
                min(c.low for c in inside),
            )
        if len(per_label) != 4:
            continue
        complete += 1
        high_at[max(per_label, key=lambda lab: per_label[lab][0])] += 1
        low_at[min(per_label, key=lambda lab: per_label[lab][1])] += 1

    # SPACING SERAGAM BERARTI TIDAK PERNAH TUTUP, dan itu harus dilaporkan bukan
    # disembunyikan. Tanpa flag ini, baris gap pada deret crypto mencetak nol di
    # keempat kuarter dengan delta -25 masing-masing, yang terbaca seperti temuan
    # ("gap menghindari setiap kuarter") padahal artinya populasinya kosong.
    steps = {candles[i + 1].time - candles[i].time for i in range(len(candles) - 1)}
    never_closes = len(steps) == 1

    return {
        "degree": degree,
        "never_closes": never_closes,
        "bars": len(candles),
        "quarters": len(qs),
        "bar_share": _share(bar_counts, bar_total),
        "placement": placement,
        "cycles_complete": complete,
        "high_share": _share(high_at, complete),
        "low_share": _share(low_at, complete),
    }


def _table(title: str, rows: list[tuple[str, int, dict, dict]]) -> None:
    print(f"\n  {title}")
    print(f"    {'objek':<14}{'n':>7}"
          + "".join(f"{lab:>8}" for lab in LABELS)
          + "".join(f"{'d' + lab[1]:>7}" for lab in LABELS))
    for name, n, share, base in rows:
        deltas = "".join(f"{share[lab] - base[lab]:>+7.1f}" for lab in LABELS)
        print(f"    {name:<14}{n:>7}"
              + "".join(f"{share[lab]:>8.1f}" for lab in LABELS)
              + deltas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--degree", default="day", help="day, week, session, month")
    ap.add_argument("--json", action="store_true", help="cetak JSON mentah saja")
    args = ap.parse_args()

    results = []
    for symbol, interval, bars in SERIES:
        candles = history.load(symbol, interval, bars)
        results.append({"series": f"{symbol}-{interval}", **measure(candles, args.degree)})

    if args.json:
        print(json.dumps(results, indent=1))
        return

    print("=" * 78)
    print(f"PENEMPATAN KUARTER, derajat = {args.degree}")
    print("=" * 78)
    print("\n  Share dalam persen. Kolom dQn adalah selisih terhadap share BAR di")
    print("  kuarter itu, jadi nol berarti objeknya jatuh persis sesebaran barnya.")

    for r in results:
        print(f"\n  {r['series']}  {r['bars']} bar, {r['quarters']} kuarter derajat {r['degree']}")
        base = r["bar_share"]
        print(f"    {'share bar':<14}{'':>7}" + "".join(f"{base[lab]:>8.1f}" for lab in LABELS))
        rows = [
            (name, d["n"], d["share"], base)
            for name, d in r["placement"].items()
            if not (name == "gap" and r["never_closes"])
        ]
        if r["never_closes"]:
            print("    gap            instrumen tidak pernah tutup, jadi nol gap"
                  " adalah konstruksi bukan temuan")
        _table("kelahiran objek", rows)
        _table("ekstrem siklus", [
            ("cycle high", r["cycles_complete"], r["high_share"], base),
            ("cycle low", r["cycles_complete"], r["low_share"], base),
        ])

    print("\n" + "=" * 78)
    print("  Base rate, bukan edge. Penempatan yang timpang belum berarti berbayar;")
    print("  yang mengukur itu langkah berikutnya, dengan ambangnya ditulis di depan.")
    print()
    print("  BACA BARIS EKSTREM SIKLUS DENGAN HATI-HATI, dan ini peringatan yang")
    print("  lahir dari hampir salah membacanya sendiri. Ekstrem sebuah window")
    print("  memang berkumpul di UJUNG dan menghindari tengahnya, dan itu hukum")
    print("  arcsine: argmax sebuah jalur Brownian terkonsentrasi di kedua ujung.")
    print("  Jadi Q1 dan Q4 tinggi sementara Q2 rendah adalah pola yang deret")
    print("  ACAK pun menghasilkan. Angka itu belum boleh dibaca sebagai temuan")
    print("  tentang kuarter sampai ada placebo yang memotong deret yang sama di")
    print("  batas yang digeser beberapa jam.")


if __name__ == "__main__":
    main()
