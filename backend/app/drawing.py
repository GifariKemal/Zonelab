"""Every shape on the chart, and the provenance beside it.

One loop over the layer registry, in the registry's own order. Purely
synchronous by design so `/api/draw` can hand it to a worker thread: it touches
no network, because the bars arrive already fetched and every block that CAN
fetch - gaps, checklist and ssmt - stays in the async handler where it belongs.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from .confluence import mark_nesting
from .dealing_range import mark_dealing_range
from .detect import DETECTORS
from .detect.structure import overlay as structure_overlay
from .detect.supply_demand import cap_per_side
from .layers import DETECTOR_IDS, LAYERS, PARAMS_BY_ID
from .models import Candle, DrawRequest, Drawing, FibonacciAnchor, Zone, ZoneState
from .overlays import BAR_OVERLAYS, bar_overlays, session_grid
from .profit_zone import mark_crowding, mark_profit_zones
from .providers import INTERVALS
from .refine import refine_zones
from .resample import resample
from . import vortex

#: Every layer handler has the same shape: read the bars, add to the drawing,
#: leave its own provenance in `meta`. Nothing returns a value - a layer that
#: needed to hand something back would be one the next layer depends on, and
#: the registry's order would stop being a display decision.
_Handler = Callable[[list[Candle], DrawRequest, Drawing, dict[str, object]], None]


def _draw_supply_demand(
    rows: list[Candle], request: DrawRequest, drawing: Drawing, meta: dict[str, object]
) -> None:
    """The one detector with passes of its own: nesting, and the road ahead.

    Both must see ONLY its own zones, which is why the registry puts it before
    the others append. A fair value gap has no opposing zone and no profit zone,
    so sweeping it through the road filter would apply one method's rule to
    another method's drawing.
    """
    zones, stats = DETECTORS["supply_demand"](rows, request.supply_demand)
    for zone in zones:
        zone.timeframe = request.interval
    drawing.zones = zones
    meta["supply_demand"] = stats

    # The road ahead and the crowding stamp are already on these zones: the
    # detector runs both passes over its full population, before the display cap,
    # which is the only place they can be measured honestly.
    if request.htf:
        higher, htf_stats = _htf_zones(rows, request, "supply_demand")
        mark_nesting(zones, higher)
        drawing.zones = higher + drawing.zones
        _htf_meta(meta)["supply_demand"] = htf_stats

    # A filter on the road as it stands NOW, not on whether the road was ever
    # shut. `crowded_at` records the history either way; a zone whose opposing
    # wall has since been broken is tradeable again and is not removed here.
    min_rr = request.supply_demand.min_profit_zone_rr
    if min_rr > 0:
        before = len(drawing.zones)
        drawing.zones = [
            z
            for z in drawing.zones
            if z.profit_zone_rr is None or z.profit_zone_rr >= min_rr
        ]
        stats["rejected_crowded"] = before - len(drawing.zones)


def _zone_layer(name: str) -> _Handler:
    """A box detector that APPENDS to whatever is already drawn.

    Appending rather than replacing is the point: a chart showing a supply zone
    and a fair value gap at the same price is showing two different claims about
    that price, and collapsing them would hide one.

    Resolved through `DETECTORS` and the layer registry by name, never from a literal
    list. A hardcoded tuple once let a newly registered detector pass validation
    and then never run - a 200 with no zones and no error, which is the exact
    silent wrong answer this project refuses to ship.

    AND IT READS `request.htf`, which it did not for a long time. HTF projection
    lived inside `_draw_supply_demand` alone, so a reader with only Fair value gap
    on could pick HTF 4h in the header and get a 200 with no `meta.htf`, no
    warning, and a chart identical to the one before - measured directly:
    `htf:"4h"` with `layers:["fvg","order_block"]` returned every zone stamped
    `15m`. An H4 fair value gap read on an M15 chart is ordinary top-down ICT, so
    the gap was in the wiring rather than in the method. Putting it here rather
    than in each of the four handlers is the point: one guard, four detectors.
    """

    def draw_layer(
        rows: list[Candle],
        request: DrawRequest,
        drawing: Drawing,
        meta: dict[str, object],
    ) -> None:
        shapes, extra = DETECTORS[name](rows, getattr(request, PARAMS_BY_ID[name]))
        for shape in shapes:
            shape.timeframe = request.interval
        drawing.zones = drawing.zones + shapes
        meta[name] = extra

        if request.htf:
            higher, htf_stats = _htf_zones(rows, request, name)
            drawing.zones = higher + drawing.zones
            _htf_meta(meta)[name] = htf_stats

    return draw_layer


def _draw_structure(
    rows: list[Candle], request: DrawRequest, drawing: Drawing, meta: dict[str, object]
) -> None:
    """Swings, breaks and sweeps. Produces no boxes, so it cannot be capped per
    side and must never be mistaken for a detector.

    Drawn for fidelity only. ICT puts bias in structure and uses zones to refine
    the entry, so a chart with no structure cannot show the method - but H6 and
    H9 measured these exact objects and both came out null, so nothing here may
    be read as a direction.
    """
    swings, events, stats = structure_overlay(rows, request.structure)
    drawing.swings = swings
    drawing.structure = events
    meta["structure"] = stats

    # Fibonacci anchors: the most recent CONFIRMED swing high and swing low,
    # at the `swing` scale. None on either side until structure has confirmed
    # both, so the grid re-anchors cleanly instead of drawing half an anchor.
    highs = [s for s in swings if s.high and s.scale == "swing"]
    lows = [s for s in swings if not s.high and s.scale == "swing"]
    if highs and lows:
        drawing.fibonacci = FibonacciAnchor(
            low=lows[-1].price, low_at=lows[-1].time,
            high=highs[-1].price, high_at=highs[-1].time,
        )


def _draw_session(
    rows: list[Candle], request: DrawRequest, drawing: Drawing, meta: dict[str, object]
) -> None:
    """The New York cycle grid, and the cheapest object in the whole engine: it
    reads the clock rather than the price, so there is nothing to calibrate and
    nothing that could carry a direction claim.

    It earns its place on frequency alone - across 51 of the owner's own
    annotated charts a named horizontal level appears on every single one, and
    Fibonacci on 12%.
    """
    meta["session"] = session_grid(rows, request.session, drawing)


def _draw_vortex(
    rows: list[Candle], request: DrawRequest, drawing: Drawing, meta: dict[str, object]
) -> None:
    """The 3-6-9 dial, which is the only layer here that reads NO bar values.

    It reads one thing off the series - the newest bar's TIME - and everything
    else comes from the calendar. Deliberately not the wall clock: the chart
    draws closed bars, and a dial pointing at `time.time()` would sit up to a
    full bar ahead of every candle on screen, which on dukascopy is 59 minutes
    of showing a sector no visible bar belongs to.

    An empty series draws no dial rather than a dial at epoch zero. A ring
    diagram pointing confidently at 1 January 1970 is worse than an absent one,
    because it looks like an answer.
    """
    if not rows:
        meta["vortex"] = {"drawn": 0, "note": "no bars, so no bar time to place"}
        return
    drawing.vortex = vortex.dial(rows[-1].time)
    meta["vortex"] = {
        "drawn": len(drawing.vortex.rings),
        "at": rows[-1].time,
        "sectors": {ring.id: ring.sector for ring in drawing.vortex.rings},
    }


#: The layers that read the already-fetched bars and share one stats bucket.
_HANDLERS: dict[str, _Handler] = {
    "supply_demand": _draw_supply_demand,
    "fvg": _zone_layer("fvg"),
    "order_block": _zone_layer("order_block"),
    "ifvg": _zone_layer("ifvg"),
    "breaker": _zone_layer("breaker"),
    "structure": _draw_structure,
    "session": _draw_session,
    "vortex": _draw_vortex,
}


def build(
    rows: list[Candle],
    request: DrawRequest,
    history: list[Candle] | None = None,
) -> tuple[Drawing, dict[str, object]]:
    """Every shape on the chart, and the provenance beside it.

    Purely synchronous by design, so `draw` can hand it to a worker thread. It
    touches no network: the bars arrive already fetched, and the only block that
    can make a provider call is the checklist, which stays in the async handler
    where it belongs.

    `history` is a longer window of the same series, fetched by the caller for
    the opening gaps and read by nothing else - a gap's closing price routinely
    sits outside the chart while the gap itself is on screen. None means the
    chart's own bars, which is what every existing caller passes.
    """
    drawing = Drawing()
    # Both numbers, always. Vendors cap a page at their own limit (Binance at
    # 1000, Yahoo by calendar range), and a short answer is otherwise
    # indistinguishable from a quiet market.
    # Provenance, because a live chart that cannot say WHICH BAR it describes is
    # asking to be trusted on nothing. The forming bar is dropped upstream, so
    # the newest bar here is closed - but the user cannot see that, and the gap
    # between "now" and the bar being drawn is real and varies by provider:
    # binance is seconds behind, dukascopy up to 59 minutes, and both look
    # identical on screen without a number.
    step = INTERVALS[request.interval]
    as_of = rows[-1].time if rows else 0
    meta: dict[str, object] = {
        "bars_requested": request.bars,
        "bars_returned": len(rows),
        "truncated_by_provider": len(rows) < request.bars,
        "as_of": as_of,
        "bar_closed_at": as_of + step if rows else 0,
        "next_close_at": as_of + 2 * step if rows else 0,
        "feed_lag_seconds": max(0, int(time.time()) - (as_of + step)) if rows else 0,
        "fetched_at": int(time.time()),
    }

    wanted = set(request.layers)

    # ONE LOOP over the registry, in the registry's own order. This used to be a
    # chain of thirteen `if` statements testing two different things - a name in
    # a `detectors` list for boxes, an `enabled` boolean inside a params block
    # for everything else - and the draw order was implicit in the order someone
    # happened to write them down. Now the order IS the tuple in
    # `app/layers.py`, where it is documented and readable in one place.
    for layer in LAYERS:
        handler = _HANDLERS.get(layer.id)
        if handler is not None and layer.id in wanted:
            handler(rows, request, drawing, meta)

    # HTF ON AND NOTHING TO PROJECT MUST SAY SO. The picker sits in the page
    # header and is never gated on the layer set, so a reader with only the cycle
    # grid on can select HTF 4h and get an identical chart. That used to be a 200
    # with no `meta.htf` at all - silence, which reads as either "no zones up
    # there" or "the feature is broken", and the two must never look alike.
    if request.htf:
        htf = meta.setdefault("htf", {})
        assert isinstance(htf, dict)
        htf["interval"] = request.htf
        usable = sorted(wanted & HTF_LAYERS)
        if not usable:
            htf["note"] = (
                f"HTF {request.htf} is selected but none of the layers that are on "
                "can be read on a higher timeframe. The five box detectors can: "
                + ", ".join(sorted(HTF_LAYERS))
            )

    # The ICT reading of where each box sits, filled for every detector's boxes
    # at once because it is a property of the CHART rather than of a formation.
    # Deliberately not `curve`: that one is the Seiden reading, a rolling 200-bar
    # range split in thirds and frozen when the zone was born, and this one is a
    # swing-to-swing range read at the moment price arrives. Two questions, two
    # fields, and neither is scored.
    #
    # After the loop rather than inside it, because it describes the FINISHED set
    # of boxes. Nothing below the detectors in the registry touches `zones`, so
    # this is the same answer the old ordering gave.
    # CALLED FOR ITS SIDE EFFECT, and the return value is deliberately dropped.
    # This stamps `zone.dealing_range_pos` on every box, which the zone panel
    # renders; the counters it also returns were assigned to `meta["dealing_range"]`
    # and read by nothing in app, tools, tests or the frontend - `types.ts` never
    # even declared the field. A stats dict nobody reads is a stats dict nobody
    # can be wrong about.
    mark_dealing_range(drawing.zones, rows, request.structure.swing_n)

    # The six that read the already-fetched bars share one helper and one stats
    # bucket, and the grouping is deliberate rather than left over: they are the
    # layers that cost no provider call, and each reports the same
    # found-against-drawn pair, so a reader compares them side by side.
    if wanted & BAR_OVERLAYS:
        meta["overlays"] = bar_overlays(rows, request, drawing, wanted, history)

    return drawing, meta

#: Which layers can be read on a higher timeframe at all.
#:
#: The five box detectors, and nothing else. This is a statement about the
#: objects rather than about the code: a box is a price region that exists on
#: whatever timeframe produced it, so an H4 order block is a real thing to draw
#: on an M15 chart. The rest are not like that. `session`, `dfr` and `gaps`
#: already carry their own degree - a "4h daily true open" is not a concept -
#: `structure` on aggregated bars would report swings whose confirming bar the
#: chart cannot show, and `ssmt`, `pools`, `liquidity`, `projections` and `news`
#: are each anchored to something other than the chart's step.
#:
#: DERIVED FROM THE REGISTRY, not written out again, and that is the whole point.
#: This used to be a literal frozenset holding the same five names, which is the
#: exact shape of the defect the note above warns about: a hand-written set of
#: names in another file is how `dfr` came to be registered, panelled, given a
#: canvas primitive, and draw nothing at all. Nothing asserted the two agreed, so
#: a sixth box detector added to `LAYERS` would have been left out of HTF
#: projection silently - and out of `test_no_repaint.py`'s parametrize list too,
#: since that test reads THIS name, so its coverage would have shrunk in the same
#: commit and with the same silence.
HTF_LAYERS = DETECTOR_IDS


def _htf_meta(meta: dict[str, object]) -> dict[str, object]:
    """The `layers` bucket inside `meta["htf"]`, created on first use.

    NESTED UNDER `layers` RATHER THAN FLAT, because five layers can now answer and
    a flat bucket would let the last one quietly overwrite the four before it. It
    also leaves room beside them for `interval` and for the `note` that fires when
    HTF is on and nothing can use it - a message that has to live somewhere a
    reader will actually see, since `/api/draw` has no notes array and `meta` is
    the only channel there is.

    The shape changed when HTF stopped being a supply-and-demand-only feature;
    `types.ts` and the refine counters in `toolbox.tsx` moved with it.
    """
    htf = meta.setdefault("htf", {})
    assert isinstance(htf, dict)
    layers = htf.setdefault("layers", {})
    assert isinstance(layers, dict)
    return layers


def _htf_zones(
    rows: list[Candle], request: DrawRequest, name: str
) -> tuple[list[Zone], dict]:
    """Zones from a higher timeframe, projected onto this chart.

    The zones are detected on aggregated bars and their lifecycle is replayed on
    those same bars, not on the chart's. That is deliberate: an H4 demand zone
    should not die because one M15 candle closed a few cents under it. The zone
    belongs to its own timeframe and is judged there.

    Every HTF bar used here is complete, because `resample` drops the forming
    one, so nothing drawn is a zone the trader could not already have seen.

    `name` is the detector to run up there, and it is a parameter rather than a
    constant because four other box layers reach this function now. Refinement
    stays supply-and-demand-only below, and that is not an oversight: `refine.py`
    shrinks a zone to the pause INSIDE it, which is a supply-and-demand idea. A
    fair value gap has no base to shrink to.
    """
    if request.htf is None or request.htf not in INTERVALS:
        return [], {"error": f"unknown timeframe '{request.htf}'"}

    higher = resample(
        rows, request.htf, request.interval, request.session_offset_hours
    )
    # Each detector's own warm-up, read off its own params, rather than supply and
    # demand's borrowed for everybody. They differ: a fair value gap needs three
    # bars and an ATR window, an order block needs its structure lookback.
    params = getattr(request, PARAMS_BY_ID[name])
    warmup = int(getattr(params, "atr_period", 14)) + 3
    if len(higher) < warmup:
        return [], {
            "bars": len(higher),
            "note": f"not enough higher-timeframe bars in this window, {warmup} needed",
        }

    # The display cap is lifted for a refining pass and re-applied at the end of
    # this function. Refinement moves the proximal line, so the road ahead and
    # the crowding stamp have to be recomputed after it - and recomputing them
    # on the CAPPED set measures the road against the handful of zones the chart
    # had room for rather than against every wall that is really there. A wall
    # that was cut for readability still blocks the road, and the error only ever
    # points one way: it makes the road look longer than it is, by exactly the
    # zones the cap threw away. Same class of defect as calibrating through the
    # cap, which has already cost this project one full round of measurement.
    #
    # Refinement is supply-and-demand only, so the cap is lifted only there. The
    # other four detectors apply their own cap inside themselves and there is no
    # second pass to invalidate it.
    refining = bool(request.refine) and name == "supply_demand"
    if refining:
        params = params.model_copy(update={"max_zones_per_side": 0})
    zones, stats = DETECTORS[name](higher, params)

    # Refinement happens BEFORE the timeframe stamp and before the carry-forward
    # below, because it moves both the box and its lifecycle. Doing it after
    # would carry a broken zone's right edge forward as though it were alive.
    if refining:
        stats.update(
            refine_zones(zones, higher, rows, request.htf, request.supply_demand)
        )
        for zone in zones:
            if zone.refinement is not None:
                zone.refinement.timeframe = request.interval
        mark_profit_zones(zones, higher[-1].time)
        mark_crowding(zones, request.supply_demand.min_profit_zone_rr)
        # Now the cap, on zones whose geometry is final. Both counts are
        # reported: the detector's own `zones` key would otherwise describe a
        # population the chart never showed.
        stats["zones_before_cap"] = len(zones)
        zones = cap_per_side(zones, request.supply_demand.max_zones_per_side)
        stats["zones"] = len(zones)

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
