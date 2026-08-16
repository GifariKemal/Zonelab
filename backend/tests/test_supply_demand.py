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
    assert 0.0 <= zone.formation_score <= 1.0
    assert sum(zone.factors.values()) == pytest.approx(zone.formation_score, abs=1e-3)


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
    before the departure, not the whole range.

    The clip must not make the formation unreadable. Three visual reviewers
    independently reported the leg-in as "detached" on exactly these zones,
    because the anatomy placed it up to nine bars from the base with nothing in
    between. `base_run_from` keeps the whole consolidation addressable, so the
    sequence stays contiguous even though the box does not cover all of it.
    """
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 12) + leg(88, +4.0, 3) + flat(100, 5)
    )

    zones, _ = detect(candles, params(base_max_bars=4))
    assert len(zones) == 1
    anatomy = zones[0].anatomy
    assert anatomy.base_to == 24, "base ends on the bar before the leg-out"
    assert anatomy.base_from == 21, "clipped to the trailing base_max_bars bars"
    assert anatomy.base_run_from == 13, "the whole consolidation is still reported"
    assert anatomy.base_run_from == anatomy.leg_in_to + 1, (
        "leg-in must sit immediately before the consolidation it arrived into"
    )


def test_a_drifting_base_is_rejected_as_a_staircase():
    """A run of small candles walking one way is not a pause.

    This is the defect four independent visual audits named most often. The
    detector's per-candle test asks "is this bar small", which a staircase
    passes at every step while price travels the whole height of the supposed
    base. The gate is justified on fidelity: calibration found no measurable
    difference in outcomes, and the two are separate standards.
    """
    # Six base bars each 1.0 tall, stepping up 1.0 each time: every bar is
    # individually quiet, and together they climb the full height of the box.
    staircase = [(88.0 + i, 88.0 + i, 0.5, 0.5) for i in range(6)]
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + staircase + leg(93, +10.0, 3) + flat(123, 5)
    )

    zones, stats = detect(candles, params(max_base_drift=0.6))
    assert stats["candidates"] == 1, "the formation is still recognised"
    assert stats["rejected_base_drifted"] == 1
    assert zones == []

    # The same bars pass once the check is switched off, so the gate is what
    # removed them and not some other filter.
    assert len(detect(candles, params(max_base_drift=1.0))[0]) == 1


def test_a_genuine_pause_survives_the_drift_gate():
    """The guard must not remove the formation it exists to protect."""
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 4) + leg(88, +4.0, 3) + flat(100, 5)
    )

    zone = detect(candles, params(max_base_drift=0.6))[0][0]
    assert zone.base_drift == 0.0, "a flat base has no drift at all"


def test_body_basis_makes_a_tighter_zone_than_wick_basis():
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 2) + leg(88, +4.0, 3) + flat(100, 5)
    )

    wick = detect(candles, params(proximal_basis="wick"))[0][0]
    body = detect(candles, params(proximal_basis="body"))[0][0]

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


@pytest.mark.parametrize("basis", ["wick", "body"])
@pytest.mark.parametrize("in_step,out_step,kind,side", FORMATIONS)
def test_the_distal_is_always_the_wick_extreme(basis, in_step, out_step, kind, side):
    """The two lines are not symmetric, and this is the mistake that matters.

    The distal is the line the stop sits beyond, so it must cover the base's
    lowest low (demand) or highest high (supply) in BOTH variants. Only the
    proximal moves between aggressive (wick) and conservative (body). Drawing
    the distal at the body puts the stop inside the base it is protecting.
    """
    base_price = 100 + in_step * 3
    candles = build(
        flat(100, 10)
        + leg(100, in_step, 3)
        + flat(base_price, 2)
        + leg(base_price, out_step, 3)
        + flat(base_price + out_step * 3, 5)
    )

    zone = detect(candles, params(proximal_basis=basis))[0][0]

    # Base bars are doji at base_price with 0.5 pads, so wick extremes are
    # +/- 0.5 and both body edges collapse onto base_price itself.
    if side is ZoneSide.DEMAND:
        assert zone.distal == pytest.approx(base_price - 0.5), "demand distal is the low"
        assert zone.proximal == pytest.approx(base_price + (0.5 if basis == "wick" else 0.0))
    else:
        assert zone.distal == pytest.approx(base_price + 0.5), "supply distal is the high"
        assert zone.proximal == pytest.approx(base_price - (0.5 if basis == "wick" else 0.0))


def test_the_minimum_height_grows_the_proximal_not_the_distal():
    """Widening a thin zone must not move the stop line.

    A symmetric expansion would push the distal past the base's own extreme,
    which is the same defect as drawing the distal at the body, arrived at by
    a different route.
    """
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 2) + leg(88, +4.0, 3) + flat(100, 5)
    )

    zone = detect(candles, params(proximal_basis="body", zone_min_atr=2.0))[0][0]

    assert zone.top - zone.bottom > 0.5, "the zone was widened"
    assert zone.distal == pytest.approx(87.5), "the distal stayed on the base's low"
    assert zone.proximal > 88.0, "the proximal absorbed the whole widening"


def test_a_zero_height_base_is_dropped_rather_than_dividing_by_it():
    """zone_min_atr=0.0 is schema-valid, so the floor cannot be relied on.

    Every base bar here has open == high == low == close, so the box is exactly
    0 high and nothing grows it. The drift ratio divides by that height, which
    made this input a ZeroDivisionError and an unhandled 500.
    """
    flat_base = [(88.0, 88.0, 0.0, 0.0)] * 2
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat_base + leg(88, +4.0, 3) + flat(100, 5)
    )

    zones, _ = detect(candles, params(zone_min_atr=0.0))

    assert all(z.top - z.bottom > 0 for z in zones), "a zero-height box escaped"


# --------------------------------------------------------------------------
# calibration invariants
# --------------------------------------------------------------------------


def test_formation_score_holds_only_formation_factors():
    """Guard on what docs/CALIBRATION.md concluded.

    Two factors were removed from the composite on evidence, and both are easy
    to reintroduce by accident because both look reasonable:

    - `departure` measured as a threshold, not a gradient. Held rate rises to
      2 ATR then goes flat, so scoring it as a gradient adds noise to a ranking
      that is already indistinguishable from chance.
    - `freshness` is constant at the exact moment the score is read, because a
      zone is fresh by definition at its first touch.

    If either name reappears here, the calibration doc is out of date and
    whoever added it needs to re-measure first.
    """
    candles = build(
        flat(100, 10) + leg(100, -4.0, 3) + flat(88, 2) + leg(88, +4.0, 3) + flat(100, 5)
    )

    zone = detect(candles, params())[0][0]

    assert set(zone.factors) == {"tightness", "compactness", "volume"}
    assert sum(zone.factors.values()) == pytest.approx(zone.formation_score, abs=1e-3)
    # Equal thirds, deliberately unfitted: n=234 cannot justify a weighting.
    assert all(v <= 1 / 3 + 1e-6 for v in zone.factors.values())

    # The validated quantity is still reported, just not inside the composite.
    assert zone.departure_atr > 0


def test_dedupe_prefers_the_less_consumed_zone():
    """Display priority, not a quality claim: given two zones at one price, the
    one price has not eaten yet is the one worth drawing."""
    candles = build(
        flat(100, 10)
        + leg(100, -4.0, 3)
        + flat(88, 2)  # zone A, later revisited and eaten
        + leg(88, +4.0, 3)
        + leg(100, -4.0, 3)  # price returns and consumes A
        + flat(88, 2)  # zone B forms at the same price, untouched after
        + leg(88, +4.0, 3)
        + flat(100, 6)
    )

    merged = detect(candles, params(merge_overlap_pct=0.5))[0]
    survivors = [z for z in merged if z.side is ZoneSide.DEMAND]

    assert survivors, "the demand level must still be drawn once"
    assert survivors[0].state is ZoneState.FRESH


# --------------------------------------------------------------------------
# higher timeframe aggregation
# --------------------------------------------------------------------------


def test_resample_aggregates_ohlcv_correctly():
    from app.resample import resample

    # Four 15m bars make one complete hour, then four more make a second.
    candles = build([(10, 12, 1, 1), (12, 11, 0, 2), (11, 15, 3, 0), (15, 14, 0, 0)] * 2)
    hourly = resample(candles, target="1h", source="15m")

    assert len(hourly) == 2
    assert hourly[0].open == 10, "open comes from the first bar in the bucket"
    assert hourly[0].close == 14, "close comes from the last"
    assert hourly[0].high == 18, "high is the max across the bucket"
    assert hourly[0].low == 9, "low is the min across the bucket"
    assert hourly[0].volume == 4000, "volume sums"
    assert hourly[1].time - hourly[0].time == 3600


def test_resample_drops_an_incomplete_final_bar():
    """A forming HTF bar's high and low are still moving. A zone built on it
    would shift under the user and would be look-ahead in any measurement."""
    from app.resample import resample

    complete = build([(10, 11, 0, 0)] * 8)  # exactly two hours of 15m bars
    partial = build([(10, 11, 0, 0)] * 9)  # two hours plus one bar

    assert len(resample(complete, "1h", "15m")) == 2
    assert len(resample(partial, "1h", "15m")) == 2, "the third hour is unfinished"


def test_resample_anchors_to_the_epoch_not_the_window():
    """Bucket boundaries must not move when the requested bar count changes,
    or every HTF zone shifts whenever the user changes the lookback."""
    from app.resample import resample

    candles = build([(10, 11, 0, 0)] * 40)
    full = resample(candles, "1h", "15m")
    trimmed = resample(candles[7:], "1h", "15m")

    shared = {c.time for c in full} & {c.time for c in trimmed}
    assert shared, "the two windows must share buckets"
    for time in shared:
        a = next(c for c in full if c.time == time)
        b = next(c for c in trimmed if c.time == time)
        assert (a.high, a.low) == (b.high, b.low) or time == min(shared), (
            "a shared complete bucket must aggregate identically"
        )


def test_resample_does_not_invent_bars_across_a_gap():
    """Weekends leave holes in gold and FX. Filling them with flat bars would
    manufacture exactly the consolidation this detector hunts for."""
    from app.resample import resample

    before = build([(10, 11, 0, 0)] * 4)
    after = [
        Candle(time=c.time + 86400 * 2, open=c.open, high=c.high, low=c.low, close=c.close)
        for c in before
    ]
    hourly = resample(before + after, "1h", "15m")

    assert len(hourly) == 2, "two real hours, and nothing in the weekend gap"
    assert hourly[1].time - hourly[0].time == 86400 * 2


def test_resample_refuses_a_target_that_is_not_higher():
    from app.resample import resample

    candles = build([(10, 11, 0, 0)] * 8)
    assert resample(candles, "15m", "15m") == []
    assert resample(candles, "5m", "15m") == []


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


# --------------------------------------------------------------------------
# the display cap, which is a measurement hazard and not only a UI setting
# --------------------------------------------------------------------------


def test_zero_disables_the_per_side_cap():
    """The cap selects on TIME, so any sample taken through it is the recent
    tail of the history wearing the whole history's name.

    Found on 2026-08-13 in `tools/calibrate.py`, which set the cap to 100 - the
    schema maximum, which reads like "off" and is not. The detector was finding
    2030 zones in a 20,000-bar series and returning 200, every one of them
    inside the last 10%. Zero is the only value that means off, and this test
    exists so that stays true.
    """
    rows: list[tuple[float, float, float, float]] = []
    price = 100.0
    for _ in range(8):  # eight identical drop-base-rally formations in a row
        rows += leg(price, -3.0, 3)
        price -= 9.0
        rows += flat(price, 3)
        rows += leg(price, 3.0, 3)
        price += 9.0
        rows += flat(price, 3)
    candles = build(rows)

    uncapped, _ = detect(candles, params(max_zones_per_side=0, merge_overlap_pct=1.0))
    capped, _ = detect(candles, params(max_zones_per_side=2, merge_overlap_pct=1.0))

    assert len(uncapped) > len(capped), "the fixture must produce more than the cap"
    for side in (ZoneSide.DEMAND, ZoneSide.SUPPLY):
        assert sum(1 for z in capped if z.side is side) <= 2

    # And what survives the cap is the NEWEST, which is the whole reason a
    # measurement must not look through it.
    newest = max(z.time_from for z in uncapped)
    assert max(z.time_from for z in capped) == newest
    assert min(z.time_from for z in capped) > min(z.time_from for z in uncapped)


def test_the_departure_window_stops_at_the_first_touch():
    """The bug that made every gate number in this project too generous.

    tools/calibrate.py always clipped the departure lookahead at the first
    touch, and said why in `score_as_of`: the finished chart's value knows more
    than the trader did. The detector never clipped, so the harness and the
    product ran two different gates under one name for months. Measured across
    24000 bars, 34% of drawn zones would have FAILED the honest gate and 0%
    went the other way.

    Here price leaves the base modestly, comes straight back into it, and only
    THEN runs away hard. The runaway happened after the trader's only moment to
    act, so the zone must not be credited with it.
    """
    rows = (
        flat(120.0, 6)
        + leg(120.0, -4.0, 5)       # leg in: drop to 100
        + flat(100.0, 3)            # the base
        + leg(100.0, 3.0, 2)        # modest leg out, to 106
        + leg(106.0, -3.0, 2)       # straight back into the base
        + leg(100.0, 8.0, 12)       # the run the zone must NOT claim
        + flat(196.0, 10)
    )
    zones, _ = detect(build(rows), params(departure_min_atr=0.0,
                                          max_zones_per_side=0, show_broken=True))
    assert zones, "the formation should still be detected"
    # Without the clip the 72-point run after the touch inflates this hugely.
    assert max(z.departure_atr for z in zones) < 15.0
