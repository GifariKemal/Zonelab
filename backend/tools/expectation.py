"""Precompute the conditional-expectation table for the expectation overlay.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.expectation > ../docs/expectation.json

The overlay draws, at the chart's right edge, the measured distribution of
resolved R for setups that look like the one on screen. That distribution is
already measured in `docs/checklist_outcomes.json` - 1855 first-touch trades
resolved on 5-minute bars - so this tool does NOT re-run the 80-minute intrabar
pass. It re-buckets the same rows by the one separator that measured non-null,
`dfr_side`, and writes a small lookup table the backend loads.

The outcome is the resolved R multiple, not a fixed-horizon forward move. That is
a deliberate choice: R is the quantity every measurement in this repo reports
(`exp_r`), and a fan of R is a claim about how the trade resolved. The overlay
maps R to price through the current ATR with the stated approximation one R is
one ATR, which is the plan's own stop scale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from app.indicators import wilder_atr

#: Which column of the measured rows the overlay conditions on. `dfr_side` is the
#: one clause of the seventeen that separated, and its sign is INVERTED - see
#: `app/ict.py:MEASURED_AGAINST` and `docs/checklist_outcomes.json`.
CONDITIONER = "dfr_side"

#: Floor on a bucket before it is worth drawing. The same number
#: `tools.conditioned` uses, so a bucket with fewer trades than this is omitted
#: rather than drawn from noise.
MIN_GROUP = 30

QUANTILES = (5, 25, 50, 75, 95)

#: The forward path the overlay draws as one line: the MEDIAN cumulative move,
#: in ATR, at each horizon up to `PATH_HORIZON` bars, sampled every `PATH_STEP`.
#: It is UNCONDITIONAL - the whole population of bars, not the first-touch
#: population the fan is built from - because a path is a claim about time and
#: the first-touch rows carry no trajectory, only a resolved R. Two different
#: quantities, and the overlay labels them apart.
PATH_HORIZON = 96
PATH_STEP = 4

#: The bar interval the path is measured on, and the ONLY interval it may be
#: drawn on. `h` counts BARS, so 96 of them is four days at 1h and one day at
#: 15m: the same table rendered on a 15m chart would put a four-day median move
#: over a one-day span. The interval travels with the table so the overlay can
#: refuse the mismatch instead of drawing it.
PATH_INTERVAL = "1h"

#: The measured verdict of the conditioner, copied from the source rather than
#: recomputed here.
VERDICT = "memisahkan, tanda terbalik (docs/checklist_outcomes.json)"

_KEY = {True: "met", False: "failed", None: "unknown"}


def quantile_set(vals: list[float]) -> dict:
    """Five quantiles of the given values, plus the count, as a JSON-ready dict."""
    v = np.asarray(vals, dtype=np.float64)
    return {"n": int(len(v)),
            **{f"q{q}": float(np.percentile(v, q)) for q in QUANTILES}}


def path(candles: list) -> list[dict]:
    """The median forward move in ATR at each horizon, from the whole series.

    Median rather than mean: a handful of gap bars move the mean and not the
    middle, and the line is read as "where price usually got to", which is the
    median's question. Each horizon is measured from every bar that has one, so
    the windows overlap - the line is a description of the sample, and no
    significance is claimed for it anywhere.
    """
    if len(candles) < PATH_HORIZON + 30:
        return []
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, 14)
    out: list[dict] = []
    for h in range(PATH_STEP, PATH_HORIZON + 1, PATH_STEP):
        base = atr[:-h]
        ok = base > 0
        if not ok.any():
            continue
        moves = (close[h:] - close[:-h])[ok] / base[ok]
        out.append({"h": h, "q50": float(np.median(moves)), "n": int(ok.sum())})
    return out


def table(rows: list[dict]) -> dict:
    """One cell per symbol: a base rate, and one bucket per `dfr_side` value.

    A bucket is emitted only when it has at least `MIN_GROUP` trades, so a thin
    bucket is omitted rather than drawn from noise. The base rate always exists
    because it is the whole population for that symbol.
    """
    cells: dict[str, dict] = {}
    for symbol in sorted({r["symbol"] for r in rows}):
        mine = [r for r in rows if r["symbol"] == symbol]
        buckets: dict[str, dict] = {}
        for key in ("met", "failed", "unknown"):
            group = [r for r in mine if _KEY.get(r.get(CONDITIONER)) == key]
            if len(group) >= MIN_GROUP:
                buckets[key] = quantile_set([r["r"] for r in group])
        cells[symbol] = {
            "base_rate": quantile_set([r["r"] for r in mine]),
            "buckets": buckets,
            "path": _path_for(symbol),
        }
    return cells


def _path_for(symbol: str) -> list[dict]:
    """The forward path for one symbol, or an empty list when it cannot load.

    Imported lazily so `--selfcheck` and any unit test can exercise the bucket
    arithmetic without a provider on the other end.
    """
    try:
        from tools.quant import clean

        candles, _, _ = clean(symbol, PATH_INTERVAL)
    except Exception:
        return []
    return path(candles or [])


def build(rows: list[dict]) -> dict:
    return {
        "preregistered": "tools/expectation.py, 2026-08-31",
        "conditioner": CONDITIONER,
        "outcome": "resolved R multiple (intrabar, 5m)",
        "min_group": MIN_GROUP,
        "verdict": VERDICT,
        "path_horizon": PATH_HORIZON,
        "path_interval": PATH_INTERVAL,
        "cells": table(rows),
    }


def load_rows(path: str) -> list[dict]:
    """The measured rows out of `docs/checklist_outcomes.json`.

    `r` is re-read as a float because the table stored it rounded to six places,
    and the `rows` block is columnar so the file stays small.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    columns = raw["rows"]["columns"]
    out: list[dict] = []
    for data in raw["rows"]["data"]:
        row = dict(zip(columns, data))
        row["r"] = float(row["r"])
        out.append(row)
    return out


def selfcheck() -> int:
    """The arithmetic this tool exists to get right, verified on synthetic data."""
    rows = []
    for i in range(120):
        flag = True if i % 3 == 0 else (False if i % 3 == 1 else None)
        r = 1.0 if flag is True else (-1.0 if flag is False else 0.0)
        rows.append({"symbol": "X", "r": r, CONDITIONER: flag})
    cells = table(rows)
    cell = cells["X"]
    assert cell["base_rate"]["n"] == 120
    assert cell["buckets"]["met"]["q50"] > 0
    assert cell["buckets"]["failed"]["q50"] < 0
    # The floor omits a thin bucket rather than drawing it from noise.
    thin = table([{"symbol": "X", "r": 0.0, CONDITIONER: True}])
    assert thin["X"]["buckets"] == {}, "a one-trade bucket must be omitted"
    # The path: a straight synthetic ramp of +1 per bar with a unit ATR must give
    # a median move of exactly h at horizon h, so an off-by-one in the slicing or
    # a mean-for-median swap fails here rather than on the chart.
    from app.models import Candle

    # No wick, so the true range of every bar is exactly the +1 step and the
    # ATR is exactly 1. Then the median move at horizon h must be exactly h.
    ramp = [Candle(time=i * 3600, open=float(i), high=float(i),
                   low=float(i), close=float(i), volume=0.0)
            for i in range(400)]
    pts = path(ramp)
    assert pts, "a 400-bar series must produce a path"
    assert [p["h"] for p in pts] == list(range(PATH_STEP, PATH_HORIZON + 1, PATH_STEP))
    for p in pts:
        assert abs(p["q50"] - p["h"]) < 0.05, (p["h"], p["q50"])
    assert path(ramp[:50]) == [], "too short a series must yield no path"
    # Quantiles are monotone.
    b = cell["base_rate"]
    assert b["q5"] <= b["q25"] <= b["q50"] <= b["q75"] <= b["q95"]
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rows",
        default=str(
            Path(__file__).resolve().parents[2] / "docs" / "checklist_outcomes.json"
        ),
    )
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()
    if args.selfcheck:
        return selfcheck()
    rows = load_rows(args.rows)
    json.dump(build(rows), sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
