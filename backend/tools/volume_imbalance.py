"""Praregistrasi: apakah VOLUME IMBALANCE memisahkan, atau ia FVG dengan nama lain?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.volume_imbalance > ../docs/volume_imbalance.json

Ditulis 2 September 2026, SEBELUM satu angka pun dihitung.

===========================================================================
1. KENAPA JUSTRU YANG INI, DARI SELURUH VOCABULARY SMC
===========================================================================

Ditanya pemiliknya apakah Zonelab perlu menambah grup SMC. Dua penyelidikan
dijalankan paralel: inventaris registry-nya sendiri, dan daftar konsep SMC
kanonik dari enam sumber luar. Keduanya bertemu di satu jawaban.

Registry-nya sudah 21 layer dan vocabulary SMC hampir seluruhnya sudah ada di
sana dengan nama lain. Yang penting bukan panjang daftarnya, tapi peta aliasnya:
MSS dan CHoCH didefinisikan identik di sumber-sumbernya; EQH/EQL adalah
`liquidity.equal_levels`; turtle soup, stop hunt dan liquidity grab satu kondisi
dengan tiga nama; mitigation block tidak punya satu pun definisi di enam sumber
itu yang memisahkannya dari order block, dan pertanyaan yang ia ajukan sudah
dijawab `ZoneState.MITIGATED`; BPR adalah overlap FVG dan IFVG yang
`poi.confluence` sudah hitung; inducement sudah ditolak tertulis di
`app/liquidity.py:93-118` dengan alasannya.

Yang TERSISA setelah peta alias itu dipakai: volume imbalance. Geometrinya
body-to-body pada dua bar BERDAMPINGAN, dan itu jatuh tepat di celah antara dua
detector yang sudah ada. `imbalance._gap` wick-to-wick pada tiga bar; `chart_gaps`
menuntut tidak ada overlap sama sekali. Sebuah body yang tidak overlap sementara
wick-nya masih bersentuhan tidak akan pernah terdeteksi keduanya.

Dan repo ini sudah MENOLAKNYA secara tertulis. `app/detect/imbalance.py:44-47`:
"Body-to-body is a DIFFERENT NAMED PATTERN (a volume imbalance), not a variant
of this one". Penolakan itu benar sebagai keputusan lingkup dan bukan pengukuran,
jadi file ini yang mengukurnya.

===========================================================================
2. HIPOTESIS, DAN KENAPA ADA YANG KEDUA
===========================================================================

H1: exp_R zona volume imbalance yang lolos gerbangnya sendiri > 0 di 30 menit,
    diuji satu sampel lawan nol.

H2: populasi VI TIDAK identik dengan populasi FVG. Diukur sebagai fraksi zona VI
    yang band-nya overlap sebuah zona FVG di bar yang berdekatan. Kalau
    fraksinya tinggi, H1 lolos pun tidak memberi objek baru, ia memberi nama
    kedua untuk objek yang sama, dan repo ini punya empat penolakan terukur di
    `docs/BACKLOG.md` justru untuk kasus itu.

H2 DIUJI LEBIH DULU dalam pembacaan, karena ia bisa membatalkan arti H1. Sebuah
edge yang nyata pada objek yang sudah digambar bukan alasan menggambarnya lagi.

Ambang t Bonferroni untuk DUA kelompok. Walk-forward 8 fold, minimal 7 bertanda
sama untuk H1.

===========================================================================
3. RIG, DAN APA YANG TIDAK DISENTUH
===========================================================================

TIDAK ADA APA PUN YANG DITAMBAHKAN KE `app/`. Detector VI hidup di file ini dan
disuntikkan ke `DETECTORS` sementara, trik yang sama yang
`detectors_costed.resolved_as` sudah pakai dan dengan batas yang sama: satu
proses, satu thread, `finally` yang mengembalikannya. Itu disengaja. `BACKLOG.md`
mencatat empat objek gambar yang diusulkan dan ditolak setelah diukur, jadi
menambah layer sebelum ada angkanya adalah urutan yang salah.

Zona dibangun lewat `imbalance._finish`, bukan lewat konstruksi Zone sendiri,
supaya lifecycle, `first_test_time`, `penetration_pct` dan kontraknya identik
dengan keempat detector imbalance yang sudah ada. Sebuah zona VI yang
lifecycle-nya dihitung dengan aturan berbeda tidak bisa dibandingkan ke mereka.

Gerbangnya `departure_atr` yang sama, dan ARAHNYA DIUJI KEDUA-DUANYA sebagai
bacaan, karena untuk fvg gerbang itu terukur TERBALIK (sisi bawah +0,2188 R di
30 menit, `docs/fvg_inverted.json`) sementara untuk supply_demand dan
order_block ia terukur benar arah. VI keluarga imbalance, jadi priornya sisi
bawah, dan menuliskannya di depan lebih baik daripada memilih sesudahnya.

===========================================================================
4. YANG TIDAK DIJANJIKAN
===========================================================================

Bar halus 30 menit adalah 5 menit, rasio 6, terkasar di tabel `FINER`. Kontrol
di `docs/lowtf_resolution.json` dan `docs/fvg_resolution.json` menunjukkan rasio
kasar MENGGELEMBUNGKAN ekspektasi di setiap sel yang diuji, jadi angka di sini
batas ATAS. Kalau H1 lolos DAN H2 lolos, kontrol resolusi 1 menit wajib
dijalankan sebelum satu baris pun ditambahkan ke `app/`.

`min_gap_atr` diambil dari `ImbalanceParams` apa adanya, tidak di-tune. Docstring
`imbalance.py` sudah mencatat bahwa threshold itu membeli keterbacaan chart dan
membayarnya dengan edge terukur, jadi menggesernya di sini akan mencampur dua
pertanyaan.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect.imbalance import _arrays, _finish, _present
from app.indicators import wilder_atr
from app.models import ImbalanceParams, Zone, ZoneKind, ZoneSide
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, GATE, cell_rows, one_sample_t

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
T_THRESHOLD = _critical_t(2)
MIN_SIGN_FOLDS = 7
#: Fraksi overlap dengan FVG di atas mana populasinya dinyatakan duplikat.
#: 0,5 dipilih SEBELUM melihat angkanya: separuh berarti objeknya lebih sering
#: menjadi FVG daripada tidak, dan sebuah nama kedua untuk itu adalah persis apa
#: yang peta alias di bagian 1 memperingatkan.
DUPLICATE_AT = 0.5


def detect_volume_imbalance(
    candles: list, params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Body dua bar BERDAMPINGAN tidak overlap, sementara wick-nya bersentuhan.

    Itu definisi yang membedakannya dari dua objek yang sudah ada, dan kedua
    syaratnya mengikat:

      body tidak overlap    memisahkannya dari bar biasa
      wick BERSENTUHAN      memisahkannya dari chart gap, yang menuntut tidak
                            ada overlap sama sekali

    Bandingkan `imbalance._gap`, yang wick-to-wick pada bar `mid-1` dan `mid+1`,
    yaitu tiga bar dan wick lawan wick. Sebuah VI bisa ada tanpa satu pun FVG di
    sekitarnya, dan itu yang H2 ukur.

    Bandingkan juga `_arrays` yang mengembalikan open juga: body butuh open, dan
    keempat detector imbalance yang ada tidak pernah membacanya.
    """
    if len(candles) < params.atr_period + 4:
        return [], {}
    # `_arrays` MEMANG mengembalikan open, dan tiga dari empat pemanggilnya
    # membuangnya sebagai `_open`. Detector ini yang pertama membacanya, karena
    # body butuh open sementara wick tidak.
    time, openp, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)
    body_hi = np.maximum(openp, close)
    body_lo = np.minimum(openp, close)

    found: list[Zone] = []
    stats: dict[str, float] = {}
    for i in range(params.atr_period + 1, len(candles) - 1):
        scale = float(atr[i])
        if scale <= 0:
            continue
        up = body_hi[i] < body_lo[i + 1] and high[i] >= low[i + 1]
        down = body_lo[i] > body_hi[i + 1] and low[i] <= high[i + 1]
        if not (up or down):
            continue
        top = float(body_lo[i + 1]) if up else float(body_lo[i])
        bottom = float(body_hi[i]) if up else float(body_hi[i + 1])
        if (top - bottom) / scale < params.min_gap_atr:
            continue
        # DEPARTURE DIUKUR SAMA DENGAN KELUARGANYA: tinggi celahnya dalam ATR.
        # `detect_fvg` memakai tinggi gap, jadi memakai besaran lain di sini akan
        # membuat gerbang 2,0 ATR menyaring dua hal berbeda dengan satu nama.
        # KIND-nya FVG, dan itu disengaja: `ZoneKind` adalah enum yang
        # frontend petakan ke warna dan caption, jadi menambah nilai baru di sana
        # berarti menyentuh `app/` untuk objek yang belum diukur. Yang
        # memisahkannya `id` ber-prefix `VI-` di bawah, yang cukup untuk studi
        # ini dan tidak cukup untuk produksi - dan itu batas yang benar sampai
        # angkanya ada.
        zone = _finish(
            ZoneKind.FVG,
            ZoneSide.DEMAND if up else ZoneSide.SUPPLY,
            top, bottom, i, i + 1, time, high, low, close, atr, params,
            (top - bottom) / scale,
        )
        if zone is not None:
            # Id-nya diberi prefix supaya ia tidak pernah bertabrakan dengan id
            # FVG di bar yang sama. Dua objek berbeda dengan id sama akan
            # membuat gate idempotensi journal menganggapnya satu.
            zone.id = f"VI-{zone.id.split('-', 1)[1]}"
            zone.note = f"volume imbalance: {(top - bottom) / scale:.2f} ATR"
            found.append(zone)
    stats["found"] = float(len(found))
    return _present(found, params, stats,
                    int(candles[-1].time) if candles else 0)


def size_census(symbol: str, interval: str, bars: int) -> dict:
    """Berapa sering geometrinya ada, dan SEBESAR APA. Ini temuan sebenarnya.

    Run pertama menemukan 4 zona di XAUUSD dan 0 di BTCUSD, dan n sekecil itu
    mudah dibaca sebagai "data kurang". Ia bukan. Sensus ini memisahkan tiga hal
    yang run itu menggabungkan: seberapa sering geometrinya MUNCUL, sebesar apa
    ia, dan berapa yang lolos `min_gap_atr`.

    Satu dugaan diuji dan GUGUR di sini, dan dicatat supaya tidak diulang: saya
    menduga VI jarang karena deret kontinu membuat `open[i+1] == close[i]`.
    Terukur, itu salah - 98,4 persen bar XAUUSD dan 84,3 persen bar BTCUSD
    justru punya open yang BEDA dari close sebelumnya, dengan diskontinuitas
    median 0,035 dan 0,890 dalam harga. Diskontinuitasnya umum; yang kecil
    ukurannya relatif terhadap ATR.
    """
    from tools.quant import clean

    candles, _, _ = clean(f"mt5:{symbol}", interval, bars)
    if len(candles) < 50:
        return {"error": "bar terlalu sedikit"}
    params = ImbalanceParams(max_zones_per_side=0)
    _t, openp, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)
    body_hi = np.maximum(openp, close)
    body_lo = np.minimum(openp, close)
    up = (body_hi[:-1] < body_lo[1:]) & (high[:-1] >= low[1:])
    down = (body_lo[:-1] > body_hi[1:]) & (low[:-1] <= high[1:])
    size = np.where(up, body_lo[1:] - body_hi[:-1],
                    np.where(down, body_lo[:-1] - body_hi[1:], 0.0))
    scale = atr[:-1]
    ok = (up | down) & (scale > 0)
    if not ok.any():
        return {"bars": len(candles), "n_geometry": 0}
    rel = size[ok] / scale[ok]
    return {
        "bars": len(candles),
        "n_geometry": int(ok.sum()),
        "pct_of_bars": float(100 * ok.mean()),
        "size_atr_p50": float(np.percentile(rel, 50)),
        "size_atr_p90": float(np.percentile(rel, 90)),
        "size_atr_p99": float(np.percentile(rel, 99)),
        "size_atr_max": float(rel.max()),
        "min_gap_atr": params.min_gap_atr,
        "n_clearing_min_gap": int((rel >= params.min_gap_atr).sum()),
        "pct_clearing_min_gap": float(100 * (rel >= params.min_gap_atr).mean()),
        "median_size_in_price": float(np.median(size[ok])),
        "median_atr_in_price": float(np.median(scale[ok])),
    }


def overlap_with_fvg(symbol: str, interval: str, bars: int) -> dict:
    """H2: berapa fraksi zona VI yang band-nya juga sebuah FVG?

    Overlap diuji pada BAND dan pada WAKTU sekaligus. Band saja akan menghitung
    sebuah FVG dari minggu lalu di harga yang sama sebagai duplikat, dan itu
    bukan pertanyaannya: pertanyaannya apakah objek yang SAMA muncul dua kali.
    Jendela waktunya tiga bar ke tiap arah, karena sebuah VI di bar i dan i+1
    dan sebuah FVG yang berpusat di i atau i+1 adalah formasi yang sama.
    """
    from tools.quant import clean

    candles, _, _ = clean(f"mt5:{symbol}", interval, bars)
    if not candles:
        return {"error": "0 bar"}
    params = ImbalanceParams(max_zones_per_side=0)
    vis, _ = detect_volume_imbalance(candles, params)
    fvgs, _ = DETECTORS["fvg"](candles, params)
    step = int(candles[1].time - candles[0].time) if len(candles) > 1 else 0
    window = 3 * step
    hit = 0
    for v in vis:
        for f in fvgs:
            if abs(f.time_from - v.time_from) > window:
                continue
            if v.side is not f.side:
                continue
            if min(v.top, f.top) > max(v.bottom, f.bottom):
                hit += 1
                break
    return {"n_vi": len(vis), "n_fvg": len(fvgs), "n_vi_also_fvg": hit,
            "fraction_duplicate": (hit / len(vis)) if vis else None}


def _walk(rows: list[dict], side: str) -> dict:
    """8 fold, tanda ekspektasi sisi `side` di tiap fold."""
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    out = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        want = [r["r"] for r in kept
                if (r["cleared"] if side == "above" else not r["cleared"])]
        entry: dict = {"fold": k + 1, "n": len(want),
                       "purged": len(opened) - len(kept)}
        if len(want) >= 20:
            entry["exp_r"] = float(np.mean(want))
            entry["readable"] = True
        else:
            entry["readable"] = False
        out.append(entry)
    graded = [e for e in out if e["readable"]]
    return {"folds": out, "graded": len(graded),
            "positive": sum(1 for e in graded if e["exp_r"] > 0)}


def judge(side_stats: dict, wf: dict) -> tuple[bool, str]:
    """H1 untuk satu sisi gerbang, dipisah supaya `--selfcheck` bisa menyuntik."""
    raw = side_stats.get("t_vs_zero")
    t0 = float(raw) if isinstance(raw, (int, float)) else float("nan")
    ok = bool((side_stats.get("exp_r") or 0.0) > 0
              and t0 == t0 and abs(t0) > T_THRESHOLD
              and wf.get("graded", 0) >= FOLDS
              and wf.get("positive", 0) >= MIN_SIGN_FOLDS)
    return ok, ("LOLOS" if ok else "TIDAK LOLOS")


def selfcheck() -> int:
    wf_ok = {"graded": FOLDS, "positive": FOLDS}
    strong = {"exp_r": 0.2, "t_vs_zero": 8.0}
    assert judge(strong, wf_ok)[0] is True
    assert judge({**strong, "exp_r": -0.2}, wf_ok)[0] is False
    assert judge({**strong, "t_vs_zero": 1.9}, wf_ok)[0] is False
    assert judge({**strong, "t_vs_zero": float("nan")}, wf_ok)[0] is False
    assert judge({**strong, "t_vs_zero": None}, wf_ok)[0] is False
    assert judge(strong, {"graded": 2, "positive": 2})[0] is False
    assert judge(strong, {"graded": FOLDS, "positive": 6})[0] is False
    assert judge({}, {})[0] is False
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=40000)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()

    out: dict = {
        "preregistration": {
            "source": "tools/volume_imbalance.py, 2026-09-02",
            "h1": "exp_R zona volume imbalance > 0 di 30m, per sisi gerbang",
            "h2": f"populasi VI tidak duplikat FVG, fraksi overlap < {DUPLICATE_AT}",
            "why": "satu-satunya geometri SMC yang tidak tertangkap detector "
                   "mana pun: body-to-body dua bar berdampingan, di antara "
                   "FVG (wick-to-wick tiga bar) dan chart gap (tanpa overlap)",
            "refused_in_writing_at": "app/detect/imbalance.py:44-47",
            "t_threshold_bonferroni_2": T_THRESHOLD,
            "gate_atr": GATE, "folds": FOLDS,
            "min_sign_folds": MIN_SIGN_FOLDS,
            "cells": [f"{s} {i}" for s, i in CELLS],
            "nothing_added_to_app": True,
            "caveat": "bar halus 5m rasio 6, batas ATAS; kontrol resolusi 1m "
                      "wajib sebelum menambah apa pun ke app/",
        },
        "size_census": {},
        "h2_duplicate_check": {},
        "cells": {},
    }

    # SENSUS UKURAN DULU, karena ia yang menjelaskan n-nya.
    for symbol, interval in CELLS:
        with contextlib.redirect_stdout(sys.stderr):
            got = size_census(symbol, interval, args.bars)
        out["size_census"][f"{symbol} {interval}"] = got
        print(f"  sensus {symbol} {interval}: geometri {got.get('n_geometry')} "
              f"({got.get('pct_of_bars')}% bar), ukuran median "
              f"{got.get('size_atr_p50')} ATR, lolos min_gap "
              f"{got.get('n_clearing_min_gap')}", file=sys.stderr)

    # H2, karena ia bisa membatalkan arti H1.
    for symbol, interval in CELLS:
        with contextlib.redirect_stdout(sys.stderr):
            got = overlap_with_fvg(symbol, interval, args.bars)
        out["h2_duplicate_check"][f"{symbol} {interval}"] = got
        print(f"  H2 {symbol} {interval}: {got}", file=sys.stderr)
    fracs = [v.get("fraction_duplicate")
             for v in out["h2_duplicate_check"].values()
             if v.get("fraction_duplicate") is not None]
    out["h2_max_duplicate_fraction"] = max(fracs) if fracs else None
    out["h2_distinct_population"] = bool(
        fracs and max(fracs) < DUPLICATE_AT)

    # H1, lewat rig berbiaya yang sama dengan setiap detector lain.
    original = DETECTORS.get("volume_imbalance")
    DETECTORS["volume_imbalance"] = detect_volume_imbalance
    try:
        pooled: list[dict] = []
        for symbol, interval in CELLS:
            label = f"{symbol} {interval}"
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    rows, span = cell_rows("volume_imbalance", symbol, interval)
            except Exception as exc:
                out["cells"][label] = {"error": str(exc)}
                print(f"  H1 {label}: GAGAL {exc}", file=sys.stderr)
                continue
            pooled.extend(rows)
            above = np.array([r["r"] for r in rows if r["cleared"]])
            below = np.array([r["r"] for r in rows if not r["cleared"]])
            out["cells"][label] = {
                "bars": span,
                "n_above": int(above.size), "n_below": int(below.size),
                "exp_r_above": float(above.mean()) if above.size else None,
                "exp_r_below": float(below.mean()) if below.size else None,
            }
            print(f"  H1 {label}: n atas {above.size} n bawah {below.size}",
                  file=sys.stderr)
    finally:
        if original is None:
            DETECTORS.pop("volume_imbalance", None)
        else:
            DETECTORS["volume_imbalance"] = original

    if not pooled:
        out["verdict"] = "tidak ada baris"
        json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
        print(file=sys.stdout)
        return 0

    out["sides"] = {}
    for side in ("above", "below"):
        vals = np.array([r["r"] for r in pooled
                         if (r["cleared"] if side == "above"
                             else not r["cleared"])])
        stats = {
            "n": int(vals.size),
            "exp_r": float(vals.mean()) if vals.size else None,
            "t_vs_zero": one_sample_t(vals) if vals.size > 1 else None,
        }
        wf = _walk(pooled, side)
        ok, verdict = judge(stats, wf)
        out["sides"][side] = {**stats, "walk_forward": wf,
                              "h1_passed": ok, "verdict": verdict}
        print(f"  sisi {side}: n {stats['n']} exp {stats['exp_r']} t "
              f"{stats['t_vs_zero']} wf {wf['positive']}/{wf['graded']} "
              f"-> {verdict}", file=sys.stderr)

    passed = [s for s, v in out["sides"].items() if v["h1_passed"]]
    out["h1_passed_sides"] = passed
    out["verdict"] = (
        f"H1 lolos di sisi {', '.join(passed)} DAN H2 populasinya berbeda; "
        "kontrol resolusi 1m wajib berikutnya"
        if passed and out["h2_distinct_population"]
        else f"H1 lolos di sisi {', '.join(passed)} TAPI H2 gagal: "
             f"fraksi duplikat {out['h2_max_duplicate_fraction']}, jadi ia nama "
             "kedua untuk objek yang sudah digambar"
        if passed
        else "H1 TIDAK LOLOS di kedua sisi"
    )
    print(f"  VERDICT: {out['verdict']}", file=sys.stderr)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
