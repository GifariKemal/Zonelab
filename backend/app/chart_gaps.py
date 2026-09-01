"""Price gaps within a trend: breakaway and measuring gaps.

`gaps.py` handles OPENING gaps - the distance across a market close. These are
the classic chart gaps of Edwards and Magee: a bar that opens past the previous
bar's extreme, leaving an unfilled price hole, classified by where it sits in
the move that carries it.

DETECTION IS GEOMETRY, CLASSIFICATION IS DOCTRINE. Finding a gap is arithmetic on
two bars. Calling it breakaway or measuring is a claim about the trend around it,
and no source publishes a measurable rule for "flat" or "mid-trend". This module
states its rules as rules.

AND THE BREAKAWAY BRANCH NEVER FIRES. Measured 1 September 2026 over the full
history of nine instruments, `docs/gap_outcomes.json`: not one breakaway gap, on
any of them. The reason is arithmetic rather than market structure. `flat_atr` is
2,0, and a 20-bar window's total range never gets that small - the minimum ratio
observed across the nine is 2,085 on platinum, and the median sits near 4,7. A
20-bar random walk spreads to roughly four or five times its own mean true range,
so a threshold of 2,0 asks for a window twice as tight as noise. Every gap this
module has ever emitted is therefore classified `measuring`, and the "BK" tag on
the canvas has never been drawn.

The number is NOT retuned here. It is a stated rule and fitting it to the data
that just measured it is the one move this repo does not make. What is fixed is
the silence: the layer's evidence now says the branch is empty, so a reader is
not offered a distinction the engine cannot produce.

MEASURED, and the rest of it is null. Also from `docs/gap_outcomes.json`: the
direction claim (a gap is a continuation object) does not beat the instrument's
own drift, t=-0,56 clustered against a Bonferroni bar of 2,73; and the measuring
projection below is not reached more often than the same bracket one horizon
earlier, t=-1,16. What DOES separate is the band being reached sooner than the
equidistant level on the other side, -2,70 bars at t=-3,65, negative on all nine
instruments - though that control cannot tell a gap apart from any other level
price has recently traded at.

CLASSIFICATION IS NO-LOOKAHEAD. A gap is labelled from the bars BEFORE it only:
a breakaway gap fires when the preceding window is flat and the gap breaks out of
it; a measuring gap fires when the preceding window is already moving in the gap
direction. The classic THIRD kind, the exhaustion gap, is defined by the reversal
that comes AFTER it, so it is deliberately not emitted at the gap bar - an
exhaustion gap is a measuring gap that a later bar proved wrong, and reporting
that needs the later bar.

THE MEASURING PROJECTION. The practitioner rule is that a measuring gap sits at
about the halfway point of a move, so the move's remaining distance equals the
distance already travelled. `target` projects that: for an up gap it is
gap_price + (gap_price - move_start), and the "ratio" of a completed move is the
gap's position in it, which is only knowable once the move has ended.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import Candle

Kind = Literal["breakaway", "measuring"]


@dataclass(frozen=True)
class ChartGap:
    """One price gap and its trend reading.

    `up` True means the next bar's low is above the previous bar's high, i.e. a
    gap up. `top` and `bottom` are the unfilled band's edges, and they are the
    HOLE only: for a gap down that is `prev.low` down to `cur.high`, not
    `prev.high`, which would swallow the whole previous bar's range into the gap
    it is not part of. `at` is the index of the second bar (the one that gapped).
    `move_start` is the price the prior leg began at, used by the measuring
    projection; `target` is that projection, and it is None for a breakaway gap
    because the halfway rule is a claim about a measuring gap only.
    """

    up: bool
    top: float
    bottom: float
    at: int
    kind: Kind
    move_start: float
    target: float | None

    @property
    def knowable_at(self) -> int:
        return self.at


def chart_gaps(
    candles: list[Candle],
    flat_atr: float = 2.0,
    lookback: int = 20,
) -> list[ChartGap]:
    """Every price gap, classified by the trend before it.

    `flat_atr` is the ceiling on the preceding window's height, in units of that
    window's own mean true range, for a gap to count as a breakaway rather than a
    measuring gap. A consolidation oscillates, so its total height is a few
    single-bar ranges; a trend moves, so its height is many. Both are chosen
    numbers, not measured ones. `lookback` is how many bars before the gap define
    its context.

    AT THE SHIPPED 2,0 THE BREAKAWAY BRANCH IS UNREACHABLE on every instrument
    measured, and the header says by how much. A caller who wants the branch to
    fire has to pass a larger `flat_atr` deliberately; nothing in this repo has
    measured which value is right, so none is offered as a default.
    """
    if len(candles) < lookback + 2:
        return []
    out: list[ChartGap] = []
    for i in range(lookback, len(candles)):
        prev = candles[i - 1]
        cur = candles[i]
        up: bool | None = None
        if cur.low > prev.high:
            up = True
        elif cur.high < prev.low:
            up = False
        if up is None:
            continue

        # The preceding window, for the flat/trending test.
        window = candles[i - lookback : i]
        w_high = max(c.high for c in window)
        w_low = min(c.low for c in window)
        window_range = w_high - w_low

        # ATR from the same window, so the flat test is scale-free and uses only
        # bars before the gap. A zero range cannot be scaled, so it is answered
        # as flat rather than guessed.
        atr = _atr(window)
        flat = atr <= 0 or window_range <= flat_atr * atr

        if up:
            broke_out = cur.low > w_high
            kind: Kind = "breakaway" if flat and broke_out else "measuring"
            move_start = w_low
            target = cur.low + (cur.low - move_start)
        else:
            broke_out = cur.high < w_low
            kind = "breakaway" if flat and broke_out else "measuring"
            move_start = w_high
            target = cur.high - (move_start - cur.high)

        # A breakaway gap opens a move, it does not halve one, so the halfway
        # projection is not its claim and is not published for it. Drawn for both
        # kinds until 1 September 2026, which put a fabricated target on every
        # breakaway band on the chart.
        # A breakaway gap opens a move, it does not halve one, so the halfway
        # projection is not its claim and is not published for it. Drawn for both
        # kinds until 1 September 2026, which put a fabricated target on every
        # breakaway band on the chart.
        if kind == "breakaway":
            target = None

        out.append(
            ChartGap(
                up=up,
                top=cur.low if up else prev.low,
                bottom=prev.high if up else cur.high,
                at=i,
                kind=kind,
                move_start=move_start,
                target=target,
            )
        )
    return out


def _atr(candles: list[Candle]) -> float:
    """The mean true range of the given window, a scale for the flat test."""
    if len(candles) < 2:
        return 0.0
    trs = []
    for a, b in zip(candles, candles[1:]):
        trs.append(max(b.high, a.close) - min(b.low, a.close))
    return sum(trs) / len(trs)
