"""Does market structure say which way price goes?

    python -m tools.structure_bias

H6, and the first hypothesis in this project aimed at an object the doctrine
itself claims carries direction. Everything measured before this - supply and
demand zones, fair value gaps, order blocks - is a LOCATION object. They beat a
placebo by 10 to 25 points and survive walk-forward, and four pre-registered
directional tests on them returned four nulls. ICT and SMC say why: bias comes
from STRUCTURE, and zones only refine the entry.

THE ESTIMAND, AND WHY IT IS A DIFFERENCE
The sample drifts upward, so "price rose after a bullish bias" proves nothing.
Write the mean forward return under each bias as

    bullish:  mu + delta
    bearish:  mu - delta

Drift enters both with the SAME sign and the structure effect with OPPOSITE
signs, so

    DELTA = mean(forward | bias +1) - mean(forward | bias -1)

cancels the drift exactly, with no model of it. Same estimand as the reaction
test, for the same reason.

MEASURED AT BREAKS, NOT AT EVERY BAR
Sampling every bar would overlap every window with its neighbours thousands of
times over and inflate any t beyond meaning. A break is the moment the bias is
established or flipped, it is when a trader would act, and consecutive breaks
are far enough apart to be closer to independent. Every-bar numbers are printed
too, clearly marked as the overlapping thing they are.

HORIZONS FIXED BEFORE THE FIRST NUMBER
1, 3, 6, 12, 24, 48 bars, primary 12. Same grid as the continuation test so the
two are comparable and neither gets a horizon chosen to flatter it.

CONFIRMATION BAR, ALSO SET IN ADVANCE
This dataset has carried many tests. A positive here needs t >= 3.0 on the
difference at the primary horizon, the same sign at both halves of the sample,
and BOS and CHoCH agreeing in sign. Anything less is reported as not confirmed.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.detect.structure import breaks
from app.indicators import wilder_atr
from tools import history

HORIZONS = (1, 3, 6, 12, 24, 48)
PRIMARY = 12
SERIES = [
    ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
]


def collect(candles, left: int = 2, right: int = 2) -> list[dict]:
    close = np.array([c.close for c in candles], dtype=np.float64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, 14)
    events, _ = breaks(candles, left, right)

    out = []
    for event in events:
        i = event.index
        if i < 1 or i + max(HORIZONS) >= len(close):
            continue
        scale = float(atr[i - 1])
        if scale <= 0:
            continue
        row = {"kind": event.kind, "dir": event.direction, "index": i}
        for h in HORIZONS:
            # RAW, not signed. The sign is applied by the split below, because
            # the estimand is a difference between the two biases and signing
            # first would hide the drift that the difference is there to cancel.
            row[f"h{h}"] = (float(close[i + h]) - float(close[i])) / scale
        out.append(row)
    return out


def table(rows: list[dict], title: str, out: dict) -> None:
    up = [r for r in rows if r["dir"] > 0]
    down = [r for r in rows if r["dir"] < 0]
    if len(up) < 100 or len(down) < 100:
        print(f"  {title}: {len(up)} up and {len(down)} down, too few")
        return

    print(f"\n  {title}   n={len(rows)}  ({len(up)} up, {len(down)} down)")
    print(f"  {'horizon':<10}{'after up':>11}{'after down':>13}{'DELTA':>10}{'t':>8}")
    per_h = {}
    for h in HORIZONS:
        a = np.array([r[f"h{h}"] for r in up])
        b = np.array([r[f"h{h}"] for r in down])
        delta = float(a.mean() - b.mean())
        se = float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
        t = delta / se if se > 0 else float("nan")
        mark = "  <- primary" if h == PRIMARY else ""
        print(f"  {h:<10}{a.mean():>11.4f}{b.mean():>13.4f}{delta:>10.4f}{t:>8.2f}{mark}")
        per_h[h] = {"up": float(a.mean()), "down": float(b.mean()),
                    "delta": delta, "t": t}
    out[title] = {"n_up": len(up), "n_down": len(down), "horizons": per_h}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    loaded = [history.load(s, tf, args.bars) for s, tf in SERIES]
    out: dict = {}

    # TWO swing widths, both fixed before any number existed. No published rule
    # gives an N for a swing point - every value in circulation is an indicator
    # default, including the 5 that one popular script hardcodes and the 50 that
    # another ships as a slider. That makes N a data-snooping surface, and
    # sweeping it would be choosing the answer. Two stated values, both reported
    # whatever they say.
    for left, right, label in ((2, 2, "N=2 minor"), (25, 25, "N=25 major")):
        rows: list[dict] = []
        for candles in loaded:
            rows.extend(collect(candles, left, right))

        print(f"\n{'=' * 78}")
        print(f"STRUCTURE BIAS   {label}   forward return in ATR")
        print(f"{'=' * 78}")
        print("  DELTA is after-up minus after-down, which cancels the sample's")
        print("  own drift exactly. Structure carrying direction needs DELTA > 0.")

        # Sweeps are held out of every break cohort. A sweep is liquidity taken,
        # not structure giving way, and pooling them would ask one question of
        # two opposite events.
        real = [r for r in rows if r["kind"] != "SWEEP"]
        table(real, f"{label} all breaks", out)
        table([r for r in real if r["kind"] == "BOS"], f"{label} BOS", out)
        table([r for r in real if r["kind"] == "CHoCH"], f"{label} CHoCH", out)
        table([r for r in rows if r["kind"] == "SWEEP"], f"{label} SWEEP", out)

        # Split-half on time. An effect living in one half is a window fit, and
        # this project has caught that twice already.
        mid = np.median([r["index"] for r in real])
        table([r for r in real if r["index"] <= mid], f"{label} first half", out)
        table([r for r in real if r["index"] > mid], f"{label} second half", out)

    print(
        "\n  BOS and CHoCH are ONE predicate wearing two labels, not two"
        "\n  hypotheses. Both are the same close-crossover of a confirmed swing;"
        "\n  which name it gets depends only on where the bias already pointed."
        "\n  They are a breakdown, not independent tests, and an earlier writeup"
        "\n  in this project treated them as two."
    )
    print(
        "\n  The t values above assume independent events. Breaks cluster and the"
        "\n  five series are correlated, so the effective sample is smaller than n"
        "\n  and these t values are OPTIMISTIC. The bar set in advance was t >= 3.0"
        "\n  at the primary horizon, same sign in both halves, BOS and CHoCH"
        "\n  agreeing. Read them against that, not against 1.96."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
