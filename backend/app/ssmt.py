"""SSMT: one quarter's extreme, read on two instruments that disagree about it.

WHAT IT IS. An SMT divergence is two correlated instruments disagreeing about an
extreme - one makes a higher high, the other fails to. SSMT adds the word
SEQUENTIAL, and the sequence is the quarter grid: the extreme in question is the
PREVIOUS QUARTER'S, and the same degree is read on both instruments. One takes
out last quarter's high, the other does not. That is the whole object.

It is the owner's primary confirmation, and until now nothing in this engine
could express it. His checklist asks "is there a stage 1 SSMT" and "is there a
stage 2 SSMT" and the engine had no answer to give at all.

A STAGE IS A DEGREE, NOT A QUARTER. Stage 1 and stage 2 are the same construct
read at two different cycle degrees, and each stage is internally a
consecutive-quarter divergence. So this function takes ONE degree, and a caller
who wants two stages calls it twice - `week` then `day`, or `day` then
`session`. An earlier reading of the same material had the stages as quarters
(stage 1 the Q1-to-Q2 divergence, stage 2 the Q2-to-Q3 one); that reading is
wrong, and it is named here so it does not come back through the same door.

TWO STAGES ARE NOT REQUIRED. The preference for two is a preference about which
readings are worth acting on, not part of what an SSMT IS, and the same source
ships a one-SSMT model beside the two-stage one. So every stage found is
reported on its own and nothing here counts stages, waits for a second one, or
withholds an event for being alone. A caller that wants the conjunction can take
the intersection of two calls; this module will not decide that for it.

WHAT IS DELIBERATELY ABSENT. "A valid bullish SSMT requires the candle itself to
be bearish" is a rule about tCISD, a different object, and it reached the SSMT
literature by misattribution. It is not implemented, and this paragraph exists so
that its absence reads as a decision rather than an oversight.

HOW OFTEN IT FIRES DEPENDS ENTIRELY ON THE PAIR, and that is the first thing a
caller has to understand. Measured at the `day` degree on 2000 hourly bars each,
gold against four partners:

    gold vs silver     14.9%   correlated, the doctrine's own kind of pair
    gold vs platinum   21.0%   correlated
    gold vs NASDAQ     36.0%   weakly related
    gold vs BTC        43.3%   unrelated
    gold vs DXY        59.5%   INVERSELY related

The rate tracks correlation exactly, which is the sanity check that this module
measures what it claims. The last row is the important one: DXY moves opposite
to gold, so "one took the extreme and the other did not" is nearly the normal
state between them, and a same-direction divergence rule applied to an inverse
pair reports a disagreement on almost every quarter. Feeding this an inversely
correlated instrument is a category error, not a rich source of setups.

A first measurement of this module used gold against BTC and concluded that an
SSMT "is not rare", at 43%. That conclusion was about the pair, not about the
construct. On the metals complex the doctrine actually prescribes it fires on
roughly one quarter-side in six.

ALIGNMENT IS A PRECONDITION, NOT AN OPTIMISATION. This module takes candles that
are already on a shared grid - `aligned.load_aligned` builds them - and refuses
anything else. Two feeds whose bar times differ by one bar produce a divergence
that is an artefact of the clock, and downstream nothing can tell it from a fact
about the market, because the candles and the prices are all real and only the
pairing is wrong. The check is that the time lists are EQUAL, and a mismatch
raises. Consequence worth stating: on a shared grid a quarter empty for one
instrument is empty for all of them, so a per-instrument hole cannot exist here
without the input being misaligned, and misaligned input never gets this far.

A HOLE IS NOT A DIVERGENCE. A quarter with no bars gives no extreme to take out
and no extreme to fail. It produces nothing, and it is counted in `stats` rather
than being quietly absorbed - a weekend, a holiday or a feed outage sitting in
the middle of a series is the most ordinary way for a population to shrink
without anyone noticing.

NOTHING IS KNOWABLE BEFORE ITS QUARTER CLOSES. A quarter's extreme is settled
only once the quarter has ended: an SSMT between quarter N-1 and quarter N is
knowable at the close of quarter N and never inside it. So a quarter counts as
closed only when a bar exists at or after its end, which is evidence from the
series itself rather than from a wall clock the series knows nothing about. That
withholds the newest quarter until the next one prints its first bar, which is
conservative by one bar and never optimistic by any. Every event carries
`knowable_at` so a chart cannot draw it early.

NO DIRECTION CLAIM. Twelve pre-registered directional hypotheses have failed in this
project, so this module reports THAT a divergence exists and WHERE, and says
nothing whatever about what price does next. `took` and `failed` are a
description of two price series, not a recommendation about either of them.

PAIRS, NOT A BASKET. Three metals produce three pair readings and not one
collapsed verdict, because "gold and silver diverged" and "gold and platinum
diverged" are different facts and a caller has to be able to see which one it
got.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from itertools import combinations
from typing import Literal

from .dealing_range import position_at, range_at
from .models import Candle, SSMTDivergence
from .quarters import Quarter, quarters


@dataclass(frozen=True)
class SSMTEvent:
    """One consecutive-quarter divergence between one pair of instruments.

    Carries the four prices the reading was made from, so the arithmetic can be
    re-done by hand from the event alone: `took_now` beat `took_prior` on the
    named side and `failed_now` did not beat `failed_prior`.
    """

    degree: str
    prior: Quarter  # quarter N-1, whose extreme was the target
    quarter: Quarter  # quarter N, in which one instrument took it
    side: Literal["high", "low"]
    took: str  # the instrument that took the previous quarter's extreme
    failed: str  # the instrument that did not
    took_prior: float
    took_now: float
    failed_prior: float
    failed_now: float
    # The BAR each of those four prices printed on. Carried so the divergence
    # can be drawn as the line the method actually describes - from the extreme
    # that was taken to the one that was not - rather than as a band smeared
    # across a whole quarter. `knowable_at` is still the only timestamp anything
    # may gate on; these four are earlier by construction and are geometry.
    took_prior_at: int
    took_now_at: int
    failed_prior_at: int
    failed_now_at: int
    knowable_at: int  # `quarter.end`: the close that settles the reading


def ssmt(
    series: dict[str, list[Candle]], degree: str
) -> tuple[list[SSMTEvent], dict[str, float]]:
    """Every consecutive-quarter divergence at `degree`, per instrument pair.

    `series` must be ALIGNED: same bar times, same order, for every symbol. That
    is what `aligned.load_aligned` returns, and fetching is the caller's job so
    that this stays a function of candles and can be tested offline.

    Returns `(events, stats)`, events ordered by quarter, then by the caller's
    symbol order, then high before low. `stats` carries:

        quarters              quarters of `degree` overlapping the series
        quarters.closed       of those, the ones a bar has printed past
        quarters.no_bars      of those, the ones with no bars on the grid
        pairs                 consecutive quarter pairs whose second has closed
        pairs.compared        of those, the ones both quarters had bars in
        pairs.skipped_no_bars of those, the ones dropped for an empty quarter
        pairs.across_gap      compared pairs not touching on the clock, see below
        events                events returned
        side.high, side.low   events by side
        pair:<A>|<B>          events for that instrument pair, one key per pair

    Raises ValueError when fewer than two instruments are given, when their bar
    times are not identical, or when `degree` is not a quarter degree.

    TAKING OUT IS STRICT. A new high must EXCEED the previous quarter's high; an
    equal high did not take it. The same downward for a low. An equal extreme is
    the one case where both readings are defensible and neither is measured here,
    so it counts as a failure to take, which keeps the two sides symmetrical.

    CONSECUTIVE MEANS ADJACENT IN THE GRID, WHICH IS A CHOICE. Quarters are
    paired with the quarter before them in time order, and at some degrees that
    is not the same as touching on the clock: the week degree has no Friday
    quarter and the month degree has no fifth week, so a Q4 and the next cycle's
    Q1 are adjacent in the list with real time in between. Those pairs are kept -
    the previous quarter is still the previous quarter - and counted separately
    as `pairs.across_gap` so a reader who disagrees can see exactly how many
    events rest on it.
    """
    stats: dict[str, float] = {
        "quarters": 0.0, "quarters.closed": 0.0, "quarters.no_bars": 0.0,
        "pairs": 0.0, "pairs.compared": 0.0, "pairs.skipped_no_bars": 0.0,
        "pairs.across_gap": 0.0, "events": 0.0, "side.high": 0.0, "side.low": 0.0,
    }  # fmt: skip
    symbols = list(series)
    if len(symbols) < 2:
        raise ValueError(
            f"ssmt is a cross-instrument read and needs at least two symbols, "
            f"got {symbols}"
        )
    for a, b in combinations(symbols, 2):
        stats[f"pair:{a}|{b}"] = 0.0

    times = [c.time for c in series[symbols[0]]]
    for symbol in symbols[1:]:
        other = [c.time for c in series[symbol]]
        if other != times:
            # Refused rather than compared on the overlap. A divergence read
            # across bars that are not the same bars is an artefact of the
            # clock, and it is indistinguishable from a real one afterwards.
            raise ValueError(
                f"{symbol} is not on the same grid as {symbols[0]}: "
                f"{len(other)} bars against {len(times)}"
                + (
                    ""
                    if len(other) != len(times)
                    else f", first difference at index "
                    f"{next(i for i, (x, y) in enumerate(zip(times, other)) if x != y)}"
                )
                + ". Align them first (app.aligned.load_aligned); nothing here "
                "fills a hole or pairs neighbouring bars."
            )
    if not times:
        return [], stats

    grid = quarters(degree, times[0], times[-1])
    stats["quarters"] = float(len(grid))

    # Bar ranges are computed ONCE, from the shared time list, because alignment
    # guarantees every symbol occupies the same indices. Per-symbol slicing here
    # would be the same numbers arrived at three times.
    spans = [
        (q, bisect_left(times, q.start), bisect_left(times, q.end)) for q in grid
    ]
    closed = [(q, lo, hi) for q, lo, hi in spans if q.end <= times[-1]]
    stats["quarters.closed"] = float(len(closed))
    stats["quarters.no_bars"] = float(sum(lo == hi for _, lo, hi in closed))

    # Each quarter's extremes per symbol, taken once. Every quarter is read
    # twice below - as N, then as N-1 for the pair after it - and scanning its
    # bars twice would be the same maximum arrived at from the same slice.
    # PRICE AND THE BAR IT PRINTED ON. The time is not decoration: a divergence
    # is DRAWN as a line between the two extremes it compares, and a price with
    # no bar behind it can only be rendered as a horizontal band across a whole
    # quarter, which is a different object from the one the method describes.
    #
    # `max`/`min` over the rows rather than over a generator of prices, so the
    # bar comes back with it. On a tie the FIRST bar wins, which is Python's own
    # rule for both and is the earlier one - deterministic, and the earlier
    # print is the one that actually set the level.
    ext: dict[tuple[int, str, str], tuple[float, int]] = {}
    for q, lo, hi in closed:
        for symbol in symbols:
            rows = series[symbol][lo:hi]
            if rows:
                top = max(rows, key=lambda c: c.high)
                bottom = min(rows, key=lambda c: c.low)
                ext[q.start, symbol, "high"] = (top.high, top.time)
                ext[q.start, symbol, "low"] = (bottom.low, bottom.time)

    events: list[SSMTEvent] = []
    for (prior, p_lo, p_hi), (now, n_lo, n_hi) in zip(closed, closed[1:]):
        stats["pairs"] += 1.0
        if p_lo == p_hi or n_lo == n_hi:
            # One of the two quarters is empty on the grid, so there is no
            # extreme to take out and none to fail. A hole, not a divergence.
            stats["pairs.skipped_no_bars"] += 1.0
            continue
        stats["pairs.compared"] += 1.0
        if prior.end != now.start:
            stats["pairs.across_gap"] += 1.0

        # Annotated because the event field is a Literal and an unannotated
        # tuple widens to `str`: nothing else stops a third side name reaching
        # a field that permits two.
        sides: tuple[Literal["high", "low"], ...] = ("high", "low")
        for a, b in combinations(symbols, 2):
            for side in sides:
                before = {s: ext[prior.start, s, side] for s in (a, b)}
                after = {s: ext[now.start, s, side] for s in (a, b)}
                took_a = _took(after[a][0], before[a][0], side)
                # Both took it, or neither did: the two instruments AGREED, and
                # agreement is the thing an SSMT is the absence of.
                if took_a == _took(after[b][0], before[b][0], side):
                    continue
                took, failed = (a, b) if took_a else (b, a)
                events.append(
                    SSMTEvent(
                        degree=degree,
                        prior=prior,
                        quarter=now,
                        side=side,
                        took=took,
                        failed=failed,
                        took_prior=before[took][0],
                        took_now=after[took][0],
                        failed_prior=before[failed][0],
                        failed_now=after[failed][0],
                        took_prior_at=before[took][1],
                        took_now_at=after[took][1],
                        failed_prior_at=before[failed][1],
                        failed_now_at=after[failed][1],
                        knowable_at=now.end,
                    )
                )
                stats[f"side.{side}"] += 1.0
                stats[f"pair:{a}|{b}"] += 1.0

    stats["events"] = float(len(events))
    return events, stats


def _took(now: float, before: float, side: str) -> bool:
    """Whether `now` exceeded the previous quarter's extreme on `side`.

    Strict, both ways: equalling the level is not taking it out.
    """
    return now > before if side == "high" else now < before


def divergences_for(
    events: list[SSMTEvent],
    symbol: str,
    candles: list[Candle] | None = None,
    swing_n: int = 50,
) -> list[SSMTDivergence]:
    """The events that involve `symbol`, positioned on `symbol`'s own price.

    A chart shows one instrument and an SSMT involves two, so only the half that
    belongs to this axis can be drawn. Events where `symbol` is neither side are
    dropped rather than projected: a basket of three produces pairs that do not
    touch the chart at all, and drawing a silver-against-platinum divergence on
    a gold chart would be a line whose every coordinate belongs elsewhere.

    ONE EVENT PER PAIR, deliberately not collapsed. Gold against silver and gold
    against platinum can diverge in the same quarter on the same side, and they
    are two facts. They come back as two segments between the same two extremes
    with different partner tags, which is exactly how the reference charts
    annotate it.

    `candles` are the CHART's own bars and are optional. When given, each
    divergence is stamped with where its own extreme sat in the dealing range
    knowable at the bar it printed on - the premium/discount reading a
    practitioner named as the thing that decides whether a divergence is
    tradeable at all, or is instead evidence about where the draw is. Without
    them the field is None and nothing else changes, so a caller that only wants
    geometry pays nothing.

    The range is read at `time_to`, the bar of the extreme this divergence is
    ABOUT, and not at `knowable_at`. Those differ by up to a whole quarter, and
    the question is where the extreme sat when it printed - reading it at the
    quarter close would answer a different question with a range that had moved.
    """
    times: list[int] = []
    knowable: list[tuple[float | None, float | None]] = []
    if candles:
        times, knowable = range_at(candles, swing_n)

    out: list[SSMTDivergence] = []
    for event in events:
        if symbol == event.took:
            partner, took = event.failed, True
            at_from, price_from = event.took_prior_at, event.took_prior
            at_to, price_to = event.took_now_at, event.took_now
            other_prior, other_now = event.failed_prior, event.failed_now
        elif symbol == event.failed:
            partner, took = event.took, False
            at_from, price_from = event.failed_prior_at, event.failed_prior
            at_to, price_to = event.failed_now_at, event.failed_now
            other_prior, other_now = event.took_prior, event.took_now
        else:
            continue
        out.append(
            SSMTDivergence(
                degree=event.degree,
                side=event.side,
                partner=partner,
                self_took=took,
                time_from=at_from,
                price_from=price_from,
                time_to=at_to,
                price_to=price_to,
                partner_prior=other_prior,
                partner_now=other_now,
                knowable_at=event.knowable_at,
                range_pos=(
                    position_at(price_to, at_to, times, knowable) if times else None
                ),
            )
        )
    return out
