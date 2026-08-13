"""Wire types shared by the API and the detection engine.

Every drawing the frontend renders is one of these objects. The engine never
returns a shape without the evidence that produced it: `anatomy` carries the bar
indices, `factors` carries the numeric score breakdown. That is what makes a
drawing auditable rather than decorative.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Candle(BaseModel):
    time: int = Field(description="Bar open time, epoch seconds UTC")
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class ZoneKind(StrEnum):
    """The four supply/demand formations, named leg-in / base / leg-out."""

    RBR = "RBR"  # Rally-Base-Rally    -> demand (continuation)
    DBR = "DBR"  # Drop-Base-Rally     -> demand (reversal)
    DBD = "DBD"  # Drop-Base-Drop      -> supply (continuation)
    RBD = "RBD"  # Rally-Base-Drop     -> supply (reversal)


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
    base_from: int
    base_to: int
    leg_out_from: int
    leg_out_to: int


class Zone(BaseModel):
    id: str
    kind: ZoneKind
    side: ZoneSide
    state: ZoneState
    timeframe: str = Field(
        default="",
        description=(
            "The timeframe whose candles formed this zone. Equal to the chart's "
            "interval for local zones, higher for projected ones. Supply and "
            "demand is a top-down method, so which timeframe drew a zone is part "
            "of what the zone means, not metadata."
        ),
    )

    # Geometry. top/bottom are absolute prices; proximal is the edge price
    # meets first on the way back, distal is the protective far edge.
    top: float
    bottom: float
    proximal: float
    distal: float

    time_from: int = Field(description="Left edge: base open time, epoch seconds")
    time_to: int = Field(
        description="Right edge: break time if broken, else last bar time"
    )

    formation_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How cleanly the zone was BUILT: base tightness, base compactness "
            "and leg-out volume, equally weighted. It is not a forecast. "
            "Measured on 234 resolved zones across five series, it does not "
            "separate zones that held from zones that failed (AUC 0.51 to 0.54, "
            "confidence interval crosses 0.5). Use it to order the display, not "
            "to rank opportunity. See docs/CALIBRATION.md."
        ),
    )
    departure_atr: float = Field(
        description=(
            "Size of the leg-out move in ATR at the base. This one IS validated, "
            "as a threshold rather than a gradient: formations clearing 2 ATR "
            "held 84.6% against 68.3% for those that did not (p < 0.0001), while "
            "above 2 ATR more departure buys nothing."
        )
    )
    profit_margin: float = Field(
        default=0.0,
        description=(
            "Leg-out travel as a multiple of the zone's own height. This is the "
            "doctrine's own test, and the only hard number in it: a base is not "
            "a level unless the initial move away is at least 3x the level. "
            "Reported for every zone; gated only if `min_profit_margin` is set."
        ),
    )
    # Two descriptions of whether the base actually paused. Reported, not yet
    # filtered on: see docs/CALIBRATION.md before turning either into a gate.
    base_drift: float = Field(
        default=0.0,
        description=(
            "One-way travel across the base as a fraction of the base's own "
            "height. Near 0 means price came back to where it started; near 1 "
            "means the 'base' was a staircase that never paused."
        ),
    )
    base_overlap: float = Field(
        default=1.0,
        description=(
            "Mean shared range between consecutive base bars. A real "
            "consolidation revisits the same prices; a slow trend does not."
        ),
    )

    touches: int = 0
    penetration_pct: float = Field(
        default=0.0, description="Deepest entry into the zone, 0..1 of its height"
    )
    first_test_time: int | None = None

    confirmed: bool = Field(
        default=True,
        description=(
            "False while the leg-out is still the newest run: the run can grow "
            "with the next bar, so the zone may still shift. The UI draws these "
            "dashed. Everything older than the newest run is final."
        ),
    )

    anatomy: Anatomy
    factors: dict[str, float] = Field(
        default_factory=dict, description="Score breakdown, sums to `strength`"
    )
    note: str = Field(default="", description="One-line human-readable rationale")


class Drawing(BaseModel):
    """Envelope for everything the engine draws. Zones today; lines, boxes and
    markers from the other ICT detectors slot in beside them."""

    zones: list[Zone] = Field(default_factory=list)


class SupplyDemandParams(BaseModel):
    """Every knob the UI exposes. Defaults are the ones the test fixtures pin."""

    atr_period: int = Field(default=14, ge=2, le=200)

    # A candle is "exciting" (part of a leg) when its body dominates its range
    # AND the range itself is large relative to ATR. Everything else is base.
    impulse_body_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    impulse_atr: float = Field(default=1.0, ge=0.1, le=10.0)

    base_max_bars: int = Field(default=6, ge=1, le=30)
    base_max_atr: float = Field(
        default=2.5, ge=0.1, le=20.0, description="Reject bases taller than this x ATR"
    )

    departure_min_atr: float = Field(
        default=2.0,
        ge=0.0,
        le=20.0,
        description="Leg-out must travel this far from the zone or it is not a zone",
    )
    departure_lookahead: int = Field(default=20, ge=1, le=500)

    proximal_basis: Literal["wick", "body"] = Field(
        default="wick",
        description=(
            "Which edge of the base the PROXIMAL line sits on. 'wick' is the "
            "aggressive variant (wider zone, more likely to be reached); 'body' "
            "is the conservative one (tighter zone, less risk to the distal). "
            "The distal line is always the wick extreme in both variants, "
            "because a distal drawn at the body puts the stop inside the base."
        ),
    )
    min_profit_margin: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description=(
            "Doctrine's one hard number: the leg-out must travel at least this "
            "many times the zone's own height for the base to count as a level "
            "(Seiden states 3:1). Measured relative to the ZONE, unlike "
            "`departure_min_atr` which is relative to volatility. Default 0 "
            "leaves it off and reported only, pending measurement."
        ),
    )
    zone_min_atr: float = Field(
        default=0.05,
        ge=0.0,
        le=2.0,
        description="Floor on zone height as x ATR, so a doji base stays clickable",
    )
    mitigation_pct: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Fraction of zone depth eaten before it counts as mitigated",
    )

    show_broken: bool = False
    show_mitigated: bool = True
    max_zones_per_side: int = Field(default=12, ge=1, le=100)
    merge_overlap_pct: float = Field(default=0.6, ge=0.0, le=1.0)


class DrawRequest(BaseModel):
    symbol: str = "XAUUSD"
    interval: str = "15m"
    bars: int = Field(default=500, ge=50, le=5000)
    provider: str | None = None
    htf: str | None = Field(
        default=None,
        description=(
            "Optional higher timeframe to also draw zones from, aggregated from "
            "the same bars. Ignored unless strictly higher than `interval`."
        ),
    )
    detectors: list[str] = Field(default_factory=lambda: ["supply_demand"])
    supply_demand: SupplyDemandParams = Field(default_factory=SupplyDemandParams)


class DrawResponse(BaseModel):
    symbol: str
    interval: str
    provider: str
    candles: list[Candle]
    drawing: Drawing
    meta: dict[str, Any] = Field(default_factory=dict)
