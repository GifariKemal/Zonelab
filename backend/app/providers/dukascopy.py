"""Dukascopy tick datafeed: real spot gold, and the first spread in this project.

Two limitations documented elsewhere here are both this file's fault to fix.
Gold was only ever represented by PAXG - tokenized gold on Binance, carrying
its own premium and trading weekends - while three of the five calibration
series were crypto. And no number anywhere in this project has included
transaction cost, because every other provider ships one price per bar and
there is nothing to subtract. Dukascopy publishes BID and ASK for every tick,
so the spread stops being an assumption nobody wrote down and becomes a
measurement that travels with the bar.

Format, established 2026-08-16 against the live feed and cross-checked against
Dukascopy's own instrument table:

  URL   https://datafeed.dukascopy.com/datafeed/{SYM}/{YYYY}/{MM}/{DD}/{HH}h_ticks.bi5
        MM IS ZERO-INDEXED: January is "00" and December is "11", while DD and
        HH are not. This is the trap in most implementations of this feed,
        because it does not fail loudly - it silently serves the neighbouring
        month, or 404s and reads as "the vendor has no data".
        limemojito.com/reading-dukascopy-bi5-tick-history-with-the-tradingdata-stream-library-for-java/
        hexdocs.pm/dukascopy/Dukascopy.DataFeed.html

  BODY  LZMA-compressed despite the .bi5 extension; stdlib `lzma.decompress`
        reads it directly. Uncompressed it is a flat array of 20-byte
        BIG-ENDIAN records, struct ">3i2f":
            int32   milliseconds after the top of the hour
            int32   ask, scaled integer
            int32   bid, scaled integer
            float32 ask volume, float32 bid volume (millions of units)
        ASK COMES FIRST. Swapping the two yields a negative spread on every
        tick, which is what tests/test_dukascopy.py checks for.

  SCALE Divide the integers by 10**priceScale from Dukascopy's instrument
        table. It is NOT 100000 for everything, and gold is the counter-
        example: XAU/USD is priceScale 3, divisor 1000, against 5 and 100000
        for EUR/USD. Guessing 100000 prints gold at 4.37 instead of 4373.35.
        Table published by Dukascopy, mirrored at Leo4815162342/dukascopy-node
        src/utils/instrument-meta-data/generated/raw-meta-data-*.json
"""

from __future__ import annotations

import asyncio
import lzma
import math
import struct
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np

from ..config import settings
from ..models import Candle
from .base import INTERVALS, ProviderError, normalize
from .sources import vendor_symbol

FEED = "https://datafeed.dukascopy.com/datafeed"
RECORD = struct.Struct(">3i2f")

# 10 ** priceScale, per the instrument table cited above. Only instruments this
# has actually been checked against are listed: a wrong divisor is silent and
# poisons every price, so refusing an unknown symbol beats guessing at one.
DIVISOR: dict[str, float] = {"XAUUSD": 1000.0, "EURUSD": 100000.0}

# One HTTP request per hour of ticks, so an interactive chart is bounded by how
# long it is willing to wait. 240 hours covers 500 M15 bars including the
# weekend they fall across and finishes in seconds at this concurrency; a
# request needing more is a measurement run and belongs in tools/dukascopy.py,
# which caches. Hanging for four minutes and then drawing is not an option the
# UI can distinguish from being broken.
# Every completed hour is cached on disk, so this cap bounds the FIRST look at a
# range, not every look. Raised from 240 once the cache existed: 240 refused a
# 500-bar H1 chart of XAUUSD, which is the default symbol, so the default
# instrument could not be drawn on the default timeframe.
HOUR_CACHE = Path(__file__).resolve().parents[2] / ".cache" / "dukascopy-hours"
MAX_INTERACTIVE_HOURS = 1200
# Measured 2026-08-16: a 120-hour fetch at 8 completed, and every request for
# the next few minutes hit a connect timeout. Lowered rather than diagnosed,
# because the vendor publishes no rate limit and guessing one would be fiction.
CONCURRENCY = 4


def hour_url(vendor: str, hour: datetime) -> str:
    return (
        f"{FEED}/{vendor}/{hour.year}/{hour.month - 1:02d}/{hour.day:02d}"
        f"/{hour.hour:02d}h_ticks.bi5"
    )


def decode(
    payload: bytes, hour: datetime, divisor: float
) -> list[tuple[int, float, float, float]]:
    """One hour's .bi5 body as (epoch ms, bid, ask, volume) tuples.

    An empty payload is a tickless hour, not a failure - see `_hour`. An LZMA
    or struct error is raised instead, because a truncated body is corruption
    and returning an empty hour for it would make it look like a weekend.
    """
    if not payload:
        return []
    base = int(hour.timestamp()) * 1000
    return [
        (base + ms, bid / divisor, ask / divisor, ask_volume + bid_volume)
        for ms, ask, bid, ask_volume, bid_volume in RECORD.iter_unpack(
            lzma.decompress(payload)
        )
    ]


def to_candles(
    ticks: list[tuple[int, float, float, float]],
    interval: str,
    covered_from: int,
    covered_to: int,
) -> list[Candle]:
    """Aggregate ticks into `interval` bars, oldest first, carrying the spread.

    Bars are the BID series because that is the price a long position exits
    at. Building them from the ask, or from the mid, credits every long half a
    spread it never got, which is precisely the cost this provider exists to
    stop hiding.

    `covered_from`/`covered_to` are the epoch seconds actually downloaded. A
    bar straddling either edge is dropped rather than emitted short: its open
    or close would come from whichever tick happened to be nearest the edge,
    and a wrong open on the oldest bar is invisible until it is the one a zone
    got drawn on.
    """
    step = INTERVALS[interval]
    buckets: dict[int, list[tuple[int, float, float, float]]] = {}
    for tick in sorted(ticks):
        buckets.setdefault(tick[0] // 1000 // step * step, []).append(tick)

    out: list[Candle] = []
    for start in sorted(buckets):
        if start < covered_from or start + step > covered_to:
            continue
        group = buckets[start]
        bids = [bid for _, bid, _, _ in group]
        out.append(
            Candle(
                time=start,
                open=bids[0],
                high=max(bids),
                low=min(bids),
                close=bids[-1],
                volume=sum(volume for *_, volume in group),
                spread=sum(ask - bid for _, bid, ask, _ in group) / len(group),
            )
        )
    return out


def _cache_path(vendor: str, hour: datetime) -> Path:
    return HOUR_CACHE / vendor.replace("/", "") / hour.strftime("%Y%m%d-%H.npy")


def _store(path: Path, ticks: list[tuple[int, float, float, float]], fresh: bool):
    """Write an hour to the cache, unless it is the hour still being made.

    A tickless hour is cached as an empty array on purpose. Weekends are a third
    of the calendar, and without this every download would re-ask the feed for
    the same 48 hours it already knows are empty.
    """
    if fresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, np.array(ticks, dtype=np.float64).reshape(-1, 4))


async def _hour(
    client: httpx.AsyncClient, vendor: str, hour: datetime, divisor: float
) -> list[tuple[int, float, float, float]]:
    # A completed hour of ticks is immutable, so caching it is correct rather
    # than merely convenient, and it is what makes this feed usable at all: the
    # cost here is one HTTP request PER HOUR, so an H1 chart of 500 bars is 500
    # requests. Cached, the second look at any overlapping range is free, and
    # changing timeframe costs nothing because the ticks underneath are the
    # same. Only past hours are cached; the current one is still filling.
    path = _cache_path(vendor, hour)
    # Two hours of margin, not one. The feed publishes with a lag, so the hour
    # just ended can answer thinly and then fill in.
    edge = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    fresh = hour >= edge - timedelta(hours=2)
    if not fresh and path.exists():
        rows = np.load(path)
        return [(int(r[0]), float(r[1]), float(r[2]), float(r[3])) for r in rows]

    url = hour_url(vendor, hour)
    for attempt in range(3):
        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            # Measured 2026-08-16: a plain connection timeout on one hour in a
            # run where its neighbours all answered. Retried rather than
            # raised, or a single flaky hour aborts a 5000-hour download.
            if attempt == 2:
                # The class name, not just str(exc). httpx.ConnectTimeout
                # stringifies to the EMPTY STRING, so the obvious f-string
                # produced "network error contacting <url>: " - a message that
                # promises a cause and then delivers nothing, which is exactly
                # the swallowed failure this project refuses to ship.
                why = str(exc) or type(exc).__name__
                raise ProviderError(
                    f"network error contacting {url}: {why}. Dukascopy is one "
                    f"request per hour and answers slowly in bursts; a smaller "
                    f"request usually goes through."
                ) from exc
            await asyncio.sleep(0.5 * (attempt + 1))
            continue

        # A tickless hour - weekend, holiday, or a quiet metal overnight - is
        # served as HTTP 200 with a ZERO-LENGTH body (measured on Saturday
        # 2026-08-15 03h), and an hour the feed has not published yet is a 404
        # (measured the same day on an hour still in the future). Both are
        # gaps in a 24/5 instrument, not errors. Treating either as a failure
        # would abort every download that crosses a weekend or reaches for the
        # newest hour, which is every download.
        if response.status_code == 404:
            # NOT cached, unlike a 200 with an empty body. A 404 means the feed
            # has not published this hour, which is a statement about the feed
            # and not about the market - publish lag would otherwise freeze an
            # hour as permanently empty. An empty 200 IS authoritative and is
            # cached below.
            return []
        if response.status_code in (500, 502, 503, 504) and attempt < 2:
            await asyncio.sleep(0.5 * (attempt + 1))  # 503 seen under bursts
            continue
        if response.status_code != 200:
            raise ProviderError(
                f"dukascopy returned HTTP {response.status_code} for {url}"
            )
        try:
            ticks = decode(response.content, hour, divisor)
            _store(path, ticks, fresh)
            return ticks
        except (lzma.LZMAError, struct.error) as exc:
            raise ProviderError(f"dukascopy sent an unreadable .bi5 at {url}: {exc}") from exc
    raise ProviderError(f"dukascopy never answered {url}")


async def fetch_ticks(
    symbol: str, hours: list[datetime]
) -> list[tuple[int, float, float, float]]:
    """Every tick in `hours`, unordered. Shared by the provider and the loader."""
    vendor = vendor_symbol("dukascopy", symbol)
    divisor = DIVISOR.get(vendor.upper())
    if divisor is None:
        raise ProviderError(
            f"dukascopy price scale for {vendor} has not been verified; "
            f"known: {', '.join(sorted(DIVISOR))}"
        )

    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(hour: datetime) -> list[tuple[int, float, float, float]]:
        async with gate:
            return await _hour(client, vendor, hour, divisor)

    async with httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": "Zonelab/0.1 (local research tool)"},
        follow_redirects=True,
    ) as client:
        pages = await asyncio.gather(*(one(hour) for hour in hours))
    return [tick for page in pages for tick in page]


class DukascopyProvider:
    """Free, keyless, and the only source here that is real spot gold with a
    spread. Slow by construction: one request per hour of ticks, hence the
    interactive cap."""

    name = "dukascopy"

    def available(self) -> bool:
        return True

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        step = INTERVALS.get(interval)
        if step is None:
            raise ProviderError(f"dukascopy has no {interval} interval")

        # Gold trades about 119 hours of every 168, so asking for exactly
        # bars x interval hours comes back a third short around every weekend.
        hours_needed = math.ceil(bars * step / 3600 * 1.5) + 1
        if hours_needed > MAX_INTERACTIVE_HOURS:
            raise ProviderError(
                f"{bars} {interval} bars needs about {hours_needed} hours of ticks, "
                f"over the {MAX_INTERACTIVE_HOURS}-hour interactive cap - dukascopy "
                f"is one HTTP request per hour, so that is a wait, not a chart. Use "
                f"fewer bars, a lower interval, or tools/dukascopy.py, which caches."
            )

        end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        hours = [end - timedelta(hours=h) for h in range(1, hours_needed + 1)]
        ticks = await fetch_ticks(symbol, hours)
        if not ticks:
            # Gold and FX are shut from Friday 21:00 to Sunday 22:00 UTC, so a
            # small bar count asked for over a weekend reaches back into
            # nothing but empty hours. That is the market, not a fault, and
            # saying "no data" without saying why sends the user looking for a
            # bug in the provider.
            raise ProviderError(
                f"dukascopy served no ticks for {symbol} in the last {hours_needed} "
                f"hours - this instrument is closed at weekends, so ask for more "
                f"bars to reach back past it, or pick another provider"
            )
        covered_from = int(hours[-1].timestamp())
        return normalize(
            to_candles(ticks, interval, covered_from, int(end.timestamp())), bars
        )
