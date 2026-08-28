"""CISD on series whose correct answer is arithmetic.

Every fixture below is built by hand from (open, close) pairs so the level under
test is a number you can read off the page, because the one thing this construct
gets wrong in the wild is WHICH candle's open it anchors to. Two tests exist only
to pin that down: one asserts the level is the FIRST candle's open, and one puts
a close between the first candle's open and the last candle's open so a naive
port passes where this must fail.

Nothing here tests whether a CISD predicts anything. It does not claim to - see
the module docstring, and docs/CALIBRATION.md for the three times market
structure was measured for direction and came out null.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_cisd.py -q
"""

from __future__ import annotations

from app.cisd import CISD, cisds, delivery_runs
from app.models import Candle
from app.providers.synthetic import generate

#: Jam dinding dibekukan untuk fixture sintetik: Kamis 2026-05-28 16:26 NY, hari
#: kerja di tengah sesi. `generate` menambatkan grid-nya ke waktu nyata dan
#: `_session_grid` melompati jam pasar tutup, jadi bar mana yang jatuh di mana
#: bergerak dengan hari kalender saat test dijalankan. Satu test di repo ini lolos
#: berbulan-bulan lalu mulai gagal stabil karena itu, tanpa fixture-nya berubah.
FROZEN_NOW = 1780000000

STEP = 900
T0 = 1_700_000_000 // 86_400 * 86_400


def series(rows: list[tuple[float, ...]]) -> list[Candle]:
    """Candles from (open, close) or (open, close, high_pad, low_pad) tuples.

    The pads default to a small symmetric wick so no fixture accidentally makes
    a wick reach a level the close does not - the one case that has its own test
    and must not leak into the others.
    """
    out: list[Candle] = []
    for i, row in enumerate(rows):
        o, c = row[0], row[1]
        hp = row[2] if len(row) > 2 else 0.5
        lp = row[3] if len(row) > 3 else 0.5
        out.append(
            Candle(
                time=T0 + i * STEP,
                open=o,
                close=c,
                high=max(o, c) + hp,
                low=min(o, c) - lp,
                volume=1000.0,
            )
        )
    return out


THREE_DOWN = [(110.0, 108.0), (108.0, 106.0), (106.0, 104.0)]
"""A down-run whose FIRST open is 110 and whose LAST open is 106."""


def flat(n: int, price: float = 100.0) -> list[Candle]:
    return series([(price, price)] * n)


# --------------------------------------------------------------------------
# The level is the first candle's open, and that is the whole construct
# --------------------------------------------------------------------------


def test_three_down_candles_then_a_close_above_anchors_on_the_first_open():
    rows = series(THREE_DOWN + [(104.0, 111.0)])

    events, runs = cisds(rows)

    assert len(events) == 1
    assert events[0] == CISD(
        index=3,
        time=rows[3].time,
        direction=1,
        level=110.0,
        run_start=0,
        run_end=2,
        run_length=3,
    )
    # The run itself, so a failure says whether the run or the break was wrong.
    assert [(r.start, r.end, r.direction, r.length) for r in runs] == [(0, 2, -1, 3)]
    assert runs[0].open_price == rows[0].open == 110.0


def test_three_up_candles_then_a_close_below_is_the_exact_mirror():
    rows = series([(100.0, 102.0), (102.0, 104.0), (104.0, 106.0), (106.0, 99.0)])

    events, _ = cisds(rows)

    assert [(e.index, e.direction, e.level) for e in events] == [(3, -1, 100.0)]


def test_the_naive_last_candle_open_would_fire_a_bar_early_and_at_a_wrong_level():
    """The single most common way this construct is coded wrong.

    The bar at index 3 closes at 107: above the LAST down candle's open of 106,
    below the FIRST down candle's open of 110. A port anchored on the last candle
    reports a CISD here at level 106. The correct answer is nothing, and the CISD
    arrives one bar later at 110 - so this asserts both the two levels differ and
    that the later one is the one taken.
    """
    rows = series(THREE_DOWN + [(104.0, 107.0), (107.0, 111.0)])

    events, runs = cisds(rows)

    naive = rows[runs[0].end].open
    assert runs[0].open_price == 110.0
    assert naive == 106.0
    assert runs[0].open_price != naive, "the fixture must separate the two readings"
    assert 106.0 < rows[3].close < 110.0, "and bar 3 must sit between them"

    assert [(e.index, e.level) for e in events] == [(4, 110.0)]


def test_a_wick_through_the_level_with_a_close_inside_produces_nothing():
    """Body close, not wick. A Pine port that tests the high fires here."""
    # Bar 3 is an up-close, so the run confirms, but its high reaches 112 while
    # its close stays at 107.
    rows = series(THREE_DOWN + [(104.0, 107.0, 5.0, 0.5)])

    events, runs = cisds(rows)

    assert rows[3].high > runs[0].open_price == 110.0
    assert rows[3].close < runs[0].open_price
    assert events == []


# --------------------------------------------------------------------------
# The two parameters, both chosen rather than measured
# --------------------------------------------------------------------------


def test_the_interruption_tolerance_changes_both_the_level_and_the_bar():
    """One opposing candle mid-run: noise, or the end of the run?

    Bars 0-1 fall, bar 2 rises, bars 3-4 fall, bars 5-6 rise. At tolerance 0 that
    is two separate down-runs and the second one's open of 107 is the live level.
    At tolerance 1 the single up candle is absorbed, the two become ONE run
    anchored at 110, and the level is not taken until bar 6. Different level,
    different bar, same data - which is why the docstring says the count is not
    stable under this parameter.
    """
    rows = series(
        [
            (110.0, 108.0),
            (108.0, 106.0),
            (106.0, 107.0),  # the interruption
            (107.0, 105.0),
            (105.0, 103.0),
            (103.0, 109.0),
            (109.0, 112.0),
        ]
    )

    strict, strict_runs = cisds(rows, interrupt_tolerance=0)
    loose, loose_runs = cisds(rows, interrupt_tolerance=1)

    assert [(e.index, e.level) for e in strict] == [(5, 107.0)]
    assert [(e.index, e.level) for e in loose] == [(6, 110.0)]
    assert strict[0].level != loose[0].level
    assert strict[0].index != loose[0].index

    # The runs underneath, because the level moving is a consequence of the runs
    # merging and a failure should say which of the two broke.
    assert [(r.start, r.end, r.length) for r in strict_runs if r.direction < 0] == [
        (0, 1, 2),
        (3, 4, 2),
    ]
    assert [(r.start, r.end, r.length) for r in loose_runs if r.direction < 0] == [
        (0, 4, 4)
    ]
    # `end` is the last CONFORMING candle, never the absorbed interruption.
    assert loose_runs[0].end == 4 and loose_runs[0].length == 4


def test_a_one_candle_run_is_excluded_by_the_default_floor_and_admitted_at_one():
    rows = series([(110.0, 108.0), (108.0, 111.0)])

    default, runs = cisds(rows)
    floored, _ = cisds(rows, min_run=1)

    assert [(r.start, r.end, r.length) for r in runs] == [(0, 0, 1)]
    assert default == [], "min_run=2 must refuse a one-candle run"
    assert [(e.index, e.level, e.run_length) for e in floored] == [(1, 110.0, 1)]


def test_min_run_filters_the_cisds_without_deleting_the_runs():
    """The drawn population and the counted one must not diverge silently."""
    rows = series(THREE_DOWN + [(104.0, 107.0), (107.0, 105.0), (105.0, 111.0)])

    _, low = cisds(rows, min_run=1)
    _, high = cisds(rows, min_run=99)

    assert low == high, "min_run must not change which runs exist"
    assert cisds(rows, min_run=99)[0] == [], "only the events may be filtered"


# --------------------------------------------------------------------------
# The property that decides whether any of this is a measurement
# --------------------------------------------------------------------------


def test_no_cisd_can_be_seen_before_the_bar_it_is_knowable_at():
    """Truncate the series AT each event's bar and it must still be found.

    A detector that reacted to a run the moment it started, or that peeked at the
    bar after the break, would produce events that vanish under truncation. This
    repo has caught lookahead in its own code before, so the property is asserted
    on a series long enough to have many events rather than argued from the loop.
    """
    rows = generate(400, STEP, seed=11, now=FROZEN_NOW)
    events, runs = cisds(rows)
    assert len(events) > 20, f"the fixture must exercise the loop, got {len(events)}"

    by_start = {r.start: r for r in runs}
    for e in events:
        assert e.time == rows[e.index].time, "the stamp is the breaking bar's own"
        assert by_start[e.run_start].confirmed_at <= e.index

        # Everything the event needs had printed by its own bar.
        truncated, _ = cisds(rows[: e.index + 1])
        assert truncated and truncated[-1] == e

        # And it was not knowable one bar sooner.
        earlier, _ = cisds(rows[: e.index])
        assert e not in earlier


def test_every_run_ends_after_it_starts_and_is_confirmed_after_it_ends():
    rows = generate(400, STEP, seed=11, now=FROZEN_NOW)

    for tolerance in (0, 1, 3):
        runs = delivery_runs(rows, interrupt_tolerance=tolerance)
        assert runs
        for r in runs:
            assert r.start <= r.end < r.confirmed_at < len(rows)
            assert r.length >= 1
            assert r.open_price == rows[r.start].open
            assert r.direction in (1, -1)
        # Non-overlapping, oldest first.
        for a, b in zip(runs, runs[1:]):
            assert a.end < b.start


# --------------------------------------------------------------------------
# Degenerate input
# --------------------------------------------------------------------------


def test_a_flat_series_produces_no_runs_rather_than_runs_of_length_zero():
    """`close == open` delivers in neither direction, so nothing accumulates."""
    rows = flat(20)

    events, runs = cisds(rows)

    assert runs == []
    assert events == []


def test_a_single_doji_ends_a_run_at_the_default_tolerance():
    rows = series(THREE_DOWN + [(104.0, 104.0), (104.0, 111.0)])

    events, runs = cisds(rows)

    assert runs[0].confirmed_at == 3, "the doji is the bar that ended the run"
    assert [(e.index, e.level) for e in events] == [(4, 110.0)]


def test_an_empty_or_one_bar_series_produces_nothing():
    assert cisds([]) == ([], [])
    assert cisds(series([(110.0, 108.0)])) == ([], [])


def test_a_run_still_open_at_the_last_bar_is_not_emitted():
    """Its end is not knowable, so it cannot anchor anything."""
    rows = series(THREE_DOWN)

    _, runs = cisds(rows)

    assert runs == []
