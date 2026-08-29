"""Baseline bebas-sinyal, diuji sebagai properti dan bukan sebagai angka.

Semua di sini OFFLINE. Besaran hasilnya properti pasar dan akan berubah tiap
hari; yang diuji adalah empat hal yang harus benar apa pun pasarnya, dan yang
kalau salah akan membuat setiap angka di bagian baseline `docs/CALIBRATION.md`
tidak berlaku:

  1. `spaced` benar-benar tidak menyisakan jendela maju yang beririsan. Ini
     gerbang yang paling menentukan: H10 mencatat t menggelembung sampai tujuh
     kali lipat semata karena tumpang tindih, jadi penipisan yang bocor akan
     mengulangi kesalahan yang sama tanpa gejala apa pun.
  2. `window_end` berhenti di rollover, bukan di horizon, kalau rollover datang
     lebih dulu. Aturan yang sama dengan `costed.trades` di bawah `flat`.
  3. Geometri bracket sintetis PERSIS pasangan yang ditarik: risk sama dengan
     tinggi ditambah buffer, target sama dengan reward multiple kali tinggi.
     Kalau ini meleset, kedua arm memakai geometri berbeda dan seluruh
     perbandingannya tidak sah.
  4. Kedua patch dikembalikan, bahkan lewat exception. Patch yang bocor akan
     membuat pengukuran berikutnya di proses yang sama membaca zona baseline
     dan melaporkannya sebagai arm nyata.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.models import (
    Anatomy,
    Candle,
    Zone,
    ZoneKind,
    ZoneSide,
    ZoneState,
)
from app.plan import DEFAULT_STOP_BUFFER_ATR, build
from tools import intrabar
from tools.baseline import _inject, _spy, draw, spaced, window_end
from tools.costed import HORIZON, ROLLOVER_HOUR_UTC

HOUR = 3600
#: Tepat 00:00 UTC, jadi rollover 21:00 jatuh di bar ke-21 dan aritmetikanya
#: bisa dibaca tanpa mengulang rumusnya di dalam tes.
T0 = 1755993600


def hourly(count: int) -> np.ndarray:
    return np.arange(T0, T0 + count * HOUR, HOUR, dtype=np.int64)


def template() -> Zone:
    return Zone(
        id="tpl", kind=ZoneKind.DBR, side=ZoneSide.DEMAND, state=ZoneState.FRESH,
        timeframe="1h", top=100.0, bottom=98.0, proximal=100.0, distal=98.0,
        time_from=T0, time_to=T0 + 10 * HOUR, formation_score=0.5,
        departure_atr=3.0, profit_zone_rr=2.0,
        anatomy=Anatomy(leg_in_from=0, leg_in_to=1, base_run_from=2,
                        base_from=2, base_to=4, leg_out_from=5, leg_out_to=8),
    )


def test_window_end_stops_at_the_rollover_not_at_the_horizon():
    """Horizon 80 bar lebih panjang dari satu hari, jadi di deret 1 jam aturan
    flat SELALU yang memotong. Kalau tes ini membaca 80, `spaced` sedang
    memesan jendela tiga kali lebih lebar dari yang dipakai walk-nya."""
    time = hourly(200)
    assert window_end(0, time) == ROLLOVER_HOUR_UTC
    assert window_end(5, time) == ROLLOVER_HOUR_UTC
    # Dibuka SESUDAH rollover hari ini, jadi yang memotong rollover besok.
    assert window_end(22, time) == 24 + ROLLOVER_HOUR_UTC


def test_window_end_falls_back_to_the_horizon_when_no_rollover_fits():
    """Deret yang terlalu pendek untuk mencapai rollover berikutnya. Yang diuji
    di sini adalah cabang yang TIDAK boleh mengembalikan indeks di luar deret."""
    time = np.arange(T0, T0 + 5 * HOUR, HOUR, dtype=np.int64)
    assert window_end(0, time) == len(time) - 1
    assert window_end(0, time) < HORIZON


def test_spaced_leaves_no_pair_of_overlapping_forward_windows():
    """Gerbang utamanya. Setiap trade yang tersisa harus dibuka SESUDAH jendela
    trade sebelumnya habis, karena itulah satu-satunya arti "tidak bertumpang
    tindih" yang dipakai H10."""
    time = hourly(400)
    rows = [{"at": i, "r": 0.0} for i in range(0, 300, 3)]
    kept = spaced(rows, time)

    assert kept, "penipisan tidak boleh mengosongkan sampel"
    assert len(kept) < len(rows), "kalau tidak ada yang dibuang, tidak ada penipisan"
    for before, after in zip(kept, kept[1:]):
        assert after["at"] > window_end(before["at"], time)


def test_spaced_keeps_trades_that_were_already_far_apart():
    """Aturannya harus MEMBUANG tumpang tindih, bukan menjarangkan apa pun.
    Tanpa cabang ini, `spaced` yang mengembalikan satu baris saja akan lolos
    tes di atas."""
    time = hourly(400)
    rows = [{"at": 0, "r": 0.0}, {"at": 100, "r": 0.0}, {"at": 250, "r": 0.0}]
    assert [r["at"] for r in spaced(rows, time)] == [0, 100, 250]


def test_spaced_reads_in_time_order_whatever_order_it_is_given():
    """Baris baseline datang dalam urutan draw, bukan urutan waktu. Penipisan
    serakah yang membaca urutan draw akan menyimpan himpunan yang berbeda."""
    time = hourly(400)
    rows = [{"at": i, "r": 0.0} for i in (250, 0, 100, 5, 101)]
    assert [r["at"] for r in spaced(rows, time)] == [0, 100, 250]


def _series(count: int, price: float = 100.0) -> list[Candle]:
    return [Candle(time=int(t), open=price, high=price + 1.0, low=price - 1.0,
                   close=price, volume=1.0) for t in hourly(count)]


@pytest.mark.parametrize("side", [ZoneSide.DEMAND, ZoneSide.SUPPLY])
def test_the_synthetic_bracket_is_the_geometry_that_was_drawn(side):
    """Risk sama dengan tinggi ditambah buffer, reward sama dengan rr kali
    tinggi, di kedua sisi. Ini yang membuat perbandingannya "ekspektasi per
    trade pada risk yang cocok" dan bukan dua taruhan berbeda."""
    # True range konstan 2,0 di deret ini (high-low, tanpa gap), jadi Wilder ATR
    # juga 2,0 begitu ia hangat. Tingginya karena itu bisa diperiksa sebagai
    # ANGKA MUTLAK: menurunkan ATR kembali dari tinggi zona akan membuat tes
    # buta terhadap penskalaan yang salah, dan itu justru cacat yang paling
    # mungkin terjadi di sini.
    candles = _series(HORIZON + 160)
    geometry = [{"height_atr": 1.5, "rr": 2.5, "side": side, "departure": 3.0}]
    eligible = np.arange(60, len(candles) - HORIZON)
    zones = draw(candles, geometry, eligible, np.random.default_rng(1),
                 "uniform", template())
    assert len(zones) == 1
    zone = zones[0]

    atr = 2.0
    height = zone.top - zone.bottom
    assert height == pytest.approx(geometry[0]["height_atr"] * atr)

    plan = build(zone, atr=atr, now=zone.first_test_time, interval_seconds=HOUR)
    assert zone.side is side
    assert plan.risk_per_unit == pytest.approx(
        height + DEFAULT_STOP_BUFFER_ATR * atr)
    assert abs(plan.target - plan.entry) == pytest.approx(
        geometry[0]["rr"] * height)


def test_the_synthetic_entry_is_the_previous_close_not_this_bar_s():
    """Level yang knowable pada AWAL bar entry. Memakai close bar entry sendiri
    akan membolehkan fill di bar halus yang terjadi sebelum harga itu ada, yaitu
    lookahead yang persis sama bentuknya dengan KOREKSI 2026-08-17."""
    candles = _series(HORIZON + 60)
    for i, candle in enumerate(candles):
        candles[i] = candle.model_copy(update={"close": 100.0 + i})
    geometry = [{"height_atr": 1.0, "rr": 2.0, "side": ZoneSide.DEMAND,
                 "departure": 3.0}]
    zones = draw(candles, geometry, np.arange(1, len(candles) - HORIZON),
                 np.random.default_rng(7), "uniform", template())

    zone = zones[0]
    entry_bar = [c for c in candles if c.time == zone.first_test_time][0]
    previous = candles[candles.index(entry_bar) - 1]
    assert zone.proximal == previous.close
    assert zone.proximal != entry_bar.close


def test_inject_restores_the_resolver_even_when_the_body_raises():
    detectors, road = intrabar.DETECTORS, intrabar.profit_zone_at
    with pytest.raises(RuntimeError):
        with _inject([]):
            assert intrabar.profit_zone_at is not road
            raise RuntimeError("boom")
    assert intrabar.DETECTORS is detectors
    assert intrabar.profit_zone_at is road


def test_spy_restores_build_even_when_the_body_raises():
    original = intrabar.build
    with pytest.raises(RuntimeError):
        with _spy({}):
            assert intrabar.build is not original
            raise RuntimeError("boom")
    assert intrabar.build is original
