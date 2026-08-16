"""Concrete market-data providers.

Symbol strings verified against each vendor on 2026-08-13. They are the single
most error-prone detail here, so each one is spelled out next to its provider
rather than guessed at call time:

    binance     PAXGUSDT        no key, free websocket, tokenized-gold proxy
    dukascopy   XAUUSD          true spot TICKS, no key, bid+ask so it is the
                                one source here that yields a measured spread
    yahoo       GC=F            COMEX futures; every spot variant now 404s
    twelvedata  XAU/USD         true spot, slash required, needs a free key
    polygon     C:XAUUSD        true spot, epoch MILLIseconds, needs a key

`SYMBOLS` below maps the app's own symbol id onto each vendor's dialect so the
frontend never has to know any of this.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import httpx

from ..config import settings
from ..models import Candle
from .base import INTERVALS, ProviderError, normalize

# app symbol -> {provider: vendor symbol}. A missing entry means that provider
# does not carry the instrument, which is reported rather than silently retried.
SYMBOLS: dict[str, dict[str, str]] = {
    "XAUUSD": {
        "binance": "PAXGUSDT",
        "dukascopy": "XAUUSD",
        "yahoo": "GC=F",
        "twelvedata": "XAU/USD",
        "polygon": "C:XAUUSD",
    },
    "BTCUSD": {
        "binance": "BTCUSDT",
        "yahoo": "BTC-USD",
        "twelvedata": "BTC/USD",
        "polygon": "X:BTCUSD",
    },
    "EURUSD": {
        "dukascopy": "EURUSD",
        "yahoo": "EURUSD=X",
        "twelvedata": "EUR/USD",
        "polygon": "C:EURUSD",
    },
}


def vendor_symbol(provider: str, symbol: str) -> str:
    mapping = SYMBOLS.get(symbol.upper())
    if mapping is None:
        # Unknown ids pass through untouched: it lets a user try any ticker the
        # vendor supports without waiting for this table to be updated.
        return symbol
    resolved = mapping.get(provider)
    if resolved is None:
        raise ProviderError(f"{provider} does not carry {symbol}")
    return resolved


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": "Zonelab/0.1 (local research tool)"},
        follow_redirects=True,
    )


async def _get_json(url: str, params: dict | None = None) -> dict | list:
    async with _client() as client:
        try:
            response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error contacting {url}: {exc}") from exc
    if response.status_code != 200:
        raise ProviderError(
            f"upstream returned HTTP {response.status_code}: {response.text[:200]}"
        )
    try:
        return response.json()
    except ValueError as exc:
        # A vendor answering 200 with an HTML error page or a captcha is
        # common on free tiers. Without this the app returns a 500 and a stack
        # trace instead of naming the provider that misbehaved.
        raise ProviderError(
            f"upstream returned HTTP 200 but not JSON: {response.text[:200]}"
        ) from exc


class BinanceProvider:
    """Free, keyless, and the reason the app runs before any setup.

    PAXG is tokenized gold quoted in USDT. It tracks XAU closely but carries its
    own premium and trades weekends, so it is labelled a proxy everywhere it is
    shown. Structure - which is all the detectors read - is faithful.
    """

    name = "binance"
    _INTERVALS = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w",
    }  # fmt: skip

    def available(self) -> bool:
        return True

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        step = self._INTERVALS.get(interval)
        if step is None:
            raise ProviderError(f"binance has no {interval} interval")

        rows = await _get_json(
            "https://api.binance.com/api/v3/klines",
            {
                "symbol": vendor_symbol(self.name, symbol),
                "interval": step,
                "limit": min(bars, 1000),  # hard vendor cap
            },
        )
        if not isinstance(rows, list):
            raise ProviderError("binance returned an unexpected payload")

        # A kline that is short a field or carries a non-numeric one raises
        # IndexError/ValueError here, and `_fetch` in main.py only converts
        # ProviderError, so the user would get a bare 500 naming nothing. The
        # vendor that misbehaved has to be said out loud, as YahooProvider does.
        try:
            return normalize(
                [
                    Candle(
                        time=int(r[0]) // 1000,  # vendor sends milliseconds
                        open=float(r[1]),
                        high=float(r[2]),
                        low=float(r[3]),
                        close=float(r[4]),
                        volume=float(r[5]),
                    )
                    for r in rows
                ],
                bars,
            )
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError(f"binance sent an unreadable kline: {exc}") from exc


class YahooProvider:
    """Gold futures (GC=F). Free and keyless but must be called server-side:
    Yahoo sends no CORS headers at all, even on a 200."""

    name = "yahoo"
    _INTERVALS = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "60m", "1d": "1d", "1w": "1wk",
    }  # fmt: skip

    def available(self) -> bool:
        return True

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        step = self._INTERVALS.get(interval)
        if step is None:
            raise ProviderError(f"yahoo has no {interval} interval (4h is unsupported)")

        # Yahoo takes a calendar range, not a bar count. Pad generously: markets
        # close, so wall-clock span is always longer than bars x interval.
        span_days = max(1, math.ceil(bars * INTERVALS[interval] / 86400 * 2.2))
        payload = await _get_json(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{vendor_symbol(self.name, symbol)}",
            {"interval": step, "range": f"{min(span_days, 730)}d"},
        )

        chart = payload.get("chart") if isinstance(payload, dict) else None
        result = (chart or {}).get("result") or []
        if not result:
            raise ProviderError(f"yahoo returned no data: {(chart or {}).get('error')}")

        block = result[0]
        stamps = block.get("timestamp") or []
        quote = (block.get("indicators", {}).get("quote") or [{}])[0]

        # Yahoo is an undocumented endpoint and its shape is not a contract.
        # Naming the missing series beats a KeyError becoming a 500.
        missing = [k for k in ("open", "high", "low", "close") if k not in quote]
        if missing:
            raise ProviderError(f"yahoo response is missing {', '.join(missing)}")

        candles = []
        for i, ts in enumerate(stamps):
            if any(i >= len(quote[k]) for k in ("open", "high", "low", "close")):
                break  # ragged arrays: trust the shortest, do not invent bars
            o, h, l, c = (
                quote["open"][i],
                quote["high"][i],
                quote["low"][i],
                quote["close"][i],
            )
            # Yahoo pads non-trading slots with nulls; a null OHLC is a hole in
            # the session, not a zero-priced bar.
            if None in (o, h, l, c):
                continue
            volumes = quote.get("volume") or []
            candles.append(
                Candle(
                    time=int(ts),
                    open=float(o),
                    high=float(h),
                    low=float(l),
                    close=float(c),
                    volume=float(volumes[i] or 0) if i < len(volumes) else 0.0,
                )
            )
        return normalize(candles, bars)


class TwelveDataProvider:
    """True spot XAU/USD. Free tier: 800 requests/day, 8 credits/minute."""

    name = "twelvedata"
    _INTERVALS = {
        "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
        "1h": "1h", "4h": "4h", "1d": "1day", "1w": "1week",
    }  # fmt: skip

    def available(self) -> bool:
        return bool(settings.twelvedata_key)

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        if not self.available():
            raise ProviderError("ZONELAB_TWELVEDATA_KEY is not set")
        step = self._INTERVALS.get(interval)
        if step is None:
            raise ProviderError(f"twelvedata has no {interval} interval")

        payload = await _get_json(
            "https://api.twelvedata.com/time_series",
            {
                "symbol": vendor_symbol(self.name, symbol),
                "interval": step,
                "outputsize": min(bars, 5000),
                "timezone": "UTC",  # otherwise datetimes come back exchange-local
                "format": "JSON",
                "apikey": settings.twelvedata_key,
            },
        )
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            message = (
                payload.get("message", payload) if isinstance(payload, dict) else payload
            )
            raise ProviderError(f"twelvedata error: {message}")

        candles = []
        # Same reason as binance above: a missing key or an unparseable datetime
        # must name twelvedata, not surface as a bare 500.
        try:
            for row in payload.get("values", []):  # newest-first; normalize re-sorts
                stamp = datetime.fromisoformat(row["datetime"]).replace(tzinfo=UTC)
                candles.append(
                    Candle(
                        time=int(stamp.timestamp()),
                        # Every OHLC field arrives as a string on this vendor.
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume") or 0),  # absent on forex/metals
                    )
                )
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError(f"twelvedata sent an unreadable row: {exc}") from exc
        return normalize(candles, bars)


class PolygonProvider:
    """True spot via Massive (formerly Polygon.io). Free tier is 5 calls/minute
    and 2 years of history, which makes it a cross-check, not a poll source."""

    name = "polygon"
    _INTERVALS = {
        "1m": (1, "minute"), "5m": (5, "minute"), "15m": (15, "minute"),
        "30m": (30, "minute"), "1h": (1, "hour"), "4h": (4, "hour"),
        "1d": (1, "day"), "1w": (1, "week"),
    }  # fmt: skip

    def available(self) -> bool:
        return bool(settings.polygon_key)

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        if not self.available():
            raise ProviderError("ZONELAB_POLYGON_KEY is not set")
        step = self._INTERVALS.get(interval)
        if step is None:
            raise ProviderError(f"polygon has no {interval} interval")
        multiplier, timespan = step

        now = int(datetime.now(UTC).timestamp())
        span = int(bars * INTERVALS[interval] * 2.2)
        start = datetime.fromtimestamp(now - span, UTC).strftime("%Y-%m-%d")
        end = datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%d")

        payload = await _get_json(
            f"https://api.polygon.io/v2/aggs/ticker/{vendor_symbol(self.name, symbol)}"
            f"/range/{multiplier}/{timespan}/{start}/{end}",
            {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": settings.polygon_key},
        )
        if not isinstance(payload, dict) or payload.get("status") not in {"OK", "DELAYED"}:
            raise ProviderError(f"polygon error: {payload}")

        # Same reason as binance above: an aggregate missing o/h/l/c/t must name
        # polygon rather than reach the client as a bare 500.
        try:
            return normalize(
                [
                    Candle(
                        time=int(r["t"]) // 1000,  # vendor sends milliseconds
                        open=float(r["o"]),
                        high=float(r["h"]),
                        low=float(r["l"]),
                        close=float(r["c"]),
                        volume=float(r.get("v") or 0),
                    )
                    for r in payload.get("results", [])
                ],
                bars,
            )
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError(f"polygon sent an unreadable aggregate: {exc}") from exc
