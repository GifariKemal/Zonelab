"""Filter CISD-di-dalam-band, dan batas di mana ia berhenti berlaku.

Pemisahan terkuat yang repo ini punya: order block yang memuat level CISD baru
di dalam band-nya menghasilkan -0,1119 R, yang tanpanya +0,0244 R, delta
-0,1363 dengan Welch t = -7,07 lawan kritis 2,24 di n=8.170, dan kedelapan fold
walk-forward bertanda sama (`docs/csid_ob_intrabar.json`).

Yang dikunci di sini bukan cuma bahwa filternya bekerja. Ketiga syaratnya harus
mengikat masing-masing, karena definisi yang bergeser sedikit menyaring
populasi lain dan angka di atas tidak berlaku untuknya. Dan yang terakhir
mengunci batasnya: di bar KEPUTUSAN kondisinya hampir selalu salah, jadi flag
itu tidak boleh dibaca sebagai "angka -0,1363 sudah terpasang".
"""

from __future__ import annotations

import pytest

from app.cisd import RECENT_CISD_BARS, CISD, recent_in_band

STEP = 1800
NOW = 1_000_000


def ev(level: float, time: int) -> CISD:
    """CISD yang cuma dua field-nya dibaca `recent_in_band`."""
    return CISD(index=0, time=time, direction=1, level=level,
                run_start=0, run_end=1, run_length=2)


def test_a_recent_level_inside_the_band_is_found():
    assert recent_in_band(100.0, 110.0, [ev(105.0, NOW - 10 * STEP)], NOW, STEP)


def test_the_band_binds():
    """Level di luar band tidak dihitung, meskipun baru."""
    assert not recent_in_band(100.0, 110.0, [ev(120.0, NOW)], NOW, STEP)
    # Dan tepinya termasuk, sesuai `bottom <= level <= top` di studinya.
    assert recent_in_band(100.0, 110.0, [ev(110.0, NOW)], NOW, STEP)
    assert recent_in_band(100.0, 110.0, [ev(100.0, NOW)], NOW, STEP)


def test_the_recency_binds_and_it_is_the_whole_tightening():
    """Level basi di dalam band tidak dihitung.

    Separuh kebaruan ini yang membuat kondisinya tidak degenerate: tanpanya 95
    persen order block memuat SEBUAH level CISD, dan diukur pada XAUUSD 30m 18
    dari 20 kandidat kena.
    """
    just_inside = NOW - RECENT_CISD_BARS * STEP
    assert recent_in_band(100.0, 110.0, [ev(105.0, just_inside)], NOW, STEP)
    assert not recent_in_band(100.0, 110.0, [ev(105.0, just_inside - 1)],
                              NOW, STEP)


def test_the_future_binds_and_that_is_the_anti_lookahead_half():
    """Level yang belum lahir di `now` tidak boleh terbaca.

    `0 <= now - e.time` yang menjaganya. Tanpa sisi ini filternya membaca masa
    depan, dan setiap angka yang diukur di atasnya jadi bocor.
    """
    assert not recent_in_band(100.0, 110.0, [ev(105.0, NOW + STEP)], NOW, STEP)


def test_step_scales_the_window_not_the_bar_count():
    """Jendelanya 50 BAR, jadi ia melebar bersama timeframe-nya.

    Kalau ia dipatok ke detik, 50 bar di 30 menit dan 50 bar di 1 jam akan
    menyaring dua populasi berbeda dengan satu nama.
    """
    stale = NOW - 60 * STEP
    assert not recent_in_band(100.0, 110.0, [ev(105.0, stale)], NOW, STEP)
    assert recent_in_band(100.0, 110.0, [ev(105.0, stale)], NOW, STEP * 2)


def test_fvg_is_not_orderable_and_the_number_says_why():
    """PENJAGA DAFTAR. `fvg` punya target sekarang, dan tetap tidak boleh.

    Di rig berbiaya `docs/detectors_costed.json` gerbang departure fvg TERBALIK:
    -0,1005 R dengan Welch t = -4,48 dan hanya 3 dari 17 sel positif, artinya
    zona fvg yang LOLOS gerbang lebih buruk daripada yang tidak. Setelah
    `mark_profit_zones` dipasang ke funnel ICT, satu-satunya yang menahan fvg
    keluar dari jalur order adalah daftar ini.
    """
    from tools.execute import ORDERABLE_LAYERS
    assert "fvg" not in ORDERABLE_LAYERS
    assert "order_block" in ORDERABLE_LAYERS
    assert "supply_demand" in ORDERABLE_LAYERS


def test_an_unmeasured_layer_is_refused_loudly():
    """Layer di luar daftar harus gagal, bukan diam-diam jatuh ke default.

    Diam di sini akan memasang order pada populasi yang tidak pernah diukur
    sambil melaporkan nama layer yang diminta.
    """
    from tools.execute import candidates
    with pytest.raises(ValueError, match="ORDERABLE_LAYERS"):
        candidates("mt5:XAUUSD", "30m", 10, layer="ifvg")
