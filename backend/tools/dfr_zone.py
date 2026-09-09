"""Pita DFR sebagai ZONA, lewat bracket yang sama dengan delapan detektor lain.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.dfr_zone --json ../docs/dfr_zone.json

================================================================================
PRAREGISTRASI, ditulis SEBELUM satu angka dihitung
================================================================================

--------------------------------------------------------------------------------
1. KENAPA pertanyaan ini, dan kenapa ia BUKAN pengulangan

Tiga bentuk uji sudah dijalankan pada `dfr` dan ketiganya null:

  `tools/conditioned.py`       `dfr_pos` dan `dfr_band` sebagai kolom pengkondisi
                               ekspektansi, 0 dari 52 dan 0 dari 58 grup
  `tools/dfr_outcomes.py`      reach level ekstensi -0,5 dan -1 dalam 96 bar
                               lawan jitter, 0 dari 10 grup
  `app/ict.py`                 klausa `dfr_side`, memisahkan tapi TANDANYA TERBALIK

Yang belum pernah dijalankan adalah bentuk uji yang justru dipakai untuk menilai
DELAPAN detektor kotak lain di repo ini: pita itu sendiri sebagai zona yang
disentuh, di-bracket, dan diadu dengan placebo. Selama itu belum ada, `dfr` tidak
bisa dibandingkan dengan `fvg` atau `order_block` sama sekali - bukan karena ia
kalah, tapi karena ia tidak pernah ikut lomba yang sama.

--------------------------------------------------------------------------------
2. OBJEK YANG DIUJI, dan satu keputusan yang harus dibaca dulu

Sebuah DFR adalah RENTANG, bukan zona berarah, jadi ia harus dibelah sebelum
bisa masuk bracket berarah. Ia dibelah di EKUILIBRIUMNYA SENDIRI:

    paruh atas   top = dfr.high, bottom = ekuilibrium   -> SUPPLY
    paruh bawah  top = ekuilibrium, bottom = dfr.low    -> DEMAND

Ekuilibrium dipilih karena ia LEVEL MILIK SUMBERNYA SENDIRI, sudah digambar
`app/overlays.py` dan sudah punya toggle di UI. Membelah di situ karena itu tidak
menambah satu pun parameter bebas. Membelah di tempat lain akan menambah.

KIND-NYA DIPINJAM, DAN ITU DISENGAJA. Tidak ada `ZoneKind.DFR`, dan menambahnya
menyentuh belasan tempat demi sebuah pengukuran. Jadi paruh atas memakai RBD dan
paruh bawah DBR - "supply/demand reversal" - yang kebetulan persis klaim yang
sedang diuji. Kotak yang keluar dari file ini TIDAK BOLEH dibaca sebagai RBD atau
DBR di tempat lain.

Lahir di `dfr.end`, yaitu Q1 close, yaitu instan pita itu knowable. `_closed` di
`app/quarterly.py` sudah membuktikan Q1 berakhir di dalam data, dan `_finish`
memulai lifecycle di bar SESUDAH `born`, jadi bar yang membentuk pita tidak bisa
menghitung dirinya sendiri sebagai sentuhan pertama.

--------------------------------------------------------------------------------
3. HIPOTESIS

H1  Paruh pita DFR yang disentuh menahan bracket LEBIH SERING daripada placebo -
    kotak sama besar, sama sisi, sama umur, di harga yang salah.
H2  Pecahan yang dibuang dari Q1 berpengaruh. Aturan Bucko membuang sepertiga
    pertama; itu satu-satunya angka bebas di seluruh konstruk ini, dan ia sampai
    ke repo ini SINGLE-SOURCED. Empat lengan diuji: buang 0, 1/3, 1/2, 2/3.

`f = 1/3` adalah lengan yang DIKIRIM. Tiga lainnya kontrol untuk pertanyaan
"apakah sepertiga itu istimewa, atau semua potongan Q1 sama saja".

--------------------------------------------------------------------------------
4. AMBANG, ditulis sebelum angkanya ada

  - menang placebo di KEDUA geometri bracket - reward dalam ATR, dan reward
    dalam tinggi kotak sendiri. Yang muncul di satu dan hilang di satunya adalah
    geometri bracket, bukan detektor. Aturan ini milik `tools/detectors.py` dan
    dipakai apa adanya.
  - lolos hold-out: lengan `f` dipilih di PARUH PERTAMA deret, lalu dinilai di
    paruh kedua. Lengan yang menang cuma di paruh pemilihnya tidak lolos.
  - walk-forward 8 fold jumlah-sama, dan jumlah fold positifnya dicetak semua,
    termasuk yang gagal.

Kurang dari itu dilaporkan apa adanya, dan `orderable` tidak disentuh file ini.

--------------------------------------------------------------------------------
5. KONTROL KUARTAL, dan kenapa placebo geser-harga saja tidak cukup di sini

Placebo geser-harga menjawab "apakah kotaknya menandai sebuah TEMPAT". Ia tidak
menjawab "apakah Q1 istimewa", dan pada konstruk ini pertanyaan kedua itu justru
yang berbahaya, karena dua paruh pita BERBAGI TEPI EKUILIBRIUM: proximal paruh
supply dan proximal paruh demand ada di harga yang sama persis. Sentuhan pertama
karena itu terjadi di instan yang sama untuk keduanya, di tengah rentang yang
harga baru saja lewati. Kalau yang menghasilkan angka adalah KONTEKS itu - masuk
bracket di tengah rentang yang baru diperdagangkan - maka rentang kuartal mana pun
akan memberi angka yang sama, dan "Q1" tidak menjelaskan apa-apa.

Jadi seluruh konstruk dijalankan ulang dengan anchor Q2, Q3 dan Q4. Geometrinya
identik, aturan pertiganya identik, hanya kuartal sumbernya yang berbeda. Kalau
Q1 tidak menonjol di atas ketiganya, temuan yang benar bukan "DFR bekerja" tapi
"ekuilibrium rentang kuartal mana pun bekerja", dan itu klaim yang jauh lebih
kecil dan bukan milik sumbernya.

--------------------------------------------------------------------------------
6. KONTROL DRIFT ARAH, dan sebuah klaim yang saya baca sebelum saya ukur

Backtest COMEX detektor 10 memberi bentuk yang mencolok: SETIAP lengan supply
rugi (PF 0,532 sampai 0,702) dan setiap lengan demand kecuali Q4 untung (sampai
1,482), seragam di keempat kuartal. Saya menyimpulkan itu drift arah - emas naik
sepanjang 2023-2026 - dan kesimpulan itu DIBACA DARI POLA TABEL, bukan diukur.
Tabel COMEX tidak punya placebo sama sekali, jadi ia memang tidak bisa
memisahkannya.

Di sini bisa. Placebo rig ini SE-ARAH dengan zona aslinya: sebuah placebo long
adalah kotak demand di harga yang salah, jadi ia menikmati tren naik yang sama
persis. Selisih drawn dikurangi placebo karena itu sudah bersih dari drift, dan
memecahnya per sisi menjawab pertanyaannya langsung:

  - kalau sisi demand unggul jauh atas placebo DEMAND-nya sendiri, keunggulan
    itu bukan drift dan pembacaan saya salah;
  - kalau selisihnya menguap sementara PF mentahnya tinggi, drift yang
    menjelaskan angka COMEX dan pembacaan saya benar - sekarang terukur.

--------------------------------------------------------------------------------
7. PARUH DAN SAMPEL PENUH DIHITUNG TERPISAH, dan itu bukan pemborosan

Angka pooled dijalankan pada DERET UTUH, bukan dari menjumlahkan hasil dua paruh.
Memotong jendela mencabut dinding dari lengan luar sampel: pita yang lahir dekat
titik potong kehilangan sebagian horizon 96 barnya di satu sisi dan kehilangan
guard repaint di sisi lain, jadi jumlah dua paruh BUKAN sampel penuh dan
melaporkannya sebagai sampel penuh adalah kekeliruan yang sudah pernah terjadi di
repo ini. Harganya satu pass tambahan per lengan. Itu murah.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

import numpy as np

from app.detect.imbalance import _arrays, _finish
from app.indicators import wilder_atr
from app.models import Candle, ImbalanceParams, Zone, ZoneKind, ZoneSide
from app.quarterly import _bars, _closed, _q1_at
from app.quarters import quarters
from tools import history
from tools.calibrate import _two_proportion, first_touch, resolve, shift

SERIES = [
    ("mt5:XAUUSD", "1h"),
    ("mt5:BTCUSD", "1h"),
    ("mt5:ETHUSD", "1h"),
    ("mt5:EURUSD", "1h"),
]
# Derajat dan timeframe DIPILIH DI BARIS PERINTAH sejak 9 September 2026.
# Run pertama tool ini hanya `day` di 1 jam, dan sumbernya sendiri menyatakan DFR
# "applies at every degree" - jadi satu derajat tidak bisa dipakai untuk menerima
# atau menolak aturan itu, cuma untuk menerima atau menolaknya DI DERAJAT ITU.
#
# `session` dan `micro` sengaja tidak masuk daftar yang dipakai: kuartalnya 90
# dan 22,5 menit, jadi sepertiga pertamanya lebih pendek dari satu bar 1 jam dan
# jendela yang disimpan tidak bisa dibedakan dari kuartal penuh. Mengukurnya di
# sini akan melaporkan angka untuk aturan pertiga yang tidak pernah dijalankan.
DEGREE = "day"
FOLDS = 8
HORIZON = 96
ARMS = {"buang 0": 0.0, "buang 1/3": 1 / 3, "buang 1/2": 0.5, "buang 2/3": 2 / 3}
SHIPPED = "buang 1/3"

# Cap tampilan dimatikan karena ia memilih kotak TERBARU - mengukur lewatnya
# adalah mengukur ekor riwayat sambil memakai nama seluruh riwayat.
#
# TIDAK ADA GERBANG DEPARTURE YANG PERLU DIMATIKAN DI SINI, dan versi pertama file
# ini mencoba mematikannya. `ImbalanceParams` tidak punya field itu sama sekali:
# gerbang 2,0 ATR hidup di lapisan penyaring, bukan di detektornya. `_finish`
# hanya menolak kotak setinggi nol, dan `_present` - yang memasang cap dan
# membuang yang broken - sengaja tidak dipanggil di sini.
PARAMS = ImbalanceParams(max_zones_per_side=0, show_broken=True)


def _quarter(q):
    """Kuartal `q` sebagai objek dengan `.start` dan `.end`.

    Untuk Q1 dipakai `_q1_at` supaya jalurnya SAMA PERSIS dengan produksi -
    kalau `_q1_at` pernah menggeser batasnya, angka Q1 di sini ikut bergeser dan
    tidak diam-diam berbeda. Q2 sampai Q4 tidak punya helper begitu dan dipakai
    apa adanya dari `quarters`.
    """
    return _q1_at(DEGREE, q.start) if q.label == "Q1" else q


def bands(
    candles: list[Candle], discard: float, label: str = "Q1"
) -> list[tuple[int, int, float, float]]:
    """(kept_from, end, high, low) tiap DFR, dengan pecahan buang yang diberikan.

    `label` memilih kuartal sumbernya. "Q1" adalah konstruk aslinya; Q2, Q3 dan Q4
    adalah kontrol Bagian 5 dan memakai geometri yang persis sama.

    Salinan sengaja dari `quarterly.defining_range` dengan SATU hal diparametrik:
    pecahan Q1 yang dibuang. Guard repaint-nya - window kept harus tercakup penuh
    oleh data - dibawa apa adanya, karena tanpa itu pita paling kiri dihitung dari
    potongan Q1 yang kebetulan ada dan BERGERAK saat data ditambah ke kiri.
    """
    if not candles:
        return []
    out = []
    for q in quarters(DEGREE, candles[0].time, candles[-1].time):
        if q.label != label:
            continue
        q1 = _quarter(q)
        if not _closed(candles, q1):
            continue
        kept_from = q1.start + int((q1.end - q1.start) * discard)
        if candles[0].time > kept_from:
            continue
        kept = _bars(candles, kept_from, q1.end)
        if not kept:
            continue
        out.append(
            (kept_from, q1.end, max(c.high for c in kept), min(c.low for c in kept))
        )
    return out


def zones_for(candles: list[Candle], discard: float, label: str = "Q1") -> list[Zone]:
    """Tiap DFR jadi dua zona, dibelah di ekuilibriumnya sendiri."""
    time, _open, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, PARAMS.atr_period)

    def bar_at(ts: int) -> int | None:
        i = int(np.searchsorted(time, ts, side="left"))
        return i if i < len(time) else None

    found: list[Zone] = []
    for kept_from, end, hi, lo in bands(candles, discard, label):
        origin, born = bar_at(kept_from), bar_at(end)
        if origin is None or born is None or born <= origin:
            continue
        eq = (hi + lo) / 2.0
        base = float(atr[max(0, origin - 1)])
        if base <= 0:
            continue
        for kind, side, top, bottom in (
            (ZoneKind.RBD, ZoneSide.SUPPLY, hi, eq),
            (ZoneKind.DBR, ZoneSide.DEMAND, eq, lo),
        ):
            zone = _finish(
                kind, side, top, bottom, origin, born,
                time, high, low, close, atr, PARAMS,
                round((top - bottom) / base, 3),
            )
            if zone is not None:
                zone.id = f"DFR-{label}-{kind.value}-{end}"
                found.append(zone)
    return found


def outcomes(
    candles: list[Candle], discard: float, reward: float, mode: str,
    label: str = "Q1",
) -> dict[str, list[bool]]:
    """Hasil bracket untuk zona yang digambar dan untuk placebo-nya."""
    time, _open, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, PARAMS.atr_period)
    index_of = {int(t): i for i, t in enumerate(time)}

    # KUNCINYA DIPECAH PER SISI, dan itu seluruh maksud tambahan ini. Tabel COMEX
    # menunjukkan setiap lengan supply rugi dan hampir setiap lengan demand untung,
    # dan saya menyebut itu drift arah dari pola tabelnya saja - dibaca, bukan
    # diukur. Di sini bisa diukur, karena placebonya SE-ARAH dengan zona aslinya:
    # sebuah placebo long ikut menikmati tren naik yang sama. Jadi kalau sisi
    # demand unggul jauh atas placebo demand-nya sendiri, keunggulan itu bukan
    # drift; kalau selisihnya menguap, drift-lah yang menjelaskan angka COMEX.
    out: dict[str, list[bool]] = {
        "drawn": [], "placebo": [],
        "drawn_SUPPLY": [], "placebo_SUPPLY": [],
        "drawn_DEMAND": [], "placebo_DEMAND": [],
    }
    for zone in zones_for(candles, discard, label):
        if zone.first_test_time is None:
            continue
        touch = index_of.get(zone.first_test_time)
        if touch is None or touch <= zone.anatomy.leg_out_to:
            continue
        got = resolve(zone, high, low, close, atr, touch, reward, HORIZON, mode)
        if got is None:
            continue
        out["drawn"].append(got)
        out[f"drawn_{zone.side.name}"].append(got)

        moved = shift(zone, float(atr[min(zone.anatomy.base_to, len(atr) - 1)]))
        p_touch = first_touch(moved, high, low, zone.anatomy.leg_out_to + 1)
        if p_touch is None:
            continue
        p_got = resolve(moved, high, low, close, atr, p_touch, reward, HORIZON, mode)
        if p_got is not None:
            out["placebo"].append(p_got)
            out[f"placebo_{zone.side.name}"].append(p_got)
    return out


def _rate(xs: list[bool]) -> float | None:
    return 100.0 * sum(xs) / len(xs) if xs else None


def _delta(got: dict[str, list[bool]], suffix: str = "") -> float | None:
    rd, rp = _rate(got["drawn" + suffix]), _rate(got["placebo" + suffix])
    return None if rd is None or rp is None else rd - rp


def _folds(drawn: list[bool], placebo: list[bool]) -> tuple[int, list[float | None]]:
    """Selisih hold-rate per fold jumlah-sama, dan berapa fold yang positif."""
    vals: list[float | None] = []
    for i in range(FOLDS):
        d = drawn[i * len(drawn) // FOLDS:(i + 1) * len(drawn) // FOLDS]
        p = placebo[i * len(placebo) // FOLDS:(i + 1) * len(placebo) // FOLDS]
        rd, rp = _rate(d), _rate(p)
        vals.append(None if rd is None or rp is None else rd - rp)
    return sum(1 for v in vals if v is not None and v > 0), vals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=20000)
    ap.add_argument("--json", default="")
    # JENDELANYA HARUS BISA DIPAKU, dan run pertama tool ini tidak bisa.
    # `load(..., 20000)` mengambil 20.000 bar TERAKHIR, jadi jendelanya maju
    # ikut jam dinding: dua run di hari yang sama, beberapa jam berjarak,
    # membaca bar yang berbeda di ujung kanan. Itu menggeser zona di ujung,
    # menggeser berapa banyak placebo yang tersentuh, dan karena `shift()`
    # menarik dari RNG bersama, menggeser SETIAP offset placebo sesudahnya.
    #
    # Terlihat langsung: dua run terpisah beberapa jam memberi Q1 +7,1pp lalu
    # +7,8pp pada lengan dan geometri yang sama. Kesimpulannya tidak berubah -
    # Q1 tidak pernah yang terbaik di run mana pun - tapi angkanya tidak boleh
    # dikutip tanpa jendelanya, dan sebelum ini jendelanya tidak dicetak.
    ap.add_argument("--as-of", default="", help="YYYY-MM-DD, potong deret di sini")
    ap.add_argument("--degree", default="day", choices=["day", "week", "month"])
    ap.add_argument("--interval", default="1h")
    args = ap.parse_args()

    global DEGREE
    DEGREE = args.degree

    as_of = None
    if args.as_of:
        as_of = int(
            dt.datetime.strptime(args.as_of, "%Y-%m-%d")
            .replace(tzinfo=dt.timezone.utc)
            .timestamp()
        )

    loaded = [
        (sym, args.interval,
         history.cut(history.load(sym, args.interval, args.bars), as_of))
        for sym, _iv in SERIES
    ]
    stamp = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    for sym, iv, cs in loaded:
        print(f"  {sym} {iv}: {len(cs)} bar, {stamp(cs[0].time)} sampai {stamp(cs[-1].time)}")
    report_window = {
        f"{sym} {iv}": [stamp(cs[0].time), stamp(cs[-1].time)] for sym, iv, cs in loaded
    }

    report: dict = {
        "series": [f"{s} {i}" for s, i, _ in loaded],
        "degree": args.degree,
        "interval": args.interval,
        "as_of": args.as_of or None,
        "window": report_window,
        "geometries": {},
    }
    for mode, reward in (("atr", 1.0), ("box", 1.0)):
        unit = "ATR" if mode == "atr" else "x tinggi kotak"
        print(f"\n{'=' * 78}")
        print(f"DFR sebagai zona   derajat {args.degree}, {args.interval}, "
              f"reward 1,0 {unit}, horizon {HORIZON} bar")
        print(f"{'=' * 78}")
        print(f"  {'lengan':<12}{'n':>7}{'tahan':>8}{'placebo':>10}{'selisih':>10}"
              f"{'wf':>6}   uji")
        arms: dict = {}
        for name, discard in ARMS.items():
            full: dict[str, list[bool]] = {
                k: [] for k in (
                    "drawn", "placebo", "drawn_SUPPLY", "placebo_SUPPLY",
                    "drawn_DEMAND", "placebo_DEMAND",
                )
            }
            halves: dict[str, dict[str, list[bool]]] = {
                h: {k: [] for k in full} for h in ("first", "second")
            }
            for _sym, _iv, cs in loaded:
                for k, v in outcomes(cs, discard, reward, mode).items():
                    full[k] += v
                mid = len(cs) // 2
                for half, chunk in (("first", cs[:mid]), ("second", cs[mid:])):
                    for k, v in outcomes(chunk, discard, reward, mode).items():
                        halves[half][k] += v

            d, p = full["drawn"], full["placebo"]
            rd, rp = _rate(d), _rate(p)
            delta = _delta(full)
            wf, per_fold = _folds(d, p)
            test = _two_proportion(np.array(d), np.array(p)) if d and p else "n kosong"
            print(f"  {name:<12}{len(d):>7}"
                  f"{'-' if rd is None else f'{rd:.1f}%':>8}"
                  f"{'-' if rp is None else f'{rp:.1f}%':>10}"
                  f"{'-' if delta is None else f'{delta:+.1f}pp':>10}"
                  f"{wf:>4}/8   {test}")
            arms[name] = {
                "n_drawn": len(d),
                "n_placebo": len(p),
                "held_pct": rd,
                "placebo_pct": rp,
                "delta_pp": delta,
                "delta_supply_pp": _delta(full, "_SUPPLY"),
                "delta_demand_pp": _delta(full, "_DEMAND"),
                "n_supply": len(full["drawn_SUPPLY"]),
                "n_demand": len(full["drawn_DEMAND"]),
                "walkforward_positive": wf,
                "folds_delta_pp": per_fold,
                "test": test,
                "halves": {
                    h: {"delta_pp": _delta(v), "n_drawn": len(v["drawn"])}
                    for h, v in halves.items()
                },
            }

        # KONTROL DRIFT ARAH, Bagian 6.
        print(f"  {'-' * 70}")
        print(f"  {'lengan':<12}{'supply n':>10}{'vs placebo':>12}"
              f"{'demand n':>11}{'vs placebo':>12}")
        for name in ARMS:
            a = arms[name]
            ds, dd = a["delta_supply_pp"], a["delta_demand_pp"]
            cs = "-" if ds is None else f"{ds:+.1f}pp"
            cd = "-" if dd is None else f"{dd:+.1f}pp"
            print(f"  {name:<12}{a['n_supply']:>10}{cs:>12}"
                  f"{a['n_demand']:>11}{cd:>12}")

        # KONTROL KUARTAL, Bagian 5. Pecahan buang dipaku ke aturan yang dikirim
        # supaya satu-satunya yang berbeda dari lengan `SHIPPED` adalah kuartal
        # sumbernya. Dua hal yang berbeda tidak bisa dibandingkan.
        print(f"  {'-' * 70}")
        for label in ("Q1", "Q2", "Q3", "Q4"):
            ctl: dict[str, list[bool]] = {
                k: [] for k in (
                    "drawn", "placebo", "drawn_SUPPLY", "placebo_SUPPLY",
                    "drawn_DEMAND", "placebo_DEMAND",
                )
            }
            for _sym, _iv, cs in loaded:
                for k, v in outcomes(
                    cs, ARMS[SHIPPED], reward, mode, label
                ).items():
                    ctl[k] += v
            cd = _delta(ctl)
            cwf, _ = _folds(ctl["drawn"], ctl["placebo"])
            crd, crp = _rate(ctl["drawn"]), _rate(ctl["placebo"])
            held = "-" if crd is None else f"{crd:.1f}%"
            plac = "-" if crp is None else f"{crp:.1f}%"
            diff = "-" if cd is None else f"{cd:+.1f}pp"
            tag = "  <- konstruknya" if label == "Q1" else ""
            print(f"  kontrol {label:<4}{len(ctl['drawn']):>7}{held:>8}"
                  f"{plac:>10}{diff:>10}{cwf:>4}/8{tag}")
            report.setdefault("quarter_control", {}).setdefault(mode, {})[label] = {
                "n_drawn": len(ctl["drawn"]),
                "delta_pp": cd,
                "walkforward_positive": cwf,
            }

        # HOLD-OUT: lengan dipilih di paruh pertama, dinilai di paruh kedua.
        scored = [
            (a, v["halves"]["first"]["delta_pp"])
            for a, v in arms.items()
            if v["halves"]["first"]["delta_pp"] is not None
        ]
        pick = max(scored, key=lambda kv: kv[1])[0] if scored else None
        held = arms[pick]["halves"]["second"]["delta_pp"] if pick else None
        print(f"  hold-out: paruh pertama memilih {pick}, di paruh kedua "
              f"{'-' if held is None else f'{held:+.1f}pp'}"
              f"   (lengan yang dikirim: {SHIPPED})")
        report["geometries"][mode] = {
            "reward": reward,
            "horizon": HORIZON,
            "arms": arms,
            "holdout": {"picked_on_first_half": pick, "second_half_delta_pp": held},
        }

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)


if __name__ == "__main__":
    main()
