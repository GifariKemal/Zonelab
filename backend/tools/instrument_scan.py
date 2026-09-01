"""Apakah reaksi lokasi zona ada di instrumen yang belum pernah diukur?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.instrument_scan > ../docs/instrument_scan.json

KENAPA TOOL INI ADA. Pada 31 Agustus 2026 lima id ditambahkan ke picker
(`RUS2000`, `ULSD`, `RBOB`, `EURFX`, `GBPFX`) dan tiga lagi sudah lama di sana
(`SPX500`, `NAS100`, `IDX`), semuanya bisa digambar dan tidak satu pun punya
satu angka di `docs/`. Diperiksa 1 September 2026: nol file bukti menyebut
mereka. Bisa dilihat bukan berarti terukur, dan sebuah picker yang menawarkan
instrumen tanpa pengukuran menawarkan sesuatu yang proyek ini tidak tahu apa-apa
tentangnya.

APA YANG DIUKUR, DAN APA YANG TIDAK. Yang diukur: hold rate zona pada sentuhan
pertama, lawan PLACEBO-nya sendiri, yaitu kotak yang sama digeser sejauh
kelipatan tingginya (`tools.calibrate.shift`). Itu menjawab "apakah lokasi
kotaknya penting di instrumen ini".

Yang TIDAK diukur, dan ini harus dibaca sebelum angkanya: **tanpa biaya**. Tidak
ada tabel spread/komisi untuk kontrak depan ini di `app/costs.py`, dan menebaknya
akan lebih buruk daripada tidak menuliskannya. Jadi ini klaim LOKASI frictionless
dan bukan klaim edge yang bisa ditradingkan. `docs/CALIBRATION.md` memakai standar
yang sama: FVG mengalahkan placebo frictionless dan tetap rugi di P&L.

Sumbernya Yahoo, karena terminal broker tidak membawa kontrak-kontrak ini
(`tools/quant.py:79`). Yahoo memberi sekitar 730 hari bar 1 jam, jadi n-nya kecil
dibanding sel MT5 dan lantai `MIN_N` di bawah ada supaya sel tipis dilaporkan
tipis, bukan disimpulkan.

WALK-FORWARD IKUT DILAPORKAN, dan tanpa itu verdict di sini tidak boleh dipakai
untuk menyalakan apa pun. Standar proyek ini menuntut sebuah pemisah bertahan di
luar sampel, bukan cuma lulus satu z gabungan, jadi tiap sel juga dibelah empat
lipatan waktu dan dihitung berapa lipatan yang hold rate-nya masih di atas
placebo-nya sendiri. Sebuah sel yang MEMISAHKAN dengan 2 dari 4 lipatan adalah
sel yang belum bertahan.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys

from app.models import SupplyDemandParams
from tools import history
from tools.calibrate import POPULATION, evaluate

#: Instrumen yang diminta pada brainstorm 31 Agustus 2026, plus tiga yang sudah
#: terukur (XAU/XAG/XPT lewat MT5) sebagai jangkar pembanding di tabel yang sama.
SYMBOLS = (
    "yahoo:SPX500",   # ES, S&P 500
    "yahoo:NAS100",   # NQ, Nasdaq 100
    "yahoo:RUS2000",  # RTY, E-mini Russell 2000
    "yahoo:WTI",      # CL, light crude
    "yahoo:ULSD",     # HO, NY Harbour ULSD
    "yahoo:RBOB",     # RB, RBOB gasoline
    "yahoo:IDX",      # ^JKSE, IDX Composite
    "yahoo:EURFX",    # 6E
    "yahoo:GBPFX",    # 6B
    "mt5:XAUUSD",     # jangkar: sudah terukur, edge-nya di sini
    "mt5:XAGUSD",
    "mt5:XPTUSD",
)

INTERVAL = "1h"
BARS = 20000
REWARD = 2.0
HORIZON = 80
MODE = "r"      # both legs scale with the zone, so geometry cannot masquerade
MIN_N = 30
FOLDS = 4


def z_two_proportion(hit_a: int, n_a: int, hit_b: int, n_b: int) -> float:
    if n_a < 1 or n_b < 1:
        return float("nan")
    pool = (hit_a + hit_b) / (n_a + n_b)
    se = math.sqrt(pool * (1 - pool) * (1 / n_a + 1 / n_b))
    if se <= 0:
        return float("nan")
    return (hit_a / n_a - hit_b / n_b) / se


def _fold_edges(obs, folds: int):
    """Equal-width time folds over the touch indices present in this cell."""
    if not obs:
        return []
    lo = min(o.touch_index for o in obs)
    hi = max(o.touch_index for o in obs) + 1
    step = max(1, (hi - lo) // folds)
    return [(lo + i * step, hi if i == folds - 1 else lo + (i + 1) * step)
            for i in range(folds)]


def cell(symbol: str, interval: str, bars: int) -> dict:
    candles = history.load(symbol, interval, bars)
    if len(candles) < 400:
        return {"bars": len(candles), "verdict": "riwayat terlalu pendek"}
    data = evaluate(candles, SupplyDemandParams(**POPULATION), REWARD, HORIZON,
                    f"{symbol}-{interval}", interval, MODE)
    real = data.real
    plac = data.placebo
    hit_r = sum(1 for o in real if o.held)
    hit_p = sum(1 for o in plac if o.held)
    z = z_two_proportion(hit_r, len(real), hit_p, len(plac))

    # Walk-forward: four time folds cut on the touch index, and how many of them
    # still put the real hold rate above the placebo's.
    edges = _fold_edges(real + plac, FOLDS)
    folds = []
    for lo, hi in edges:
        r = [o for o in real if lo <= o.touch_index < hi]
        q = [o for o in plac if lo <= o.touch_index < hi]
        if len(r) < 20 or len(q) < 20:
            folds.append(None)
            continue
        folds.append(sum(o.held for o in r) / len(r) - sum(o.held for o in q) / len(q))

    verdict = "n kecil"
    if len(real) >= MIN_N and len(plac) >= MIN_N and not math.isnan(z):
        # Bonferroni over the twelve cells this tool reports, two-sided.
        verdict = "MEMISAHKAN" if abs(z) >= 2.87 else "null"
        if verdict == "MEMISAHKAN" and z < 0:
            verdict = "MEMISAHKAN, TANDA TERBALIK"
    return {
        "bars": len(candles),
        "first": candles[0].time,
        "last": candles[-1].time,
        "n_real": len(real),
        "hold_real": hit_r / len(real) if real else None,
        "n_placebo": len(plac),
        "hold_placebo": hit_p / len(plac) if plac else None,
        "z": z,
        "verdict": verdict,
        "fold_deltas": folds,
        "positive_folds": sum(1 for f in folds if f is not None and f > 0),
        "graded_folds": sum(1 for f in folds if f is not None),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default=INTERVAL)
    parser.add_argument("--bars", type=int, default=BARS)
    args = parser.parse_args()

    out: dict = {
        "preregistered": "tools/instrument_scan.py, 2026-09-01",
        "question": "apakah hold rate zona mengalahkan placebo geser di instrumen ini",
        "frictionless": True,
        "note": "TANPA BIAYA. Klaim lokasi, bukan klaim edge tradeable.",
        "reward": REWARD, "horizon": HORIZON, "mode": MODE,
        "critical_z": 2.87,
        "cells": {},
    }
    with contextlib.redirect_stdout(sys.stderr):
        for symbol in [s.strip() for s in args.symbols.split(",") if s.strip()]:
            try:
                out["cells"][symbol] = cell(symbol, args.interval, args.bars)
            except Exception as exc:  # a provider that cannot serve it is a FACT
                out["cells"][symbol] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"{symbol}: {out['cells'][symbol]}", file=sys.stderr)
    json.dump(out, sys.stdout, indent=2, default=float)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
