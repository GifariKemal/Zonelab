"""Four degrees of structure, and whether they agree. The owner's rule, run.

WHOSE VIEW THIS IS, AND WHOSE IT IS NOT
Not the engine's. This module executes ONE rule, handed over by the owner of
the account in his own words:

    "Daily - check bearish apa bullish, ada konfirmasi reversal? Kalau ngga
     asumsi continuation; H4 - check bearish juga sejajar sm daily? H1 - sama?
     M15? Sama? Semuanya harus sejajar kalo mau trade continuation."

Read the bias on the Daily; ask whether a reversal was confirmed there and
assume continuation if it was not; then ask whether H4 agrees with the Daily,
whether H1 agrees, whether M15 agrees. All four must line up before he takes a
continuation trade. He trades M15 because he wants to see each session, and
takes H4 as the higher degree the M15 read hangs off.

So the question answered here is "do your four timeframes agree". That is a
fact about his checklist and the report stops there. It is emphatically NOT
this project asserting that agreement precedes a move. Structure is the one
object this doctrine claims carries direction, and that claim was TESTED here
and it failed. H6 took BOS, CHoCH and SWEEP as three separate cohorts and found
nothing. H9 took the sweep-then-MSS conjunction: t = -0.79 and -0.12 on the
primary horizon against a pre-registered bar of 3.0, with the sign REVERSING
between the two halves. H11 took the three-part conjunction the sources
actually describe - sweep, displacement, break - and it failed in all four
configurations. Twelve pre-registered directional hypotheses have failed in this
repo. See docs/CALIBRATION.md and the module docstring of detect/structure.py.

Nothing below has been measured either, and it carries no number that could be
mistaken for a measurement. It reports his answer and the evidence each degree's
answer was read off, so a ticked box can be inspected instead of believed.

THE VOCABULARY IS BORROWED, NOT INVENTED
`detect.structure` already names these events and this module says nothing new:
a BOS is the trend continuing, a CHoCH is the character having changed - which
is exactly the "konfirmasi reversal" he asks for on each degree. A SWEEP is
liquidity being taken rather than structure giving way, so it answers neither
question, and it is skipped here for the same reason `bias_series` skips it.

WHY EACH DEGREE MUST BE FETCHED, AND WHY app/resample.py IS THE WRONG TOOL
`resample` aggregates the bars a chart is already showing, and a chart showing
15m bars cannot be aggregated into a Daily read. 500 fifteen-minute bars is
about five days. That is roughly five daily bars, and five is below the floor
derived next - a single Daily swing would not even have confirmed. Aggregating
anyway produces a Daily "bias" computed from one trading week, which is not a
Daily bias, and nothing downstream could tell the difference. Each degree needs
its OWN fetch at its OWN interval.

That fetching belongs to the caller. This module takes candles and returns a
reading, which is what keeps it testable with no network.

THE MINIMUM BARS PER DEGREE, DERIVED
`min_bars(left, right)` and nothing hard-coded. Two constraints, and the second
is the one that binds:

  1. A pivot at bar `i` needs `left` bars behind it and `right` ahead, so the
     earliest possible pivot sits at `left` and becomes knowable at `left+right`
     (see `structure.swings`). A break is a later bar closing beyond it, so the
     bar at `left+right` must exist: n >= left + right + 1.
  2. `structure.breaks` refuses to run at all below `left + right + 2` bars,
     returning no events. That guard is the code that actually executes, so it
     is the floor this module reports: n >= left + right + 2.

At the default width used here, left = right = 2, that is SIX bars per degree.
Six bars at each degree's own interval:

    1d    6 daily bars     about 8 calendar days of a five-day week
    4h    6 four-hour bars 24 hours
    1h    6 bars           6 hours
    15m   6 bars           90 minutes

Said plainly, because a floor is not a sample: six is the point at which a
break becomes POSSIBLE, not the point at which the bias means much. At the
shipped structure widths the same arithmetic gives 12 bars for internal_n = 5
and 102 for swing_n = 50, and 102 daily bars is about five months of history.
Ask for more bars than the floor at every degree.

WHY "TOO SHORT" IS NOT "NO BIAS YET"
A degree with fewer bars than the floor reads UNKNOWN - `bias is None` - with a
reason, never 0 and never as agreement. A degree with enough bars and no break
yet reads 0, which is `bias_series`'s own value before the first break: there
is nothing there to have a character, let alone to change it. Both fail the
checklist, and they fail it for different reasons that a trader must be able to
tell apart. Neither one ever counts as alignment, because a checklist that
cannot distinguish "I could not look" from "I looked and it is flat" will tick
a box it should not.
"""

from __future__ import annotations

from dataclasses import dataclass

from .detect.structure import bias_series, breaks
from .models import Candle

# Daily first, because his rule starts there and every other degree is checked
# AGAINST the Daily rather than against a majority of the four.
DEGREES = ("1d", "4h", "1h", "15m")


def min_bars(left: int, right: int) -> int:
    """Fewest bars at one degree before a bias can exist there.

    The `structure.breaks` guard, restated rather than copied to a number: see
    the module docstring for why this and not `left + right + 1`.
    """
    return left + right + 2


@dataclass(frozen=True)
class DegreeReading:
    """One timeframe's answer, and what it was read off."""

    timeframe: str
    # -1 bearish, +1 bullish, 0 no break yet, None UNKNOWN (see `reason`).
    bias: int | None
    bars: int
    needs: int
    # The most recent BOS or CHoCH at this degree; None when there has been
    # none. SWEEPs are excluded - liquidity taken is not structure giving way.
    last_break: str | None
    reason: str | None

    @property
    def reversal_confirmed(self) -> bool | None:
        """His "ada konfirmasi reversal?", answered in structure's own words.

        A CHoCH is the confirmation; a BOS is the trend continuing, which is
        the "kalau ngga, asumsi continuation" branch. None when no break has
        happened here, or when the degree is UNKNOWN - there is nothing to
        assume continuation OF.
        """
        return None if self.last_break is None else self.last_break == "CHoCH"


@dataclass(frozen=True)
class AlignmentReport:
    """Whether the four degrees line up, and which ones did not."""

    degrees: tuple[DegreeReading, ...]  # in DEGREES order, Daily first
    aligned: bool
    direction: int | None  # the shared bias when aligned, else None
    disagreeing: tuple[str, ...]  # the degrees that broke it, named


def alignment(
    series: dict[str, list[Candle]], left: int = 2, right: int = 2
) -> AlignmentReport:
    """Read each degree in `series` and report whether all four agree.

    `series` is keyed by timeframe: "1d", "4h", "1h", "15m". A key that is
    missing or empty reads UNKNOWN like any other short series - absent is a
    kind of too-short - and other keys are ignored.

    The Daily is the reference, which is his rule and not a convenience: if the
    Daily has no usable bias the checklist never starts, so the Daily alone is
    named as what broke it rather than the three degrees that had nothing to
    agree with.
    """
    needs = min_bars(left, right)
    degrees = tuple(
        _read(tf, series.get(tf) or [], left, right, needs) for tf in DEGREES
    )

    daily = degrees[0]
    if daily.bias in (-1, 1):
        # UNKNOWN (None) and 0 both fall out here, because neither equals a
        # usable Daily bias. That is the whole guard: no `is not None` test to
        # forget, and silence cannot pass as assent.
        disagreeing = tuple(d.timeframe for d in degrees if d.bias != daily.bias)
    else:
        disagreeing = (daily.timeframe,)

    return AlignmentReport(
        degrees=degrees,
        aligned=not disagreeing,
        direction=daily.bias if not disagreeing else None,
        disagreeing=disagreeing,
    )


def _read(
    tf: str, candles: list[Candle], left: int, right: int, needs: int
) -> DegreeReading:
    if len(candles) < needs:
        return DegreeReading(
            timeframe=tf,
            bias=None,
            bars=len(candles),
            needs=needs,
            last_break=None,
            reason=(
                f"{len(candles)} bars of {tf}, {needs} needed at swing width "
                f"left={left} right={right}. This degree has to be fetched at "
                f"its own interval; aggregating a lower one does not make it."
            ),
        )

    # The bias comes from `bias_series` rather than from the events below, even
    # though the last non-SWEEP event's direction is the same number. It is the
    # function that owns the anti-lookahead rule - bar i sees only breaks
    # already knowable at i - and restating its definition here is how the two
    # would come to disagree. The second pass costs one walk of a short series.
    events, _ = breaks(candles, left, right)
    structural = [e for e in events if e.kind != "SWEEP"]
    return DegreeReading(
        timeframe=tf,
        bias=int(bias_series(candles, left, right)[-1]),
        bars=len(candles),
        needs=needs,
        last_break=structural[-1].kind if structural else None,
        reason=None,
    )
