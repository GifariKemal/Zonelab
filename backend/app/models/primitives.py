"""Bars, zone vocabulary, and the evidence a shape carries."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Candle(BaseModel):
    time: int = Field(description="Bar open time, epoch seconds UTC")
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    spread: float | None = Field(
        default=None,
        description=(
            "Mean ask-minus-bid across the bar, in price units. Optional "
            "because only the Dukascopy tick feed carries both sides: binance, "
            "yahoo, twelvedata and polygon all ship one price per bar and "
            "leave this None. Anything that reads it MUST handle None rather "
            "than assume a number - an absent spread means 'not measured', "
            "never 'zero', and defaulting it to zero would quietly reinstate "
            "the free-trading assumption this field exists to remove."
        ),
    )


class ZoneKind(StrEnum):
    """The four supply/demand formations, named leg-in / base / leg-out."""

    RBR = "RBR"  # Rally-Base-Rally    -> demand (continuation)
    DBR = "DBR"  # Drop-Base-Rally     -> demand (reversal)
    DBD = "DBD"  # Drop-Base-Drop      -> supply (continuation)
    RBD = "RBD"  # Rally-Base-Drop     -> supply (reversal)

    # From the ICT/SMC lineage rather than the Seiden one. Same shape - a box
    # with a near and a far edge - so they share `Zone`, and `kind` says which
    # detector drew it.
    FVG = "FVG"  # Fair value gap: three bars whose outer wicks never met
    OB = "OB"  # Order block: last opposite candle before an impulsive move

    # The same two boxes after price closed through them, re-read from the other
    # side. `replay_lifecycle` has always computed the bar a box died on and
    # every caller threw it away; these two kinds are that number kept.
    #
    # Drawn, and deliberately NOT sold as direction: H8 measured post-inversion
    # touches against a control that only knows the trailing 20-bar move and the
    # boxes came out SIGNIFICANTLY NEGATIVE on all three detectors. Knowing a box
    # inverted made the directional guess worse than not knowing. So an IFVG on
    # this chart says "this band flipped role here", which is a fact about the
    # drawing, and says nothing about what price will do next.
    IFVG = "IFVG"  # Inversion fair value gap: a gap price closed through
    BRK = "BRK"  # Breaker block: the order block version of the same inversion


class ZoneSide(StrEnum):
    DEMAND = "demand"
    SUPPLY = "supply"


class ZoneState(StrEnum):
    FRESH = "fresh"  # price has not returned since the leg-out
    TESTED = "tested"  # price entered the zone but did not consume it
    MITIGATED = "mitigated"  # price ate past the mitigation threshold
    BROKEN = "broken"  # a bar closed beyond the distal line; zone is dead


class Anatomy(BaseModel):
    """Bar indices that formed the zone. Lets the UI highlight the exact
    candles and lets a human replay the decision."""

    leg_in_from: int
    leg_in_to: int
    base_run_from: int = Field(
        default=-1,
        description=(
            "First bar of the WHOLE consolidation. When a long pause is clipped "
            "so the zone is drawn on the bars the move actually left from, "
            "`base_from` moves forward and this does not, so the formation still "
            "reads as one contiguous sequence. Without it the anatomy claims a "
            "leg-in adjacent to a base that is up to nine bars away."
        ),
    )
    base_from: int
    base_to: int
    leg_out_from: int
    leg_out_to: int


class Refinement(BaseModel):
    """Evidence that a zone was shrunk to the lower-timeframe base inside it.

    Kept alongside the refined geometry rather than replacing it silently. A box
    that moved without saying where it moved from is exactly the kind of drawing
    this engine refuses to produce.
    """

    timeframe: str = Field(
        default="", description="Interval of the candles the refined box was cut from"
    )
    from_top: float = Field(description="Top of the box before refinement")
    from_bottom: float = Field(description="Bottom of the box before refinement")
    shrank_to: float = Field(
        description="Refined height as a fraction of the original, 0..1"
    )
    bars: int = Field(description="Lower-timeframe bars the refined box was cut from")
    time_from: int = Field(description="Open time of the first of those bars")
    time_to: int = Field(description="Open time of the last of those bars")


class Displacement(BaseModel):
    """The move that qualified a box, described instead of reduced to a scalar.

    ICT states displacement STRUCTURALLY - an aggressive leg that breaks
    structure and leaves an inefficiency behind - while this engine has only ever
    tested it as a size: `displacement_atr` ATR within `displacement_bars`. That
    is a different object wearing the same name, and it was listed as a departure
    in docs/FIDELITY.md long before this model existed.

    So the leg is now reported as what it is: where it ran, how big it was, and
    whether the two structural properties the sources actually name were present.
    `broke_structure` is None when no structure was computed for the request,
    which is not the same as False and must not be read as it.
    """

    time_from: int = Field(description="Open time of the first bar of the leg")
    time_to: int = Field(description="Open time of the last bar of the leg")
    atr: float = Field(description="Size of the leg in ATR before the box")
    broke_structure: bool | None = Field(
        default=None,
        description=(
            "Whether the leg closed beyond a confirmed swing. None means "
            "structure was not computed, NOT that the leg failed the test."
        ),
    )
    left_gap: bool = Field(
        default=False,
        description="Whether the leg left a fair value gap, the ICT inefficiency",
    )
