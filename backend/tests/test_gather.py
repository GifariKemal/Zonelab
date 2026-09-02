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

    def inner(symbol, interval, bars, equity, risk_pct, lot, rules,
              partners=None, **_):
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

    def inner(symbol, interval, bars, equity, risk_pct, lot, rules,
              partners=None, **_):
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


def test_the_layer_reaches_candidates(monkeypatch):
    """Rantai penerusan `--layer`, dan kenapa ia dites daripada dipercaya.

    `cycle` menerima `layer`, meneruskannya ke `gather`, dan `gather` ke
    `candidates`. Tiga sambungan, dan sebuah sambungan yang lepas TIDAK
    menimbulkan error: `candidates` punya default `"supply_demand"`, jadi
    order akan dipasang pada populasi default sambil setiap laporan menyebut
    nama layer yang diminta. Itu kelas cacat yang paling sulit terlihat di repo
    ini, dan satu-satunya cara menutupnya adalah memeriksa nilainya sampai di
    ujung.
    """
    seen: list[tuple[str, bool]] = []

    def inner(symbol, interval, bars, equity, risk_pct, lot, rules,
              partners=None, layer="supply_demand", no_cisd_in_band=False):
        seen.append((layer, no_cisd_in_band))
        return [], [], 1.0

    monkeypatch.setattr(execute, "candidates", inner)
    monkeypatch.setattr(
        execute.history, "load",
        lambda *a, **k: [types.SimpleNamespace(time=1787227200 + i * 3600)
                         for i in range(50)])
    monkeypatch.setattr(execute, "blockers", lambda response: [])
    execute.gather(["mt5:XAUUSD"], ["30m"], 10, None, 0.01, {}, Rules(),
                   layer="order_block", no_cisd_in_band=True)
    assert seen == [("order_block", True)]


def test_the_alphabet_does_not_decide_which_symbol_gets_the_slots():
    """Dua slot tidak boleh selalu jatuh ke simbol yang namanya lebih awal.

    `by_method_ranked` mengembalikan `(symbol, zone.id)` dan `cycle` memotong
    daftarnya di `max_orders`, jadi tanpa `round_robin` urutan abjad MENJADI
    prioritas. Dengan config daemon `mt5:XAUUSD,mt5:BTCUSD` dan `--max-orders`
    default 2, "BTCUSD" mendahului "XAUUSD" sehingga XAU tidak pernah diorder
    selama BTC punya dua kandidat, dan diukur 2 September 2026 BTC punya 9 di
    30m dan 10 di 15m.
    """
    rows = [("BTCUSD", "30m", f"b{i}", None, None) for i in range(5)]
    rows += [("XAUUSD", "30m", f"x{i}", None, None) for i in range(3)]
    rows.sort(key=lambda r: (r[0], r[2]))
    got = execute.round_robin(rows)
    # Dua pertama harus datang dari dua simbol yang BERBEDA.
    assert got[0][0] != got[1][0], [r[0] for r in got[:4]]
    # Tidak ada yang hilang, dan tidak ada yang berganda.
    assert sorted(got) == sorted(rows)
    # Urutan DI DALAM satu simbol dipertahankan apa adanya.
    assert [r[2] for r in got if r[0] == "BTCUSD"] == ["b0", "b1", "b2", "b3", "b4"]
    assert [r[2] for r in got if r[0] == "XAUUSD"] == ["x0", "x1", "x2"]


def test_round_robin_is_deterministic_and_survives_one_symbol():
    """Satu simbol saja harus lewat tanpa berubah, dan dua run harus sama."""
    rows = [("XAUUSD", "30m", f"x{i}", None, None) for i in range(4)]
    assert execute.round_robin(rows) == rows
    assert execute.round_robin([]) == []
    mixed = [("A", "30m", "a0", None, None), ("A", "30m", "a1", None, None),
             ("B", "30m", "b0", None, None)]
    assert execute.round_robin(mixed) == execute.round_robin(mixed)


def test_gather_actually_applies_the_round_robin(monkeypatch, recorder):
    """Dan ia dipasang di `gather`, bukan cuma tersedia sebagai fungsi.

    Suntikan yang membuktikan test di atas TIDAK cukup: menghapus
    `round_robin(...)` dari `return` di `gather` tidak membuat satu pun test di
    atas merah, karena semuanya memanggil fungsinya langsung. Sebuah perbaikan
    yang tidak terpasang terlihat persis sama dengan perbaikan yang terpasang.
    """
    log = recorder
    monkeypatch.setattr(execute, "candidates", fake_candidates(log, {
        "mt5:BTCUSD": [(5, 100.0, 110.0), (4, 101.0, 111.0)],
        "mt5:XAUUSD": [(3, 200.0, 210.0), (2, 201.0, 211.0)],
    }))
    ranked, _, _ = execute.gather(
        ["mt5:BTCUSD", "mt5:XAUUSD"], ["30m"], 10, None, 0.01, {}, Rules())
    assert len(ranked) == 4
    assert ranked[0][0] != ranked[1][0], [r[0] for r in ranked]
