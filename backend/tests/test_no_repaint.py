"""NOTHING MAY REPAINT. The one property a drawing engine cannot trade away.

A repainting indicator changes what it drew in the PAST as new data arrives. It
looks superb in hindsight and is worthless live, because the picture you are
reading now is not the picture that was there when the decision had to be made.
Every other property in this project is negotiable against evidence; this one is
not, because a chart that rewrites itself cannot be evidence of anything.

TWO DIRECTIONS, AND BOTH ARE REAL USER ACTIONS.

  - GROWING RIGHT is a live chart: the same window start, more bars arriving.
  - GROWING LEFT is the Bars picker: the same right edge, more history behind it.

The second is the one that gets forgotten, and it is where every defect this file
was written after actually lived. Changing 500 to 20000 must not move a line.

WHAT IS ALLOWED TO CHANGE, stated precisely, because a test that forbids all
change would forbid the engine working:

  - AN OBJECT MAY APPEAR. More history reveals older formations. That is not
    repaint; nothing already drawn moved.
  - A LIFECYCLE MAY ADVANCE. A fresh zone becomes tested, then broken, as price
    moves forward. It may never go BACKWARDS.
  - AN UNMEASURED FIELD MAY BECOME MEASURED, when the field says it is unmeasured.
    `range_pos` is None until the dealing range confirms and the canvas prints no
    letter for it, so gaining a value adds a letter that was never absent-by-
    assertion. `formation_score` falls back to a neutral 0.5 inside its own
    200-bar volume warm-up.

WHAT MAY NEVER CHANGE: geometry. A price, an edge, a boundary, a band. If a drawn
coordinate differs between two windows that both contain the object, that is a
repaint and this file fails.

MEASURED DEFECTS THIS FILE WAS WRITTEN AFTER, all found growing LEFT:

  - 7 true opens. A boundary before the window's first bar cannot be told apart
    from a boundary the market was shut on, so the approximate fallback reached
    forward past it: a week open read 4827.589 approximate at 2,000 bars and
    4827.612 EXACT at 20,000. Same named level, two prices, one dropdown.
  - 3 defining ranges. `_closed` proved Q1 had ended and nothing proved it had
    begun inside the data, so a band whose kept two-thirds started before the
    first bar was computed from whatever fraction was in the window - and moved,
    with every projection off it.
"""

from __future__ import annotations

import asyncio

import pytest

from app.detect import DETECTORS
from app.drawing import _HANDLERS, HTF_LAYERS
from app.models import (
    Drawing,
    DrawRequest,
    ImbalanceParams,
    SupplyDemandParams,
)
from app.overlays import bar_overlays
from app.providers import get_candles
from app.quarters import true_opens

#: One fetch, then sliced. The synthetic provider is generated relative to NOW,
#: so two fetches are two different series - but slices of ONE fetch are honest
#: prefixes of one another, which is exactly what a repaint test needs.
BARS = 6000
INTERVAL = "1h"

#: Where the volume baseline and the dealing range are still warming up. A field
#: that says it is unmeasured is allowed to become measured inside this; outside
#: it, nothing may move at all.
WARMUP_BARS = 200

STATE_ORDER = ["fresh", "tested", "mitigated", "broken"]


@pytest.fixture(scope="module")
def series():
    rows, _ = asyncio.run(get_candles("BTCUSDT", INTERVAL, BARS, "synthetic"))
    assert len(rows) > 3000, f"need a long series to slice, got {len(rows)}"
    return rows


def windows(rows):
    """Every prefix a reader could actually be looking at, both directions."""
    out = []
    for cut in range(len(rows) // 2, len(rows), len(rows) // 5):
        out.append(("grew right", rows[:cut]))
    for take in range(len(rows) // 3, len(rows) + 1, len(rows) // 5):
        out.append(("grew left", rows[-take:]))
    return out


# --------------------------------------------------------------- true opens


@pytest.mark.parametrize("approximate", [False, True])
def test_a_true_open_never_changes_its_price(series, approximate):
    """Including the approximate ones, which is where this broke.

    An approximate level is still a drawn line with a price on it. That it is
    dashed and tagged with a `~` says the price came from a bar after the
    boundary; it does not license the price to change.
    """
    degrees = ("quadrennial", "year", "month", "week", "day")
    full = {
        (o.degree, o.time): (o.price, o.bar, o.approximate)
        for o in true_opens(series, degrees, approximate=approximate)
    }
    moved = []
    for how, window in windows(series):
        for o in true_opens(window, degrees, approximate=approximate):
            key = (o.degree, o.time)
            was = (o.price, o.bar, o.approximate)
            if key in full and full[key] != was:
                moved.append(f"{how}: {key} {was} vs {full[key]}")
    assert not moved, "true opens repainted:\n" + "\n".join(moved[:5])


def test_a_boundary_outside_the_window_yields_nothing_rather_than_a_guess(series):
    """The guard behind the fix, asserted directly.

    With the window trimmed past a boundary, that boundary must produce NO level
    - not an approximate one. Inside the function the two cases look identical
    ("no bar on this instant"), and treating them alike is precisely what let a
    level change price when the window grew.
    """
    trimmed = series[len(series) // 2 :]
    start = trimmed[0].time
    for level in true_opens(trimmed, ("day", "week"), approximate=True):
        assert level.time >= start, (
            f"a level at {level.time} sits before the window's first bar {start}"
        )


# ------------------------------------------------------------ defining range


def _dfr(window):
    request = DrawRequest(
        symbol="BTCUSDT",
        interval=INTERVAL,
        bars=len(window),
        provider="synthetic",
        layers=["dfr"],
        dfr={"degrees": ["day", "week"], "max_ranges": 0},
    )
    drawing = Drawing()
    bar_overlays(window, request, drawing, {"dfr"}, None)
    return {
        (b.degree, b.time_from): (
            round(b.high, 8),
            round(b.low, 8),
            round(b.equilibrium, 8),
            tuple(sorted((e.multiple, e.side, round(e.price, 8)) for e in b.extensions)),
        )
        for b in drawing.dfr
    }


def test_a_defining_range_never_moves(series):
    """Band, midpoint and every projection off it.

    The projections matter as much as the band: they are `abs(multiple)` of the
    band's own height, so a band that moves by a hair moves four lines with it.
    """
    full = _dfr(series)
    assert full, "the fixture has to produce some bands"
    moved = []
    for how, window in windows(series):
        for key, value in _dfr(window).items():
            if key in full and full[key] != value:
                moved.append(f"{how}: {key}")
    assert not moved, "defining ranges repainted:\n" + "\n".join(moved[:5])


# -------------------------------------------------------------------- gaps


def _gaps(window):
    request = DrawRequest(
        symbol="BTCUSDT",
        interval=INTERVAL,
        bars=len(window),
        provider="synthetic",
        layers=["gaps"],
        gaps={"keep": 0},
    )
    drawing = Drawing()
    bar_overlays(window, request, drawing, {"gaps"}, None)
    return (
        {
            # GEOMETRY AND THE HEDGE FLAG ARE SEPARATED, because they obey
            # different rules - see the assertion below.
            (g.kind, g.open_time): (
                (round(g.top, 8), round(g.bottom, 8), round(g.ce, 8)),
                g.approximate,
            )
            for g in drawing.gaps
        },
        {
            tuple(sorted(s.open_times)): (
                round(s.top, 8),
                round(s.bottom, 8),
                round(s.fraction, 8),
            )
            for s in drawing.gap_stacks
        },
    )


def test_an_opening_gap_and_its_stack_never_move(series):
    """Geometry frozen; the HEDGE FLAG may only ever relax, never tighten.

    THIS TEST WAS FAILING AND THE ENGINE WAS RIGHT, which is the interesting half.
    It compared geometry and `approximate` as one tuple and forbade any change to
    either, and an NWOG came back `approximate=True` on the one window whose FIRST
    BAR was the gap's own closing bar - the Friday close - and False everywhere
    else. Its top, bottom and midpoint were identical in every window.

    That is the engine being MORE CAUTIOUS with less history, not less accurate. If
    the closing bar is the first bar in the window there is nothing before it to
    prove the session really ran up to it, so the edge is the best price the feed
    can offer rather than the last one that traded - which is exactly what
    `approximate` says. The same shape as the true-open guard: a boundary at the
    edge of a window cannot be told apart from a boundary the market was shut on.

    So the honest invariant is DIRECTIONAL, and the direction was measured before
    it was allowed rather than assumed. Across 261 gaps and eight windows of this
    fixture:

        price or midpoint moved                     0
        hedged with less history (allowed)          1
        claimed EXACT with less history (forbidden) 0

    The dangerous direction is the last one: a band drawn as precise on a short
    window and hedged once more bars arrive would be a confidence claim that
    shrank under the reader. It never happens, and this test fails if it ever
    starts, while no longer failing on caution.
    """
    full_gaps, full_stacks = _gaps(series)
    moved, overclaimed = [], []
    for how, window in windows(series):
        gaps, stacks = _gaps(window)
        for key, (shape, approximate) in gaps.items():
            if key not in full_gaps:
                continue
            full_shape, full_approximate = full_gaps[key]
            if shape != full_shape:
                moved.append(f"{how}: gap {key} {shape} vs {full_shape}")
            # Exact on the SHORTER window while the full one hedges.
            if full_approximate and not approximate:
                overclaimed.append(f"{how}: gap {key} claimed exact on less history")
        moved += [
            f"{how}: stack {k}"
            for k, v in stacks.items()
            if k in full_stacks and full_stacks[k] != v
        ]
    assert not moved, "gap geometry repainted:\n" + "\n".join(moved[:5])
    assert not overclaimed, (
        "a gap edge was drawn as EXACT on a shorter window and hedged on a longer "
        "one, so its confidence shrank as history arrived:\n"
        + "\n".join(overclaimed[:5])
    )


# --------------------------------------------------- higher-timeframe zones


def _htf(window, layer):
    """Every box the top-down pass projects onto this chart, for one layer.

    A NEW SURFACE, and it needs its own check rather than inheriting the local
    one. HTF projection was wired to supply and demand alone; four more box
    detectors reach it now, and each of them is being run on bars this module
    aggregates rather than on bars a provider sent. Two things there could move
    under the reader and neither would show up in the local-timeframe tests:
    a bucket boundary that shifts when the window grows, and the live-zone right
    edge that `_htf_zones` carries forward to the chart's last bar.
    """
    request = DrawRequest(
        symbol="BTCUSDT",
        interval=INTERVAL,
        bars=len(window),
        provider="synthetic",
        layers=[layer],
        htf="1d",
    )
    drawing = Drawing()
    meta: dict[str, object] = {}
    build_layer = _HANDLERS[layer]
    build_layer(window, request, drawing, meta)
    return {
        z.id: (round(z.top, 8), round(z.bottom, 8), z.time_from, z.side.value)
        for z in drawing.zones
        if z.timeframe == "1d"
    }


@pytest.mark.parametrize("layer", sorted(HTF_LAYERS))
def test_a_projected_higher_timeframe_box_never_moves(series, layer):
    """Geometry and left edge, for all five box detectors that can project.

    The RIGHT edge is deliberately not asserted: `_htf_zones` carries a live
    zone's `time_to` forward to the chart's last bar so it does not appear to
    stop early, which means it advances by design as bars arrive. Everything that
    describes WHERE the box is - both prices, its opening bar, its side - may not.
    """
    full = _htf(series, layer)
    if not full:
        pytest.skip(f"{layer} projects no daily box on this fixture")
    moved = []
    for how, window in windows(series):
        for zid, value in _htf(window, layer).items():
            if zid in full and full[zid] != value:
                moved.append(f"{how}: {zid} {value} vs {full[zid]}")
    assert not moved, f"projected {layer} boxes repainted:\n" + "\n".join(moved[:5])


# ---------------------------------------- relative equal highs and lows


def _shelves(window):
    """Every REQH/REQL shelf, keyed so a moved price shows up as a missing key.

    The COUNT is deliberately not in the key. A shelf's touch count grows as more
    swings join it, which is the same kind of change a zone's lifecycle makes:
    nothing already drawn moves. Its price, its side and the bar it became
    knowable on are what may not.
    """
    from app.liquidity import equal_levels

    return {
        (level.name.split()[0], round(level.price, 8)): level.knowable_at
        for level in equal_levels(window, swing_n=10)
    }


def test_an_equal_high_shelf_never_moves(series):
    """Price and knowable-bar frozen, in both directions.

    Growing LEFT is the one that matters here and it is the reason this object
    could be got wrong: one of the two tolerances in circulation among open-source
    implementations is a fraction of the LOADED WINDOW's range, so under that rule
    a shelf would appear and vanish as the reader moved the Bars picker with no
    candle having moved. This engine's tolerance is ATR-relative for exactly that
    reason, and this asserts the consequence rather than trusting the argument.
    """
    full = _shelves(series)
    if not full:
        pytest.skip("no shelf on this fixture")
    moved = []
    for how, window in windows(series):
        for key, knowable in _shelves(window).items():
            if key in full and full[key] != knowable:
                moved.append(f"{how}: {key} knowable {knowable} vs {full[key]}")
    assert not moved, "equal-high shelves repainted:\n" + "\n".join(moved[:5])


# -------------------------------------------------------------------- zones


def _zones(window, layer="supply_demand"):
    #: Which parameter block each detector reads. `app/layers.py` is the
    #: authority and this mirrors it for two entries; a sixth detector added
    #: there and not here fails loudly with a KeyError rather than being
    #: silently skipped.
    params = (
        SupplyDemandParams(max_zones_per_side=0, show_broken=True)
        if layer == "supply_demand"
        else ImbalanceParams(max_zones_per_side=0, show_broken=True)
    )
    zones, _ = DETECTORS[layer](window, params)
    return {z.id: z for z in zones}


@pytest.mark.parametrize("layer", sorted(HTF_LAYERS))
def test_a_zone_never_moves_and_its_lifecycle_never_runs_backwards(series, layer):
    """Geometry is frozen; the lifecycle may only advance.

    Both halves are needed. Freezing everything would forbid a fresh zone ever
    becoming tested, which is the engine working. Freezing nothing would let a
    box move.

    PARAMETRISED SINCE 1 September 2026, and it matters which way. Until then
    this ran on `supply_demand` alone, so the only base-timeframe repaint
    evidence for `fvg`, `order_block`, `ifvg` and `breaker` was that they share
    `replay_lifecycle` - which is reasoning about shared code, and the part
    that is NOT shared is exactly the risky part: each detector decides its own
    `born` bar, and a `born` one bar early lets the candle that created a box
    count as the first test of it. The list comes from `HTF_LAYERS` for the
    same reason the projection test reads it: a sixth detector joins both
    tests in the commit that adds it, or neither.
    """
    full = _zones(series, layer)
    assert full, f"the fixture has to produce some {layer} zones"
    moved, regressed = [], []
    for how, window in windows(series):
        for zid, zone in _zones(window, layer).items():
            done = full.get(zid)
            if done is None:
                continue
            if (round(zone.top, 8), round(zone.bottom, 8)) != (
                round(done.top, 8),
                round(done.bottom, 8),
            ):
                moved.append(f"{how}: {zid}")
            if STATE_ORDER.index(zone.state.value) > STATE_ORDER.index(done.state.value):
                regressed.append(f"{how}: {zid} {zone.state.value} -> {done.state.value}")
    assert not moved, "zone geometry repainted:\n" + "\n".join(moved[:5])
    assert not regressed, "a lifecycle ran backwards:\n" + "\n".join(regressed[:5])


def test_a_formation_score_only_moves_inside_its_own_volume_warm_up(series):
    """The score is bounded, not frozen, and the bound is the thing to pin.

    `formation_score`'s volume factor needs a FULL 200 trailing bars or it falls
    back to a neutral 0.5 - so a zone within 200 bars of the window's start
    scores differently from the same zone with history behind it. That is "not
    measurable here", and the field's own comment says so.

    What must hold is that the bound is exactly 200 bars. Measured on 20,000
    hourly bars of real broker gold: every differing score sat inside the
    warm-up, and ZERO sat outside it. A score that moved outside would mean the
    baseline was reading the window rather than the bars before the leg, which is
    the lookahead this was rewritten to remove.
    """
    full = _zones(series)
    outside = []
    for how, window in windows(series):
        boundary = window[min(WARMUP_BARS, len(window) - 1)].time
        for zid, zone in _zones(window).items():
            done = full.get(zid)
            if done is None:
                continue
            a, b = zone.formation_score, done.formation_score
            if a is None and b is None:
                continue
            if a is not None and b is not None and abs(a - b) <= 1e-9:
                continue
            # AN UNCONFIRMED ZONE IS ALLOWED TO MOVE, and the warm-up boundary was
            # the wrong guard for it.
            #
            # `confirmed` is False while the leg-out is still the NEWEST run, which
            # the panel prints as ", forming" and the canvas draws dashed. Such a
            # zone has been declared non-final by the engine itself, in a field the
            # reader can see, so its score settling once the run ends is the engine
            # working rather than a repaint.
            #
            # Measured on the zone that caught this: at 6000 bars it was
            # confirmed and settled with score 0.7695; cut to 5400 bars its
            # leg-out ran to the last bar, `confirmed` was False, and the score
            # read 0.8049. Same zone, same left edge, one of the two readings
            # explicitly labelled provisional.
            #
            # This surfaced months after the test was written because the synthetic
            # fixture is generated relative to NOW, so which bar lands at the cut
            # moves with the wall clock. The gate still forbids what it was written
            # for: a CONFIRMED zone's score may not move, which is what a baseline
            # reading the window rather than the bars before the leg would cause.
            if not zone.confirmed or not done.confirmed:
                continue
            if zone.time_from >= boundary:
                outside.append(f"{how}: {zid} {a} vs {b}")
    assert not outside, (
        "formation_score moved OUTSIDE the 200-bar volume warm-up, so the "
        "baseline is reading the window rather than the bars before the leg:\n"
        + "\n".join(outside[:5])
    )
