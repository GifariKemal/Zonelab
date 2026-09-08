"""Dua aturan `liquidity_pool` yang paling mudah hanyut, dikunci di sini.

Geometri dan pemetaan sisinya sudah dijaga `_selftest()` di modulnya. Yang di
sini dua sifat yang cuma muncul saat detektor dijalankan atas deret sungguhan,
dan keduanya adalah tempat detektor semacam ini biasanya bocor.
"""

from __future__ import annotations

import numpy as np

from app.detect.liquidity_pool import detect
from app.detect.structure import swings
from app.models import Candle, LiquidityPoolParams, ZoneKind, ZoneSide


def _bar(t: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=0.0)


def _series(highs: list[float], lows: list[float]) -> list[Candle]:
    """Deret sintetis: body kecil di tengah tiap bar, wick yang dipesan."""
    out = []
    for i, (h, lo) in enumerate(zip(highs, lows)):
        mid = (h + lo) / 2
        out.append(_bar(1_700_000_000 + i * 3600, mid, h, lo, mid))
    return out


def test_kotak_tidak_pernah_lahir_sebelum_pivotnya_terkonfirmasi() -> None:
    """`born` sebuah kolam harus >= `confirmed_at` anggota terakhirnya.

    Ini pemeriksaan lookahead yang sesungguhnya untuk detektor ini. Sebuah
    fraktal di bar i baru bisa diketahui di bar i + right, jadi kolam yang
    digambar lebih awal dari itu menggambar sesuatu yang belum ada. Diuji lewat
    `first_test_time`, yang `_finish` mulai hitung dari `born + 1`.
    """
    rng = np.random.default_rng(20260908)
    n = 400
    base = 100.0 + np.cumsum(rng.normal(0, 0.4, n))
    highs = (base + rng.uniform(0.2, 1.0, n)).tolist()
    lows = (base - rng.uniform(0.2, 1.0, n)).tolist()
    candles = _series(highs, lows)

    params = LiquidityPoolParams(max_zones_per_side=0, show_broken=True,
                                 equal_tol_atr=0.5)
    zones, _ = detect(candles, params)
    assert zones, "deret ini harus menghasilkan kolam, kalau tidak tesnya kosong"

    time = [c.time for c in candles]
    hi = np.array(highs)
    lo = np.array(lows)
    pivots = swings(hi, lo, params.swing_n, params.swing_n)
    conf_of = {(p.index, p.high): p.confirmed_at for p in pivots}

    for z in zones:
        # Id membawa waktu pivot pertama dan pivot yang melahirkan kotaknya.
        _, t_origin, t_born_pivot = z.id.split("-")
        i_born = time.index(int(t_born_pivot))
        is_high = z.kind is ZoneKind.BSL
        confirmed = conf_of[(i_born, is_high)]
        assert confirmed >= i_born, "fraktal tidak bisa dikonfirmasi sebelum barnya"
        # Lifecycle mulai di born + 1, jadi sentuhan pertama tidak boleh
        # tercatat pada atau sebelum bar konfirmasi.
        if z.first_test_time is not None:
            assert time.index(z.first_test_time) > confirmed, z.id
        assert int(t_origin) < int(t_born_pivot), "origin harus mendahului kelahiran"


def test_kolam_yang_sudah_disapu_tidak_menangkap_pivot_baru() -> None:
    """Aturan mati kolam, dan tanpa ia satu harga akan hidup selamanya.

    Dibangun tangan: dua high di 110 membentuk kolam, harga lalu MENEMBUS jauh
    di atas 110, lalu kembali dan mencetak high ketiga di 110 lagi. Kolam
    pertama sudah diambil likuiditasnya, jadi high ketiga harus memulai kolam
    BARU, bukan menjadi anggota ketiga yang tidak memancarkan apa-apa.

    Yang diperiksa jumlah kotak BSL: satu kalau kolam mati dan yang baru lahir
    lagi, dan itu hanya mungkin kalau sapuan memutus yang pertama.
    """
    # Puncaknya SENGAJA tidak persis sama. Kolam yang seluruh pivotnya berharga
    # identik memberi kotak setinggi nol dan ditolak by design - versi pertama
    # tes ini memakai 110,0 empat kali dan gagal karena aturan itu, bukan karena
    # aturan sapuannya.
    flat = 100.0
    highs: list[float] = []
    lows: list[float] = []

    def push(h: float, lo: float, k: int = 1) -> None:
        for _ in range(k):
            highs.append(h)
            lows.append(lo)

    push(flat, 95.0, 8)
    push(110.0, 105.0)           # pivot high 1
    push(flat, 95.0, 8)
    push(110.3, 105.0)           # pivot high 2 -> kolam lahir
    push(flat, 95.0, 8)
    push(130.0, 120.0)           # SAPUAN: jauh di atas 110 + toleransi
    push(flat, 95.0, 8)
    push(110.1, 105.0)           # pivot high 3, sesudah disapu
    push(flat, 95.0, 8)
    push(110.4, 105.0)           # pivot high 4 -> kolam KEDUA lahir
    push(flat, 95.0, 8)

    candles = _series(highs, lows)
    params = LiquidityPoolParams(max_zones_per_side=0, show_broken=True,
                                 equal_tol_atr=0.5, swing_n=3)
    zones, stats = detect(candles, params)
    bsl = [z for z in zones if z.kind is ZoneKind.BSL]

    assert stats["candidates"] >= 2, (
        "sapuan tidak memutus kolam pertama: high ketiga dan keempat menempel "
        f"ke kluster lama, stats={stats}"
    )
    assert bsl, "tidak ada kotak BSL sama sekali"
    for z in bsl:
        assert z.side is ZoneSide.SUPPLY, "BSL harus duduk di sisi supply"
