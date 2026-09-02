"""Guards on the two places a wrong answer arrives silently rather than loudly.

Neither of these is about market structure. They are about the seams: the
detector registry the API dispatches through, and the vendor payloads nobody
controls.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import pytest

from app.clock import market_shut
from app.detect import DETECTORS
from app.layers import DETECTOR_IDS, PARAMS_BY_ID
from app.models import DrawRequest
from app.providers import ProviderError, resolve
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


#: A Wednesday, 10:00 New York, chosen because `clock.market_shut` says the
#: market is open then and the assertion below proves it rather than trusting the
#: comment.
MIDWEEK = int(datetime(2026, 8, 19, 14, 0, tzinfo=UTC).timestamp())
#: Saturday, same clock. Shut all day on the CME week.
WEEKEND = int(datetime(2026, 8, 22, 14, 0, tzinfo=UTC).timestamp())


def _frozen_at(monkeypatch, epoch: int):
    """Freeze the wall clock at `epoch` and empty both provider caches.

    BOTH CACHES, and that is the part worth stating. They expire on
    `time.monotonic`, which a frozen `time.time` does not touch, so the second of
    two frozen-clock tests reads the first one's answer and passes or fails for a
    reason that has nothing to do with the instant it asked about. Measured while
    writing these two: the Saturday test was handed the Wednesday forming bar,
    stamped 1787148000, a cache hit from 300ms earlier.
    """
    from app.providers import _cache, _forming, get_candles, get_forming

    monkeypatch.setattr(time, "time", lambda: epoch + 300.0)
    _cache.clear()
    _forming.clear()
    return get_candles, get_forming


def test_the_forming_bar_is_exactly_the_one_the_candles_do_not_carry(monkeypatch):
    """The two halves have to agree on which bar is live.

    `get_candles` drops it and `get_forming` returns it, and if those ever
    disagree the chart draws a bar the detectors also have - two candles on one
    timestamp, which lightweight-charts throws on - or leaves a hole. Both are
    derived from `drop_forming` for that reason, and this is the check that says
    so out loud.

    THE CLOCK IS FROZEN, and that is the repair. This test read the real clock
    and asserted a forming bar exists "because the synthetic series is anchored
    to now" - which stopped being true when the synthetic feed learned to close.
    It failed on a Friday at 23:06 UTC having caught nothing: the market had shut
    two hours earlier and there was correctly no open bar. Conditioning the
    assertion on the day would have gone quiet every weekend instead, which is
    the same defect wearing a passing result.
    """
    assert not market_shut(MIDWEEK), "the frozen instant must be a live session"
    get_candles, get_forming = _frozen_at(monkeypatch, MIDWEEK)

    candles, _ = asyncio.run(get_candles("BTCUSDT", "15m", 120, "synthetic"))
    bar, _ = asyncio.run(get_forming("BTCUSDT", "15m", "synthetic"))

    assert bar is not None, "mid-session, so one bar is open"
    assert bar.time == candles[-1].time + 900, "the forming bar is the NEXT slot"
    assert all(c.time != bar.time for c in candles), "it must not be in both"


def test_a_shut_market_has_no_forming_bar_rather_than_a_stale_one(monkeypatch):
    """The other half of the pair above, and the reason it needs stating.

    A chart whose last candle keeps ticking through a closed weekend is inventing
    price. `get_forming` returning None here is what makes the frontend draw
    nothing instead of animating the Friday close for two days.
    """
    assert market_shut(WEEKEND), "the frozen instant must be a shut market"
    get_candles, get_forming = _frozen_at(monkeypatch, WEEKEND)

    candles, _ = asyncio.run(get_candles("BTCUSDT", "15m", 120, "synthetic"))
    bar, _ = asyncio.run(get_forming("BTCUSDT", "15m", "synthetic"))

    assert bar is None, "the market is shut, so no bar is forming"
    assert candles, "the closed history is still served"

    # AND NOT BECAUSE THE FETCH CAME BACK EMPTY. `get_forming` asks for exactly
    # two bars, and an empty answer reads as "nothing is forming" - the right
    # verdict reached by the wrong route. This is the assertion that separates
    # them, and it is the one that fails against the old `bars * 8` walk: two
    # bars requested on a Saturday found zero open slots and now raise instead.
    rows = asyncio.run(resolve("synthetic").fetch("BTCUSDT", "15m", 2))
    assert len(rows) == 2, "a two-bar request must still cross the weekend hole"


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
    `exness_raw` prices it at 2.434 - a 5.7x understatement, returned as HTTP
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


# --------------------------------------------------------------------------
# one symbol convention, both doors
# --------------------------------------------------------------------------


def test_a_prefixed_symbol_reaches_the_provider_it_names():
    """`tools/history.load` has always taken `mt5:XAUUSD` while this path
    demanded `XAUUSD` plus a provider field, so one string meant two things
    depending on the door. It cost a debugging session on 2026-08-21: the API
    answered 502 with "the terminal carries no symbol 'mt5:XAUUSD'. Check the
    broker's naming", which reads like a broker problem and is not one.

    Synthetic, so the test needs no terminal and no network.
    """
    from app.providers import get_candles

    rows, name = asyncio.run(get_candles("synthetic:XAUUSD", "1h", 200))
    assert name == "synthetic"
    assert len(rows) > 0


def test_the_prefix_and_the_field_may_agree():
    from app.providers import get_candles

    rows, name = asyncio.run(get_candles("synthetic:XAUUSD", "1h", 200, "synthetic"))
    assert name == "synthetic"
    assert len(rows) > 0


def test_a_prefix_that_contradicts_the_field_is_refused():
    """Not a precedence rule. `mt5:XAUUSD` with `provider=yahoo` is not a request
    anybody meant, and choosing a winner silently answers with the wrong feed's
    prices - which is indistinguishable from a market that moved."""
    from app.providers import get_candles

    with pytest.raises(ProviderError, match="Send one or the other"):
        asyncio.run(get_candles("synthetic:XAUUSD", "1h", 200, "yahoo"))


def test_a_colon_that_is_not_a_provider_is_left_alone():
    """A symbol may legitimately contain a colon. Only a KNOWN provider name in
    front of one is a routing prefix."""
    from app.providers import get_candles

    with pytest.raises(ProviderError):
        # `notaprovider` is not in PROVIDERS, so the whole string stays the
        # symbol and the default provider is asked for it.
        asyncio.run(get_candles("notaprovider:XAUUSD", "1h", 200, "yahoo"))


def test_a_layer_family_is_a_heading_that_already_exists():
    """A family must be one of the two the registry declares, or absent.

    The families are HEADINGS in the menu and nothing more - the switch stays on
    each layer, so a family cannot turn a doctrine on as a bloc. That makes the
    failure mode quiet rather than loud: a typo ("ict" for "ICT") does not raise
    anything, it opens a SECOND group with one member in it, and the reader sees
    two headings where the registry meant one.

    The membership itself is not restated here, because a second list of layer
    ids is the drift `app/detect/__init__.py` warns about at its own bottom.
    What is pinned is the set of NAMES, so adding a third family stays a
    deliberate edit in two places instead of an accident in one.

    `docs/ADOPSI.md` is the authority on which layer belongs where, and it keeps
    ICT, SMC and Quarterly Theory apart rather than folding them together.
    """
    from app.layers import LAYERS, catalogue

    allowed = {"ICT", "Quarterly Theory", None}
    seen = {layer.family for layer in LAYERS}
    assert seen <= allowed, f"family yang tidak dideklarasikan: {sorted(seen - allowed, key=str)}"

    # Served, not merely stored. The menu is built from `/api/config`, so a
    # field the catalogue drops is a field the UI cannot group by.
    rows = catalogue()
    assert all("family" in row for row in rows)
    assert {row["family"] for row in rows} == seen

    # A heading with one member reads as a mistake even when it is not, and is
    # what a typo produces. Two is the smallest group worth a heading.
    counts: dict[str, int] = {}
    for layer in LAYERS:
        if layer.family:
            counts[layer.family] = counts.get(layer.family, 0) + 1
    thin = sorted(name for name, n in counts.items() if n < 2)
    assert not thin, f"family beranggota satu, hampir selalu salah ketik: {thin}"


def test_a_pinned_synthetic_clock_survives_the_clock_moving(monkeypatch):
    """The pin has to hold across TIME, which is the thing the old check missed.

    `e2e/labels.mjs` was pinned to this provider on 1 September 2026 so that "a
    red run means something", and the pin was verified by fetching twice and
    comparing bytes. Two fetches in a row always land in the same bar, so that
    check could not fail for the reason it existed - measured the same day, two
    back-to-back calls were byte-identical and a third one 70 seconds later had
    moved a full 15 minute bar, 1787629500 to 1787630400.

    So this advances the clock instead of calling twice, and asserts both
    halves: unpinned still tracks the calendar, which is what the offline chart
    wants, and pinned does not, which is what a geometry assertion needs.
    """
    from app.providers import synthetic as mod

    def series(when: float) -> tuple[int, int]:
        monkeypatch.setattr(mod._time, "time", lambda: when)
        rows = asyncio.run(mod.SyntheticProvider().fetch("XAUUSD", "15m", 120))
        return rows[0].time, rows[-1].time

    # Dua hari KERJA, sehari terpisah. Percobaan pertama memakai 1788000000 dan
    # 1788086400, yang keduanya jatuh di akhir pekan: `_session_grid` mundur ke
    # penutupan Jumat yang sama untuk dua-duanya, jadi deretnya identik dan
    # bagian "unpinned" gagal karena fixture-nya, bukan karena kodenya. Selasa
    # 1 September 2026 10:00 UTC dan Rabu 2 September, jam yang sama.
    early, late = 1788256800.0, 1788343200.0

    monkeypatch.setattr(mod.settings, "synthetic_now", 0)
    assert series(early) != series(late), (
        "unpinned synthetic stopped following the clock; the offline chart "
        "would sit on a fixed date"
    )

    monkeypatch.setattr(mod.settings, "synthetic_now", int(early))
    assert series(early) == series(late), (
        "a pinned clock still moved with the wall clock, so any harness that "
        "asserts geometry on this provider is still measuring a moving series"
    )
