"""Why the engine acted, written down at the moment it acted.

`deduce.py` ends on a promise this module keeps: "Scoring is a later join against
a broker statement." The join needs one side of itself to exist first, and until
2026-08-21 it did not - there was no record anywhere tying a broker ticket to the
zone it came from, the plan that sized it, or the evidence that let it through.

WHAT THIS IS NOT. It is not `snapshots.py`. A snapshot is the whole picture, 2.6
MB of it, and answers "what did the reader see". This answers "what did the
engine DO, and on what grounds", in one greppable line per event, and points at
a snapshot for the picture rather than copying it.

THREE FIELDS CARRY THE WHOLE ARGUMENT, and none of them is optional:

  `why`       the measured grounds, each item carrying its own number. An empty
              `why` on a placed order is a bug, not a terse record: it means
              something acted for reasons it could not state.
  `blockers`  what `actionable.blockers` found. Recorded even when empty, and
              recorded on a REFUSAL too, because "we refused and here is the
              string" is the only form of that event worth keeping.
  `rule`      which decision procedure produced this. A journal without it can
              tell you what happened and never why the answer changed between
              March and August, which is the question a review actually asks.

APPEND ONLY, AND ONE LINE PER EVENT. No record is ever rewritten: an order that
fills later gets a SECOND line naming the same ticket rather than an edit to the
first. A log that can be edited in place cannot be evidence about the moment it
describes - and the fill is a different moment from the decision, with a
different price and a different reason to exist.

NEVER COMMITTED. `.journal/` holds account state and personal decisions, exactly
like `.snapshots/`, and is ignored for the same reason.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DIRECTORY = Path(__file__).resolve().parent.parent / ".journal"

#: One file per UTC day, so a review reads a day without parsing a year and an
#: append never rewrites a file that has grown large.
def _path(at: int) -> Path:
    day = time.strftime("%Y-%m-%d", time.gmtime(at))
    return DIRECTORY / f"{day}.jsonl"


#: `armed` and `disarmed` are here because flipping the auto-trade switch is an
#: audit-worthy act: it is the moment a human decided the engine could trade
#: unattended, and a review that can see the orders but not that decision is
#: reading half the story.
EVENTS = ("placed", "refused", "filled", "closed", "cancelled", "armed", "disarmed")


def record(
    event: str,
    *,
    why: list[str],
    rule: dict[str, Any],
    blockers: list[str] | None = None,
    zone_id: str | None = None,
    ticket: int | None = None,
    plan: dict[str, Any] | None = None,
    snapshot_id: str | None = None,
    extra: dict[str, Any] | None = None,
    at: int | None = None,
) -> dict[str, Any]:
    """Append one event and return the record as written.

    Raises on an unknown event and on a `placed` with no `why`. Both are
    programmer errors and both are silent disasters if allowed through: the first
    makes the log unreadable by category, the second produces an order whose
    grounds are the empty list.
    """
    if event not in EVENTS:
        raise ValueError(f"unknown event {event!r}, expected one of {EVENTS}")
    if event == "placed" and not why:
        raise ValueError(
            "a placed order must carry its grounds; an empty `why` means "
            "something acted for reasons it could not state"
        )
    if not rule:
        raise ValueError("every record needs its rule version, see the docstring")

    entry = {
        "at": int(time.time()) if at is None else at,
        "event": event,
        "zone_id": zone_id,
        "ticket": ticket,
        "plan": plan,
        "why": why,
        "blockers": list(blockers or []),
        "rule": rule,
        "snapshot_id": snapshot_id,
        "extra": extra or {},
    }
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = _path(entry["at"])
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def entries(day: str | None = None) -> list[dict[str, Any]]:
    """Every record, oldest first. `day` is `YYYY-MM-DD`; None reads all days.

    A line that will not parse is SKIPPED AND COUNTED nowhere, the same rule
    `snapshots.listing` follows: these files are hand-editable and one bad line
    must not take a review down.
    """
    if not DIRECTORY.exists():
        return []
    files = [DIRECTORY / f"{day}.jsonl"] if day else sorted(DIRECTORY.glob("*.jsonl"))
    out: list[dict[str, Any]] = []
    for path in files:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return sorted(out, key=lambda e: e.get("at", 0))


def for_zone(zone_id: str) -> list[dict[str, Any]]:
    """Every event about one zone, which is what idempotency asks about.

    Keyed on the zone rather than on the ticket on purpose: before an order
    exists there is no ticket, and "have I already acted on this zone" is a
    question that has to be answerable at exactly that moment.
    """
    return [e for e in entries() if e.get("zone_id") == zone_id]


def for_ticket(ticket: int) -> list[dict[str, Any]]:
    """Every event about one broker ticket, which is what scoring asks about."""
    return [e for e in entries() if e.get("ticket") == ticket]
