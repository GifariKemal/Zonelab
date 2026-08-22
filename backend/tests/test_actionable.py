"""The refusals have to fire, and they have to stay quiet on a sound drawing.

`truncated_by_provider` was written into every response for months and read by
nothing. A guard nobody calls is not a guard, and a guard whose tests only prove
the happy path is the same thing wearing a test suite.
"""

from __future__ import annotations

from app.actionable import blockers

STEP = 3600
AS_OF = 1_787_299_200  # a closed 1h bar


def response(**over) -> dict:
    """A sound drawing, which each test then breaks in exactly one way."""
    meta = {
        "bars_requested": 1000,
        "bars_returned": 1000,
        "truncated_by_provider": False,
        "as_of": AS_OF,
    }
    meta.update(over.pop("meta", {}))
    out = {
        "interval": "1h",
        "candles": [{"time": AS_OF, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}],
        "meta": meta,
    }
    out.update(over)
    return out


def test_a_sound_drawing_has_no_blockers():
    # Mid-bar: the next bar has not closed yet, which is the normal live state.
    assert blockers(response(), now=AS_OF + STEP + 600) == []


def test_truncated_history_blocks_and_names_both_counts():
    got = blockers(
        response(meta={"truncated_by_provider": True, "bars_returned": 400}),
        now=AS_OF + STEP + 600,
    )
    assert len(got) == 1
    assert "400 of 1000" in got[0], (
        "one count alone reads as a quiet market; both read as missing history"
    )


def test_a_missed_bar_close_blocks():
    """One interval of lag is normal. Two means a close was missed."""
    assert blockers(response(), now=AS_OF + STEP + STEP + 1) != []


def test_the_edge_of_one_interval_is_still_sound():
    """Exactly one interval of lag is the last moment before the next close, not
    a missed one. Asserted because an off-by-one here refuses every chart in the
    final second of every bar."""
    assert blockers(response(), now=AS_OF + 2 * STEP) == []


def test_no_candles_blocks_on_its_own():
    got = blockers(response(candles=[]), now=AS_OF + STEP)
    assert got == ["no candles: there is nothing drawn to act on"]


def test_a_response_without_meta_is_not_a_drawing():
    assert blockers({"candles": [1]}, now=AS_OF) == [
        "no meta block: this is not a /api/draw response"
    ]


def test_an_unknown_interval_blocks_rather_than_passing_silently():
    """The staleness check needs the bar length. Without it the answer is not
    "sound", it is "unknown", and those must not be the same output."""
    got = blockers(response(interval="7m"), now=AS_OF + STEP)
    assert any("unknown interval" in b for b in got)


def test_two_faults_are_both_reported():
    """Not first-fault-wins: the journal records everything that was wrong, or a
    fixed truncation would reveal a staleness nobody had been told about."""
    got = blockers(
        response(meta={"truncated_by_provider": True, "bars_returned": 10}),
        now=AS_OF + 5 * STEP,
    )
    assert len(got) == 2, got
