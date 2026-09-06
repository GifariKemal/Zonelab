"""Varian aturan supply and demand, diukur di rig yang sama dengan detector aslinya.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.sd_variants
    PYTHONPATH=. .venv/Scripts/python.exe -m tools.sd_variants --cells all

KENAPA. Empat detector lain sudah lewat sapuan ini pada 5 dan 6 September 2026,
dan tiga di antaranya berubah karenanya: ifvg dapat gerbang plafon, order block
ganti geometri kotak dan cara impulsnya diukur, breaker menolak seluruh cabang
Keluarga 2. Supply and demand adalah detector TERTUA di repo ini dan yang paling
banyak dokumentasinya, tetapi ATURAN DETEKSINYA belum pernah disapu lawan outcome
di rig yang sekarang. `docs/CALIBRATION.md` menyapu `ImbalanceParams`, bukan
`SupplyDemandParams`, dan metodenya pun beda: held-rate lawan placebo, bukan
exp_r dengan walk-forward.

APA YANG DISAPU, dan semuanya diregistrasi sebelum angkanya dilihat:

  A  produksi saat ini      aturan yang dikirim hari ini
  B  lilin keluar 0,70      SATU SATUNYA ARM YANG PUNYA SUMBER. Kodifikasi
                            Seiden yang beredar menuntut lilin yang KELUAR dari
                            base punya body minimal 70 persen rentangnya, dan
                            kita mengirim 0,50 untuk KEDUA kaki. Arm ini
                            menerapkan angka itu persis seperti sumbernya
                            menyebutnya: pada lilin keluar saja, lilin pertama
                            leg-out, bukan pada leg-in
  C  body ratio 0,7         angka yang sama tapi pada KEDUA kaki, supaya efek
                            "lilin keluar" bisa dipisahkan dari efek "ambang
                            lebih ketat"
  D  body ratio 0,6         satu langkah, untuk melihat monotonisitasnya
  E  body ratio 0,4         ARAH SEBALIKNYA, supaya sapuan ini tidak cuma bisa
                            bergerak ke satu sisi. Tanpa arm ini "lebih ketat
                            lebih baik" tidak bisa dibedakan dari "apa pun yang
                            memotong populasi terlihat lebih baik"
  F  proximal_basis body    knob PRODUKSI yang belum pernah diukur lawan
                            outcome. Ia memindahkan garis proximal dari sumbu
                            ke badan, jadi ia mengubah entry DAN tinggi kotak,
                            dan karena R dinormalisasi terhadap risk ia
                            menggerakkan setiap angka R sekaligus
  G  base_max_bars 3        base lebih pendek
  H  base_max_bars 12       base lebih panjang
  I  impulse_atr 1,5        kaki harus lebih besar terhadap ATR
  J  base_max_atr 1,5       base harus lebih rapat
  K  gerbang saat deteksi    BUKAN aturan baru: ambang yang SAMA dengan yang
                            `gate_sweep` pasang sesudahnya, tapi dipasang di
                            titik produksi memasangnya. Menjawab apakah dua
                            titik pasang itu memberi angka yang sama

ARM B TIDAK MENYENTUH `app/`, dan ia tidak menyalin detector-nya. `Anatomy`
sudah membawa `leg_out_from`, jadi aturannya bisa ditegakkan sebagai saringan
di atas keluaran detector produksi. Sebuah salinan scan akan menambah
implementasi kedua dari aturan yang sama, dan dua implementasi aturan yang sama
adalah cara sebuah sapuan mulai mengukur bug-nya sendiri.

SEL DIPATOK DI 30m untuk pass pertama, sama seperti `tools/ob_variants.py`.
Pakai `--cells all` untuk mengonfirmasi arm yang lolos di 12 sel. Dua tahap
karena satu arm di 12 sel butuh belasan menit, dan menyapu sepuluh arm di sana
lebih dulu berarti membayar dua jam untuk mengetahui arm mana yang layak.

ATURAN LULUS, ditulis sebelum angkanya dilihat. Sebuah varian dinyatakan LEBIH
BAIK dari produksi hanya bila exp_r-nya lebih tinggi DAN walk-forward-nya penuh
DAN n-nya masih di atas `MIN_GROUP`, DAN |t| Welch-nya melewati ambang
Bonferroni atas jumlah pembanding.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import pathlib
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect.supply_demand import detect as detect_supply_demand
from app.models import Candle, SupplyDemandParams, Zone
# POPULASI DARI RIG, BUKAN DARI DEFAULT PARAMS, dan ini bukan detail. Versi
# pertama berkas ini memakai `SupplyDemandParams(max_zones_per_side=0,
# show_broken=True)` dan itu meleset DUA knob dari populasi yang setiap angka
# S&D lain di repo ini diukur di atasnya: `merge_overlap_pct` 0,6 lawan 1,0 dan
# `departure_min_atr` 2,0 lawan 0,0. Lengan A-nya menghasilkan n=274 di 30m
# sementara gerbang 12-sel menyimpan 895 di timeframe yang sama, dan sepuluh
# lengan itu jadi varian dari populasi ketiga yang tidak sebanding dengan apa
# pun. `_selftest` di bawah sekarang mengikatnya.
from tools.calibrate import POPULATION
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, one_sample_t, welch
from tools.gate_sweep import CELL_SETS
from tools.gate_sweep import cell_rows as _cell_rows

CELLS = CELL_SETS["30m"]
MIN_FOLD = 20
MIN_GROUP = 30
CACHE = (
    pathlib.Path(__file__).resolve().parents[2] / "docs" / "sd_variants_rows_cache.json"
)

#: Body minimum lilin yang KELUAR dari base, sebagai pecahan rentangnya sendiri.
#: Angka ini datang dari kodifikasi Seiden yang beredar, bukan dari sapuan ini.
EXIT_BODY_RATIO = 0.70


def detect_exit_body(
    candles: list[Candle], params: SupplyDemandParams
) -> tuple[list[Zone], dict[str, float]]:
    """Produksi, lalu buang zona yang lilin keluarnya berbadan tipis.

    Lilin keluar adalah `anatomy.leg_out_from`, yaitu bar PERTAMA leg-out, dan
    itu memang yang sumbernya sebut: "the candle that exits the base".
    """
    zones, stats = detect_supply_demand(candles, params)
    kept = []
    dropped = 0
    for z in zones:
        i = z.anatomy.leg_out_from if z.anatomy else None
        if i is None or not (0 <= i < len(candles)):
            # TIDAK BISA DINILAI BUKAN LULUS. Sebuah zona tanpa anatomy akan
            # lolos diam diam kalau default-nya "simpan", dan arm ini akan
            # mengukur populasi yang lebih besar dari yang dinyatakan namanya.
            dropped += 1
            continue
        k = candles[i]
        rng = k.high - k.low
        if rng <= 0.0 or abs(k.close - k.open) / rng < EXIT_BODY_RATIO:
            dropped += 1
            continue
        kept.append(z)
    stats = dict(stats)
    stats["rejected_thin_exit_candle"] = dropped
    return kept, stats


#: Nama varian, detector-nya, dan parameternya.
#:
#: `None` sebagai detector berarti `supply_demand.detect` yang asli.
VARIANTS: list[dict] = [
    # LENGAN A MELACAK PRODUKSI. Kunci cache memuat set sel dan nama lengan,
    # TIDAK memuat kodenya, jadi baris yang ditulis sebelum detector-nya berubah
    # akan disajikan lagi setelahnya tanpa satu pesan pun. Jebakan itu sudah
    # menggigit di `tools/ob_variants.py` pada 6 September 2026.
    {"name": "A produksi saat ini", "fn": None, "p": {}},
    {"name": "B lilin keluar body 0,70", "fn": detect_exit_body, "p": {}},
    {"name": "C body ratio 0,7 kedua kaki", "fn": None, "p": {"impulse_body_ratio": 0.7}},
    {"name": "D body ratio 0,6", "fn": None, "p": {"impulse_body_ratio": 0.6}},
    {"name": "E body ratio 0,4", "fn": None, "p": {"impulse_body_ratio": 0.4}},
    {"name": "F proximal_basis body", "fn": None, "p": {"proximal_basis": "body"}},
    {"name": "G base_max_bars 3", "fn": None, "p": {"base_max_bars": 3}},
    {"name": "H base_max_bars 12", "fn": None, "p": {"base_max_bars": 12}},
    {"name": "I impulse_atr 1,5", "fn": None, "p": {"impulse_atr": 1.5}},
    {"name": "J base_max_atr 1,5", "fn": None, "p": {"base_max_atr": 1.5}},
    # LENGAN K MENGUKUR RIG-NYA SENDIRI, bukan sebuah aturan baru. Produksi
    # mengirim `departure_min_atr = 2.0` dan menolak KANDIDAT di titik deteksi;
    # `tools/gate_sweep.py` memasang ambang yang sama sebagai SARINGAN atas
    # baris yang sudah selesai. Predikatnya sama, titik pasangnya tidak, dan
    # menolak kandidat lebih awal mengubah apa yang tersisa untuk `_dedupe` dan
    # `mark_crowding`. Kalau kedua angka berbeda, seluruh angka gerbang S&D di
    # repo ini mengukur sesuatu yang tidak persis dijalankan produksi.
    {"name": "K departure_min_atr 2,0 saat deteksi", "fn": None,
     "p": {"departure_min_atr": 2.0}},
    # LENGAN L SAMPAI O DIUKUR DI ATAS K, BUKAN DI ATAS A, dan itu perbedaan
    # yang menentukan. Produksi MENGIRIM gerbangnya, jadi sebuah aturan yang
    # membantu populasi tanpa gerbang belum tentu membantu populasi yang sudah
    # disaring gerbang itu - keduanya bisa menyaring hal yang sama. Persis itu
    # yang terjadi di order block pada 6 September 2026: gerbang departure-nya
    # berhenti memisahkan begitu filter impuls-dari-close dikirim.
    {"name": "L K + proximal_basis body", "fn": None,
     "p": {"departure_min_atr": 2.0, "proximal_basis": "body"}},
    {"name": "M K + impulse_atr 1,5", "fn": None,
     "p": {"departure_min_atr": 2.0, "impulse_atr": 1.5}},
    {"name": "N K + body ratio 0,7", "fn": None,
     "p": {"departure_min_atr": 2.0, "impulse_body_ratio": 0.7}},
    {"name": "O K + body + impulse_atr 1,5", "fn": None,
     "p": {"departure_min_atr": 2.0, "proximal_basis": "body", "impulse_atr": 1.5}},
    # ATURAN MITIGASI, dan ini celah yang riset temukan, bukan tebakan. Empat
    # aturan yang saling bertentangan beredar di literatur: mati saat disentuh
    # sekali, mati saat close menembus, mati saat sumbu menembus, dan melemah
    # setelah beberapa tes. PENETRASI PERSENTASE TIDAK ADA DI SATU SUMBER PUN,
    # tidak di literatur metodenya dan tidak di tiga belas indikator TradingView
    # terpopuler yang kodenya dibaca. Kita mengirim `mitigation_pct = 0.5`.
    #
    # Dua ujung grid-nya memetakan ke dua aturan yang MEMANG ada di literatur:
    # 0,0 adalah "sekali pakai, mati saat disentuh", 1,0 adalah "hidup sampai
    # tertembus penuh". Diukur sendiri sendiri dan di atas gerbang produksi,
    # karena pelajaran lengan L adalah bahwa keduanya bisa menjawab berbeda.
    {"name": "P mitigation_pct 0,0 sekali pakai", "fn": None,
     "p": {"mitigation_pct": 0.0}},
    {"name": "Q mitigation_pct 1,0 tembus penuh", "fn": None,
     "p": {"mitigation_pct": 1.0}},
    {"name": "R K + mitigation_pct 0,0", "fn": None,
     "p": {"departure_min_atr": 2.0, "mitigation_pct": 0.0}},
    {"name": "S K + mitigation_pct 1,0", "fn": None,
     "p": {"departure_min_atr": 2.0, "mitigation_pct": 1.0}},
    # AMBANG IMPULS 3,0, KARENA DUA RUTE MQL5 YANG BERBEDA MENDARAT DI SANA.
    # `Liquidity Zone` menyatakannya sebagai default `RatioMultiplier`, dan
    # artikel MQL5 20904 memperolehnya sebagai median cluster pada 9.663 pasangan
    # base-exit XAUUSD M5. Kebetulan yang layak diuji, BUKAN konfirmasi: rute
    # kedua meng-cluster geometri lilin tanpa satu variabel outcome pun di dalam
    # pipeline-nya, jadi angkanya menggambarkan bentuk lilin yang paling umum,
    # bukan zona yang paling sering bekerja. Dan besarannya pun tidak sama
    # dengan `impulse_atr` kita: mereka rasio terhadap base, kita rasio terhadap
    # ATR. Diuji karena murah, dilaporkan sebagai apa adanya.
    {"name": "T K + impulse_atr 2,5", "fn": None,
     "p": {"departure_min_atr": 2.0, "impulse_atr": 2.5}},
    {"name": "U K + impulse_atr 3,0", "fn": None,
     "p": {"departure_min_atr": 2.0, "impulse_atr": 3.0}},
]
#: Bonferroni atas jumlah varian yang dibandingkan dengan produksi.
T_THRESHOLD = _critical_t(len(VARIANTS) - 1)


def walk_forward(rows: list[dict]) -> dict:
    """8 fold posisi relatif, di-purge seperti sapuan yang lain."""
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    folds = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = np.array([r["r"] for r in opened if r["exit_pos"] < hi])
        entry: dict = {"fold": k + 1, "n": int(kept.size)}
        entry["readable"] = kept.size >= MIN_FOLD
        if entry["readable"]:
            entry["exp_r"] = float(kept.mean())
        folds.append(entry)
    graded = [f for f in folds if f["readable"]]
    return {
        "graded": len(graded),
        "positive": sum(1 for f in graded if f["exp_r"] > 0),
    }


def rates(rows: list[dict]) -> dict:
    r = np.array([x["r"] for x in rows])
    if not r.size:
        return {"n": 0}
    wins = r[r > 0]
    losses = r[r <= 0]
    gross_loss = float(abs(losses.sum()))
    return {
        "n": int(r.size),
        "exp_r": round(float(r.mean()), 4),
        "t_vs_zero": round(one_sample_t(r), 3) if r.size > 1 else None,
        "win_rate": round(float(wins.size / r.size), 4),
        "profit_factor": round(float(wins.sum()) / gross_loss, 3) if gross_loss else None,
        "mean_win_r": round(float(wins.mean()), 4) if wins.size else None,
        "mean_loss_r": round(float(losses.mean()), 4) if losses.size else None,
    }


def run(variant: dict) -> dict:
    """Baris satu varian, di seluruh sel, lewat rig yang sama."""
    params = SupplyDemandParams(**{**POPULATION, **variant["p"]})
    real = variant["fn"] or detect_supply_demand
    original = DETECTORS["supply_demand"]
    DETECTORS["supply_demand"] = lambda candles, _ignored: real(candles, params)
    try:
        rows: list[dict] = []
        for symbol, interval in CELLS:
            with contextlib.redirect_stdout(sys.stderr):
                got, _span = _cell_rows("supply_demand", symbol, interval)
            rows.extend(got)
    finally:
        DETECTORS["supply_demand"] = original

    out = {"variant": variant["name"], **rates(rows)}
    if out.get("n", 0) >= MIN_GROUP:
        wf = walk_forward(rows)
        out["wf_positive"], out["wf_graded"] = wf["positive"], wf["graded"]
    out["_rows"] = [
        {"cell": x["cell"], "r": x["r"], "pos": x["pos"], "exit_pos": x["exit_pos"]}
        for x in rows
    ]
    out["_r"] = [x["r"] for x in rows]
    return out


def _selftest() -> None:
    """Arm B harus benar benar MEMISAHKAN populasi, bukan cuma dinamai.

    Tanpa ini sebuah bug di predikatnya akan membuat B mengembalikan populasi
    yang sama dengan produksi, dan sapuannya akan melaporkan dua lengan identik
    sebagai temuan. Bentuk kegagalan yang persis sama sudah terjadi dua kali di
    repo ini: lengan D di `tools/brk_variants.py` dan versi pertama lengan
    lantai kotak di berkas yang sama.
    """
    from tools.quant import clean

    # POPULASI RIG HARUS PERSIS. Kalau salah satu knob ini bergeser, seluruh
    # sapuan jadi varian dari populasi yang tak seorang pun mengukurnya.
    assert POPULATION["departure_min_atr"] == 0.0, POPULATION
    assert POPULATION["merge_overlap_pct"] == 1.0, POPULATION
    assert POPULATION["max_zones_per_side"] == 0, POPULATION

    c, _d, _r = clean("XAUUSD", "30m")
    c = c[:4000]
    p = SupplyDemandParams(**POPULATION)
    base, _ = detect_supply_demand(c, p)
    strict, stats = detect_exit_body(c, p)
    assert 0 < len(strict) < len(base), (len(strict), len(base))
    assert stats["rejected_thin_exit_candle"] == len(base) - len(strict)
    # Dan setiap yang TERSISA harus benar benar lolos ambangnya, bukan cuma
    # ikut terbawa karena saringannya salah arah.
    for z in strict:
        k = c[z.anatomy.leg_out_from]
        assert abs(k.close - k.open) / (k.high - k.low) >= EXIT_BODY_RATIO, z.id


def main() -> int:
    global CELLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="30m", choices=sorted(CELL_SETS))
    ap.add_argument("--only", default="",
                    help="awalan nama varian, dipisah koma. Kosong berarti semua")
    args = ap.parse_args()
    CELLS = CELL_SETS[args.cells]
    wanted = tuple(x.strip() for x in args.only.split(",") if x.strip())
    todo = [v for v in VARIANTS if not wanted or v["name"].startswith(wanted)]
    print(f"  cells={args.cells} ({len(CELLS)} sel) varian={len(todo)} "
          f"bonferroni={T_THRESHOLD:.4f}", file=sys.stderr)

    cached = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    results = []
    for v in todo:
        # KUNCI CACHE MEMUAT SET SELNYA, alasan yang sama seperti di
        # `tools/ob_variants.py`: tanpa itu hasil dua sel akan dibaca sebagai
        # hasil dua belas sel pada run berikutnya, tanpa pesan kesalahan.
        key = f"{args.cells}|{v['name']}"
        if key in cached:
            r = cached[key]
            print(f"  {v['name']} dari cache, n={r.get('n')}", file=sys.stderr)
        else:
            print(f"  {v['name']}...", file=sys.stderr, flush=True)
            r = run(v)
            cached[key] = r
            CACHE.write_text(json.dumps(cached), encoding="utf-8")
        results.append(r)
        print(f"    n={r.get('n')} exp_r={r.get('exp_r')} WR={r.get('win_rate')} "
              f"PF={r.get('profit_factor')} wf={r.get('wf_positive')}/"
              f"{r.get('wf_graded')}", file=sys.stderr)

    # PER TIMEFRAME, karena sebuah varian yang menyelamatkan satu timeframe dan
    # memperburuk yang lain akan terbaca sehat di angka gabungan.
    for r in results:
        rows = r.get("_rows") or []
        per_tf: dict[str, dict] = {}
        for tf in sorted({x["cell"].split()[-1] for x in rows}):
            sub = [x for x in rows if x["cell"].endswith(f" {tf}")]
            per_tf[tf] = rates(sub)
            if len(sub) >= MIN_GROUP:
                wf = walk_forward(sub)
                per_tf[tf]["wf_positive"] = wf["positive"]
                per_tf[tf]["wf_graded"] = wf["graded"]
        r["per_timeframe"] = per_tf
        r.pop("_rows", None)

    base = results[0]
    base_r = np.array(base.pop("_r"))
    for r in results[1:]:
        arm = np.array(r.pop("_r"))
        if arm.size >= MIN_GROUP and base_r.size >= MIN_GROUP:
            r["welch_t_vs_baseline"] = round(welch(arm, base_r), 3)
            better = (
                r["exp_r"] > base["exp_r"]
                and r.get("wf_graded", 0) > 0
                and r.get("wf_positive") == r.get("wf_graded")
            )
            # LABELNYA MENYEBUT LENGAN A, BUKAN PRODUKSI, dan perbedaan itu
            # bukan kerapian. Lengan A adalah populasi rig, yang menjalankan
            # `departure_min_atr = 0.0`; produksi mengirim 2,0. Versi pertama
            # baris ini berbunyi "LEBIH BAIK dari produksi" dan pada 6 September
            # 2026 ia mencetak itu untuk lengan L, yang Welch t-nya lawan
            # produksi sebenarnya +0,272 - jauh di bawah ambang yang sama.
            # Sebuah lengan yang mengalahkan baseline tanpa gerbang belum
            # mengalahkan apa pun yang dikirim.
            r["verdict"] = (
                "lebih baik dari lengan A, BUKAN dari produksi" if better and
                abs(r["welch_t_vs_baseline"]) >= T_THRESHOLD
                else "lebih baik dari A tapi tidak signifikan" if better
                else "tidak lebih baik dari A"
            )
        else:
            r["verdict"] = "tidak terukur, n di bawah MIN_GROUP"

    json.dump({
        "question": "aturan deteksi supply and demand mana yang mengubah outcome",
        "cell_set": args.cells,
        "cells": [f"{s} {i}" for s, i in CELLS],
        "sourced_arm": (
            "B, lilin keluar body 0,70. Satu satunya arm yang angkanya datang "
            "dari kodifikasi Seiden dan bukan dari sapuan ini"
        ),
        "t_threshold_bonferroni": round(T_THRESHOLD, 4),
        "min_group": MIN_GROUP,
        "baseline_is_not_production": (
            "Lengan A menjalankan `departure_min_atr = 0.0`, populasi rig. "
            "Produksi mengirim 2,0, yaitu lengan K. Setiap `welch_t_vs_baseline` "
            "di bawah ini diukur lawan A; untuk pertanyaan pengiriman, "
            "bandingkan lawan K."
        ),
        "baseline": base,
        "variants": results[1:],
    }, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    _selftest()
    raise SystemExit(main())
