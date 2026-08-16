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
from app.providers.dukascopy import fetch_ticks

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

    rows, missed = _download(symbol, interval, bars)
    # A holed series is NOT cached. The per-hour cache already kept everything
    # that did arrive, so re-running is cheap and fills the gaps; writing the
    # final file here would freeze the holes in place and every later run would
    # read them back as if they were the market being quiet.
    if missed:
        print(f"  not caching: {missed} hours unreachable. Re-run to fill them; "
              f"the hours already fetched are cached and will not be re-asked.")
    else:
        np.savez_compressed(path, rows=rows)
    return _to_candles(rows)


def _download(symbol: str, interval: str, bars: int) -> tuple[np.ndarray, int]:
    step = INTERVALS[interval]
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

    # Hours cannot be computed from bars x interval: gold is shut about 49
    # hours a week and the feed also has genuinely empty hours inside the
    # session. So walk backwards until the bar count is met, with a ceiling so
    # an instrument that runs out of history stops instead of paging to 1999 -
    # the same failure tools/history.py guards against when Binance keeps
    # returning the same first bar forever.
    ceiling = math.ceil(bars * step / 3600 * 3) + 720

    # Folded into per-bar accumulators as each batch lands, NOT accumulated as
    # ticks. Holding every tick for the whole range is what a 20000-bar pull did
    # before this, and it reached 6 GB of resident memory before being killed:
    # 5000 trading hours is tens of millions of 4-tuples, and Python charges
    # over a hundred bytes for each. Folding bounds the cost by the number of
    # BARS, which is the number actually asked for.
    #
    # The accumulator is order-independent on purpose - first and last are kept
    # by tick timestamp rather than by arrival - so a bar straddling a batch
    # boundary merges correctly instead of taking its open from whichever batch
    # happened to be processed first.
    acc: dict[int, list] = {}
    starts: set[int] = set()  # bucket count, so the aggregate is not rebuilt per batch
    hours = 0
    missed = 0
    while len(starts) <= bars and hours < ceiling:
        batch = [end - timedelta(hours=h) for h in range(hours + 1, hours + 1 + BATCH)]
        # Tolerant here and nowhere else. The feed refuses connections for a
        # stretch after a few hundred hours, so all-or-nothing means a long
        # download can never finish - measured 2026-08-16, a 5000-hour pull died
        # at hour 144. Every completed hour is cached, so a tolerant pull that
        # reports its holes and is re-run converges on a complete series.
        page, failed = asyncio.run(fetch_ticks(symbol, batch, tolerate_gaps=True))
        for ms, bid, ask, volume in page:
            start = ms // 1000 // step * step
            slot = acc.get(start)
            if slot is None:
                acc[start] = [ms, bid, ms, bid, bid, bid, volume, ask - bid, 1]
                continue
            if ms < slot[0]:
                slot[0], slot[1] = ms, bid
            if ms > slot[2]:
                slot[2], slot[3] = ms, bid
            slot[4] = max(slot[4], bid)
            slot[5] = min(slot[5], bid)
            slot[6] += volume
            slot[7] += ask - bid
            slot[8] += 1
        missed += failed
        starts.update(acc)
        hours += BATCH
        print(f"  {symbol} {interval}: {len(starts)} bars from {hours}h"
              f"{f', {missed} hours unreachable' if missed else ''}    ", end="\r")

    covered_from = int((end - timedelta(hours=hours)).timestamp())
    covered_to = int(end.timestamp())
    # Same edge rule as to_candles: a bar straddling either end of what was
    # downloaded is dropped rather than emitted short, because its open would
    # come from whichever tick happened to sit nearest the edge.
    candles = [
        Candle(time=start, open=slot[1], high=slot[4], low=slot[5],
               close=slot[3], volume=slot[6], spread=slot[7] / slot[8])
        for start, slot in sorted(acc.items())
        if start >= covered_from and start + step <= covered_to
    ][-bars:]
    if not candles:
        raise ProviderError(
            f"dukascopy served no {interval} bars for {symbol} across {hours} hours"
        )

    print(f"  {symbol} {interval}: {len(candles)} bars from {hours}h of ticks"
          + (f", {missed} hours unreachable" if missed else ""))
    return np.array(
        [[c.time, c.open, c.high, c.low, c.close, c.volume, c.spread] for c in candles],
        dtype=np.float64,
    ), missed


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
