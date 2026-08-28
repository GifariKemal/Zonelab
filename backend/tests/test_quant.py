"""Mesin statistik `tools/quant.py`, diuji pada deret yang dibuat sendiri.

TANPA MT5. Setiap fungsi di bawah menerima baris trade sebagai dict, jadi test
ini menyuntikkan deret yang jawabannya sudah diketahui secara aritmetika. Itu
satu-satunya cara memisahkan "kodenya benar" dari "pasarnya sedang baik".

Yang paling penting di file ini ada dua. Pertama, `test_max_drawdown_depends_on
_the_order`: max drawdown adalah properti URUTAN, dan sebuah implementasi yang
mengurutkan atau mengelompokkan baris sebelum menghitungnya akan memberi angka
yang lebih kecil dan tetap terlihat masuk akal. Kedua, `test_null_ruin_is_worse
_than_live_ruin`: skenario null yang TIDAK lebih buruk berarti pergeseran
mean-nya tidak terjadi, dan seluruh tabel sizing jadi bohong ke arah yang
menenangkan.
"""

from __future__ import annotations

import math

import pytest

from tools.quant import (
    autocorrelation,
    bootstrap,
    concurrency,
    folds,
    kelly,
    metrics,
    null_ruin,
    ruin,
    sign_test,
)


def rows(values, start=0, hold=3):
    """Baris trade minimal: R, bar masuk, bar keluar, biaya, malam."""
    return [
        {"r": float(v), "at": start + i * (hold + 1),
         "exit": start + i * (hold + 1) + hold, "cost_r": 0.1, "nights": 0,
         "won": v > 0}
        for i, v in enumerate(values)
    ]


# ---------------------------------------------------------------- metrics


def test_metrics_on_a_hand_computable_series():
    """Empat trade, +1 +1 -1 +1. Mean +0,5, SD 1,0, win 75%."""
    m = metrics(rows([1.0, 1.0, -1.0, 1.0]))
    assert m["n"] == 4
    assert m["exp_r"] == pytest.approx(0.5)
    assert m["sd"] == pytest.approx(1.0)
    assert m["se"] == pytest.approx(0.5)
    assert m["t"] == pytest.approx(1.0)
    assert m["win_rate"] == pytest.approx(0.75)
    assert m["payoff"] == pytest.approx(1.0)
    assert m["total_r"] == pytest.approx(2.0)


def test_confidence_interval_brackets_the_mean_symmetrically():
    m = metrics(rows([1.0, 1.0, -1.0, 1.0]))
    assert m["ci_lo"] == pytest.approx(m["exp_r"] - 1.96 * m["se"])
    assert m["ci_hi"] == pytest.approx(m["exp_r"] + 1.96 * m["se"])


def test_max_drawdown_depends_on_the_order():
    """Himpunan R yang SAMA, dua urutan, dua drawdown.

    Ini yang membuat drawdown berbeda dari metrik lain di file itu: mengurutkan
    baris sebelum menghitungnya, atau mengelompokkannya per instrumen, akan
    memberi angka yang lebih kecil dan tetap terlihat wajar.
    """
    losses_first = metrics(rows([-1.0, -1.0, -1.0, 3.0, 3.0]))
    losses_last = metrics(rows([3.0, 3.0, -1.0, -1.0, -1.0]))
    assert losses_first["total_r"] == losses_last["total_r"]
    assert losses_first["max_dd"] == pytest.approx(3.0)
    assert losses_last["max_dd"] == pytest.approx(3.0)
    mixed = metrics(rows([3.0, -1.0, 3.0, -1.0, -1.0]))
    assert mixed["max_dd"] < losses_first["max_dd"]


def test_an_empty_series_reports_nothing_rather_than_zero():
    """Nol bukan jawaban untuk "berapa ekspektasinya" pada nol trade, karena ia
    akan terbaca sebagai "diukur dan hasilnya nol"."""
    assert metrics([]) == {"n": 0}


def test_kurtosis_is_raw_and_not_excess():
    """Deret normal harus memberi kurtosis sekitar 3, bukan sekitar 0. PSR dan
    minTRL memakai bentuk mentah, dan konvensi yang tertukar menggeser keduanya
    tanpa error apa pun."""
    import numpy as np

    r = np.random.default_rng(4).normal(size=20000)
    m = metrics(rows(r))
    assert 2.8 < m["kurtosis"] < 3.2, m["kurtosis"]


# ------------------------------------------------------------ autocorrelation


def test_autocorrelation_is_near_zero_for_independent_draws():
    import numpy as np

    r = np.random.default_rng(2).normal(size=4000)
    acf = autocorrelation(rows(r))
    assert max(abs(v) for v in acf) < 0.05, acf


def test_autocorrelation_finds_an_alternating_series():
    """+1 -1 +1 -1 punya lag-1 mendekati -1. Kalau tandanya terbalik di
    implementasi, baris ini yang menangkapnya."""
    acf = autocorrelation(rows([1.0, -1.0] * 200))
    assert acf[0] < -0.9
    assert acf[1] > 0.9


def test_autocorrelation_of_a_flat_series_is_empty_rather_than_nan():
    assert autocorrelation(rows([1.0] * 50)) == []


# -------------------------------------------------------------------- folds


def test_folds_split_by_bar_and_purge_what_straddles():
    """Trade yang keluar setelah batas fold dibuang dari fold itu. Tanpa ini,
    dua fold bersebelahan berbagi bar yang sama tanpa ada yang menyebutnya."""
    straddler = {"r": 5.0, "at": 95, "exit": 130, "cost_r": 0.1, "nights": 0}
    inside = {"r": 1.0, "at": 10, "exit": 20, "cost_r": 0.1, "nights": 0}
    out, purged = folds([inside, straddler], bars=800, count=8)
    assert purged == 1
    assert out[0]["n"] == 1 and out[0]["exp_r"] == pytest.approx(1.0)
    assert out[1]["n"] == 0


def test_sign_test_matches_the_binomial_by_hand():
    """8 dari 8 positif pada koin jujur: 2 * (1/256) = 0,0078."""
    assert sign_test([1.0] * 8) == pytest.approx(2 / 256, abs=1e-6)
    assert sign_test([1.0] * 4 + [-1.0] * 4) == pytest.approx(1.0)
    assert sign_test([]) == 1.0


# --------------------------------------------------------------- konkurensi


def test_concurrency_counts_overlap_and_the_peak():
    spans = [
        {"r": 1.0, "at": 0, "exit": 10},
        {"r": 1.0, "at": 5, "exit": 15},   # tumpang tindih dengan yang pertama
        {"r": 1.0, "at": 7, "exit": 9},    # tumpang tindih dengan keduanya
        {"r": 1.0, "at": 50, "exit": 55},  # sendiri
    ]
    got = concurrency(spans)
    assert got["overlapping"] == 2
    assert got["peak_concurrent"] == 3
    assert got["overlap_rate"] == pytest.approx(0.5)


def test_no_overlap_when_every_trade_closes_before_the_next_opens():
    got = concurrency(rows([1.0] * 5, hold=3))
    assert got["overlapping"] == 0 and got["peak_concurrent"] == 1
    assert got["avg_hold_bars"] == pytest.approx(4.0)


# ---------------------------------------------------------------- bootstrap


def test_bootstrap_median_lands_near_the_realised_total():
    """Resample dari deret yang sama harus memusat di total deret itu. Kalau
    tidak, ada bias di pengambilannya."""
    data = rows([1.0, -1.0, 1.0, -1.0, 1.0, 1.0] * 20)
    total = sum(x["r"] for x in data)
    b = bootstrap(data, draws=4000, seed=1)
    assert b["total_r_p50"] == pytest.approx(total, rel=0.15)
    assert b["total_r_p05"] < b["total_r_p50"] < b["total_r_p95"]


def test_bootstrap_drawdown_is_at_least_the_realised_one_at_the_upper_tail():
    """p95 dari sebaran drawdown harus melebihi drawdown yang teramati. Kalau
    tidak, sebarannya lebih sempit dari kenyataan dan seluruh guna tabel itu
    hilang."""
    data = rows([1.0, -1.0] * 60 + [-1.0, -1.0, 1.0] * 20)
    realised = metrics(data)["max_dd"]
    b = bootstrap(data, draws=4000, seed=3)
    assert b["max_dd_p95"] >= realised


def test_bootstrap_of_a_two_trade_series_still_answers():
    assert bootstrap(rows([1.0, -1.0]), draws=100)["draws"] == 100
    assert bootstrap(rows([1.0])) == {}


def test_block_bootstrap_returns_the_same_length_paths():
    """Blok yang tidak membagi n harus tetap menghasilkan path sepanjang n, atau
    total R-nya akan lebih kecil hanya karena aritmetika indeks."""
    data = rows([1.0] * 7)
    b = bootstrap(data, draws=500, block=3, seed=5)
    assert b["total_r_p50"] == pytest.approx(7.0)


# ------------------------------------------------------------ Kelly dan ruin


def test_kelly_matches_the_worked_example():
    """p=0,4 W=2R L=1R memberi f* = 0,4/1 - 0,6/2 = 0,1."""
    data = rows([2.0] * 4 + [-1.0] * 6)
    k = kelly(data)
    assert k["p"] == pytest.approx(0.4)
    assert k["kelly_f"] == pytest.approx(0.1, abs=1e-9)
    assert k["half_kelly"] == pytest.approx(0.05, abs=1e-9)


def test_kelly_declines_to_answer_without_both_sides():
    assert kelly(rows([1.0, 2.0])) == {}
    assert kelly(rows([-1.0, -2.0])) == {}


def test_ruin_rises_with_the_risk_fraction():
    data = rows([1.0, -1.0, 1.0, -1.0, -1.0] * 20)
    small = ruin(data, 0.01, paths=3000, trades_ahead=200)
    large = ruin(data, 0.15, paths=3000, trades_ahead=200)
    assert large["p_ruin"] > small["p_ruin"]


def test_null_ruin_is_worse_than_live_ruin():
    """Deret dengan edge positif digeser ke mean nol harus jadi LEBIH berbahaya.

    Kalau tidak, pergeserannya tidak terjadi, dan tabel sizing berbohong ke arah
    yang menenangkan, yang merupakan arah paling mahal untuk salah.
    """
    data = rows([2.0] * 60 + [-1.0] * 40)
    live = ruin(data, 0.05, paths=4000, trades_ahead=300)
    null = null_ruin(data, 0.05, paths=4000, trades_ahead=300)
    assert null["p_ruin"] > live["p_ruin"]


def test_ruin_never_exceeds_one_and_never_goes_negative():
    data = rows([1.0, -1.0] * 30)
    for risk in (0.001, 0.05, 0.5, 0.99):
        p = ruin(data, risk, paths=1000, trades_ahead=100)["p_ruin"]
        assert 0.0 <= p <= 1.0


def test_a_total_loss_bet_size_does_not_produce_nan():
    """Risk 100% pada R = -1 menghapus akun tepat sekali. `log1p` di clip harus
    menahannya, bukan menghasilkan -inf yang menyebar ke seluruh tabel."""
    got = ruin(rows([-1.0, 1.0]), 1.0, paths=500, trades_ahead=50)
    assert math.isfinite(got["equity_p50"])
    assert got["p_ruin"] == pytest.approx(1.0)


def test_the_single_cell_path_passes_the_same_flags_as_the_matrix_path(monkeypatch):
    """`--quant` dan `--tcistd` harus SAMPAI ke `cell`, bukan cuma ke header.

    Sampai 28 Agustus 2026 jalur satu simbol memanggil
    `cell(symbol, interval, flat, bars)` tanpa kedua flag, sementara header di
    atasnya tetap mencetak "filters: Z-Score+Volume+Regime". Dua run pada
    XAUUSD 1h, satu dengan `--quant` dan satu tanpa, keluar bit-identik: 535
    trade, Kelly -0.0344, PSR 0.3210 pada keduanya.

    Konsekuensinya bukan sekadar flag yang tidak jalan. Ia membuat pilar
    Z-Score terbaca "sudah diukur dan tidak berpengaruh" oleh siapa pun yang
    menjalankan mode satu simbol, padahal filternya tidak pernah dijalankan
    sekali pun. Sebuah instrumen yang melaporkan hijau di atas sesuatu yang
    tidak berjalan adalah kegagalan yang paling sering memakan waktu di project
    ini, dan ini bentuknya yang paling mahal: ia menghasilkan angka yang salah
    label, bukan error.
    """
    import sys

    from tools import quant

    seen: dict = {}

    def fake_cell(symbol, interval, flat=True, bars=0, tcistd=False, quant_=False,
                  **kwargs):
        seen.update(symbol=symbol, interval=interval, tcistd=tcistd,
                    quant=kwargs.get("quant", quant_))
        return {"symbol": symbol, "interval": interval, "n": 0, "note": "stub"}

    monkeypatch.setattr(quant, "cell", fake_cell)
    monkeypatch.setattr(sys, "argv", [
        "quant", "--symbol", "XAUUSD", "--interval", "1h", "--quant", "--tcistd",
    ])

    quant.main()

    assert seen.get("symbol") == "XAUUSD", "cell tidak pernah dipanggil"
    assert seen["quant"] is True, (
        "--quant tidak sampai ke cell: header mencetak filter menyala sementara "
        "baseline yang dijalankan"
    )
    assert seen["tcistd"] is True, "--tcistd tidak sampai ke cell"


def quant_candle(t: int, price: float, width: float):
    """Satu bar dengan tinggi yang dikendalikan, untuk menggerakkan ATR."""
    from app.models import Candle

    return Candle(time=t, open=price, high=price + width, low=price - width,
                  close=price, volume=100.0)


def test_the_regime_is_judged_at_the_trade_bar_and_never_from_later_bars(monkeypatch):
    """Rezim per trade, dan dari sejarah yang knowable di bar itu saja.

    Versi lama memanggil `regime` SEKALI atas seluruh deret, jadi verdict-nya
    sama untuk setiap trade: filternya cuma bisa membunuh semuanya atau tidak
    sama sekali. Dan persentilnya menghitung bar yang belum terjadi saat trade
    diambil, yang membuat sebuah bar terbaca chop gara-gara volatilitas enam
    bulan kemudian.

    Deret di bawah tenang dulu lalu meledak. Trade yang lahir di bagian tenang
    HARUS dinilai dari bagian tenang saja, jadi ia tidak boleh terbaca chop
    hanya karena ledakan yang menyusul.
    """
    from tools import quant

    seen: list[int] = []
    real_regime = quant.regime_filter

    def spy(atr_slice):
        seen.append(len(atr_slice))
        return real_regime(atr_slice)

    monkeypatch.setattr(quant, "regime_filter", spy)
    monkeypatch.setattr(quant.history, "load", lambda *a, **k: [])

    step = 3600
    rows = []
    for i in range(400):
        # 300 bar rentang sempit, lalu 100 bar rentang lebar.
        width = 0.5 if i < 300 else 20.0
        price = 100.0 + (i % 3)
        rows.append(quant_candle(1_700_000_000 + i * step, price, width))

    trades_in = [{"at": 120, "side": "demand"}, {"at": 380, "side": "supply"}]
    quant.quant_filter("XAUUSD", rows, "1h", trades_in)

    assert seen, "regime tidak pernah dipanggil"
    # SATU PANGGILAN PER BAR TRADE, dengan panjang potongan = bar + 1. Kalau
    # filternya kembali menilai sekali untuk seluruh deret, panjangnya akan
    # 400 pada kedua trade.
    assert sorted(seen) == [121, 381], seen


def test_tcisd_that_cannot_be_computed_returns_no_trades_rather_than_all(
    monkeypatch, capsys,
):
    """Diam tidak lolos sebagai persetujuan, aturan `Setup.failed_required`.

    Versi lama mengembalikan SELURUH trade tiap kali filter tCISD tidak bisa
    dihitung, jadi `--tcistd` mencetak "entry: tCISD" lalu mengukur populasi
    yang tidak difilter sama sekali. Terukur 28 Agustus 2026 pada XAUUSD 1h:
    535 trade dengan flag dan 535 tanpa, exp R -0,0210 pada keduanya, identik
    sampai digit terakhir. Angka yang salah label lebih mahal daripada error.
    """
    from tools import quant

    monkeypatch.setattr(quant.history, "load", lambda *a, **k: [])
    monkeypatch.setattr(quant, "trades",
                        lambda *a, **k: [{"at": 1, "side": "demand",
                                          "skipped": False}])

    out = quant.tcisd_trades("XAUUSD", [], "1h")

    assert out == [], "filter yang tidak bisa dihitung meloloskan semuanya"
    assert "0 trade" in capsys.readouterr().out


def test_one_failing_cell_stops_that_cell_and_not_the_whole_matrix(
    monkeypatch, capsys,
):
    """Aturan `execute.gather`, dibawa ke matrix: satu deret gagal, satu deret.

    28 Agustus 2026 satu `ProviderError` pada USOIL membatalkan seluruh
    `--matrix` setelah 22 sel selesai dihitung, termasuk ringkasan DSR di
    bawahnya. Yang membuatnya mahal adalah bentuk keluarannya: tabel 22 baris
    tercetak rapi, traceback-nya mendarat di ATAS file karena stderr tidak
    dibuffer sementara stdout dibuffer, dan exit code-nya 1. Pembaca yang
    menilai dari tabel akan menyimpulkan run itu sukses dengan universe yang
    lebih kecil.

    Kegagalannya juga sesaat, bukan permanen: simbol yang sama terbaca 500 bar
    satu menit kemudian. Daemon auto-trade memanggil terminal yang sama tiap 20
    detik, jadi rebutan adalah keadaan normal di mesin ini.
    """
    import sys

    from tools import quant

    calls: list[str] = []

    def flaky_cell(symbol, interval, flat=True, bars=0, **kwargs):
        calls.append(symbol)
        if symbol == "XAGUSD":
            raise RuntimeError("mt5 returned no bars for XAGUSD")
        return {"symbol": symbol, "interval": interval, "n": 0, "note": "stub"}

    monkeypatch.setattr(quant, "cell", flaky_cell)
    monkeypatch.setattr(quant, "UNIVERSE", ("XAUUSD", "XAGUSD", "EURUSD"))
    monkeypatch.setattr(sys, "argv",
                        ["quant", "--matrix", "--intervals", "1h"])

    quant.main()
    out = capsys.readouterr().out

    assert calls == ["XAUUSD", "XAGUSD", "EURUSD"], (
        f"matrix berhenti di sel yang gagal: {calls}"
    )
    assert "GAGAL" in out
    assert "1 sel GAGAL" in out, "sel yang hilang tidak dilaporkan"
