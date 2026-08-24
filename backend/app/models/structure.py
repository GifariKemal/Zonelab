"""Swings, structure events, and the session quarter they land in."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SwingPoint(BaseModel):
    """A pivot, and the bar it became knowable on.

    `confirmed_at` is the whole reason this is drawable without lying: a swing
    high at bar i is not knowable at bar i, only at i + right once enough bars
    have printed beside it. The UI draws the marker at `time` and must never
    present it as available before `confirmed_at`.
    """

    time: int
    price: float
    high: bool = Field(description="True for a swing high, False for a swing low")
    confirmed_at: int = Field(
        description="Open time of the bar this swing became knowable on"
    )
    scale: Literal["swing", "internal"] = "swing"


class StructureEvent(BaseModel):
    """A close beyond a confirmed swing, or a wick that took liquidity.

    Drawn as a fact about the chart, never as a direction. Twelve pre-registered
    directional hypotheses failed in this project and two of them were about
    exactly these objects: H6 tested BOS, CHoCH and SWEEP separately, H9 tested
    the sweep-then-MSS conjunction, and all of it came out null or negative. The
    reason to draw them anyway is fidelity - ICT puts bias in structure and uses
    zones to refine the entry, so a chart that cannot show structure cannot show
    the method - and because an order block that must follow a break needs the
    break to exist as an object first.
    """

    time: int = Field(description="Open time of the bar that broke or swept")
    kind: Literal["BOS", "CHoCH", "SWEEP", "MSS"]
    direction: int = Field(description="+1 broke or swept upward, -1 downward")
    level: float = Field(description="The swing price that gave way")
    swing_time: int = Field(description="Open time of the bar that made that swing")
    bias_before: int = Field(description="-1, 0 or +1 before this event")
    scale: Literal["swing", "internal"] = Field(
        default="swing",
        description=(
            "Which fractal width produced it. Two widths run side by side, and "
            "until now nobody ever CROSSED them - `aligned_with_swing` is that "
            "crossing, and it was listed as a missing ICT conjunction."
        ),
    )
    aligned_with_swing: bool | None = Field(
        default=None,
        description=(
            "For an internal event: whether the prevailing swing-scale bias "
            "pointed the same way. None when the question has no answer - on a "
            "swing-scale event, where it does not apply, and when no swing-scale "
            "break has happened yet, so there is no major structure to agree or "
            "disagree with. False therefore always means the major structure "
            "pointed the OTHER way, which is the only reading that makes the "
            "field worth filtering on."
        ),
    )
    reversed_within: int | None = Field(
        default=None,
        description=(
            "SWEEP only. Bars until price closed back inside the swept level, or "
            "None if it never did within the window. The sources describe a sweep "
            "as liquidity taken AND rejected; this engine only ever coded the "
            "taking, which is why the reversal is reported rather than assumed."
        ),
    )
    swept_at: int | None = Field(
        default=None,
        description=(
            "MSS only: open time of the sweep that qualified this break. An MSS "
            "is a break with a preceding opposite sweep, which is the single "
            "requirement every source uses to tell it from a plain CHoCH."
        ),
    )


class SessionQuarter(BaseModel):
    """One quarter of one cycle, in the New York grid.

    A fact about the clock, not about price: it says nothing about what the
    market did inside it. Drawn so the reader can see which phase of a cycle a
    move happened in, which is the whole premise of the method this serves.
    """

    degree: str = Field(description="year, month, week, day, session or micro")
    label: Literal["Q1", "Q2", "Q3", "Q4"]
    time_from: int
    time_to: int = Field(description="Exclusive: the next quarter opens here")


class TrueOpenLevel(BaseModel):
    """The opening price of a cycle's Q2, which is what a true open IS.

    Not the first bar of the cycle. The daily true open is midnight New York
    rather than 18:00 precisely because midnight is the day cycle's Q2, and the
    originator states it that way directly.

    A level only exists when a bar opened EXACTLY on the boundary. Weekends,
    holidays and feed gaps mean it often did not, and then there is no level -
    nothing is carried forward and nothing is interpolated, the same rule
    `Candle.spread` follows by being None rather than 0 when unmeasured.

    That rule is relaxed ONLY on request, and then the level says so. See
    `approximate` below: some boundaries can never satisfy the strict rule, and a
    level that can never exist is a missing feature rather than a conservative
    choice - but a level silently moved to the next open would be worse.
    """

    degree: str
    time: int = Field(description="The Q2 boundary this level belongs to")
    price: float
    bar: int = Field(
        default=0,
        description=(
            "Open time of the bar the price was read from. Equal to `time` "
            "unless `approximate`."
        ),
    )
    approximate: bool = Field(
        default=False,
        description=(
            "True when no bar opened on the boundary and the first bar after it "
            "was used instead. Drawn dashed and tagged with a ~, never as a "
            "measured level. Only possible when the caller asked for it: the "
            "quadrennial Q2 boundary is 1 January and the market is shut on 1 "
            "January every year, so on ten years of hourly gold the strict rule "
            "returned that degree's level zero times."
        ),
    )


class FibonacciAnchor(BaseModel):
    """The two structural swing anchors the Fibonacci/OTE grid is drawn over.

    `low` is the most recent confirmed swing low (Anchor 0); `high` is the
    most recent confirmed swing high (Anchor 1). Both carry the price and the
    bar it became knowable on, so the grid can be drawn at the exact pip and
    re-anchored without repainting. Empty (both None) until the structure
    layer has confirmed a swing on both sides.
    """

    low: float | None = None
    low_at: int | None = None
    high: float | None = None
    high_at: int | None = None
