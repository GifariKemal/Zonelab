"""The one place a provider failure becomes an HTTP status.

Its own module because both `main` and `checklist` fetch, and `checklist` is
imported by `main` - leaving this in `main` would close that loop.
"""

from __future__ import annotations

from fastapi import HTTPException

from .models import Candle
from .providers import ProviderError, get_candles


async def fetch(
    symbol: str, interval: str, bars: int, provider: str | None
) -> tuple[list[Candle], str]:
    """Turn provider failures into a 502 carrying the upstream's own words.

    A silent empty chart is the worst outcome here - the user cannot tell a
    missing API key from a symbol that does not exist from a rate limit.
    """
    try:
        return await get_candles(symbol, interval, bars, provider)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
