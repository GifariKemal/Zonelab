"""The 3-6-9 dial: digital roots of ring x sector, and where the clock sits now.

WHAT THIS IS, said before anything else, because the name invites a claim the
module cannot make. The digital root of a positive integer is what you get by
summing its digits until one digit remains, and it has a closed form:
`(n - 1) % 9 + 1`. This file builds the 6 x 9 table of `digital_root(r * k)`
for six timeframe rings and nine sectors, and it reports which sector of each
ring the newest bar falls in. It reads the CALENDAR. It never reads a price.

WHY THE "TRIANGLE" IS A TRIANGLE ON FOUR RINGS AND NOT ON TWO. A cell lands in
{3, 6, 9} exactly when 3 divides `r * k`, which happens when 3 divides r or 3
divides k. So:

  - rings 1, 2, 4 and 5 light up at k = 3, 6 and 9, and nowhere else. The same
    three sectors every time, which is the triangle;
  - rings 3 and 6 light up at EVERY sector, because r is already a multiple of
    three. There is no triangle on those two rings; the whole ring qualifies.

That is a fact about multiples of three. It is not a fact about this market, or
about any market, and the renderer draws rings 3 and 6 differently for exactly
that reason - a reader who sees nine lit nodes on one ring and three on another
should be able to see WHY without being told a story about it.

WHAT IT IS FOR. Navigation, and the module is wired so that this is the only
thing it can be. `docs/PRAREGISTRASI-YATIM.md` records pre-registered
directional hypotheses that failed in this project, the most recent being the
OTE band across twelve instruments (Section 10, zero of twelve passed). A
geometric time construct with no measurement behind it does not get to sit on
the decision path on the strength of being pretty. So the dial reaches the
drawing payload and stops there: no detector reads it, no gate consults it, and
`tests/test_vortex.py` asserts that seam by searching the execution modules for
this module's name.

WHAT THE SECTOR ACTUALLY MEANS. Each ring owns one cycle of the New York clock,
taken from `app/quarters.py` rather than re-derived here, and the sector is
which NINTH of that cycle the bar sits in. Nine is the dial's own number and
does not divide four, so a sector is NOT a quarter and must never be read as
one: Q2 of a day cycle spans sectors 3, 4 and part of 5. The quarter ribbon
below the chart is where quarters are read.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import VortexDial, VortexRing
from .quarters import _containing, _cycle

#: Sectors per ring. Nine because the digital root of anything is one of nine
#: values, so a tenth sector would have no cell to sit in.
SECTORS = 9

#: The lit set. Named rather than written inline at the places that test it,
#: because "3, 6, 9" appearing as a literal inside a renderer is how a fourth
#: number gets added by someone who thinks it looks better.
LIT = (3, 6, 9)


@dataclass(frozen=True)
class Ring:
    """One timeframe ring, and which cycle of the NY clock supplies its span."""

    #: The multiplier in `digital_root(r * k)`. Also the draw order, innermost
    #: first, so the fastest cycle is the smallest circle.
    r: int
    id: str
    label: str
    #: Degree in `app/quarters.py` whose cycle this ring spans. Empty for the
    #: calendar quarter, which that module has no degree for - see `span`.
    degree: str


#: Six rings, innermost fastest. This ladder is NOT `quarters.DEGREES`: that one
#: is year/month/week/day/session/micro, this one swaps `micro` for the calendar
#: quarter and so needs the special case in `span` below.
RINGS: tuple[Ring, ...] = (
    Ring(1, "session", "Session", "session"),
    Ring(2, "day", "Daily", "day"),
    Ring(3, "week", "Weekly", "week"),
    Ring(4, "month", "Monthly", "month"),
    Ring(5, "quarter", "Quarterly", ""),
    Ring(6, "year", "Yearly", "year"),
)


def digital_root(n: int) -> int:
    """Recursive digit sum, in closed form.

    Zero maps to zero, which is the one place the closed form needs a guard:
    `(0 - 1) % 9 + 1` is 9, and calling zero nine would light a node under a
    ring that does not exist. A negative cannot arise from this dial - r and k
    are both counted from one - so it is rejected rather than silently folded,
    because a negative arriving here means a caller computed an index wrong and
    the folded answer would look perfectly plausible.
    """
    if n < 0:
        raise ValueError(f"digital root of a negative is undefined here: {n}")
    return 0 if n == 0 else (n - 1) % 9 + 1


def matrix() -> list[list[int]]:
    """The 6 x 9 table, rows in `RINGS` order and columns k = 1..9.

    Sent over the wire on every draw even though it never changes, and that is
    deliberate. `app/layers.py` records what this project already paid for
    hand-copying a backend fact into the frontend: a set of five layer names
    written out twice is how `dfr` came to be registered, panelled, given a
    canvas primitive, and draw nothing at all. Fifty-four small integers is a
    cheaper price than a second copy of the arithmetic.
    """
    return [[digital_root(ring.r * k) for k in range(1, SECTORS + 1)] for ring in RINGS]


def span(ring: Ring, epoch: int) -> tuple[int, int]:
    """Start and end of the cycle `ring` is in at `epoch`, on the NY clock.

    Everything comes from `app/quarters.py`, the two private helpers included,
    because that module already owns every boundary this project uses - the
    18:00 day open, the Sunday-evening week open, the first-Monday month. A
    second implementation of "when does the week start" is a second answer
    waiting to disagree with the ribbon and with the true opens.

    THE CALENDAR QUARTER IS THE ONE SPECIAL CASE. `quarters` has no `quarter`
    degree, but its `year` cycle is already cut at January, April, July and
    October - those edges ARE the calendar quarters - so the containing quarter
    is read off the year cycle instead of being computed a second time.
    """
    if ring.id == "quarter":
        edges, _ = _cycle("year", epoch)
        return _containing(edges, epoch)
    edges, following = _cycle(ring.degree, epoch)
    return edges[0], following


def sector(start: int, end: int, epoch: int) -> int:
    """Which ninth of [`start`, `end`) holds `epoch`, counted from 1.

    Clamped rather than trusted. `_cycle("week", ...)` returns a span running to
    the following Sunday while its four quarters stop on Thursday, so Friday is
    real time inside the span and inside no quarter; the ninths cover the whole
    span, so Friday lands in sector 8 or 9 and nothing has to special-case it. A
    degenerate span cannot come out of `_cycle` today, and returning 1 for one is
    still better than a division that raises in the middle of a draw.
    """
    if end <= start:
        return 1
    k = 1 + (epoch - start) * SECTORS // (end - start)
    return min(SECTORS, max(1, k))


def dial(epoch: int) -> VortexDial:
    """The whole payload for one moment: the table, and six live positions.

    `epoch` is the newest CLOSED bar's time, never the wall clock. The chart
    draws closed bars and the dial has to point at the same instant they do - a
    dial reading `time.time()` would drift ahead of the candles by up to a full
    bar on a slow feed, and on dukascopy that is 59 minutes of the reader being
    shown a sector that no bar on screen belongs to.
    """
    table = matrix()
    rings: list[VortexRing] = []
    for row, ring in enumerate(RINGS):
        start, end = span(ring, epoch)
        k = sector(start, end, epoch)
        rings.append(
            VortexRing(
                r=ring.r,
                id=ring.id,
                label=ring.label,
                sector=k,
                root=table[row][k - 1],
                cycle_start=start,
                cycle_end=end,
            )
        )
    return VortexDial(rings=rings, matrix=table, sectors=SECTORS, lit=list(LIT))
