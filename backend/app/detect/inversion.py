"""Inversion fair value gaps and breaker blocks.

Two boxes that are not new geometry. Both are an existing box read from the
other side after price closed through it: a demand zone price closed below is
now resistance, so the edge price meets first is the old BOTTOM and the
protective edge is the old TOP. `replay_lifecycle` has always computed
`break_index` - the bar a box died on - and every caller in this codebase threw
it away. These two kinds are that number kept.

WHAT THEY ARE
**Inversion fair value gap.** A fair value gap price closed through. The parent
is the one crisply defined object in the SMC vocabulary, so the inversion
inherits a rule with no discretion in it and adds exactly one more event.

**Breaker block.** The order block version of the same event, and it inherits
the order block's contested definition wholesale: whole-candle range, an
`impulse_atr` threshold, no structure break required. Every departure listed in
`imbalance.py` applies here unchanged, because the parent detector is called
rather than reimplemented.

NOTHING IS INVENTED HERE, and that is the point
The rectangle, the ATR scale, the gap floor and the impulse threshold all come
from the parent. This module contributes one decision - the lifecycle of the
inverted box starts at `break_index + 1` - and one field, `inverted_at`. A
second gap threshold for the inversion would let the two populations drift
apart, so `ImbalanceParams` is shared with the pair being inverted.

DO NOT READ THESE AS DIRECTIONAL. This is the honest part and it is not
optional. H8 in docs/CALIBRATION.md built the one subsample this project had
never had - all 11,469 first touches recorded elsewhere approach a box from the
near side and ZERO come through it - and measured the forward return after a
post-inversion touch against a control that knows only the trailing 20-bar move
and has no box anywhere. What the box ADDS over that control:

    supply_demand  -0.179  t = -2.40
    fvg            -0.165  t = -2.23
    order_block    -0.274  t = -4.22

All three SIGNIFICANTLY NEGATIVE. Knowing a box had inverted made the
directional guess WORSE than merely knowing which way price had just moved, and
order_block was negative standing alone (-0.110, t = -2.25), which is the
opposite of the breaker block doctrine rather than a null of it. n was large and
neither half of the sample rescued anything. What survived every one of nine
directional hypotheses was the control: the last 20 bars of movement, +0.164 at
t = 3.83, which is time-series momentum and needs no box at all.

So an IFVG or a BRK drawn on this chart says "this band flipped role on this
bar". That is a fact about the drawing. It says nothing about what price will do
next, and the measurement says that if you let it say something, it will say the
wrong thing.

WHAT IS DELIBERATELY NOT HERE
No score. `formation_score` is 0.0, the same as the fvg and order block
detectors, for the same reason those two ship unscored: the supply/demand
detector shipped a composite score and had to retract it. Scoring a box whose
own directional claim measured negative would be that retraction repeated with
worse evidence.
"""

from __future__ import annotations

from ..indicators import wilder_atr
from ..models import Candle, ImbalanceParams, Zone, ZoneKind, ZoneSide, ZoneState
from .imbalance import _arrays, _finish, _present, detect_fvg, detect_order_block


def _invert(
    kind: ZoneKind,
    parent,
    candles: list[Candle],
    params: ImbalanceParams,
) -> tuple[list[Zone], dict[str, float]]:
    """Every parent box that broke, re-entered from the other side.

    The parent runs with `show_broken=True` because a broken box is the raw
    material here and the parent's own state filter would otherwise eat the
    entire population, and with no per-side cap because that cap keeps only the
    NEWEST boxes - taking it on the parent would confine the inversions to the
    tail of the history before this detector ever saw them. The caller's cap is
    still honoured, by `_present` below, on the inverted boxes themselves.
    """
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n, "candidates": 0, "rejected_never_broke": 0,
        "rejected_too_small": 0, "rejected_state_filter": 0,
    }
    parents, _ = parent(
        candles,
        params.model_copy(update={"show_broken": True, "max_zones_per_side": 0}),
    )
    if not parents:
        return _present([], params, stats)

    time, _open, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)
    index_of = {int(t): i for i, t in enumerate(time)}

    found: list[Zone] = []
    for zone in parents:
        stats["candidates"] += 1
        if zone.state is not ZoneState.BROKEN:
            stats["rejected_never_broke"] += 1
            continue

        # ponytail: a BROKEN parent's `time_to` IS its break bar - both `_finish`
        # and `supply_demand.detect` set it from `replay_lifecycle`'s
        # `break_index` and set BROKEN only when that index exists - so the first
        # of the two lifecycle passes is already done and stored. A second replay
        # here would recompute a number the parent is contractually holding.
        broke = index_of[zone.time_to]

        # The same rectangle, entered from the other side. `_finish` derives
        # proximal and distal from the side it is given, and its rule for supply
        # is (proximal, distal) = (bottom, top) - which is exactly the swap the
        # inversion needs, so the flip is expressed by passing the other side
        # rather than by computing edges here.
        #
        # `broke` is the bar the box became knowable on, so the lifecycle starts
        # at `broke + 1`. Starting on the breaking bar itself would let the very
        # candle that killed the old box count as the first test of the new one -
        # the same rule, and the same reason, as the gap detector's third bar.
        inverted = _finish(
            kind,
            ZoneSide.SUPPLY if zone.side is ZoneSide.DEMAND else ZoneSide.DEMAND,
            zone.top, zone.bottom,
            index_of[zone.time_from], broke,
            time, high, low, close, atr, params,
            # The parent's own displacement, carried rather than recomputed: it
            # describes the box, and the box is the parent's.
            zone.departure_atr,
        )
        if inverted is None:
            stats["rejected_too_small"] += 1
            continue
        # The LEFT EDGE is the inversion, not the parent's origin, and that is a
        # correction rather than a preference. `_finish` derives `time_from` from
        # the origin bar it is given, so an inverted box was drawn from the bar
        # its PARENT was built on - putting a supply box on the chart with a hard
        # left edge across a window in which that same band was demand. Measured
        # before the fix: 9 of 9 breakers on one 500-bar series started before
        # they inverted. The box may not claim to have existed before the event
        # that created it.
        #
        # What this does NOT fix, checked rather than assumed: it leaves
        # `tools/collisions.py`'s opposite-side count essentially unchanged, 100
        # to 99. A first reading blamed those on a parent drawn beside its own
        # inversion, and that reading was wrong - measured, ZERO of them are a
        # box against its own parent, because inverting requires the parent to be
        # BROKEN and `show_broken` ships false, so the parent is never on the
        # chart at the same time. The 79 that involve an inversion are genuinely
        # different rectangles, and they are the real cost of these two detectors.
        #
        # `origin` is still the parent's bar, so `anatomy` and the id keep
        # pointing at the candles the rectangle came from. The evidence is
        # preserved; only the claim about WHEN this box existed is corrected.
        found.append(inverted.model_copy(update={
            "inverted_at": int(time[broke]),
            "time_from": int(time[broke]),
        }))

    return _present(found, params, stats)


def detect_ifvg(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """A fair value gap price closed through, read from the other side."""
    return _invert(ZoneKind.IFVG, detect_fvg, candles, params)


def detect_breaker(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """An order block price closed through, read from the other side."""
    return _invert(ZoneKind.BRK, detect_order_block, candles, params)
