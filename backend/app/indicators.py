"""Numeric primitives the detectors share.

Kept deliberately small and dependency-free (numpy only) so every number a zone
reports can be traced to a few lines of arithmetic.
"""

from __future__ import annotations

import numpy as np

# Guards a division when a bar has high == low (a real thing on illiquid ticks).
EPS = 1e-12


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev_close = np.concatenate(([close[0]], close[:-1]))
    return np.maximum.reduce(
        [high - low, np.abs(high - prev_close), np.abs(low - prev_close)]
    )


def wilder_atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
) -> np.ndarray:
    """Wilder's ATR (RMA of true range), same definition MetaTrader and
    TradingView use, so zone sizes match what the user sees elsewhere.

    Warmup bars are backfilled with the first full average rather than NaN: a
    NaN ATR would silently disable every threshold that divides by it.
    """
    n = len(close)
    tr = true_range(high, low, close)
    atr = np.empty(n, dtype=np.float64)

    if n == 0:
        return atr
    if n <= period:
        atr[:] = tr.mean()
        return atr

    seed = tr[:period].mean()
    atr[:period] = seed
    prev = seed
    for i in range(period, n):
        prev = (prev * (period - 1) + tr[i]) / period
        atr[i] = prev
    return atr


def flat_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int,
    at: int,
) -> float | None:
    """Mean true range over the `period` bars ending at `at`, or None.

    A SECOND volatility figure in a file whose whole point is one definition, and
    it exists for the one job `wilder_atr` cannot do: this value is a function of
    `period` bars and nothing else, so it does not move when the window's left
    edge does.

    Wilder's is an RMA and therefore has infinite memory - its value at any bar
    still carries the seed taken from the window's first `period` bars. For a
    THRESHOLD that is harmless, which is why every gate in this project keeps
    using it and must keep using it. For a PRICE it is not: `supply_demand` and
    `refine` grow a too-short base up to `zone_min_atr * atr`, and a drawn edge
    computed that way moves when the reader loads more history.

    MEASURED, 2026-08-21. The same projected 1d supply zone reported a bottom of
    3518.24852106 with 312 daily buckets behind it and 3518.24600835 with 165,
    because Wilder read 17.71318025 against 17.75984495 at the same bar. At
    bucket 34 the seed still carries (13/14)^20 = 0.23 of the weight. For a
    supply zone the bottom is the PROXIMAL, which is where an order goes.

    Returns None when the bars are not all present. The caller must then grow
    nothing: no floor is stable at the very left edge of a window, and a raw bar
    extreme always is.

    Reads one bar EARLIER than `period` on purpose. `true_range` has to invent a
    previous close for its first element, so that element is a function of where
    the slice starts; taking one extra bar and dropping it leaves every remaining
    true range computed from two real bars.
    """
    lo = at - period + 1
    if period <= 0 or lo < 1 or at >= len(close) or at < 0:
        return None
    tr = true_range(high[lo - 1 : at + 1], low[lo - 1 : at + 1], close[lo - 1 : at + 1])
    return float(tr[1:].mean())


def classify_candles(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    body_ratio_min: float,
    range_atr_min: float,
) -> np.ndarray:
    """Label every bar +1 (exciting up), -1 (exciting down) or 0 (base).

    A bar is *exciting* when its body dominates its own range AND that range is
    large against ATR. Two conditions, not one: the body ratio alone would
    promote a tiny decisive candle inside a consolidation, and the ATR test
    alone would promote a huge doji that resolved nothing.

    The ATR is lagged one bar on purpose. Wilder's ATR at bar i already contains
    bar i's own true range, so testing `range[i] >= m * atr[i]` lets a bar raise
    the very bar it is judged against - the effect is worst for exactly the
    violent candles the test exists to catch. Comparing against the volatility
    that prevailed *before* the bar removes the self-reference.

    Everything that is not exciting is base. Making this a strict partition
    matters: a third "neutral" label would leave gaps between runs that the
    pattern scan would have to guess about.
    """
    rng = np.maximum(high - low, EPS)
    body = close - open_
    body_ratio = np.abs(body) / rng
    prior_atr = np.concatenate(([atr[0]], atr[:-1])) if len(atr) else atr

    exciting = (body_ratio >= body_ratio_min) & (rng >= range_atr_min * prior_atr)
    return np.where(exciting, np.sign(body), 0).astype(np.int8)


def runs(labels: np.ndarray) -> list[tuple[int, int, int]]:
    """Compress a label array into consecutive runs of (label, start, end).

    `end` is inclusive. An empty input yields an empty list.
    """
    n = len(labels)
    if n == 0:
        return []

    out: list[tuple[int, int, int]] = []
    start = 0
    for i in range(1, n):
        if labels[i] != labels[start]:
            out.append((int(labels[start]), start, i - 1))
            start = i
    out.append((int(labels[start]), start, n - 1))
    return out
