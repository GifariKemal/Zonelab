"""Penghakiman `tools/lowtf_costed.py` harus bisa MENOLAK, dan praregistrasinya
tidak boleh bergeser tanpa ada yang tahu.

Studi ini yang menemukan populasi tradeable positif pertama di repo ini:
supply_demand +0,1125 R dan order_block +0,0858 R di atas gerbang departure 2,0
ATR pada XAUUSD dan BTCUSD 30 menit dengan biaya, keduanya lolos H1 dan H2.
Sebuah angka sebesar itu adalah alasan untuk memeriksa rig-nya lebih keras,
bukan lebih ringan.
"""

from __future__ import annotations

import math

from tools.lowtf_costed import (
    CELLS,
    DETECTORS_TESTED,
    FOLDS,
    MIN_SIGN_FOLDS,
    T_THRESHOLD,
    judge,
    selfcheck,
)

GOOD_WF = {"graded": FOLDS, "positive": FOLDS}
STRONG = {"difference": 0.5, "welch_t": 9.0, "exp_r_above": 0.2,
          "t_above_vs_zero": 9.0}


def test_the_selfcheck_runs_here_too():
    """Selfcheck-nya diikat ke gate, bukan cuma tersedia lewat flag.

    Sebuah selfcheck yang harus diingat untuk dijalankan adalah selfcheck yang
    tidak akan dijalankan.
    """
    assert selfcheck() == 0


def test_both_hypotheses_must_hold_independently():
    assert judge(STRONG, GOOD_WF)[:2] == (True, True)
    assert judge({**STRONG, "exp_r_above": -0.2}, GOOD_WF)[1] is False
    assert judge({**STRONG, "welch_t": 1.9}, GOOD_WF)[0] is False


def test_a_separating_gate_over_two_losing_sides_is_not_a_trade():
    """H1 tanpa H2 harus punya kalimatnya sendiri.

    Itu keadaan yang benar-benar terjadi di 1 jam: order_block memisahkan dengan
    t=+6,95 sementara populasi di atas gerbangnya sendiri -0,0429 R dengan
    t=-6,21. Kalau kedua keadaan itu memakai satu kalimat, laporan sesi akan
    menyebut "gerbangnya lolos" untuk populasi yang kalah.
    """
    h1, h2, kalimat = judge(
        {"difference": 0.5, "welch_t": 9.0, "exp_r_above": -0.04,
         "t_above_vs_zero": -6.2}, GOOD_WF)
    assert (h1, h2) == (True, False)
    assert "keduanya kalah" in kalimat


def test_an_unreadable_t_is_not_a_pass():
    """NaN dan None tidak boleh lewat lewat perbandingan yang kebetulan False.

    `abs(nan) > 2.5` adalah False, jadi ia sudah aman secara kebetulan. Yang
    dikunci di sini: ia aman karena diperiksa, bukan karena kebetulan.
    """
    assert judge({**STRONG, "t_above_vs_zero": float("nan")},
                 GOOD_WF)[1] is False
    assert judge({**STRONG, "t_above_vs_zero": None}, GOOD_WF)[1] is False
    assert judge({}, {})[:2] == (False, False)


def test_the_walk_forward_floor_binds_at_seven_of_eight():
    """Tujuh dari delapan, bukan enam, dan bukan delapan.

    Tujuh adalah uji tanda p = 0,0352. Menurunkannya ke enam membuat p = 0,1445
    yang bukan lagi bukti; menaikkannya ke delapan mengubah aturan yang
    dipraregistrasi setelah hasilnya dilihat, dan supply_demand justru
    mendapat 7 dari 8.
    """
    assert MIN_SIGN_FOLDS == 7
    assert judge(STRONG, {"graded": FOLDS, "positive": 7})[0] is True
    assert judge(STRONG, {"graded": FOLDS, "positive": 6})[0] is False


def test_the_preregistration_did_not_drift():
    """Praregistrasi dikunci angkanya, karena itu satu-satunya gunanya.

    Ambang Bonferroni diturunkan dari EMPAT kelompok yang dinilai: dua detektor
    kali dua hipotesis. Menambah detektor ketiga atau hipotesis ketiga tanpa
    menaikkan ambangnya adalah p-hacking, dan bentuknya di kode adalah konstanta
    yang tidak ikut berubah.
    """
    assert len(DETECTORS_TESTED) * 2 == 4
    assert math.isclose(T_THRESHOLD, 2.4977, abs_tol=5e-4), T_THRESHOLD
    # Dua sel, dan keduanya instrumen yang benar-benar ditradingkan.
    assert CELLS == [("XAUUSD", "30m"), ("BTCUSD", "30m")]
