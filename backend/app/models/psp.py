"""The wire shape of a Precision Swing Point.

The detector in `app/psp.py` works in bar indices; the wire speaks in times.

A READING, NEVER A BIAS, and here the null is measured rather than assumed.
`docs/psp_outcomes.json` graded 48 cells across four pairs, three bracket widths
and both directions: not one separated, and the largest |z| seen was 2,10
against a Bonferroni bar of 3,28. That covers both questions - whether a PSP
after an SSMT beats a bar with no PSP on it, and whether the SSMT in front of it
adds anything over a PSP standing alone.
"""

from __future__ import annotations

from pydantic import BaseModel


class PSPModel(BaseModel):
    #: Open time of the bar the sweep and rejection printed on.
    at: int
    #: The level that was swept: the open of the bar three back.
    level: float
    #: "buy" swept below and closed back above, "sell" is the mirror.
    direction: str
    #: Open time of the bar the SSMT settled on.
    ssmt_at: int
    #: How many bars after that the sweep printed, 1 to 3.
    bars_after_ssmt: int
    #: True when a partner printed the OPPOSITE candle sign on this bar, the
    #: "crack in correlation" the source names. Reported, never filtered on.
    triad_crack: bool = False
