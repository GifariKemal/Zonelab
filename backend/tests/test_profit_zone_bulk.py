"""`mark_profit_zones` stopped being a loop over `profit_zone_at`. Same stamps?

The loop is still the definition of the answer - `profit_zone_at` is untouched,
and this file asserts the bulk pass agrees with calling it once per zone. That
is the only claim the rewrite makes.

WHY IT WAS REWRITTEN. Profiled 12 September 2026 with all 25 layers on and 5,000
bars: the pass was 0.111s of a 0.625s draw. About 1,900 zones each scanned all
1,900, which is 3.4 million comparisons to produce 1,900 numbers.

WHAT THE CASES ARE FOR. The rewrite replaced two `>`/`<` comparisons with two
different bisects, and bisect has a left and a right for a reason: the loop
required a STRICTLY positive gap, so a wall sitting exactly on this zone's
proximal is not a wall. That is the mistake this rewrite could most plausibly
make, it never shows up on random floats, and it has its own case below.
"""

from __future__ import annotations

import random

import pytest

from app.models import Zone, ZoneSide, ZoneState
from app.models.primitives import Anatomy
from app.profit_zone import mark_profit_zones, profit_zone_at


def _zone(i, side, proximal, height=1.0, t_from=0, t_to=10**9, state=ZoneState.FRESH):
    top = proximal if side is ZoneSide.SUPPLY else proximal + height
    bottom = top - height
    return Zone(
        id=f"z{i}",
        kind="RBR" if side is ZoneSide.DEMAND else "RBD",
        side=side,
        top=top,
        bottom=bottom,
        proximal=proximal,
        distal=bottom if side is ZoneSide.DEMAND else top,
        time_from=t_from,
        time_to=t_to,
        state=state,
        # Not read by anything under test; present because the model demands it.
        formation_score=0.0,
        departure_atr=2.0,
        anatomy=Anatomy(
            leg_in_from=0, leg_in_to=1, base_from=1,
            base_to=2, leg_out_from=2, leg_out_to=3,
        ),
    )


def _loop_stamps(zones, now):
    """What the pass used to compute, straight from the untouched function."""
    return [profit_zone_at(z, zones, now) for z in zones]


def _bulk_stamps(zones, now):
    mark_profit_zones(zones, now)
    return [z.profit_zone_rr for z in zones]


@pytest.mark.parametrize("seed", range(12))
def test_the_bulk_pass_agrees_with_the_loop(seed):
    rng = random.Random(seed)
    zones = []
    for i in range(60):
        side = ZoneSide.DEMAND if rng.random() < 0.5 else ZoneSide.SUPPLY
        state = ZoneState.BROKEN if rng.random() < 0.25 else ZoneState.FRESH
        zones.append(
            _zone(
                i, side,
                proximal=round(rng.uniform(90, 110), 2),
                height=round(rng.uniform(0.2, 3.0), 2),
                t_from=rng.randint(0, 1000),
                t_to=rng.randint(0, 1000),
                state=state,
            )
        )
    now = 500
    want = _loop_stamps(zones, now)
    assert _bulk_stamps(zones, now) == want


def test_a_wall_exactly_on_the_proximal_is_not_a_wall():
    """`gap > 0` was strict, so bisect_right and bisect_left, not the reverse.

    A supply zone whose proximal equals a demand zone's proximal gives gap
    exactly 0. The loop skipped it. `bisect_left` in place of `bisect_right`
    would find it, and no random-float test would ever notice.
    """
    zones = [
        _zone(0, ZoneSide.DEMAND, 100.0, height=2.0),
        _zone(1, ZoneSide.SUPPLY, 100.0),
        _zone(2, ZoneSide.SUPPLY, 104.0),
    ]
    assert _bulk_stamps(zones, 500) == _loop_stamps(zones, 500)
    assert zones[0].profit_zone_rr == 2.0, "must reach past the tie to 104"


def test_a_zone_with_no_opposing_wall_is_none():
    zones = [_zone(0, ZoneSide.DEMAND, 100.0), _zone(1, ZoneSide.DEMAND, 105.0)]
    assert _bulk_stamps(zones, 500) == _loop_stamps(zones, 500) == [None, None]


def test_a_wall_behind_the_entry_does_not_count():
    """Direction matters: a supply zone BELOW a demand zone is not ahead of it."""
    zones = [
        _zone(0, ZoneSide.DEMAND, 100.0, height=1.0),
        _zone(1, ZoneSide.SUPPLY, 90.0),
    ]
    assert _bulk_stamps(zones, 500) == _loop_stamps(zones, 500) == [None, None]


def test_a_wall_that_had_not_formed_yet_does_not_count():
    zones = [
        _zone(0, ZoneSide.DEMAND, 100.0, height=1.0),
        _zone(1, ZoneSide.SUPPLY, 102.0, t_from=900),
    ]
    assert _bulk_stamps(zones, 500) == _loop_stamps(zones, 500)
    assert zones[0].profit_zone_rr is None


def test_a_wall_already_broken_does_not_count():
    zones = [
        _zone(0, ZoneSide.DEMAND, 100.0, height=1.0),
        _zone(1, ZoneSide.SUPPLY, 102.0, t_to=100, state=ZoneState.BROKEN),
        _zone(2, ZoneSide.SUPPLY, 106.0),
    ]
    assert _bulk_stamps(zones, 500) == _loop_stamps(zones, 500)
    assert zones[0].profit_zone_rr == 6.0, "the broken wall at 102 is gone"


def test_a_zero_height_zone_is_none_rather_than_a_division():
    zones = [
        _zone(0, ZoneSide.DEMAND, 100.0, height=0.0),
        _zone(1, ZoneSide.SUPPLY, 102.0),
    ]
    assert _bulk_stamps(zones, 500) == _loop_stamps(zones, 500)
    assert zones[0].profit_zone_rr is None


def test_an_empty_list_does_nothing():
    zones: list[Zone] = []
    mark_profit_zones(zones, 500)
    assert zones == []
