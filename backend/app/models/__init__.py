"""Wire types shared by the API and the detection engine.

Every drawing the frontend renders is one of these objects. The engine never
returns a shape without the evidence that produced it: `anatomy` carries the bar
indices, `factors` carries the numeric score breakdown. That is what makes a
drawing auditable rather than decorative.
"""

from __future__ import annotations

from .primitives import (
    Candle,
    ZoneKind,
    ZoneSide,
    ZoneState,
    Anatomy,
    Refinement,
    Displacement,
)
from .structure import (
    SwingPoint,
    StructureEvent,
    SessionQuarter,
    TrueOpenLevel,
)
from .gaps import (
    OpeningGap,
    NewsEvent,
    GapStack,
    TierHorizon,
    EventHorizonLevel,
)
from .liquidity import (
    RangeReading,
    PremiumDiscount,
    LiquidityPool,
    NamedLevel,
    RangeLiquidityReport,
    DrawCandidate,
    DrawOnLiquidity,
    ProjectionLevel,
    RangeProjection,
)
from .cycle import (
    QuarterChain,
    OpenStack,
    CISDEvent,
    DegreeBias,
    BiasAlignment,
    DFRExtension,
    DefiningRange,
    DefiningRangeBand,
    CycleProfile,
    ManipulationEvent,
    SSMTDivergence,
    SSMTHit,
)
from .zone import (
    Zone,
    Drawing,
)
from .params import (
    DFRParams,
    SupplyDemandParams,
    ImbalanceParams,
    StructureParams,
    SessionParams,
    LiquidityParams,
    ProjectionParams,
    NewsParams,
    PoolParams,
    GapParams,
    CISDParams,
    ChecklistParams,
)
from .plan import (
    ChecklistReport,
    CostSpec,
    LotSpec,
    TradePlan,
    Note,
    Advice,
)
from .api import (
    DrawRequest,
    DrawResponse,
)

__all__ = [
    "Candle",
    "ZoneKind",
    "ZoneSide",
    "ZoneState",
    "Anatomy",
    "Refinement",
    "Displacement",
    "SwingPoint",
    "StructureEvent",
    "SessionQuarter",
    "TrueOpenLevel",
    "OpeningGap",
    "NewsEvent",
    "GapStack",
    "TierHorizon",
    "EventHorizonLevel",
    "RangeReading",
    "PremiumDiscount",
    "LiquidityPool",
    "NamedLevel",
    "RangeLiquidityReport",
    "DrawCandidate",
    "DrawOnLiquidity",
    "ProjectionLevel",
    "RangeProjection",
    "QuarterChain",
    "OpenStack",
    "CISDEvent",
    "DegreeBias",
    "BiasAlignment",
    "DFRExtension",
    "DFRParams",
    "DefiningRange",
    "DefiningRangeBand",
    "CycleProfile",
    "ManipulationEvent",
    "SSMTDivergence",
    "SSMTHit",
    "Zone",
    "Drawing",
    "SupplyDemandParams",
    "ImbalanceParams",
    "StructureParams",
    "SessionParams",
    "LiquidityParams",
    "ProjectionParams",
    "NewsParams",
    "PoolParams",
    "GapParams",
    "CISDParams",
    "ChecklistParams",
    "ChecklistReport",
    "CostSpec",
    "LotSpec",
    "TradePlan",
    "Note",
    "Advice",
    "DrawRequest",
    "DrawResponse",
]
