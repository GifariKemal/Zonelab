"""H9. Does a break carry direction when a liquidity sweep came first?

    python -m tools.mss

This exists because H6 contained a logical gap of my own making. It tested BOS,
CHoCH and SWEEP as three separate cohorts, found nothing that survived, and the
writeup concluded that market structure does not carry direction. But the thing
ICT actually claims is directional is none of those three on its own - it is
their CONJUNCTION, the Market Structure Shift: liquidity is taken first, and
THEN price closes beyond the opposite structure.

Testing the parts and declaring the whole dead is not a valid inference. Every
source that describes an MSS distinguishes it from a plain CHoCH by exactly one
requirement, the preceding sweep, and that requirement has never been tested
here.

WHAT COUNTS AS AN MSS
A SWEEP event at bar j - a wick beyond a confirmed swing whose close did not
follow - and then a real break, in the OPPOSITE direction to that sweep, within
`window` bars. Opposite is the whole point: liquidity is taken above, then price
goes down. A sweep above followed by a break upward is just a delayed
continuation and is counted separately as a sanity check, not as an MSS.

THE CONTROL THAT MATTERS IS NOT RANDOM BARS
It is the plain break with NO sweep in front of it. That isolates precisely what
the sweep adds, which is the only thing this hypothesis claims. Random bars
carrying the trailing move are reported too, because H7 died to exactly that
control and it is now standing procedure here, but the break-without-sweep
cohort is the sharper one.

THE ESTIMAND
    DELTA = mean(forward | broke up) - mean(forward | broke down)

Drift enters both cells with the same sign and the structure effect with
opposite signs, so the difference cancels the drift exactly. Same estimand as
H6, deliberately, so the two are directly comparable.

FIXED BEFORE ANY NUMBER EXISTED
  - swing widths 2 and 25, both reported. No published rule gives an N and
    sweeping it would be choosing the answer - the same rule H6 used;
  - sweep-to-break windows 5 and 20, both reported, for the same reason. This
    is a NEW data-snooping surface and it is being pinned, not explored;
  - horizons 1, 3, 6, 12, 24, 48, primary 12;
  - the bar: t >= 3.0 on DELTA at the primary horizon, the same sign in both
    halves, and MSS must beat the plain break it is carved out of.

HONEST PRIOR: LOW, and lower than H8's. H6's sweep cohort alone gave t=1.89 at
N=25 and its all-breaks cohort collapsed thirteenfold between halves. The
conjunction will have a far smaller n than either. Expect a null; run it because
the conjunction has never been asked and the parts do not answer for the whole.
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
TRAIL = 20
SERIES = [
    ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
]


def collect(candles, left: int, right: int, window: int) -> dict[str, list]:
    """Split every real break by whether an opposite sweep preceded it."""
    close = np.array([c.close for c in candles], dtype=np.float64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, 14)
    events, _ = breaks(candles, left, right)

    sweeps = [e for e in events if e.kind == "SWEEP"]
    real = [e for e in events if e.kind != "SWEEP"]

    out: dict[str, list] = {"mss": [], "plain": [], "same_way": []}
    for event in real:
        i = event.index
        if i < 1 or i + max(HORIZONS) >= len(close):
            continue
        scale = float(atr[i - 1])
        if scale <= 0:
            continue

        # Any sweep in the window, and which way it took liquidity. Opposite
        # means the MSS reading: liquidity taken above, then price breaks down.
        recent = [s for s in sweeps if i - window <= s.index < i]
        opposite = any(s.direction == -event.direction for s in recent)
        same = any(s.direction == event.direction for s in recent)

        row = {"dir": event.direction, "index": i, "kind": event.kind}
        for h in HORIZONS:
            row[f"h{h}"] = (float(close[i + h]) - float(close[i])) / scale

        if opposite:
            out["mss"].append(row)
        elif same:
            out["same_way"].append(row)
        else:
            out["plain"].append(row)
    return out


def control(candles, rng) -> list[dict]:
    """Random bars carrying only the trailing move, given a fake direction.

    Standing procedure since H7: any construct conditioned on where price has
    just been will re-find momentum unless momentum is measured beside it.
    """
    close = np.array([c.close for c in candles], dtype=np.float64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, 14)

    out = []
    for i in rng.integers(TRAIL + 1, len(close) - max(HORIZONS) - 1, 4000):
        i = int(i)
        scale = float(atr[i - 1])
        moved = close[i] - close[i - TRAIL]
        if scale <= 0 or moved == 0:
            continue
        row = {"dir": 1 if moved > 0 else -1, "index": i, "kind": "control"}
        for h in HORIZONS:
            row[f"h{h}"] = (float(close[i + h]) - float(close[i])) / scale
        out.append(row)
    return out


def contrast(rows: list[dict]) -> tuple[float, float, int, int]:
    up = np.array([r[f"h{PRIMARY}"] for r in rows if r["dir"] > 0])
    down = np.array([r[f"h{PRIMARY}"] for r in rows if r["dir"] < 0])
    if len(up) < 40 or len(down) < 40:
        return float("nan"), float("nan"), len(up), len(down)
    return (
        float(up.mean() - down.mean()),
        float(up.var(ddof=1) / len(up) + down.var(ddof=1) / len(down)),
        len(up), len(down),
    )


def report(rows: list[dict], title: str, out: dict) -> None:
    delta, var, nu, nd = contrast(rows)
    if np.isnan(delta):
        print(f"  {title:<34}too few, {nu} up and {nd} down")
        return
    up = np.mean([r[f"h{PRIMARY}"] for r in rows if r["dir"] > 0])
    down = np.mean([r[f"h{PRIMARY}"] for r in rows if r["dir"] < 0])
    t = delta / np.sqrt(var) if var > 0 else float("nan")
    print(f"  {title:<34}{up:>9.4f}{down:>10.4f}{delta:>9.4f}{t:>7.2f}"
          f"{nu:>7}{nd:>7}")
    out[title] = {"up": float(up), "down": float(down), "delta": delta,
                  "t": float(t), "n_up": nu, "n_down": nd}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    loaded = [history.load(s, tf, args.bars) for s, tf in SERIES]
    out: dict = {}

    rng = np.random.default_rng(20260816)
    ctrl: list[dict] = []
    for candles in loaded:
        ctrl.extend(control(candles, rng))

    for left, right in ((2, 2), (25, 25)):
        for window in (5, 20):
            label = f"N={left} window={window}"
            print(f"\n{'=' * 84}")
            print(f"H9  SWEEP THEN MSS   {label}   forward return in ATR")
            print(f"{'=' * 84}")
            print("  DELTA is after-up minus after-down, which cancels drift.")
            print(f"  {'':<34}{'after up':>9}{'after dn':>10}{'DELTA':>9}"
                  f"{'t':>7}{'n up':>7}{'n dn':>7}")

            pool: dict[str, list] = {"mss": [], "plain": [], "same_way": []}
            for candles in loaded:
                got = collect(candles, left, right, window)
                for key in pool:
                    pool[key].extend(got[key])

            report(ctrl, "TRAILING MOVE ONLY, no break", out)
            report(pool["mss"], f"{label} MSS, sweep then opposite break", out)
            report(pool["plain"], f"{label} plain break, no sweep", out)
            report(pool["same_way"], f"{label} sweep then SAME-way break", out)

            if len(pool["mss"]) > 160:
                mid = np.median([r["index"] for r in pool["mss"]])
                report([r for r in pool["mss"] if r["index"] <= mid],
                       f"{label} MSS first half", out)
                report([r for r in pool["mss"] if r["index"] > mid],
                       f"{label} MSS second half", out)

            # What the SWEEP adds to a break that would have happened anyway.
            # This is the line H9 turns on: MSS is carved out of the plain
            # break population, so beating it is the whole claim.
            dm, vm, _, _ = contrast(pool["mss"])
            dp, vp, _, _ = contrast(pool["plain"])
            if not np.isnan(dm) and not np.isnan(dp):
                adds = dm - dp
                se = float(np.sqrt(vm + vp))
                print(f"    SWEEP ADDS over a plain break: {adds:+.4f}   "
                      f"t={adds / se if se > 0 else float('nan'):.2f}")
                out[f"{label} DiD"] = {"adds": adds,
                                       "t": adds / se if se > 0 else None}

    print(
        "\n  The bar, fixed in advance: t >= 3.0 on DELTA at the primary horizon,"
        "\n  the same sign in both halves, and MSS must beat the plain break it is"
        "\n  carved out of. Four cells are reported and all four must be read -"
        "\n  picking the best of them after the fact is how a null becomes a claim."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
