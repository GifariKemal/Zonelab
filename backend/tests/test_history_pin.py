"""Patokan ekor dikunci di sini, karena patokan yang tidak memotong tidak terlihat.

`tools/order_key.py` dijalankan dua kali di tree yang sama pada 2 September 2026
dan memberi n = 1847 lalu n = 1850: bar baru tutup di antara dua run. Verdict-nya
kebetulan bertahan, dan "kebetulan bertahan" adalah persis yang `e2e/labels.mjs`
lakukan sampai ia memberi 7/9, 8/9, 8/9, 7/9, 9/9 di tree yang sama tanpa satu
baris kode berubah.

Yang dijaga di sini tiga hal, dan yang ketiga yang paling mudah hilang: default
`AS_OF` harus tetap NOL, supaya tidak satu pun jalur live diam-diam kehilangan
bar terbarunya karena sebuah rig pengukuran lupa mengembalikan global.
"""

from __future__ import annotations

from app.models import Candle
from tools import history


def _bar(time: int) -> Candle:
    return Candle(time=time, open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)


def _series() -> list[Candle]:
    return [_bar(t) for t in (100, 200, 300, 400, 500)]


def test_default_is_the_live_tail():
    """NOL, dan ini yang paling penting di file ini.

    `AS_OF` global. Sebuah rig yang menyalakannya lalu crash meninggalkan
    proses dengan patokan menyala, dan di proses yang juga melayani API itu
    berarti chart kehilangan bar terbarunya tanpa error apa pun. Default-nya
    diuji supaya nilai yang dipatok tidak pernah masuk ke source sebagai
    default "sementara".
    """
    assert history.AS_OF == 0


def test_cut_drops_only_what_closed_after():
    """Batasnya INKLUSIF: bar yang tutup TEPAT di patokan ikut."""
    assert [c.time for c in history.cut(_series(), 300)] == [100, 200, 300]
    assert [c.time for c in history.cut(_series(), 299)] == [100, 200]


def test_cut_at_zero_returns_everything():
    assert history.cut(_series(), 0) == _series()


def test_cut_reads_the_global_when_no_argument():
    """Jalur yang benar-benar dipakai `load`, bukan hanya jalur argumen."""
    before = history.AS_OF
    try:
        history.AS_OF = 200
        assert [c.time for c in history.cut(_series())] == [100, 200]
    finally:
        history.AS_OF = before
    assert history.AS_OF == 0


def test_load_applies_the_pin(monkeypatch):
    """PATOKANNYA DI `load`, BUKAN DI PEMANGGIL.

    Lima jalur return di `_load` melayani empat venue plus sebuah cache. Sebuah
    patokan yang dipasang per pemanggil adalah patokan yang bocor di pemanggil
    yang ditambahkan besok, jadi yang diuji di sini `load` dan bukan `cut`.
    """
    monkeypatch.setattr(history, "_load", lambda *a, **k: _series())
    monkeypatch.setattr(history, "AS_OF", 300)
    assert [c.time for c in history.load("X", "1h", 5)] == [100, 200, 300]

    monkeypatch.setattr(history, "AS_OF", 0)
    assert len(history.load("X", "1h", 5)) == 5


def test_the_pinned_value_is_a_real_moment_and_is_stated():
    """Mengubahnya mengubah angka setiap studi yang memakainya.

    Jadi ia dieja sekali, dan test ini menolak nilai yang tidak masuk akal:
    patokan di masa depan tidak memotong apa pun dan patokan sebelum 2020
    memotong semuanya, dan keduanya lolos tanpa suara.
    """
    from datetime import datetime, timezone

    at = datetime.fromtimestamp(history.PINNED_AS_OF, timezone.utc)
    assert at.year >= 2020
    assert at < datetime.now(timezone.utc)
