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


def mark_crowding(zones: list[Zone], min_rr: float) -> None:
    """Stamp when a newly born opposing zone first closed the road. In place.

    Every other lifecycle field in this engine is driven by price: touched,
    mitigated, broken. This one is not. The guidance is explicit that a zone
    stops being worth trading once the road ahead of it shrinks below the
    minimum, and the road can shrink without price moving at all - a fresh
    opposing zone forming in the way does it. So validity has to be re-checked
    on an event this code did not previously listen for: **another zone being
    born.**

    Which is why the answer is a separate field and not a new `ZoneState`. The
    two causes need to stay tellable apart. A zone price ate through and a zone
    boxed in by a newcomer are different situations that happen to be equally
    untradeable, and collapsing them would throw away the only information that
    says which.

    `crowded_at` is a historical fact and does not expire. If the opposing zone
    is later broken the road reopens, and the CURRENT `profit_zone_rr` says so;
    the stamp still records that the road was shut once. The optional filter in
    the API drops zones whose road is shut NOW, which is the question a trader
    is actually asking.
    """
    if min_rr <= 0:
        return

    # One pass, not a sweep over every birth instant. "The road is shorter than
    # `min_rr`" and "some opposing zone stands closer than `min_rr` heights"
    # are the same statement, so the earliest moment the road was shut is just
    # the earliest such wall - no need to re-measure the nearest one at every
    # instant to find out when it stopped being far enough away.
    for zone in zones:
        height = zone.top - zone.bottom
        if height <= 0:
            continue
        limit = min_rr * height
        want_up = zone.side is ZoneSide.DEMAND

        earliest: int | None = None
        for other in zones:
            if other.side is zone.side:
                continue
            gap = (
                other.proximal - zone.proximal
                if want_up
                else zone.proximal - other.proximal
            )
            if not 0 < gap < limit:
                continue
            # A wall built before this zone was already in the way the moment
            # the zone appeared, so the road was shut at the zone's own birth.
            moment = max(other.time_from, zone.time_from)
            if moment > zone.time_to:
                continue  # this zone was already dead
            if other.state is ZoneState.BROKEN and other.time_to <= moment:
                continue  # and this wall was already gone
            earliest = moment if earliest is None else min(earliest, moment)

        zone.crowded_at = earliest
