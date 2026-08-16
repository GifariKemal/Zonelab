"""Dukascopy ticks aggregated into bars, cached exactly as tools/history.py is.

Same contract - `load(symbol, interval, bars)`, oldest-first Candles - and the
same reason for the cache: calibration must get identical bars on every re-run,
otherwise "the score improved" cannot be told apart from "the window moved".
The cache earns its keep far harder here than it does for Binance, because this
feed is one HTTP request per HOUR of ticks: a 20,000-bar M15 series is roughly
five thousand downloads, so the .npz is the difference between a minute and an
afternoon.

Bars are the BID series and each one carries the mean spread over it, which is
the first transaction-cost figure any number in this project has ever had. The
.bi5 format, the zero-indexed month and the gold price divisor are all
documented with their sources in app/providers/dukascopy.py.
"""

from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from app.models import Candle
from app.providers.base import INTERVALS, ProviderError
from app.providers.dukascopy import fetch_ticks, to_candles

CACHE = Path(__file__).resolve().parent.parent / ".cache"
BATCH = 48  # hours per round trip; wide enough to amortise, small enough to stop early


def load(symbol: str, interval: str, bars: int, refresh: bool = False) -> list[Candle]:
    CACHE.mkdir(exist_ok=True)
    # Prefixed, unlike the Binance cache: these bars are bid-side with a spread
    # and those are last-trade without one. Two files that disagree about what
    # a price means must never be able to answer to the same name.
    path = CACHE / f"dukascopy-{symbol}-{interval}-{bars}.npz"

    if path.exists() and not refresh:
        raw = np.load(path)
        return _to_candles(raw["rows"])

    rows = _download(symbol, interval, bars)
    np.savez_compressed(path, rows=rows)
    return _to_candles(rows)


def _download(symbol: str, interval: str, bars: int) -> np.ndarray:
    step = INTERVALS[interval]
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

    # Hours cannot be computed from bars x interval: gold is shut about 49
    # hours a week and the feed also has genuinely empty hours inside the
    # session. So walk backwards until the bar count is met, with a ceiling so
    # an instrument that runs out of history stops instead of paging to 1999 -
    # the same failure tools/history.py guards against when Binance keeps
    # returning the same first bar forever.
    ceiling = math.ceil(bars * step / 3600 * 3) + 720

    ticks: list[tuple[int, float, float, float]] = []
    starts: set[int] = set()  # bucket count, so the aggregate is not rebuilt per batch
    hours = 0
    while len(starts) <= bars and hours < ceiling:
        batch = [end - timedelta(hours=h) for h in range(hours + 1, hours + 1 + BATCH)]
        page = asyncio.run(fetch_ticks(symbol, batch))
        ticks.extend(page)
        starts.update(t[0] // 1000 // step * step for t in page)
        hours += BATCH
        print(f"  {symbol} {interval}: {len(starts)} bars from {hours}h", end="\r")

    covered_from = int((end - timedelta(hours=hours)).timestamp())
    candles = to_candles(ticks, interval, covered_from, int(end.timestamp()))[-bars:]
    if not candles:
        raise ProviderError(
            f"dukascopy served no {interval} bars for {symbol} across {hours} hours"
        )

    print(f"  {symbol} {interval}: {len(candles)} bars from {hours}h of ticks")
    return np.array(
        [[c.time, c.open, c.high, c.low, c.close, c.volume, c.spread] for c in candles],
        dtype=np.float64,
    )


def _to_candles(rows: np.ndarray) -> list[Candle]:
    return [
        Candle(
            time=int(r[0]),
            open=r[1],
            high=r[2],
            low=r[3],
            close=r[4],
            volume=r[5],
            spread=r[6],
        )
        for r in rows
    ]
