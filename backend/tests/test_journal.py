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


# ----------------------------------------------------- idempotensi per simbol


def test_the_same_zone_id_on_another_symbol_is_a_different_trade():
    """Zone id adalah `KIND-bartime` DAN TIDAK MEMBAWA SIMBOL.

    Terukur di window 400 bar 1h pada 2026-08-27: XAUUSD dan XAGUSD berbagi
    EMPAT id, salah satunya `DBR-1787227200`. Tanpa simbol di kuncinya, gate
    idempotensi di `tools/execute.py` membunuh trade silver dan melaporkannya
    sebagai "SUDAH pernah diorder, ticket 4573230383" - ticket yang ada di gold.
    """
    journal.record("placed", why=WHY, rule=RULE, zone_id="DBR-1787227200",
                   symbol="mt5:XAUUSD", ticket=4573230383, plan={"entry": 4489.624})

    assert journal.for_zone("DBR-1787227200", "mt5:XAUUSD")[0]["ticket"] == 4573230383
    assert journal.for_zone("DBR-1787227200", "mt5:XAGUSD") == []
    # Dan tanpa simbol, jawabannya tetap semua entri untuk id itu.
    assert len(journal.for_zone("DBR-1787227200")) == 1


def test_a_record_written_before_symbols_existed_still_suppresses():
    """Entri lama tidak punya field `symbol`, dan yang aman adalah menahan.

    Ticket-nya sudah ada di broker. Kalau entri tanpa simbol dianggap tidak
    match, run berikutnya akan mengirim duplikat ke zona yang sudah punya order.
    Jadi None match apa pun, dan itu keputusan, bukan sisa.
    """
    journal.record("placed", why=WHY, rule=RULE, zone_id="DBR-9", ticket=1,
                   plan={"entry": 1.0})  # tanpa symbol=

    assert journal.for_zone("DBR-9", "mt5:XAUUSD")[0]["ticket"] == 1
    assert journal.for_zone("DBR-9", "mt5:XAGUSD")[0]["ticket"] == 1


def test_a_correction_is_a_third_line_and_leaves_the_placed_why_intact():
    """A wrong `why` cannot be edited out, so it is answered in place.

    The defect this locks: two orders on 2 September 2026 carried grounds
    measured on `supply_demand` while sitting on `order_block` zones. The
    original line has to survive - it is what was actually acted on - and the
    correction has to be readable beside it.
    """
    journal.record("placed", why=["gerbang supply_demand +0,1105 R"], rule=RULE,
                   zone_id="OB-1", ticket=99, at=100)
    journal.record("corrected", why=["populasi sebenarnya order_block, +0,0827 R t=+3,32"],
                   rule=RULE, zone_id="OB-1", ticket=99, at=300)
    rows = journal.for_ticket(99)
    assert [r["event"] for r in rows] == ["placed", "corrected"]
    assert rows[0]["why"] == ["gerbang supply_demand +0,1105 R"]
    assert "order_block" in rows[1]["why"][0]


def test_a_correction_with_no_grounds_is_still_written():
    """Only `placed` demands its grounds. A correction is free to be terse, and
    refusing it here would push the correction out of the log entirely."""
    got = journal.record("corrected", why=[], rule=RULE, ticket=100)
    assert got["event"] == "corrected"
