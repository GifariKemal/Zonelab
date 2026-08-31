"""Does a CISD inside an order block condition the block's resolved R? (intrabar)

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.csid_ob_intrabar > ../docs/csid_ob_intrabar.json

The intrabar cousin of `tools/csid_ob_outcomes.py`, which measured the DIRECTIONAL
forward move and came out null (t=+1.81) with the condition near-degenerate (97%
of blocks have a CISD inside). This one measures the RESOLVED R multiple - the
repo's canonical trade outcome - by resolving order blocks on 5-minute bars
through `tools.detectors_costed.resolved_as("order_block", ...)`, the same rig
that produced `docs/detectors_costed.json` (order_block PASS).

PRIOR, stated. `cisd_in_band` for the supply/demand box is NULL (t=-1.29,
`docs/checklist_outcomes.json`), a standalone CISD is NULL (t=-0.53,
`app/layers.py`), and the directional version of this exact question is NULL. So
the prior for a CISD inside a block conditioning the resolved R is low.

HYPOTHESIS, two-sided. The resolved R of blocks whose band contains a RECENT CISD
level (formed within RECENT_BARS of the touch) differs from blocks whose band
does not, both measured above the 2.0 ATR departure gate. Two-sided because a
recent CISD inside a block could read as confirmation or as the block already
being mitigated. The recency is the tightening: without it the condition is
degenerate (95% of blocks hold SOME CISD level), and a stale level from weeks
ago is not a state-of-delivery reading at this block.

SYARAT LOLOS. n >= 30 in both arms, |Welch t| past the Bonferroni bar (2 groups),
and walk-forward 8 folds with a stable sign. A near-degenerate split (one arm
over 95% of the population) is reported as such rather than as a separating
result.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys

import numpy as np

from app.cisd import cisds
from app.detect import DETECTORS
from app.providers.base import INTERVALS
from tools.conditioned import _critical_t
from tools.costed import _params
from tools.detectors_costed import resolved_as
from tools.intrabar import FINER
from tools.quant import clean

FOLDS = 8
MIN_FOLD = 20

SYMBOLS = ("XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
           "AUDUSD", "US30", "USOIL")

MIN_GROUP = 30
K = 2  # two groups judged: CISD inside vs not

#: A CISD counts as "inside the block" only when it formed within this many bars
#: before the block's first touch. The un-tightened condition is degenerate (95%
#: of blocks hold SOME CISD level, because levels are dense and bands are wide);
#: this recency window cuts it to a balanced split. 50 hourly bars is about two
#: days - a fresh enough state-of-delivery to read as confirmation, a stale level
#: is not. Chosen, not measured: see the selectivity probe in the session log.
RECENT_BARS = 50


def _welch(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else float("nan")


def _efficiency(closes: list[float], touch_idx: int, n: int = 20) -> float | None:
    """Arrival efficiency: net move over path length, low = choppy.

    The confound probe: `fresh CISD inside` correlates with this at t=-77, so a
    fresh CISD is largely a proxy for a choppy arrival. This measure is orthogonal
    to the CISD definition and is used to control for it.
    """
    lo = touch_idx - n
    if lo < 0 or touch_idx - lo < 2:
        return None
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(lo + 1, touch_idx + 1))
    net = abs(closes[touch_idx] - closes[lo])
    return net / path if path > 0 else None


def _wf_in_band(rows: list[dict]) -> dict:
    """Eight time folds, the CISD-inside delta in each.

    Split by `in_band`, NOT by the departure gate, and pooled across cells by the
    relative position `pos` (0 at the first assessable trade, 1 at the last), the
    same correction the 5m-vs-1h history gap forces everywhere else here.
    """
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    folds = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        inside = [r["r"] for r in kept if r["in_band"]]
        outside = [r["r"] for r in kept if not r["in_band"]]
        entry = {"fold": k + 1, "n_inside": len(inside), "n_outside": len(outside),
                 "purged": len(opened) - len(kept)}
        if len(inside) < MIN_FOLD or len(outside) < MIN_FOLD:
            entry["readable"] = False
            entry["delta"] = None
        else:
            entry["readable"] = True
            entry["delta"] = float(np.mean(inside) - np.mean(outside))
        folds.append(entry)
    graded = [f for f in folds if f["readable"]]
    positive = [f for f in graded if f["delta"] > 0]
    return {
        "folds": folds,
        "graded": len(graded),
        "positive": len(positive),
        "failed": [f["fold"] for f in graded if f["delta"] <= 0],
    }


def cell_rows(symbol: str, interval: str) -> list[dict]:
    fine = FINER[interval]
    with contextlib.redirect_stdout(sys.stderr):
        rows = [r for r in resolved_as("order_block", symbol, interval, fine)
                if r["cleared"]]
    if not rows:
        return []
    candles, _, _ = clean(symbol, interval)
    # Re-detect the order blocks to recover each band, matched by zone id. The
    # SAME params `resolved_as` used, so the ids are byte-for-byte the same set.
    blocks, _ = DETECTORS["order_block"](candles, _params("order_block"))
    by_id = {z.id: z for z in blocks}
    times = [c.time for c in candles]
    closes = [c.close for c in candles]
    events, _ = cisds(candles)
    # CISD levels sorted by time, for the anti-lookahead lookup.
    cisd_sorted = sorted(events, key=lambda e: e.time)

    out: list[dict] = []
    for row in rows:
        block = by_id.get(row["zone_id"])
        if block is None or int(row["at"]) < 1:
            continue
        now = times[int(row["at"])]
        # A CISD is in the band when its level sits inside it, was knowable at the
        # touch bar, AND formed within RECENT_BARS of the touch. The recency half
        # is the whole tightening: without it the condition is degenerate.
        window = RECENT_BARS * INTERVALS[interval]
        in_band = any(
            block.bottom <= e.level <= block.top and 0 <= now - e.time <= window
            for e in cisd_sorted
        )
        out.append({"r": row["r"], "at": int(row["at"]),
                    "fine_bars_held": row["fine_bars_held"],
                    "efficiency": _efficiency(closes, int(row["at"])),
                    "in_band": in_band, "cell": f"{symbol} {interval}"})

    # The relative position, measured on the ASSESSABLE range not the full series,
    # the same correction detectors_costed made: the 5m history covers ~347 days
    # while the 1h series is far longer, so every resolved trade sits in the tail.
    ratio = INTERVALS[interval] // INTERVALS[fine]
    for r in out:
        r["exit_est"] = r["at"] + math.ceil(r["fine_bars_held"] / ratio)
    if out:
        lo = min(r["at"] for r in out)
        width = max(max(r["exit_est"] for r in out) - lo, 1)
        for r in out:
            r["pos"] = (r["at"] - lo) / width
            r["exit_pos"] = (r["exit_est"] - lo) / width
    return out


def study(symbols: list[str], interval: str) -> dict:
    rows: list[dict] = []
    per_cell: dict[str, dict] = {}
    for symbol in symbols:
        try:
            got = cell_rows(symbol, interval)
        except Exception as exc:
            per_cell[f"{symbol} {interval}"] = {"error": str(exc)}
            continue
        rows += got
        inside = [r["r"] for r in got if r["in_band"]]
        outside = [r["r"] for r in got if not r["in_band"]]
        per_cell[f"{symbol} {interval}"] = {
            "n": len(got), "n_in": len(inside), "n_out": len(outside),
            "exp_r_in": float(np.mean(inside)) if inside else None,
            "exp_r_out": float(np.mean(outside)) if outside else None,
            "delta": float(np.mean(inside) - np.mean(outside))
            if inside and outside else None,
            "welch_t": _welch(np.array(inside), np.array(outside))
            if inside and outside else None,
        }
        print(f"  {symbol}: {len(got)} trade", file=sys.stderr)
    if not rows:
        return {"error": "populasi kosong", "cells": per_cell}

    inside = np.array([r["r"] for r in rows if r["in_band"]])
    outside = np.array([r["r"] for r in rows if not r["in_band"]])
    n_in, n_out = len(inside), len(outside)
    total = n_in + n_out
    out: dict = {
        "preregistered": "tools/csid_ob_intrabar.py, 2026-08-31",
        "question": "apakah CISD di dalam order block mengkondisikan resolved R",
        "rig": "tools.detectors_costed.resolved_as(order_block), bar 5m, biaya",
        "cells": per_cell,
        "population": {
            "n": total, "n_cisd_inside": n_in, "n_no_cisd": n_out,
            "pct_inside": round(100 * n_in / total, 1) if total else None,
            "exp_r_in_band": float(inside.mean()) if n_in else None,
            "exp_r_no_cisd": float(outside.mean()) if n_out else None,
        },
    }
    if n_in < 2 or n_out < 2:
        out["verdict"] = "degenerat: satu lengan kosong"
        return out

    delta = float(inside.mean() - outside.mean())
    t = _welch(inside, outside)
    wf = _wf_in_band(rows)
    crit = _critical_t(K)
    out["result"] = {
        "delta": delta, "welch_t": t, "critical_t": crit,
        "walk_forward": wf,
    }
    degenerate = (max(n_in, n_out) / total) > 0.95
    out["degenerate"] = degenerate
    out["verdict"] = (
        "MEMISAHKAN" if (not degenerate and n_in >= MIN_GROUP and n_out >= MIN_GROUP
                         and abs(t) >= crit
                         and wf["graded"] == 8 and wf["positive"] in (0, 8))
        else ""
    )
    if degenerate:
        out["verdict"] += " (hampir degenerat, satu lengan > 95% populasi)"

    # CONFOUND: is the CISD effect a proxy for arrival choppiness? Split by the
    # median arrival efficiency (low = choppy) and by CISD-in-band, and read the
    # CISD delta WITHIN each choppiness bucket. If it is a proxy, the within-bucket
    # delta collapses while the between-bucket (choppy vs clean) delta stays.
    effs = [r["efficiency"] for r in rows if r["efficiency"] is not None]
    if effs:
        med = float(np.median(effs))
        buckets = {"choppy_cisd": [], "choppy_nocisd": [], "clean_cisd": [],
                   "clean_nocisd": []}
        for r in rows:
            if r["efficiency"] is None:
                continue
            choppy = r["efficiency"] < med
            key = ("choppy" if choppy else "clean") + (
                "_cisd" if r["in_band"] else "_nocisd")
            buckets[key].append(r["r"])
        confound = {k: {"n": len(v),
                        "exp_r": float(np.mean(v)) if v else None}
                    for k, v in buckets.items() if v}
        choppy_delta = (confound["choppy_cisd"]["exp_r"]
                        - confound["choppy_nocisd"]["exp_r"]) \
            if "choppy_cisd" in confound and "choppy_nocisd" in confound else None
        clean_delta = (confound["clean_cisd"]["exp_r"]
                       - confound["clean_nocisd"]["exp_r"]) \
            if "clean_cisd" in confound and "clean_nocisd" in confound else None
        out["confound"] = {
            "median_efficiency": med,
            "cells": confound,
            "cisd_delta_within_choppy": choppy_delta,
            "cisd_delta_within_clean": clean_delta,
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, args.interval)
    json.dump(out, sys.stdout, indent=2, default=float)
    print()
    return 0 if "error" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
