"""tCISD Entry Trigger — mathematical precision entry mechanics.

The practitioner's rule, as taught in POSKO 618:

1. Identify the first candle creating the SSMT. Ensure it closes in the
   setup direction (bullish SSMT → bearish candle, bearish SSMT → bullish).
2. Extract the OPEN price of this candle → tCISD_Level.
3. Wait for a subsequent candle to close completely THROUGH tCISD_Level.
4. Place a Limit Order at tCISD_Level for the retest. Execution REQUIRES
   a small rejection wick upon touching the level.
5. Set Stop Loss exactly at the SSMT invalidation extreme (the sweep
   low/high).

This replaces the generic "entry at zone proximal" logic with a specific
SSMT → tCISD → retest sequence. The tCISD level is the most important
price on the chart — it is the level where the algorithm proved it could
reverse the move.

WHAT THIS IS NOT. It is not a detector. It is an entry RULE that takes
an SSMT event and candles, and returns whether a tCISD entry exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Candle


@dataclass(frozen=True)
class TCISDEntry:
    """A valid tCISD entry, if one exists."""

    #: The OPEN price of the candle that created the SSMT.
    level: float
    #: The bar index of the tCISD candle.
    candle_at: int
    #: The bar index where price closed through tCISD.
    broken_at: int
    #: The stop loss — the SSMT invalidation extreme.
    stop: float
    #: Direction: 'buy' means the tCISD is above current price (retest long).
    direction: str  # 'buy' or 'sell'


def find(
    candles: list[Candle],
    ssmt_candle_idx: int,
    ssmt_side: str,  # 'high' or 'low'
    sweep_extreme: float,
) -> TCISDEntry | None:
    """Find a tCISD entry from an SSMT event.

    `candles` are the chart's own bars, in time order.
    `ssmt_candle_idx` is the index of the candle that created the SSMT
    (the one that took the previous quarter's extreme).
    `ssmt_side` is 'high' for bullish SSMT, 'low' for bearish.
    `sweep_extreme` is the extreme that was swept — the stop loss level.

    Returns a TCISDEntry if the full sequence is found, or None if the
    tCISD sequence is incomplete or invalid.
    """
    if ssmt_candle_idx < 0 or ssmt_candle_idx >= len(candles):
        return None

    ssmt_candle = candles[ssmt_candle_idx]
    if ssmt_candle.open <= 0:
        return None

    # Step 1: Extract tCISD level = OPEN of the SSMT candle
    tcisd_level = ssmt_candle.open

    # Step 2: Validate candle direction
    # Bullish SSMT (side=high) → candle must be bearish (close < open)
    # Bearish SSMT (side=low) → candle must be bullish (close > open)
    if ssmt_side == "high":
        if ssmt_candle.close >= ssmt_candle.open:
            return None  # candle not bearish
        direction = "buy"
    else:
        if ssmt_candle.close <= ssmt_candle.open:
            return None  # candle not bullish
        direction = "sell"

    # Step 3: Wait for a subsequent candle to close THROUGH tCISD
    broken_at = None
    for i in range(ssmt_candle_idx + 1, len(candles)):
        c = candles[i]
        if direction == "buy":
            if c.close > tcisd_level:
                broken_at = i
                break
        else:
            if c.close < tcisd_level:
                broken_at = i
                break

    if broken_at is None:
        return None  # tCISD never broken

    # Step 4: Check for retest — price must come back to tCISD with a
    # rejection wick. The wick is the proof that the level is respected.
    for i in range(broken_at + 1, len(candles)):
        c = candles[i]
        if direction == "buy":
            # Price dips to tCISD and rejects (low touches, close stays above)
            if c.low <= tcisd_level and c.close > tcisd_level:
                return TCISDEntry(
                    level=tcisd_level,
                    candle_at=ssmt_candle_idx,
                    broken_at=broken_at,
                    stop=sweep_extreme,
                    direction=direction,
                )
        else:
            # Price rallies to tCISD and rejects (high touches, close stays below)
            if c.high >= tcisd_level and c.close < tcisd_level:
                return TCISDEntry(
                    level=tcisd_level,
                    candle_at=ssmt_candle_idx,
                    broken_at=broken_at,
                    stop=sweep_extreme,
                    direction=direction,
                )

    return None  # no retest found


def placeable(entry: TCISDEntry, current_price: float) -> bool:
    """Whether the tCISD entry is still placeable at the current price.

    A buy entry is placeable if the current price is above the tCISD
    level (so a limit order would be below market). A sell entry is
    placeable if the current price is below.
    """
    if entry.direction == "buy":
        return current_price > entry.level
    return current_price < entry.level