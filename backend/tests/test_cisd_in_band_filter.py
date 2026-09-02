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


def test_the_orderable_list_holds_exactly_the_measured_three():
    """PENJAGA DAFTAR, dan ia sudah sekali berubah dalam satu hari.

    Versi pertama test ini menuntut `"fvg" not in ORDERABLE_LAYERS`, dan itu
    BENAR saat ditulis: di rig berbiaya 1 jam dan 4 jam gerbang departure
    terbalik untuk fvg, selisih -0,1005 R dengan Welch t = -4,48 dan cuma 3 dari
    17 sel positif. Yang berubah bukan pendiriannya, tapi pertanyaannya. Yang
    tidak ditanyakan saat itu: sisi BAWAH gerbang sendiri berapa, dan
    `fvg_inverted` menjawab +0,2188 R di n=3.799 dengan t lawan nol +8,53 dan
    walk-forward 8 dari 8, bertahan positif di kontrol resolusi 1 menit.

    Jadi yang dikunci di sini bukan "fvg boleh" atau "fvg tidak boleh", tapi
    bahwa daftarnya berisi TEPAT tiga layer yang punya angka, dan layer keempat
    tidak bisa masuk tanpa test ini berubah warna. `ifvg` dan `breaker` belum
    pernah lewat rig berbiaya sama sekali.
    """
    from tools.execute import ORDERABLE_LAYERS
    assert set(ORDERABLE_LAYERS) == {"supply_demand", "order_block", "fvg"}
    assert "ifvg" not in ORDERABLE_LAYERS
    assert "breaker" not in ORDERABLE_LAYERS


def test_an_unmeasured_layer_is_refused_loudly():
    """Layer di luar daftar harus gagal, bukan diam-diam jatuh ke default.

    Diam di sini akan memasang order pada populasi yang tidak pernah diukur
    sambil melaporkan nama layer yang diminta.
    """
    from tools.execute import candidates
    with pytest.raises(ValueError, match="ORDERABLE_LAYERS"):
        candidates("mt5:XAUUSD", "30m", 10, layer="ifvg")


def test_fvg_is_orderable_now_but_only_where_it_was_measured():
    """PEMBALIKAN, dan ia punya angkanya sendiri.

    `fvg` keluar dari `ORDERABLE_LAYERS` pagi 2 September 2026 karena gerbang
    departure TERBALIK untuknya di rig berbiaya 1 jam dan 4 jam: selisih
    -0,1005 R dengan Welch t = -4,48. Yang tidak ditanyakan saat itu: sisi
    bawahnya sendiri berapa. `docs/detectors_costed.json` mencatat +0,0938 R di
    n=16.200, satu-satunya angka positif di file itu, tidak pernah diuji lawan
    nol.

    `tools/fvg_inverted.py` menanyakannya di 30 menit: sisi BAWAH +0,2188 R di
    n=3.799, t lawan nol +8,53 lawan kritis 2,24, walk-forward 8 DARI 8. Kontrol
    resolusi 1 menit (rasio 30 lawan 6) menyusutkannya ke +0,1354 dan +0,1235
    dan TANDANYA BERTAHAN, sementara supply_demand di kontrol yang sama jadi
    +0,0549 dan +0,0359.
    """
    from tools.execute import GATE_DIRECTION, MEASURED_INTERVALS, ORDERABLE_LAYERS
    assert "fvg" in ORDERABLE_LAYERS
    # Dan gerbangnya harus menghadap ke arah yang diukur, bukan ke default.
    assert GATE_DIRECTION["fvg"] == "ceiling"
    assert GATE_DIRECTION["supply_demand"] == "floor"
    assert GATE_DIRECTION["order_block"] == "floor"
    # 30 menit saja, karena itu satu-satunya timeframe yang diukur.
    assert MEASURED_INTERVALS["fvg"] == ("30m",)
    # Dan layer ber-`floor` tidak boleh punya batas interval yang salah pasang.
    assert "supply_demand" not in MEASURED_INTERVALS
    assert "order_block" not in MEASURED_INTERVALS


def test_an_unmeasured_interval_is_refused_and_the_error_says_why():
    """1 jam harus DITOLAK untuk fvg, bukan dijalankan dengan angka 30 menit.

    Sisi bawah fvg di 1 jam +0,0938 R belum pernah diuji lawan nol dan tidak
    punya walk-forward, dan di 15 menit tidak ada angka sama sekali karena
    riwayat 1 menit cuma 103 hari XAUUSD dan 69 hari BTCUSD. Menjalankannya di
    sana akan memasang order pada populasi yang belum diukur sambil mengutip
    angka 30 menit.
    """
    from tools.execute import candidates
    with pytest.raises(ValueError, match="cuma terukur di"):
        candidates("mt5:XAUUSD", "1h", 10, layer="fvg")
    with pytest.raises(ValueError, match="cuma terukur di"):
        candidates("mt5:XAUUSD", "15m", 10, layer="fvg")


def test_the_ceiling_keeps_the_measured_side_and_drops_the_other():
    """Arah gerbangnya harus benar-benar membalik, bukan cuma dinamai begitu.

    Diukur: cuma 129 dari 3.928 zona fvg lolos gerbang 2,0 ATR, dan 129 itu
    yang TIDAK pernah diuji lawan nol. `floor` untuk fvg akan memasang order
    pada 129 itu sambil membuang 3.799 yang sudah diukur, yaitu kebalikan dari
    apa yang angkanya katakan.
    """
    import inspect

    from tools.execute import GATE_DIRECTION, candidates
    src = inspect.getsource(candidates)
    body = src[src.index("departure = zone.departure_atr"):]
    head = body[:body.index("plan = build") if "plan = build" in body else 400]
    # `floor` membuang yang di bawah; `ceiling` membuang yang di atas. Kedua
    # perbandingan harus ada, dan ke arah yang berbeda.
    assert "departure < DEPARTURE_GATE_ATR" in head, head
    assert "departure >= DEPARTURE_GATE_ATR" in head, head
    assert GATE_DIRECTION.get("fvg") == "ceiling"
