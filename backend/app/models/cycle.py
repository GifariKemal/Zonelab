"""Quarter chains, true opens, CISD, and the checklist's own inputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .structure import TrueOpenLevel


class QuarterChain(BaseModel):
    """Which quarter of each nested degree a bar sits in, as his three-digit chain.

    A FACT ABOUT THE CLOCK, and that part is safe. `in_his_list` says only that
    the chain is one of the ten he wrote down; it is NOT a probability, and the
    field is named so it cannot be read as one.

    NOBODY HAS MEASURED whether the listed chains behave differently from the
    unlisted ones. Ten of the 64 three-digit chains is 15.6%, so landing in the
    list is not rare, and the base rate belongs beside the flag every time.

    > And the chain is only readable at all on a timeframe that divides the
    > grid. Measured: on 1-hour bars only 28 to 30 of the 64 chains can ever
    > occur, and SIX of his ten - 114, 141, 144, 414, 441 and 444 - are
    > structurally unreachable rather than merely rare, because a micro quarter
    > is 1350 seconds and an hour is 3600. Any study of these must sample at
    > 22.5 minutes or finer, or it is measuring the bar interval.
    """

    at: int
    degrees: list[str]
    quarters: list[int]
    text: str = Field(description='Hyphenated, as he writes it: "2-1-3"')
    compact: str = Field(description='As he labels charts: "213"')
    in_his_list: bool | None = Field(
        default=None, description="None when the chain is not three degrees long"
    )
    base_rate: float = Field(
        default=0.15625, description="Ten of 64. Quoted with the flag, always."
    )


class OpenStack(BaseModel):
    """How many true opens price sits above, and how many below.

    His stated precondition is that at least two true opens must point the same
    way before he acts. This counts them and says which; it does NOT say what to
    do about the answer, and nothing here has been measured against outcomes.
    """

    price: float
    above: list[TrueOpenLevel] = Field(default_factory=list)
    below: list[TrueOpenLevel] = Field(default_factory=list)


class CISDEvent(BaseModel):
    """A close beyond the OPENING price of the last opposing delivery run.

    A delivery run is the consecutive stretch of candles closing one way, and the
    level is the open of the FIRST candle in it - not the last, which is the usual
    way this construct is coded wrong.

    First construct in this engine keyed to a candle's OPEN rather than its high or
    low, and that turned out to matter more than expected. On 495 shared 15m bars
    of two gold feeds the opens disagreed on direction 3.84% of the time, which is
    no worse than the extremes the other detectors use (3.04% on highs, 4.45% on
    lows). But one flipped sign splits or merges a whole RUN, so that 3.84% became
    a **29% disagreement about which bars carry a CISD** - roughly eightfold
    amplification. When the two feeds do agree on the bar they almost always agree
    on the anchor (47 of 49), so the failure mode is whole events existing on one
    feed only rather than levels drifting.

    Reports that a level was closed through, and nothing more. Predictive value is
    UNMEASURED: no published hit rate exists, and this project has had twelve
    pre-registered directional hypotheses fail, market structure three times.
    """

    time: int = Field(description="The bar that closed beyond, and when it became knowable")
    direction: int = Field(
        description="+1 closed above a down-run's open, -1 closed below an up-run's"
    )
    level: float = Field(description="The open of the FIRST candle of the run")
    run_from: int = Field(description="Open time of that first candle")
    run_to: int = Field(description="Open time of the run's last conforming candle")
    run_length: int = Field(description="Conforming candles only; absorbed interruptions excluded")


class DegreeBias(BaseModel):
    """The structural bias at one timeframe, and why it is what it is."""

    timeframe: str
    bias: int | None = Field(
        description=(
            "-1, 0 or +1, and None means UNKNOWN. The three are different facts "
            "and collapsing them is the whole trap here: 0 is 'no break has "
            "happened yet', None is 'this timeframe did not have enough bars to "
            "say', and neither may be counted as agreement with anything."
        )
    )
    bars: int
    needs: int = Field(description="Bars this degree needed before a break was possible")
    last_break: str | None = Field(
        default=None, description="BOS or CHoCH. Sweeps are excluded; a sweep is not a break."
    )
    reversal_confirmed: bool | None = Field(
        default=None,
        description=(
            "True on a CHoCH, False on a BOS, None when no break has happened. "
            "This is the owner's own first question on the daily."
        ),
    )
    reason: str | None = Field(default=None, description="Set only when the bias is UNKNOWN")


class BiasAlignment(BaseModel):
    """Do the timeframes agree, which is the owner's continuation precondition.

    His rule, verbatim: read the Daily, ask whether a reversal is confirmed, and
    if not assume continuation; then require H4, H1 and M15 to agree before
    taking a continuation trade.

    Reported, never scored. Twelve pre-registered directional hypotheses have
    failed in this project, and market structure specifically was tested three
    times (H6, H9, H11) and was null every time. This says whether HIS rule is
    satisfied. It is not the engine forming a view, and there is deliberately no
    field here called signal, confidence or probability.
    """

    degrees: list[DegreeBias]
    aligned: bool
    direction: int | None = Field(description="The shared bias when aligned, else None")
    disagreeing: list[str] = Field(
        default_factory=list, description="The timeframes that broke the alignment"
    )


class DefiningRange(BaseModel):
    """The DFR: Q1 split in thirds, first third discarded, extremes of the rest.

    Bucko Trades' rule, and it is shipped as his. It is NOT a reimplementation of
    the closed-source `Quarterly DFR [Dango]` indicator, whose own description
    says its logic is proprietary and invokes momentum, volatility and volume
    that the thirds rule never touches. The rule also reached this project
    single-sourced, so it must be verified against the course material before any
    number is scored on it.
    """

    degree: str
    cycle_start: int
    time_from: int = Field(description="Start of the kept two thirds of Q1")
    time_to: int = Field(description="Q1's close, which is also when this becomes knowable")
    high: float
    low: float
    equilibrium: float = Field(
        description=(
            "Midpoint of the range. The source states it as part of the object - "
            "Bucko's own description says an optional 50% equilibrium line marks "
            "the midpoint - and it shipped without one, so a reader had to do the "
            "arithmetic by eye off two numbers on a panel. It is the same "
            "quantity `OpeningGap.ce` already carries under ICT's name for it, "
            "and it is derived, never measured: a range with a high and a low "
            "has a midpoint whether or not anyone drew it. NOTHING here says "
            "price does anything at this level."
        )
    )


class CycleProfile(BaseModel):
    """AMDX or XAMD, read off Q1 after Q1 has closed.

    Q1 contained inside the previous cycle's Q4 range is AMDX; Q1 breaking
    outside it is XAMD. Nobody claims this can be known before Q1 closes, so a
    cycle whose Q1 is still forming has no profile rather than a guessed one.
    """

    degree: str
    cycle_start: int
    name: Literal["AMDX", "XAMD"]
    manipulation: Literal["Q2", "Q3"] = Field(
        description="Which quarter is the manipulation phase under this profile"
    )
    knowable_at: int


class ManipulationEvent(BaseModel):
    """Manipulation, which is a CONJUNCTION and not either half alone.

    The time half is the profile's manipulation quarter; the price half is
    liquidity taken and rejected, which is the SWEEP this engine already emits.
    A sweep in the wrong quarter is not manipulation, and the right quarter with
    no sweep is not either.
    """

    degree: str
    cycle_start: int
    profile: Literal["AMDX", "XAMD"]
    quarter_label: Literal["Q1", "Q2", "Q3", "Q4"]
    time_from: int
    time_to: int
    level: float = Field(
        description=(
            "The previous quarter's extreme that the wick took. A stated choice: "
            "three candidate levels appear in the sources and none is ranked, and "
            "the previous quarter's extreme keeps this consistent with the SSMT "
            "anchor. The other two are the previous cycle's extreme and the true "
            "open."
        )
    )
    swing_level: float = Field(description="The confirmed swing the sweep itself fired on")
    direction: int = Field(description="+1 wick above, -1 below. Not a forecast.")
    sweep_time: int


class SSMTHit(BaseModel):
    """Two correlated instruments disagreeing about the previous quarter's extreme.

    Knowable only at `knowable_at`, the close of the second quarter: a quarter's
    extreme is not settled until that quarter has ended.

    HOW OFTEN THIS FIRES DEPENDS ENTIRELY ON THE PAIR, and a reader must know it
    before treating one as scarce. Measured at the day degree on 2000 hourly
    bars: gold against silver 14.9%, platinum 21.0%, NASDAQ 36.0%, BTC 43.3%,
    DXY 59.5%. The rate tracks correlation, which is the sanity check that this
    measures what it claims - and it means an inversely correlated instrument
    like DXY disagrees on nearly every quarter by construction, so pairing one
    with a same-direction divergence rule is a category error rather than a rich
    source of setups.
    """

    degree: str
    side: Literal["high", "low"]
    took: str = Field(description="Instrument that took the previous quarter's extreme")
    failed: str = Field(description="Instrument that did not")
    # The quarter's own window was carried here as `quarter_from`/`quarter_to`
    # and was read by nothing: not the frontend, not a harness, not a test. It
    # was written on every hit and consumed nowhere, which is the worst kind of
    # field - it looks like provenance and proves nothing, because no reader ever
    # checked it. `knowable_at` is the timestamp that IS load-bearing here, and
    # the quarter is recoverable from it through the same grid that produced it.
    knowable_at: int
    took_prior: float
    took_now: float
    failed_prior: float
    failed_now: float


class SSMTDivergence(BaseModel):
    """One divergence, positioned so it can be DRAWN on the chart's own price.

    `SSMTHit` is the same event as a reading; this is the same event as a shape.
    They are separate because they answer different questions and a reader who
    saw one object would take the other for a duplicate: the hit says WHAT was
    read and carries all four prices as evidence, this says WHERE to put a line
    on a chart of one instrument.

    The line runs from the chart symbol's extreme in the prior quarter to its
    extreme in the current one - the two prices the comparison was actually made
    between - which is how the reference charts annotate it: a segment with a
    tag naming the degree and the partner, `dc - Platinum`.

    ONLY THE CHART'S OWN SYMBOL IS POSITIONED. The partner's two prices ride
    along as `partner_prior` and `partner_now` because they are the other half
    of the evidence, but they belong to a different instrument's price scale and
    must never be plotted on this one. A silver price drawn on a gold axis is
    the most confidently wrong line a chart can carry.
    """

    degree: str
    side: Literal["high", "low"]
    partner: str = Field(description="The other instrument in the pair")
    self_took: bool = Field(
        description=(
            "True when the CHART's symbol is the one that took the previous "
            "quarter's extreme and the partner failed; False when it is the "
            "other way round. This is the whole direction of the reading and "
            "the label is meaningless without it."
        )
    )
    time_from: int = Field(description="Bar of the chart symbol's prior extreme")
    price_from: float
    time_to: int = Field(description="Bar of the chart symbol's current extreme")
    price_to: float
    partner_prior: float
    partner_now: float
    knowable_at: int = Field(
        description=(
            "Close of the second quarter, and the ONLY timestamp anything may "
            "gate on. The two bar times above are earlier by construction: they "
            "are where the extremes printed, not when the divergence could be "
            "read. Drawing the line back at `time_from` is correct; ACTING on "
            "it before `knowable_at` is hindsight."
        )
    )
    range_pos: float | None = Field(
        default=None,
        description=(
            "Where this divergence's own extreme sat in the dealing range "
            "knowable at the bar it printed on: 0 at the range low, 1 at the "
            "high. None when either side of the range had not confirmed yet - "
            "never a substituted 0.5.\n\n"
            "PRESENT BECAUSE THE READING IS INCOMPLETE WITHOUT IT, and that came "
            "from a practitioner rather than from this codebase: 'FVG/OB/REQL/"
            "REQH/CISD semuanya harus dalam premium kalo mau sell, harus dalam "
            "discount kalo mau buy', and then the part that makes a divergence "
            "outside those zones useful rather than void - 'kalo ssmt terjadi di "
            "luar premium/discount, itu bisa kita pake buat tentuin DOL'. A "
            "divergence with no position in the range cannot be read either "
            "way.\n\n"
            "REPORTED, NEVER SCORED, and the same warning `mark_dealing_range` "
            "carries applies here word for word: the raw range position looked "
            "like the strongest finding in this project until it was split by "
            "side, and then it was upward drift in the sample. There is no "
            "verdict field beside this one and there must not be."
        ),
    )


class DFRExtension(BaseModel):
    """One projected level off a defining range, and the multiple that made it.

    THE SOURCE GIVES MULTIPLES AND NOT A DIRECTION. Bucko's own description says
    extensions at -0.5 and -1 "often function as manipulation or reversal
    targets" and stops there: it does not say the range is projected up, down, or
    in the direction of some leg. So both sides are computed and each carries
    its own `side`, rather than one being picked and presented as the rule. The
    same choice the Q4 label makes when its source gives two readings.
    """

    multiple: float = Field(description="As the source writes it, so -0.5 and -1")
    side: Literal["above", "below"] = Field(
        description="Which side of the range this projection falls on"
    )
    price: float


class DefiningRangeBand(BaseModel):
    """The DFR as a SHAPE: the band, its midpoint, and its projections.

    `DefiningRange` in the checklist is the same object as a reading and carries
    no projections. This is the drawable one, and they are separate for the
    reason `SSMTHit` and `SSMTDivergence` are separate: a reader who saw one
    would take the other for a duplicate.

    Knowable at `time_to`, which is Q1's close - the range is not final until
    the window that defines it has ended, and `quarterly.defining_range` returns
    nothing at all before then.
    """

    degree: str
    cycle_start: int
    time_from: int
    time_to: int = Field(description="Q1's close, and when this becomes knowable")
    high: float
    low: float
    equilibrium: float
    extensions: list[DFRExtension] = Field(default_factory=list)
