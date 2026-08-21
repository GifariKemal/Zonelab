"""Guards on the two places a wrong answer arrives silently rather than loudly.

Neither of these is about market structure. They are about the seams: the
detector registry the API dispatches through, and the vendor payloads nobody
controls.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.detect import DETECTORS
from app.layers import DETECTOR_IDS, PARAMS_BY_ID
from app.models import DrawRequest
from app.providers import ProviderError
from app.providers.sources import BinanceProvider


def test_every_detector_is_advertised_and_has_the_params_block_it_names():
    """A detector function nobody can switch on, or a menu entry that runs
    nothing, are both silent failures: 200 OK, no zones, no error.

    This guard got STRONGER when `PARAMS_FOR` was deleted. It used to compare
    two dicts that sat four lines apart in the same file - which caught a typo
    and nothing else. Now it compares the function registry against the layer
    catalogue the API actually advertises, so it also fails when a detector
    exists but no menu entry offers it, and when an entry is filed under the
    wrong kind.
    """
    assert set(DETECTORS) == set(DETECTOR_IDS), (
        "a detector exists that the menu does not offer, or the other way round"
    )
    request = DrawRequest(symbol="XAUUSD")
    for name in DETECTORS:
        block = PARAMS_BY_ID[name]
        assert hasattr(request, block), f"DrawRequest has no '{block}' block"


def test_a_short_vendor_row_names_the_provider(monkeypatch):
    """`fetch` in fetching.py converts ProviderError and nothing else, so an
    IndexError from a truncated kline would reach the user as a bare 500 with
    no mention of which vendor sent it.
    """

    async def truncated(url, params=None):
        return [[1_700_000_000_000, "2400.0", "2401.0"]]  # ohlcv cut off after high

    monkeypatch.setattr("app.providers.sources._get_json", truncated)

    with pytest.raises(ProviderError, match="binance"):
        asyncio.run(BinanceProvider().fetch("XAUUSD", "15m", 100))


def test_a_timeout_names_its_cause(monkeypatch):
    """`httpx.ConnectTimeout` can stringify to the EMPTY STRING, and the bare
    f-string then produced "network error contacting <url>: " - a message that
    promises a reason and delivers nothing.

    Measured 2026-08-17 against the live app: api.binance.com resolves to an
    ISP-held address here and times out, and the 502 body was exactly that
    trailing colon. dukascopy.py already learned this; sources.py is the helper
    all four keyed and keyless vendors route through, so it is the one place
    the lesson has to hold.
    """
    import httpx

    from app.providers import sources

    def refuse(request):
        raise httpx.ConnectTimeout("")

    monkeypatch.setattr(
        sources, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(refuse))
    )

    with pytest.raises(ProviderError, match="ConnectTimeout"):
        asyncio.run(sources._get_json("https://api.binance.com/api/v3/klines"))


def test_the_forming_bar_never_reaches_the_detector():
    """Four of six providers shipped it, and it made the drawing lie.

    Measured on 599 real 15m formations before this guard: 42 zone states
    changed and changed back INSIDE one bar, 15 zones vanished and returned,
    and a stop's risk-per-unit swung 14% in 90 seconds with no bar closing.
    The guard lives at the single point every caller routes through, so a new
    provider cannot forget it.
    """
    import time as _time

    from app.models import Candle
    from app.providers import drop_forming

    now = int(_time.time())
    closed = Candle(time=now - 1800, open=1.0, high=1.0, low=1.0, close=1.0)
    forming = Candle(time=now - 60, open=1.0, high=1.0, low=1.0, close=1.0)

    assert drop_forming([closed, forming], "15m") == [closed]
    assert drop_forming([closed], "15m") == [closed]
    # An unknown interval must not silently drop the newest bar: guessing here
    # would be a different lie from the one being fixed.
    assert drop_forming([closed, forming], "nonsense") == [closed, forming]
    assert drop_forming([], "15m") == []


def test_the_response_says_which_bar_it_drew():
    """A live chart that cannot say WHICH BAR it describes is asking to be
    trusted on nothing. Binance is seconds behind and dukascopy up to 59
    minutes, and without a number the two look identical on screen."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = client.post("/api/draw", json={
        "symbol": "BTCUSDT", "interval": "15m", "bars": 200,
        "provider": "synthetic",
    }).json()
    meta = body["meta"]

    for key in ("as_of", "bar_closed_at", "next_close_at", "feed_lag_seconds",
                "fetched_at"):
        assert key in meta, key
    assert meta["bar_closed_at"] == meta["as_of"] + 900
    assert meta["next_close_at"] == meta["as_of"] + 1800
    assert meta["feed_lag_seconds"] >= 0
    # The newest bar is CLOSED, which is the whole point of the guard above.
    assert meta["bar_closed_at"] <= meta["fetched_at"]


def test_the_same_symbol_draws_the_same_prices_in_a_fresh_process():
    """The offline chart must not change when the server restarts.

    This has to run in a SUBPROCESS or it proves nothing. The old seed was
    `abs(hash(symbol))`, and CPython randomises `hash()` of a str once per
    process: inside a single interpreter it looks perfectly deterministic, and
    every in-process assertion anyone could have written would have passed while
    the chart changed on every restart. The failure was only ever visible across
    a process boundary, which is exactly why it survived so long - and why the
    cost of spawning an interpreter here is the point rather than an overhead to
    optimise away.

    Prices only. The time anchor is `now` by design, so the timestamps are
    expected to differ and comparing them would make this test a clock test.
    """
    import subprocess
    import sys

    probe = (
        "import asyncio;"
        "from app.providers.synthetic import SyntheticProvider;"
        "c=asyncio.run(SyntheticProvider().fetch('BTCUSDT','15m',40));"
        "print([x.close for x in c])"
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, check=True
        ).stdout.strip()
        for _ in range(2)
    }
    assert len(runs) == 1, "two fresh processes drew different prices"
    assert runs.pop().startswith("["), "the probe printed no series"


def test_two_requests_for_different_bars_do_not_queue_behind_each_other():
    """The lock is per key, and this is the test that says why that matters.

    A single global lock held across the fetch made every DIFFERENT request wait
    out a full network round trip before it could look at the cache. Measured
    while it was happening, with the harness's browser already closed:
    `/api/candles` took 5.23 seconds against 0.15 for the same call made
    directly, and `POST /api/draw` did not return inside 60 seconds. Health was
    0.34s throughout, which is exactly why it read as a hang and not as a queue.

    Two keys, one slow fetch each. Serialised they take two delays; per key they
    take one. The margin is generous on purpose - this asserts the SHAPE, not a
    timing budget, and a loaded CI box must not turn it red.
    """
    import asyncio
    import time

    from app.models import Candle
    from app.providers import PROVIDERS, get_candles

    DELAY = 0.4
    provider = PROVIDERS["synthetic"]
    original = provider.fetch

    async def slow_fetch(symbol, interval, bars):
        await asyncio.sleep(DELAY)
        return await original(symbol, interval, bars)

    async def both() -> float:
        t0 = time.monotonic()
        await asyncio.gather(
            get_candles("BTCUSDT", "15m", 120, "synthetic"),
            get_candles("BTCUSDT", "15m", 300, "synthetic"),
        )
        return time.monotonic() - t0

    provider.fetch = slow_fetch  # type: ignore[method-assign]
    try:
        elapsed = asyncio.run(both())
    finally:
        provider.fetch = original  # type: ignore[method-assign]

    assert elapsed < DELAY * 1.8, (
        f"two different keys took {elapsed:.2f}s against one {DELAY}s fetch, "
        "so they were serialised"
    )
    assert isinstance(
        asyncio.run(get_candles("BTCUSDT", "15m", 120, "synthetic"))[0][0], Candle
    ), "the cache still returns candles"


class _Fake:
    """A two-bar feed whose newest bar is always still forming."""

    name = "fake"

    def __init__(self, local: bool = False) -> None:
        self.calls: list[int] = []
        if local:
            self.local = True

    def available(self) -> bool:
        return True

    async def fetch(self, symbol: str, interval: str, bars: int):
        from app.models import Candle

        self.calls.append(bars)
        now = int(time.time()) // 900 * 900
        return [
            Candle(time=now - 900, open=1.0, high=1.0, low=1.0, close=1.0),
            Candle(time=now, open=1.0, high=2.0, low=1.0, close=1.5),
        ]


def _fake_provider(monkeypatch, local: bool) -> _Fake:
    from app.providers import PROVIDERS, _forming

    provider = _Fake(local)
    monkeypatch.setitem(PROVIDERS, "fake", provider)
    _forming.clear()
    return provider


def test_the_forming_bar_is_exactly_the_one_the_candles_do_not_carry():
    """The two halves have to agree on which bar is live.

    `get_candles` drops it and `get_forming` returns it, and if those ever
    disagree the chart draws a bar the detectors also have - two candles on one
    timestamp, which lightweight-charts throws on - or leaves a hole. Both are
    derived from `drop_forming` for that reason, and this is the check that says
    so out loud.
    """
    from app.providers import get_candles, get_forming

    candles, _ = asyncio.run(get_candles("BTCUSDT", "15m", 120, "synthetic"))
    bar, _ = asyncio.run(get_forming("BTCUSDT", "15m", "synthetic"))

    assert bar is not None, "the synthetic series is anchored to now, so one is open"
    assert bar.time == candles[-1].time + 900, "the forming bar is the NEXT slot"
    assert all(c.time != bar.time for c in candles), "it must not be in both"


def test_a_metered_source_is_not_polled_once_a_second(monkeypatch):
    """The browser polls this at 1Hz. A free tier metered at 800 calls a day
    would be spent before lunch by one tab left open, so anything that has not
    declared itself local keeps the ordinary cache window."""
    from app.providers import get_forming

    provider = _fake_provider(monkeypatch, local=False)
    first, _ = asyncio.run(get_forming("X", "15m", "fake"))
    second, _ = asyncio.run(get_forming("X", "15m", "fake"))

    assert first is not None and second == first
    assert len(provider.calls) == 1, "a metered upstream was asked twice in a second"


def test_a_local_terminal_is_asked_fresh_every_time(monkeypatch):
    """The whole point of the local provider. A cached forming bar is a candle
    that does not move, which is the thing this endpoint exists to fix."""
    from app.providers import get_forming

    provider = _fake_provider(monkeypatch, local=True)
    asyncio.run(get_forming("X", "15m", "fake"))
    asyncio.run(get_forming("X", "15m", "fake"))

    assert len(provider.calls) == 2, "a local terminal must not be served from cache"


def test_an_unknown_broker_is_refused_rather_than_priced_generically():
    """The silent failure this replaces was on a MONEY path.

    `broker="nope"` and `broker="EXNESS_ZERO"` both fell through to the generic
    per-instrument row and priced the overnight carry at 0.424 where
    `exness_zero` prices it at 2.434 - a 5.7x understatement, returned as HTTP
    200, with the advice text quoting the wrong figure and no hedge. Every other
    unknown identifier on this request already failed loudly.

    Case is part of it. A cost table keyed by a lowercase identifier that
    silently accepts the uppercase spelling is a table with two answers.
    """
    from fastapi.testclient import TestClient

    from app.costs import BROKERS
    from app.main import app

    client = TestClient(app)
    body = {
        "symbol": "XAUUSD",
        "interval": "1h",
        "bars": 200,
        "provider": "synthetic",
        "layers": ["supply_demand"],
    }

    known = sorted(BROKERS)[0]
    assert client.post("/api/draw", json={**body, "broker": known}).status_code == 200
    assert client.post("/api/draw", json={**body, "broker": ""}).status_code == 200

    for wrong in ("nope", known.upper(), " " + known):
        response = client.post("/api/draw", json={**body, "broker": wrong})
        assert response.status_code == 422, (wrong, response.status_code)
        assert "unknown broker" in response.text, response.text
        # The message has to name the alternatives, or the caller's only recourse
        # is reading the source.
        assert known in response.text


def test_the_candle_memo_is_bounded_by_total_candles():
    """It was unbounded, and `bars` is a free integer.

    Measured before the bound existed: 60 successive requests differing only in
    `bars` grew the worker by 695.6 MB, linear at 11.6 MB per key, and three
    TTLs of idle freed nothing - the TTL is a freshness gate and was never an
    eviction. This walks the same loop and asserts the total held, which is the
    quantity the bound is written in.
    """
    import asyncio

    from app.providers import _MAX_CACHED_CANDLES, _cache, get_candles

    _cache.clear()
    try:
        # Enough distinct keys to exceed the bound several times over.
        step = max(1, _MAX_CACHED_CANDLES // 12)
        total_asked = 0
        for i in range(24):
            bars = 1000 + i * 7
            asyncio.run(get_candles("XAUUSD", "1h", bars, "synthetic"))
            total_asked += bars
        held = sum(len(rows) for _, rows in _cache.values())
        assert held <= _MAX_CACHED_CANDLES, held
        assert _cache, "the bound must not empty the cache, only trim it"
        # And the newest key survives: evicting what the chart is currently
        # looking at would turn a bound into a cache that never hits.
        assert ("synthetic", "XAUUSD", "1h", 1000 + 23 * 7) in _cache
        assert step > 0
    finally:
        _cache.clear()


def test_provider_probes_run_concurrently():
    """Serially, one unreachable host set the floor for the whole option list.

    Measured: `/api/config` answered in 1.93 s cold against 4.8 ms warm, all of
    it a single 2-second HEAD to a host unreachable on this machine. Asserted as
    wall clock against the SUM of the delays, which is the property that broke,
    rather than against an absolute number that would be a machine benchmark.
    """
    import asyncio
    import time

    from app import providers as mod

    class Slow:
        name = "slow"

        def __init__(self, tag: str) -> None:
            self.tag = tag

        def available(self) -> bool:
            return True

        async def probe(self) -> bool:
            await asyncio.sleep(0.12)
            return True

    original = dict(mod.PROVIDERS)
    mod.PROVIDERS.clear()
    mod.PROVIDERS.update({f"slow{i}": Slow(f"slow{i}") for i in range(5)})
    try:
        start = time.monotonic()
        result = asyncio.run(mod.availability())
        elapsed = time.monotonic() - start
    finally:
        mod.PROVIDERS.clear()
        mod.PROVIDERS.update(original)

    assert len(result) == 5 and all(result.values())
    assert elapsed < 0.12 * 5 * 0.6, f"{elapsed:.3f}s looks serial for 5 x 0.12s probes"
