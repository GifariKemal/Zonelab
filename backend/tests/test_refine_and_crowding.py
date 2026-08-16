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


# --------------------------------------------------------------------------
# fair value gaps and order blocks
# --------------------------------------------------------------------------

from app.detect.imbalance import detect_fvg, detect_order_block  # noqa: E402
from app.models import ImbalanceParams  # noqa: E402


def imb(**overrides) -> ImbalanceParams:
    base = {"atr_period": 5, "min_gap_atr": 0.0, "displacement_atr": 1.0,
            "displacement_bars": 3, "max_zones_per_side": 0, "show_broken": True}
    return ImbalanceParams(**(base | overrides))


def calm(n: int, price: float = 100.0) -> list[Candle]:
    return [bar(T0 + i * STEP, price, price, 0.5, 0.5) for i in range(n)]


def test_a_gap_is_the_band_the_middle_bar_flew_through():
    """Three bars whose outer wicks never met. The box is exactly that band,
    and nothing about it is a judgement call."""
    rows = calm(20)
    t = T0 + 20 * STEP
    rows.append(bar(t, 100.0, 100.0, 0.5, 0.5))          # first: high 100.5
    rows.append(bar(t + STEP, 101.0, 106.0, 0.2, 0.2))   # the leap
    rows.append(bar(t + 2 * STEP, 106.0, 106.0, 0.5, 1.0))  # third: low 105.0
    rows += [bar(t + (3 + i) * STEP, 106.0, 106.0, 0.5, 0.5) for i in range(10)]

    zones, stats = detect_fvg(rows, imb())

    assert stats["candidates"] >= 1
    # Selected by ORIGIN bar, not by position. The leap leaves a second gap
    # between its own low and the bar after the third, which is correct and is
    # exactly the kind of thing an index-based assertion would test by accident.
    gap = [z for z in zones if z.time_from == t]
    assert len(gap) == 1
    assert gap[0].side is ZoneSide.DEMAND
    assert gap[0].bottom == pytest.approx(100.5)  # high of the first bar
    assert gap[0].top == pytest.approx(105.0)  # low of the third
    # Demand: price meets the top first coming down, the stop sits below.
    assert gap[0].proximal == pytest.approx(105.0)
    assert gap[0].distal == pytest.approx(100.5)


def test_the_bar_that_made_the_gap_does_not_count_as_testing_it():
    """The middle bar's range spans the whole gap by construction. If the
    lifecycle started before the third bar, every gap would be born already
    tested by the candle that created it."""
    rows = calm(20)
    t = T0 + 20 * STEP
    rows.append(bar(t, 100.0, 100.0, 0.5, 0.5))
    rows.append(bar(t + STEP, 101.0, 106.0, 0.2, 0.2))
    rows.append(bar(t + 2 * STEP, 106.0, 106.0, 0.5, 1.0))
    rows += [bar(t + (3 + i) * STEP, 106.0, 106.0, 0.5, 0.5) for i in range(10)]

    zones, _ = detect_fvg(rows, imb())
    gap = [z for z in zones if z.time_from == t][0]

    assert gap.touches == 0
    assert gap.state is ZoneState.FRESH


def test_a_gap_smaller_than_the_floor_is_counted_not_silently_dropped():
    rows = calm(20)
    t = T0 + 20 * STEP
    rows.append(bar(t, 100.0, 100.0, 0.5, 0.5))
    rows.append(bar(t + STEP, 100.6, 100.8, 0.05, 0.05))
    rows.append(bar(t + 2 * STEP, 100.9, 100.9, 0.2, 0.3))
    rows += [bar(t + (3 + i) * STEP, 100.9, 100.9, 0.2, 0.2) for i in range(10)]

    _, stats = detect_fvg(rows, imb(min_gap_atr=5.0))

    assert stats["candidates"] >= 1
    assert stats["rejected_too_small"] == stats["candidates"]


def test_an_order_block_is_the_last_opposite_candle_before_the_move():
    rows = calm(20)
    t = T0 + 20 * STEP
    # One down candle, then three up candles that travel far enough.
    rows.append(bar(t, 100.0, 99.0, 0.3, 0.4))  # the block: high 100.3, low 98.6
    price = 99.0
    for i in range(1, 6):
        rows.append(bar(t + i * STEP, price, price + 3.0, 0.0, 0.0))
        price += 3.0
    rows += [bar(t + (6 + i) * STEP, price, price, 0.5, 0.5) for i in range(10)]

    zones, _ = detect_order_block(rows, imb())
    blocks = [z for z in zones if z.side is ZoneSide.DEMAND and z.time_from == t]

    assert len(blocks) == 1
    # The WHOLE range of that candle, which is the choice this module states
    # rather than a convention it inherited.
    assert blocks[0].top == pytest.approx(100.3)
    assert blocks[0].bottom == pytest.approx(98.6)


def test_a_block_with_no_impulse_after_it_is_rejected_and_counted():
    rows = calm(20)
    t = T0 + 20 * STEP
    rows.append(bar(t, 100.0, 99.0, 0.3, 0.4))
    rows += [bar(t + (1 + i) * STEP, 99.0, 99.1, 0.1, 0.1) for i in range(10)]

    _, stats = detect_order_block(rows, imb(displacement_atr=5.0))

    assert stats["candidates"] > 0
    assert stats["rejected_weak_move"] == stats["candidates"]


def test_both_detectors_honour_zero_as_no_cap():
    """The same hazard as the supply/demand cap: it selects the NEWEST boxes,
    so a measurement taken through it is a measurement of the recent tail."""
    rows = calm(10)
    price = 100.0
    t = T0 + 10 * STEP
    for block in range(6):
        rows.append(bar(t, price, price - 1.0, 0.3, 0.4))
        t += STEP
        for _ in range(4):
            rows.append(bar(t, price, price + 2.0, 0.0, 0.0))
            price += 2.0
            t += STEP
        for _ in range(3):
            rows.append(bar(t, price, price, 0.4, 0.4))
            t += STEP

    uncapped, _ = detect_order_block(rows, imb(max_zones_per_side=0))
    capped, _ = detect_order_block(rows, imb(max_zones_per_side=1))

    assert len(uncapped) > len(capped)
    assert max(z.time_from for z in capped) == max(z.time_from for z in uncapped)


# --------------------------------------------------------------------------
# market structure
# --------------------------------------------------------------------------

import numpy as np  # noqa: E402

from app.detect.structure import bias_series, breaks, swings  # noqa: E402


def wave(points: list[float], per: int = 3) -> list[Candle]:
    """A zigzag through `points`, `per` bars per leg. Pivot bars are exact."""
    rows: list[Candle] = []
    t = T0
    for a, b in zip(points, points[1:]):
        for k in range(per):
            o = a + (b - a) * k / per
            c = a + (b - a) * (k + 1) / per
            rows.append(bar(t, o, c, 0.01, 0.01))
            t += STEP
    return rows


def test_a_swing_is_not_knowable_until_the_bars_to_its_right_have_printed():
    """The single rule that separates this from hindsight.

    A pivot at bar i is only confirmed at bar i+right. A detector that reacted
    to it at bar i would be reading bars that had not happened, and it would
    produce a beautiful directional edge made entirely of the future.
    """
    rows = wave([100, 110, 95, 115, 90], per=4)
    high = np.array([c.high for c in rows])
    low = np.array([c.low for c in rows])

    found = swings(high, low, left=2, right=2)

    assert found, "the fixture must produce pivots"
    for s in found:
        assert s.confirmed_at == s.index + 2
        assert s.confirmed_at > s.index


def test_no_break_ever_uses_a_swing_confirmed_after_it():
    rows = wave([100, 112, 96, 118, 92, 120], per=4)

    events, _ = breaks(rows, left=2, right=2)

    assert events, "the fixture must produce breaks"
    for e in events:
        assert e.swing_index < e.index


def test_a_wick_through_is_not_a_break():
    """A wick beyond a swing that closes back inside is a sweep, which most
    codifications treat as the OPPOSITE signal. Counting it as a break would
    merge two opposite events under one name."""
    rows = wave([100, 108, 100], per=4)
    t = rows[-1].time + STEP
    # A bar whose high pierces well above every prior high but closes below it.
    peak = max(c.high for c in rows)
    rows.append(bar(t, 100.0, 100.5, peak + 5 - 100.5, 0.5))
    rows += [bar(t + (1 + i) * STEP, 100.0, 100.0, 0.2, 0.2) for i in range(6)]

    events, _ = breaks(rows, left=2, right=2)
    before = bias_series(rows, left=2, right=2)

    pierced = [e for e in events if e.index == len(rows) - 7]
    assert pierced, "the wick through must be REPORTED, not silently dropped"
    assert all(e.kind == "SWEEP" for e in pierced)
    # Every genuine break must have closed beyond the level it broke.
    for e in events:
        if e.kind != "SWEEP":
            close = rows[e.index].close
            assert (close > e.level) if e.direction == 1 else (close < e.level)
    # And a sweep must not move the bias, or a wick could flip the trend.
    at = pierced[0].index
    assert before[at] == before[at - 1]


def test_the_first_break_is_a_bos_not_a_choch():
    """CHoCH means the character CHANGED. Before any break there is no
    character, so calling the first one a change claims a turn from nothing."""
    rows = wave([100, 112, 96, 118], per=4)

    events, _ = breaks(rows, left=2, right=2)

    assert events
    assert events[0].kind == "BOS"
    assert events[0].bias_before == 0


def test_bias_only_ever_uses_breaks_that_already_happened():
    rows = wave([100, 112, 96, 118, 92, 122], per=4)
    events, _ = breaks(rows, left=2, right=2)
    series = bias_series(rows, left=2, right=2)

    assert len(series) == len(rows)
    for e in events:
        assert series[e.index] == e.direction
        if e.index > 0:
            earlier = [x for x in events if x.index < e.index]
            expected = earlier[-1].direction if earlier else 0
            assert series[e.index - 1] == expected


def test_a_level_is_only_broken_once():
    """Without clearing the level after a break, every subsequent bar above it
    would emit another break and the event count would be meaningless."""
    rows = wave([100, 110, 100], per=4)
    t = rows[-1].time + STEP
    peak = max(c.high for c in rows)
    for i in range(8):  # eight bars all closing well above the swing high
        rows.append(bar(t + i * STEP, peak + 5, peak + 5, 0.2, 0.2))

    events, _ = breaks(rows, left=2, right=2)
    upward = [e for e in events if e.direction == 1]

    assert len(upward) == 1, f"one level, one break, got {len(upward)}"
