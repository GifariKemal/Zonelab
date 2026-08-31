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


def market_shut(epoch: int, always_open: bool = False) -> bool:
    """Is the market shut at this instant, on the CME futures week?

    `always_open` short-circuits to False, for an instrument whose own bars say
    it trades through the CME week. Default False, so every existing caller -
    `app/gaps.py` reads its NDOG and NWOG off this - keeps the answer it had.

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
    if always_open:
        return False
    when = to_ny(epoch)
    if when.hour == 17:
        return True
    weekday = when.weekday()  # Monday 0 .. Sunday 6
    if weekday == 5:  # all Saturday
        return True
    if weekday == 4 and when.hour >= 17:  # Friday evening onward
        return True
    return weekday == 6 and when.hour < 18  # Sunday before the reopen


#: Bagian bar terkecil di dalam jendela tutup yang sudah dianggap bukti bahwa
#: instrumennya dagang saat pasar CME tutup.
#:
#: Diukur 30 Agustus 2026 pada 2000 bar per deret, `market_shut` per bar:
#:
#:   mt5:XAUUSD 1h   0 dari 2000 (0,0%)     15m   0 dari 2000 (0,0%)
#:   mt5:BTCUSD 1h 621 dari 2000 (31,1%)    15m 620 dari 2000 (31,0%)
#:   mt5:ETHUSD 1h 621 dari 2000 (31,1%)    15m 620 dari 2000 (31,0%)
#:
#: Nol lawan 31 persen, jadi ambangnya boleh di mana saja di antaranya dan 5
#: persen jauh dari keduanya. Ia ada supaya satu bar nyasar di batas 17:00
#: tidak membalik jawabannya.
WEEKEND_BAR_SHARE = 0.05


def trades_when_shut(times: list[int], floor: float = WEEKEND_BAR_SHARE) -> bool:
    """Apakah instrumen ini dagang saat minggu CME bilang pasar tutup.

    DIUKUR DARI DERETNYA SENDIRI, bukan dari daftar ticker. Daftar ticker harus
    dirawat, dan yang lupa dirawat tetap menjawab dengan yakin; deret bar tidak
    bisa bohong soal jam berapa ia ada.

    JANGAN PAKAI `weekday() >= 5` UNTUK INI. Emas punya 102 bar akhir pekan pada
    2000 bar 1h, karena CME buka lagi Minggu 18:00 NY, jadi cek "ada bar Sabtu
    atau Minggu" menandai emas sebagai instrumen 24/7. Yang memisahkan adalah
    bar DI DALAM jendela tutup, dan di sana emas nol.
    """
    if not times:
        return False
    hits = sum(1 for t in times if market_shut(int(t)))
    return hits / len(times) >= floor
