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

WHERE THIS DEPARTS FROM THE SOURCES, checked 2026-08-15
The primary source for both patterns is a YouTube channel. There is no book, no
paper, no canon, and every written definition in circulation is a third-party
codification of a video. So the departures are listed rather than argued, and
two of them were settled by measurement instead of opinion.

  FVG geometry            NO DEPARTURE. Wick-to-wick, `h1 < l3` or `l1 > h3`,
                          is the consensus and is what the two measured studies
                          test. Body-to-body is a DIFFERENT NAMED PATTERN (a
                          volume imbalance), not a variant of this one.

  no middle-candle test   Some codifications require the middle candle to close
                          in the gap's direction. Measured on 16,693 gaps across
                          four series: that test would reject **12 of them,
                          0.1%**. The departure is real and negligible, and now
                          it is a number rather than an argument.

  min_gap_atr = 0.1       OURS. No primary source has a minimum. Indicator
                          defaults range from 0 (off) to 0.25 x ATR. SWEPT, and
                          the result is worth knowing: the gap-versus-placebo
                          difference is LARGEST with the filter off (+29.1
                          points) and shrinks as the threshold rises (+25.2 at
                          the shipped 0.1, +15.3 at 0.5). So this threshold buys
                          CHART READABILITY and pays for it in measured edge. It
                          is not a quality filter and must not be read as one.
                          Results here are also not comparable to published FVG
                          statistics, which gate nothing at all.

  consequent encroachment ALREADY PRESENT, under another name. The 50% level is
                          the most-cited operational level in this literature.
                          `penetration_pct >= 0.5` is exactly "price traded to
                          the midpoint", and `mitigation_pct` ships at 0.5, so a
                          box in state `mitigated` has by definition reached it.
                          Not added as a separate field, because a second name
                          for one number is how two fields drift apart.

  order block box         Whole high-to-low range. The most common convention,
                          and the WIDEST of three - which mechanically raises
                          the touch rate against a body-only detector, so
                          cross-study comparison is invalid.

  no structure break      THE BIGGEST DEPARTURE, and a contested rule. Required
                          by some codifications, "recommended not mandatory" by
                          others, absent from the candle-level definition
                          itself. Worth knowing: the figures usually quoted to
                          justify requiring it (52% against 65-68% on 2,400
                          setups) are UNTRACEABLE - the page they are attributed
                          to contains no statistics at all. Neither camp has
                          evidence, so this is a stated choice on both sides.

  1.5 ATR over 5 bars     OURS ENTIRELY. No published ATR multiple exists for
                          "impulsive"; the nearest analogues are "2-3x average
                          candle size" asserted without derivation. Swept: the
                          ATR multiple behaves like the old detector's departure
                          gate - stricter means a wider margin over placebo
                          (+8.3 at 0.5 ATR, +15.5 at the shipped 1.5, +18.9 at
                          2.5) and far fewer boxes (46,868 down to 8,758). The
                          BAR WINDOW barely matters at all: +16.1, +15.5, +15.4
                          for 3, 5 and 10 bars. One invented number that turns
                          out to carry no weight, which is the best thing a
                          sweep can tell you about a number you made up.

  opposite-coloured       Read as `close < open`. Others codify the same phrase
                          as `close < close[1]`, which picks a different candle
                          on inside and outside bars. Nobody resolves it.

WHAT THE MEASURED LITERATURE SAYS, since it bears on how loudly to claim anything
Two studies disclose their method. One tested FVG reaction against a random
placebo on four futures over seven years and found the reaction real - beating
random in 34 of 36 cells by about 5 points - while the tradeable edge was
consumed by costs in 17 of 18 configurations. The other ran 54 mechanical SMC
variations on 2.55 million EURUSD bars and found **none profitable** after half
a pip. Both match the shape of what this project keeps finding on its own
detector: the reaction is real, the edge is not established.
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

    LAST, and this word used to be a lie. Until 2026-08-16 the scan marked EVERY
    opposite-coloured candle whose forward window cleared the threshold, so a run
    of three bearish candles before a rally produced three order blocks stacked
    on each other, all sharing one impulse. The docstring said "last" and the
    code said "any". It showed in the population: 21565 order blocks against
    12745 fair value gaps on identical bars, with the surplus being the same
    observation counted several times - which inflates n, correlates outcomes,
    and makes every order block statistic rest on a smaller effective sample
    than it claims.

    Last is now enforced the only way that needs no discretion: the very next
    candle must close the other way, because that candle is the start of the
    impulse. In a run of three bearish candles only the third has a bullish
    successor.
    """
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n, "candidates": 0, "rejected_weak_move": 0,
        "rejected_not_last": 0, "rejected_state_filter": 0,
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

        # The "last" in the definition, tested AFTER the impulse because the
        # impulse is the requirement and "last" only decides which candle gets
        # the box. Ordered the other way, a chart with no impulse anywhere would
        # report its rejections under the wrong reason.
        #
        # The next candle has to close the other way, because that candle is the
        # move starting - which is exactly what makes this one the final candle
        # of its colour before it. A doji successor counts as neither and is
        # rejected, the same way a doji block candle is rejected above.
        nxt = i + 1
        turned = close[nxt] > open_[nxt] if bearish else close[nxt] < open_[nxt]
        if not turned:
            stats["rejected_not_last"] += 1
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

    NO overlap merge here, and that is a decision rather than an omission. It
    was tried: reusing supply and demand's `_dedupe` cut same-side overlaps by
    74%, and it was reverted the same hour because it was removing real objects
    for a bad reason. `_dedupe` picks the survivor by `formation_score`, which is
    0.0 for every imbalance zone, so the winner was whatever happened to sort
    first - on one test that meant keeping a 0.3-wide sliver and discarding the
    4.5-wide gap containing it. Two gaps at different bars are two events, not
    one drawn twice, and ICT treats stacked gaps as meaningful.

    The redundancy the merge was hiding was real, but its cause was the order
    block detector marking EVERY opposite candle instead of the last one. That
    is fixed at the source in `detect_order_block`.
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
