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
#:
#: `corrected` EXISTS BECAUSE THIS LOG IS APPEND-ONLY AND A `why` CAN BE WRONG.
#: On 2 September 2026 two orders were placed on `order_block` zones whose
#: grounds cited the `supply_demand` numbers - the departure gate at +0.1105 R
#: and a 2R hit rate of 36.8 per cent - because the prefix `OB` was read as a
#: supply/demand box. Re-measured per detector with the display cap OFF
#: (`ImbalanceParams.max_zones_per_side` defaults to 6, so 50,000 bars first
#: answered with twelve boxes), order_block at a fixed 2R came out +0.0827 R at
#: t=+3.32 on XAUUSD and +0.0754 R at t=+3.01 on BTCUSD, both 4 of 4 folds
#: same-signed - a STRONGER population than the one quoted, not a weaker one.
#:
#: There was no way to say that here. Editing the `placed` line was never an
#: option: `test_a_fill_is_a_second_line_and_never_an_edit` states the rule, and
#: a record that can be rewritten is not evidence. Cancelling and re-sending
#: would have bought a correct `why` with two extra tickets and a re-entry at a
#: level the account already held.
#:
#: NO CONSUMER READS IT, and that is deliberate rather than incidental: every
#: reader in this repo filters on `event == "placed"` (`autotrade.py:209`,
#: `execute.py:686`, `flatten.py:182`, `stress_decision.py:125`), so adding this
#: name cannot change what any tool decides. It carries `ticket` so
#: `for_ticket` prints it beside the record it corrects.
EVENTS = ("placed", "refused", "filled", "closed", "cancelled", "armed",
          "disarmed", "corrected")


def record(
    event: str,
    *,
    why: list[str],
    rule: dict[str, Any],
    blockers: list[str] | None = None,
    zone_id: str | None = None,
    symbol: str | None = None,
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
        "symbol": symbol,
        "ticket": ticket,
        "plan": plan,
        "why": why,
        "blockers": list(blockers or []),
        "rule": rule,
        "snapshot_id": snapshot_id,
        "extra": extra or {},
    }
    # A refusal carries no order geometry worth keeping. `why` already names the
    # target and reward, and `plan` is write-only everywhere in this repo (no
    # code reads it back). It is the single largest term in a day's journal
    # growth: 16,561 refusals on 31 August 2026, ~1 KB of plan each. Dropping it
    # here, at the one place every refusal routes through, fixes all five
    # `refused` call sites at once instead of editing each.
    if event == "refused":
        entry.pop("plan", None)
    key_before = _stat_key()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = _path(entry["at"])
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    _append_to_cache(entry, key_before)
    return entry


def _append_to_cache(entry: dict[str, Any],
                     key_before: tuple[tuple[str, int, int], ...]) -> None:
    """Keep the in-memory cache current after this process writes a record.

    `entries()` memoizes its parse keyed on file stat. A record appended by THIS
    process must show up in the next `entries()` without forcing a re-parse of
    the whole (now large) journal, or a live cycle that interleaves one read
    with one write re-parses the journal once per candidate.

    `key_before` is the stat key captured in `record` BEFORE the append, so the
    append is skipped unless the cache was built from this very directory and
    file state. Without that guard a cache warmed by one directory (a test's
    monkeypatched `DIRECTORY`) leaks its entries into the next test's records.
    """
    global _cache_key
    if _cache is None or _cache_key != key_before:
        return
    _cache.append(entry)
    _cache.sort(key=lambda e: e.get("at", 0))
    _cache_key = _stat_key()


#: Cache dari parse terakhir seluruh journal, dan key stat file yang
#: menghasilkannya. `for_zone` dan `for_ticket` dipanggil sekali per kandidat di
#: loop kandidat `execute.py`, dan sampai 30 Agustus 2026 keduanya men-scan ulang
#: seluruh `.journal` tiap panggilan. Saat journal tumbuh ke 113 MB (hari itu 62
#: MB), 36 kandidat berarti 36 scan = ~160 detik per cycle, padahal `STALE_AFTER`
#: cuma 60 detik, jadi `daemon_alive` selalu False di atas daemon yang hidup.
#: Cache-nya di-invalidate oleh perubahan stat file (mtime/size), dan `record`
#: menambah ke cache alih-alih memaksa re-scan, supaya cycle live yang menyelingi
#: satu baca dengan satu tulis tidak re-scan 36 kali.
_cache: list[dict[str, Any]] | None = None
_cache_key: tuple[tuple[str, int, int], ...] | None = None


def _stat_key() -> tuple[tuple[str, int, int], ...]:
    if not DIRECTORY.exists():
        return ()
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size)
                 for p in sorted(DIRECTORY.glob("*.jsonl")))


def _read(paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in paths:
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


def entries(day: str | None = None) -> list[dict[str, Any]]:
    """Every record, oldest first. `day` is `YYYY-MM-DD`; None reads all days.

    A line that will not parse is SKIPPED AND COUNTED nowhere, the same rule
    `snapshots.listing` follows: these files are hand-editable and one bad line
    must not take a review down.
    """
    if day is not None:
        return _read([DIRECTORY / f"{day}.jsonl"])
    global _cache, _cache_key
    key = _stat_key()
    if _cache is None or _cache_key != key:
        _cache = _read(sorted(DIRECTORY.glob("*.jsonl")) if DIRECTORY.exists()
                       else [])
        _cache_key = key
    return _cache


def for_zone(zone_id: str, symbol: str | None = None) -> list[dict[str, Any]]:
    """Every event about one zone, which is what idempotency asks about.

    Keyed on the zone rather than on the ticket on purpose: before an order
    exists there is no ticket, and "have I already acted on this zone" is a
    question that has to be answerable at exactly that moment.

    AND ON THE SYMBOL, because a zone id does not carry one. Ids are built as
    `f"{kind}-{bar_time}"` in both detector modules, so two instruments that form
    the same kind of zone on the same bar get the SAME id: measured on a 400-bar
    1h window, gold and silver shared four. Without the symbol, gate 5 in
    `tools/execute.py` suppressed a silver trade because gold already had an order
    from its own zone, and reported it as "already ordered, ticket N" - a silent
    skip wearing the words of correct behaviour, on the basket
    `.autotrade.json` was actually configured for.

    A RECORD WITH NO SYMBOL MATCHES ANY SYMBOL, and that is deliberate rather
    than lazy. Entries written before this field existed cannot say which
    instrument they were for, so treating them as ambiguous keeps the
    conservative answer: an order that may already exist is not placed twice.
    New records carry the symbol and are scoped exactly.
    """
    out = []
    for e in entries():
        if e.get("zone_id") != zone_id:
            continue
        if symbol is not None and e.get("symbol") not in (None, symbol):
            continue
        out.append(e)
    return out


def open_tickets(zone_id: str, symbol: str | None = None) -> list[int]:
    """Ticket `placed` untuk zona ini yang BELUM dicatat mati.

    KENAPA INI ADA. Gate idempotensi di `tools/execute.py` menyaring
    `event == "placed"` saja, jadi sebuah zona yang order-nya sudah DIBATALKAN
    tetap terkunci selamanya, dan penolakannya berbunyi "SUDAH pernah diorder,
    ticket N" - kalimat yang persis dipakai docstring `for_zone` di atas untuk
    menggambarkan cacat lain di gate yang sama. Diukur 2 September 2026: 35 zona
    punya record `placed` dan 29 di antaranya TIDAK punya satu pun ticket yang
    masih hidup di broker.
    Dari 29 itu, 13 punya record `cancelled` atau `closed` di journal ini dan 16
    tidak punya catatan kematian sama sekali - ticket-nya hilang dari broker
    tanpa journal pernah tahu, misalnya dibatalkan langsung di terminal.

    JADI FUNGSI INI MENJAWAB SEPARUHNYA, dan separuhnya saja. Ia membaca apa
    yang JOURNAL tahu: sebuah `placed` yang diikuti `cancelled` atau `closed`
    dengan ticket yang sama sudah tidak mengunci apa pun. Untuk 16 sisanya
    journal memang tidak tahu, dan jawabannya harus datang dari order book
    broker, yang dipegang pemanggilnya. `tools/execute.py` memotongnya lagi
    dengan daftar ticket hidup ketika terminalnya terbaca.

    URUTAN TIDAK DIANDALKAN. `cancelled` bisa tercatat di file hari yang berbeda
    dari `placed`-nya, dan `entries()` membaca per hari, jadi yang dipakai
    kesamaan TICKET dan bukan posisi barisnya.
    """
    placed: list[int] = []
    dead: set[int] = set()
    ticketless = False
    for e in for_zone(zone_id, symbol):
        event, ticket = e.get("event"), e.get("ticket")
        if event == "placed":
            # `placed` TANPA TICKET MENGUNCI TANPA SYARAT, dan itu menahan
            # perilaku lama alih-alih melonggarkannya. Ia berarti "sesuatu
            # dipasang dan kita tidak tahu apa", dan sebuah zona yang mungkin
            # sudah punya order tidak boleh diorder dua kali. Tidak ada
            # pemanggil di repo ini yang menulisnya begitu - setiap
            # `record("placed", ...)` mengoper `ticket=` - tapi tanda tangan
            # `record` mengizinkannya, jadi jawabannya tidak boleh bergantung
            # pada kebiasaan pemanggil.
            if ticket is None:
                ticketless = True
            else:
                placed.append(int(ticket))
        elif event in ("cancelled", "closed") and ticket is not None:
            dead.add(int(ticket))
    live = [t for t in placed if t not in dead]
    # -1 bukan ticket yang bisa ada, jadi pemanggil yang memotongnya dengan
    # daftar ticket hidup broker tidak akan pernah menganggapnya hidup - tapi
    # pemanggil yang TIDAK bisa membaca broker tetap melihat zona ini terkunci.
    return live + ([-1] if ticketless else [])


def for_ticket(ticket: int) -> list[dict[str, Any]]:
    """Every event about one broker ticket, which is what scoring asks about."""
    return [e for e in entries() if e.get("ticket") == ticket]
