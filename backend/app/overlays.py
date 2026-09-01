"""Everything drawn from bars that were already fetched.

Opening gaps, CISDs, liquidity pools and levels, deviation projections, the
quarter grid, and the one block here that does reach the network - the economic
calendar. None of the others can cost a provider call, which is why they share
one stats bucket in the response.
"""

from __future__ import annotations

from bisect import bisect_right

from . import (
    gaps as gaps_read,
    liquidity as liq,
    news as news_feed,
    pools as pools_read,
    projections as proj,
)
from .cisd import cisds
from .models import (
    Candle,
    CISDEvent,
    ChartGapModel,
    DrawCandidate,
    DrawOnLiquidity,
    DrawRequest,
    Drawing,
    EventHorizonLevel,
    ExpectationFan,
    PathPoint,
    GapStack,
    LiquidityPool,
    NamedLevel,
    NewsEvent,
    OpeningGap,
    ProjectionLevel,
    QuantileSet,
    RangeLiquidityReport,
    RangeProjection,
    SessionParams,
    SessionQuarter,
    TierHorizon,
    DFRExtension,
    DefiningRangeBand,
    TrueOpenLevel,
    WyckoffPhaseModel,
    ZoneSide,
)
from .providers import INTERVALS
from . import quarterly
from .quarters import ALL_DEGREES
from .quarters import quarters as quarter_grid
from .quarters import true_opens


#: The layers `bar_overlays` actually handles, declared HERE rather than in
#: `drawing.py` because it has to match the `if` chain below and a set kept one
#: file away from its chain drifts. It already did: the `dfr` layer shipped
#: registered, exposed in the UI and wired to a primitive, and drew nothing at
#: all, because the caller's copy of this set still named five layers. The test
#: `test_every_layer_is_dispatched` now fails if any registered layer is in
#: neither this set nor a handler.
BAR_OVERLAYS = frozenset(
    {"gaps", "cisd", "dfr", "pools", "liquidity", "projections", "expectation",
     "chart_gaps", "wyckoff"}
)


def bar_overlays(
    rows: list[Candle],
    request: DrawRequest,
    drawing: Drawing,
    wanted: set[str],
    history: list[Candle] | None = None,
) -> dict[str, object]:
    """Opening gaps, event horizons, CISDs and liquidity pools onto the drawing.

    `history` is a LONGER window of the same series, and only the opening gaps
    read it. Everything else here reads the chart's own bars, so the old promise
    that this function cannot cost a provider call still holds for them.

    WHY THE GAPS NEEDED THEIR OWN WINDOW. An opening gap is two prices from
    either side of a closed market, and the closing price can easily sit outside
    the chart while the gap it produced is the first thing on screen. Measured
    on MT5 gold 15m, 2026-08-19: at 300 bars the Friday close was in the window
    and the weekend gap drew; at 250, 200 and 150 bars it was not and the layer
    drew NOTHING - no band, no error, on a chart whose leftmost candle was the
    Sunday reopen. 200 is one of the shipped Bars options, so the most common
    way to look at this chart was the way that hid the gap.

    This is also how the object is meant to behave. The bands are drawn extended
    to the right precisely because they outlive the session that made them; a
    band that vanishes when you zoom in is not that object.

    Two conversions happen here and both are deliberate. The detectors work in bar
    INDICES, and the wire has always spoken in TIMES: an index is meaningless to a
    client that trimmed or resampled the series, so it never leaves this process.
    And the event-horizon level set is asked for as of the LAST BAR rather than as
    of nothing, because that is the only question with a stable answer - see
    `EventHorizonLevel`, the one object here whose value is not fixed at birth.

    Unknown session names are reported rather than raised, the same choice
    `session_grid` makes and for the same reason: one bad name must not take the
    rest of a correct chart down with it.
    """
    stats: dict[str, object] = {}
    if not rows:
        return stats

    if "gaps" in wanted:
        # The longer window where one was supplied, the chart's own bars where it
        # was not, so this function still works standalone in every test that
        # calls it with one series.
        source = history if history else rows
        gap_stats: dict[str, int] = {}
        found = gaps_read.opening_gaps(source, gap_stats)
        stats["gap_history_bars"] = len(source)
        # Both reasons a boundary yielded nothing, reported rather than summed
        # into one silence. `no_bars` means the window still does not reach the
        # closing session; `traded_through` means the market never shut across
        # that boundary and there is no gap to find - which is the whole answer
        # on a 24/7 instrument and must not read as a failure.
        stats["gaps_no_bars"] = gap_stats.get("no_bars", 0)
        stats["gaps_traded_through"] = gap_stats.get("traded_through", 0)
        # `keep` trims the BANDS as well as the levels, and the two must be the
        # same set. Drawing all of them beside levels derived from five would put
        # 53 bands and 4 levels on a 1200-bar gold chart with no way to tell which
        # five produced them - and 53 bands each extended to the right edge is not
        # a chart, it is a wash. This is a display limit like `max_quarters`, so a
        # measurement passes 0 and the count found is reported either way.
        kept = (
            sorted(found, key=lambda g: g.knowable_at)[-request.gaps.keep:]
            if request.gaps.keep > 0
            else found
        )
        # The three adopted readings, all computed over the DRAWN set so the
        # ordinals a reader sees match the bands beside them. `label` and
        # `degree` come from the reference indicator's own rendered vocabulary;
        # `distance_to_ce` is a snapshot against the last bar and is the one
        # field here that moves after the gap is settled.
        ordinal = {o.gap.open_time: o.label for o in gaps_read.gap_ordinals(kept)}
        away = {
            d.gap.open_time: d.distance
            for d in gaps_read.distances_to_ce(kept, rows[-1].close)
        }
        drawing.gaps = [
            OpeningGap(
                kind=g.kind,
                top=g.top,
                bottom=g.bottom,
                ce=g.ce,
                close_time=g.close_time,
                open_time=g.open_time,
                approximate=g.approximate,
                label=ordinal.get(g.open_time, ""),
                degree=gaps_read.weekend_degree(g),
                distance_to_ce=away.get(g.open_time),
            )
            for g in kept
        ]
        # One zone per kind, over the newest few gaps of that kind. Computed on
        # the FOUND set rather than the drawn one: the tier's own retention is
        # its definition, so letting the display cap trim it would make the zone
        # depend on how many bands the chart had room for.
        tiers = gaps_read.tier_horizons(
            found,
            keep=request.gaps.tier_keep,
            reduction=request.gaps.tier_reduction,
            as_of=rows[-1].time,
        )
        drawing.tier_horizons = [
            TierHorizon(
                kind=t.kind,
                reduction=t.reduction,
                top=t.top,
                bottom=t.bottom,
                ce=t.ce,
                knowable_at=t.knowable_at,
                open_times=[g.open_time for g in t.gaps],
            )
            for t in tiers
        ]
        stats["tier_horizons"] = len(tiers)
        stats["tier_reduction"] = request.gaps.tier_reduction

        stacks = gaps_read.gap_stacks(kept)
        drawing.gap_stacks = [
            GapStack(
                top=st.top,
                bottom=st.bottom,
                fraction=st.fraction,
                kinds=[st.gaps[0].kind, st.gaps[1].kind],
                open_times=[st.gaps[0].open_time, st.gaps[1].open_time],
                knowable_at=st.knowable_at,
            )
            for st in stacks
        ]
        stats["gap_stacks"] = len(stacks)
        stats["gaps_by_degree"] = {
            deg: sum(1 for g in kept if gaps_read.weekend_degree(g) == deg)
            for deg in ("month", "year")
        }
        stats["gaps_found"] = len(found)
        stats["gaps"] = len(kept)
        # The flag matters enough to surface as a count: a chart drawn from 4-hour
        # bars gets every band approximate, and a reader who never opens a band's
        # tooltip would not otherwise know. Counted on what was DRAWN.
        stats["gaps_approximate"] = sum(1 for g in kept if g.approximate)
        if request.gaps.event_horizons:
            levels = gaps_read.event_horizons(
                found, keep=request.gaps.keep, as_of=rows[-1].time
            )
            drawing.event_horizons = [
                EventHorizonLevel(
                    price=level.price,
                    knowable_at=level.knowable_at,
                    lower_open_time=level.lower.open_time,
                    upper_open_time=level.upper.open_time,
                )
                for level in levels
            ]
            stats["event_horizons"] = len(levels)

    if "dfr" in wanted:
        # UNKNOWN DEGREES ARE REPORTED, not raised, the same choice `session_grid`
        # makes: one bad name must not take a correct chart down with it.
        wanted_degrees = list(dict.fromkeys(request.dfr.degrees))
        unknown = [d for d in wanted_degrees if d not in ALL_DEGREES]
        bands: list[DefiningRangeBand] = []
        for degree in wanted_degrees:
            if degree in unknown:
                continue
            for found in quarterly.defining_ranges(rows, degree):
                height = found.high - found.low
                extensions: list[DFRExtension] = []
                # BOTH SIDES of every multiple. The source gives the numbers and
                # not a direction - "extensions at -0.5 and -1 often function as
                # manipulation or reversal targets" - so picking one side would
                # be inventing the half nobody published. `abs` because the
                # source writes them negative and a negative multiple of a
                # height would flip the two sides for no reason a reader could
                # see on the chart.
                for multiple in request.dfr.extensions:
                    reach = abs(multiple) * height
                    extensions.append(
                        DFRExtension(
                            multiple=multiple, side="above", price=found.high + reach
                        )
                    )
                    extensions.append(
                        DFRExtension(
                            multiple=multiple, side="below", price=found.low - reach
                        )
                    )
                bands.append(
                    DefiningRangeBand(
                        degree=found.degree,
                        cycle_start=found.cycle_start,
                        time_from=found.start,
                        time_to=found.end,
                        high=found.high,
                        low=found.low,
                        # Derived, never stored twice: a range with a high and a
                        # low has a midpoint whether or not anyone drew it.
                        equilibrium=(found.high + found.low) / 2,
                        extensions=extensions,
                    )
                )
        bands.sort(key=lambda b: (b.time_to, b.degree))
        stats["dfr_found"] = len(bands)
        keep = request.dfr.max_ranges
        drawing.dfr = bands[-keep:] if keep > 0 else bands
        stats["dfr"] = len(drawing.dfr)
        if unknown:
            stats["dfr_unknown_degrees"] = unknown

    if "cisd" in wanted:
        events, runs = cisds(
            rows,
            min_run=request.cisd.min_run,
            interrupt_tolerance=request.cisd.interrupt_tolerance,
        )
        # Newest first, the same display limit the structure overlay applies to
        # its own events. `events` is already in time order out of the detector.
        shown = events[-request.cisd.max_events:] if request.cisd.max_events else events
        drawing.cisd = [
            CISDEvent(
                time=event.time,
                direction=event.direction,
                level=event.level,
                run_from=rows[event.run_start].time,
                run_to=rows[event.run_end].time,
                run_length=event.run_length,
            )
            for event in shown
        ]
        stats["cisd_found"] = len(events)
        stats["cisd"] = len(shown)
        # Runs are reported as a count only. They are the population the events
        # were selected FROM, so the ratio says how selective `min_run` was on
        # this series, which is the one thing a chosen-not-measured default owes
        # its reader.
        stats["delivery_runs"] = len(runs)

    if "pools" in wanted and request.pools.sessions:
        known = [s for s in dict.fromkeys(request.pools.sessions) if s in pools_read.SESSIONS]
        unknown = [s for s in request.pools.sessions if s not in pools_read.SESSIONS]
        found_pools = pools_read.liquidity_pools(rows, known) if known else []
        stats["pools_found"] = len(found_pools)
        # A DISPLAY LIMIT, newest first, for the same reason `max_quarters` exists.
        # Two sessions over 50 days of hourly gold is 212 rays, and a chart with
        # 212 named horizontal lines has stopped annotating price. The cap is on
        # recency because that is what the fact is worth: "the London high already
        # got taken" kills an idea this morning and says nothing seven weeks on.
        # Standing pools are kept ahead of taken ones at equal age, since only a
        # standing pool is still a candidate target.
        if request.pools.max_pools:
            found_pools = sorted(
                found_pools, key=lambda p: (p.knowable_at, p.taken_at is None)
            )[-request.pools.max_pools:]
        drawing.pools = [
            LiquidityPool(
                session=pool.session,
                side=pool.side,
                price=pool.price,
                window_from=pool.window_from,
                window_to=pool.window_to,
                bars=pool.bars,
                covered=pool.covered,
                knowable_at=pool.knowable_at,
                taken_at=pool.taken_at,
            )
            for pool in found_pools
        ]
        stats["pools"] = len(found_pools)
        stats["pools_standing"] = sum(1 for p in found_pools if p.taken_at is None)
        # A partial window's high is not the session high. Counted separately from
        # "taken" because the two are different facts: one is about the market,
        # the other about the feed.
        stats["pools_partial"] = sum(1 for p in found_pools if not p.covered)
        if unknown:
            stats["unknown_sessions"] = unknown

    if "liquidity" in wanted:
        stats.update(_liquidity(rows, request, drawing))

    if "projections" in wanted and request.projections.sessions:
        stats.update(_projections(rows, request, drawing))

    if "expectation" in wanted:
        stats["expectation"] = _expectation(rows, request, drawing)

    if "chart_gaps" in wanted:
        stats.update(_chart_gaps(rows, drawing))

    if "wyckoff" in wanted:
        stats.update(_wyckoff(rows, request, drawing))

    return stats


def _wyckoff(
    rows: list[Candle], request: DrawRequest, drawing: Drawing
) -> dict[str, object]:
    """Wyckoff phase readings onto the drawing, off the bars already fetched."""
    from .wyckoff import phases

    found = phases(rows, lookback=request.wyckoff.lookback)
    times = [c.time for c in rows]
    drawing.wyckoff = [
        WyckoffPhaseModel(
            kind=p.kind,
            at=times[p.at],
            level=p.level,
            tr_low=p.tr_low,
            tr_high=p.tr_high,
        )
        for p in found
    ]
    by_kind: dict[str, int] = {}
    for p in found:
        by_kind[p.kind] = by_kind.get(p.kind, 0) + 1
    return {"wyckoff": len(found), **{f"wyckoff_{k}": v for k, v in by_kind.items()}}


def _chart_gaps(rows: list[Candle], drawing: Drawing) -> dict[str, object]:
    """Breakaway and measuring gaps onto the drawing, off the bars already fetched.

    Unmeasured doctrine, drawn for fidelity: the classification is stated as a
    rule rather than a result, and the measuring projection is the practitioner's
    halfway rule, not a fitted target.
    """
    from .chart_gaps import chart_gaps

    found = chart_gaps(rows)
    times = [c.time for c in rows]
    drawing.chart_gaps = [
        ChartGapModel(
            up=g.up,
            top=g.top,
            bottom=g.bottom,
            at=times[g.at],
            kind=g.kind,
            move_start=g.move_start,
            target=g.target,
        )
        for g in found
    ]
    return {
        "chart_gaps": len(found),
        "chart_gaps_breakaway": sum(1 for g in found if g.kind == "breakaway"),
        "chart_gaps_measuring": sum(1 for g in found if g.kind == "measuring"),
    }


def _dfr_side_key(side: ZoneSide, pos: float | None) -> str:
    """The `dfr_side` bucket a zone falls into, from its dealing-range position.

    Mirrors `app/ict.py:evaluate`: a demand zone wants the lower half of the
    range (pos < 0.5), a supply zone the upper half (pos > 0.5). `None` position
    is the "unknown" bucket. This is a PROXY for the measured `dfr_side` clause,
    which reads the DEFINING range rather than the dealing range; both answer
    "which half of a range is this zone on", and the proxy is stated in the
    overlay's note, not hidden.
    """
    if pos is None:
        return "unknown"
    met = pos < 0.5 if side is ZoneSide.DEMAND else pos > 0.5
    return "met" if met else "failed"


def _expectation(
    rows: list[Candle], request: DrawRequest, drawing: Drawing
) -> dict[str, object]:
    """The measured R distribution for this cell, looked up from a precomputed table.

    No provider call and no lookahead: the table is a static measurement written
    by `tools.expectation`, and this block only matches the newest zone's side
    against the measured `dfr_side` buckets. The match is a PROXY: the table's
    `dfr_side` reads the DEFINING range, while the live side reads the DEALING
    range already stamped on each zone by `mark_dealing_range`. Both answer "is
    the zone in the lower or upper half of a range", so the proxy is stated, not
    hidden.

    A cell that was never measured (every symbol outside the eight-instrument
    first-touch population) reports `measured: false` and draws nothing, which is
    a fact about the table and never a silent empty fan.
    """
    from . import expectation as exp

    cell = exp.cell(request.symbol)
    if cell is None:
        drawing.expectation = None
        return {"measured": False, "reason": "no measured cell for this symbol"}

    base = cell.get("base_rate")
    if not base:
        drawing.expectation = None
        return {"measured": False, "reason": "cell has no base rate"}

    # The newest zone with a known range position. No such zone, or no zones at
    # all, leaves the fan on the base rate alone.
    key = None
    with_pos = [z for z in drawing.zones if z.dealing_range_pos is not None]
    if with_pos:
        newest = max(with_pos, key=lambda z: z.time_to)
        key = _dfr_side_key(newest.side, newest.dealing_range_pos)

    matched = exp.buckets(cell).get(key or "")
    anchor = rows[-1].close if rows else None
    atr = None
    if rows:
        import numpy as np

        from .indicators import wilder_atr

        high = np.array([c.high for c in rows], dtype=np.float64)
        low = np.array([c.low for c in rows], dtype=np.float64)
        close = np.array([c.close for c in rows], dtype=np.float64)
        atr_arr = wilder_atr(high, low, close, request.supply_demand.atr_period)
        if len(atr_arr):
            atr = float(atr_arr[-1])

    drawing.expectation = ExpectationFan(
        symbol=request.symbol,
        interval=request.interval,
        base_rate=QuantileSet(**base),
        matched=QuantileSet(**matched) if matched else None,
        matched_key=key,
        verdict=exp.verdict(),
        note=(
            "matched by the newest zone's side in the dealing range, a proxy for "
            "the defining-range dfr_side the table was measured on"
        ),
        anchor=anchor,
        atr=atr,
        # THE PATH IS BAR-COUNTED, so it only means what it says on the interval
        # it was measured on. On any other interval it is not published, and the
        # stats block below says which interval would carry it.
        path=(
            [PathPoint(**pt) for pt in exp.path(cell)]
            if request.interval == exp.path_interval()
            else []
        ),
    )
    return {
        "measured": True,
        "matched": key,
        "buckets": len(exp.buckets(cell)),
        "path_points": len(drawing.expectation.path),
        "path_interval": exp.path_interval(),
    }


def _named(level: liq.PeriodLevel) -> NamedLevel:
    return NamedLevel(
        name=level.name,
        price=level.price,
        knowable_at=level.knowable_at,
        taken_at=level.taken_at,
        side=level.side,
        boundary=level.boundary,
        window_from=level.window_from,
        window_to=level.window_to,
        gap_at_open=level.gap_at_open,
        gap_at_close=level.gap_at_close,
    )


def _liquidity(
    rows: list[Candle], request: DrawRequest, drawing: Drawing
) -> dict[str, object]:
    """Named previous-period levels: PDH, PDL, PWH, PWL and the named day extremes.

    The display cap picks the newest and prefers the ones still standing, because
    only a standing level is still a target and a swept one from seven weeks ago
    is not the fact that kills an idea this morning.
    """
    stats: dict[str, object] = {}
    params = request.liquidity
    unknown = [p for p in params.periods if p not in liq.PERIODS]
    known = [p for p in dict.fromkeys(params.periods) if p in liq.PERIODS]
    if unknown:
        stats["unknown_periods"] = unknown

    found = (
        liq.previous_period_levels(rows, known, params.boundary) if known else []
    )
    stats["levels_found"] = len(found)
    shown = (
        sorted(found, key=lambda level: (level.knowable_at, level.taken_at is None))[
            -params.max_levels:
        ]
        if params.max_levels
        else list(found)
    )
    drawing.levels = [_named(level) for level in shown]
    stats["levels"] = len(shown)
    stats["levels_standing"] = sum(1 for level in shown if level.taken_at is None)
    stats["boundary"] = params.boundary

    # RELATIVE EQUAL HIGHS AND LOWS. Appended after the cap for the same reason
    # the range frame is: `max_levels` exists to stop forty previous-period
    # extremes burying the price, and a shelf is a different object competing for
    # nothing with them. Its own count is reported so a reader can see how many
    # were found rather than how many the cap left.
    if params.equal_levels:
        shelves = liq.equal_levels(
            rows,
            swing_n=request.structure.swing_n,
            tolerance_atr=params.equal_tolerance_atr,
        )
        drawing.levels = drawing.levels + [_level(level) for level in shelves]
        stats["equal_levels"] = len(shelves)
        stats["equal_levels_standing"] = sum(1 for s in shelves if s.taken_at is None)
        # THE FRACTAL WIDTH IS THE STRUCTURE LAYER'S, not a second knob. The
        # shelves are built from `detect.structure.swings`, so giving this block
        # its own width would let the chart draw a shelf between two swings the
        # structure overlay does not consider swings at all.
        stats["equal_levels_swing_n"] = request.structure.swing_n

    # THE DEALING RANGE, ON THE CHART. Appended after the cap on purpose and
    # exempt from it: `max_levels` is there to stop forty previous-period extremes
    # burying the price, and the frame is five lines that describe the window every
    # one of those extremes is being read inside. Letting a display cap drop the
    # equilibrium would be the same class of error as measuring the road ahead
    # after the zone cap, which this project has already paid for once.
    if params.range_frame:
        found_range = liq.range_liquidity(rows, drawing.zones)
        if found_range is None:
            # Said rather than left blank. The range needs a confirmed swing on
            # BOTH sides, so a short window or a one-directional run legitimately
            # has no range - and an empty chart must never look like a broken one.
            stats["range_frame"] = "no confirmed swing on both sides of this window"
        else:
            # The two extremes are prices the market printed; the three inside are
            # arithmetic on them. Solid and dashed respectively, which is the
            # reference set's own convention and the reason `derived` exists.
            printed = [_level(level) for level in found_range.external]
            computed = [
                _level(level, derived=True) for level in liq.range_frame(found_range)
            ]
            drawing.levels = drawing.levels + printed + computed
            stats["range_frame"] = len(printed) + len(computed)
            stats["range_height"] = round(found_range.high - found_range.low, 8)

    return stats


def _level(level: liq.Level, derived: bool = False) -> NamedLevel:
    """An ERL or IRL level onto the wire, with the fields a period level carries
    and this one cannot: a range edge has no period, no boundary and no side.

    `side` is left absent rather than inferred. It WAS inferred, from the level's
    own name, and that got every external high wrong: the name was `range_high` in
    lower case and the test asked for `HIGH`. It is `RNG H` now, which would not
    have helped. An internal level is named after the
    zone it came from, so there was never a string to read there either.

    `derived` is passed by the caller rather than read off the name here, for the
    same reason `side` is not inferred: the caller KNOWS which levels it computed
    and which the market printed, and a string test would be one rename away from
    dashing the wrong lines.
    """
    return NamedLevel(
        name=level.name,
        price=level.price,
        knowable_at=level.knowable_at,
        taken_at=level.taken_at,
        side=None,
        derived=derived,
        boundary="range",
        window_from=level.knowable_at,
        window_to=level.knowable_at,
        gap_at_open=0,
        gap_at_close=0,
    )


def liquidity_report(
    rows: list[Candle], request: DrawRequest, drawing: Drawing
) -> tuple[RangeLiquidityReport | None, DrawOnLiquidity | None]:
    params = request.liquidity
    """The two liquidity answers that belong on the RESPONSE rather than the chart.

    ERL and IRL are a reading of a range, and the draw candidates are a list with
    a deliberate hole in the middle of it. Neither is a shape, so neither goes in
    `drawing` - the same separation the checklist already follows.

    THE CANDIDATES ARE BUILT FROM EVERY LEVEL FOUND, NOT FROM THE DRAWN SUBSET,
    and an earlier version of this docstring claimed the opposite while the code
    did this - so the comment was wrong rather than the behaviour. Reading it
    off the drawn set would make the answer depend on `max_levels`, a DISPLAY
    setting, and this project has already paid for that mistake once: the road
    ahead was measured after the zone display cap, and the same zone reported a
    target under one cap and none under another. A level the chart had no room
    for is still liquidity the market can reach.
    """
    report: RangeLiquidityReport | None = None
    if params.range_liquidity:
        found = liq.range_liquidity(rows, drawing.zones)
        if found is not None:
            report = RangeLiquidityReport(
                at=found.at,
                high=found.high,
                low=found.low,
                high_time=found.high_time,
                low_time=found.low_time,
                knowable_at=found.knowable_at,
                external=[_level(level) for level in found.external],
                internal=[_level(level) for level in found.internal],
            )

    draw_on: DrawOnLiquidity | None = None
    if params.draw_candidates and rows:
        levels = liq.previous_period_levels(
            rows, request.liquidity.periods, request.liquidity.boundary
        )
        found_dol = liq.dol_candidates(levels, rows[-1].close, rows[-1].time)
        draw_on = DrawOnLiquidity(
            at=found_dol.at,
            price=found_dol.price,
            above=[
                DrawCandidate(
                    name=c.name,
                    price=c.price,
                    distance=c.distance,
                    knowable_at=c.knowable_at,
                )
                for c in found_dol.above
            ],
            below=[
                DrawCandidate(
                    name=c.name,
                    price=c.price,
                    distance=c.distance,
                    knowable_at=c.knowable_at,
                )
                for c in found_dol.below
            ],
        )
    return report, draw_on


def _session_ranges(
    rows: list[Candle], sessions: list[str]
) -> list[tuple[str, pools_read.Pool, pools_read.Pool]]:
    """Each session window paired back into a range, high with low.

    Built from `pools.liquidity_pools` rather than re-cut here, so the window a
    projection is measured over is byte-for-byte the window the pool rays are
    drawn from. Two objects disagreeing about where London was would be worse
    than either being wrong.
    """
    pools = pools_read.liquidity_pools(rows, sessions)
    by_window: dict[tuple[str, int], dict[str, pools_read.Pool]] = {}
    for pool in pools:
        by_window.setdefault((pool.session, pool.window_from), {})[pool.side] = pool
    out: list[tuple[str, pools_read.Pool, pools_read.Pool]] = []
    for (session, _), sides in by_window.items():
        high, low = sides.get("BSL"), sides.get("SSL")
        if high is not None and low is not None:
            out.append((session, high, low))
    out.sort(key=lambda row: row[1].window_from)
    return out


def _projections(
    rows: list[Candle], request: DrawRequest, drawing: Drawing
) -> dict[str, object]:
    """Deviation stacks off the newest session range, in the asked-for directions.

    ONE RANGE PER SESSION, the newest, and that is a display decision rather than
    a doctrinal one: six levels times two directions times two sessions is 24
    lines, and this project has measured what happens to a chart past about a
    third ink coverage. His own charts carry two stacks at a time.
    """
    stats: dict[str, object] = {}
    params = request.projections
    known = [s for s in dict.fromkeys(params.sessions) if s in pools_read.SESSIONS]
    unknown = [s for s in params.sessions if s not in pools_read.SESSIONS]
    if unknown:
        stats["unknown_projection_sessions"] = unknown

    # 0 means both, and both is the default: direction on his own charts is read
    # from where price went AFTER the range, which is hindsight, and the engine
    # will not supply a direction it cannot know.
    directions = [1, -1] if params.direction == 0 else [params.direction]
    levels = tuple(params.levels)
    out: list[RangeProjection] = []
    for session, high, low in _session_ranges(rows, known)[-1:] if known else []:
        for direction in directions:
            found = proj.projection(
                rows,
                high.window_from,
                high.window_to,
                high.price,
                low.price,
                direction,
                levels=levels,
            )
            if found is None:
                continue
            out.append(
                RangeProjection(
                    time_from=found.time_from,
                    time_to=found.time_to,
                    high=found.high,
                    low=found.low,
                    height=found.height,
                    direction=found.direction,
                    origin=found.origin,
                    bars=found.bars,
                    knowable_at=found.knowable_at,
                    label=f"{session} {'up' if direction > 0 else 'down'}",
                    levels=[
                        ProjectionLevel(
                            multiple=level.multiple,
                            price=level.price,
                            taken_at=level.taken_at,
                        )
                        for level in found.levels
                    ],
                )
            )
    drawing.projections = out
    stats["projections"] = len(out)
    stats["projection_levels"] = sum(len(p.levels) for p in out)
    return stats

def session_grid(
    rows: list[Candle], params: SessionParams, drawing: Drawing
) -> dict[str, object]:
    """Fill the drawing's quarter boxes and true opens, and say what was dropped.

    Unknown degree names are reported rather than raised. A caller asking for a
    degree that does not exist has made a mistake worth telling them about, but
    it is not worth failing a whole chart over - every other shape in the
    response is still correct, and a 502 here would hide them.

    The two counts are separate because the reasons they come up short differ.
    A quarter is pure arithmetic on the clock, so it always exists inside the
    window. A true open only exists when a bar opened exactly on the boundary,
    and over a weekend or a holiday no bar did - so `true_opens_missing` is a
    fact about the feed, not a failure, and it is reported rather than filled.
    """
    stats: dict[str, object] = {}
    if not rows:
        return stats

    span = (rows[0].time, rows[-1].time)
    unknown: list[str] = []

    found: list[SessionQuarter] = []
    for degree in dict.fromkeys(params.quarters):
        try:
            found.extend(
                SessionQuarter(
                    degree=q.degree, label=q.label, time_from=q.start, time_to=q.end
                )
                for q in quarter_grid(degree, *span)
            )
        except ValueError:
            unknown.append(degree)

    found.sort(key=lambda q: q.time_from)
    stats["quarters_found"] = len(found)
    if params.max_quarters and len(found) > params.max_quarters:
        found = found[-params.max_quarters:]
    drawing.quarters = found
    stats["quarters_drawn"] = len(found)

    degrees = [d for d in dict.fromkeys(params.true_opens) if d not in unknown]
    drawn: list[TrueOpenLevel] = []
    for degree in degrees:
        try:
            drawn.extend(
                TrueOpenLevel(
                    degree=o.degree,
                    time=o.time,
                    price=o.price,
                    bar=o.bar,
                    approximate=o.approximate,
                )
                for o in true_opens(
                    rows, [degree], approximate=params.approximate_true_opens
                )
            )
        except ValueError:
            unknown.append(degree)
    drawing.true_opens = drawn
    stats["true_opens"] = len(drawn)
    # Reported separately, because an approximate level and a measured one are
    # not the same object and the count is the only way a reader of `meta` can
    # tell how much of the set is which.
    loose = sum(1 for o in drawn if o.approximate)
    if loose:
        stats["true_opens_approximate"] = loose

    # How many cycles had a Q2 boundary in this window with no bar on it, PER
    # DEGREE. Counted against that degree's own full quarter grid, which is the
    # only set it can be compared with: an earlier version subtracted from
    # `drawing.quarters`, which is capped for readability and only holds the
    # degrees asked for as BOXES, so a week-degree true open was measured
    # against day-degree quarters that had also been truncated. It reported
    # minus ten missing levels, which is how the mistake announced itself.
    missing: dict[str, int] = {}
    for degree in degrees:
        if degree in unknown:
            continue
        expected = sum(1 for q in quarter_grid(degree, *span) if q.label == "Q2")
        missing[degree] = expected - sum(1 for o in drawn if o.degree == degree)
    if missing:
        stats["true_opens_missing"] = missing
    if unknown:
        stats["unknown_degrees"] = sorted(set(unknown))
    return stats


async def news_overlay(
    rows: list[Candle], request: DrawRequest, drawing: Drawing
) -> dict[str, object]:
    """The economic calendar. The one overlay here that reaches the network, and
    the only block in the engine that talks to somebody other than the price
    provider - so it is async and runs in the handler rather than inside `build`,
    which is handed to a worker thread and must stay free of I/O.

    Its failure is reported in the feed's own words, never as an empty chart.
    That matters more than usual here: the host rate-limits, measured at three
    or four requests inside about two minutes, so a chart that quietly drew
    nothing would be indistinguishable from a quiet week.
    """
    week = await news_feed.read()
    picked = news_feed.select(
        week.events,
        impact=request.news.impacts or None,
        currency=request.news.currencies or None,
    )
    # Only what the chart is actually showing. A release outside the drawn bars
    # has no x to be drawn at, and counting it would inflate the number beside a
    # chart that cannot show it.
    #
    # Inside the window is not enough, and that was a real defect: 08:30 New
    # York is 12:30 UTC, no hourly bar opens then, and three of five releases
    # were counted here while the chart drew nothing for them. So each one is
    # placed against the bar it happened DURING, and a release that fell while
    # the market was shut - a weekend row, a holiday row - is dropped and
    # counted separately rather than nailed to the last bar before it.
    step = INTERVALS[request.interval]
    times = [r.time for r in rows]
    window = (rows[0].time, rows[-1].time) if rows else (0, 0)
    inside = [e for e in picked if window[0] <= e.time <= window[1]]
    visible: list[NewsEvent] = []
    shut = 0
    for e in inside:
        bar = times[bisect_right(times, e.time) - 1]
        if e.time - bar >= step:
            shut += 1
            continue
        visible.append(
            NewsEvent(
                time=e.time,
                title=e.title,
                currency=e.currency,
                impact=e.impact,
                forecast=e.forecast,
                previous=e.previous,
                bar=bar,
                offset=(e.time - bar) / step,
            )
        )
    drawing.news = visible
    stats: dict[str, object] = {
        "news_found": len(week.events),
        "news": len(visible),
    }
    if shut:
        stats["news_market_shut"] = shut
    if week.covers_from is not None and week.covers_to is not None:
        # Read from the data, never assumed to be seven days: the live feed came
        # back covering 4.65 days on the day this was written.
        stats["news_window"] = f"{(week.covers_to - week.covers_from) / 86400:.2f} days"
    if week.error:
        stats["news_error"] = week.error[:200]
    return stats
