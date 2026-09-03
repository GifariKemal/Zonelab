"""Praregistrasi: apakah shelf S&R DI DEKAT zona mengkondisikan hasilnya?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.shelf_proximity > ../docs/shelf_proximity.json

Ditulis 2 September 2026, SEBELUM satu angka outcome pun dihitung.

===========================================================================
1. KENAPA PERTANYAANNYA BERGESER DARI CONTAINMENT KE KEDEKATAN
===========================================================================

`tools/shelf_conditioned.py` menanyakan apakah zona yang BAND-nya memuat shelf
support/resistance resolve berbeda, dan jawabannya tidak bisa diukur: 1 dari
3.496 zona supply_demand dan 0 dari 3.931 zona fvg. Uraian per filter di
`docs/BACKLOG.md` bagian 3c menunjukkan containment sendiri umum, 4.951 dari
7.063 zona XAUUSD, dan yang memusnahkan populasinya syarat "belum diambil".

Kedekatan adalah pertanyaan yang berbeda dan lebih longgar: shelf tidak harus
berada DI DALAM band, cukup dalam `X` ATR dari tepinya. Itu juga bentuk yang
lebih dekat dengan cara S&R dibaca orang, karena sebuah level jarang jatuh
persis di dalam sebuah zona.

===========================================================================
2. X ADALAH PARAMETER BARU, JADI IA TIDAK BOLEH DIPILIH
===========================================================================

Ini yang membedakan studi ini dari yang sebelumnya. `SWING_N` di studi itu
dipilih dari sensus JUMLAH shelf yang tidak pernah menyentuh outcome, dan itu
perencanaan daya. `X` di sini adalah kondisi yang sedang diuji itu sendiri:
memilihnya setelah melihat hasil adalah memilih hasilnya.

Karena itu SELURUH GRID DINILAI, dan ambang Bonferroni menghitung setiap selnya.
Empat nilai X kali dua detector adalah delapan kelompok yang dinilai. Tidak ada
sel yang boleh dikutip sendirian tanpa menyebut bahwa ia satu dari delapan.

Nilai X-nya dipilih untuk MEMBENTANG, bukan untuk mengenai: 0,25 dan 0,5 adalah
kedekatan ketat, 1,0 satu ATR penuh, dan 2,0 sengaja longgar supaya kalau tidak
satu pun sel memisahkan, hasilnya tidak bisa dijelaskan sebagai jendela yang
kekecilan.

===========================================================================
3. DIPATOK DI KELAHIRAN ZONA
===========================================================================

Sama seperti studi sebelumnya, dan alasannya sama. Versi bar-sentuhan di sana
gugur karena nyaris tautologi: shelf yang dekat zona hampir selalu sudah
tersentuh saat harga sampai ke zonanya. Di kelahiran, kondisinya tetap dan tidak
bisa dicemari oleh sentuhan yang datang kemudian, dan anti-lookahead-nya utuh
karena `knowable_at <= time_from` berarti shelf itu sudah bisa digambar sebelum
zonanya ada.

DUA VARIAN, satu dinilai satu dibaca. Yang DINILAI menuntut shelf masih berdiri
di kelahiran (`taken_at` kosong atau di depan), karena level yang sudah ditembus
bukan lagi S&R. Yang DIBACA mengabaikan syarat itu, supaya kalau populasinya
runtuh lagi, penyebabnya terbaca alih-alih ditebak.

===========================================================================
4. DUA SISI
===========================================================================

Bacaan klasik: shelf low di dekat zona demand memperkuatnya. Bacaan ICT: equal
lows adalah likuiditas yang disapu. Keduanya memprediksi tanda berlawanan dari
kondisi yang sama, jadi hipotesisnya dua arah dan selisih negatif yang
signifikan juga MEMISAHKAN.

===========================================================================
5. ATURAN LOLOS DAN YANG TIDAK DIJANJIKAN
===========================================================================

Per sel: |Welch t| di atas ambang Bonferroni untuk DELAPAN kelompok, n minimal
`MIN_GROUP` di kedua sisi, dan walk-forward minimal 7 dari 8 fold bertanda sama.

Bar halus 30 menit adalah 5 menit, rasio 6, dan kontrol resolusi di
`docs/fvg_resolution.json` menunjukkan rasio kasar menggelembungkan ekspektasi
absolut. Studi ini membandingkan dua kelompok yang diukur di resolusi yang sama,
jadi penggelembungannya sebagian besar meniadakan di selisihnya; angka absolut
per kelompok tetap batas atas.

Kalau tidak satu pun sel memisahkan, yang boleh disimpulkan hanya bahwa S&R
`equal_levels` tidak mengkondisikan hasil zona pada rentang jarak ini di 30
menit. Itu bukan pernyataan tentang S&R secara umum, dan bukan izin untuk
mencoba definisi kelima.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from app.detect import DETECTORS
from app.indicators import wilder_atr
from app.liquidity import equal_levels
from app.models import ZoneSide
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, _params, cell_rows, welch
from tools.quant import clean
from tools.shelf_conditioned import MIN_TOUCHES, SWING_N

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
NAMES = ("supply_demand", "fvg")
#: Dibentangkan, bukan diarahkan. 2,0 sengaja longgar supaya sebuah null tidak
#: bisa dijelaskan sebagai jendela yang kekecilan.
XS = (0.25, 0.5, 1.0, 2.0)
#: Delapan sel dinilai: empat X kali dua detector.
T_THRESHOLD = _critical_t(len(XS) * len(NAMES))
MIN_GROUP = 30
MIN_SIGN_FOLDS = 7


def _gap_atr(zone, level, scale: float) -> float | None:
    """Jarak shelf ke TEPI TERDEKAT band zona, dalam ATR. 0 kalau di dalam."""
    if scale <= 0:
        return None
    if zone.bottom <= level.price <= zone.top:
        return 0.0
    gap = (zone.bottom - level.price if level.price < zone.bottom
           else level.price - zone.top)
    return gap / scale


def _nearest(zone, levels, scale: float, same_side: bool,
             require_standing: bool) -> float | None:
    """Jarak ke shelf sesisi terdekat yang sudah knowable di KELAHIRAN zona."""
    want_high = (zone.side is ZoneSide.SUPPLY) if same_side else (
        zone.side is ZoneSide.DEMAND)
    born = zone.time_from
    best: float | None = None
    for level in levels:
        if level.name.startswith("REQH") is not want_high:
            continue
        if level.knowable_at > born:
            continue
        if require_standing and level.taken_at is not None \
                and level.taken_at <= born:
            continue
        d = _gap_atr(zone, level, scale)
        if d is not None and (best is None or d < best):
            best = d
    return best


def rows_for(name: str, symbol: str, interval: str) -> tuple[list[dict], dict]:
    rows, _ = cell_rows(name, symbol, interval)
    # DERET YANG SAMA PERSIS dengan yang `cell_rows` pakai: ticker telanjang,
    # `bars` default. Run pertama `shelf_conditioned` memakai deret yang lebih
    # pendek dan BTCUSD mencocokkan nol dari baris-barisnya.
    candles, _, _ = clean(symbol, interval)
    params = _params(name)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, params.atr_period)
    times = [c.time for c in candles]
    index = {t: i for i, t in enumerate(times)}
    levels = equal_levels(candles, swing_n=SWING_N, min_touches=MIN_TOUCHES)
    zones, _ = DETECTORS[name](candles, params)
    by_id = {z.id: z for z in zones}

    out: list[dict] = []
    for row in rows:
        zone = by_id.get(row["zone_id"])
        if zone is None:
            continue
        i = index.get(zone.time_from)
        if i is None or i >= len(atr):
            continue
        scale = float(atr[i])
        out.append({
            **row,
            "d_standing": _nearest(zone, levels, scale, True, True),
            "d_any": _nearest(zone, levels, scale, True, False),
        })
    info = {"shelves": len(levels), "n_rows": len(out)}
    for x in XS:
        info[f"n_within_{x}_standing"] = sum(
            1 for r in out if r["d_standing"] is not None and r["d_standing"] <= x)
        info[f"n_within_{x}_any"] = sum(
            1 for r in out if r["d_any"] is not None and r["d_any"] <= x)
    return out, info


def _walk(rows: list[dict], key: str, x: float) -> dict:
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    out = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        near = [r["r"] for r in kept
                if r[key] is not None and r[key] <= x]
        far = [r["r"] for r in kept
               if r[key] is None or r[key] > x]
        entry: dict = {"fold": k + 1, "n_near": len(near), "n_far": len(far),
                       "purged": len(opened) - len(kept)}
        if len(near) >= 20 and len(far) >= 20:
            entry["difference"] = float(np.mean(near) - np.mean(far))
            entry["readable"] = True
        else:
            entry["readable"] = False
        out.append(entry)
    graded = [e for e in out if e["readable"]]
    return {"graded": len(graded),
            "positive": sum(1 for e in graded if e["difference"] > 0)}


def summarise(rows: list[dict], key: str, x: float) -> dict:
    near = np.array([r["r"] for r in rows
                     if r[key] is not None and r[key] <= x])
    far = np.array([r["r"] for r in rows
                    if r[key] is None or r[key] > x])
    out: dict = {"n_near": int(near.size), "n_far": int(far.size),
                 "exp_r_near": float(near.mean()) if near.size else None,
                 "exp_r_far": float(far.mean()) if far.size else None}
    if near.size > 1 and far.size > 1:
        out["difference"] = float(near.mean() - far.mean())
        out["welch_t"] = welch(near, far)
    return out


def judge(stats: dict, wf: dict) -> tuple[bool, str]:
    """Dua sisi. Selisih negatif yang signifikan juga MEMISAHKAN."""
    raw = stats.get("welch_t")
    t = float(raw) if isinstance(raw, (int, float)) else float("nan")
    same = wf.get("positive", 0)
    graded = wf.get("graded", 0)
    ok = bool(t == t and abs(t) > T_THRESHOLD
              and stats.get("n_near", 0) >= MIN_GROUP
              and stats.get("n_far", 0) >= MIN_GROUP
              and graded >= FOLDS
              and max(same, graded - same) >= MIN_SIGN_FOLDS)
    if not ok:
        return False, "TIDAK MEMISAHKAN"
    arah = "lebih baik" if (stats.get("difference") or 0.0) > 0 else "lebih BURUK"
    return True, f"MEMISAHKAN, zona dekat shelf {arah}"


def selfcheck() -> int:
    wf_ok = {"graded": FOLDS, "positive": FOLDS}
    strong = {"welch_t": 6.0, "n_near": 100, "n_far": 100, "difference": 0.2}
    assert judge(strong, wf_ok)[0] is True
    ok, kalimat = judge({**strong, "welch_t": -6.0, "difference": -0.2},
                        {"graded": FOLDS, "positive": 0})
    assert ok is True and "lebih BURUK" in kalimat, kalimat
    assert judge({**strong, "welch_t": 2.4}, wf_ok)[0] is False, "ambang 8 sel"
    assert judge({**strong, "n_near": 5}, wf_ok)[0] is False
    assert judge({**strong, "n_far": 5}, wf_ok)[0] is False
    assert judge(strong, {"graded": 4, "positive": 4})[0] is False
    assert judge(strong, {"graded": FOLDS, "positive": 4})[0] is False
    assert judge({**strong, "welch_t": float("nan")}, wf_ok)[0] is False
    assert judge({}, {})[0] is False

    # Geometri jaraknya, karena satu tanda terbalik di sini membalik seluruh
    # tabelnya tanpa satu test pun berubah warna.
    class _Z:
        top, bottom = 110.0, 100.0
        side = ZoneSide.DEMAND
        time_from = 0

    class _L:
        def __init__(self, price):
            self.price = price
            self.name = "REQL 2x"
            self.knowable_at = 0
            self.taken_at = None

    z = _Z()
    assert _gap_atr(z, _L(105.0), 10.0) == 0.0, "di dalam band = 0"
    assert _gap_atr(z, _L(95.0), 10.0) == 0.5, "di bawah bottom"
    assert _gap_atr(z, _L(120.0), 10.0) == 1.0, "di atas top"
    assert _gap_atr(z, _L(95.0), 0.0) is None, "ATR nol tidak terbaca"
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()

    out: dict = {
        "preregistration": {
            "source": "tools/shelf_proximity.py, 2026-09-02",
            "question": "apakah shelf S&R dalam X ATR dari tepi zona "
                        "mengkondisikan resolved R",
            "why": "containment tidak bisa diukur, 1 dari 3.496 dan 0 dari "
                   "3.931 (docs/shelf_conditioned.json)",
            "x_is_not_chosen": "seluruh grid dinilai dan Bonferroni menghitung "
                               "kedelapan selnya; X adalah kondisi yang diuji, "
                               "jadi memilihnya setelah melihat hasil adalah "
                               "memilih hasilnya",
            "xs": list(XS), "detectors": list(NAMES),
            "judged_cells": len(XS) * len(NAMES),
            "t_threshold_bonferroni": T_THRESHOLD,
            "pinned_at": "kelahiran zona, time_from",
            "judged_variant": "shelf masih BERDIRI di kelahiran",
            "read_variant": "abaikan taken_at, dilaporkan tidak dinilai",
            "two_sided": True,
            "min_group": MIN_GROUP, "folds": FOLDS,
            "min_sign_folds": MIN_SIGN_FOLDS,
            "swing_n": SWING_N, "min_touches": MIN_TOUCHES,
        },
        "cells": {},
        "grid": {},
    }

    for name in NAMES:
        pooled: list[dict] = []
        for symbol, interval in CELLS:
            label = f"{name} {symbol} {interval}"
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    rows, info = rows_for(name, symbol, interval)
            except Exception as exc:
                out["cells"][label] = {"error": str(exc)}
                print(f"  {label}: GAGAL {exc}", file=sys.stderr)
                continue
            out["cells"][label] = info
            pooled.extend(rows)
            print(f"  {label}: {info}", file=sys.stderr)
        if not pooled:
            continue
        for x in XS:
            stats = summarise(pooled, "d_standing", x)
            wf = _walk(pooled, "d_standing", x)
            ok, verdict = judge(stats, wf)
            out["grid"][f"{name} X={x}"] = {
                **stats, "walk_forward": wf, "separates": ok,
                "verdict": verdict,
                "reading_ignoring_taken": summarise(pooled, "d_any", x),
            }
            print(f"  {name} X={x}: n_dekat {stats['n_near']} exp "
                  f"{stats.get('exp_r_near')} lawan {stats.get('exp_r_far')} "
                  f"welch {stats.get('welch_t')} wf {wf['positive']}/"
                  f"{wf['graded']} -> {verdict}", file=sys.stderr)

    out["separating"] = [k for k, v in out["grid"].items() if v.get("separates")]
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
