"""Peluang yang dilekatkan di order harus benar, atau ia lebih buruk daripada
tidak ada.

Sampai 3 September 2026 order dipasang tanpa satu angka pun tentang seberapa
sering setup seperti itu berakhir bagaimana. Yang paling berbahaya bukan
ketiadaannya, tapi angka tunggal yang salah baca: P(R > 0) untuk supply_demand
XAUUSD 30m adalah 0,5496, dan itu terbaca sebagai "menang 55 persen" padahal
target 2R hanya kena 4,9 persen dan hampir setiap kemenangan adalah exit horizon
kecil rata-rata +0,445 R.
"""

from __future__ import annotations

import json

import pytest

from app import probability
from app.probability import outcome_odds, summary


def test_it_reports_four_outcomes_and_never_one_win_rate():
    """Satu angka akan menipu sebelas kali lipat. Empat yang keluar.

    Kalau suatu saat ini diringkas jadi satu "win rate", angka 55 persen itu
    akan muncul di sebelah order yang target-nya kena 5 persen.
    """
    got = outcome_odds("supply_demand", "XAUUSD", "30m")
    assert got is not None
    for key in ("p_full_stop", "p_small_loss", "p_small_win", "p_target",
                "exp_r", "n", "p_target_ci95"):
        assert key in got, key
    total = (got["p_full_stop"] + got["p_small_loss"] + got["p_small_win"]
             + got["p_target"])
    assert abs(total - 1.0) < 1e-9, total
    # Dan jaraknya harus tetap terlihat: target jauh di bawah "menang".
    assert got["p_target"] < 0.10
    assert got["p_small_win"] > 0.40


def test_the_gate_side_selects_the_population_that_is_actually_ordered():
    """Sisi yang salah mencetak peluang dari populasi yang tak pernah diorder.

    Untuk `fvg` gerbangnya TERBALIK: sisi bawah n=1939 dengan P(target) 0,1444,
    sisi atas n=62 dengan P(target) 0,0161. Jalur order mengambil sisi bawah,
    jadi mencetak sisi atas akan salah sembilan kali lipat di angka yang paling
    diperhatikan.
    """
    below = outcome_odds("fvg", "XAUUSD", "30m", cleared_gate=False)
    above = outcome_odds("fvg", "XAUUSD", "30m", cleared_gate=True)
    assert below is not None and above is not None
    assert below["n"] > above["n"] * 10, (below["n"], above["n"])
    assert below["p_target"] > above["p_target"] * 5
    assert "below_gate" in below["population"]
    assert "above_gate" in above["population"]


def test_an_unmeasured_population_returns_none_not_a_guess():
    """Layer atau timeframe yang belum diukur tidak punya peluang.

    Mengisinya dengan rata-rata global akan memberi angka yang terlihat sah
    untuk setup yang tidak pernah dilihat siapa pun, dan itu lebih buruk
    daripada diam.
    """
    assert outcome_odds("breaker", "XAUUSD", "30m") is None
    assert outcome_odds("ifvg", "XAUUSD", "30m") is None
    assert outcome_odds("fvg", "XAUUSD", "1h") is None
    assert outcome_odds("fvg", "EURUSD", "30m") is None
    assert summary(None) == "peluang: BELUM DIUKUR untuk populasi ini"


def test_the_venue_prefix_does_not_lose_the_lookup():
    """`mt5:XAUUSD` dan `XAUUSD` harus menjawab sama.

    Jalur order mengoper simbol berprefix, dan tabelnya memakai ticker
    telanjang. Sebuah lookup yang meleset di sini akan mencetak "BELUM DIUKUR"
    untuk setiap order sungguhan sementara test yang memakai ticker telanjang
    tetap hijau.
    """
    assert outcome_odds("fvg", "mt5:XAUUSD", "30m") == outcome_odds(
        "fvg", "XAUUSD", "30m")


def test_a_missing_table_does_not_take_the_order_path_down(monkeypatch,
                                                           tmp_path):
    """File hilang berarti TIDAK ADA peluang, bukan crash.

    Jalur order memasang uang sungguhan; sebuah tabel kalibrasi yang hilang
    tidak boleh jadi alasan ia berhenti.
    """
    monkeypatch.setattr(probability, "TABLE", tmp_path / "tidak-ada.json")
    monkeypatch.setattr(probability, "_cache", None)
    assert outcome_odds("fvg", "XAUUSD", "30m") is None

    rusak = tmp_path / "rusak.json"
    rusak.write_text("{ bukan json", encoding="utf-8")
    monkeypatch.setattr(probability, "TABLE", rusak)
    monkeypatch.setattr(probability, "_cache", None)
    assert outcome_odds("fvg", "XAUUSD", "30m") is None


def test_the_thresholds_match_the_tool_that_wrote_the_table():
    """Dua definisi bucket yang melenceng membuat angkanya berhenti berarti."""
    from tools import entry_probability

    assert probability.FULL_STOP == entry_probability.FULL_STOP
    assert probability.SMALL_LOSS == entry_probability.SMALL_LOSS
    assert probability.TARGET_R == entry_probability.TARGET_R


def test_the_summary_names_n_so_sixty_two_never_reads_like_two_thousand():
    """Peluang dari 62 trade dan dari 1.939 tidak boleh terbaca sama."""
    line = summary(outcome_odds("fvg", "XAUUSD", "30m", cleared_gate=True))
    assert "n=62" in line, line
    assert "CI" in line, line


def test_the_order_path_prints_the_odds_and_picks_the_side_from_the_gate():
    """PENJAGA WIRING. Sebuah peluang yang tidak tercetak tidak menolong siapa pun.

    Dan sisinya harus datang dari `GATE_DIRECTION`, bukan dari
    `zone.departure_atr` mentah: untuk fvg gerbangnya terbalik, jadi membaca
    departure langsung akan memilih populasi yang salah tanpa satu error pun.
    """
    import inspect

    # `cycle`, bukan `candidates`: di situ baris per kandidat dicetak ke
    # operator, dan sebuah peluang yang dihitung tapi tidak dicetak sama saja
    # dengan tidak ada.
    from tools.execute import cycle

    src = inspect.getsource(cycle)
    assert "outcome_odds(" in src, "peluang tidak dihitung di jalur order"
    # HASILNYA harus masuk ke `head`, bukan sekadar dipanggil. Versi pertama
    # test ini cuma mencari `odds_line(odds)`, dan mengganti barisnya jadi
    # `_unused = odds_line(odds)` tetap membuatnya HIJAU sementara peluangnya
    # berhenti tercetak.
    assert "head += " in src and "odds_line(odds)" in src
    joined = [l for l in src.splitlines() if "odds_line(odds)" in l]
    assert joined and all("head" in l for l in joined), joined
    assert 'GATE_DIRECTION.get(layer, "floor") == "floor"' in src, src[:200]


def test_the_table_on_disk_carries_its_preregistration():
    """Tabel tanpa praregistrasinya adalah angka tanpa asalnya."""
    if not probability.TABLE.exists():
        pytest.skip("tabel kalibrasi belum dihasilkan di mesin ini")
    data = json.loads(probability.TABLE.read_text(encoding="utf-8"))
    pre = data.get("preregistration") or {}
    assert pre.get("source", "").startswith("tools/entry_probability.py")
    assert "why_not_direction" in pre, "harus menyatakan ini BUKAN prediksi arah"
    assert pre.get("buckets"), "ambang bucket harus tercatat bersama angkanya"
