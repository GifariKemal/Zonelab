"""Labels and bookkeeping over the quarter grid. Not one new price anywhere.

Three items from the owner's own notes live here, and all three are read off
`quarters.py`'s grid rather than off bars. Nothing in this file computes a level,
a range or an extreme; every function here takes a CLOCK instant, and the two
that take candles only count what the clock already said.

================================================================================
1. THE NOMINAL ROLE OF A QUARTER, WHICH IS NOT THE OBSERVED PROFILE

His note: Q1 accumulation, Q2 manipulation, Q3 distribution, Q4 continuation OR
reversal. `nominal_role` answers exactly that, from position alone.

Q4 KEEPS BOTH READINGS. His note gives two words for it and does not say which,
so `role` is a tuple and Q4's has two entries. Collapsing it to one word would be
inventing the half of the note he did not write, and the ambiguity is itself
information about how firm the doctrine is here.

**THIS IS THE TRAP THIS MODULE EXISTS TO PREVENT.** `quarterly.profile` already
answers a DIFFERENT question with the same vocabulary, and the two disagree
systematically:

  `sequence.nominal_role`     NOMINAL. Which quarter this is by POSITION in the
                              cycle, and the word his note attaches to that
                              position. Knowable from the calendar alone, for any
                              instant, past or future, with no bars at all.

  `quarterly.profile`         OBSERVED. Which quarter actually did the
                              manipulating in ONE cycle, read off Q1 after Q1 has
                              closed: Q1 contained in the previous cycle's Q4 is
                              AMDX and manipulates in Q2; Q1 breaking outside it
                              is XAMD and manipulates in Q3. Needs bars, and
                              returns None until Q1 has provably closed.

Under AMDX the two agree that Q2 is the manipulation quarter. **Under XAMD they
disagree by construction**: the nominal role of Q2 is still "manipulation",
because that is what position two is called, while the observed manipulation
quarter is Q3. A caller that reads a nominal role as though it were a profile
therefore gets the wrong quarter on every XAMD cycle and gets no warning at all,
because both answers are the same four strings. `tests/test_sequence.py` asserts
that disagreement directly on an XAMD fixture.

So: a nominal role is a fact about the CLOCK. An observed profile is a fact about
PRICE in one cycle. Ask `quarterly.profile` when you want to know what happened.

================================================================================
2. THE INTRADAY QUARTER-TO-SESSION MAPPING, AND HOW APPROXIMATE IT IS

His note: Q1 Asia, Q2 London, Q3 New York AM, Q4 New York PM. `intraday_session`
attaches those four names to the DAY-degree quarters and to nothing else - the
names are intraday, and a week-degree Q2 is a Tuesday, not London.

THE NAMES ARE NICKNAMES FOR SIX-HOUR BOXES AND ARE NOT THE SESSIONS THIS REPO
ALREADY DRAWS. The day quarters open 18:00, 00:00, 06:00 and 12:00 New York, so:

  Q1  18:00-00:00  called "asia"          `pools.SESSIONS["asia"]`   is 19:00-00:00
  Q2  00:00-06:00  called "london"        `pools.SESSIONS["london"]` is 02:00-05:00
  Q3  06:00-12:00  called "new_york_am"   no killzone defined in this repo
  Q4  12:00-18:00  called "new_york_pm"   no killzone defined in this repo

Answering the question plainly: **no, 00:00-06:00 New York is not what anyone
would call London.** London's cash open is 03:00 New York in the winter and 02:00
in the summer, and this repo's own London killzone is 02:00-05:00 - three hours
sitting INSIDE a six-hour box, sharing neither edge with it. The quarter starts
two hours before the killzone and ends an hour after it. Asia is the same shape:
the killzone starts an hour into Q1.

A quarter box and a session box are therefore DIFFERENT OBJECTS with overlapping
names, and reading a chart that shows both requires knowing which one a statement
was made about. `IntradaySession.killzone` carries this repo's own window beside
the quarter's, taken from `pools.SESSIONS` rather than copied, and `same_window`
is False on every quarter that has one - it has never once been True and is not
expected to be. Nothing here widens, shifts or reconciles the two.

================================================================================
3. QUARTER SEQUENCE CHAINS

He writes the quarter number at each nested degree as a chain - `2-1-3`, `3-3-3`,
`4-1-4` - and labels them on his charts as `222`, `333`, `411`, `441`. `chain`
returns exactly that for a bar time and an ordered list of degrees, outermost
first. It reads the same grid `quarters.py` publishes and computes nothing else.

THE CHAIN IS A FACT ABOUT THE CLOCK. It needs no candles, it is knowable at the
bar it describes and equally at any instant a year from now, and it cannot be
revised by a later bar. That part is safe to draw and safe to quote.

**THE LIST IS NOT.** He keeps ten chains - 111, 114, 141, 144, 222, 333, 411,
414, 441, 444 - and states that the longer the aligned chain the better the
outcome. That is a claim about probability, and **NOBODY HAS MEASURED IT**.
Nothing in this project has compared what price did after a listed chain against
what it did after an unlisted one; the claim reached this module unmeasured and
is shipped unmeasured. Twelve pre-registered directional hypotheses have already
failed here, three of them on market structure, so an unmeasured claim of this
shape is the exact thing this repo does not ship as a filter.

Consequences, all of them load-bearing:

  - the membership flag is called `in_his_list`. It says the chain appears in a
    list he wrote down. It does not say the chain is likely, and there is
    deliberately no field here that ranks or scores anything;

  - **10 of the 64 three-digit chains are listed, which is 15.625%**, and that
    number is `BASE_RATE`. A chain landing in the list is not rare and must never
    be reported as though it were. Quote the base rate whenever the flag is
    quoted - one bar in six is in the list by arithmetic alone;

  - the list is three digits only, so `in_his_list` is **None** for a chain of any
    other length. None means the question has no answer, not False;

  - `occurrences` counts how often each chain actually happens over a supplied
    series. That is the first thing anyone measuring this needs, and it measures
    NO OUTCOME - it counts bars and nothing else. If the listed ten turn out to
    occupy far more or far less than 15.625% of bars, the base rate a later study
    compares against is not 15.625% and finding that out afterwards would invalidate
    it.

CHOSEN IS NOT MEASURED. The four role words, the four session names, the ten
listed chains and the day-degree scope of the session names are all HIS, taken as
written. Not one of them has been tested against anything in this project.

TIME THAT BELONGS TO NO QUARTER produces NOTHING rather than a substitute. Friday
is not a quarter of the week and a fifth week is not a quarter of the month (see
`quarters.py`, where that is doctrine rather than an off-by-one), so a chain that
includes the week degree has no value at all on a Friday, `nominal_role` returns
None there, and `occurrences` counts those bars in `outside` rather than dropping
them. The counts plus `outside` always equal the bars examined.

NO TIMEZONE ARITHMETIC HERE. Every instant comes from `quarters.py` and
`clock.py`. The chain therefore stretches with its parent across a DST transition
for free: on 2025-03-09 the day cycle's Q2 is five real hours and its micro
quarters are 1125 seconds, and a chain read inside it lands on a different digit
than a fixed-offset grid would give.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from . import clock
from .models import Candle
from .pools import SESSIONS as KILLZONES
from .quarters import DEGREES, Quarter, quarters

# His four words. Q4 carries TWO because his own note does, and the pair is kept
# as a pair rather than resolved - see the module docstring.
ROLES: dict[str, tuple[str, ...]] = {
    "Q1": ("accumulation",),
    "Q2": ("manipulation",),
    "Q3": ("distribution",),
    "Q4": ("continuation", "reversal"),
}

# His four session names, for the DAY degree only. Nicknames for six-hour boxes,
# not the killzone windows of the same name - see the module docstring.
INTRADAY_SESSIONS: dict[str, str] = {
    "Q1": "asia",
    "Q2": "london",
    "Q3": "new_york_am",
    "Q4": "new_york_pm",
}

# His ten. A list he wrote down, and nothing in this project has measured whether
# these behave any differently from the other fifty-four.
HIS_LIST: frozenset[str] = frozenset(
    {"111", "114", "141", "144", "222", "333", "411", "414", "441", "444"}
)

# 10 of 64. Quote it whenever `in_his_list` is quoted: a chain being listed is a
# one-in-six event by arithmetic, before any market behaviour is involved.
BASE_RATE = len(HIS_LIST) / 4**3


@dataclass(frozen=True)
class NominalRole:
    """The word his note attaches to a quarter's POSITION, and that quarter.

    NOT `quarterly.Profile`. This is knowable from the calendar with no bars at
    all; the profile is read off a closed Q1 and can name a different quarter as
    the manipulation one. See the module docstring for how they diverge.
    """

    degree: str
    label: Literal["Q1", "Q2", "Q3", "Q4"]
    start: int  # epoch seconds, inclusive - the quarter's own edges
    end: int  # epoch seconds, exclusive
    role: tuple[str, ...]  # two entries on Q4, because his note gives two


@dataclass(frozen=True)
class IntradaySession:
    """A day-degree quarter and the session name his note gives it.

    `killzone` is this repo's own window for that name where one exists, carried
    so the two boxes can be compared instead of confused. `same_window` has never
    been True: the killzone is strictly inside the quarter and shares no edge with
    it.
    """

    label: Literal["Q1", "Q2", "Q3", "Q4"]
    session: str
    start: int  # the QUARTER's window
    end: int
    killzone: tuple[int, int] | None  # `pools.SESSIONS`', when that name has one
    same_window: bool


@dataclass(frozen=True)
class Chain:
    """Which quarter of each nested degree an instant falls in.

    A fact about the clock, knowable at the bar it describes and never revised.
    `in_his_list` says the chain appears in a list he wrote; it says nothing about
    what price does next, and 15.625% of three-digit chains are in that list
    before any market behaviour is involved. None when the chain is not three
    digits, because his list only covers those.
    """

    at: int
    degrees: tuple[str, ...]  # outermost first
    quarters: tuple[int, ...]  # 1..4, one per degree, same order
    text: str  # "2-1-3", the form he writes
    compact: str  # "213", the form he labels charts with
    in_his_list: bool | None


@dataclass(frozen=True)
class Occurrence:
    """How often each chain happened. Counts bars; measures no outcome.

    `counts` plus `outside` always equals `bars`. `listed_share` is measured
    against the bars that HAVE a chain, which is the population `base_rate`
    describes. Both are 0 by construction when `degrees` is not three long, since
    his list only names three-digit chains - that is "not applicable" rather than
    "measured zero", the same way `Chain.in_his_list` is None there.
    """

    degrees: tuple[str, ...]
    bars: int
    outside: int  # bars in time belonging to no quarter at some degree
    counts: dict[str, int]  # compact chain -> bars, descending by count
    listed: int  # bars whose chain is in his list
    listed_share: float
    base_rate: float  # 10/64, what `listed_share` would be if chains were uniform


def _quarter_at(degree: str, at: int) -> Quarter | None:
    """The quarter of `degree` holding `at`, or None when no quarter does.

    `quarters(degree, at, at)` returns the containing quarter and only that one,
    so this is a lookup rather than a search. Empty is a real answer: Friday at
    the week degree and a fifth week at the month degree are in no quarter.
    """
    here = quarters(degree, at, at)
    return here[0] if here else None


def _ordered(degrees: Sequence[str]) -> tuple[str, ...]:
    """Validate the degrees are known and nest outermost-first, or raise.

    Read off `quarters.DEGREES` at call time rather than against a list spelled
    here, so a degree added to the grid works with no edit to this file.

    The order is not decoration: a chain's whole meaning is "the quarter of each
    successively finer degree", and a caller who hands them over reversed gets a
    string that reads like a chain and means the opposite nesting.
    """
    if not degrees:
        raise ValueError("a chain needs at least one degree")
    for degree in degrees:
        if degree not in DEGREES:
            raise ValueError(f"unknown degree {degree!r}, expected one of {DEGREES}")
    order = [DEGREES.index(d) for d in degrees]
    if any(b <= a for a, b in zip(order, order[1:])):
        raise ValueError(
            f"degrees must nest outermost-first, {tuple(degrees)} does not: "
            f"the grid's order is {DEGREES}"
        )
    return tuple(degrees)


def nominal_role(degree: str, at: int) -> NominalRole | None:
    """The role his note gives this quarter BY POSITION. Not the observed profile.

    Knowable from the clock alone - no candles are taken and none are needed -
    which is exactly what separates it from `quarterly.profile`, which needs bars
    and withholds its answer until Q1 has provably closed. Under XAMD the profile
    names Q3 as the manipulation quarter while the nominal role of Q2 is still
    "manipulation", and both answers are correct about different questions.

    Q4's `role` has TWO entries. His note offers continuation or reversal and does
    not resolve which, so neither does this.

    None when `at` belongs to no quarter of `degree`.
    """
    quarter = _quarter_at(degree, at)
    if quarter is None:
        return None
    return NominalRole(
        degree=degree,
        label=quarter.label,
        start=quarter.start,
        end=quarter.end,
        role=ROLES[quarter.label],
    )


def intraday_session(at: int) -> IntradaySession | None:
    """His session name for the DAY-degree quarter holding `at`.

    Day degree only, because the names are intraday: a week-degree Q2 is a
    Tuesday and calling it London would be nonsense.

    The name is a nickname for a six-hour box and is NOT the session window this
    repo draws under the same name. `killzone` carries that window where one
    exists so the difference is visible rather than assumed away; it is strictly
    inside the quarter in both cases, so `same_window` is False. See the module
    docstring.

    None only when the day grid has no quarter for `at`, which the day degree
    does not produce - every instant is in some day cycle - so in practice this
    returns a session for every bar.
    """
    quarter = _quarter_at("day", at)
    if quarter is None:
        return None

    name = INTRADAY_SESSIONS[quarter.label]
    spec = KILLZONES.get(name)
    killzone = None
    if spec is not None:
        open_h, open_m, close_h, close_m, close_days = spec
        opens = clock.to_ny(quarter.start).date()
        shuts = opens + timedelta(days=close_days)
        killzone = (
            clock.ny_wall(opens.year, opens.month, opens.day, open_h, open_m),
            clock.ny_wall(shuts.year, shuts.month, shuts.day, close_h, close_m),
        )

    return IntradaySession(
        label=quarter.label,
        session=name,
        start=quarter.start,
        end=quarter.end,
        killzone=killzone,
        same_window=killzone == (quarter.start, quarter.end),
    )


def chain(at: int, degrees: Sequence[str]) -> Chain | None:
    """The quarter number at each degree, outermost first. A fact about the clock.

    `degrees` is ordered outermost-first and must nest that way; it is required
    rather than defaulted, because which three degrees a chain is read at is his
    choice per chart and not something this module should pick for a caller.

    None when ANY requested degree has no quarter at `at` - a chain including the
    week degree does not exist on a Friday, and a partial chain would read as a
    different chain rather than as a missing one.

    `in_his_list` is membership of a list he wrote down and is NOT a forecast.
    15.625% of three-digit chains are in it (`BASE_RATE`), and no one has measured
    whether the listed ones behave differently from the rest.
    """
    order = _ordered(degrees)
    found = [_quarter_at(d, at) for d in order]
    if any(q is None for q in found):
        return None

    numbers = tuple(int(q.label[1]) for q in found if q is not None)
    compact = "".join(str(n) for n in numbers)
    return Chain(
        at=at,
        degrees=order,
        quarters=numbers,
        text="-".join(str(n) for n in numbers),
        compact=compact,
        in_his_list=compact in HIS_LIST if len(numbers) == 3 else None,
    )


def occurrences(candles: list[Candle], degrees: Sequence[str]) -> Occurrence:
    """How often each chain occurs over these bars. Counts bars, measures nothing else.

    This is the distribution a study of his list needs BEFORE it starts, and it
    deliberately looks at no outcome: no return, no excursion, no zone, nothing
    after the bar. It answers one question - how common is each chain - because
    `BASE_RATE` is the uniform expectation and the real one may be nothing like
    it, in which case a later comparison against 15.625% would be measuring the
    calendar rather than the market.

    Every bar is accounted for: `counts` plus `outside` equals `bars`. Bars in
    time that belongs to no quarter go to `outside` rather than being dropped.
    """
    order = _ordered(degrees)
    tally: Counter[str] = Counter()
    outside = 0
    for candle in candles:
        found = chain(candle.time, order)
        if found is None:
            outside += 1
        else:
            tally[found.compact] += 1

    counted = len(candles) - outside
    listed = sum(n for text, n in tally.items() if text in HIS_LIST)
    return Occurrence(
        degrees=order,
        bars=len(candles),
        outside=outside,
        counts=dict(tally.most_common()),
        listed=listed,
        listed_share=round(listed / counted, 4) if counted else 0.0,
        base_rate=BASE_RATE,
    )


@dataclass(frozen=True)
class Killzone:
    """A window where every requested degree is in the SAME numbered quarter.

    Two independent sources name this object. Bucko's A-Z guide calls it a QT
    Killzone and gives the worked example "Q3 of Q3" for 09:00-10:30 New York:
    the daily cycle's Q3 (the AM session) and, inside it, the 90-minute cycle's
    Q3. The `quarter-sequence` reference calls the same thing an N-stage
    sequence. Neither supplies a number for it.

    A FACT ABOUT THE CLOCK, and nothing else. It takes no candles, reads no
    price and predicts nothing - which is exactly the property that lets it be
    measured honestly later: the windows exist before any outcome does, so a
    study over them cannot be accused of choosing them after the fact.

    `number` is the quarter all the degrees share, 1 to 4. `depth` is how many
    degrees agreed, which is the only ranking the sources offer ("stacking
    deeper" - four overlapping Q3s is their strongest case).
    """

    degrees: tuple[str, ...]  # outermost first
    number: int  # 1..4, the quarter every degree is in
    depth: int  # = len(degrees); how many agreed
    start: int  # epoch seconds, inclusive
    end: int  # epoch seconds, exclusive


def killzones(
    degrees: Sequence[str], start: int, end: int
) -> list[Killzone]:
    """Every window in [start, end) where all `degrees` share a quarter number.

    Built from the FINEST degree's own quarters, because the finest quarter is
    the shortest one and any window where all degrees agree is therefore exactly
    one of its quarters - no interval arithmetic and no merging is needed. That
    also means the returned windows never overlap and are already in time order.

    `degrees` must nest outermost-first, the same rule `chain` enforces and for
    the same reason; one degree is legal and returns that degree's own quarters,
    which is the degenerate case and is what "depth 1" means.

    Returns an empty list rather than raising when nothing aligns. Alignment is
    not rare and must never be read as a signal on its own: with two degrees a
    quarter of the finer one aligns 25% of the time by construction, with three
    6.25%. `depth` is on every row so a caller can price that in.
    """
    order = _ordered(degrees)
    finest = order[-1]
    out: list[Killzone] = []
    for quarter in quarters(finest, start, end):
        here = chain(quarter.start, order)
        if here is None:
            continue
        first = here.quarters[0]
        if all(n == first for n in here.quarters):
            out.append(
                Killzone(
                    degrees=order,
                    number=first,
                    depth=len(order),
                    start=quarter.start,
                    end=quarter.end,
                )
            )
    return out


def _selftest_killzones() -> None:
    """The worked example from the source, and the base rate its shape implies."""
    from datetime import datetime, timedelta, timezone

    # 09:00-10:30 New York on a weekday is Q3 of the day cycle AND Q3 of the
    # session cycle - the one window the source names outright.
    day = datetime(2026, 9, 9, tzinfo=timezone.utc)
    span = (int(day.timestamp()), int((day + timedelta(days=1)).timestamp()))
    found = killzones(("day", "session"), *span)
    assert found, "day+session must align somewhere inside a full day"
    assert all(k.depth == 2 for k in found)
    assert all(k.number in (1, 2, 3, 4) for k in found)

    # A quarter of the finer degree is the unit, so the windows tile that degree
    # and never overlap.
    for a, b in zip(found, found[1:]):
        assert a.end <= b.start, "killzone windows must not overlap"

    # BASE RATE, ASSERTED RATHER THAN ASSUMED. One of every four session
    # quarters aligns with its day quarter, by construction. Over a long window
    # the count must come out at a quarter of the session quarters, and that is
    # the number any later study has to beat.
    wide = (
        int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp()),
    )
    all_session = quarters("session", *wide)
    aligned = killzones(("day", "session"), *wide)
    share = len(aligned) / len(all_session)
    assert 0.24 < share < 0.26, f"expected ~0.25 of session quarters, got {share}"

    # Three degrees agree an order of magnitude less often, and that is the
    # whole reason "stacking deeper" is claimed to be stronger.
    deep = killzones(("day", "session", "micro"), *wide)
    all_micro = quarters("micro", *wide)
    deep_share = len(deep) / len(all_micro)
    assert 0.055 < deep_share < 0.07, f"expected ~0.0625, got {deep_share}"

    # One degree is the degenerate case: every quarter of it qualifies.
    alone = killzones(("day",), *span)
    assert len(alone) == len(quarters("day", *span))
    assert all(k.depth == 1 for k in alone)


def _selftest() -> None:
    """The gate's entry point for this module.

    Named `_selftest` exactly, because `tests/test_selftests_run.py` discovers
    by that name and a helper called anything else never runs - the same hole
    that left nine of these unexecuted until 5 September 2026.
    """
    _selftest_killzones()


if __name__ == "__main__":
    _selftest()
