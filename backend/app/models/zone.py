"""The zone itself, and the drawing that carries every shape."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .primitives import Anatomy, Displacement, Refinement, ZoneKind, ZoneSide, ZoneState
from .structure import FibonacciAnchor, SessionQuarter, StructureEvent, SwingPoint, TrueOpenLevel
from .gaps import EventHorizonLevel, GapStack, NewsEvent, OpeningGap, TierHorizon
from .liquidity import LiquidityPool, NamedLevel, RangeProjection
from .cycle import CISDEvent, DefiningRangeBand, SMTDivergence, SSMTDivergence


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
            "and leg-out volume, equally weighted. It is not a forecast, and it "
            "is WORSE than useless as a ranking: measured on 2707 resolved zones "
            "across five series it ranks BACKWARDS, AUC 0.464 and 0.477, so a "
            "higher score goes with a slightly worse outcome. Use it to order "
            "the display, never to rank opportunity. See docs/CALIBRATION.md."
        ),
    )
    departure_atr: float = Field(
        description=(
            "Size of the leg-out move in ATR at the base. This one IS validated, "
            "as a threshold rather than a gradient, and as a SORTER rather than a "
            "picker. On the instrument actually traded, on 5-minute bars, "
            "formations clearing 2 ATR held 43.0% against 40.2% - a hold-rate "
            "difference that is NOT significant. What is significant is the "
            "expectancy gap, +0.124 R at t=+4.82. The 85.8 against 64.4 this "
            "field used to quote was measured on Binance crypto, not on this "
            "instrument. Above 2 ATR more departure buys nothing. "
            "Two limits on reading it. The validation is a FIRST-TOUCH result: "
            "measured at touch 2 and later the same gate separates outcomes by "
            "-0.2, -2.5 and -4.3 points across the three geometries, so a zone "
            "that has already been visited carries no filter this project has "
            "validated. And on an IFVG or a BRK this number describes the leg "
            "that built the PARENT box, not the inversion - the inverted box was "
            "made by a close through a level, which has no leg to measure. "
            "`displacement` is left None there for the same reason."
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

    inverted_at: int | None = Field(
        default=None,
        description=(
            "IFVG and BRK only: when price closed through the original box, "
            "epoch seconds. `side` is the side the box became, and `distal` its "
            "far edge read from the new direction, so the geometry is the old "
            "rectangle entered from the other side rather than a new box."
        ),
    )
    dealing_range_pos: float | None = Field(
        default=None,
        description=(
            "ICT premium/discount: where the zone's proximal line sat inside the "
            "swing-to-swing dealing range AT ITS FIRST TOUCH, 0 at the range low "
            "and 1 at the high. This is NOT `curve`, and the difference is the "
            "deviation docs/FIDELITY.md listed: `curve` is a 200-bar rolling "
            "range split in thirds and frozen when the zone was born, which is "
            "the Seiden reading. ICT reads the position at the moment price "
            "arrives, on a range anchored to the last confirmed swing high and "
            "low. None until the zone has been touched, or when no dealing range "
            "could be established."
        ),
    )
    displacement: Displacement | None = Field(
        default=None,
        description=(
            "The qualifying leg as an object rather than a threshold. None for "
            "detectors that have no displacement concept."
        ),
    )
    structure_break_time: int | None = Field(
        default=None,
        description=(
            "Order block only, and only when `require_structure_break` is on: "
            "the break this block's impulse produced. None means the block was "
            "admitted without a structural requirement, which is this engine's "
            "default and its largest remaining ICT departure."
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

    settled: bool = Field(
        default=True,
        description=(
            "Every reported field for this zone is final given closed bars: the "
            "leg-out run has ended AND the departure window that decided the "
            "gate has fully printed. This is the flag `confirmed` was mistaken "
            "for. A zone that is confirmed but not settled still has a gate "
            "verdict that can move."
        ),
    )
    confirmed: bool = Field(
        default=True,
        description=(
            "False while the leg-out is still the newest run: the run can grow "
            "with the next bar, so the zone may still shift. The UI draws these "
            "dashed. "
            "It does NOT mean the zone is final, and its docstring used to claim "
            "exactly that. An audit measured a confirmed zone's departure_atr "
            "growing on 101 of 599 bar formations, its state changing 24 times "
            "and reverting 21, and the flag itself flipping True to False when a "
            "later bar extended the leg-out. Read it as `leg_out_open`, inverted. "
            "For finality use `settled`."
        ),
    )

    anatomy: Anatomy
    factors: dict[str, float] = Field(
        default_factory=dict, description="Score breakdown, sums to `formation_score`"
    )
    note: str = Field(default="", description="One-line human-readable rationale")


class Drawing(BaseModel):
    """Envelope for everything the engine draws: boxes, pivots and structure."""

    zones: list[Zone] = Field(default_factory=list)
    swings: list[SwingPoint] = Field(
        default_factory=list,
        description="Confirmed pivots, empty unless structure was requested",
    )
    structure: list[StructureEvent] = Field(
        default_factory=list,
        description=(
            "Breaks, sweeps and shifts, empty unless structure was requested. "
            "Ordered by time. Carries no direction claim: see StructureEvent."
        ),
    )
    fibonacci: FibonacciAnchor | None = Field(
        default=None,
        description=(
            "The two structural swing anchors the Fibonacci/OTE grid is drawn "
            "over: most recent confirmed swing low and high. None until the "
            "structure layer has confirmed a swing on both sides."
        ),
    )
    quarters: list[SessionQuarter] = Field(
        default_factory=list,
        description="Quarter divisions, empty unless a degree was requested",
    )
    true_opens: list[TrueOpenLevel] = Field(
        default_factory=list,
        description="True opens, empty unless a degree was requested",
    )
    dfr: list[DefiningRangeBand] = Field(
        default_factory=list,
        description=(
            "Defining ranges with their equilibrium and projections, empty "
            "unless the dfr layer was requested. Read off the bars already "
            "fetched, so it costs no provider call. The checklist reports the "
            "same object as a READING, without projections."
        ),
    )
    ssmt: list[SSMTDivergence] = Field(
        default_factory=list,
        description=(
            "Cross-instrument divergences positioned on THIS symbol's price, "
            "empty unless the ssmt layer was requested. The same events also "
            "appear in the checklist as `SSMTHit`, which is the reading; "
            "these are the shape. Costs one provider call per partner."
        ),
    )
    smt: list[SMTDivergence] = Field(
        default_factory=list,
        description=(
            "Regular (non-sequential) SMT divergences on this symbol's price. "
            "Liquidity readings rather than trend confirmations: one instrument "
            "took the running extreme, the other failed. Drawn as markers, not "
            "segments. Empty unless the ssmt layer was requested."
        ),
    )
    gaps: list[OpeningGap] = Field(
        default_factory=list,
        description="NDOG and NWOG bands, empty unless gaps were requested",
    )
    news: list[NewsEvent] = Field(
        default_factory=list,
        description="Scheduled releases in the chart's window. Empty unless requested.",
    )
    tier_horizons: list[TierHorizon] = Field(
        default_factory=list,
        description="One zone per gap kind. Empty unless gaps were requested.",
    )
    gap_stacks: list[GapStack] = Field(
        default_factory=list,
        description="Overlaps between gaps of different kinds. Empty unless gaps were requested.",
    )
    event_horizons: list[EventHorizonLevel] = Field(
        default_factory=list,
        description=(
            "Levels between adjacent gaps in PRICE order. Empty unless gaps were "
            "requested. These MOVE when a new gap appears: see EventHorizonLevel."
        ),
    )
    cisd: list[CISDEvent] = Field(
        default_factory=list,
        description="Delivery-state changes, empty unless requested. Ordered by time.",
    )
    pools: list[LiquidityPool] = Field(
        default_factory=list,
        description=(
            "Session extremes as candidate targets, empty unless requested. Zones "
            "are targets the same way, and are NOT duplicated here: an untouched "
            "box is already identifiable from `zones` by its own state."
        ),
    )
    levels: list[NamedLevel] = Field(
        default_factory=list,
        description="PDH, PDL, PWH, PWL and the named day extremes. Empty unless requested.",
    )
    projections: list[RangeProjection] = Field(
        default_factory=list,
        description="Deviation stacks off named ranges. Empty unless requested.",
    )
