"""Pita DFR: Python lawan Pine detektor 10, pada FEED YANG SAMA.

KENAPA BERKAS INI ADA. Dua implementasi DFR dibangun pada 9 September 2026 -
`app/quarterly.defining_range` di Python dan detektor 10 di
`mql5/pine/ZonelabImbalanceStrategy.pine` - dan tidak satu pun membuktikan
keduanya menghasilkan pita yang sama. Angka dilaporkan dari keduanya sebelum itu
diperiksa.

FEED-NYA HARUS SAMA, dan itu seluruh sebab bentuk tes ini aneh. Zonelab membaca
terminal MT5, TradingView membaca OANDA, dan harga keduanya berbeda beberapa sen.
Membandingkan lintas feed tidak bisa memisahkan "aturannya beda" dari "datanya
beda" - alasan yang sama yang ditulis `tools/box_parity.py`. Jadi bar di bawah
DISALIN DARI TRADINGVIEW lewat `data_get_ohlcv` pada OANDA:XAUUSD 1 jam, dan
harga harapannya DISALIN DARI TABEL PINE yang berjalan di bar-bar itu juga.
Selisih apa pun yang tersisa adalah selisih aturan.

YANG DIUJI, dan kenapa justru ini. Dua hal paling mungkin berbeda antara dua
implementasi ini, dan keduanya terbaca dari waktu dan harga pita:

  1. BATAS KUARTAL DALAM WAKTU NEW YORK. Q1 derajat hari adalah 18:00-00:00 New
     York. Pada September itu EDT, jadi jendelanya tutup pukul 04:00 UTC. Pine
     memakai `hour(time, "America/New_York")`, Python memakai `app/quarters.py`.
     Dua jalur berbeda menuju batas yang sama, dan pergeseran satu jam saja akan
     menggeser SETIAP harga di bawah.
  2. PEMOTONGAN SEPERTIGA. Dari kuartal 6 jam, dua jam pertama dibuang, jadi
     jendela yang disimpan 00:00-04:00 UTC. Membuang di ujung yang salah, atau
     memotong dengan pembulatan yang berbeda, mengubah high dan low.

Harga harapan diformat `#.##` di Pine, jadi perbandingannya dilakukan pada dua
desimal DENGAN pembulatan yang sama, bukan pada float mentah.

DAN PEMBULATAN ITU BUKAN DETAIL. Versi pertama tes ini memakai `round()` bawaan
Python dan GAGAL di tiga dari sepuluh harga - 4282.625, 4487.545 dan 4429.605.
Ketiganya kasus tepat-setengah, dan nilai mentahnya identik dengan bar-nya:
`round()` Python membulatkan setengah KE GENAP, `str.tostring(x, "#.##")` di
Pine membulatkan setengah MENJAUH DARI NOL. Yang tidak sepakat komparatornya,
bukan kedua implementasinya. Karena itu `_half_up` di bawah, dan karena itu
`round()` tidak boleh dipakai di berkas ini.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.models import Candle
from tools.dfr_zone import bands

# Bar OANDA:XAUUSD 1 jam, disalin apa adanya dari `data_get_ohlcv` TradingView
# pada 9 September 2026. Lima jendela DFR yang disimpan, masing-masing empat bar
# (00:00 sampai 03:00 UTC), ditambah bar 04:00 yang membuktikan jendelanya sudah
# tutup - tanpa bar itu `_closed` menolak dan tidak ada pita yang lahir.
BARS = [
    # 2026-09-02
    (1788307200, 4324.455, 4334.590, 4314.630, 4315.905),
    (1788310800, 4315.815, 4326.815, 4288.440, 4291.110),
    (1788314400, 4291.120, 4314.855, 4287.270, 4303.055),
    (1788318000, 4302.950, 4304.455, 4282.625, 4303.450),
    (1788321600, 4303.440, 4308.060, 4301.320, 4307.465),
    # 2026-09-03
    (1788393600, 4385.735, 4397.985, 4382.505, 4395.585),
    (1788397200, 4395.645, 4412.625, 4387.365, 4410.565),
    (1788400800, 4410.530, 4420.565, 4406.795, 4420.425),
    (1788404400, 4420.415, 4432.685, 4419.400, 4431.485),
    (1788408000, 4431.455, 4438.725, 4425.665, 4437.405),
    # 2026-09-04
    (1788480000, 4480.060, 4487.475, 4472.910, 4486.400),
    (1788483600, 4486.510, 4487.545, 4467.125, 4478.925),
    (1788487200, 4479.075, 4482.605, 4470.430, 4477.470),
    (1788490800, 4477.495, 4478.730, 4467.185, 4467.185),
    (1788494400, 4467.145, 4475.125, 4465.490, 4473.825),
    # 2026-09-07, akhir pekan tidak punya bar dan memang tidak boleh punya pita
    (1788739200, 4423.535, 4429.605, 4410.100, 4412.780),
    (1788742800, 4412.750, 4416.870, 4389.585, 4409.215),
    (1788746400, 4409.230, 4419.020, 4403.085, 4408.910),
    (1788750000, 4408.995, 4410.705, 4401.260, 4404.285),
    (1788753600, 4404.270, 4407.455, 4394.580, 4398.145),
    # 2026-09-08
    (1788825600, 4423.145, 4430.325, 4415.215, 4426.255),
    (1788829200, 4426.240, 4440.810, 4417.190, 4437.245),
    (1788832800, 4437.330, 4438.785, 4421.295, 4424.410),
    (1788836400, 4424.405, 4440.235, 4422.750, 4437.875),
    (1788840000, 4437.965, 4442.980, 4431.695, 4436.000),
    # Jendela Q2, 06:00 sampai 09:00 UTC plus bar 10:00 yang menutupnya. Q2
    # ditambahkan 9 September 2026 karena versi pertama berkas ini hanya menguji
    # Q1, dan Q1 SATU-SATUNYA kuartal yang jendelanya melewati tengah malam:
    # `inKept` di Pine bercabang ke bentuk gabungan untuk Q1 dan ke bentuk selang
    # untuk sisanya, jadi lolosnya Q1 tidak mengatakan apa pun soal cabang yang
    # lain - padahal kontrol kuartal COMEX seluruhnya berdiri di atas cabang itu.
    (1788328800, 4320.160, 4329.325, 4314.525, 4321.875),
    (1788332400, 4321.840, 4331.405, 4319.285, 4323.170),
    (1788336000, 4323.200, 4331.645, 4312.685, 4313.070),
    (1788339600, 4313.045, 4322.540, 4304.870, 4308.645),
    (1788343200, 4308.680, 4312.355, 4301.745, 4309.395),
    (1788415200, 4431.185, 4436.380, 4417.575, 4420.590),
    (1788418800, 4420.610, 4431.635, 4419.165, 4428.910),
    (1788422400, 4428.860, 4443.715, 4428.135, 4434.970),
    (1788426000, 4435.025, 4442.040, 4425.595, 4427.620),
    (1788429600, 4427.660, 4429.965, 4419.090, 4427.345),
    (1788501600, 4472.210, 4473.500, 4460.155, 4462.935),
    (1788505200, 4462.915, 4490.895, 4461.510, 4483.425),
    (1788508800, 4483.430, 4486.540, 4474.490, 4477.970),
    (1788512400, 4477.950, 4479.315, 4464.000, 4465.690),
    (1788516000, 4465.665, 4476.450, 4465.530, 4472.955),
    (1788760800, 4394.255, 4399.865, 4385.330, 4392.910),
    (1788764400, 4392.945, 4406.830, 4391.855, 4406.450),
    (1788768000, 4406.350, 4423.885, 4405.275, 4411.005),
    (1788771600, 4411.055, 4413.885, 4403.695, 4405.745),
    (1788775200, 4405.645, 4406.355, 4388.110, 4391.695),
    (1788847200, 4419.595, 4420.365, 4398.325, 4403.710),
    (1788850800, 4403.705, 4409.465, 4390.190, 4392.580),
    (1788854400, 4392.575, 4398.670, 4388.010, 4394.190),
    (1788858000, 4394.185, 4405.725, 4390.900, 4403.040),
    (1788861600, 4403.035, 4407.015, 4393.690, 4395.300),
    # Jendela Q3 (12:00-15:00 UTC) dan Q4 (18:00-21:00 UTC), masing-masing
    # dengan bar penutupnya. Ditambahkan 9 September 2026 supaya keempat
    # kuartal terukur, bukan dua diukur dan dua diargumentasikan.
    (1788350400, 4332.500, 4344.385, 4327.495, 4331.525),
    (1788354000, 4331.610, 4385.515, 4330.850, 4385.120),
    (1788357600, 4385.105, 4397.750, 4374.410, 4377.040),
    (1788361200, 4377.065, 4381.045, 4364.640, 4373.195),
    (1788364800, 4373.180, 4374.910, 4364.520, 4368.400),
    (1788436800, 4444.250, 4495.230, 4437.855, 4493.535),
    (1788440400, 4493.585, 4496.010, 4456.925, 4470.785),
    (1788444000, 4470.780, 4485.425, 4458.385, 4485.365),
    (1788447600, 4485.370, 4510.930, 4484.280, 4493.345),
    (1788451200, 4493.335, 4495.570, 4485.530, 4486.280),
    (1788523200, 4467.170, 4476.665, 4376.180, 4393.770),
    (1788526800, 4393.735, 4434.930, 4365.570, 4413.285),
    (1788530400, 4413.270, 4442.260, 4412.060, 4427.605),
    (1788534000, 4427.670, 4449.000, 4422.825, 4436.655),
    (1788537600, 4436.605, 4443.615, 4432.310, 4436.370),
    (1788782400, 4385.335, 4398.170, 4385.335, 4396.845),
    (1788786000, 4396.745, 4407.850, 4395.470, 4402.430),
    (1788789600, 4402.445, 4419.655, 4401.160, 4416.035),
    (1788793200, 4416.045, 4416.705, 4408.905, 4414.530),
    (1788796800, 4414.515, 4417.400, 4411.965, 4414.575),
    (1788868800, 4406.430, 4411.900, 4385.475, 4411.730),
    (1788872400, 4411.735, 4413.235, 4390.490, 4395.655),
    (1788876000, 4395.635, 4403.715, 4389.295, 4398.845),
    (1788879600, 4398.850, 4409.310, 4394.740, 4394.765),
    (1788883200, 4394.770, 4398.560, 4380.655, 4393.720),
    (1788372000, 4377.075, 4379.850, 4369.320, 4374.265),
    (1788375600, 4374.240, 4391.365, 4371.830, 4391.205),
    (1788379200, 4391.230, 4391.670, 4384.055, 4388.220),
    (1788386400, 4391.290, 4391.835, 4383.535, 4384.750),
    (1788458400, 4486.705, 4489.835, 4474.020, 4475.190),
    (1788462000, 4475.175, 4480.805, 4472.650, 4475.290),
    (1788465600, 4475.235, 4475.740, 4470.550, 4472.965),
    (1788472800, 4476.075, 4478.990, 4471.515, 4474.645),
    (1788544800, 4416.615, 4426.750, 4411.970, 4424.035),
    (1788548400, 4424.060, 4438.565, 4422.615, 4434.925),
    (1788552000, 4434.915, 4435.245, 4428.690, 4429.825),
    (1788732000, 4422.495, 4435.255, 4422.165, 4429.390),
    (1788804000, 4407.180, 4409.185, 4403.130, 4406.065),
    (1788818400, 4412.870, 4413.605, 4406.295, 4407.645),
    (1788890400, 4390.150, 4390.485, 4358.340, 4375.740),
    (1788894000, 4375.695, 4377.460, 4356.800, 4359.505),
    (1788897600, 4359.485, 4364.465, 4345.060, 4355.705),
    (1788904800, 4357.660, 4357.920, 4350.740, 4354.335),
    # Dua bar Senin 7 September yang belum terpakai kuartal mana pun, dibutuhkan
    # supaya jendela derajat MINGGU (06:00-22:00 UTC) utuh.
    (1788778800, 4391.680, 4394.975, 4381.240, 4385.330),
    (1788800400, 4414.570, 4415.185, 4407.125, 4407.175),
]
BARS.sort()

# Disalin dari baris `band0` sampai `band4` tabel Pine, XAUUSD 60,
# detektor 10, kuartal 1. Kuncinya waktu tutup jendela dalam UTC.
PINE = {
    1788321600: (4334.59, 4282.63),
    1788408000: (4432.69, 4382.51),
    1788494400: (4487.55, 4467.13),
    1788753600: (4429.61, 4389.59),
    1788840000: (4440.81, 4415.22),
}


# Kuartal 3, jendela 12:00-16:00 UTC.
PINE_Q3 = {
    1788364800: (4397.75, 4327.5),
    1788451200: (4510.93, 4437.86),
    1788537600: (4476.67, 4365.57),
    1788796800: (4419.66, 4385.34),
    1788883200: (4413.24, 4385.48),
}

# Kuartal 4, jendela 18:00-22:00 UTC. Kuncinya WAKTU BAR KELAHIRAN,
# bukan waktu tutup jendela: pita 4 September lahir di bar 6 September
# 22:00 karena emas tutup akhir pekan dan tidak ada bar di antaranya.
# Python melakukan hal yang sama lewat `bar_at(end)`, jadi keduanya
# sepakat - tapi hanya kalau yang dibandingkan besaran yang sama.
PINE_Q4 = {
    1788386400: (4391.67, 4369.32),
    1788472800: (4489.84, 4470.55),
    1788732000: (4438.57, 4411.97),
    1788818400: (4409.19, 4403.13),
    1788904800: (4390.49, 4345.06),
}

# DERAJAT MINGGU, Q1. Siklusnya buka Minggu 18:00 New York dan kuartalnya satu
# hari penuh, jadi Q1 adalah Senin: jendela yang disimpan 02:00-18:00 New York,
# yaitu 06:00-22:00 UTC. Satu pita saja di deret ini - Senin 7 September - dan
# itu cukup, karena yang diuji CABANG KODENYA, yang berbeda dari derajat hari:
# derajat hari memilih jendela lewat jam, derajat minggu lewat hari dalam
# minggu. Satu-satunya angka yang bisa salah tanpa ketahuan di derajat hari.
PINE_WEEK_Q1 = {
    1788818400: (4423.89, 4381.24),
}

def _half_up(x: float) -> float:
    """Dua desimal, setengah menjauh dari nol - konvensi `#.##` milik Pine."""
    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# Disalin dari baris `band0` sampai `band4` tabel Pine dengan kuartal 2.
# Jendelanya tutup 10:00 UTC, yaitu 06:00 New York, yaitu akhir Q2.
PINE_Q2 = {
    1788343200: (4331.65, 4304.87),
    1788429600: (4443.72, 4417.58),
    1788516000: (4490.90, 4460.16),
    1788775200: (4423.89, 4385.33),
    1788861600: (4420.37, 4388.01),
}


def _candles() -> list[Candle]:
    return [
        Candle(time=t, open=o, high=h, low=lo, close=c, volume=0, spread=0)
        for t, o, h, lo, c in BARS
    ]


def _born(label: str) -> dict[int, tuple[float, float]]:
    """Pita satu kuartal, dikunci ke WAKTU BAR tempat ia jadi knowable.

    Bukan ke `end`, yaitu tutup jendela nominal. Keduanya sama selama ada bar
    tepat di batasnya, dan BERBEDA begitu pasar tutup - yang di deret ini
    terjadi pada Q4 4 September. `zones_for` memakai `bar_at(end)` untuk
    menentukan bar kelahiran, jadi bar itulah yang menentukan kapan zona masuk
    bracket, dan itu besaran yang sama yang dicetak tabel Pine.
    """
    cs = _candles()
    times = [c.time for c in cs]
    out = {}
    for _kept_from, end, hi, lo in bands(cs, 1 / 3, label):
        birth = next((t for t in times if t >= end), None)
        if birth is not None:
            out[birth] = (hi, lo)
    return out


@pytest.fixture(scope="module")
def ours() -> dict[int, tuple[float, float]]:
    return _born("Q1")


@pytest.fixture(scope="module")
def ours_q2() -> dict[int, tuple[float, float]]:
    return _born("Q2")


@pytest.mark.parametrize("end", sorted(PINE_Q2))
def test_q2_identik_juga(ours_q2, end):
    """Cabang jendela yang TIDAK melewati tengah malam, diuji terpisah.

    Q3 dan Q4 memakai cabang yang sama persis dengan Q2 dan hanya berbeda
    konstanta jam pembukanya, jadi satu kuartal non-wrap cukup untuk menutup
    cabang itu. Q1 punya tesnya sendiri di atas karena cabangnya lain.
    """
    want_hi, want_lo = PINE_Q2[end]
    got_hi, got_lo = ours_q2[end]
    assert _half_up(got_hi) == want_hi, f"high pita Q2 {end}"
    assert _half_up(got_lo) == want_lo, f"low pita Q2 {end}"


@pytest.mark.parametrize(
    "label,want", [("Q3", PINE_Q3), ("Q4", PINE_Q4)]
)
def test_q3_dan_q4_identik_juga(label, want):
    """Keempat kuartal diukur, dan versi sebelumnya hanya mengukur dua.

    Q3 dan Q4 dulu DIARGUMENTASIKAN - "cabang non-wrap yang sama dengan Q2,
    cuma beda konstanta jam" - dan argumen itu benar tapi bukan pengukuran.
    Q4 khususnya membawa kasus yang tidak dimiliki kuartal lain: satu pitanya
    lahir dua hari sesudah jendelanya tutup, karena pasar tutup akhir pekan.
    """
    got = _born(label)
    assert sorted(got) == sorted(want), f"pita {label} lahir di instan berbeda"
    for end, (want_hi, want_lo) in want.items():
        got_hi, got_lo = got[end]
        assert _half_up(got_hi) == want_hi, f"high {label} {end}"
        assert _half_up(got_lo) == want_lo, f"low {label} {end}"


def test_derajat_minggu_identik(monkeypatch):
    """Cabang derajat, yang sama sekali tidak tersentuh oleh keempat tes di atas.

    Derajat hari memilih jendela lewat JAM New York; derajat minggu lewat HARI
    dalam minggu, dengan kuartal satu hari penuh dan Jumat bukan kuartal. Dua
    aturan berbeda, dan lolosnya yang satu tidak mengatakan apa pun soal yang
    lain - pelajaran yang sama yang membuat Q3 dan Q4 akhirnya diukur.

    `DEGREE` di `tools.dfr_zone` adalah global yang dipilih baris perintah, jadi
    ia di-monkeypatch di sini dan dikembalikan otomatis - kalau bocor, setiap tes
    derajat hari di berkas ini akan diam-diam mengukur minggu.
    """
    import tools.dfr_zone as rig

    monkeypatch.setattr(rig, "DEGREE", "week")
    cs = _candles()
    times = [c.time for c in cs]
    got = {}
    for _kept_from, end, hi, lo in rig.bands(cs, 1 / 3, "Q1"):
        birth = next((t for t in times if t >= end), None)
        if birth is not None:
            got[birth] = (hi, lo)

    assert sorted(got) == sorted(PINE_WEEK_Q1), "pita minggu lahir di instan berbeda"
    for end, (want_hi, want_lo) in PINE_WEEK_Q1.items():
        got_hi, got_lo = got[end]
        assert _half_up(got_hi) == want_hi, f"high minggu {end}"
        assert _half_up(got_lo) == want_lo, f"low minggu {end}"


def test_q1_dan_q2_tidak_pernah_pita_yang_sama(ours, ours_q2):
    """Dua kuartal, dua jendela, dan tidak boleh ada yang tumpang tindih.

    Kalau pemetaan kuartalnya salah - misalnya offset jam yang sama dipakai dua
    kali - kedua daftar akan memuat instan yang sama dan setiap angka kontrol
    kuartal jadi perbandingan sesuatu dengan dirinya sendiri.
    """
    assert not (set(ours) & set(ours_q2))


def test_pita_yang_sama_lahir_di_instan_yang_sama(ours):
    """Batas kuartalnya sepakat, yang menguji butir 1 di docstring."""
    assert sorted(ours) == sorted(PINE), (
        "Pine dan Python tidak sepakat kapan pita lahir. Selisih di sini adalah "
        "batas kuartal atau zona waktunya, bukan harganya."
    )


@pytest.mark.parametrize("end", sorted(PINE))
def test_high_dan_low_identik_pada_feed_yang_sama(ours, end):
    """Jendela yang disimpan sepakat, yang menguji butir 2 di docstring."""
    want_hi, want_lo = PINE[end]
    got_hi, got_lo = ours[end]
    assert _half_up(got_hi) == want_hi, f"high pita {end}"
    assert _half_up(got_lo) == want_lo, f"low pita {end}"


def test_jendelanya_empat_bar_dan_bukan_enam(ours):
    """Sepertiga pertama memang dibuang, bukan cuma diklaim dibuang.

    Kalau seluruh Q1 dipakai, pita 2026-09-03 akan mengambil juga bar 22:00 dan
    23:00 tanggal 2 - dan low tanggal 2 jauh di bawah, jadi kegagalan aturan
    pertiga akan terlihat sebagai low yang meleset. Yang dicek di sini bahwa
    jendelanya betul-betul empat bar 1 jam.
    """
    kept = {end: kf for kf, end, _hi, _lo in bands(
        [Candle(time=t, open=o, high=h, low=lo, close=c, volume=0, spread=0)
         for t, o, h, lo, c in BARS], 1 / 3)}
    for end, kept_from in kept.items():
        assert end - kept_from == 4 * 3600, (
            f"jendela pita {end} selebar {(end - kept_from) / 3600} jam, "
            "harusnya 4 - dua pertiga dari kuartal 6 jam"
        )
