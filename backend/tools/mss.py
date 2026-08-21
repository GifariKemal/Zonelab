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

================================================================================
H11. AND DOES DISPLACEMENT RESCUE IT?
Pre-registered 2026-08-17, written before any number in this section existed.

H9 above tested a TWO-part MSS: sweep, then opposite break. That is two thirds of
the definition. ICT's own 2022 mentorship IS retrievable, as SRT transcripts, and
in it he rules the two-part reading out by name:

    "It's not that it goes above this old, relative equal high, and then goes
     down below that - that's not it, folks, that's not it. You have to see it go
     below that in displacement with energetic move, take out a short term low.
     That's how you filter out these trades that may not be high probability."
                                             - Episode 24, 2022-05-06

And he operationalises displacement not as a candle size or an ATR multiple but
as an inefficiency INSIDE THE LEG, as a hard gate:

    "you don't have a trade entry yet, until you determine if it has a fair value
     gap. Where does that reside? Between the displacement high and the
     displacement low ... if there isn't one there, you don't have a trade."
                                             - Episode 6, 2022-02-04

So H9 measured a construct no source describes. That is a real gap in the
argument, and H11 closes it.

WHAT COUNTS AS A DISPLACED MSS
`app.detect.structure.mss_sweeps`, imported rather than restated, because the
drawn MSS and the measured MSS have to be one object: a sweep, an opposite break
inside `window` bars, and a fair value gap in the break's direction somewhere in
the leg between them, from the same `_gap` predicate the FVG detector uses.

THE CELLS, AND WHY ALL FOUR MUST BE READ
A 2x2 on (opposite sweep) x (gap in the leg), because either factor alone could
carry whatever the pair carries:

    sweep + gap     the MSS the sources describe. THE CLAIM.
    sweep, no gap   the pair H9 called an MSS and the sources call a plain CHoCH.
    gap, no sweep   displacement on its own.
    neither         the plain break. THE CONTROL THAT MATTERS, as in H9.

The four partition H9's own pools exactly - "mss" splits into the first two,
"plain" into the last two - so the decomposition is checkable and is asserted
below rather than trusted. The two no-sweep cells have no sweep to anchor a leg
to, so their gap is looked for across the whole `window` before the break, a
WIDER net than the MSS leg gets. That favours the control, deliberately.

FIXED BEFORE ANY NUMBER EXISTED
  - same estimand as H6 and H9, DELTA at the primary horizon, so the three are
    directly comparable;
  - swing widths 2 and 25 and windows 5 and 20, the SAME pins H9 used.
    Displacement adds NO new knob, because ICT gives it no number and every
    impulsiveness number this repo invented is marked as invented;
  - horizons 1, 3, 6, 12, 24, 48, primary 12;
  - the bar: t >= 3.0 on DELTA at the primary horizon for the sweep-and-gap cell,
    the same sign in both halves, and it must beat BOTH controls - the plain break
    it is carved out of, AND the sweep-without-gap cell that displacement is
    supposed to be separating it from. Beating one and not the other is a fail,
    not a partial pass;
  - ON FAILURE I conclude: the three-part conjunction the sources actually
    describe carries no direction either; the two-of-three charge against H9 was
    a FIDELITY defect and not a measurement defect; and the drawn MSS stays a
    fidelity object with no direction claim. I do NOT then go hunting for a
    displacement threshold that works, because that is choosing the answer.

HONEST PRIOR: NULL, and I am not fighting it. H6 and H9 both failed, nine
directional hypotheses in this repo have all failed, and the two most recent
failed in the direction OPPOSITE their own doctrine. Displacement makes the cohort
strictly RARER than H9's, which was already too rare to test at N=25, so the most
likely outcome is not even a null but an inability to measure. Run it because the
conjunction the sources describe has never been asked.

================================================================================
THE PIVOT SENSITIVITY, which is not a hypothesis and changes nothing

H9 reported the conjunction as too rare to test at N=25: 7 and 43 events. That
number is partly about markets and partly about OUR pivot rule. The most-installed
public codification, LuxAlgo's "Smart Money Concepts", uses a ONE-SIDED pivot:

    swings(len)=>
        upper = ta.highest(len)
        lower = ta.lowest(len)
        os := high[len] > upper ? 0 : low[len] < lower ? 1 : os[1]
        top = os == 0 and os[1] != 0 ? high[len] : 0

`high[len] > upper` tests the candidate against the `len` bars to its RIGHT only,
plus a trend-state flip so a top is emitted once per turn. Ours demands dominance
on BOTH sides, so at N=50 it asks for 100 bars of context where LuxAlgo asks for
50. `--pivots` measures what that costs in events.

It does NOT change anything. The symmetric fractal with `confirmed_at = i + right`
is what makes every number in this repo anti-lookahead - and note LuxAlgo's rule
is anti-lookahead too, it also reports the pivot `len` bars late, so this is a
selectivity difference and not a hindsight one. Switching would invalidate every
published number, so the difference is reported as a sensitivity instead, and the
docs can then say whether H9's rarity was our definition or the market.
"""

from __future__ import annotations

import argparse
import json
from bisect import bisect_left

import numpy as np

from app.detect.imbalance import _gap
from app.detect.structure import Swing, breaks, mss_sweeps, swings, walk_breaks
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
    """Split every real break by whether an opposite sweep preceded it.

    The three keys and their membership rules are H9's and are untouched, so its
    published numbers stay reproducible. Each row now also carries the two flags
    H11 needs, which ADD to the rows rather than re-sorting them:

      `displaced`  an opposite sweep in the window whose leg to this break left a
                   fair value gap - the full three-part MSS, from the shared
                   `mss_sweeps` the overlay draws with;
      `gap_only`   a gap in the break's direction anywhere in the `window` before
                   it, used only for the no-sweep control arm, which has no sweep
                   to anchor a leg to and therefore gets the wider net.
    """
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

        # `recent` is already windowed and `mss_sweeps` re-checks the window, so
        # this is one scan rather than two. Passing the full sweep list would be
        # the same answer and quadratic in the series length.
        row["displaced"] = bool(mss_sweeps(high, low, recent, event, window))
        row["leg_atr"] = _leg_atr(high, low, atr, i, window)
        row["gap_only"] = any(
            _gap(high, low, mid) == event.direction
            for mid in range(max(i - window, 1), i)
        )

        if opposite:
            out["mss"].append(row)
        elif same:
            out["same_way"].append(row)
        else:
            out["plain"].append(row)
    return out


def _leg_atr(high, low, atr, i: int, window: int) -> float:
    """Size of the `window` bars before the break, in ATR. DESCRIPTIVE ONLY.

    Reported so the reader can see how big these legs actually are, and never
    used as a cell boundary. ICT publishes no ATR multiple for "energetic", so a
    threshold here would be one this repo invented - and the one it did invent for
    order blocks, 1.5 ATR over 5 bars, is labelled invented in docs/FIDELITY.md.
    """
    lo = max(i - window, 0)
    scale = float(atr[i - 1])
    return (float(high[lo : i + 1].max()) - float(low[lo : i + 1].min())) / scale


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


def lux_swings(high: np.ndarray, low: np.ndarray, length: int) -> list[Swing]:
    """LuxAlgo's ONE-SIDED pivot, reimplemented from its published Pine source.

    Line for line with the `swings(len)` function quoted in the module docstring.
    `upper` is the highest high of the `length` bars to the RIGHT of the
    candidate, and the candidate only has to beat those - there is no left-side
    test at all. `os` is a trend state, so a top is emitted once per turn rather
    than on every bar that passes.

    Reimplemented rather than approximated because the whole point of the
    comparison is that ONLY the pivot rule differs; the break loop it feeds is
    `walk_breaks`, the same one `breaks` runs.

    `confirmed_at` is `i`, the bar the state flipped, which is `length` bars after
    the pivot itself. So LuxAlgo is anti-lookahead here too and the difference
    measured below is selectivity, not hindsight.
    """
    out: list[Swing] = []
    state = 0
    for i in range(length, len(high)):
        c = i - length
        before = state
        if high[c] > high[c + 1 : i + 1].max():
            state = 0
        elif low[c] < low[c + 1 : i + 1].min():
            state = 1
        if state == 0 and before != 0:
            out.append(Swing(c, float(high[c]), True, i))
        elif state == 1 and before != 1:
            out.append(Swing(c, float(low[c]), False, i))
    return sorted(out, key=lambda s: (s.confirmed_at, s.index))


def pivot_census(candles, length: int, window: int) -> dict[str, int]:
    """Swings, breaks, sweeps and MSS conjunctions under both pivot rules.

    Both arms run the same `walk_breaks` and the same `mss_sweeps`, so the only
    variable between them is which bars count as pivots.
    """
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    times = [c.time for c in candles]

    got: dict[str, int] = {}
    arms = (
        ("ours", swings(high, low, length, length)),
        ("lux", lux_swings(high, low, length)),
    )
    for name, found in arms:
        events = walk_breaks(high, low, close, times, found)
        sweeps = [e for e in events if e.kind == "SWEEP"]
        real = [e for e in events if e.kind != "SWEEP"]
        got[f"{name}.swings"] = len(found)
        got[f"{name}.breaks"] = len(real)
        got[f"{name}.sweeps"] = len(sweeps)

        # `walk_breaks` emits in bar order, so sweep indices ascend and the window
        # can be bisected out. Scanning every sweep for every break instead is
        # ~78M comparisons per series here, which is the difference between this
        # running and not.
        at = [s.index for s in sweeps]
        pair = mss = 0
        for e in real:
            recent = sweeps[bisect_left(at, e.index - window):bisect_left(at, e.index)]
            if any(s.direction == -e.direction for s in recent):
                pair += 1
            if mss_sweeps(high, low, recent, e, window):
                mss += 1
        # H9's two-part pairing and H11's three-part one, side by side, because
        # the rarity being explained was H9's.
        got[f"{name}.pair"] = pair
        got[f"{name}.mss"] = mss
    return got


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


def h11(pool: dict[str, list], label: str, out: dict) -> None:
    """The three-way conjunction, as a 2x2 on (opposite sweep) x (gap in the leg).

    The split is a partition of H9's own pools and that is asserted, not assumed:
    if it ever stopped holding, the two hypotheses would be about different
    populations and neither number would mean what it says.
    """
    cells = {
        "sweep+gap MSS": [r for r in pool["mss"] if r["displaced"]],
        "sweep, no gap": [r for r in pool["mss"] if not r["displaced"]],
        "gap only, no sweep": [r for r in pool["plain"] if r["gap_only"]],
        "plain break": [r for r in pool["plain"] if not r["gap_only"]],
    }
    assert sum(len(v) for v in cells.values()) == len(pool["mss"]) + len(pool["plain"])

    print(f"\n{'-' * 84}")
    print(f"H11  SWEEP x DISPLACEMENT x BREAK   {label}   forward return in ATR")
    print(f"{'-' * 84}")
    print("  sweep+gap MSS is the claim. sweep-no-gap is what the sources call a")
    print("  plain CHoCH. plain break is H9's control. All four must be read.")
    print(f"  {'':<34}{'after up':>9}{'after dn':>10}{'DELTA':>9}"
          f"{'t':>7}{'n up':>7}{'n dn':>7}")
    for title, rows in cells.items():
        report(rows, f"{label} {title}", out)
        if rows:
            legs = float(np.mean([r["leg_atr"] for r in rows]))
            out[f"{label} {title}"] = out.get(f"{label} {title}", {}) | {
                "n": len(rows), "leg_atr_mean": legs,
            }

    claim = cells["sweep+gap MSS"]
    if len(claim) > 160:
        mid = np.median([r["index"] for r in claim])
        report([r for r in claim if r["index"] <= mid],
               f"{label} sweep+gap 1st half", out)
        report([r for r in claim if r["index"] > mid],
               f"{label} sweep+gap 2nd half", out)

    # The two controls the pre-registered bar names, both of them.
    dc, vc, _, _ = contrast(claim)
    for name, rows in (("the same pair with NO gap", cells["sweep, no gap"]),
                       ("a plain break", cells["plain break"])):
        do, vo, _, _ = contrast(rows)
        if np.isnan(dc) or np.isnan(do):
            print(f"    vs {name}: not measurable, {len(claim)} against {len(rows)}")
            continue
        adds = dc - do
        se = float(np.sqrt(vc + vo))
        t = adds / se if se > 0 else float("nan")
        print(f"    DISPLACEMENT ADDS over {name}: {adds:+.4f}   t={t:.2f}")
        out[f"{label} H11 vs {name}"] = {"adds": adds, "t": t}
    print("    mean leg size over the window, ATR, descriptive only: "
          + ", ".join(
              f"{k.split(',')[0]} {np.mean([r['leg_atr'] for r in v]):.2f}"
              for k, v in cells.items() if v
          ))


def pivots(loaded: list, out: dict) -> None:
    """What a one-sided pivot would do to the counts. A sensitivity, not a switch.

    Read the module docstring: nothing here changes the repo's pivot. The number
    that matters is `pair`, because H9's headline caveat was that the two-part
    conjunction happened only 7 and 43 times at N=25, and this says how much of
    that was the fractal rule rather than the market.
    """
    print(f"\n{'=' * 84}")
    print("PIVOT SENSITIVITY   symmetric fractal (ours) against LuxAlgo one-sided")
    print(f"{'=' * 84}")
    print("  Pooled over all five series. `pair` is H9's two-part conjunction,")
    print("  `mss` is H11's three-part one. Same break loop, same MSS predicate.")
    print(f"  {'N':>4}{'win':>5}{'swings':>17}{'breaks':>15}{'sweeps':>15}"
          f"{'pair':>13}{'mss':>13}")
    for length in (2, 5, 25, 50):
        for window in (5, 20):
            total: dict[str, int] = {}
            for candles in loaded:
                for key, value in pivot_census(candles, length, window).items():
                    total[key] = total.get(key, 0) + value
            out[f"pivots N={length} window={window}"] = total

            def pair(field: str) -> str:
                ours, lux = total[f"ours.{field}"], total[f"lux.{field}"]
                ratio = ours / lux if lux else float("inf")
                return f"{ours:>7}/{lux:<6}{ratio:>4.1f}x"

            print(f"  {length:>4}{window:>5}  {pair('swings')} {pair('breaks')} "
                  f"{pair('sweeps')} {pair('pair')} {pair('mss')}")
    print("\n  Left of the slash is ours, right is LuxAlgo's, then the ratio.")
    print("  Reported so the docs can say whether H9's rarity was the definition")
    print("  or the market. NOT adopted: our `confirmed_at = i + right` is what")
    print("  makes every published number here anti-lookahead.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    parser.add_argument("--pivots", action="store_true",
                        help="also run the one-sided-pivot count sensitivity")
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

            h11(pool, label, out)

    print(
        "\n  The bar, fixed in advance: t >= 3.0 on DELTA at the primary horizon,"
        "\n  the same sign in both halves, and MSS must beat the plain break it is"
        "\n  carved out of. Four cells are reported and all four must be read -"
        "\n  picking the best of them after the fact is how a null becomes a claim."
        "\n  H11 adds one more control it must also beat: the same sweep-then-break"
        "\n  pair WITHOUT a gap in the leg, which is what displacement separates."
    )

    if args.pivots:
        pivots(loaded, out)

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
