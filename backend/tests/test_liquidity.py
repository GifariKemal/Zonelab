"""The named horizontal levels: previous-period extremes, ERL/IRL, and DOL.

Three tests here earn the file on their own.

The first is the BOUNDARY test. A previous-day high measured 18:00-to-18:00 is a
DIFFERENT NUMBER from one measured midnight-to-midnight, and the test asserts
that difference directly on one hand-built series: the same question answered
twice, 3410 against 3500, because an evening spike belongs to tomorrow's cycle
under one rule and to today under the other. Every object carries the boundary it
was measured under, so if that assertion is ever relaxed the module has started
hiding the trap it exists to document.

The second is the SYMMETRY test. `dol_candidates` reports untaken liquidity above
price and untaken liquidity below it, and on a normal bar both lists are
populated at once. That is the whole reason nothing here names a draw: choosing
one of two sets that always both exist is a forecast, and twelve pre-registered
directional hypotheses have failed in this project.

The third is the KNOWABILITY pair. A period's extreme does not exist until a bar
proves the period closed, and a dealing range read at bar 6 must not contain a
swing that confirmed at bar 7. Both are asserted by truncation rather than by
intent.

Nothing here asserts that any level predicts anything.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_liquidity.py -q
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app import liquidity
from app.clock import NY
from app.liquidity import (
    Level,
    dol_candidates,
    pool_levels,
    previous_period_levels,
    range_liquidity,
)
from app.models import Anatomy, Candle, Zone, ZoneKind, ZoneSide, ZoneState
from app.pools import liquidity_pools

HOUR = 3600

ANATOMY = Anatomy(
    leg_in_from=0, leg_in_to=1, base_run_from=2, base_from=2, base_to=3,
    leg_out_from=4, leg_out_to=5,
)


def ny(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    """Epoch of a New York wall-clock time, built here rather than imported.

    Deliberately not `clock.ny_wall`: the expected values must come from the
    calendar independently of the code under test.
    """
    return int(datetime(year, month, day, hour, minute, tzinfo=NY).timestamp())


def bar(t: int, high: float, low: float) -> Candle:
    return Candle(time=t, open=(high + low) / 2, high=high, low=low,
                  close=(high + low) / 2)


def flat(start: int, end: int, high: float, low: float) -> list[Candle]:
    """Hourly bars over [start, end) that all share one high and low."""
    return [bar(t, high, low) for t in range(start, end, HOUR)]


def zone(zone_id: str, proximal: float, formed_at: int,
         touched_at: int | None = None) -> Zone:
    """A zone reduced to the fields internal range liquidity reads."""
    return Zone(
        id=zone_id,
        kind=ZoneKind.FVG,
        side=ZoneSide.DEMAND,
        state=ZoneState.FRESH if touched_at is None else ZoneState.TESTED,
        top=proximal,
        bottom=proximal - 5.0,
        proximal=proximal,
        distal=proximal - 5.0,
        time_from=formed_at,
        time_to=formed_at + HOUR,
        formation_score=0.5,
        departure_atr=2.0,
        first_test_time=touched_at,
        anatomy=ANATOMY,
    )


# --------------------------------------------------------------------------- #
# Previous-period extremes
# --------------------------------------------------------------------------- #


def test_the_previous_day_high_and_low_are_the_extremes_of_the_closed_day():
    # One whole midnight-to-midnight day, 24 hourly bars, with exactly one high
    # and one low that stand out. The answer is arithmetic: 3450 and 3350.
    candles = flat(ny(2025, 6, 10), ny(2025, 6, 10, 10), 3410.0, 3390.0)
    candles.append(bar(ny(2025, 6, 10, 10), 3450.0, 3390.0))
    candles += flat(ny(2025, 6, 10, 11), ny(2025, 6, 10, 14), 3410.0, 3390.0)
    candles.append(bar(ny(2025, 6, 10, 14), 3410.0, 3350.0))
    candles += flat(ny(2025, 6, 10, 15), ny(2025, 6, 11), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 6), 3405.0, 3395.0)

    levels = previous_period_levels(candles, periods=("day",), boundary="midnight")

    assert [level.name for level in levels] == ["PDH", "PDL"]
    assert [level.price for level in levels] == [3450.0, 3350.0]
    assert levels[0].window_from == ny(2025, 6, 10)
    assert levels[0].window_to == ny(2025, 6, 11)
    assert levels[0].bars == 24
    assert levels[0].boundary == "midnight"
    assert levels[0].knowable_at == ny(2025, 6, 11)
    # The feed spans the window edge to edge, so nothing of it went unmeasured.
    assert (levels[0].gap_at_open, levels[0].gap_at_close) == (0, 0)
    # Neither extreme was traded through by the bars that followed.
    assert all(level.taken_at is None for level in levels)


def test_the_same_series_gives_a_different_previous_day_high_on_each_boundary():
    """THE TRAP THIS MODULE EXISTS TO DOCUMENT, asserted rather than described.

    One spike, at 20:00 on Wednesday. Under the midnight boundary it belongs to
    Wednesday, whose window closed at 00:00 and which is therefore a completed
    previous day: PDH 3500. Under the 18:00 cycle boundary that same spike
    belongs to THURSDAY's cycle, which has not closed yet and so produces no
    level at all, leaving the newest PDH at 3410.

    Same series, same question, two different numbers. A caller who does not read
    `boundary` off the object cannot tell which one it was handed.
    """
    candles = flat(ny(2025, 6, 10), ny(2025, 6, 11, 20), 3410.0, 3390.0)
    candles.append(bar(ny(2025, 6, 11, 20), 3500.0, 3390.0))
    candles += flat(ny(2025, 6, 11, 21), ny(2025, 6, 12, 12), 3410.0, 3390.0)

    cycle = [
        level
        for level in previous_period_levels(candles, ("day",), boundary="cycle")
        if level.side == "BSL"
    ]
    midnight = [
        level
        for level in previous_period_levels(candles, ("day",), boundary="midnight")
        if level.side == "BSL"
    ]

    assert cycle[-1].price == 3410.0
    assert midnight[-1].price == 3500.0
    assert cycle[-1].price != midnight[-1].price
    # And they are not even measuring the same window.
    assert cycle[-1].window_from == ny(2025, 6, 10, 18)
    assert cycle[-1].window_to == ny(2025, 6, 11, 18)
    assert midnight[-1].window_from == ny(2025, 6, 11)
    assert midnight[-1].window_to == ny(2025, 6, 12)
    # Every object says which rule produced it, on both sides of the pair.
    assert {level.boundary for level in cycle} == {"cycle"}
    assert {level.boundary for level in midnight} == {"midnight"}


def test_a_period_extreme_is_not_reported_until_a_bar_proves_the_period_closed():
    # Truncation rather than intent: the answer computed from bars up to the
    # knowable instant must equal the answer from the whole series, and the
    # answer one bar earlier must not exist at all.
    candles = flat(ny(2025, 6, 10), ny(2025, 6, 11), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 3), 3405.0, 3395.0)

    inside_only = previous_period_levels(candles[:24], ("day",), boundary="midnight")
    at_close = previous_period_levels(candles[:25], ("day",), boundary="midnight")

    assert inside_only == []
    assert [level.price for level in at_close] == [3410.0, 3390.0]
    assert at_close[0].knowable_at == ny(2025, 6, 11)


def test_a_level_is_taken_by_the_first_bar_that_pierced_it_and_not_a_later_one():
    candles = flat(ny(2025, 6, 10), ny(2025, 6, 11), 3410.0, 3390.0)
    candles.append(bar(ny(2025, 6, 11), 3405.0, 3395.0))
    first = bar(ny(2025, 6, 11, 1), 3420.0, 3400.0)  # takes the 3410 PDH
    later = bar(ny(2025, 6, 11, 2), 3480.0, 3400.0)  # takes it again, much harder
    candles += [first, later]

    levels = previous_period_levels(candles, ("day",), boundary="midnight")
    pdh = next(level for level in levels if level.name == "PDH")

    assert pdh.price == 3410.0
    assert pdh.taken_at == first.time
    assert pdh.taken_at != later.time
    # A taken level is still reported: it is the fact that kills a trade idea.
    assert pdh in levels


def test_an_equal_high_touches_the_level_without_taking_it():
    candles = flat(ny(2025, 6, 10), ny(2025, 6, 11), 3410.0, 3390.0)
    # Both later bars print exactly the previous day's extremes and no further.
    candles += [
        bar(ny(2025, 6, 11), 3410.0, 3395.0),
        bar(ny(2025, 6, 11, 1), 3405.0, 3390.0),
    ]

    levels = previous_period_levels(candles, ("day",), boundary="midnight")

    assert len(levels) == 2
    assert all(level.taken_at is None for level in levels)


def test_a_holiday_with_no_bars_in_the_window_produces_no_level_at_all():
    # A feed that skips the 11th entirely. The window is never widened to find a
    # bar and no price is carried over from the day that did trade.
    candles = flat(ny(2025, 6, 10), ny(2025, 6, 11), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 12), ny(2025, 6, 12, 6), 3420.0, 3380.0)

    levels = previous_period_levels(candles, ("day",), boundary="midnight")

    assert [level.window_from for level in levels] == [ny(2025, 6, 10)] * 2
    assert ny(2025, 6, 11) not in [level.window_from for level in levels]


def test_a_partial_period_reports_the_seconds_of_window_that_had_no_bars():
    # The feed only opens at 06:00, so the high of these bars is NOT the day's
    # high. The level is still reported - the bars do exist - and the six unbarred
    # hours at the window's open are stated in seconds rather than compressed
    # into a flag that cannot tell a short feed from a closed market.
    partial = flat(ny(2025, 6, 10, 6), ny(2025, 6, 11), 3410.0, 3390.0)
    partial += flat(ny(2025, 6, 11), ny(2025, 6, 11, 2), 3405.0, 3395.0)
    whole = flat(ny(2025, 6, 10), ny(2025, 6, 11), 3410.0, 3390.0)
    whole += flat(ny(2025, 6, 11), ny(2025, 6, 11, 2), 3405.0, 3395.0)

    short = previous_period_levels(partial, ("day",), boundary="midnight")
    full = previous_period_levels(whole, ("day",), boundary="midnight")

    assert short[0].gap_at_open == 6 * HOUR
    assert short[0].first_bar == ny(2025, 6, 10, 6)
    assert short[0].bars == 18
    # The same window with every bar present reads zero at both edges, so the
    # numbers are tracking coverage and not some constant.
    assert (full[0].gap_at_open, full[0].gap_at_close) == (0, 0)
    assert full[0].bars == 24


def test_coverage_is_seconds_because_a_flag_would_read_false_on_every_correct_level():
    """The one place this module's shape departs from `pools.py`, and the reason.

    `pools.covered` wants a bar within one step of each window edge. Both windows
    here close on a market CLOSURE instead: an 18:00 day cycle closes on the far
    side of the 17:00-to-18:00 maintenance break, and a week cycle closes on a
    Sunday evening. On a feed shaped like a real gold trading week that flag
    would have read False on every correct level in the series - and a flag that
    is False on everything is a bug rather than a reading, which this project has
    shipped once already (see the modal-step regression in test_pools.py).
    """
    rows: list[Candle] = []
    for day in (date(2025, 6, 1) + timedelta(days=i) for i in range(21)):
        weekday = day.weekday()
        hours = (
            range(18, 24) if weekday == 6
            else range(0, 17) if weekday == 4
            else [] if weekday == 5
            else [*range(0, 17), *range(18, 24)]
        )
        rows += [
            bar(ny(day.year, day.month, day.day, hour, minute), 3410.0, 3390.0)
            for hour in hours
            for minute in (0, 15, 30, 45)
        ]

    days = previous_period_levels(rows, ("day",), boundary="cycle")
    weeks = previous_period_levels(rows, ("week",), boundary="cycle")

    assert len(days) == 28 and len(weeks) == 4  # two levels per window
    # The daily maintenance break, and the weekend. Both are the market being
    # shut rather than the feed being short, and no boolean can tell them apart.
    assert {level.gap_at_close for level in days} == {HOUR}
    assert {level.gap_at_close for level in weeks} == {49 * HOUR}
    assert {level.gap_at_open for level in days + weeks} == {0}


def test_the_previous_week_runs_sunday_evening_to_sunday_evening_on_the_cycle_boundary():
    candles = flat(ny(2025, 6, 8, 18), ny(2025, 6, 10, 12), 3410.0, 3390.0)
    candles.append(bar(ny(2025, 6, 10, 12), 3480.0, 3320.0))
    candles += flat(ny(2025, 6, 10, 13), ny(2025, 6, 15, 20), 3410.0, 3390.0)

    levels = previous_period_levels(candles, ("week",), boundary="cycle")

    assert [level.name for level in levels] == ["PWH", "PWL"]
    assert [level.price for level in levels] == [3480.0, 3320.0]
    assert levels[0].window_from == ny(2025, 6, 8, 18)
    assert levels[0].window_to == ny(2025, 6, 15, 18)
    assert levels[0].window_to - levels[0].window_from == 7 * 24 * HOUR
    assert levels[0].knowable_at == ny(2025, 6, 15, 18)
    assert (levels[0].gap_at_open, levels[0].gap_at_close) == (0, 0)


def test_friday_and_monday_are_named_apart_from_the_day_windows_they_repeat():
    # He names these two separately because they carry their own meaning in his
    # week profile, so they are the same measurement under their own names - and
    # asking for a day beside them reports that window twice on purpose.
    candles = flat(ny(2025, 6, 8, 18), ny(2025, 6, 15, 20), 3410.0, 3390.0)

    named = previous_period_levels(candles, ("friday", "monday"), boundary="cycle")
    doubled = previous_period_levels(candles, ("day", "monday"), boundary="cycle")

    monday = next(level for level in named if level.name == "MON H")
    friday = next(level for level in named if level.name == "FRI H")

    assert {level.name for level in named} == {"FRI H", "FRI L", "MON H", "MON L"}
    # Monday's cycle opens on the Sunday evening, Friday's on the Thursday one.
    assert monday.window_from == ny(2025, 6, 8, 18)
    assert monday.window_to == ny(2025, 6, 9, 18)
    assert friday.window_from == ny(2025, 6, 12, 18)
    assert friday.window_to == ny(2025, 6, 13, 18)
    same_window = [
        level.name for level in doubled if level.window_from == monday.window_from
    ]
    assert sorted(same_window) == ["MON H", "MON L", "PDH", "PDL"]


def test_unknown_periods_and_boundaries_are_rejected_rather_than_silently_skipped():
    candles = flat(ny(2025, 6, 10), ny(2025, 6, 11, 2), 3410.0, 3390.0)

    with pytest.raises(ValueError):
        previous_period_levels(candles, periods=("quarter",))
    with pytest.raises(ValueError):
        previous_period_levels(candles, boundary="utc")


def test_no_candles_produce_no_levels_and_no_range():
    assert previous_period_levels([]) == []
    assert range_liquidity([]) is None


# --------------------------------------------------------------------------- #
# ERL and IRL
# --------------------------------------------------------------------------- #


def swing_series() -> list[Candle]:
    """Twelve bars with one clear swing high at bar 2 and a lower low at bar 5.

    At width 2 the pivots are: a high of 3450 and a low of 3380 at bar 2, both
    confirmed at bar 4, and a low of 3300 at bar 5, confirmed at bar 7.
    """
    highs = [3400, 3405, 3450, 3405, 3400, 3395, 3390, 3395, 3400, 3405, 3410, 3415]
    lows = [3390, 3385, 3380, 3385, 3390, 3300, 3390, 3385, 3380, 3385, 3390, 3395]
    start = ny(2025, 6, 10)
    return [
        bar(start + i * HOUR, float(high), float(low))
        for i, (high, low) in enumerate(zip(highs, lows))
    ]


def test_the_external_range_liquidity_is_the_two_confirmed_swing_extremes():
    candles = swing_series()

    found = range_liquidity(candles, at=candles[9].time, swing_n=2)

    assert found is not None
    assert (found.high, found.low) == (3450.0, 3300.0)
    assert found.high_time == candles[2].time
    assert found.low_time == candles[5].time
    # The range is a PAIR, so it is knowable only once the later of the two
    # swings has confirmed - bar 7, not bar 4.
    assert found.knowable_at == candles[7].time
    assert [level.name for level in found.external] == ["RNG H", "RNG L"]
    assert [level.price for level in found.external] == [3450.0, 3300.0]
    # Each extreme carries its OWN confirmation, and neither was traded through.
    assert found.external[0].knowable_at == candles[4].time
    assert found.external[1].knowable_at == candles[7].time
    assert all(level.taken_at is None for level in found.external)


def test_the_range_is_built_only_from_swings_confirmed_at_or_before_the_bar_read():
    # The 3300 low prints at bar 5 and confirms at bar 7. A range read at bar 6
    # must not contain it, however visible it is on the chart by then.
    candles = swing_series()

    early = range_liquidity(candles, at=candles[6].time, swing_n=2)
    late = range_liquidity(candles, at=candles[7].time, swing_n=2)

    assert early is not None and late is not None
    assert early.low == 3380.0
    assert early.low_time == candles[2].time
    assert late.low == 3300.0
    assert late.low_time == candles[5].time


def test_internal_range_liquidity_is_the_zones_resting_inside_the_range():
    candles = swing_series()
    formed = candles[0].time
    zones = [
        zone("inside-1", 3400.0, formed),
        zone("inside-2", 3350.0, formed, touched_at=candles[8].time),
        zone("above", 3500.0, formed),
        zone("at-the-high", 3450.0, formed),  # the range extreme is ERL, not IRL
        zone("later", 3380.0, candles[11].time),  # not formed by the bar read
    ]

    found = range_liquidity(candles, zones, at=candles[9].time, swing_n=2)

    assert found is not None
    # The KIND, not the zone id. An internal level is named after the formation
    # it came from, because these are rendered beside `PDH` and `range_high` and
    # `DBD-1787015700-4487.39990` reads as a bug on screen. Two zones of one kind
    # therefore share a name and are told apart by price, which is how every
    # other level in this module already works.
    assert [level.name for level in found.internal] == ["FVG", "FVG"]
    assert len({level.price for level in found.internal}) == len(found.internal), (
        "two internal levels at one price would be indistinguishable once named by kind"
    )
    # The zone's own touch record is carried across; no second opinion is
    # computed here, so this cannot disagree with the box the engine drew.
    assert found.internal[0].taken_at is None
    assert found.internal[1].taken_at == candles[8].time


# --------------------------------------------------------------------------- #
# DOL candidates
# --------------------------------------------------------------------------- #


def test_there_is_untaken_liquidity_above_and_below_price_on_a_normal_bar():
    """The symmetry is the point, so it is the assertion.

    Both lists are populated at the same instant, which is what makes naming
    either one of them "the draw" a forecast rather than a reading.
    """
    at = ny(2025, 6, 11, 4)
    levels = [
        Level("PDH", 3450.0, ny(2025, 6, 11), None),
        Level("PWH", 3600.0, ny(2025, 6, 11), None),
        Level("PDL", 3350.0, ny(2025, 6, 11), None),
        Level("asia SSL", 3300.0, ny(2025, 6, 11), None),
        Level("london BSL", 3420.0, ny(2025, 6, 11), ny(2025, 6, 11, 2)),
    ]

    report = dol_candidates(levels, price=3400.0, at=at)

    assert report.above and report.below
    assert [c.name for c in report.above] == ["PDH", "PWH"]
    assert [c.name for c in report.below] == ["PDL", "asia SSL"]
    assert [c.distance for c in report.above] == [50.0, 200.0]
    assert [c.distance for c in report.below] == [50.0, 100.0]
    # The London high was taken two hours ago and is no longer standing.
    assert "london BSL" not in [c.name for c in report.above]
    # There is no field on this object that could be read as a prediction.
    assert not hasattr(report, "draw")
    assert not hasattr(report, "target")


def test_a_session_pool_becomes_a_candidate_without_being_measured_a_second_time():
    candles = flat(ny(2025, 6, 10, 19), ny(2025, 6, 11), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 2), 3405.0, 3395.0)

    pools = liquidity_pools(candles, sessions=("asia",))
    levels = pool_levels(pools)

    assert [level.name for level in levels] == ["asia BSL", "asia SSL"]
    # A rename and nothing else: every decision stays the one `pools.py` made.
    assert [(level.price, level.knowable_at, level.taken_at) for level in levels] == [
        (pool.price, pool.knowable_at, pool.taken_at) for pool in pools
    ]


def test_a_level_that_was_not_yet_knowable_is_not_a_candidate():
    at = ny(2025, 6, 11, 4)
    levels = [
        Level("PDH", 3450.0, ny(2025, 6, 11, 6), None),  # knowable two hours later
        Level("PDL", 3350.0, ny(2025, 6, 11), None),
    ]

    report = dol_candidates(levels, price=3400.0, at=at)

    assert report.above == ()
    assert [c.name for c in report.below] == ["PDL"]


def test_a_level_taken_after_the_bar_being_read_still_stands_at_that_bar():
    # Reading a future `taken_at` as though it were the present is exactly the
    # lookahead this filter exists to prevent: at 04:00 that level had not been
    # taken, and the chart at 04:00 is what is being described.
    at = ny(2025, 6, 11, 4)
    levels = [Level("PDH", 3450.0, ny(2025, 6, 11), ny(2025, 6, 11, 9))]

    assert [c.name for c in dol_candidates(levels, 3400.0, at).above] == ["PDH"]
    assert dol_candidates(levels, 3400.0, ny(2025, 6, 11, 10)).above == ()


def test_inducement_is_not_shipped_and_the_module_says_why():
    """An honest absence, pinned so nobody quietly adds a field that reads ahead.

    Identifying an inducement needs the move that came AFTER the level was taken,
    so it is never available at decision time; every definition of it needs a
    window this project would have to invent; and the one definition that needs
    no invented number is an object the engine already emits as an MSS with its
    `swept_at`. See PART THREE of the module docstring.
    """
    assert not [name for name in dir(liquidity) if "inducement" in name.lower()]
    assert liquidity.__doc__ is not None
    assert "INDUCEMENT IS NOT SHIPPED" in liquidity.__doc__


# --------------------------------------------------------- the label column


#: Advance width of the canvas label font, MEASURED rather than assumed.
#:
#: `levels-primitive.ts` sets `10px ui-monospace, monospace` and draws the ray tag
#: left-aligned from the label column with no clamp, so anything wider than the
#: column is cut off by the edge of the canvas. Measured in that exact font in a
#: real browser: "PDH" is 16.5px and "PREM 0.75" is 49.5px - 5.5px per character
#: on the nose, which is what monospace means.
LABEL_ADVANCE_PX = 5.5

#: The `pad = 4 * kx` the primitive adds to the label's COLLISION RECT.
#:
#: Four, not two, and the two was a real off-by-one in this budget. The rect is
#: `{x: gutter, w: measureText(tag) + pad}` and it has to fit inside the gutter, so
#: the text may use `LABEL_GUTTER - pad` and not `LABEL_GUTTER - pad / 2`. Half the
#: pad is the offset the TEXT is drawn at; the whole pad is what the rect spends.
#: At 2 this function returned a budget of 8 characters, and an 8-character name
#: measures 44px against a 42px allowance - a rect ending 2px past the pane edge,
#: which `e2e/labels.mjs` fails as a claim cut in half by the edge. Every shipped
#: name is 7 or shorter, so nothing had to be renamed; the gate was simply letting
#: the next one through.
LABEL_PAD_PX = 4.0


def _label_budget() -> int:
    """How many characters fit, read from the TypeScript rather than restated.

    `LABEL_GUTTER` lives in `structure-primitive.ts` and is shared by every
    primitive that writes in the name column. Reading it here is the same seam
    `test_every_degree_has_an_ink_weight_on_the_canvas` uses: the authority on the
    vocabulary is Python and the authority on the column width is TypeScript, and
    a constant copied into both is a constant that will disagree.
    """
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "components"
        / "structure-primitive.ts"
    ).read_text(encoding="utf-8")
    match = re.search(r"LABEL_GUTTER\s*=\s*(\d+)", source)
    assert match, "LABEL_GUTTER is no longer declared in structure-primitive.ts"
    return int((int(match.group(1)) - LABEL_PAD_PX) // LABEL_ADVANCE_PX)


def test_every_level_name_fits_the_canvas_label_column():
    """A name too wide for the column is silently cut in half on the chart.

    THIS WAS SHIPPING. Four names - `FRIDAY_HIGH`, `FRIDAY_LOW`, `MONDAY_HIGH`,
    `MONDAY_LOW`, at 10 and 11 characters against a budget of 8 - had been drawing
    truncated on every chart where a reader selected the friday or monday period,
    and `range_high` did the same the moment the dealing-range frame reached the
    canvas: it rendered as `range_hi`. Nothing warned. The label simply ran off the
    edge, and a truncated name is worse than a missing one, because `FRIDAY_HI`
    still looks like a label somebody meant to write.

    Every name the engine can emit is checked, not a sample: the period names from
    `NAMES`, the dealing range's two extremes and its three derived lines.
    """
    budget = _label_budget()
    assert budget >= 6, f"the label column has shrunk to {budget} characters"

    names = {name for pair in liquidity.NAMES.values() for name in pair}

    # The range frame's five, built from a real range rather than typed out, so a
    # renamed or added line is covered without editing this test.
    candles = [
        Candle(time=i * HOUR, open=100.0, high=100.0 + i % 7, low=99.0 - i % 5, close=100.0)
        for i in range(400)
    ]
    found = range_liquidity(candles, swing_n=3)
    assert found is not None, "the fixture must produce a range to name"
    names |= {level.name for level in found.external}
    names |= {level.name for level in liquidity.range_frame(found)}

    too_wide = sorted(
        f"{name} ({len(name)}ch, {len(name) * LABEL_ADVANCE_PX:.1f}px)"
        for name in names
        if len(name) > budget
    )
    assert not too_wide, (
        f"level names wider than the {budget}-character label column, so the "
        f"canvas cuts them off:\n  " + "\n  ".join(too_wide)
    )


# ------------------------------------ relative equal highs and lows (REQH/REQL)


def _shelf_series(peaks: list[float], pad: int = 12, warmup: int = 260) -> list[Candle]:
    """A flat series with one spike per entry in `peaks`.

    Flat between spikes on purpose: every swing is then unambiguous and the ATR is
    a known constant, so the tolerance the shelf is judged against is arithmetic
    rather than whatever the fixture happened to produce.
    """
    rows = [
        Candle(time=i * HOUR, open=49.5, high=50.0, low=49.0, close=49.5, volume=1.0)
        for i in range(warmup)
    ]
    for peak in peaks:
        for _ in range(pad):
            rows.append(
                Candle(
                    time=len(rows) * HOUR, open=49.5, high=50.0, low=49.0,
                    close=49.5, volume=1.0,
                )
            )
        rows.append(
            Candle(
                time=len(rows) * HOUR, open=49.5, high=peak, low=49.0,
                close=49.5, volume=1.0,
            )
        )
        for _ in range(pad):
            rows.append(
                Candle(
                    time=len(rows) * HOUR, open=49.5, high=50.0, low=49.0,
                    close=49.5, volume=1.0,
                )
            )
    for _ in range(30):
        rows.append(
            Candle(
                time=len(rows) * HOUR, open=49.5, high=50.0, low=49.0,
                close=49.5, volume=1.0,
            )
        )
    return rows


def test_a_lower_high_in_between_does_not_break_the_shelf():
    """THE DEFECT THIS FUNCTION WAS REWRITTEN AFTER, and it found nothing at all.

    Highs at 100.00, then a LOWER high at 95.00, then 100.05. A reader sees one
    two-touch shelf at 100 and would act on it. The first version of
    `equal_levels` grouped CONSECUTIVE swings and broke the run the moment one
    fell outside the band, so it emitted no shelf here - measured on this exact
    series before the rewrite. On 3000 bars of real gold the run version found 4
    shelves where the cluster version finds 20, so it was missing most of them.
    """
    found = liquidity.equal_levels(
        _shelf_series([100.0, 95.0, 100.05]), swing_n=5, min_touches=2
    )
    highs = [level for level in found if level.name.startswith("REQH")]
    assert len(highs) == 1, [level.name for level in found]
    assert highs[0].price == pytest.approx(100.0)
    assert highs[0].name == "REQH 2x", "the touch count is the information"


def test_the_shelf_price_is_the_first_member_not_the_running_mean():
    """A mean moves every time another swing joins, which would be a drawn line
    sliding under the reader as bars arrive. The anchor never moves."""
    found = liquidity.equal_levels(
        _shelf_series([100.0, 100.04, 100.08]), swing_n=5, min_touches=2
    )
    highs = [level for level in found if level.name.startswith("REQH")]
    assert len(highs) == 1 and highs[0].name == "REQH 3x"
    assert highs[0].price == pytest.approx(100.0), (
        "anchored to the first member; the mean of these three is 100.04"
    )


def test_swings_further_apart_than_the_tolerance_are_two_shelves_or_none():
    """The tolerance has to actually bite, or this function reports every pair of
    swings as equal and says nothing."""
    # 100 and 106 on a series whose ATR is about 1, so six ATR apart.
    found = liquidity.equal_levels(
        _shelf_series([100.0, 106.0]), swing_n=5, min_touches=2
    )
    assert not [level for level in found if level.name.startswith("REQH")], (
        "two swings six ATR apart are not an equal high"
    )


def test_the_tolerance_does_not_depend_on_how_many_bars_were_loaded():
    """THE RULE THIS ENGINE REFUSES, asserted directly.

    One of the two tolerances in circulation among open-source implementations is
    `0.01 x (dataset high - dataset low)`, a fraction of the LOADED WINDOW. Under
    that rule the same two swings stop being equal, or start being equal, when the
    reader changes the Bars picker and no candle has moved - and both charts look
    correct. This engine's tolerance is ATR-relative, so a longer window that adds
    only quiet bars cannot change the verdict on a shelf inside it.
    """
    base = _shelf_series([100.0, 100.05])
    # A far taller swing appended LATER cannot reach back and unmake the shelf.
    taller = base + _shelf_series([400.0], warmup=0)
    a = [level for level in liquidity.equal_levels(base, swing_n=5) if level.name.startswith("REQH")]
    b = [level for level in liquidity.equal_levels(taller, swing_n=5) if level.name.startswith("REQH")]
    assert a, "the fixture must produce a shelf to begin with"
    assert any(
        level.price == pytest.approx(a[0].price) and level.name == a[0].name for level in b
    ), (
        "a shelf changed when a taller swing was appended outside it, so the "
        "tolerance is reading the window's range rather than ATR"
    )


def test_a_shelf_is_not_knowable_before_its_second_member_confirmed():
    """A swing high at bar i is not knowable at i. A SHELF is not knowable until
    the member that proved it was one has confirmed, which is later still."""
    rows = _shelf_series([100.0, 100.05])
    found = [
        level
        for level in liquidity.equal_levels(rows, swing_n=5)
        if level.name.startswith("REQH")
    ]
    assert found
    # The second spike's own bar, found by price rather than by index arithmetic.
    second = max(
        (candle for candle in rows if candle.high == pytest.approx(100.05)),
        key=lambda c: c.time,
    )
    assert found[0].knowable_at > second.time, (
        f"knowable at {found[0].knowable_at} but the second member printed at "
        f"{second.time}"
    )


def test_a_single_swing_is_not_a_shelf():
    """`detect.structure` already draws swings. One of them is not resting
    liquidity at a level, it is a level."""
    found = liquidity.equal_levels(_shelf_series([100.0]), swing_n=5, min_touches=2)
    assert not [level for level in found if level.name.startswith("REQH")]


def test_a_shelf_traded_through_is_reported_as_taken_rather_than_dropped():
    """The same rule every other level here follows: "that shelf already got
    swept" is the fact that kills an idea, so removing it removes the reason."""
    rows = _shelf_series([100.0, 100.05, 120.0])
    found = [
        level
        for level in liquidity.equal_levels(rows, swing_n=5)
        if level.name.startswith("REQH") and level.price == pytest.approx(100.0)
    ]
    assert found, "the shelf must still be reported after being taken"
    assert found[0].taken_at is not None
