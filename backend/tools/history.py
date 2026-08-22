"""Paged historical download with an on-disk cache.

Calibration needs tens of thousands of bars and needs the same bars on every
re-run, otherwise "the score improved" cannot be told apart from "the window
moved". Binance caps a klines call at 1000 rows, so this pages backwards from
now and caches the result as .npz.

Binance for the crypto tickers, Dukascopy for the spot-FX and metal symbols it
has a verified price scale for. The split is invisible to callers: `load` takes
the same three arguments either way.

A third route exists only because it must be asked for by name. Gold has two
sources here and they are not interchangeable - Dukascopy is spot, Yahoo is the
COMEX future - so nothing may pick between them on a caller's behalf. Prefix
the symbol, `yahoo:XAUUSD`, and see tools/yahoo.py for what that instrument is.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import numpy as np

from app.models import Candle
from app.providers.base import INTERVALS
from app.providers.dukascopy import DIVISOR as DUKASCOPY_SYMBOLS

from tools import dukascopy, mt5, yahoo

CACHE = Path(__file__).resolve().parent.parent / ".cache"
PAGE = 1000  # vendor hard cap

#: How many gaps to look at when deciding whether a stretch is really the
#: interval it claims to be, and how many of them have to match.
_SPACING_WINDOW = 50
_SPACING_MATCH = 25


def irregular_prefix(candles: list[Candle], interval: str) -> int:
    """How many leading bars are NOT spaced at `interval`.

    THE DEFECT THIS EXPOSES, measured on 2026-08-21. `load("mt5:XAUUSD", "1h",
    50000)` answers with 35,192 bars reaching back to 2016 - and the oldest
    1,338 of them are spaced ONE DAY apart while still being labelled hourly.
    The terminal simply has no deep intraday history and serves what it has. A
    detector reads consecutive bars as adjacent, so ATR, swings and every zone
    in that stretch are computed across day-wide steps.

    It was found through a symptom that looked unrelated: a trade reporting 42
    nights held on an 80-bar horizon, which is impossible at one bar an hour and
    ordinary at one bar a day.

    WHAT IT COST, AND THE DIRECTION MATTERS. Those 1,338 bars carry 43 of the 953
    gate-clearing trades, and they read -0.192 R against +0.216 R for the 910 in
    the genuinely hourly stretch. So the contaminated region DILUTED the headline
    rather than inflating it: +0.198 R pooled is conservative. That is luck, not
    design, and the next instrument may not be lucky.

    Counted rather than trimmed. A tool that wants a clean window can slice; one
    that silently dropped a tenth of a series would be answering a question
    nobody asked.
    """
    step = INTERVALS[interval]
    if len(candles) < _SPACING_WINDOW + 1:
        return 0
    gaps = [b.time - a.time for a, b in zip(candles, candles[1:])]
    for start in range(len(gaps) - _SPACING_WINDOW):
        window = gaps[start : start + _SPACING_WINDOW]
        # A market shuts, so a regular stretch still holds weekend and session
        # gaps. Requiring HALF the window to be exactly one step is enough to
        # tell "hourly with holes" from "daily wearing an hourly label".
        if sum(1 for gap in window if gap == step) >= _SPACING_MATCH:
            # The window says "the regular stretch begins somewhere in here" and
            # it can trip up to `_SPACING_MATCH` gaps EARLY, because half a
            # window of regular gaps already satisfies it. Walk on to the first
            # gap that IS the step, which is where the stretch actually starts.
            # Without this the count understates by about 25 every time - it read
            # 1,314 where the boundary was 1,338 on the terminal's own history.
            for index in range(start, len(gaps)):
                if gaps[index] == step:
                    return index
            return start
    return len(candles)


def load(symbol: str, interval: str, bars: int, refresh: bool = False) -> list[Candle]:
    # An explicit `yahoo:` prefix rather than a new argument, for the same
    # reason the Dukascopy route is a test on the symbol: it keeps
    # `load(symbol, interval, bars)` intact for the two dozen callers, and it
    # lets any of them reach the cross-check series by editing one string in a
    # SERIES list or on a command line instead of learning a keyword. It has to
    # be spelled out because the two gold series are different INSTRUMENTS, so
    # falling back from one to the other would swap spot for futures silently.
    source, _, ticker = symbol.partition(":")
    if source.lower() == "yahoo":
        return yahoo.load(ticker, interval, bars, refresh)

    # The local terminal, on the same rule and for the same reason as `yahoo:`.
    # `mt5:XAUUSD` is the broker's spot CFD, `yahoo:XAUUSD` the COMEX future and
    # bare `XAUUSD` Dukascopy spot - measured 56 dollars apart on 2026-08-19 at
    # the same minute, so none of the three may stand in for another. It has no
    # page cap and no rate limit, which is what makes a 50,000-bar walk-forward
    # on real broker gold possible at all; see tools/mt5.py.
    if source.lower() == "mt5":
        return mt5.load(ticker, interval, bars, refresh)

    # XAUUSD here is real spot gold with a measured spread, not PAXG; only
    # Dukascopy carries it, and everything else this project measures on is a
    # Binance ticker. Routing on the symbol rather than on a new argument is
    # what keeps `load(symbol, interval, bars)` working for the two dozen tools
    # that already call it.
    if symbol.upper() in DUKASCOPY_SYMBOLS:
        return dukascopy.load(symbol, interval, bars, refresh)

    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{symbol}-{interval}-{bars}.npz"

    if path.exists() and not refresh:
        raw = np.load(path)
        return _to_candles(raw["rows"])

    rows = _download(symbol, interval, bars)
    np.savez_compressed(path, rows=rows)
    return _to_candles(rows)


def _download(symbol: str, interval: str, bars: int) -> np.ndarray:
    step_ms = INTERVALS[interval] * 1000
    end = int(time.time() * 1000) // step_ms * step_ms
    collected: dict[int, list[float]] = {}

    with httpx.Client(timeout=30.0) as client:
        while len(collected) < bars:
            want = min(PAGE, bars - len(collected))
            start = end - want * step_ms
            response = client.get(
                "https://api.binance.com/api/v3/klines",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": start,
                    "endTime": end,
                    "limit": want,
                },
            )
            response.raise_for_status()
            page = response.json()
            if not page:
                break  # ran off the start of the instrument's history

            for r in page:
                collected[int(r[0])] = [
                    float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])
                ]  # fmt: skip

            oldest = int(page[0][0])
            if oldest >= end:
                # The cursor did not move. It happens at the start of an
                # instrument's history, where the same first bar comes back
                # forever, and without this the loop never terminates and never
                # says why.
                break
            end = oldest
            time.sleep(0.12)  # stay well inside the weight budget

    ordered = sorted(collected)
    print(f"  {symbol} {interval}: {len(ordered)} bars")
    return np.array(
        [[t, *collected[t]] for t in ordered], dtype=np.float64
    )


def _to_candles(rows: np.ndarray) -> list[Candle]:
    return [
        Candle(
            time=int(r[0]) // 1000,
            open=r[1],
            high=r[2],
            low=r[3],
            close=r[4],
            volume=r[5],
        )
        for r in rows
    ]
