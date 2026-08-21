"""Concrete market-data providers.

Symbol strings verified against each vendor on 2026-08-13. They are the single
most error-prone detail here, so each one is spelled out next to its provider
rather than guessed at call time:

    mt5         XAUUSD          the local terminal's own history: the broker's
                                real tape, with its real spread, no network at
                                all. Lives in mt5.py, not this file.
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
        "mt5": "XAUUSD",
        "binance": "PAXGUSDT",
        "dukascopy": "XAUUSD",
        "yahoo": "GC=F",
        "twelvedata": "XAU/USD",
        "polygon": "C:XAUUSD",
    },
    "BTCUSD": {
        "mt5": "BTCUSD",
        "binance": "BTCUSDT",
        "yahoo": "BTC-USD",
        "twelvedata": "BTC/USD",
        "polygon": "X:BTCUSD",
    },
    "EURUSD": {
        "mt5": "EURUSD",
        "dukascopy": "EURUSD",
        "yahoo": "EURUSD=X",
        "twelvedata": "EUR/USD",
        "polygon": "C:EURUSD",
    },
    # --- the correlated instruments, for cross-asset reads -------------------
    # Gold is not analysed alone here: the method this engine is being built for
    # reads divergence ACROSS correlated instruments, so the metals complex, the
    # dollar, yields, energy and the indices all have to be reachable by one id.
    #
    # Every ticker below was fetched from Yahoo before it was written down, on
    # 2026-08-18, and each returned real bars. `DX=F` was tried for the dollar
    # index and 404s, which is why the dollar is the `.NYB` cash index instead.
    #
    # FUTURES ARE PREFERRED OVER CASH INDICES, and that is a session decision
    # rather than a taste one. Measured on the same 5-day 1h window: the futures
    # return 116 bars, the cash indices 35 to 36, because the cash index only
    # prints during regular trading hours. Aligning a cash index against gold
    # intersects down to the index's session and throws away two thirds of the
    # bars - so `NAS100` and the yields map to the CME contracts, and the cash
    # tickers are left out rather than offered as a trap.
    #
    # The `mt5` column was read off the Exness terminal's own `symbols_get()` on
    # 2026-08-19, all 314 of them, rather than guessed from the Yahoo ticker.
    # Two entries below have NO mt5 name and that is deliberate: this broker
    # carries no bond contract at all. `US30` exists and is the Dow Jones index,
    # not the 30-year bond, and mapping `US30Y` onto it would put an equity
    # index behind a yield id - real prices under the wrong name, which is the
    # one failure nothing downstream can detect.
    "XAGUSD": {"mt5": "XAGUSD", "yahoo": "SI=F", "twelvedata": "XAG/USD", "polygon": "C:XAGUSD"},
    "XPTUSD": {"mt5": "XPTUSD", "yahoo": "PL=F", "twelvedata": "XPT/USD"},
    "XPDUSD": {"mt5": "XPDUSD", "yahoo": "PA=F", "twelvedata": "XPD/USD"},
    "COPPER": {"mt5": "XCUUSD", "yahoo": "HG=F"},
    "DXY": {"mt5": "DXY", "yahoo": "DX-Y.NYB"},
    "NAS100": {"mt5": "USTEC", "yahoo": "NQ=F"},
    "SPX500": {"mt5": "US500", "yahoo": "ES=F"},
    "WTI": {"mt5": "USOIL", "yahoo": "CL=F"},
    "BRENT": {"mt5": "UKOIL", "yahoo": "BZ=F"},
    # The 10-year note and the 30-year bond as CME contracts. The `^TNX` and
    # `^TYX` yield series exist and were verified, but they are cash, they print
    # a YIELD rather than a price (so they move inverse to the contract), and
    # they carry a third of the bars. Both facts would have to be explained at
    # every call site, so the contracts are what this table offers.
    "US10Y": {"yahoo": "ZN=F"},
    "US30Y": {"yahoo": "ZB=F"},
    "ETHUSD": {"mt5": "ETHUSD", "binance": "ETHUSDT", "yahoo": "ETH-USD", "polygon": "X:ETHUSD"},
    # --- added 2026-08-20, because they WORKED and were unreachable -----------
    # `US30` and `GBPJPY` returned real bars from this terminal all along, through
    # the pass-through below, and neither was in this table - so neither appeared
    # in the symbol picker, which is generated from these keys. They were
    # reachable only by hand-editing a URL. `DE40` was tried and this broker has
    # no such symbol; the DAX is `DE30` here, which nothing knew about.
    #
    # Same rule as the block above: the mt5 column comes from the terminal's own
    # `symbols_get()` and the yahoo column was fetched before being written down.
    # Measured on one 5-day 1h window: `YM=F` 90 bars against `^DJI` 31, and
    # `NIY=F` 90 against `^N225` 36 - so the futures again, for the session reason
    # already stated.
    "US30": {"mt5": "US30", "yahoo": "YM=F"},
    # THE DOLLAR-YEN, which belongs in a gold complex more than most indices do.
    # Verified: 113 bars on the same window.
    "USDJPY": {"mt5": "USDJPY", "yahoo": "USDJPY=X"},
    "GBPJPY": {"mt5": "GBPJPY", "yahoo": "GBPJPY=X"},
    # Natural gas, the energy leg beside WTI and BRENT.
    "NGAS": {"mt5": "XNGUSD", "yahoo": "NG=F"},
    # THE DAX IS MT5-ONLY HERE, and that is the honest entry rather than a gap.
    # Yahoo publishes no DAX future: `FDAX=F` 404s and `DAX=F` answers 200 with
    # zero bars. The cash index `^GDAXI` exists and returns 45 bars against the
    # futures' 90, and this table's own rule is that a cash index is left out
    # rather than offered as a trap. One provider is a fact about the venue, the
    # same shape `US10Y` and `US30Y` already have in reverse.
    "DE30": {"mt5": "DE30"},
    # NOT ADDED, deliberately: `twelvedata` and `polygon` do carry several of the
    # instruments above under mechanical ids like `USD/JPY`, and no key is
    # installed on this machine to verify them. Writing an unverified mapping
    # would break this table's one rule. Until then `vendor_symbol` says "does not
    # carry", which is a true statement about what has been checked.
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
        # The User-Agent is LOAD-BEARING, not courtesy. Measured 2026-08-16:
        # the same Yahoo request answers HTTP 429 "Edge: Too Many Requests" on
        # httpx's default `python-httpx/*` UA and 200 on any other string,
        # including this one, on the first call of the day. Yahoo blocklists
        # the client library by name, so deleting this line as boilerplate
        # breaks every Yahoo fetch with an error that reads like a rate limit.
        headers={"User-Agent": "Zonelab/0.1 (local research tool)"},
        follow_redirects=True,
    )


async def _get_json(url: str, params: dict | None = None) -> dict | list:
    async with _client() as client:
        try:
            response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            # The class name, not just str(exc). httpx.ConnectTimeout stringifies
            # to the EMPTY STRING, so the obvious f-string ends at a colon and
            # names no cause at all - the same swallowed failure dukascopy.py
            # already had to fix, here at the helper every vendor routes through.
            why = str(exc) or type(exc).__name__
            raise ProviderError(f"network error contacting {url}: {why}") from exc
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
        # IndexError/ValueError here, and `fetch` in fetching.py only converts
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
        "1h": "60m", "4h": "4h", "1d": "1d", "1w": "1wk",
    }  # fmt: skip

    # Yahoo's intraday depth is a RECENCY wall, not a window width. Measured
    # 2026-08-16 against the live endpoint: a 60-day-wide 15m window starting
    # 90 days back is refused with the same HTTP 422 as a 90-day-wide one, so
    # the range cannot be paged backwards - what is past the wall is simply not
    # obtainable. Clamping here is the difference between a shorter chart and
    # NO chart: before it, 3000 15m bars computed a 69-day range and 422'd, and
    # 3000 is well inside `max_bars`. 1d/1w keep the old 730 because neither
    # has been measured and inventing a limit is worse than the one in use.
    #
    # 1m is EIGHT days, not the seven every write-up repeats: measured, 7d
    # returns 7126 bars, 8d returns 9655, and 9d is the first to 422.
    _WALL_DAYS = {"1m": 8, "5m": 60, "15m": 60, "30m": 60, "1h": 730, "4h": 730}

    def available(self) -> bool:
        return True

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        step = self._INTERVALS.get(interval)
        if step is None:
            raise ProviderError(f"yahoo has no {interval} interval")

        # Yahoo takes a calendar range, not a bar count. Pad generously: markets
        # close, so wall-clock span is always longer than bars x interval.
        span_days = max(1, math.ceil(bars * INTERVALS[interval] / 86400 * 2.2))
        payload = await _get_json(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{vendor_symbol(self.name, symbol)}",
            {
                "interval": step,
                "range": f"{min(span_days, self._WALL_DAYS.get(interval, 730))}d",
            },
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
        rows = normalize(candles, bars)

        # Yahoo refuses an interval it will not serve by answering 200 with a
        # SILENTLY COARSER series, not with an error: measured 2026-08-16,
        # interval=1h with range=max came back as 267 bars spanning 2000 to
        # 2026, which is monthly. Real prices on the wrong timeframe are the
        # worst failure available here because nothing downstream can detect
        # it - a zone drawn on monthly bars is still a valid-looking zone. The
        # smallest gap between consecutive bars is exactly one interval inside
        # any session, so it is the cheapest thing that catches the swap.
        gaps = [b.time - a.time for a, b in zip(rows, rows[1:])]
        if gaps and min(gaps) > INTERVALS[interval]:
            raise ProviderError(
                f"yahoo was asked for {interval} bars and returned none closer "
                f"together than {min(gaps)}s: it downgraded the interval silently"
            )
        return rows


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
