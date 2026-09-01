"""The expectation overlay's payload: a measured forward-outcome distribution.

The numbers arrive precomputed from `tools.expectation` into
`docs/expectation.json`; the overlay only looks them up. This is a READING, not
a shape: it carries a distribution, so it sits on the drawing and is drawn by the
expectation primitive from the quantiles, never by a detector.
"""

from __future__ import annotations

from pydantic import BaseModel


class QuantileSet(BaseModel):
    """Five quantiles of a distribution, in R multiples, plus the sample size."""

    n: int
    q5: float
    q25: float
    q50: float
    q75: float
    q95: float


class PathPoint(BaseModel):
    """One point of the median forward path: `h` bars ahead, `q50` ATR of move.

    A different quantity from the fan. The fan is resolved R over the first-touch
    population; this is the median cumulative move of the WHOLE series at a fixed
    horizon. Drawn as one line and off by default, because a lone line reads as a
    forecast and nothing here forecasts.
    """

    h: int
    q50: float
    n: int


class ExpectationFan(BaseModel):
    """One expectation reading for the chart's cell.

    `base_rate` is the unconditional distribution of resolved R for this symbol,
    measured over the first-touch population. `matched` is the distribution
    conditioned on `dfr_side` - the one measured separator - for the bucket the
    newest zone's own side falls into. `matched` is None when there is no zone to
    read, or no measured bucket for that key.

    Every number is a MEASUREMENT of what happened, never a prediction. The fan
    is drawn at the right edge in R-multiple space mapped through the current
    ATR, and it is labelled measurement because twelve pre-registered directional
    hypotheses have failed in this project.

    `anchor` and `atr` are the last close and the ATR at it, sent so the renderer
    can place R quantiles as prices without computing the ATR itself. The R-to-
    price mapping is one R equals one ATR, which is the plan's own stop scale and
    is stated, not fitted.
    """

    symbol: str
    interval: str
    base_rate: QuantileSet
    matched: QuantileSet | None = None
    matched_key: str | None = None  # "met", "failed" or "unknown"
    verdict: str = ""
    note: str = ""
    anchor: float | None = None
    atr: float | None = None
    #: The median forward path, empty when the cell has none measured.
    path: list[PathPoint] = []
