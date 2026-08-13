"""Zonelab API.

Four endpoints. `/api/draw` is the one that matters: it returns the candles and
the shapes drawn on them in a single response, so the chart can never render
zones computed from bars it is not showing.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .detect import DETECTORS
from .models import Candle, DrawRequest, DrawResponse, Drawing, Zone, ZoneState
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

        if request.htf:
            higher, htf_stats = _htf_zones(rows, request)
            drawing.zones = higher + drawing.zones
            meta["htf"] = htf_stats

    return DrawResponse(
        symbol=request.symbol,
        interval=request.interval,
        provider=used,
        candles=rows,
        drawing=drawing,
        meta=meta,
    )


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

    higher = resample(rows, request.htf, request.interval)
    if len(higher) < request.supply_demand.atr_period + 3:
        return [], {
            "bars": len(higher),
            "note": "not enough higher-timeframe bars in this window",
        }

    zones, stats = DETECTORS["supply_demand"](higher, request.supply_demand)
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
