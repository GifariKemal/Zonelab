"""Opening gaps and Event Horizons, on series whose answer is arithmetic.

Every band here is built from two prices this file puts in the series by hand,
so the expected number is written down rather than derived from whatever the
market did. `app.providers.synthetic.generate` is not used: its prices are
seeded but its time anchor is `now`, and every boundary in this module is a New
York wall-clock hour, so a sliding anchor would move the boundaries out from
under the assertions.

The week of 2026-06-01 is used throughout: Monday the 1st through Sunday the
7th, all inside US daylight time, so 17:00 and 18:00 New York are 21:00 and
22:00 UTC. `clock.ny_wall` builds them, and no test here does its own offset
arithmetic.

Two of these tests exist for properties nothing else in this repo has had to
worry about: the Event Horizon level set changes when a gap is inserted BETWEEN
two existing gaps, and the pairing is by price and not by time.

THE LAST GROUP IS DIFFERENT AND SAYS SO. `distances_to_ce`, `gap_ordinals`,
`gap_stacks` and `weekend_degree` implement definitions that were decoded from
the RENDERED OUTPUT of a closed-source indicator, never from its source, so
those tests are built from the indicator's own published numbers - price
28164.00 against two bands, and the `EV STACK W+D 91%` label. Reproducing them
is the strongest check available here: it compares this implementation against
the reference implementation's actual printed output. It is still not a proof of
the definition, because a different rule agreeing on one chart would look
identical from here, and none of it is measured against outcomes by anyone.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_gaps.py -q
"""

from __future__ import annotations

from typing import Literal

import pytest

from app import clock
from app.gaps import (
    REDUCTIONS,
    tier_horizons,
    EventHorizon,
    OpeningGap,
    distances_to_ce,
    event_horizons,
    gap_ordinals,
    gap_stacks,
    opening_gaps,
    weekend_degree,
)
from app.models import Candle
from app.quarters import quarters

HOUR = 3600


def bar(epoch: int, open_: float, close: float) -> Candle:
    """A bar with nothing in it but the two prices the gap rules read."""
    return Candle(
        time=epoch,
        open=open_,
        high=max(open_, close),
        low=min(open_, close),
        close=close,
    )


def ny(day: int, hour: int, minute: int = 0) -> int:
    """Epoch of a New York wall-clock time in the week of 2026-06-01."""
    return clock.ny_wall(2026, 6, day, hour, minute)


def five_minute_session(day: int, *, last_close: float) -> list[Candle]:
    """Three 5m bars ending with the one that opens 16:55 and closes at 17:00.

    The 16:50 bar is not decoration: it is how the module infers the closing
    bar's width, and without a predecessor the boundary cannot be proven exact.
    """
    return [
        bar(ny(day, 16, 45), last_close, last_close),
        bar(ny(day, 16, 50), last_close, last_close),
        bar(ny(day, 16, 55), last_close, last_close),
    ]


def gap(
    *,
    top: float,
    bottom: float,
    open_time: int,
    kind: Literal["NDOG", "NWOG"] = "NDOG",
    close_time: int | None = None,
) -> OpeningGap:
    """A hand-built gap, for the Event Horizon tests that need no candles."""
    return OpeningGap(
        kind=kind,
        top=top,
        bottom=bottom,
        close_time=open_time - HOUR if close_time is None else close_time,
        open_time=open_time,
        approximate=False,
    )


# --------------------------------------------------------------------------
# NDOG and NWOG
# --------------------------------------------------------------------------


def test_an_ndog_off_five_minute_bars_is_the_two_prices_and_their_midpoint():
    # Tuesday's 17:00 close at 100.0 against Tuesday's 18:00 open at 101.5.
    candles = five_minute_session(2, last_close=100.0) + [
        bar(ny(2, 18, 0), 101.5, 101.5),
        bar(ny(2, 18, 5), 101.5, 101.5),
    ]

    gaps = opening_gaps(candles)

    assert len(gaps) == 1
    ndog = gaps[0]
    assert ndog.kind == "NDOG"
    assert (ndog.bottom, ndog.top) == (100.0, 101.5)
    assert ndog.ce == 100.75
    assert ndog.close_time == ny(2, 16, 55)
    assert ndog.open_time == ny(2, 18, 0)
    # 16:55 + 5m lands exactly on 17:00 and the opening bar opens exactly on
    # 18:00, so this band's edges are the prices the definition asks for.
    assert ndog.approximate is False


def test_the_gap_is_signed_neither_way_when_the_new_session_opens_lower():
    # Same boundary, opening below the close. `top` is still the higher price;
    # the band does not record which side it came from, because nothing here
    # makes a directional claim off that.
    candles = five_minute_session(2, last_close=101.5) + [
        bar(ny(2, 18, 0), 100.0, 100.0)
    ]

    (ndog,) = opening_gaps(candles)

    assert (ndog.bottom, ndog.top) == (100.0, 101.5)
    assert ndog.ce == 100.75


def test_fridays_close_against_sunday_makes_an_nwog_and_no_ndog():
    candles = five_minute_session(5, last_close=200.0) + [
        bar(ny(7, 18, 0), 205.0, 205.0),
        bar(ny(7, 18, 5), 205.0, 205.0),
    ]

    gaps = opening_gaps(candles)

    # Exactly one object: Friday has no 18:00 open of its own, so the weekend
    # band is an NWOG and there is no NDOG anywhere in this series.
    assert len(gaps) == 1
    assert gaps[0].kind == "NWOG"
    assert [g.kind for g in gaps] != ["NDOG"]
    assert (gaps[0].bottom, gaps[0].top) == (200.0, 205.0)
    assert gaps[0].close_time == ny(5, 16, 55)
    assert gaps[0].open_time == ny(7, 18, 0)


def test_four_daily_boundaries_and_one_weekend_in_a_full_week():
    candles: list[Candle] = []
    for day in (1, 2, 3, 4):
        candles += five_minute_session(day, last_close=100.0 + day)
        candles.append(bar(ny(day, 18, 0), 100.5 + day, 100.5 + day))
    candles += five_minute_session(5, last_close=200.0)
    candles.append(bar(ny(7, 18, 0), 205.0, 205.0))

    gaps = opening_gaps(candles)

    assert [g.kind for g in gaps] == ["NDOG", "NDOG", "NDOG", "NDOG", "NWOG"]
    assert [g.open_time for g in gaps] == [
        ny(1, 18),
        ny(2, 18),
        ny(3, 18),
        ny(4, 18),
        ny(7, 18),
    ]


def test_a_holiday_with_no_bar_in_the_closing_session_yields_nothing():
    # Wednesday's session (18:00 Tuesday through 17:00 Wednesday) never traded.
    # The only bars are Wednesday's 18:00 open onwards. Nothing is carried
    # forward from Tuesday, so there is no Wednesday NDOG at all.
    candles = [
        bar(ny(3, 18, 0), 101.0, 101.0),
        bar(ny(3, 18, 5), 101.0, 101.0),
    ]

    assert opening_gaps(candles) == []


def test_a_holiday_with_no_bar_at_the_new_open_yields_nothing():
    candles = five_minute_session(3, last_close=100.0)

    assert opening_gaps(candles) == []


def test_a_bar_from_the_wrong_session_is_not_reached_for():
    # Monday's close exists, then the feed goes dark until Wednesday evening.
    # Wednesday's 18:00 open must not be paired with Monday's close: they are
    # two days apart and the band between them is not a gap anyone can trade.
    candles = five_minute_session(1, last_close=100.0) + [
        bar(ny(3, 18, 0), 130.0, 130.0)
    ]

    assert opening_gaps(candles) == []


def test_four_hour_bars_report_the_boundary_as_approximate():
    # A 14:00 bar on 4h bars closes at 18:00, so its close is the 18:00 price
    # and not the 17:00 one. The band is still the best this feed can give and
    # it is returned, flagged.
    candles = [
        bar(ny(2, 6), 100.0, 100.0),
        bar(ny(2, 10), 100.0, 100.0),
        bar(ny(2, 14), 100.0, 99.0),
        bar(ny(2, 18), 101.5, 101.5),
    ]

    (ndog,) = opening_gaps(candles)

    assert ndog.approximate is True
    assert (ndog.bottom, ndog.top) == (99.0, 101.5)


def test_one_hour_bars_land_on_the_boundary_and_are_not_approximate():
    candles = [
        bar(ny(2, 15), 100.0, 100.0),
        bar(ny(2, 16), 100.0, 100.0),  # closes at 17:00 exactly
        bar(ny(2, 18), 101.5, 101.5),
    ]

    (ndog,) = opening_gaps(candles)

    assert ndog.approximate is False


def test_a_closing_bar_with_no_predecessor_cannot_be_proven_exact():
    # The bar's width is inferred from the bar before it, because no bar trades
    # between 17:00 and 18:00 and the step cannot be measured forwards. First
    # bar in the feed, no predecessor, so exactness is unproven and reported so
    # rather than assumed.
    candles = [
        bar(ny(2, 16, 55), 100.0, 100.0),
        bar(ny(2, 18, 0), 101.5, 101.5),
    ]

    (ndog,) = opening_gaps(candles)

    assert ndog.approximate is True
    assert (ndog.bottom, ndog.top) == (100.0, 101.5)


def test_an_empty_series_has_no_gaps():
    assert opening_gaps([]) == []


# --------------------------------------------------------------------------
# Event Horizon
# --------------------------------------------------------------------------


def three_gaps_in_scrambled_time_order() -> tuple[OpeningGap, OpeningGap, OpeningGap]:
    """Three gaps whose time order is the reverse of their price order."""
    high = gap(top=31.0, bottom=29.0, open_time=ny(1, 18))  # ce 30, oldest
    low = gap(top=11.0, bottom=9.0, open_time=ny(2, 18))  # ce 10
    mid = gap(top=21.0, bottom=19.0, open_time=ny(3, 18))  # ce 20, newest
    return high, low, mid


def test_three_gaps_give_exactly_two_levels_paired_by_price_not_by_time():
    high, low, mid = three_gaps_in_scrambled_time_order()

    levels = event_horizons([high, low, mid])

    assert len(levels) == 2
    # Price order is low, mid, high. So the pairs are low-mid and mid-high.
    assert [level.price for level in levels] == [15.0, 25.0]
    assert (levels[0].lower, levels[0].upper) == (low, mid)
    assert (levels[1].lower, levels[1].upper) == (mid, high)
    # Time order would have paired high with low first, giving avg(31, 9) = 20.
    assert 20.0 not in [level.price for level in levels]


def test_the_input_order_of_the_gaps_does_not_change_the_levels():
    high, low, mid = three_gaps_in_scrambled_time_order()

    assert event_horizons([high, low, mid]) == event_horizons([mid, high, low])


def test_a_level_moves_when_a_new_gap_appears_between_two_existing_ones():
    # THE property that breaks every birth-settled assumption in this repo: no
    # price changes, no gap is edited, a fourth gap simply forms in the space
    # between two others - and a level already on the chart moves.
    high, low, mid = three_gaps_in_scrambled_time_order()
    before = event_horizons([high, low, mid])
    assert before[0].price == 15.0 and (before[0].lower, before[0].upper) == (low, mid)

    inserted = gap(top=16.0, bottom=14.0, open_time=ny(4, 18))  # ce 15, between
    after = event_horizons([high, low, mid, inserted])

    assert len(after) == 3
    assert [level.price for level in after] == [12.5, 17.5, 25.0]
    # The level above `low` was 15.0 and is now 12.5, and its upper gap is no
    # longer `mid`.
    assert after[0].lower is low
    assert after[0].upper is inserted
    assert after[0].price != before[0].price
    assert 15.0 not in [level.price for level in after]


def test_keeping_fewer_gaps_deletes_a_level_rather_than_trimming_one():
    high, low, mid = three_gaps_in_scrambled_time_order()

    all_three = event_horizons([high, low, mid], keep=0)
    newest_two = event_horizons([high, low, mid], keep=2)

    # keep=2 drops `high`, the oldest by knowable_at, even though it is the
    # highest in price. One whole level disappears and it is not the last one
    # in the list.
    assert [level.price for level in all_three] == [15.0, 25.0]
    assert [level.price for level in newest_two] == [15.0]
    assert (newest_two[0].lower, newest_two[0].upper) == (low, mid)


def test_two_gaps_give_one_level_and_one_gap_gives_none():
    high, low, _ = three_gaps_in_scrambled_time_order()

    assert len(event_horizons([low, high])) == 1
    assert event_horizons([low]) == []
    assert event_horizons([]) == []


def test_overlapping_gaps_still_produce_a_level():
    lower = gap(top=25.0, bottom=5.0, open_time=ny(1, 18))  # ce 15
    upper = gap(top=30.0, bottom=10.0, open_time=ny(2, 18))  # ce 20, overlaps

    (level,) = event_horizons([lower, upper])

    assert level.price == 17.5  # avg(lower.top 25, upper.bottom 10)
    assert (level.lower, level.upper) == (lower, upper)


# --------------------------------------------------------------------------
# Anti-lookahead
# --------------------------------------------------------------------------


def test_a_gap_does_not_exist_before_its_second_price_prints():
    session = five_minute_session(2, last_close=100.0)
    opening = bar(ny(2, 18, 0), 101.5, 101.5)

    # The 17:00 close has printed. The 18:00 open has not.
    assert opening_gaps(session) == []
    # It prints, and only then is there a band - knowable on that bar, not before.
    (ndog,) = opening_gaps(session + [opening])
    assert ndog.knowable_at == ny(2, 18, 0)


def test_a_level_is_not_reported_before_the_later_of_its_two_gaps():
    high, low, mid = three_gaps_in_scrambled_time_order()
    gaps = [high, low, mid]

    # Before the third gap prints, only the pair that exists is reported.
    early = event_horizons(gaps, as_of=ny(2, 18))
    assert [level.price for level in early] == [20.0]  # avg(low.top 11, high.bottom 29)
    assert (early[0].lower, early[0].upper) == (low, high)

    # One second before `mid` prints, the level set still does not know it.
    assert event_horizons(gaps, as_of=ny(3, 18) - 1) == early
    # On the bar it prints, it counts - knowable AT that bar, not after it.
    assert len(event_horizons(gaps, as_of=ny(3, 18))) == 2

    assert event_horizons(gaps, as_of=ny(1, 18)) == []  # one gap, no pair yet


def test_no_level_is_ever_knowable_after_the_bar_it_is_reported_at():
    high, low, mid = three_gaps_in_scrambled_time_order()
    gaps = [high, low, mid]

    for as_of in (ny(1, 18), ny(2, 18), ny(3, 18), ny(4, 18)):
        for level in event_horizons(gaps, as_of=as_of):
            assert level.knowable_at <= as_of
            assert level.lower.knowable_at <= as_of
            assert level.upper.knowable_at <= as_of


def test_a_level_carries_the_later_of_its_two_gaps_as_its_own_birth():
    high, low, mid = three_gaps_in_scrambled_time_order()

    levels = event_horizons([high, low, mid])

    assert levels[0].knowable_at == max(low.knowable_at, mid.knowable_at)
    assert levels[1].knowable_at == max(mid.knowable_at, high.knowable_at)


def test_the_whole_chain_from_candles_to_levels_holds_together():
    candles: list[Candle] = []
    # Three NDOGs at separated prices, so the price order is knowable by eye.
    days = ((1, 100.0, 101.0), (2, 110.0, 111.0), (3, 120.0, 121.0))
    for day, last_close, first_open in days:
        candles += five_minute_session(day, last_close=last_close)
        candles.append(bar(ny(day, 18, 0), first_open, first_open))

    gaps = opening_gaps(candles)
    levels = event_horizons(gaps)

    assert len(gaps) == 3
    assert len(levels) == 2
    assert [level.price for level in levels] == [105.5, 115.5]
    assert all(isinstance(level, EventHorizon) for level in levels)
    assert all(g.approximate is False for g in gaps)


def test_the_bar_that_opens_exactly_at_seventeen_hundred_is_excluded():
    """"Before 17:00" is load-bearing, and live gold data proves it.

    COMEX gold on Yahoo emits a bar that OPENS at 17:00 New York on a Friday -
    the hour the market is shut. On 2026-08-14 that bar read O4432.00 H4437.30
    L4432.00 C4437.30 with a reported volume of 1, while the 16:00 bar closed at
    4432.10 and the Sunday 18:00 reopen printed 4433.70.

    So the two readings of the rule give NON-OVERLAPPING bands:

        opens BEFORE 17:00   ->  4432.10 .. 4433.70   (shipped)
        opens AT OR BEFORE   ->  4433.70 .. 4437.30
        consequent encroachment moves 2.60 points

    Neither band contains the other's midpoint. A one-word change in the
    boundary therefore relocates every NWOG on the feed, and nothing else in the
    suite would notice - the count stays the same, the kinds stay the same, and
    the anti-lookahead property still holds. Hence this test, built from the
    prices actually observed rather than from invented ones.

    A note on the volume, because it is easy to over-read: bars at these session
    boundaries frequently report 0 or 1 on this feed while carrying a full and
    genuine OHLC range - 2026-08-12 18:00 reported volume 0 across a 13.8 point
    range. The volume field is unreliable AT THE BOUNDARY, the prices are not,
    and this test therefore keys on the CLOCK and never on the volume.
    """
    step = 3600
    # Friday 2026-08-14, hours 14:00 through 17:00 New York, then the Sunday
    # reopen. Real timestamps, real prices.
    fri_14 = clock.at_ny_hour(clock.ny_wall(2026, 8, 14, 12), 14)
    sun_18 = clock.at_ny_hour(clock.ny_wall(2026, 8, 16, 12), 18)

    def bar(t, o, h, low, c, v):
        return Candle(time=t, open=o, high=h, low=low, close=c, volume=v)

    rows = [
        bar(fri_14, 4429.0, 4431.0, 4428.0, 4430.30, 5830.0),
        bar(fri_14 + step, 4430.30, 4432.0, 4429.5, 4431.50, 3055.0),
        bar(fri_14 + 2 * step, 4431.50, 4433.0, 4430.0, 4432.10, 1870.0),
        # The bar that opens exactly on the close. It must not be used.
        bar(fri_14 + 3 * step, 4432.0, 4437.30, 4432.0, 4437.30, 1.0),
        bar(sun_18, 4433.70, 4442.0, 4433.0, 4441.60, 1615.0),
        bar(sun_18 + step, 4441.60, 4445.0, 4424.0, 4425.50, 2616.0),
    ]

    found = [g for g in opening_gaps(rows) if g.kind == "NWOG"]
    assert len(found) == 1, [g.kind for g in opening_gaps(rows)]
    gap = found[0]

    assert gap.close_time == fri_14 + 2 * step, "the 17:00 bar was used as the close"
    assert (gap.bottom, gap.top) == (4432.10, 4433.70)
    assert gap.ce == pytest.approx(4432.90)

    # And the band the other reading would give, asserted so the difference
    # cannot be dismissed as a rounding argument.
    other = (4433.70, 4437.30)
    assert gap.top <= other[0], "the two readings must not overlap on this data"


# --------------------------------------------------------------------------
# Readings decoded from the closed-source indicator's rendered output
# --------------------------------------------------------------------------

# The indicator's published preview chart, NASDAQ 100 E-mini futures 1h. These
# five numbers are the whole evidence base for the four functions below, so they
# are written once, spelled exactly as rendered.
#
#     EV   Top       Bot       Dist          price 28164.00
#     W    29206.75  28580.75  -730
#     D    28768.00  28561.50  -501          EV STACK W+D  91%
DECODED_PRICE = 28164.00


def decoded_week_and_day() -> tuple[OpeningGap, OpeningGap]:
    """The two bands from the indicator's own table, tops and bottoms verbatim."""
    week = gap(top=29206.75, bottom=28580.75, open_time=ny(7, 18), kind="NWOG")
    day = gap(top=28768.00, bottom=28561.50, open_time=ny(2, 18), kind="NDOG")
    return week, day


def test_the_distance_reproduces_both_rows_of_the_indicators_own_table():
    """Both `Dist` cells, from the tops and bottoms printed beside them.

    This is the strongest check in this file: it is not an assertion about what
    the definition ought to be, it is this implementation's output against the
    reference implementation's published output. The definition was decoded from
    that output, not read from the protected source, so agreement here is
    evidence and not verification.
    """
    week, day = decoded_week_and_day()

    (w, d) = distances_to_ce([week, day], DECODED_PRICE)

    # The encroachments the arithmetic goes through, pinned on the way.
    assert week.ce == 28893.75
    assert day.ce == 28664.75
    assert w.distance == -729.75
    assert d.distance == -500.75
    # Rendered as integers in the table. Both match to the rounding shown, which
    # is where the reproduction is exact and where it stops being exact.
    assert round(w.distance) == -730
    assert round(d.distance) == -501

    # And it is a distance to the ENCROACHMENT, not to an edge: no edge of
    # either band produces the rendered number.
    for edge in (week.top, week.bottom, day.top, day.bottom):
        assert round(DECODED_PRICE - edge) not in (-730, -501)


def test_the_distance_is_a_reading_against_a_price_and_not_a_field_on_the_gap():
    # Negative below the encroachment, positive above it, and the same settled
    # band answers differently at two prices without changing at all - which is
    # why the number is not an attribute of the band.
    week, _ = decoded_week_and_day()

    below = distances_to_ce([week], 28164.00)[0]
    above = distances_to_ce([week], 29000.00)[0]

    assert below.distance < 0 < above.distance
    assert (below.price, above.price) == (28164.00, 29000.00)
    assert below.gap is week and above.gap is week
    assert week == gap(top=29206.75, bottom=28580.75, open_time=ny(7, 18), kind="NWOG")
    assert not hasattr(week, "distance")


def test_the_ordinal_counts_within_a_kind_and_never_across_kinds():
    older_day = gap(top=11.0, bottom=9.0, open_time=ny(1, 18))
    newer_day = gap(top=21.0, bottom=19.0, open_time=ny(3, 18))
    week = gap(top=31.0, bottom=29.0, open_time=ny(7, 18), kind="NWOG")

    ordinals = gap_ordinals([older_day, newer_day, week])

    # Returned in the order given, so a caller can zip it against its own list.
    assert [o.gap for o in ordinals] == [older_day, newer_day, week]
    assert [o.ordinal for o in ordinals] == [2, 1, 1]
    assert [o.label for o in ordinals] == ["D-2", "D-1", "W-1"]
    # Counting across the whole list would have made the weekend gap the third
    # thing in it. It is W-1 because it is the newest of ITS kind.
    assert ordinals[2].ordinal != 3


def test_an_ordinal_renumbers_when_a_newer_gap_of_that_kind_appears():
    # The not-fixed-at-birth hazard, asserted directly: no price changes, no gap
    # is edited, a newer NDOG simply forms - and yesterday's D-1 becomes D-2.
    day = gap(top=11.0, bottom=9.0, open_time=ny(1, 18))
    week = gap(top=31.0, bottom=29.0, open_time=ny(7, 18), kind="NWOG")

    before = gap_ordinals([day, week])
    assert [o.label for o in before] == ["D-1", "W-1"]

    newer_day = gap(top=21.0, bottom=19.0, open_time=ny(4, 18))
    after = gap_ordinals([day, week, newer_day])

    assert [o.gap for o in after] == [day, week, newer_day]
    assert [o.label for o in after] == ["D-2", "W-1", "D-1"]
    # The same unchanged band carries a different number than it did a moment
    # ago, and the weekend gap's number did not move with it.
    assert before[0].gap == after[0].gap
    assert before[0].ordinal != after[0].ordinal
    assert before[1].ordinal == after[1].ordinal


def test_the_stack_percentage_reproduces_the_indicators_ninety_one_percent():
    """`EV STACK W+D 91%`, from the same two bands as the table above.

    Overlap of W 28580.75..29206.75 with D 28561.50..28768.00 is
    28580.75..28768.00, 187.25 high, over the SMALLER zone (D, 206.50).
    """
    week, day = decoded_week_and_day()

    (stack,) = gap_stacks([week, day])

    assert (stack.bottom, stack.top) == (28580.75, 28768.00)
    assert stack.top - stack.bottom == 187.25
    assert stack.fraction == pytest.approx(187.25 / 206.50)
    assert round(stack.fraction * 100) == 91
    assert stack.gaps == (week, day)


def test_the_stack_denominator_is_a_choice_that_one_label_cannot_pin():
    # Chosen is not measured. The published 91% fits the smaller zone; the two
    # denominators not taken give visibly different numbers on the same bands,
    # and one label cannot rule them out - it only fails to contradict the one
    # that was implemented.
    week, day = decoded_week_and_day()

    (stack,) = gap_stacks([week, day])
    overlap = stack.top - stack.bottom
    larger = week.top - week.bottom
    union = max(week.top, day.top) - min(week.bottom, day.bottom)

    assert round(overlap / larger * 100) == 30
    assert round(overlap / union * 100) == 29
    assert round(stack.fraction * 100) == 91


def test_two_gaps_of_the_same_kind_overlapping_are_not_a_stack():
    # The construct is about a lower degree confirming a higher one. Two NDOGs
    # sitting on each other overlap in exactly the same arithmetic sense and are
    # still not a stack.
    one = gap(top=25.0, bottom=5.0, open_time=ny(1, 18))
    two = gap(top=30.0, bottom=10.0, open_time=ny(2, 18))

    assert min(one.top, two.top) > max(one.bottom, two.bottom)  # they do overlap
    assert gap_stacks([one, two]) == []

    both_weeks = [
        gap(top=25.0, bottom=5.0, open_time=ny(7, 18), kind="NWOG"),
        gap(top=30.0, bottom=10.0, open_time=ny(14, 18), kind="NWOG"),
    ]
    assert gap_stacks(both_weeks) == []


def test_bands_that_only_touch_or_miss_produce_no_stack():
    day = gap(top=20.0, bottom=10.0, open_time=ny(2, 18))
    touching = gap(top=30.0, bottom=20.0, open_time=ny(7, 18), kind="NWOG")
    clear = gap(top=40.0, bottom=30.0, open_time=ny(7, 18), kind="NWOG")

    assert gap_stacks([day, touching]) == []
    assert gap_stacks([day, clear]) == []
    # A zero-width gap - which `opening_gaps` deliberately keeps - can only ever
    # touch, so no denominator here is ever zero.
    flat = gap(top=15.0, bottom=15.0, open_time=ny(7, 18), kind="NWOG")
    assert gap_stacks([day, flat]) == []


def test_a_stack_is_not_knowable_before_the_later_of_its_two_gaps():
    week, day = decoded_week_and_day()

    (stack,) = gap_stacks([week, day])

    assert stack.knowable_at == max(week.knowable_at, day.knowable_at)
    assert stack.knowable_at == ny(7, 18)
    # Fed only the gaps that had printed by the earlier bar, there is no pair
    # and therefore no overlap to report.
    live = [g for g in (week, day) if g.knowable_at <= ny(2, 18)]
    assert gap_stacks(live) == []
    assert [o.label for o in gap_ordinals(live)] == ["D-1"]


def test_a_weekend_gap_is_labelled_monthly_on_the_month_degrees_own_q2():
    # `quarters.py` puts June 2026's month Q2 at Sunday the 7th 18:00 New York -
    # the Sunday that begins the second full week - and that is exactly an NWOG
    # boundary. No second grid is defined for this.
    second_week = [q for q in quarters("month", ny(2, 0), ny(26, 0)) if q.label == "Q2"]
    assert [q.start for q in second_week] == [ny(7, 18)]

    monthly = gap(top=101.0, bottom=100.0, open_time=ny(7, 18), kind="NWOG")
    assert weekend_degree(monthly) == "month"


def test_an_ordinary_weekend_gap_gets_no_degree_and_a_weekday_gap_never_does():
    ordinary = gap(top=101.0, bottom=100.0, open_time=ny(14, 18), kind="NWOG")
    assert weekend_degree(ordinary) is None
    assert weekend_degree(gap(top=101.0, bottom=100.0, open_time=ny(21, 18),
                              kind="NWOG")) is None

    # The label answers "which weekend gap matters at which degree", so a
    # weekday gap is outside the question even when it opens the same Sunday
    # instant a monthly one would.
    assert weekend_degree(gap(top=101.0, bottom=100.0, open_time=ny(7, 18))) is None


def test_the_weekend_gap_over_a_year_boundary_is_labelled_yearly():
    # April 1 2028 is a Saturday, so the year cycle's Q2 - April 1 00:00 New
    # York - falls inside a weekend when nothing trades, and the Sunday 18:00
    # reopen is the first price that quarter ever sees. Year outranks month.
    sunday = clock.ny_wall(2028, 4, 2, 18)
    yearly = gap(top=101.0, bottom=100.0, open_time=sunday, kind="NWOG")

    assert weekend_degree(yearly) == "year"
    # And the same month's monthly weekend is a different, later Sunday.
    monthly = gap(
        top=101.0, bottom=100.0, open_time=clock.ny_wall(2028, 4, 9, 18), kind="NWOG"
    )
    assert weekend_degree(monthly) == "month"


def test_the_degree_label_rides_on_a_real_gap_and_invents_no_geometry():
    # A monthly opening gap is not a fifth kind: it is an NWOG built by the same
    # two prices as every other NWOG, that happens to open the month cycle. Here
    # it is grown from candles rather than hand-built, so the label is applied to
    # something `opening_gaps` actually produced.
    candles = five_minute_session(5, last_close=200.0) + [
        bar(ny(7, 18, 0), 205.0, 205.0)
    ]

    (nwog,) = opening_gaps(candles)

    assert nwog.kind == "NWOG"
    assert (nwog.bottom, nwog.top) == (200.0, 205.0)
    assert weekend_degree(nwog) == "month"
    # Nothing about the band changed because of the label.
    assert nwog.ce == 202.5
    assert nwog.knowable_at == ny(7, 18)


def _tier_gaps() -> list[OpeningGap]:
    """Three NDOGs on consecutive weeknights, with hand-chosen edges.

    Built so every reduction gives a DIFFERENT answer. A fixture where two of
    them agree would let a swapped default pass unnoticed, which is exactly the
    failure this construct is exposed to while its reduction is unresolved.
    """
    step = 3600
    base = clock.at_ny_hour(clock.ny_wall(2026, 6, 1, 12), 18)
    out: list[OpeningGap] = []
    for day, (bottom, top) in enumerate(
        [(100.0, 110.0), (130.0, 134.0), (120.0, 128.0)]
    ):
        opened = clock.at_ny_hour(clock.ny_wall(2026, 6, 1 + day, 12), 18)
        out.append(
            OpeningGap(
                kind="NDOG",
                top=top,
                bottom=bottom,
                close_time=opened - step,
                open_time=opened,
                approximate=False,
            )
        )
    assert base <= out[0].open_time
    return out


def test_a_tier_horizon_reduces_the_three_latest_gaps_of_one_kind():
    """His retention rule, confirmed directly: three latest, per kind, per tier.

    `TIER_KEEP` is therefore HIS number rather than a reconstruction, unlike the
    stack denominator next door.
    """
    gaps = _tier_gaps()
    tiers = tier_horizons(gaps)
    assert [t.kind for t in tiers] == ["NDOG"], "no NWOG in the fixture"
    tier = tiers[0]
    assert len(tier.gaps) == 3
    assert tier.gaps == tuple(sorted(gaps, key=lambda g: g.knowable_at))
    assert tier.knowable_at == max(g.knowable_at for g in gaps)
    # The envelope of 100..110, 130..134 and 120..128.
    assert (tier.bottom, tier.top) == (100.0, 134.0)
    assert tier.ce == 117.0


def test_every_reduction_gives_a_different_zone_so_none_can_hide():
    """The reduction is UNRESOLVED, and this test is what keeps that visible.

    The reference indicator's own published table is not reproduced by any of
    these four on real data, so shipping one silently would present a guess as a
    match. Pinning all four means the day the real rule arrives, the wrong ones
    are already on record as tried.
    """
    gaps = _tier_gaps()
    bands = {}
    for how in REDUCTIONS:
        tiers = tier_horizons(gaps, reduction=how)
        assert tiers, how
        bands[how] = (tiers[0].bottom, tiers[0].top)

    assert bands["envelope"] == (100.0, 134.0)
    assert bands["ce_span"] == (105.0, 132.0)
    assert bands["newest"] == (120.0, 128.0)
    assert len(set(bands.values())) == len(bands), bands


def test_a_kind_with_too_few_gaps_produces_no_tier_at_all():
    """Reducing over a short set and calling it a tier would be a zone whose
    inputs do not match its own definition."""
    gaps = _tier_gaps()
    assert tier_horizons(gaps[:2]) == []
    assert tier_horizons(gaps[:2], keep=2), "two gaps make a two-gap tier"


def test_a_tier_moves_when_a_newer_gap_of_its_kind_arrives():
    """Not fixed at birth, the same hazard `event_horizons` carries.

    A new gap pushes the oldest out of the retained set and the whole zone moves
    without one price changing, which is why `as_of` exists.
    """
    gaps = _tier_gaps()
    before = tier_horizons(gaps)[0]

    step = 3600
    opened = clock.at_ny_hour(clock.ny_wall(2026, 6, 4, 12), 18)
    newer = OpeningGap(
        kind="NDOG", top=200.0, bottom=190.0,
        close_time=opened - step, open_time=opened, approximate=False,
    )
    after = tier_horizons([*gaps, newer])[0]

    assert (after.bottom, after.top) != (before.bottom, before.top)
    assert before.gaps[0] not in after.gaps, "the oldest should have been pushed out"
    # And asking as of the older bar gives the older zone back.
    as_before = tier_horizons([*gaps, newer], as_of=before.knowable_at)[0]
    assert (as_before.bottom, as_before.top) == (before.bottom, before.top)


def test_an_unknown_reduction_is_refused_rather_than_defaulted():
    """A typo silently falling back to the default would ship a zone the caller
    did not ask for, and the four reductions disagree by design."""
    with pytest.raises(ValueError, match="unknown reduction"):
        tier_horizons(_tier_gaps(), reduction="middle")


def test_an_instrument_that_never_closes_has_no_opening_gaps():
    """The failure this replaces shipped fabricated bands flagged EXACT.

    An opening gap is the distance across an interval in which nothing traded.
    A 24/7 series has no such interval, but the two lookups inside `_gap_at`
    will still find a bar before 17:00 and a bar at 18:00 and report the
    distance between them. On clean hourly bars the exactness test then passes -
    16:00 plus one hour IS 17:00, and the 18:00 bar does open at 18:00 - so the
    invented band went out with `approximate=False`.

    Measured against the live feed on 2026-08-19: binance BTCUSDT 1h produced 29
    such bands, every one exact-flagged. Binance PAXGUSDT and BTCUSDT are the
    series most of docs/CALIBRATION.md is measured on.
    """
    start = clock.ny_wall(2026, 6, 1, 12)
    rows = [bar(start + i * 3600, 100.0 + i, 100.5 + i) for i in range(72)]

    stats: dict[str, int] = {}
    assert opening_gaps(rows, stats) == []
    assert stats["traded_through"] == 1, "an empty layer must be told from a broken one"


def test_a_market_that_does_close_still_gets_its_gaps():
    """The other half of the guard, because a rule that rejects everything is
    not a rule. One hole in the grid - the shut hour - is what separates this
    series from the one above, and it is the only difference between them."""
    start = clock.ny_wall(2026, 6, 1, 12)
    rows = [
        bar(t, 100.0, 100.0)
        # 12:00 through 16:00. Stopping before 17:00 is the whole fixture: it is
        # what leaves the shut hour as a hole in the grid.
        for t in (start + i * 3600 for i in range(5))
    ]
    rows.append(bar(clock.at_ny_hour(start, 18), 103.0, 103.0))
    rows.append(bar(clock.at_ny_hour(start, 19), 103.0, 103.0))

    stats: dict[str, int] = {}
    found = opening_gaps(rows, stats)

    assert [g.kind for g in found] == ["NDOG"]
    assert (found[0].bottom, found[0].top) == (100.0, 103.0)
    assert "traded_through" not in stats


def test_coarse_bars_cannot_see_the_shut_hour_and_do_not_pretend_to():
    """A 4-hour grid running 06:00, 10:00, 14:00, 18:00 is seamless whether or
    not the market shut at 17:00 - the shut window is smaller than one bar. So
    the never-closes guard only applies at an hour or finer; above it the old
    answer stands, which is the band flagged `approximate`. Without this the
    guard silently deleted every gap on a 4h chart."""
    rows = [
        bar(clock.at_ny_hour(clock.ny_wall(2026, 6, 2, 12), h), 100.0, 100.0)
        for h in (6, 10, 14)
    ]
    rows.append(bar(clock.at_ny_hour(clock.ny_wall(2026, 6, 2, 12), 18), 101.5, 101.5))

    (ndog,) = opening_gaps(rows)

    assert ndog.approximate is True
