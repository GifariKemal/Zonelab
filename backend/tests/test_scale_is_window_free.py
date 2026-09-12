"""Skala gerbang FVG tidak boleh bergantung berapa bar yang dimuat.

`detect_fvg` memakai `mean_true_range` sejak 7 September 2026, bukan
`wilder_atr`. Wilder adalah RMA yang disemai dari bar pertama, jadi nilainya di
satu bar absolut BERBEDA tergantung panjang jendela - dan itu masuk ke dua
tempat: rasio `departure_atr` yang jadi gerbang, dan ATR yang dipakai penelepon
untuk menaruh stop. Terukur di XAUUSD 4h lawan acuan 99.999 bar, Wilder memberi
`departure_atr` berbeda untuk 46 dari 96 zona bersama di jendela 500 bar; setelah
penukaran, yang berbeda hanya zona di dalam warmup.

WARMUP ADALAH SATU-SATUNYA PENGECUALIAN YANG DIIZINKAN, dan test ini menyatakan
batasnya secara eksplisit: sebuah rata-rata atas `atr_period` suku tidak bisa
dihitung dari bar yang lebih sedikit dari itu, jadi zona yang lahir di
`atr_period` bar pertama sebuah jendela memang harus boleh berbeda. Zona di luar
itu tidak boleh, satu pun.

Deret sintetis dan bukan data pasar, supaya gate ini jalan tanpa terminal MT5.
"""

from __future__ import annotations

import numpy as np

from app.detect.imbalance import detect_fvg
from app.models import Candle, ImbalanceParams

STEP = 3600


def _series(n: int = 600) -> list[Candle]:
    """Jalan acak berbenih dengan lompatan berkala, supaya gap-nya banyak."""
    rng = np.random.default_rng(20260907)
    price = 100.0
    rows: list[Candle] = []
    for i in range(n):
        drift = float(rng.normal(0, 0.4))
        # Lompatan tiap tujuh bar: itu yang meninggalkan celah wick-ke-wick.
        if i % 7 == 3:
            drift += float(rng.choice([-1, 1])) * 3.0
        o = price
        c = price + drift
        hi = max(o, c) + abs(float(rng.normal(0, 0.15)))
        lo = min(o, c) - abs(float(rng.normal(0, 0.15)))
        rows.append(Candle(time=1_700_000_000 + i * STEP, open=o, high=hi,
                           low=lo, close=c, volume=100.0))
        price = c
    return rows


def test_departure_atr_is_identical_outside_the_warmup() -> None:
    full = _series()
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True)

    ref, _ = detect_fvg(full, params)
    by_id = {z.id: z.departure_atr for z in ref}
    assert len(by_id) >= 30, f"deret uji cuma menghasilkan {len(by_id)} zona"

    for cut in (200, 350, 500):
        window = full[len(full) - cut:]
        start = window[0].time
        cur, _ = detect_fvg(window, params)
        pos = {c.time: i for i, c in enumerate(window)}
        shared = [z for z in cur if z.id in by_id]
        assert len(shared) >= 10, f"jendela {cut} cuma berbagi {len(shared)} zona"

        for z in shared:
            if pos[z.time_from] < params.atr_period:
                continue  # warmup, satu-satunya pengecualian
            assert z.departure_atr == by_id[z.id], (
                f"jendela {cut}: zona {z.id} di bar {pos[z.time_from]} "
                f"(di luar warmup {params.atr_period}) membaca "
                f"{z.departure_atr} lawan {by_id[z.id]} di deret penuh - "
                "skalanya bergantung jendela lagi"
            )
        assert start  # dipakai supaya niat 'jendela dipotong dari kiri' terbaca


def test_the_box_itself_never_depended_on_the_window() -> None:
    """Geometri sudah bebas jendela SEBELUM penukaran, dan harus tetap.

    Ia diturunkan dari tiga wick dan tidak menyentuh skala sama sekali. Kalau
    baris ini gugur, penukaran skala bocor ke tempat yang bukan urusannya.
    """
    full = _series()
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True)
    ref = {z.id: (z.top, z.bottom) for z in detect_fvg(full, params)[0]}
    cur = detect_fvg(full[300:], params)[0]
    checked = 0
    for z in cur:
        if z.id in ref:
            assert (z.top, z.bottom) == ref[z.id], f"kotak {z.id} bergeser"
            checked += 1
    assert checked >= 10, f"cuma {checked} kotak yang bisa dibandingkan"
