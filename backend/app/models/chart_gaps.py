"""The wire shape of a breakaway or measuring gap.

The detector in `app/chart_gaps.py` works in bar indices; the wire speaks in
times, so this is the index-free shape the chart renders. Distinct from
`OpeningGap` in `models/gaps.py`, which is a session gap, not a trend gap.
"""

from __future__ import annotations

from pydantic import BaseModel


class ChartGapModel(BaseModel):
    up: bool
    top: float
    bottom: float
    #: Open time of the bar that gapped, so the band can be placed on the axis.
    at: int
    kind: str  # "breakaway" or "measuring"
    move_start: float
    target: float
