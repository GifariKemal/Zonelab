"""Shrink a higher-timeframe zone to the lower-timeframe base inside it.

The method is top-down: the zone belongs to the higher timeframe, the entry
belongs to the lower one. A 4h base is four 1h candles wide, and price rarely
turns from all four - it turns from the handful of lower-timeframe bars where
the move actually paused. Refinement replaces the coarse box with that inner
pause.

Three things make this honest rather than merely tighter.

1. **The bars are already in hand.** The higher-timeframe series is built by
   aggregating the chart's own candles, so the lower-timeframe detail inside
   every HTF base is sitting in the same request. No second fetch, no second
   cache, and no way for the refined box to be computed from bars the chart is
   not showing.

2. **The distal is still a wick extreme**, just of a smaller set of candles.
   That keeps the one rule the doctrine never wavers on - the stop sits beyond
   the wick - while making the stop tighter, which is the entire point of
   refining. The trade-off is real and it cuts both ways: a tighter stop is a
   better price and an easier stop to hit, so `tools/reaction.py` and
   `tools/walkforward.py` measure it rather than assuming it.

3. **The lifecycle is replayed after the box moves.** A narrower distal is a
   different question about the same bars: price that never closed past the wide
   edge may well have closed past the narrow one. A refined zone carrying its
   old `state` would be drawn fresh on a chart that plainly shows it broken.

The zone is judged on its OWN timeframe's bars both times. Refinement sharpens
where the box sits; it does not demote an H4 zone to an M15 one, and an H4 zone
still must not die because a single M15 candle dipped through it.

WHERE THE RULES CAME FROM, and how firm they are
Searched 2026-08-13. **No primary source in this lineage publishes a refinement
procedure at all.** Seiden's FXStreet and MoneyShow columns, the Online Trading
Academy user guide, and the OTA patent (US8650115B1, Seiden named inventor) all
work on one timeframe and contain no drill-down step. Refinement is a
third-party codification attributed to that lineage. Absence of a published rule
is not absence of a rule - the paid course material was never public - but it
does mean nothing here can cite a primary source, so the choices are stated
rather than justified by authority:

- **Both edges move, and the stop goes on the refined distal.** This is the
  dominant third-party reading, and one SMC guide states the opposite practice
  (an HTF stop under an LTF entry) is a mistake. Nobody argues the third
  position, refined entry with the HTF distal kept.
- **ICT's sub-candle refinement does the reverse** - enter at the 50% mean
  threshold, keep the stop beyond the full wick - and no source reconciles the
  two conventions. This module implements the drill-down one.
- **The LAST pause is chosen, not the tightest.** The cluster camp describes
  finding "the source" the departure left from, which is the last one. A
  tightest-cluster rule appears in no source; inventing one and calling it
  doctrine would be exactly the kind of borrowed authority this project avoids.
- **No timeframe ratio is published.** The circulating "daily to H1, H4 to H1,
  M15 to M5" triple traces to one secondary blog and encodes a floor rather than
  a divisor. Here the lower timeframe is simply the chart's own, which is the
  only one whose bars are guaranteed present.
- **Nobody has published a number for what refinement buys.** The claimed gain
  is arithmetic - a tighter stop divides into a bigger R multiple - which
  assumes the tighter stop survives at the same rate. That is the untested
  assumption, and `tools/reaction.py` and `tools/walkforward.py` test it.
"""

from __future__ import annotations

import numpy as np

from .detect.supply_demand import replay_lifecycle
from .indicators import EPS, classify_candles, runs, wilder_atr
from .models import Candle, Refinement, SupplyDemandParams, Zone, ZoneSide
from .providers.base import INTERVALS


def refine_zones(
    zones: list[Zone],
    htf_bars: list[Candle],
    ltf_bars: list[Candle],
    htf: str,
    params: SupplyDemandParams,
) -> dict[str, float]:
    """Refine every zone in place. Returns a stats dict explaining the misses.

    Nothing is dropped: a zone that cannot be refined is left exactly as it was
    and counted under the reason. "No zone refined" and "refinement is off" have
    to be distinguishable, or a silent no-op reads as a working feature.
    """
    stats: dict[str, float] = {
        "refine_candidates": len(zones),
        "refined": 0,
        "refine_no_ltf_bars": 0,
        "refine_no_inner_base": 0,
        "refine_not_contained": 0,
        "refine_no_gain": 0,
    }
    if not zones or not ltf_bars or htf not in INTERVALS:
        return stats

    step = INTERVALS[htf]

    lt_time = np.array([c.time for c in ltf_bars], dtype=np.int64)
    lt_open = np.array([c.open for c in ltf_bars], dtype=np.float64)
    lt_high = np.array([c.high for c in ltf_bars], dtype=np.float64)
    lt_low = np.array([c.low for c in ltf_bars], dtype=np.float64)
    lt_close = np.array([c.close for c in ltf_bars], dtype=np.float64)

    # Classified once over the WHOLE lower series, not per window. ATR and the
    # one-bar lag inside `classify_candles` both need the bars before the base;
    # slicing first would judge the first bar of every window against its own
    # volatility and quietly relabel it.
    lt_atr = wilder_atr(lt_high, lt_low, lt_close, params.atr_period)
    lt_labels = classify_candles(
        lt_open, lt_high, lt_low, lt_close, lt_atr,
        params.impulse_body_ratio, params.impulse_atr,
    )

    ht_time = np.array([c.time for c in htf_bars], dtype=np.int64)
    ht_high = np.array([c.high for c in htf_bars], dtype=np.float64)
    ht_low = np.array([c.low for c in htf_bars], dtype=np.float64)
    ht_close = np.array([c.close for c in htf_bars], dtype=np.float64)
    ht_atr = wilder_atr(ht_high, ht_low, ht_close, params.atr_period)

    for zone in zones:
        anatomy = zone.anatomy
        if not (0 <= anatomy.base_from <= anatomy.base_to < len(ht_time)):
            continue

        # The base's span in wall-clock time, which is what the two series
        # share. Bar indices do not survive the change of timeframe.
        window_from = int(ht_time[anatomy.base_from])
        window_to = int(ht_time[anatomy.base_to]) + step
        lo = int(np.searchsorted(lt_time, window_from, side="left"))
        hi = int(np.searchsorted(lt_time, window_to, side="left"))
        if hi - lo < 2:
            stats["refine_no_ltf_bars"] += 1
            continue

        inner = _inner_base(lt_labels[lo:hi], params.base_max_bars)
        if inner is None:
            stats["refine_no_inner_base"] += 1
            continue
        start, end = lo + inner[0], lo + inner[1]

        box = _box(
            lt_open[start : end + 1], lt_high[start : end + 1],
            lt_low[start : end + 1], lt_close[start : end + 1],
            zone.side is ZoneSide.DEMAND, params,
            float(lt_atr[max(0, start - 1)]),
        )
        if box is None:
            stats["refine_no_inner_base"] += 1
            continue
        top, bottom = box

        # Containment is not a formality. A refined box that pokes outside the
        # HTF zone would move the distal the WRONG way, loosening the stop it
        # exists to tighten, and would also break the promise that a refined
        # zone is a subset of the zone the user was already shown.
        if top > zone.top + EPS or bottom < zone.bottom - EPS:
            stats["refine_not_contained"] += 1
            continue

        old_height = zone.top - zone.bottom
        new_height = top - bottom
        if old_height <= EPS or new_height >= old_height - EPS:
            # The inner base already spans the whole HTF base. Refining changes
            # nothing, and stamping evidence of a refinement that did not happen
            # would be a lie the UI would repeat.
            stats["refine_no_gain"] += 1
            continue

        is_demand = zone.side is ZoneSide.DEMAND
        proximal, distal = (top, bottom) if is_demand else (bottom, top)

        life = replay_lifecycle(
            ht_time, ht_high, ht_low, ht_close, ht_atr,
            top, bottom, distal, is_demand, anatomy.leg_out_to + 1, params,
        )

        zone.refinement = Refinement(
            timeframe="",  # filled by the caller, which knows the chart interval
            from_top=round(zone.top, 8),
            from_bottom=round(zone.bottom, 8),
            shrank_to=round(new_height / old_height, 4),
            bars=end - start + 1,
            time_from=int(lt_time[start]),
            time_to=int(lt_time[end]),
        )
        zone.top, zone.bottom = top, bottom
        zone.proximal, zone.distal = proximal, distal
        zone.state = life.state
        zone.touches = life.touches
        zone.penetration_pct = round(life.penetration, 4)
        zone.first_test_time = life.first_test_time
        zone.arrival_atr = life.arrival_atr
        zone.time_to = (
            int(ht_time[life.break_index])
            if life.break_index is not None
            else int(ht_time[-1])
        )
        stats["refined"] += 1

    return stats


def _inner_base(labels: np.ndarray, max_bars: int) -> tuple[int, int] | None:
    """The last pause inside the window, clipped to its tail.

    Last, not longest and not tightest. The zone is the ground the departure
    left from, so when a base contains several pauses the one that matters is
    the one price was standing on when it went. Picking the tightest instead
    would sometimes hand back a pause price had already walked away from.

    Clipping to `max_bars` mirrors what the detector does one timeframe up, so
    the two boxes are cut by the same rule rather than by two rules that happen
    to agree today.
    """
    found: tuple[int, int] | None = None
    for label, start, end in runs(labels):
        if label == 0:
            found = (start, end)
    if found is None:
        return None
    start, end = found
    return max(start, end - max_bars + 1), end


def _box(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    is_demand: bool,
    params: SupplyDemandParams,
    atr_base: float,
) -> tuple[float, float] | None:
    """Top and bottom for a run of base candles, by the detector's own rules.

    Deliberately the same asymmetry as `detect`: the distal is the wick extreme
    in both variants, only the proximal moves, and the minimum-height floor
    grows from the proximal side alone so that widening a doji base can never
    push the stop into it.
    """
    if len(high) == 0:
        return None

    wick_hi, wick_lo = float(high.max()), float(low.min())
    if params.proximal_basis == "body":
        body_hi = float(np.maximum(open_, close).max())
        body_lo = float(np.minimum(open_, close).min())
    else:
        body_hi, body_lo = wick_hi, wick_lo

    top, bottom = (body_hi, wick_lo) if is_demand else (wick_hi, body_lo)

    floor = params.zone_min_atr * max(atr_base, 0.0)
    if top - bottom < floor:
        if is_demand:
            top = bottom + floor
        else:
            bottom = top - floor

    return (top, bottom) if top - bottom > EPS else None
