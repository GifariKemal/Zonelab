"""Does a conditioning column that cleared the bar hold on folds it never saw?

    python -m tools.qtaz_walkforward --symbol mt5:BTCUSD --interval 1h --bars 50000

`tools/conditioned.py` judges a column on the WHOLE sample at once. That is the
right first question and it is in-sample in the way that matters: the row that
looks interesting was picked after looking at those bars. `docs/PRAREGISTRASI-QT-AZ.md`
therefore requires a second gate before any row is called anything - eight
chronological folds, and at least six agreeing on the sign.

WHY IT IS A SEPARATE FILE FROM `tools/walkforward.py`. That one walks the
DEPARTURE GATE: it re-chooses a threshold per fold and asks whether the chosen
threshold survives. There is no threshold to re-choose here. A conditioning
column is a label the bar already carries, so the only question is whether the
separation it names is stable in time, and answering the wrong question with
the wrong tool would be worse than having no second gate at all.

WHAT IT DOES NOT DO. It does not choose which column to walk - the caller
names it, and `docs/PRAREGISTRASI-QT-AZ.md` names which rows earned one. A tool
that searched for the best column and then walked it would be the search this
whole pre-registration exists to prevent.
"""

from __future__ import annotations

import argparse
from math import sqrt

import numpy as np

from tools.conditioned import MIN_GROUP, rows_with_state

#: Folds are chronological and equal in COUNT, not in calendar time. Equal
#: calendar spans put wildly different numbers of touches in each fold on a
#: feed with weekends and holidays, and a fold holding nine events votes as
#: loudly as one holding two hundred.
FOLDS = 8


def _delta(group: np.ndarray, rest: np.ndarray) -> tuple[float, float]:
    """Welch delta and t of one arm against its complement.

    The SAME comparison `conditioned.py` makes, and deliberately so: a fold
    that answered a different question than the whole-sample row would not be
    a check on that row.
    """
    if len(group) < 2 or len(rest) < 2:
        return 0.0, 0.0
    se = sqrt(group.var(ddof=1) / len(group) + rest.var(ddof=1) / len(rest))
    delta = float(group.mean() - rest.mean())
    return delta, (delta / se if se > 0 else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="mt5:BTCUSD")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--bars", type=int, default=50000)
    ap.add_argument(
        "--column",
        default="tpd_outside",
        help="the state column to walk, named by the pre-registration",
    )
    ap.add_argument(
        "--value",
        default="inside",
        help="the arm of that column that cleared the whole-sample bar",
    )
    ap.add_argument(
        "--against",
        default=None,
        help=(
            "an EXISTING column to stratify by, to ask whether the new column "
            "adds anything over it or is the same reading relabelled"
        ),
    )
    ap.add_argument("--hold", action="store_true")
    args = ap.parse_args()

    rows = rows_with_state(args.symbol, args.interval, args.bars, not args.hold)
    rows.sort(key=lambda r: int(r["at"]))
    print(f"{args.symbol} {args.interval} {args.bars} bar, n={len(rows)}")
    print(f"walking {args.column} == {args.value!r} over {FOLDS} folds\n")

    whole = np.array([r["r"] for r in rows])
    arm = np.array([r["r"] for r in rows if r["state"].get(args.column) == args.value])
    other = np.array(
        [r["r"] for r in rows if r["state"].get(args.column) != args.value]
    )
    d_all, t_all = _delta(arm, other)
    print(
        f"whole sample: n={len(arm)} of {len(whole)}  "
        f"exp R {arm.mean():+.3f}  delta {d_all:+.3f}  t {t_all:+.2f}\n"
    )

    edges = np.linspace(0, len(rows), FOLDS + 1).astype(int)
    agree = 0
    usable = 0
    for i in range(FOLDS):
        chunk = rows[edges[i]:edges[i + 1]]
        a = np.array([r["r"] for r in chunk if r["state"].get(args.column) == args.value])
        b = np.array([r["r"] for r in chunk if r["state"].get(args.column) != args.value])
        if len(a) < MIN_GROUP or len(b) < MIN_GROUP:
            print(f"  fold {i + 1}: n={len(a)}/{len(b)}  too small to judge")
            continue
        usable += 1
        d, t = _delta(a, b)
        same = (d > 0) == (d_all > 0)
        agree += same
        print(
            f"  fold {i + 1}: n={len(a):4d}/{len(b):4d}  "
            f"delta {d:+.3f}  t {t:+.2f}  {'agrees' if same else 'DISAGREES'}"
        )

    # ---------------------------------------------------- the overlap check
    # A COLUMN THAT SEPARATES IS NOT YET A NEW READING. If an existing column
    # separates the same bars in the same direction, the new one may be the old
    # one relabelled - and the only way to tell is to hold the old one fixed
    # and see whether the new one still moves anything inside each stratum.
    #
    # Asked here rather than in a second tool because the rows are already
    # loaded and the question is meaningless apart from the walk above.
    if args.against:
        print(f"\nheld against {args.against}, stratum by stratum:")
        strata: dict[object, list[dict]] = {}
        for r in rows:
            strata.setdefault(r["state"].get(args.against), []).append(r)
        for key in sorted(strata, key=lambda k: (k is None, str(k))):
            chunk = strata[key]
            a = np.array(
                [r["r"] for r in chunk if r["state"].get(args.column) == args.value]
            )
            b = np.array(
                [r["r"] for r in chunk if r["state"].get(args.column) != args.value]
            )
            if len(a) < MIN_GROUP or len(b) < MIN_GROUP:
                print(f"  {str(key):12s} n={len(a)}/{len(b)}  too small to judge")
                continue
            d, t = _delta(a, b)
            print(f"  {str(key):12s} n={len(a):4d}/{len(b):4d}  delta {d:+.3f}  t {t:+.2f}")
        # And the contingency, so a reader sees how much the two overlap rather
        # than inferring it from the deltas.
        print(f"\n  overlap:")
        for key in sorted(strata, key=lambda k: (k is None, str(k))):
            inside = sum(
                1 for r in strata[key] if r["state"].get(args.column) == args.value
            )
            print(
                f"  {str(key):12s} {inside:4d} of {len(strata[key]):4d} are "
                f"{args.column}={args.value}"
            )

    print(f"\n{agree} of {usable} usable folds agree with the whole-sample sign")
    # THE BAR IS THE PRE-REGISTRATION'S, NOT THIS FILE'S. Six of eight, written
    # down before any of these numbers existed. A fold too small to judge is not
    # counted as agreement - it is removed from the denominator, which makes the
    # bar harder rather than easier.
    passed = agree >= 6 and usable >= 6
    print("PASSES the pre-registered walk-forward" if passed else "FAILS it")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
