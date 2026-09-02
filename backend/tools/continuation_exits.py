"""Sensitivitas EXIT untuk entry kelanjutan: apakah target lebih jauh menolongnya?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.continuation_exits \
        > ../docs/continuation_exits.json

BACAAN, BUKAN HIPOTESIS, dan itu dinyatakan di depan supaya tidak dikutip
sebagai hasil yang lolos. `tools/continuation_backtest.py` mempraregistrasi empat
arm dengan stop 1,0 ATR dan target 2,0 R dan KEEMPATNYA gagal, ekspektasi real
-0,0921 sampai -0,1602 R dengan t lawan nol -2,53 sampai -5,58 di n=10.049.

Keberatan yang sah terhadap hasil itu bukan soal entry-nya, tapi soal EXIT-nya.
Trade kelanjutan biasanya berlari jauh atau mati cepat, dan target 2R tetap
memotong bagian yang berlari. Rally XAU 2 September 2026 dari 4331 ke 4397,85
berjarak kira-kira 4 sampai 6 R dari stop 1 ATR-nya, jadi aturan 2R akan
mengambil 2R dan meninggalkan sisanya.

KARENA ITU SELURUH GRID DILAPORKAN, bukan yang terbaik. Empat arm kali empat
target adalah 16 sel, dan memilih satu sesudah melihatnya adalah p-hacking. Yang
bisa dibaca dari tabel penuh cuma ARAH: apakah ekspektasi membaik monoton saat
target dijauhkan, dan apakah ada nilai target yang membuatnya positif sama
sekali. Kalau ada, itu jadi praregistrasi BERIKUTNYA dengan Bonferroni yang
menghitung 16, bukan kesimpulan dari file ini.

Stop tetap 1,0 ATR di seluruh grid. Menggeser stop DAN target sekaligus mengubah
dua hal dan tabelnya tidak bisa dibaca lagi.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from app.cisd import cisds
from app.costs import schedule
from app.detect.structure import breaks
from app.indicators import wilder_atr
from tools.dfr_outcomes import SERIES
from tools.event_backtest import (
    ATR_PERIOD,
    BROKER,
    FINE,
    INTERVAL,
    STOP_ATR,
    Fine,
    simulate,
)
from tools.quant import clean

#: Target yang dicoba, semuanya dengan stop 1,0 ATR. 2,0 adalah nilai yang
#: dipraregistrasi di `continuation_backtest`; tiga sisanya ada supaya arahnya
#: terbaca, bukan supaya salah satunya dipilih.
TARGETS = (2.0, 3.0, 4.0, 6.0)
ARMS = ("bos", "choch", "cisd", "sweep_against")


def events_for(coarse) -> list[tuple[str, int, int]]:
    """`(arm, index event, arah)`, definisi yang SAMA dengan studi utamanya."""
    out: list[tuple[str, int, int]] = []
    found, _ = breaks(coarse)
    for b in found:
        if b.index + 1 >= len(coarse):
            continue
        if b.kind == "BOS":
            out.append(("bos", b.index, b.direction))
        elif b.kind == "CHoCH":
            out.append(("choch", b.index, b.direction))
        else:
            out.append(("sweep_against", b.index, -b.direction))
    for e in cisds(coarse)[0]:
        if e.index + 1 < len(coarse):
            out.append(("cisd", e.index, e.direction))
    return out


def rows_for(symbol: str, bars: int) -> list[dict]:
    coarse, _, _ = clean(f"mt5:{symbol}", INTERVAL, bars)
    if len(coarse) < 500:
        return []
    small, _, _ = clean(f"mt5:{symbol}", FINE, 99_999)
    if len(small) < 500:
        return []
    fine = Fine(small)
    fees = schedule(symbol, False, BROKER)
    atr = wilder_atr(
        np.array([c.high for c in coarse], dtype=np.float64),
        np.array([c.low for c in coarse], dtype=np.float64),
        np.array([c.close for c in coarse], dtype=np.float64),
        ATR_PERIOD,
    )
    out: list[dict] = []
    for arm, i_event, direction in events_for(coarse):
        row = {"arm": arm}
        # SEMUA TARGET DARI SATU EVENT YANG SAMA, jadi keempat kolom tabelnya
        # berdiri di atas populasi yang identik. Menghitungnya di pass terpisah
        # akan membuat sel yang satu trade-nya gagal dibuka punya n berbeda, dan
        # perbandingan antar kolom berhenti berarti.
        for rr in TARGETS:
            row[f"r{rr}"] = simulate(coarse, fine, atr, i_event + 1, direction,
                                     fees, stop_atr=STOP_ATR, rr=rr)
        if all(row[f"r{rr}"] is not None for rr in TARGETS):
            out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=20000)
    args = ap.parse_args()

    rows: list[dict] = []
    for symbol, interval, bars in SERIES:
        if interval != INTERVAL:
            continue
        bare = symbol.split(":")[-1]
        with contextlib.redirect_stdout(sys.stderr):
            got = rows_for(bare, min(bars, args.bars))
        print(f"{bare}: {len(got)} trade", file=sys.stderr)
        rows.extend(got)

    table: dict = {}
    for arm in ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        if not mine:
            table[arm] = {"n": 0}
            continue
        cell: dict = {"n": len(mine)}
        for rr in TARGETS:
            vals = np.array([r[f"r{rr}"] for r in mine], dtype=np.float64)
            se = float(vals.std(ddof=1) / np.sqrt(vals.size)) if vals.size > 1 else 0.0
            cell[f"rr_{rr}"] = {
                "exp_r": float(vals.mean()),
                "t_vs_zero": float(vals.mean() / se) if se > 0 else None,
                "hit_rate": float((vals > 0).mean()),
            }
        exps = [cell[f"rr_{rr}"]["exp_r"] for rr in TARGETS]
        cell["monotone_improving"] = all(b > a for a, b in zip(exps, exps[1:]))
        cell["best_target"] = TARGETS[int(np.argmax(exps))]
        cell["any_positive"] = any(e > 0 for e in exps)
        table[arm] = cell

    out = {
        "status": "BACAAN, bukan hipotesis; 16 sel dan tidak satu pun "
                  "dipraregistrasi. Sel positif di sini jadi praregistrasi "
                  "berikutnya dengan Bonferroni atas 16, bukan kesimpulan.",
        "why": "keberatan sah terhadap continuation_backtest bukan entry-nya "
               "tapi exit-nya: target 2R memotong bagian yang berlari, dan "
               "rally XAU 2 September 2026 berjarak 4 sampai 6 R",
        "stop_atr": STOP_ATR, "targets": list(TARGETS),
        "interval": INTERVAL, "fine": FINE, "broker": BROKER,
        "arms": table,
        "any_cell_positive": [a for a, v in table.items() if v.get("any_positive")],
    }
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
