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

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ..indicators import EPS, classify_candles, flat_atr, runs, wilder_atr
from ..profit_zone import mark_crowding, mark_profit_zones
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
# docs/CALIBRATION.md. On 2707 resolved zones across five series no factor
# separated held from failed with a confidence interval clear of 0.5, so fitting
# weights here would be fitting noise. The sum itself ranks BACKWARDS (AUC 0.464
# and 0.477), which is a stronger reason not to fit it than being merely flat.
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


#: Bars of TRAILING volume the leg-out is judged against, and the minimum that
#: makes the judgement possible at all.
#:
#: THIS REPLACES `volume.mean()` OVER THE WHOLE WINDOW, which was lookahead and
#: reached the user. A zone that formed in 2024 was scored against the mean
#: volume of every bar in the request, including bars years in its future, while
#: the comment above the use said "everything here is fixed when the zone forms
#: and never moves again" and `Zone.settled` promised the same. Both were false.
#:
#: Measured through the shipped API on 2026-08-20, XAUUSD 15m, mt5, caps lifted:
#: nine zones appear in both a 500-bar and a 3000-bar window with byte-identical
#: geometry, and SEVEN of them carry a different `formation_score` in the two -
#: 0.7960 against 0.7792, 0.8516 against 0.8387. Same zone, same bars under it,
#: different number because the user moved the Bars picker. Over 3000 to 50000
#: bars the window mean went 1840.8 to 3250.3, a 77% shift.
#:
#: It was not only cosmetic. `_dedupe` ranks overlapping zones by this score, so
#: WHICH box is drawn was future-dependent too: on XAUUSD 15m two supply zones
#: that both predate bar 3000 swap survivor between a 3000-bar and a 20000-bar
#: request, with no change to either one's geometry.
#:
#: 200 is the same lookback `curve_lookback` already uses for the neighbouring
#: "what counts as normal here" question, so it is this file's own convention
#: rather than a new number. Trailing rather than expanding, because an
#: expanding mean anchored to the window's first bar is still a function of
#: where the caller started.
#:
#: ALL OF IT OR NONE OF IT, and the middle ground was tried first and measured
#: wrong. A baseline over "however many bars happen to precede this zone" is
#: still a function of where the window starts: with a 20-bar floor, seven of
#: ten zones still moved between a 500-bar and a 3000-bar request, because a
#: zone 100 bars into the short window is 2600 bars into the long one and gets a
#: different amount of history either side. Requiring the full 200 leaves
#: exactly one boundary - a zone either has the same 200 bars behind it in every
#: window that contains them, or it has no baseline at all and goes neutral.
#:
#: What remains, stated rather than hidden: a zone inside the first 200 bars of
#: the window scores neutral on volume and the same zone scores properly in a
#: longer window. That is a warm-up, not lookahead - nothing from the future
#: enters either answer - and it is the same shape as any trailing indicator's
#: first N bars. `formation_score` orders the display and feeds `_dedupe`; it
#: gates nothing, which is why a neutral warm-up is an acceptable price and a
#: future-dependent score was not.
_VOLUME_BASELINE_BARS = 200


class LifecycleParams(Protocol):
    """The only two settings the replay actually reads.

    Narrower than `SupplyDemandParams` on purpose: the fair-value-gap and order
    block detectors reuse this replay and have nothing to do with bases or
    departures, so demanding the whole supply/demand parameter block would be
    asking them to carry fields they must not have.
    """

    mitigation_pct: float
    arrival_bars: int


@dataclass
class Lifecycle:
    """What price did to a zone after its leg-out."""

    state: ZoneState
    touches: int
    penetration: float
    first_test_time: int | None
    arrival_atr: float | None
    break_index: int | None


# THE HOT SPOT, MEASURED AND DELIBERATELY LEFT ALONE.
#
# cProfile on 50,000 bars with all twelve bar layers on: this function is 26.60s
# of 37.06s total tottime over 55,322 calls, 53,629 of them from
# `imbalance._finish`. The next-largest entry is 0.97s. It is a per-candidate
# Python scalar loop over numpy arrays, and it is called once per candidate box
# BEFORE the state filter, so most of the work is discarded - at 1500 bars
# `order_block` reports 1,493 candidates and draws 7 boxes.
#
# Not optimised, and the reason is that the two paths through here want opposite
# things. Where a display cap is finite, replaying newest-first and stopping once
# the cap is satisfied would skip almost all of it - but that path is already
# fast: 500 bars, the UI's own default, costs 18ms end to end. Where the cap is 0
# the caller is MEASURING, and every candidate has to be replayed by definition,
# so there is nothing to skip. The expensive path is the one that cannot be
# short-circuited without changing the answer, and the cheap path does not need
# it. Vectorising the walk itself is the real fix and it is a rewrite of the
# lifecycle semantics, not a tweak; `docs/BACKLOG.md` carries it.
#
# What this DOES mean for anyone reading a timing: above roughly 5,000 bars every
# second belongs to this function. The provider is not the bottleneck (the MT5
# terminal answers a 50,001-bar read in 2.8ms) and neither is serialisation
# (75ms for a 5.65MB response).
def replay_lifecycle(
    time: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    top: float,
    bottom: float,
    distal: float,
    is_demand: bool,
    start: int,
    params: LifecycleParams,
) -> Lifecycle:
    """Walk the bars from `start` and report what became of this box.

    Separate from `detect` because refinement shrinks a zone AFTER detection,
    and a tighter distal is a different question about the same bars: price that
    never closed past the wide edge may well have closed past the narrow one. A
    refined zone that kept its old `state` would be drawn as fresh when the
    chart plainly shows it broken.
    """
    height = max(top - bottom, EPS)
    touches = 0
    penetration = 0.0
    first_test_time: int | None = None
    arrival_atr: float | None = None
    break_index: int | None = None
    was_inside = False

    for i in range(start, len(close)):
        if close[i] < distal if is_demand else close[i] > distal:
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
                    # whether fast is good or bad, so it is recorded and left
                    # unscored.
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

    return Lifecycle(
        state, touches, penetration, first_test_time, arrival_atr, break_index
    )


def cap_per_side(zones: list[Zone], limit: int) -> list[Zone]:
    """Keep the newest `limit` zones per side, 0 meaning no cap.

    Cap per side by recency: the zones price can actually reach next are the ones
    nearest in time, not the strongest one from 400 bars ago. Selection is by
    TIME rather than by any quality figure, deliberately - the only composite
    this project ever tried to rank with turned out to rank backwards.

    Zero disables it, and that escape hatch is not a nicety. This cap is a
    READABILITY limit, but it selects on time, so any measurement taken through
    it is a measurement of the recent tail wearing the whole history's name. It
    did exactly that here until 2026-08-13.

    Lives here, and is imported by the imbalance detectors and by the API, because
    the rule was written out three separate times and the third copy appeared the
    day a refining pass had to lift the cap and put it back. A display rule
    duplicated across three files is the same hazard the detector registry warns
    about: change it in one place, and the other two keep the old behaviour while
    still looking correct.
    """
    if limit == 0:
        return sorted(zones, key=lambda z: z.time_from)
    kept: list[Zone] = []
    for side in (ZoneSide.DEMAND, ZoneSide.SUPPLY):
        per_side = sorted(
            (z for z in zones if z.side is side),
            key=lambda z: z.time_from,
            reverse=True,
        )
        kept.extend(per_side[:limit])
    kept.sort(key=lambda z: z.time_from)
    return kept


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
    # Prefix sums so each zone's trailing baseline is O(1) rather than a slice
    # per zone. See `_VOLUME_BASELINE_BARS` for why it is trailing at all.
    volume_prefix = np.concatenate(([0.0], np.cumsum(volume))) if has_volume else None

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
        # NOT `atr_base`, and the difference is a repainting price rather than a
        # rounding taste. `atr_base` is Wilder's, whose seed never fully leaves
        # it, so a floor derived from it makes the grown edge a function of where
        # the window starts - see `flat_atr` for the two readings that proved it.
        # None means the flat window is not fully present, and then nothing is
        # grown: the raw bar extremes are already stable, and a box that is
        # merely thin is better than a box that moves.
        floor_scale = flat_atr(high, low, close, params.atr_period, base_from)
        floor = params.zone_min_atr * floor_scale if floor_scale is not None else 0.0
        height = top - bottom
        if height < floor:
            if side is ZoneSide.DEMAND:
                top = bottom + floor
            else:
                bottom = top - floor
            height = top - bottom

        # zone_min_atr is schema-valid at 0.0, and a base whose bars all have
        # open == high == low == close then has no floor to grow into: height is
        # exactly 0 and the drift ratio below divides by it. Same guard as
        # refine.py and imbalance.py, which both drop a zero-height box.
        if height <= EPS:
            continue

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
        # CLIPPED AT THE FIRST TOUCH, and this is not a refinement. Without the
        # clip the window keeps running after price has already come back, so
        # the gate is decided partly by bars that printed AFTER the only moment
        # a trader could have acted on it.
        #
        # tools/calibrate.py has always clipped - `score_as_of` says so in its
        # own docstring - so the harness and the product were running two
        # different gates and only one of them was honest. Measured on 24,000
        # bars across three series: the first touch lands inside the lookahead
        # window for 87% of touched zones, and 34% of the zones the product drew
        # would have FAILED the gate applied as of the touch. Zero went the
        # other way, because the unclipped window is a superset. That is
        # systematic over-admission, not noise, and it means the drawn
        # population was never the measured population.
        first_touch = None
        for j in range(leg_out[2] + 1, n):
            if low[j] <= top and high[j] >= bottom:
                first_touch = j
                break
        look_to = min(n, leg_out[1] + params.departure_lookahead)
        if first_touch is not None:
            # max(), so a zone touched immediately still has one bar of window
            # rather than an empty slice.
            look_to = max(leg_out[1] + 1, min(look_to, first_touch))
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
        life = replay_lifecycle(
            time, high, low, close, atr, top, bottom, distal, is_demand,
            leg_out[2] + 1, params,
        )
        state = life.state
        touches = life.touches
        penetration = life.penetration
        first_test_time = life.first_test_time
        arrival_atr = life.arrival_atr
        break_index = life.break_index

        # --- formation description -------------------------------------------
        # Everything here is fixed when the zone forms and never moves again.
        # That is the point: it describes how the zone was built, and makes no
        # statement about what price will do when it comes back.
        #
        # THAT SENTENCE WAS FALSE UNTIL 2026-08-20 and the comment is what made
        # it hard to see: the volume factor divided by the mean volume of the
        # WHOLE requested window, so a zone's score moved when the user widened
        # the Bars picker. See `_VOLUME_BASELINE_BARS` for the measurement and
        # for why `_dedupe` made it worse than cosmetic.
        f_tightness = float(
            np.clip(1.0 - (height / atr_base) / params.base_max_atr, 0.0, 1.0)
        )
        span = params.base_max_bars - 1
        f_compactness = 1.0 - ((base_to - base_from) / span if span > 0 else 0.0)
        # The baseline is the volume of the bars BEFORE this leg, never the
        # window's. `leg_out[1]` is the leg's first bar, so the slice stops
        # short of it and no bar the leg itself contributed can raise the bar it
        # is being judged against.
        baseline = 0.0
        if volume_prefix is not None:
            lo = max(0, leg_out[1] - _VOLUME_BASELINE_BARS)
            # Not `span`: that name is already the compactness denominator four
            # lines up, and shadowing it here would leave two different meanings
            # of one word inside one loop body.
            history = leg_out[1] - lo
            if history >= _VOLUME_BASELINE_BARS:
                baseline = (
                    float(volume_prefix[leg_out[1]] - volume_prefix[lo]) / history
                )
        if baseline > EPS:
            leg_vol = float(volume[leg_out[1] : leg_out[2] + 1].mean())
            f_volume = min(leg_vol / (2.0 * baseline), 1.0)
        else:
            # Neutral, and it covers two cases on purpose: a feed with no volume
            # at all, and a zone too near the start of the series to have a
            # baseline. Both are "not measurable here", and neither may be
            # rendered as weak volume.
            f_volume = 0.5

        factors = {
            "tightness": round(f_tightness * _W_TIGHTNESS, 4),
            "compactness": round(f_compactness * _W_COMPACTNESS, 4),
            "volume": round(f_volume * _W_VOLUME, 4),
        }
        formation_score = float(np.clip(sum(factors.values()), 0.0, 1.0))

        time_to = int(time[break_index]) if break_index is not None else int(time[-1])

        found.append(
            Zone(
                # IDENTITY MAY NOT BE A PRICE. Until 2026-08-21 this ended in
                # `-{top:.5f}`, so a zone whose top moved by a hundredth became a
                # DIFFERENT zone to anything keying on the id - and boxes do
                # move: `test_a_projected_higher_timeframe_box_never_moves`
                # caught a projected 1d box shifting its bottom by 0.009. For a
                # reader that is invisible; for anything that has to say "I have
                # already acted on this zone" it is a new key and a second
                # action.
                #
                # Kind plus the base bar's OPEN TIME is enough, and that is
                # measured rather than assumed: on 50,000 bars of broker gold the
                # five detectors draw 25,134 zones and the price-free key
                # collides ZERO times. The time is an epoch from the feed, so it
                # does not shift when the window grows the way a bar index would.
                # Prices stay on the object as `top` and `bottom`, which is where
                # a price belongs.
                id=f"{kind.value}-{int(time[base_from])}",
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
                # Settled means the GATE verdict can no longer move: the
                # leg-out has ended and the window that decided departure has
                # fully printed. `look_to` is that window's end, clipped at the
                # first touch, so this is exactly the bar after which nothing
                # this zone reports will change.
                settled=leg_out[2] < n - 1 and look_to < n,
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

    # The two cross-zone passes run HERE, on everything that survived detection,
    # and not in the caller on what survived the display cap. A wall the chart
    # did not have room to draw is still a wall, and measuring the road against
    # the drawn subset makes it look longer than it is - by exactly the amount
    # the cap threw away. Same class of error as calibrating through the cap.
    if visible:
        mark_profit_zones(visible, int(time[-1]))
        mark_crowding(visible, params.min_profit_zone_rr)

    result = cap_per_side(visible, params.max_zones_per_side)
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
        key=lambda z: (_STATE_PRIORITY[z.state], z.departure_atr or 0.0),
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
