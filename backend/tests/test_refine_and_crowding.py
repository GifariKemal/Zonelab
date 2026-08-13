"""Refinement and the road-ahead check, on series where the answer is known.

Both features change a zone after the detector has finished with it, which is a
place bugs hide well: the numbers still look like zone numbers, and the only way
to catch a wrong one is to build a series whose correct answer is arithmetic.

Run with:  .venv\\Scripts\\python -m pytest tests -q
"""

from __future__ import annotations

import pytest

from app.detect.supply_demand import detect
from app.models import (
    Anatomy,
    Candle,
    SupplyDemandParams,
    Zone,
    ZoneKind,
    ZoneSide,
    ZoneState,
)
from app.profit_zone import mark_crowding
from app.refine import refine_zones
from app.resample import resample

STEP = 900  # 15-minute bars
HTF = "1h"  # exactly four of them
# Anchored to a day boundary so every group of four bars is one whole HTF bucket.
# An unaligned start splits the fixture across buckets and the "known" answer
# stops being known.
T0 = 1_700_000_000 // 86_400 * 86_400


def bar(t: int, o: float, c: float, hp: float, lp: float) -> Candle:
    return Candle(
        time=t, open=o, close=c, high=max(o, c) + hp, low=min(o, c) - lp, volume=1000.0
    )


def series(dip_close: float | None = None, wide: bool = True) -> list[Candle]:
    """Drop, then a base that is WIDE for one HTF bar and TIGHT for the next.

    The whole point of the fixture is that the two halves differ. On the higher
    timeframe they merge into one 6-point box; the tight half is only visible to
    a series that still has the lower-timeframe bars, which is exactly the
    information refinement is supposed to recover.

    `dip_close` appends a bar that closes inside the wide box but below the
    tight one, so the two boxes give different answers about whether the zone is
    still alive.
    """
    rows: list[Candle] = []
    t = T0

    for _ in range(16):  # 4 HTF bars of quiet, so ATR has something to warm on
        rows.append(bar(t, 100.0, 100.0, 0.5, 0.5))
        t += STEP

    price = 100.0
    for _ in range(4):  # one HTF bar of drop
        rows.append(bar(t, price, price - 2.0, 0.0, 0.0))
        price -= 2.0
        t += STEP

    for _ in range(4):  # wide half of the base: high 95, low 89
        rows.append(bar(t, 92.0, 92.0, 3.0 if wide else 0.5, 3.0 if wide else 0.5))
        t += STEP
    for _ in range(4):  # tight half: high 92.5, low 91.5
        rows.append(bar(t, 92.0, 92.0, 0.5, 0.5))
        t += STEP

    price = 92.0
    for _ in range(4):  # one HTF bar of rally, far enough to clear the gate
        rows.append(bar(t, price, price + 5.0, 0.0, 0.0))
        price += 5.0
        t += STEP

    for _ in range(8):
        rows.append(bar(t, price, price, 0.5, 0.5))
        t += STEP

    if dip_close is not None:
        for _ in range(4):
            rows.append(bar(t, price, dip_close, 0.5, 0.5))
            price = dip_close
            t += STEP

    return rows


def params(**overrides) -> SupplyDemandParams:
    base = {
        "atr_period": 5,
        "base_max_bars": 4,  # so the inner pause clips to the tight half exactly
        "base_max_atr": 4.0,
        "max_zones_per_side": 100,
        "merge_overlap_pct": 1.0,
        "show_broken": True,
    }
    return SupplyDemandParams(**(base | overrides))


def one_zone(rows: list[Candle], p: SupplyDemandParams) -> tuple[Zone, list[Candle]]:
    """The DBR the fixture is built around, plus the bars it was found on.

    Selected by formation rather than by position: the dip variant creates a
    second, incidental supply zone, and an index would silently start testing
    that one instead.
    """
    higher = resample(rows, HTF, "15m")
    zones, _ = detect(higher, p)
    picked = [z for z in zones if z.kind is ZoneKind.DBR]
    assert len(picked) == 1, f"fixture should yield one DBR, got {len(picked)}"
    return picked[0], higher


# --------------------------------------------------------------------------
# Refinement
# --------------------------------------------------------------------------


def test_the_higher_timeframe_box_spans_the_whole_base():
    """The premise. If this fails the other tests prove nothing."""
    p = params()
    zone, _ = one_zone(series(), p)

    assert zone.side is ZoneSide.DEMAND
    assert zone.kind is ZoneKind.DBR
    assert zone.top == pytest.approx(95.0)  # wick high of the wide half
    assert zone.bottom == pytest.approx(89.0)  # wick low of the wide half


def test_refinement_cuts_the_box_down_to_the_inner_pause():
    p = params()
    rows = series()
    zone, higher = one_zone(rows, p)

    stats = refine_zones([zone], higher, rows, HTF, p)

    assert stats["refined"] == 1
    assert zone.top == pytest.approx(92.5)
    assert zone.bottom == pytest.approx(91.5)
    # Demand: proximal is the edge price meets on the way down, distal is below.
    assert zone.proximal == pytest.approx(92.5)
    assert zone.distal == pytest.approx(91.5)


def test_a_refined_zone_says_where_it_came_from():
    p = params()
    rows = series()
    zone, higher = one_zone(rows, p)
    refine_zones([zone], higher, rows, HTF, p)

    assert zone.refinement is not None
    assert zone.refinement.from_top == pytest.approx(95.0)
    assert zone.refinement.from_bottom == pytest.approx(89.0)
    assert zone.refinement.shrank_to == pytest.approx(1.0 / 6.0, abs=1e-3)
    assert zone.refinement.bars == 4
    # The refined box is cut from the LAST four lower-timeframe bars of the base,
    # which are bars 24..27 of the fixture.
    assert zone.refinement.time_from == T0 + 24 * STEP
    assert zone.refinement.time_to == T0 + 27 * STEP


def test_the_refined_box_never_reaches_outside_the_original():
    """The stop may only move inward. A refined distal that sat below the
    original would loosen the very stop refinement exists to tighten."""
    p = params()
    rows = series()
    zone, higher = one_zone(rows, p)
    before_top, before_bottom = zone.top, zone.bottom

    refine_zones([zone], higher, rows, HTF, p)

    assert zone.top <= before_top
    assert zone.bottom >= before_bottom


def test_refinement_recomputes_the_lifecycle_it_invalidated():
    """The test that justifies the whole re-replay.

    Price closes at 91, which is inside the wide box (89 to 95) and below the
    tight one (91.5 to 92.5). The unrefined zone is alive and merely tested; the
    refined zone is dead. Carrying the old state across would draw a broken zone
    as a live one.
    """
    p = params()
    rows = series(dip_close=91.0)
    zone, higher = one_zone(rows, p)

    assert zone.state is not ZoneState.BROKEN

    refine_zones([zone], higher, rows, HTF, p)

    assert zone.state is ZoneState.BROKEN


def test_a_base_with_no_inner_detail_is_left_alone_and_counted():
    """When every lower-timeframe bar in the base is one undivided pause, the
    refined box IS the box. Refinement has to be a no-op that says so: a silent
    no-op is indistinguishable from a feature that works."""
    p = params()
    rows = series(wide=False)  # both halves tight, so the base is uniform
    zone, higher = one_zone(rows, p)
    top, bottom = zone.top, zone.bottom

    stats = refine_zones([zone], higher, rows, HTF, p)

    assert stats["refined"] == 0
    assert stats["refine_no_gain"] == 1
    assert (zone.top, zone.bottom) == (top, bottom)
    assert zone.refinement is None


# --------------------------------------------------------------------------
# The road ahead
# --------------------------------------------------------------------------

ANATOMY = Anatomy(
    leg_in_from=0, leg_in_to=1, base_run_from=2, base_from=2, base_to=3,
    leg_out_from=4, leg_out_to=5,
)


def zone(
    side: ZoneSide,
    proximal: float,
    height: float,
    born: int,
    dies: int = 10_000,
    state: ZoneState = ZoneState.FRESH,
) -> Zone:
    """A zone reduced to the five fields the road check actually reads."""
    top, bottom = (
        (proximal, proximal - height)
        if side is ZoneSide.DEMAND
        else (proximal + height, proximal)
    )
    return Zone(
        id=f"{side.value}-{born}-{proximal}",
        kind=ZoneKind.RBR if side is ZoneSide.DEMAND else ZoneKind.DBD,
        side=side,
        state=state,
        top=top,
        bottom=bottom,
        proximal=proximal,
        distal=bottom if side is ZoneSide.DEMAND else top,
        time_from=born,
        time_to=dies,
        formation_score=0.5,
        departure_atr=3.0,
        anatomy=ANATOMY,
    )


def test_a_zone_with_a_clear_road_is_never_marked_crowded():
    demand = zone(ZoneSide.DEMAND, 100.0, 2.0, born=100)
    supply = zone(ZoneSide.SUPPLY, 120.0, 2.0, born=200)  # 10x the height away

    mark_crowding([demand, supply], min_rr=3.0)

    assert demand.crowded_at is None


def test_a_newly_born_opposing_zone_closes_the_road():
    """The event this feature exists for: nothing about the demand zone changed
    and price did not move, yet it stopped being a trade."""
    demand = zone(ZoneSide.DEMAND, 100.0, 2.0, born=100)
    far = zone(ZoneSide.SUPPLY, 120.0, 2.0, born=100)  # 10.0 heights of road
    near = zone(ZoneSide.SUPPLY, 104.0, 2.0, born=500)  # 2.0 heights of road

    mark_crowding([demand, far, near], min_rr=3.0)

    assert demand.crowded_at == 500


def test_the_road_is_measured_only_against_zones_that_already_existed():
    """A wall that had not been built yet was not in the way. Reading it early
    is the same look-ahead error as scoring a zone with its own future."""
    demand = zone(ZoneSide.DEMAND, 100.0, 2.0, born=100)
    near = zone(ZoneSide.SUPPLY, 104.0, 2.0, born=900)

    mark_crowding([demand, near], min_rr=3.0)

    assert demand.crowded_at == 900  # not 100, when the demand zone was born


def test_a_zone_born_into_a_shut_road_is_marked_at_its_own_birth():
    demand = zone(ZoneSide.DEMAND, 100.0, 2.0, born=700)
    near = zone(ZoneSide.SUPPLY, 104.0, 2.0, born=100)

    mark_crowding([demand, near], min_rr=3.0)

    assert demand.crowded_at == 700


def test_a_wall_price_already_broke_is_not_a_wall():
    demand = zone(ZoneSide.DEMAND, 100.0, 2.0, born=100)
    dead = zone(
        ZoneSide.SUPPLY, 104.0, 2.0, born=200, dies=300, state=ZoneState.BROKEN
    )

    mark_crowding([demand, dead], min_rr=3.0)

    assert demand.crowded_at == 200  # shut while it stood...
    assert dead.time_to == 300  # ...and the record says when it stopped standing


def test_the_check_is_off_at_zero():
    """Zero is the shipped default and has to mean OFF, not 'a road of zero is
    always long enough', which would be indistinguishable until someone read
    the code."""
    demand = zone(ZoneSide.DEMAND, 100.0, 2.0, born=100)
    near = zone(ZoneSide.SUPPLY, 100.5, 2.0, born=200)

    mark_crowding([demand, near], min_rr=0.0)

    assert demand.crowded_at is None
