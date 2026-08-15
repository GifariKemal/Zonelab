"""Fair value gaps and order blocks.

Two more boxes, from the ICT and SMC lineage rather than the Seiden one. They
are here for one reason: this project has a measurement rig that has killed four
plausible findings, and the only honest way to add a detector is to put it
through that rig rather than to ship it and hope.

WHAT THEY ARE, AND HOW FIRM THE DEFINITIONS ARE

**Fair value gap.** The one crisply defined object in the whole SMC vocabulary,
and the only detector here whose rule admits no discretion at all: three
consecutive bars where the first bar's high sits below the third bar's low, or
the first's low above the third's high. The middle bar moved far enough that the
wicks on either side never met, so a band of prices was skipped. The box is that
band. Nothing is chosen, nothing is fitted, and two implementations that read
the definition will produce identical output.

**Order block.** Contested, and the contest matters. The common statement is
"the last opposite-coloured candle before a strong impulsive move". Sources
disagree about (a) whether the move must break structure, (b) whether the box is
the candle's whole range or only its body, and (c) how strong "strong" is. There
is no primary source that settles any of the three. So the choices are stated:
the box is the WHOLE RANGE of the last opposite-coloured candle, the move must
clear `impulse_atr` ATR, and no structure break is required. A structure-break
variant is a different detector and would need its own measurement.

WHY THEY REUSE `Zone`
Both are boxes with a near edge, a far edge and a lifecycle, which is what
`Zone` already models. Inventing a second shape would double the drawing code,
the inspector, and the pixel harness for no gain. The `kind` field says which
detector drew it.

WHAT IS DELIBERATELY NOT HERE
No scoring, no ranking, no composite. The supply/demand detector shipped a score
and had to retract it; starting these two without one is the lesson applied
rather than repeated.
"""

from __future__ import annotations

import numpy as np

from ..indicators import EPS, wilder_atr
from ..models import (
    Anatomy,
    Candle,
    ImbalanceParams,
    Zone,
    ZoneKind,
    ZoneSide,
    ZoneState,
)
from .supply_demand import replay_lifecycle


def _arrays(candles: list[Candle]):
    return (
        np.array([c.time for c in candles], dtype=np.int64),
        np.array([c.open for c in candles], dtype=np.float64),
        np.array([c.high for c in candles], dtype=np.float64),
        np.array([c.low for c in candles], dtype=np.float64),
        np.array([c.close for c in candles], dtype=np.float64),
    )


def _finish(
    kind: ZoneKind,
    side: ZoneSide,
    top: float,
    bottom: float,
    origin: int,
    born: int,
    time: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    params: ImbalanceParams,
    displacement: float,
) -> Zone | None:
    """Wrap a raw box in the same lifecycle and contract as a supply zone.

    `born` is the bar the box became knowable, and the lifecycle starts on the
    bar AFTER it. Starting on the bar itself would let the candle that created
    the gap count as the first test of it, which is how a detector ends up
    reporting that its own construction touched it.
    """
    if top - bottom <= EPS:
        return None
    is_demand = side is ZoneSide.DEMAND
    proximal, distal = (top, bottom) if is_demand else (bottom, top)

    life = replay_lifecycle(
        time, high, low, close, atr, top, bottom, distal, is_demand,
        born + 1, params,
    )
    return Zone(
        id=f"{kind.value}-{int(time[origin])}-{top:.5f}",
        kind=kind,
        side=side,
        state=life.state,
        top=top,
        bottom=bottom,
        proximal=proximal,
        distal=distal,
        time_from=int(time[origin]),
        time_to=(
            int(time[life.break_index]) if life.break_index is not None
            else int(time[-1])
        ),
        formation_score=0.0,  # deliberately unscored, see the module docstring
        departure_atr=round(displacement, 3),
        touches=life.touches,
        penetration_pct=round(life.penetration, 4),
        first_test_time=life.first_test_time,
        arrival_atr=life.arrival_atr,
        confirmed=born < len(close) - 1,
        anatomy=Anatomy(
            leg_in_from=origin, leg_in_to=origin,
            base_run_from=origin, base_from=origin, base_to=origin,
            leg_out_from=born, leg_out_to=born,
        ),
        note=f"{kind.value}: displacement {displacement:.1f} ATR, {life.state.value}",
    )


def detect_fvg(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Three bars whose outer wicks never met.

    The gap is knowable when the THIRD bar closes, not when the first one does,
    so that is the bar the lifecycle starts after. Getting this wrong would let
    the middle bar - the one that created the gap by flying through it - be
    counted as having tested it.
    """
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n, "candidates": 0, "rejected_too_small": 0,
        "rejected_state_filter": 0,
    }
    if n < params.atr_period + 3:
        return [], stats

    time, _open, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)

    found: list[Zone] = []
    for i in range(1, n - 1):
        first, third = i - 1, i + 1
        up = high[first] < low[third]
        down = low[first] > high[third]
        if not (up or down):
            continue
        stats["candidates"] += 1

        top, bottom = (
            (float(low[third]), float(high[first])) if up
            else (float(low[first]), float(high[third]))
        )
        scale = float(atr[max(0, first - 1)])
        if scale <= EPS or (top - bottom) < params.min_gap_atr * scale:
            stats["rejected_too_small"] += 1
            continue

        zone = _finish(
            ZoneKind.FVG,
            ZoneSide.DEMAND if up else ZoneSide.SUPPLY,
            top, bottom, first, third,
            time, high, low, close, atr, params,
            (top - bottom) / scale,
        )
        if zone is not None:
            found.append(zone)

    return _present(found, params, stats)


def detect_order_block(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """The last opposite-coloured candle before an impulsive move.

    Scanned forward, and the impulse is measured from the block candle's own
    close to the extreme of the `displacement_bars` that follow it. Measuring to
    the end of some later swing instead would make the box depend on where a
    human decided the swing ended, which is the discretion this file exists to
    avoid.
    """
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n, "candidates": 0, "rejected_weak_move": 0,
        "rejected_state_filter": 0,
    }
    if n < params.atr_period + params.displacement_bars + 2:
        return [], stats

    time, open_, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)

    found: list[Zone] = []
    for i in range(1, n - params.displacement_bars - 1):
        scale = float(atr[max(0, i - 1)])
        if scale <= EPS:
            continue
        bearish = close[i] < open_[i]
        window = slice(i + 1, i + 1 + params.displacement_bars)

        # A bearish candle before an up move is a bullish block, and the
        # reverse. Both directions are checked on every bar rather than one
        # being inferred from the other, because a doji satisfies neither.
        if bearish:
            move = (float(high[window].max()) - float(close[i])) / scale
            side = ZoneSide.DEMAND
        elif close[i] > open_[i]:
            move = (float(close[i]) - float(low[window].min())) / scale
            side = ZoneSide.SUPPLY
        else:
            continue

        stats["candidates"] += 1
        if move < params.displacement_atr:
            stats["rejected_weak_move"] += 1
            continue

        zone = _finish(
            ZoneKind.OB, side, float(high[i]), float(low[i]), i,
            i + params.displacement_bars,
            time, high, low, close, atr, params, move,
        )
        if zone is not None:
            found.append(zone)

    return _present(found, params, stats)


def _present(
    found: list[Zone], params: ImbalanceParams, stats: dict[str, float]
) -> tuple[list[Zone], dict[str, float]]:
    """State filter and the per-side cap, with zero meaning no cap.

    Deliberately the same shape as the supply/demand detector's tail, including
    that zero disables the cap. A measurement taken through a recency cap is a
    measurement of the tail of the history, and that mistake has already cost
    this project one full round of calibration.
    """
    allowed = {ZoneState.FRESH, ZoneState.TESTED}
    if params.show_mitigated:
        allowed.add(ZoneState.MITIGATED)
    if params.show_broken:
        allowed.add(ZoneState.BROKEN)
    visible = [z for z in found if z.state in allowed]
    stats["rejected_state_filter"] = len(found) - len(visible)

    result: list[Zone] = []
    for side in (ZoneSide.DEMAND, ZoneSide.SUPPLY):
        per_side = sorted(
            (z for z in visible if z.side is side),
            key=lambda z: z.time_from,
            reverse=True,
        )
        result.extend(
            per_side if params.max_zones_per_side == 0
            else per_side[: params.max_zones_per_side]
        )

    result.sort(key=lambda z: z.time_from)
    stats["zones"] = len(result)
    stats["found_demand"] = sum(1 for z in found if z.side is ZoneSide.DEMAND)
    stats["found_supply"] = len(found) - stats["found_demand"]
    return result, stats
