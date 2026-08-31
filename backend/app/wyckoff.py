"""Wyckoff phase readings over a rolling trading range.

This is the DETERMINABLE subset of the Wyckoff schematic, stated in the spec at
`docs/superpowers/specs/2026-08-31-wyckoff-design.md`. The full schematic has
phases that need volume or discretion (Selling Climax, Secondary Test, Last
Point of Support); those are left out rather than guessed, because this project
refuses to invent a rule a source never published. What survives is what OHLC
can actually say:

  - a TRADING RANGE (TR): the high and low of the preceding window;
  - a SPRING: a sweep below the TR low that closes back inside it;
  - an UPTHRUST: a sweep above the TR high that closes back inside;
  - a SIGN OF STRENGTH (SOS): a close above the TR high;
  - a SIGN OF WEAKNESS (SOW): a close below the TR low.

All five are geometry on bars, classified no-lookahead from the bars that
precede the event. Nothing here has been measured against outcomes, and the
structure primitives these map onto (sweep, break) are already measured null in
H6 and H9 - so this is a reading, never a bias.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import Candle

Kind = Literal["spring", "upthrust", "sos", "sow"]


@dataclass(frozen=True)
class WyckoffPhase:
    """One phase event against a rolling trading range."""

    kind: Kind
    at: int            # index of the event bar
    level: float       # the TR edge swept or broken
    tr_low: float
    tr_high: float

    @property
    def knowable_at(self) -> int:
        return self.at


def _range(candles: list[Candle], i: int, lookback: int) -> tuple[float, float]:
    """The trading range high/low of the `lookback` bars ending before bar `i`."""
    window = candles[i - lookback:i]
    return max(c.high for c in window), min(c.low for c in window)


def phases(candles: list[Candle], lookback: int = 20) -> list[WyckoffPhase]:
    """Spring, upthrust, sign-of-strength and sign-of-weakness events.

    For each bar after the warm-up, the trading range is the high/low of the
    `lookback` bars before it, and the current bar is read against that range.
    A sweep that rejects is a spring/upthrust; a close through the edge is a
    SOS/SOW. A bar can carry at most one phase: a rejected sweep is checked
    first, because a close back inside the range is not a break of it.
    """
    out: list[WyckoffPhase] = []
    for i in range(lookback, len(candles)):
        tr_high, tr_low = _range(candles, i, lookback)
        cur = candles[i]
        # Sweep + rejection: the bar's wick crosses the edge and the close is
        # back inside. This is the same operationalisation of "purge" as
        # `app/psp.py`: the bar must have arrived from the near side.
        if cur.open >= tr_low and cur.low < tr_low and cur.close > tr_low:
            out.append(WyckoffPhase("spring", i, tr_low, tr_low, tr_high))
            continue
        if cur.open <= tr_high and cur.high > tr_high and cur.close < tr_high:
            out.append(WyckoffPhase("upthrust", i, tr_high, tr_low, tr_high))
            continue
        # A clean break of the edge.
        if cur.close > tr_high:
            out.append(WyckoffPhase("sos", i, tr_high, tr_low, tr_high))
        elif cur.close < tr_low:
            out.append(WyckoffPhase("sow", i, tr_low, tr_low, tr_high))
    return out
