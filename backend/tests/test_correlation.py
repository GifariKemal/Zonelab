"""How correlated the SSMT partner is, on series where the answer is arithmetic.

The whole point of `app/correlation.py` is to replace a guess with a number, so
its own tests cannot be built on real bars: on real bars the correct answer is
whatever the code computes, which tests nothing. Every fixture here has a
coefficient that is known before the function runs.

The failure modes that matter are all quiet ones. A price correlation instead of
a returns correlation reads +0.99 between any two rising series. A nan reaching
the wire is a browser parse error rather than a missing field. A partner paired
off a different grid compares bar 100 of one instrument with bar 100 of another
that started a week later, and every price involved is real.
"""

from __future__ import annotations

import math

from app.correlation import MIN_PAIRS, RECENT_FRACTION, correlations
from app.models import Candle

STEP = 3600
START = 1_700_000_000


def series(closes: list[float], step: int = STEP, start: int = START) -> list[Candle]:
    return [
        Candle(
            time=start + i * step,
            open=c,
            high=c * 1.001,
            low=c * 0.999,
            close=c,
            volume=1.0,
        )
        for i, c in enumerate(closes)
    ]


def walk(n: int, seed: float, factor: float = 1.0) -> list[float]:
    """A deterministic zigzag whose log returns are exactly proportional between
    two calls with the same `n`. `factor` scales the return, and Pearson is scale
    invariant, so two walks with the same shape must correlate at +1 regardless.
    """
    out = [seed]
    for i in range(1, n):
        step = (1 if i % 3 else -1) * (0.002 + 0.001 * (i % 5)) * factor
        out.append(out[-1] * (1.0 + step))
    return out


def test_the_same_shape_at_a_different_scale_correlates_at_plus_one():
    """Scale invariance, and it is not academic here.

    This broker quotes copper at 13968.59 while the network source quotes the same
    metal at 6.44 - a factor of two thousand, because the units differ and it is
    not a basis. A returns correlation is blind to that by construction, and this
    pins it.
    """
    base = walk(400, 2400.0)
    found = correlations(
        {"GOLD": series(base), "TWIN": series([c * 2170.0 for c in base])}, "GOLD"
    )
    assert len(found) == 1
    assert found[0].full is not None
    assert found[0].full == 1.0 or math.isclose(found[0].full, 1.0, abs_tol=1e-9)


def test_a_mirrored_series_correlates_at_minus_one_and_is_not_judged():
    """An inverse partner is a valid pairing read the other way round, so the sign
    is REPORTED. Nothing here returns a verdict, and there is no field for one."""
    base = walk(400, 2400.0)
    # Each bar's return negated, which is what an inversely correlated instrument
    # looks like at the return level.
    mirrored = [100.0]
    for i in range(1, len(base)):
        mirrored.append(mirrored[-1] * (base[i - 1] / base[i]))

    found = correlations({"GOLD": series(base), "MIRROR": series(mirrored)}, "GOLD")
    assert found[0].full is not None
    assert math.isclose(found[0].full, -1.0, abs_tol=1e-9)
    assert not hasattr(found[0], "verdict")
    assert not hasattr(found[0], "valid")


def test_prices_that_both_rise_do_not_score_as_correlated():
    """THE DEFECT A PRICE CORRELATION WOULD HAVE.

    Two series that both trend upward correlate near +1 on PRICES for no reason
    other than both trending. Here one rises in a zigzag and the other rises in a
    perfectly smooth line, so their bar-to-bar returns are close to unrelated
    while their prices march together. A price correlation would report a strong
    pairing; a returns correlation must not.
    """
    zig = walk(400, 2400.0)
    smooth = [100.0 * (1.0015**i) for i in range(400)]
    found = correlations({"GOLD": series(zig), "SMOOTH": series(smooth)}, "GOLD")
    assert found[0].full is not None
    assert abs(found[0].full) < 0.35, (
        "a smooth ramp must not read as correlated with a zigzag just because both "
        f"rise, got {found[0].full}"
    )


def test_a_flat_partner_is_absent_rather_than_nan():
    """`np.corrcoef` answers nan for a constant series, and a nan serialised onto
    the wire is not valid JSON - it reaches the browser as a parse error, which is
    a worse failure than a missing field. A flat series is a real case: an index
    outside its session prints identical closes."""
    found = correlations(
        {"GOLD": series(walk(400, 2400.0)), "FLAT": series([100.0] * 400)}, "GOLD"
    )
    assert found[0].full is None
    assert found[0].recent is None
    assert found[0].pairs == 399


def test_too_few_paired_returns_is_absent_rather_than_a_confident_number():
    """Pearson on a handful of points is noise wearing the shape of a
    measurement, so below `MIN_PAIRS` there is no coefficient at all."""
    short = MIN_PAIRS  # MIN_PAIRS closes make MIN_PAIRS - 1 returns
    found = correlations(
        {"GOLD": series(walk(short, 2400.0)), "SILVER": series(walk(short, 30.0))},
        "GOLD",
    )
    assert found[0].full is None, f"{short - 1} returns must not produce an r"


def test_a_partner_off_a_different_grid_is_reported_rather_than_truncated():
    """Truncating to the shorter series would pair bar 100 of one instrument with
    bar 100 of another that started a week later. Every price would be real and
    the pairing would be wrong, which is the exact failure `aligned.py` exists to
    prevent - so a length mismatch here means the caller did not come through it,
    and the answer is no coefficient rather than a plausible one."""
    found = correlations(
        {"GOLD": series(walk(400, 2400.0)), "SHORT": series(walk(120, 30.0))}, "GOLD"
    )
    assert found[0].symbol == "SHORT"
    assert found[0].full is None
    assert found[0].pairs == 0


def test_a_decoupling_in_the_recent_window_shows_up_as_a_sign_change():
    """WHY TWO WINDOWS EXIST. Correlation is a property of a pair over a period,
    not of the pair - so a series that tracked gold for three quarters and then
    inverted must not average out to "still correlated"."""
    base = walk(800, 2400.0)
    # Follows the base for the first three quarters, then mirrors it.
    turn = int(800 * (1 - RECENT_FRACTION))
    partner = [50.0]
    for i in range(1, 800):
        ratio = base[i] / base[i - 1]
        partner.append(partner[-1] * (ratio if i < turn else 1.0 / ratio))

    found = correlations({"GOLD": series(base), "TURNED": series(partner)}, "GOLD")
    got = found[0]
    assert got.full is not None and got.recent is not None
    assert got.recent < 0 < got.full, f"full={got.full} recent={got.recent}"
    assert got.sign_changed, "the disagreement between the two windows IS the finding"


def test_partners_are_ordered_by_strength_and_the_unmeasurable_sort_last():
    """The order a reader picks a partner in. An absent coefficient is an answer,
    so it stays in the list rather than being dropped - just at the bottom."""
    base = walk(400, 2400.0)
    weak = walk(400, 30.0, factor=1.0)
    weak = [c * (1.0 + 0.02 * ((i % 7) - 3)) for i, c in enumerate(weak)]

    found = correlations(
        {
            "GOLD": series(base),
            "WEAK": series(weak),
            "TWIN": series([c * 3.0 for c in base]),
            "FLAT": series([1.0] * 400),
        },
        "GOLD",
    )
    order = [c.symbol for c in found]
    assert order[0] == "TWIN", f"strongest first, got {order}"
    assert order[-1] == "FLAT", f"unmeasurable last, got {order}"


def test_the_base_symbol_is_not_correlated_with_itself():
    """A perfect +1 row for the chart's own symbol would be noise in the list and
    would sort to the top of it, pushing the partner a reader asked about down."""
    base = series(walk(400, 2400.0))
    found = correlations({"GOLD": base, "SILVER": series(walk(400, 30.0))}, "GOLD")
    assert [c.symbol for c in found] == ["SILVER"]


def test_a_missing_base_symbol_gives_nothing_rather_than_raising():
    """This runs inside `_draw_ssmt`, where every failure is reported and survived:
    one overlay of sixteen must not take down a drawing whose own bars arrived."""
    assert correlations({"SILVER": series(walk(400, 30.0))}, "GOLD") == []
    assert correlations({}, "GOLD") == []
