"""How correlated the SSMT partner actually is, measured rather than assumed.

WHY THIS EXISTS. The cross-instrument read is the one thing in this engine that
needs a second symbol, and until now nothing measured whether the second symbol
was a sensible choice. `ssmt.py`'s own docstring says its hit rate "tracks
correlation exactly" - gold against silver diverges on 14.9% of readings and
against DXY on 59.5% - and the only thing standing between a reader and a
meaningless pairing was a hardcoded list of three tickers in the toolbox. A
number belongs there instead.

WHAT IS MEASURED, precisely, because a correlation figure is easy to compute
wrongly:

  - LOG RETURNS, not prices. Two trending series correlate at 0.9 for no reason
    other than both trending, and a price correlation between gold and the Nasdaq
    over a bull run says nothing about whether they move together bar to bar.
  - ON THE ALIGNED GRID. `aligned.load_aligned` returns the strict intersection
    of bar times with no fill and no interpolation, so both return series are
    computed from bars that genuinely happened at the same instants. A correlation
    over forward-filled holes is a correlation with invented data in it.
  - PEARSON, and it is stated rather than implied. Spearman would be defensible
    and would answer a different question; nothing here has measured which
    predicts the divergence rate better, so one is chosen and named.

WHAT IS NOT CLAIMED. This says nothing about direction, nothing about whether a
divergence will resolve, and nothing about whether a pair is "good". It is a
description of the window it was measured on. In particular:

  - A high correlation does not make a divergence meaningful; it makes one RARE,
    which is a different statement.
  - The sign is reported, not judged. An inversely correlated instrument is not
    invalid - it is a pairing whose divergences have to be read the other way
    round, and the reader is the one who knows that.

TWO WINDOWS, and this is the part a single number hides. Correlation is not a
property of a pair, it is a property of a pair over a period: metals decouple,
the dollar's grip loosens and tightens. So the full window and its most recent
quarter are both reported. When they disagree, that disagreement is the finding.

SCALE DOES NOT MATTER HERE and one measurement proves why it must not: this
broker quotes copper at 13968.59 while Yahoo quotes the same metal at 6.44, a
factor of two thousand, because they are different units and not a basis. A
returns correlation is invariant to that; anything comparing prices across venues
would be nonsense. `aligned.py` is fed ONE provider for exactly this reason.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import Candle

#: Fewest paired returns worth reporting a coefficient from.
#:
#: Pearson on a handful of points is noise that looks like a measurement: with 10
#: observations an r of 0.6 is not distinguishable from zero at any conventional
#: threshold. `aligned.load_aligned` already refuses a grid below 50 bars, so this
#: floor bites only on the recent sub-window, which is where it matters most - a
#: reader must not be shown a decoupling that is four bars of noise.
MIN_PAIRS = 30

#: What fraction of the window counts as "recent" for the second reading.
#:
#: A quarter, which is a CHOICE and not a citation. It is long enough to clear
#: `MIN_PAIRS` on any window `load_aligned` accepts and short enough to move when
#: a relationship changes. Nothing here has measured which fraction detects a
#: decoupling soonest.
RECENT_FRACTION = 0.25


@dataclass(frozen=True)
class Correlation:
    """One partner's relationship to the base symbol over one aligned window."""

    symbol: str
    #: Pearson r on log returns over the whole aligned window. None below MIN_PAIRS.
    full: float | None
    #: The same, over the most recent `RECENT_FRACTION` of it.
    recent: float | None
    #: Paired returns behind `full`, so a reader can weigh it.
    pairs: int
    recent_pairs: int
    #: The window the numbers describe, as bar open times.
    time_from: int
    time_to: int
    #: True when the two readings fall on opposite sides of zero. Not a verdict -
    #: a flag that the single number would have been misleading.
    sign_changed: bool


def _log_returns(candles: list[Candle]) -> np.ndarray:
    close = np.array([c.close for c in candles], dtype=np.float64)
    # A non-positive close cannot be logged. It does not occur on any instrument
    # here, and returning an empty array rather than a nan-filled one keeps the
    # failure visible as "not measured" instead of poisoning the coefficient.
    if close.size < 2 or np.any(close <= 0):
        return np.empty(0, dtype=np.float64)
    return np.diff(np.log(close))


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    """Pearson r, or None where it is not defined.

    `np.corrcoef` returns nan for a constant series rather than raising, and a nan
    serialised onto the wire is not valid JSON - it reaches the browser as a
    parse error, which is a worse failure than an absent field. A flat series is
    also a real case: an index outside its session prints identical closes.
    """
    if a.size < MIN_PAIRS or a.size != b.size:
        return None
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        return None
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    r = float(np.corrcoef(a, b)[0, 1])
    return r if np.isfinite(r) else None


def correlations(series: dict[str, list[Candle]], base: str) -> list[Correlation]:
    """Every partner in `series` against `base`, on the grid they arrived on.

    `series` is what `aligned.load_aligned` returns: one entry per symbol, all on
    the same bar times. Nothing is fetched here and nothing is re-aligned - this
    reads the bars it is handed, so it cannot disagree with the divergences
    computed from the same dict.

    Ordered by the absolute value of the full-window coefficient, strongest
    relationship first, because that is the order a reader chooses a partner in.
    Partners with no coefficient sort last rather than being dropped: "not
    measurable on this window" is an answer.
    """
    anchor = series.get(base)
    if not anchor or len(anchor) < 2:
        return []

    base_returns = _log_returns(anchor)
    cut = max(MIN_PAIRS, int(base_returns.size * RECENT_FRACTION))
    out: list[Correlation] = []

    for symbol, candles in series.items():
        if symbol == base:
            continue
        partner = _log_returns(candles)
        # The grid guarantees equal length; a mismatch means the caller did not
        # come through `load_aligned`, and truncating to the shorter series would
        # silently pair bar 100 of one instrument with bar 100 of another that
        # started a week later.
        if partner.size != base_returns.size:
            out.append(
                Correlation(
                    symbol=symbol,
                    full=None,
                    recent=None,
                    pairs=0,
                    recent_pairs=0,
                    time_from=anchor[0].time,
                    time_to=anchor[-1].time,
                    sign_changed=False,
                )
            )
            continue

        full = _pearson(base_returns, partner)
        recent = (
            _pearson(base_returns[-cut:], partner[-cut:])
            if base_returns.size >= cut
            else None
        )
        out.append(
            Correlation(
                symbol=symbol,
                full=full,
                recent=recent,
                pairs=int(base_returns.size),
                recent_pairs=int(min(cut, base_returns.size)),
                time_from=anchor[0].time,
                time_to=anchor[-1].time,
                sign_changed=(
                    full is not None and recent is not None and full * recent < 0
                ),
            )
        )

    out.sort(key=lambda c: (c.full is None, -abs(c.full or 0.0), c.symbol))
    return out
