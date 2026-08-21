"""Higher-timeframe nesting, on zones whose answer is arithmetic.

This module had NO unit test until now. Its only check lived in
`tools/validate_api.py` and asked whether both cohorts - nested and standalone -
appeared in a live chart, which is a question about today's market rather than
about the code. It failed on 2026-08-17 with "0 nested, 7 alone" because a
1000-bar window happened to hold a single 4h zone, and it failed again on the
synthetic provider, whose prices are seeded but whose TIME anchor is `now`, so
the higher-timeframe buckets slide with the wall clock.

The four conditions in `mark_nesting` are each a way of being wrong, so each one
gets a zone built to violate exactly it and nothing else.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_confluence.py -q
"""

from __future__ import annotations

from app.confluence import CONTAINMENT, mark_nesting
from app.models import Anatomy, Zone, ZoneKind, ZoneSide, ZoneState

HOUR = 3600


def zone(
    *,
    top: float,
    bottom: float,
    time_from: int,
    time_to: int,
    side: ZoneSide = ZoneSide.DEMAND,
    timeframe: str = "15m",
) -> Zone:
    return Zone(
        id=f"{timeframe}-{time_from}-{top}",
        kind=ZoneKind.DBR,
        side=side,
        state=ZoneState.FRESH,
        timeframe=timeframe,
        top=top,
        bottom=bottom,
        proximal=top,
        distal=bottom,
        time_from=time_from,
        time_to=time_to,
        formation_score=0.0,
        departure_atr=3.0,
        anatomy=Anatomy(
            leg_in_from=0, leg_in_to=1, base_run_from=2,
            base_from=2, base_to=3, leg_out_from=4, leg_out_to=5,
        ),
    )


def htf(**kw) -> Zone:
    return zone(timeframe="4h", **kw)


# One higher-timeframe demand zone, born early, still alive, 10 wide.
PARENT = htf(top=110.0, bottom=100.0, time_from=0, time_to=100 * HOUR)


def test_a_local_zone_inside_a_live_higher_zone_is_nested():
    local = zone(top=106.0, bottom=104.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([local], [PARENT])

    assert local.nested_in == ["4h"]


def test_a_zone_that_merely_touches_the_edge_is_not_nested():
    """The strictness IS the feature. A first attempt used bare overlap and
    marked 226 of 234 zones as nested; a condition 97% of cases satisfy cannot
    distinguish anything, so the containment floor is what makes the field
    measurable at all."""
    # Height 4, and only 1 of it (from 100 to 101) lies inside the parent, which
    # is 25% against the 80% the rule demands.
    local = zone(top=101.0, bottom=97.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([local], [PARENT])

    assert local.nested_in == []


def test_containment_is_measured_against_the_local_zones_own_height():
    """Exactly at the floor passes, just under it does not - pinned so a change
    to CONTAINMENT cannot pass silently."""
    height = 5.0
    just_in = zone(
        top=100.0 + CONTAINMENT * height,
        bottom=100.0 + CONTAINMENT * height - height,
        time_from=10 * HOUR,
        time_to=20 * HOUR,
    )
    just_out = zone(
        top=100.0 + CONTAINMENT * height - 0.01,
        bottom=100.0 + CONTAINMENT * height - 0.01 - height,
        time_from=10 * HOUR,
        time_to=20 * HOUR,
    )

    mark_nesting([just_in, just_out], [PARENT])

    assert just_in.nested_in == ["4h"]
    assert just_out.nested_in == []


def test_an_opposing_higher_zone_is_a_conflict_and_never_confluence():
    supply_parent = htf(
        top=110.0, bottom=100.0, time_from=0, time_to=100 * HOUR,
        side=ZoneSide.SUPPLY,
    )
    local = zone(top=106.0, bottom=104.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([local], [supply_parent])

    assert local.nested_in == []


def test_a_higher_zone_born_later_is_hindsight_and_does_not_count():
    """The causal condition, and the reason it exists: an HTF zone that formed
    AFTER the local one could not have provided context at the time, so counting
    it would be reading the answer off the future."""
    late = htf(top=110.0, bottom=100.0, time_from=50 * HOUR, time_to=100 * HOUR)
    local = zone(top=106.0, bottom=104.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([local], [late])

    assert local.nested_in == []


def test_a_higher_zone_born_on_the_same_bar_is_the_same_event_twice():
    same_bar = htf(top=110.0, bottom=100.0, time_from=10 * HOUR, time_to=100 * HOUR)
    local = zone(top=106.0, bottom=104.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([local], [same_bar])

    assert local.nested_in == []


def test_a_higher_zone_already_dead_offers_no_context():
    dead = htf(top=110.0, bottom=100.0, time_from=0, time_to=5 * HOUR)
    local = zone(top=106.0, bottom=104.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([local], [dead])

    assert local.nested_in == []


def test_both_cohorts_exist_in_one_pass():
    """The assertion the API contract test was really reaching for, asked where
    the answer is arithmetic instead of where it depends on the session."""
    inside = zone(top=106.0, bottom=104.0, time_from=10 * HOUR, time_to=20 * HOUR)
    outside = zone(top=90.0, bottom=88.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([inside, outside], [PARENT])

    assert [z.nested_in for z in (inside, outside)] == [["4h"], []]


def test_only_higher_timeframes_are_named_and_never_repeated():
    """Two parents on the same timeframe must name it once: the field is a set of
    timeframes, not a count of boxes."""
    second = htf(top=112.0, bottom=101.0, time_from=1 * HOUR, time_to=100 * HOUR)
    local = zone(top=106.0, bottom=104.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([local], [PARENT, second])

    assert local.nested_in == ["4h"]


def test_a_zero_height_zone_is_skipped_rather_than_dividing_by_zero():
    flat = zone(top=105.0, bottom=105.0, time_from=10 * HOUR, time_to=20 * HOUR)

    mark_nesting([flat], [PARENT])

    assert flat.nested_in == []
