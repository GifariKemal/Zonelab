"""The 3-6-9 dial: the arithmetic, the clock, and the seam that keeps it visual.

The last test in this file is the one that matters most. Everything else here
checks that a decorative object is drawn correctly; that one checks it can only
ever be decorative.
"""

from __future__ import annotations

import datetime as dt
import pathlib

import pytest

from app import clock, vortex
from app.models import Candle, DrawRequest, Drawing


def at(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return clock.to_epoch(dt.datetime(year, month, day, hour, minute, tzinfo=clock.NY))


def test_the_digital_root_matches_the_recursive_digit_sum_it_claims_to_be():
    """The closed form is an optimisation, so it is checked against the thing it
    optimises rather than against a table someone typed.

    A table would encode whatever the author believed; summing the digits is the
    definition. Range goes past 9 * 9 = 81 because the dial's largest product is
    54 and a form that broke at three digits would still pass a check stopping
    at two.
    """

    def by_hand(n: int) -> int:
        while n > 9:
            n = sum(int(c) for c in str(n))
        return n

    for n in range(1, 1000):
        assert vortex.digital_root(n) == by_hand(n), n


def test_zero_stays_zero_because_the_closed_form_would_call_it_nine():
    """`(0 - 1) % 9 + 1` is 9. Nine is a LIT value, so without the guard a zero
    reaching the dial would light a node - and zero is what an unset ring or an
    off-by-one index looks like.
    """
    assert vortex.digital_root(0) == 0
    with pytest.raises(ValueError, match="negative"):
        vortex.digital_root(-3)


def test_the_lit_cells_are_exactly_the_multiples_of_three_and_nothing_mystical():
    """The claim in `app/vortex.py`'s docstring, asserted rather than asserted-in-prose.

    A cell is lit when 3 divides r * k. That means rings 1, 2, 4 and 5 light at
    k = 3, 6, 9 and nowhere else, and rings 3 and 6 light everywhere. If someone
    later adds a fourth number to `LIT` or reorders `RINGS`, this fails - which
    is the point, because the renderer draws two ring shapes off this fact and
    would silently draw the wrong one.
    """
    table = vortex.matrix()
    assert len(table) == len(vortex.RINGS)
    for row, ring in zip(table, vortex.RINGS):
        assert len(row) == vortex.SECTORS
        lit = {k for k, root in enumerate(row, start=1) if root in vortex.LIT}
        expected = (
            set(range(1, 10)) if ring.r % 3 == 0 else {3, 6, 9}
        )
        assert lit == expected, (ring.label, sorted(lit))


def test_every_ring_spans_the_new_york_cycle_that_names_it():
    """The boundaries come from `app/quarters.py` and this pins the ones a
    reader would check by eye on a chart: the 18:00 day, the Sunday-evening
    week, and the calendar quarter read off the year cycle's own edges.

    Friday 10:00 NY on 2026-08-28 is deliberate. At the week degree Friday
    belongs to NO quarter - `quarters` cuts Monday through Thursday - so it is
    exactly the case where a ninth-split and a quarter-split disagree, and the
    dial must still place it.
    """
    epoch = at(2026, 8, 28, 10)
    got = {ring.id: ring for ring in vortex.dial(epoch).rings}

    assert got["day"].cycle_start == at(2026, 8, 27, 18)
    assert got["day"].cycle_end == at(2026, 8, 28, 18)
    # Sunday evening opens Monday's cycle.
    assert got["week"].cycle_start == at(2026, 8, 23, 18)
    assert got["week"].cycle_end == at(2026, 8, 30, 18)
    assert got["quarter"].cycle_start == at(2026, 7, 1)
    assert got["quarter"].cycle_end == at(2026, 10, 1)
    assert got["year"].cycle_start == at(2026, 1, 1)
    assert got["year"].cycle_end == at(2027, 1, 1)
    # Friday is inside the week span and inside none of its quarters.
    assert 1 <= got["week"].sector <= vortex.SECTORS


def test_the_sector_walks_one_to_nine_across_a_cycle_and_stops_there():
    """Nine sectors, first to last, with the boundaries landing where the
    arithmetic says and not one index past.

    The clamp is what is really under test. `sector` is called with epochs at
    and beyond both edges, because `_cycle` hands back spans whose ends are
    exclusive and an unclamped `1 + delta * 9 // span` returns 10 at the far
    edge - a tenth column, in a table that has nine.
    """
    start, end = 0, 900
    seen = [vortex.sector(start, end, t) for t in range(0, 900, 100)]
    assert seen == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert vortex.sector(start, end, end) == 9
    assert vortex.sector(start, end, end + 10_000) == 9
    assert vortex.sector(start, end, start - 10_000) == 1
    # A degenerate span answers rather than raising mid-draw.
    assert vortex.sector(5, 5, 5) == 1


def test_the_root_on_the_wire_agrees_with_the_matrix_on_the_wire():
    """Two fields that could drift, checked against each other.

    `root` is a convenience so the renderer does not index the table for the
    live cell, and a convenience that disagrees with its source is worse than no
    convenience: the dial would highlight one node and label it another.
    """
    for epoch in (at(2026, 1, 1, 3), at(2026, 8, 28, 10), at(2026, 12, 31, 23)):
        payload = vortex.dial(epoch)
        for row, ring in enumerate(payload.rings):
            assert ring.root == payload.matrix[row][ring.sector - 1], (epoch, ring.id)
            assert ring.r == vortex.RINGS[row].r


def test_the_layer_draws_the_dial_and_an_empty_series_draws_none_of_it():
    """Absent beats confident-and-wrong.

    With no bars there is no bar time, and a dial placed at epoch zero would
    point at 1 January 1970 while looking exactly as authoritative as a correct
    one. `meta` says why instead.
    """
    from app.drawing import _draw_vortex

    drawing, meta = Drawing(), {}
    _draw_vortex([], DrawRequest(symbol="XAUUSD"), drawing, meta)
    assert drawing.vortex is None
    assert meta["vortex"]["drawn"] == 0

    when = at(2026, 8, 28, 10)
    rows = [Candle(time=when, open=1, high=2, low=0.5, close=1.5, volume=1)]
    drawing, meta = Drawing(), {}
    _draw_vortex(rows, DrawRequest(symbol="XAUUSD"), drawing, meta)
    assert drawing.vortex is not None
    assert len(drawing.vortex.rings) == 6
    assert meta["vortex"]["at"] == when


def test_the_dial_is_placed_on_the_newest_bar_and_never_on_the_wall_clock():
    """A dial that read `time.time()` would pass every test above and still be
    wrong on screen, because it would point at a sector no visible candle is in.

    Verified by feeding a bar from a year the wall clock is not in: if anything
    read the real clock, the year ring's span would be this year's.
    """
    from app.drawing import _draw_vortex

    old = at(2021, 3, 5, 14)
    rows = [Candle(time=old, open=1, high=2, low=0.5, close=1.5, volume=1)]
    drawing = Drawing()
    _draw_vortex(rows, DrawRequest(symbol="XAUUSD"), drawing, {})
    assert drawing.vortex is not None
    year = next(r for r in drawing.vortex.rings if r.id == "year")
    assert year.cycle_start == at(2021, 1, 1)
    assert year.cycle_end == at(2022, 1, 1)


def test_no_execution_module_can_read_the_dial():
    """THE SEAM. Everything above says the dial draws correctly; this says it
    cannot do anything else.

    `docs/PRAREGISTRASI-YATIM.md` is a record of what happens when a construct
    with no measurement behind it gets near a decision: twelve pre-registered
    directional hypotheses, all failed, the most recent being the OTE band
    across twelve instruments at zero of twelve. The 3-6-9 dial has less than
    that - it has no hypothesis at all, because it reads no price - so it is
    barred from the order path by a test rather than by an intention.

    Checked by SOURCE TEXT, not by import graph, and that difference is the
    whole strength of it. An import graph check passes the moment someone reads
    `drawing.vortex` off a response dict, which needs no import. Any mention of
    the module, the field or the layer id inside these files fails here.
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    # The files that decide, size, gate or send. Named one by one rather than
    # globbed, so adding an execution module is a decision someone writes down
    # here instead of quietly falling outside the guard.
    guarded = [
        root / "app" / "ict.py",
        root / "app" / "portfolio.py",
        root / "app" / "advisor.py",
        root / "app" / "confluence.py",
        root / "tools" / "execute.py",
        root / "tools" / "autotrade.py",
        root / "tools" / "flatten.py",
    ]
    missing = [p.name for p in guarded if not p.exists()]
    assert not missing, f"guard points at files that are gone: {missing}"

    for path in guarded:
        source = path.read_text(encoding="utf-8")
        for banned in ("vortex", "digital_root", "3-6-9"):
            assert banned not in source, (
                f"{path.name} mentions {banned!r}. The 3-6-9 dial is visual "
                "only: it reads no price and has no measurement behind it, so "
                "it must not reach anything that decides, sizes or sends."
            )
