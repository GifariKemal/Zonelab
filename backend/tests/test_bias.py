"""The four-degree alignment checklist, on series whose answer is arithmetic.

Every fixture here is hand-built so the expected bias at each degree is a fact
about the bars rather than a fact about a random walk. `app.providers.synthetic`
would work too, but its bars anchor to `now`, and none of these assertions want
a clock in them.

Two of these tests are the ones that matter. One asserts that a degree with too
few bars is UNKNOWN and never counts as agreement, because "I could not look"
passing as "yes" is how a checklist ticks a box it should not. The other asserts
the anti-lookahead property directly: the reading at a bar must not change when
later bars arrive.

Nothing here tests whether alignment predicts anything. It does not - twelve
pre-registered directional hypotheses have failed in this repo. See the module
docstring of app/bias.py.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_bias.py -q
"""

from __future__ import annotations

from app.bias import DEGREES, alignment, min_bars
from app.detect.structure import bias_series
from app.models import Candle

STEP = 900
T0 = 1_700_000_000 // 86_400 * 86_400


def bar(t: int, o: float, c: float) -> Candle:
    return Candle(
        time=t, open=o, close=c, high=max(o, c) + 0.01, low=min(o, c) - 0.01,
        volume=1000.0,
    )


def wave(points: list[float], per: int = 4) -> list[Candle]:
    """A zigzag through `points`, `per` bars per leg. Pivot bars are exact."""
    rows: list[Candle] = []
    t = T0
    for a, b in zip(points, points[1:]):
        for k in range(per):
            rows.append(bar(t, a + (b - a) * k / per, a + (b - a) * (k + 1) / per))
            t += STEP
    return rows


def rising() -> list[Candle]:
    """Higher low, then a close beyond the swing high: bullish, by BOS."""
    return wave([100, 110, 105, 120])


def falling() -> list[Candle]:
    """The mirror: bearish, by BOS."""
    return wave([120, 110, 115, 100])


def turned() -> list[Candle]:
    """Bullish first, then a close beyond the swing low: bearish, by CHoCH."""
    return wave([100, 110, 105, 120, 95])


def quiet() -> list[Candle]:
    """Long enough to look at, with nothing that ever breaks a level: bias 0."""
    return [bar(T0 + i * STEP, 100.0, 100.0) for i in range(12)]


def series(**overrides: list[Candle]) -> dict[str, list[Candle]]:
    """All four degrees rising unless a test says otherwise."""
    return {tf: rising() for tf in DEGREES} | overrides


def reading(report, tf: str):
    return next(d for d in report.degrees if d.timeframe == tf)


# --------------------------------------------------------------------------
# The checklist itself
# --------------------------------------------------------------------------


def test_four_bullish_degrees_report_aligned_and_name_the_direction():
    report = alignment(series())

    assert report.aligned
    assert report.direction == 1
    assert report.disagreeing == ()
    assert [d.bias for d in report.degrees] == [1, 1, 1, 1]


def test_one_disagreeing_degree_breaks_alignment_and_is_named():
    """"Semuanya harus sejajar" - so a report that only said False would leave
    him opening four charts to find out which one it was."""
    report = alignment(series(**{"1h": falling()}))

    assert not report.aligned
    assert report.direction is None
    assert report.disagreeing == ("1h",)
    assert reading(report, "1h").bias == -1


def test_the_degrees_are_reported_daily_first_in_the_order_he_checks_them():
    assert tuple(d.timeframe for d in alignment(series()).degrees) == DEGREES
    assert DEGREES[0] == "1d"


def test_a_daily_without_a_usable_bias_is_named_as_the_break_on_its_own():
    """His rule starts at the Daily. With no bias there the other three have
    nothing to agree WITH, so naming them too would be three false accusations."""
    report = alignment(series(**{"1d": quiet()}))

    assert not report.aligned
    assert report.disagreeing == ("1d",)


# --------------------------------------------------------------------------
# UNKNOWN, and why it is not zero
# --------------------------------------------------------------------------


def test_a_degree_with_too_few_bars_is_unknown_with_a_reason_not_a_bias():
    short = rising()[: min_bars(2, 2) - 1]

    report = alignment(series(**{"4h": short}))
    degree = reading(report, "4h")

    assert degree.bias is None
    assert degree.bars == len(short)
    assert degree.needs == min_bars(2, 2) == 6
    assert degree.reason and "4h" in degree.reason and "6 needed" in degree.reason


def test_an_unknown_degree_never_counts_as_agreement():
    report = alignment(series(**{"15m": rising()[:3]}))

    assert not report.aligned
    assert report.disagreeing == ("15m",)


def test_a_missing_degree_reads_unknown_rather_than_quietly_dropping_out():
    """A dict with three keys must not produce a three-of-three tick."""
    incomplete = {tf: rising() for tf in DEGREES if tf != "4h"}

    report = alignment(incomplete)

    assert reading(report, "4h").bias is None
    assert reading(report, "4h").bars == 0
    assert not report.aligned
    assert report.disagreeing == ("4h",)


def test_no_break_yet_reads_zero_and_is_distinct_from_unknown():
    """Two different facts. "Enough bars, nothing broke" is a flat market;
    "not enough bars" is a fetch that was too small. Both fail the checklist."""
    report = alignment(series(**{"1h": quiet()}))
    flat = reading(report, "1h")

    assert flat.bias == 0
    assert flat.bias is not None
    assert flat.reason is None
    assert flat.bars >= flat.needs
    assert not report.aligned
    assert report.disagreeing == ("1h",)


# --------------------------------------------------------------------------
# Reversal against continuation, in structure's own vocabulary
# --------------------------------------------------------------------------


def test_a_choch_on_a_degree_reads_as_the_reversal_confirmation_he_asks_for():
    report = alignment(series(**{"1d": turned()}))
    daily = reading(report, "1d")

    assert daily.last_break == "CHoCH"
    assert daily.reversal_confirmed is True
    assert daily.bias == -1


def test_a_bos_reads_as_continuation_rather_than_reversal():
    daily = reading(alignment(series()), "1d")

    assert daily.last_break == "BOS"
    assert daily.reversal_confirmed is False


def test_a_degree_with_no_break_confirms_nothing_either_way():
    """False would claim continuation of a trend that was never established."""
    flat = reading(alignment(series(**{"1d": quiet()})), "1d")

    assert flat.last_break is None
    assert flat.reversal_confirmed is None


# --------------------------------------------------------------------------
# The one rule that makes or breaks it
# --------------------------------------------------------------------------


def test_the_reading_at_a_bar_is_unchanged_by_bars_that_had_not_printed_yet():
    """Truncate the series and the answer at that bar must be identical. If it
    is not, the reading is made of hindsight - see detect/structure.py."""
    full = turned()
    reference = bias_series(full, 2, 2)

    for cut in range(min_bars(2, 2), len(full) + 1):
        degree = reading(alignment({"1d": full[:cut]}), "1d")
        assert degree.bias == int(reference[cut - 1]), f"bias moved at bar {cut}"


def test_the_choch_in_that_series_is_only_visible_once_its_bar_has_printed():
    """The truncation test above is worth nothing if the fixture never turns."""
    full = turned()
    early = reading(alignment({"1d": full[:12]}), "1d")
    late = reading(alignment({"1d": full}), "1d")

    assert (early.bias, early.last_break) == (1, "BOS")
    assert (late.bias, late.last_break) == (-1, "CHoCH")


def test_a_wider_swing_width_raises_the_floor_and_takes_the_bias_with_it():
    """`left` and `right` are the caller's, and the floor is derived from them
    rather than fixed: the same 12 bars that answer at width 2 are UNKNOWN at
    width 5, where the shipped internal width sits."""
    assert min_bars(5, 5) == 12

    degree = reading(alignment({"1d": rising()}, left=5, right=5), "1d")

    assert len(rising()) == 12
    assert degree.bias == 0  # long enough to look, no swing confirmed in time
    assert reading(alignment({"1d": rising()[:11]}, left=5, right=5), "1d").bias is None
