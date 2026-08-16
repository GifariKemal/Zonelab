"""Guards on the four ways the Dukascopy feed goes wrong silently.

None of these touch the network. Every payload is built here, byte for byte,
because the whole point of the file under test is that a wrong divisor, a
swapped ask/bid, a mis-bucketed tick and a weekend-mistaken-for-an-error all
produce plausible numbers rather than exceptions.
"""

from __future__ import annotations

import asyncio
import lzma
import struct
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.models import Candle
from app.providers import dukascopy
from app.providers.base import ProviderError
from app.providers.dukascopy import (
    RECORD,
    DukascopyProvider,
    _hour,
    decode,
    hour_url,
    to_candles,
)
from app.providers.sources import BinanceProvider

HOUR = datetime(2026, 8, 13, 14, tzinfo=UTC)


def bi5(*records: tuple[int, int, int, float, float]) -> bytes:
    """The real feed's body: LZMA over 20-byte big-endian records, ask first."""
    return lzma.compress(
        b"".join(RECORD.pack(*r) for r in records), format=lzma.FORMAT_ALONE
    )


def test_the_month_in_the_url_is_zero_indexed():
    """August is "07". Off by one here does not raise: it silently serves the
    neighbouring month, and every bar downstream is real but from the wrong
    week. It is the single most common defect in implementations of this feed.
    """
    assert hour_url("XAUUSD", HOUR).endswith("/XAUUSD/2026/07/13/14h_ticks.bi5")
    assert hour_url("XAUUSD", datetime(2026, 1, 2, 3, tzinfo=UTC)).endswith(
        "/XAUUSD/2026/00/02/03h_ticks.bi5"
    )


def test_gold_prices_come_out_at_the_right_scale_with_ask_before_bid():
    """XAU/USD is priceScale 3, so the divisor is 1000, NOT the 100000 that
    works for EUR/USD. At 100000 gold prints as 4.37 and at 100 as 43733; both
    are numbers, neither is an error, and only the magnitude gives it away.
    """
    payload = bi5((171, 4_373_355, 4_372_785, 0.5, 0.25))
    (ms, bid, ask, volume), = decode(payload, HOUR, 1000.0)

    assert ask == pytest.approx(4373.355)
    assert bid == pytest.approx(4372.785)
    assert ask - bid == pytest.approx(0.570)  # ask first in the record, so positive
    assert ms == int(HOUR.timestamp()) * 1000 + 171
    assert volume == pytest.approx(0.75)

    # Same bytes read as an FX major, to pin that the divisor is what moves.
    (_, eur_bid, _, _), = decode(payload, HOUR, 100000.0)
    assert eur_bid == pytest.approx(43.72785)


def test_ticks_land_in_their_own_bar_and_the_spread_is_the_mean():
    """A tick at :14:59 belongs to the 14:45 bar and one at :15:00 does not.
    The bar is the BID series - a long exits at the bid - and the spread is the
    mean over the bar, so a bar's cost is its own, not the last tick's.
    """
    base = int(HOUR.timestamp())
    ticks = [
        (base * 1000, 100.0, 100.2, 1.0),  # 14:00 bar, spread 0.2
        (base * 1000 + 60_000, 101.0, 101.4, 2.0),  # 14:01, still the 14:00 bar
        (base * 1000 + 899_999, 99.0, 99.6, 3.0),  # 14:14:59.999, last of it
        (base * 1000 + 900_000, 105.0, 105.1, 4.0),  # 14:15:00.000, next bar
    ]
    bars = to_candles(ticks, "15m", base, base + 1800)

    assert [c.time for c in bars] == [base, base + 900]
    first, second = bars
    assert (first.open, first.high, first.low, first.close) == (100.0, 101.0, 99.0, 99.0)
    assert first.volume == pytest.approx(6.0)
    assert first.spread == pytest.approx((0.2 + 0.4 + 0.6) / 3)
    assert second.spread == pytest.approx(0.1)


def test_a_bar_straddling_the_downloaded_edge_is_dropped():
    """Only whole bars. A bar whose later hours were never downloaded would
    get its close from whichever tick sat nearest the edge - a real price, in
    the wrong place, on the newest bar the user is looking at.
    """
    base = int(HOUR.timestamp())
    ticks = [(base * 1000 + 100, 100.0, 100.2, 1.0)]
    assert to_candles(ticks, "1h", base, base + 3600) != []
    assert to_candles(ticks, "1h", base, base + 1800) == []  # right edge cuts it
    assert to_candles(ticks, "1h", base + 60, base + 3600) == []  # left edge does


def test_a_missing_hour_is_a_gap_not_an_error(tmp_path, monkeypatch):
    """Measured against the live feed on 2026-08-16: a weekend hour answers
    HTTP 200 with an empty body, an unpublished hour answers 404. Raising on
    either would abort every download that crosses a Saturday, which is every
    download, and the failure would read as "the vendor is down".

    The cache is redirected at a temp directory so the test cannot write into
    the developer's real .cache, and each case gets its OWN hour, because an
    empty 200 is cached: asking one hour four different questions is something
    a completed hour can never be asked in reality, and reusing it here would
    just serve the first answer back from disk.
    """
    monkeypatch.setattr(dukascopy, "HOUR_CACHE", tmp_path)

    async def run(handler, hour):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _hour(client, "XAUUSD", hour, 1000.0)

    assert asyncio.run(run(lambda r: httpx.Response(200, content=b""), HOUR)) == []
    assert asyncio.run(
        run(lambda r: httpx.Response(404), HOUR - timedelta(hours=1))) == []
    assert decode(b"", HOUR, 1000.0) == []

    # A body that is neither is still an error, and it names the vendor rather
    # than surfacing as a bare 500 the way a stray LZMAError would.
    with pytest.raises(ProviderError, match="dukascopy"):
        asyncio.run(run(lambda r: httpx.Response(200, content=b"not lzma"),
                        HOUR - timedelta(hours=2)))
    with pytest.raises(ProviderError, match="403"):
        asyncio.run(run(lambda r: httpx.Response(403), HOUR - timedelta(hours=3)))


def test_a_bulk_pull_tolerates_an_unreachable_hour_and_a_chart_does_not(
    tmp_path, monkeypatch
):
    """The one asymmetry in this module, and it is deliberate.

    A chart quietly missing an hour is a lie about the market and the user
    cannot see the hole, so interactively an unreachable hour must be said. In a
    bulk pull the rule inverts: measured 2026-08-16, the feed stops accepting
    connections for a stretch after a few hundred hours, and under all-or-
    nothing a 5000-hour download died at hour 144 and could never finish.
    """
    monkeypatch.setattr(dukascopy, "HOUR_CACHE", tmp_path)

    # Patched at _hour, not at the transport: fetch_ticks builds its own
    # AsyncClient, so a MockTransport handed to the test's client is never used
    # and the test silently reaches the real feed. It did exactly that once.
    async def refuse(client, vendor, hour, divisor):
        raise ProviderError("network error contacting ...: ConnectTimeout")

    monkeypatch.setattr(dukascopy, "_hour", refuse)
    hours = [HOUR - timedelta(hours=h) for h in range(3)]

    async def run(tolerate):
        return await dukascopy.fetch_ticks("XAUUSD", hours, tolerate_gaps=tolerate)

    with pytest.raises(ProviderError):
        asyncio.run(run(False))

    ticks, failed = asyncio.run(run(True))
    assert ticks == []
    # Returned, not logged, so a caller cannot mistake a holed pull for a whole
    # one - which is what stops the holes being written into the bar cache.
    assert failed == len(hours)


def test_a_past_hour_is_fetched_once_and_a_404_is_never_cached(tmp_path, monkeypatch):
    """The cache is what makes this feed usable: one HTTP request PER HOUR means
    a 500-bar H1 chart is 500 requests, and changing timeframe would pay for the
    same ticks again. A completed hour never changes, so caching it is correct.

    A 404 is deliberately NOT cached. It says the feed has not published the
    hour, which is a fact about the feed rather than about the market, so
    caching it would freeze a merely-late hour as permanently empty.
    """
    monkeypatch.setattr(dukascopy, "HOUR_CACHE", tmp_path)
    calls = {"n": 0}

    def serve(status: int, body: bytes):
        def handler(request):
            calls["n"] += 1
            return httpx.Response(status, content=body)
        return handler

    async def run(handler):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _hour(client, "XAUUSD", HOUR, 1000.0)

    payload = lzma.compress(struct.pack(">3i2f", 1000, 4373_500, 4372_900, 1.0, 1.0))
    assert asyncio.run(run(serve(200, payload))) != []
    assert calls["n"] == 1
    assert asyncio.run(run(serve(200, payload))) != []
    assert calls["n"] == 1, "second look at a completed hour must not hit the feed"

    calls["n"] = 0
    other = HOUR - timedelta(hours=1)

    async def run_other(handler):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _hour(client, "XAUUSD", other, 1000.0)

    assert asyncio.run(run_other(serve(404, b""))) == []
    assert asyncio.run(run_other(serve(404, b""))) == []
    assert calls["n"] == 2, "a 404 must be re-asked, not remembered"


def test_an_oversized_interactive_request_is_refused_rather_than_awaited():
    """One request per hour of ticks, so a big ask is minutes of silence. The
    provider has to say so; a UI cannot tell a slow fetch from a hung one.
    """
    with pytest.raises(ProviderError, match="interactive cap"):
        asyncio.run(DukascopyProvider().fetch("XAUUSD", "1d", 500))


def test_only_dukascopy_fills_in_a_spread(monkeypatch):
    """`spread` is optional so nothing existing breaks, which means consumers
    must handle None. A candle from any other provider proves the default is
    None and not a silently helpful 0.0.
    """
    assert Candle(time=0, open=1, high=1, low=1, close=1).spread is None

    async def one_kline(url, params=None):
        return [[1_700_000_000_000, "2400.0", "2401.0", "2399.0", "2400.5", "12.0"]]

    monkeypatch.setattr("app.providers.sources._get_json", one_kline)
    candles = asyncio.run(BinanceProvider().fetch("XAUUSD", "15m", 10))
    assert [c.spread for c in candles] == [None]


def test_the_bulk_loader_folds_ticks_instead_of_hoarding_them(monkeypatch):
    """Same bars as to_candles, but bounded memory.

    A 20000-bar pull used to hold every tick for the whole range in one list and
    reached 6 GB before it was killed - 5000 trading hours is tens of millions of
    4-tuples and Python charges over a hundred bytes for each. The loader now
    folds each batch into per-bar accumulators as it lands. That is only worth
    doing if it produces IDENTICAL bars, which is what this asserts, and it is
    checked across a batch boundary because that is the one place a fold can go
    wrong: a bar split over two batches must not take its open from whichever
    batch was processed first.
    """
    import numpy as np

    from app.providers.dukascopy import to_candles
    from tools import dukascopy as loader

    step = 900  # 15m
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    base = int(end.timestamp())

    # Ticks spanning several hours, several per bar, with a drifting price so
    # open/high/low/close are all distinguishable.
    ticks = []
    for k in range(3000):
        ms = (base - 200 * 3600 + k * 60) * 1000
        bid = 4000.0 + (k % 37) * 0.1
        ticks.append((ms, bid, bid + 0.5, 1.0))

    served = {"n": 0}

    async def fake_fetch(symbol, hours, tolerate_gaps=False):
        # Hand back only the ticks inside the requested hours, so the split
        # across batches is the real one the loader would see.
        lo = int(min(hours).timestamp()) * 1000
        hi = (int(max(hours).timestamp()) + 3600) * 1000
        served["n"] += 1
        return [t for t in ticks if lo <= t[0] < hi], 0

    monkeypatch.setattr(loader, "fetch_ticks", fake_fetch)
    rows, missed = loader._download("XAUUSD", "15m", 40)
    assert missed == 0
    assert served["n"] > 1, "the point is a MULTI-batch fold"

    covered_from = base - 200 * 3600 - 3600
    expected = to_candles(ticks, "15m", covered_from, base)[-40:]
    assert len(rows) == len(expected) > 0
    for row, want in zip(rows, expected):
        assert int(row[0]) == want.time
        assert row[1] == pytest.approx(want.open)
        assert row[2] == pytest.approx(want.high)
        assert row[3] == pytest.approx(want.low)
        assert row[4] == pytest.approx(want.close)
        assert row[6] == pytest.approx(want.spread)
