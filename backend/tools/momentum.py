"""H10. The only thing that ever separated direction here, tested properly.

    python -m tools.momentum

Nine hypotheses failed to get a direction out of the drawings. The thing that
kept appearing instead, every time it was used as a CONTROL, was the trailing
move: bars carrying nothing but "price has been going up" separated forward
returns better than any box ever did. H8's control gave +0.164 at t=3.83.

That is time-series momentum, it is established and peer-reviewed, and it needs
no drawing at all. Which makes it the honest candidate for the one component
Zonelab is missing - and also makes it the candidate most likely to be an
artefact, because every one of those control numbers was measured a way this
project has criticised elsewhere.

THE PROBLEM WITH EVERY PREVIOUS READING, INCLUDING MY OWN
They sampled 4000 random bars out of 20000 and gave each a 48-bar forward
window. Those windows overlap enormously, so the observations are nowhere near
independent, the standard error is understated, and t is inflated by a factor
nobody computed. `structure_bias.py` says this out loud about its own numbers
and then still reports them; `alignment.py` used the same overlapping control to
kill H7, which was safe because an inflated control makes a null STRONGER, but
it is not safe when the control is the thing being proposed.

So this tool samples NON-OVERLAPPING windows. Consecutive samples are separated
by lookback + horizon bars, so no bar is ever in two lookbacks or two forward
windows. That costs most of the sample - a few hundred events per series instead
of four thousand - and what is left is honest.

The overlapping figure is printed beside it, clearly labelled, because the size
of the gap between them is itself the finding worth recording.

THE ESTIMAND
    DELTA = mean(forward | trailing up) - mean(forward | trailing down)
Drift enters both cells with the same sign and momentum with opposite signs, so
the difference cancels the drift exactly, with no model of it. Same estimand as
every other directional test here, deliberately, so they are comparable.

FIXED BEFORE ANY NUMBER EXISTED
  - lookbacks 20, 60 and 120 bars. Three values, all reported. No published rule
    gives an intraday momentum lookback and sweeping one would be choosing the
    answer - the same rule the swing width N got;
  - horizons 1, 3, 6, 12, 24, 48, primary 12, the same grid as every other
    directional test here;
  - six instruments, including XAUUSD from Dukascopy, which is the first REAL
    gold this project has had rather than the PAXG proxy;
  - the bar: t >= 3.0 at the primary horizon on the non-overlapping sample, the
    same sign in both halves, and the same sign on at least four of the six
    instruments. Momentum that only exists in aggregate is a portfolio effect,
    not a rule anyone can trade on one chart.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.indicators import wilder_atr
from tools import history

HORIZONS = (1, 3, 6, 12, 24, 48)
PRIMARY = 12
LOOKBACKS = (20, 60, 120)
SERIES = [
    ("XAUUSD", "15m", 5000),
    ("PAXGUSDT", "15m", 20000), ("PAXGUSDT", "1h", 20000),
    ("BTCUSDT", "15m", 20000), ("BTCUSDT", "1h", 20000),
    ("ETHUSDT", "1h", 20000),
]


def events(candles, lookback: int, overlapping: bool) -> list[dict]:
    close = np.array([c.close for c in candles], dtype=np.float64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, 14)

    # Non-overlapping means no bar appears in two lookbacks or two forward
    # windows, so consecutive samples are lookback + horizon apart. It throws
    # away most of the series on purpose: an inflated t is worse than a small n,
    # because a small n is visible and an inflated t is not.
    step = 1 if overlapping else lookback + max(HORIZONS)
    out = []
    for i in range(lookback + 1, len(close) - max(HORIZONS) - 1, step):
        scale = float(atr[i - 1])
        moved = float(close[i] - close[i - lookback])
        if scale <= 0 or moved == 0:
            continue
        row = {"up": moved > 0, "index": i}
        for h in HORIZONS:
            row[f"h{h}"] = (float(close[i + h]) - float(close[i])) / scale
        out.append(row)
    return out


def contrast(rows: list[dict], horizon: int = PRIMARY) -> tuple:
    up = np.array([r[f"h{horizon}"] for r in rows if r["up"]])
    down = np.array([r[f"h{horizon}"] for r in rows if not r["up"]])
    if len(up) < 30 or len(down) < 30:
        return float("nan"), float("nan"), len(up), len(down)
    delta = float(up.mean() - down.mean())
    se = float(np.sqrt(up.var(ddof=1) / len(up) + down.var(ddof=1) / len(down)))
    return delta, delta / se if se > 0 else float("nan"), len(up), len(down)


def line(rows: list[dict], title: str, out: dict) -> float:
    delta, t, nu, nd = contrast(rows)
    if np.isnan(delta):
        print(f"  {title:<34}too few: {nu} up, {nd} down")
        return float("nan")
    print(f"  {title:<34}{delta:>9.4f}{t:>8.2f}{nu:>8}{nd:>8}")
    out[title] = {"delta": delta, "t": t, "n_up": nu, "n_down": nd}
    return delta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    loaded = [(s, tf, history.load(s, tf, n)) for s, tf, n in SERIES]
    out: dict = {}

    for lookback in LOOKBACKS:
        print(f"\n{'=' * 74}")
        print(f"H10  TRAILING {lookback}-BAR MOVE   forward return in ATR, "
              f"horizon {PRIMARY}")
        print(f"{'=' * 74}")
        print(f"  {'':<34}{'DELTA':>9}{'t':>8}{'n up':>8}{'n dn':>8}")

        pooled: list[dict] = []
        signs = []
        for symbol, tf, candles in loaded:
            rows = events(candles, lookback, overlapping=False)
            pooled.extend(rows)
            d = line(rows, f"  {symbol} {tf}", out)
            if not np.isnan(d):
                signs.append(d > 0)

        print()
        line(pooled, f"L{lookback} POOLED, non-overlapping", out)
        mid = np.median([r["index"] for r in pooled])
        line([r for r in pooled if r["index"] <= mid],
             f"L{lookback} first half", out)
        line([r for r in pooled if r["index"] > mid],
             f"L{lookback} second half", out)

        # The same thing measured the way every previous control here measured
        # it. The gap between these two lines is the inflation, and it is the
        # reason this tool exists.
        overlap: list[dict] = []
        for _, _, candles in loaded:
            overlap.extend(events(candles, lookback, overlapping=True))
        line(overlap, f"L{lookback} OVERLAPPING, inflated", out)

        agree = sum(signs)
        print(f"\n  same sign on {agree} of {len(signs)} instruments"
              f"{'  <- meets the bar' if agree >= 4 else '  <- below the bar'}")
        out[f"L{lookback} instruments agreeing"] = agree

    print(
        "\n  The bar, fixed in advance: t >= 3.0 at the primary horizon on the"
        "\n  NON-OVERLAPPING sample, the same sign in both halves, and the same"
        "\n  sign on at least four of six instruments. Momentum that exists only"
        "\n  in the pool is a portfolio effect, not something to trade one chart"
        "\n  on, and this project has no portfolio."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
