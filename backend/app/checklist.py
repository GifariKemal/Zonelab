"""The owner's five checklist items, and the two blocks that cost a fetch.

Wiring only. Every rule below lives in `quarterly`, `bias`, `pools` or `ssmt`;
if this module ever starts deciding something itself, that decision is in the
wrong file.
"""

from __future__ import annotations

import asyncio

from . import bias, clock, news, pools as pools_read, quarterly, sequence as seq
from .aligned import load_aligned
from .fetching import fetch
from .judas import classify as judas_classify
from .models import (
    BiasAlignment,
    Candle,
    ChecklistParams,
    ChecklistReport,
    CycleProfile,
    DefiningRange,
    DegreeBias,
    DrawRequest,
    JudasReading,
    ManipulationEvent,
    NewsItem,
    OpenStack,
    PremiumDiscount,
    QuarterChain,
    RangeReading,
    SSMTHit,
    TrueOpenLevel,
)
from .providers import ProviderError
from .quarters import quarters as quarter_grid
from .quarters import stacked_opens, true_opens
from .ssmt import ssmt as ssmt_read


async def build(
    rows: list[Candle], request: DrawRequest, used: str
) -> tuple[ChecklistReport, dict[str, object]]:
    """The owner's own pre-trade checklist, computed from his own rules.

    Five modules carrying 83 tests between them were complete and unreachable
    until this function existed. What it adds is only wiring: every rule below
    lives in `quarterly`, `bias` or `ssmt`, and if this function ever starts
    deciding something itself, that decision is in the wrong file.

    THE CYCLE IS THE CURRENT ONE. Every quarterly reading takes a `cycle_start`,
    and it is derived from the LAST bar rather than passed in, because a
    checklist about last week's cycle answers a question nobody asked.

    ABSENT IS EXPLAINED. Each None that has a reason gets a line in `notes`.
    "No profile because Q1 has not closed" is a fact about the clock and must
    not read like a failure - the same rule `Candle.spread` follows by being
    None rather than 0 when unmeasured.

    NOTHING HERE IS A FORECAST. Twelve pre-registered directional hypotheses
    have failed in this project and market structure specifically failed three
    times (H6, H9, H11). This reports whether HIS checklist items are satisfied.
    None of the five has been measured against outcomes by anyone, including him.
    """
    params = request.checklist
    notes: list[str] = []
    fetches = 0
    stats: dict[str, object] = {}
    report = ChecklistReport(degree=params.degree)

    # The cycle containing the last bar. `quarters` is asked for a window ending
    # at that bar and the newest Q1 at or before it opens the live cycle.
    grid = quarter_grid(params.degree, rows[0].time, rows[-1].time)
    q1s = [q for q in grid if q.label == "Q1" and q.start <= rows[-1].time]
    if not q1s:
        notes.append(
            f"no complete {params.degree} cycle opens inside this window, so the "
            "defining range, the profile and manipulation have nothing to read"
        )
        report.notes = notes
        return report, stats
    cycle_start = q1s[-1].start

    dfr = quarterly.defining_range(rows, params.degree, cycle_start)
    if dfr is None:
        notes.append(
            "no defining range: the kept two thirds of Q1 hold no bars in this "
            "feed, which over a weekend or a holiday is the honest answer rather "
            "than a failure"
        )
    else:
        report.dfr = DefiningRange(
            degree=dfr.degree, cycle_start=dfr.cycle_start, time_from=dfr.start,
            time_to=dfr.end, high=dfr.high, low=dfr.low,
            # Derived here rather than stored on the dataclass, because it is
            # arithmetic on two fields that are already there and a second copy
            # of a midpoint is a second thing that can disagree with its range.
            equilibrium=(dfr.high + dfr.low) / 2,
        )

    prof = quarterly.profile(rows, params.degree, cycle_start)
    if prof is None:
        notes.append(
            "no cycle profile: Q1 has not closed yet, and nobody claims AMDX or "
            "XAMD can be known before it does"
        )
    else:
        report.profile = CycleProfile(
            degree=prof.degree, cycle_start=prof.cycle_start, name=prof.name,
            manipulation=prof.manipulation, knowable_at=prof.knowable_at,
        )

    manip = quarterly.manipulation_done(rows, params.degree, cycle_start)
    if manip is None:
        notes.append(
            "manipulation not seen: it is a CONJUNCTION, so this means either the "
            "manipulation quarter has not arrived or no sweep took the previous "
            "quarter's extreme inside it"
        )
    else:
        report.manipulation = ManipulationEvent(
            degree=manip.degree, cycle_start=manip.cycle_start,
            profile=manip.profile, quarter_label=manip.quarter.label,
            time_from=manip.quarter.start, time_to=manip.quarter.end,
            level=manip.level, swing_level=manip.swing_level,
            direction=manip.direction, sweep_time=manip.sweep_time,
        )

    # "In discount?", his third question, and the last of the five to be built.
    # It costs nothing: the range comes from the bars already fetched. Kept above
    # the fetching blocks for that reason.
    report.discount = _discount(rows, params)
    if report.discount is None:
        notes.append(
            f"no premium or discount reading: nothing sits above the "
            f"{params.degree} degree, so there is no parent range to measure in"
        )
    elif report.discount.chosen is None:
        notes.append(
            f"the {params.discount_anchor} anchor produced no window here, so the "
            f"reading is absent rather than neutral: {'; '.join(report.discount.absent)}"
        )
    elif report.discount.disagree:
        # Surfaced as a NOTE, not left in a field nobody opens. The whole reason
        # every anchor is computed is that they can disagree, and a reader who
        # quotes "in discount" without knowing another anchor said premium has
        # been misled by this engine rather than by the market.
        words = ", ".join(f"{r.anchor} says {r.reading}" for r in report.discount.readings)
        notes.append(f"the discount anchors do not agree: {words}")

    # The quarter chain, a fact about the clock and nothing more. It costs
    # nothing and it is only READABLE on a timeframe that divides the grid: a
    # micro quarter is 1350 seconds, so on hourly bars six of his ten listed
    # chains cannot occur at all. The note says so rather than leaving a reader
    # to wonder why they never see 444.
    if params.chain_degrees:
        found_chain = seq.chain(rows[-1].time, params.chain_degrees)
        if found_chain is None:
            notes.append(
                "no quarter chain: one of the degrees asked for is not in the "
                "grid, or they were not given outermost first"
            )
        else:
            report.chain = QuarterChain(
                at=found_chain.at,
                degrees=list(found_chain.degrees),
                quarters=list(found_chain.quarters),
                text=found_chain.text,
                compact=found_chain.compact,
                in_his_list=found_chain.in_his_list,
                base_rate=seq.BASE_RATE,
            )
            if "micro" in params.chain_degrees or "nano" in params.chain_degrees:
                notes.append(
                    "the chain includes a degree finer than this chart's bars can "
                    "address, so some chains can never appear: a micro quarter is "
                    "1350 seconds and no standard interval divides it"
                )

    # His two-agreeing-opens precondition, counted rather than judged.
    #
    # Recomputed from the raw grid instead of read off `drawing.true_opens`,
    # and that is not laziness in reverse. The drawing holds wire models; the
    # rule lives in `quarters.stacked_opens` and takes the grid's own dataclass.
    # Partitioning the wire models here would be a SECOND implementation of his
    # rule, and two of those drift. Recomputing is pure clock arithmetic on bars
    # already in memory and costs no provider call.
    if request.session.true_opens:
        levels = true_opens(rows, request.session.true_opens)
        if levels:
            stack = stacked_opens(rows[-1].close, levels)
            report.stacked = OpenStack(
                price=rows[-1].close,
                above=[
                    TrueOpenLevel(degree=o.degree, time=o.time, price=o.price)
                    for o in stack.above
                ],
                below=[
                    TrueOpenLevel(degree=o.degree, time=o.time, price=o.price)
                    for o in stack.below
                ],
            )

    # Judas Swing template from London session bias. Costs no provider call:
    # it reads the London window from bars already in memory. Only meaningful
    # when the last bar is inside or past the NY AM kill zone.
    report.judas = _judas(rows)

    # --- the two blocks that cost provider calls ---------------------------
    # Gathered rather than awaited in turn: they are independent I/O, and eight
    # serial fetches on a live request is a latency bug waiting to happen. Each
    # is caught on its own, because one unreachable timeframe must not throw away
    # the zones, plans and structure this response already holds correctly.
    if params.bias_timeframes:
        wanted = list(dict.fromkeys(params.bias_timeframes))
        fetched = await asyncio.gather(
            *(
                fetch(request.symbol, tf, params.bias_bars, used)
                for tf in wanted
            ),
            return_exceptions=True,
        )
        series: dict[str, list[Candle]] = {}
        for tf, got in zip(wanted, fetched):
            fetches += 1
            if isinstance(got, BaseException):
                notes.append(f"bias on {tf} unavailable: {got}")
            else:
                series[tf] = got[0]
        if series:
            found = bias.alignment(series)
            report.bias = BiasAlignment(
                degrees=[
                    DegreeBias(
                        timeframe=d.timeframe, bias=d.bias, bars=d.bars,
                        needs=d.needs, last_break=d.last_break,
                        reversal_confirmed=(
                            None if d.last_break is None else d.last_break == "CHoCH"
                        ),
                        reason=d.reason,
                    )
                    for d in found.degrees
                ],
                aligned=found.aligned,
                direction=found.direction,
                disagreeing=list(found.disagreeing),
            )

    if params.ssmt_symbols and params.ssmt_degrees:
        symbols = list(dict.fromkeys([request.symbol, *params.ssmt_symbols]))
        # The basket's source, which is the CHART's unless asked otherwise. The
        # chart symbol is refetched from it rather than reused, because a basket
        # spanning two venues is the artefact aligned.py exists to prevent - see
        # `ssmt_provider` for why that is worth an extra call.
        ssmt_source = params.ssmt_provider or used
        if ssmt_source != used:
            notes.append(
                f"SSMT read the whole basket on {ssmt_source}, while the chart "
                f"is drawn from {used}. The divergences are a statement about "
                f"{ssmt_source} and the levels on screen are not."
            )
        # The synthetic provider INVENTS an instrument for any string, seeded by
        # the symbol's own name, so nothing here can fail and a typo produces a
        # fictional partner rather than an error. Measured while writing the
        # tests: a divergence read of BTCUSDT against "NOT_A_REAL_SYMBOL"
        # returned 76 confident-looking hits. They are real arithmetic on fake
        # bars, which is the most misleading kind of correct. Said out loud for
        # the same reason the cost table announces a fallback row rather than
        # printing a number that looks like a measurement.
        if ssmt_source == "synthetic":
            notes.append(
                "SSMT ran on the synthetic provider, which generates a series "
                "for any symbol including one that does not exist: these "
                "divergences are arithmetic on fabricated bars and are not a "
                "reading of any market"
            )
        try:
            series, load_stats = await load_aligned(
                symbols, request.interval, request.bars, ssmt_source
            )
            # Minus one only when the chart's own bars were already in hand,
            # which stops being true the moment the basket is on another source.
            fetches += len(symbols) - (ssmt_source == used)
            stats["ssmt_grid"] = load_stats.get("grid")
            for degree in dict.fromkeys(params.ssmt_degrees):
                events, _ = ssmt_read(series, degree)
                report.ssmt.extend(
                    SSMTHit(
                        degree=e.degree, side=e.side, took=e.took, failed=e.failed,
                        knowable_at=e.knowable_at, took_prior=e.took_prior,
                        took_now=e.took_now, failed_prior=e.failed_prior,
                        failed_now=e.failed_now,
                    )
                    for e in events
                )
        except (ProviderError, ValueError) as exc:
            notes.append(f"SSMT unavailable: {exc}")

    # High-impact events on today's NY date. The calendar is cached (15 min TTL)
    # so this adds at most one HTTP call per quarter hour, not one per redraw.
    try:
        week = await news.read()
        if not week.error:
            today = clock.to_ny(rows[-1].time).date()
            high = news.select(week.events, impact="High")
            report.news = [
                NewsItem(
                    time=e.time, title=e.title,
                    currency=e.currency, impact=e.impact,
                )
                for e in high
                if clock.to_ny(e.time).date() == today
            ]
    except Exception as exc:
        notes.append(f"news calendar unavailable: {exc}")

    report.notes = notes
    # Counted and reported, because an expensive option that hides its cost is
    # how a UI ends up hammering a rate-limited feed. A fully specified request
    # turns one provider call into eight, and Yahoo answers 429 when hammered.
    stats["extra_fetches"] = fetches
    stats["notes"] = len(notes)
    return report, stats

def _reading(source: pools_read.RangeReading) -> RangeReading:
    """One candidate range, from the detector's dataclass onto the wire."""
    return RangeReading(
        anchor=source.anchor,
        degree=source.degree,
        time_from=source.time_from,
        time_to=source.time_to,
        complete=source.complete,
        bars=source.bars,
        high=source.high,
        low=source.low,
        equilibrium=source.equilibrium,
        position=source.position,
        reading=source.reading,
    )


def _discount(rows: list[Candle], params: ChecklistParams) -> PremiumDiscount | None:
    """His third checklist question, with every anchor's answer rather than one.

    Returns None when the degree has no parent, which is a fact about the grid
    rather than a failure: nothing sits above `year`.
    """
    try:
        read = pools_read.premium_discount(
            rows, degree=params.degree, anchor=params.discount_anchor
        )
    except ValueError:
        return None
    if read is None:
        return None
    return PremiumDiscount(
        degree=read.degree,
        anchor=read.anchor,
        at=read.at,
        price=read.price,
        chosen=_reading(read.chosen) if read.chosen is not None else None,
        readings=[_reading(r) for r in read.readings],
        absent=list(read.absent),
        disagree=read.disagree,
    )


def _judas(rows: list[Candle]) -> JudasReading | None:
    """Classify the Judas Swing template from the London session on the day
    of the last bar. Returns None when no London bars exist in the window."""
    last_ny = clock.to_ny(rows[-1].time)
    london_open = clock.ny_wall(
        last_ny.year, last_ny.month, last_ny.day, 3,
    )
    london_close = clock.ny_wall(
        last_ny.year, last_ny.month, last_ny.day, 12,
    )
    london_bars = [r for r in rows if london_open <= r.time < london_close]
    if not london_bars:
        return None

    move = london_bars[-1].close - london_bars[0].open
    rng = max(r.high for r in london_bars) - min(r.low for r in london_bars)
    avg_bar = sum(r.high - r.low for r in rows[-14:]) / min(14, len(rows))
    range_pct = rng / avg_bar if avg_bar > 0 else 0.0

    if move > 0:
        london_bias = "bullish"
    elif move < 0:
        london_bias = "bearish"
    else:
        london_bias = "neutral"

    js = judas_classify(london_bias, range_pct)
    return JudasReading(
        template=js.template,
        london_bias=js.london_bias,
        judas_direction=js.judas_direction,
        expansion_direction=js.expansion_direction,
        description=js.description,
    )
