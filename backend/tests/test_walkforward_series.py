"""`--series` has to reach EVERY gate, not most of them.

This exists because it did not. `tools/walkforward.py` held the five-series list
twice: once as the module constant that `--series` rewrites, and once as a
literal inside `gather()`. The three supply/demand gates route through `gather`,
so the documented MT5 gold run printed `Series overridden: [('mt5:XAUUSD', ...)]`
and then measured PAXG, BTC and ETH anyway. Five rows of
`docs/WALKFORWARD-MT5.md` carried the wrong instrument label, and one of them -
`profit zone rr` at 8/8 - reversed to 5/8 once it was measured on the instrument
it claimed. Nothing in the output looked wrong. The override was even echoed back
to the operator.

So the test is not "does gather work". It is: does every entry point honour the
one constant, checked by asking WHICH SYMBOLS were loaded. A second copy of the
list would make this fail on the first assert.

Bars are tiny and the candles are synthetic. The numbers this produces are
meaningless and nothing here asserts one - the only claim is about plumbing.
"""

from __future__ import annotations

import asyncio

import pytest

from tools import walkforward


@pytest.fixture
def loaded(monkeypatch):
    """Records every (symbol, interval) the module asks history for."""
    from app.providers import get_candles

    rows = asyncio.run(get_candles("XAUUSD", "1h", 900, "synthetic"))[0]
    seen: list[tuple[str, str]] = []

    def fake_load(symbol: str, interval: str, bars: int):
        seen.append((symbol, interval))
        return rows

    monkeypatch.setattr(walkforward.history, "load", fake_load)
    return seen


def test_gather_reads_the_module_series_and_not_a_copy(loaded, monkeypatch):
    """The supply/demand path. This is the one that was broken."""
    monkeypatch.setattr(walkforward, "SERIES", [("SENTINEL", "1h")])
    walkforward.gather(900, 1.0, 40)
    assert loaded == [("SENTINEL", "1h")], (
        "gather loaded something the override did not name, so it is reading a "
        "second copy of SERIES"
    )


def test_gather_detector_reads_the_module_series_and_not_a_copy(loaded, monkeypatch):
    """The imbalance path. It was already correct, and it stays checked so a
    future edit cannot break the half that used to work while the other half is
    the one everybody remembers."""
    monkeypatch.setattr(walkforward, "SERIES", [("SENTINEL", "15m")])
    walkforward.gather_detector("fvg", 900, 1.0, 40)
    assert loaded == [("SENTINEL", "15m")]


def test_the_series_literal_appears_exactly_once_in_the_file():
    """Belt and braces, and cheap. The two tests above catch a second copy in
    the two functions that exist today; this one catches a THIRD copy pasted
    into a function nobody has written yet, which is how the first duplicate got
    there. Matched on a symbol name rather than on the whole literal so
    reformatting cannot defeat it."""
    from pathlib import Path

    source = Path(walkforward.__file__).read_text(encoding="utf-8")
    # Counted in LINES, not in mentions: the constant names PAXGUSDT twice on
    # one line, once per interval, and a mention count would read 2 for a file
    # that is perfectly correct. One line is the constant; a second line is a
    # copy wherever it sits.
    lines = [n for n, line in enumerate(source.splitlines(), 1) if "PAXGUSDT" in line]
    assert len(lines) == 1, (
        f"the default series list is written on lines {lines} - it belongs only "
        "to the module constant SERIES; see this test's docstring for what a "
        "second copy cost"
    )
