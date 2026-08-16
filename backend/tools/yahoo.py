"""Yahoo's gold FUTURES, cached exactly as tools/history.py and tools/dukascopy.py are.

Same contract - `load(symbol, interval, bars)`, oldest-first Candles - and the
same reason for the cache: calibration must get identical bars on every re-run,
otherwise "the score improved" cannot be told apart from "the window moved".

WHAT THIS IS NOT: spot. GC=F is the COMEX front-month future. Yahoo carries no
spot gold at all - XAUUSD=X and XAU=X both answer 404 (measured 2026-08-16), so
there is no spot variant to prefer. Futures carry a financing premium over spot
and keep the exchange's own session, so these bars exist to cross-check
STRUCTURE against the Dukascopy spot series, never to stand in for it.

Independence is the entire reason this source was picked, and it is the one
thing the obvious alternative turned out not to have. HistData.com publishes
monthly XAUUSD M1 zips that are genuine spot, reach back to 2009, need no key
and cost two HTTP requests per MONTH against Dukascopy's one per HOUR. Measured
against Dukascopy over the 660 common minutes of 2026-08-06 12:00-23:59 UTC,
98.6% of opens, 99.7% of highs, 99.7% of lows and 99.1% of closes were
BIT-IDENTICAL, mean |dClose| 0.0011. Two independent gold feeds cannot agree to
the millipip on 99% of minutes; it is the same feed repackaged, and a second
opinion from it would corroborate nothing. Yahoo is a different vendor quoting
a different instrument on a different exchange, which is worth more here than
a faster copy of the series already held.

One HTTP request buys the whole series, so this is also the fast source the
Dukascopy loader is not: 17,358 H1 bars arrive in about a second.

MEASURED against Dukascopy spot on the overlapping bars, 2026-08-16:

  15m, 495 bars over 7 days   basis +58.73 mean, sd 1.55, return corr 0.9969
  1h,  448 bars over 30 days  basis +39.11 mean, sd 26.02, return corr 0.9665

The futures premium is real, large and NOT constant, so absolute levels from
the two sources are never comparable - only structure is. Over a week the basis
barely moves (sd 1.55 on a level of 59) and the two instruments are the same
shape; over a month it drifted from +5 to +57.

THE TRAP IN "=F": it is a CONTINUOUS front-month series, so it steps when the
contract rolls. One roll sits inside the sample above, 2026-07-29 between 04:00
and 07:00 UTC, where the basis jumped -1.56 to +59.03 - a 60-point gap on a
4100 instrument that gold never actually made. Dropping that one bar lifts the
H1 return correlation from 0.9665 to 0.9919, which is the measure of how much
damage it does. Every detector here would read that gap as a huge impulse
candle and draw a zone on it, so a roll bar is an artefact to find and exclude,
not a formation. Rolls are quarterly, so a window under about two months
usually contains none - the 15m series above contains none, hence its 0.9969.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np

from app.models import Candle
from app.providers.base import ProviderError
from app.providers.sources import YahooProvider

CACHE = Path(__file__).resolve().parent.parent / ".cache"


def load(symbol: str, interval: str, bars: int, refresh: bool = False) -> list[Candle]:
    CACHE.mkdir(exist_ok=True)
    # Prefixed like the Dukascopy cache, and for a sharper reason than that one
    # has: these bars are a different INSTRUMENT, not merely a different
    # vendor's view of the same one. A file of futures bars answering to the
    # name of a spot series is exactly the silent wrong answer this loader was
    # added to guard against.
    path = CACHE / f"yahoo-{symbol}-{interval}-{bars}.npz"

    if path.exists() and not refresh:
        raw = np.load(path)
        return _to_candles(raw["rows"])

    rows = _download(symbol, interval, bars)
    np.savez_compressed(path, rows=rows)
    return _to_candles(rows)


def _download(symbol: str, interval: str, bars: int) -> np.ndarray:
    candles = asyncio.run(YahooProvider().fetch(symbol, interval, bars))
    if not candles:
        raise ProviderError(f"yahoo served no {interval} bars for {symbol}")

    # A short series is SAID rather than returned quietly. Yahoo's intraday
    # history is a hard recency wall - 60 days at 15m, 730 at 1h, measured
    # 2026-08-16 - so falling short is the vendor's ceiling and not a fault,
    # but a calibration run that asked for 20,000 bars and silently got 5,637
    # would attribute its number to a sample four times larger than it had.
    short = (
        ""
        if len(candles) >= bars
        else f" ({bars} asked for; Yahoo's intraday recency wall, not an error)"
    )
    print(f"  yahoo {symbol} {interval}: {len(candles)} bars{short}")
    return np.array(
        [[c.time, c.open, c.high, c.low, c.close, c.volume] for c in candles],
        dtype=np.float64,
    )


def _to_candles(rows: np.ndarray) -> list[Candle]:
    # Six columns, not the Dukascopy loader's seven: Yahoo ships one price per
    # bar, so there is no spread to store and `spread` stays None. None means
    # "not measured" and must not become 0.0 here, or every cost figure taken
    # off this series would quietly assume free trading.
    return [
        Candle(
            time=int(r[0]),
            open=r[1],
            high=r[2],
            low=r[3],
            close=r[4],
            volume=r[5],
        )
        for r in rows
    ]
