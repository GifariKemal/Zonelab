"""Inversion fair value gaps and breaker blocks, on series whose answer is known.

These two detectors invent no geometry - they re-enter a parent box from the
other side after price closed through it - so almost every way they can be wrong
is a way of getting the SEAM wrong: the bar the lifecycle starts on, the side, or
which edge became protective. Each fixture is built so the correct answer is
arithmetic rather than judgement.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_inversion.py -q
"""

from __future__ import annotations

import pytest

from app.detect import DETECTORS
from app.layers import PARAMS_BY_ID
from app.detect.imbalance import detect_fvg
from app.detect.inversion import detect_breaker, detect_ifvg
from app.models import Candle, ImbalanceParams, ZoneKind, ZoneSide, ZoneState

STEP = 900  # 15-minute bars
T0 = 1_700_000_000 // 86_400 * 86_400


def bar(t: int, o: float, c: float, hp: float, lp: float) -> Candle:
    return Candle(
        time=t, open=o, close=c, high=max(o, c) + hp, low=min(o, c) - lp, volume=1000.0
    )


def imb(**overrides) -> ImbalanceParams:
    base = {"atr_period": 5, "min_gap_atr": 0.0, "displacement_atr": 1.0,
            "displacement_bars": 3, "max_zones_per_side": 0}
    return ImbalanceParams(**(base | overrides))


def calm(n: int, price: float = 100.0) -> list[Candle]:
    return [bar(T0 + i * STEP, price, price, 0.5, 0.5) for i in range(n)]


T = T0 + 20 * STEP
BREAK_BAR = T + 5 * STEP  # index 25, the bar that closes through the gap
TOUCH_BAR = T + 7 * STEP  # index 27, the first bar that re-enters it


def gap_that_breaks() -> list[Candle]:
    """A demand gap between 100.5 and 105.0 that price later closes below.

    The breaking bar deliberately SPANS the whole box (open 106, close 99), so
    if the inverted box's lifecycle started one bar too early that bar would be
    counted as the first test of it. That is the only way this fixture can pass
    the anti-lookahead test by accident, and it is closed by construction.
    """
    rows = calm(20)                                          # 0-19  quiet at 100
    rows.append(bar(T, 100.0, 100.0, 0.5, 0.5))              # 20  first: high 100.5
    rows.append(bar(T + STEP, 101.0, 106.0, 0.2, 0.2))       # 21  the leap
    rows.append(bar(T + 2 * STEP, 106.0, 106.0, 0.5, 1.0))   # 22  third: low 105.0
    rows.append(bar(T + 3 * STEP, 106.0, 106.0, 0.5, 0.5))   # 23
    rows.append(bar(T + 4 * STEP, 106.0, 106.0, 0.5, 0.5))   # 24
    rows.append(bar(BREAK_BAR, 106.0, 99.0, 0.3, 0.5))       # 25  THE BREAK
    rows.append(bar(T + 6 * STEP, 99.0, 99.0, 0.5, 0.5))     # 26  below, no touch
    rows.append(bar(TOUCH_BAR, 99.0, 102.0, 0.2, 0.2))       # 27  back up into it
    rows += [bar(T + (8 + i) * STEP, 99.0, 99.0, 0.5, 0.5) for i in range(6)]
    return rows


def the_ifvg(rows: list[Candle], **overrides):
    zones, stats = detect_ifvg(rows, imb(**overrides))
    # Selected by the PARENT the box was made from, which the id carries, not by
    # `time_from`. This helper used to look for `time_from == T`, which quietly
    # pinned the defect it was written beside: an inverted box was drawn from its
    # parent's origin, so it claimed to be supply across a window where the same
    # band was demand. The assertions here were always about the seam; only the
    # lookup was wrong. `inverted_at` is not enough to select on either - this
    # fixture has two gaps that die on the same bar.
    boxes = [z for z in zones if z.id.startswith(f"IFVG-{T}-")]
    assert len(boxes) == 1, f"expected one inversion of the gap at {T}, got {boxes}"
    return boxes[0], stats


def test_an_inverted_box_is_not_tested_by_the_bar_that_broke_it():
    """The anti-lookahead rule, and the reason it needs its own test: the box is
    knowable only once the bar that closed through it has closed, so its
    lifecycle starts at `break_index + 1`. The breaking bar's range covers the
    entire box here, so starting one bar earlier would report the candle that
    KILLED the old box as the first visitor to the new one - a detector touching
    its own construction, which is exactly the mistake the gap detector's third
    bar comment exists to prevent.
    """
    box, _ = the_ifvg(gap_that_breaks())

    assert box.inverted_at == BREAK_BAR
    assert box.first_test_time == TOUCH_BAR
    assert box.first_test_time > box.inverted_at
    assert box.touches == 1
    assert box.state is ZoneState.TESTED


def test_the_inverted_side_is_the_opposite_of_the_side_that_broke():
    """`side` is the side the box BECAME. A demand gap price closed below is
    resistance now, so it is reported as supply."""
    rows = gap_that_breaks()

    # The parent, asserted rather than assumed, so a fixture that stopped
    # producing a DEMAND gap could not make this test pass for a new reason.
    parent = [z for z in detect_fvg(rows, imb(show_broken=True))[0]
              if z.time_from == T]
    assert len(parent) == 1
    assert parent[0].side is ZoneSide.DEMAND
    assert parent[0].state is ZoneState.BROKEN

    box, _ = the_ifvg(rows)
    assert box.side is ZoneSide.SUPPLY
    assert box.kind is ZoneKind.IFVG


def test_the_inverted_distal_is_the_old_near_edge():
    """No new geometry: the same rectangle, entered from the other side. The
    edge price met first as demand (the top) is the protective edge now, and the
    edge that was protective (the bottom) is the one price meets first."""
    box, _ = the_ifvg(gap_that_breaks())

    assert box.top == pytest.approx(105.0)      # unchanged
    assert box.bottom == pytest.approx(100.5)   # unchanged
    assert box.proximal == pytest.approx(100.5)  # was the demand distal
    assert box.distal == pytest.approx(105.0)    # was the demand proximal


def test_a_box_that_never_broke_produces_nothing_and_is_counted():
    """"No inversions here" and "the filter ate them" have to be different
    readings. The gap in this fixture is alive at the last bar, so there is no
    inversion event and the stats must say which of the two happened."""
    rows = gap_that_breaks()[:25]  # everything up to but not including the break

    zones, stats = detect_ifvg(rows, imb())

    assert zones == []
    assert stats["candidates"] >= 1
    assert stats["rejected_never_broke"] == stats["candidates"]
    assert stats["zones"] == 0


def test_the_parents_state_filter_cannot_hide_the_boxes_this_is_made_of():
    """A broken parent is the raw material, and `show_broken` ships OFF. Calling
    the parent with the caller's params unchanged would make this detector
    return nothing on default settings and look like a market with no
    inversions in it."""
    box, _ = the_ifvg(gap_that_breaks(), show_broken=False)

    assert box.state is ZoneState.TESTED


def test_confirmed_and_settled_coincide_on_the_breaking_bar():
    """Same reasoning as the gap detector: an inverted box has no departure
    window to wait out, it is fixed the moment the breaking bar closes. So both
    flags read off that one bar, and both are False when it is the newest bar
    there is."""
    box, _ = the_ifvg(gap_that_breaks())
    assert box.confirmed is True
    assert box.settled is True

    fresh, _ = the_ifvg(gap_that_breaks()[:26])  # the break IS the last bar
    assert fresh.inverted_at == BREAK_BAR
    assert fresh.confirmed is False
    assert fresh.settled is False
    assert fresh.touches == 0


def test_neither_inversion_ships_a_score():
    """0.0, exactly as `fvg` and `order_block` do. The supply/demand detector
    shipped a composite score and had to retract it; scoring a box whose own
    directional claim measured significantly NEGATIVE (H8) would be that
    retraction repeated on worse evidence."""
    ifvg, _ = detect_ifvg(gap_that_breaks(), imb())
    brk, _ = detect_breaker(block_that_breaks(), imb())

    assert [z.formation_score for z in ifvg + brk]
    assert all(z.formation_score == 0.0 for z in ifvg + brk)


# --------------------------------------------------------------------------
# breaker blocks
# --------------------------------------------------------------------------

B = T0 + 20 * STEP
B_BREAK = B + 6 * STEP    # index 26
B_TOUCH = B + 10 * STEP   # index 30


def block_that_breaks() -> list[Candle]:
    """A demand order block at 98.6-100.3, a rally, then a close below 98.6.

    The breaking bar spans the box for the same reason the gap fixture's does.
    """
    rows = calm(20)
    rows.append(bar(B, 100.0, 99.0, 0.3, 0.4))   # 20  block: high 100.3, low 98.6
    price = 99.0
    for i in range(1, 6):                        # 21-25  the impulse
        rows.append(bar(B + i * STEP, price, price + 3.0, 0.0, 0.0))
        price += 3.0
    rows.append(bar(B_BREAK, price, 97.0, 0.0, 0.0))  # 26  THE BREAK, spans the box
    rows += [bar(B + (7 + i) * STEP, 97.0, 97.0, 0.2, 0.2) for i in range(3)]
    rows.append(bar(B_TOUCH, 97.0, 99.2, 0.0, 0.0))   # 30  back up into it
    rows += [bar(B + (11 + i) * STEP, 97.0, 97.0, 0.2, 0.2) for i in range(4)]
    return rows


def test_a_breaker_is_the_order_block_read_from_underneath():
    """The whole-candle range of the parent block, unchanged, with the side and
    the protective edge flipped - and the same anti-lookahead rule, since the
    breaking bar here also covers the box end to end."""
    zones, stats = detect_breaker(block_that_breaks(), imb())
    # By the parent block the id names, for the same reason as `the_ifvg`: the
    # box's own left edge is now the inversion bar, not the block at B.
    boxes = [z for z in zones if z.id.startswith(f"BRK-{B}-")]

    assert len(boxes) == 1
    box = boxes[0]
    assert box.kind is ZoneKind.BRK
    assert box.side is ZoneSide.SUPPLY          # was a demand block
    assert box.top == pytest.approx(100.3)      # the parent's whole range
    assert box.bottom == pytest.approx(98.6)
    assert box.proximal == pytest.approx(98.6)  # was the block's distal
    assert box.distal == pytest.approx(100.3)
    assert box.inverted_at == B_BREAK
    assert box.first_test_time == B_TOUCH
    # The supply block the rally's last candle leaves behind never breaks, so it
    # is refused for a stated reason rather than silently absent.
    assert stats["rejected_never_broke"] >= 1


def test_the_registry_runs_both_inversion_detectors():
    """A detector the layer registry does not name passes request validation and
    never runs: 200 OK, no zones, no error. Dispatching through the registry is
    the only way this file proves the wiring, rather than proving the functions
    it imported directly."""
    for name, kind, rows in (
        ("ifvg", ZoneKind.IFVG, gap_that_breaks()),
        ("breaker", ZoneKind.BRK, block_that_breaks()),
    ):
        assert PARAMS_BY_ID[name] == "imbalance"
        zones, stats = DETECTORS[name](rows, imb())
        assert zones, f"{name} drew nothing through the registry"
        assert all(z.kind is kind for z in zones)
        for key in ("bars", "candidates", "zones", "found_demand", "found_supply"):
            assert key in stats, f"{name} stats missing {key}"


@pytest.mark.parametrize(
    "name, rows",
    [("ifvg", gap_that_breaks()), ("breaker", block_that_breaks())],
)
def test_an_inverted_box_is_not_drawn_before_it_inverted(name, rows):
    """The left edge is the flip, not the parent's origin.

    `_finish` takes the left edge from the origin bar it is handed, so an
    inverted box was drawn from the bar its PARENT was built on. That put a
    supply box on the chart spanning a window in which the same band was demand,
    and stated it with a hard edge - the drawing asserting something the data
    contradicts, which is the one thing this engine may not do.

    It was not caught by any test here because every test asked about the SEAM
    (side, distal, lifecycle start) and none asked where the box BEGINS - and the
    helper that located the box selected it by `time_from == T`, so the defect
    was written into the lookup that would have exposed it.
    """
    zones, _ = DETECTORS[name](rows, imb())

    assert zones, f"{name} drew nothing to check"
    for zone in zones:
        assert zone.inverted_at is not None, "an inverted box must say when"
        assert zone.time_from == zone.inverted_at, (
            f"{name} box starts at {zone.time_from} but only inverted at "
            f"{zone.inverted_at}"
        )
        # The parent's bars survive as evidence: the correction moves the drawn
        # edge, it does not throw away where the rectangle came from.
        assert zone.anatomy.base_from <= zone.anatomy.leg_out_from
