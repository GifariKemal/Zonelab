"""One parameter block per layer. Adding a layer adds one class here."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ParamBlock(BaseModel):
    """Base for every params block below. Its only job is to REFUSE a field it
    does not know.

    `DrawRequest` has carried `extra="forbid"` since the incident recorded in
    `models/api.py`: five providers were "measured" by sending a `source` field
    that model never had, pydantic ignored it, and all five answered 200 with
    identical Yahoo bars. The top level was closed that day and these twelve
    nested blocks were not, which left the same defect one level down and made
    it worse in one respect: the top level holds eight scalar fields a typo is
    hard to hide in, while these hold roughly seventy knobs whose names are
    hand-copied into TypeScript. `supply_demand.departure_min_ATR`,
    `imbalance.min_gap`, `session.true_open` - each of those was a silent no-op
    with an HTTP 200 and a chart drawn on the DEFAULT, which is a wrong reading
    that looks right. That is the same failure shape, and it is the one this
    project's own notes call the worst way for an API to be wrong.

    Closing it is safe because the caller sends exactly these names and the
    seam is already tested from the other side: `tests/test_frontend_defaults`
    fails when `DEFAULT_LAYER_PARAMS` in `frontend/src/lib/types.ts` carries a
    key no model has. Before this class that test was the ONLY thing standing
    between a renamed knob and a silent drop; now the request itself refuses,
    and the test explains why in TypeScript terms rather than being the guard.

    A base class rather than twelve `model_config` lines, so the thirteenth
    params block cannot ship open by forgetting one.
    """

    model_config = ConfigDict(extra="forbid")


class SupplyDemandParams(ParamBlock):
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
        default=6,
        ge=0,
        le=100,
        description=(
            "Most zones to return per side, newest first. The cap applies per "
            "detector AND per side, so with all FIVE box detectors on it permits "
            "5 x 2 x this. At the old default of 12 that painted 39.6% of the "
            "chart on average and 52.4% on one series, which is not annotation "
            "any more; 6 halves the ink for a third fewer boxes. Readability is "
            "a display decision, so it was settled by measuring ink rather than "
            "by taste. **0 means no cap**, "
            "and measurement code must use 0: this is a readability limit, and "
            "leaving it at any finite value keeps only the most RECENT zones, "
            "which silently confines a sample to the tail of the history. At its "
            "own schema maximum of 100 it still cut 2030 candidate zones down to "
            "200, all of them inside the last 10% of a 20,000-bar series."
        ),
    )
    merge_overlap_pct: float = Field(default=0.6, ge=0.0, le=1.0)


class ImbalanceParams(ParamBlock):
    """Knobs for the four detectors that read imbalance: fvg, order_block,
    ifvg and breaker.

    The inversion pair shares this block with the pair it inverts rather than
    getting its own gap threshold, because an IFVG is an FVG plus one more
    event and two thresholds would let the two populations drift apart.

    Deliberately few. The supply/demand detector shipped with a composite score
    over three factors and had to retract it when measurement said the composite
    ranked backwards; these two start with no score at all, so there is nothing
    to weight and nothing to retract.
    """

    atr_period: int = Field(default=14, ge=2, le=200)

    min_gap_atr: float = Field(
        default=0.1,
        ge=0.0,
        le=5.0,
        description=(
            "Smallest fair value gap worth drawing, as a multiple of the ATR "
            "before it. Every three bars in a quiet market technically leave "
            "micro-gaps; without a floor the chart is unreadable and the "
            "population is dominated by noise."
        ),
    )
    displacement_atr: float = Field(
        default=1.5,
        ge=0.0,
        le=10.0,
        description=(
            "How far price must travel away from an order block candle for the "
            "move to count as impulsive. The published sources say 'strong' and "
            "never say how strong, so this number is ours and is stated as such."
        ),
    )
    displacement_bars: int = Field(
        default=5,
        ge=1,
        le=50,
        description=(
            "Bars after the block candle in which that travel is measured. "
            "Fixed rather than run to the end of a swing, because where a swing "
            "ends is a human judgement and this detector has none."
        ),
    )

    # Read by the shared lifecycle replay, which is why they are named exactly
    # as the supply/demand block names them.
    mitigation_pct: float = Field(default=0.5, ge=0.0, le=1.0)
    arrival_bars: int = Field(default=6, ge=1, le=50)

    require_structure_break: bool = Field(
        default=False,
        description=(
            "Order block only: demand that the block's impulse CLOSE beyond a "
            "confirmed swing, not merely travel `displacement_atr` ATR. This is "
            "the contested rule and the engine's biggest ICT departure. It ships "
            "OFF, and the reason is the same one every gate here answers to: the "
            "figures usually quoted to justify requiring it (52% against 65-68% "
            "on 2,400 setups) are untraceable, so neither camp has evidence. On "
            "by request, measured like everything else."
        ),
    )
    structure_break_bars: int = Field(
        default=5,
        ge=1,
        le=50,
        description=(
            "Bars after the block candle in which the qualifying break must "
            "happen. Defaults to the same window the size test uses, so turning "
            "the structural test on changes the TEST and not the window."
        ),
    )
    structure_n: int = Field(
        default=5,
        ge=1,
        le=100,
        description=(
            "Fractal width of the swings the break is tested against. 5 is the "
            "internal-structure default in the most-installed public "
            "codification; no primary source publishes a number."
        ),
    )

    show_broken: bool = False
    show_mitigated: bool = True
    max_zones_per_side: int = Field(default=6, ge=0, le=100)


class StructureParams(ParamBlock):
    """Knobs for the structure overlay. Off unless the caller asks for it.

    Two widths on purpose. ICT reads structure at two scales and treats the small
    one as subordinate to the large one, and this engine has run two widths side
    by side in the measurement harness without ever crossing them. Drawing both
    with `aligned_with_swing` filled in is that crossing.
    """


    swing_n: int = Field(
        default=50,
        ge=1,
        le=200,
        description=(
            "Fractal width of the major structure. 50 is the swing default in "
            "the most-installed public codification of these ideas; the "
            "measurement harness pinned 2 and 25 rather than sweeping, because "
            "no primary source publishes an N and sweeping it would be choosing "
            "the answer."
        ),
    )
    internal_n: int = Field(
        default=5,
        ge=1,
        le=200,
        description="Fractal width of the minor structure. 5, same source as swing_n.",
    )
    sweep_reversal_bars: int = Field(
        default=3,
        ge=1,
        le=50,
        description=(
            "Bars in which a swept level must be closed back inside for the "
            "sweep to be marked reversed. Reported, never required: the engine "
            "codes the taking of liquidity and the sources describe taking AND "
            "rejection, so the difference is measured rather than assumed away."
        ),
    )
    mss_window: int = Field(
        default=5,
        ge=1,
        le=200,
        description=(
            "Bars between a sweep and the opposite break for the pair to count "
            "as a Market Structure Shift. 5 and 20 were both tested in H9 and "
            "both were null; 5 is the tighter reading."
        ),
    )
    max_events: int = Field(
        default=40,
        ge=0,
        le=500,
        description=(
            "Newest events kept, for readability. 0 means no cap, and any "
            "measurement MUST pass 0: a recency cap silently confines a sample "
            "to the tail of the history, which has already cost this project one "
            "full round of calibration."
        ),
    )


class SessionParams(ParamBlock):
    """Which parts of the New York cycle grid to draw. Nothing, by default.

    Two separate lists rather than one switch, because they answer different
    questions and cost different amounts. A true open is one line per cycle and
    is the object that appears on 100% of the owner's own charts. Quarter boxes
    are four regions per cycle and get dense fast: a month of `micro` quarters
    is nearly two thousand objects, which is why the cap below exists.
    """

    quarters: list[str] = Field(
        default_factory=list,
        description=(
            "Degrees to divide into quarters: year, month, week, day, session, "
            "micro, nano, quadrennial. Empty draws none."
        ),
    )
    true_opens: list[str] = Field(
        default_factory=list,
        description=(
            "Degrees to take the true open of. Empty draws none. `quadrennial` "
            "is available here and is NOT in the quarter-box list's own six: it "
            "is the four-year cycle whose Q2 is the United States presidential "
            "election year."
        ),
    )
    approximate_true_opens: bool = Field(
        default=False,
        description=(
            "Allow a true open to be read from the first bar AFTER its boundary "
            "when no bar opened on it, flagged as approximate and drawn dashed. "
            "Off by default, because turning it on changes what a drawn line "
            "means and every measurement in this project was taken under the "
            "strict rule.\n\n"
            "It exists because the strict rule is structurally unsatisfiable at "
            "the coarsest degree: the quadrennial Q2 boundary is 1 January, the "
            "market is shut on 1 January every year, and on ten years of hourly "
            "broker gold that degree therefore produced no level at all. With "
            "this on it produces two, at 19 and 18 hours past their boundaries. "
            "The reach is bounded at 120 hours OR one bar of the chart being "
            "drawn, whichever is larger. 120 comes from the longest real closure "
            "in the feed (96 hours, the Christmas and New Year weeks); the bar "
            "interval is in it because a weekly bar opens once every 168 hours, "
            "so on a coarse chart a boundary can sit five days from the next open "
            "with the market never having shut. Which boundaries produce a level "
            "is a fact about the clock, so hourly and weekly now agree on the "
            "set - 2 quadrennial and 10 year - and differ only in the lag."
        ),
    )
    max_quarters: int = Field(
        default=200,
        ge=0,
        le=5000,
        description=(
            "Newest quarters kept, for readability. 0 means no cap, and any "
            "measurement must pass 0 - a recency cap silently confines a sample "
            "to the tail of the history, which has already cost this project "
            "one full round of calibration."
        ),
    )


class DFRParams(ParamBlock):
    """The defining range: Q1 split in thirds, first third discarded.

    SINGLE-SOURCED AND UNVERIFIED, which is why it is off by default and why
    this docstring says so before it says anything else. The thirds rule reached
    this project from one description of a closed-source indicator, and it has
    never been checked against the course material it came from, let alone
    against outcomes. `quarterly.py` carries the same warning at the function.
    """

    degrees: list[str] = Field(
        default_factory=list,
        description=(
            "Cycle degrees to draw the defining range at. Empty draws none and "
            "costs nothing. Reads the bars already fetched, so no degree here "
            "costs a provider call."
        ),
    )
    extensions: list[float] = Field(
        default_factory=lambda: [-0.5, -1.0],
        description=(
            "Multiples of the range projected past it. -0.5 and -1 are the "
            "source's own numbers, quoted as it writes them: extensions that "
            "'often function as manipulation or reversal targets'. "
            "THE SOURCE GIVES NO DIRECTION for them, so each multiple is drawn "
            "on BOTH sides and each level says which side it is on. Picking one "
            "would be inventing the half of the rule nobody published. Empty "
            "draws the band and its equilibrium and no projections."
        ),
    )
    equilibrium: bool = Field(
        default=True,
        description=(
            "The 50% line. The source calls it optional and names it as part of "
            "the object; it shipped missing entirely until 2026-08-20, so a "
            "reader had to halve two numbers by eye off a panel."
        ),
    )
    max_ranges: int = Field(
        default=4,
        ge=0,
        le=500,
        description=(
            "Newest bands drawn, for readability. FOUR and not twenty, because "
            "this cap multiplies: every band carries its own extension levels, "
            "so two multiples on both sides is five objects per band and twenty "
            "bands would put a hundred lines on a chart whose ink budget was "
            "already measured as crowded at a third coverage. 0 draws them all, "
            "and any measurement must pass 0 - a recency cap silently confines a "
            "sample to the tail of the history."
        ),
    )


class LiquidityParams(ParamBlock):
    """Named previous-period levels, plus the dealing range read as ERL and IRL."""

    periods: list[str] = Field(
        default_factory=lambda: ["day", "week"],
        description="day, week, friday, monday. Empty draws none.",
    )
    boundary: str = Field(
        default="cycle",
        description=(
            "`cycle` opens the day at 18:00 New York, which is the grid every "
            "other object here is drawn on and is also the CME open; `midnight` "
            "is the calendar day. This is a JUDGEMENT, not a citation - no source "
            "says which one his own PDH is read on - and the two give different "
            "numbers on identical bars, so both stay reachable."
        ),
    )
    range_liquidity: bool = Field(
        default=False,
        description="ERL and IRL off the dealing range. Internal levels come from the drawn zones.",
    )
    range_frame: bool = Field(
        default=False,
        description=(
            "Draw the dealing range on the CHART: both extremes, the 50% "
            "equilibrium and the two quartile boundaries. The range has always "
            "been computed and stamped on every box as `dealing_range_pos`, and "
            "it only ever reached a side panel as two numbers - so the frame a "
            "reader's zones were being judged against was the one thing they "
            "could not see. The quartiles use the SAME constants `app/deduce.py` "
            "tests against, so the drawn boundary and the printed verdict cannot "
            "disagree. Off by default like every other level source here: an "
            "overlay that switched itself on would spend an ink budget somebody "
            "else had accounted for."
        ),
    )
    equal_levels: bool = Field(
        default=False,
        description=(
            "Relative equal highs and lows, drawn as REQH and REQL with their "
            "touch count. Two or more swings that printed at almost the same "
            "price, where stops rest. THE CHECKLIST HAS BEEN ASKING FOR THIS "
            "OBJECT: the practitioner rule quoted in `models/cycle.py` names it "
            "beside the ones the engine does draw - 'FVG/OB/REQL/REQH/CISD "
            "semuanya harus dalam premium kalo mau sell' - and nothing drew it. "
            "Fidelity only: nothing here has been measured against outcomes, and "
            "there is no score field for one to be read as."
        ),
    )
    equal_tolerance_atr: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description=(
            "How far apart two swings may be and still count as equal, in ATR. "
            "0.1 is the figure the surveyed open-source implementations use, "
            "adopted with its provenance rather than invented - and nothing here "
            "has measured whether it separates shelves that matter. The other "
            "rule in circulation, a fraction of the LOADED WINDOW's range, is "
            "refused outright: it makes the tolerance depend on how many bars a "
            "reader happened to pick, so the same two swings stop being equal "
            "when the Bars picker changes and no candle has moved."
        ),
    )
    draw_candidates: bool = Field(
        default=False,
        description=(
            "The untaken levels above and below the last price. Reported in BOTH "
            "directions and never resolved to one: naming the draw is a forecast."
        ),
    )
    max_levels: int = Field(
        default=16, ge=0, le=500, description="Newest levels drawn. 0 draws them all."
    )


class ProjectionParams(ParamBlock):
    """Standard deviation projections off a named session range."""

    sessions: list[str] = Field(
        default_factory=lambda: ["london"],
        description="Which session ranges to project from. asia, london.",
    )
    direction: int = Field(
        default=0,
        ge=-1,
        le=1,
        description=(
            "+1 projects upward, -1 downward, and 0 draws BOTH. Zero is the "
            "default deliberately: on his own charts the direction is read from "
            "where price went after the range, which is hindsight, and this "
            "engine will not supply a direction it cannot know. Drawing both is "
            "the honest shape, at the cost of twice the ink."
        ),
    )
    levels: list[float] = Field(
        default_factory=lambda: [0.0, -0.5, -1.0, -1.5, 2.0, 2.5],
        description=(
            "His own labels, transcribed from image 27 and NOT a citation of any "
            "rule. The set skips +0.5 and +1 because those are the range's "
            "midpoint and far edge, already drawn as the box."
        ),
    )


class NewsParams(ParamBlock):
    """The economic calendar. The SECOND block that can make a network call.

    The checklist was the only one until now, and the difference matters to a
    caller: everything else here reads bars that were already fetched, while
    this reaches a third party whose feed can be down. A failure is reported in
    that feed's own terms rather than as an empty chart.
    """

    impacts: list[str] = Field(
        default_factory=lambda: ["High"],
        description=(
            "Which impact labels to draw. High only by default, because the "
            "sampled week held 75 Low rows against 8 High ones and drawing all "
            "98 would bury the chart. A DISPLAY choice: the label is the feed's, "
            "and nothing here has measured that High matters more."
        ),
    )
    currencies: list[str] = Field(
        default_factory=list,
        description=(
            "Currency codes to keep, e.g. USD. Empty keeps every currency, which "
            "is the honest default for a cross-asset chart - gold answers to USD "
            "releases, and a trader watching DXY wants more than one."
        ),
    )


class PoolParams(ParamBlock):
    """Session extremes as candidate targets. No extra provider call."""

    sessions: list[str] = Field(
        default_factory=lambda: ["asia", "london"],
        description="asia is 19:00-00:00 New York, london is 02:00-05:00. Empty draws none.",
    )
    max_pools: int = Field(
        default=12,
        ge=0,
        le=1000,
        description=(
            "Newest pools drawn, a DISPLAY limit like `SessionParams.max_quarters`. "
            "Two sessions over 50 days of hourly gold is 212 named rays, which is "
            "no longer a chart. Recency is the right axis here because that is what "
            "the fact is worth: a London high taken this morning kills an idea and "
            "the same fact from seven weeks ago does not. At equal age a standing "
            "pool outranks a taken one, since only a standing pool is still a "
            "target. 0 draws them all, and a measurement must pass 0."
        ),
    )


class GapParams(ParamBlock):
    """Opening gaps, and the levels between them.

    Costs no extra provider call: both are read off the bars already fetched. Off
    by default only because they are one more layer of ink on a chart the ink
    budget already measured as crowded.
    """

    keep: int = Field(
        default=5,
        ge=0,
        le=60,
        description=(
            "Newest gaps retained before the levels are paired. ICT says a minimum "
            "of four and prefers five; a widely used third-party port keeps ten. "
            "The default of 5 is a CHOICE and not a measured result. This knob does "
            "not merely trim the picture: dropping a gap DELETES a level and "
            "re-pairs its neighbours, so any two values give different level sets. "
            "0 keeps everything, and a measurement must pass 0."
        ),
    )
    tier_keep: int = Field(
        default=3,
        ge=0,
        le=20,
        description=(
            "Gaps per kind behind each tier zone. THREE IS THE OWNER'S OWN "
            "NUMBER, confirmed directly rather than reverse-engineered, which "
            "is why it is not restated here as a guess."
        ),
    )
    tier_reduction: Literal["envelope", "ce_span", "newest", "eh_span"] = Field(
        default="envelope",
        description=(
            "How those gaps become one zone: envelope, ce_span, newest or "
            "eh_span. UNRESOLVED - none of the four reproduces the reference "
            "indicator's published table, and `envelope` is the plainest "
            "reading rather than a match. See `TierHorizon`."
        ),
    )
    event_horizons: bool = Field(
        default=True,
        description="The levels between adjacent gaps. The gaps themselves are drawn either way.",
    )


class CISDParams(ParamBlock):
    """Change in state of delivery, off the bars already fetched.

    Both knobs change the ANSWER rather than the presentation, and neither was
    measured against anything.
    """

    min_run: int = Field(
        default=2,
        ge=1,
        le=20,
        description=(
            "Shortest delivery run allowed to arm a level. 1 makes almost every "
            "bar a CISD, so 2 is the floor that excludes the degenerate case - a "
            "chosen number, not a measured one. Runs shorter than this still exist "
            "and are still reported; the floor gates arming, not existence."
        ),
    )
    interrupt_tolerance: int = Field(
        default=0,
        ge=0,
        le=5,
        description=(
            "Opposing closes a run absorbs before it ends. 0 is the literal reading "
            "of 'consecutive'. Raising it merges runs, which moves both the level "
            "and the bar the event lands on, so the count of CISDs is not stable "
            "under it."
        ),
    )
    max_events: int = Field(
        default=40,
        ge=0,
        le=2000,
        description=(
            "Newest events drawn, a DISPLAY limit matching "
            "`StructureParams.max_events` because these are the same class of "
            "object: an event stamped on a bar. At the shipped floor, 1200 bars of "
            "hourly gold produce 131 of them, which is one on every ninth bar. 0 "
            "draws them all, and a measurement must pass 0."
        ),
    )


class ChecklistParams(ParamBlock):
    """The owner's own pre-trade checklist, computed rather than asserted.

    OFF BY DEFAULT, and unlike every other block here that is a COST decision as
    much as a caution. The zone detectors read the bars already fetched; these do
    not. Bias needs one fetch per timeframe at a bar count high enough for
    structure to exist, and SSMT needs one fetch per correlated instrument. A
    fully specified request can therefore turn one provider call into eight, and
    the response says how many it made rather than leaving that invisible.
    """

    degree: str = Field(
        default="day",
        description="Cycle degree the DFR, profile and manipulation are read at",
    )
    discount_anchor: str = Field(
        default="parent_cycle",
        description=(
            "Which range the 'In discount?' item is measured against: "
            "parent_cycle is the running cycle one degree above `degree`, "
            "parent_previous the last closed one, previous_quarter the last "
            "provably closed quarter of that grid. All three are computed and "
            "returned regardless; this only picks which one is `chosen`."
        ),
    )
    chain_degrees: list[str] = Field(
        default_factory=list,
        description=(
            "Degrees to read the quarter chain at, outermost first. His examples "
            "are three digits but never name the degrees, so there is no default "
            "worth inventing. Empty skips it and costs nothing."
        ),
    )
    bias_timeframes: list[str] = Field(
        default_factory=list,
        description=(
            "Timeframes to read the structural bias on, his order being 1d, 4h, "
            "1h, 15m. Empty skips it, and skipping it costs nothing. Each entry "
            "is one extra provider call."
        ),
    )
    bias_bars: int = Field(
        default=400,
        ge=50,
        le=5000,
        description=(
            "Bars fetched per bias timeframe. 400 is not a doctrine number: it "
            "is enough for the shipped swing width to confirm pivots on a daily "
            "series, where 6 bars is where a break becomes POSSIBLE and 102 is "
            "where the shipped width can see one. Stated as ours."
        ),
    )
    ssmt_symbols: list[str] = Field(
        default_factory=list,
        description=(
            "Instruments to read SSMT across, the chart's own symbol included "
            "automatically. Empty skips it. They must be correlated for the "
            "reading to mean anything - see SSMTHit for the measured rates."
        ),
    )
    ssmt_degrees: list[str] = Field(
        default_factory=list,
        description=(
            "One degree per stage. A stage IS a degree, so two stages is two "
            "entries, and nothing here requires two: the same source ships a "
            "one-SSMT model beside the two-stage one."
        ),
    )
    ssmt_max: int = Field(
        default=40,
        ge=0,
        le=2000,
        description=(
            "Newest divergences DRAWN, for readability. Measured on the first "
            "run of the layer: XAUUSD 1h, 2000 bars, two partners and two "
            "degrees produced 1312 segments, which is not a chart. The count is "
            "multiplicative by construction - partners times degrees times two "
            "sides - so this fills up faster than any other overlay's cap.\n\n"
            "A DISPLAY LIMIT and nothing else. It never changes which "
            "divergences exist, only how many are returned, and the checklist's "
            "own SSMT count is taken before it. 0 draws them all, and any "
            "measurement must pass 0 - a recency cap silently confines a sample "
            "to the tail of the history, which has already cost this project "
            "one full round of calibration."
        ),
    )
    ssmt_provider: str | None = Field(
        default=None,
        description=(
            "Source for the SSMT basket, INCLUDING the chart's own symbol in "
            "it. None means the chart's source, which is the old behaviour. "
            "This exists because the venue you trade and the complex you read "
            "divergence across need not be the same one, and forcing them to "
            "be makes one of the two wrong. Charting the local MT5 terminal "
            "puts gold on the broker's spot CFD - correct, it is what gets "
            "filled - and would then read silver and copper as that broker's "
            "CFDs too. Set this to 'yahoo' and the whole basket is the COMEX "
            "complex instead: GC=F, SI=F, HG=F, PL=F, PA=F, which is what "
            "TradingView draws as COMEX:GC1! and what the divergence doctrine "
            "was written on. THE BASKET IS ONE VENUE EITHER WAY, and that is "
            "the point: gold from one venue against silver from another gives "
            "divergences that are an artefact of two session calendars, which "
            "is the exact failure aligned.py refuses to paper over."
        ),
    )


class ChartGapParams(ParamBlock):
    """Breakaway and measuring gaps. No knobs: the detection constants are
    doctrine and live in `app/chart_gaps.py`, not on the wire, because nothing
    has measured a better value for any of them."""


class WyckoffParams(ParamBlock):
    """Wyckoff phase readings. One knob, the rolling trading-range width."""

    lookback: int = Field(
        default=20,
        ge=5,
        le=200,
        description=(
            "Bars in the rolling trading range a phase is read against. 20 is a "
            "chosen number, not a measured one - the Wyckoff method names no "
            "window, so this is stated rather than fitted."
        ),
    )


class PSPParams(ParamBlock):
    """Precision swing points. One knob, how many of the newest to draw."""

    max_events: int = Field(
        default=40,
        ge=0,
        le=500,
        description=(
            "Newest PSP events drawn, 0 for no cap. The window and the level "
            "are NOT knobs: three bars and the open of the bar three back are "
            "the owner's own numbers, and a slider on them would invite the "
            "search this repo measures against."
        ),
    )


class ExpectationParams(ParamBlock):
    """The expectation overlay. Reads a precomputed table, so it costs no
    provider call and carries one knob.

    The fan is a MEASUREMENT and is on with the layer. `show_path` adds the mean
    expected path as a single line, and it is OFF by default because a lone line
    reads as a forecast, and this engine does not forecast - it draws the average
    historical trajectory, labelled as such, and only when the reader asks.
    """

    show_path: bool = Field(
        default=False,
        description=(
            "Draw the median expected path as a single line in addition to the "
            "fan. Off by default and kept separate: a line reads as a forecast, "
            "and this engine does not forecast. It is the average historical "
            "trajectory, not a prediction."
        ),
    )
