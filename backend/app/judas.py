"""NY Judas Swing - Templates A, B, C, D for the 09:30 EST counter-move.

The practitioner's rule: at 09:30 EST (inside the 09:00-10:30 Killzone), the
algorithm must validate the counter-directional Judas Swing based on the
London session profile before validating the true Q3 expansion.

TEMPLATES:
  A: London bullish → Judas SELL (down), then Q3 expansion BUY (up)
  B: London bearish → Judas BUY (up), then Q3 expansion SELL (down)
  C: London consolidation → no Judas, wait for breakout
  D: London range → Judas in both directions, wait for true direction

The London session directional bias is read from the London Open (03:00 EST)
to the London Close (12:00 EST). The bias is determined by the net movement
and the structure within the session.

The Judas Swing is the counter-move that happens at 09:30 EST. Retail
traders see the breakout and enter in the wrong direction. The algorithm
waits for the Judas to complete, then enters in the opposite direction
(the true Q3 expansion).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Template = Literal["A", "B", "C", "D"]


@dataclass(frozen=True)
class JudasSwing:
    """The NY Judas Swing validation for the current session."""

    template: Template
    london_bias: Literal["bullish", "bearish", "neutral"]
    judas_direction: Literal["buy", "sell", "none"]
    expansion_direction: Literal["buy", "sell", "none"]
    description: str


def classify(
    london_bias: Literal["bullish", "bearish", "neutral"],
    london_range_pct: float = 0.0,
) -> JudasSwing:
    """Classify the NY Judas Swing template based on London session bias.

    `london_bias` is the directional bias of the London session.
    `london_range_pct` is the range as a percentage of ATR (used for
    distinguishing consolidation vs. range in Template C vs D).

    Template A: London bullish → Judas sell, expansion buy
    Template B: London bearish → Judas buy, expansion sell
    Template C: London neutral + tight range → no Judas, wait for breakout
    Template D: London neutral + wide range → Judas in both directions
    """
    if london_bias == "bullish":
        return JudasSwing(
            template="A",
            london_bias="bullish",
            judas_direction="sell",
            expansion_direction="buy",
            description=(
                "Template A: London bullish → Judas sell (09:30 counter-move "
                "down), then Q3 expansion buy (true direction up)"
            ),
        )
    if london_bias == "bearish":
        return JudasSwing(
            template="B",
            london_bias="bearish",
            judas_direction="buy",
            expansion_direction="sell",
            description=(
                "Template B: London bearish → Judas buy (09:30 counter-move "
                "up), then Q3 expansion sell (true direction down)"
            ),
        )
    if london_range_pct < 0.5:
        return JudasSwing(
            template="C",
            london_bias="neutral",
            judas_direction="none",
            expansion_direction="none",
            description=(
                "Template C: London consolidation (tight range) → no Judas. "
                "Wait for breakout before entering."
            ),
        )
    return JudasSwing(
        template="D",
        london_bias="neutral",
        judas_direction="none",
        expansion_direction="none",
        description=(
            "Template D: London range (wide) → Judas in both directions. "
            "Wait for the true Q3 direction to establish before entering."
        ),
    )