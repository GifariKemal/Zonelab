"""Ringkasan kontrol resolusi harus membedakan keadaan yang berbeda.

File ini ada karena versi pertama `conclude()` MENJAWAB SALAH pada datanya
sendiri. Ia mencetak "TIDAK BERTAHAN, resolusi halus membalik tandanya"
sementara satu dari empat sel yang berbalik tanda, bukan empat, dan ia
menyatukan dua pertanyaan yang datanya pisahkan dengan jelas: daya pisah
gerbang bertahan di keempat sel, ekspektasi absolut di atas gerbang tidak.

Sebuah ringkasan yang salah lebih buruk daripada tidak ada ringkasan. Ia yang
dikutip.
"""

from __future__ import annotations

from tools.lowtf_resolution import CELLS, FINES, NAMES, conclude, selfcheck


def cell(a: float, b: float, d5: float = 0.2, d1: float = 0.15) -> dict:
    return {"fine_5m": {"exp_r_above": a, "difference": d5},
            "fine_1m": {"exp_r_above": b, "difference": d1}}


def test_the_selfcheck_runs_here_too():
    assert selfcheck() == 0


def test_the_two_questions_are_answered_separately():
    """Angka sungguhannya, dan keduanya harus keluar berbeda.

    supply_demand +0,1110 ke +0,0549 dan +0,0809 ke +0,0359: menyusut, tanda
    bertahan. order_block +0,0701 ke +0,0107 dan +0,0576 ke -0,0031: menyusut,
    tanda HILANG di salah satu sel.
    """
    got = conclude({
        "supply_demand XAUUSD 30m": cell(0.1110, 0.0549, 0.1981, 0.1614),
        "supply_demand BTCUSD 30m": cell(0.0809, 0.0359, 0.2243, 0.1889),
        "order_block XAUUSD 30m": cell(0.0701, 0.0107, 0.1571, 0.1252),
        "order_block BTCUSD 30m": cell(0.0576, -0.0031, 0.2133, 0.1921),
    })
    assert got["separation_survives"] is True
    assert got["all_exp_above_shrink"] is True
    assert got["exp_above_survives"] is False
    assert got["per_detector"]["supply_demand"][
        "exp_above_keeps_sign_at_ratio_30"] is True
    assert got["per_detector"]["order_block"][
        "exp_above_keeps_sign_at_ratio_30"] is False
    assert "bertahan untuk supply_demand" in got["verdict"]
    assert "HILANG untuk order_block" in got["verdict"]


def test_a_dying_separation_reads_differently_from_a_dying_expectation():
    """Kalau H1 ikut mati, kalimatnya tidak boleh sama."""
    got = conclude({"a X 30m": cell(0.11, 0.05, 0.2, -0.01)})
    assert got["separation_survives"] is False
    assert got["verdict"].startswith("SEPARASI gerbang TIDAK bertahan")


def test_growth_is_not_reported_as_shrinkage():
    """Angka yang NAIK di resolusi halus adalah temuan lain, bukan yang ini."""
    assert conclude({"a X 30m": cell(0.05, 0.11)})["all_exp_above_shrink"] is False


def test_an_unreadable_cell_is_not_counted():
    """NaN dan sel kosong tidak boleh terbaca sebagai jawaban."""
    assert conclude({})["verdict"] == "tidak terbaca"
    assert conclude({"a X 30m": cell(float("nan"), 0.05)})["cells_compared"] == 0
    assert conclude({"a X 30m": {"fine_5m": {}, "fine_1m": {}}})[
        "cells_compared"] == 0


def test_the_control_compares_two_resolutions_on_the_traded_cells():
    """Kalau daftarnya bergeser, kontrolnya bukan lagi kontrol untuk studi itu.

    Ia harus membandingkan rasio 6 lawan rasio 30 pada dua sel yang sama dengan
    `lowtf_costed`, dan pada kedua detektor yang studi itu nilai.
    """
    assert FINES == ("5m", "1m")
    assert CELLS == [("XAUUSD", "30m"), ("BTCUSD", "30m")]
    assert set(NAMES) == {"supply_demand", "order_block"}
