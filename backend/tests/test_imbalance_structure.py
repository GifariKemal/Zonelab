"""The order block's structure gate, and displacement described instead of scored.

Two departures from docs/FIDELITY.md are closed here, and both are closed in a
way that has to be TESTED rather than trusted:

`require_structure_break` demands that the impulse close beyond a confirmed
swing. It ships OFF, so the first thing these tests protect is the default
population: the knobs must be inert, and structure must not even be COMPUTED
when the gate is off. That is asserted by making `breaks` explode rather than by
comparing timings, because a test that measures speed measures the machine.

The wider proof the unit tests cannot give is recorded here instead. Detector
output was dumped on the cached PAXGUSDT 1h series, 20,000 bars, before and after
the change and compared field by field: 12 zones at the shipped defaults, 297
uncapped, 3536 with no state filter - identical in all three, every field except
the two that were added. Stats gained exactly one key,
`rejected_no_structure_break`, which reads 0 with the gate off. With the gate ON
the same 3536 become 936, 26.5%.

The second departure is `Zone.displacement`, and its one delicate property is
`broke_structure`: None means structure was not computed, and a reader must never
be able to confuse that with tested-and-failed. Asserted in both directions.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_imbalance_structure.py -q
"""

from __future__ import annotations

import pytest

from app.detect import imbalance
from app.detect.imbalance import detect_fvg, detect_order_block
from app.detect.structure import breaks
from app.models import Candle, ImbalanceParams, ZoneSide

STEP = 900
T0 = 1_700_000_000 // 86_400 * 86_400


def bar(t: int, o: float, c: float, hp: float = 0.0, lp: float = 0.0) -> Candle:
    return Candle(
        time=t, open=o, close=c, high=max(o, c) + hp, low=min(o, c) - lp, volume=1000.0
    )


def imb(**overrides) -> ImbalanceParams:
    # `structure_n=2` and small windows so a hand-built fixture is long enough to
    # confirm a swing before the impulse reaches it. The shipped default is 5.
    base = {
        "atr_period": 5, "min_gap_atr": 0.0, "displacement_atr": 1.0,
        "displacement_bars": 3, "structure_n": 2, "structure_break_bars": 3,
        "max_zones_per_side": 0, "show_broken": True,
    }
    return ImbalanceParams(**(base | overrides))


def calm(n: int, price: float = 100.0) -> list[Candle]:
    """Flat bars. Every high is equal, so no fractal pivot registers at all and
    the only swing in the fixture is the one the test puts there on purpose."""
    return [bar(T0 + i * STEP, price, price, 0.5, 0.5) for i in range(n)]


def fixture(sweep_only: bool) -> tuple[list[Candle], int, int]:
    """A confirmed swing high at 104, a bearish block, then an impulse at it.

    The two variants differ in ONE bar. Both travel the same distance, so both
    pass the size test and the "last candle" test, and the only thing that can
    separate them is whether the impulse CLOSED beyond the swing or merely wicked
    through it and closed back inside. That is the difference between a break and
    a sweep, and the sources call the second one the opposite event.

    Returns the bars, the block candle's time, and the time of the bar that broke
    or swept.
    """
    rows = calm(20)
    t = T0 + 20 * STEP

    # The swing high: one tall bar, then two lower ones so it CONFIRMS at
    # structure_n=2 before the block candle even prints. A swing that confirms
    # later than the break would be a swing nobody could see yet.
    rows.append(bar(t, 100.0, 103.8, 0.2))            # high 104.0, the level
    rows.append(bar(t + STEP, 103.8, 102.0, 0.0, 0.2))
    rows.append(bar(t + 2 * STEP, 102.0, 101.5, 0.0, 0.2))

    block = t + 3 * STEP
    rows.append(bar(block, 101.5, 100.8, 0.2, 0.3))   # bearish: 101.7 .. 100.5
    rows.append(bar(block + STEP, 100.8, 102.0))      # bullish: the impulse starts

    if sweep_only:
        rows.append(bar(block + 2 * STEP, 102.0, 103.0))
        # The wick pierces 104 and the close does not: a SWEEP.
        rows.append(bar(block + 3 * STEP, 103.0, 103.2, 1.8))
        last = 103.2
    else:
        rows.append(bar(block + 2 * STEP, 102.5, 103.5))
        # Closes above 104: a break. Its low also clears the impulse's first bar,
        # so the leg leaves a fair value gap behind it.
        rows.append(bar(block + 3 * STEP, 103.8, 105.0, 0.0, 0.2))
        last = 105.0

    rows += [
        bar(block + (4 + i) * STEP, last, last, 0.2, 0.2) for i in range(10)
    ]
    return rows, block, block + 3 * STEP


def at(zones, time: int):
    return [z for z in zones if z.time_from == time]


# --------------------------------------------------------------------------
# the default population, which must not move
# --------------------------------------------------------------------------


def test_the_default_path_never_computes_structure_at_all(monkeypatch):
    """`require_structure_break` ships False, and the cheapest proof that the
    default is untouched is that the structure module is never even reached. A
    timing comparison would test the machine; an exploding stub tests the code."""
    rows, block, _ = fixture(sweep_only=True)
    before, _ = detect_order_block(rows, imb())

    def explode(*args, **kwargs):
        raise AssertionError("structure computed with the gate off")

    monkeypatch.setattr(imbalance, "breaks", explode)

    after, stats = detect_order_block(rows, imb())
    assert [z.model_dump() for z in after] == [z.model_dump() for z in before]
    # "No rejections" has to be a reported zero, not an absent key: the whole
    # point of the counter is that "no blocks here" and "the filter ate them"
    # stay distinguishable.
    assert stats["rejected_no_structure_break"] == 0

    with pytest.raises(AssertionError):
        detect_order_block(rows, imb(require_structure_break=True))


def test_the_structure_knobs_are_inert_while_the_gate_is_off():
    """Both windows set to values that would change every verdict, on a series
    whose block only ever swept. Nothing may move."""
    rows, _, _ = fixture(sweep_only=True)

    base, base_stats = detect_order_block(rows, imb())
    fiddled, fiddled_stats = detect_order_block(
        rows, imb(structure_n=17, structure_break_bars=1)
    )

    assert [z.model_dump() for z in fiddled] == [z.model_dump() for z in base]
    assert fiddled_stats == base_stats


# --------------------------------------------------------------------------
# the gate itself
# --------------------------------------------------------------------------


def test_a_block_whose_impulse_only_swept_the_level_is_rejected_and_counted():
    """The rule the sources are loudest about: a sweep is liquidity taken, the
    OPPOSITE event to structure giving way. This impulse travels far enough and
    wicks clean through the swing, and must still not qualify a block."""
    rows, block, swept = fixture(sweep_only=True)

    events, _ = breaks(rows, 2, 2)
    assert [e.kind for e in events if e.time == swept] == ["SWEEP"], (
        "fixture must produce a sweep and nothing else on that bar"
    )

    admitted, off_stats = detect_order_block(rows, imb())
    gated, on_stats = detect_order_block(rows, imb(require_structure_break=True))

    # Without the gate the block is a block, so what removes it below is the
    # gate and not the size test or the "last candle" test.
    assert len(at(admitted, block)) == 1
    assert off_stats["rejected_weak_move"] == on_stats["rejected_weak_move"]
    assert at(gated, block) == []
    assert on_stats["rejected_no_structure_break"] >= 1


def test_a_block_whose_impulse_closed_beyond_a_confirmed_swing_is_admitted():
    rows, block, broke = fixture(sweep_only=False)

    gated, stats = detect_order_block(rows, imb(require_structure_break=True))
    blocks = at(gated, block)

    assert len(blocks) == 1
    assert blocks[0].side is ZoneSide.DEMAND
    # The evidence, on the box, as a bar time a human can go and look at.
    assert blocks[0].structure_break_time == broke

    # And the event at that bar is a real break in the impulse's own direction,
    # read back out of the module that decided it rather than restated here.
    named = [e for e in breaks(rows, 2, 2)[0] if e.time == broke]
    assert [(e.kind, e.direction) for e in named] == [("BOS", 1)]
    # The supply-side candidate in this same fixture has no downward break behind
    # it and is refused, which is what makes the counter worth reading: the gate
    # admits and rejects on the same chart.
    assert stats["rejected_no_structure_break"] >= 1


def test_a_block_admitted_without_the_gate_says_not_tested_not_failed():
    """None and False are different answers and the model docstring says so. A
    detector that reported False here would be claiming it looked."""
    rows, block, _ = fixture(sweep_only=True)

    off = at(detect_order_block(rows, imb())[0], block)[0]
    assert off.displacement is not None
    assert off.displacement.broke_structure is None
    assert off.structure_break_time is None

    rows, block, _ = fixture(sweep_only=False)
    on = at(detect_order_block(rows, imb(require_structure_break=True))[0], block)[0]
    assert on.displacement.broke_structure is True


# --------------------------------------------------------------------------
# displacement as an object
# --------------------------------------------------------------------------


def test_a_gap_reports_itself_as_the_inefficiency_it_is():
    """For a fair value gap `left_gap` is not a test, it is the definition: the
    gap IS the inefficiency. And no structure is computed for gaps at all, so
    `broke_structure` must read None rather than False."""
    rows = calm(20)
    t = T0 + 20 * STEP
    rows.append(bar(t, 100.0, 100.0, 0.5, 0.5))          # first: high 100.5
    rows.append(bar(t + STEP, 101.0, 106.0, 0.2, 0.2))   # the leap
    rows.append(bar(t + 2 * STEP, 106.0, 106.0, 0.5, 1.0))  # third: low 105.0
    rows += [bar(t + (3 + i) * STEP, 106.0, 106.0, 0.5, 0.5) for i in range(10)]

    gap = at(detect_fvg(rows, imb())[0], t)[0]

    assert gap.displacement is not None
    assert gap.displacement.left_gap is True
    assert gap.displacement.broke_structure is None
    # The leg is the three bars, first to third, and its size is the gap in ATR -
    # the same number the gate used, not a second measurement of it.
    assert gap.displacement.time_from == t
    assert gap.displacement.time_to == t + 2 * STEP
    assert gap.displacement.atr == gap.departure_atr


def test_an_order_block_leg_answers_the_gap_question_with_the_gap_rule():
    """`left_gap` on a block is a real test, and it has to be the SAME test
    `detect_fvg` applies - wick to wick - or the file would hold two definitions
    of a gap that drift apart."""
    rows, block, _ = fixture(sweep_only=False)
    leg = at(detect_order_block(rows, imb())[0], block)[0].displacement

    assert leg.time_from == block + STEP        # the impulse, not the block candle
    assert leg.time_to == block + 3 * STEP      # the last bar the size test saw
    assert leg.left_gap is True

    # The same bars, put through the gap detector itself: it finds demand gaps
    # inside the impulse, which is what the flag above claims.
    inside = [
        g for g in detect_fvg(rows, imb())[0]
        if block < g.time_from < block + 3 * STEP
    ]
    assert inside and all(g.side is ZoneSide.DEMAND for g in inside)


def test_a_leg_with_no_gap_in_it_says_so():
    """The flag has to be able to read False, or it is decoration.

    Worth knowing while building this: a monotone three-bar ramp leaves a gap
    whether it looks like one or not, because the rule is wick to wick and the
    outer two bars of a ramp never meet. Only wicks long enough to overlap ACROSS
    the middle bar kill it - which is the definition doing its job, and is why
    this fixture wicks 2.0 either side.
    """
    rows = calm(20)
    t = T0 + 20 * STEP
    rows.append(bar(t, 100.0, 99.0, 0.3, 0.4))           # the block
    price = 99.0
    for i in range(1, 5):
        rows.append(bar(t + i * STEP, price, price + 3.0, 2.0, 2.0))
        price += 3.0
    rows += [bar(t + (5 + i) * STEP, price, price, 0.5, 0.5) for i in range(10)]

    leg = at(detect_order_block(rows, imb())[0], t)[0].displacement

    assert leg.left_gap is False
    assert leg.atr > 1.0  # it did displace; it just left nothing behind
