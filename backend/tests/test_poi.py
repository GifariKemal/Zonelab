"""A POI is objects from ONE displacement stacking, not any box at that price.

The first version of `poi.confluence` counted every same-side box that overlapped
the zone's band at any time in the series. Measured on 3000 bars of broker gold it
marked 14 of 14 live candidates with all four families present, supports running
to 75 and conflicts to 68. A condition satisfied by every case distinguishes
nothing - the same trap `confluence.py` records for any-overlap nesting.

So a supporting box has to be BORN inside the zone's own formation bracket, which
is also what the doctrine describes: one impulse leaving a gap, a block and a
retracement level at the same price. With that restriction the families spread
1/2/3/4 across the same 22 zones, which is a column that can vary and therefore a
column that can be measured.
"""

from __future__ import annotations

from app.models import Anatomy, Zone, ZoneKind, ZoneSide, ZoneState
from app.poi import FAMILIES, confluence

BORN = 1_700_000_000
HOUR = 3600


def box(kind: ZoneKind, side: ZoneSide, top: float, bottom: float, at: int) -> Zone:
    return Zone(
        id=f"{kind.value}-{at}", kind=kind, side=side, state=ZoneState.FRESH,
        top=top, bottom=bottom,
        proximal=bottom if side is ZoneSide.SUPPLY else top,
        distal=top if side is ZoneSide.SUPPLY else bottom,
        time_from=at, time_to=at + HOUR, formation_score=0.0, departure_atr=3.0,
        anatomy=Anatomy(leg_in_from=0, leg_in_to=1, base_run_from=1, base_from=1,
                        base_to=2, leg_out_from=3, leg_out_to=4),
    )


def zone() -> Zone:
    """A supply zone 100 to 110, born at BORN."""
    return box(ZoneKind.DBD, ZoneSide.SUPPLY, 110.0, 100.0, BORN)


def others(*boxes: Zone) -> dict[str, list[Zone]]:
    out: dict[str, list[Zone]] = {name: [] for name in FAMILIES}
    for b in boxes:
        name = {"FVG": "fvg", "OB": "order_block", "IFVG": "ifvg",
                "BRK": "breaker"}[b.kind.value]
        out[name].append(b)
    return out


def test_a_box_from_the_same_displacement_supports():
    stack = confluence(
        zone(),
        others(box(ZoneKind.FVG, ZoneSide.SUPPLY, 108.0, 104.0, BORN + HOUR)),
        as_of=BORN + 99 * HOUR, born_from=BORN - HOUR, born_to=BORN + 3 * HOUR,
    )
    assert stack.supports["fvg"] == 1
    assert stack.families == 1
    assert stack.conflicts == 0


def test_a_box_at_the_same_price_from_months_later_does_not():
    """The regression. Same price, same side, wrong impulse."""
    stack = confluence(
        zone(),
        others(box(ZoneKind.FVG, ZoneSide.SUPPLY, 108.0, 104.0, BORN + 2000 * HOUR)),
        as_of=BORN + 3000 * HOUR, born_from=BORN - HOUR, born_to=BORN + 3 * HOUR,
    )
    assert stack.total_supports == 0, (
        "a coincidence at a number is not a point of interest"
    )


def test_an_opposite_side_box_is_a_conflict_and_is_never_netted_off():
    stack = confluence(
        zone(),
        others(box(ZoneKind.FVG, ZoneSide.SUPPLY, 108.0, 104.0, BORN),
               box(ZoneKind.OB, ZoneSide.DEMAND, 106.0, 102.0, BORN)),
        as_of=BORN + HOUR, born_from=BORN - HOUR, born_to=BORN + 3 * HOUR,
    )
    assert stack.total_supports == 1
    assert stack.conflicts == 1, "a disagreement is its own number"


def test_families_counts_tools_and_not_boxes():
    """Three order blocks are one PD array tool three times. The doctrine's claim
    is that MULTIPLE TOOLS converge, so both numbers are reported and they are
    not the same number."""
    three = [box(ZoneKind.OB, ZoneSide.SUPPLY, 108.0, 104.0, BORN + n) for n in (0, 1, 2)]
    stack = confluence(zone(), others(*three), as_of=BORN + HOUR,
                       born_from=BORN - HOUR, born_to=BORN + 3 * HOUR)
    assert stack.total_supports == 3
    assert stack.families == 1


def test_a_box_that_does_not_touch_the_band_is_not_in_the_stack():
    stack = confluence(
        zone(),
        others(box(ZoneKind.FVG, ZoneSide.SUPPLY, 99.0, 95.0, BORN)),
        as_of=BORN + HOUR, born_from=BORN - HOUR, born_to=BORN + 3 * HOUR,
    )
    assert stack.total_supports == 0


def test_touching_edge_to_edge_is_not_an_overlap():
    """A box whose top is exactly the zone's bottom shares one price and no band.
    Counted, it would make every adjacent box a confluence."""
    stack = confluence(
        zone(),
        others(box(ZoneKind.FVG, ZoneSide.SUPPLY, 100.0, 95.0, BORN)),
        as_of=BORN + HOUR, born_from=BORN - HOUR, born_to=BORN + 3 * HOUR,
    )
    assert stack.total_supports == 0


def test_as_of_caps_the_window_even_when_the_bracket_is_wider():
    """The anti-lookahead half. A harness judging the touch bar passes that bar's
    time, and a box born after it must not enter the count even if it falls
    inside the formation bracket."""
    stack = confluence(
        zone(),
        others(box(ZoneKind.FVG, ZoneSide.SUPPLY, 108.0, 104.0, BORN + 5 * HOUR)),
        as_of=BORN + 2 * HOUR, born_from=BORN - HOUR, born_to=BORN + 9 * HOUR,
    )
    assert stack.total_supports == 0


def test_levels_inside_the_band_are_counted():
    stack = confluence(
        zone(), others(), as_of=BORN + HOUR, born_from=BORN, born_to=BORN + HOUR,
        cisd_levels=[105.0, 90.0], true_open_prices=[101.0, 120.0, 109.9],
    )
    assert stack.cisd == 1
    assert stack.true_opens == 2
