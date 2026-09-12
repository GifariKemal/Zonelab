"""SMT Fill: one instrument returns into its gap, a correlated one does not.

The fourth crack in correlation this project carries, beside SSMT, PSP and the
SMT of `ssmt.smt`. The rule, from the A-Z guide chapter 07:

  Two or more closely correlated assets print a fair value gap AT THE SAME BAR.
  Once the gaps exist, watch how far each instrument trades back into ITS OWN
  gap. Three ways they can diverge:

    entered  one trades back inside its gap at all, the other never does
    half     both enter, but one passes the 50% mark of its gap and the other
             stays above it
    full     both enter, one fills its gap completely and the other does not

  All three are "the gap is holding on the instrument that did not fill it".

WHY THE GAP DEFINITION IS IMPORTED RATHER THAN WRITTEN HERE. `detect.imbalance`
already owns the only definition of a fair value gap in this codebase, and its
own docstring says why: two copies of the comparison is how two answers about
what a gap is eventually disagree. This module asks a different question of the
same object, so it takes the object.

NO PARAMETER, ANYWHERE. There is no minimum gap size, no lookahead cap and no
threshold on the depth difference. The source is explicit that size does not
matter ("If the gap is very small - still valid"), and the three variants are
defined by 0, 0.5 and 1.0, which are the gap's own geometry rather than tuning.
A knob added here would be a knob nobody in the source asked for.

MEASURED NOWHERE YET. Nothing in this module is gated on, drawn heavier, or
scored. It produces events; whether those events separate outcomes is a
different question and belongs in a pre-registered study, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Literal

import numpy as np

from .detect.imbalance import _gap
from .models import Candle

Variant = Literal["entered", "half", "full"]

#: The three depths that define the variants, in the order they can fire, and
#: WHETHER THE DEEP SIDE MUST BEAT THE LEVEL OR ONLY REACH IT.
#:
#: That third column is not decoration, it is a bug fix. `depth` is clamped at
#: 1.0 - a bar that blows clean through a gap reports filled, not more than
#: filled - so a uniform rule of "deep side strictly above the level" makes the
#: `full` variant unreachable. It shipped that way for one live request and the
#: symptom was a clean zero: 17 entered, 23 half, 0 full, on a window where gaps
#: are filled through all the time. A variant that can never fire is worse than
#: a missing one, because the zero reads as a measurement.
_THRESHOLDS: tuple[tuple[Variant, float, bool], ...] = (
    ("entered", 0.0, True),  # touched at all against never touched
    ("half", 0.5, True),  # past the midpoint against not past it
    ("full", 1.0, False),  # filled through against not filled through
)


@dataclass(frozen=True)
class Gap:
    """One instrument's fair value gap, and where it sits.

    `at` is the MIDDLE bar of the three, which is the bar the gap is centred on;
    `knowable_at` is the third bar's time, because a gap is not a gap until the
    bar that completes it has printed. Everything downstream starts after that.
    """

    symbol: str
    at: int  # middle bar's time
    knowable_at: int  # third bar's time
    direction: int  # +1 the gap is above the first bar, -1 below
    top: float
    bottom: float

    @property
    def height(self) -> float:
        return self.top - self.bottom

    def depth(self, high: float, low: float) -> float:
        """How far into the gap a bar reached, 0 untouched to 1 filled through.

        A bullish gap is entered from ABOVE, so depth grows as price falls into
        it; a bearish gap from below. Clamped at both ends: a bar that blows
        clean through reports 1.0 rather than 1.4, because "filled" has no
        degrees past complete.
        """
        span = self.height
        if span <= 0:
            return 0.0
        reach = (self.top - low) if self.direction == 1 else (high - self.bottom)
        return max(0.0, min(1.0, reach / span))


@dataclass(frozen=True)
class FillEvent:
    """One instrument went further into its gap than a correlated one did.

    Carries both depths so the reading can be redone by hand from the event
    alone, and both gaps so it can be drawn on either instrument's chart.
    """

    variant: Variant
    at: int  # the bar the divergence became readable on
    knowable_at: int  # that bar's close - the only time anything may gate on
    direction: int  # +1 both gaps were bullish, -1 both bearish
    gap_at: int  # the bar the pair of gaps formed on
    filled: str  # the instrument that went deeper
    held: str  # the instrument that did not
    filled_depth: float  # 0..1
    held_depth: float  # 0..1
    filled_gap: Gap
    held_gap: Gap


def gaps_for(candles: list[Candle], symbol: str) -> list[Gap]:
    """Every fair value gap in one series, by the project's own definition."""
    n = len(candles)
    if n < 3:
        return []
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    out: list[Gap] = []
    for i in range(1, n - 1):
        direction = _gap(high, low, i)
        if direction == 0:
            continue
        top, bottom = (
            (float(low[i + 1]), float(high[i - 1]))
            if direction == 1
            else (float(low[i - 1]), float(high[i + 1]))
        )
        out.append(
            Gap(
                symbol=symbol,
                at=candles[i].time,
                knowable_at=candles[i + 1].time,
                direction=direction,
                top=top,
                bottom=bottom,
            )
        )
    return out


def fills(
    series: dict[str, list[Candle]]
) -> tuple[list[FillEvent], dict[str, float]]:
    """Every SMT fill across every pair in an ALIGNED basket.

    `series` must be aligned - same bar times, same order, for every symbol -
    which is what `aligned.load_aligned` returns. Raises ValueError otherwise,
    for the same reason `ssmt.ssmt` does: a comparison between two instruments
    on two different grids is not a comparison.

    ONE FORWARD PASS. Gaps are opened as their third bar prints and retired once
    every instrument holding one has filled it completely, so nothing is
    re-walked and nothing can read a bar before it exists.

    ponytail: the open-gap set is scanned per bar, so this is O(bars x open
    gaps). On the windows this app draws that is nothing; if it is ever pointed
    at 50,000 bars with hundreds of simultaneously open gaps, bucket the open
    set by price before scanning it.
    """
    stats: dict[str, float] = {
        "bars": 0.0,
        "gaps": 0.0,
        "simultaneous": 0.0,
        "events": 0.0,
        "variant.entered": 0.0,
        "variant.half": 0.0,
        "variant.full": 0.0,
    }
    symbols = list(series)
    if len(symbols) < 2:
        raise ValueError("an SMT fill needs at least two instruments")

    times = [c.time for c in series[symbols[0]]]
    for symbol in symbols[1:]:
        other = [c.time for c in series[symbol]]
        if other != times:
            raise ValueError(
                f"{symbol} is not on the same grid as {symbols[0]}: "
                f"{len(other)} bars against {len(times)}. Align them first "
                "(app.aligned.load_aligned)."
            )
    stats["bars"] = float(len(times))
    if not times:
        return [], stats

    #: Gaps that formed on the SAME BAR in the SAME DIRECTION, keyed by that bar.
    #: A gap one instrument printed alone is not part of this question - the
    #: source requires the gap to exist on both before the fill can diverge.
    by_bar: dict[tuple[int, int], dict[str, Gap]] = {}
    for symbol in symbols:
        found = gaps_for(series[symbol], symbol)
        stats["gaps"] += float(len(found))
        for gap in found:
            by_bar.setdefault((gap.at, gap.direction), {})[symbol] = gap
    shared = {key: row for key, row in by_bar.items() if len(row) >= 2}
    stats["simultaneous"] = float(len(shared))
    if not shared:
        return [], stats

    #: open gap sets, and which variants each PAIR has already reported. A pair
    #: reports each variant at most once, because the first crossing is the
    #: event and every bar after it is the same fact restated.
    watching: list[dict] = [
        {
            "gap_at": at,
            "direction": direction,
            "row": row,
            "depth": {s: 0.0 for s in row},
            "fired": {pair: set() for pair in combinations(sorted(row), 2)},
        }
        for (at, direction), row in sorted(shared.items())
    ]

    index = {t: i for i, t in enumerate(times)}
    events: list[FillEvent] = []
    live: list[dict] = []
    pending = list(watching)

    for bar_i, now in enumerate(times):
        # Gaps become watchable at their THIRD bar, never before it.
        while pending and index[pending[0]["row"][
            next(iter(pending[0]["row"]))
        ].knowable_at] <= bar_i:
            live.append(pending.pop(0))

        if not live:
            continue

        still: list[dict] = []
        for watch in live:
            row = watch["row"]
            for symbol, gap in row.items():
                bar = series[symbol][bar_i]
                if bar.time <= gap.knowable_at:
                    continue
                watch["depth"][symbol] = max(
                    watch["depth"][symbol], gap.depth(bar.high, bar.low)
                )
            for a, b in watch["fired"]:
                da, db = watch["depth"][a], watch["depth"][b]
                deeper, shallower = (a, b) if da >= db else (b, a)
                d_deep = max(da, db)
                d_shallow = min(da, db)
                for variant, level, strict in _THRESHOLDS:
                    if variant in watch["fired"][a, b]:
                        continue
                    # The deeper one is past the level and the shallower one is
                    # not - that gap between them IS the divergence. `strict`
                    # says which comparison the deep side gets; see the table.
                    deep_past = d_deep > level if strict else d_deep >= level
                    shallow_short = d_shallow < level if not strict else d_shallow <= level
                    if not (deep_past and shallow_short):
                        continue
                    watch["fired"][a, b].add(variant)
                    events.append(
                        FillEvent(
                            variant=variant,
                            at=now,
                            knowable_at=now,
                            direction=watch["direction"],
                            gap_at=watch["gap_at"],
                            filled=deeper,
                            held=shallower,
                            filled_depth=round(d_deep, 6),
                            held_depth=round(d_shallow, 6),
                            filled_gap=row[deeper],
                            held_gap=row[shallower],
                        )
                    )
                    stats[f"variant.{variant}"] += 1.0
            # Retired once every instrument has filled its own gap through:
            # there is nothing left for either side to diverge about.
            if not all(d >= 1.0 for d in watch["depth"].values()):
                still.append(watch)
        live = still

    events.sort(key=lambda e: (e.at, e.gap_at, e.variant))
    stats["events"] = float(len(events))
    return events, stats


def for_symbol(events: list[FillEvent], symbol: str) -> list[FillEvent]:
    """Only the events one instrument is a party to.

    The same filter `ssmt.divergences_for` applies and for the same reason: a
    divergence between two partners that does not involve the chart's own
    instrument has no gap to draw on the chart being looked at.
    """
    return [e for e in events if symbol in (e.filled, e.held)]


def _selftest() -> None:
    """Hand-built bars whose answer is arithmetic, not incidental."""

    def bar(t: int, o: float, h: float, low: float, c: float) -> Candle:
        return Candle(time=t, open=o, high=h, low=low, close=c, volume=1.0)

    # Three bars making a bullish gap between bar0.high=10 and bar2.low=20, on
    # both instruments at the same bar, then bars that reach into it by
    # different amounts. Gap band is 10..20, so height 10 and depth is
    # (20 - low) / 10.
    def three(times: list[int]) -> list[Candle]:
        return [
            bar(times[0], 5, 10, 5, 9),
            bar(times[1], 11, 30, 11, 29),
            bar(times[2], 21, 25, 20, 24),
        ]

    t = [0, 60, 120, 180, 240, 300]
    a = three(t[:3]) + [
        bar(t[3], 24, 25, 24, 24),  # nowhere near the gap
        bar(t[4], 24, 25, 16, 17),  # depth (20-16)/10 = 0.4
        bar(t[5], 17, 18, 11, 12),  # depth (20-11)/10 = 0.9
    ]
    b = three(t[:3]) + [
        bar(t[3], 24, 25, 24, 24),
        bar(t[4], 24, 25, 24, 24),  # never enters
        bar(t[5], 24, 25, 24, 24),
    ]

    events, stats = fills({"A": a, "B": b})
    # Three gaps in total and only ONE of them simultaneous: A also prints a
    # bearish gap later that B does not, which is the lonely-gap path exercised
    # in passing rather than in a fixture of its own.
    assert stats["gaps"] == 3.0, stats
    assert stats["simultaneous"] == 1.0, stats
    kinds = [e.variant for e in events]
    assert kinds == ["entered", "half"], kinds
    first = events[0]
    assert first.filled == "A" and first.held == "B"
    assert first.filled_depth == 0.4 and first.held_depth == 0.0
    # KNOWABILITY: the event cannot predate the bar that produced it, and that
    # bar cannot predate the gap's own third bar.
    for event in events:
        assert event.knowable_at >= event.filled_gap.knowable_at
        assert event.knowable_at > event.gap_at

    # `half` fires on the bar that crossed 0.5, not on the one that reached 0.4.
    assert events[1].at == t[5] and events[1].filled_depth == 0.9

    # FULL MUST BE REACHABLE, which it was not until 11 September 2026: `depth`
    # clamps at 1.0, so "deep side strictly greater than 1.0" could never be
    # true and the variant reported a clean zero forever. A fills through, B
    # stops at 0.4.
    through = three(t[:3]) + [
        bar(t[3], 24, 25, 24, 24),
        bar(t[4], 24, 25, 16, 17),
        bar(t[5], 17, 18, 5, 6),  # straight through the 10..20 band
    ]
    partial = three(t[:3]) + [
        bar(t[3], 24, 25, 24, 24),
        bar(t[4], 24, 25, 16, 17),  # depth 0.4 and no further
        bar(t[5], 17, 18, 16, 17),
    ]
    full_events, full_stats = fills({"A": through, "B": partial})
    assert full_stats["variant.full"] == 1.0, full_stats
    last = [e for e in full_events if e.variant == "full"][0]
    assert last.filled == "A" and last.filled_depth == 1.0
    assert last.held == "B" and last.held_depth == 0.4

    # BOTH FILLING IS NOT A DIVERGENCE, which is the source's own note: "If both
    # assets fill it, the SSMT is likely failing." Same bars on both sides must
    # produce nothing at all.
    same, same_stats = fills({"A": a, "B": list(a)})
    assert same == [], same
    # Both of A's gaps are now shared, since B is A: two simultaneous pairs and
    # still not one divergence, because identical bars cannot diverge.
    assert same_stats["simultaneous"] == 2.0, same_stats

    # A gap on one instrument alone is not part of the question.
    # bar0's high REACHES the flat bars that follow, so there is no gap on this
    # instrument at all. The first draft used high 10 against a low of 11 and
    # quietly printed a gap at the same bar as A, which made the fixture test
    # the opposite of what it claims.
    lonely = [bar(t[0], 5, 12, 5, 9)] + [bar(x, 11, 12, 11, 11) for x in t[1:]]
    alone, alone_stats = fills({"A": a, "B": lonely})
    assert alone_stats["simultaneous"] == 0.0
    assert alone == []

    # An unaligned basket is refused rather than silently compared.
    try:
        fills({"A": a, "B": b[:-1]})
    except ValueError as exc:
        assert "same grid" in str(exc)
    else:  # pragma: no cover - the raise above is the contract
        raise AssertionError("unaligned series must raise")

    # Depth is clamped: blowing through a gap is filled, not more than filled.
    gap = Gap("A", 0, 60, 1, top=20.0, bottom=10.0)
    assert gap.depth(25.0, 5.0) == 1.0
    assert gap.depth(25.0, 20.0) == 0.0
    assert gap.depth(25.0, 15.0) == 0.5


if __name__ == "__main__":  # pragma: no cover
    _selftest()
    print("smt_fill selftest ok")
