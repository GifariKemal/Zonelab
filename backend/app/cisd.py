"""Change In State Of Delivery: a close beyond the open that started the last
opposing run.

WHAT IT IS
A delivery run is the consecutive stretch of candles delivering one way -
down-close candles for a sell run, up-close candles for a buy run, where a
candle's delivery is the sign of `close - open`. The level a run leaves behind
is the OPEN OF ITS FIRST CANDLE. A bullish CISD is a candle whose body closes
ABOVE the open of the first candle of the last down-run; a bearish CISD is the
mirror. That is the whole construct.

The single most common way this is coded wrong is to anchor on the LAST candle
of the run instead of the first. In a three-candle down-run the last candle's
open is the deepest one, so the wrong anchor produces a level price reaches
several bars sooner and a CISD count several times larger. `delivery_runs`
therefore stores `start` and `open_price` together and the test suite asserts
the two-way difference directly.

THE THING TO BE SUSPICIOUS OF: THIS IS THE FIRST DETECTOR HERE KEYED TO AN OPEN
Every other detector in this repo reads highs, lows and closes. Order blocks,
fair value gaps, sweeps and breaks in `detect/structure.py` all key off the
extremes. Nothing before this module has depended on a candle's OPENING price,
and the open is the field most likely to differ between two providers for the
same instrument and the same minute: a feed that stitches sessions, fills a
quiet minute, or reconstructs bars from ticks will agree with its peers on where
price got to and disagree about where the bar began. So this construct is only
as trustworthy as the feed's opens, and this repo has never before had to care.

That was measured rather than asserted, and the result was NOT the one expected.
On the 495 shared 15m timestamps in the two XAUUSD series already cached here,
Dukascopy against Yahoo:

    sign(close - open), the input THIS module keys on   3.84% disagree
    sign(high[i] - high[i-1]), what other detectors use 3.04% disagree
    sign(low[i] - low[i-1])                             4.45% disagree
    sign(close[i] - close[i-1])                         3.44% disagree

Opens are not measurably worse than extremes on that pair, so the fear stated
above is unconfirmed. Two caveats make it a bound rather than a clean answer,
and both are why the number is reported instead of believed: the two series are
DIFFERENT INSTRUMENTS - Dukascopy XAUUSD is spot, Yahoo XAUUSD is the COMEX
future, per tools/history.py - and the Yahoo 15m series has session gaps the
Dukascopy one does not. A same-instrument comparison was not possible on this
machine, where Binance and Dukascopy both time out and Yahoo is the only live
provider.

What the number does NOT excuse is the AMPLIFICATION, and that was measured too,
because it is the part that actually decides whether this construct is portable.
A run is a stretch of same-signed bodies, so one bar whose sign flips between
feeds does not move a level slightly - it splits one run into two or merges two
into one, and the anchor open jumps to a different bar entirely. Running `cisds`
on the two feeds over the same 495 timestamps:

    tolerance   runs         CISDs        same bar   Jaccard   same anchor bar
    0           237 / 232    59 / 59      49         0.710     47 of 49
    1            92 /  98    47 / 46      38         0.691     31 of 38

A 3.8% per-bar disagreement about delivery direction becomes a 29% disagreement
about which bars are CISDs - roughly eightfold. When the two feeds do agree on
the bar they almost always agree on the anchor (47 of 49 at the default), so the
failure mode is a whole event appearing on one feed and not the other, not a
level drifting. The median level difference on the shared bars is 59 price units,
which is the spot-versus-future basis rather than any disagreement, and is the
clearest evidence that these are two instruments and this is an upper bound.

The reproduction is four lines against `.cache/dukascopy-XAUUSD-15m-5000.npz` and
`.cache/yahoo-XAUUSD-15m-500.npz`; it is not a test, because a test that reads
the calibration cache fails on a clean checkout.

DECISIONS THE SOURCE MATERIAL LEAVES OPEN, made here in the open
1. BODY CLOSE, NOT WICK. A CISD requires the CLOSE to be beyond the level. A
   wick through that closes back inside is nothing here. This matters for anyone
   comparing against a third-party Pine port: several published ones test the
   high or the low against the level, which fires earlier and more often, so
   identical data will give a different count and neither is a bug.
2. WHAT ENDS A RUN. `interrupt_tolerance` is the number of CONSECUTIVE opposing
   candles a run absorbs as noise without ending. The default 0 is the literal
   reading of "consecutive" - one opposing close ends the run - and it was
   CHOSEN, not measured. The count of CISDs is not stable under this parameter:
   raising it merges runs, moves anchors to earlier and further-away opens, and
   both the number and the LEVELS change. A test asserts that change rather than
   describing it.
3. MINIMUM RUN LENGTH. `min_run` defaults to 2. A one-candle run makes a level
   out of nearly every bar's open and a CISD out of nearly every bar after it,
   which is why a floor exists at all. 2 is the smallest floor that excludes
   that degenerate case; it was CHOSEN, not measured, and no run length has been
   shown here to work better than another.
   A candle with `close == open` delivers in neither direction and so counts as
   non-conforming, which means a flat series yields no runs at all rather than
   runs of length zero.

ANTI-LOOKAHEAD
A CISD is knowable at the CLOSE of the candle that breaks the level, and not one
bar sooner. Two facts have to be in hand at that bar: that the run is OVER, and
that this close is beyond its opening price. Both are properties of bars that
have already printed, so `DeliveryRun.confirmed_at` is the index of the bar at
which the run's end became knowable - with tolerance 0 that is the first
opposing candle, which may itself be the CISD bar, and with tolerance k it is
the (k+1)-th consecutive opposing candle. `cisds` runs one forward pass that at
bar `i` may only see runs whose `confirmed_at` is at or before `i`, exactly as
`detect/structure.walk_breaks` may only see swings already confirmed. This repo
has caught lookahead in its own detectors before, which is why a test asserts
the property by re-running on truncated series instead of trusting the loop.

NO DIRECTION CLAIM
CISD is popularly sold as an entry trigger. This module reports that a level was
closed through and reports nothing else. Twelve pre-registered directional
hypotheses have failed in this project and market structure specifically failed
three times (H6, H9, H11 - see docs/CALIBRATION.md), and no published measured
hit rate for CISD exists to compare against. Its predictive value here is
therefore UNMEASURED. Nothing in this file is a forecast.

OUT OF SCOPE
`tCISD`, the time-based variant in the same doctrine, is not built here and is
not approximated by anything here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Candle


@dataclass(frozen=True)
class DeliveryRun:
    """A stretch of same-delivering candles, and the bar it became knowable at.

    `open_price` is the open of candle `start` - the FIRST candle - which is the
    whole point of the construct and the field a naive port gets wrong.
    """

    start: int  # index of the first candle; the one whose open is the level
    end: int  # index of the last conforming candle, inclusive
    direction: int  # +1 up-closes (buy run), -1 down-closes (sell run)
    open_price: float
    confirmed_at: int  # bar index at which the run's end became knowable
    length: int  # conforming candles only, so absorbed interruptions do not count


@dataclass(frozen=True)
class CISD:
    """A body close beyond the opening price of the last opposing run."""

    index: int  # the bar that closed beyond, and the bar it is knowable at
    time: int
    direction: int  # +1 closed above a down-run's open, -1 below an up-run's
    level: float  # the open of the run's FIRST candle
    run_start: int
    run_end: int
    run_length: int


def delivery_runs(
    candles: list[Candle], interrupt_tolerance: int = 0
) -> list[DeliveryRun]:
    """Non-overlapping delivery runs, each stamped with when its end was known.

    One forward pass. A run starts at the first candle that delivers either way,
    takes that candle's direction, and extends while no more than
    `interrupt_tolerance` CONSECUTIVE non-conforming candles appear. `end` is
    always the last CONFORMING candle, so an absorbed interruption never becomes
    the run's tail, and scanning resumes at `end + 1` so runs never overlap.

    A run still open at the last candle is NOT returned. Its end is not knowable
    yet, so it cannot anchor anything, and emitting it would put an unconfirmed
    object in the same list as confirmed ones.
    """
    out: list[DeliveryRun] = []
    n = len(candles)
    i = 0
    while i < n:
        direction = _delivery(candles[i])
        if direction == 0:
            i += 1
            continue

        start = i
        end = i
        length = 1
        opposing = 0
        j = i + 1
        confirmed_at = -1
        while j < n:
            if _delivery(candles[j]) == direction:
                end = j
                length += 1
                opposing = 0
            else:
                opposing += 1
                if opposing > interrupt_tolerance:
                    confirmed_at = j
                    break
            j += 1

        # ponytail: an in-progress run at the tail is dropped rather than
        # emitted with confirmed_at=None. Nothing can anchor to it, so the only
        # caller it would serve is a chart wanting to draw the forming run; add
        # the nullable field when a chart actually asks.
        if confirmed_at >= 0:
            out.append(
                DeliveryRun(
                    start, end, direction, candles[start].open, confirmed_at, length
                )
            )
        i = end + 1
    return out


def cisds(
    candles: list[Candle], min_run: int = 2, interrupt_tolerance: int = 0
) -> tuple[list[CISD], list[DeliveryRun]]:
    """Walk the bars once, emitting a CISD each time one closes beyond a level.

    Shaped after `detect/structure.walk_breaks` deliberately, so the two can be
    read side by side: the most recent CONFIRMED run on each side is held live,
    a level can only be taken once, and bar `i` sees nothing that was not
    knowable at `i`.

    See the module docstring for what `min_run` and `interrupt_tolerance` do and
    for the fact that both defaults were chosen rather than measured.

    The returned run list is UNFILTERED - `min_run` decides which runs may arm a
    level, not which runs existed. A caller drawing the runs and a caller
    counting the CISDs would otherwise be looking at two different populations,
    which is the mismatch `detect/structure.overlay` avoids by emitting a break
    alongside the MSS carved out of it.
    """
    runs = delivery_runs(candles, interrupt_tolerance)
    by_confirm: dict[int, list[DeliveryRun]] = {}
    for run in runs:
        if run.length >= min_run:
            by_confirm.setdefault(run.confirmed_at, []).append(run)

    live_down: DeliveryRun | None = None
    live_up: DeliveryRun | None = None
    out: list[CISD] = []

    for i, candle in enumerate(candles):
        for run in by_confirm.get(i, ()):
            if run.direction < 0:
                live_down = run
            else:
                live_up = run

        # The close, never the wick. Up is evaluated before down so a bar that
        # closes beyond BOTH live levels emits both rather than one silently
        # swallowing the other - the same stated choice `walk_breaks` makes for
        # an outside bar, and no source addresses the case.
        if live_down is not None and candle.close > live_down.open_price:
            out.append(_event(i, candle.time, 1, live_down))
            live_down = None
        if live_up is not None and candle.close < live_up.open_price:
            out.append(_event(i, candle.time, -1, live_up))
            live_up = None

    return out, runs


def _delivery(candle: Candle) -> int:
    """+1 an up-close, -1 a down-close, 0 neither.

    `close == open` delivers nothing, so it is non-conforming rather than
    silently counted as a continuation. That is what makes a flat series produce
    no runs instead of runs nobody could anchor to.
    """
    if candle.close > candle.open:
        return 1
    if candle.close < candle.open:
        return -1
    return 0


def _event(index: int, time: int, direction: int, run: DeliveryRun) -> CISD:
    return CISD(
        index=index,
        time=time,
        direction=direction,
        level=run.open_price,
        run_start=run.start,
        run_end=run.end,
        run_length=run.length,
    )
