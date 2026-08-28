"""Penyelesaian di bar halus, diuji sebagai properti dan bukan sebagai angka.

BUTUH TERMINAL, jadi ia skip di mesin tanpa MT5. Yang diuji bukan besaran
hasilnya: itu properti pasar dan akan berubah tiap hari. Yang diuji adalah tiga
hal yang harus benar apa pun pasarnya, dan yang kalau salah akan membuat seluruh
kesimpulan di `docs/QA-QUANT.md` bagian 6 tidak berlaku:

  1. Kebenaran harus DI ANTARA dua arm bar besar. Mengizinkan target di bar entry
     adalah batas optimis, menundanya adalah batas pesimis, dan resolusi halus
     tidak boleh keluar dari keduanya. Kalau ia keluar, walk halusnya memakai
     jendela waktu atau harga yang berbeda dan bukan sekadar resolusi berbeda.
  2. Trade yang di arm bar besar selesai BELAKANGAN tidak ambigu, jadi kedua
     resolusi harus sepakat di sana. Itu uji yang paling menentukan: ia
     memisahkan "resolusinya lebih halus" dari "implementasinya lain".
  3. Entry harus terisi sebelum diselesaikan, dan indeksnya tidak boleh negatif.
"""

from __future__ import annotations

import numpy as np
import pytest

from tools.costed import trades
from tools.quant import BROKER, clean, metrics

SYMBOL, INTERVAL, FINE = "XAUUSD", "1h", "5m"


@pytest.fixture(scope="module")
def arms():
    """Tiga arm pada HIMPUNAN TRADE YANG SAMA, atau perbandingannya tidak sah."""
    from app.providers import mt5 as mt5mod

    provider = mt5mod.MT5Provider()
    if not provider.available():
        pytest.skip("tidak ada terminal MetaTrader 5 di mesin ini")

    from tools.intrabar import resolved

    fine = [r for r in resolved(SYMBOL, INTERVAL, FINE) if r["cleared"]]
    if len(fine) < 50:
        pytest.skip(f"hanya {len(fine)} trade punya riwayat {FINE}")
    ids = {r["zone_id"] for r in fine}
    candles, _, _ = clean(SYMBOL, INTERVAL)
    coarse = {}
    for label, same in (("allow", True), ("defer", False)):
        coarse[label] = [
            x for x in trades("supply_demand", candles, INTERVAL, True,
                              symbol=SYMBOL, broker=BROKER,
                              flat_by_rollover=True, same_bar_target=same)
            if not x["skipped"] and x["cleared"] and x["zone_id"] in ids
        ]
    return {"fine": fine, **coarse}


def test_the_three_arms_cover_the_same_trades(arms):
    """Prasyarat setiap perbandingan di bawah."""
    n = {k: len(v) for k, v in arms.items()}
    assert n["fine"] == n["allow"] == n["defer"], n


def test_the_fine_truth_sits_between_the_two_coarse_bounds(arms):
    """Properti utama. Keluar dari selang ini berarti walk-nya berbeda, bukan
    resolusinya."""
    allow = metrics(arms["allow"])["exp_r"]
    defer = metrics(arms["defer"])["exp_r"]
    fine = metrics(arms["fine"])["exp_r"]
    assert defer <= fine <= allow, (defer, fine, allow)


def test_the_optimistic_arm_is_never_below_the_pessimistic_one(arms):
    """Mengizinkan pembayaran di bar entry hanya bisa menambah kemenangan.
    Kalau urutannya terbalik, cabang `i == touch` dipasang di sisi yang salah."""
    assert metrics(arms["allow"])["win_rate"] >= metrics(arms["defer"])["win_rate"]


def test_unambiguous_trades_agree_between_resolutions(arms):
    """Trade yang butuh lebih dari satu bar besar tidak punya ambiguitas urutan.

    Diukur 22 Agustus 2026: 121 trade seperti itu memberi +0,176 R di bar 1 jam
    dan +0,162 R di bar 5 menit, dengan 90,9% tanda hasil yang sama. Ambangnya
    dipasang longgar di 0,75 karena exit mark-to-market memang bisa berbeda di
    resolusi berbeda; yang tidak boleh adalah keduanya bercerita lain.
    """
    fine = {r["zone_id"]: r["r"] for r in arms["fine"]}
    later = [x for x in arms["allow"] if x["bars_held"] > 0]
    if len(later) < 30:
        pytest.skip(f"hanya {len(later)} trade yang selesai belakangan")
    a = np.array([x["r"] for x in later])
    b = np.array([fine[x["zone_id"]] for x in later])
    same_sign = float((np.sign(a) == np.sign(b)).mean())
    assert same_sign >= 0.75, f"hanya {same_sign:.1%} sepakat tandanya"
    assert abs(a.mean() - b.mean()) < 0.10, (a.mean(), b.mean())


def test_every_fine_trade_filled_before_it_resolved(arms):
    for r in arms["fine"]:
        assert r["fine_bars_to_fill"] >= 0
        assert r["fine_bars_held"] >= 0
        assert np.isfinite(r["r"])


def test_the_fine_arm_reports_a_cost_ratio_for_every_trade(arms):
    """`cost_r` yang nol di setiap baris berarti biayanya tidak pernah dibebankan,
    dan itu terlihat sama seperti pasar yang murah."""
    ratios = [r["cost_r"] for r in arms["fine"]]
    assert all(x > 0 for x in ratios), "ada trade tanpa biaya"
    assert max(ratios) < 1.0, max(ratios)


def test_the_touch_bar_may_stop_but_may_not_pay():
    """Aturan yang sama seperti `costed.py`, sekarang dipaku untuk `calibrate`.

    Tanpa terminal, karena ini aritmetika: satu zona demand, satu bar sentuh yang
    high-nya sudah melewati target. OHLC tidak bisa mengatakan high-nya tercetak
    sebelum atau sesudah low yang mengisi entry, jadi bacaan yang tidak mengarang
    adalah menunggu bar berikutnya.

    `calibrate.resolve` memakai konvensi lama sampai 26 Agustus 2026 sementara
    `costed.py` sudah dibalik pada 22 Agustus, dan tujuh tool mewarisi yang lama.
    """
    from types import SimpleNamespace

    from app.models import ZoneSide
    from tools.calibrate import resolve

    # proximal 100, distal 99, target 100 + 2 * 1 ATR = 102.
    zone = SimpleNamespace(side=ZoneSide.DEMAND, proximal=100.0, distal=99.0)
    # Bar sentuh (indeks 1) sendiri sudah menyentuh 102. Bar sesudahnya datar.
    high = np.array([100.0, 102.5, 100.2, 100.2])
    low = np.array([100.0, 99.5, 100.0, 100.0])
    close = np.array([100.0, 100.1, 100.1, 100.1])
    atr = np.array([1.0, 1.0, 1.0, 1.0])

    optimistic = resolve(zone, high, low, close, atr, 1, 2.0, 3, same_bar_target=True)
    honest = resolve(zone, high, low, close, atr, 1, 2.0, 3, same_bar_target=False)

    assert optimistic is True, "bar sentuh membayar: batas optimis"
    assert honest is not True, "bar sentuh TIDAK boleh membayar secara bawaan"

    # Dan yang tidak boleh ikut berubah: bar sentuh tetap boleh MENGHENTIKAN.
    stopped_close = np.array([100.0, 98.5, 100.1, 100.1])
    assert resolve(
        zone, high, low, stopped_close, atr, 1, 2.0, 3, same_bar_target=False
    ) is False, "bar sentuh yang menutup melewati distal tetap gagal, bukan None"
