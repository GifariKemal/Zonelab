# FVG Recalibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove FVG detection is geometrically correct via cross-engine parity, then find the optimal gate parameter via measured sweep, replacing the current inverted gate.

**Architecture:** Two parallel tracks. Track 1: Pine Script FVG indicator compiled in TradingView Desktop, reading back box coordinates via `data_get_pine_boxes`. Track 2: Python parameter sweep tool reusing `detect_fvg` and `cell_rows` from `tools/detectors_costed.py`. The two tracks merge at a parity check comparing Pine box coordinates against Python box coordinates on the same bars. Gate decision follows from the sweep. Report documents everything with provenance.

**Tech Stack:** Pine Script v6, Python 3.13 (existing venv), numpy, existing `tools/intrabar` rig, TradingView Desktop MCP (84 tools via CDP).

## Global Constraints

- Instrument: XAUUSD only. Other instruments after pipeline proves itself.
- Timeframe fokus: 30m. 1H dan 4H sebagai validasi.
- Ground truth: pure ICT wick-to-wick (`high[i-1] < low[i+1]` / `low[i-1] > high[i+1]`).
- Detection logic di `imbalance.py` TIDAK berubah. Yang berubah: parameter dan gate.
- Walk-forward 8-fold. Pass: difference > 0, |welch t| > 2.24, >= 7/8 folds positive.
- Ponytail: shortest diff, reuse existing functions, no abstractions.
- Semua angka dari command yang dijalankan, bukan dari ringkasan.
- `humanize-tone` voice target berlaku di semua output teks.
- Pine Script: indicator type, max 500 `box.new()`, `ta.atr()` (Wilder).
- Parity tolerance: `tick_size` per instrumen (0.01 untuk XAUUSD).

---

### Task 1: Pine Script FVG Indicator

**Files:**
- Create: `mql5/pine/ZonelabFVG.pine`

**Interfaces:**
- Consumes: nothing (standalone indicator)
- Produces: box coordinates readable via `data_get_pine_boxes`, console log parseable as CSV (`FVG,{unix_time},{side},{top},{bottom},{size_atr}`)

- [ ] **Step 1: Write Pine Script**

```pine
// This source code is subject to the terms of the Mozilla Public License 2.0
// at https://mozilla.org/MPL/2.0/
// Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)

//@version=6
indicator("Zonelab FVG", overlay=true, max_boxes_count=500)

atr_period  = input.int(14, "ATR Period", minval=1)
min_gap_atr = input.float(0.1, "Min Gap (ATR)", minval=0.0, step=0.05)
max_boxes   = input.int(200, "Max Boxes", minval=10, maxval=500)
show_labels = input.bool(true, "Show Labels")

atr_val = ta.atr(atr_period)

bull_fvg = high[2] < low[0]
bear_fvg = low[2] > high[0]

bull_gap = bull_fvg ? low[0] - high[2] : 0.0
bear_gap = bear_fvg ? low[2] - high[0] : 0.0

bull_pass = bull_fvg and not na(atr_val) and atr_val > 0 and bull_gap >= min_gap_atr * atr_val
bear_pass = bear_fvg and not na(atr_val) and atr_val > 0 and bear_gap >= min_gap_atr * atr_val

var int box_count = 0

if bull_pass
    if box_count >= max_boxes
        box.delete(box.all.first())
    else
        box_count += 1
    top_price = low[0]
    bot_price = high[2]
    box.new(bar_index[2], top_price, bar_index, bot_price,
         bgcolor=color.new(color.blue, 85),
         border_color=color.new(color.blue, 60),
         extend=extend.right)
    if show_labels
        label.new(bar_index[1], (top_price + bot_price) / 2,
             str.tostring(bull_gap / atr_val, "#.##") + " ATR",
             style=label.style_label_center, size=size.tiny,
             color=color.new(color.blue, 90), textcolor=color.blue)
    log.info("FVG," + str.tostring(time[2]) + ",demand," +
         str.tostring(top_price) + "," + str.tostring(bot_price) + "," +
         str.tostring(bull_gap / atr_val))

if bear_pass
    if box_count >= max_boxes
        box.delete(box.all.first())
    else
        box_count += 1
    top_price = low[2]
    bot_price = high[0]
    box.new(bar_index[2], top_price, bar_index, bot_price,
         bgcolor=color.new(color.red, 85),
         border_color=color.new(color.red, 60),
         extend=extend.right)
    if show_labels
        label.new(bar_index[1], (top_price + bot_price) / 2,
             str.tostring(bear_gap / atr_val, "#.##") + " ATR",
             style=label.style_label_center, size=size.tiny,
             color=color.new(color.red, 90), textcolor=color.red)
    log.info("FVG," + str.tostring(time[2]) + ",supply," +
         str.tostring(top_price) + "," + str.tostring(bot_price) + "," +
         str.tostring(bear_gap / atr_val))
```

- [ ] **Step 2: Launch TradingView Desktop dan compile**

```bash
# Load tool schemas dulu
# ToolSearch("select:mcp__tradingview-desktop__tv_launch,mcp__tradingview-desktop__tv_health_check,mcp__tradingview-desktop__pine_set_source,mcp__tradingview-desktop__pine_smart_compile,mcp__tradingview-desktop__pine_get_errors,mcp__tradingview-desktop__chart_set_symbol,mcp__tradingview-desktop__chart_set_timeframe")

# 1. tv_launch
# 2. tv_health_check - pastikan cdp_connected: true
# 3. chart_set_symbol("OANDA:XAUUSD")
# 4. chart_set_timeframe("30")
# 5. pine_set_source(<isi file ZonelabFVG.pine>)
# 6. pine_smart_compile
# 7. pine_get_errors - harus kosong
```

Expected: indicator ter-compile tanpa error, box biru (demand) dan merah (supply) muncul di chart.

- [ ] **Step 3: Baca box coordinates dari TradingView**

```bash
# data_get_pine_boxes(study_filter="Zonelab FVG")
# Simpan hasilnya ke file sementara untuk parity check nanti
```

Expected: array of `{high, low}` pairs dengan timestamp, parseable.

- [ ] **Step 4: Screenshot verifikasi visual**

```bash
# capture_screenshot(region="chart")
```

Expected: FVG boxes terlihat di chart XAUUSD 30m, demand biru, supply merah. Boxes sejajar dengan gap tiga-bar yang terlihat.

- [ ] **Step 5: Baca console log**

```bash
# pine_get_console
# Parse output CSV: FVG,{time},{side},{top},{bottom},{size_atr}
```

Expected: tiap baris log cocok dengan satu box di chart.

- [ ] **Step 6: Commit**

```bash
git add mql5/pine/ZonelabFVG.pine
git commit -m "Add Pine Script FVG indicator for parity check

Pure wick-to-wick detection matching imbalance.py _gap().
Indicator type, max 500 boxes, console log CSV for parsing.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Python Parameter Sweep Tool

**Files:**
- Create: `backend/tools/fvg_sweep.py`

**Interfaces:**
- Consumes: `tools.detectors_costed.cell_rows`, `tools.detectors_costed.welch`, `tools.detectors_costed.one_sample_t`, `tools.detectors_costed.FOLDS`, `tools.costed._params`, `tools.conditioned._critical_t`
- Produces: `docs/fvg_sweep.json` - array of 42 objects sorted by walk-forward stability

- [ ] **Step 1: Write the sweep tool**

```python
"""Parameter sweep untuk FVG: min_gap_atr x gate_atr di 30m XAUUSD+BTCUSD.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_sweep > ../docs/fvg_sweep.json

Grid: 7 min_gap_atr x 6 gate_atr = 42 konfigurasi.
Tiap konfigurasi diukur di dua sel (XAUUSD 30m, BTCUSD 30m) lalu di-pool.
Walk-forward 8-fold per konfigurasi.

Reuse `cell_rows` dari `detectors_costed` yang sudah menangani resolusi
intrabar, posisi relatif, dan purging fold. Detection-nya tetap `detect_fvg`
tanpa modifikasi; yang berubah hanya `min_gap_atr` yang dikirim ke
`ImbalanceParams` lewat `_params`.
"""

from __future__ import annotations

import contextlib
import json
import math
import sys

import numpy as np

from app.detect import DETECTORS
from app.models.params import ImbalanceParams
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, cell_rows, one_sample_t, welch
from tools.intrabar import FINER

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]

MIN_GAP_VALUES = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5]
GATE_VALUES = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0]

T_THRESHOLD = _critical_t(len(MIN_GAP_VALUES) * len(GATE_VALUES))


def _walk(rows: list[dict], gate: float) -> dict:
    """8-fold walk-forward pada exp_R bawah gate."""
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    out = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        if gate > 0:
            below = [r["r"] for r in kept
                     if r["departure_atr"] < gate]
            above = [r["r"] for r in kept
                     if r["departure_atr"] >= gate]
        else:
            below = [r["r"] for r in kept]
            above = []
        entry: dict = {"fold": k + 1,
                       "n_below": len(below), "n_above": len(above),
                       "purged": len(opened) - len(kept)}
        if len(below) >= 20:
            entry["exp_r"] = float(np.mean(below))
            entry["readable"] = True
        else:
            entry["readable"] = False
        out.append(entry)
    graded = [e for e in out if e["readable"]]
    return {"folds": out, "graded": len(graded),
            "positive": sum(1 for e in graded if e.get("exp_r", 0) > 0)}


def _sweep_one(min_gap: float, gate: float) -> dict:
    """Satu konfigurasi: pool dua sel, hitung metrik."""
    pooled: list[dict] = []
    per_cell: dict = {}

    original_fvg = DETECTORS.get("fvg")
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True,
                             min_gap_atr=min_gap)

    for symbol, interval in CELLS:
        label = f"{symbol} {interval}"
        try:
            real_fvg = DETECTORS["fvg"]
            DETECTORS["supply_demand"] = lambda c, _ig, _p=params, _r=real_fvg: (
                _r(c, _p)
            )
            with contextlib.redirect_stdout(sys.stderr):
                rows, span = cell_rows("supply_demand", symbol, interval)
        except Exception as exc:
            per_cell[label] = {"error": str(exc)}
            continue
        finally:
            from app.detect.supply_demand import detect as _orig_sd
            DETECTORS["supply_demand"] = _orig_sd

        for r in rows:
            r["departure_atr"] = r.get("departure_atr", 0.0)
        pooled.extend(rows)
        per_cell[label] = {"bars": span, "n": len(rows)}

    if not pooled:
        return {"min_gap_atr": min_gap, "gate_atr": gate,
                "error": "no rows", "cells": per_cell}

    if gate > 0:
        below = np.array([r["r"] for r in pooled
                          if r["departure_atr"] < gate])
        above = np.array([r["r"] for r in pooled
                          if r["departure_atr"] >= gate])
    else:
        below = np.array([r["r"] for r in pooled])
        above = np.array([])

    wf = _walk(pooled, gate)

    result = {
        "min_gap_atr": min_gap, "gate_atr": gate,
        "n_below": int(below.size), "n_above": int(above.size),
        "exp_r_below": float(below.mean()) if below.size else None,
        "exp_r_above": float(above.mean()) if above.size else None,
        "t_below_vs_zero": one_sample_t(below) if below.size > 1 else None,
        "walk_forward": wf,
        "cells": per_cell,
    }
    if below.size and above.size:
        result["difference"] = float(below.mean() - above.mean())
        result["welch_t"] = welch(below, above)
    elif below.size:
        result["exp_r_all"] = float(below.mean())

    return result


def main() -> int:
    results = []
    total = len(MIN_GAP_VALUES) * len(GATE_VALUES)
    for i, min_gap in enumerate(MIN_GAP_VALUES):
        for j, gate in enumerate(GATE_VALUES):
            idx = i * len(GATE_VALUES) + j + 1
            print(f"  [{idx}/{total}] min_gap={min_gap} gate={gate}",
                  file=sys.stderr)
            results.append(_sweep_one(min_gap, gate))

    results.sort(key=lambda r: (
        -(r.get("walk_forward", {}).get("positive", 0)),
        -(r.get("exp_r_below") or -999),
    ))

    out = {
        "grid": {"min_gap_atr": MIN_GAP_VALUES, "gate_atr": GATE_VALUES},
        "cells": [f"{s} {i}" for s, i in CELLS],
        "t_threshold_bonferroni": T_THRESHOLD,
        "folds": FOLDS,
        "results": results,
    }
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verifikasi import dan run dry**

Run:
```
cd C:\Users\Administrator\Music\Zonelab\backend
PYTHONPATH=. .venv\Scripts\python.exe -c "from tools.fvg_sweep import main; print('imports OK')"
```
Expected: `imports OK`, no import error.

- [ ] **Step 3: Run sweep (estimasi 5-10 menit)**

Run:
```
cd C:\Users\Administrator\Music\Zonelab\backend
PYTHONPATH=. .venv\Scripts\python.exe -m tools.fvg_sweep > ..\docs\fvg_sweep.json
```
Expected: 42 configurations processed, output to `docs/fvg_sweep.json`. Progress di stderr.

- [ ] **Step 4: Validasi output**

```python
import json
data = json.load(open("../docs/fvg_sweep.json"))
assert len(data["results"]) == 42
assert all("min_gap_atr" in r for r in data["results"])
assert all("gate_atr" in r for r in data["results"])
# Gate=0 berarti semua FVG masuk, jadi n_above harus 0
no_gate = [r for r in data["results"] if r["gate_atr"] == 0]
assert all(r["n_above"] == 0 for r in no_gate)
print("sweep output valid")
```

- [ ] **Step 5: Commit**

```bash
git add backend/tools/fvg_sweep.py docs/fvg_sweep.json
git commit -m "Add FVG parameter sweep: 7 min_gap x 6 gate on 30m XAUUSD+BTCUSD

42 configurations, walk-forward 8-fold each. Reuses cell_rows
from detectors_costed for intrabar resolution and fold purging.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Parity Check Tool

**Files:**
- Create: `backend/tools/fvg_parity.py`

**Interfaces:**
- Consumes: `detect_fvg` dari `app/detect/imbalance.py`, Pine box data dari TradingView MCP `data_get_pine_boxes`, OHLCV dari `data_get_ohlcv`
- Produces: `docs/fvg_parity.json` - match rate, mismatches, per-FVG comparison

- [ ] **Step 1: Write parity check tool**

```python
"""Parity check: Pine Script FVG vs Python detect_fvg pada bar yang sama.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_parity \
        --pine-boxes pine_boxes.json \
        --python-bars ohlcv.json \
        > ../docs/fvg_parity.json

Input:
  --pine-boxes: JSON dari data_get_pine_boxes (array of {high, low, ...})
  --python-bars: JSON dari data_get_ohlcv (array of {time, open, high, low, close, volume})

Matching rule:
  Dua FVG identik jika time_from, side, dan harga top/bottom cocok
  dalam toleransi tick_size (0.01 untuk XAUUSD).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.detect.imbalance import detect_fvg
from app.models.candle import Candle
from app.models.params import ImbalanceParams

TICK_SIZE = 0.01


def _python_fvgs(bars: list[dict]) -> list[dict]:
    """Jalankan detect_fvg pada OHLCV bars, kembalikan list sederhana."""
    candles = [
        Candle(
            time=b["time"], open=b["open"], high=b["high"],
            low=b["low"], close=b["close"], volume=b.get("volume", 0),
        )
        for b in bars
    ]
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True)
    zones, stats = detect_fvg(candles, params)
    out = []
    for z in zones:
        out.append({
            "time_from": z.time_from,
            "side": z.side.value,
            "top": z.top,
            "bottom": z.bottom,
            "departure_atr": z.departure_atr,
        })
    return out, stats


def _match(pine: list[dict], python: list[dict], tol: float) -> dict:
    """Match Pine boxes ke Python zones."""
    matched = []
    pine_only = []
    python_only = list(python)
    geometry_mismatch = []

    for pb in pine:
        found = False
        for pz in python_only:
            time_match = abs(pb["time_from"] - pz["time_from"]) < 1000
            side_match = pb["side"] == pz["side"]
            if time_match and side_match:
                if (abs(pb["top"] - pz["top"]) < tol
                        and abs(pb["bottom"] - pz["bottom"]) < tol):
                    matched.append({"pine": pb, "python": pz})
                else:
                    geometry_mismatch.append({"pine": pb, "python": pz})
                python_only.remove(pz)
                found = True
                break
        if not found:
            pine_only.append(pb)

    total = len(matched) + len(pine_only) + len(python_only) + len(geometry_mismatch)
    match_rate = len(matched) / total if total else 0.0

    return {
        "n_pine": len(pine),
        "n_python": len(python),
        "n_matched": len(matched),
        "match_rate": round(match_rate, 4),
        "pine_only": pine_only,
        "python_only": python_only,
        "geometry_mismatch": geometry_mismatch,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pine-boxes", required=True)
    ap.add_argument("--python-bars", required=True)
    ap.add_argument("--tick-size", type=float, default=TICK_SIZE)
    args = ap.parse_args()

    with open(args.pine_boxes) as f:
        pine_raw = json.load(f)
    with open(args.python_bars) as f:
        bars = json.load(f)

    # Parse Pine boxes ke format standar
    pine = []
    for b in pine_raw:
        pine.append({
            "time_from": b.get("time_from", b.get("x1_time", 0)),
            "side": "demand" if b.get("bgcolor", "").find("blue") >= 0
                    else "supply",
            "top": b["high"] if "high" in b else b.get("y1", 0),
            "bottom": b["low"] if "low" in b else b.get("y2", 0),
        })

    python, stats = _python_fvgs(bars)
    result = _match(pine, python, args.tick_size)
    result["detection_stats"] = stats
    result["tick_size"] = args.tick_size

    print(f"  Pine: {len(pine)}, Python: {len(python)}, "
          f"Matched: {result['n_matched']}, "
          f"Rate: {result['match_rate']:.1%}", file=sys.stderr)

    json.dump(result, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verifikasi import**

Run:
```
cd C:\Users\Administrator\Music\Zonelab\backend
PYTHONPATH=. .venv\Scripts\python.exe -c "from tools.fvg_parity import main; print('imports OK')"
```
Expected: `imports OK`.

- [ ] **Step 3: Kumpulkan data dari TradingView untuk parity**

Langkah ini interaktif, membutuhkan TradingView Desktop hidup:

1. `data_get_pine_boxes(study_filter="Zonelab FVG")` - simpan ke `pine_boxes.json`
2. `data_get_ohlcv(count=500, summary=false)` - simpan ke `ohlcv.json`

Kedua file di-save ke `backend/` sebagai input sementara.

- [ ] **Step 4: Run parity check**

Run:
```
cd C:\Users\Administrator\Music\Zonelab\backend
PYTHONPATH=. .venv\Scripts\python.exe -m tools.fvg_parity \
    --pine-boxes pine_boxes.json --python-bars ohlcv.json \
    > ..\docs\fvg_parity.json
```
Expected: match rate >= 95%. Kalau kurang, trace tiap mismatch.

- [ ] **Step 5: Commit**

```bash
git add backend/tools/fvg_parity.py docs/fvg_parity.json
git commit -m "Add FVG parity check: Pine Script vs Python detect_fvg

Match rate measured on XAUUSD 30m visible range.
Tolerance: tick_size (0.01). Matching by time_from + side + price.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Gate Decision

**Files:**
- Modify: `backend/app/layers.py:138` (evidence string update)
- Modify: `backend/app/models/params.py` (update defaults jika parameter berubah)

**Interfaces:**
- Consumes: `docs/fvg_sweep.json`, `docs/fvg_parity.json`
- Produces: keputusan gate yang terukur, perubahan di layers.py

- [ ] **Step 1: Analisis sweep results**

Baca `docs/fvg_sweep.json`. Cari konfigurasi terbaik:
1. Filter: walk-forward >= 7/8 positive
2. Filter: |t_below_vs_zero| > T_THRESHOLD
3. Sort: exp_r_below descending
4. Kalau gate=0 (tanpa gate) lolos semua kriteria, itu jawaban paling sederhana
5. Kalau gate terbalik (below > above) pada threshold tertentu, catat threshold itu

- [ ] **Step 2: Ambil keputusan**

Tiga kemungkinan:
- **Buang gate** jika gate=0 positif dan stabil
- **Balik gate** (ceiling, bukan floor) jika threshold X menghasilkan below > above yang stabil
- **Tidak ubah** jika tidak ada konfigurasi yang pass

Keputusan ini ditentukan ANGKA, bukan argumen.

- [ ] **Step 3: Update layers.py jika parameter berubah**

Jika min_gap_atr berubah dari 0.1:
```python
# Di backend/app/layers.py, baris sekitar 138
# Update evidence string dengan angka dari sweep
```

Jika gate berubah:
```python
# Update gate="ceiling" atau gate=None sesuai keputusan
```

- [ ] **Step 4: Update params.py jika default berubah**

Jika min_gap_atr optimal bukan 0.1:
```python
# Di backend/app/models/params.py, ImbalanceParams
# min_gap_atr: float = <new_value>
```

- [ ] **Step 5: Run existing gates**

```
cd C:\Users\Administrator\Music\Zonelab\backend
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pyflakes app tools tests
```
Expected: semua test hijau, pyflakes bersih.

- [ ] **Step 6: Commit**

```bash
git add backend/app/layers.py backend/app/models/params.py
git commit -m "Update FVG gate based on measured sweep

<decision summary with numbers here>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Report

**Files:**
- Create: `docs/QA-FVG-RECALIBRATION.md`

**Interfaces:**
- Consumes: `docs/fvg_sweep.json`, `docs/fvg_parity.json`, screenshot TradingView, keputusan Task 4
- Produces: prose report dengan provenance, terdaftar di `docs/README.md`

- [ ] **Step 1: Write report**

```markdown
# QA: FVG Recalibration

Pengukuran akurasi detection dan rekalibrasi gate parameter FVG.
Tanggal: 2026-09-05.

## 1. Ringkasan

<keputusan gate, angka-angka kunci>

## 2. Parity check

Pine Script vs Python detect_fvg pada XAUUSD 30m.
Match rate: <dari fvg_parity.json>.
Mismatch: <jumlah dan sebab>.

## 3. Parameter sweep

42 konfigurasi (7 min_gap_atr x 6 gate_atr) pada XAUUSD+BTCUSD 30m.

<tabel top-10 konfigurasi>

## 4. Gate decision

<opsi yang dipilih dan angkanya>

## 5. Kontrol resolusi

<dari lowtf_resolution jika dijalankan>

## 6. Yang TIDAK berubah

- Detection logic di imbalance.py: tidak berubah
- MQL5 FVGDetector.mqh: tidak berubah
- 1231 test: tetap hijau
```

- [ ] **Step 2: Update docs/README.md**

Tambahkan entry untuk `QA-FVG-RECALIBRATION.md` di peta dokumen.

- [ ] **Step 3: Run semua gate**

```
cd C:\Users\Administrator\Music\Zonelab\backend
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pyflakes app tools tests
cd ..\frontend
npm run check
npm run build
```
Expected: semua exit 0.

- [ ] **Step 4: Commit**

```bash
git add docs/QA-FVG-RECALIBRATION.md docs/README.md
git commit -m "Add FVG recalibration report

Parity check, parameter sweep, and gate decision documented.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Catatan eksekusi

**Paralelisasi:** Task 1 (Pine Script) dan Task 2 (Python sweep) bisa dijalankan bersamaan oleh dua subagent. Task 3 (parity) butuh output keduanya. Task 4 butuh Task 2 dan 3. Task 5 butuh semuanya.

**Dependency graph:**
```
Task 1 (Pine) ----\
                   +--> Task 3 (Parity) --> Task 4 (Gate) --> Task 5 (Report)
Task 2 (Sweep) ---/
```

**Perhatian khusus pada sweep tool:** `cell_rows` memanggil `intrabar.resolved` yang mencetak ke stdout. Semua panggilan sudah di-wrap dengan `contextlib.redirect_stdout(sys.stderr)`. Kalau output JSON corrupt, itu penyebab pertama yang dicek.

**Perhatian pada Pine parsing:** format output `data_get_pine_boxes` belum pasti bentuknya sampai dijalankan. Step 3 di Task 3 mungkin perlu adaptasi parser Pine box berdasarkan format aktual yang dikembalikan MCP.
