"""The wire shape of a Wyckoff phase reading.

The detector in `app/wyckoff.py` works in bar indices; the wire speaks in times.
A reading, never a bias: the structure primitives these map onto are measured
null in H6 and H9.
"""

from __future__ import annotations

from pydantic import BaseModel


class WyckoffPhaseModel(BaseModel):
    kind: str  # "spring", "upthrust", "sos", "sow"
    at: int    # open time of the event bar
    level: float
    tr_low: float
    tr_high: float
