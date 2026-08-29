"""The request and response bodies of /api/draw."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import settings
from ..layers import DEFAULT_LAYERS
from .primitives import Candle
from .liquidity import DrawOnLiquidity, RangeLiquidityReport
from .zone import Drawing
from .params import (
    DFRParams,
    CISDParams,
    ChecklistParams,
    GapParams,
    ImbalanceParams,
    LiquidityParams,
    NewsParams,
    PoolParams,
    ProjectionParams,
    SessionParams,
    StructureParams,
    SupplyDemandParams,
)
from .plan import Advice, ChecklistReport, CostSpec, LotSpec, TradePlan


class DrawRequest(BaseModel):
    # A FIELD NAME THIS MODEL DOES NOT KNOW IS A 422, not a shrug.
    #
    # Found by being caught out by it: five providers were measured by sending
    # `source`, which this model has never had, and pydantic's default is to
    # ignore what it does not recognise. All five requests came back 200 carrying
    # Yahoo data, the default - identical prices, identical bar times, and
    # nothing anywhere saying the field had been dropped. The reading was wrong
    # and looked right, which is the worst way for an API to be wrong.
    #
    # Refusing is safe because the client sends exactly the fields below: the
    # layer parameter blocks it spreads into the body are keyed from
    # `/api/config`, which is generated from this same registry.
    #
    # THE NESTED BLOCKS ARE CLOSED TOO, and for a long time they were not. This
    # config only ever guarded the eight scalars at this level; the twelve
    # params blocks below inherited nothing and allowed extras, so the identical
    # defect lived one level down where the field names are - about seventy of
    # them, hand-copied into TypeScript. `supply_demand.departure_min_ATR` was a
    # 200 over a chart drawn on the default. They now inherit
    # `params.ParamBlock`, which carries this same line for the same reason.
    model_config = ConfigDict(extra="forbid")

    symbol: str = "XAUUSD"
    interval: str = "15m"
    # The ceiling tracks `settings.max_bars` instead of restating it. They were
    # two numbers for one rule and they drifted the moment the local terminal
    # arrived: `max_bars` went to 50,000 for the deep history MT5 can serve, and
    # this stayed at 5000, so the endpoint the chart actually calls rejected
    # anything past the old wall with a 422 while the setting said otherwise.
    # `get_candles` still clamps, so this bound is the request contract and that
    # one is the fetch's.
    bars: int = Field(default=500, ge=50, le=settings.max_bars)
    provider: str | None = None
    lot: LotSpec = Field(
        default_factory=LotSpec,
        description=(
            "Venue rules the size must obey. Defaults describe Exness XAUUSD on "
            "a standard account; `volume_step` in particular is inferred rather "
            "than published and should be replaced with the live value."
        ),
    )
    equity: float | None = Field(
        default=None,
        gt=0.0,
        description=(
            "Account size, used ONLY to turn a stop distance into a position "
            "size. Absent by default, and when it is absent the plan reports no "
            "size rather than assuming one - a made-up account is the fastest "
            "way to make a risk number look authoritative while meaning nothing."
        ),
    )
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
    costs: CostSpec | None = Field(
        default=None,
        description=(
            "Broker frictions to charge the plan. Absent means the engine looks "
            "the symbol up in its own researched table and says in the plan's "
            "warnings which row it used; a symbol with no row is charged nothing "
            "and the plan says THAT too."
        ),
    )
    broker: str = Field(
        default="",
        description=(
            "Name a researched broker profile from `app/costs.py` BROKERS, so "
            "the plan is priced at the venue the orders will actually fill on. "
            "Empty uses the generic per-instrument row.\n\n"
            "This existed for the measurement harness and was unreachable from "
            "the product, which meant the plans on screen were priced at a "
            "venue nobody here trades: the generic XAUUSD row carries a "
            "Dukascopy spread and an unverified commission, while the shipped "
            "`exness_raw` profile carries Exness's own published commission "
            "and its 4.545bp per-night administration fee - a figure larger "
            "than every other cost in the model combined. A chart that prices "
            "the wrong venue is not a smaller version of pricing the right one.\n\n"
            "Ignored when `costs` is supplied: a caller that states a schedule "
            "has stated it.\n\n"
            "VALIDATED against the table, and case-sensitively. It was not, and "
            "the failure was silent on a money path: `broker=\"nope\"` and "
            "`broker=\"EXNESS_ZERO\"` both fell through to the generic row and "
            "priced the overnight carry at 0.424 where `exness_raw` prices it "
            "at 2.434 - a 5.7x understatement, HTTP 200, and the advice text "
            "quoting the wrong figure with no hedge. Every other unknown "
            "identifier on this request already fails loudly: an unknown layer "
            "is a 422, an unknown provider or interval a 502."
        ),
    )
    layers: list[str] = Field(
        default_factory=lambda: list(DEFAULT_LAYERS),
        description=(
            "Every drawing to produce, by name, from `app/layers.py`. ONE list "
            "for detectors, overlays and the checklist alike - there used to be "
            "two mechanisms, a detector list and an `enabled` boolean inside each "
            "overlay's own params block, which meant the same intent had two "
            "spellings and the UI had to know which was which. Order here is "
            "ignored; the registry's own order is the draw order, and it is "
            "load-bearing."
        ),
    )
    supply_demand: SupplyDemandParams = Field(default_factory=SupplyDemandParams)
    imbalance: ImbalanceParams = Field(
        default_factory=ImbalanceParams,
        description=(
            "Shared by the fvg, order_block, ifvg and breaker detectors. The "
            "inversion pair reads the same geometry knobs as the pair it inverts, "
            "because an IFVG is an FVG plus one more event and inventing a second "
            "gap threshold for it would let the two populations drift apart."
        ),
    )
    checklist: ChecklistParams = Field(
        default_factory=ChecklistParams,
        description=(
            "The owner's pre-trade checklist. Off by default, and the only block "
            "here that can make extra provider calls."
        ),
    )
    session: SessionParams = Field(
        default_factory=SessionParams,
        description=(
            "The New York cycle grid. An overlay like `structure`, not a "
            "detector: it draws no boxes and is a fact about the clock rather "
            "than a reading of price."
        ),
    )
    dfr: DFRParams = Field(
        default_factory=DFRParams,
        description=(
            "The defining range, its 50% equilibrium and its projections. Its "
            "own block rather than a corner of `session`, because it asks a "
            "different question: the grid is a fact about the clock and this is "
            "a reading of the price inside one quarter of it. Single-sourced and "
            "never verified - see `DFRParams`."
        ),
    )
    structure: StructureParams = Field(
        default_factory=StructureParams,
        description=(
            "Swings, breaks and sweeps. Off by default, and it is an OVERLAY "
            "rather than a detector: it produces no boxes, so it does not belong "
            "in `detectors` and cannot be capped per side."
        ),
    )
    gaps: GapParams = Field(
        default_factory=GapParams,
        description=(
            "Opening gaps and the levels between them. An overlay: the bands have "
            "no side and nothing to cap per side."
        ),
    )
    cisd: CISDParams = Field(
        default_factory=CISDParams,
        description="Delivery-state changes. An overlay, for the same reason.",
    )
    news: NewsParams = Field(
        default_factory=NewsParams,
        description="Scheduled economic releases. An overlay, and it can make a network call.",
    )
    pools: PoolParams = Field(
        default_factory=PoolParams,
        description="Session extremes as candidate targets. An overlay.",
    )
    liquidity: LiquidityParams = Field(
        default_factory=LiquidityParams,
        description="Named previous-period levels, and the dealing range as ERL and IRL.",
    )
    projections: ProjectionParams = Field(
        default_factory=ProjectionParams,
        description="Deviation stacks off a session range. An overlay.",
    )


    @field_validator("broker")
    @classmethod
    def _known_broker(cls, value: str) -> str:
        """Reject a name the cost table does not carry.

        A membership test and nothing cleverer: `BROKERS` is already served by
        `/api/config`, so a client has the list, and any name outside it is a
        typo or a stale build rather than a request worth honouring quietly.
        Imported here rather than at module scope because `app.costs` imports
        the models.
        """
        if not value:
            return value
        from ..costs import BROKERS

        if value not in BROKERS:
            raise ValueError(
                f"unknown broker {value!r}; known profiles are "
                f"{', '.join(sorted(BROKERS))}. Leave it empty for the generic "
                "per-instrument row."
            )
        return value

class DrawResponse(BaseModel):
    symbol: str
    interval: str
    provider: str
    candles: list[Candle]
    drawing: Drawing
    plans: list[TradePlan] = Field(
        default_factory=list,
        description=(
            "One per drawn zone, in the same order. Geometry and risk only - "
            "every plan's `direction_evidence` is None, because nothing here "
            "predicts which way price goes."
        ),
    )
    advice: list[Advice] = Field(
        default_factory=list,
        description="One per drawn zone, in the same order as `plans`.",
    )
    draw_on_liquidity: DrawOnLiquidity | None = Field(
        default=None,
        description=(
            "Untaken liquidity on BOTH sides of the last price. Present only when "
            "asked for, and never resolved to a single direction."
        ),
    )
    range_liquidity: RangeLiquidityReport | None = Field(
        default=None, description="ERL and IRL, present only when asked for."
    )
    checklist: ChecklistReport | None = Field(
        default=None,
        description="Present only when the checklist was requested and enabled",
    )
    meta: dict[str, Any] = Field(default_factory=dict)
