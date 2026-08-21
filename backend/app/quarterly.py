"""The first two items of the owner's own pre-trade checklist, and nothing else.

His list opens with two questions, and this module answers exactly those two and
stops:

    DFR Consolidation udah terjadi?   -> `defining_range`
    Manipulation sudah?               -> `manipulation_done`

Both are answered as FACTS ABOUT BARS THAT HAVE PRINTED. Nothing here says which
way price will go. Twelve pre-registered directional hypotheses have died in this
project and three of them - H6, H9 and H11 - tested market structure, which is
the very detector this module leans on for its price half. The words a forecast
would need do not appear anywhere in this file, and that is deliberate.

--------------------------------------------------------------------------------
1. THE DEFINING RANGE (DFR)

Take Q1 of any cycle, split it into THIRDS, DISCARD the first third, and take the
highest high and the lowest low of the remaining two thirds. That range is the
DFR. It applies at every degree, and it has no free parameters at all - there is
no length, no multiple, no threshold to tune, so there is nothing here to
overfit. The worked example in the source is the daily cycle, whose Q1 is Asia
18:00 to midnight New York: you keep 20:00 to midnight.

PROVENANCE, said plainly so that nobody later claims something this is not.

  - The thirds rule as implemented here is BUCKO TRADES' rule and is shipped as
    his (youtube.com/@BuckoTrades, "Quarterly Theory: The COMPLETE Course",
    written library at oracleinsights.io), itself a codification of Jevaunie
    Daye's Quarterly Theory.

  - It is NOT a reimplementation of the paid TradingView indicator "Quarterly DFR
    [Dango]" (4,378 boosts). That script is closed source, its own description
    states that its logic is proprietary, and that description invokes momentum,
    volatility and volume - three inputs the thirds rule never touches. This code
    could not be equivalent to it even by accident, and no claim of equivalence
    should ever be made on the strength of the shared name "DFR".

  - VERIFICATION STATUS, and this is the weak link: the thirds rule reached us
    SINGLE-SOURCED, through a summarising fetch, corroborated only by the
    author's own site. That is one voice, twice. It must be verified against the
    course video itself before any number is scored on it. Until then, treat
    every DFR this module draws as provisional.

--------------------------------------------------------------------------------
2. THE CYCLE PROFILE, AMDX VERSUS XAMD

Which quarter does the manipulating depends on the cycle's profile, and the
profile is READ OFF Q1 AFTER Q1 CLOSES:

    Q1 contained inside the previous cycle's Q4 range   ->  AMDX
    Q1 breaks outside that range                        ->  XAMD

    AMDX  ->  the manipulation quarter is Q2
    XAMD  ->  the manipulation quarter is Q3

NOBODY CLAIMS THIS CAN BE PREDICTED BEFORE Q1 CLOSES, and neither does this code.
Ask for the profile of a cycle whose Q1 is still forming and you get None. Not a
guess, not a provisional label, not the previous cycle's answer carried forward.

Two readings inside that rule are OURS and are choices rather than citations:
  - containment is tested on the WHOLE of Q1, high and low, against the whole of
    the previous cycle's Q4. The source says "Q1", so the two-thirds DFR window
    is not used here;
  - a touch is containment. Equal high, or equal low, reads as inside, because
    "breaks outside" describes exceeding a level rather than reaching it.

--------------------------------------------------------------------------------
3. MANIPULATION IS A CONJUNCTION

Neither half alone is manipulation:

    TIME     the cycle is in its manipulation quarter - Q2 under AMDX, Q3 under
             XAMD;
    PRICE    liquidity is taken and rejected INSIDE that quarter, which is
             exactly the existing SWEEP event: a wick beyond a confirmed swing
             whose close did NOT follow.

The price half is `detect.structure.breaks`, imported rather than rewritten. A
second sweep detector would be a second definition, and a chart that disagrees
with its own calibration is how this project has already lost a round.

THE ONE DECISION, LABELLED AS A DECISION AND NOT AS A CITATION. Three candidate
levels appear in the sources for what the sweep has to take, and no source ranks
them:

    IMPLEMENTED     the PREVIOUS QUARTER's extreme - Q1's under AMDX, Q2's under
                    XAMD. Chosen because it keeps this consistent with the way
                    the SSMT anchor is defined in this repo, so the two objects
                    can be read against each other.
    NOT IMPLEMENTED the previous CYCLE's high or low.
    NOT IMPLEMENTED the true open (`quarters.true_opens`).

The SWEEP event brings its own level with it - the confirmed swing that the wick
went past - and that is a different thing from the quarter extreme. Both are
reported: `swing_level` is what the sweep detector fired on, `level` is the
previous quarter's extreme that the same wick also exceeded. Requiring both is
what makes this "the sweep took THAT liquidity" rather than "a sweep happened
nearby".

`direction` is the direction the WICK went. It is a description of a bar that has
closed. It is not a forecast and must not be read as one.

--------------------------------------------------------------------------------
ANTI-LOOKAHEAD, which is the only thing here that can silently turn the whole
module into fiction:

    a DFR      is not knowable until Q1's final two thirds have printed;
    a profile  is not knowable until Q1 closes;
    manipulation is not knowable until the sweep bar closes.

So a DFR and a profile are withheld until the series carries a bar opening at or
after Q1's end - that bar's existence is the proof, readable from the data alone,
that Q1's last bar has closed. A series that stops inside Q1 gets None from both.
`tests/test_quarterly.py` asserts this by truncation rather than by intent: the
answer computed from bars up to the knowable instant must equal the answer
computed from the whole series, and the answer one bar earlier must be None.

NO LEVEL WITHOUT A BAR, the same rule `quarters.true_opens` and `Candle.spread`
follow. A two-thirds window with no bars in it - weekends and holidays make this
common - has no DFR, and None is returned. Nothing is interpolated and nothing is
carried forward from the previous cycle. Absent means absent.

NO INVENTED NUMBERS. The thirds are the source's. The only other constant in this
file is `n`, the fractal width handed to `structure.breaks`, and it is a knob
rather than a doctrine number: no primary source publishes a pivot width, 2 is
`breaks`' own default, and the measurement harness pinned widths rather than
sweeping them for exactly that reason.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from typing import Literal

from .detect.structure import breaks
from .models import Candle
from .quarters import Quarter, quarters


@dataclass(frozen=True)
class DFR:
    """The defining range: the extremes of Q1's final two thirds.

    `start` is where the kept window opens, one third into Q1. `end` is Q1's
    close, and it is also the instant the DFR becomes knowable - the window is
    not over, and the range therefore not final, until then.
    """

    degree: str
    cycle_start: int  # = Q1's start, which is the cycle's start
    start: int  # epoch seconds, inclusive: Q1's start plus one third of Q1
    end: int  # epoch seconds, exclusive: Q1's end
    high: float
    low: float


@dataclass(frozen=True)
class Profile:
    """Which of the two cycle shapes Q1 turned out to be, once Q1 closed.

    `knowable_at` is Q1's end. Before that instant this object does not exist,
    because the profile is read off a closed Q1 and is not predicted.
    """

    degree: str
    cycle_start: int
    name: Literal["AMDX", "XAMD"]
    manipulation: Literal["Q2", "Q3"]  # which quarter does the manipulating
    knowable_at: int  # = Q1's end
    q1_high: float
    q1_low: float
    prev_q4_high: float
    prev_q4_low: float


@dataclass(frozen=True)
class Manipulation:
    """Both halves satisfied: the right quarter, and a sweep inside it.

    Evidence, not a verdict about what follows. `sweep_time` is the open time of
    the bar that swept; the fact is knowable at that bar's CLOSE and not before,
    the same convention `SwingPoint.confirmed_at` uses.
    """

    degree: str
    cycle_start: int
    profile: Literal["AMDX", "XAMD"]
    quarter: Quarter  # the manipulation quarter, Q2 under AMDX or Q3 under XAMD
    swept: Quarter  # the quarter whose extreme was taken, always the one before
    level: float  # that quarter's extreme - the DECISION, see the module docstring
    swing_level: float  # the confirmed swing the SWEEP event itself fired on
    direction: int  # +1 the wick went above, -1 below. Not a forecast.
    sweep_time: int


def _bars(candles: list[Candle], start: int, end: int) -> list[Candle]:
    """Bars whose OPEN time falls in [start, end). Assumes time order, as the feed is."""
    return candles[
        bisect_left(candles, start, key=lambda c: c.time) :
        bisect_left(candles, end, key=lambda c: c.time)
    ]


def _q1_at(degree: str, cycle_start: int) -> Quarter:
    """The Q1 that `cycle_start` opens.

    A ValueError rather than None when it is not a Q1 boundary: that is a caller
    mistake, and None in this module is reserved for "the bars are not there",
    which is a fact about the market and not about the code.
    """
    here = quarters(degree, cycle_start, cycle_start)
    if not here or here[0].label != "Q1" or here[0].start != cycle_start:
        raise ValueError(f"{cycle_start} does not open a {degree} cycle's Q1")
    return here[0]


def _cycle_quarters(degree: str, cycle_start: int) -> dict[str, Quarter]:
    """The four quarters of the cycle that `cycle_start` opens, keyed by label.

    Walked forward and stopped at the NEXT Q1 rather than measured out as four
    equal spans: a cycle's quarters are not all the same length - a DST day has a
    five or seven hour quarter in it - and at the week and month degrees there is
    real time after Q4 that belongs to no quarter at all.
    """
    q1 = _q1_at(degree, cycle_start)
    out: dict[str, Quarter] = {}
    for q in quarters(degree, cycle_start, cycle_start + 8 * (q1.end - q1.start)):
        if q.label == "Q1" and q.start != cycle_start:
            break
        out[q.label] = q
    return out


def _closed(candles: list[Candle], quarter: Quarter) -> bool:
    """Has `quarter` finished, provably, from the bars alone?

    A bar opening at or after its end is the proof: it cannot exist until the
    quarter's last bar has closed. Withholding the answer for one more bar when
    the feed simply stops on the boundary is the conservative direction, and
    conservative is the only safe direction for a knowability test.
    """
    return bool(candles) and candles[-1].time >= quarter.end


def defining_range(
    candles: list[Candle], degree: str, cycle_start: int
) -> DFR | None:
    """Bucko's DFR for one cycle: discard Q1's first third, take the rest.

    None when Q1 has not provably closed, and None when the kept two-thirds
    window holds no bars at all. See the module docstring for the provenance and
    for the verification status, which is single-sourced.
    """
    q1 = _q1_at(degree, cycle_start)
    if not _closed(candles, q1):
        return None

    kept_from = q1.start + (q1.end - q1.start) // 3
    # THE WINDOW'S OWN START MUST BE COVERED, or the extremes are read from a
    # window the data only partly holds - which is the rule this codebase already
    # applies to a period high: a partial high is not the high.
    #
    # This is a REPAINT guard, not tidiness. `_closed` proves Q1 ended; nothing
    # proved it began inside the data. So a band whose kept two-thirds started
    # before the first bar was computed from whatever fraction happened to be in
    # the window, and it MOVED when the window grew backwards. Measured on 20,000
    # hourly bars of gold at day and week degree: three bands changed their high,
    # low and every projection off them when the window was extended leftward.
    # A drawn box that moves because the reader changed one dropdown is the thing
    # a drawing engine exists not to do.
    if candles[0].time > kept_from:
        return None

    kept = _bars(candles, kept_from, q1.end)
    if not kept:
        return None

    return DFR(
        degree=degree,
        cycle_start=q1.start,
        start=kept_from,
        end=q1.end,
        high=max(c.high for c in kept),
        low=min(c.low for c in kept),
    )


def defining_ranges(candles: list[Candle], degree: str) -> list[DFR]:
    """Every cycle's DFR across the bars given, in time order.

    Cycles whose Q1 window is empty, and the last cycle if its Q1 has not closed
    yet, are simply absent from the list. There is no placeholder for them.
    """
    if not candles:
        return []
    return [
        dfr
        for q in quarters(degree, candles[0].time, candles[-1].time)
        if q.label == "Q1"
        and (dfr := defining_range(candles, degree, q.start)) is not None
    ]


def _previous_q4(degree: str, q1: Quarter) -> Quarter | None:
    """The last Q4 that ended at or before this cycle's Q1 opened.

    Found by looking back rather than by stepping back one quarter, because at
    the week degree the previous Q4 is NOT adjacent - Friday sits between it and
    the next cycle and belongs to no quarter at all. Eight Q1-spans is a window
    wide enough for every degree the grid defines.
    """
    span = q1.end - q1.start
    prior = quarters(degree, q1.start - 8 * span, q1.start - 1)
    found = [q for q in prior if q.label == "Q4" and q.end <= q1.start]
    return found[-1] if found else None


def profile(
    candles: list[Candle], degree: str, cycle_start: int
) -> Profile | None:
    """AMDX or XAMD, read off Q1 once Q1 has closed.

    None while Q1 is still forming - the profile is not predictable before then
    and this returns no guess - and None when either Q1 or the previous cycle's
    Q4 has no bars to measure.
    """
    q1 = _q1_at(degree, cycle_start)
    if not _closed(candles, q1):
        return None

    prev = _previous_q4(degree, q1)
    if prev is None:
        return None

    before = _bars(candles, prev.start, prev.end)
    during = _bars(candles, q1.start, q1.end)
    if not before or not during:
        return None

    q4_high, q4_low = max(c.high for c in before), min(c.low for c in before)
    q1_high, q1_low = max(c.high for c in during), min(c.low for c in during)
    inside = q1_high <= q4_high and q1_low >= q4_low

    return Profile(
        degree=degree,
        cycle_start=q1.start,
        name="AMDX" if inside else "XAMD",
        manipulation="Q2" if inside else "Q3",
        knowable_at=q1.end,
        q1_high=q1_high,
        q1_low=q1_low,
        prev_q4_high=q4_high,
        prev_q4_low=q4_low,
    )


def manipulation_done(
    candles: list[Candle], degree: str, cycle_start: int, n: int = 2
) -> Manipulation | None:
    """Both halves, or nothing: the manipulation quarter AND a sweep inside it.

    The first qualifying sweep is the one reported, because the question being
    answered is "manipulation sudah?" and the first one settles it.

    None means one of the halves is missing, and the caller cannot tell which
    from the return value alone - ask `profile` for the time half. `n` is the
    fractal width handed to `structure.breaks`; it is a knob, not a number from
    any source. `breaks` re-walks the whole series, so calling this once per
    cycle over a long history is linear per call.
    """
    shape = profile(candles, degree, cycle_start)
    if shape is None:
        return None

    cycle = _cycle_quarters(degree, cycle_start)
    window = cycle.get(shape.manipulation)
    swept = cycle.get("Q1" if shape.manipulation == "Q2" else "Q2")
    if window is None or swept is None:
        return None

    before = _bars(candles, swept.start, swept.end)
    if not before:
        return None
    high, low = max(c.high for c in before), min(c.low for c in before)

    events, _ = breaks(candles, n, n)
    for event in events:
        if event.kind != "SWEEP" or not (
            window.start <= event.time < window.end
        ):
            continue
        bar = candles[event.index]
        took = bar.high > high if event.direction == 1 else bar.low < low
        if took:
            return Manipulation(
                degree=degree,
                cycle_start=cycle_start,
                profile=shape.name,
                quarter=window,
                swept=swept,
                level=high if event.direction == 1 else low,
                swing_level=event.level,
                direction=event.direction,
                sweep_time=event.time,
            )
    return None
