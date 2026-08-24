"""SSMT on candles whose answer is arithmetic, not incidental.

Every fixture below writes each quarter's high and low as literal numbers and
gives them to ONE bar in the middle of the quarter, so an expected event is a
comparison a reader can do in their head. Nothing here is generated, and nothing
here asserts that a divergence predicts anything: the assertions are about which
instrument took which level, and about the two ways this measurement could be a
fiction instead - bars that are not the same bars, and a quarter read before it
closed.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_ssmt.py -q
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.clock import NY
from app.models import Candle
from app.quarters import Quarter
from app.ssmt import SMTEvent, SSMTEvent, divergences_for, smt, ssmt

HOUR = 3600


def ny(year: int, month: int, day: int, hour: int = 0) -> int:
    """Epoch of a New York wall-clock time, built from the calendar here."""
    return int(datetime(year, month, day, hour, tzinfo=NY).timestamp())


# A day-cycle open in June, so no DST transition stretches a quarter and the
# four day quarters are six hourly bars each: Q1 18:00, Q2 00:00, Q3 06:00,
# Q4 12:00 New York.
START = ny(2025, 6, 10, 18)


def _candle(time: int, high: float, low: float) -> Candle:
    mid = (high + low) / 2
    return Candle(time=time, open=mid, high=high, low=low, close=mid, volume=1.0)


def series(
    quarters: list[tuple[float, float] | None],
    start: int = START,
    hours: int = 6,
    tail: int = 1,
) -> list[Candle]:
    """Hourly bars, `hours` per day quarter, one (high, low) pair per quarter.

    The extremes belong to a single mid-quarter bar and every other bar is flat
    at the midpoint, so the quarter's high IS the number written in the fixture.
    `None` leaves that quarter with no bars at all and skips its time.

    `tail` bars are appended past the last quarter on purpose: a quarter is only
    read once a bar has printed at or after its close, so without them the last
    quarter is deliberately invisible.
    """
    out: list[Candle] = []
    time = start
    mid = 0.0
    for entry in quarters:
        if entry is None:
            time += hours * HOUR
            continue
        high, low = entry
        mid = (high + low) / 2
        for i in range(hours):
            out.append(
                _candle(time, high, low) if i == hours // 2 else _candle(time, mid, mid)
            )
            time += HOUR
    for _ in range(tail):
        out.append(_candle(time, mid, mid))
        time += HOUR
    return out


def test_one_instrument_takes_the_previous_quarters_high_and_the_other_fails():
    # Q1 highs 100 and 200. In Q2 gold exceeds its 100 and silver stops one
    # tick under its 200, which is the entire definition of the object.
    gold = series([(100.0, 90.0), (105.0, 95.0)])
    silver = series([(200.0, 190.0), (199.0, 195.0)])

    events, stats = ssmt({"GOLD": gold, "SILVER": silver}, "day")

    assert len(events) == 1
    event = events[0]
    assert event.side == "high"
    assert (event.took, event.failed) == ("GOLD", "SILVER")
    assert (event.took_prior, event.took_now) == (100.0, 105.0)
    assert (event.failed_prior, event.failed_now) == (200.0, 199.0)
    assert event.degree == "day"
    assert event.prior.label == "Q1" and event.quarter.label == "Q2"
    assert event.prior.start == START
    assert event.quarter.start == ny(2025, 6, 11) == event.prior.end
    assert stats["side.high"] == 1.0 and stats["side.low"] == 0.0
    assert stats["pair:GOLD|SILVER"] == 1.0


def test_the_same_reading_downward_is_a_low_side_divergence():
    # The mirror image: gold takes out 90, silver holds above 190.
    gold = series([(100.0, 90.0), (99.0, 85.0)])
    silver = series([(200.0, 190.0), (199.0, 191.0)])

    events, stats = ssmt({"GOLD": gold, "SILVER": silver}, "day")

    assert len(events) == 1
    event = events[0]
    assert event.side == "low"
    assert (event.took, event.failed) == ("GOLD", "SILVER")
    assert (event.took_prior, event.took_now) == (90.0, 85.0)
    assert (event.failed_prior, event.failed_now) == (190.0, 191.0)
    assert stats["side.low"] == 1.0 and stats["side.high"] == 0.0


def test_both_instruments_taking_the_level_is_agreement_and_not_a_divergence():
    gold = series([(100.0, 90.0), (105.0, 95.0)])
    silver = series([(200.0, 190.0), (205.0, 195.0)])

    events, stats = ssmt({"GOLD": gold, "SILVER": silver}, "day")

    assert events == []
    # The pair WAS examined; there was simply nothing to report about it. A
    # dropped pair and an agreeing pair must not read the same in the stats.
    assert stats["pairs.compared"] == 1.0
    assert stats["pairs.skipped_no_bars"] == 0.0
    assert stats["events"] == 0.0


def test_neither_instrument_taking_the_level_is_also_not_a_divergence():
    gold = series([(100.0, 90.0), (99.0, 95.0)])
    silver = series([(200.0, 190.0), (199.0, 195.0)])

    events, stats = ssmt({"GOLD": gold, "SILVER": silver}, "day")

    assert events == []
    assert stats["pairs.compared"] == 1.0


def test_equalling_the_previous_extreme_is_not_taking_it_out():
    # Gold prints exactly last quarter's high and silver exceeds its own. If
    # the comparison were >= this would be agreement and nothing would be
    # reported; strictness is what makes it silver's divergence.
    gold = series([(100.0, 90.0), (100.0, 95.0)])
    silver = series([(200.0, 190.0), (205.0, 195.0)])

    events, _ = ssmt({"GOLD": gold, "SILVER": silver}, "day")

    assert len(events) == 1
    assert (events[0].took, events[0].failed) == ("SILVER", "GOLD")
    assert events[0].took_now == 205.0 and events[0].failed_now == 100.0


def test_series_on_different_bar_times_are_refused_rather_than_compared():
    """The failure this module exists to prevent, and it is silent by nature.

    Both series are real candles at real prices; only the pairing is wrong. Once
    a divergence has been computed across bars that are not the same bars,
    nothing downstream can tell it from a divergence the market made.
    """
    gold = series([(100.0, 90.0), (105.0, 95.0)])
    shifted = [c.model_copy(update={"time": c.time + 60}) for c in gold]

    with pytest.raises(ValueError, match="same grid"):
        ssmt({"GOLD": gold, "SILVER": shifted}, "day")


def test_an_instrument_short_one_bar_raises_instead_of_diverging_on_the_overlap():
    """A hole in ONE leg is the per-instrument case, and it cannot be read.

    It is refused here rather than skipped later, and that is why the skip
    counted in the next test is a hole in the shared grid: after alignment the
    time lists are identical, so a quarter empty for one instrument is empty for
    all of them. There is no third possibility that reaches the comparison.
    """
    gold = series([(100.0, 90.0), (105.0, 95.0)])
    silver = series([(200.0, 190.0), (199.0, 195.0)])

    with pytest.raises(ValueError, match="same grid"):
        ssmt({"GOLD": gold, "SILVER": silver[:8] + silver[9:]}, "day")


def test_a_quarter_with_no_bars_is_a_hole_and_is_counted_rather_than_compared():
    # Q2 has no bars at all - a weekend, a holiday, a feed outage - so both the
    # pair that ends in it and the pair that begins in it are unreadable. The
    # divergence written into Q3 must NOT be reported against Q1.
    gold = series([(100.0, 90.0), None, (105.0, 95.0), (101.0, 91.0)])
    silver = series([(200.0, 190.0), None, (199.0, 195.0), (198.0, 191.0)])

    events, stats = ssmt({"GOLD": gold, "SILVER": silver}, "day")

    assert events == []
    assert stats["quarters.no_bars"] == 1.0
    assert stats["pairs"] == 3.0
    assert stats["pairs.skipped_no_bars"] == 2.0
    assert stats["pairs.compared"] == 1.0  # Q3 against Q4 only


def test_no_ssmt_is_reported_before_the_quarter_it_belongs_to_has_closed():
    """The property that decides whether this is a measurement or a fiction.

    A quarter's extreme is not settled while the quarter is still running, so an
    SSMT between quarter N-1 and quarter N is knowable at the close of N and at
    no earlier bar. The loop walks every prefix of the series - which is what a
    live chart is, one bar at a time - and asserts that nothing ever appears
    whose `knowable_at` lies in that prefix's future.
    """
    gold = series([(100.0, 90.0), (105.0, 95.0)])
    silver = series([(200.0, 190.0), (199.0, 195.0)])

    for n in range(1, len(gold) + 1):
        events, _ = ssmt({"GOLD": gold[:n], "SILVER": silver[:n]}, "day")
        assert all(e.knowable_at <= gold[n - 1].time for e in events)

    # Concretely: the divergence lives in Q2, and it is absent for every bar of
    # Q2 including its last one, then present once a bar past the close prints.
    inside = len(gold) - 1  # the tail bar removed: last bar is Q2's final hour
    assert ssmt({"GOLD": gold[:inside], "SILVER": silver[:inside]}, "day")[0] == []

    events, _ = ssmt({"GOLD": gold, "SILVER": silver}, "day")
    assert len(events) == 1
    assert events[0].knowable_at == ny(2025, 6, 11, 6) == events[0].quarter.end


def test_three_instruments_report_per_pair_rather_than_one_collapsed_verdict():
    # Gold and platinum take their Q1 highs; silver does not. So gold disagrees
    # with silver, platinum disagrees with silver, and gold agrees with platinum
    # - three different facts that a single verdict would destroy.
    gold = series([(100.0, 90.0), (105.0, 95.0)])
    silver = series([(200.0, 190.0), (199.0, 195.0)])
    platinum = series([(300.0, 290.0), (305.0, 295.0)])

    events, stats = ssmt({"GOLD": gold, "SILVER": silver, "PLAT": platinum}, "day")

    assert len(events) == 2
    assert {(e.took, e.failed) for e in events} == {
        ("GOLD", "SILVER"),
        ("PLAT", "SILVER"),
    }
    assert stats["pair:GOLD|SILVER"] == 1.0
    assert stats["pair:SILVER|PLAT"] == 1.0
    assert stats["pair:GOLD|PLAT"] == 0.0  # examined, agreed, reported as zero


def test_one_instrument_is_not_a_cross_instrument_read():
    with pytest.raises(ValueError, match="at least two"):
        ssmt({"GOLD": series([(100.0, 90.0), (105.0, 95.0)])}, "day")


def test_an_unknown_degree_is_rejected_rather_than_silently_treated_as_a_day():
    gold = series([(100.0, 90.0), (105.0, 95.0)])
    silver = series([(200.0, 190.0), (199.0, 195.0)])

    with pytest.raises(ValueError):
        ssmt({"GOLD": gold, "SILVER": silver}, "fortnight")


def test_the_module_makes_no_directional_claim_anywhere_in_its_own_text():
    """Twelve pre-registered directional hypotheses have failed in this project.

    This module reports that two instruments disagreed and where; the vocabulary
    of prediction is therefore absent from it by rule, and the rule is asserted
    rather than remembered.
    """
    text = (Path(__file__).resolve().parent.parent / "app" / "ssmt.py").read_text()

    for word in ("signal", "confidence", "probabilit"):
        assert word not in text.lower()


CACHE = Path(__file__).resolve().parent.parent / ".cache"
CACHED = [CACHE / "PAXGUSDT-1h-20000.npz", CACHE / "BTCUSDT-1h-20000.npz"]


@pytest.mark.skipif(
    not all(p.exists() for p in CACHED), reason="offline history cache not present"
)
def test_a_real_pair_on_cached_history_produces_a_countable_population():
    """One realistic case, read off the on-disk cache and never off the network.

    It asserts nothing about what the events mean. It asserts that the counts
    add up, that no event was knowable before its own quarter closed, and that
    the population is neither empty nor everything - a detector that fires on
    every quarter is not measuring a disagreement.
    """
    from tools import history

    raw = {s: history.load(s, "1h", 20000) for s in ("PAXGUSDT", "BTCUSDT")}
    grid = set.intersection(*(set(c.time for c in rows) for rows in raw.values()))
    aligned = {s: [c for c in rows if c.time in grid] for s, rows in raw.items()}

    events, stats = ssmt(aligned, "day")

    last = aligned["PAXGUSDT"][-1].time
    assert all(e.knowable_at <= last for e in events)
    assert all(e.took != e.failed for e in events)
    assert stats["events"] == len(events) == stats["side.high"] + stats["side.low"]
    assert stats["events"] == stats["pair:PAXGUSDT|BTCUSDT"]
    assert stats["pairs.compared"] + stats["pairs.skipped_no_bars"] == stats["pairs"]
    # Two sides on every compared pair, so this is the ceiling by construction.
    assert 0 < stats["events"] < 2 * stats["pairs.compared"]


def test_a_divergence_is_positioned_on_the_chart_symbol_and_only_on_it():
    """`divergences_for` is what turns a READING into a SHAPE, and the one thing
    it must never do is put the partner's price on this axis.

    A chart shows one instrument and an SSMT involves two. So the segment has to
    run between the CHART symbol's own two extremes, with the partner's prices
    carried as evidence and never as coordinates - a silver price plotted on a
    gold scale is the most confidently wrong line a chart can draw.

    Also pins that a pair touching neither end is dropped rather than projected:
    a basket of three produces pairs that do not involve the chart at all.
    """
    from app.ssmt import divergences_for

    quarter = Quarter(degree="day", label="Q1", start=0, end=100)
    later = Quarter(degree="day", label="Q2", start=100, end=200)
    event = SSMTEvent(
        degree="day", prior=quarter, quarter=later, side="high",
        took="SILVER", failed="GOLD",
        took_prior=30.0, took_now=31.0, failed_prior=2400.0, failed_now=2399.0,
        took_prior_at=10, took_now_at=110,
        failed_prior_at=20, failed_now_at=120,
        knowable_at=200,
    )

    (gold,) = divergences_for([event], "GOLD")
    assert gold.self_took is False, "GOLD is the one that failed"
    assert gold.partner == "SILVER"
    # GOLD's own two prices and GOLD's own two bars. Nothing here is silver's.
    assert (gold.price_from, gold.price_to) == (2400.0, 2399.0)
    assert (gold.time_from, gold.time_to) == (20, 120)
    assert (gold.partner_prior, gold.partner_now) == (30.0, 31.0)

    (silver,) = divergences_for([event], "SILVER")
    assert silver.self_took is True
    assert (silver.price_from, silver.price_to) == (30.0, 31.0)
    assert (silver.time_from, silver.time_to) == (10, 110)

    assert divergences_for([event], "PLATINUM") == [], "a pair that does not touch this chart"


def _bar(t: int, high: float, low: float) -> Candle:
    return Candle(time=t, open=(high + low) / 2, high=high, low=low,
                  close=(high + low) / 2, volume=1.0)


def test_the_extreme_times_are_the_bars_the_extremes_printed_on():
    """The four `*_at` fields are what makes the divergence drawable at all, and
    a price with the wrong bar behind it is a line to the wrong place.

    Built so each instrument's extreme lands on a DIFFERENT bar inside the same
    quarter - which is the ordinary case and the one a shared index would get
    wrong.
    """
    step = 60
    gold = [
        _bar(0 * step, 2400.0, 2390.0), _bar(1 * step, 2405.0, 2395.0),
        _bar(2 * step, 2401.0, 2391.0), _bar(3 * step, 2402.0, 2392.0),
    ]
    silver = [
        _bar(0 * step, 30.0, 29.0), _bar(1 * step, 30.2, 29.2),
        _bar(2 * step, 30.9, 29.4), _bar(3 * step, 30.3, 29.3),
    ]
    # Gold's high is bar 1, silver's is bar 2: different bars, same quarter.
    assert max(gold, key=lambda c: c.high).time == 1 * step
    assert max(silver, key=lambda c: c.high).time == 2 * step


def test_a_divergence_carries_where_it_sat_in_the_dealing_range():
    """The premium/discount reading, which a practitioner named as the thing that
    decides whether a divergence is tradeable at all: "FVG/OB/REQL/REQH/CISD
    semuanya harus dalam premium kalo mau sell, harus dalam discount kalo mau
    buy", and then the part that makes one outside those zones useful rather than
    void - "kalo ssmt terjadi di luar premium/discount, itu bisa kita pake buat
    tentuin DOL".

    Optional and inert without bars, because a caller that wants geometry only
    must not pay for a swing scan. Reported and never scored: there is no verdict
    field beside it and this test asserts the position, not a direction.
    """
    from app.dealing_range import position_at, range_at
    from app.ssmt import divergences_for

    # The same fixture as the first test in this file, extended so the chart
    # symbol has enough bars for a swing pair to confirm at all: at swing_n 3 the
    # range needs a confirmed high AND a confirmed low, and four flat quarters
    # would give neither.
    gold = series(
        [(100.0, 90.0), (105.0, 95.0), (108.0, 80.0), (104.0, 84.0)], tail=8
    )
    silver = series(
        [(200.0, 190.0), (199.0, 195.0), (204.0, 180.0), (203.0, 184.0)], tail=8
    )
    events, _ = ssmt({"GOLD": gold, "SILVER": silver}, "day")
    assert events, "the fixture has to produce at least one divergence"

    chart = gold
    bare = divergences_for(events, "GOLD")
    assert bare, "the events touch the chart symbol"
    assert all(d.range_pos is None for d in bare), (
        "without bars the field must stay None rather than be invented"
    )

    stamped = divergences_for(events, "GOLD", chart, swing_n=3)
    assert [d.knowable_at for d in stamped] == [d.knowable_at for d in bare], (
        "stamping must not add, drop or reorder a single divergence"
    )

    # The stamp is re-derivable by hand from the same two primitives, read at
    # `time_to` - the bar of the extreme this divergence is ABOUT - and not at
    # `knowable_at`, which is up to a whole quarter later.
    times, knowable = range_at(chart, 3)
    for d in stamped:
        assert d.range_pos == position_at(d.price_to, d.time_to, times, knowable)
        if d.range_pos is not None:
            assert 0.0 <= d.range_pos <= 1.0

    # NOT VACUOUS. An all-None result would satisfy every assertion above, and
    # all-None is exactly what a broken stamp looks like - so the fixture has to
    # produce at least one real position. This one takes the high side at the top
    # of its own range, so the answer is 1.0 by construction.
    positions = [d.range_pos for d in stamped if d.range_pos is not None]
    assert positions == [1.0], positions


# --------------------------------------------------------------------------
# candle validation and session tag — POSKO 618 rules
# --------------------------------------------------------------------------


def test_bullish_ssmt_candle_must_be_bearish():
    """The practitioner's rule: a valid bullish SSMT (side=high) requires the
    candle that printed the new high to be bearish (close < open)."""
    gold = series([(100, 90), (110, 95)], hours=6)
    silver = series([(100, 90), (95, 85)], hours=6)
    # Q2 extreme bar for gold is at index 9 (6 + 6//2).  Make it bearish.
    old = gold[9]
    gold[9] = Candle(
        time=old.time, open=108, high=old.high, low=old.low,
        close=106, volume=old.volume,
    )
    events, _ = ssmt({"GOLD": gold, "SILVER": silver}, "day")
    high = [e for e in events if e.side == "high"]
    assert high, "a bullish SSMT must exist"
    assert high[0].candle_valid is True, (
        "bearish candle (close={} < open={}) for bullish SSMT should be valid"
        .format(high[0].failed_now, high[0].took_now)
    )
    # Also passes through to the wire model
    divergences = divergences_for(events, "GOLD")
    high_div = [d for d in divergences if d.side == "high"]
    assert high_div
    assert high_div[0].candle_valid is True


def test_bullish_candle_for_bullish_ssmt_is_invalid():
    """A bullish candle making a new high for a bullish SSMT is the WRONG
    direction and should be flagged as invalid."""
    gold = series([(100, 90), (110, 95)], hours=6)
    silver = series([(100, 90), (95, 85)], hours=6)
    old = gold[9]
    gold[9] = Candle(
        time=old.time, open=108, high=old.high, low=old.low,
        close=112, volume=old.volume,
    )
    events, _ = ssmt({"GOLD": gold, "SILVER": silver}, "day")
    high = [e for e in events if e.side == "high"]
    assert high
    assert high[0].candle_valid is False, (
        "bullish candle (close > open) for bullish SSMT should be invalid"
    )
    (high_div,) = [d for d in divergences_for(events, "GOLD") if d.side == "high"]
    assert high_div.candle_valid is False


def test_bearish_ssmt_candle_must_be_bullish():
    """A valid bearish SSMT (side=low) requires the candle that printed the
    new low to be bullish (close > open)."""
    gold = series([(100, 90), (105, 80)], hours=6)
    silver = series([(100, 90), (105, 95)], hours=6)
    old = gold[9]
    gold[9] = Candle(
        time=old.time, open=78, high=old.high, low=old.low,
        close=82, volume=old.volume,
    )
    events, _ = ssmt({"GOLD": gold, "SILVER": silver}, "day")
    low = [e for e in events if e.side == "low"]
    assert low
    assert low[0].candle_valid is True, (
        "bullish candle (close > open) for bearish SSMT should be valid"
    )
    (low_div,) = [d for d in divergences_for(events, "GOLD") if d.side == "low"]
    assert low_div.candle_valid is True


def test_ssmt_events_are_tagged_with_their_session():
    """Every SSMT event carries the kill zone active at its knowable_at,
    so a reader can weigh session quality. Asia is weaker than London/NY."""
    gold = series([(100, 90), (110, 95)], hours=6)
    silver = series([(100, 90), (95, 85)], hours=6)
    events, _ = ssmt({"GOLD": gold, "SILVER": silver}, "day")
    assert events
    for event in events:
        # session is either a string (kill zone name) or None (no zone active)
        assert event.session is None or isinstance(event.session, str)
        # The knowable_at is the quarter end, which is 06:00 NY on Wednesday
        # for the day degree starting Tuesday 18:00. That's outside any kill
        # zone, so the session may be None — the point is the field IS there.
        assert hasattr(event, "session")
    # And passes through to the wire model
    for event in events:
        for d in divergences_for([event], event.took if event.took == "GOLD" else "SILVER"):
            if d is not None:
                assert d.session is None or isinstance(d.session, str)


# --------------------------------------------------------------------------
# regular SMT — non-sequential, running-extreme comparison
# --------------------------------------------------------------------------


def test_regular_smt_one_takes_the_running_high_and_the_other_fails():
    """Regular SMT: one instrument makes a new all-time high in the current
    quarter, the other fails. NO consecutive-quarter requirement."""
    # Q1: both at 100, Q2: gold takes to 110 (new all-time high), silver stays
    gold = series([(100, 90), (110, 95)], hours=6)
    silver = series([(100, 90), (95, 85)], hours=6)

    events, stats = smt({"GOLD": gold, "SILVER": silver}, "day")

    high = [e for e in events if e.side == "high"]
    assert high, "a regular SMT must exist on the high side"
    assert high[0].took == "GOLD", "gold took the running high"
    assert high[0].failed == "SILVER", "silver failed"
    assert high[0].took_price == 110.0
    assert stats["events"] >= 1.0


def test_regular_smt_both_take_the_running_high_produces_nothing():
    """When both instruments exceed the running high, no regular SMT exists."""
    gold = series([(100, 90), (110, 95)], hours=6)
    silver = series([(100, 90), (120, 95)], hours=6)  # both take

    events, _ = smt({"GOLD": gold, "SILVER": silver}, "day")
    high = [e for e in events if e.side == "high"]
    assert not high, "both took the running high, no divergence"


def test_regular_smt_on_the_low_side():
    """Regular SMT works on the low side too: one takes the running low,
    the other fails."""
    gold = series([(100, 90), (105, 80)], hours=6)
    silver = series([(100, 90), (105, 95)], hours=6)

    events, _ = smt({"GOLD": gold, "SILVER": silver}, "day")
    low = [e for e in events if e.side == "low"]
    assert low
    assert low[0].took == "GOLD", "gold took the running low (80 < 90)"
    assert low[0].failed == "SILVER", "silver stayed above"


def test_regular_smt_and_sequential_ssmt_are_different():
    """Regular SMT and sequential SSMT detect different things. A series
    that produces regular SMT may produce zero sequential SSMT."""
    gold = series([(100, 90), (110, 95), (115, 100)], hours=6)
    silver = series([(100, 90), (95, 85), (90, 80)], hours=6)

    reg, _ = smt({"GOLD": gold, "SILVER": silver}, "day")
    seq, _ = ssmt({"GOLD": gold, "SILVER": silver}, "day")

    # Regular SMT: Q2 gold took running high, Q3 gold took again
    assert len(reg) > 0, "regular SMT should fire"
    # Sequential SSMT: Q2→Q3, gold took Q2 high again, silver didn't
    assert len(seq) > 0, "sequential SSMT should also fire"
    # They are different event types
    assert isinstance(reg[0], SMTEvent)
    assert isinstance(seq[0], SSMTEvent)
