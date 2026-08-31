"""`STAGE_PAIRS` hanya boleh menyebut derajat yang benar-benar ada.

Sampai 30 Agustus 2026 ia memetakan `1h` ke `("day", "90m")` dan `15m` ke
`("90m", "micro")`. `app/quarters.ALL_DEGREES` tidak pernah memuat `"90m"`, jadi
`quarters()` melempar ValueError, `except ValueError` di `tools/execute.py`
menelannya, dan `two_stage_confirmed` TIDAK PERNAH BISA True pada 1h maupun 15m.
Nol baris log, dan sebuah klausa yang mustahil True terbaca sama persis dengan
klausa yang kebetulan False.

Derajat yang dimaksud adalah `session`: `app/quarters.py` baris 23 mendefinisikan
satu kuarter sesi sebagai 90 menit.
"""

from __future__ import annotations

import pytest

from app.quarters import ALL_DEGREES, quarters
from tools.execute import STAGE_PAIRS


def test_setiap_derajat_di_stage_pairs_ada_di_all_degrees():
    tak_dikenal = {
        (interval, degree)
        for interval, pair in STAGE_PAIRS.items()
        for degree in pair
        if degree not in ALL_DEGREES
    }
    assert not tak_dikenal


@pytest.mark.parametrize("interval", sorted(STAGE_PAIRS))
def test_quarters_benar_benar_menerima_kedua_derajatnya(interval):
    """Bukan sekadar ada di tuple: `quarters()` yang jadi hakimnya.

    Yang diuji NAMA derajatnya diterima, bukan jumlah kuarter yang keluar.
    Versi pertama test ini menuntut hasil tidak kosong pada jendela 100.000
    detik, dan `week` serta `month` mengembalikan nol di jendela sesempit itu
    dengan benar. Itu akan memaku ukuran jendela, bukan cacatnya.
    """
    for degree in STAGE_PAIRS[interval]:
        quarters(degree, 1_787_900_000, 1_788_000_000)


def test_derajat_yang_tidak_ada_memang_melempar():
    """Gerbang di atas kosong kalau `quarters` diam saja untuk nama asing."""
    with pytest.raises(ValueError, match="90m"):
        quarters("90m", 1_787_900_000, 1_788_000_000)


def test_1h_dan_15m_memakai_session_bukan_90m():
    """Dua pemetaan yang cacatnya terukur, dipaku pada nilai yang benar."""
    assert STAGE_PAIRS["1h"] == ("day", "session")
    assert STAGE_PAIRS["15m"] == ("session", "micro")
