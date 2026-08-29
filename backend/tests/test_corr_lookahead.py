"""Anti-lookahead untuk `partner_corr_band`, satu-satunya hal yang membatalkan
seluruh run praregistrasi 29 Agustus 2026.

`docs/PRAREGISTRASI-KORELASI.md` Bagian 5 menuliskannya sebelum satu angka pun
ada: kalau test ini gagal, run-nya DIBUANG, bukan dilaporkan lebih lemah. Angka
dari kolom yang melihat masa depan bukan angka yang lebih lemah, ia angka yang
salah.

Test ini dibuktikan TIDAK KOSONG di dalam file ini sendiri. Bar yang disuntikkan
sesudah bar keputusan bukan bar netral: satu test di bawah menuntut bar itu
BENAR-BENAR mengubah pita begitu ia masuk jendela. Tanpa itu, "pita tidak
berubah" bisa berarti "jendelanya benar" atau "suntikannya tidak berpengaruh",
dan dua-duanya lulus.
"""

from __future__ import annotations

import numpy as np

from app.models import Candle
from tools.conditioned import _corr_band, _partner

STEP = 3600
BASE = "mt5:XAUUSD"
PARTNER = "mt5:XAGUSD"


def _candles(closes: np.ndarray) -> list[Candle]:
    return [
        Candle(time=i * STEP, open=float(c), high=float(c), low=float(c),
               close=float(c), volume=1.0)
        for i, c in enumerate(closes)
    ]


def _pair(bars: int = 260) -> tuple[dict[str, list[Candle]], list[int]]:
    """Dua deret yang bergerak bersama, cukup untuk mendarat di pita teratas.

    Seed tetap, karena pita yang berpindah antar-run tidak bisa dibedakan dari
    bug jendela.
    """
    rng = np.random.default_rng(618)
    shared = rng.normal(0.0, 0.01, bars)
    own = rng.normal(0.0, 0.002, bars)
    base = 2000.0 * np.exp(np.cumsum(shared))
    partner = 25.0 * np.exp(np.cumsum(shared * 0.9 + own))
    series = {BASE: _candles(base), PARTNER: _candles(partner)}
    return series, [c.time for c in series[BASE]]


def _inject(series: dict[str, list[Candle]]) -> list[int]:
    """Satu bar SESUDAH bar keputusan yang cukup ekstrem untuk memindah pita.

    Base melompat, partner tidak. Satu titik pencilan sebesar ini mendominasi
    kovarians, jadi kalau jendela membacanya, koefisiennya runtuh dan pita ikut
    pindah. Itu yang membuat test di bawah punya gigi.
    """
    last = len(series[BASE])
    series[BASE].append(Candle(time=last * STEP, open=2000.0, high=2000.0,
                               low=2000.0, close=200_000.0, volume=1.0))
    series[PARTNER].append(
        Candle(time=last * STEP, open=25.0, high=25.0, low=25.0,
               close=float(series[PARTNER][-1].close), volume=1.0)
    )
    return [c.time for c in series[BASE]]


def test_bars_after_the_decision_bar_never_move_the_band():
    """Bar masa depan disuntikkan, pita harus tetap.

    Ini syarat yang praregistrasi Bagian 3 poin 7 tuntut dengan kata-katanya
    sendiri: korelasi dihitung dari bar yang BERAKHIR di bar keputusan.
    """
    series, times = _pair()
    at = times[-1]
    before = _corr_band(series, BASE, times, at)

    grown = _inject(series)
    after = _corr_band(series, BASE, grown, at)

    assert after == before, (
        f"pita berubah dari {before} ke {after} setelah bar SESUDAH bar "
        f"keputusan disuntikkan: kolom korelasi membaca dari masa depan"
    )


def test_the_injected_bar_really_would_move_the_band():
    """Bukti test di atas tidak kosong.

    Bar yang sama, dibaca dengan bar keputusan yang maju satu langkah, HARUS
    mengubah pita. Kalau tidak, test anti-lookahead di atas lulus karena
    suntikannya tumpul dan bukan karena jendelanya benar.
    """
    series, times = _pair()
    at = times[-1]
    before = _corr_band(series, BASE, times, at)

    grown = _inject(series)
    after = _corr_band(series, BASE, grown, grown[-1])

    assert after != before, (
        "bar suntikan tidak memindah pita bahkan saat ikut dibaca, jadi test "
        "anti-lookahead di atas tidak membuktikan apa pun"
    )


def test_a_window_under_thirty_pairs_is_unknown_and_not_zero():
    """Praregistrasi Bagian 3 poin 5: di bawah 30 pasang return nilainya
    `unknown`, dan `unknown` pita tersendiri, bukan nol dan bukan dibuang."""
    series, times = _pair()
    short = {s: rows[:20] for s, rows in series.items()}
    assert _corr_band(short, BASE, times[:20], times[19]) == "unknown"


def test_the_partner_comes_from_the_repo_map_and_not_from_this_run():
    """Partner ditetapkan sebelum run, dan untuk `mt5:XAUUSD` ia `mt5:XAGUSD`.

    Prefix provider ikut terbawa: `load_aligned` menolak mencampur feed, dan
    partner tanpa prefix akan diambil dari provider default, yaitu instrumen
    yang berbeda dengan harga yang berbeda.
    """
    assert _partner("mt5:XAUUSD") == "mt5:XAGUSD"
    assert _partner("mt5:XAGUSD") == "mt5:XAUUSD"
    assert _partner("XAUUSD") == "XAGUSD"
