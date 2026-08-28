"""Tiga modul yang dipakai jalur riset dan tidak punya satu pun test.

KENAPA FILE INI ADA. `app/regime.py`, `app/zscore.py` dan `app/triad.py`
dipanggil dari kode yang benar-benar jalan - dua yang pertama dari
`tools/quant.py`, yang ketiga dari endpoint `/api/triad` yang hasilnya diumpankan
ke AI Agent - dan tidak satu pun pernah dieksekusi oleh test. `test_quant.py`
mengimpor sembilan fungsi statistik murni dan tidak menyentuh `quant_filter`
maupun `tcisd_trades`, jadi jalur yang memanggil ketiga modul ini tidak pernah
dilewati.

Konsekuensinya bukan hipotetis. Kalau `regime()` membalik klasifikasi chop, sebuah
aturan bisa lolos uji stabilitas dengan alasan yang salah dan tidak ada baris
merah di mana pun. Kalau `_consolidation_score` salah, agen mengutip Truth Asset
yang salah ke pembaca dengan percaya diri penuh.

Yang diuji di sini adalah PROPERTI, bukan angka: arah klasifikasi, warm-up yang
jujur, tie-break, dan penolakan yang benar saat data tidak cukup. Seri dibangun
dengan tangan supaya jawaban benarnya diketahui secara konstruksi.
"""

from __future__ import annotations

import numpy as np

from app.models import Candle
from app.regime import MIN_ATR_HISTORY, regime
from app.tcisd import TCISDEntry, placeable
from app.triad import truth_asset
from app.zscore import direction, spread, validate, zscore


def bars(highs: list[float], lows: list[float], step: int = 3600) -> list[Candle]:
    """Candle dari pasangan high/low; close di tengah supaya ATR terdefinisi."""
    return [
        Candle(
            time=i * step,
            open=(h + lo) / 2,
            high=h,
            low=lo,
            close=(h + lo) / 2,
            volume=1.0,
        )
        for i, (h, lo) in enumerate(zip(highs, lows))
    ]


# ----------------------------------------------------------------- regime


def test_too_little_history_is_normal_rather_than_a_guess():
    """Di bawah ambang riwayat, jawabannya bukan chop dan bukan wild.

    Ini bentuk yang sama dengan `Candle.spread`: yang belum bisa diukur
    dilaporkan sebagai tidak diukur, bukan sebagai bacaan netral yang kebetulan.
    """
    assert regime(np.full(MIN_ATR_HISTORY - 1, 5.0)) == "normal"
    assert regime(np.array([])) == "normal"


def test_the_classification_is_not_inverted():
    """ATR rendah harus chop dan ATR tinggi harus wild, bukan sebaliknya.

    Justru inilah cacat yang tidak akan tertangkap apa pun sebelum test ini ada:
    membalik dua cabang menghasilkan modul yang tetap berjalan, tetap
    mengembalikan string yang sah, dan menolak trade di rejim yang salah.
    """
    base = np.linspace(1.0, 100.0, MIN_ATR_HISTORY + 20)

    quiet = base.copy()
    quiet[-1] = 0.5  # di bawah persentil 20 mana pun pada deret ini
    assert regime(quiet) == "chop"

    loud = base.copy()
    loud[-1] = 500.0  # di atas persentil 80
    assert regime(loud) == "wild"

    middle = base.copy()
    middle[-1] = float(np.median(base))
    assert regime(middle) == "normal"


def test_a_non_positive_current_atr_is_not_read_as_the_quietest_market():
    """ATR nol berarti tidak terukur, dan nol adalah nilai terendah yang mungkin.

    Tanpa guard-nya, sebuah ATR nol akan selalu jatuh di bawah persentil 20 dan
    dilaporkan sebagai chop - yaitu bacaan rejim yang dibuat oleh data yang hilang.
    """
    series = np.linspace(1.0, 100.0, MIN_ATR_HISTORY + 5)
    series[-1] = 0.0
    assert regime(series) == "normal"


# ----------------------------------------------------------------- zscore


def test_the_warm_up_is_nan_rather_than_zero():
    """Nilai sebelum window penuh harus NaN, bukan nol.

    Nol akan terbaca sebagai "spread tepat di rata-ratanya", yaitu klaim, sedang
    yang benar adalah belum ada rata-rata untuk dibandingkan.
    """
    a = np.linspace(100.0, 120.0, 60)
    b = np.linspace(50.0, 55.0, 60)
    z = zscore(a, b, lookback=50)
    assert len(z) == len(a)
    assert np.isnan(z[:49]).all()
    assert not np.isnan(z[-1])


def test_two_series_moving_together_produce_no_divergence():
    """Spread konstan berarti sigma nol, dan sigma nol bukan Z besar.

    Pembagian tanpa guard akan memberi inf atau NaN yang lolos sebagai
    "divergensi ekstrem" - kebalikan dari yang benar, karena spread yang tidak
    bergerak adalah dua aset yang bergerak bersama.
    """
    a = np.linspace(100.0, 200.0, 80)
    b = a / 2.0  # log spread konstan: log(a) - log(a/2) = log 2
    z = zscore(a, b, lookback=50)
    assert not validate(float(np.nan_to_num(z[-1], nan=0.0)))
    assert np.isnan(z[-1]) or abs(z[-1]) < 2.0


def test_the_spread_is_scale_invariant():
    """Log spread, jadi mengalikan satu deret dengan konstanta menggeser level
    dan tidak mengubah bentuknya. Itu alasan modul ini memakai log dan bukan
    selisih harga, dan itu properti yang harus dijaga."""
    a = np.array([100.0, 110.0, 105.0])
    b = np.array([50.0, 55.0, 52.5])
    base = spread(a, b)
    scaled = spread(a * 1000.0, b * 1000.0)
    assert np.allclose(base, scaled)


def test_validate_and_direction_agree_on_the_same_threshold():
    """Dua fungsi di satu file tidak boleh berbeda pendapat soal satu bacaan.

    `direction` mematok 2.0 sementara `validate` menerima parameter, jadi
    memanggil keduanya dengan threshold 1.5 memberi "signifikan" dari yang satu
    dan "neutral" dari yang lain.
    """
    z = 1.7
    assert not validate(z, 2.0)
    assert direction(z, 2.0) == "neutral"
    assert validate(z, 1.5)
    assert direction(z, 1.5) == "up"
    assert direction(-z, 1.5) == "down"


def test_a_nan_reading_is_neutral_and_not_significant():
    assert not validate(float("nan"))
    assert direction(float("nan")) == "neutral"


# ----------------------------------------------------------------- triad


def test_the_truth_asset_is_the_tightest_range_not_the_widest():
    """Skor konsolidasi rendah berarti range sempit terhadap volatilitasnya
    sendiri, jadi Truth Asset adalah yang TERENDAH. Membalik perbandingan
    menghasilkan modul yang tetap menjawab sebuah simbol, dan menjawab yang
    persis salah - dan agen akan mengutipnya."""
    n = 40
    tight = bars([100.5] * n, [99.5] * n)
    wide = bars([100.0 + i for i in range(n)], [99.0 - i for i in range(n)])

    reading = truth_asset({"TIGHT": tight, "WIDE": wide}, "TIGHT", "monetary")
    assert reading is not None
    assert reading.symbol == "TIGHT", reading.scores
    assert reading.scores["TIGHT"] < reading.scores["WIDE"]


def test_a_series_too_short_to_measure_is_dropped_not_fatal():
    """Satu partner yang tidak bisa diukur tidak boleh membatalkan bacaannya.

    Bentuk yang sama dengan cacat `aligned.py`: satu simbol yang gagal pernah
    membatalkan tujuh partner yang sah.
    """
    n = 40
    good = bars([100.5] * n, [99.5] * n)
    short = bars([100.0, 101.0], [99.0, 98.0])

    reading = truth_asset({"GOOD": good, "SHORT": short}, "GOOD", "monetary")
    assert reading is not None
    assert "SHORT" not in reading.scores
    assert reading.symbol == "GOOD"


def test_nothing_measurable_is_none_rather_than_a_default_pick():
    """Kalau tidak ada yang bisa diukur, jawabannya None. Memilih simbol
    pertama akan menjadi bacaan yang dibuat oleh ketiadaan data."""
    short = bars([100.0, 101.0], [99.0, 98.0])
    assert truth_asset({"A": short, "B": list(short)}, "A", "monetary") is None


# ----------------------------------------------------------------- tcisd


def test_a_tcisd_entry_is_only_placeable_from_the_side_it_retests_from():
    """Limit buy harus berada DI BAWAH pasar dan limit sell di atasnya.

    Kalau ini terbalik, jalur order mengirim limit di sisi yang salah, yang
    terisi seketika sebagai market order dengan harga lebih buruk.
    """
    buy = TCISDEntry(level=100.0, candle_at=5, broken_at=7, stop=99.0, direction="buy")
    sell = TCISDEntry(level=100.0, candle_at=5, broken_at=7, stop=101.0, direction="sell")

    assert placeable(buy, 101.0)
    assert not placeable(buy, 99.0)
    assert placeable(sell, 99.0)
    assert not placeable(sell, 101.0)
    # Tepat di level bukan placeable di kedua arah: perbandingannya ketat.
    assert not placeable(buy, 100.0)
    assert not placeable(sell, 100.0)
