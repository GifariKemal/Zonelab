"""Deterministic offline candles.

Exists for two reasons: the app must render with no network and no key, and the
detector tests need a price series that is identical on every machine and every
run. Seeded from the symbol, so the same symbol always draws the same chart.
"""

from __future__ import annotations

import time as _time

import numpy as np

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
        return generate(bars, step, seed=abs(hash(symbol)) % (2**31))


def generate(bars: int, step: int, seed: int = 7, start_price: float = 3400.0) -> list[Candle]:
    """Random walk with deliberate impulse/consolidation alternation.

    A pure Gaussian walk almost never produces a clean base-then-departure, so
    the detector would have nothing to find. This alternates calm and trending
    stretches, which is what the real series does and what makes the offline
    mode a useful preview rather than a blank chart.
    """
    rng = np.random.default_rng(seed)
    now = int(_time.time()) // step * step
    price = start_price
    out: list[Candle] = []

    i = 0
    while i < bars:
        trending = rng.random() < 0.45
        length = int(rng.integers(3, 9) if trending else rng.integers(4, 14))
        drift = float(rng.normal(0, 1.4)) if trending else 0.0
        vol = 3.2 if trending else 0.7

        for _ in range(min(length, bars - i)):
            open_ = price
            close = open_ + drift + float(rng.normal(0, vol))
            wick = abs(float(rng.normal(0, vol * 0.5)))
            high = max(open_, close) + wick
            low = min(open_, close) - wick
            out.append(
                Candle(
                    time=now - (bars - 1 - i) * step,
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
