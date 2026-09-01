"""Single-candle structure: which side a candle rejected.

OHLC bars cannot say the ORDER a candle visited its extremes in - that needs
tick data. "OLHC" (open, low, high, close) and "OHLC" (open, high, low, close)
name that order, and reading either from a completed OHLC bar is guessing. What
a bar CAN say is which side it REJECTED, from the close position and the wick
split:

  - accumulation: closed in the upper half with a longer lower wick - swept down
    and was bought, the shape behind the OLHC reading;
  - distribution: closed in the lower half with a longer upper wick - swept up
    and was sold, the shape behind OHLC;
  - neutral: neither, including a clean trend candle with no wick.

This is the single-candle cousin of the structure sweep-reversal in
`app/detect/structure.py` and of the rejection-wick test in `app/tcisd.py`. It
is a reading, never a bias.

MEASURED 1 September 2026, `docs/olhc_outcomes.json`, and there are two findings.

FIRST, THIS FUNCTION CARRIES NOTHING BEYOND THE OPEN AND THE CLOSE. On a bar of
range R the two wicks are not free:

    lower_wick / R = min(open_pos, close_pos)
    upper_wick / R = 1 - max(open_pos, close_pos)

so the rule below is exactly

    accumulation  <=>  close_pos >= 0.5  and  min(o, c) > 1 - max(o, c)

`classify` is a relabelling of the pair (open position, close position). That is
not a defect - a name for a shape is useful - but it does mean no study can ask
what the WICK adds, because holding both positions fixed fixes the class too.
The identity is gated in `tools/olhc_outcomes.py --selfcheck` over 20 000 random
bars, so it fails loudly if this function ever stops being that relabelling.

SECOND, THE DIRECTION IT NAMES IS NULL. Against the instrument's own drift over
nine instruments at 1h, clustered on overlapping forward windows: accumulation
t=+0,29 on 59 035 events, distribution t=+0,005 on 51 367, against a Bonferroni
bar of 2,24. The module stays unwired, now for a measured reason rather than an
overlooked one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import Candle

Kind = Literal["accumulation", "distribution", "neutral"]


@dataclass(frozen=True)
class CandleStructure:
    at: int
    kind: Kind
    close_pos: float   # 0 at the low, 1 at the high
    lower_wick: float
    upper_wick: float


def classify(candle: Candle) -> tuple[Kind, float, float, float]:
    """The rejection structure of one candle.

    A rejection needs BOTH halves: the close on one side of the range AND the
    opposite wick dominant. A clean trend candle (no wick) is neutral, because
    it rejected nothing - the same reason `app/psp.py` refuses to call a plain
    break a purge.
    """
    rng = candle.high - candle.low
    if rng <= 0:
        return "neutral", 0.5, 0.0, 0.0
    body_high = max(candle.open, candle.close)
    body_low = min(candle.open, candle.close)
    lower_wick = body_low - candle.low
    upper_wick = candle.high - body_high
    close_pos = (candle.close - candle.low) / rng

    upper_half = close_pos >= 0.5
    if upper_half and lower_wick > upper_wick:
        return "accumulation", close_pos, lower_wick, upper_wick
    if not upper_half and upper_wick > lower_wick:
        return "distribution", close_pos, lower_wick, upper_wick
    return "neutral", close_pos, lower_wick, upper_wick


def structure(candles: list[Candle]) -> list[CandleStructure]:
    """One reading per candle, in time order."""
    out: list[CandleStructure] = []
    for i, c in enumerate(candles):
        kind, pos, lw, uw = classify(c)
        out.append(CandleStructure(at=i, kind=kind, close_pos=pos,
                                   lower_wick=lw, upper_wick=uw))
    return out
