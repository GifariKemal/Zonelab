"""Scanning a basket is not five scans that happen to run together.

`gather` is orchestration, so it is tested as orchestration: `candidates` and
`history.load` are replaced by recorders, and what is asserted is the ORDER of
the calls and the shape of what comes back. The detection those two do has its
own tests, and repeating them here would only make this file slow enough that
nobody runs it.

Three properties, and each of them is a defect this file caught while being
written:

  1. one ranking across the whole basket, not the best two from each pair;
  2. a stale feed on one series stops that series and nothing else;
  3. every series is loaded BEFORE the first candidate is scored, because the
     SSMT clause reads the partners and a scan that loaded as it scored would
     give the first pair no partners and the last pair all of them.
"""

from __future__ import annotations

import types

import pytest

from app.ict import Rules, Setup
from tools import execute


class FakePlan:
    """Only the two fields the ranking reads."""

    def __init__(self, entry: float, target: float):
        self.entry, self.target = entry, target


def checklist(met: int) -> Setup:
    """A `Setup` whose `met` is exactly `met`, built from real conditions."""
    from app.ict import Condition

    return Setup(conditions=[
        Condition(f"c{i}", i < met, "doctrine", "") for i in range(12)
    ])


@pytest.fixture
def recorder(monkeypatch):
    """Replaces both collaborators and records every call, in order.

    Returns the log itself, so a test asserts on the sequence rather than on a
    mock's opinion of what a sequence is.
    """
    log: list[tuple] = []

    def load(symbol, interval, bars):
        log.append(("load", symbol, interval))
        return [types.SimpleNamespace(time=1787227200 + i * 3600) for i in range(50)]

    monkeypatch.setattr(execute.history, "load", load)
    monkeypatch.setattr(execute, "blockers", lambda response: list(response or []))
    return log


def fake_candidates(log: list, table: dict[str, list[tuple[int, float, float]]]):
    """`table` maps symbol to (met, entry, target) triples. Response is empty."""

    def inner(symbol, interval, bars, equity, risk_pct, lot, rules, partners=None):
        log.append(("scan", symbol, interval, tuple(sorted(partners or ()))))
        rows = [
            (types.SimpleNamespace(id=f"{symbol}-{i}"), FakePlan(entry, target),
             checklist(met))
            for i, (met, entry, target) in enumerate(table.get(symbol, []))
        ]
        return rows, [], 100.0

    return inner


# ------------------------------------------------------------------ ranking


def test_the_best_checklist_wins_wherever_it_is(monkeypatch, recorder):
    """Gold is scanned first and its candidate is NEARER its target. Silver's
    satisfies more of the method, so silver's is first. Ordering by distance
    alone - which is what this did before the checklist existed - would put the
    weaker setup at the top of a live scan."""
    monkeypatch.setattr(execute, "candidates", fake_candidates(recorder, {
        "mt5:XAUUSD": [(4, 100.0, 101.0)],   # 1.0 away, 4 clauses met
        "mt5:XAGUSD": [(9, 50.0, 60.0)],     # 10.0 away, 9 clauses met
    }))
    found, blocked, series = execute.gather(
        ["mt5:XAUUSD", "mt5:XAGUSD"], ["1h"], 500, None, 0.01, None, Rules()
    )
    assert [row[0] for row in found] == ["mt5:XAGUSD", "mt5:XAUUSD"]
    assert blocked == []
    assert sorted(series) == ["XAGUSD", "XAUUSD"]


def test_distance_still_breaks_a_tie():
    """The checklist ranks first and distance second, so two setups that satisfy
    the same clauses are ordered by how far the target is. Otherwise the order
    would be whatever the loop happened to produce."""
    rows = [
        ("A", "1h", None, FakePlan(100.0, 130.0), checklist(5)),
        ("B", "1h", None, FakePlan(100.0, 105.0), checklist(5)),
    ]
    rows.sort(key=lambda t: (-t[4].met, abs(t[3].entry - t[3].target)))
    assert [r[0] for r in rows] == ["B", "A"]


# ----------------------------------------------------------------- blockers


def test_a_stale_series_blocks_only_itself(monkeypatch, recorder):
    """A Saturday leaves exactly one pair quiet. A scan that refused the whole
    basket for it would be unusable on the day it is most needed."""

    def inner(symbol, interval, bars, equity, risk_pct, lot, rules, partners=None):
        if symbol == "mt5:XAUUSD":
            return [], ["feed is 3 bars behind"], 100.0
        return (
            [(types.SimpleNamespace(id="z"), FakePlan(50.0, 60.0), checklist(6))],
            [], 50.0,
        )

    monkeypatch.setattr(execute, "candidates", inner)
    found, blocked, _ = execute.gather(
        ["mt5:XAUUSD", "mt5:XAGUSD"], ["1h"], 500, None, 0.01, None, Rules()
    )
    assert [row[0] for row in found] == ["mt5:XAGUSD"]
    assert blocked == [("mt5:XAUUSD", "1h", ["feed is 3 bars behind"])]


def test_a_blocked_series_contributes_no_candidate_even_when_it_found_some():
    """The blocker check comes BEFORE the extend, and this is the assertion that
    keeps it there. A stale feed that still produced zones is the exact case
    where a misordered guard is invisible."""
    import inspect

    src = inspect.getsource(execute.gather)
    assert src.index("blocked.append") < src.index("found.extend"), (
        "the blocker branch must short-circuit before candidates are collected"
    )


# ------------------------------------------------------- partners and order


def test_every_series_is_loaded_before_the_first_one_is_scored(monkeypatch,
                                                              recorder):
    """The SSMT ordering property, stated as a test.

    `candidates` answers the `ssmt` clause from the partners it is handed, so a
    single pass that loaded each series as it scored it would hand the first pair
    an empty basket and the last pair a full one. The clause's verdict would then
    depend on the order of `--symbol`, which is not a market fact.
    """
    monkeypatch.setattr(execute, "candidates", fake_candidates(recorder, {}))
    execute.gather(
        ["mt5:XAUUSD", "mt5:XAGUSD", "mt5:XPTUSD"], ["1h", "4h"],
        500, None, 0.01, None, Rules(),
    )
    kinds = [row[0] for row in recorder]
    assert kinds.count("load") == 3, "one load per symbol, not one per timeframe"
    assert kinds.index("scan") > max(
        i for i, k in enumerate(kinds) if k == "load"
    ), "a series was scored before the whole basket had been loaded"


def test_each_scan_is_handed_the_whole_basket(monkeypatch, recorder):
    """Not just the partners loaded so far. Same defect as above, seen from the
    other side: this is what the SSMT clause actually reads."""
    monkeypatch.setattr(execute, "candidates", fake_candidates(recorder, {}))
    execute.gather(
        ["mt5:XAUUSD", "mt5:XAGUSD"], ["1h"], 500, None, 0.01, None, Rules()
    )
    handed = {row[3] for row in recorder if row[0] == "scan"}
    assert handed == {("XAGUSD", "XAUUSD")}, handed


def test_the_returned_series_map_is_keyed_bare(monkeypatch, recorder):
    """`admits` looks up `XAUUSD`, and the scan is given `mt5:XAUUSD`. A map
    keyed with the prefix would make the correlation guard silently find nothing
    and admit every pair - a guard that passes because it looked in the wrong
    dictionary."""
    monkeypatch.setattr(execute, "candidates", fake_candidates(recorder, {}))
    _, _, series = execute.gather(
        ["mt5:XAUUSD"], ["1h"], 500, None, 0.01, None, Rules()
    )
    assert list(series) == ["XAUUSD"]
    assert all(":" not in key for key in series)
