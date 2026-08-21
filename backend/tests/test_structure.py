"""The structure overlay, on series whose correct answer is arithmetic.

`swings`, `breaks` and `bias_series` are already covered in
test_refine_and_crowding.py, including the one rule that matters most - a swing
is not knowable until the bars to its right have printed. These tests cover
`overlay()`, which draws those primitives at two fractal widths, and they extend
the anti-lookahead assertion to the drawn objects: a break tested against a
swing nobody could see yet would produce a beautiful directional edge made
entirely of the future.

Nothing here tests whether the overlay predicts anything. It does not: H6 and H9
measured that and both came out null. See the module docstring.

Run with:  .venv\\Scripts\\python -m pytest tests -q
"""

from __future__ import annotations

import numpy as np

from app.detect.structure import (
    bias_series,
    breaks,
    mss_sweeps,
    overlay,
    swings,
    walk_breaks,
)
from app.models import Candle, StructureParams
from tools.mss import lux_swings

STEP = 900
T0 = 1_700_000_000 // 86_400 * 86_400


def bar(t: int, o: float, c: float, hp: float = 0.01, lp: float = 0.01) -> Candle:
    return Candle(
        time=t, open=o, close=c, high=max(o, c) + hp, low=min(o, c) - lp, volume=1000.0
    )


def wave(points: list[float], per: int = 4) -> list[Candle]:
    """A zigzag through `points`, `per` bars per leg. Pivot bars are exact."""
    rows: list[Candle] = []
    t = T0
    for a, b in zip(points, points[1:]):
        for k in range(per):
            o = a + (b - a) * k / per
            c = a + (b - a) * (k + 1) / per
            rows.append(bar(t, o, c))
            t += STEP
    return rows


def flat(rows: list[Candle], closes: list[float]) -> list[Candle]:
    """Append quiet bars at the given closes, so nothing new pivots by accident."""
    t = rows[-1].time + STEP
    for k, c in enumerate(closes):
        rows.append(bar(t + k * STEP, c, c))
    return rows


def params(**overrides) -> StructureParams:
    # Small widths so a hand-built fixture is long enough to confirm swings at
    # both scales. The shipped defaults are 50 and 5.
    base = {"swing_n": 5, "internal_n": 2, "max_events": 0}
    return StructureParams(**(base | overrides))


def at(rows: list[Candle], time: int) -> int:
    return next(i for i, c in enumerate(rows) if c.time == time)


def swept_series() -> tuple[list[Candle], float]:
    """A swing high, then a bar whose wick pierces it and whose close does not."""
    rows = wave([100, 110, 100], per=4)
    level = max(c.high for c in rows)
    t = rows[-1].time + STEP
    # The sweep: high well above the level, close far below it.
    rows.append(bar(t, 100.0, 100.5, level + 5 - 100.5, 0.5))
    return rows, level


# --------------------------------------------------------------------------
# Two scales, and the crossing between them
# --------------------------------------------------------------------------


def test_an_internal_event_reports_the_swing_bias_that_was_knowable_at_its_bar():
    """The crossing docs/FIDELITY.md listed as missing: the small fractal
    conditioned on the large one. The bias must be the one `bias_series` gives at
    that same bar, which uses only breaks already knowable there."""
    rows = wave([100, 120, 105, 140, 110, 150, 115], per=6)
    p = params()

    _, events, _ = overlay(rows, p)
    reference = bias_series(rows, p.swing_n, p.swing_n)

    internal = [e for e in events if e.scale == "internal"]
    assert internal, "the fixture must produce internal events"
    for e in internal:
        expected = reference[at(rows, e.time)] == e.direction
        assert e.aligned_with_swing is bool(expected)
    assert any(e.aligned_with_swing for e in internal), "and some must agree"


def test_a_swing_scale_event_never_answers_the_alignment_question():
    """It is the question of whether the SUBORDINATE scale agreed. Asking it of
    the senior scale would be asking whether it agreed with itself."""
    rows = wave([100, 120, 105, 140, 110, 150], per=6)

    _, events, stats = overlay(rows, params())

    major = [e for e in events if e.scale == "swing"]
    assert major, "the fixture must produce swing-scale events"
    assert all(e.aligned_with_swing is None for e in major)
    assert stats["events.swing"] and stats["events.internal"]


def test_both_scales_are_drawn_and_counted_apart():
    rows = wave([100, 120, 105, 140, 110, 150], per=6)

    swings_drawn, events, stats = overlay(rows, params())

    for scale in ("swing", "internal"):
        assert stats[f"swings.{scale}"] == sum(
            s.scale == scale for s in swings_drawn
        )
        assert stats[f"events.{scale}"] == sum(e.scale == scale for e in events)
    assert stats["swings.total"] == len(swings_drawn)
    assert stats["events.total"] == len(events)


# --------------------------------------------------------------------------
# Sweep reversal: reported, never required
# --------------------------------------------------------------------------


def test_a_sweep_price_never_closed_back_inside_reports_none():
    """Liquidity taken and ACCEPTED. Every source calls a sweep taken and
    rejected, so the sweep that was not rejected has to be visible as such -
    and it must still be drawn, because a filter here would delete the very
    population the deviation is about."""
    rows, level = swept_series()
    rows = flat(rows, [level + 3, level + 4, level + 5, level + 6])
    p = params(sweep_reversal_bars=3)

    _, events, stats = overlay(rows, p)

    sweeps = [e for e in events if e.kind == "SWEEP"]
    assert sweeps, "the wick through must still be drawn"
    assert all(e.reversed_within is None for e in sweeps)
    assert stats["kind.SWEEP"] == len(sweeps)
    assert stats["sweeps.reversed"] == 0


def test_a_rejected_sweep_reports_the_bar_it_was_rejected_on():
    rows, level = swept_series()
    rows = flat(rows, [level - 4, level - 4, level - 4, level - 4])
    p = params(sweep_reversal_bars=3)

    _, events, stats = overlay(rows, p)

    sweeps = [e for e in events if e.kind == "SWEEP"]
    assert sweeps
    # The sweep bar's own close is inside by construction, so the count starts
    # at the next bar: 0 would be true of every sweep ever recorded.
    assert all(e.reversed_within == 1 for e in sweeps)
    assert stats["sweeps.reversed"] == len(sweeps)


def test_a_reversal_outside_the_window_is_not_a_reversal():
    rows, level = swept_series()
    rows = flat(rows, [level + 3, level + 3, level + 3, level - 4, level - 4])
    p = params(sweep_reversal_bars=3)

    _, tight, _ = overlay(rows, p)
    _, wide, _ = overlay(rows, params(sweep_reversal_bars=4))

    assert [e.reversed_within for e in tight if e.kind == "SWEEP"] == [None]
    assert [e.reversed_within for e in wide if e.kind == "SWEEP"] == [4]


def test_a_sweep_does_not_disarm_the_level_it_swept():
    """The doctrine is silent on whether the level should be raised to the sweep
    wick, and raising it would change every break downstream. `overlay` must not
    quietly settle that question - the primitives' behaviour has to survive."""
    rows, level = swept_series()
    rows = flat(rows, [level - 4, level + 6, level + 6])

    raw, _ = breaks(rows, 2, 2)
    _, events, _ = overlay(rows, params())

    broke = [e for e in events if e.scale == "internal" and e.kind in ("BOS", "CHoCH")]
    assert broke, "the level must still be there to break"
    assert [e.level for e in broke] == [
        b.level for b in raw if b.kind != "SWEEP"
    ]


# --------------------------------------------------------------------------
# MSS as an object
# --------------------------------------------------------------------------


def mss_series(down_first: bool, gap: int = 0) -> list[Candle]:
    """A swing high and a swing low, a sweep of one of them, then a break.

    `down_first` makes the break go the OPPOSITE way to the sweep, one of the
    three requirements. The leg here also leaves a fair value gap, which is the
    third; `mss_series_no_gap` is the same pair without it.
    `gap` pushes the break that many quiet bars further from the sweep.
    """
    rows = wave([100, 110, 95, 108, 96], per=4)
    high = max(c.high for c in rows[:12])
    low = min(c.low for c in rows)
    t = rows[-1].time + STEP
    # Sweep upward: wick above the swing high, close back down.
    rows.append(bar(t, 100.0, 100.5, high + 5 - 100.5, 0.5))
    target = low - 3 if down_first else high + 6
    # A flat run breaks no level and, by the tie rule in `swings`, pivots nothing.
    return flat(rows, [100.0] * gap + [target, target, target])


def mss_series_no_gap() -> list[Candle]:
    """The same sweep-then-opposite-break pair, with NO gap left in the leg.

    Only the break bar differs from `mss_series(down_first=True)`: it still closes
    below the swing low, but it carries a tall upper wick that reaches back over
    the low of the bar before the sweep, so the wick-to-wick test finds no
    inefficiency anywhere in the leg. That is the one variable, so any difference
    in what gets drawn is the displacement requirement and nothing else.
    """
    rows = wave([100, 110, 95, 108, 96], per=4)
    high = max(c.high for c in rows[:12])
    low = min(c.low for c in rows)
    before_sweep = rows[-1].low
    t = rows[-1].time + STEP
    rows.append(bar(t, 100.0, 100.5, high + 5 - 100.5, 0.5))
    target = low - 3
    rows.append(
        Candle(
            time=t + STEP, open=100.0, close=target,
            high=before_sweep + 0.5, low=target - 0.5, volume=1000.0,
        )
    )
    return flat(rows, [target, target])


def test_an_mss_requires_a_break_opposite_to_the_sweep():
    opposite = mss_series(down_first=True)
    same_way = mss_series(down_first=False)

    _, against, _ = overlay(opposite, params(mss_window=5))
    _, along, _ = overlay(same_way, params(mss_window=5))

    shifts = [e for e in against if e.kind == "MSS"]
    assert shifts, "a sweep up then a break down is the MSS reading"
    assert all(e.direction == -1 for e in shifts)
    assert [e.kind for e in along if e.kind == "MSS"] == [], (
        "a sweep up then a break UP is a delayed continuation, not a shift"
    )


def test_an_mss_is_drawn_beside_its_own_break_not_instead_of_it():
    """An MSS is a break with one extra property. Swallowing the break would
    leave the drawn population disagreeing with the measured one, which is the
    population tools/mss.py reports on."""
    rows = mss_series(down_first=True)

    _, events, stats = overlay(rows, params(mss_window=5))

    shifts = [e for e in events if e.kind == "MSS"]
    assert shifts
    for e in shifts:
        twin = [
            x for x in events
            if x.kind != "MSS" and x.time == e.time and x.scale == e.scale
            and x.level == e.level and x.direction == e.direction
        ]
        assert twin, "the underlying break must still be emitted"
        assert e.swept_at is not None and e.swept_at < e.time
    assert stats["kind.MSS"] == len(shifts)


def test_an_mss_requires_a_gap_in_the_leg():
    """The third requirement, and the one H9 never tested. ICT rules the two-part
    reading out by name - "that's not it, folks, that's not it. You have to see it
    go below that in displacement" - and operationalises displacement as a fair
    value gap inside the leg, not as a size: "if there isn't one there, you don't
    have a trade". So a sweep and an opposite break with a flat leg is a CHoCH,
    and the break must still be drawn, because the requirement belongs to the NAME
    and deletes no population."""
    displaced = mss_series(down_first=True)
    flat_leg = mss_series_no_gap()
    p = params(mss_window=5)

    _, with_gap, _ = overlay(displaced, p)
    _, without, stats = overlay(flat_leg, p)

    assert [e for e in with_gap if e.kind == "MSS"], "the gap leg is the MSS"
    assert [e for e in without if e.kind == "MSS"] == [], (
        "a sweep then an opposite break with no gap in the leg is not a shift"
    )
    assert stats["kind.MSS"] == 0
    # The break itself survives, at both scales, exactly as before.
    assert [e for e in without if e.kind in ("BOS", "CHoCH") and e.direction == -1]
    assert [e for e in without if e.kind == "SWEEP" and e.direction == 1]


def test_an_mss_matches_the_shared_definition_the_harness_measures():
    """`mss_sweeps` is the definition of record and tools/mss.py imports the same
    function. If the drawing applied any other rule the chart and the calibration
    would be about different objects, which is the whole reason the pairing lives
    in one place instead of being restated in both."""
    rows = mss_series(down_first=True)
    window = 5

    raw, _ = breaks(rows, 2, 2)
    high = np.array([c.high for c in rows], dtype=np.float64)
    low = np.array([c.low for c in rows], dtype=np.float64)
    sweeps = [e for e in raw if e.kind == "SWEEP"]
    expected = [
        b.time for b in raw
        if b.kind != "SWEEP" and mss_sweeps(high, low, sweeps, b, window)
    ]

    _, events, _ = overlay(rows, params(mss_window=window))

    got = [e.time for e in events if e.kind == "MSS" and e.scale == "internal"]
    assert got == expected
    assert expected, "the fixture must produce at least one shift"


def test_a_sweep_too_far_back_does_not_qualify_a_break():
    rows = mss_series(down_first=True, gap=3)  # the break is 4 bars after the sweep

    _, near, _ = overlay(rows, params(mss_window=5))
    _, far, _ = overlay(rows, params(mss_window=2))

    assert [e for e in near if e.kind == "MSS"]
    assert [e for e in far if e.kind == "MSS"] == []


# --------------------------------------------------------------------------
# The pivot sensitivity, which reports a difference and adopts nothing
# --------------------------------------------------------------------------


def test_the_one_sided_pivot_reports_highs_the_symmetric_fractal_rejects():
    """The sensitivity in tools/mss.py only means anything if the LuxAlgo rule
    reimplemented there really is one-sided, so two properties are pinned here.

    It reports a high that its own left neighbour already matched or exceeded,
    which our fractal can never do: `swings` demands a STRICT maximum on the left
    and LuxAlgo tests nothing on the left at all. And it still reports the pivot
    `length` bars late, so the difference between the two rules is selectivity and
    NOT hindsight. That second one is why the sensitivity is honest to report and
    still not a reason to switch.
    """
    rows = wave([100, 120, 105, 140, 110, 150, 115, 160, 120], per=6)
    high = np.array([c.high for c in rows], dtype=np.float64)
    low = np.array([c.low for c in rows], dtype=np.float64)
    length = 5

    ours = swings(high, low, length, length)
    lux = lux_swings(high, low, length)

    assert all(s.confirmed_at == s.index + length for s in lux)
    left_dominated = [
        s for s in lux
        if s.high and s.index >= 1 and high[s.index - 1] >= high[s.index]
    ]
    assert left_dominated, "the fixture must show the one-sided difference"
    ours_highs = {s.index for s in ours if s.high}
    assert not any(s.index in ours_highs for s in left_dominated)
    assert len(lux) > len(ours), "one-sided is the less selective of the two"


# --------------------------------------------------------------------------
# The cap, and the rule that makes it safe
# --------------------------------------------------------------------------


def test_zero_max_events_caps_nothing_and_a_finite_cap_says_what_it_dropped():
    """A recency cap silently confines a sample to the tail of the history, and
    that has already cost this project one full round of calibration. So 0 must
    mean no cap, and any cap that bites must be countable."""
    rows = wave([100, 120, 105, 140, 110, 150, 115, 160], per=6)

    _, everything, uncapped = overlay(rows, params(max_events=0))
    _, few, capped = overlay(rows, params(max_events=3))

    assert uncapped["events.dropped_by_cap"] == 0
    assert len(everything) == uncapped["events.total"]
    assert len(few) == 3 < len(everything)
    assert capped["events.dropped_by_cap"] == len(everything) - 3
    # The cap is applied LAST, so every count still describes the whole history.
    assert capped["events.total"] == uncapped["events.total"]
    assert capped["kind.BOS"] == uncapped["kind.BOS"]
    # Newest kept, which is the whole hazard: it is the tail, not a sample.
    assert [e.time for e in few] == [e.time for e in everything[-3:]]


def test_no_overlay_event_ever_references_a_swing_confirmed_after_it():
    """The same rule test_no_break_ever_uses_a_swing_confirmed_after_it pins on
    `breaks`, extended to what is DRAWN: both scales, all four kinds, and the
    MSS's sweep too. A drawing that shows a break against a swing nobody could
    see yet is hindsight with a line on it."""
    rows = wave([100, 120, 105, 140, 110, 150, 115, 160], per=6)

    drawn, events, _ = overlay(rows, params())

    confirmed = {(s.scale, s.time): s.confirmed_at for s in drawn}
    assert events, "the fixture must produce events"
    for e in events:
        assert e.swing_time < e.time
        assert confirmed[(e.scale, e.swing_time)] <= e.time
        if e.swept_at is not None:
            assert e.swept_at < e.time
    for s in drawn:
        assert s.confirmed_at > s.time


def test_a_level_is_swept_once_and_the_breaks_are_untouched():
    """`docs/FIDELITY.md` listed unlimited re-sweeping as a departure, and the
    measured consequence was 8,725 sweeps against 9,210 breaks - one sweep per
    break, which is not what the object is.

    The most-used open-source implementation of the IDENTICAL predicate,
    LuxAlgo's Liquidity Sweeps at 20,752 likes, marks the level instead:
    `if not oO and not get.wic ... get.wic := true`. So the predicate was never
    the difference; re-arming was.

    Measured on 3000 bars of XAUUSD 15m: at swing width 5, 147 sweeps came from
    88 distinct levels and one level was swept SEVEN times; the fix leaves 88
    from 88. At width 50, 17 from 10 becomes 10 from 10. The BREAK count is
    unchanged in both - 133 and 14 - which is the property that matters: this
    drops duplicates and nothing else.

    `resweep=True` is kept so the harness can reproduce numbers that were
    measured before the fix, not because either reading is in doubt.
    """
    # Built as raw arrays: the point is one swing high and three wicks through
    # it that never close above, which is easier to read as numbers than as a
    # chain of helper calls.
    high = np.array(
        [95.0, 95.0, 95.0, 95.0, 100.0, 95.0, 95.0, 95.0, 95.0,
         102.0, 95.0, 102.0, 95.0, 102.0, 95.0]
    )
    low = np.array(
        [94.0, 94.0, 94.0, 94.0, 99.0, 94.0, 94.0, 94.0, 94.0,
         96.0, 94.0, 96.0, 94.0, 96.0, 94.0]
    )
    close = np.array(
        [94.5, 94.5, 94.5, 94.5, 99.5, 94.5, 94.5, 94.5, 94.5,
         97.0, 94.5, 97.0, 94.5, 97.0, 94.5]
    )
    times = [i * 900 for i in range(len(high))]
    found = swings(high, low, 4, 4)

    once = walk_breaks(high, low, close, times, found)
    many = walk_breaks(high, low, close, times, found, resweep=True)

    once_sweeps = [b for b in once if b.kind == "SWEEP"]
    many_sweeps = [b for b in many if b.kind == "SWEEP"]
    assert len(once_sweeps) == 1, "one level, one sweep"
    assert len(many_sweeps) >= 2, "the old behaviour re-armed and must still be reachable"
    assert once_sweeps[0].index == many_sweeps[0].index, "the FIRST taking is the one kept"
    assert [b.kind for b in once if b.kind != "SWEEP"] == [
        b.kind for b in many if b.kind != "SWEEP"
    ], "breaks must be untouched by the sweep rule"
