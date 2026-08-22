"""Formula penghakim backtest, diuji ke contoh numerik yang sudah diterbitkan.

INI SATU-SATUNYA CARA MEMASTIKAN FORMULA INI BENAR. Sebuah implementasi PSR yang
salah tetap mengembalikan angka antara 0 dan 1, tetap terlihat masuk akal, dan
tetap dipakai untuk memutuskan apakah sebuah strategi layak dijalankan. Yang bisa
menangkapnya hanya perbandingan ke angka yang dihitung di luar repo ini.

Sumber angkanya: Bailey dan Lopez de Prado, "The Sharpe Ratio Efficient Frontier"
(PSR, minTRL) dan "The Deflated Sharpe Ratio" (E[max SR], DSR), plus contoh
kerja yang diverifikasi ulang terhadap scipy dan implementasi open source
sampai selisih 1e-9.
"""

from __future__ import annotations

import math

import pytest

from tools.stats import (
    deflated_sharpe,
    expected_max_sharpe,
    ljung_box,
    lo_annualised,
    min_trl,
    norm_cdf,
    norm_ppf,
    pbo,
    psr,
    sharpe_sd,
)

#: Contoh kerja: T=250 observasi, Sharpe harian 0,05, skew -0,5, kurtosis 5,0.
#: Fat tail dan skew negatif, yaitu profil yang MEMPERBURUK setiap angka di
#: bawah, dipilih justru karena itu.
T, SR, SKEW, KURT = 250, 0.05, -0.5, 5.0


# ---------------------------------------------------------------- primitif


def test_normal_cdf_matches_known_quantiles():
    assert norm_cdf(0.0) == pytest.approx(0.5, abs=1e-12)
    assert norm_cdf(1.959963985) == pytest.approx(0.975, abs=1e-9)
    assert norm_cdf(-1.959963985) == pytest.approx(0.025, abs=1e-9)


def test_inverse_normal_is_the_inverse():
    """Diuji sebagai round trip, bukan ke tabel: itu memeriksa kedua cabang
    Acklam sekaligus, termasuk yang di ekor."""
    for p in (1e-6, 0.001, 0.02, 0.024, 0.5, 0.9, 0.975, 0.99999):
        assert norm_cdf(norm_ppf(p)) == pytest.approx(p, abs=1e-9)


def test_inverse_normal_refuses_impossible_probabilities():
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            norm_ppf(bad)


# --------------------------------------------------------------- PSR, DSR


def test_sharpe_standard_error_matches_the_worked_example():
    """V[SR] = (1 - g3 SR + ((g4-1)/4) SR^2)/(T-1) = 1,0275/249."""
    assert sharpe_sd(SR, T, SKEW, KURT) == pytest.approx(
        math.sqrt(1.0275 / 249), rel=1e-12)


def test_normal_returns_reduce_to_the_familiar_form():
    """Skew 0 dan kurtosis 3 harus menyusut ke sqrt((1 + 0.5 SR^2)/(n-1)).
    Kalau konvensi kurtosis di implementasi ini excess dan bukan mentah, baris
    ini gagal, dan itulah gunanya."""
    got = sharpe_sd(0.2, 101, 0.0, 3.0)
    assert got == pytest.approx(math.sqrt((1 + 0.5 * 0.04) / 100), rel=1e-12)


def test_psr_matches_the_worked_example():
    assert psr(SR, T, SKEW, KURT, 0.0) == pytest.approx(0.781821, abs=1e-5)


def test_negative_skew_hurts_and_positive_skew_helps():
    """Arahnya, bukan hanya besarannya. Tanda yang tertukar di suku skew tetap
    memberi angka yang masuk akal dan membalik kesimpulannya."""
    worse = psr(SR, T, -1.0, KURT)
    better = psr(SR, T, +1.0, KURT)
    assert better > psr(SR, T, 0.0, KURT) > worse


def test_fat_tails_lower_the_probability():
    assert psr(SR, T, SKEW, 12.0) < psr(SR, T, SKEW, 3.0)


def test_expected_max_sharpe_matches_the_worked_example():
    """N=50 percobaan, SD lintas percobaan 0,02: 0,045526."""
    assert expected_max_sharpe(50, 0.02) == pytest.approx(0.045526, abs=1e-6)


def test_expected_max_sharpe_matches_the_papers_headline_number():
    """N=1000 dengan SD 1 memberi 3,2551, angka yang dikutip di paper aslinya
    sebagai ~3,26. Test ini yang mengikat implementasi ke sumbernya."""
    assert expected_max_sharpe(1000, 1.0) == pytest.approx(3.2551, abs=1e-3)


def test_more_trials_raise_the_bar():
    bars = [expected_max_sharpe(n, 0.02) for n in (2, 10, 50, 500)]
    assert bars == sorted(bars), "menambah percobaan harus menaikkan ambang"


def test_a_single_trial_needs_no_deflation():
    """Satu percobaan berarti tidak ada seleksi, jadi benchmark-nya adalah mean
    lintas percobaan dan DSR runtuh ke PSR."""
    assert expected_max_sharpe(1, 0.02) == 0.0
    assert deflated_sharpe(SR, T, SKEW, KURT, 1, 0.02) == pytest.approx(
        psr(SR, T, SKEW, KURT), rel=1e-12)


def test_deflated_sharpe_matches_the_worked_example():
    """PSR 0,7818 turun ke 0,5278 setelah dikoreksi 50 percobaan. Selisih itu
    adalah seluruh alasan DSR ada."""
    assert deflated_sharpe(SR, T, SKEW, KURT, 50, 0.02) == pytest.approx(
        0.527762, abs=1e-5)


def test_deflation_only_ever_lowers_the_verdict():
    plain = psr(SR, T, SKEW, KURT)
    for trials in (2, 5, 20, 100):
        assert deflated_sharpe(SR, T, SKEW, KURT, trials, 0.02) <= plain


# ------------------------------------------------------------------ minTRL


def test_min_trl_matches_the_worked_example():
    """1112,98 observasi untuk Sharpe harian 0,05 pada confidence 95%."""
    assert min_trl(SR, T, SKEW, KURT) == pytest.approx(1112.98, abs=0.01)


def test_a_sharpe_at_or_below_the_benchmark_never_qualifies():
    """Tidak ada jumlah observasi yang membuat Sharpe 0,05 signifikan di atas
    0,05. Mengembalikan angka berhingga di sini akan berbunyi seperti target
    yang bisa dicapai."""
    assert min_trl(0.05, T, 0.0, 3.0, benchmark=0.05) == float("inf")
    assert min_trl(0.01, T, 0.0, 3.0, benchmark=0.05) == float("inf")


def test_a_stronger_sharpe_needs_less_history():
    assert min_trl(0.20, T, 0.0, 3.0) < min_trl(0.05, T, 0.0, 3.0)


# ------------------------------------------------- Ljung-Box dan Lo (2002)


def test_ljung_box_is_zero_for_no_autocorrelation():
    q, df = ljung_box([0.0, 0.0, 0.0], 500)
    assert q == pytest.approx(0.0) and df == 3


def test_ljung_box_grows_with_the_correlation_and_the_sample():
    small, _ = ljung_box([0.2, 0.1], 100)
    large, _ = ljung_box([0.2, 0.1], 1000)
    assert large > small
    stronger, _ = ljung_box([0.5, 0.1], 100)
    assert stronger > small


def test_lo_correction_reduces_to_root_q_without_autocorrelation():
    assert lo_annualised(0.2, 400, []) == pytest.approx(0.2 * 20.0, rel=1e-12)
    assert lo_annualised(0.2, 400, [0.0, 0.0]) == pytest.approx(
        0.2 * 20.0, rel=1e-12)


def test_positive_autocorrelation_lowers_the_annual_sharpe():
    """Arah yang penting. sqrt(q) naif MELEBIHKAN Sharpe tahunan saat trade
    berurutan berkorelasi positif, dan itu arah kesalahan yang membesarkan angka
    yang dipakai orang untuk memutuskan."""
    naive = lo_annualised(0.2, 400, [])
    assert lo_annualised(0.2, 400, [0.3, 0.2, 0.1]) < naive
    assert lo_annualised(0.2, 400, [-0.3, -0.2]) > naive


# --------------------------------------------------------------------- PBO


def test_pbo_refuses_a_single_configuration():
    """Yang paling penting di file ini. CSCV pada satu kolom mengembalikan angka
    yang terlihat seperti PBO dan tidak mengukur apa pun, karena tidak ada
    seleksi yang terjadi. Menolak lebih baik daripada melaporkan."""
    import numpy as np

    one = np.random.default_rng(1).normal(size=(320, 1))
    with pytest.raises(ValueError, match="minimal 2 konfigurasi"):
        pbo(one)


def test_pbo_is_low_when_one_configuration_is_genuinely_better_everywhere():
    """Kolom 0 punya drift lebih tinggi di SETIAP blok, bukan di satu blok.

    Itu definisi edge yang nyata: pemenang in-sample menang lagi out-of-sample,
    jadi logit-nya positif dan PBO mendekati nol.
    """
    import numpy as np

    rng = np.random.default_rng(3)
    m = rng.normal(loc=0.0, scale=1.0, size=(320, 8))
    m[:, 0] += 0.5
    got = pbo(m, splits=8)
    assert got["configs"] == 8 and got["combinations"] == 70
    assert got["pbo"] < 0.1, got
    assert got["logit_median"] > 0


def test_pbo_is_high_when_each_configuration_only_wins_in_its_own_block():
    """Tanda tangan overfitting, dibangun sengaja.

    Kolom i hanya positif di blok i dan negatif di sisanya. Pemenang in-sample
    selalu kolom yang blok emasnya kebetulan masuk ke train, dan justru karena
    itu ia buruk di test. PBO harus tinggi.

    Ini juga koreksi terhadap versi pertama test ini, yang memakai kolom noise
    iid dan mengharapkan PBO sekitar 0,5. Yang keluar 0,14, dan yang salah adalah
    ekspektasinya: mean SAMPEL sebuah kolom noise dibagi antara train dan test,
    jadi kolom yang kebetulan bermean tinggi tetap tinggi di kedua paruh. PBO
    rendah di situ benar. Yang mengukur overfitting adalah struktur di bawah ini.
    """
    import numpy as np

    rng = np.random.default_rng(5)
    splits, per, n = 8, 40, 8
    m = rng.normal(scale=0.2, size=(splits * per, n)) - 0.05
    for i in range(n):
        m[i * per:(i + 1) * per, i] += 1.0
    got = pbo(m, splits=splits)
    assert got["pbo"] > 0.7, got
    assert got["logit_median"] < 0


def test_pbo_refuses_an_odd_split_count_and_a_short_sample():
    import numpy as np

    m = np.random.default_rng(7).normal(size=(320, 4))
    with pytest.raises(ValueError, match="genap"):
        pbo(m, splits=7)
    with pytest.raises(ValueError, match="terlalu sedikit"):
        pbo(m[:8], splits=8)
