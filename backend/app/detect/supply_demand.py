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

# Formation weights. Equal thirds, and deliberately not fitted: see
# docs/CALIBRATION.md. On 234 resolved zones across five series no factor
# separated held from failed with a confidence interval clear of 0.5, so fitting
# weights here would be fitting noise.
#
# Two factors that used to be in this sum are gone, both because measurement
# said so rather than because the code got tidier:
#
#   departure  - held rate rises steeply to 2 ATR and is FLAT above it
#                (87.2% / 83.0% / 85.7% / 82.4% across the 2-3, 3-4, 4-5 and 5+
#                buckets). It is a threshold, and it is already enforced as one
#                by `departure_min_atr`. Scoring it as a gradient added noise.
#   freshness  - a zone is fresh by definition at the moment it is first
#                touched, so this term was constant exactly when it was read.
#                Lifecycle now lives only in `state`, `touches` and
#                `penetration_pct`, where it is not double counted.
_W_TIGHTNESS = 1 / 3
_W_COMPACTNESS = 1 / 3
_W_VOLUME = 1 / 3
assert abs(_W_TIGHTNESS + _W_COMPACTNESS + _W_VOLUME - 1.0) < 1e-9

# Display priority when two overlapping zones collapse into one. This is a
# presentation choice, not a quality claim: given two zones at the same price,
# the one price has not yet consumed is the more useful one to draw.
_STATE_PRIORITY = {
    ZoneState.FRESH: 3,
    ZoneState.TESTED: 2,
    ZoneState.MITIGATED: 1,
    ZoneState.BROKEN: 0,
}

# Kept for the calibration harness, which needs a stable scale to bucket raw
# departure on. Nothing in the shipped score uses it any more.
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
        "rejected_base_drifted": 0,
        "rejected_weak_departure": 0,
        "rejected_thin_profit_margin": 0,
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

        # The two lines are NOT symmetric, and getting that wrong is the most
        # consequential drawing mistake in the method. The distal is always the
        # wick extreme of the base, because the stop sits beyond it and a distal
        # drawn at the body puts the stop inside the base it is protecting. Only
        # the proximal moves between the aggressive (wick) and conservative
        # (body) variants, and the doctrine never settled which is right.
        span = slice(base_from, base_to + 1)
        wick_hi = float(high[span].max())
        wick_lo = float(low[span].min())

        if params.proximal_basis == "body":
            body_hi = float(np.maximum(open_[span], close[span]).max())
            body_lo = float(np.minimum(open_[span], close[span]).min())
        else:
            body_hi, body_lo = wick_hi, wick_lo

        if side is ZoneSide.DEMAND:
            top, bottom = body_hi, wick_lo  # proximal above, distal below
        else:
            top, bottom = wick_hi, body_lo  # distal above, proximal below

        # A base of doji bodies can be near zero-height. Grow it to the floor so
        # it stays visible, hoverable and able to register a touch, but grow it
        # from the PROXIMAL side only: the distal is a wick extreme the stop
        # sits beyond, and widening it symmetrically would quietly move the
        # stop into the base.
        floor = params.zone_min_atr * atr_base
        height = top - bottom
        if height < floor:
            if side is ZoneSide.DEMAND:
                top = bottom + floor
            else:
                bottom = top - floor
            height = top - bottom

        if height > params.base_max_atr * atr_base:
            stats["rejected_base_too_tall"] += 1
            continue

        is_demand = side is ZoneSide.DEMAND
        proximal, distal = (top, bottom) if is_demand else (bottom, top)

        # Did the base actually pause? "No single candle here was big enough to
        # be an impulse" is not the same test as "price stopped going
        # anywhere", and a slow staircase satisfies the first while failing the
        # second. Both are reported so the question can be measured before any
        # threshold is invented.
        drift = abs(close[base_to] - open_[base_from]) / height
        if base_to > base_from:
            span = np.maximum(high[base_from + 1 : base_to + 1], high[base_from:base_to]) - np.minimum(
                low[base_from + 1 : base_to + 1], low[base_from:base_to]
            )
            shared = np.minimum(high[base_from + 1 : base_to + 1], high[base_from:base_to]) - np.maximum(
                low[base_from + 1 : base_to + 1], low[base_from:base_to]
            )
            overlap = float(np.mean(np.where(span > EPS, np.maximum(shared, 0.0) / np.maximum(span, EPS), 1.0)))
        else:
            overlap = 1.0  # a single bar trivially overlaps itself

        # --- departure: how far the leg-out ran away from the zone ---------
        look_to = min(n, leg_out[1] + params.departure_lookahead)
        if is_demand:
            excursion = float(high[leg_out[1] : look_to].max()) - proximal
        else:
            excursion = proximal - float(low[leg_out[1] : look_to].min())
        departure_atr = max(0.0, excursion) / atr_base

        # The doctrine's own test, and the only hard number in it: a base is not
        # a level unless the initial move away is at least three times the level
        # itself. It measures the same leg against a different yardstick than
        # `departure_min_atr` does - the zone's own height rather than the
        # market's volatility - so a wide zone has to earn a wider departure.
        profit_margin = max(0.0, excursion) / height

        if drift > params.max_base_drift:
            stats["rejected_base_drifted"] += 1
            continue
        if departure_atr < params.departure_min_atr:
            stats["rejected_weak_departure"] += 1
            continue
        if profit_margin < params.min_profit_margin:
            stats["rejected_thin_profit_margin"] += 1
            continue

        # --- curve: where in the prevailing range does this sit? ------------
        # Read only from bars BEFORE the base, so the value is fixed the moment
        # the zone forms and never moves again. Using the whole window instead
        # would make every zone's curve shift when the user changed the bar
        # count, which is the same class of defect as anchoring an HTF bucket
        # to the window rather than the epoch.
        look_from = max(0, base_from - params.curve_lookback)
        if base_from > look_from:
            ref_hi = float(high[look_from:base_from].max())
            ref_lo = float(low[look_from:base_from].min())
        else:
            ref_hi = ref_lo = 0.0
        ref_span = ref_hi - ref_lo
        midpoint = (top + bottom) / 2.0
        curve = (
            float(np.clip((midpoint - ref_lo) / ref_span, 0.0, 1.0))
            if ref_span > EPS
            else 0.5
        )
        curve_favourable = curve <= 1 / 3 if is_demand else curve >= 2 / 3

        # --- lifecycle: replay every bar after the leg-out ------------------
        touches = 0
        penetration = 0.0
        first_test_time: int | None = None
        arrival_atr: float | None = None
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
                        # How hard price came back. Measured once, at the first
                        # touch, because that is the only moment the question is
                        # actionable. The doctrine disagrees with itself about
                        # whether fast is good or bad, so it is recorded and
                        # left unscored.
                        arr_from = max(0, i - params.arrival_bars)
                        if atr[i] > EPS and i > arr_from:
                            arrival_atr = round(
                                abs(close[i] - close[arr_from]) / float(atr[i]), 3
                            )
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

        # --- formation description -------------------------------------------
        # Everything here is fixed when the zone forms and never moves again.
        # That is the point: it describes how the zone was built, and makes no
        # statement about what price will do when it comes back.
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
            "tightness": round(f_tightness * _W_TIGHTNESS, 4),
            "compactness": round(f_compactness * _W_COMPACTNESS, 4),
            "volume": round(f_volume * _W_VOLUME, 4),
        }
        formation_score = float(np.clip(sum(factors.values()), 0.0, 1.0))

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
                formation_score=round(formation_score, 4),
                departure_atr=round(departure_atr, 3),
                profit_margin=round(min(profit_margin, 99.9), 2),
                curve=round(curve, 3),
                curve_favourable=curve_favourable,
                arrival_atr=arrival_atr,
                base_drift=round(min(drift, 9.99), 3),
                base_overlap=round(overlap, 3),
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
                    base_run_from=base_run[1],
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
    # Per-side counts BEFORE the display cap. Without these the only visible
    # numbers are post-cap, so a detector that genuinely found more of one side
    # than the other is indistinguishable from one whose output was simply
    # truncated at the cap on both.
    stats["found_demand"] = sum(1 for z in found if z.side is ZoneSide.DEMAND)
    stats["found_supply"] = len(found) - stats["found_demand"]
    return result, stats


def _dedupe(
    zones: list[Zone], max_overlap: float, stats: dict[str, float]
) -> list[Zone]:
    """Collapse zones that mostly repeat another zone at the same price.

    Overlap is measured against the *smaller* of the two heights, so a thin zone
    swallowed by a fat one is correctly seen as redundant.

    The survivor is chosen by display priority, not by predicted quality: least
    consumed first, then formation. Two zones at one price are one level, and
    the one price has not eaten yet is the one worth drawing.
    """
    kept: list[Zone] = []
    ranked = sorted(
        zones,
        key=lambda z: (_STATE_PRIORITY[z.state], z.formation_score),
        reverse=True,
    )
    for zone in ranked:
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
