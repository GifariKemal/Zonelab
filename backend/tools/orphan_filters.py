"""tCISD, Z-Score and regime: the three claims that only lived in a transcript.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.orphan_filters > ../docs/orphan_filters.json

WHY THIS EXISTS. `docs/PRAREGISTRASI-YATIM.md` section 5 excludes `app/tcisd.py`,
`app/zscore.py` and `app/regime.py` from its measured list on the grounds that
they were "already answered", and cites three numbers:

    tCISD as a standalone entry   -0,926 R, 0 of 11 positive   24 Aug transcript
    tCISD as a filter             -0,087 R, identical baseline  24 Aug transcript
    Z-Score + volume + regime     -0,0893 to -0,1301 R over 24 cells, sign test
                                  p=0,405, zero cells clear of zero   28 Aug

Every other line in that document points at a tool and a JSON. These three point
at a chat log. Nobody can re-run them, nobody can tell whether the code they were
computed from still behaves that way, and the register nevertheless uses them to
justify leaving three modules unmeasured. This file closes that.

IT IS NOT A NEW PRE-REGISTRATION. The hypotheses were stated and answered
elsewhere; this reproduces them from committed code and writes the evidence file
that should have existed. A number that comes back DIFFERENT is the finding.

## The three arms, each a configuration of `tools.quant.cell`

  baseline   zone trades, no filter                    cell(...)
  tcisd      zone trades filtered by tCISD direction   cell(..., tcistd=True)
  quant      zone trades filtered by Z-Score, volume
             and regime                                cell(..., quant=True)

Nothing here reimplements a filter. `cell`, `tcisd_trades` and `quant_filter` are
the shipped paths, called as they ship, so what this measures is what the engine
would do.

## One thing to expect before reading the numbers

`tools/quant.py:tcisd_trades` carries a comment saying its zero-confirmation
branch USED TO return every trade, "which made the whole --tcistd mode measure
the baseline while labelling it tCISD". The transcript's second row - tCISD as a
filter, -0,087 R, IDENTICAL TO BASELINE - is exactly the signature that bug
produces. Written here before the run so that reading it in the output afterwards
is a confirmation and not a story fitted to a number.

## What is reported

Per cell: n, expectancy in R, the walk-forward folds and the sign test that
`cell` already computes, and for the two filter arms the delta against the
baseline of the same cell. Pooled across cells: how many arms beat their own
baseline, and the sign test over the per-cell deltas.

No new pass threshold is invented. These modules stay unwired either way; the
question this file answers is whether the numbers in the register are the
numbers the code produces.

ONE SOURCE OF DRIFT INSIDE A SINGLE RUN, and it is small but real. The three
arms of a cell are fetched minutes apart from a live MT5 tail, so a bar can
arrive between the baseline call and the tCISD call. Measured on the 1 September
run: 11 of 12 pass-through cells came back byte-identical and USDCAD 1h differed
by 0,0002 R on the same trade count, which is that drift and not a filter. The
`identical_to_baseline` flag reports it as not-identical, correctly and
uselessly, so read the flag alongside the trade count rather than alone.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

from tools.quant import UNIVERSE, cell

ARMS = ("baseline", "tcisd", "quant")

#: What section 5 of the register claims, carried in the output so the
#: comparison is in the file rather than in a reader's memory.
CLAIMED = {
    "tcisd": {"exp_r": -0.926, "note": "standalone entry, 0 of 11 positive"},
    "tcisd_as_filter": {"exp_r": -0.087, "note": "identical to baseline"},
    "quant": {"exp_r_range": [-0.1301, -0.0893],
              "note": "24 cells, sign test p=0,405, zero cells clear of zero"},
}


def arm(symbol: str, interval: str, which: str, bars: int) -> dict:
    got = cell(symbol, interval, bars=bars,
               tcistd=(which == "tcisd"), quant=(which == "quant"))
    return {
        k: got.get(k)
        for k in ("n", "touched", "exp_r", "win_rate", "profit_factor",
                  "folds_positive", "folds_counted", "sign_p", "note")
        if got.get(k) is not None
    }


def study(symbols: list[str], intervals: list[str], bars: int) -> dict:
    cells: dict[str, dict] = {}
    for symbol in symbols:
        for interval in intervals:
            key = f"{symbol}|{interval}"
            block: dict = {}
            for which in ARMS:
                try:
                    block[which] = arm(symbol, interval, which, bars)
                except Exception as exc:  # noqa: BLE001
                    block[which] = {"error": f"{type(exc).__name__}: {exc}"}
            base = block["baseline"].get("exp_r")
            for which in ("tcisd", "quant"):
                got = block[which].get("exp_r")
                if base is not None and got is not None:
                    block[which]["delta_vs_baseline"] = round(got - base, 6)
                    # THE BUG SIGNATURE, checked rather than eyeballed: a filter
                    # that changed nothing kept every trade and every R.
                    block[which]["identical_to_baseline"] = (
                        block[which].get("n") == block["baseline"].get("n")
                        and abs(got - base) < 1e-9
                    )
            cells[key] = block

    out: dict = {
        "reproduced": "tools/orphan_filters.py, 2026-09-01",
        "replaces": "docs/PRAREGISTRASI-YATIM.md section 5, transcript-only",
        "claimed_in_register": CLAIMED,
        "bars": bars,
        "cells": cells,
        "pooled": {},
    }
    for which in ("tcisd", "quant"):
        deltas = [
            c[which]["delta_vs_baseline"]
            for c in cells.values()
            if isinstance(c.get(which), dict) and "delta_vs_baseline" in c[which]
        ]
        rs = [
            c[which]["exp_r"]
            for c in cells.values()
            if isinstance(c.get(which), dict) and c[which].get("exp_r") is not None
        ]
        identical = [
            k for k, c in cells.items()
            if isinstance(c.get(which), dict) and c[which].get("identical_to_baseline")
        ]
        out["pooled"][which] = {
            "cells_measured": len(rs),
            "exp_r_min": min(rs) if rs else None,
            "exp_r_max": max(rs) if rs else None,
            "exp_r_mean": round(sum(rs) / len(rs), 6) if rs else None,
            "cells_positive": sum(1 for r in rs if r > 0),
            "beats_own_baseline": sum(1 for d in deltas if d > 0),
            "deltas_counted": len(deltas),
            "cells_identical_to_baseline": identical,
        }
    base_rs = [
        c["baseline"]["exp_r"] for c in cells.values()
        if isinstance(c.get("baseline"), dict)
        and c["baseline"].get("exp_r") is not None
    ]
    out["pooled"]["baseline"] = {
        "cells_measured": len(base_rs),
        "exp_r_mean": round(sum(base_rs) / len(base_rs), 6) if base_rs else None,
        "cells_positive": sum(1 for r in base_rs if r > 0),
    }
    return out


def selfcheck() -> int:
    """The one piece of arithmetic this file owns: the identical-to-baseline flag.

    Everything else is `tools.quant.cell` called as it ships. This flag is the
    only new judgement, and it is the one that decides whether a transcript
    number was a measurement or a bug, so it gets a gate.
    """
    same = {"baseline": {"n": 40, "exp_r": -0.087},
            "tcisd": {"n": 40, "exp_r": -0.087}}
    fewer = {"baseline": {"n": 40, "exp_r": -0.087},
             "tcisd": {"n": 12, "exp_r": -0.087}}
    drifted = {"baseline": {"n": 40, "exp_r": -0.087},
               "tcisd": {"n": 40, "exp_r": -0.086}}

    def flag(block: dict) -> bool:
        base = block["baseline"]["exp_r"]
        got = block["tcisd"]["exp_r"]
        return block["tcisd"]["n"] == block["baseline"]["n"] and abs(got - base) < 1e-9

    assert flag(same) is True, "same n and same R is the bug signature"
    assert flag(fewer) is False, "a filter that removed trades is not identical"
    assert flag(drifted) is False, "a different R is not identical"
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(UNIVERSE))
    parser.add_argument("--intervals", default="1h,4h")
    parser.add_argument("--bars", type=int, default=20_000)
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()
    if args.selfcheck:
        return selfcheck()
    selfcheck()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    intervals = [i.strip() for i in args.intervals.split(",") if i.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, intervals, args.bars)
    json.dump(out, sys.stdout, indent=2, default=float)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
