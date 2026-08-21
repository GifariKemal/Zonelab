"""The clock-anchored premium/discount reading, and the session liquidity pools.

Two tests here earn the file on their own.

The first is the DISAGREEMENT test. The anchor of this reading is single-sourced,
so `premium_discount` returns every candidate rather than one boolean, and the
test constructs a bar where the running parent cycle says discount while the last
closed quarter says premium. If that assertion ever has to be relaxed, the module
has started hiding the thing it exists to disclose.

The second is the MIDNIGHT test. The Asian window is 19:00 to 00:00 New York, so
it opens on one calendar date and closes on the next. An implementation that
builds both edges from the same date measures an empty five-hour span backwards
and every Asian pool in the product is wrong, silently. The DST pair beside it is
the same class of failure: the windows are wall clock, so on 2025-03-09 the
London killzone is two real hours because 02:00 New York does not exist that day.

Nothing here asserts that either item predicts anything. A pool is a price a
session made, and "in discount" is a position in a range.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_pools.py -q
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.clock import NY, to_ny
from app.models import Anatomy, Candle, Zone, ZoneKind, ZoneSide, ZoneState
from app.pools import liquidity_pools, premium_discount, zone_targets

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


def bar(t: int, high: float, low: float, close: float | None = None) -> Candle:
    return Candle(
        time=t,
        open=(high + low) / 2,
        high=high,
        low=low,
        close=(high + low) / 2 if close is None else close,
    )


def flat(start: int, end: int, high: float, low: float) -> list[Candle]:
    """Hourly bars over [start, end) that all share one high and low."""
    return [bar(t, high, low) for t in range(start, end, HOUR)]


def zone(zone_id: str, proximal: float, touched_at: int | None) -> Zone:
    """A zone reduced to the fields a target reads: id, proximal, first touch."""
    return Zone(
        id=zone_id,
        kind=ZoneKind.FVG,
        side=ZoneSide.DEMAND,
        state=ZoneState.FRESH if touched_at is None else ZoneState.TESTED,
        top=proximal,
        bottom=proximal - 5.0,
        proximal=proximal,
        distal=proximal - 5.0,
        time_from=ny(2025, 6, 10, 20),
        time_to=ny(2025, 6, 11, 12),
        formation_score=0.5,
        departure_atr=2.0,
        first_test_time=touched_at,
        anatomy=ANATOMY,
    )


# --------------------------------------------------------------------------- #
# Part one: the time-defined premium and discount
# --------------------------------------------------------------------------- #


def test_the_reading_is_price_against_the_fifty_percent_of_the_parent_cycle_range():
    # Traded degree `session`, so the anchor cycle is the DAY: 18:00 to 18:00.
    # The range is 3350..3450 by construction, so the line is exactly 3400 and
    # the arithmetic is checkable by hand.
    candles = flat(ny(2025, 6, 10, 18), ny(2025, 6, 11, 2), 3450.0, 3350.0)
    candles.append(bar(ny(2025, 6, 11, 2), 3380.0, 3370.0, close=3375.0))

    report = premium_discount(candles, degree="session")

    assert report is not None
    assert report.chosen is not None
    assert report.chosen.degree == "day"
    assert report.chosen.time_from == ny(2025, 6, 10, 18)
    assert (report.chosen.high, report.chosen.low) == (3450.0, 3350.0)
    assert report.chosen.equilibrium == 3400.0
    assert report.price == 3375.0
    assert report.chosen.position == 0.25
    assert report.chosen.reading == "discount"
    # The parent cycle has not closed, and the object says so rather than
    # presenting a still-growing range as settled.
    assert report.chosen.complete is False


def test_price_above_the_fifty_percent_line_reads_premium():
    candles = flat(ny(2025, 6, 10, 18), ny(2025, 6, 11, 2), 3450.0, 3350.0)
    candles.append(bar(ny(2025, 6, 11, 2), 3430.0, 3420.0, close=3425.0))

    report = premium_discount(candles, degree="session")

    assert report is not None and report.chosen is not None
    assert report.chosen.position == 0.75
    assert report.chosen.reading == "premium"


def test_the_parent_cycle_and_the_previous_quarter_anchors_disagree_on_one_bar():
    # Q1 of the day cycle (18:00 to midnight) sits low, 3350..3360. Q2 then runs
    # up to 3450. Reading at 02:00 with price 3375:
    #   parent_cycle      range 3350..3450, line 3400  ->  DISCOUNT
    #   previous_quarter  range 3350..3360, line 3355  ->  PREMIUM
    # Same bar, same price, opposite words. This is the entire reason the module
    # returns every candidate instead of one boolean.
    candles = flat(ny(2025, 6, 10, 18), ny(2025, 6, 11), 3360.0, 3350.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 2), 3450.0, 3400.0)
    candles.append(bar(ny(2025, 6, 11, 2), 3380.0, 3370.0, close=3375.0))

    report = premium_discount(candles, degree="session")

    assert report is not None
    by_anchor = {r.anchor: r for r in report.readings}
    assert by_anchor["parent_cycle"].reading == "discount"
    assert by_anchor["previous_quarter"].reading == "premium"
    assert by_anchor["previous_quarter"].time_from == ny(2025, 6, 10, 18)
    assert by_anchor["previous_quarter"].complete is True
    assert report.disagree is True


def test_every_candidate_anchor_is_reported_beside_the_chosen_one():
    candles = flat(ny(2025, 6, 9, 18), ny(2025, 6, 11, 2), 3450.0, 3350.0)

    report = premium_discount(candles, degree="session", anchor="parent_previous")

    assert report is not None
    assert report.anchor == "parent_previous"
    assert report.chosen is not None
    assert report.chosen.anchor == "parent_previous"
    # The previous day cycle is whole and closed; the running one is not.
    assert report.chosen.time_from == ny(2025, 6, 9, 18)
    assert report.chosen.complete is True
    assert {r.anchor for r in report.readings} == {
        "parent_cycle",
        "parent_previous",
        "previous_quarter",
    }
    assert report.absent == ()


def test_an_anchor_whose_window_has_no_bars_is_named_absent_rather_than_guessed():
    # The feed starts at this day cycle's open, so the PREVIOUS day cycle has no
    # bars at all. Nothing is carried forward from it and no neighbouring window
    # is substituted; the anchor is simply reported as absent, with the reason.
    candles = flat(ny(2025, 6, 10, 18), ny(2025, 6, 11, 2), 3450.0, 3350.0)

    report = premium_discount(candles, degree="session")

    assert report is not None
    assert {r.anchor for r in report.readings} == {"parent_cycle", "previous_quarter"}
    assert len(report.absent) == 1
    assert report.absent[0].startswith("parent_previous: no bars")


def test_the_year_degree_is_rejected_because_it_has_no_degree_above_it():
    candles = flat(ny(2025, 6, 10, 18), ny(2025, 6, 10, 22), 3450.0, 3350.0)

    with pytest.raises(ValueError):
        premium_discount(candles, degree="year")
    with pytest.raises(ValueError):
        premium_discount(candles, degree="fortnight")
    with pytest.raises(ValueError):
        premium_discount(candles, degree="session", anchor="last_swing")


def test_the_reading_is_taken_on_the_bar_asked_for_and_not_on_the_newest_one():
    candles = flat(ny(2025, 6, 10, 18), ny(2025, 6, 11), 3360.0, 3350.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 4), 3450.0, 3440.0)

    early = premium_discount(candles, degree="session", at=ny(2025, 6, 10, 20))
    late = premium_discount(candles, degree="session")

    assert early is not None and late is not None
    assert early.at == ny(2025, 6, 10, 20)
    assert late.at == ny(2025, 6, 11, 3)
    # The early bar cannot see the 3450 high that printed after it.
    assert early.chosen is not None and early.chosen.high == 3360.0
    assert late.chosen is not None and late.chosen.high == 3450.0


def test_a_friday_read_at_the_day_degree_has_no_week_cycle_and_so_no_reading():
    # Friday belongs to no quarter of the week, so a day-degree reading on Friday
    # has no parent cycle at all. Every anchor is absent and nothing is folded
    # into Thursday's cycle to manufacture an answer.
    candles = flat(ny(2025, 6, 13, 12), ny(2025, 6, 13, 16), 3450.0, 3350.0)

    report = premium_discount(candles, degree="day")

    assert report is not None
    assert report.readings == ()
    assert report.chosen is None
    assert report.disagree is False
    assert len(report.absent) == 3
    assert all("no week cycle" in reason for reason in report.absent)


def test_no_candles_and_a_bar_before_the_series_both_give_no_reading():
    candles = flat(ny(2025, 6, 10, 18), ny(2025, 6, 10, 22), 3450.0, 3350.0)

    assert premium_discount([], degree="session") is None
    assert premium_discount(candles, degree="session", at=ny(2025, 6, 1)) is None


# --------------------------------------------------------------------------- #
# Part two: liquidity pools
# --------------------------------------------------------------------------- #


def test_the_asian_high_is_measured_across_the_new_york_midnight_boundary():
    # 19:00 on the 10th to 00:00 on the 11th. The high sits at 22:00, which is
    # before midnight, and the low at 01:00, which is AFTER the window closed and
    # must not be in it.
    candles = flat(ny(2025, 6, 10, 19), ny(2025, 6, 10, 22), 3410.0, 3390.0)
    candles.append(bar(ny(2025, 6, 10, 22), 3450.0, 3400.0))
    candles += flat(ny(2025, 6, 10, 23), ny(2025, 6, 11), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 2), 3395.0, 3300.0)

    pools = liquidity_pools(candles, sessions=("asia",))

    assert len(pools) == 2
    assert [p.side for p in pools] == ["BSL", "SSL"]
    assert pools[0].window_from == ny(2025, 6, 10, 19)
    assert pools[0].window_to == ny(2025, 6, 11)  # midnight of the NEXT date
    assert pools[0].window_to - pools[0].window_from == 5 * HOUR
    assert pools[0].price == 3450.0
    assert pools[1].price == 3390.0  # not the 3300 low, which printed after
    assert pools[0].bars == 5 and pools[0].covered is True
    assert pools[0].knowable_at == ny(2025, 6, 11)


def test_the_london_killzone_is_02_00_to_05_00_new_york():
    candles = flat(ny(2025, 6, 10, 1), ny(2025, 6, 10, 2), 3500.0, 3200.0)
    candles += flat(ny(2025, 6, 10, 2), ny(2025, 6, 10, 5), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 10, 5), ny(2025, 6, 10, 7), 3405.0, 3395.0)

    pools = liquidity_pools(candles, sessions=("london",))

    assert len(pools) == 2
    assert pools[0].window_from == ny(2025, 6, 10, 2)
    assert pools[0].window_to == ny(2025, 6, 10, 5)
    # The 01:00 bar is an hour before the killzone opens and is excluded, so its
    # far wider range is not the London range.
    assert (pools[0].price, pools[1].price) == (3410.0, 3390.0)


def test_the_london_window_loses_the_hour_that_does_not_exist_on_the_spring_forward_day():
    # 2025-03-09: 02:00 EST becomes 03:00 EDT, so 02:00 New York never happens.
    # The window is wall clock, so with fold=0 its open lands on the pre-transition
    # offset - 03:00 EDT - and the killzone is two real hours that day rather than
    # three. Stated in the module docstring; asserted here so it cannot drift.
    candles = flat(ny(2025, 3, 9, 1), ny(2025, 3, 9, 7), 3410.0, 3390.0)

    pools = liquidity_pools(candles, sessions=("london",))

    assert pools
    assert to_ny(pools[0].window_from).hour == 3
    assert to_ny(pools[0].window_to).hour == 5
    assert pools[0].window_to - pools[0].window_from == 2 * HOUR
    assert pools[0].bars == 2


def test_the_asian_window_on_the_autumn_fall_back_day_is_still_five_wall_clock_hours():
    # The repeated hour on 2025-11-02 falls between 01:00 and 02:00, which is
    # outside both windows, so the Asian window that opened at 19:00 on the 1st
    # closes at midnight and spans five hours even though the day runs 25.
    candles = flat(ny(2025, 11, 1, 19), ny(2025, 11, 2, 3), 3410.0, 3390.0)

    pools = liquidity_pools(candles, sessions=("asia",))

    assert pools
    assert to_ny(pools[0].window_from).utcoffset() != to_ny(ny(2025, 11, 2, 3)).utcoffset()
    assert pools[0].window_from == ny(2025, 11, 1, 19)
    assert pools[0].window_to == ny(2025, 11, 2)
    assert pools[0].window_to - pools[0].window_from == 5 * HOUR


def test_a_pool_is_taken_by_the_first_bar_that_pierced_it_and_not_a_later_one():
    candles = flat(ny(2025, 6, 10, 19), ny(2025, 6, 11), 3410.0, 3390.0)
    candles.append(bar(ny(2025, 6, 11), 3405.0, 3395.0))
    first = bar(ny(2025, 6, 11, 1), 3420.0, 3400.0)  # takes the 3410 BSL
    later = bar(ny(2025, 6, 11, 2), 3480.0, 3400.0)  # takes it again, much harder
    candles += [first, later]

    pools = liquidity_pools(candles, sessions=("asia",))
    bsl = next(p for p in pools if p.side == "BSL")

    assert bsl.price == 3410.0
    assert bsl.taken_at == first.time
    assert bsl.taken_at != later.time


def test_a_pool_price_never_traded_through_still_stands_and_reports_none():
    candles = flat(ny(2025, 6, 10, 19), ny(2025, 6, 11), 3410.0, 3390.0)
    # Every later bar sits strictly inside the session range, and one prints an
    # EQUAL high: a touch is not a take, so the pool still stands.
    candles += [
        bar(ny(2025, 6, 11), 3410.0, 3395.0),
        bar(ny(2025, 6, 11, 1), 3405.0, 3390.0),
    ]

    pools = liquidity_pools(candles, sessions=("asia",))

    assert len(pools) == 2
    assert all(p.taken_at is None for p in pools)


def test_a_holiday_with_no_bars_in_the_window_produces_no_pool_at_all():
    # A feed that skips the 10th entirely: bars before its Asian window and bars
    # long after it. The window is never widened to find a bar, and no price is
    # carried over from the session that did trade.
    candles = flat(ny(2025, 6, 10, 12), ny(2025, 6, 10, 17), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 11, 19), ny(2025, 6, 12, 2), 3420.0, 3380.0)

    pools = liquidity_pools(candles, sessions=("asia",))

    assert [p.window_from for p in pools] == [ny(2025, 6, 11, 19)] * 2


def test_a_partial_window_reports_its_coverage_rather_than_a_wrong_high():
    # The feed only covers 21:00 to 00:00, so the high of those bars is NOT the
    # Asian high. The pool is still reported - the bars do exist - but `covered`
    # is False and the coverage fields say exactly what was measured.
    candles = flat(ny(2025, 6, 10, 21), ny(2025, 6, 11), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 2), 3405.0, 3395.0)

    pools = liquidity_pools(candles, sessions=("asia",))
    full = liquidity_pools(
        flat(ny(2025, 6, 10, 19), ny(2025, 6, 11), 3410.0, 3390.0)
        + flat(ny(2025, 6, 11), ny(2025, 6, 11, 2), 3405.0, 3395.0),
        sessions=("asia",),
    )

    assert pools[0].covered is False
    assert pools[0].window_from == ny(2025, 6, 10, 19)
    assert pools[0].first_bar == ny(2025, 6, 10, 21)
    assert pools[0].bars == 3
    # The same window with every bar present reads covered, so the flag is
    # tracking the coverage and not some constant.
    assert full[0].covered is True and full[0].bars == 5


def test_a_session_extreme_is_not_reported_until_a_bar_proves_the_session_closed():
    # Truncation rather than intent: the answer computed from bars up to the
    # knowable instant must equal the answer from the whole series, and the
    # answer one bar earlier must not exist at all.
    candles = flat(ny(2025, 6, 10, 19), ny(2025, 6, 11), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 2), 3405.0, 3395.0)

    inside_only = liquidity_pools(candles[:5], sessions=("asia",))
    at_close = liquidity_pools(candles[:6], sessions=("asia",))

    assert inside_only == []
    assert at_close
    assert at_close[0].knowable_at == ny(2025, 6, 11)
    assert [p.price for p in at_close] == [3410.0, 3390.0]
    # And the pool that exists at the close bar is the same object the full
    # series reports, aside from the takes that happened later.
    full = liquidity_pools(candles, sessions=("asia",))
    assert [(p.side, p.price, p.window_from) for p in full] == [
        (p.side, p.price, p.window_from) for p in at_close
    ]


def test_both_sessions_come_back_in_time_order_and_name_themselves():
    candles = flat(ny(2025, 6, 10, 19), ny(2025, 6, 11), 3410.0, 3390.0)
    candles += flat(ny(2025, 6, 11), ny(2025, 6, 11, 7), 3450.0, 3350.0)

    pools = liquidity_pools(candles)

    assert [p.session for p in pools] == ["asia", "asia", "london", "london"]
    assert [p.window_from for p in pools] == sorted(p.window_from for p in pools)


def test_an_unknown_session_name_is_rejected_rather_than_silently_skipped():
    candles = flat(ny(2025, 6, 10, 19), ny(2025, 6, 11, 2), 3410.0, 3390.0)

    with pytest.raises(ValueError):
        liquidity_pools(candles, sessions=("newyork",))


def test_no_candles_produce_no_pools():
    assert liquidity_pools([]) == []


# --------------------------------------------------------------------------- #
# Zones as targets
# --------------------------------------------------------------------------- #


def test_zone_targets_keep_the_untouched_ones_and_report_the_taken_ones_as_history():
    touched_at = ny(2025, 6, 11, 4)
    targets = zone_targets(
        [zone("fvg-1", 3400.0, None), zone("fvg-2", 3380.0, touched_at)]
    )

    standing = [t for t in targets if t.taken_at is None]

    assert [t.zone_id for t in targets] == ["fvg-1", "fvg-2"]
    assert [t.zone_id for t in standing] == ["fvg-1"]
    assert targets[0].price == 3400.0  # the proximal line, the edge price meets
    assert targets[1].taken_at == touched_at
    assert targets[1].kind == "FVG"


def test_no_zones_produce_no_targets():
    assert zone_targets([]) == []


def test_one_stray_timestamp_cannot_make_a_complete_session_look_partial():
    """The feed's bar interval is the MODAL gap, never the smallest.

    This is a regression test for a real defect that reached the screen. `_step`
    took the smallest gap, reasoning that missing bars only make gaps larger so
    the minimum survives them, and that under-reporting the step merely made
    `covered` stricter. But on 500 bars of Yahoo 15m gold the gap is 900 seconds
    493 times and 899 exactly ONCE, so the minimum adopted that single
    one-second irregularity as the interval - a full five-hour Asian window then
    measured 20 x 899 against 18.000 and came back partial. Every pool ray on the
    chart was tagged "not covered" while every window was in fact complete.

    "Stricter" is not the safe direction when the flag's whole job is to say THIS
    high is not the session high. Firing it on a complete session tells the reader
    the opposite of the truth.
    """
    from app import clock
    from app.models import Candle
    from app.pools import liquidity_pools

    step = 900
    # A full Asian window, 19:00 to 00:00 New York, plus one bar after it so the
    # session can be proven closed.
    start = clock.at_ny_hour(clock.ny_wall(2026, 6, 2, 12), 19)
    rows = [
        Candle(
            time=start + i * step,
            open=100.0, high=101.0 + i * 0.01, low=99.0 - i * 0.01, close=100.5,
            volume=1.0,
        )
        for i in range(21)
    ]
    # One timestamp a single second early, exactly as the live feed had it. It is
    # the only irregular gap in the series and it must not decide anything.
    rows[10] = Candle(
        time=rows[10].time - 1, open=100.0, high=101.1, low=98.9, close=100.5, volume=1.0
    )

    pools = liquidity_pools(rows, ["asia"])
    assert pools, "the window had 20 bars and must produce a pool"
    assert all(p.covered for p in pools), [
        (p.side, p.bars, p.covered) for p in pools
    ]
