"""Precision Swing Point - sweep plus rejection, timed against SSMT.

> NOT WIRED, BUT NO LONGER GUESSING. `in_same_candle` used to test the base
> symbol's absolute `psp.level` against another instrument's low, high and close,
> and `app/correlation.py` in this same repo documents why that cannot be done:
> one id is a different instrument per venue and the difference is not always
> basis - COPPER closes at 13968.59 on one feed and 6.44 on another.
>
> RESOLVED 27 AUGUST 2026 from the source, which had not been read when that note
> was written. `Referensi grup dan Bg Nas/Discord/Buku=Pegangan.txt` gives the
> rule and then gives an example, and the example is what settles it:
>
>     Harus di candle yang sama
>     Contoh ini menunjukkan ada PSP di antara tiga2 asset:
>     XAU - Bullish Candle
>     XAG - Bearish Candle
>     Platinum - Bullish Candle
>
> "The same candle" is the same BAR, and what is compared across the triad is the
> candle's SIGN, not its price - in his own example the three signs are not even
> equal, which is the crack. So the predicate is scale-free after all, and the
> price comparison was never what the doctrine asked for.


A PSP is an anticipatory structural point that appears after SSMT divergence
and purges liquidity. It is the "crack in correlation" - the exact moment
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
    lookback: int = 3,
) -> PSPEvent | None:
    """Detect a PSP within `lookback` bars after an SSMT event.

    `candles` are the chart's own bars.
    `ssmt_candle_idx` is the index of the candle that created the SSMT.
    `levels` are the key levels to check for sweep (PDH, PDL, session
    extremes, previous swing highs/lows, or the open of a candle N bars back -
    the caller supplies the level, this function never invents one).
    `lookback` is how many bars after the SSMT to search.

    A PSP is found when:
    1. Price sweeps BELOW a key level and closes BACK ABOVE it → buy PSP
    2. Price sweeps ABOVE a key level and closes BACK BELOW it → sell PSP

    The sweep must happen within `lookback` bars after the SSMT candle. The
    default is 3 - "the last 3 candles" - not the 10 this function shipped with,
    and the change is a doctrine reading rather than a measured one: the
    practitioner's rule names three candles, and no source publishes a longer
    window.
    """
    end = min(ssmt_candle_idx + lookback + 1, len(candles))
    for i in range(ssmt_candle_idx + 1, end):
        c = candles[i]
        for level in levels:
            # PRICE MUST ARRIVE FROM THE OTHER SIDE, and this is the project's
            # operationalisation of one word in the source rather than a quote.
            # The source says "Harus purge liquidity" and does not give the
            # geometry. A purge takes liquidity resting BEYOND a level, so the bar
            # has to start on the near side: without the `open` guard below, the
            # sell branch also fires on a bar that opened above the level and
            # closed under it, which is a plain break down and has purged nothing.
            # Found by a test whose fixture was written to be a non-event and was
            # reported as a PSP.
            #
            # Buy PSP: approaches from above, sweeps below, closes back above.
            if c.open >= level and c.low < level and c.close > level:
                return PSPEvent(
                    at=i,
                    level=level,
                    direction="buy",
                    ssmt_at=ssmt_candle_idx,
                    bars_after_ssmt=i - ssmt_candle_idx,
                )
            # Sell PSP: approaches from below, sweeps above, closes back below.
            if c.open <= level and c.high > level and c.close < level:
                return PSPEvent(
                    at=i,
                    level=level,
                    direction="sell",
                    ssmt_at=ssmt_candle_idx,
                    bars_after_ssmt=i - ssmt_candle_idx,
                )
    return None


def polarity(candle: Candle) -> int:
    """+1 bullish, -1 bearish, 0 for a candle with no side.

    A doji is 0 rather than being forced into one camp: it is the one candle that
    cannot disagree with anything, and counting it as agreement or as a crack
    would both be inventions.
    """
    if candle.close > candle.open:
        return 1
    if candle.close < candle.open:
        return -1
    return 0


def in_same_candle(
    psp: PSPEvent,
    base_candles: list[Candle],
    partner_candles: list[list[Candle]],
) -> bool:
    """Does the triad crack on the PSP's own bar?

    True when at least one partner prints the OPPOSITE sign to the base symbol at
    bar `psp.at`. That is the "crack in correlation" the source names: correlated
    instruments are supposed to agree, so a bar where one of them does not is the
    event.

    NO PRICE IS COMPARED, and that is deliberate. Comparing `psp.level` against a
    partner's low or close - which this function used to do - is meaningless
    across instruments: the same id is a different contract per venue, and
    `app/correlation.py` records a case two thousand times apart. Signs are
    comparable, prices are not.

    THE BAR INDEX IS ONLY MEANINGFUL ON AN ALIGNED GRID, and that is the caller's
    job, exactly as it is for `ssmt()`. Pass series from
    `aligned.load_aligned`, which trims every symbol to the shared timestamps. A
    partner shorter than the index is answered False rather than guessed at: a
    missing bar is not a disagreement.
    """
    i = psp.at
    if i < 0 or i >= len(base_candles):
        return False
    base = polarity(base_candles[i])
    if base == 0:
        return False
    for partner in partner_candles:
        if i >= len(partner):
            return False
        if polarity(partner[i]) == -base:
            return True
    return False
