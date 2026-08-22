"""A fold may not be graded on bars the NEXT fold decided.

This exists because it was not enforced. `tools/costed.py` split its walk-forward
folds on the touch bar alone, so a trade opening near a fold's end had its
outcome settled by the following fold's bars and was still counted as that
fold's evidence. `tools/walkforward.py` had purging and said why; `costed.py`
had neither the rule nor a note explaining its absence, and every fold count it
ever printed - including the 8/8 that put the departure gate into `app/plan.py` -
came off unpurged slices.

Re-measured after the fix, 0 of the 8 graded folds lost a trade at 50,000 bars:
the median trade is held ONE bar and 1.2% reach the 80-bar horizon. So the
finding did not move. That is the outcome worth having, and it is only worth
anything because the rule is now checked rather than assumed - `purged 2` on a
4,000-bar run is what the same code prints when the folds are narrow enough for
trades to cross them.
"""

from __future__ import annotations

from tools.costed import purged_fold


def row(at: int, exit_at: int) -> dict:
    """The two fields purging reads. Everything else on a real row is noise here."""
    return {"at": at, "exit": exit_at, "r": 1.0, "skipped": False, "cleared": True}


def test_a_trade_resolving_inside_the_fold_is_kept():
    kept, dropped = purged_fold([row(10, 20)], 0, 100)
    assert (len(kept), dropped) == (1, 0)


def test_a_trade_resolving_after_the_fold_is_dropped():
    """The defect this file is named for: opens at 95, decided at 105, and the
    fold ends at 100. Counting it grades fold one on fold two's bars."""
    kept, dropped = purged_fold([row(95, 105)], 0, 100)
    assert (kept, dropped) == ([], 1)


def test_a_trade_exiting_exactly_on_the_boundary_is_dropped():
    """`hi` is the first bar of the NEXT fold, so a trade decided on it was
    decided there. Half-open in both directions or the two folds disagree about
    who owns the bar."""
    kept, dropped = purged_fold([row(95, 100)], 0, 100)
    assert (kept, dropped) == ([], 1)


def test_a_trade_opening_before_the_fold_is_not_this_fold_s_trade():
    """Not purging - ownership. It belongs to the earlier fold and must not be
    counted twice."""
    kept, dropped = purged_fold([row(5, 50)], 10, 100)
    assert (kept, dropped) == ([], 0), "an earlier fold's trade is not a purge"


def test_ownership_and_purging_are_counted_separately():
    """Three rows, one of each kind, so a single mistaken predicate cannot pass:
    inside is kept, crossing is purged, earlier is neither."""
    rows = [row(20, 30), row(95, 105), row(5, 8)]
    kept, dropped = purged_fold(rows, 10, 100)
    assert [r["at"] for r in kept] == [20]
    assert dropped == 1


def test_the_boundary_is_half_open_at_the_start_too():
    """A trade opening exactly on `lo` is this fold's, and one opening exactly on
    `hi` is the next fold's."""
    kept, _ = purged_fold([row(10, 11), row(100, 101)], 10, 100)
    assert [r["at"] for r in kept] == [10]
