"""The threshold has to get harder as more groups are tested, and it has to be
computed rather than typed.

A conditioning study with fifty groups and an uncorrected alpha finds something
every time. The correction is the only thing standing between this tool and a
table of coincidences, so the arithmetic behind it is checked here.
"""

from __future__ import annotations

from math import erfc, sqrt

from tools.conditioned import ALPHA, MIN_GROUP, _critical_t, _dfr_band


def test_one_group_is_the_ordinary_two_sided_threshold():
    """No correction with nothing to correct for: alpha 0.05 two-sided is 1.96."""
    assert abs(_critical_t(1) - 1.96) < 0.01


def test_more_groups_means_a_higher_bar():
    values = [_critical_t(n) for n in (1, 10, 52, 200)]
    assert values == sorted(values), values
    assert values[0] < values[-1]


def test_the_fifty_two_group_case_this_study_actually_ran():
    """52 groups, alpha 0.05/52 = 0.00096, and the printed critical value was
    3.30. Pinned so a change to the solver cannot quietly move the bar under a
    published result."""
    assert round(_critical_t(52), 2) == 3.30


def test_the_solver_agrees_with_the_tail_it_inverts():
    """Round trip: the critical value fed back through the normal tail must
    return the corrected alpha. Catches a bisection that converged on the wrong
    side or the wrong tail."""
    for groups in (1, 7, 52):
        t = _critical_t(groups)
        assert abs(erfc(t / sqrt(2)) - ALPHA / groups) < 1e-6


def test_zero_groups_cannot_pass_anything():
    """A run that judged nothing must not report a finding, so the bar is
    infinite rather than zero."""
    assert _critical_t(0) == float("inf")


def test_the_minimum_group_is_big_enough_for_a_normal_approximation():
    """The critical values above are normal, not Student. That is only honest
    while every judged group has at least this many observations."""
    assert MIN_GROUP >= 30


def test_the_dfr_bands_name_outside_the_range_as_outside():
    """Inside, above and below are three different facts about a trade. Folding
    the two outside cases into one another is how a saturated reading gets
    mistaken for a location."""
    assert _dfr_band(0.5) == "inside_range"
    assert _dfr_band(0.0) == "inside_range"
    assert _dfr_band(1.0) == "inside_range"
    assert _dfr_band(1.01) == "above_range"
    assert _dfr_band(-0.01) == "below_range"
    assert _dfr_band(None) is None
