"""Deterministic offline candles.

Exists for two reasons: the app must render with no network and no key, and the
detector tests need a price series that is identical on every machine and every
run. Seeded from the symbol, so the same symbol always draws the same chart.

That claim used to be FALSE, and the way it was false is worth keeping written
down. The seed was `abs(hash(symbol))`, and CPython randomises `hash()` of a str
per process unless PYTHONHASHSEED is pinned: three subprocesses on this machine
seeded 580043279, 1385725993 and 1467721949 off the same "BTCUSDT". So every
server restart drew a different chart under the same symbol, and every harness
run against this provider was reproducible only within one process. `crc32` is
stable by specification, which is the property the docstring was already
promising. What made this hard to notice is that a second, unrelated source of
variation WAS found and documented first - the time anchor below - and it
explained the symptom well enough to stop the search.
"""

from __future__ import annotations

import time as _time
from zlib import crc32

import numpy as np

from .. import clock
from ..models import Candle
from .base import INTERVALS, ProviderError


class SyntheticProvider:
    name = "synthetic"

    def available(self) -> bool:
        return True

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        step = INTERVALS.get(interval)
        if step is None:
            raise ProviderError(f"unknown interval {interval}")
        # crc32, not hash(): see the module docstring. Stable across processes
        # by specification, and already bounded to 32 bits.
        return generate(bars, step, seed=crc32(symbol.encode()))


def _closed(epoch: int) -> bool:
    """Is the market shut at this instant, on the CME futures week?

    Shut from 17:00 New York Friday to 18:00 Sunday, and for the one-hour daily
    maintenance break from 17:00 to 18:00 on the other weekdays. Those are the
    same boundaries `app/gaps.py` reads its NDOG and NWOG off, which is the
    point: a fake market that never closes cannot exercise a single line of the
    session code, and this repo has a whole module about session boundaries.
    """
    when = clock.to_ny(epoch)
    if when.hour == 17:
        return True
    weekday = when.weekday()  # Monday 0 .. Sunday 6
    if weekday == 5:  # all Saturday
        return True
    if weekday == 4 and when.hour >= 17:  # Friday evening onward
        return True
    return weekday == 6 and when.hour < 18  # Sunday before the reopen


def _session_grid(now: int, step: int, bars: int) -> list[int]:
    """`bars` open times ending at `now`, skipping the hours the market is shut.

    THE SERIES USED TO BE PERFECTLY CONTIGUOUS, and that was a hole in every
    offline test that touches time. `gaps.opening_gaps` decides whether an
    instrument has opening gaps at all by asking whether its bar grid ever has a
    hole; on the old synthetic series it never did, so the honest answer was
    "this is a 24/7 instrument, it has no opening gaps" - and the overlay tests
    that asserted gaps DID exist were asserting fabricated objects. Only the
    timestamps change here. Prices are drawn from the seeded generator in the
    same order as before, so nothing that measures price moves.
    """
    out: list[int] = []
    t = now
    # Bounded rather than `while True`: a step longer than a week would
    # otherwise spin forever looking for an open slot that the coarse grid keeps
    # landing outside of. 8 slots per bar is far more than any real ratio needs.
    for _ in range(bars * 8):
        if len(out) == bars:
            break
        if not _closed(t):
            out.append(t)
        t -= step
    out.reverse()
    return out


def generate(bars: int, step: int, seed: int = 7, start_price: float = 3400.0) -> list[Candle]:
    """Random walk with deliberate impulse/consolidation alternation.

    A pure Gaussian walk almost never produces a clean base-then-departure, so
    the detector would have nothing to find. This alternates calm and trending
    stretches, which is what the real series does and what makes the offline
    mode a useful preview rather than a blank chart.
    """
    rng = np.random.default_rng(seed)
    grid = _session_grid(int(_time.time()) // step * step, step, bars)
    price = start_price
    out: list[Candle] = []

    i = 0
    while i < bars:
        trending = rng.random() < 0.45
        length = int(rng.integers(3, 9) if trending else rng.integers(4, 14))
        drift = float(rng.normal(0, 1.4)) if trending else 0.0
        vol = 3.2 if trending else 0.7

        for _ in range(min(length, bars - i)):
            # A REOPEN JUMPS. Putting holes in the time grid without jumping the
            # price produced a market that shuts and then reopens at exactly the
            # last traded price, so every NDOG and NWOG came out ZERO WIDE - the
            # gap tests still ran and were measuring nothing, and two of the four
            # tier reductions collapsed onto identical bands because the gaps
            # they reduce had no height to differ over. The whole point of an
            # opening gap is that the reopen is somewhere else.
            #
            # Four times a bar's own volatility, which is the order of magnitude
            # the real feed shows: measured on MT5 gold, the three weekend gaps
            # to 2026-08-19 were 29.2, 5.3 and 3.6 against a typical 15m range
            # near 2. Drawn from the same seeded generator, so the series stays
            # reproducible bar for bar.
            if i > 0 and grid[i] - grid[i - 1] > step:
                price += float(rng.normal(0, vol * 4.0))
            open_ = price
            close = open_ + drift + float(rng.normal(0, vol))
            wick = abs(float(rng.normal(0, vol * 0.5)))
            high = max(open_, close) + wick
            low = min(open_, close) - wick
            out.append(
                Candle(
                    time=grid[i],
                    open=round(open_, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close, 2),
                    volume=round(float(rng.uniform(500, 5000)) * (2.0 if trending else 1.0), 1),
                )
            )
            price = close
            i += 1
    return out
