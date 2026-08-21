"""Guards on the shared time grid a cross-instrument read stands on.

SSMT - divergence between correlated instruments - is a claim about two symbols
AT THE SAME MOMENT. Every failure here is silent by nature: the candles stay
real and the prices stay real, only the pairing goes wrong, so a divergence born
of a one-minute boundary offset or a filled hole reads exactly like a divergence
born of the market. These tests are the only place that difference is visible.
"""

from __future__ import annotations

import asyncio

import pytest

from app.aligned import MIN_GRID, load_aligned
from app.models import Candle
from app.providers import ProviderError

STEP = 900  # 15m, the interval every fixture below is stamped on
START = 1_700_000_000


def _price(base: float, t: int) -> float:
    """A price that is a function of the bar's OWN time, and deliberately not a
    straight line: on a linear fixture an interpolated value equals the true one
    and the interpolation cannot be caught. The half-step zigzag makes the mean
    of two neighbours a value no real bar here ever takes."""
    i = (t - START) // STEP
    return base + i + (i % 2) * 0.5


def _series(times: list[int], base: float) -> list[Candle]:
    return [
        Candle(
            time=t,
            open=_price(base, t),
            high=_price(base, t) + 0.5,
            low=_price(base, t) - 0.5,
            close=_price(base, t),
            volume=1.0,
        )
        for t in times
    ]


def _fake_feed(monkeypatch, feeds: dict[str, list[Candle]]) -> None:
    async def get_candles(symbol, interval, bars, provider=None):
        return feeds[symbol], "fixture"

    monkeypatch.setattr("app.aligned.get_candles", get_candles)


def _grid(n: int, offset: int = 0) -> list[int]:
    return [START + offset + i * STEP for i in range(n)]


def test_two_partly_overlapping_symbols_come_back_on_the_common_grid(monkeypatch):
    """The plain case, and the one every later assertion depends on: after
    alignment the two lists are the same length and carry the same timestamps
    in the same order, so index i of one is comparable with index i of the
    other. Without that, "index i against index i" - which is what any
    divergence read does - is comparing different moments."""
    # GOLD starts 20 bars earlier, SILVER runs 20 bars later. 80 in common.
    _fake_feed(monkeypatch, {
        "GOLD": _series(_grid(100), 2400.0),
        "SILVER": _series(_grid(100, offset=20 * STEP), 30.0),
    })

    series, stats = asyncio.run(load_aligned(["GOLD", "SILVER"], "15m", 100))

    assert [c.time for c in series["GOLD"]] == [c.time for c in series["SILVER"]]
    assert len(series["GOLD"]) == len(series["SILVER"]) == 80
    assert stats["grid"] == 80.0
    assert series["GOLD"][0].time == START + 20 * STEP


def test_a_bar_missing_from_one_symbol_is_dropped_from_every_symbol(monkeypatch):
    """A hole in ONE feed has to remove that timestamp everywhere, not just
    from the feed that was short. Keeping the bar for the other symbols leaves
    the two lists different lengths, and then every comparison after the hole is
    off by one - a divergence manufactured by an index, not by the market."""
    hole = START + 40 * STEP
    _fake_feed(monkeypatch, {
        "GOLD": _series([t for t in _grid(100) if t != hole], 2400.0),
        "SILVER": _series(_grid(100), 30.0),
        "PLATINUM": _series(_grid(100), 900.0),
    })

    series, stats = asyncio.run(load_aligned(["GOLD", "SILVER", "PLATINUM"], "15m", 100))

    for symbol, rows in series.items():
        assert hole not in {c.time for c in rows}, symbol
        assert len(rows) == 99, symbol
    assert stats["grid"] == 99.0
    # The two complete feeds each lost a bar they did have. That loss is the
    # point: it is paid in honesty about the hole, not hidden by filling it.
    assert stats["fetched:SILVER"] == 100.0 and stats["kept:SILVER"] == 99.0


def test_no_price_is_carried_forward_or_interpolated_across_a_hole(monkeypatch):
    """The failure this module exists to prevent, stated as arithmetic.

    GOLD is missing bar 40. A carry-forward would put bar 39's price on the 40
    slot; an interpolation would put the mean of 39 and 41 there. Both are
    arithmetically obvious against `_series`, where price is a function of the
    bar's own time. Neither may appear, and the timestamp must simply be gone.
    """
    hole = START + 40 * STEP
    gold = _series([t for t in _grid(100) if t != hole], 2400.0)
    _fake_feed(monkeypatch, {"GOLD": gold, "SILVER": _series(_grid(100), 30.0)})

    series, _ = asyncio.run(load_aligned(["GOLD", "SILVER"], "15m", 100))

    for symbol, base in (("GOLD", 2400.0), ("SILVER", 30.0)):
        for candle in series[symbol]:
            # Every surviving price is still the one its own bar arrived with.
            assert candle.close == _price(base, candle.time)
            assert candle.open == candle.close
            assert candle.high == candle.close + 0.5
            assert candle.low == candle.close - 0.5

    closes = [c.close for c in series["GOLD"]]
    padded = _price(2400.0, hole)  # 2440.0, the bar that was never fetched
    carried = _price(2400.0, hole - STEP)  # 2439.5, bar 39 held over
    interpolated = (carried + _price(2400.0, hole + STEP)) / 2  # 2440.5
    assert padded not in closes, "a bar the feed never sent came back"
    assert interpolated not in closes, "the hole was interpolated"
    # 2439.5 is a legitimate price - it is bar 39's - so the test is that it
    # occurs ONCE. Twice would be bar 39 carried forward onto the hole.
    assert closes.count(carried) == 1


def test_the_stats_say_what_the_intersection_cost_each_symbol(monkeypatch):
    """A caller that asked for 500 bars and got 340 must be able to see that,
    and see WHICH feed was short. Silent truncation is the thing this project
    refuses everywhere else; a stats dict that only reported the grid size would
    say the series is short without saying who shortened it."""
    _fake_feed(monkeypatch, {
        "GOLD": _series(_grid(200), 2400.0),
        "SILVER": _series(_grid(120), 30.0),  # a shorter history, not a hole
    })

    series, stats = asyncio.run(load_aligned(["GOLD", "SILVER"], "15m", 200))

    assert stats == {
        "grid": 120.0,
        "requested": 200.0,
        "skipped": [],
        "fetched:GOLD": 200.0,
        "kept:GOLD": 120.0,
        "fetched:SILVER": 120.0,
        "kept:SILVER": 120.0,
    }
    # The report has to match what was actually handed back, or it is decoration.
    for symbol, rows in series.items():
        assert stats[f"kept:{symbol}"] == float(len(rows))


def test_an_empty_intersection_raises_instead_of_returning_nothing_quietly(monkeypatch):
    """Boundaries one minute apart, which is the realistic version of this
    failure: both feeds are 15m, both cover the same hours, and not a single
    timestamp matches. Returning an empty series here would look like a quiet
    market rather than two incompatible clocks."""
    _fake_feed(monkeypatch, {
        "GOLD": _series(_grid(100), 2400.0),
        "SILVER": _series(_grid(100, offset=60), 30.0),
    })

    with pytest.raises(ProviderError, match="share only 0 bar times"):
        asyncio.run(load_aligned(["GOLD", "SILVER"], "15m", 100))


def test_a_tiny_intersection_raises_with_the_numbers_in_the_message(monkeypatch):
    """Six shared bars are worse than none, because six bars still plot. The
    error has to carry the counts so the caller can see the shape of the
    mismatch instead of guessing at an empty chart."""
    _fake_feed(monkeypatch, {
        "GOLD": _series(_grid(100), 2400.0),
        "SILVER": _series(_grid(100, offset=94 * STEP), 30.0),
    })

    with pytest.raises(ProviderError) as caught:
        asyncio.run(load_aligned(["GOLD", "SILVER"], "15m", 100))

    message = str(caught.value)
    assert "share only 6 bar times" in message
    assert "GOLD=100" in message and "SILVER=100" in message
    assert f"minimum {MIN_GRID}" in message


def test_one_symbol_is_a_no_op_that_still_reports_stats(monkeypatch):
    """Degenerate on purpose: the intersection of one set is that set. Nothing
    may be dropped, and the stats must still be well formed, because a caller
    reading `fetched:` against `kept:` should not have to special-case the
    single-symbol call."""
    bars = _series(_grid(120), 2400.0)
    _fake_feed(monkeypatch, {"GOLD": bars})

    series, stats = asyncio.run(load_aligned(["GOLD"], "15m", 120))

    assert series["GOLD"] == bars
    assert stats == {
        "grid": 120.0,
        "requested": 120.0,
        "skipped": [],
        "fetched:GOLD": 120.0,
        "kept:GOLD": 120.0,
    }


def test_no_symbols_at_all_is_refused(monkeypatch):
    """`set.intersection(*())` is a TypeError, and a TypeError from inside a
    fetch path reaches the client as a bare 500 naming nothing. ProviderError is
    how this codebase says a request cannot be served."""
    _fake_feed(monkeypatch, {})
    with pytest.raises(ProviderError, match="at least one symbol"):
        asyncio.run(load_aligned([], "15m", 100))


def test_a_repeated_symbol_is_fetched_once(monkeypatch):
    """The same instrument twice would collapse into one dict key anyway, so
    fetching it twice is a wasted upstream call on a feed metered at 5 a
    minute."""
    calls: list[str] = []

    async def counting(symbol, interval, bars, provider=None):
        calls.append(symbol)
        return _series(_grid(100), 2400.0), "fixture"

    monkeypatch.setattr("app.aligned.get_candles", counting)

    series, stats = asyncio.run(load_aligned(["GOLD", "GOLD"], "15m", 100))

    assert calls == ["GOLD"]
    assert list(series) == ["GOLD"] and stats["grid"] == 100.0


def test_two_real_sessions_intersect_without_being_filled(monkeypatch):
    """The realistic case, entirely offline: COMEX gold futures (exchange
    hours, with a daily break) against BTCUSDT (never closes), both 1h, both
    read from backend/.cache.

    Measured on those cached files: 500 bars each, 346 shared. That loss is
    what a real session difference costs, and it is exactly what a caller must
    be shown rather than have filled in. The assertion is a band, not the
    number, because the cached files can legitimately be refreshed - what must
    never change is that both sides come back equal, aligned, and shorter.
    """
    from tools import history

    feeds = {
        "yahoo:XAUUSD": history.load("yahoo:XAUUSD", "1h", 500),
        "BTCUSDT": history.load("BTCUSDT", "1h", 500),
    }

    _fake_feed(monkeypatch, feeds)
    series, stats = asyncio.run(load_aligned(["yahoo:XAUUSD", "BTCUSDT"], "1h", 500))

    gold, btc = series["yahoo:XAUUSD"], series["BTCUSDT"]
    assert [c.time for c in gold] == [c.time for c in btc]
    assert MIN_GRID <= len(gold) < 500, "the two sessions must not align perfectly"
    assert stats["fetched:BTCUSDT"] == 500.0
    assert stats["kept:yahoo:XAUUSD"] == float(len(gold))

    # Prices survived untouched, and every kept bar existed in BOTH raw feeds.
    raw_gold = {c.time: c for c in feeds["yahoo:XAUUSD"]}
    raw_btc = {c.time: c for c in feeds["BTCUSDT"]}
    for candle in gold:
        assert candle.time in raw_btc
        assert candle.close == raw_gold[candle.time].close


# ------------------------------------- one partner missing, the rest survive


def _feed_with_failures(monkeypatch, feeds, broken: dict[str, str]) -> None:
    """Serve `feeds`, and raise ProviderError for anything in `broken`.

    The realistic shape of this: a broker with no bond contract, a vendor whose
    plan excludes an index, a typo. The provider layer already answers with a
    sentence naming the symbol, and that sentence is what has to survive.
    """

    async def get_candles(symbol, interval, bars, provider=None):
        if symbol in broken:
            raise ProviderError(broken[symbol])
        return feeds[symbol], "fixture"

    monkeypatch.setattr("app.aligned.get_candles", get_candles)


def test_one_unavailable_partner_does_not_take_the_others_with_it(monkeypatch):
    """The defect this was written after, and it cost seven partners.

    Asking for gold against silver, the dollar, oil, the Nasdaq, bitcoin, the yen
    AND the ten-year note returned `{"drawn": 0, "error": "mt5 does not carry
    US10Y"}` on a live call. `asyncio.gather` had no `return_exceptions`, so the
    first failure cancelled every sibling fetch - and the one that failed was the
    one instrument this broker has no contract for, a permanent condition rather
    than a transient one. Six correct correlations and a full divergence read were
    thrown away to report a fact about a seventh.
    """
    _feed_with_failures(
        monkeypatch,
        {
            "GOLD": _series(_grid(120), 2400.0),
            "SILVER": _series(_grid(120), 30.0),
            "COPPER": _series(_grid(120), 4.0),
        },
        {"BOND": "mt5 does not carry BOND"},
    )

    series, stats = asyncio.run(
        load_aligned(["GOLD", "SILVER", "BOND", "COPPER"], "15m", 120)
    )

    assert sorted(series) == ["COPPER", "GOLD", "SILVER"]
    assert stats["grid"] == 120.0
    # Named and quoted, not counted. A reader who is told "1 skipped" has to guess
    # which instrument vanished and why; the provider already said.
    assert stats["skipped"] == ["BOND: mt5 does not carry BOND"]
    assert "fetched:BOND" not in stats, "a symbol that never arrived has no count"


def test_the_base_symbol_failing_is_still_fatal(monkeypatch):
    """Dropping it would leave partners with nothing to be compared against, and
    the natural next step - comparing them with each other - answers a question
    nobody asked."""
    _feed_with_failures(
        monkeypatch,
        {"SILVER": _series(_grid(120), 30.0)},
        {"GOLD": "mt5 does not carry GOLD"},
    )

    with pytest.raises(ProviderError, match="GOLD is the base symbol"):
        asyncio.run(load_aligned(["GOLD", "SILVER"], "15m", 120))


def test_losing_every_partner_says_so_rather_than_returning_a_lone_series(monkeypatch):
    """A one-entry dict would flow downstream and produce zero divergences and
    zero correlations - which reads as "the market agreed today" rather than
    "nothing was compared"."""
    _feed_with_failures(
        monkeypatch,
        {"GOLD": _series(_grid(120), 2400.0)},
        {"SILVER": "mt5 does not carry SILVER", "BOND": "mt5 does not carry BOND"},
    )

    with pytest.raises(ProviderError) as caught:
        asyncio.run(load_aligned(["GOLD", "SILVER", "BOND"], "15m", 120))

    message = str(caught.value)
    assert "nothing left to compare GOLD with" in message
    assert "SILVER" in message and "BOND" in message
