"""The journal has to refuse a record that cannot be audited.

A log that accepts anything is a log that will contain an order with no stated
grounds, and that record is worse than a missing one: it looks like evidence.
"""

from __future__ import annotations

import json

import pytest

from app import journal

RULE = {"gate": "departure>=2.0", "exit": "flat_at_rollover", "horizon_bars": 80}
WHY = ["departure 6.27 ATR clears the 2.0 gate (85.8% vs 64.4%, 8/8 folds)"]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Never write to the real `.journal` from a test. The directory holds
    account state, and a test that appended to it would be editing evidence."""
    monkeypatch.setattr(journal, "DIRECTORY", tmp_path / ".journal")
    return tmp_path


def test_a_placed_order_is_written_with_its_grounds():
    got = journal.record("placed", why=WHY, rule=RULE, zone_id="DBD-1", ticket=7,
                         plan={"entry": 4604.221, "stop": 4628.043})
    assert got["event"] == "placed"
    assert got["why"] == WHY
    assert journal.for_zone("DBD-1")[0]["ticket"] == 7


def test_a_placed_order_with_no_grounds_is_refused():
    """The regression this file exists for."""
    with pytest.raises(ValueError, match="grounds"):
        journal.record("placed", why=[], rule=RULE, zone_id="DBD-1")


def test_a_record_with_no_rule_version_is_refused():
    with pytest.raises(ValueError, match="rule version"):
        journal.record("refused", why=["x"], rule={})


def test_an_unknown_event_is_refused():
    with pytest.raises(ValueError, match="unknown event"):
        journal.record("yolo", why=["x"], rule=RULE)


def test_a_refusal_records_its_blockers():
    """A refusal with no blocker string is not a refusal anybody can argue
    with, and arguing with it later is the point."""
    got = journal.record("refused", why=["nothing cleared the gate"], rule=RULE,
                         blockers=["history truncated: 400 of 1000 bars"])
    assert got["blockers"] == ["history truncated: 400 of 1000 bars"]


def test_blockers_are_recorded_even_when_empty():
    """Empty is a finding: it says the guard ran. A missing key would say
    nothing ran, and those must not look the same."""
    got = journal.record("placed", why=WHY, rule=RULE)
    assert got["blockers"] == []


def test_a_fill_is_a_second_line_and_never_an_edit():
    """The decision and the fill are different moments at different prices. An
    in-place edit would destroy the first one."""
    journal.record("placed", why=WHY, rule=RULE, zone_id="DBD-1", ticket=7, at=100)
    journal.record("filled", why=["limit touched"], rule=RULE, zone_id="DBD-1",
                   ticket=7, at=200)
    rows = journal.for_ticket(7)
    assert [r["event"] for r in rows] == ["placed", "filled"]
    assert [r["at"] for r in rows] == [100, 200]


def test_a_broken_line_does_not_take_the_review_down(isolated):
    journal.record("placed", why=WHY, rule=RULE, zone_id="ok", at=100)
    day = sorted(journal.DIRECTORY.glob("*.jsonl"))[0]
    with day.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    assert [e["zone_id"] for e in journal.entries()] == ["ok"]


def test_records_are_one_line_each_and_machine_readable(isolated):
    journal.record("placed", why=WHY, rule=RULE, zone_id="a", at=100)
    journal.record("closed", why=["rollover"], rule=RULE, zone_id="a", at=200)
    day = sorted(journal.DIRECTORY.glob("*.jsonl"))[0]
    lines = [l for l in day.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # raises if a record spans lines or is not valid JSON
