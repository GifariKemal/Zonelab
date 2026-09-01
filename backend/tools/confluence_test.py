"""Apakah confluence (S&D + OB/FVG di harga yang sama) menaikkan hold rate?

    python -m tools.confluence_test --bars 20000 --interval 1h

Pertanyaan yang diuji: zona supply/demand yang punya OB atau FVG di harga yang
sama - apakah bertahan lebih sering daripada zona sendirian?

Ini langkah terakhir dari roadmap "independen dulu, baru dikombinasikan".

DUA DEFINISI, DAN SEBUAH SAPUAN, karena satu definisi tidak bisa menjawabnya.
Versi pertama tool ini (1 September 2026) cuma menjalankan satu ambang, 0,3 ATR,
mendapat 555 lawan 0, lalu menyimpulkan "confluence tidak menyaring". Fungsi
`overlap()` ditulis di file itu dan tidak pernah dipanggil, sementara README EA
menuliskan klaim bahwa overlap penuh juga sudah diuji - klaim yang tidak bisa
direproduksi dari kode yang di-commit.

Pembelahan 555 lawan 0 bukan pengukuran daya saring. Ia pengukuran KEPADATAN:
kalau setiap zona kena, tidak ada kontras untuk dibandingkan. Jadi tool ini
sekarang menyapu ambangnya sampai kontrasnya muncul, dan baru di situ hold
rate-nya boleh dibandingkan. Kalau di ambang paling ketat pun selisihnya nol,
barulah "tidak menyaring" adalah temuan dan bukan artefak.
"""

from __future__ import annotations

import argparse
import math

import numpy as np

from app.detect.imbalance import detect_fvg, detect_order_block
from app.detect.supply_demand import detect
from app.indicators import wilder_atr
from app.models import ImbalanceParams, SupplyDemandParams
from tools import history
from tools.calibrate import resolve

#: No display cap, no state filter: the whole population.
SD_POP = SupplyDemandParams(
    merge_overlap_pct=1.0, max_zones_per_side=0, show_broken=True
)

#: Ambang jarak proximal, dalam ATR, dari longgar ke paling ketat.
TOLERANCES = (0.30, 0.10, 0.05, 0.02, 0.01, 0.005)


def overlap(a_top, a_bottom, b_top, b_bottom) -> float:
    """Overlap between two boxes, positive if they share price."""
    return min(a_top, b_top) - max(a_bottom, b_bottom)


def two_proportion_z(hit_a: int, n_a: int, hit_b: int, n_b: int) -> float:
    """z untuk selisih dua proporsi. NaN kalau salah satu sel kosong."""
    if n_a < 1 or n_b < 1:
        return float("nan")
    pa, pb = hit_a / n_a, hit_b / n_b
    pool = (hit_a + hit_b) / (n_a + n_b)
    se = math.sqrt(pool * (1 - pool) * (1 / n_a + 1 / n_b))
    return (pa - pb) / se if se > 0 else float("nan")


def split(zones, pool, atr, decide) -> tuple[list, list]:
    """Bagi zona jadi (confluent, alone) memakai predikat `decide`."""
    conf, alone = [], []
    for z, out in zones:
        (conf if decide(z, pool, atr) else alone).append(out)
    return conf, alone


def report(name: str, conf: list, alone: list) -> None:
    hc, ha = sum(conf), sum(alone)
    z = two_proportion_z(hc, len(conf), ha, len(alone))
    line = (f"{name:<34} confluent n={len(conf):4d} held="
            f"{(hc / len(conf) if conf else float('nan')):.1%}"
            f"   alone n={len(alone):4d} held="
            f"{(ha / len(alone) if alone else float('nan')):.1%}")
    if conf and alone:
        d = hc / len(conf) - ha / len(alone)
        line += f"   delta {d:+.1%}  z={z:+.2f}"
    else:
        line += "   DEGENERAT, tidak ada kontras"
    print(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    args = parser.parse_args()

    candles = history.load(args.symbol, args.interval, args.bars)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, 14)

    zones, _ = detect(candles, SD_POP)
    imb = ImbalanceParams(max_zones_per_side=0, show_broken=True)
    gaps, _ = detect_fvg(candles, imb)
    blocks, _ = detect_order_block(candles, imb)
    pool = list(gaps) + list(blocks)
    print(f"{args.symbol} {args.interval} {len(candles)} bar")
    print(f"S&D zones: {len(zones)}, OB blocks: {len(blocks)}, FVG gaps: {len(gaps)}")

    # Resolve once. The touch index is looked up from a time->index map rather
    # than a linear scan per zone, which is what made the first version O(n*m).
    at = {c.time: i for i, c in enumerate(candles)}
    graded = []
    for z in zones:
        if z.first_test_time is None or z.first_test_time not in at:
            continue
        out = resolve(z, high, low, close, atr, at[z.first_test_time], 2.0, 80, "r")
        if out is None:
            continue
        graded.append((z, out))
    print(f"graded (first touch resolved): {len(graded)}\n")

    # Definisi A: overlap penuh box. Ini yang README klaim sudah diuji dan tidak
    # pernah dijalankan sampai sekarang.
    conf, alone = split(
        graded, pool, atr,
        lambda z, p, _a: any(
            overlap(z.top, z.bottom, o.top, o.bottom) > 0 for o in p),
    )
    report("A. overlap box penuh", conf, alone)

    # Definisi B: jarak proximal, disapu dari longgar ke ketat.
    for tol in TOLERANCES:
        conf, alone = split(
            graded, pool, atr,
            lambda z, p, a, t=tol: any(
                abs(o.proximal - z.proximal)
                <= t * float(a[max(0, z.anatomy.base_from - 1)])
                for o in p),
        )
        report(f"B. proximal dalam {tol:.3f} ATR", conf, alone)


if __name__ == "__main__":
    main()
