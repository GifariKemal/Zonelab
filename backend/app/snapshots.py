"""What the screen said, at the second somebody decided to act on it.

WHY THIS IS NOT A DRAW ENDPOINT. `/api/draw` answers "what is true now". This
answers "what did the reader SEE", and those are different questions the moment a
tick lands between them. So a snapshot never re-derives the market data: the
client posts back the exact response body it is displaying, verbatim, and this
module writes it down with a clock reading beside it. Re-drawing would produce a
snapshot of a chart nobody ever looked at, which is worse than no snapshot,
because it would be indistinguishable from one that was real.

THE LAGS, AND WHY THEY ARE FOUR FIELDS RATHER THAN ONE. An audit weeks later has
to be able to say whether the picture on screen matched the broker's tape at that
second, and there are three independent things that could have been true - one of
which looks alarming and is not:

  1. INTRA-BAR POSITION. `meta.feed_lag_seconds` is `now - bar_closed_at`, so on
     a 15-minute chart it runs 0 to 900 purely because time passes inside the bar
     being formed. The first run of this module measured 558 seconds and nothing
     was wrong at all: that was nine minutes into a fifteen-minute bar. Read as
     staleness it would have looked like a nine-minute-old chart.
  2. OVERDUE. Anything BEYOND one whole bar is the real staleness signal: a bar
     that should have closed and has not arrived means the feed is behind. This
     is the provider's, and dukascopy has been seen 59 minutes out.
  3. SCREEN STALENESS, measured here for the first time: server answer to
     snapshot. A chart left open for eleven minutes while somebody thought about
     it is eleven minutes old, and the response cannot know that - only the
     moment of the snapshot can.

`total_seconds` is 2 plus 3 and deliberately EXCLUDES 1, because being nine
minutes into a fifteen-minute bar is not being behind, it is being where the
clock is. All four are stored so the total can always be decomposed again, and so
nobody has to remember which of them to add.

NOTHING HERE IS SCORED, AND NOTHING IS AN OUTCOME. A snapshot holds no entry, no
exit, no profit and no verdict, because Zonelab does not execute and must not
pretend to know what happened next. It is the left-hand side of an audit: what
the engine said. The right-hand side is whatever the reader did, and that lives
in a broker statement, not here. Joining them is the point of keeping this.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Where snapshots land. Beside the price cache rather than in it: both are
#: local state that must never be committed, but a cache can be deleted freely
#: and this cannot - a deleted snapshot is a deleted observation.
DIRECTORY = Path(__file__).resolve().parent.parent / ".snapshots"

#: Cap on how many are listed at once. A weekly review reads tens, not
#: thousands, and an unbounded listing would read every file on the disk to
#: answer one request.
LIST_LIMIT = 200


@dataclass(frozen=True)
class Lag:
    """How far behind the tape a decision was, split by cause.

    FOUR NUMBERS, NOT ONE, and the split is the whole value of the record. Stored
    rather than derived on read, because a number recomputed by a later version
    of this file is not the same evidence as one written down at the time.

    `feed_seconds` IS NOT STALENESS ON ITS OWN, and reading it as staleness is the
    trap this class exists to close. It is `now - bar_closed_at`, so on a healthy
    15-minute chart it runs 0 to 900 simply because time passes inside the bar
    being formed: a first run of this measured 558 seconds and nothing was wrong -
    that was nine minutes into a fifteen-minute bar. Splitting it:

      - `intra_bar_seconds`: how far into the forming bar, capped at one bar.
        Normal, unavoidable, and says nothing about the provider.
      - `overdue_seconds`: how much MORE than one whole bar has passed. This is
        the real staleness signal, because a bar that should have closed and has
        not arrived means the feed is behind. Zero on a healthy feed at any
        moment inside the bar.
      - `screen_seconds`: server answer to snapshot, the reader's own delay.

    An audit weeks later asks "did the screen match the broker's tape". The
    answer is `overdue_seconds + screen_seconds`; `intra_bar_seconds` is context
    and must not be added to it, which is exactly why it is a separate field
    rather than folded into a single total that nobody could decompose again.
    """

    feed_seconds: int
    intra_bar_seconds: int
    overdue_seconds: int
    screen_seconds: int
    total_seconds: int


def measure_lag(meta: dict[str, Any], taken_at: int) -> Lag:
    """The two lags, from the response's own provenance and the snapshot clock.

    `fetched_at` is when the SERVER answered, so `taken_at - fetched_at` is how
    long the reader sat with that answer. Clamped at zero: a client clock ahead
    of the server's would otherwise produce a negative staleness, which would
    read as the future and is never information.

    A response with no `fetched_at` - an older client, a hand-made body - yields
    a screen staleness of zero rather than a guess, and the feed lag likewise.
    Zero here means UNKNOWN, and the caller can tell it apart from a real zero by
    the absence of the field it came from.
    """
    feed = int(meta.get("feed_lag_seconds") or 0)
    fetched = int(meta.get("fetched_at") or 0)
    screen = max(0, taken_at - fetched) if fetched else 0

    # The bar's own length, read from the two boundaries the response already
    # carries rather than from an interval table - so this stays right if a new
    # interval is added and nothing here has to learn about it.
    closed = int(meta.get("bar_closed_at") or 0)
    nxt = int(meta.get("next_close_at") or 0)
    step = nxt - closed if nxt > closed else 0
    intra = min(feed, step) if step else 0
    overdue = max(0, feed - step) if step else 0

    # TOTAL EXCLUDES `intra_bar`, deliberately. Being nine minutes into a
    # fifteen-minute bar is not being behind; it is being where the clock is.
    return Lag(
        feed_seconds=feed,
        intra_bar_seconds=intra,
        overdue_seconds=overdue,
        screen_seconds=screen,
        total_seconds=overdue + screen,
    )


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    """The few numbers a listing needs, so a review does not read every body.

    Deliberately thin. Anything a reader might argue about lives in the full
    file, and a summary that grew until it could be argued with would just be a
    second copy of the response with a chance to disagree with the first.
    """
    drawing = payload.get("response", {}).get("drawing", {}) or {}
    drawn = {
        name: len(objects)
        for name, objects in drawing.items()
        if isinstance(objects, list) and objects
    }
    return {
        "id": payload["id"],
        "taken_at": payload["taken_at"],
        "note": payload["note"],
        "symbol": payload["response"].get("symbol"),
        "interval": payload["response"].get("interval"),
        "provider": payload["response"].get("provider"),
        "layers": sorted(drawn),
        "objects": sum(drawn.values()),
        "plans": len(payload["response"].get("plans") or []),
        "lag": payload["lag"],
    }


def save(response: dict[str, Any], note: str) -> dict[str, Any]:
    """Write one snapshot and return its summary.

    The response is stored EXACTLY as given. No field is recomputed, dropped or
    reordered, because the value of this file is that it is the same bytes the
    reader was looking at - and a snapshot this module had edited would be
    evidence about this module rather than about the market.
    """
    taken_at = int(time.time())
    meta = response.get("meta") or {}
    lag = measure_lag(meta, taken_at)
    # The id carries the instant and the instrument, so a directory listing is
    # already sorted and already readable without opening anything.
    symbol = str(response.get("symbol") or "unknown").replace("/", "-")
    interval = str(response.get("interval") or "?")
    payload = {
        "id": f"{taken_at}-{symbol}-{interval}",
        "taken_at": taken_at,
        "note": note,
        "lag": {
            "feed_seconds": lag.feed_seconds,
            "intra_bar_seconds": lag.intra_bar_seconds,
            "overdue_seconds": lag.overdue_seconds,
            "screen_seconds": lag.screen_seconds,
            "total_seconds": lag.total_seconds,
        },
        "response": response,
    }
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = DIRECTORY / f"{payload['id']}.json"
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return _summary(payload)


def listing() -> list[dict[str, Any]]:
    """Every snapshot's summary, newest first.

    A file that cannot be parsed is skipped and NOT counted, rather than taking
    the listing down: these are hand-editable observations on a local disk, and
    one broken file must not hide the rest of a review.
    """
    if not DIRECTORY.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(DIRECTORY.glob("*.json"), reverse=True)[:LIST_LIMIT]:
        try:
            out.append(_summary(json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return out


def read(snapshot_id: str) -> dict[str, Any] | None:
    """One snapshot in full, or None.

    The id is checked against the directory listing rather than joined onto the
    path, so a caller cannot walk out of it with dots or slashes. That matters
    even on a local-only API: this is a filesystem read driven by a request
    body, which is the shape every path-traversal bug has.
    """
    if not DIRECTORY.exists():
        return None
    for path in DIRECTORY.glob("*.json"):
        if path.stem == snapshot_id:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
    return None
