"""Kalender akhir pekan berlaku per instrumen, bukan per kalender futures.

Sampai 30 Agustus 2026 klausa `day_of_week` memakai `ny_day in (0,1,2,3,4)`
tanpa parameter simbol, jadi BTCUSD ditolak tiap Sabtu dan Minggu atas nama
hari libur forex, pada pasar yang jelas buka. Daemon auto-trade menjalankan
klausa itu sebagai klausa wajib selama tiga belas menit hari itu, dan yang
membuatnya terlihat adalah header brief yang menulis "Pasar tutup: True"
semenit setelah terminal menyerahkan bar 15m berumur 244 detik.

Fixture zona, state dan stack diimpor dari `test_ict`, bukan disalin: dua
salinan yang menua terpisah adalah dua checklist yang akan berbeda pendapat.
"""

from __future__ import annotations

from app import clock
from app.clock import market_shut, trades_when_shut
from app.ict import evaluate

from test_ict import stack, state, zone

#: Minggu 30 Agustus 2026, 08:00 NY. Di dalam jendela tutup CME, dan hari
#: ketika keempat order BTCUSD dikirim.
SUNDAY = clock.ny_wall(2026, 8, 30, 8, 0)
#: Minggu yang sama, 19:00 NY. CME sudah buka lagi sejak 18:00.
SUNDAY_REOPEN = clock.ny_wall(2026, 8, 30, 19, 0)
WEDNESDAY = clock.ny_wall(2026, 9, 2, 8, 0)


def _day_of_week(when: int, always_open: bool):
    conditions = evaluate(zone(), state(at=when), stack(),
                          always_open=always_open)
    return next(c for c in conditions if c.name == "day_of_week")


def test_sunday_masih_ditolak_untuk_instrumen_kalender_futures():
    assert _day_of_week(SUNDAY, always_open=False).met is False


def test_sunday_lolos_untuk_instrumen_yang_dagang_saat_cme_tutup():
    clause = _day_of_week(SUNDAY, always_open=True)
    assert clause.met is True
    assert "CME" in clause.detail


def test_hari_kerja_tidak_berubah_oleh_flag():
    assert _day_of_week(WEDNESDAY, always_open=False).met is True
    assert _day_of_week(WEDNESDAY, always_open=True).met is True


def test_trades_when_shut_membaca_deret_bukan_ticker():
    weekend = [SUNDAY + i * 3600 for i in range(10)]
    assert all(market_shut(t) for t in weekend)
    assert trades_when_shut(weekend) is True

    weekday = [WEDNESDAY + i * 3600 for i in range(8)]
    assert all(not market_shut(t) for t in weekday)
    assert trades_when_shut(weekday) is False


def test_bar_minggu_malam_saja_tidak_membalik_jawabannya():
    """Emas punya bar akhir pekan, dan bukan instrumen 24/7.

    CME buka lagi Minggu 18:00 NY, jadi `weekday() >= 5` menandai emas: 102
    dari 2000 bar 1h, terukur 30 Agustus 2026. Yang memisahkan adalah bar DI
    DALAM jendela tutup, dan di sana emas nol dari 2000.
    """
    assert market_shut(SUNDAY_REOPEN) is False
    series = [SUNDAY_REOPEN + i * 3600 for i in range(100)]
    assert trades_when_shut(series) is False


def test_always_open_mematikan_market_shut():
    assert market_shut(SUNDAY) is True
    assert market_shut(SUNDAY, always_open=True) is False
