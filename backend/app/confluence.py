"""Higher-timeframe nesting.

The one multi-timeframe claim every school of this method agrees on: a
lower-timeframe zone sitting inside a higher-timeframe zone of the same side is
worth more than one standing alone. Seiden puts it as "every smaller timeframe
zone is in context to a larger timeframe zone"; the ICT and SMC literature says
the same thing in different words.

It is also, as far as the published record goes, **never quantified**. So it is
computed here and reported, and `tools/calibrate.py` measures it rather than
assuming it.

The causal condition is what makes the measurement honest. An HTF zone that
formed *after* the LTF zone could not have provided confluence at the time, and
counting it would be reading the answer off the future.
"""

from __future__ import annotations

from .models import Zone


CONTAINMENT = 0.8


def mark_nesting(local: list[Zone], higher: list[Zone]) -> None:
    """Stamp each local zone with the higher-timeframe zones enclosing it.

    Mutates in place. Four conditions, and the strictness of the first is the
    whole point:

    1. **Contained, not merely touching.** At least `CONTAINMENT` of the local
       zone's height must lie inside the higher one. Testing for any overlap at
       all marks nearly every zone as nested, because a higher-timeframe zone
       is several times taller, and a condition satisfied by 97% of cases
       cannot distinguish anything.
    2. Same side. A demand zone inside a supply zone is a conflict, not
       confluence.
    3. The higher zone formed strictly earlier. One born later is hindsight;
       one born on the same bar is the same event counted twice.
    4. The higher zone was still alive. A zone price already broke offers no
       context to something forming after it.
    """
    for zone in local:
        height = zone.top - zone.bottom
        if height <= 0:
            continue

        zone.nested_in = sorted(
            {
                other.timeframe
                for other in higher
                if other.side is zone.side
                and other.time_from < zone.time_from
                and other.time_to >= zone.time_from
                and (min(zone.top, other.top) - max(zone.bottom, other.bottom))
                >= CONTAINMENT * height
            }
        )
