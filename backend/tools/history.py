"""Paged historical download with an on-disk cache.

Calibration needs tens of thousands of bars and needs the same bars on every
re-run, otherwise "the score improved" cannot be told apart from "the window
moved". Binance caps a klines call at 1000 rows, so this pages backwards from
now and caches the result as .npz.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import numpy as np

from app.models import Candle
from app.providers.base import INTERVALS

CACHE = Path(__file__).resolve().parent.parent / ".cache"
PAGE = 1000  # vendor hard cap


def load(symbol: str, interval: str, bars: int, refresh: bool = False) -> list[Candle]:
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
