"""What every layer said at ONE bar, as flat values a measurement can group by.

THE PROBLEM THIS SOLVES. Layer state has only ever been reachable through
`/api/draw`, which is async, fetches from a provider and answers for the LAST bar
of a window. A conditioning study needs the state at the bar a trade was entered
on, for nine hundred trades, without nine hundred HTTP calls - and it needs the
state as scalars, because "expectancy by day quarter" is a group-by and a nested
object cannot be grouped.

EVERY FIELD IS KNOWABLE AT `index` AND NOT ONE BAR LATER. The slice is taken
once, at the top, and every reader below sees only `candles[: index + 1]`. That
is the whole anti-lookahead argument and it is one line rather than a promise
repeated at each call site. A study that conditions on a value the trader could
not have had is not a study, it is the answer read off the back of the paper.

WHAT IS NOT HERE, AND WHY. Cross-instrument state - SSMT, the partner
correlations - needs a second series fetched at the same grid, which is a
provider call and turns this from arithmetic into IO. It belongs in the study
that wants it, passed in, not smuggled in here where every caller pays for it.

NOTHING HERE IS SCORED. No field is weighted, combined or ranked. Twelve
directional hypotheses have failed in this project and a thirteenth built by
summing these columns would fail the same way; the point of the flat shape is
that each column can be measured on its own and reported on its own.
"""

from __future__ import annotations

import datetime

from .bias import DEGREES as BIAS_DEGREES, alignment
from .dealing_range import DISCOUNT_TO, PREMIUM_FROM, position_at, range_at
from .models import Candle
from .quarterly import defining_range, manipulation_done, profile
from .quarters import quarters
from .resample import resample

#: Degrees the bias reading is taken at, and it is `bias.DEGREES` itself rather
#: than a list of the same strings. `alignment` reads exactly that tuple, so a
#: local copy would drift the day a degree is added and this module would silently
#: stop reporting it.


def _cycle_start(degree: str, since: int, at: int) -> int | None:
    """The start of the cycle containing `at`, which is its own Q1's start.

    A cycle is four quarters, so the newest Q1 at or before `at` opens the cycle
    `at` sits inside. The grid has to be asked for a WINDOW rather than for the
    instant: a single instant inside Q3 returns Q3 and no Q1, which read as "this
    bar is in no cycle" and silently emptied every quarterly column on the first
    run of this module. `app/checklist.py` asks the same way, from the window's
    first bar.
    """
    grid = quarters(degree, since, at)
    q1s = [q for q in grid if q.label == "Q1" and q.start <= at]
    return q1s[-1].start if q1s else None


def _quarter_label(degree: str, at: int) -> str | None:
    for quarter in quarters(degree, at, at):
        if quarter.start <= at <= quarter.end:
            return quarter.label
    return None


def _band(position: float | None) -> str | None:
    """Premium, discount or equilibrium, on the boundaries `dealing_range` owns.

    THE SATURATED READINGS GET THEIR OWN NAMES, and that is the point of this
    function existing at all. `position_at` CLIPS to 0..1, so a price that has
    left the range entirely comes back as exactly 1.0 or exactly 0.0 - which is
    indistinguishable from "at the high" if you only compare against 0.75. Folded
    into `premium`, that hid a real finding on 2026-08-21: 40 of 40 SSMT
    divergences read premium, and the reason was not that all forty sat in the
    top quartile of a live range, it was that price was 2.19 to 6.22 range
    heights ABOVE the frame and every reading had pinned to its ceiling.
    """
    if position is None:
        return None
    if position >= 1.0:
        return "at_or_above_high"
    if position <= 0.0:
        return "at_or_below_low"
    if position >= PREMIUM_FROM:
        return "premium"
    if position <= DISCOUNT_TO:
        return "discount"
    return "equilibrium"


def at_bar(
    candles: list[Candle],
    index: int,
    interval: str,
    degree: str = "day",
) -> dict[str, object]:
    """Flat layer state at `candles[index]`, using no bar after it.

    `None` in any field means NOT KNOWABLE HERE - the grid has no cycle for this
    bar, the window is too short to aggregate, the range has not formed. It never
    means neutral, and a study that treats the two the same will report a finding
    about its own warm-up.
    """
    if not candles or not 0 <= index < len(candles):
        return {}
    past = candles[: index + 1]
    bar = past[-1]
    when = datetime.datetime.fromtimestamp(bar.time, datetime.UTC)

    out: dict[str, object] = {
        "at": bar.time,
        "index": index,
        "weekday": when.weekday(),
        "hour_utc": when.hour,
        "close": bar.close,
    }

    # ------------------------------------------------------------ quarterly
    out[f"quarter_{degree}"] = _quarter_label(degree, bar.time)
    out["quarter_session"] = _quarter_label("session", bar.time)
    cycle = _cycle_start(degree, past[0].time, bar.time)
    out["cycle_start"] = cycle

    if cycle is None:
        out["amd_profile"] = None
        out["in_manipulation_quarter"] = None
        out["manipulation_done"] = None
        out["dfr_pos"] = None
    else:
        read = profile(past, degree, cycle)
        out["amd_profile"] = read.name if read else None
        # The profile names WHICH quarter manipulates - Q2 under AMDX, Q3 under
        # XAMD - so being in it is a different fact from the manipulation having
        # happened, and the two are separate columns because the source treats
        # them as a conjunction.
        out["in_manipulation_quarter"] = (
            None if read is None else out[f"quarter_{degree}"] == read.manipulation
        )
        done = manipulation_done(past, degree, cycle)
        out["manipulation_done"] = None if read is None else done is not None

        dfr = defining_range(past, degree, cycle)
        if dfr is None or dfr.high <= dfr.low:
            out["dfr_pos"] = None
        else:
            out["dfr_pos"] = round((bar.close - dfr.low) / (dfr.high - dfr.low), 4)

    # -------------------------------------------------- premium / discount
    times, knowable = range_at(past)
    # `at` is a bar TIME, not an index. Passing the index put every lookup before
    # the start of the series and returned None for the whole column.
    position = position_at(bar.close, bar.time, times, knowable)
    out["range_pos"] = None if position is None else round(position, 4)
    out["range_band"] = _band(position)

    # ------------------------------------------------------------ structure
    # PER DEGREE ONLY. `alignment` also reports `aligned` and `direction`, and
    # both are structurally unavailable here: they require ALL FOUR degrees to
    # agree, and 15m cannot be built from an hourly series - aggregation only
    # goes upward. Shipping them anyway gave two columns that read `False` and
    # `None` on 300 consecutive bars, which is a constant wearing the costume of
    # a variable. A caller that has the 15m bars can call `alignment` itself.
    series = {interval: past} if interval in BIAS_DEGREES else {}
    for target in BIAS_DEGREES:
        if target == interval:
            continue
        rows = resample(past, target, interval)
        if rows:
            series[target] = rows
    for target in BIAS_DEGREES:
        out[f"bias_{target}"] = None
    if series:
        for reading in alignment(series).degrees:
            out[f"bias_{reading.timeframe}"] = reading.bias

    return out
