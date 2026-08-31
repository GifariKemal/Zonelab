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

#: Which column of the measured rows the overlay conditions on. `dfr_side` is the
#: one clause of the seventeen that separated, and its sign is INVERTED - see
#: `app/ict.py:MEASURED_AGAINST` and `docs/checklist_outcomes.json`.
CONDITIONER = "dfr_side"

#: Floor on a bucket before it is worth drawing. The same number
#: `tools.conditioned` uses, so a bucket with fewer trades than this is omitted
#: rather than drawn from noise.
MIN_GROUP = 30

QUANTILES = (5, 25, 50, 75, 95)

#: The measured verdict of the conditioner, copied from the source rather than
#: recomputed here.
VERDICT = "memisahkan, tanda terbalik (docs/checklist_outcomes.json)"

_KEY = {True: "met", False: "failed", None: "unknown"}


def quantile_set(vals: list[float]) -> dict:
    """Five quantiles of the given values, plus the count, as a JSON-ready dict."""
    v = np.asarray(vals, dtype=np.float64)
    return {"n": int(len(v)),
            **{f"q{q}": float(np.percentile(v, q)) for q in QUANTILES}}


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
        }
    return cells


def build(rows: list[dict]) -> dict:
    return {
        "preregistered": "tools/expectation.py, 2026-08-31",
        "conditioner": CONDITIONER,
        "outcome": "resolved R multiple (intrabar, 5m)",
        "min_group": MIN_GROUP,
        "verdict": VERDICT,
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
