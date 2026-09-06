"""Varian aturan breaker block, diukur di rig yang sama dengan detector aslinya.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.brk_variants
    PYTHONPATH=. .venv/Scripts/python.exe -m tools.brk_variants --cells all

KENAPA. `docs/QA-BRK-GATE.md` menemukan gerbang departure BRK tidak memisahkan
di satu ambang pun, sementara populasi mentahnya sudah exp_r +0,2618 di
t=+12,60. Jadi tidak ada yang bisa diperbaiki dengan menyetel ambang, dan
pertanyaan berikutnya adalah ATURANNYA.

Permukaan aturan BRK sangat kecil, dan itu harus dinyatakan supaya sapuan ini
tidak terlihat lebih besar dari yang sebenarnya. `detect/inversion.py`
mewarisi rectangle, skala ATR dan ambang impuls dari order block induknya, lalu
menyumbang PERSIS SATU keputusan sendiri: lifecycle kotak terbalik mulai di
`break_index + 1`. Semua yang disapu di bawah karena itu adalah hal yang saat
ini DIWARISI, bukan hal yang saat ini disetel.

APA YANG DISAPU, diregistrasi sebelum angkanya dilihat:

  A  baseline                aturan yang dikirim hari ini
  B  sweep WAJIB             syarat konstitutif Keluarga 2. Riset sumber luar
                             menemukan breaker punya dua keluarga definisi yang
                             bukan varian satu sama lain, dan yang satu menuntut
                             kaki induknya MENYAPU ekstrem sebelumnya. Kita
                             mengimplementasi keluarga yang tidak menuntutnya
  C  sweep DILARANG          komplemen B, dan tanpa lengan ini B tidak bisa
                             dibaca: sebuah lengan yang lebih baik dari baseline
                             bisa saja cuma subsampel yang lebih kecil
  D  impuls diukur DI BREAK  bukan diwarisi dari induk. Riset menemukan TIDAK
                             SATU PUN implementasi Pine terbuka yang membawa
                             angka induknya; semuanya mengukur ulang di break
  E  lantai tinggi kotak     0,05 ATR, dimekarkan simetris. Ini pertanyaan
                             GAMBAR: kotak badan mewarisi ekor sangat tipis dari
                             order block, 8 sampai 12 persen di bawah 0,05 ATR,
                             dan sebagian di bawah satu pixel di layar

YANG TIDAK DISAPU, dan alasannya. Break lewat SUMBU alih-alih CLOSE adalah
perselisihan sumber yang nyata, tetapi ia hidup di dalam `replay_lifecycle`
milik `supply_demand.py`, dan menirunya di sini berarti menyalin siklus hidup
penuh sebuah zona ke berkas studi. Biaya salinannya lebih besar dari nilai
jawabannya, dan sebuah salinan yang melenceng akan mengukur detector yang tidak
ada. Dicatat sebagai belum diukur.

ATURAN LULUS, ditulis sebelum angkanya dilihat: sebuah varian LEBIH BAIK hanya
bila exp_r-nya di atas baseline DAN walk-forward 8 dari 8 DAN `|t|` Welch lawan
baseline melewati Bonferroni atas jumlah lengan.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import pathlib
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect import imbalance
from app.detect.imbalance import _arrays, _finish, _present, detect_order_block
from app.detect.structure import breaks
from app.indicators import wilder_atr
from app.models import Candle, ImbalanceParams, Zone, ZoneKind, ZoneSide, ZoneState
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, one_sample_t, welch
from tools.gate_sweep import CELL_SETS
from tools.gate_sweep import cell_rows as _cell_rows


@contextlib.contextmanager
def _floor(value: float):
    """Menyetel lantai tinggi kotak produksi untuk sebentar.

    SATU PROSES, SATU THREAD. Ia menukar konstanta modul, jadi dua pengukuran
    paralel di proses yang sama akan saling merusak - pola yang sama dengan
    penukaran `DETECTORS[nama]` di tools lain di direktori ini.
    """
    before = imbalance.MIN_OB_BOX_RANGE
    imbalance.MIN_OB_BOX_RANGE = value
    try:
        yield
    finally:
        imbalance.MIN_OB_BOX_RANGE = before

CELLS = CELL_SETS["30m"]
MIN_FOLD = 20
MIN_GROUP = 30
CACHE = (
    pathlib.Path(__file__).resolve().parents[2] / "docs" / "brk_variants_rows_cache.json"
)


def _swept_windows(candles: list[Candle], params: ImbalanceParams) -> set[int]:
    """Bar yang punya event SWEEP, dipetakan ke indeksnya.

    `breaks()` sudah memisahkan SWEEP dari BOS dengan alasan tertulis: sumbu
    yang menembus level lalu ditutup kembali di dalam adalah peristiwa yang
    BERLAWANAN dengan struktur yang jebol. Varian B memakai pemisahan itu apa
    adanya alih alih mengarang definisi sweep kedua.
    """
    return {
        e.index
        for e in breaks(candles, params.structure_n, params.structure_n)[0]
        if e.kind == "SWEEP"
    }


def _invert_variant(
    candles: list[Candle],
    params: ImbalanceParams,
    *,
    sweep: str = "any",        # any | required | forbidden
    impulse_at_break: bool = False,
    unfloor: bool = False,
) -> tuple[list[Zone], dict[str, float]]:
    """`detect/inversion.py:_invert` untuk BRK, dengan lengan-lengan sapuan.

    Disalin dan bukan diparameterkan di `app/`, pola yang sama dengan
    `tools/ob_variants.py` dan `tools/volume_imbalance.py`: sebuah knob produksi
    untuk sebuah percobaan adalah permukaan yang harus didukung selamanya.
    """
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n, "candidates": 0, "rejected_never_broke": 0,
        "rejected_too_small": 0, "rejected_sweep_arm": 0,
        "rejected_state_filter": 0,
    }
    # LANTAI TINGGI KOTAK ADA DI PRODUKSI, di `detect_order_block`, dan kotak
    # BRK menyalin `zone.top, zone.bottom` dari parent-nya. Jadi satu satunya
    # cara mengukur biayanya di BRK adalah MENCABUTNYA, bukan menambahkannya:
    # sebuah lengan yang memasang lantai di atas baseline yang sudah berlantai
    # akan mengukur nol, dan `_selftest` di bawah menangkap versi itu.
    with _floor(0.0 if unfloor else imbalance.MIN_OB_BOX_RANGE):
        parents, _ = detect_order_block(
            candles,
            params.model_copy(update={"show_broken": True, "max_zones_per_side": 0}),
        )
    if not parents:
        return _present([], params, stats, int(candles[-1].time) if candles else 0)

    time, _open, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)
    index_of = {int(t): i for i, t in enumerate(time)}
    swept = _swept_windows(candles, params) if sweep != "any" else set()

    found: list[Zone] = []
    for zone in parents:
        stats["candidates"] += 1
        if zone.state is not ZoneState.BROKEN:
            stats["rejected_never_broke"] += 1
            continue
        broke = index_of[zone.time_to]
        origin = index_of[zone.time_from]

        if sweep != "any":
            # Jendela kaki induk: bar sesudah lilin block sampai bar tempat
            # kotaknya jadi bisa diketahui.
            window = range(origin + 1, origin + 1 + params.displacement_bars)
            has = any(i in swept for i in window)
            if (sweep == "required") != has:
                stats["rejected_sweep_arm"] += 1
                continue

        departure = zone.departure_atr
        if impulse_at_break:
            # DIUKUR DI BREAK, bukan diwarisi. Dari close bar yang menembus ke
            # ekstrem close `displacement_bars` sesudahnya, skala ATR di bar
            # sebelum break - bentuk yang sama dengan induknya, momen berbeda.
            end = min(broke + 1 + params.displacement_bars, n)
            if end <= broke + 1:
                continue
            scale = float(atr[max(0, broke - 1)])
            if scale <= 0:
                continue
            after = close[broke + 1:end]
            if zone.side is ZoneSide.DEMAND:
                # Induk demand ditembus ke BAWAH, jadi kotaknya jadi supply dan
                # geraknya turun.
                departure = float(float(close[broke]) - after.min()) / scale
            else:
                departure = float(after.max() - float(close[broke])) / scale

        top, bottom = zone.top, zone.bottom
        inverted = _finish(
            ZoneKind.BRK,
            ZoneSide.SUPPLY if zone.side is ZoneSide.DEMAND else ZoneSide.DEMAND,
            top, bottom, origin, broke,
            time, high, low, close, atr, params, departure,
        )
        if inverted is None:
            stats["rejected_too_small"] += 1
            continue
        found.append(inverted.model_copy(update={
            "inverted_at": int(time[broke]),
            "time_from": int(time[broke]),
        }))
    return _present(found, params, stats, int(candles[-1].time) if candles else 0)


VARIANTS: list[dict] = [
    # MELACAK PRODUKSI, dan namanya harus mengatakan itu. Kunci cache memuat
    # set sel dan nama lengan, tidak memuat kodenya, jadi baris yang ditulis
    # sebelum `detect_order_block` berubah akan disajikan lagi setelahnya tanpa
    # satu pesan pun. Jebakan yang sama sudah menggigit di `tools/ob_variants.py`
    # pada 6 September 2026.
    {"name": "A produksi saat ini", "kw": {}},
    {"name": "B sweep WAJIB", "kw": {"sweep": "required"}},
    {"name": "C sweep DILARANG", "kw": {"sweep": "forbidden"}},
    {"name": "D impuls diukur di break", "kw": {"impulse_at_break": True}},
    {"name": "E TANPA lantai kotak", "kw": {"unfloor": True}},
    {"name": "F B+D bersama", "kw": {"sweep": "required", "impulse_at_break": True}},
]
T_THRESHOLD = _critical_t(len(VARIANTS) - 1)


def walk_forward(rows: list[dict]) -> dict:
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    folds = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = np.array([r["r"] for r in opened if r["exit_pos"] < hi])
        entry = {"fold": k + 1, "n": int(kept.size), "readable": kept.size >= MIN_FOLD}
        if entry["readable"]:
            entry["exp_r"] = float(kept.mean())
        folds.append(entry)
    graded = [f for f in folds if f["readable"]]
    return {"graded": len(graded),
            "positive": sum(1 for f in graded if f["exp_r"] > 0)}


def rates(rows: list[dict]) -> dict:
    r = np.array([x["r"] for x in rows])
    if not r.size:
        return {"n": 0}
    wins, losses = r[r > 0], r[r <= 0]
    gross_loss = float(abs(losses.sum()))
    return {
        "n": int(r.size),
        "exp_r": round(float(r.mean()), 4),
        "t_vs_zero": round(one_sample_t(r), 3) if r.size > 1 else None,
        "win_rate": round(float(wins.size / r.size), 4),
        "profit_factor": round(float(wins.sum()) / gross_loss, 3) if gross_loss else None,
    }


def run(variant: dict) -> dict:
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True)
    kw = variant["kw"]
    original = DETECTORS["breaker"]
    DETECTORS["breaker"] = lambda c, _p: _invert_variant(c, params, **kw)
    try:
        rows: list[dict] = []
        for symbol, interval in CELLS:
            with contextlib.redirect_stdout(sys.stderr):
                got, _span = _cell_rows("breaker", symbol, interval)
            rows.extend(got)
    finally:
        DETECTORS["breaker"] = original

    out = {"variant": variant["name"], **rates(rows)}
    if out.get("n", 0) >= MIN_GROUP:
        wf = walk_forward(rows)
        out["wf_positive"], out["wf_graded"] = wf["positive"], wf["graded"]
    out["_r"] = [x["r"] for x in rows]
    return out


def main() -> int:
    global CELLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="30m", choices=sorted(CELL_SETS))
    args = ap.parse_args()
    CELLS = CELL_SETS[args.cells]
    print(f"  cells={args.cells} ({len(CELLS)} sel) varian={len(VARIANTS)} "
          f"bonferroni={T_THRESHOLD:.4f}", file=sys.stderr)

    cached = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    results = []
    for v in VARIANTS:
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
            r["verdict"] = (
                "LEBIH BAIK dari baseline"
                if better and abs(r["welch_t_vs_baseline"]) >= T_THRESHOLD
                else "lebih baik tapi tidak signifikan" if better
                else "tidak lebih baik"
            )
        else:
            r["verdict"] = "tidak terukur, n di bawah MIN_GROUP"

    json.dump({
        "question": "aturan breaker mana yang mengubah outcome",
        "cell_set": args.cells,
        "cells": [f"{s} {i}" for s, i in CELLS],
        "t_threshold_bonferroni": round(T_THRESHOLD, 4),
        "min_group": MIN_GROUP,
        "not_swept": (
            "break lewat sumbu alih alih close: hidup di replay_lifecycle "
            "supply_demand.py, menyalinnya ke sini lebih mahal dari jawabannya"
        ),
        "baseline": base,
        "variants": results[1:],
    }, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


def _selftest() -> None:
    """Lengan sweep harus benar benar memisahkan populasi, bukan cuma dinamai.

    Tanpa ini sebuah bug di predikatnya akan membuat B dan C mengembalikan
    populasi yang sama, dan sapuannya akan melaporkan dua lengan identik sebagai
    temuan.
    """
    from tools.quant import clean

    c, _d, _r = clean("XAUUSD", "30m")
    c = c[:4000]
    p = ImbalanceParams(max_zones_per_side=0, show_broken=True)
    base, _ = _invert_variant(c, p)
    req, _ = _invert_variant(c, p, sweep="required")
    forb, _ = _invert_variant(c, p, sweep="forbidden")
    assert len(req) + len(forb) == len(base), (len(req), len(forb), len(base))
    assert 0 < len(req) < len(base), len(req)
    # Arahnya DICABUT, bukan ditambahkan: lantainya sudah ada di produksi.
    # Versi pertama lengan ini menambahkannya di atas baseline yang sudah
    # berlantai, dan assert ini gagal - itulah yang mengungkapkannya.
    bare, _ = _invert_variant(c, p, unfloor=True)
    assert min(z.top - z.bottom for z in base) > min(
        z.top - z.bottom for z in bare
    ), "lantai produksi tidak memekarkan apa pun di BRK"


if __name__ == "__main__":
    _selftest()
    raise SystemExit(main())
