"""The local MetaTrader 5 terminal as a HISTORY source for the measurement rig.

    from tools import history
    history.load("mt5:XAUUSD", "15m", 50000)

WHY THIS EXISTS. Every number in docs/CALIBRATION.md was measured on what the
network would give: Binance crypto, Dukascopy where it answered, Yahoo COMEX
futures for the gold cross-check. Three of the five series are crypto and gold
is represented by PAXG - the calibration document says so itself, in its own
list of what was not measured. The terminal on this machine carries the
broker's own gold, deep, with no rate limit and no page cap: 99,999 fifteen
minute bars answered in 0.01 seconds, measured 2026-08-19.

WHY IT IS A PREFIXED SOURCE AND NOT A FALLBACK, which is the same rule the
`yahoo:` route already follows. `mt5:XAUUSD` is the BROKER'S SPOT CFD;
`yahoo:XAUUSD` is the COMEX front-month future; plain `XAUUSD` is Dukascopy
spot. Measured side by side on 2026-08-19 at the same minute, the MT5 spot
closed at 4459.6 while GC=F closed at 4515.8 - a 56 dollar basis. Letting any
of them substitute for another would swap the instrument under a measurement
and change its answer for a reason that has nothing to do with the market.

NO CACHE FILE, and that is deliberate rather than an omission. `history.load`
caches because Binance pages 1000 bars at a time over the network and a re-run
must see the same bars. This source reads a local file the terminal already
maintains; caching it would add a second copy that goes stale silently, and the
terminal is the authority on its own history. The cost it saves is 0.01s.
"""

from __future__ import annotations

import time

from app.models import Candle
from app.providers.base import INTERVALS, ProviderError
from app.providers.mt5 import MT5Provider, _MAX_COUNT, _TIMEFRAMES, mt5


def load(symbol: str, interval: str, bars: int, refresh: bool = False) -> list[Candle]:
    """`bars` closed candles of `symbol`, oldest first, straight off the terminal.

    `refresh` is accepted and ignored so the signature matches the other three
    loaders `history.load` dispatches to. There is nothing to refresh: the read
    is live every time.

    THE FORMING BAR IS DROPPED HERE TOO. `app/providers/__init__.py` explains at
    length why an unclosed bar must never reach a detector - 42 zone states
    changed and changed back inside one bar over 599 real formations - and a
    measurement rig is the last place that should be exempt. This path bypasses
    `get_candles`, so it has to do it itself rather than inherit it.
    """
    if mt5 is None:
        raise ProviderError(
            "the MetaTrader5 package is not installed - it is Windows-only, and "
            "this source needs a terminal on this machine"
        )
    step = INTERVALS.get(interval)
    timeframe = _TIMEFRAMES.get(interval)
    if step is None or timeframe is None:
        raise ProviderError(f"mt5 has no {interval} interval")

    provider = MT5Provider()
    # Ask for one MORE than wanted, because the newest is about to be dropped.
    # Without this a caller asking for 50,000 bars silently measures 49,999.
    count = min(bars + 1, _MAX_COUNT)
    rows = provider._fetch(symbol.upper(), timeframe, count)
    if not rows:
        raise ProviderError(f"mt5 returned no bars for {symbol}")

    now = int(time.time())
    if rows[-1].time + step > now:
        rows = rows[:-1]
    return rows[-bars:]
