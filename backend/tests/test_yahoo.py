"""Guards on the ways Yahoo's chart endpoint gives a wrong answer as an HTTP 200.

None of these touch the network: every payload is built here. That is the whole
point of the file under test - Yahoo is an undocumented endpoint whose failure
modes are successes. A coarser timeframe than the one asked for, a range past
the intraday wall, a session hole padded with nulls and a missing OHLC series
all arrive as 200s, and three of the four produce numbers that look right.
"""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from app.providers.base import ProviderError
from app.providers.sources import YahooProvider
from tools import history, yahoo

HOUR = 1_786_000_000 // 3600 * 3600


def chart(times: list[int], **series) -> dict:
    """The v8 payload shape, with OHLC defaulting to a flat plausible series."""
    quote = {
        key: series.get(key, [4400.0 + i for i in range(len(times))])
        for key in ("open", "high", "low", "close")
    }
    quote["volume"] = series.get("volume", [10.0] * len(times))
    for key in ("open", "high", "low", "close", "volume"):
        if key in series and series[key] is None:
            del quote[key]
    return {"chart": {"result": [{"timestamp": times, "indicators": {"quote": [quote]}}]}}


def capture(monkeypatch, payload):
    """Swap the one network seam and hand back what the provider asked for."""
    seen: dict = {}

    async def fake(url, params=None):
        seen["url"], seen["params"] = url, params
        return payload

    monkeypatch.setattr("app.providers.sources._get_json", fake)
    return seen


def test_gold_is_fetched_as_the_comex_future_and_carries_no_spread(monkeypatch):
    """Yahoo has no spot gold - XAUUSD=X and XAU=X both 404, measured
    2026-08-16 - so the app's XAUUSD must resolve to GC=F, a different
    instrument. And Yahoo ships one price per bar, so `spread` stays None:
    None means "not measured", and a helpful 0.0 here would reinstate the
    free-trading assumption the field exists to remove.
    """
    times = [HOUR + i * 900 for i in range(3)]
    seen = capture(monkeypatch, chart(times))

    candles = asyncio.run(YahooProvider().fetch("XAUUSD", "15m", 100))

    assert seen["url"].endswith("/GC%3DF") or seen["url"].endswith("/GC=F")
    assert [c.time for c in candles] == times
    assert [c.spread for c in candles] == [None, None, None]
    assert candles[0].open == pytest.approx(4400.0)


def test_the_interval_is_translated_into_yahoos_own_dialect(monkeypatch):
    """Yahoo spells the hour "60m" but the four-hour just "4h". Passing "1h"
    through untranslated does not fail loudly - Yahoo answers 200 with a
    default timeframe - so the mapping is what stops a silent substitution.

    4h is served natively and was refused here until 2026-08-16 on the belief
    that it was not: measured, range=730d returns 4348 bars whose modal gap is
    exactly 14400s, so a whole timeframe was being thrown away.
    """
    seen = capture(monkeypatch, chart([HOUR + i * 3600 for i in range(3)]))
    asyncio.run(YahooProvider().fetch("XAUUSD", "1h", 100))
    assert seen["params"]["interval"] == "60m"

    seen = capture(monkeypatch, chart([HOUR + i * 14400 for i in range(3)]))
    asyncio.run(YahooProvider().fetch("XAUUSD", "4h", 100))
    assert seen["params"]["interval"] == "4h"

    with pytest.raises(ProviderError, match="yahoo has no 3h interval"):
        asyncio.run(YahooProvider().fetch("XAUUSD", "3h", 100))


def test_the_requested_range_is_clamped_to_yahoos_intraday_wall(monkeypatch):
    """Measured 2026-08-16: 15m data is refused outright past 60 days and 1h
    past 730, and the limit is on RECENCY, so the window cannot be paged
    backwards to get more. 3000 15m bars works out at a 69-day range, which is
    inside `max_bars` and used to come back as HTTP 422 - no chart at all
    rather than a shorter one.
    """
    seen = capture(monkeypatch, chart([HOUR + i * 900 for i in range(3)]))
    asyncio.run(YahooProvider().fetch("XAUUSD", "15m", 3000))
    assert seen["params"]["range"] == "60d"

    seen = capture(monkeypatch, chart([HOUR + i * 3600 for i in range(3)]))
    asyncio.run(YahooProvider().fetch("XAUUSD", "1h", 20000))
    assert seen["params"]["range"] == "730d"

    # 1m is eight days, not the seven every write-up repeats: measured, 8d
    # returns 9655 bars and 9d is the first to be refused. A day of 1m bars is
    # 1440 of them, so the difference is not a rounding detail.
    seen = capture(monkeypatch, chart([HOUR + i * 60 for i in range(3)]))
    asyncio.run(YahooProvider().fetch("XAUUSD", "1m", 20000))
    assert seen["params"]["range"] == "8d"


def test_a_silently_coarser_series_is_refused_rather_than_drawn(monkeypatch):
    """The worst thing this endpoint does. Measured 2026-08-16: asked for
    interval=1h over range=max it returned 267 bars spanning 2000 to 2026,
    which is monthly. Every price is real and every bar is on the wrong
    timeframe, and a zone drawn on them looks exactly like a valid one.
    """
    daily = [HOUR + i * 86400 for i in range(5)]
    capture(monkeypatch, chart(daily))

    with pytest.raises(ProviderError, match="yahoo.*downgraded the interval"):
        asyncio.run(YahooProvider().fetch("XAUUSD", "15m", 100))

    # The check must not fire on a real session break, which is a gap BETWEEN
    # bars that are otherwise one interval apart - a weekend, not a downgrade.
    weekend = [HOUR, HOUR + 900, HOUR + 900 + 2 * 86400, HOUR + 1800 + 2 * 86400]
    capture(monkeypatch, chart(weekend))
    assert len(asyncio.run(YahooProvider().fetch("XAUUSD", "15m", 100))) == 4


def test_a_missing_series_names_yahoo_instead_of_raising_a_keyerror(monkeypatch):
    """`_fetch` in main.py converts ProviderError and nothing else, so a
    KeyError on an absent `low` would reach the user as a bare 500 naming no
    vendor. Yahoo's shape is not a contract, so the gap has to be reported.
    """
    capture(monkeypatch, chart([HOUR, HOUR + 900], low=None))
    with pytest.raises(ProviderError, match="yahoo response is missing low"):
        asyncio.run(YahooProvider().fetch("XAUUSD", "15m", 100))

    capture(monkeypatch, {"chart": {"result": [], "error": "Not Found"}})
    with pytest.raises(ProviderError, match="yahoo returned no data"):
        asyncio.run(YahooProvider().fetch("XAUUSD", "15m", 100))


def test_a_null_padded_slot_is_a_hole_in_the_session_not_a_zero_priced_bar(monkeypatch):
    """Yahoo pads non-trading slots inside the returned range with nulls. Read
    as numbers they become bars priced at zero, which is a 100% drop and a
    formation every detector here would happily draw on.
    """
    times = [HOUR + i * 900 for i in range(5)]
    holed = [1.0, 2.0, None, 4.0, 5.0]
    capture(
        monkeypatch,
        chart(times, open=holed, high=holed, low=holed, close=holed),
    )
    candles = asyncio.run(YahooProvider().fetch("XAUUSD", "15m", 100))
    assert [c.time for c in candles] == [times[i] for i in (0, 1, 3, 4)]

    # And the hole must not read as a downgraded interval. The gap check uses
    # the SMALLEST gap for exactly this reason: a padded slot widens one pair,
    # a downgrade widens every one of them.
    assert all(c.close > 0 for c in candles)


def test_the_cache_returns_the_same_bars_without_asking_yahoo_again(monkeypatch, tmp_path):
    """The loader's whole reason for existing. Calibration re-runs must get
    identical bars, otherwise "the score improved" cannot be told apart from
    "the window moved" - and Yahoo's range is anchored to NOW, so an uncached
    second call would silently return a shifted window every time.
    """
    monkeypatch.setattr(yahoo, "CACHE", tmp_path)
    times = [HOUR + i * 900 for i in range(4)]
    calls = {"n": 0}

    async def fake(url, params=None):
        calls["n"] += 1
        return chart(times)

    monkeypatch.setattr("app.providers.sources._get_json", fake)

    first = yahoo.load("XAUUSD", "15m", 4)
    second = yahoo.load("XAUUSD", "15m", 4)
    assert calls["n"] == 1, "a cached series must not be re-downloaded"
    assert [(c.time, c.close) for c in first] == [(c.time, c.close) for c in second]
    assert [c.spread for c in second] == [None] * 4, "npz round-trip must not invent 0.0"

    # A different bar count is a different window and gets its own file.
    yahoo.load("XAUUSD", "15m", 3)
    assert calls["n"] == 2


def test_the_yahoo_prefix_routes_without_disturbing_the_existing_symbols(monkeypatch):
    """`load(symbol, interval, bars)` is called by two dozen tools with bare
    tickers. The cross-check series had to become reachable without any of them
    changing, and without a bare "XAUUSD" ever drifting off Dukascopy spot onto
    the COMEX future.
    """
    seen: list[tuple] = []
    monkeypatch.setattr(yahoo, "load", lambda *a: seen.append(("yahoo", *a)) or [])
    monkeypatch.setattr(history.dukascopy, "load", lambda *a: seen.append(("duka", *a)) or [])

    history.load("yahoo:XAUUSD", "1h", 500)
    history.load("XAUUSD", "1h", 500)

    assert seen == [
        ("yahoo", "XAUUSD", "1h", 500, False),
        ("duka", "XAUUSD", "1h", 500, False),
    ]


def test_the_stored_npz_carries_six_columns_and_no_spread_column():
    """Seven columns is the Dukascopy shape, where the seventh is the measured
    spread. Six here is the assertion that Yahoo has none to store, so nothing
    downstream can read a spread off a futures bar that never had one.
    """
    rows = np.array([[HOUR, 1.0, 2.0, 0.5, 1.5, 9.0]], dtype=np.float64)
    (candle,) = yahoo._to_candles(rows)
    assert (candle.open, candle.high, candle.low, candle.close) == (1.0, 2.0, 0.5, 1.5)
    assert candle.spread is None
