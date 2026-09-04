"""Triad families and Truth Asset detection for POSKO 618.

A triad is three correlated instruments read together. The framework teaches
that among a triad, the asset that is CONSOLIDATING while the others are choppy
shows the real premium and discount - the "Truth Asset."

Four named triads, each with a base symbol (the chart's own) and two partners
that are compared against it. The base is always the first entry; the caller
substitutes the chart's own symbol, so the Monetary triad works with any base
that belongs to it.

TRUTH ASSET COMPUTATION. For each symbol in the triad, compute a consolidation
score: the ratio of the recent range to the recent ATR, both over the same
lookback. A low ratio means the asset is ranging tightly relative to its own
volatility - it is consolidating. The asset with the lowest score is the Truth
Asset.

A TRUTH ASSET IS NOT A DIRECTION. It is a statement about which price action
is clearer, and twelve pre-registered directional hypotheses have failed in this
project. The panel reports the asset and its score; nothing here picks a side.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .correlation import correlations
from .indicators import wilder_atr
from .models import Candle

#: Bars over which the consolidation score is measured. Twenty, because it is
#: long enough to contain a swing and short enough to move when the regime
#: changes. Not fitted - stated as a choice.
CONSOLIDATION_LOOKBACK = 20

#: Four named triads. The first entry is the BASE - the chart's own symbol is
#: substituted in by the caller, so the triad works with any asset that belongs
#: to it. The two partners are fetched and compared against the base.
#:
#: The pairs are chosen from the measured correlation table in
#: docs/QA-PRODUKSI.md section 4: each partner has a known relationship to gold
#: and to each other, so the triad is not three random instruments.
TRIAD_FAMILIES: dict[str, tuple[str, str, str]] = {
    "monetary": ("XAUUSD", "DXY", "EURUSD"),
    "commodity": ("XAUUSD", "WTI", "XAGUSD"),
    "risk": ("XAUUSD", "NAS100", "US30"),
    "fx": ("XAUUSD", "USDJPY", "XPTUSD"),
    "bonds": ("XAUUSD", "US10Y", "US30Y"),
    "energy": ("XAUUSD", "WTI", "BRENT"),
}


@dataclass(frozen=True)
class TruthAsset:
    """Which asset in a triad is consolidating, and by how much."""

    #: The symbol that is consolidating - the one with the lowest score.
    symbol: str
    #: Consolidation score for each symbol in the triad. Lower = more
    #: consolidated, so the entry with the minimum value IS the truth asset.
    scores: dict[str, float]
    #: The base symbol the triad was read against.
    base: str
    #: The triad key that produced this reading.
    triad: str


def _consolidation_score(candles: list[Candle]) -> float | None:
    """How tightly this asset is ranging, relative to its own volatility.

    Returns None when the series is too short to measure. A short series is
    not an error - it is a fact about the feed - and the caller handles it.
    """
    if len(candles) < CONSOLIDATION_LOOKBACK + 2:
        return None
    recent = candles[-CONSOLIDATION_LOOKBACK:]
    high = np.array([c.high for c in recent], dtype=np.float64)
    low = np.array([c.low for c in recent], dtype=np.float64)
    close = np.array([c.close for c in recent], dtype=np.float64)
    atr = wilder_atr(high, low, close, CONSOLIDATION_LOOKBACK)
    if atr[-1] <= 0:
        return None
    price_range = float(np.max(high) - np.min(low))
    return price_range / float(atr[-1])


def truth_asset(
    series: dict[str, list[Candle]],
    base: str,
    triad_key: str,
) -> TruthAsset | None:
    """Which asset in the triad is consolidating, if any can be measured.

    `series` is what `aligned.load_aligned` returns: one entry per symbol, all
    on the same grid. Nothing is fetched here - the caller aligns the bars.

    Returns None when every symbol in the triad is unmeasurable. A single
    unmeasurable partner is dropped from the scores but does not cancel the
    reading.

    Ties are broken by the partner with the highest absolute correlation to
    the base, because the framework teaches that the consolidating asset should
    be the one most closely tied to the anchor.
    """
    scores: dict[str, float] = {}
    for symbol, candles in series.items():
        score = _consolidation_score(candles)
        if score is not None:
            scores[symbol] = score
    if not scores:
        return None

    # Lowest score first, and on a tie the higher absolute correlation wins.
    corr = {c.symbol: abs(c.full or 0.0) for c in correlations(series, base)}
    ranked = sorted(scores, key=lambda s: (scores[s], -corr.get(s, 0.0)))
    return TruthAsset(
        symbol=ranked[0],
        scores={s: round(v, 3) for s, v in scores.items()},
        base=base,
        triad=triad_key,
    )