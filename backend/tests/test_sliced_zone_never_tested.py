"""Zona yang disayat satu bar tetap tercatat disentuh.

`replay_lifecycle` memeriksa `close` menembus distal SEBELUM memeriksa
sentuhan, jadi sebuah bar yang masuk zona dan menutup di seberangnya
menghasilkan `touches=0` dan `first_test_time=None`. Setiap rig hasil di repo
memakai `first_test_time` sebagai pemicu entry, sementara `broker.py` hanya
bisa LIMIT dan limit itu duduk di proximal - jadi jalur hidup MENGAMBIL trade
yang jalur ukur tidak pernah hitung.

Diukur di XAUUSD 30m, fvg, gate 0,25, target 2R, resolusi 5m, 2025-04-08 ke
depan: urutan repo memberi n=1045, PF 1,943, exp_r +0,4785. Urutan limit hidup
memberi n=1657, PF 1,115, exp_r +0,0736. Strategy Tester TradingView pada
aturan yang sama memberi n=1664 - populasi lengan kedua, bukan lengan pertama.

DIPERBAIKI 6 September 2026: sentuhan sekarang dicatat sebelum pecah. Test ini
menjaga arah perbaikannya dari dua sisi - zona tersayat WAJIB mengaku disentuh,
dan ia WAJIB tetap tergambar broken di bar yang sama, karena satu-satunya cara
perbaikan ini merusak gambar adalah kalau ia menunda `break_index`.
"""

from __future__ import annotations

from app.detect.imbalance import detect_fvg
from app.models import Candle, ImbalanceParams


def _bar(t: int, o: float, h: float, low: float, c: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=low, close=c, volume=100.0)


def _series() -> list[Candle]:
    step = 1800
    rows = [_bar(1000 + i * step, 100.0, 101.0, 99.0, 100.0) for i in range(20)]
    rows += [
        _bar(1000 + 20 * step, 100.0, 101.0, 99.0, 100.5),    # first, high 101
        _bar(1000 + 21 * step, 101.0, 106.0, 101.0, 105.5),   # mid, terbang
        _bar(1000 + 22 * step, 105.5, 106.5, 103.0, 106.0),   # third, low 103
        # Penyayat: masuk zona sampai 100,0 lalu tutup 100,5 di bawah distal 101.
        _bar(1000 + 23 * step, 106.0, 106.0, 100.0, 100.5),
    ]
    rows += [_bar(1000 + (24 + i) * step, 100.5, 101.0, 100.0, 100.5) for i in range(5)]
    return rows


def test_sliced_zone_reports_no_touch() -> None:
    rows = _series()
    zones, _ = detect_fvg(rows, ImbalanceParams(max_zones_per_side=0, show_broken=True))
    zone = next(z for z in zones if z.time_from == 1000 + 20 * 1800)
    assert (zone.top, zone.bottom, zone.proximal) == (103.0, 101.0, 103.0)

    slicer = rows[23]
    # Bar itu masuk zona, dan menembus proximal: sebuah limit di sana terisi.
    assert slicer.low <= zone.top and slicer.high >= zone.bottom
    assert slicer.low <= zone.proximal

    # Sisi ukur: bar itu memang sentuhan pertama, dan sekarang diakui.
    assert zone.touches == 1
    assert zone.first_test_time == slicer.time

    # Sisi gambar: bar yang sama tetap mematahkannya, dan kotaknya tetap
    # berhenti di situ. Kalau salah satu dari dua baris ini gugur, perbaikan
    # ukur sudah menggeser apa yang tergambar.
    assert zone.state.value == "broken"
    assert zone.time_to == slicer.time
