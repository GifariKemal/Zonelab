"""Supply and Demand zone detection.

The formation is always the same three acts: a leg in, a base where the move
pauses, and a leg out. Which pair of directions the two legs have decides the
name, and whether the zone is demand or supply:

    leg-in    base    leg-out     name    side
    drop      .....   rally       DBR     demand   (reversal)
    rally     .....   rally       RBR     demand   (continuation)
    rally     .....   drop        RBD     supply   (reversal)
    drop      .....   drop        DBD     supply   (continuation)

The scan is a single pass. Bars are partitioned into "exciting" (part of a leg)
and "base", compressed into runs, and every ``exciting -> base -> exciting``
triple is a candidate. Everything after that is measurement, not search.

Two design choices worth stating, because they are the ones that decide whether
the output is trustworthy:

1. Thresholds are ATR-relative, never absolute. A 5-dollar candle is an impulse
   on a quiet XAU session and noise on a volatile one.
2. Nothing is dropped silently. A candidate that fails the departure gate is
   counted in ``stats`` so the UI can tell "no zones here" apart from "the
   filter ate them".
"""

from __future__ import annotations

import numpy as np

from ..indicators import EPS, classify_candles, runs, wilder_atr
from ..models import (
    Anatomy,
    Candle,
    SupplyDemandParams,
    Zone,
    ZoneKind,
    ZoneSide,
    ZoneState,
)

# leg-in direction, leg-out direction -> (formation, side)
_FORMATION: dict[tuple[int, int], tuple[ZoneKind, ZoneSide]] = {
    (-1, 1): (ZoneKind.DBR, ZoneSide.DEMAND),
    (1, 1): (ZoneKind.RBR, ZoneSide.DEMAND),
    (1, -1): (ZoneKind.RBD, ZoneSide.SUPPLY),
    (-1, -1): (ZoneKind.DBD, ZoneSide.SUPPLY),
}

# Score weights. They sum to 1.0; the assertion below keeps that true if someone
# edits one and forgets the others.
_W_DEPARTURE = 0.35
_W_FRESHNESS = 0.25
_W_TIGHTNESS = 0.20
_W_COMPACTNESS = 0.10
_W_VOLUME = 0.10
assert (
    abs(_W_DEPARTURE + _W_FRESHNESS + _W_TIGHTNESS + _W_COMPACTNESS + _W_VOLUME - 1.0)
    < 1e-9
)

# Departure beyond this many ATR is treated as maximal; scoring saturates so a
# freak 20-ATR run does not dominate the ranking on that factor alone.
_DEPARTURE_SATURATION = 5.0


def detect(
    candles: list[Candle], params: SupplyDemandParams
) -> tuple[list[Zone], dict[str, float]]:
    """Return surviving zones plus a stats dict explaining what was filtered."""
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n,
        "candidates": 0,
        "rejected_base_too_tall": 0,
        "rejected_weak_departure": 0,
        "rejected_overlap": 0,
        "rejected_state_filter": 0,
    }
    if n < params.atr_period + 3:
        return [], stats

    time = np.array([c.time for c in candles], dtype=np.int64)
    open_ = np.array([c.open for c in candles], dtype=np.float64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    volume = np.array([c.volume for c in candles], dtype=np.float64)

    atr = wilder_atr(high, low, close, params.atr_period)
    labels = classify_candles(
        open_,
        high,
        low,
        close,
        atr,
        params.impulse_body_ratio,
        params.impulse_atr,
    )
    run_list = runs(labels)

    has_volume = bool(volume.any())
    mean_volume = float(volume.mean()) if has_volume else 0.0

    found: list[Zone] = []

    for k in range(len(run_list) - 2):
        leg_in, base_run, leg_out = run_list[k], run_list[k + 1], run_list[k + 2]
        if leg_in[0] == 0 or base_run[0] != 0 or leg_out[0] == 0:
            continue

        formation = _FORMATION.get((leg_in[0], leg_out[0]))
        if formation is None:  # unreachable: every non-zero pair is mapped
            continue
        kind, side = formation

        # A long consolidation is still a valid origin; the zone is the handful
        # of candles the departure actually left from, so clip to the tail of
        # the base rather than discarding the pattern.
        base_to = base_run[2]
        base_from = max(base_run[1], base_to - params.base_max_bars + 1)

        stats["candidates"] += 1

        # Reference volatility is read from the bar BEFORE the base, not inside
        # it. A tall sloppy base inflates its own ATR, so measuring its height
        # against atr[base_to] lets the very bases the height gate exists to
        # reject pass by widening their own denominator.
        atr_base = float(atr[max(0, base_from - 1)])
        if atr_base <= EPS:
            continue

        if params.zone_basis == "body":
            body_hi = np.maximum(open_[base_from : base_to + 1], close[base_from : base_to + 1])
            body_lo = np.minimum(open_[base_from : base_to + 1], close[base_from : base_to + 1])
            top = float(body_hi.max())
            bottom = float(body_lo.min())
        else:
            top = float(high[base_from : base_to + 1].max())
            bottom = float(low[base_from : base_to + 1].min())

        # A base of doji bodies can be zero-height. Grow it symmetrically about
        # its midpoint to the floor so it stays visible, hoverable, and able to
        # register a touch - a zero-height zone can never be tested.
        floor = params.zone_min_atr * atr_base
        height = top - bottom
        if height < floor:
            mid = (top + bottom) / 2.0
            top, bottom = mid + floor / 2.0, mid - floor / 2.0
            height = top - bottom

        if height > params.base_max_atr * atr_base:
            stats["rejected_base_too_tall"] += 1
            continue

        is_demand = side is ZoneSide.DEMAND
        proximal, distal = (top, bottom) if is_demand else (bottom, top)

        # --- departure: how far the leg-out ran away from the zone ---------
        look_to = min(n, leg_out[1] + params.departure_lookahead)
        if is_demand:
            excursion = float(high[leg_out[1] : look_to].max()) - proximal
        else:
            excursion = proximal - float(low[leg_out[1] : look_to].min())
        departure_atr = max(0.0, excursion) / atr_base

        if departure_atr < params.departure_min_atr:
            stats["rejected_weak_departure"] += 1
            continue

        # --- lifecycle: replay every bar after the leg-out ------------------
        touches = 0
        penetration = 0.0
        first_test_time: int | None = None
        break_index: int | None = None
        was_inside = False

        for i in range(leg_out[2] + 1, n):
            if is_demand and close[i] < distal:
                break_index = i
                break
            if not is_demand and close[i] > distal:
                break_index = i
                break

            inside = low[i] <= top and high[i] >= bottom
            if inside:
                # Consecutive bars sitting in the zone are one visit, not five.
                if not was_inside:
                    touches += 1
                    if first_test_time is None:
                        first_test_time = int(time[i])
                depth = (top - low[i]) if is_demand else (high[i] - bottom)
                penetration = max(penetration, min(1.0, depth / height))
            was_inside = inside

        if break_index is not None:
            state = ZoneState.BROKEN
        elif penetration >= params.mitigation_pct:
            state = ZoneState.MITIGATED
        elif touches > 0:
            state = ZoneState.TESTED
        else:
            state = ZoneState.FRESH

        # --- score ----------------------------------------------------------
        f_departure = min(departure_atr / _DEPARTURE_SATURATION, 1.0)
        f_freshness = 1.0 / (1.0 + touches)
        f_tightness = float(
            np.clip(1.0 - (height / atr_base) / params.base_max_atr, 0.0, 1.0)
        )
        span = params.base_max_bars - 1
        f_compactness = 1.0 - ((base_to - base_from) / span if span > 0 else 0.0)
        if has_volume and mean_volume > EPS:
            leg_vol = float(volume[leg_out[1] : leg_out[2] + 1].mean())
            f_volume = min(leg_vol / (2.0 * mean_volume), 1.0)
        else:
            f_volume = 0.5  # neutral: absent volume must not look like weak volume

        factors = {
            "departure": round(f_departure * _W_DEPARTURE, 4),
            "freshness": round(f_freshness * _W_FRESHNESS, 4),
            "tightness": round(f_tightness * _W_TIGHTNESS, 4),
            "compactness": round(f_compactness * _W_COMPACTNESS, 4),
            "volume": round(f_volume * _W_VOLUME, 4),
        }
        strength = float(np.clip(sum(factors.values()), 0.0, 1.0))

        time_to = int(time[break_index]) if break_index is not None else int(time[-1])

        found.append(
            Zone(
                id=f"{kind.value}-{int(time[base_from])}-{top:.5f}",
                kind=kind,
                side=side,
                state=state,
                top=top,
                bottom=bottom,
                proximal=proximal,
                distal=distal,
                time_from=int(time[base_from]),
                time_to=time_to,
                strength=round(strength, 4),
                departure_atr=round(departure_atr, 3),
                touches=touches,
                penetration_pct=round(penetration, 4),
                first_test_time=first_test_time,
                # The newest run is still open: another bar of the same kind
                # extends it and moves this zone's leg-out. Say so rather than
                # presenting a provisional shape as settled.
                confirmed=leg_out[2] < n - 1,
                anatomy=Anatomy(
                    leg_in_from=leg_in[1],
                    leg_in_to=leg_in[2],
                    base_from=base_from,
                    base_to=base_to,
                    leg_out_from=leg_out[1],
                    leg_out_to=leg_out[2],
                ),
                factors=factors,
                note=(
                    f"{kind.value}: {base_to - base_from + 1}-bar base, "
                    f"departure {departure_atr:.1f} ATR, {state.value}"
                    + (f", {touches} test(s)" if touches else "")
                ),
            )
        )

    kept = _dedupe(found, params.merge_overlap_pct, stats)

    allowed = {ZoneState.FRESH, ZoneState.TESTED}
    if params.show_mitigated:
        allowed.add(ZoneState.MITIGATED)
    if params.show_broken:
        allowed.add(ZoneState.BROKEN)
    visible = [z for z in kept if z.state in allowed]
    stats["rejected_state_filter"] = len(kept) - len(visible)

    result: list[Zone] = []
    for side in (ZoneSide.DEMAND, ZoneSide.SUPPLY):
        # Cap per side by recency: the zones price can actually reach next are
        # the ones nearest in time, not the strongest one from 400 bars ago.
        per_side = [z for z in visible if z.side is side]
        per_side.sort(key=lambda z: z.time_from, reverse=True)
        result.extend(per_side[: params.max_zones_per_side])

    result.sort(key=lambda z: z.time_from)
    stats["zones"] = len(result)
    return result, stats


def _dedupe(
    zones: list[Zone], max_overlap: float, stats: dict[str, float]
) -> list[Zone]:
    """Drop a zone that mostly repeats a stronger zone on the same side.

    Overlap is measured against the *smaller* of the two heights, so a thin zone
    swallowed by a fat one is correctly seen as redundant.
    """
    kept: list[Zone] = []
    for zone in sorted(zones, key=lambda z: z.strength, reverse=True):
        redundant = False
        for other in kept:
            if other.side is not zone.side:
                continue
            overlap = min(zone.top, other.top) - max(zone.bottom, other.bottom)
            if overlap <= 0:
                continue
            smaller = min(zone.top - zone.bottom, other.top - other.bottom)
            if smaller > EPS and overlap / smaller > max_overlap:
                redundant = True
                break
        if redundant:
            stats["rejected_overlap"] += 1
        else:
            kept.append(zone)
    return kept
