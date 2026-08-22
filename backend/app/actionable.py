"""May this drawing be acted on? The refusals, in one place.

A drawing is FIT TO READ under conditions that are looser than the conditions
that make it fit to ACT ON, and until 2026-08-21 nothing in this project drew
that line. `drawing.py` has stamped `truncated_by_provider` into every response
since the field was born and NOTHING ever read it: a source that could only
return 400 of the 1000 bars asked for drew a shorter chart that looked exactly
like a quiet market, and any automation reading that response would have placed
an order against zones that were missing rather than absent.

WHY REFUSALS AND NOT A SCORE. A score invites a threshold, a threshold invites
tuning, and a tuned threshold is a parameter fitted to whatever went wrong last.
Each blocker below is a fact with a number attached, and the caller either has
none or does not act. Nothing here is weighted against anything else.

WHY IT RETURNS STRINGS. They go straight into the decision journal beside the
order, so the record says why the engine acted or refused in the words the check
itself used, rather than as a flag that has to be decoded a month later.

WHAT IS DELIBERATELY NOT HERE. Anything about whether the trade is a good idea:
that is `plan.py` (geometry and risk) and the gates in `docs/CALIBRATION.md`
(whether the formation is worth anything). This module only answers whether the
PICTURE is sound enough to be acted on at all.
"""

from __future__ import annotations

import time as _time

from .providers.base import INTERVALS


def blockers(response: dict, now: int | None = None) -> list[str]:
    """Reasons this response must not be traded from. Empty means none found.

    `now` is injectable so a test can pin the clock; production passes nothing.
    """
    out: list[str] = []
    meta = response.get("meta") or {}
    candles = response.get("candles") or []

    if not meta:
        return ["no meta block: this is not a /api/draw response"]
    if not candles:
        return ["no candles: there is nothing drawn to act on"]

    requested = meta.get("bars_requested")
    returned = meta.get("bars_returned")
    if meta.get("truncated_by_provider"):
        # BOTH counts, because "400" alone reads as a quiet market and
        # "400 of 1000" reads as a missing history. That distinction is the whole
        # reason the field exists.
        out.append(
            f"history truncated by the provider: {returned} of {requested} bars. "
            "A zone that is missing because its bars are missing cannot be told "
            "apart from a zone that never formed"
        )

    interval = response.get("interval")
    step = INTERVALS.get(interval) if isinstance(interval, str) else None
    if step is None:
        out.append(f"unknown interval {interval!r}, so staleness cannot be judged")
    else:
        # `feed_lag_seconds` is measured from the newest bar's CLOSE, so a lag
        # anywhere inside one interval is the normal state of a live chart: the
        # next bar has simply not finished. Beyond one full interval a close has
        # been missed, and the picture is describing a bar that is no longer the
        # last one. Recomputed from `as_of` rather than trusted, because the
        # stamped figure is as old as the response and this question is about now.
        as_of = int(meta.get("as_of") or 0)
        lag = max(0, (now if now is not None else int(_time.time())) - (as_of + step))
        if lag > step:
            out.append(
                f"feed is {lag}s behind on a {step}s interval, so at least one "
                "bar has closed since this was drawn"
            )

    return out
