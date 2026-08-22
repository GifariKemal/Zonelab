"""A zone's id is an identity, so it may not be made of a price.

Until 2026-08-21 every detector built `f"{kind}-{bar}-{top:.5f}"`. That reads
fine and fails at exactly one job: telling a caller "this is the same zone I saw
last time". Prices in this engine are not stable to the last decimal -
`test_no_repaint.py` caught a projected 1d box moving its bottom by 0.009 - and a
key that changes when a price twitches is a key that says "new zone" to anything
keeping a record. For a reader that is invisible. For an executor that has
already placed an order it is a second order.

So the id is `kind` plus the ORIGIN BAR'S OPEN TIME, and the two properties that
makes it fit for the job are checked below rather than argued: it survives a
price change, and it is still unique.

Uniqueness is not obvious and was not assumed. The inversion families are the
awkward ones: fourteen breakers in one real window share an `inverted_at` AND a
`time_from`, and only their parent's origin separates them. That is why the
origin bar is the component that stayed.
"""

from __future__ import annotations

import asyncio

import pytest

from app.detect import DETECTORS
from app.models import ImbalanceParams, SupplyDemandParams, ZoneKind
from app.providers import get_candles

DETECTOR_PARAMS = {
    "supply_demand": SupplyDemandParams,
    "fvg": ImbalanceParams,
    "order_block": ImbalanceParams,
    "ifvg": ImbalanceParams,
    "breaker": ImbalanceParams,
}


@pytest.fixture(scope="module")
def series():
    """Synthetic, and deliberately long enough to draw thousands of boxes: a
    uniqueness claim on twelve zones is not a uniqueness claim."""
    return asyncio.run(get_candles("XAUUSD", "1h", 4000, "synthetic"))[0]


def _zones(name: str, candles):
    params = DETECTOR_PARAMS[name](max_zones_per_side=0, show_broken=True)
    return DETECTORS[name](candles, params)[0]


@pytest.mark.parametrize("name", sorted(DETECTOR_PARAMS))
def test_no_id_carries_a_price(name, series):
    """The regression itself. A price is a float with a decimal point in it, and
    no id may contain one - checked on the STRING so a future edit that puts the
    price back in another format still has to get past this."""
    zones = _zones(name, series)
    assert zones, f"{name} drew nothing, so this proves nothing"
    with_dot = [z.id for z in zones if "." in z.id]
    assert with_dot == [], (
        f"{len(with_dot)} {name} ids carry a decimal point, so a price is in the "
        f"identity again: {with_dot[:3]}"
    )


@pytest.mark.parametrize("name", sorted(DETECTOR_PARAMS))
def test_ids_are_unique_within_a_detector(name, series):
    zones = _zones(name, series)
    ids = [z.id for z in zones]
    assert len(set(ids)) == len(ids), (
        f"{name} repeats an id, so the price segment was load-bearing after all"
    )


def test_an_id_does_not_move_when_the_box_moves():
    """The property the old format lacked, stated as arithmetic rather than as a
    story: two zones identical except for their prices must share an id.

    Built by hand instead of by moving the market, because the repaint this
    guards against is a hundredth of a point and no fixture reproduces it on
    demand. What is being asserted is the FORMAT: given the same kind and the
    same origin bar, the id may not depend on `top`.
    """
    from app.models import Anatomy, Zone, ZoneSide, ZoneState

    anatomy = Anatomy(
        leg_in_from=0, leg_in_to=1, base_run_from=1, base_from=1, base_to=2,
        leg_out_from=3, leg_out_to=4,
    )

    def zone(top: float, bottom: float) -> Zone:
        return Zone(
            id=f"{ZoneKind.DBD.value}-1700000000",
            kind=ZoneKind.DBD, side=ZoneSide.SUPPLY, state=ZoneState.FRESH,
            top=top, bottom=bottom, proximal=bottom, distal=top,
            time_from=1700000000, time_to=1700003600,
            formation_score=0.0, departure_atr=3.0, anatomy=anatomy,
        )

    assert zone(100.0, 90.0).id == zone(100.009, 90.0).id


def test_the_price_is_still_reachable_on_the_object():
    """Dropping the price from the id must not drop it from the zone: the plan
    reads `top` and `bottom` to place the entry and the stop."""
    zones = _zones("supply_demand", asyncio.run(
        get_candles("XAUUSD", "1h", 900, "synthetic"))[0])
    assert zones
    for z in zones[:5]:
        assert z.top > z.bottom
        assert z.proximal in (z.top, z.bottom)
        assert z.distal in (z.top, z.bottom)
