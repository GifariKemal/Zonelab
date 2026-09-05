"""Apakah IFVG punya gerbang departure, dan ke arah mana.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.ifvg_gate

PERTANYAAN INI BELUM PERNAH DITANYAKAN, dan itu alasan berkas ini ada. Plafon
0,25 ATR yang dipakai `CEILING_KINDS` diukur pada FVG saja: sweep di commit
44196e2 menyuntik `detect_fvg` ke `DETECTORS` dan tidak menyentuh satu pun zona
inversi. IFVG dimasukkan ke tuple itu di commit yang sama karena bentuknya
mirip.

ADA ALASAN SPESIFIK UNTUK MERAGUKAN ANALOGI ITU, dan bukan sekadar ketiadaan
angka. `detect/inversion.py:130` MEMBAWA `departure_atr` milik parent alih alih
menghitungnya ulang, dengan alasannya sendiri: sebuah inversi dibuat oleh CLOSE
yang menembus level, dan close tidak punya kaki yang bisa diukur. Jadi angka
yang digerbangi di sini menggambarkan kaki keluar yang membangun kotak ASALNYA,
sebuah peristiwa yang terjadi SEBELUM inversinya. Menggerbanginya dengan ambang
yang dikalibrasi pada outcome first-touch sebuah FVG adalah dua peristiwa
berbeda yang dinilai satu angka.

APA YANG TIDAK DITANYAKAN DI SINI. Arah. `docs/CALIBRATION.md` bagian H8 sudah
mengukur sentuhan pasca-inversi sebagai klaim arah pada n=38.058 dan hasilnya
NEGATIF SIGNIFIKAN, delta -0,179 / -0,165 / -0,274 dengan t sampai -4,22.
Menjalankan ulang pertanyaan itu berarti menempuh ulang keputusan yang sudah
diambil. Yang ditanyakan berkas ini adalah pertanyaan penyortiran: di dalam
populasi IFVG, apakah ada ambang departure yang MEMISAHKAN outcome, dan apakah
kohort yang dipertahankan ada di bawah atau di atasnya.

PRAREGISTRASI, ditulis sebelum angkanya dilihat:

  - Sel, ambang dan geometri persis sama dengan sweep FVG, supaya kedua hasil
    bisa diletakkan bersebelahan: XAUUSD 30m dan BTCUSD 30m.
  - `GATE_GRID` dan KEDUA arah diuji untuk setiap ambang. Menguji satu arah
    saja adalah cara paling mudah menemukan gerbang yang sebenarnya tidak ada.
  - Ambang |t| memakai koreksi Bonferroni atas SELURUH sel grid, yaitu jumlah
    ambang dikali dua arah, bukan atas satu hipotesis.
  - Sebuah gerbang dinyatakan ADA hanya bila ia lolos |t| Bonferroni DAN
    walk-forward, dengan aturan yang sama yang dipakai FVG. Ini yang membedakan
    penyortir dari ambang yang kebetulan terlihat bagus di satu potong data.
  - `MIN_GROUP` 30. Sebuah kohort di bawah itu tidak dinilai, dinyatakan tidak
    terukur. `docs/BACKLOG.md` bagian 3c mencatat sebuah t=+2,92 yang lolos
    Bonferroni di atas TUJUH trade; lantai ini ada supaya itu tidak terulang.
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np

from app.providers.base import INTERVALS
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, one_sample_t, resolved_as, welch
from tools.intrabar import FINER
from tools.quant import clean

#: Deret halus yang mengadili urutan intrabar tiap timeframe.
#:
#: DUA BARIS DI LUAR `intrabar.FINER`, dan keduanya dinyatakan di sini alih alih
#: menambal peta bersama itu: 1d diadili oleh 1h dan 1w oleh 4h. Peta aslinya
#: berhenti di 4h karena tool lain tidak pernah menanyakan timeframe di atasnya,
#: dan menambahkannya di sana akan mengubah default tool tool itu tanpa ada yang
#: memintanya.
#:
#: 1m DAN 5m TIDAK ADA DI SINI DAN TIDAK BISA DITAMBAHKAN. Tidak ada deret yang
#: lebih halus dari keduanya di provider ini, jadi urutan stop lawan target di
#: dalam satu bar tidak bisa diadili, cuma diasumsikan. `docs/` sudah mencatat
#: apa yang asumsi itu memakan: +0,2 R jadi -0,0153 R begitu resolusinya
#: dihaluskan. Mengukur di 1m tanpa deret pengadil bukan versi kasar dari
#: pengukuran ini, ia pengukuran yang berbeda.
FINER_EXT = {**FINER, "1d": "1h", "1w": "4h"}
SYMBOLS = ("XAUUSD", "BTCUSD")
TIMEFRAMES = ("15m", "30m", "1h", "4h", "1d", "1w")
CELLS = [(s, tf) for tf in TIMEFRAMES for s in SYMBOLS]
#: Ambang yang diuji. Memuat 0,25 (plafon yang sedang terpasang untuk IFVG,
#: tanpa pengukuran) dan 2,0 (lantai yang dipakai semua kind lain), jadi kedua
#: posisi yang mungkin diambil kode saat ini ikut dinilai.
GATE_GRID = [0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0]
DIRECTIONS = ("ceiling", "floor")
MIN_FOLD = 20
MIN_GROUP = 30
#: Bonferroni atas seluruh sel grid: tiap ambang dikali dua arah.
T_THRESHOLD = _critical_t(len(GATE_GRID) * len(DIRECTIONS))


def keep_mask(
    rows: list[dict], gate: float, direction: str
) -> tuple[np.ndarray, np.ndarray]:
    """R dari kohort yang gerbangnya PERTAHANKAN, dan R dari sisanya.

    `ceiling` mempertahankan yang di BAWAH ambang, `floor` yang di ATAS. Kedua
    perbandingan mengikuti kode produksi persis: plafon eksklusif, lantai
    inklusif (`app/models/zone.py`).
    """
    if direction == "ceiling":
        kept = [r["r"] for r in rows if r["departure"] < gate]
        rest = [r["r"] for r in rows if r["departure"] >= gate]
    else:
        kept = [r["r"] for r in rows if r["departure"] >= gate]
        rest = [r["r"] for r in rows if r["departure"] < gate]
    return np.array(kept), np.array(rest)


def walk_forward(rows: list[dict], gate: float, direction: str) -> dict:
    """8 fold posisi relatif, tanda exp_R kohort yang dipertahankan.

    Fold di-PURGE seperti di `fvg_sweep`: trade yang keluar setelah batas fold
    dibuang, supaya sebuah fold tidak dinilai dengan hasil yang belum bisa
    diketahui di dalamnya.
    """
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    folds = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept_rows = [r for r in opened if r["exit_pos"] < hi]
        kept, _rest = keep_mask(kept_rows, gate, direction)
        entry: dict = {"fold": k + 1, "n": int(kept.size),
                       "purged": len(opened) - len(kept_rows)}
        entry["readable"] = kept.size >= MIN_FOLD
        if entry["readable"]:
            entry["exp_r"] = float(kept.mean())
        folds.append(entry)
    graded = [f for f in folds if f["readable"]]
    return {"folds": folds, "graded": len(graded),
            "positive": sum(1 for f in graded if f["exp_r"] > 0)}


def census(rows: list[dict]) -> dict:
    """Sebaran departure yang sedang digerbangi, supaya gerbang bisa dibaca.

    Sebuah ambang yang jatuh di luar rentang datanya bukan gerbang, ia saklar
    mati, dan itu terlihat di sini sebelum satu t pun dihitung.
    """
    d = np.array([r["departure"] for r in rows])
    if not d.size:
        return {"n": 0}
    return {
        "n": int(d.size),
        "min": round(float(d.min()), 4),
        "p05": round(float(np.percentile(d, 5)), 4),
        "median": round(float(np.median(d)), 4),
        "p95": round(float(np.percentile(d, 95)), 4),
        "max": round(float(d.max()), 4),
        "share_below_0.25": round(float((d < 0.25).mean()), 4),
        "share_at_or_above_2.0": round(float((d >= 2.0).mean()), 4),
    }


def rates(rows: list[dict], gate: float, direction: str) -> dict:
    """Win rate dan profit factor kohort yang dipertahankan.

    ADA CONFOUND MEKANIS DI SINI DAN INILAH YANG MENGUKURNYA. `app/plan.py`
    menaruh target di zona lawan terdekat dan stop di luar distal, jadi reward
    adalah jarak ABSOLUT ke zona lawan sementara risk adalah tinggi box plus
    buffer. Kotak yang lebih kecil karena itu memberi R lebih besar per
    kemenangan tanpa satu pun klaim prediksi.
    Yang memisahkan edge dari aritmetika adalah WIN RATE: kalau kohort gap
    kecil menang sesering kohort gap besar sambil membawa stop lebih rapat,
    itu trade yang benar-benar lebih baik. Kalau ia menang jauh lebih jarang,
    R yang lebih tinggi cuma kompensasi.
    """
    if direction == "ceiling":
        kept = [r for r in rows if r["departure"] < gate]
    else:
        kept = [r for r in rows if r["departure"] >= gate]
    if not kept:
        return {}
    wins = [r["r"] for r in kept if r["r"] > 0]
    losses = [r["r"] for r in kept if r["r"] <= 0]
    gross_loss = abs(sum(losses))
    return {
        "win_rate": round(len(wins) / len(kept), 4),
        "profit_factor": round(sum(wins) / gross_loss, 3) if gross_loss else None,
        "mean_win_r": round(float(np.mean(wins)), 4) if wins else None,
        "mean_loss_r": round(float(np.mean(losses)), 4) if losses else None,
    }


def evaluate(rows: list[dict], gate: float, direction: str) -> dict:
    kept, rest = keep_mask(rows, gate, direction)
    out: dict = {
        "gate_atr": gate,
        "direction": direction,
        "n_kept": int(kept.size),
        "n_rest": int(rest.size),
        "exp_r_kept": round(float(kept.mean()), 4) if kept.size else None,
        "exp_r_rest": round(float(rest.mean()), 4) if rest.size else None,
        **rates(rows, gate, direction),
    }
    if kept.size < MIN_GROUP or rest.size < MIN_GROUP:
        out["verdict"] = "tidak terukur, kohort di bawah MIN_GROUP"
        return out

    out["welch_t"] = round(welch(kept, rest), 4)
    out["t_vs_zero"] = round(one_sample_t(kept), 4)
    wf = walk_forward(rows, gate, direction)
    out["wf_positive"] = wf["positive"]
    out["wf_graded"] = wf["graded"]

    separates = abs(out["welch_t"]) >= T_THRESHOLD
    forward = wf["graded"] > 0 and wf["positive"] == wf["graded"]
    if separates and forward:
        out["verdict"] = "gerbang, lolos t dan walk-forward"
    elif separates:
        out["verdict"] = "memisahkan tapi gagal walk-forward"
    else:
        out["verdict"] = "tidak memisahkan"
    return out


#: Baris hasil resolusi bar halus, disimpan per sel.
#:
#: Resolusi itu bagian yang mahal, dan tanpa cache setiap pertanyaan lanjutan
#: pada populasi yang SAMA harus menunggunya lagi. `docs/` sudah memuat catatan
#: bahwa run panjang di sini bisa terbunuh di tengah; menulis per sel berarti
#: sel yang sudah selesai tidak diulang.
CACHE = pathlib.Path(__file__).resolve().parents[2] / "docs" / "ifvg_rows_cache.json"


def cell_rows(symbol: str, interval: str) -> tuple[list[dict], int]:
    """`detectors_costed.cell_rows`, tapi deret halusnya dari `FINER_EXT`.

    Disalin dan bukan dipanggil KARENA SATU BARIS: yang asli membaca
    `FINER[interval]` dan akan KeyError di 1d dan 1w. Sisanya identik, termasuk
    posisi relatif yang diukur pada rentang yang bisa DINILAI dan bukan pada
    seluruh deret kasar - cacat yang catatan di `detectors_costed.py` jelaskan
    panjang lebar, dan yang akan terulang di sini kalau baris `lo`/`width` di
    bawah ditulis ulang dengan `len(candles)`.
    """
    fine = FINER_EXT[interval]
    rows = resolved_as("ifvg", symbol, interval, fine)
    span = len(clean(symbol, interval)[0])
    ratio = INTERVALS[interval] // INTERVALS[fine]
    for r in rows:
        r["exit_est"] = r["at"] + math.ceil(r["fine_bars_held"] / ratio)
        r["cell"] = f"{symbol} {interval}"
    if rows:
        lo = min(r["at"] for r in rows)
        width = max(max(r["exit_est"] for r in rows) - lo, 1)
        for r in rows:
            r["pos"] = (r["at"] - lo) / width
            r["exit_pos"] = (r["exit_est"] - lo) / width
    return rows, span


def _rows_cached() -> tuple[list[dict], dict[str, dict]]:
    """Baris tiap sel, DITULIS SEGERA setelah selnya selesai.

    Bukan sekali di akhir. Run ini dua belas sel panjang dan sebuah proses yang
    terbunuh di sel kesebelas tidak boleh membuang sepuluh sel yang sudah
    selesai.
    """
    cached: dict = {}
    if CACHE.exists():
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
    all_rows: list[dict] = []
    cells: dict[str, dict] = {}
    for symbol, interval in CELLS:
        key = f"{symbol} {interval}"
        if key in cached:
            rows, span = cached[key]["rows"], cached[key]["span_bars"]
            print(f"  {key} dari cache, n={len(rows)}", file=sys.stderr)
        else:
            print(f"  {key}...", file=sys.stderr, flush=True)
            try:
                rows, span = cell_rows(symbol, interval)
            except Exception as exc:  # noqa: BLE001
                # SATU SEL YANG GAGAL BUKAN RUN YANG MATI. Sebuah timeframe
                # tanpa riwayat halus yang cukup akan meledak di sini, dan
                # tanpa penjagaan ini sebelas sel lain ikut hilang bersamanya.
                print(f"    GAGAL {type(exc).__name__}: {exc}", file=sys.stderr)
                cells[key] = {"error": f"{type(exc).__name__}: {exc}"}
                continue
            cached[key] = {"span_bars": span, "rows": rows}
            CACHE.write_text(json.dumps(cached), encoding="utf-8")
            print(f"    n={len(rows)}, ditulis ke cache", file=sys.stderr, flush=True)
        all_rows.extend(rows)
        cells[key] = {"span_bars": span, "census": census(rows)}
    return all_rows, cells


def main() -> int:
    all_rows, cells = _rows_cached()
    for key, meta in cells.items():
        print(f"    {key} {meta['census']}", file=sys.stderr)

    baseline = np.array([r["r"] for r in all_rows])
    results = [evaluate(all_rows, g, d) for g in GATE_GRID for d in DIRECTIONS]
    for r in results:
        print(f"    gate {r['gate_atr']:>4} {r['direction']:<7} "
              f"n={r['n_kept']:<5} exp_r={r['exp_r_kept']} "
              f"t={r.get('welch_t')} wf={r.get('wf_positive')}/"
              f"{r.get('wf_graded')} :: {r['verdict']}", file=sys.stderr)

    # PER TIMEFRAME, bukan cuma gabungan. Sebuah gerbang yang hidup di dua
    # timeframe dan mati di empat lainnya akan terbaca sehat di angka gabungan,
    # dan itu persis bentuk kegagalan yang sudah tercatat di repo ini untuk
    # gerbang lain: menyala 4,8 persen di dua instrumen dan tak terukur di sana.
    per_tf: dict[str, dict] = {}
    for tf in TIMEFRAMES:
        tf_rows = [r for r in all_rows if r["cell"].endswith(f" {tf}")]
        if not tf_rows:
            per_tf[tf] = {"n": 0, "note": "tidak ada baris, sel gagal atau kosong"}
            continue
        base = np.array([r["r"] for r in tf_rows])
        graded = [evaluate(tf_rows, g, d) for g in GATE_GRID for d in DIRECTIONS]
        per_tf[tf] = {
            "n": len(tf_rows),
            "baseline_exp_r": round(float(base.mean()), 4),
            "census": census(tf_rows),
            "grid": graded,
            "passing": [g for g in graded if g["verdict"].startswith("gerbang")],
        }
        best = max(
            (g for g in graded if g["verdict"].startswith("gerbang")),
            key=lambda g: g["exp_r_kept"], default=None,
        )
        print(f"  == {tf}: n={len(tf_rows)} baseline={base.mean():+.4f} "
              f"terbaik={best['gate_atr'] if best else None} "
              f"{best['direction'] if best else '-'} "
              f"exp_r={best['exp_r_kept'] if best else None}", file=sys.stderr)

    # BEFORE LAWAN AFTER, dinyatakan sebagai angka dan bukan sebagai kesan.
    # "Before" adalah yang kode KIRIM hari ini: plafon 0,25 ATR, diwarisi dari
    # sweep FVG tanpa pernah diukur pada populasi ini.
    before = evaluate(all_rows, 0.25, "ceiling")
    passing = [r for r in results if r["verdict"].startswith("gerbang")]
    best_overall = max(
        passing, key=lambda g: g["exp_r_kept"], default=None,
    ) if passing else None

    json.dump({
        "question": "apakah IFVG punya gerbang departure, dan ke arah mana",
        "not_asked": "arah pasca-inversi; sudah diukur negatif di H8, n=38058",
        "cells": cells,
        "t_threshold_bonferroni": round(T_THRESHOLD, 4),
        "min_group": MIN_GROUP,
        "baseline_no_gate": {
            "n": int(baseline.size),
            "exp_r": round(float(baseline.mean()), 4) if baseline.size else None,
            "t_vs_zero": round(one_sample_t(baseline), 4) if baseline.size > 1 else None,
        },
        "before_shipped_0_25_ceiling": before,
        "best_measured": best_overall,
        "per_timeframe": per_tf,
        "grid": results,
        "passing": passing,
        "verdict": (
            "tidak ada gerbang yang lolos praregistrasi" if not passing
            else f"{len(passing)} sel lolos"
        ),
    }, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
