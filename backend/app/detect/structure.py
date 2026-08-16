"""Market structure: swing points, breaks, and a directional bias.

The first object in this project that claims to say WHICH WAY rather than WHERE.

Everything measured here so far - supply and demand zones, fair value gaps,
order blocks - marks a location. All three beat a placebo control by 10 to 25
points and survive walk-forward, and none of them carries direction: four
pre-registered directional hypotheses, four nulls. The doctrine itself says why.
ICT and SMC put directional bias in market STRUCTURE and use zones only to
refine the entry. Structure decides which way; a zone decides where.

So this module exists to be measured, not to be believed.

THE ONE THING THAT MAKES OR BREAKS IT
A swing high at bar `i` is not knowable at bar `i`. It is knowable at bar
`i + LEFT`, once enough bars have printed to its right to confirm nothing
exceeded it. A detector that reacts to a swing the moment it forms is reading
bars that had not happened yet, and it would show a beautiful directional edge
made entirely of hindsight.

Every swing here therefore carries `confirmed_at`, and every break is tested
only against swings whose `confirmed_at` is at or before the breaking bar. That
single rule is the difference between a measurement and a fiction, and it is
asserted in the tests rather than trusted.

BREAK, NOT SWEEP
A break requires a bar to CLOSE beyond the swing. A wick through that closes
back inside is a sweep, which in most codifications is the opposite signal - it
is liquidity being taken, not structure giving way. Using the wick would merge
the two into one event and guarantee the detector cannot tell them apart.

BOS AND CHoCH
Both are closes beyond a confirmed swing. The difference is only which way the
bias was already pointing:

    bias      break beyond        name    means
    bullish   last swing HIGH     BOS     the trend continued
    bullish   last swing LOW      CHoCH   the trend may have turned
    bearish   last swing LOW      BOS     the trend continued
    bearish   last swing HIGH     CHoCH   the trend may have turned

Before any break has happened the bias is `none`, and the first break in either
direction sets it. Calling that first break a CHoCH would claim a character
changed from a character that was never established.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..models import Candle


@dataclass(frozen=True)
class Swing:
    """A pivot, and the bar at which it became knowable."""

    index: int
    price: float
    high: bool
    confirmed_at: int


@dataclass(frozen=True)
class Break:
    """A close beyond a confirmed swing."""

    index: int  # the bar that closed beyond
    time: int
    kind: str  # "BOS" or "CHoCH"
    direction: int  # +1 broke upward, -1 broke downward
    level: float  # the swing price that gave way
    swing_index: int  # which bar made that swing
    bias_before: int  # -1, 0 or +1


def swings(
    high: np.ndarray, low: np.ndarray, left: int, right: int
) -> list[Swing]:
    """Fractal pivots, each stamped with the bar it became knowable on.

    `left` bars must be lower (higher) on one side and `right` on the other. The
    two are separate because they do different jobs: `left` is how much history
    a pivot has to dominate, `right` is how long you must WAIT before you are
    allowed to know about it. Collapsing them into one number hides the second.

    Ties are broken by requiring a strict maximum on the left and a
    non-exceedance on the right. A flat top would otherwise register a pivot on
    every bar of the plateau.
    """
    out: list[Swing] = []
    n = len(high)
    for i in range(left, n - right):
        window_l = slice(i - left, i)
        window_r = slice(i + 1, i + 1 + right)
        if high[i] > high[window_l].max() and high[i] >= high[window_r].max():
            out.append(Swing(i, float(high[i]), True, i + right))
        if low[i] < low[window_l].min() and low[i] <= low[window_r].min():
            out.append(Swing(i, float(low[i]), False, i + right))
    return sorted(out, key=lambda s: (s.confirmed_at, s.index))


def breaks(
    candles: list[Candle], left: int = 2, right: int = 2
) -> tuple[list[Break], list[Swing]]:
    """Walk the bars once, emitting a break each time one closes beyond a swing.

    The loop is deliberately a single forward pass with no lookahead of any
    kind: at bar `i` it may only see swings already confirmed at `i`, and it
    tests only the CLOSE of bar `i`. Anything else would let a break know how
    the bar it broke on ended up.
    """
    if len(candles) < left + right + 2:
        return [], []

    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    times = [c.time for c in candles]

    found = swings(high, low, left, right)
    by_confirm: dict[int, list[Swing]] = {}
    for swing in found:
        by_confirm.setdefault(swing.confirmed_at, []).append(swing)

    # The most recent CONFIRMED swing on each side, and the level each one put
    # in the way. They are replaced as new swings confirm and cleared when
    # broken, so a level can only be broken once.
    live_high: Swing | None = None
    live_low: Swing | None = None
    bias = 0
    out: list[Break] = []

    for i in range(len(candles)):
        for swing in by_confirm.get(i, ()):
            if swing.high:
                live_high = swing
            else:
                live_low = swing

        # A close beyond, never a wick. A wick through that closes back inside
        # is a SWEEP - liquidity taken - and calling it a break would merge two
        # opposite events into one name. Sweeps are emitted rather than silently
        # skipped: it is the only object in this doctrine with a peer-reviewed
        # mechanism behind it (stop orders clustering just beyond a level), and
        # a detector that drops them cannot ever be asked about them.
        #
        # Up is evaluated before down, so an outside bar that closes beyond BOTH
        # levels emits both and ends bearish. No source addresses that case; the
        # order is a stated choice, and both events are kept rather than one
        # being swallowed by an `elif`.
        if live_high is not None:
            if close[i] > live_high.price:
                kind = "BOS" if bias >= 0 else "CHoCH"
                out.append(
                    Break(i, times[i], kind, 1, live_high.price, live_high.index, bias)
                )
                bias = 1
                live_high = None
            elif high[i] > live_high.price:
                out.append(
                    Break(i, times[i], "SWEEP", 1, live_high.price,
                          live_high.index, bias)
                )
                # The level stays armed and unchanged. Raising it to the sweep
                # wick would change every break downstream, and doctrine is
                # silent on which is right.

        if live_low is not None:
            if close[i] < live_low.price:
                kind = "BOS" if bias <= 0 else "CHoCH"
                out.append(
                    Break(i, times[i], kind, -1, live_low.price, live_low.index, bias)
                )
                bias = -1
                live_low = None
            elif low[i] < live_low.price:
                out.append(
                    Break(i, times[i], "SWEEP", -1, live_low.price,
                          live_low.index, bias)
                )

    return out, found


def bias_series(candles: list[Candle], left: int = 2, right: int = 2) -> np.ndarray:
    """Directional bias at every bar, as -1, 0 or +1.

    Zero until the first break, because before that there is nothing to have a
    character, let alone to change it. The value at bar `i` uses only breaks
    that had already happened at `i`, so it is safe to read forward returns from
    it without leaking.
    """
    events, _ = breaks(candles, left, right)
    out = np.zeros(len(candles), dtype=np.int8)
    at = 0
    cursor = 0
    for i in range(len(candles)):
        while cursor < len(events) and events[cursor].index <= i:
            # A sweep is liquidity being taken, not structure giving way, so it
            # must not move the bias. Reading `direction` off every event
            # regardless of kind would let a wick flip the trend.
            if events[cursor].kind != "SWEEP":
                at = events[cursor].direction
            cursor += 1
        out[i] = at
    return out
