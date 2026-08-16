"""Zonelab API.

Four endpoints. `/api/draw` is the one that matters: it returns the candles and
the shapes drawn on them in a single response, so the chart can never render
zones computed from bars it is not showing.
"""

from __future__ import annotations

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .advisor import explain
from .config import settings
from .confluence import mark_nesting
from .detect import DETECTORS, PARAMS_FOR
from .indicators import wilder_atr
from .models import (
    Advice,
    Candle,
    DrawRequest,
    DrawResponse,
    Drawing,
    TradePlan,
    Zone,
    ZoneState,
)
from .plan import build as plan_for
from .profit_zone import mark_crowding, mark_profit_zones
from .refine import refine_zones
from .resample import resample
from .providers import (
    INTERVALS,
    PROVIDERS,
    SYMBOLS,
    ProviderError,
    availability,
    get_candles,
)

app = FastAPI(
    title="Zonelab API",
    version="0.1.0",
    summary="Automatic technical drawing engine for chart analysis",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/config")
async def config() -> dict:
    """Everything the UI needs to build its pickers, so the option lists cannot
    drift out of sync with what the backend actually supports."""
    live = await availability()
    return {
        "providers": [
            {
                "id": name,
                "available": live[name],
                "needs_key": name in {"twelvedata", "polygon"},
            }
            for name in PROVIDERS
        ],
        "default_provider": settings.default_provider,
        "symbols": [
            {"id": sid, "providers": sorted(vendors)} for sid, vendors in SYMBOLS.items()
        ],
        "intervals": list(INTERVALS),
        "detectors": sorted(DETECTORS),
    }


@app.get("/api/candles")
async def candles(
    symbol: str = "XAUUSD",
    interval: str = "15m",
    bars: int = 500,
    provider: str | None = None,
) -> dict[str, object]:
    rows, used = await _fetch(symbol, interval, bars, provider)
    return {"symbol": symbol, "interval": interval, "provider": used, "candles": rows}


@app.post("/api/draw", response_model=DrawResponse)
async def draw(request: DrawRequest) -> DrawResponse:
    rows, used = await _fetch(
        request.symbol, request.interval, request.bars, request.provider
    )

    unknown = set(request.detectors) - set(DETECTORS)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown detector(s): {', '.join(sorted(unknown))}",
        )

    drawing = Drawing()
    # Both numbers, always. Vendors cap a page at their own limit (Binance at
    # 1000, Yahoo by calendar range), and a short answer is otherwise
    # indistinguishable from a quiet market.
    meta: dict[str, object] = {
        "bars_requested": request.bars,
        "bars_returned": len(rows),
        "truncated_by_provider": len(rows) < request.bars,
    }

    if "supply_demand" in request.detectors:
        zones, stats = DETECTORS["supply_demand"](rows, request.supply_demand)
        for zone in zones:
            zone.timeframe = request.interval
        drawing.zones = zones
        meta["supply_demand"] = stats

        # The road ahead and the crowding stamp are already on these zones: the
        # detector runs both passes over its full population, before the display
        # cap, which is the only place they can be measured honestly.
        if request.htf:
            higher, htf_stats = _htf_zones(rows, request)
            mark_nesting(zones, higher)
            htf_stats["nested_local_zones"] = sum(1 for z in zones if z.nested_in)
            drawing.zones = higher + drawing.zones
            meta["htf"] = htf_stats

        # The road-ahead filter, and it is a filter on the road as it stands
        # NOW, not on whether the road was ever shut. `crowded_at` records the
        # history either way; a zone whose opposing wall has since been broken
        # is tradeable again and is not removed here.
        #
        # It runs BEFORE the other detectors append, because the road is a
        # supply-and-demand idea: a fair value gap has no opposing zone and no
        # profit zone, so sweeping it through this filter would be applying one
        # method's rule to another method's drawing.
        min_rr = request.supply_demand.min_profit_zone_rr
        if min_rr > 0:
            before = len(drawing.zones)
            drawing.zones = [
                z
                for z in drawing.zones
                if z.profit_zone_rr is None or z.profit_zone_rr >= min_rr
            ]
            stats["rejected_crowded"] = before - len(drawing.zones)

    # The other detectors. They append rather than replace, because a chart
    # showing a supply zone and a fair value gap at the same price is showing
    # two different claims about that price and collapsing them would hide one.
    #
    # Driven off the request and PARAMS_FOR, never off a literal list of names.
    # The validation above accepts anything in DETECTORS, so a hardcoded tuple
    # here let a newly registered detector pass validation and then never run -
    # a 200 with no zones and no error, the exact silent wrong answer this
    # project refuses to ship. Deduplicated because a name listed twice would
    # otherwise append its shapes twice.
    for name in dict.fromkeys(request.detectors):
        if name == "supply_demand":
            continue  # already run above, with its own HTF and road passes
        shapes, extra = DETECTORS[name](rows, getattr(request, PARAMS_FOR[name]))
        for shape in shapes:
            shape.timeframe = request.interval
        drawing.zones = drawing.zones + shapes
        meta[name] = extra

    # Plans and advice are computed for what SURVIVED to the screen, and that is
    # the one place in this codebase where working off the display-capped set is
    # correct rather than a bug: a plan is an offer to act on a box the user can
    # see. Every cross-zone measurement still happens inside the detector, before
    # the cap, exactly as before.
    plans, advice = _annotate(drawing.zones, rows, request)

    return DrawResponse(
        symbol=request.symbol,
        interval=request.interval,
        provider=used,
        candles=rows,
        drawing=drawing,
        plans=plans,
        advice=advice,
        meta=meta,
    )


def _annotate(
    zones: list[Zone], rows: list[Candle], request: DrawRequest
) -> tuple[list[TradePlan], list[Advice]]:
    """A trade plan and an explanation per zone, in the order they are drawn."""
    if not zones or not rows:
        return [], []

    high = np.array([c.high for c in rows], dtype=np.float64)
    low = np.array([c.low for c in rows], dtype=np.float64)
    close = np.array([c.close for c in rows], dtype=np.float64)
    atr = wilder_atr(high, low, close, request.supply_demand.atr_period)
    now = rows[-1].time
    # Only Dukascopy publishes a spread. When the feed does not, the plan says
    # so rather than charging zero and quietly flattering every reward figure.
    spread = rows[-1].spread

    plans: list[TradePlan] = []
    advice: list[Advice] = []
    for zone in zones:
        scale = float(atr[-1])
        plan = plan_for(
            zone, scale, now, INTERVALS[request.interval],
            equity=request.equity, spread=spread,
        )
        if plan is not None:
            plans.append(plan)
        advice.append(explain(zone, plan, zone.timeframe or request.interval))
    return plans, advice


def _htf_zones(rows: list[Candle], request: DrawRequest) -> tuple[list[Zone], dict]:
    """Zones from a higher timeframe, projected onto this chart.

    The zones are detected on aggregated bars and their lifecycle is replayed on
    those same bars, not on the chart's. That is deliberate: an H4 demand zone
    should not die because one M15 candle closed a few cents under it. The zone
    belongs to its own timeframe and is judged there.

    Every HTF bar used here is complete, because `resample` drops the forming
    one, so nothing drawn is a zone the trader could not already have seen.
    """
    if request.htf is None or request.htf not in INTERVALS:
        return [], {"error": f"unknown timeframe '{request.htf}'"}

    higher = resample(
        rows, request.htf, request.interval, request.session_offset_hours
    )
    if len(higher) < request.supply_demand.atr_period + 3:
        return [], {
            "bars": len(higher),
            "note": "not enough higher-timeframe bars in this window",
        }

    zones, stats = DETECTORS["supply_demand"](higher, request.supply_demand)

    # Refinement happens BEFORE the timeframe stamp and before the carry-forward
    # below, because it moves both the box and its lifecycle. Doing it after
    # would carry a broken zone's right edge forward as though it were alive.
    if request.refine:
        stats.update(
            refine_zones(zones, higher, rows, request.htf, request.supply_demand)
        )
        for zone in zones:
            if zone.refinement is not None:
                zone.refinement.timeframe = request.interval
        # Refining moves the proximal line, and the road is measured from it, so
        # both cross-zone answers are stale the moment a box shrinks.
        # ponytail: this second pass sees the display-capped set, unlike the one
        # inside the detector. Refined zones can therefore read a slightly
        # longer road than they have. Fix by refining before the cap, which
        # means handing the lower-timeframe bars to the detector.
        mark_profit_zones(zones, higher[-1].time)
        mark_crowding(zones, request.supply_demand.min_profit_zone_rr)

    last_chart_bar = rows[-1].time

    for zone in zones:
        zone.timeframe = request.htf
        # Ids must not collide with a local zone that happens to share a price.
        zone.id = f"{request.htf}:{zone.id}"
        # A live HTF zone ends on its own last bar, which sits up to one HTF
        # period behind the chart's right edge. Carry it forward so it does not
        # appear to stop early for a reason the user cannot see.
        if zone.state is not ZoneState.BROKEN:
            zone.time_to = max(zone.time_to, last_chart_bar)

    stats["bars"] = len(higher)
    return zones, stats


async def _fetch(
    symbol: str, interval: str, bars: int, provider: str | None
) -> tuple[list[Candle], str]:
    """Turn provider failures into a 502 carrying the upstream's own words.

    A silent empty chart is the worst outcome here - the user cannot tell a
    missing API key from a symbol that does not exist from a rate limit.
    """
    try:
        return await get_candles(symbol, interval, bars, provider)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
