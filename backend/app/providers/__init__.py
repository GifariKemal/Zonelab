"""Provider registry and the short-lived response cache in front of it."""

from __future__ import annotations

import asyncio
import time

from ..config import settings
from ..models import Candle
from .base import INTERVALS, Provider, ProviderError
from .dukascopy import DukascopyProvider
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
        BinanceProvider(),
        DukascopyProvider(),
        YahooProvider(),
        TwelveDataProvider(),
        PolygonProvider(),
        SyntheticProvider(),
    )
}

# (provider, symbol, interval, bars) -> (fetched_at, candles)
_cache: dict[tuple[str, str, str, int], tuple[float, list[Candle]]] = {}
_lock = asyncio.Lock()


async def availability() -> dict[str, bool]:
    """Which providers can actually serve a request right now.

    `available()` is a static capability check - is a key configured, is the URL
    set. A provider may also expose `probe()` when being configured is not the
    same as being reachable; listing such a provider as available would be a lie
    the user only discovers by picking it and getting a 502.
    """
    result: dict[str, bool] = {}
    for name, provider in PROVIDERS.items():
        probe = getattr(provider, "probe", None)
        result[name] = await probe() if probe else provider.available()
    return result


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


async def get_candles(
    symbol: str, interval: str, bars: int, provider_name: str | None = None
) -> tuple[list[Candle], str]:
    """Fetch candles, memoised for `cache_ttl_seconds`.

    The lock is held across the fetch so a burst of parameter tweaks from the UI
    - which all want the same bars - makes one upstream call, not twelve. That
    matters on free tiers metered at 5 calls/minute.
    """
    if interval not in INTERVALS:
        raise ProviderError(
            f"unknown interval '{interval}'. Known: {', '.join(INTERVALS)}"
        )
    bars = max(50, min(bars, settings.max_bars))

    provider = resolve(provider_name)
    key = (provider.name, symbol.upper(), interval, bars)

    async with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < settings.cache_ttl_seconds:
            return hit[1], provider.name

        candles = drop_forming(await provider.fetch(symbol, interval, bars), interval)
        if not candles:
            raise ProviderError(f"{provider.name} returned no candles for {symbol}")
        _cache[key] = (time.monotonic(), candles)
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
    "resolve",
]
