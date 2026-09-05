"""The six Quarterly Theory builders `app/ict.py` never had a column for.

WHY THIS MODULE IS SEPARATE FROM `ict.py`. Nine of the fifteen items on the
practitioner's QT entry checklist already have a clause in `ict.evaluate`, and
`docs/checklist_outcomes.json` measured all of them: one separated, `dfr_side`,
with the sign INVERTED, and the aggregate `met` score did not separate at all
(n=1855, `separates: false`). The remaining six were never measured here
because no column existed. This module is those six columns and nothing else.

NOTHING HERE IS WIRED TO THE ORDER PATH, and that ordering is the repo's own
rule rather than caution: `ict.Rules.required` defaults to empty so a clause can
be measured before it is ever allowed to block a trade. Adding these to
`ict.evaluate` would also change `Setup.met`, which `tools/execute.py` sorts
candidates by, and would break comparability with every number already taken
under the seventeen-clause checklist. They go into the measurement rig first.

EACH PREDICATE ANSWERS FOR ONE SIDE. `demand=True` means the candidate is a
long. `None` means NOT KNOWABLE - no levels yet, no London bars, no partner
series - and never "no", the same rule `Candle.spread` and `conditions.at_bar`
follow. A study that reads absent as false measures its own warm-up.

===========================================================================
WHERE THIS REPO AND THE SOURCE DISAGREE, STATED BEFORE ANY NUMBER IS TAKEN
===========================================================================

The reference material was re-read against this repo on 5 September 2026. Five
divergences were found, and each is carried as a SEPARATE COLUMN rather than
resolved by picking a winner, because picking one before measuring is how a
checklist becomes a belief. A sixth, the VWAP anchor, is recorded on
`day_anchored` itself because it is a property of that one reading.

1. JUDAS, AND THIS ONE IS AN INVERSION. `app/judas.py` derives the expansion
   direction from the LONDON bias alone: London bullish -> Template A ->
   expansion BUY. The source's own four-template table derives it from the
   OBSERVED New York counter-move: London up plus a Judas that sweeps BSL
   (up) is Template A and its distribution is DOWN. In the source table the
   London leg only labels the template; the direction is a pure function of
   the Judas sweep and is always its opposite. So the two give OPPOSITE calls
   on the same day whenever the Judas runs with London rather than against it.
   `judas_agrees` reads this repo's version. `judas_source_side` reads the
   source's. Both are measured.

2. TRUTH ASSET, TWO DIFFERENT METRICS. `app/triad.py` scores consolidation as
   range over ATR on a 20-bar lookback. The reference implementation
   (`QT-Auto-Scanner/python/triads.py`) takes the standard deviation of simple
   returns over the whole supplied window and picks the argmin. Neither carries
   a threshold, so both always name an asset even when all three are equally
   choppy. `truth_asset_agrees` reads this repo's; `truth_asset_by_volatility`
   reproduces the reference's.

3. B8 IS PROXIMITY, NOT SIDE. The source defines the volume builder as an OR:
   entry within 1 ATR of anchored VWAP, OR VWAP aligning with a True Open, OR
   CVD supporting the direction. That is a LOCATION claim. A separate line of
   the same source states a directional rule ("price above POC = bullish"),
   and it is NOT one of the three OR clauses. They are kept apart here:
   `vwap_near` and `vwap_at_true_open` are the source's clauses; `vwap_side`
   and `value_area_edge` are the directional and POC readings.

4. THE 90-MINUTE DEGREE IS CALLED `session` HERE. The source's chain is
   Weekly-Daily-90m. In this repo the `day` degree's four quarters ARE the six
   hour sessions, so the 90-minute quarter is the `session` degree's. Only the
   NAMES line up. See 5 for the boundaries, which do not.

5. THE BOUNDARIES ARE 90 MINUTES APART, AND THIS IS THE BIGGEST DIVERGENCE.
   `app/quarters.py` opens the day cycle at 18:00 New York, so its quarters run
   18:00, 00:00, 06:00 and 12:00. The source runs 19:30, 01:30, 07:30 and
   13:30. `app/sequence.py` already writes this down at its own line 54, and it
   is not a bug on either side - the 18:00 grid is the ICT-lineage convention
   this repo was built on. But it means "Q3" names a different six hours in the
   two systems, overlapping 4.5 hours of 6.

   Consequence, and it is the reason `source_chain` exists below: a chain read
   off this repo's grid is NOT the chain his list was written against. Both are
   computed, as `sequence_listed` and `sequence_listed_source`, and the MQL5
   side (`mql5/ZonelabSupplyDemand/QTClock.mqh`) implements the SOURCE grid so
   the two venues measure the same object.

===========================================================================
WHAT IS NOT HERE, AND WHY IT CANNOT BE
===========================================================================

    B9 `news_clear` has no implementation and cannot get one from the shipped
    source. `app/news.py` documents it: the feed is
    `ff_calendar_thisweek.json`, and `_nextweek`, `_lastweek`, `_thismonth`,
    `_thisyear` all return HTTP 404, so there is no history to score a past bar
    against. The MetaTrader5 package on this machine (5.0.6090) exposes no
    calendar function either - checked, `[a for a in dir(mt5) if "calendar"]`
    is empty. So B9 is structurally unmeasurable here and is reported as
    blocked rather than filled with today's calendar, which would score this
    week's events against bars from last year. The reference implementation
    does not solve this either: it hardcodes `news_clear=True` on every call,
    so the builder scores its point unconditionally there.

    The CVD half of B8 is likewise absent. MT5 ticks on an FX or metals CFD do
    not carry a trustworthy trade side (`TICK_FLAG_BUY`/`TICK_FLAG_SELL` are
    not populated by brokers on this instrument class), so a CVD here would be
    a Lee-Ready tick-rule INFERENCE, not a measurement.
"""

from __future__ import annotations

import numpy as np

from . import clock
from .indicators import volume_profile, vwap
from .models import Candle
from .quarters import stacked_opens
from .sequence import chain
from .triad import TruthAsset

#: Degrees the three-digit chain is read at, outermost first. Week-Day-Session
#: because that is what the practitioner's notation W-D-90m names: his `daily`
#: quarter is a six hour session, which is this repo's `day` degree, and his
#: 90-minute quarter is a quarter of that session, which is this repo's
#: `session` degree. `chain` requires the caller to choose for exactly this
#: reason and defaults nothing.
CHAIN_DEGREES: tuple[str, str, str] = ("week", "day", "session")

#: Degrees the true-open stack is counted over. Month, week and day are TMO,
#: TWO and TDO, and they are the three the source's own worked example names
#: ("true opens harus pake dua minimal", with Week and Month as the pair).
#:
#: THE INTRADAY OPENS ARE DELIBERATELY ABSENT. The source lists TAO, TLO and
#: TNYO at 19:30, 01:30 and 07:30 New York. This repo derives a true open as a
#: cycle's Q2 open, and the `session` degree's Q2 opens 90 minutes into a
#: session - 21:00, not 19:30. Adding `session` here would count a level that
#: is not the level the source names, so it is left out and the gap is stated.
OPEN_DEGREES: tuple[str, str, str] = ("month", "week", "day")

#: True opens that must agree before B3 passes. Two, and it is HIS figure.
#: Unmeasured, which is why this study exists.
MIN_TRUE_OPENS = 2

#: How close to anchored VWAP counts as "at" it, in ATR. One, and it is the
#: source's own constant: "entry price within 1 ATR of anchored VWAP".
VWAP_TOLERANCE_ATR = 1.0

#: How close to POC, VAH or VAL counts as "at" it, in ATR. The source gives NO
#: tolerance for this clause, so a quarter ATR is this repo's choice, stated
#: rather than justified: the zones it is measured against are ATR-scaled, and
#: a fixed price tolerance would mean something different on gold and EURUSD.
VALUE_AREA_TOLERANCE_ATR = 0.25

#: The New York window the source gives for the Judas leg, in wall-clock hours.
#: 09:00 to 10:00. A second file in the same source says the containing
#: 90-minute quarter runs 09:00-10:30; the narrower window is used because it
#: is the one the Judas page itself states, and the difference is recorded here
#: rather than averaged away.
JUDAS_WINDOW_NY: tuple[int, int] = (9, 10)

#: Bars the reference implementation requires before it will score an asset's
#: volatility. Twenty, from `QT-Auto-Scanner/python/triads.py`.
VOLATILITY_MIN_BARS = 20


#: Session boundaries the SOURCE uses, in minutes since New York midnight.
#: Asia wraps midnight, so it is checked as two pieces rather than one. These
#: are NOT this repo's boundaries - see divergence 5 in the module docstring -
#: and they are duplicated in `mql5/ZonelabSupplyDemand/QTClock.mqh`, which is
#: exactly why `tests/test_mql5_contract.py` binds the two copies together.
SOURCE_ASIA_START = 1170    # 19:30
SOURCE_LONDON_START = 90    # 01:30
SOURCE_NYAM_START = 450     # 07:30
SOURCE_NYPM_START = 810     # 13:30

#: The ten chains he wrote down, as three-digit codes. Held here as well as in
#: `sequence.HIS_LIST` because this module reads them off the SOURCE grid, and
#: the test that binds MQL5 to Python compares against both.
SOURCE_HIGH_PROB: frozenset[str] = frozenset(
    {"111", "114", "141", "144", "222", "333", "411", "414", "441", "444"}
)


def source_chain(at: int) -> tuple[int, int, int]:
    """The (weekly, daily, 90m) quarter numbers on the SOURCE's grid.

    Weekly is 1 on Monday through 4 on Thursday and 0 from Friday to Sunday,
    where 0 means NO quarter rather than a quarter numbered zero: Friday has
    its own profile in this method and is not a fifth quarter.

    Daily and 90m are always 1..4 - every instant sits inside some session.

    Pure clock arithmetic, no bars, so it cannot look ahead by construction.
    Mirrors `mql5/ZonelabSupplyDemand/QTClock.mqh` line for line.
    """
    ny = clock.to_ny(at)
    weekday = ny.weekday()  # Monday == 0
    weekly = weekday + 1 if weekday <= 3 else 0

    minutes = ny.hour * 60 + ny.minute
    if minutes >= SOURCE_ASIA_START or minutes < SOURCE_LONDON_START:
        daily = 1
        into = (minutes - SOURCE_ASIA_START if minutes >= SOURCE_ASIA_START
                else minutes + (1440 - SOURCE_ASIA_START))
    elif minutes < SOURCE_NYAM_START:
        daily, into = 2, minutes - SOURCE_LONDON_START
    elif minutes < SOURCE_NYPM_START:
        daily, into = 3, minutes - SOURCE_NYAM_START
    else:
        daily, into = 4, minutes - SOURCE_NYPM_START
    return weekly, daily, min(into // 90 + 1, 4)


def sequence_listed_source(at: int) -> bool | None:
    """B2 on the SOURCE's grid. None from Friday to Sunday, where no chain exists.

    The reference implementation answers False there instead. None is used here
    so Friday lands in its own bucket rather than being pooled with genuinely
    unlisted chains; the MQL5 side must answer False because an EA has to
    decide, and that difference is stated in both files.
    """
    weekly, daily, q90 = source_chain(at)
    if weekly == 0:
        return None
    return f"{weekly}{daily}{q90}" in SOURCE_HIGH_PROB


def current_opens(levels, now: int) -> list:
    """The LATEST true open of each degree that has already opened at `now`.

    THIS FILTER IS THE WHOLE CLAUSE, and leaving it out is not a small error.
    `quarters.true_opens` returns every boundary in the window, which on 50.000
    hourly bars is about 2.400 levels across month, week and day. Counting how
    many of THOSE sit below price makes "at least two agree" true on almost
    every bar: measured on XAUUSD, the unfiltered column read 209 True against
    13 False, which is a constant wearing the costume of a variable.

    What the source names is the CURRENT TMO, TWO and TDO - one level per
    degree - so that is what is counted. `true_opens` returns levels ordered by
    time within each degree, so keeping the last per degree keeps the newest.

    Right-bounded at `now` on `bar`, the open time of the bar the price was
    read from, so a level whose bar has not opened yet cannot enter.
    """
    latest: dict[str, object] = {}
    for level in levels:
        if level.bar <= now:
            latest[level.degree] = level
    return list(latest.values())


def sequence_listed(at: int, degrees: tuple[str, ...] = CHAIN_DEGREES) -> bool | None:
    """B2. Is the quarter chain at `at` one of the ten he wrote down?

    Side-independent, because his list is: a chain is listed or it is not, and
    the note attaches no direction to any of the ten.

    None when any degree has no quarter at `at` - Friday has no week quarter,
    and a partial chain would read as a different chain rather than a missing
    one. The reference implementation returns FALSE on a Friday instead; the
    difference is deliberate here, so Friday lands in its own bucket rather
    than being pooled with genuinely unlisted chains.

    QUOTE THE BASE RATE WHENEVER THIS IS QUOTED. Ten of sixty-four chains are
    listed, so `True` is a one-in-six event by arithmetic before any market
    behaviour is involved (`sequence.BASE_RATE`).
    """
    found = chain(at, degrees)
    return None if found is None else found.in_his_list


def true_opens_agree(
    price: float,
    levels,
    demand: bool,
    minimum: int = MIN_TRUE_OPENS,
) -> bool | None:
    """B3. Do at least `minimum` true opens sit on the side the trade needs?

    A long needs price ABOVE the levels, so the levels are BELOW price; a short
    is the same reading from the other end. `quarters.stacked_opens` does the
    counting and deliberately holds no threshold, so the threshold is here.

    None when no levels were passed at all. Zero levels is not zero agreement,
    it is no reading: `true_opens` returns nothing for a boundary with no bar
    on it, which is a fact about the calendar rather than about price.
    """
    if not levels:
        return None
    stack = stacked_opens(price, levels)
    supporting = stack.below if demand else stack.above
    return len(supporting) >= minimum


def judas_agrees(reading, demand: bool) -> bool | None:
    """B6, THIS REPO'S READING. Does `judas.classify`'s expansion match the side?

    `reading` is `checklist._judas` output. Templates A and B name a direction;
    C and D name "wait", and waiting is not disagreement - it returns None, so
    a template that declines to call a side never counts as a failed builder.

    See divergence 1 in the module docstring: this reading is derived from the
    London bias alone and is the OPPOSITE of the source's table on any day when
    the Judas runs with London rather than against it.
    """
    if reading is None:
        return None
    wanted = "buy" if demand else "sell"
    direction = getattr(reading, "expansion_direction", None)
    if direction not in ("buy", "sell"):
        return None
    return direction == wanted


def judas_source_side(candles: list[Candle], index: int) -> str | None:
    """B6, THE SOURCE'S READING. Which way distribution should go, from the sweep.

    The source's four templates collapse to one rule: the Judas swing is always
    opposite the real distribution, so distribution is the opposite of whatever
    the New York counter-move swept. Sweeping buy-side liquidity (taking out
    the pre-09:00 high) is a Judas UP, so distribution is DOWN.

    "Pre-09:00" is the day's own bars from midnight New York - the True Day
    Open - up to the window. That is Asia plus London, which is exactly the
    liquidity the source names as the pool being taken.

    Returns "buy", "sell", or None. None covers four honest cases and they are
    not distinguished, because none of them is a direction: the window has not
    closed yet at `index`, no bars fall in it, nothing was swept, or BOTH sides
    were swept and the sweep names no side.

    USES NO BAR AFTER `index`.
    """
    if not 0 <= index < len(candles):
        return None
    now = candles[index].time
    day = clock.to_ny(now)
    start = clock.ny_wall(day.year, day.month, day.day, JUDAS_WINDOW_NY[0])
    end = clock.ny_wall(day.year, day.month, day.day, JUDAS_WINDOW_NY[1])
    # The window must be CLOSED at the bar being judged. Reading a window that
    # still has bars to come is the lookahead this whole rig exists to avoid.
    if now < end:
        return None
    open_ny = clock.ny_wall(day.year, day.month, day.day, 0)

    past = candles[: index + 1]
    before = [c for c in past if open_ny <= c.time < start]
    window = [c for c in past if start <= c.time < end]
    if not before or not window:
        return None

    took_high = max(c.high for c in window) > max(c.high for c in before)
    took_low = min(c.low for c in window) < min(c.low for c in before)
    if took_high == took_low:  # neither, or both - no side either way
        return None
    return "sell" if took_high else "buy"


def truth_asset_agrees(reading: TruthAsset | None, base: str) -> bool | None:
    """B7, THIS REPO'S READING. Is the traded instrument the triad's Truth Asset?

    The framework's claim is that the consolidating member of a triad shows the
    real premium and discount. It attaches NO direction to that - `app/triad.py`
    says so in its own docstring - so this asks membership only.

    None when the triad could not be scored, which happens when every partner
    series is too short.
    """
    if reading is None:
        return None
    return reading.symbol.split(":")[-1].upper() == base.split(":")[-1].upper()


def truth_asset_by_volatility(
    series: dict[str, list[Candle]], base: str
) -> bool | None:
    """B7, THE REFERENCE'S READING. Argmin of return standard deviation.

    Reproduces `QT-Auto-Scanner/python/triads.py:identify_truth_asset`: simple
    percentage returns over the whole supplied window, standard deviation, and
    the lowest wins. No threshold, so it always names one - which means a triad
    where all three are equally choppy still produces a Truth Asset, and that
    is a property of the rule rather than of the market.

    None when fewer than two members clear `VOLATILITY_MIN_BARS`; one member
    scored against nobody is a ranking of one.
    """
    scores: dict[str, float] = {}
    for symbol, candles in series.items():
        if len(candles) < VOLATILITY_MIN_BARS:
            continue
        close = np.array([c.close for c in candles], dtype=np.float64)
        if not np.all(close[:-1] > 0):
            continue
        returns = np.diff(close) / close[:-1]
        scores[symbol.split(":")[-1].upper()] = float(returns.std(ddof=0))
    if len(scores) < 2:
        return None
    winner = min(scores, key=lambda s: scores[s])
    return winner == base.split(":")[-1].upper()


def vwap_near(
    price: float,
    level: float | None,
    scale: float,
    tolerance: float = VWAP_TOLERANCE_ATR,
) -> bool | None:
    """B8, the source's first clause. Is entry within `tolerance` ATR of VWAP?

    Side-independent: the source states proximity, not a side.

    None when the anchor produced no value or there is no usable ATR.

    THE VOLUME IS TICK VOLUME. `indicators.vwap` says it: MT5 publishes ticks
    per bar, not traded size, so this VWAP is an approximation whose accuracy
    is unknown on this feed and has not been measured here.
    """
    if level is None or not np.isfinite(level) or scale <= 0:
        return None
    return abs(price - level) <= tolerance * scale


def vwap_at_true_open(
    level: float | None,
    levels,
    scale: float,
    tolerance: float = VWAP_TOLERANCE_ATR,
) -> bool | None:
    """B8, the source's second clause. Does anchored VWAP sit on a True Open?

    The source says "VWAP level aligns with a True Open price level" and gives
    no tolerance for "aligns", so it borrows the one tolerance the same clause
    does state, 1 ATR. That borrowing is a choice and is recorded as one.

    None when either side of the comparison is missing.
    """
    if level is None or not np.isfinite(level) or scale <= 0 or not levels:
        return None
    band = tolerance * scale
    return any(abs(level - float(lv.price)) <= band for lv in levels)


def vwap_side(price: float, level: float | None, demand: bool) -> bool | None:
    """B8's directional cousin, which the source keeps OUT of the builder.

    Reported separately so the location claim and the direction claim cannot be
    confused for one another. Standing exactly on the line is not a side.
    """
    if level is None or not np.isfinite(level):
        return None
    if price == level:
        return None
    return price > level if demand else price < level


def value_area_edge(
    price: float,
    profile: dict | None,
    scale: float,
    tolerance: float = VALUE_AREA_TOLERANCE_ATR,
) -> bool | None:
    """B8's profile clause. Is price at POC, VAH or VAL, within `tolerance` ATR?

    Side-independent: the source names a location and not a direction. Whether
    the location favours a long or a short is what the study is for.

    The 70 per cent value area is the source's figure and `indicators.volume_profile`
    already uses it. The bin count is NOT the source's - it gives none - and is
    this repo's default of 24.

    None when there is no profile or no usable ATR.
    """
    if not profile or scale <= 0:
        return None
    band = tolerance * scale
    for key in ("poc", "vah", "val"):
        level = profile.get(key)
        if level and abs(price - float(level)) <= band:
            return True
    return False


def day_anchored(
    candles: list[Candle], index: int, cycle_start: int | None
) -> tuple[float | None, dict | None]:
    """VWAP value and volume profile for the day cycle containing `index`.

    Anchored to the DAY CYCLE start, which in this repo is 18:00 New York, and
    that is NOT True Day Open. TDO is midnight, the day cycle's Q2 open;
    `conditions.at_bar` reports the CYCLE start, and this reads what it reports.
    18:00 New York is the Asia session open on this repo's grid, so it is one
    of the anchors the source's volume layer names ("session open") - but it is
    the wrong one to call TDO, and an earlier draft of this docstring did.

    Anchoring to midnight, or to the week, would each be a different and
    equally defensible choice. None of the three is measured, so this one is
    stated rather than justified.

    USES NO BAR AFTER `index`. The slice is taken once and both readings come
    off it, the same discipline `conditions.at_bar` enforces in one line.

    Returns `(None, None)` when the cycle start is unknown or falls outside the
    window - a bar in the first day of the series has no anchored reading, and
    that is absence, not zero.
    """
    if cycle_start is None or not 0 <= index < len(candles):
        return None, None
    past = candles[: index + 1]
    first = next((i for i, c in enumerate(past) if c.time >= cycle_start), None)
    if first is None or first > index:
        return None, None

    window = past[first:]
    if not window:
        return None, None
    high = np.array([c.high for c in window], dtype=np.float64)
    low = np.array([c.low for c in window], dtype=np.float64)
    close = np.array([c.close for c in window], dtype=np.float64)
    volume = np.array([c.volume for c in window], dtype=np.float64)
    if volume.sum() <= 0:
        # A feed that ships no volume cannot produce either reading, and a VWAP
        # computed over zeros would be the mean typical price wearing a volume
        # name. Absent, not substituted.
        return None, None

    line = vwap(high, low, close, volume)
    last = float(line[-1]) if len(line) and np.isfinite(line[-1]) else None
    return last, volume_profile(high, low, close, volume)


#: B9. Named so a reader looking for it finds the reason rather than nothing.
NEWS_CLEAR_BLOCKED = (
    "app/news.py serves only ff_calendar_thisweek.json; _lastweek, _nextweek, "
    "_thismonth and _thisyear all return HTTP 404, and MetaTrader5 5.0.6090 "
    "exposes no calendar function. There is no history to score a past bar "
    "against, so B9 cannot be measured on this machine. The reference "
    "implementation hardcodes news_clear=True and so never measured it either."
)


def _selftest() -> None:
    """Each predicate's failure mode, injected and checked."""
    # Absent inputs answer None, never False. This is the rule the whole module
    # turns on and the one a refactor is most likely to break.
    assert true_opens_agree(1.0, [], True) is None
    assert judas_agrees(None, True) is None
    assert truth_asset_agrees(None, "XAUUSD") is None
    assert vwap_side(1.0, None, True) is None
    assert vwap_near(1.0, None, 1.0) is None
    assert vwap_near(1.0, 1.0, 0.0) is None
    assert vwap_at_true_open(1.0, [], 1.0) is None
    assert value_area_edge(1.0, None, 1.0) is None
    assert value_area_edge(1.0, {"poc": 1.0}, 0.0) is None
    assert day_anchored([], 0, 123) == (None, None)
    assert truth_asset_by_volatility({}, "XAUUSD") is None

    class _Level:
        def __init__(self, price: float) -> None:
            self.price = price

    below = [_Level(0.9), _Level(0.8)]
    assert true_opens_agree(1.0, below, demand=True) is True
    assert true_opens_agree(1.0, below, demand=False) is False
    # One level is not two, and the threshold is the whole point of the clause.
    assert true_opens_agree(1.0, below[:1], demand=True) is False

    class _Judas:
        expansion_direction = "buy"

    assert judas_agrees(_Judas(), demand=True) is True
    assert judas_agrees(_Judas(), demand=False) is False
    _Judas.expansion_direction = "none"
    assert judas_agrees(_Judas(), demand=True) is None

    assert truth_asset_agrees(
        TruthAsset(symbol="mt5:XAUUSD", scores={}, base="XAUUSD", triad="x"),
        "XAUUSD") is True
    assert truth_asset_agrees(
        TruthAsset(symbol="XAGUSD", scores={}, base="XAUUSD", triad="x"),
        "XAUUSD") is False

    assert vwap_side(2.0, 1.0, demand=True) is True
    assert vwap_side(2.0, 1.0, demand=False) is False
    # Standing on the line is not a side.
    assert vwap_side(1.0, 1.0, demand=True) is None
    # Proximity is not side: BELOW vwap by less than an ATR still counts as near.
    assert vwap_near(99.5, 100.0, 1.0) is True
    assert vwap_near(97.0, 100.0, 1.0) is False
    assert vwap_at_true_open(100.0, [_Level(100.5)], 1.0) is True
    assert vwap_at_true_open(100.0, [_Level(104.0)], 1.0) is False

    assert value_area_edge(100.0, {"poc": 100.2, "vah": 0, "val": 0}, 1.0) is True
    assert value_area_edge(100.0, {"poc": 105.0, "vah": 0, "val": 0}, 1.0) is False

    # Argmin of return volatility, and the flat series must win it.
    flat_series = [Candle(time=i * 3600, open=1, high=1, low=1, close=1.0)
                   for i in range(30)]
    noisy = [Candle(time=i * 3600, open=1, high=2, low=0.5,
                    close=1.0 + (0.2 if i % 2 else -0.2)) for i in range(30)]
    assert truth_asset_by_volatility(
        {"XAUUSD": flat_series, "XAGUSD": noisy}, "XAUUSD") is True
    assert truth_asset_by_volatility(
        {"XAUUSD": noisy, "XAGUSD": flat_series}, "XAUUSD") is False
    # One member is a ranking of one, and a ranking of one is not a ranking.
    assert truth_asset_by_volatility({"XAUUSD": flat_series}, "XAUUSD") is None

    # A day-anchored reading exists once there are bars with volume in the day.
    bars = [Candle(time=t, open=1, high=2, low=0.5, close=1.5, volume=10)
            for t in range(0, 3600 * 5, 3600)]
    line, profile = day_anchored(bars, 4, cycle_start=0)
    assert line is not None and profile is not None and profile["poc"] > 0
    # No volume, no reading - not a VWAP built out of zeros.
    zeroed = [c.model_copy(update={"volume": 0.0}) for c in bars]
    assert day_anchored(zeroed, 4, cycle_start=0) == (None, None)

    _selftest_current_opens()
    _selftest_source_grid()
    _selftest_judas()
    print("qt selftest ok")


def _selftest_current_opens() -> None:
    """Satu level per derajat, yang terbaru, dan tidak ada yang dari masa depan."""
    from .quarters import TrueOpen

    levels = [
        TrueOpen(degree="month", time=100, price=1.0, bar=100),
        TrueOpen(degree="month", time=200, price=2.0, bar=200),
        TrueOpen(degree="week", time=150, price=3.0, bar=150),
        TrueOpen(degree="week", time=250, price=4.0, bar=250),
        TrueOpen(degree="day", time=300, price=5.0, bar=300),
    ]
    at_260 = current_opens(levels, 260)
    assert {lv.degree for lv in at_260} == {"month", "week"}
    # Yang TERBARU per derajat, bukan yang pertama.
    assert {lv.degree: lv.price for lv in at_260} == {"month": 2.0, "week": 4.0}
    # Level yang barnya belum buka tidak boleh masuk.
    assert all(lv.bar <= 260 for lv in at_260)
    assert current_opens(levels, 50) == []
    assert len(current_opens(levels, 999)) == 3

    # DAN INI ALASAN FILTERNYA ADA: tanpa membatasi ke satu per derajat,
    # ambang "minimal dua" terpenuhi oleh riwayat dan bukan oleh harga.
    assert true_opens_agree(9.0, levels, demand=True) is True
    assert true_opens_agree(9.0, current_opens(levels, 260), demand=True) is True
    assert true_opens_agree(3.0, levels, demand=True) is True
    assert true_opens_agree(3.0, current_opens(levels, 260), demand=True) is False


def _selftest_source_grid() -> None:
    """The source grid, checked at its own boundaries and at the repo's.

    The two grids are 90 minutes apart, so a timestamp that is Q3 on one is Q2
    on the other for an hour and a half every session. That offset IS the
    finding, so it is asserted rather than described.
    """
    def at(y, m, d, hh, mm=0):
        return clock.ny_wall(y, m, d, hh, mm)

    # 2 September 2026 is a Wednesday, so weekly quarter 3.
    assert source_chain(at(2026, 9, 2, 10, 45))[0] == 3
    # Friday, Saturday, Sunday carry no week quarter at all.
    assert source_chain(at(2026, 9, 4, 10))[0] == 0
    assert source_chain(at(2026, 9, 5, 10))[0] == 0
    assert source_chain(at(2026, 9, 6, 10))[0] == 0

    # Session edges, from the source's own table.
    assert source_chain(at(2026, 9, 2, 19, 30))[1] == 1   # Asia opens
    assert source_chain(at(2026, 9, 2, 1, 29))[1] == 1    # Asia still, past midnight
    assert source_chain(at(2026, 9, 2, 1, 30))[1] == 2    # London opens
    assert source_chain(at(2026, 9, 2, 7, 29))[1] == 2
    assert source_chain(at(2026, 9, 2, 7, 30))[1] == 3    # NY AM opens
    assert source_chain(at(2026, 9, 2, 13, 29))[1] == 3
    assert source_chain(at(2026, 9, 2, 13, 30))[1] == 4   # NY PM opens

    # 90-minute quarters inside NY AM, from the source's own table.
    for hour, minute, want in ((7, 30, 1), (8, 59, 1), (9, 0, 2), (10, 29, 2),
                               (10, 30, 3), (11, 59, 3), (12, 0, 4), (13, 29, 4)):
        assert source_chain(at(2026, 9, 2, hour, minute))[2] == want, (hour, minute)

    # ASIA WRAPS MIDNIGHT, and this is the branch that silently restarts the
    # 90-minute grid every morning if it is removed.
    assert source_chain(at(2026, 9, 2, 22, 45))[2] == 3   # 195 min into Asia
    assert source_chain(at(2026, 9, 2, 0, 15))[2] == 4    # 285 min into Asia

    # Wednesday 10:45 NY is 3-3-3, the chain the source calls prime time.
    assert source_chain(at(2026, 9, 2, 10, 45)) == (3, 3, 3)
    assert sequence_listed_source(at(2026, 9, 2, 10, 45)) is True
    # 3-3-1 is not on his list.
    assert sequence_listed_source(at(2026, 9, 2, 7, 45)) is False
    # No chain from Friday, so no answer.
    assert sequence_listed_source(at(2026, 9, 4, 10, 45)) is None

    # THE OFFSET ITSELF. 06:30 New York is NY AM on this repo's 18:00 grid and
    # still LONDON on the source's 19:30 grid. If these ever agree, one of the
    # two grids has been changed and the two venues stopped measuring the same
    # object.
    from .quarters import quarters as _grid
    when = at(2026, 9, 2, 6, 30)
    repo = [q.label for q in _grid("day", when, when)]
    assert repo == ["Q3"], repo
    assert source_chain(when)[1] == 2


def _selftest_judas() -> None:
    """The source's Judas rule, built as bars so the window logic is exercised."""
    day = clock.ny_wall(2026, 9, 2, 0)  # a Wednesday, midnight New York
    hours = 12

    def series(sweep: str) -> list[Candle]:
        out = []
        for i in range(hours):
            t = day + i * 3600
            ny_hour = clock.to_ny(t).hour
            high, low = 100.0, 99.0
            if ny_hour in range(JUDAS_WINDOW_NY[0], JUDAS_WINDOW_NY[1]):
                if sweep == "high":
                    high = 101.0
                elif sweep == "low":
                    low = 98.0
                elif sweep == "both":
                    high, low = 101.0, 98.0
            out.append(Candle(time=t, open=99.5, high=high, low=low,
                              close=99.5, volume=1))
        return out

    high_swept = series("high")
    last = len(high_swept) - 1
    # Judas took the high, so it was a Judas UP, so distribution is DOWN.
    assert judas_source_side(high_swept, last) == "sell"
    assert judas_source_side(series("low"), last) == "buy"
    # Both sides taken names no side, and neither does neither.
    assert judas_source_side(series("both"), last) is None
    assert judas_source_side(series("none"), last) is None
    # ANTI-LOOKAHEAD: judged at a bar inside the window, the window is not
    # closed yet and the answer must be absent rather than early.
    inside = next(i for i, c in enumerate(high_swept)
                  if clock.to_ny(c.time).hour == JUDAS_WINDOW_NY[0])
    assert judas_source_side(high_swept, inside) is None


if __name__ == "__main__":
    _selftest()
