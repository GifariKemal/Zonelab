"""The quarter grid, on dates whose correct answer comes from the calendar.

The test that earns this file is the DST pair. The grid is stated in New York
wall clock - 18:00, 00:00, 06:00, 12:00 - so on 2025-03-09 the day cycle is 23
hours and on 2025-11-02 it is 25, and the Q2 quarter that is nominally six hours
is really five and then seven. A fixed-offset implementation passes every other
test in this file and fails those two, which is exactly how it would behave in
production: right for half the year, an hour wrong for the other half, and
silent about which.

Nothing here asserts that a true open predicts anything. It is a horizontal line
at a defined instant, drawn only when a bar exists to draw it from.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_quarters.py -q
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.clock import NY, to_ny
from app.models import Candle
from app.providers.synthetic import generate
from app.quarters import (
    ALL_DEGREES,
    DEGREES,
    TrueOpen,
    quarters,
    stacked_opens,
    true_opens,
)

#: Jam dinding dibekukan untuk fixture sintetik: Kamis 2026-05-28 16:26 NY, hari
#: kerja di tengah sesi. `generate` menambatkan grid-nya ke waktu nyata dan
#: `_session_grid` melompati jam pasar tutup, jadi bar mana yang jatuh di mana
#: bergerak dengan hari kalender saat test dijalankan. Satu test di repo ini lolos
#: berbulan-bulan lalu mulai gagal stabil karena itu, tanpa fixture-nya berubah.
FROZEN_NOW = 1780000000

HOUR = 3600


def ny(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    """Epoch of a New York wall-clock time, built here rather than imported.

    Deliberately not `clock.ny_wall`: the expected values must come from the
    calendar independently of the code under test.
    """
    return int(datetime(year, month, day, hour, minute, tzinfo=NY).timestamp())


def hourly(start: int, end: int, skip: tuple[int, ...] = ()) -> list[Candle]:
    """Hourly bars over [start, end), each with a unique open, minus `skip`."""
    return [
        Candle(
            time=t,
            open=3400.0 + (t - start) // HOUR,
            high=3401.0 + (t - start) // HOUR,
            low=3399.0 + (t - start) // HOUR,
            close=3400.0 + (t - start) // HOUR,
        )
        for t in range(start, end, HOUR)
        if t not in skip
    ]


def on_boundaries(starts: list[int]) -> list[Candle]:
    """One bar opening EXACTLY on each given instant, each with its own price.

    The nano boundaries land on seconds no feed emits, so the only way to test
    the level is to build the bar that would carry it.
    """
    return [
        Candle(
            time=t,
            open=3400.0 + i,
            high=3401.0 + i,
            low=3399.0 + i,
            close=3400.0 + i,
        )
        for i, t in enumerate(starts)
    ]


def wall(epoch: int) -> tuple[int, int, int]:
    when = to_ny(epoch)
    return when.hour, when.minute, when.second


def test_the_day_quarters_open_at_18_00_midnight_06_00_and_12_00_new_york():
    day = quarters("day", ny(2025, 6, 10, 20), ny(2025, 6, 11, 13))

    assert [q.label for q in day] == ["Q1", "Q2", "Q3", "Q4"]
    assert [wall(q.start)[0] for q in day] == [18, 0, 6, 12]
    assert day[0].start == ny(2025, 6, 10, 18)
    assert day[1].start == ny(2025, 6, 11, 0)
    assert day[3].end == ny(2025, 6, 11, 18)


def test_the_quarters_of_a_cycle_tile_it_with_no_gap_and_no_overlap():
    day = quarters("day", ny(2025, 6, 10, 19), ny(2025, 6, 11, 12))
    for earlier, later in zip(day, day[1:]):
        assert earlier.end == later.start


def test_the_spring_forward_day_keeps_its_wall_clock_boundaries_and_runs_23_hours():
    # 2025-03-09: 02:00 EST becomes 03:00 EDT, so the day cycle that opened at
    # 18:00 on the 8th at UTC-5 closes at 18:00 on the 9th at UTC-4.
    day = quarters("day", ny(2025, 3, 8, 18), ny(2025, 3, 9, 17))
    cycle = [q for q in day if q.start >= ny(2025, 3, 8, 18)][:4]

    assert [wall(q.start)[0] for q in cycle] == [18, 0, 6, 12]
    assert to_ny(cycle[0].start).utcoffset().total_seconds() == -5 * HOUR
    assert to_ny(cycle[2].start).utcoffset().total_seconds() == -4 * HOUR

    # The hour is lost inside Q2, which is five real hours rather than six. A
    # fixed-offset build reports 6 here and 6 in the autumn test, and is wrong
    # in both.
    assert cycle[1].end - cycle[1].start == 5 * HOUR
    assert cycle[3].end - cycle[0].start == 23 * HOUR


def test_the_autumn_fall_back_day_keeps_its_wall_clock_boundaries_and_runs_25_hours():
    day = quarters("day", ny(2025, 11, 1, 18), ny(2025, 11, 2, 17))
    cycle = [q for q in day if q.start >= ny(2025, 11, 1, 18)][:4]

    assert [wall(q.start)[0] for q in cycle] == [18, 0, 6, 12]
    assert to_ny(cycle[0].start).utcoffset().total_seconds() == -4 * HOUR
    assert to_ny(cycle[2].start).utcoffset().total_seconds() == -5 * HOUR

    assert cycle[1].end - cycle[1].start == 7 * HOUR
    assert cycle[3].end - cycle[0].start == 25 * HOUR


def test_the_true_day_open_is_the_q2_open_which_is_midnight_new_york():
    start, end = ny(2025, 6, 9, 12), ny(2025, 6, 11, 12)
    candles = hourly(start, end)

    opens = true_opens(candles, ("day",))

    assert [o.time for o in opens] == [ny(2025, 6, 10), ny(2025, 6, 11)]
    assert [wall(o.time)[0] for o in opens] == [0, 0]
    by_time = {c.time: c.open for c in candles}
    assert [o.price for o in opens] == [by_time[o.time] for o in opens]
    # And explicitly not 18:00, which is the cycle open rather than the true open.
    assert ny(2025, 6, 9, 18) not in {o.time for o in opens}


def test_a_true_open_with_no_bar_on_the_boundary_returns_nothing_rather_than_a_guess():
    start, end = ny(2025, 6, 9, 12), ny(2025, 6, 11, 12)
    missing = ny(2025, 6, 10)
    candles = hourly(start, end, skip=(missing,))

    opens = true_opens(candles, ("day",))

    # The 10th has no midnight bar, so it has no true open at all. The bar
    # before it is NOT carried forward and the two neighbours are NOT averaged.
    assert [o.time for o in opens] == [ny(2025, 6, 11)]


def test_a_weekend_gap_produces_no_true_open_for_the_days_with_no_bars():
    # Friday evening to Sunday evening, the shape every FX and gold feed has.
    candles = hourly(ny(2025, 6, 6, 12), ny(2025, 6, 6, 17)) + hourly(
        ny(2025, 6, 8, 18), ny(2025, 6, 9, 6)
    )

    opens = true_opens(candles, ("day",))

    assert [o.time for o in opens] == [ny(2025, 6, 9)]


def test_the_week_has_four_quarters_monday_to_thursday_and_friday_is_not_one():
    week = quarters("week", ny(2025, 3, 9, 18), ny(2025, 3, 14, 12))

    assert [q.label for q in week] == ["Q1", "Q2", "Q3", "Q4"]
    assert week[0].start == ny(2025, 3, 9, 18)  # Sunday 18:00 opens Monday
    assert week[3].end == ny(2025, 3, 13, 18)  # closes Thursday 18:00

    # Friday belongs to no week quarter. Not an off-by-one: the doctrine gives
    # the week four quarters, and there is deliberately no Q5.
    friday_noon = ny(2025, 3, 14, 12)
    assert not [q for q in week if q.start <= friday_noon < q.end]


def test_a_friday_is_still_a_day_cycle_even_though_it_is_no_week_quarter():
    friday = quarters("day", ny(2025, 3, 13, 18), ny(2025, 3, 14, 13))

    assert [q.label for q in friday] == ["Q1", "Q2", "Q3", "Q4"]
    assert friday[1].start == ny(2025, 3, 14)


def test_a_session_is_the_six_hour_quarter_split_into_four_90_minute_cycles():
    session = quarters("session", ny(2025, 6, 10, 6), ny(2025, 6, 10, 11, 59))

    assert [q.label for q in session] == ["Q1", "Q2", "Q3", "Q4"]
    assert all(q.end - q.start == 90 * 60 for q in session)
    assert session[0].start == ny(2025, 6, 10, 6)
    assert session[3].end == ny(2025, 6, 10, 12)


def test_a_90_minute_cycle_splits_into_four_micro_quarters_of_1350_seconds():
    micro = quarters("micro", ny(2025, 6, 10, 6), ny(2025, 6, 10, 7, 29))

    assert [q.label for q in micro] == ["Q1", "Q2", "Q3", "Q4"]
    assert all(q.end - q.start == 1350 for q in micro)

    # 22.5 minutes is 1350 whole SECONDS, so the half minute is exact and is
    # never rounded to a whole minute: the boundaries land on :22:30 and :67:30.
    assert [wall(q.start) for q in micro] == [
        (6, 0, 0),
        (6, 22, 30),
        (6, 45, 0),
        (7, 7, 30),
    ]


def test_the_micro_quarters_stretch_with_their_parent_on_a_transition_day():
    # The parent Q2 is five hours on 2025-03-09, so its 90-minute cycles are 75
    # minutes and its 22.5-minute micros are 1125 seconds. The nesting stays
    # exact; only the nominal length gives.
    session = quarters("session", ny(2025, 3, 9), ny(2025, 3, 9, 5, 59))
    micro = quarters("micro", ny(2025, 3, 9), ny(2025, 3, 9, 1, 14))

    assert all(q.end - q.start == 75 * 60 for q in session)
    assert all(q.end - q.start == 1125 for q in micro)


def test_the_year_quarters_open_in_january_april_july_and_october():
    year = quarters("year", ny(2024, 12, 31, 12), ny(2025, 1, 2))

    ends_2024 = [q for q in year if q.start < ny(2025, 1, 1)]
    starts_2025 = [q for q in year if q.start >= ny(2025, 1, 1)]

    assert [q.label for q in ends_2024] == ["Q4"]
    assert ends_2024[0].start == ny(2024, 10, 1)
    assert ends_2024[0].end == ny(2025, 1, 1) == starts_2025[0].start
    assert [q.label for q in starts_2025] == ["Q1"]


def test_the_true_year_open_is_the_april_open():
    candles = hourly(ny(2025, 3, 31, 20), ny(2025, 4, 1, 4))

    opens = true_opens(candles, ("year",))

    assert [o.time for o in opens] == [ny(2025, 4, 1)]
    assert opens[0].price == 3404.0  # the 5th hourly bar of the fixture


def test_the_month_quarters_are_the_four_weeks_from_the_months_first_monday():
    # March 2025 begins on a Saturday, so its first Monday is the 3rd and the
    # monthly cycle opens on Sunday the 2nd at 18:00.
    month = quarters("month", ny(2025, 3, 3), ny(2025, 3, 28))

    assert [q.label for q in month] == ["Q1", "Q2", "Q3", "Q4"]
    assert month[0].start == ny(2025, 3, 2, 18)
    assert month[3].end == ny(2025, 3, 30, 18)
    # 1 and 2 March precede the first Monday and belong to no monthly quarter.
    assert not [q for q in month if q.start <= ny(2025, 3, 1, 12) < q.end]


def test_a_monthly_quarter_across_the_spring_transition_is_an_hour_short_of_a_week():
    month = quarters("month", ny(2025, 3, 3), ny(2025, 3, 28))

    # Wall clock says seven days; the clock says 167 hours. Adding 7 * 86400
    # seconds instead would slide every later monthly boundary by an hour.
    assert month[0].end - month[0].start == 7 * 24 * HOUR - HOUR
    assert month[1].end - month[1].start == 7 * 24 * HOUR


def test_the_true_month_open_is_the_second_weeks_open():
    candles = hourly(ny(2025, 3, 9, 12), ny(2025, 3, 9, 23))

    opens = true_opens(candles, ("month",))

    assert [o.time for o in opens] == [ny(2025, 3, 9, 18)]


def test_an_unknown_degree_is_rejected_rather_than_silently_treated_as_a_day():
    with pytest.raises(ValueError):
        quarters("fortnight", ny(2025, 6, 10), ny(2025, 6, 11))


def test_a_micro_cycle_splits_into_four_nano_quarters_that_tile_it_exactly():
    base = ny(2025, 6, 10, 6)  # a micro cycle opens here: 22.5 minutes long
    nano = quarters("nano", base, base + 1349)

    assert [q.label for q in nano] == ["Q1", "Q2", "Q3", "Q4"]
    assert nano[0].start == base
    assert nano[3].end == base + 1350
    for earlier, later in zip(nano, nano[1:]):
        assert earlier.end == later.start


def test_the_337_and_a_half_second_nano_is_whole_seconds_that_still_tile_1350():
    base = ny(2025, 6, 10, 6)
    nano = quarters("nano", base, base + 1349)

    # 1350 / 4 is 337.5, so four EQUAL whole-second parts do not exist. The
    # module keeps the tiling and gives up the equality, never the other way
    # round: a half-second of equality is not what anything nests on.
    assert 1350 % 4 != 0
    spans = [q.end - q.start for q in nano]
    assert spans == [337, 338, 337, 338]
    assert sum(spans) == 1350  # the parent's span, exactly, with nothing over
    assert max(spans) - min(spans) == 1
    assert all(isinstance(q.start, int) for q in nano)


def test_the_nano_quarters_stretch_with_their_parent_on_a_transition_day():
    # On 2025-03-09 the day Q2 is five hours, its session quarters 75 minutes and
    # its micros 1125 seconds - so a nano there is 281.25 seconds, not 337.5. A
    # nano hardcoded to 337.5 (or to 337) tiles nothing on this day.
    base = ny(2025, 3, 9)
    nano = quarters("nano", base, base + 1124)

    spans = [q.end - q.start for q in nano]
    assert spans == [281, 281, 281, 282]
    assert sum(spans) == 1125
    assert nano[3].end == base + 1125


def test_every_nano_lies_wholly_inside_one_micro_quarter():
    start, end = ny(2025, 6, 10, 6), ny(2025, 6, 10, 12) - 1
    micro = quarters("micro", start, end)
    nano = quarters("nano", start, end)

    assert len(micro) == 16 and len(nano) == 4 * len(micro)
    assert all(any(m.start <= n.start and n.end <= m.end for m in micro) for n in nano)


def test_the_true_nano_open_is_the_q2_open_of_the_micro_cycle_it_quarters():
    base = ny(2025, 6, 10, 6)
    grid = quarters("nano", base, base + 1349)
    candles = on_boundaries([q.start for q in grid])

    opens = true_opens(candles, ("nano",))

    # Q2, one fourth into the 22.5-minute cycle: 337 seconds, not 337.5 and not
    # a rounded-up 338. And the level is that bar's own open price.
    assert [o.time for o in opens] == [base + 337]
    assert [o.degree for o in opens] == ["nano"]
    assert opens[0].price == candles[1].open


def test_a_nano_true_open_needs_a_bar_on_its_own_second_or_it_does_not_exist():
    base = ny(2025, 6, 10, 6)
    starts = [q.start for q in quarters("nano", base, base + 1349)]

    without = on_boundaries([t for t in starts if t != base + 337])
    one_second_late = on_boundaries([base, base + 338, base + 675, base + 1012])

    # Nothing is carried forward from Q1 and nothing is interpolated, and a bar
    # a single second off the boundary is not the bar on the boundary.
    assert true_opens(without, ("nano",)) == []
    assert true_opens(one_second_late, ("nano",)) == []


def test_a_nano_true_open_is_unchanged_when_the_bars_after_it_are_removed():
    base = ny(2025, 6, 10, 6)
    candles = on_boundaries([q.start for q in quarters("nano", base, base + 1349)])

    full = true_opens(candles, ("nano",))
    at_the_moment_it_became_knowable = true_opens(
        [c for c in candles if c.time <= base + 337], ("nano",)
    )

    assert full == at_the_moment_it_became_knowable != []


def test_the_two_extra_degrees_are_accepted_but_stay_out_of_the_six():
    """`DEGREES` is read elsewhere as an ordered parent chain (pools.py) and as a
    loop with a per-degree table of documented holes (tools/session_accuracy), so
    appending to it changes those files from inside this one. Both the finest
    degree and the coarsest therefore live in `ALL_DEGREES` only - nano below the
    six, quadrennial above them - and the tuple's exact shape is pinned so a
    careless insertion into the middle fails here rather than in pools."""
    assert "nano" not in DEGREES
    assert "quadrennial" not in DEGREES
    assert ALL_DEGREES == ("quadrennial",) + DEGREES + ("nano",)
    assert quarters("nano", ny(2025, 6, 10, 6), ny(2025, 6, 10, 6, 22))
    assert quarters("quadrennial", ny(2025, 6, 10), ny(2025, 6, 11))


def test_the_true_london_open_is_the_true_day_open_and_not_a_second_object():
    # The notes mark the London session's opening at 00:00 New York, and 00:00 is
    # the day cycle's Q2 open. TLO and TDO are one instant, one bar, one level.
    candles = hourly(ny(2025, 6, 9, 18), ny(2025, 6, 10, 12))
    day = quarters("day", ny(2025, 6, 9, 18), ny(2025, 6, 10, 12))
    london = [q for q in day if q.label == "Q2"][0]

    opens = true_opens(candles, ("day",))

    assert [o.time for o in opens] == [london.start] == [ny(2025, 6, 10)]
    # There is no separate degree for it, so it cannot be drawn twice and then
    # counted twice by anything that counts agreeing levels.
    with pytest.raises(ValueError):
        quarters("london", ny(2025, 6, 9), ny(2025, 6, 10))


def test_the_new_york_marking_at_06_00_is_a_q3_open_and_therefore_no_true_open():
    candles = hourly(ny(2025, 6, 9, 18), ny(2025, 6, 10, 12))
    six = ny(2025, 6, 10, 6)

    day = quarters("day", ny(2025, 6, 9, 18), ny(2025, 6, 10, 12))

    assert [q.label for q in day if q.start == six] == ["Q3"]
    # A bar opens exactly there, so the absence of a level is the definition
    # working - a true open is a Q2 open - and not a missing bar.
    assert six in {c.time for c in candles}
    assert six not in {o.time for o in true_opens(candles, ("day",))}


def test_two_true_opens_below_the_price_are_counted_and_named():
    week = TrueOpen("week", ny(2025, 6, 9, 18), 3400.0)
    month = TrueOpen("month", ny(2025, 6, 9, 18), 3390.0)
    day = TrueOpen("day", ny(2025, 6, 10), 3420.0)

    stack = stacked_opens(3410.0, [week, month, day])

    assert stack.below == (week, month)
    assert stack.above == (day,)
    assert (len(stack.below), len(stack.above)) == (2, 1)


def test_a_true_open_exactly_at_the_price_is_on_neither_side_of_it():
    level = TrueOpen("day", ny(2025, 6, 10), 3400.0)

    stack = stacked_opens(3400.0, [level])

    assert stack.above == () and stack.below == ()
    assert stacked_opens(3400.0, []) == stack


def test_every_true_open_on_a_generated_series_comes_from_a_bar_that_exists():
    candles = generate(bars=300, step=HOUR, now=FROZEN_NOW)
    times = {c.time for c in candles}

    opens = true_opens(candles, ("day", "week"))

    assert opens
    assert all(o.time in times for o in opens)
    assert all(wall(o.time)[0] == 0 for o in opens if o.degree == "day")
    assert all(wall(o.time)[0] == 18 for o in opens if o.degree == "week")


def test_the_quadrennial_cycle_puts_the_us_election_year_in_q2():
    """The rule, from the practitioner who named the omission: "Quadrennial: 1
    taun = satu cycle. Paling gampang ingat, q2 = PILPRES Amerika."

    US presidential elections fall on years divisible by four, so this is an
    anchor and not a fitted parameter: there is nothing here to tune. Q1 is the
    year before the election, Q3 the year after, Q4 two years after - which makes
    2023 Q1, 2024 Q2, 2025 Q3 and 2026 Q4.
    """
    found = quarters("quadrennial", ny(2022, 6, 1), ny(2029, 6, 1))
    labelled = {
        to_ny(q.start).year: q.label for q in found if to_ny(q.start).month == 1
    }
    assert labelled[2024] == "Q2", "2024 was an election year"
    assert labelled[2028] == "Q2", "so is 2028, one full cycle later"
    assert labelled[2023] == "Q1"
    assert labelled[2025] == "Q3"
    assert labelled[2026] == "Q4"

    # Each quarter is exactly one calendar year, and they tile without a gap.
    for q in found:
        assert to_ny(q.start).month == 1 and to_ny(q.start).day == 1
        assert to_ny(q.end).year == to_ny(q.start).year + 1
    for a, b in zip(found, found[1:]):
        assert a.end == b.start, "the cycle must tile, like every other degree"


def test_the_quadrennial_true_open_needs_the_approximate_rule_to_exist_at_all():
    """1 January is the one boundary that can never have a bar on it.

    This is the whole reason the flag exists. The strict rule - a bar opening
    EXACTLY on the boundary - is the default everywhere and is what every
    measurement in this project was taken under, but at this degree it is
    structurally unsatisfiable: the market is shut on 1 January every year.
    Measured on ten years of hourly broker gold, the strict rule returned zero
    quadrennial levels; with the flag it returns two, 19 and 18 hours late.

    Bars here are hourly and skip 1 January entirely, which is what the real feed
    does.
    """
    # THE WINDOW SPANS THE BOUNDARY, and it has to. Bars run from late December
    # through 3 January with 1 January absent, which is the real shape: the
    # market was shut on the holiday and the feed simply has no bar there. A
    # window that STARTED on 2 January would look identical from inside the
    # function and mean something different - "this data does not reach the
    # boundary" - and treating the two alike is what made seven levels repaint
    # when a window was extended leftward.
    candles = hourly(ny(2023, 12, 28), ny(2024, 1, 1)) + hourly(
        ny(2024, 1, 2), ny(2024, 1, 4)
    )

    strict = true_opens(candles, ("quadrennial",))
    assert strict == [], "no bar on the boundary means no level, and that is the default"

    loose = true_opens(candles, ("quadrennial",), approximate=True)
    assert len(loose) == 1, loose
    level = loose[0]
    assert level.approximate is True
    assert level.time == ny(2024, 1, 1), "the level belongs to its BOUNDARY"
    first_after = next(c for c in candles if c.time >= level.time)
    assert level.bar == first_after.time, "the price came from the first bar after it"
    assert level.bar > level.time
    assert level.price == first_after.open

    # AND IT MUST VANISH when the window no longer reaches the boundary, because
    # then nothing can tell a holiday from a short window.
    truncated = [c for c in candles if c.time > level.time]
    assert true_opens(truncated, ("quadrennial",), approximate=True) == [], (
        "a boundary outside the window is unknowable, not approximate"
    )


def test_the_approximate_true_open_never_reaches_backward_or_too_far_forward():
    """Two ways the fallback could lie, and it does neither.

    Backward would read a price from the PREVIOUS cycle and label it this one's
    open - the exact error the strict rule exists to prevent. Too far forward is
    the bug this test was written after finding: the 2016 quadrennial boundary
    took the first bar of the window, seven months later, and called it that
    cycle's open. The reach is bounded at 120 hours, measured from the longest
    real closure in the feed (96 hours, the Christmas and New Year weeks).
    """
    # The boundary is 1 January 2024. These bars start in March, months late.
    late = hourly(ny(2024, 3, 1), ny(2024, 3, 3))
    assert true_opens(late, ("quadrennial",), approximate=True) == [], (
        "a bar months after the boundary is not that boundary's open"
    )

    # And a window that opens BEFORE the boundary is fine: the boundary is inside
    # it, so the first bar at or after it is a real answer.
    across = hourly(ny(2023, 12, 28), ny(2024, 1, 3))
    got = true_opens(across, ("quadrennial",), approximate=True)
    assert len(got) == 1
    assert got[0].bar >= got[0].time, "never a bar from before the boundary"
    assert got[0].bar - got[0].time <= 120 * 3600


def test_the_approximate_reach_scales_with_the_bar_interval():
    """A coarse chart must not lose levels to a bound measured on a fine one.

    The 120-hour floor was measured from market CLOSURES, and on an intraday
    chart a closure is the only thing between a boundary and its next bar. Weekly
    bars open once every 168 hours, so a boundary can sit five days from the next
    open with the market never having shut - and a fixed floor then rejects the
    level for a reason that has nothing to do with why it was measured. It did:
    on real weekly gold the fixed bound found one quadrennial open where the
    hourly series found two.

    The invariant this pins is the one that matters: WHICH boundaries produce a
    level is a fact about the clock, so the two timeframes must agree on the set
    even though they disagree on the lag. Measured on real broker gold, both now
    report 2 quadrennial and 10 year levels.
    """
    boundary = ny(2024, 1, 1)
    # Weekly bars, none of them within 120 hours of 1 January 2024 - the nearest
    # opens on the Monday, six days later.
    def bar(t: int, price: float) -> Candle:
        return Candle(time=t, open=price, high=price + 1, low=price - 1, close=price)

    weekly = [bar(boundary - 7 * 86_400, 1999.0)] + [
        bar(boundary + 6 * 86_400 + i * 7 * 86_400, 2000.0 + i) for i in range(12)
    ]
    got = true_opens(weekly, ("quadrennial",), approximate=True)
    assert len(got) == 1, "a weekly chart must still place the level"
    assert got[0].bar - got[0].time > 120 * 3600, (
        "and the point is that this lag EXCEEDS the intraday bound"
    )
    assert got[0].bar - got[0].time <= 7 * 86_400, "but not its own bar interval"

    # The same boundary on hourly bars keeps the tight bound, because there the
    # only thing between a boundary and a bar is a closure.
    hourly_late = [bar(boundary - HOUR, 1999.0)] + [
        bar(boundary + 200 * HOUR + i * HOUR, 2000.0) for i in range(12)
    ]
    assert true_opens(hourly_late, ("quadrennial",), approximate=True) == [], (
        "200 hours on an hourly series is past every measured closure"
    )


def test_an_exact_true_open_is_never_flagged_approximate():
    """The flag has to mean something. With the relaxation ON, a boundary that
    does have a bar still reports `approximate=False` and reads its own bar - or
    the flag would be a statement about the request rather than about the level."""
    candles = hourly(ny(2025, 6, 9, 18), ny(2025, 6, 10, 12))
    for flag in (False, True):
        opens = true_opens(candles, ("day",), approximate=flag)
        assert len(opens) == 1, opens
        assert opens[0].approximate is False
        assert opens[0].bar == opens[0].time == ny(2025, 6, 10)
