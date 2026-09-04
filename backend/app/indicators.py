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


def wilder_adx(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
) -> np.ndarray:
    """Wilder's ADX, same definition MetaTrader uses.

    Returns values 0-100. Warmup bars backfilled like `wilder_atr`.
    """
    n = len(close)
    adx = np.zeros(n, dtype=np.float64)
    if n < period + 1:
        return adx

    prev_high = np.concatenate(([high[0]], high[:-1]))
    prev_low = np.concatenate(([low[0]], low[:-1]))
    up = high - prev_high
    down = prev_low - low
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = true_range(high, low, close)

    def _smooth(arr: np.ndarray) -> np.ndarray:
        out = np.empty(n, dtype=np.float64)
        seed = arr[:period].sum()
        out[:period] = seed
        prev = seed
        for i in range(period, n):
            prev = prev - prev / period + arr[i]
            out[i] = prev
        return out

    s_tr = _smooth(tr)
    s_plus = _smooth(plus_dm)
    s_minus = _smooth(minus_dm)

    plus_di = np.where(s_tr > 0, s_plus / s_tr * 100, 0.0)
    minus_di = np.where(s_tr > 0, s_minus / s_tr * 100, 0.0)
    di_sum = plus_di + minus_di
    dx = np.where(di_sum > 0, np.abs(plus_di - minus_di) / di_sum * 100, 0.0)

    # ADX = Wilder smooth of DX, starting after first `period` DX values
    start = 2 * period - 1
    if start >= n:
        return adx
    seed = dx[period:start + 1].mean()
    adx[:start + 1] = seed
    prev_adx = seed
    for i in range(start + 1, n):
        prev_adx = (prev_adx * (period - 1) + dx[i]) / period
        adx[i] = prev_adx
    return adx


def bb_width(
    close: np.ndarray, period: int = 20, mult: float = 2.0
) -> np.ndarray:
    """Bollinger Band Width: (upper - lower) / middle.

    Warmup bars backfilled with the first full value.
    """
    n = len(close)
    width = np.zeros(n, dtype=np.float64)
    if n < period:
        return width
    for i in range(period - 1, n):
        window = close[i - period + 1 : i + 1]
        mid = window.mean()
        if mid <= 0:
            continue
        std = window.std(ddof=0)
        width[i] = (2 * mult * std) / mid
    width[:period - 1] = width[period - 1]
    return width


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


def vwap(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    anchor_idx: int = 0,
) -> np.ndarray:
    """Volume-Weighted Average Price from anchor_idx forward.

    Typical price = (H+L+C)/3, weighted by tick volume.
    Returns array same length as input, NaN before anchor.

    WARNING: MT5 tick volume is the number of ticks per bar, not real exchange
    volume. The VWAP computed from it is an approximation whose accuracy
    depends on the instrument and session.
    """
    n = len(close)
    out = np.full(n, np.nan, dtype=np.float64)
    if n == 0 or anchor_idx >= n:
        return out
    anchor_idx = max(anchor_idx, 0)
    tp = (high[anchor_idx:] + low[anchor_idx:] + close[anchor_idx:]) / 3.0
    vol = volume[anchor_idx:]
    cum_vol = np.cumsum(vol)
    cum_tpv = np.cumsum(tp * vol)
    # ponytail: EPS guards zero-volume stretches without masking
    out[anchor_idx:] = cum_tpv / np.maximum(cum_vol, EPS)
    return out


def volume_profile(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    bins: int = 24,
) -> dict:
    """Fixed-range volume profile over the given bars.

    Distributes each bar's tick volume across the price bins its range covers.
    Returns dict with poc, vah, val and the bin histogram.

    Same tick-volume caveat as `vwap` above.
    """
    n = len(close)
    if n == 0 or bins < 1:
        return {"poc": 0.0, "vah": 0.0, "val": 0.0, "bins": []}

    lo = float(low.min())
    hi = float(high.max())
    if hi - lo < EPS:
        tp = float((high[0] + low[0] + close[0]) / 3.0)
        total_vol = float(volume.sum())
        return {
            "poc": tp, "vah": tp, "val": tp,
            "bins": [{"price": tp, "volume": total_vol}],
        }

    edges = np.linspace(lo, hi, bins + 1)
    centres = (edges[:-1] + edges[1:]) / 2.0
    accum = np.zeros(bins, dtype=np.float64)

    # ponytail: O(n*bins) via searchsorted, n<=50k and bins<=100
    for i in range(n):
        bar_lo, bar_hi, bar_vol = low[i], high[i], volume[i]
        if bar_vol <= 0:
            continue
        first = int(np.searchsorted(edges[1:], bar_lo, side="left"))
        last = int(np.searchsorted(edges[:-1], bar_hi, side="right")) - 1
        first = max(first, 0)
        last = min(last, bins - 1)
        if first > last:
            first = last
        span = last - first + 1
        accum[first : last + 1] += bar_vol / span

    poc_idx = int(accum.argmax())
    poc = float(centres[poc_idx])

    total = accum.sum()
    if total < EPS:
        return {
            "poc": poc, "vah": poc, "val": poc,
            "bins": [{"price": float(c), "volume": float(v)} for c, v in zip(centres, accum)],
        }

    # Value area: expand outward from POC until 70% of volume covered
    target = total * 0.70
    area_vol = accum[poc_idx]
    lo_idx, hi_idx = poc_idx, poc_idx
    while area_vol < target and (lo_idx > 0 or hi_idx < bins - 1):
        add_lo = accum[lo_idx - 1] if lo_idx > 0 else -1.0
        add_hi = accum[hi_idx + 1] if hi_idx < bins - 1 else -1.0
        if add_lo >= add_hi:
            lo_idx -= 1
            area_vol += accum[lo_idx]
        else:
            hi_idx += 1
            area_vol += accum[hi_idx]

    return {
        "poc": poc,
        "vah": float(centres[hi_idx]),
        "val": float(centres[lo_idx]),
        "bins": [{"price": float(c), "volume": float(v)} for c, v in zip(centres, accum)],
    }


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
