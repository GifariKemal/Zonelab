"""PSP — Precision Swing Point detector.

A PSP is an anticipatory structural point that appears after SSMT divergence
and purges liquidity. It is the "crack in correlation" — the exact moment
where the triad confirms the direction.

The practitioner's definition:
  - Bukan swing point biasa
  - Harus purge liquidity
  - Muncul/terjadi beberapa candle sesudah SSMT
  - Harus di candle yang sama (across the triad)
  - Ini bisa kita ambil sebagai crack-in-correlation

A PSP is detected when, within a window after an SSMT event:
  1. Price sweeps a key level (previous high/low, PDH/PDL, session extreme)
  2. The sweep candle closes BACK inside the swept level (rejection)
  3. This happens in the SAME candle across the triad instruments

Routes:
  Route A (Model 3/4/5): SSMT → tCISD (no PSP needed)
  Route B (Late Entry): SSMT → tCISD → PSP → TOB (PSP required)
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Candle


@dataclass(frozen=True)
class PSPEvent:
    """One Precision Swing Point detection."""

    #: The bar index where the PSP occurred.
    at: int
    #: The price level that was swept and rejected.
    level: float
    #: The direction: 'buy' means price swept below and closed back above.
    direction: str  # 'buy' or 'sell'
    #: The SSMT event index that preceded this PSP.
    ssmt_at: int
    #: How many bars after the SSMT this PSP appeared.
    bars_after_ssmt: int


def detect(
    candles: list[Candle],
    ssmt_candle_idx: int,
    levels: list[float],
    lookback: int = 10,
) -> PSPEvent | None:
    """Detect a PSP within `lookback` bars after an SSMT event.

    `candles` are the chart's own bars.
    `ssmt_candle_idx` is the index of the candle that created the SSMT.
    `levels` are the key levels to check for sweep (PDH, PDL, session
    extremes, previous swing highs/lows).
    `lookback` is how many bars after the SSMT to search.

    A PSP is found when:
    1. Price sweeps BELOW a key level and closes BACK ABOVE it → buy PSP
    2. Price sweeps ABOVE a key level and closes BACK BELOW it → sell PSP

    The sweep must happen within `lookback` bars after the SSMT candle.
    """
    end = min(ssmt_candle_idx + lookback + 1, len(candles))
    for i in range(ssmt_candle_idx + 1, end):
        c = candles[i]
        for level in levels:
            # Buy PSP: price sweeps below level and closes back above
            if c.low < level and c.close > level:
                return PSPEvent(
                    at=i,
                    level=level,
                    direction="buy",
                    ssmt_at=ssmt_candle_idx,
                    bars_after_ssmt=i - ssmt_candle_idx,
                )
            # Sell PSP: price sweeps above level and closes back below
            if c.high > level and c.close < level:
                return PSPEvent(
                    at=i,
                    level=level,
                    direction="sell",
                    ssmt_at=ssmt_candle_idx,
                    bars_after_ssmt=i - ssmt_candle_idx,
                )
    return None


def in_same_candle(
    psp: PSPEvent,
    partner_candles: list[list[Candle]],
    level_tolerance: float = 0.001,
) -> bool:
    """Check if the PSP occurs in the SAME candle across the triad.

    The practitioner's rule: "Harus di candle yang sama" — the PSP must
    be visible across all three instruments at the same bar index.

    `partner_candles` are the aligned candle lists for the other instruments
    in the triad. All lists must have the same length (aligned grid).

    `level_tolerance` is the relative tolerance for price level matching.
    """
    idx = psp.at
    for partner in partner_candles:
        if idx >= len(partner):
            return False
        c = partner[idx]
        if psp.direction == "buy":
            if not (c.low < psp.level * (1 - level_tolerance) and c.close > psp.level * (1 + level_tolerance)):
                return False
        else:
            if not (c.high > psp.level * (1 + level_tolerance) and c.close < psp.level * (1 - level_tolerance)):
                return False
    return True