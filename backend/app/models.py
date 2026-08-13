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
    curve: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Where the zone sits in the prevailing range, 0 at the low and 1 at "
            "the high, measured only on bars that preceded it. The doctrine's "
            "'curve': demand is wholesale near 0, supply is retail near 1, and a "
            "textbook formation sitting at equilibrium is held to be a weak one "
            "because that is where imbalance is smallest."
        ),
    )
    curve_favourable: bool = Field(
        default=False,
        description=(
            "True when the zone is on the useful side of the curve for its own "
            "side: demand in the lower third, supply in the upper third."
        ),
    )
    profit_zone_rr: float | None = Field(
        default=None,
        description=(
            "Distance from this zone's proximal line to the nearest live "
            "opposing zone, in units of this zone's own height. The doctrine's "
            "most-overlooked enhancer, and the reason zone validity depends on "
            "the pair of zones rather than on one alone. None when no opposing "
            "zone stands in the way."
        ),
    )
    crowded_at: int | None = Field(
        default=None,
        description=(
            "When a NEWLY FORMED opposing zone first pushed this zone's profit "
            "zone below `min_profit_zone_rr`, epoch seconds. The guidance says a "
            "zone stops being worth trading when the road ahead of it closes, "
            "which means validity has to be re-checked when ANOTHER ZONE IS "
            "BORN, not only when price moves. Every other lifecycle field here "
            "answers 'what did price do'; this one answers 'what did the rest of "
            "the chart do', and mixing the two into `state` would hide which "
            "cause applied. None when the road never closed."
        ),
    )
    refinement: Refinement | None = Field(
        default=None,
        description=(
            "Set when this zone was shrunk to the lower-timeframe base inside "
            "it. Carries the geometry it had before, so the refinement can be "
            "audited or undone. None when the zone was never refined."
        ),
    )
    arrival_atr: float | None = Field(
        default=None,
        description=(
            "How hard price travelled into the zone over the bars before its "
            "first touch, in ATR. Sources contradict each other on whether a "
            "fast arrival is good or bad, so this is measured rather than "
            "scored. None until the zone has been touched."
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

    nested_in: list[str] = Field(
        default_factory=list,
        description=(
            "Higher timeframes whose zone of the same side encloses this one, "
            "and which already existed when this zone formed. The one "
            "multi-timeframe claim every school of this method agrees on, and "
            "one nobody has published a number for. Reported, not scored."
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
    min_profit_zone_rr: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description=(
            "How much clear road a zone needs ahead of it, measured from its "
            "proximal line to the nearest live opposing zone in units of its own "
            "height. The guidance calls the road closing an invalidation: a "
            "textbook demand zone with fresh supply sitting 1.5x its height "
            "above it is not a trade however cleanly it formed. Above 0 this "
            "also becomes a filter. Default 0 leaves it OFF and reported only, "
            "because nobody has published a measured number for it and this "
            "project does not ship gates it has not measured."
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

    max_base_drift: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description=(
            "Reject a base whose one-way travel exceeds this fraction of its "
            "own height. A base is where price PAUSED; a run of candles that "
            "each happen to be small but which walk steadily in one direction "
            "is a staircase, and marking it as an origin is the defect four "
            "independent visual audits flagged most often. They also converged "
            "on where the line sits: staircases measured 0.42 to 0.86, bases "
            "they passed measured 0.02 to 0.34. Set to 1.0 to disable. "
            "Justified on fidelity, NOT on outcomes: calibration found no "
            "measurable performance difference, and the two are separate "
            "standards. See docs/FIDELITY.md."
        ),
    )
    curve_lookback: int = Field(
        default=200,
        ge=20,
        le=2000,
        description=(
            "Bars before the zone used as the reference range for its curve "
            "position. Only past bars, so the value never changes once the zone "
            "has formed."
        ),
    )
    arrival_bars: int = Field(
        default=6,
        ge=1,
        le=50,
        description="Bars before the first touch measured as the arrival move.",
    )

    show_broken: bool = False
    show_mitigated: bool = True
    max_zones_per_side: int = Field(
        default=12,
        ge=0,
        le=100,
        description=(
            "Most zones to return per side, newest first. **0 means no cap**, "
            "and measurement code must use 0: this is a readability limit, and "
            "leaving it at any finite value keeps only the most RECENT zones, "
            "which silently confines a sample to the tail of the history. At its "
            "own schema maximum of 100 it still cut 2030 candidate zones down to "
            "200, all of them inside the last 10% of a 20,000-bar series."
        ),
    )
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
    refine: bool = Field(
        default=False,
        description=(
            "Shrink each higher-timeframe zone to the lower-timeframe base "
            "inside it, using the chart's own candles. Ignored unless `htf` is "
            "set, because there is no lower timeframe to refine from otherwise. "
            "Off by default: it tightens the stop, which is both the point of "
            "refining and a reason it can score worse, and that is a question "
            "for measurement rather than for a default."
        ),
    )
    session_offset_hours: float = Field(
        default=0.0,
        ge=-12.0,
        le=12.0,
        description=(
            "Shifts the higher-timeframe grid off UTC midnight, to match the "
            "broker's trading day. Gold and FX brokers commonly start at 22:00 "
            "or 01:00; leaving this at 0 puts every H4 and D1 zone one candle "
            "away from where the terminal draws it."
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
