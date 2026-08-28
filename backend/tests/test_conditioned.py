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


def test_the_ote_band_is_direction_aware_like_the_clause_it_reports_on():
    """Demand mau discount, supply mau premium. Satu pita, dua arah.

    `app/fibonacci.py` dulu membawa `in_ote` yang mengembalikan pita discount
    untuk KEDUA sisi, dan file itu dihapus justru karena dua fungsi di dalamnya
    tidak sepakat separuh mana OTE berada. Kolom ini membaca angka dari
    `app/ict.py`, satu-satunya definisi yang tersisa, dan test ini yang menjaga
    ia tidak kembali jadi salinan kedua yang menyimpang.
    """
    from tools.conditioned import _ote_band

    assert _ote_band(0.30, "demand") == "ote"
    assert _ote_band(0.30, "supply") == "discount"
    assert _ote_band(0.70, "supply") == "ote"
    assert _ote_band(0.70, "demand") == "premium"
    # TIDAK ADA RANGE BUKAN EQUILIBRIUM. Menggabungkannya akan membuat zona yang
    # tidak terbaca tampak seperti zona yang terbaca tepat di tengah.
    assert _ote_band(None, "demand") == "none"
    assert _ote_band(0.5, "demand") == "equilibrium"


def test_the_london_bias_never_reads_a_bar_after_the_touch():
    """Anti-lookahead, dan ini satu-satunya hal yang berdiri antara kolom Judas
    dan sebuah hasil yang dibuat dari masa depan.

    Bar sesudah `touch` diberi harga ekstrem. Kalau bias membacanya, template
    akan berubah. Template harus tetap sama.
    """
    from datetime import datetime

    from app.clock import NY
    from app.models import Candle
    from tools.conditioned import _london_bias

    step = 3600
    origin = int(datetime(2026, 1, 6, 1, 0, tzinfo=NY).timestamp())
    rows = [Candle(time=origin + i * step, open=100.0 + i, high=101.0 + i,
                   low=99.0 + i, close=100.5 + i, volume=1.0) for i in range(8)]
    touch = 5
    before = _london_bias(rows, touch)

    rows[6] = rows[6].model_copy(update={"high": 9_000.0, "close": 8_999.0})
    rows[7] = rows[7].model_copy(update={"low": 1.0, "close": 2.0})
    assert _london_bias(rows, touch) == before, (
        "bias London berubah setelah bar SESUDAH sentuhan diubah: kolom Judas "
        "membaca dari masa depan"
    )


def test_the_orphan_columns_are_pre_registered_and_separate_from_the_others():
    """Tiga daftar, tidak digabung, dan itu yang membuat urutannya terbaca.

    `COLUMNS` (21 Agustus), `ICT_COLUMNS` (21 Agustus, praregistrasi kedua),
    `ORPHAN_COLUMNS` (28 Agustus, ketiga). Menggabungkannya akan menyembunyikan
    pertanyaan mana yang diajukan sebelum jawabannya ada, yang adalah
    satu-satunya hal yang membuat ketiganya layak dipercaya.

    `ladder` sengaja TIDAK di sana: ia tabel lookup tanpa input pasar, dan itu
    dinyatakan di `docs/PRAREGISTRASI-YATIM.md` Bagian 2 sebelum angka apa pun.
    """
    from tools.conditioned import COLUMNS, ICT_COLUMNS, ORPHAN_COLUMNS

    assert ORPHAN_COLUMNS == (
        "in_judas_window", "judas_template", "psp_before_touch",
        "true_opens_in_zone", "ote_band",
    )
    assert not set(ORPHAN_COLUMNS) & set(COLUMNS)
    assert not set(ORPHAN_COLUMNS) & set(ICT_COLUMNS)
    assert not any("ladder" in c for c in ORPHAN_COLUMNS)
