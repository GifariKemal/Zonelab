"""The economic calendar, and the one row on the time board nothing else answers.

The method this engine is built for names NFP, CPI and FOMC against the
accumulation, manipulation and distribution phases, and `docs/ADOPSI.md` records
`News/NFP 08:30 New York` as the single line with no implementation behind it.
This module is that line and nothing more: it reads a schedule.

THE SOURCE
    https://nfs.faireconomy.media/ff_calendar_thisweek.json

Keyless, no account, about 13 KB, probed live on 2026-08-19. `robots.txt` on
that host is `User-agent: *` with an EMPTY `Disallow:`, so the whole host is
permitted. `www.forexfactory.com` itself is NOT touched here and must not be:
it sits behind a Cloudflare managed challenge, so scraping it is both blocked
and out of bounds. The CDN feed is the sanctioned path.

Each row carries exactly six fields, verified on 98 of them:

    {"title": "Non-Farm Employment Change", "country": "USD",
     "date": "2026-08-17T08:30:00-04:00", "impact": "High",
     "forecast": "0.4%", "previous": "-0.4%"}

`country` is a CURRENCY code (USD, GBP, EUR, CAD, CNY, JPY, AUD, NZD), which is
why it is called `currency` on the way out.

THREE PROPERTIES THAT DECIDE EVERYTHING BELOW

1. THE TIMESTAMP CARRIES ITS OWN UTC OFFSET, AND IT IS READ, NEVER ASSUMED.
   Every row on the live sample read `-04:00`, which is New York in summer. In
   winter it will read `-05:00`. A constant offset would therefore be exactly
   right for half the year and silently an hour wrong for the other half, with
   nothing on the chart saying which half you are looking at - the same failure
   `app/clock.py` exists to prevent, arriving through a different door. So the
   offset is parsed out of the string by `datetime.fromisoformat` and a row
   whose timestamp carries NO offset is refused rather than guessed at.
   The winter case is covered by unit test only; it has never been observed
   live from here, because only the current week is fetchable.

2. THERE IS NO `actual` FIELD, AND THAT IS THE REASON THIS IS SAFE TO DRAW.
   The feed publishes the schedule plus forecast and previous, never the
   outcome. It therefore CANNOT leak a result backwards into a bar. Everything
   this engine draws is computed from closed bars and nothing that happened
   after them, and a calendar that never publishes what happened preserves that
   property by construction rather than by discipline.

3. ONLY THE CURRENT WEEK EXISTS, SO THIS DATA CAN NEVER BE MEASURED.
   `ff_calendar_nextweek.json`, `_lastweek`, `_thismonth` and `_thisyear` were
   all probed and every one returns HTTP 404. There is no history. Any backtest
   built on this source would be scoring today's calendar against yesterday's
   bars, which measures nothing. That is why `NewsWeek` carries the window it
   ACTUALLY covers instead of a seven-day assumption, and why there is no
   `history` parameter here: a parameter that cannot be honoured is a promise.

WHAT `impact` IS NOT
`impact` is the FEED'S OWN LABEL for how much attention an event draws. It is
not a forecast, not a direction, and not a measured effect. Nobody on this
project has measured whether a High row moves price more than a Low one, and
twelve pre-registered directional hypotheses have already failed here. The
value is passed through verbatim and never ranked.

ABSENT IS NOT ZERO
An empty `forecast` means the feed published none. It stays the empty string.
Coercing it to 0 would invent a number the calendar never printed.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from .providers.base import ProviderError
from .providers.sources import _get_json

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# There is deliberately NO `IMPACTS` whitelist here. The live sample showed three
# labels (8 High / 15 Medium / 75 Low) and a constant naming them existed for a
# while, unread: the only filter menu in the product is in the frontend, which
# keeps its own list, and a label outside the tuple was passed through anyway -
# dropping a real row to protect a constant would be the reader lying about the
# calendar. A constant that no caller reads and no code enforces is documentation
# pretending to be a type.

# CHOSEN, NOT MEASURED. A weekly schedule changes rarely - a time revision or a
# new forecast, a few times a day at most - and fifteen minutes is a guess at
# where freshness stops being worth the traffic. Nobody here has measured how
# often the feed actually changes.
#
# The need for a cache, though, IS measured. Three requests inside two minutes
# on 2026-08-19 were answered with HTTP 429 and an HTML page titled "Rate
# Limited": the first returned all 98 rows, the third and fourth returned
# nothing. The host's actual threshold is unknown - it was found by crossing it
# once, not by probing for it - so an uncached read on every chart redraw would
# not merely be rude, it would fail.
CACHE_TTL_SECONDS = 900


@dataclass(frozen=True)
class NewsEvent:
    """One scheduled release. No outcome, because the feed publishes none."""

    time: int  # epoch seconds, converted from the ROW'S OWN UTC offset
    title: str
    currency: str  # the feed's `country`, which holds a currency code
    impact: str  # the feed's own attention label, verbatim; see module docstring
    forecast: str  # "" means the feed published none - NOT zero
    previous: str  # "" means the feed published none - NOT zero


@dataclass(frozen=True)
class NewsWeek:
    """The events, the window they actually cover, and what went wrong.

    `covers_from`/`covers_to` are read off the parsed rows, never assumed to be
    seven days: the feed is "this week" by the publisher's reckoning, and this
    engine has no business inventing its edges. Both are None when nothing
    parsed, which is the honest answer to "what does this cover".
    """

    events: tuple[NewsEvent, ...]
    covers_from: int | None
    covers_to: int | None
    error: str = ""  # non-empty means the feed could not be read, and says why
    skipped: tuple[str, ...] = ()  # rows refused, one reason each, never silent


def _text(value: object) -> str:
    """A feed field as text. Absent stays absent; it never becomes a number."""
    return "" if value is None else str(value).strip()


def parse(rows: object) -> NewsWeek:
    """Turn the decoded feed into events. Bad rows are skipped, not fatal.

    A single malformed row must not cost the other ninety-seven. The reason is
    kept per row so a shape change upstream shows up as text rather than as a
    calendar that quietly got shorter.
    """
    if not isinstance(rows, list):
        return NewsWeek((), None, None, error=f"feed was {type(rows).__name__}, not a list")

    events: list[NewsEvent] = []
    skipped: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            skipped.append(f"row {index}: {type(row).__name__}, not an object")
            continue
        stamp = _text(row.get("date"))
        try:
            when = datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            skipped.append(f"row {index}: unreadable date {stamp!r}")
            continue
        # A naive timestamp is REFUSED, not defaulted. The whole point of this
        # module is that the offset comes from the data; a row without one is a
        # row whose instant nobody knows.
        if when.utcoffset() is None:
            skipped.append(f"row {index}: date {stamp!r} carries no UTC offset")
            continue
        title = _text(row.get("title"))
        if not title:
            skipped.append(f"row {index}: no title")
            continue
        events.append(
            NewsEvent(
                time=int(when.timestamp()),
                title=title,
                currency=_text(row.get("country")).upper(),
                impact=_text(row.get("impact")),
                forecast=_text(row.get("forecast")),
                previous=_text(row.get("previous")),
            )
        )

    events.sort(key=lambda e: e.time)
    return NewsWeek(
        events=tuple(events),
        covers_from=events[0].time if events else None,
        covers_to=events[-1].time if events else None,
        skipped=tuple(skipped),
    )


def select(
    events: Iterable[NewsEvent],
    *,
    impact: str | Iterable[str] | None = None,
    currency: str | Iterable[str] | None = None,
) -> tuple[NewsEvent, ...]:
    """Filter by the feed's impact label and by currency, case-insensitively.

    NO DEFAULT FILTER, and that is a decision rather than an oversight: keeping
    only High rows by default would be this module ranking the feed's labels,
    and nobody here has measured that a High row matters more than a Low one.
    The caller chooses; `None` means everything.
    """
    wanted_impact = _folded(impact)
    wanted_currency = _folded(currency)
    return tuple(
        e
        for e in events
        if (wanted_impact is None or e.impact.casefold() in wanted_impact)
        and (wanted_currency is None or e.currency.casefold() in wanted_currency)
    )


def _folded(value: str | Iterable[str] | None) -> set[str] | None:
    if value is None:
        return None
    # A bare string is one name, not a set of letters. Without this, passing
    # "High" would filter on {"h","i","g","h"} and match nothing.
    names = [value] if isinstance(value, str) else list(value)
    return {name.casefold() for name in names}


# (fetched_at_monotonic, week) - the same shape as the provider cache in
# `providers/__init__.py`, held behind the same kind of lock so a burst of
# redraws makes one upstream call rather than twelve.
_cache: tuple[float, NewsWeek] | None = None
_lock = asyncio.Lock()


async def read(ttl_seconds: int = CACHE_TTL_SECONDS) -> NewsWeek:
    """The current week's calendar, memoised for `ttl_seconds`.

    An unreachable feed returns an EMPTY week carrying the upstream's own words
    in `error`, the same way a provider failure surfaces its reason instead of
    an empty chart. That failure is cached too: an outage must not turn every
    chart redraw into a retry against a host already struggling. The cost is
    that recovery is noticed up to one TTL late, which is the cheaper mistake.
    """
    global _cache
    async with _lock:
        if _cache and time.monotonic() - _cache[0] < ttl_seconds:
            return _cache[1]
        try:
            week = parse(await _get_json(FEED_URL))
        except ProviderError as exc:
            week = NewsWeek((), None, None, error=str(exc))
        _cache = (time.monotonic(), week)
        return week
