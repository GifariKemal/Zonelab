"""Zonelab API.

Seventeen endpoints, and `/api/draw` is the one that matters: it returns the
candles and the shapes drawn on them in a single response, so the chart can never
render zones computed from bars it is not showing. The rest are the surfaces that
grew around it - snapshots, deduce, account, autotrade, four agent routes,
forming, triad - and the count is written down because it said "four" for weeks
after it stopped being four.

The shapes themselves live next door. `drawing.py` builds them synchronously off
already-fetched bars and `overlays.py` holds the layers that read those same
bars. THREE blocks may fetch more, not one: `gaps` when the window is too short
to contain its own history, `checklist` per bias timeframe and per SSMT
instrument, and `ssmt` through its aligned partner series. All three fetch here,
in the async handler, never inside the synchronous build. This file is the wire:
it fetches, dispatches, and assembles the response.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import autotrade, journal, snapshots
from . import agent as agent_mod
from .advisor import explain
from .deduce import deduce
from .llm import LLMUnavailable
from .aligned import load_aligned
from .checklist import build as checklist_for
from .config import settings
from .correlation import correlations
from .dealing_range import DISCOUNT_TO, PREMIUM_FROM
from .costs import BROKERS
from .costs import spec as cost_spec
from .drawing import build as build_drawing
from .fetching import fetch
from .indicators import wilder_atr
from .layers import LAYER_IDS, catalogue
from .models import (
    Advice,
    Candle,
    DrawOnLiquidity,
    DrawRequest,
    DrawResponse,
    Drawing,
    RangeLiquidityReport,
    SMTDivergence,
    SSMTDivergence,
    TradePlan,
    Zone,
    ZoneSide,
)
from .overlays import liquidity_report, news_overlay
from .plan import build as plan_for
from .pools import killzones_at
from .ssmt import divergences_for
from .ssmt import smt as smt_read
from .ssmt import smt_positions_for
from .ssmt import ssmt as ssmt_read
from .triad import TRIAD_FAMILIES, truth_asset
from .providers import (
    INTERVALS,
    PROVIDERS,
    SYMBOLS,
    ProviderError,
    availability,
    get_forming,
    resolve,
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
        # ONE list, in draw order, every entry saying what it is. There used to
        # be two - `detectors` and `overlays` - and the UI had to know which id
        # belonged to which, duplicating in TypeScript a fact that only the
        # backend can be right about. A layer added to the registry now appears
        # in the menu with no frontend edit at all.
        #
        # `evidence` is not optional here, and that is the point of serving this
        # rather than a bare id list: two of these layers have measured NEGATIVE
        # results as direction claims and most have no measurement whatsoever. A
        # menu that made every row look equally endorsed would be the most
        # misleading thing on the screen.
        "layers": catalogue(),
        "symbols": [
            {"id": sid, "providers": sorted(vendors)} for sid, vendors in SYMBOLS.items()
        ],
        "intervals": list(INTERVALS),
        # Served so the UI can offer them without a second copy of the list.
        # An empty pick is the generic per-instrument row, which is what the
        # product charged for everything until 2026-08-20 - including for a user
        # whose orders fill at a broker the table has a researched profile for.
        "brokers": sorted(BROKERS),
    }


@app.get("/api/candles")
async def candles(
    symbol: str = "XAUUSD",
    interval: str = "15m",
    bars: int = 500,
    provider: str | None = None,
) -> dict[str, object]:
    rows, used = await fetch(symbol, interval, bars, provider)
    return {"symbol": symbol, "interval": interval, "provider": used, "candles": rows}


@app.get("/api/account")
async def account(provider: str | None = None) -> dict:
    """Account size from the source, for callers that would otherwise type it.

    OPT-IN AND PER PROVIDER. Only a provider that is a real broker connection can
    answer this, and today that is the local terminal alone - a price feed knows
    nothing about anybody's account. A provider without the capability gets a 501
    naming itself rather than a generic failure, because "yahoo cannot tell you
    your equity" is a fact about yahoo and the caller should read it that way.
    """
    # INSIDE the try, because `resolve` is what rejects an unknown provider name.
    # It used to sit outside, so `?provider=nonsense` came back as a bare 500
    # while every other route answers an unknown provider with a 502 carrying the
    # vendor's own words. A 501 for a known feed without an account was already
    # right; it was the unknown NAME that leaked.
    try:
        resolved = resolve(provider)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    reader = getattr(resolved, "account", None)
    if reader is None:
        raise HTTPException(
            status_code=501,
            detail=(
                f"{resolved.name} is a price feed and holds no account. Only a "
                "broker connection can answer this; on this machine that is mt5."
            ),
        )
    try:
        return {"provider": resolved.name, **await reader()}
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/snapshot")
async def snapshot(body: dict) -> dict:
    """Write down what the screen said, and how far behind the tape it was.

    THE CLIENT POSTS BACK THE RESPONSE IT IS DISPLAYING, verbatim, and this
    endpoint does not redraw. Redrawing would answer "what is true now" when the
    question is "what did the reader see", and between those two a tick lands -
    so the snapshot would be of a chart nobody ever looked at, indistinguishable
    from one that was real.

    `deduce` is optional and, when given, is evaluated and stored ALONGSIDE the
    state rather than after it. That ordering is the point: a rule recorded at
    decision time can be scored later, and a rule recalled afterwards cannot.
    """
    response = body.get("response")
    if not isinstance(response, dict) or "meta" not in response:
        raise HTTPException(
            status_code=422,
            detail="post the /api/draw response you are displaying, under `response`",
        )
    note = str(body.get("note") or "")[:2000]
    draw = body.get("draw") or "unnominated"
    if draw not in ("higher", "lower", "unnominated"):
        raise HTTPException(
            status_code=422, detail="draw must be higher, lower or unnominated"
        )
    verdict = deduce(response, draw) if body.get("deduce") else None
    if verdict is not None:
        response = {**response, "deduction": verdict}
    saved = snapshots.save(response, note)
    return {**saved, "deduction": verdict}


@app.get("/api/snapshots")
async def snapshot_list() -> dict:
    """Every snapshot's summary, newest first. The weekly-review index."""
    return {"snapshots": snapshots.listing()}


@app.get("/api/snapshots/{snapshot_id}")
async def snapshot_read(snapshot_id: str) -> dict:
    found = snapshots.read(snapshot_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"no snapshot {snapshot_id!r}")
    return found


@app.post("/api/deduce")
async def deduce_only(body: dict) -> dict:
    """Apply the rule without storing anything.

    Separate from `/api/snapshot` so a rule can be tried against a state without
    filling the review index with experiments - and so the deducer is testable
    without touching a disk.
    """
    response = body.get("response")
    if not isinstance(response, dict) or "meta" not in response:
        raise HTTPException(
            status_code=422,
            detail="post the /api/draw response you are displaying, under `response`",
        )
    draw = body.get("draw") or "unnominated"
    if draw not in ("higher", "lower", "unnominated"):
        raise HTTPException(
            status_code=422, detail="draw must be higher, lower or unnominated"
        )
    return deduce(response, draw)


@app.get("/api/autotrade")
async def autotrade_state() -> dict:
    """The auto-trade switch, and whether anything is actually running.

    TWO FACTS, NEVER ONE. `enabled` is what a human asked for; `daemon_alive` is
    whether a process is there to honour it. A UI that showed only the first would
    display ON over a dead daemon, which is the exact failure this project keeps a
    list of - an instrument reporting green while the thing it measures has
    crashed.
    """
    return autotrade.read()


@app.post("/api/autotrade")
async def autotrade_arm(body: dict) -> dict:
    """Flip the switch. THIS ENDPOINT PLACES NO ORDER AND CANNOT.

    All it does is write a flag that `tools/autotrade.py` reads. Order placement
    lives outside `app/` so that no HTTP request can reach it, and this endpoint
    exists precisely so a button does not have to break that.

    Arming while no daemon runs is ALLOWED and is not an error: the operator may
    arm first and start the daemon second. The response says `daemon_alive` either
    way, and saying so is the UI's job.
    """
    if "enabled" not in body or not isinstance(body["enabled"], bool):
        raise HTTPException(
            status_code=422, detail="send {\"enabled\": true} or {\"enabled\": false}"
        )
    note = str(body.get("note") or "")
    state = autotrade.arm(body["enabled"], note)
    # Journalled, because this is the moment a human decided the engine could
    # trade unattended. A review that sees the orders but not the arming is
    # reading half the story.
    journal.record(
        "armed" if state["enabled"] else "disarmed",
        why=[f"switch set to {state['enabled']} at {state['updated_at']}"
             + (f", note: {note}" if note else "")],
        rule={"surface": "POST /api/autotrade", "places_orders": False},
        extra={"daemon_alive": state["daemon_alive"],
               "heartbeat_age_seconds": state["heartbeat_age_seconds"]},
    )
    return state


@app.get("/api/agent/config")
async def agent_config() -> dict:
    """The AI Agent endpoint settings, key masked, plus availability.

    `available` is computed from the same three fields a chat needs, so a UI
    that shows a green dot over an empty key is impossible by construction -
    the same two-facts rule the autotrade switch follows.
    """
    return agent_mod.masked()


@app.post("/api/agent/config")
async def agent_config_save(body: dict) -> dict:
    """Save endpoint settings, then PROBE the upstream before answering.

    Saving without probing would report success for a typo, and the typo
    would surface minutes later in the middle of a chat. The save stands
    either way - the operator may be pre-configuring an endpoint that is
    briefly down - but the response says whether it answered.
    """
    try:
        agent_mod.save_config(
            base_url=str(body.get("base_url") or ""),
            api_key=str(body.get("api_key") or ""),
            model=str(body.get("model") or ""),
            temperature=(None if body.get("temperature") is None
                         else float(body["temperature"])),
        )
    # TypeError beside ValueError, because `float()` raises different exceptions
    # for different wrong types: "abc" is a ValueError and was already a 422,
    # while a list or a dict is a TypeError and fell through as a bare 500 - on
    # the endpoint that handles the model endpoint's credentials.
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reachable, why, offered = await agent_mod.probe()
    return {**agent_mod.masked(), "reachable": reachable, "error": why,
            "models": offered}


@app.get("/api/agent/models")
async def agent_models() -> dict:
    """Model ids from the configured endpoint, for the picker."""
    try:
        return {"models": await agent_mod.models()}
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/agent/chat")
async def agent_chat(body: dict) -> dict:
    """One assistant turn over the drawing the client is looking at.

    The client posts its history plus the `/api/draw` response it holds, so
    the server stays stateless and the model can never be discussing a
    drawing other than the one on screen. Refusals surface as 503 with the
    module's own wording, for the same reason provider errors do: "no data"
    tells the reader nothing.
    """
    messages = body.get("messages")
    context = body.get("context")
    try:
        return await agent_mod.chat(messages, context)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/forming")
async def forming(
    symbol: str = "XAUUSD",
    interval: str = "15m",
    provider: str | None = None,
) -> dict[str, object]:
    """The bar still being built, for the CHART and for nothing else.

    Its own endpoint rather than a field on `/api/draw`, and that separation is
    the safety property, not a routing preference. A drawing is expensive - the
    detectors, the plan, the overlays - and re-running all of it once a second
    to move one candle would recompute every zone against a bar that has not
    closed, which is precisely what `drop_forming` exists to prevent. This
    returns one candle, costs one provider call, and touches no detector.

    `candle` is null when the newest bar has already closed, which is a real
    answer and not an error: it means the chart's own last candle is current.
    """
    try:
        candle, used = await get_forming(symbol, interval, provider)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "symbol": symbol,
        "interval": interval,
        "provider": used,
        "candle": candle,
    }


@app.get("/api/triad")
async def triad_read(
    symbol: str = "XAUUSD",
    interval: str = "1h",
    bars: int = 2000,
    triad: str = "monetary",
    provider: str | None = None,
) -> dict:
    """One triad, three symbols, and which of them is the Truth Asset.

    A triad is three correlated instruments read together. The Truth Asset is
    the one that is consolidating while the others are choppy — it shows the
    real premium and discount.

    Fetches all three symbols on a shared grid via `load_aligned`, so the
    correlation and consolidation scores are computed from bars that genuinely
    happened at the same instants. One unavailable partner is skipped; the
    base symbol failing is a 502.

    The provider defaults to the chart's own, but the triad partners may not
    be carried by it — Binance only serves three symbols. So when the
    caller's provider is a limited feed, the triad silently falls back to
    mt5 which carries all twenty instruments.
    """
    family = TRIAD_FAMILIES.get(triad)
    if family is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"unknown triad {triad!r}, "
                f"pick one of {sorted(TRIAD_FAMILIES)}"
            ),
        )

    base = symbol.split(":")[-1]
    symbols = [base, *[p for p in family[1:] if p != base]]
    # Binance and Yahoo only carry a handful of the twenty instruments. The
    # triad partners — DXY, EURUSD, WTI, NAS100, etc. — are not among them,
    # so a triad read on those providers would always fail. MT5 carries all
    # twenty and is the fallback.
    triad_provider = provider
    if provider in ("binance", "yahoo", None):
        triad_provider = "mt5"
    try:
        series, load_stats = await load_aligned(
            symbols, interval, bars, triad_provider
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    found = truth_asset(series, base, triad)
    corr = [
        {
            "symbol": c.symbol,
            "full": None if c.full is None else round(c.full, 4),
            "recent": None if c.recent is None else round(c.recent, 4),
            "pairs": c.pairs,
            "sign_changed": c.sign_changed,
        }
        for c in correlations(series, base)
    ]

    now_utc = datetime.now(timezone.utc)
    ny = now_utc.astimezone(ZoneInfo("America/New_York"))
    wib = now_utc.astimezone(ZoneInfo("Asia/Jakarta"))
    ts = int(now_utc.timestamp())
    zones_now = killzones_at(ts)

    return {
        "triad": triad,
        "base": base,
        "partners": [s for s in symbols if s != base],
        "truth_asset": (
            {"symbol": found.symbol, "scores": found.scores}
            if found
            else None
        ),
        "correlation": corr,
        "time": {
            "ny": ny.strftime("%H:%M"),
            "wib": wib.strftime("%H:%M"),
            "ny_day": ny.strftime("%a"),
            "wib_day": wib.strftime("%a"),
            "session": zones_now[0] if zones_now else None,
            "all_sessions": zones_now,
        },
        "grid": load_stats.get("grid"),
        "skipped": load_stats.get("skipped") or [],
    }


#: Calendar days of history the opening-gap layer reads, over and above whatever
#: the chart itself asked for. Ten because it must contain at least one weekend
#: with room to spare for a holiday: nine would be a coin flip on a short month.
_GAP_HISTORY_DAYS = 10


async def _gap_history(rows: list[Candle], request: DrawRequest) -> list[Candle] | None:
    """A window long enough to contain the gaps' CLOSING prices, or None.

    An opening gap is two prices from either side of a shut market, and the
    closing one routinely sits outside the chart while the gap it produced is
    the leftmost thing on screen. Measured on MT5 gold 15m on 2026-08-19: at 300
    bars the Friday close was in the window and the weekend gap drew; at 250,
    200 and 150 it was not, and the layer drew nothing at all - no band, no
    warning - with the Sunday reopen as the first candle. 200 is a shipped Bars
    option, so the ordinary way to look at this chart was the way that hid it.

    Returns None when the chart already reaches back far enough, so the common
    case still costs no second call. When it does fetch, the result is memoised
    by `get_candles` under its own key and the local terminal answers in
    hundredths of a second; a metered vendor is asked at most once per cache
    window, which is the same bound every other fetch here lives under.

    A failure here is swallowed on purpose. The gaps are one overlay; a vendor
    hiccup on the SECOND call must not take down a drawing whose bars already
    arrived. The layer then falls back to the chart's own window, which is the
    behaviour that shipped before this existed.
    """
    if "gaps" not in set(request.layers) or not rows:
        return None
    step = INTERVALS.get(request.interval)
    if step is None:
        return None
    days = max(_GAP_HISTORY_DAYS, request.gaps.keep + 5)
    needed = min(int(days * 86400 / step), settings.max_bars)
    if needed <= len(rows):
        return None
    try:
        history, _ = await fetch(request.symbol, request.interval, needed, request.provider)
    except HTTPException:
        return None
    return history if len(history) > len(rows) else None


async def _draw_ssmt(
    rows: list[Candle], request: DrawRequest, drawing: Drawing, used: str
) -> dict[str, object]:
    """Fill `drawing.ssmt` with the divergences that touch the chart's symbol.

    Every failure here is REPORTED AND SURVIVED, never raised. This is one
    overlay among fourteen and it is the only one that reaches a second
    instrument: a partner that the provider does not carry, or a shared grid too
    short to compare on, must not take down a drawing whose own bars arrived.
    `bar_overlays` makes the same choice about an unknown session name.
    """
    params = request.checklist
    stats: dict[str, object] = {"drawn": 0}
    if not (params.ssmt_symbols and params.ssmt_degrees):
        stats["reason"] = "pick at least one instrument and one degree"
        return stats

    source = params.ssmt_provider or used
    symbols = list(dict.fromkeys([request.symbol, *params.ssmt_symbols]))
    try:
        series, load_stats = await load_aligned(
            symbols, request.interval, request.bars, source
        )
    except ProviderError as exc:
        stats["error"] = str(exc)
        return stats

    stats["grid"] = load_stats.get("grid")
    stats["source"] = source
    # WHICH PARTNERS DID NOT ARRIVE, and why, in the provider's own words. An
    # unavailable partner used to cancel every sibling fetch, so this list was
    # never populated - the whole block failed instead. Now it is the difference
    # between "gold and silver did not diverge" and "silver never loaded".
    skipped = load_stats.get("skipped") or []
    if skipped:
        stats["skipped"] = skipped
    found: list[SSMTDivergence] = []
    for degree in dict.fromkeys(params.ssmt_degrees):
        events, _ = ssmt_read(series, degree)
        # `rows` are the CHART's own bars, and they are what the premium/discount
        # stamp is read against. Deliberately not the aligned grid the divergence
        # was computed on: the reading is "where did this extreme sit in the
        # range a reader of THIS chart could see", and the aligned grid is an
        # intersection that may have dropped bars this chart has.
        found.extend(
            divergences_for(
                events, request.symbol, rows, request.structure.swing_n
            )
        )
    # Oldest first, so the newest segment is drawn last and sits on top where
    # two divergences share an extreme.
    found.sort(key=lambda d: (d.time_from, d.degree, d.partner))
    stats["found"] = len(found)
    # FOUND against DRAWN, both reported, the same shape every other capped
    # overlay uses. The cap trims the tail so the newest survive; see `ssmt_max`
    # for why this layer needs one more than the others do.
    drawing.ssmt = found[-params.ssmt_max:] if params.ssmt_max > 0 else found
    stats["drawn"] = len(drawing.ssmt)

    # WHERE IN THE RANGE the drawn ones sat, as three counts. The canvas puts one
    # letter on each segment, which answers the question per divergence; this
    # answers it for the set, and the set is what a reader looks at before
    # deciding whether the layer is telling them anything. The practitioner's rule
    # is that a divergence in premium and one in discount mean opposite things, so
    # a pane full of them with no split reported is a pane that has not been read.
    #
    # `unknown` is the warm-up and is counted rather than folded into EQ: both
    # sides of the dealing range must have confirmed, and at the shipped swing
    # width that takes about a hundred bars. Measured on 2000 hourly bars of gold
    # against silver at day degree: 24 premium, 33 equilibrium, 31 discount, 11
    # unknown.
    # THE TWO THRESHOLDS ARE IMPORTED, not written here. They were `0.75` and
    # `0.25` inline, a third copy of constants that also lived in `deduce.py` and
    # are now drawn on the canvas by the range frame - so this block could have
    # labelled a divergence "premium" while the line beside it said otherwise.
    bands = {"premium": 0, "equilibrium": 0, "discount": 0, "unknown": 0}
    for d in drawing.ssmt:
        if d.range_pos is None:
            bands["unknown"] += 1
        elif d.range_pos >= PREMIUM_FROM:
            bands["premium"] += 1
        elif d.range_pos <= DISCOUNT_TO:
            bands["discount"] += 1
        else:
            bands["equilibrium"] += 1
    stats["range"] = bands

    # HOW CORRELATED THE PARTNER ACTUALLY IS, and this costs nothing: `series` is
    # already the aligned grid the divergences were computed on, so the
    # coefficients describe exactly the bars the layer read.
    #
    # It answers the question the layer could not: this method reads divergence
    # BETWEEN CORRELATED instruments, the measured hit rate tracks correlation, and
    # a reader picking a partner from a dropdown of twenty had nothing to go on but
    # a hardcoded list of three tickers in the toolbox. Two windows, because a
    # single number hides a decoupling.
    stats["correlation"] = [
        {
            "symbol": c.symbol,
            "full": None if c.full is None else round(c.full, 4),
            "recent": None if c.recent is None else round(c.recent, 4),
            "pairs": c.pairs,
            "recent_pairs": c.recent_pairs,
            "sign_changed": c.sign_changed,
        }
        for c in correlations(series, request.symbol)
    ]
    # The same warning the checklist prints, for the same reason: the synthetic
    # provider invents a series for ANY string, so a typo becomes a confident
    # partner rather than an error.
    if source == "synthetic":
        stats["synthetic"] = True

    # Regular SMT: non-sequential, running-extreme comparison. Liquidity
    # readings rather than trend confirmations. Computed from the same
    # aligned series, so it costs no extra provider call.
    if params.ssmt_degrees:
        smt_found: list[SMTDivergence] = []
        for degree in dict.fromkeys(params.ssmt_degrees):
            smt_events, _ = smt_read(series, degree)
            smt_found.extend(smt_positions_for(smt_events, request.symbol))
        smt_found.sort(key=lambda d: (d.time_at, d.degree, d.partner))
        drawing.smt = smt_found
        stats["smt_events"] = len(smt_found)

    return stats


# HOW MANY DRAWINGS MAY BE COMPUTED AT ONCE. Two, on an eight-core machine, and
# the number is deliberately far below the core count.
#
# `asyncio.to_thread` moves `build` off the event loop but it does NOT make it
# parallel: the work is CPU-bound Python, so every thread it hands out is another
# competitor for the GIL, and the event loop is just one more Python thread in
# that queue. Its default pool is min(32, cores + 4), which is twelve here.
#
# Measured while it was happening, after an end-to-end harness fired a draw per
# interaction: the worker process burned **6.05 seconds of CPU in 6 seconds**
# across 20 threads, `/api/health` - which does nothing but return a dict - took
# **8.01 seconds**, and `POST /api/draw` never came back inside 60. Upstream was
# innocent and was checked at the time: Binance answered in 0.13s.
#
# This also corrects an earlier diagnosis recorded in the README. "CPU delta 0
# over 6 seconds, so the loop stopped without spinning" was measured on the
# PARENT process; uvicorn runs as two, and the parent is only a launcher. The
# child was pinned at a full core. The symptom was saturation, never a stall.
#
# A browser is unaffected: it has one drawing in flight and aborts the previous
# one. The cap only bites when something floods the API, and then it queues
# instead of taking the whole process down with it.
_BUILDS = asyncio.Semaphore(2)


@app.post("/api/draw", response_model=DrawResponse)
async def draw(request: DrawRequest, http: Request) -> DrawResponse:
    # WHOEVER ASKED IS STILL THERE, checked before the two expensive steps.
    #
    # The UI aborts the previous drawing on every keystroke and every slider
    # nudge, and an abort only closes the socket - it does not stop the work. So
    # the server kept computing answers nobody would read, and the backlog was
    # not small: 40 abandoned requests left the worker process burning **5.33
    # seconds of CPU per 5 seconds** minutes after every client had given up, and
    # a fresh single request timed out at 60 seconds behind them. Reproduced with
    # the synthetic provider and 40 distinct bar counts, so no network and no
    # cache hit was involved in it at all.
    #
    # 499 is nginx's "client closed request". Nothing reads this response, by
    # definition; the code exists so the log line says what happened.
    if await http.is_disconnected():
        raise HTTPException(status_code=499, detail="client went away before the fetch")

    rows, used = await fetch(
        request.symbol, request.interval, request.bars, request.provider
    )

    unknown = set(request.layers) - LAYER_IDS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown layer(s): {', '.join(sorted(unknown))}",
        )

    # OFF THE EVENT LOOP, and this is not a micro-optimisation. Everything below
    # is CPU-bound numpy and Python, and an `async def` handler runs its
    # synchronous body inline - so until this line the API served exactly one
    # request at a time, with no concurrency whatsoever. Measured: a request that
    # takes 0.04s alone took 2.76s behind five heavy ones, and the five completed
    # at 0.71, 1.34, 1.97, 2.52 and 3.16 seconds. Strictly serialised, ~0.63s
    # apart, which is the signature and not a coincidence. It showed up as the
    # end-to-end harnesses timing each other out, which is the only reason anyone
    # looked. Bounded by `_BUILDS` above, because off the loop is not the same as
    # unlimited - the thread pool would hand out twelve of these at once.
    # OUTSIDE the semaphore, and that placement is the point of the line. This is
    # a network fetch and `_BUILDS` rations CPU: holding a two-slot CPU gate open
    # across a vendor round trip would let two slow fetches stall every drawing
    # on the machine, which is the exact failure the semaphore was added to stop.
    gap_history = await _gap_history(rows, request)

    async with _BUILDS:
        # AND AGAIN HERE, which is the check that actually drains a backlog. The
        # one before the fetch only catches clients that left early; a request
        # that waited its turn in this queue has had every chance to be
        # abandoned, and this is the last moment before the expensive part.
        if await http.is_disconnected():
            raise HTTPException(
                status_code=499, detail="client went away before the drawing"
            )
        drawing, meta = await asyncio.to_thread(
            build_drawing, rows, request, gap_history
        )

    wanted = set(request.layers)
    if "news" in wanted:
        meta["news"] = await news_overlay(rows, request, drawing)

    # The checklist after the drawing, because everything above must already be
    # correct without it. It is NOT the only block that fetches and it is not
    # last: `_gap_history` fetches before `_build` even runs, and `_draw_ssmt`
    # fetches its partner series after this.
    checklist = None
    if "checklist" in wanted and rows:
        checklist, checklist_stats = await checklist_for(rows, request, used)
        meta["checklist"] = checklist_stats

    # SSMT AS A DRAWING, which is the one overlay that cannot be built off the
    # bars already fetched: a divergence needs a second instrument. That is why
    # it lives here beside the checklist and not in `bar_overlays`, whose whole
    # promise is that it costs no provider call.
    #
    # The two blocks read the SAME three params, so turning both on asks for the
    # same basket twice - and gets it, from `get_candles`'s memo, at the price of
    # one dict lookup. The alternative was a second copy of the basket settings.
    if "ssmt" in wanted and rows:
        meta["ssmt"] = await _draw_ssmt(rows, request, drawing, used)

    # Plans and advice are computed for what SURVIVED to the screen, and that is
    # the one place in this codebase where working off the display-capped set is
    # correct rather than a bug: a plan is an offer to act on a box the user can
    # see. Every cross-zone measurement still happens inside the detector, before
    # the cap, exactly as before.
    #
    # OFF THE LOOP AND UNDER THE SEMAPHORE, exactly like `build_drawing` above,
    # and it was neither for a long time. The argument written out at the top of
    # this function applies word for word to this pass and it was simply left
    # behind: `_annotate` is CPU-bound Python with one `plan_for` and one
    # `explain` per zone, and `liquidity_report` walks the bars again. Measured
    # at 50,000 bars with the display caps lifted: the build took 28.65s inside
    # its thread while this pass took 4.94s ON THE LOOP, and `/api/health` -
    # which does nothing but return a constant - answered in as much as 6.899s on
    # the same request. Five concurrent caps-off draws pushed it to 8.247s, which
    # is the original eight-second stall reproduced through the one route the
    # semaphore did not cover. Unbounded, too: `max_zones_per_side: 0` removes
    # the only thing limiting the zone count, and 36,169 zones is 36,169 inline
    # calls.
    #
    # A SECOND acquisition rather than one held across the blocks between. The
    # news, checklist and SSMT blocks in between make provider calls, and holding
    # a two-slot CPU gate open across a vendor round trip is precisely the
    # failure `_BUILDS` was added to stop.
    async with _BUILDS:
        plans, advice, range_report, draw_on = await asyncio.to_thread(
            _finish, drawing, rows, request, wanted
        )

    return DrawResponse(
        symbol=request.symbol,
        interval=request.interval,
        provider=used,
        candles=rows,
        drawing=drawing,
        plans=plans,
        advice=advice,
        range_liquidity=range_report,
        draw_on_liquidity=draw_on,
        checklist=checklist,
        meta=meta,
    )


def _finish(
    drawing: Drawing,
    rows: list[Candle],
    request: DrawRequest,
    wanted: set[str],
) -> tuple[list[TradePlan], list[Advice], RangeLiquidityReport | None, DrawOnLiquidity | None]:
    """Everything after the drawing that is still CPU-bound, in one thread hop.

    Two calls rather than one, bundled here purely so the handler pays a single
    `to_thread` and a single semaphore acquisition for both. Neither touches the
    network - that is the property that lets them share a CPU gate with the
    build - and `liquidity_report` is included because it walks the bar arrays
    again, which is the same cost class as the plans.
    """
    plans, advice = _annotate(drawing.zones, rows, request)
    range_report, draw_on = (
        liquidity_report(rows, request, drawing)
        if "liquidity" in wanted and rows
        else (None, None)
    )
    return plans, advice, range_report, draw_on


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

    # The rest of the frictions, from the same table the measurement harness
    # reads - and that shared table is the point. These numbers lived only in
    # tools/ until now, so every reward figure the product showed was the
    # frictionless one while the project's own measurement said costs take 9.4%
    # to 20.5% of R on gold and decide whether the edge survives out of sample.
    # A caller may state its own schedule; absent that, an unknown symbol is
    # charged NOTHING and the plan warns, rather than being charged a row that
    # belongs to a different instrument.
    # BOTH SIDES, resolved once and picked per zone, because the overnight carry
    # is a property of the side and not of the instrument. Measured on the
    # connected Exness terminal 2026-08-20: XAUUSD swap_long is -541.4 points -
    # 54.14 USD a night on a 100 ounce lot, 1.20bp at gold 4500 - while
    # swap_short is exactly zero. One spec for every zone charged shorts a cost
    # they never pay. Computed outside the loop because `cost_spec` is a table
    # lookup and two of them is still two, not two per zone.
    #
    # A caller-supplied `request.costs` still wins for both sides: a caller that
    # states a schedule has stated it, and second-guessing it by side would put
    # a number in the plan that the caller never asked for.
    long_spec = request.costs or cost_spec(
        request.symbol, broker=request.broker, long_side=True
    )
    short_spec = request.costs or cost_spec(
        request.symbol, broker=request.broker, long_side=False
    )

    plans: list[TradePlan] = []
    advice: list[Advice] = []
    for zone in zones:
        scale = float(atr[-1])
        plan = plan_for(
            zone, scale, now, INTERVALS[request.interval],
            equity=request.equity, lot=request.lot, spread=spread,
            costs=long_spec if zone.side is ZoneSide.DEMAND else short_spec,
        )
        if plan is not None:
            plans.append(plan)
        advice.append(explain(zone, plan, zone.timeframe or request.interval))
    return plans, advice
