"""The audit trail, and the rule engine that writes into it.

Two things are pinned here and they are the two that make the record worth
keeping at all:

  - a snapshot is the response VERBATIM. If this module ever starts editing the
    body it stores, the file stops being evidence about the market and becomes
    evidence about this module.
  - the lag decomposition. `feed_lag_seconds` on a 15-minute chart runs 0 to 900
    for no reason other than time passing inside the forming bar, so reading it
    as staleness is wrong by up to a whole bar. The first live run measured 558
    seconds with a perfectly healthy feed.

Nothing here asserts that the rule works. The rule has no walk-forward, no
placebo and no base rate; these tests assert that it is applied consistently and
that its premises are labelled by origin, which is what makes a later score
meaningful.
"""

from __future__ import annotations

import json

import pytest

from app import snapshots
from app.deduce import deduce

FIFTEEN = 900


def meta(feed_lag: int, fetched_at: int = 1_000_000, step: int = FIFTEEN) -> dict:
    closed = 1_787_211_900
    return {
        "as_of": closed - step,
        "bar_closed_at": closed,
        "next_close_at": closed + step,
        "feed_lag_seconds": feed_lag,
        "fetched_at": fetched_at,
    }


# ----------------------------------------------------------------- the lags


def test_time_inside_the_forming_bar_is_not_counted_as_staleness():
    """The trap this decomposition exists to close.

    Nine minutes into a fifteen-minute bar is where the clock is, not a feed
    that is behind. A single summed lag would have reported 558 seconds and an
    auditor would have concluded the screen was nine minutes old.
    """
    lag = snapshots.measure_lag(meta(feed_lag=558), taken_at=1_000_003)
    assert lag.feed_seconds == 558
    assert lag.intra_bar_seconds == 558
    assert lag.overdue_seconds == 0
    assert lag.screen_seconds == 3
    assert lag.total_seconds == 3, "only overdue + screen counts as behind"


def test_a_bar_that_should_have_closed_and_did_not_is_overdue():
    """Past one whole bar, the excess IS staleness and has to surface."""
    lag = snapshots.measure_lag(meta(feed_lag=FIFTEEN + 120), taken_at=1_000_005)
    assert lag.intra_bar_seconds == FIFTEEN, "capped at one bar"
    assert lag.overdue_seconds == 120
    assert lag.total_seconds == 125


def test_a_reader_who_sat_on_the_chart_is_charged_for_it():
    """Screen staleness is the reader's own delay and nothing else's."""
    lag = snapshots.measure_lag(meta(feed_lag=10), taken_at=1_000_000 + 660)
    assert lag.screen_seconds == 660
    assert lag.overdue_seconds == 0
    assert lag.total_seconds == 660


def test_a_client_clock_ahead_of_the_server_cannot_produce_negative_staleness():
    """A negative would read as the future, which is never information."""
    lag = snapshots.measure_lag(meta(feed_lag=10), taken_at=999_000)
    assert lag.screen_seconds == 0


def test_a_response_without_provenance_reports_zero_rather_than_a_guess():
    lag = snapshots.measure_lag({}, taken_at=1_000_000)
    assert (lag.feed_seconds, lag.intra_bar_seconds, lag.overdue_seconds) == (0, 0, 0)
    assert lag.screen_seconds == 0


# ------------------------------------------------------------- the snapshot


def test_a_snapshot_stores_the_response_byte_for_byte(tmp_path, monkeypatch):
    """The one property that makes the file evidence.

    A snapshot this module had edited would be a record of this module. So the
    stored `response` must compare equal to what was handed in, field for field
    and order aside - including fields this module has never heard of.
    """
    monkeypatch.setattr(snapshots, "DIRECTORY", tmp_path)
    response = {
        "symbol": "XAUUSD",
        "interval": "15m",
        "provider": "mt5",
        "candles": [{"time": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}],
        "drawing": {"zones": [{"id": "z"}], "ssmt": [], "levels": [{"n": 1}, {"n": 2}]},
        "plans": [{"lots": 0.06}],
        "meta": meta(feed_lag=100),
        "a_field_this_module_has_never_heard_of": {"keep": "me"},
    }
    saved = snapshots.save(response, note="rule v1")

    stored = json.loads((tmp_path / f"{saved['id']}.json").read_text(encoding="utf-8"))
    assert stored["response"] == response, "the body must survive untouched"
    assert stored["note"] == "rule v1"

    # The summary counts only non-empty arrays, so an overlay that drew nothing
    # is not listed as a layer that was on.
    assert saved["layers"] == ["levels", "zones"], saved["layers"]
    assert saved["objects"] == 3
    assert saved["plans"] == 1


def test_the_listing_survives_one_unreadable_file(tmp_path, monkeypatch):
    """These are hand-editable files on a local disk. One broken one must not
    hide a whole review."""
    monkeypatch.setattr(snapshots, "DIRECTORY", tmp_path)
    snapshots.save({"symbol": "A", "interval": "1h", "meta": meta(1)}, "first")
    (tmp_path / "9999999999-broken-1h.json").write_text("{not json", encoding="utf-8")

    listed = snapshots.listing()
    assert len(listed) == 1
    assert listed[0]["note"] == "first"


def test_an_id_cannot_walk_out_of_the_snapshot_directory(tmp_path, monkeypatch):
    """A filesystem read driven by a request body is the shape every
    path-traversal bug has, so the id is matched against the listing rather
    than joined onto the path."""
    monkeypatch.setattr(snapshots, "DIRECTORY", tmp_path)
    snapshots.save({"symbol": "A", "interval": "1h", "meta": meta(1)}, "only")
    (tmp_path.parent / "outside.json").write_text('{"secret": 1}', encoding="utf-8")

    assert snapshots.read("../outside") is None
    assert snapshots.read("..\\outside") is None
    assert snapshots.read("nope") is None


# --------------------------------------------------------------- the deducer


def state(*, side="high", self_took=True, range_pos=0.9, knowable_at=500) -> dict:
    return {
        "symbol": "XAUUSD",
        "interval": "15m",
        "provider": "mt5",
        "candles": [
            {"time": i, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
            for i in range(40)
        ],
        "drawing": {
            "ssmt": [
                {
                    "side": side,
                    "self_took": self_took,
                    "partner": "DXY",
                    "degree": "day",
                    "knowable_at": knowable_at,
                    "range_pos": range_pos,
                }
            ]
        },
        "meta": {**meta(feed_lag=100), "as_of": 1000},
    }


def test_all_three_conditions_met_reports_rule_met_and_never_the_word_valid():
    """The verdict is a statement about the RULE, not about the market.

    "Valid" would be the engine endorsing a rule with no walk-forward, no
    placebo and no base rate, in a project where twelve pre-registered
    directional hypotheses have failed. The wording is load-bearing.
    """
    out = deduce(state(), draw="lower")
    assert out["status"] == "RULE MET"
    assert out["stopped_at"] is None
    assert "valid" not in json.dumps(out).lower()
    assert "twelve pre-registered" in out["caveat"]


def test_the_nominated_premise_is_labelled_as_nominated():
    """Two premises are measured and one is the caller's. A deduction whose
    premises came from different places and did not say so reads as three
    measurements when it is two."""
    out = deduce(state(), draw="lower")
    path = "\n".join(out["deduction_path"])
    assert "[nominated]" in path
    assert path.count("[measured]") == 2
    assert "Zonelab does not measure this" in path


@pytest.mark.parametrize("draw", ["higher", "unnominated"])
def test_any_draw_other_than_lower_stops_the_rule(draw):
    out = deduce(state(), draw=draw)
    assert out["status"] == "NO SETUP"
    assert out["stopped_at"] == "dol_direction_lower"


def test_a_divergence_the_chart_did_not_take_is_not_a_bearish_smt():
    """Bearish means a shape: this symbol took the high, the partner failed.
    The mirror is a different reading and must not satisfy the clause."""
    out = deduce(state(self_took=False), draw="lower")
    assert out["stopped_at"] == "smt_divergence"


def test_a_low_side_divergence_does_not_satisfy_a_short_rule():
    out = deduce(state(side="low"), draw="lower")
    assert out["stopped_at"] == "smt_divergence"


def test_a_divergence_not_yet_knowable_is_refused():
    """The anti-hindsight gate. A divergence settles at its quarter's close;
    reading one before that instant is reading the future, and this whole module
    is worthless if it does that once."""
    out = deduce(state(knowable_at=5000), draw="lower")
    assert out["stopped_at"] == "smt_divergence"
    assert out["evidence"]["as_of"] == 1000


def test_equilibrium_and_discount_both_fail_the_premium_clause():
    for pos in (0.5, 0.74, 0.25, 0.0):
        out = deduce(state(range_pos=pos), draw="lower")
        assert out["stopped_at"] == "price_location_premium", pos
    assert deduce(state(range_pos=0.75), draw="lower")["status"] == "RULE MET"


def test_an_unconfirmed_range_cannot_assert_premium():
    """None is the warm-up, not a midpoint. Asserting premium from an unknown
    position would be inventing the one number the range refused to give."""
    out = deduce(state(range_pos=None), draw="lower")
    assert out["stopped_at"] == "price_location_premium"
    assert "cannot be asserted" in "\n".join(out["deduction_path"])


def test_the_evidence_carries_the_bar_close_and_a_real_atr():
    out = deduce(state(), draw="lower")
    assert out["evidence"]["bar_closed_at"] == 1_787_211_900
    assert out["evidence"]["atr_14"] == pytest.approx(2.0, abs=0.5)
    assert out["evidence"]["atr_period"] == 14


def test_too_few_bars_yields_no_atr_rather_than_a_zero():
    """A zero ATR would make every ratio expressed in it infinite."""
    thin = state()
    thin["candles"] = thin["candles"][:5]
    assert deduce(thin, draw="lower")["evidence"]["atr_14"] is None
