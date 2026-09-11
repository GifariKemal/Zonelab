"""Bars from TradingView Desktop for the offline tools, cached like the others.

    from tools.history import load
    load("tradingview:XAUUSD", "1d", 13000)

WHY A CALIBRATION RUN WOULD WANT THIS RATHER THAN `mt5:`. Depth, in the one
place the broker tape runs out first. Measured 12 September 2026 on XAUUSD:

    1d    tradingview 13,003 bars back to 1975 | mt5 3,132 back to 2016
    4h    tradingview 15,479                   | mt5 10,649
    1h    tradingview 20,000 (the request cap) | mt5 35,536

So MT5 still wins the intraday walk-forwards and this wins the slow ones, which
is the only reason both are reachable by prefix instead of one being the answer.

WHAT THESE BARS ARE, and it is not what `mt5:XAUUSD` is: `tradingview:XAUUSD`
resolves to COMEX:GC1!, the exchange's front-month future. `mt5:XAUUSD` is the
broker's spot CFD. They were measured 51.7 points apart on the same minute, so
neither may stand in for the other and this file never falls back to one when
the other is missing - the same rule the `yahoo:` and `mt5:` routes already
follow, for the same reason.

THE DELAY DOES NOT MATTER HERE and that is worth saying, because it matters a
great deal on the chart. Every one of these instruments except crypto and FX
arrives on the exchange's ten-minute delay, which moves only the newest bar. A
study reading closed history is unaffected; a study reading the forming bar was
already wrong for other reasons.
"""

from __future__ import annotations

import asyncio

import numpy as np

from app.models import Candle
from app.providers.tradingview import TradingViewProvider

from .yahoo import CACHE, _to_candles


def load(symbol: str, interval: str, bars: int, refresh: bool = False) -> list[Candle]:
    CACHE.mkdir(exist_ok=True)
    # Prefixed for the reason the yahoo cache is: these bars are a different
    # INSTRUMENT, not another vendor's view of the same one, and a file of
    # COMEX futures answering to a name a caller reads as spot is the silent
    # wrong answer the prefixes exist to prevent.
    path = CACHE / f"tradingview-{symbol}-{interval}-{bars}.npz"
    if path.exists() and not refresh:
        return _to_candles(np.load(path)["rows"])

    rows = _download(symbol, interval, bars)
    np.savez_compressed(path, rows=rows)
    return _to_candles(rows)


def _download(symbol: str, interval: str, bars: int) -> np.ndarray:
    """One synchronous pull, because every caller of `history.load` is sync.

    `asyncio.run` rather than a shared loop: these tools are one-shot scripts,
    the provider holds no state between calls beyond a delay it re-reads
    anyway, and a module-level loop would be a lifetime to manage for no gain.
    """
    candles = asyncio.run(TradingViewProvider().fetch(symbol, interval, bars))
    return np.array(
        [[c.time, c.open, c.high, c.low, c.close, c.volume] for c in candles],
        dtype=np.float64,
    )


def _selftest() -> None:
    """The cache key, which is the only thing here that can be silently wrong.

    Touches no network and no disk. What it pins is that the three feeds cannot
    collide on one file: they carry different instruments under the same app
    symbol, so a shared key would serve COMEX futures to a caller who asked for
    the broker's spot and nothing would look wrong.
    """
    mine = f"tradingview-{'XAUUSD'}-{'1d'}-{100}.npz"
    assert mine.startswith("tradingview-")
    assert mine != f"yahoo-{'XAUUSD'}-{'1d'}-{100}.npz"
    assert mine != f"{'XAUUSD'}-{'1d'}-{100}.npz"
