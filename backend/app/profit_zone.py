"""How far can price travel before it meets the opposing wall?

The doctrine calls this the profit zone and its author calls it the enhancer
most people overlook: a textbook demand zone with a supply zone sitting 1.5x its
own height above it is not a trade, however cleanly it formed.

It has a consequence the rest of the model does not: **a zone's worth depends on
the other zones around it, not only on itself.** So it cannot be computed inside
the detector, which sees one formation at a time. It is a pass over the finished
set, and it has to be recomputed whenever the set changes.
"""

from __future__ import annotations

from .models import Zone, ZoneSide, ZoneState


def profit_zone_at(zone: Zone, zones: list[Zone], when: int) -> float | None:
    """Distance to the nearest opposing zone that was live at `when`.

    Measured from this zone's proximal line to the opposing zone's proximal
    line, in units of this zone's own height, because that height is what the
    stop is sized against.

    "Live at `when`" carries the whole causal argument. An opposing zone that
    had not formed yet was not a wall, and one price had already broken was not
    a wall either. Passing the last bar's time answers "what does the trader see
    now"; passing a touch time answers "what could the trader have seen then",
    and only the second is safe to measure outcomes against.
    """
    height = zone.top - zone.bottom
    if height <= 0:
        return None

    want_up = zone.side is ZoneSide.DEMAND
    nearest: float | None = None

    for other in zones:
        if other.side is zone.side or other.time_from > when:
            continue
        if other.state is ZoneState.BROKEN and other.time_to <= when:
            continue
        # The wall has to lie in the direction price would travel, and ahead of
        # the entry rather than behind it.
        gap = (
            other.proximal - zone.proximal
            if want_up
            else zone.proximal - other.proximal
        )
        if gap > 0 and (nearest is None or gap < nearest):
            nearest = gap

    return round(nearest / height, 2) if nearest is not None else None


def mark_profit_zones(zones: list[Zone], now: int) -> None:
    """Stamp every zone with its profit zone as of `now`. Mutates in place."""
    for zone in zones:
        zone.profit_zone_rr = profit_zone_at(zone, zones, now)
