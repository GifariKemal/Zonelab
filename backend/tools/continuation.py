"""Does price CONTINUE in the direction that made the box?

    python -m tools.continuation

Every directional test in this project so far treated a box as a REVERSAL
object: price arrives, does it turn. Three pre-registered hypotheses, three
nulls. This asks the opposite question, which had never been asked: a fair value
gap is CREATED by a directional move, so does price carry on that way.

THE PRIOR, WRITTEN DOWN BEFORE THE NUMBERS, AND IT IS AGAINST THE HYPOTHESIS
This test was proposed on a premise that turned out to be wrong, and the
correction is recorded here rather than quietly dropped.

The claim was that the peer-reviewed equity gap literature supports continuation.
Checked properly, it does not, in the form needed:

  - Plastun et al. (NAJEF 2020) and Caporale & Plastun (IAJ 2017) study
    OVERNIGHT close-to-open gaps on DAILY bars. 96% of their FX gaps fall on
    Mondays; the object is substantially a weekend artefact. Ours is an intraday
    three-bar imbalance where trading occurred at every price. There is no
    information backlog to absorb, so their mechanism does not transfer.
  - Their continuation effect is SAME-SESSION only, explicitly excludes the gap
    jump itself, is null at 1 to 3 days, and decayed after the 1990s.
  - Caporale & Plastun's FX result is a same-day FADE, not a continuation.
  - Both papers do refute gap FILL, which is the one part that survived.

Against it:

  - The intraday return autocorrelation term structure is NEGATIVE across 5 to
    60 minutes, with its global minimum near 15 minutes (Baule et al. 2025).
    Continuation appears only at sub-minute horizons.
  - The closest measured analogue - "expansion bars", tested for continuation on
    72,604 five-minute MNQ bars - came back significantly the WRONG WAY
    (t = -10.96), with the diagnosis that the burst is consumed inside the bar
    that makes it, so what a next-bar entry captures is post-exhaustion reversal.
  - Osler's round-number continuation is the only clean mechanism in the
    literature. It is worth about 0.7 basis points, it dies within two hours,
    and it works because a round number is a coordination-free focal point. A
    detector-drawn edge is not: it depends on bar interval, threshold and
    wick-versus-body, so two traders draw different boxes and the order cluster
    never forms.

So the prior probability of a tradeable continuation effect is LOW, and that
raises the bar rather than lowering it.

THE CONFOUND, WHICH HAS A NAME
Selecting events on the pre-event return manufactures abnormal returns from
nothing (Ahern, "Sample Selection and Event Study Estimation"), and the induced
bias is largest exactly when the true effect is small - which is the regime here.
A box is created BY a move, so measuring from creation measures the tail of that
move, or worse overlaps it.

Two separations, both applied below:

  DORMANCY   measure from the first touch, and only count touches where price
             had fully left the box and at least `DORMANT` bars had passed. The
             displacement is then entirely outside the measurement window.
  TRAILING   report the same statistic inside buckets of trailing return. An
             effect that lives only in the top trailing bucket is momentum
             rediscovered with extra steps, not the box.

WHAT THIS CANNOT SEPARATE, STATED SO IT IS NOT CLAIMED
For an order block touched from the FAR side, "continuation of the displacement"
and "reversal at the box" predict the SAME sign. On that subsample this test
cannot discriminate from the reversal test already rejected, and it is reported
separately for that reason.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.detect import DETECTORS
from app.indicators import wilder_atr
from app.models import Candle, ImbalanceParams, SupplyDemandParams, ZoneSide
from tools import history
from tools.calibrate import POPULATION

# Fixed before any number existed. 12 bars brackets Osler's roughly two-hour
# decay on a 15-minute chart, and puts the 15-minute point - the most adversarial
# place in the equity autocorrelation term structure - inside the window rather
# than at its edge.
PRIMARY = 12
HORIZONS = (1, 3, 6, 12, 24, 48)
DORMANT = 10  # bars that must pass between creation and the touch that counts

SERIES = [
    ("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "1h"),
]


def events(name: str, candles: list[Candle]) -> list[dict]:
    """One row per dormant first touch, signed by the DISPLACEMENT direction."""
    # Each detector reads its own parameter block. Handing an ImbalanceParams to
    # the supply/demand detector raises on the first field it does not have,
    # which is a loud failure and the right kind - a params object that silently
    # defaulted would have run and produced numbers for the wrong population.
    params = (
        SupplyDemandParams(**POPULATION)
        if name == "supply_demand"
        else ImbalanceParams(max_zones_per_side=0, show_broken=True)
    )
    zones, _ = DETECTORS[name](candles, params)

    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)
    index_of = {c.time: i for i, c in enumerate(candles)}
    n = len(candles)

    out = []
    for zone in zones:
        if zone.first_test_time is None:
            continue
        touch = index_of.get(zone.first_test_time)
        born = zone.anatomy.leg_out_to
        if touch is None or touch - born < DORMANT or touch + max(HORIZONS) >= n:
            continue
        scale = float(atr[touch - 1]) if touch else 0.0
        if scale <= 0:
            continue

        # The direction the MOVE went, which for an order block is the opposite
        # of the block candle's own colour. Using the candle colour would sign
        # half the sample backwards.
        way = 1.0 if zone.side is ZoneSide.DEMAND else -1.0

        # Where price came from over the bars before the touch, in ATR. This is
        # the trailing-momentum control: if the effect lives only where price
        # was already running, it is momentum and not the box.
        back = max(0, touch - PRIMARY)
        trailing = way * (float(close[touch]) - float(close[back])) / scale

        row = {
            "trailing": trailing,
            "near_side": bool(
                (zone.side is ZoneSide.DEMAND and close[touch - 1] > zone.top)
                or (zone.side is ZoneSide.SUPPLY and close[touch - 1] < zone.bottom)
            ),
        }
        for h in HORIZONS:
            row[f"h{h}"] = way * (float(close[touch + h]) - float(close[touch])) / scale
        out.append(row)
    return out


def report(name: str, rows: list[dict], out: dict) -> None:
    if len(rows) < 200:
        print(f"  {name}: only {len(rows)} dormant touches, refusing to report")
        return

    print(f"\n{'=' * 78}")
    print(f"CONTINUATION   {name}   n={len(rows)} dormant first touches")
    print(f"{'=' * 78}")
    print("  Signed by the DISPLACEMENT direction, in ATR. Positive means price")
    print(f"  carried on the way the move went. Primary horizon is {PRIMARY} bars.\n")

    print(f"  {'horizon':<10}{'mean':>10}{'t':>9}{'share > 0':>12}")
    per_h = {}
    for h in HORIZONS:
        values = np.array([r[f"h{h}"] for r in rows])
        # A plain t is optimistic here: events cluster in time and the five
        # series are correlated, so the effective sample is far smaller than n.
        # Printed anyway, and the caveat printed with it.
        t = float(values.mean() / (values.std(ddof=1) / np.sqrt(len(values))))
        mark = "  <- primary" if h == PRIMARY else ""
        print(f"  {h:<10}{values.mean():>10.4f}{t:>9.2f}{(values > 0).mean():>12.1%}{mark}")
        per_h[h] = {"mean": float(values.mean()), "t": t,
                    "share_positive": float((values > 0).mean())}
    out[name] = {"n": len(rows), "horizons": per_h}

    # The trailing-momentum control. Quartiles of where price came from.
    trail = np.array([r["trailing"] for r in rows])
    primary = np.array([r[f"h{PRIMARY}"] for r in rows])
    edges = np.quantile(trail, [0, 0.25, 0.5, 0.75, 1.0])
    print(f"\n  inside buckets of TRAILING move, at h={PRIMARY}")
    print(f"  {'trailing (ATR)':<22}{'n':>6}{'mean':>10}")
    buckets = []
    for i in range(4):
        lo, hi = edges[i], edges[i + 1]
        pick = (trail >= lo) & (trail <= hi if i == 3 else trail < hi)
        if pick.sum() < 50:
            continue
        print(f"  {f'{lo:.2f} to {hi:.2f}':<22}{pick.sum():>6}{primary[pick].mean():>10.4f}")
        buckets.append({"from": float(lo), "to": float(hi), "n": int(pick.sum()),
                        "mean": float(primary[pick].mean())})
    out[name]["trailing_buckets"] = buckets

    near = np.array([r["near_side"] for r in rows])
    print(f"\n  approached from the near side  n={int(near.sum())}")
    print(f"  approached through the box     n={int((~near).sum())}")
    if near.any() and not near.all():
        print(f"\n  near-side touches  n={near.sum():<6} mean {primary[near].mean():>8.4f}")
        print(f"  far-side touches   n={(~near).sum():<6} mean {primary[~near].mean():>8.4f}")
        print(
            "  Only the NEAR-SIDE column discriminates. On a far-side touch,"
            "\n  continuation and reversal predict the same sign, so that column"
            "\n  cannot separate this hypothesis from the one already rejected."
        )
        out[name]["near_side"] = {
            "n_near": int(near.sum()), "mean_near": float(primary[near].mean()),
            "n_far": int((~near).sum()), "mean_far": float(primary[~near].mean()),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print("Loading history (cached after the first run)")
    loaded = [history.load(s, tf, args.bars) for s, tf in SERIES]

    out: dict = {}
    for name in ("fvg", "order_block", "supply_demand"):
        rows: list[dict] = []
        for candles in loaded:
            rows.extend(events(name, candles))
        report(name, rows, out)

    print(
        "\n  Read against the prior, which was written before these numbers and"
        "\n  is AGAINST the hypothesis: intraday autocorrelation is negative"
        "\n  across this whole horizon band, the closest measured analogue came"
        "\n  back the wrong way at t = -10.96, and the only clean continuation"
        "\n  mechanism in the literature is worth 0.7 basis points at round"
        "\n  numbers, which these boxes are not. A small positive here is what"
        "\n  selection on the pre-event return produces on its own."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
