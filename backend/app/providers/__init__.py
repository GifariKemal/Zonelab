"""Provider registry and the short-lived response cache in front of it."""

from __future__ import annotations

import asyncio
import time

from ..config import settings
from ..models import Candle
from .base import INTERVALS, Provider, ProviderError
from .sources import (
    SYMBOLS,
    AurixProvider,
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
        YahooProvider(),
        TwelveDataProvider(),
        PolygonProvider(),
        AurixProvider(),
        SyntheticProvider(),
    )
}

# (provider, symbol, interval, bars) -> (fetched_at, candles)
_cache: dict[tuple[str, str, str, int], tuple[float, list[Candle]]] = {}
_lock = asyncio.Lock()


async def availability() -> dict[str, bool]:
    """Which providers can actually serve a request right now.

    `available()` is a static capability check - is a key configured, is the URL
    set. That is enough for the hosted vendors, but the local Aurix bridge can
    be configured and simply not running, and listing it as available then is a
    lie the user only discovers by picking it and getting a 502.
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

        candles = await provider.fetch(symbol, interval, bars)
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
    "get_candles",
    "resolve",
]
