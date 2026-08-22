"""New York wall clock, because the quarter grid is stated in wall clock.

Every boundary the quarter grid uses (18:00, 00:00, 06:00, 12:00) is a
*New York local* time, so each one has to be built from wall-clock fields and
then converted to an instant, never from a constant offset added to UTC. New
York runs UTC-5 in winter and UTC-4 in summer. An implementation that hard-codes
either one is exactly right for part of the year and silently an hour wrong for
the rest, and nothing on the chart says which half you are looking at - the
levels just sit an hour off. That is the failure this module exists to prevent,
and `tests/test_quarters.py` asserts it directly on both transition days.

stdlib `zoneinfo` only, no dependency added. On Windows `zoneinfo` reads the
`tzdata` package instead of a system tz database; it is already present in this
venv, and if it were missing `ZoneInfo` raises at construction rather than
quietly falling back to a wrong offset.

One PEP 495 caveat, stated rather than handled: wall times inside a DST
transition are ambiguous (fall back) or non-existent (spring forward). US
transitions happen at 02:00 local, and no boundary in `quarters.py` is built at
an hour between 02:00 and 03:00, so the question never arises here. `fold=0`
(the first of the two passes) applies if a caller ever asks for one.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def to_ny(epoch: int) -> datetime:
    """The New York wall clock at `epoch`, timezone-aware."""
    return datetime.fromtimestamp(epoch, NY)


def to_epoch(when: datetime) -> int:
    """Epoch seconds for an aware datetime."""
    return int(when.timestamp())


def ny_wall(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    """Epoch seconds of a New York wall-clock date and time."""
    return to_epoch(datetime(year, month, day, hour, minute, tzinfo=NY))


def at_ny_hour(epoch: int, hour: int, days: int = 0) -> int:
    """`hour`:00 New York on the New York calendar date of `epoch`, shifted `days`."""
    day = to_ny(epoch).date() + timedelta(days=days)
    return ny_wall(day.year, day.month, day.day, hour)


def add_ny_days(epoch: int, days: int) -> int:
    """Same wall-clock time, `days` calendar days later.

    Not `epoch + days * 86400`: across a transition a calendar day is 23 or 25
    hours, so adding seconds moves the wall clock and would slide the grid.
    """
    wall = to_ny(epoch).replace(tzinfo=None) + timedelta(days=days)
    return to_epoch(wall.replace(tzinfo=NY))


def market_shut(epoch: int) -> bool:
    """Is the market shut at this instant, on the CME futures week?

    Shut from 17:00 New York Friday to 18:00 Sunday, and for the one-hour daily
    maintenance break from 17:00 to 18:00 on the other weekdays. Those are the
    same boundaries `app/gaps.py` reads its NDOG and NWOG off.

    HERE RATHER THAN IN `providers/synthetic.py`, where it lived until
    2026-08-21. Two tests needed the same predicate that night - one asking why
    there was no forming bar, one asking why an MT5 bar was two hours old - and
    the alternative to moving it was a second and a third copy of the CME week.
    Both tests had already been written against a market that never closes, and
    both failed on a Friday evening for that reason alone.
    """
    when = to_ny(epoch)
    if when.hour == 17:
        return True
    weekday = when.weekday()  # Monday 0 .. Sunday 6
    if weekday == 5:  # all Saturday
        return True
    if weekday == 4 and when.hour >= 17:  # Friday evening onward
        return True
    return weekday == 6 and when.hour < 18  # Sunday before the reopen
