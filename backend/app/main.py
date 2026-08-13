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
from .models import Candle, DrawRequest, DrawResponse, Drawing
from .providers import INTERVALS, PROVIDERS, SYMBOLS, ProviderError, get_candles

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
    return {
        "providers": [
            {
                "id": name,
                "available": provider.available(),
                "needs_key": name in {"twelvedata", "polygon"},
            }
            for name, provider in PROVIDERS.items()
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
    meta: dict[str, object] = {"bars_returned": len(rows)}

    if "supply_demand" in request.detectors:
        zones, stats = DETECTORS["supply_demand"](rows, request.supply_demand)
        drawing.zones = zones
        meta["supply_demand"] = stats

    return DrawResponse(
        symbol=request.symbol,
        interval=request.interval,
        provider=used,
        candles=rows,
        drawing=drawing,
        meta=meta,
    )


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
