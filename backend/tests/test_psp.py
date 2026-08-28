"""PSP, dipaku ke definisi sumbernya dan bukan ke selera.

KENAPA FILE INI ADA. `in_same_candle` dulu membandingkan `psp.level` milik base
symbol terhadap low, high dan close instrumen LAIN, dan `app/correlation.py` di
repo yang sama mendokumentasikan kenapa itu tidak sah: satu id adalah instrumen
berbeda per venue, dan selisihnya tidak selalu basis. Sumbernya
(`Referensi grup dan Bg Nas/Discord/Buku=Pegangan.txt`) memberi contoh yang
menyelesaikannya:

    XAU - Bullish Candle
    XAG - Bearish Candle
    Platinum - Bullish Candle

Ketiga tandanya bahkan tidak sama, dan justru itu crack-nya. Jadi yang
dibandingkan TANDA candle di bar yang sama, bukan harga.
"""

from __future__ import annotations

from app.models import Candle
from app.psp import PSPEvent, detect, in_same_candle, polarity


def bull(t: int, base: float = 100.0) -> Candle:
    return Candle(time=t, open=base, high=base + 2, low=base - 1, close=base + 1, volume=1.0)


def bear(t: int, base: float = 100.0) -> Candle:
    return Candle(time=t, open=base + 1, high=base + 2, low=base - 1, close=base, volume=1.0)


def doji(t: int, base: float = 100.0) -> Candle:
    return Candle(time=t, open=base, high=base + 1, low=base - 1, close=base, volume=1.0)


def event(at: int = 3, direction: str = "buy") -> PSPEvent:
    return PSPEvent(at=at, level=99.5, direction=direction, ssmt_at=0, bars_after_ssmt=at)


# ------------------------------------------------------------------ polarity


def test_polarity_gives_a_doji_no_side():
    assert polarity(bull(0)) == 1
    assert polarity(bear(0)) == -1
    assert polarity(doji(0)) == 0


# ------------------------------------------------- crack, bukan perbandingan harga


def test_a_partner_with_the_opposite_sign_is_the_crack():
    """Contoh sumbernya sendiri: base bullish, satu partner bearish."""
    base = [bull(i) for i in range(5)]
    xag = [bull(i) for i in range(5)]
    plat = [bull(i) for i in range(5)]
    xag[3] = bear(3)  # satu partner berbalik tanda di bar PSP

    assert in_same_candle(event(3), base, [xag, plat])


def test_a_triad_that_agrees_is_not_a_crack():
    base = [bull(i) for i in range(5)]
    partners = [[bull(i) for i in range(5)], [bull(i) for i in range(5)]]
    assert not in_same_candle(event(3), base, partners)


def test_the_scale_of_the_partner_cannot_change_the_answer():
    """Ini properti yang membuat perbaikannya benar, dan yang versi lama gagal.

    COPPER tutup di 13968,59 di satu feed dan 6,44 di feed lain. Predikat yang
    membandingkan harga akan menjawab berbeda untuk dua deret yang bentuknya
    identik; predikat yang membandingkan tanda tidak boleh.
    """
    base = [bull(i) for i in range(5)]
    small = [bull(i, base=6.4) for i in range(5)]
    huge = [bull(i, base=13968.0) for i in range(5)]
    small[3] = bear(3, base=6.4)
    huge[3] = bear(3, base=13968.0)

    assert in_same_candle(event(3), base, [small])
    assert in_same_candle(event(3), base, [huge])
    # Dan skala yang berbeda di antara dua partner tidak mengubahnya.
    assert in_same_candle(event(3), base, [small, huge])


def test_a_doji_base_has_nothing_to_disagree_with():
    base = [bull(i) for i in range(5)]
    base[3] = doji(3)
    partners = [[bear(i) for i in range(5)]]
    assert not in_same_candle(event(3), base, partners)


def test_a_partner_shorter_than_the_bar_is_false_rather_than_a_guess():
    """Bar yang tidak ada bukan ketidaksepakatan.

    Index bar cuma berarti di grid yang sudah di-align, dan itu tugas caller.
    Partner yang lebih pendek berarti pertanyaannya tidak bisa dijawab.
    """
    base = [bull(i) for i in range(5)]
    assert not in_same_candle(event(4), base, [[bear(i) for i in range(3)]])
    assert not in_same_candle(event(99), base, [[bear(i) for i in range(5)]])


def test_no_partner_at_all_is_not_a_crack():
    base = [bull(i) for i in range(5)]
    assert not in_same_candle(event(3), base, [])


# ------------------------------------------------------------------- detect


def test_a_psp_must_come_after_the_ssmt_and_inside_the_window():
    """Dua syarat sumbernya: purge liquidity, dan beberapa candle SESUDAH SSMT."""
    level = 99.0
    rows = [bull(i) for i in range(12)]
    # Bar 5 menyapu di bawah level lalu close kembali di atasnya.
    rows[5] = Candle(time=5, open=100.0, high=101.0, low=98.0, close=100.0, volume=1.0)

    found = detect(rows, ssmt_candle_idx=2, levels=[level], lookback=10)
    assert found is not None
    assert found.at == 5
    assert found.direction == "buy"
    assert found.bars_after_ssmt == 3

    # Bar yang sama, tapi SSMT-nya sesudahnya: tidak ada PSP.
    assert detect(rows, ssmt_candle_idx=6, levels=[level], lookback=10) is None
    # Dan di luar jendela juga tidak ada.
    assert detect(rows, ssmt_candle_idx=2, levels=[level], lookback=2) is None


def test_a_sweep_that_does_not_close_back_is_not_a_psp():
    """Purge tanpa rejection bukan PSP, ia cuma break."""
    rows = [bull(i) for i in range(8)]
    rows[4] = Candle(time=4, open=100.0, high=100.5, low=98.0, close=98.2, volume=1.0)
    assert detect(rows, ssmt_candle_idx=1, levels=[99.0], lookback=6) is None
