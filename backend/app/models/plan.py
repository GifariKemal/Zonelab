"""Checklist verdict, cost table, lot sizing, and the trade plan."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .primitives import ZoneSide
from .liquidity import PremiumDiscount
from .cycle import (
    BiasAlignment,
    CycleProfile,
    DefiningRange,
    ManipulationEvent,
    OpenStack,
    QuarterChain,
    SSMTHit,
)


class ChecklistReport(BaseModel):
    """Every item answered, with the evidence, and nothing collapsed to a verdict.

    Deliberately NOT a single pass or fail. The items are separate claims with
    separate provenance and separate confidence, and reducing them to one boolean
    would hide which one is carrying the weight - and would present a checklist
    the owner ticks by hand as though the engine had validated it. Nothing here
    has been measured against outcomes.
    """

    degree: str
    dfr: DefiningRange | None = None
    profile: CycleProfile | None = None
    manipulation: ManipulationEvent | None = None
    discount: PremiumDiscount | None = Field(
        default=None,
        description=(
            "His third question, 'In discount?', and the one item that can answer "
            "itself three ways at once. Read `disagree` before quoting it."
        ),
    )
    chain: QuarterChain | None = Field(
        default=None,
        description="The quarter chain at the last bar. A clock fact, not a probability.",
    )
    stacked: OpenStack | None = Field(
        default=None,
        description="His two-true-opens-agreeing precondition, counted rather than judged.",
    )
    bias: BiasAlignment | None = None
    ssmt: list[SSMTHit] = Field(default_factory=list)
    notes: list[str] = Field(
        default_factory=list,
        description="Why an item is absent, when it is absent for a reason",
    )


class CostSpec(BaseModel):
    """What a round turn costs, in basis points of notional.

    Basis points rather than price units, because price units are not comparable
    across instruments: 0.30 is a wide gold spread and invisible on BTC.

    None means NOT MEASURED and never zero, the same rule `Candle.spread`
    follows. A plan that charged zero for an unknown cost would quietly restore
    the free-trading assumption these fields exist to remove - and the assumption
    is not academic here, because at the only gold commission schedule that could
    actually be retrieved the measured edge stops clearing its costs.
    """

    commission_bp: float | None = None
    slippage_bp: float | None = None
    spread_bp: float | None = Field(
        default=None,
        description=(
            "Used ONLY when the feed publishes no spread. A measured spread from "
            "the ticks always wins over an assumed constant."
        ),
    )
    carry_bp_per_night: float | None = Field(
        default=None,
        description=(
            "Swap plus any per-night administration fee, charged per rollover "
            "the position is held through, FOR THE SIDE THIS PLAN TAKES. "
            "Exness charges 200 USD per lot per night on XAUUSD held past 21:00 "
            "UTC, which is 4.5bp - larger than every other cost in this model "
            "combined. Read `carry_asymmetric` before comparing two plans on "
            "opposite sides: the number below is not the same for both."
        ),
    )
    carry_asymmetric: bool = Field(
        default=False,
        description=(
            "True when the venue charges the two sides differently and this "
            "plan's figure is therefore its own side's, not the instrument's. "
            "Measured on the connected Exness terminal 2026-08-20: XAUUSD "
            "swap_long is -541.4 points, which on a 100 ounce lot is -54.14 USD "
            "a night, or 1.20bp at gold 4500 - while swap_short is EXACTLY "
            "ZERO. Holding gold short overnight costs nothing there and holding "
            "it long is the largest recurring cost in the model. Charging both "
            "sides the same made every short look worse than it is and every "
            "long look better, which is the direction that flatters a demand "
            "zone - and on the day this was found, every zone near price was a "
            "demand zone. The asymmetry also FLIPS by venue rather than being a "
            "property of gold: IBKR, a real borrow, charges 1.29bp a day to "
            "borrow gold short and 0.028bp to store it long, which is the other "
            "way round from this CFD."
        ),
    )
    nights: int = Field(
        default=0,
        ge=0,
        le=30,
        description=(
            "Rollovers the plan assumes it crosses. 0 means intraday, which is "
            "an ASSUMPTION and is stated in the plan's warnings rather than "
            "hidden: a zone entry can sit unfilled for days, and each night "
            "carries the fee above."
        ),
    )
    source: str = Field(
        default="",
        description="Where these numbers came from, so a reader can check them",
    )


class LotSpec(BaseModel):
    """What the venue will actually accept as an order size.

    Every field here is a BROKER fact, not a market fact, and getting one wrong
    is not a rounding error. Standard Cent redefines a lot as 1 troy ounce
    rather than 100, so treating a cent balance as USD sizes every position 100x
    too large.

    `volume_step` is the one Exness documents as a field and never publishes a
    value for: its API exposes `volume_step` and rejects with
    TRADING_RULE_INVALID_VOLUME_STEP, but no page states the number for gold.
    0.01 is an INFERENCE from `volume_min`, which Exness does publish, and it is
    defaulted here so the code runs - it should be replaced by the live value
    from the terminal or the API rather than trusted.
    """

    contract_size: float = Field(
        default=100.0,
        gt=0.0,
        description="Units per lot. 100 troy ounces for XAUUSD; 1 on Standard Cent.",
    )
    volume_min: float = Field(default=0.01, gt=0.0)
    volume_max: float = Field(default=200.0, gt=0.0)
    volume_step: float = Field(
        default=0.01,
        gt=0.0,
        description="Inferred from volume_min, not published. Read it at runtime.",
    )
    commission_round_turn: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Per lot, both sides, in account currency. Exness charges both at "
            "OPEN: 0 on Standard/Cent/Pro, 7.00 on Raw Spread, 11.00 on Zero."
        ),
    )
    leverage: float = Field(
        default=2000.0,
        gt=0.0,
        description=(
            "Used only for the margin check. Exness steps this down by equity - "
            "1:2000 under 30k, 1:1000 to 100k, 1:500 above - and caps XAU at "
            "1:200 to 1:1000 inside a Higher Margin Requirement window."
        ),
    )


class TradePlan(BaseModel):
    """What a trade at one zone would look like, with no view on whether to take it.

    Every price here comes from geometry that has been validated to the pixel.
    The one thing this project could never validate - which way price will go -
    is represented by `direction_evidence`, which is always None. That field is
    a finding, not a gap waiting to be filled: Twelve pre-registered hypotheses
    failed to get a sign out of these drawings, and the last two failed in the
    direction OPPOSITE to their own doctrine.
    """

    zone_id: str
    side: ZoneSide = Field(
        description=(
            "Which side the zone is, NOT a recommendation. A plan on a demand "
            "zone is what a long would look like if you already had a reason."
        )
    )
    entry: float = Field(description="The proximal line, plus the spread if known")
    stop: float = Field(description="Beyond the distal by the stop buffer")
    target: float | None = Field(
        description=(
            "The nearest live opposing zone. None when there is no wall ahead, "
            "and None is left in place rather than substituted with a "
            "conventional R multiple, because a convention is not a reading."
        )
    )
    risk_per_unit: float
    reward_r: float | None
    units: float | None = Field(
        description="Position size, only when an account equity was supplied"
    )
    lots: float | None = Field(
        default=None,
        description=(
            "The size an order can actually carry: floored to the venue's step, "
            "clamped to its maximum. None when no equity was given, or when the "
            "trade is not placeable at all."
        ),
    )
    placeable: bool = Field(
        default=True,
        description=(
            "False when the size floors BELOW the venue's minimum. Rounding it "
            "up instead would risk more than the budget by construction, so the "
            "honest answer is that this account cannot take this trade."
        ),
    )
    realised_risk: float | None = Field(
        default=None,
        description=(
            "What the FLOORED size actually risks, including commission. Not the "
            "budget: one step is a large fraction of a small account's budget, "
            "so nominal and realised diverge sharply there and only the realised "
            "figure is true."
        ),
    )
    realised_risk_pct: float | None = None
    margin_required: float | None = Field(
        default=None,
        description="At the stated leverage. Zero when leverage is unlimited.",
    )

    age_bars: int
    departure_held_rate: float = Field(
        description=(
            "Measured survival of the cohort this zone belongs to, 0.858 above "
            "the 2 ATR gate and 0.644 below it. A COHORT RATE, not this trade's "
            "probability, and it excludes costs."
        )
    )
    age_held_rate: float = Field(
        description=(
            "Same kind of number for the age band. Do NOT multiply it with "
            "`departure_held_rate`: the two factors were shown to be entangled "
            "when age turned out to be the departure gate in disguise."
        )
    )
    spread_charged: float | None = Field(
        description=(
            "The spread actually charged into the entry fill, in price units. "
            "Two sources reach this field and the plan's warnings say which one "
            "applied: a spread MEASURED per bar by the feed, which only the "
            "Dukascopy tick source publishes, or a stated constant from the cost "
            "schedule. None means neither existed, so nothing was charged - and "
            "a reader who sees a number here must check the warning before "
            "treating it as a measurement."
        )
    )
    cost_charged: float | None = Field(
        default=None,
        description=(
            "Everything a round turn costs in price units: spread, commission, "
            "slippage, and carry for the nights assumed. None when no cost "
            "schedule could be established for this symbol. Until this field "
            "existed the plan charged the spread only, so the reward on screen "
            "was the frictionless one and the researched costs lived exclusively "
            "in the measurement harness."
        ),
    )
    cost_share_of_reward: float | None = Field(
        default=None,
        description=(
            "`cost_charged` as a fraction of the distance to target. The number "
            "that decides whether an edge survives: at the retrievable gold "
            "commission schedule costs took 20.5% of R and the out-of-sample "
            "walk-forward fell from 8 of 8 slices to 4 of 8."
        ),
    )
    carry_per_night: float | None = Field(
        default=None,
        description=(
            "Price units charged per rollover held. Reported separately because "
            "the number of nights is an assumption, not a measurement."
        ),
    )
    direction_evidence: None = Field(
        default=None,
        description=(
            "Always None. Kept as an explicit field so that a consumer asking "
            "'what says this will go up' gets an answer rather than silence."
        ),
    )
    warnings: list[str] = Field(default_factory=list)


class Note(BaseModel):
    """One thing the advisor can say, with the doc section that explains it."""

    topic: str
    text: str
    learn: str | None = Field(
        description=(
            "Anchor of the /docs section that teaches this, or None when the "
            "note is a warning specific to this zone rather than a concept."
        )
    )


class Advice(BaseModel):
    """Everything the advisor can say about one zone.

    The final note is always what CANNOT be known. That ordering is deliberate
    and is enforced by a test: a reader who stops early should still have read
    the honest sentences, and a reader who reads to the end cannot miss the one
    that matters most.
    """

    zone_id: str
    notes: list[Note]
