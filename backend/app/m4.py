"""M4 Judas window definition.

The Judas window is 09:30-10:30 New York. This module defines it once, so
`tools/conditioned.py` and `tools/quant.py` share a single source of truth
rather than each carrying the same two numbers.
"""

from __future__ import annotations

from datetime import datetime

#: NY time the Judas window opens. Before this, NO entry signals are valid.
JUDAS_OPEN_HOUR = 9
JUDAS_OPEN_MINUTE = 30

#: NY time the Judas window closes. After this, the engine may scan for triggers.
JUDAS_CLOSE_HOUR = 10
JUDAS_CLOSE_MINUTE = 30


def in_judas_window(when: datetime) -> bool:
    """Is `when` inside the Judas window, on ITS OWN clock.

    Exists so the window has one definition. `tools/quant.py` carried the same
    two numbers written out by hand, which is how a revision here would have left
    the measurement arm silently scanning the old hours. Takes an aware datetime
    already in New York rather than converting: the caller has the bar time and
    the zone, and converting twice is how an off-by-an-hour appears at a DST edge.
    """
    hour, minute = when.hour, when.minute
    after_open = hour > JUDAS_OPEN_HOUR or (
        hour == JUDAS_OPEN_HOUR and minute >= JUDAS_OPEN_MINUTE
    )
    before_close = hour < JUDAS_CLOSE_HOUR or (
        hour == JUDAS_CLOSE_HOUR and minute <= JUDAS_CLOSE_MINUTE
    )
    return after_open and before_close
