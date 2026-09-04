"""Labels over the quarter grid, on instants whose right answer is arithmetic.

Every expected value here is counted off the calendar by hand, and `ny` is built
in this file rather than imported from `app.clock`, so the fixtures cannot agree
with the code by sharing its arithmetic.

Three tests carry more weight than the rest:

  - the NOMINAL-VERSUS-OBSERVED pair. On an XAMD cycle `quarterly.profile` says
    the manipulation happened in Q3 while the nominal role of Q2 is still
    "manipulation". Both are right about different questions, both are the same
    four strings, and confusing them is the whole reason `app/sequence.py`
    exists. It is asserted directly on the fixture, not described.

  - the DST CHAIN. At 03:00 New York on 2025-03-09 the correct chain is 223. A
    grid that assumed a six-hour Q2 returns 222 there - one digit, silently
    wrong, on two days a year.

  - the DISTRIBUTION SUM. Counts plus `outside` must equal the bars examined, so
    a bar in time that belongs to no quarter cannot be quietly dropped.

Nothing here asserts that any chain, role or session name predicts anything. The
membership tests assert membership of a list he wrote down and nothing more; the
list has never been measured against outcomes in this project.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_sequence.py -q
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.clock import NY
from app.models import Candle
from app.pools import SESSIONS as KILLZONES
from app.quarterly import profile
from app.quarters import DEGREES, quarters
from app.sequence import (
    BASE_RATE,
    HIS_LIST,
    chain,
    intraday_session,
    nominal_role,
    occurrences,
)

HOUR = 3600


def ny(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    """Epoch of a New York wall-clock time, built from the calendar, not the code."""
    return int(datetime(year, month, day, hour, minute, tzinfo=NY).timestamp())


# 2025-06-10 is a plain Tuesday in EDT with no transition near it. The day cycle
# that opens 18:00 on the 10th runs:
#
#   Q1  18:00 Jun 10 - 00:00 Jun 11
#   Q2  00:00        - 06:00
#   Q3  06:00        - 12:00     -> its 90-minute sessions open 06:00 07:30 09:00 10:30
#   Q4  12:00        - 18:00     -> its 90-minute sessions open 12:00 13:30 15:00 16:30
NESTED = ("day", "session", "micro")


# --------------------------------------------------------------------------
# 1. The nominal role, and the profile it must not be mistaken for


def test_the_four_nominal_roles_come_from_position_alone():
    cycle = [
        nominal_role("day", t)
        for t in (
            ny(2025, 6, 10, 20),
            ny(2025, 6, 11, 2),
            ny(2025, 6, 11, 8),
            ny(2025, 6, 11, 14),
        )
    ]

    assert [r.label for r in cycle if r] == ["Q1", "Q2", "Q3", "Q4"]
    assert [r.role for r in cycle if r] == [
        ("accumulation",),
        ("manipulation",),
        ("distribution",),
        ("continuation", "reversal"),
    ]


def test_q4_keeps_both_readings_because_his_note_does_not_resolve_them():
    q4 = nominal_role("day", ny(2025, 6, 11, 14))

    assert q4 is not None
    # Two words, in a pair. Not "continuation", not "reversal", not a guess
    # between them - his note gives both and does not say which.
    assert len(q4.role) == 2
    assert set(q4.role) == {"continuation", "reversal"}


ROLE_OF = {
    "Q1": ("accumulation",),
    "Q2": ("manipulation",),
    "Q3": ("distribution",),
    "Q4": ("continuation", "reversal"),
}


def test_a_nominal_role_needs_no_candles_at_all_so_it_can_never_look_ahead():
    # The signature is the proof: there is nothing to read a future bar out of.
    # A year from now is as answerable as yesterday.
    future = nominal_role("day", ny(2030, 1, 2, 3))

    assert future is not None
    assert future.role == ROLE_OF[future.label]


def test_time_that_belongs_to_no_quarter_has_no_nominal_role():
    # Friday is not a quarter of the week. Not an off-by-one: the week has four
    # quarters, Monday to Thursday, and there is deliberately no Q5.
    friday = ny(2025, 3, 14, 12)

    assert nominal_role("week", friday) is None
    # The same instant is still inside a day cycle, and has a role there.
    assert nominal_role("day", friday) is not None


# The XAMD fixture, lifted from tests/test_quarterly.py so the two files cannot
# drift apart about what an XAMD cycle is. Hourly bars from 12:00 New York on
# 2025-06-10; bar i is hour i from noon, so the cycle opens at i = 6.
NOON = ny(2025, 6, 10, 12)
CYCLE = NOON + 6 * HOUR
QUIET = (3405.0, 3395.0, 3400.0)
XAMD = {
    0: (3450.0, 3395.0, 3400.0),  # previous Q4 high
    1: (3405.0, 3350.0, 3400.0),  # previous Q4 low
    7: (3460.0, 3395.0, 3400.0),  # Q1 breaks ABOVE that high -> XAMD
    8: (3405.0, 3360.0, 3400.0),
}


def bars(count: int, at: dict[int, tuple[float, float, float]]) -> list[Candle]:
    return [
        Candle(
            time=NOON + i * HOUR,
            open=at.get(i, QUIET)[2],
            high=at.get(i, QUIET)[0],
            low=at.get(i, QUIET)[1],
            close=at.get(i, QUIET)[2],
        )
        for i in range(count)
    ]


def test_the_nominal_role_and_the_observed_profile_disagree_on_an_xamd_cycle():
    """The confusion this module exists to prevent, asserted rather than described."""
    candles = bars(26, XAMD)
    q2_open = ny(2025, 6, 11, 0)
    q3_open = ny(2025, 6, 11, 6)

    observed = profile(candles, "day", CYCLE)
    assert observed is not None
    assert observed.name == "XAMD"

    # OBSERVED: the manipulation happened in Q3, read off a closed Q1.
    assert observed.manipulation == "Q3"

    # NOMINAL: Q2 is still called the manipulation quarter, because that is the
    # word his note attaches to position two. Same string, different question.
    nominal_q2 = nominal_role("day", q2_open)
    nominal_q3 = nominal_role("day", q3_open)
    assert nominal_q2 is not None and nominal_q3 is not None
    assert nominal_q2.role == ("manipulation",)
    assert nominal_q3.role == ("distribution",)

    # And so they point at different quarters. A caller reading one as the other
    # is wrong here and gets no warning, because both answers are Q-labels.
    assert observed.manipulation != nominal_q2.label
    assert nominal_q3.label == observed.manipulation
    assert "manipulation" not in nominal_q3.role


def test_the_observed_profile_is_unknowable_mid_q1_while_the_nominal_role_is_not():
    # Bars stop at 23:00, one hour inside Q1.
    mid_q1 = bars(12, XAMD)

    assert profile(mid_q1, "day", CYCLE) is None
    # The clock already knows what Q2 is called, and knew before the market opened.
    role = nominal_role("day", ny(2025, 6, 11, 0))
    assert role is not None and role.role == ("manipulation",)


# --------------------------------------------------------------------------
# 2. The session names, and the killzones they are not


def test_his_four_session_names_land_on_the_18_00_grid():
    named = [
        intraday_session(t)
        for t in (
            ny(2025, 6, 10, 20),
            ny(2025, 6, 11, 2),
            ny(2025, 6, 11, 8),
            ny(2025, 6, 11, 14),
        )
    ]

    assert [s.session for s in named if s] == [
        "asia",
        "london",
        "new_york_am",
        "new_york_pm",
    ]
    assert [s.start for s in named if s] == [
        ny(2025, 6, 10, 18),
        ny(2025, 6, 11, 0),
        ny(2025, 6, 11, 6),
        ny(2025, 6, 11, 12),
    ]


def test_the_quarter_called_london_is_not_this_repos_london_killzone():
    """The honest answer to 'does 00:00-06:00 New York mean London'. It does not."""
    q2 = intraday_session(ny(2025, 6, 11, 2))

    assert q2 is not None
    assert q2.session == "london"
    assert (q2.start, q2.end) == (ny(2025, 6, 11, 0), ny(2025, 6, 11, 6))

    # `pools.SESSIONS["london"]` is 02:00-05:00 New York: three hours strictly
    # inside a six-hour box, sharing NEITHER edge with it.
    assert KILLZONES["london"] == (2, 0, 5, 0, 0)
    assert q2.killzone == (ny(2025, 6, 11, 2), ny(2025, 6, 11, 5))
    assert q2.same_window is False
    assert q2.start < q2.killzone[0] and q2.killzone[1] < q2.end


def test_the_quarter_called_asia_is_an_hour_wider_than_the_asian_session():
    q1 = intraday_session(ny(2025, 6, 10, 20))

    assert q1 is not None
    assert (q1.start, q1.end) == (ny(2025, 6, 10, 18), ny(2025, 6, 11, 0))
    # 19:00 to midnight, so the box starts a full hour before the session does.
    assert q1.killzone == (ny(2025, 6, 10, 19), ny(2025, 6, 11, 0))
    assert q1.same_window is False


def test_the_new_york_halves_have_no_killzone_in_this_repo_and_say_so():
    for at in (ny(2025, 6, 11, 8), ny(2025, 6, 11, 14)):
        named = intraday_session(at)
        assert named is not None
        # None is "this repo defines no window of that name", which is not the
        # same as a window that happens to match.
        assert named.killzone is None
        assert named.same_window is False


# --------------------------------------------------------------------------
# 3. Chains


def test_a_chain_is_the_quarter_number_at_each_degree_outermost_first():
    # 07:00 New York on 2025-06-11, counted by hand:
    #   day      06:00-12:00 is Q3                                  -> 3
    #   session  Q3's fourths open 06:00 07:30 09:00 10:30 -> Q1    -> 1
    #   micro    Q1's fourths open 06:00 06:22:30 06:45 07:07:30    -> Q3
    found = chain(ny(2025, 6, 11, 7), NESTED)

    assert found is not None
    assert found.quarters == (3, 1, 3)
    assert found.text == "3-1-3"
    assert found.compact == "313"
    assert found.degrees == NESTED


def test_the_chain_changes_at_a_known_quarter_boundary_and_not_a_second_early():
    # 09:45:00 New York opens the third micro quarter of the third session
    # quarter of the day's Q3, so 332 becomes 333 exactly there.
    before = chain(ny(2025, 6, 11, 9, 44), NESTED)
    after = chain(ny(2025, 6, 11, 9, 45), NESTED)

    assert before is not None and after is not None
    assert before.compact == "332"
    assert after.compact == "333"
    # And the boundary is the grid's own, not a number spelled in this file.
    micro = quarters("micro", ny(2025, 6, 11, 9, 45), ny(2025, 6, 11, 9, 45))
    assert micro[0].start == ny(2025, 6, 11, 9, 45)


def test_a_chain_read_across_the_spring_forward_stretches_with_its_parent():
    # 2025-03-09: 02:00 EST becomes 03:00 EDT, so the day cycle's Q2 is FIVE real
    # hours, its sessions are 75 minutes and its micros 1125 seconds.
    #
    # 03:00 EDT is 7200 seconds into that Q2:
    #   day      Q2                                          -> 2
    #   session  fourths of 4500s: 0 4500 9000 13500 -> Q2   -> 2
    #   micro    fourths of 1125s: 4500 5625 6750 7875 -> Q3 -> 3
    found = chain(ny(2025, 3, 9, 3), NESTED)

    assert found is not None
    assert found.compact == "223"
    # A grid that assumed a six-hour Q2 puts the same instant in micro Q2 and
    # returns 222 - one digit wrong, twice a year, silently.
    assert found.compact != "222"

    q2 = quarters("day", ny(2025, 3, 9, 3), ny(2025, 3, 9, 3))
    assert q2[0].end - q2[0].start == 5 * HOUR


def test_membership_says_the_chain_is_in_his_list_and_nothing_more():
    # 09:50 New York: day Q3, session Q3 (09:00-10:30), micro Q3 (09:45-10:07:30).
    listed = chain(ny(2025, 6, 11, 9, 50), NESTED)
    # 07:00 New York, computed above as 313, which he does not list.
    unlisted = chain(ny(2025, 6, 11, 7), NESTED)

    assert listed is not None and unlisted is not None
    assert (listed.compact, listed.in_his_list) == ("333", True)
    assert (unlisted.compact, unlisted.in_his_list) == ("313", False)

    # The flag is membership of a list he wrote down. Ten of the sixty-four
    # three-digit chains are in it, so being in it is a one-in-six event before
    # any market behaviour is involved, and nothing here has been measured
    # against outcomes.
    assert len(HIS_LIST) == 10
    assert BASE_RATE == 10 / 64


def test_his_ten_are_listed_and_a_neighbouring_chain_of_each_is_not():
    assert HIS_LIST == frozenset(
        {"111", "114", "141", "144", "222", "333", "411", "414", "441", "444"}
    )
    # 442 differs from a listed 441 by one digit and is not listed; nor are 223,
    # 313 or 332, all of which this file produces from real instants above.
    for absent in ("442", "223", "313", "332", "123"):
        assert absent not in HIS_LIST


def test_a_chain_that_is_not_three_digits_has_no_answer_rather_than_a_false_one():
    two = chain(ny(2025, 6, 11, 7), ("day", "session"))

    assert two is not None
    assert two.compact == "31"
    # His list names three-digit chains only, so the question does not apply.
    # None, not False - False would claim the list excluded it.
    assert two.in_his_list is None


def test_a_chain_including_the_week_degree_does_not_exist_on_a_friday():
    friday = ny(2025, 3, 14, 12)

    assert chain(friday, ("week", "day", "session")) is None
    # A partial chain would read as a different chain rather than a missing one,
    # so nothing is returned at all. The finer degrees still have quarters.
    assert chain(friday, NESTED) is not None


def test_degrees_handed_over_in_the_wrong_nesting_order_are_rejected():
    # A chain's meaning is "each successively finer degree", so a reversed list
    # would produce a string that reads like a chain and means the opposite.
    with pytest.raises(ValueError):
        chain(ny(2025, 6, 11, 7), ("micro", "session", "day"))
    with pytest.raises(ValueError):
        chain(ny(2025, 6, 11, 7), ("day", "day"))
    with pytest.raises(ValueError):
        chain(ny(2025, 6, 11, 7), ("fortnight", "day"))


def test_the_chain_reads_whatever_degrees_the_grid_currently_defines():
    # Read off `quarters.DEGREES` at call time, so a degree added to the grid
    # needs no edit here. The three coarsest and the three finest both work.
    for triple in (DEGREES[:3], DEGREES[-3:]):
        found = chain(ny(2025, 6, 11, 7), triple)
        assert found is not None
        assert found.degrees == tuple(triple)
        assert len(found.quarters) == 3


def test_a_chain_needs_no_candles_so_it_cannot_be_revised_by_a_later_bar():
    # Knowable at the bar it describes, and identical when asked again with a
    # month of hindsight, because hindsight is not an input.
    at = ny(2025, 6, 11, 7)

    assert chain(at, NESTED) == chain(at, NESTED)
    assert chain(at, NESTED).at == at


# --------------------------------------------------------------------------
# 4. The occurrence distribution, which measures no outcome


def hourly(start: int, count: int) -> list[Candle]:
    return [
        Candle(time=start + i * HOUR, open=1.0, high=1.0, low=1.0, close=1.0)
        for i in range(count)
    ]


def test_every_bar_examined_is_accounted_for_in_the_distribution():
    candles = hourly(ny(2025, 6, 9, 18), 96)  # four day cycles

    found = occurrences(candles, NESTED)

    assert found.bars == len(candles) == 96
    assert sum(found.counts.values()) + found.outside == found.bars
    assert found.outside == 0  # every instant is in some day cycle


def test_bars_in_time_that_belongs_to_no_quarter_are_counted_not_dropped():
    # Sunday 18:00 for a full week, so the Fridays are in the sample and belong
    # to no week quarter.
    candles = hourly(ny(2025, 6, 8, 18), 168)

    found = occurrences(candles, ("week", "day", "session"))

    assert found.outside > 0
    assert sum(found.counts.values()) + found.outside == found.bars == 168
    # The week's four quarters run Sunday 18:00 to Thursday 18:00, so everything
    # from Thursday 18:00 to the next Sunday 18:00 is in no week quarter at all:
    # the Friday day-cycle plus the weekend, 24 + 48 hourly bars.
    assert found.outside == 72


def test_the_distribution_reports_the_base_rate_beside_the_listed_share():
    candles = hourly(ny(2025, 6, 9, 18), 96)

    found = occurrences(candles, NESTED)

    assert found.base_rate == 10 / 64
    assert found.listed == sum(
        n for text, n in found.counts.items() if text in HIS_LIST
    )
    # Reported as a share so it can be read against the base rate. Neither number
    # says anything about what price did; no outcome is measured anywhere here.
    assert 0.0 <= found.listed_share <= 1.0


def test_the_distribution_counts_bars_and_nothing_about_price():
    # Identical timestamps, wildly different prices: the counts must not move.
    flat = hourly(ny(2025, 6, 9, 18), 96)
    wild = [
        Candle(time=c.time, open=1.0, high=999.0, low=0.001, close=500.0) for c in flat
    ]

    assert occurrences(flat, NESTED).counts == occurrences(wild, NESTED).counts
