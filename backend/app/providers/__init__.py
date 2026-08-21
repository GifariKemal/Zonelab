"""Provider registry and the short-lived response cache in front of it."""

from __future__ import annotations

import asyncio
import time

from ..config import settings
from ..models import Candle
from .base import INTERVALS, Provider, ProviderError
from .dukascopy import DukascopyProvider
from .mt5 import MT5Provider
from .sources import (
    SYMBOLS,
    BinanceProvider,
    PolygonProvider,
    TwelveDataProvider,
    YahooProvider,
)
from .synthetic import SyntheticProvider

PROVIDERS: dict[str, Provider] = {
    p.name: p
    for p in (
        # First, because order here is the UI's option order and the local
        # terminal beats every network source on depth, latency and on being
        # the venue the user actually trades. It reports itself unavailable
        # where no terminal exists, so this costs nothing on a machine without.
        MT5Provider(),
        BinanceProvider(),
        DukascopyProvider(),
        YahooProvider(),
        TwelveDataProvider(),
        PolygonProvider(),
        SyntheticProvider(),
    )
}

#: (provider, symbol, interval, bars) -> (fetched_at, candles)
_CacheKey = tuple[str, str, str, int]
_cache: dict[_CacheKey, tuple[float, list[Candle]]] = {}

#: Total candles the memo may hold before the least recently used keys are
#: dropped, and it is bounded in CANDLES rather than in keys because the keys
#: differ in size by two orders of magnitude: a 500-bar key is nothing and a
#: 50,000-bar key is about 64 MB.
#:
#: IT HAD NO BOUND AT ALL, and `bars` is a free integer with 49,951 reachable
#: values - the same observation `_MAX_LOCKS` below was written for, never
#: applied to the thing actually holding the data. Measured: 60 successive
#: `/api/candles?bars=9000..9059` grew the worker by 695.6 MB, dead linear at
#: 11.6 MB per key, and sixty seconds of idle - three times
#: `cache_ttl_seconds` - freed nothing, because the TTL is a freshness gate and
#: never an eviction. Over one working session the worker reached 2.8 GB on a
#: 15.7 GB machine. No detector or drawing is involved; `/api/candles` alone
#: does it.
#:
#: 250,000 at the measured 1.29 KB per candle is roughly 320 MB: five keys at
#: the 50,000-bar measurement size, or five hundred at the 500-bar size the UI
#: actually asks for. Sized so the common case never evicts and the pathological
#: case cannot run away.
_MAX_CACHED_CANDLES = 250_000

#: ONE LOCK PER KEY, never one lock for everything.
#
# A single global lock held across the upstream fetch turns every request for
# DIFFERENT bars into a queue: each waiter sits through a full network round trip
# before it can even look at the cache. Measured on 2026-08-19, after an
# end-to-end harness had walked 178 controls and its browser had already closed:
# `/api/candles` took 5.23 seconds while the same call to Binance took 0.15, and
# `POST /api/draw` did not return inside 60 seconds - all of it waiting on the
# lock, none of it on the network. `/api/health` stayed at 0.34s throughout,
# which is why this reads as a hang rather than as load.
#
# Per key keeps the only property the global lock was there for - a burst of
# parameter tweaks that all want the SAME bars makes one upstream call, not
# twelve, which matters on tiers metered at 5 calls a minute - and drops the part
# nobody asked for.
_locks: dict[_CacheKey, asyncio.Lock] = {}

#: Above this many distinct keys, unlocked entries are dropped. `bars` is a free
#: integer, so a client looping over it could otherwise grow this without bound.
#: Only idle locks go: evicting a held one would let two fetches for one key
#: overlap, which costs an extra call and breaks nothing.
_MAX_LOCKS = 512


async def availability() -> dict[str, bool]:
    """Which providers can actually serve a request right now.

    `available()` is a static capability check - is a key configured, is the URL
    set. A provider may also expose `probe()` when being configured is not the
    same as being reachable; listing such a provider as available would be a lie
    the user only discovers by picking it and getting a 502.
    """
    async def one(provider: Provider) -> bool:
        probe = getattr(provider, "probe", None)
        return await probe() if probe else provider.available()

    # CONCURRENT, because serially the slowest unreachable host sets the floor
    # for the whole option list. Measured: `/api/config` answered in 1.93 s cold
    # against 4.8 ms warm, all of it one 2-second HEAD to a host that is
    # unreachable on this machine - so one page load in every `PROBE_TTL_SECONDS`
    # window waited two seconds for a list of dropdown options. Gathered, the
    # cold cost is the slowest single probe instead of their sum.
    names = list(PROVIDERS)
    flags = await asyncio.gather(*(one(PROVIDERS[name]) for name in names))
    return dict(zip(names, flags))


def resolve(name: str | None) -> Provider:
    provider = PROVIDERS.get(name or settings.default_provider)
    if provider is None:
        raise ProviderError(
            f"unknown provider '{name}'. Known: {', '.join(sorted(PROVIDERS))}"
        )
    return provider


def drop_forming(candles: list[Candle], interval: str) -> list[Candle]:
    """Remove the bar that has not finished yet, for EVERY provider.

    Four of the six ship it: binance returns the open kline, twelvedata and
    polygon include the current period, and yahoo appends the live quote as a
    pseudo-bar stamped with the quote time rather than the bar open - so it is
    not even on the interval grid, has zero range, and is therefore classified
    as a base bar by construction. Only dukascopy is clean, because it never
    requests the current hour.

    Every one of those makes the detector read a bar whose high, low and close
    are still moving. Measured over 599 real 15m formations: 42 zone states
    changed and changed back INSIDE one bar, 15 zones vanished and returned, and
    a stop's risk-per-unit swung 14% in 90 seconds with no bar having closed.
    None of that is the market. It is an unclosed bar being treated as evidence.

    The guard lives HERE, at the one point every caller routes through, rather
    than in each provider or inside `resample`. Putting it in resample would
    leave the same wrong assumption sitting in `detect`; putting it per provider
    guarantees the next provider forgets it.

    Consequence worth stating: the chart is now always at least one bar behind
    live price. That is the correct trade. A drawing computed from a bar that
    has not closed is a drawing that will change, and this project measured its
    numbers on closed bars.
    """
    if not candles:
        return candles
    step = INTERVALS.get(interval)
    if step is None:
        return candles
    now = int(time.time())
    return candles[:-1] if candles[-1].time + step > now else candles


#: (provider, symbol, interval) -> (fetched_at, the unclosed bar or None).
#: Separate from `_cache` because the key has no `bars` in it: the forming bar is
#: the same object no matter how long a chart the caller asked for.
_forming: dict[tuple[str, str, str], tuple[float, Candle | None]] = {}


async def get_forming(
    symbol: str, interval: str, provider_name: str | None = None
) -> tuple[Candle | None, str]:
    """The bar that has NOT closed yet, which `get_candles` deliberately drops.

    THIS IS FOR DRAWING ONLY. `drop_forming` explains at length why an unclosed
    bar must never reach the detectors - 42 zone states changed and changed back
    inside one bar over 599 real formations - and nothing here weakens that. The
    forming bar leaves the backend through its OWN endpoint and its own field,
    so a detector cannot read it by accident: it is not in `candles`, and no
    code path merges the two. What it buys is a chart whose last candle moves,
    which is the one thing a closed-bar chart cannot show and the reason people
    keep a terminal open beside it.

    Forming-ness is decided by `drop_forming` rather than re-derived here. The
    same comparison written twice is the same comparison until someone edits one
    of them, and then the chart and the detectors disagree about which bar is
    live - which would look exactly like a data bug and would not be one.
    """
    if interval not in INTERVALS:
        raise ProviderError(
            f"unknown interval '{interval}'. Known: {', '.join(INTERVALS)}"
        )
    provider = resolve(provider_name)
    key = (provider.name, symbol.upper(), interval)

    # A LOCAL terminal costs nothing to ask and is the whole point of polling
    # this once a second. A metered HTTP tier is not, and a browser tab left
    # open overnight would spend a free plan's daily quota before morning - so
    # everything that is not local keeps the ordinary cache window.
    ttl = 0.0 if getattr(provider, "local", False) else settings.cache_ttl_seconds
    hit = _forming.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1], provider.name

    # `symbol` is free text, so the key space is caller-controlled. One candle
    # per entry makes this cheap, but not unbounded.
    if len(_forming) > _MAX_LOCKS:
        _forming.clear()

    rows = await provider.fetch(symbol, interval, 2)
    closed = drop_forming(rows, interval)
    candle = rows[-1] if rows and len(closed) < len(rows) else None
    _forming[key] = (time.monotonic(), candle)
    return candle, provider.name


async def get_candles(
    symbol: str, interval: str, bars: int, provider_name: str | None = None
) -> tuple[list[Candle], str]:
    """Fetch candles, memoised for `cache_ttl_seconds`.

    The key's own lock is held across the fetch so a burst of parameter tweaks
    from the UI - which all want the SAME bars - makes one upstream call, not
    twelve. That matters on free tiers metered at 5 calls/minute.

    Held per key and never globally. See `_locks`: one lock for everything made
    requests for different bars queue through each other's network round trips,
    and it presented as the API hanging.
    """
    if interval not in INTERVALS:
        raise ProviderError(
            f"unknown interval '{interval}'. Known: {', '.join(INTERVALS)}"
        )
    bars = max(50, min(bars, settings.max_bars))

    provider = resolve(provider_name)
    key = (provider.name, symbol.upper(), interval, bars)

    if len(_locks) > _MAX_LOCKS:
        for stale, lock in list(_locks.items()):
            if not lock.locked():
                del _locks[stale]
    # `setdefault` and not a get-then-set: there is no `await` between the two
    # halves of that, but writing it as two statements invites someone to add
    # one, and then two callers would each hold their own lock for one key.
    async with _locks.setdefault(key, asyncio.Lock()):
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < settings.cache_ttl_seconds:
            # Re-inserted so recency is insertion order, which is what makes the
            # eviction below LRU rather than FIFO. One line, and it is the
            # difference between evicting the key nobody wants and evicting the
            # key the chart is sitting on.
            _cache[key] = _cache.pop(key)
            return hit[1], provider.name

        # Ask for one MORE than wanted, because the newest is about to be
        # dropped. Without this the guard silently shortchanges every caller by
        # a bar - a request for 120 returned 119 - and a caller asking for a
        # bar count is asking for that many USABLE bars, not that many minus
        # whatever the feed happened to include.
        fetched = await provider.fetch(symbol, interval, bars + 1)
        candles = drop_forming(fetched, interval)[-bars:]
        if not candles:
            raise ProviderError(f"{provider.name} returned no candles for {symbol}")
        _cache[key] = (time.monotonic(), candles)
        # Oldest first, until the total is back under the bound. `next(iter(...))`
        # is the least recently used key because a hit above re-inserts.
        held = sum(len(rows) for _, rows in _cache.values())
        while held > _MAX_CACHED_CANDLES and len(_cache) > 1:
            oldest = next(iter(_cache))
            held -= len(_cache.pop(oldest)[1])
        return candles, provider.name


__all__ = [
    "INTERVALS",
    "PROVIDERS",
    "SYMBOLS",
    "Provider",
    "ProviderError",
    "availability",
    "drop_forming",
    "get_candles",
    "get_forming",
    "resolve",
]
