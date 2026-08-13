"""Golden-fixture tests for the zone engine.

Every series here is hand-built so the correct answer is known by construction,
not by eyeballing a chart. Geometry assertions are exact: if a boundary moves by
a tick, that is a behaviour change and the test should say so.

Run with:  .venv\\Scripts\\python -m pytest tests -q
"""

from __future__ import annotations

import numpy as np
import pytest

from app.detect.supply_demand import detect
from app.indicators import classify_candles, runs, wilder_atr
from app.models import Candle, SupplyDemandParams, ZoneKind, ZoneSide, ZoneState
from app.providers.base import normalize

STEP = 900  # 15-minute bars
T0 = 1_700_000_000


def build(rows: list[tuple[float, float, float, float]]) -> list[Candle]:
    """rows are (open, close, high_pad, low_pad); pads extend beyond the body."""
    return [
        Candle(
            time=T0 + i * STEP,
            open=o,
            high=max(o, c) + hp,
            low=min(o, c) - lp,
            close=c,
            volume=1000.0,
        )
        for i, (o, c, hp, lp) in enumerate(rows)
    ]


def flat(price: float, n: int) -> list[tuple[float, float, float, float]]:
    """Doji bars: zero body, range 1.0. Always classified as base."""
    return [(price, price, 0.5, 0.5)] * n


def leg(start: float, step: float, n: int) -> list[tuple[float, float, float, float]]:
    """Full-body marubozu bars. Always classified as an impulse."""
    out = []
    price = start
    for _ in range(n):
        out.append((price, price + step, 0.0, 0.0))
        price += step
    return out


def params(**overrides) -> SupplyDemandParams:
    base = {
        "atr_period": 5,
        "impulse_atr": 1.0,
        "base_max_bars": 6,
        "base_max_atr": 2.5,
        "departure_min_atr": 2.0,
    }
    return SupplyDemandParams(**(base | overrides))


# --------------------------------------------------------------------------
# indicators
# --------------------------------------------------------------------------


def test_atr_is_never_nan_during_warmup():
    """A NaN ATR would disable every threshold that divides by it, silently."""
    candles = build(flat(100, 3))
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])

    atr = wilder_atr(high, low, close, period=14)  # period exceeds bar count
    assert len(atr) == 3
    assert np.isfinite(atr).all()
    assert atr[0] == pytest.approx(1.0)


def test_classify_partitions_every_bar():
    candles = build(flat(100, 8) + leg(100, -4, 3))
    arrays = [np.array([getattr(c, f) for c in candles]) for f in ("open", "high", "low", "close")]
    atr = wilder_atr(arrays[1], arrays[2], arrays[3], 5)

    labels = classify_candles(*arrays, atr, 0.5, 1.0)
    assert set(labels[:8]) == {0}, "doji bars must be base"
    assert set(labels[8:]) == {-1}, "marubozu down bars must be impulse-down"


def test_runs_compresses_and_is_inclusive():
    assert runs(np.array([0, 0, 1, 1, 1, 0])) == [(0, 0, 1), (1, 2, 4), (0, 5, 5)]
    assert runs(np.array([], dtype=np.int8)) == []


# --------------------------------------------------------------------------
# the four formations
# --------------------------------------------------------------------------

# (leg-in step, leg-out step) -> (formation, side)
FORMATIONS = [
    (-4.0, +4.0, ZoneKind.DBR, ZoneSide.DEMAND),
    (+4.0, +4.0, ZoneKind.RBR, ZoneSide.DEMAND),
    (+4.0, -4.0, ZoneKind.RBD, ZoneSide.SUPPLY),
    (-4.0, -4.0, ZoneKind.DBD, ZoneSide.SUPPLY),
]


@pytest.mark.parametrize("in_step,out_step,kind,side", FORMATIONS)
def test_each_formation_is_found_with_exact_geometry(in_step, out_step, kind, side):
    base_price = 100 + in_step * 3
    candles = build(
        flat(100, 10)
        + leg(100, in_step, 3)
        + flat(base_price, 2)
        + leg(base_price, out_step, 3)
        + flat(base_price + out_step * 3, 5)
    )

    zones, stats = detect(candles, params())

    assert len(zones) == 1, f"expected exactly one zone, stats={stats}"
    zone = zones[0]
    assert zone.kind is kind
    assert zone.side is side

    # The base is two doji bars at base_price with 0.5 pads on each side.
    assert zone.top == pytest.approx(base_price + 0.5)
    assert zone.bottom == pytest.approx(base_price - 0.5)

    # Proximal is the edge price meets first coming back; distal is the far one.
    if side is ZoneSide.DEMAND:
        assert (zone.proximal, zone.distal) == (zone.top, zone.bottom)
    else:
        assert (zone.proximal, zone.distal) == (zone.bottom, zone.top)

    assert zone.anatomy.leg_in_from == 10 and zone.anatomy.leg_in_to == 12
    assert zone.anatomy.base_from == 13 and zone.anatomy.base_to == 14
    assert zone.anatomy.leg_out_from == 15 and zone.anatomy.leg_out_to == 17

    assert zone.state is ZoneState.FRESH
    assert zone.touches == 0
    assert zone.time_from == T0 + 13 * STEP
    assert zone.departure_atr > 2.0
    assert 0.0 <= zone.strength <= 1.0
    assert sum(zone.factors.values()) == pytest.approx(zone.strength, abs=1e-3)


# --------------------------------------------------------------------------
# quality gates
# --------------------------------------------------------------------------


def test_weak_departure_is_rejected_and_counted():
    """A move that stalls right after the base is not a zone. The rejection has
    to be visible in stats, or the UI cannot explain an empty chart."""
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 2) + leg(88, +2.0, 1) + flat(90, 6)
    )

    zones, stats = detect(candles, params())

    assert zones == []
    assert stats["candidates"] == 1
    assert stats["rejected_weak_departure"] == 1


def test_departure_gate_can_be_relaxed():
    """Same bars, lower threshold: the candidate was real, only under-sized."""
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 2) + leg(88, +2.0, 1) + flat(90, 6)
    )

    zones, _ = detect(candles, params(departure_min_atr=0.5))
    assert len(zones) == 1
    assert zones[0].kind is ZoneKind.DBR


def test_base_taller_than_limit_is_rejected():
    """A wide, sloppy base is a range, not an origin.

    The leg-out has to be scaled up too: a tall base drags ATR up with it, and
    an ordinary 4-point departure would no longer read as an impulse at all -
    the pattern would never reach the height gate under test.
    """
    wide_base = [(88.0, 88.0, 3.5, 3.5), (88.0, 88.0, 3.5, 3.5)]  # 7.0 tall
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + wide_base + leg(88, +10.0, 3) + flat(118, 5)
    )

    zones, stats = detect(candles, params())
    assert stats["candidates"] == 1, "the formation itself must be recognised"
    assert stats["rejected_base_too_tall"] == 1
    assert zones == []


def test_long_consolidation_clips_to_the_bars_the_move_left_from():
    """A 12-bar base is still a valid origin; the zone is the last few candles
    before the departure, not the whole range."""
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 12) + leg(88, +4.0, 3) + flat(100, 5)
    )

    zones, _ = detect(candles, params(base_max_bars=4))
    assert len(zones) == 1
    anatomy = zones[0].anatomy
    assert anatomy.base_to == 24, "base ends on the bar before the leg-out"
    assert anatomy.base_from == 21, "clipped to the trailing base_max_bars bars"


def test_body_basis_makes_a_tighter_zone_than_wick_basis():
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 2) + leg(88, +4.0, 3) + flat(100, 5)
    )

    wick = detect(candles, params(zone_basis="wick"))[0][0]
    body = detect(candles, params(zone_basis="body"))[0][0]

    assert (wick.top, wick.bottom) == pytest.approx((88.5, 87.5))
    # Doji bodies collapse to a single price, so the body zone is the minimum
    # visible thickness rather than zero-height.
    assert body.top - body.bottom < wick.top - wick.bottom


# --------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------


def test_zone_becomes_tested_then_broken():
    """Price returns into the demand zone (tested), then closes below the distal
    line (broken). Both transitions must be observed on the same zone."""
    candles = build(
        flat(100, 10)
        + leg(100, -4.0, 3)
        + flat(88, 2)
        + leg(88, +4.0, 3)  # -> 100
        + leg(100, -4.0, 3)  # back down to 88, into the zone
        + leg(88, -4.0, 2)  # -> 80, closes well under the 87.5 distal
        + flat(80, 4)
    )

    zones, _ = detect(candles, params(show_broken=True))
    demand = [z for z in zones if z.side is ZoneSide.DEMAND and z.kind is ZoneKind.DBR]

    assert demand, "the original DBR must still be reported"
    zone = demand[0]
    assert zone.state is ZoneState.BROKEN
    assert zone.touches >= 1
    assert zone.first_test_time is not None
    # Right edge stops at the break instead of running to the last bar.
    assert zone.time_to < candles[-1].time


def test_broken_zones_are_hidden_by_default():
    candles = build(
        flat(100, 10)
        + leg(100, -4.0, 3)
        + flat(88, 2)
        + leg(88, +4.0, 3)
        + leg(100, -4.0, 5)
        + flat(80, 4)
    )

    visible = detect(candles, params())[0]
    with_broken = detect(candles, params(show_broken=True))[0]

    assert len(with_broken) > len(visible)
    assert all(z.state is not ZoneState.BROKEN for z in visible)


def test_consecutive_bars_inside_the_zone_count_as_one_test():
    """Five bars parked in a zone is one visit. Counting each bar would make
    freshness scoring meaningless."""
    candles = build(
        flat(100, 10)
        + leg(100, -4.0, 3)
        + flat(88, 2)
        + leg(88, +4.0, 3)
        + leg(100, -4.0, 3)  # returns to 88
        + flat(88, 5)  # sits inside the zone
        + leg(88, +4.0, 3)
        + flat(100, 3)
    )

    # Dedup off: the parked bars form a second base at the same price, and
    # merging them would hide the very zone whose touch count is under test.
    zones, _ = detect(candles, params(merge_overlap_pct=1.0))
    original = next(z for z in zones if z.anatomy.base_from == 13)
    assert original.touches == 1
    assert original.penetration_pct == pytest.approx(1.0)


# --------------------------------------------------------------------------
# dedup and caps
# --------------------------------------------------------------------------


def test_overlapping_zones_collapse_to_the_stronger_one():
    """Two departures from nearly the same price is one level, drawn once."""
    candles = build(
        flat(100, 10)
        + leg(100, -4.0, 3)
        + flat(88, 2)
        + leg(88, +4.0, 3)
        + leg(100, -4.0, 3)
        + flat(88.2, 2)  # second base overlapping the first
        + leg(88.2, +4.0, 3)
        + flat(100.2, 5)
    )

    merged, stats = detect(candles, params(merge_overlap_pct=0.6))
    split, _ = detect(candles, params(merge_overlap_pct=1.0))

    assert stats["rejected_overlap"] >= 1
    assert len(merged) < len(split)


def test_max_zones_per_side_is_enforced():
    rows = flat(100, 10)
    price = 100.0
    for _ in range(6):
        rows += leg(price, -4.0, 3)
        price -= 12
        rows += flat(price, 2)
        rows += leg(price, +4.0, 3)
        price += 12
        rows += leg(price, -4.0, 3)
        price -= 12
    candles = build(rows + flat(price, 5))

    zones, _ = detect(candles, params(max_zones_per_side=2, merge_overlap_pct=1.0))
    assert len([z for z in zones if z.side is ZoneSide.DEMAND]) <= 2
    assert len([z for z in zones if z.side is ZoneSide.SUPPLY]) <= 2


def test_short_series_returns_nothing_instead_of_raising():
    zones, stats = detect(build(flat(100, 4)), params())
    assert zones == []
    assert stats["bars"] == 4


# --------------------------------------------------------------------------
# causality: geometry must not repaint
# --------------------------------------------------------------------------


def test_confirmed_zone_geometry_never_changes_as_bars_arrive():
    """The non-repaint guarantee.

    Replay the series bar by bar. Any zone reported as confirmed at bar k must
    still exist at the end with byte-identical geometry. Lifecycle fields are
    allowed to move - a fresh zone legitimately becomes tested - but the box
    itself must never be redrawn under the user.
    """
    from app.providers.synthetic import generate

    # Every display filter is off. A cap or a dedup dropping a zone is a
    # presentation choice, not a repaint, and would make this test lie.
    unfiltered = params(
        show_broken=True,
        show_mitigated=True,
        max_zones_per_side=100,
        merge_overlap_pct=1.0,
    )

    candles = generate(bars=400, step=STEP, seed=11)
    final = {z.id: z for z in detect(candles, unfiltered)[0]}

    checked = 0
    for k in range(120, len(candles), 17):
        for zone in detect(candles[:k], unfiltered)[0]:
            if not zone.confirmed:
                continue
            assert zone.id in final, f"confirmed zone {zone.id} vanished by the end"
            later = final[zone.id]
            assert (zone.top, zone.bottom) == pytest.approx((later.top, later.bottom))
            assert zone.anatomy == later.anatomy
            checked += 1

    assert checked > 20, "fixture produced too few zones to prove anything"


def test_unconfirmed_zone_is_flagged_while_its_leg_out_is_still_open():
    """A zone whose leg-out run reaches the last bar can still grow."""
    candles = build(flat(100, 10) + leg(100, -4.0, 3) + flat(88, 2) + leg(88, +4.0, 3))

    zones, _ = detect(candles, params())
    assert len(zones) == 1
    assert zones[0].confirmed is False

    settled = detect(candles + build(flat(100, 3))[:3], params())[0]
    assert settled[0].confirmed is True


def test_doji_base_is_grown_to_the_minimum_height():
    """A zero-height zone can never register a touch, so it is never zero."""
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 2) + leg(88, +4.0, 3) + flat(100, 5)
    )

    zone = detect(candles, params(zone_basis="body", zone_min_atr=0.2))[0][0]
    assert zone.top > zone.bottom
    # Grown symmetrically about the doji price, which is 88.
    assert (zone.top + zone.bottom) / 2 == pytest.approx(88.0)


# --------------------------------------------------------------------------
# provider normalisation
# --------------------------------------------------------------------------


def test_normalize_dedupes_and_sorts():
    """Duplicate bar times crash the chart and double-count in the detector, so
    they are collapsed once at the provider boundary."""
    rows = [
        Candle(time=300, open=3, high=3, low=3, close=3),
        Candle(time=100, open=1, high=1, low=1, close=1),
        Candle(time=300, open=9, high=9, low=9, close=9),  # later wins
        Candle(time=200, open=2, high=2, low=2, close=2),
    ]

    out = normalize(rows, bars=10)
    assert [c.time for c in out] == [100, 200, 300]
    assert out[-1].close == 9

    assert [c.time for c in normalize(rows, bars=2)] == [200, 300]
