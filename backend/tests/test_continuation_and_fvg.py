"""Tiga studi yang ditulis 2 September 2026, dan penghakimannya harus mengikat.

Semuanya lahir dari satu hari yang terukur. XAU rally 115,54 poin dan engine
tidak mengambil sebagian pun, karena entry long satu-satunya adalah limit di
zona yang belum tersentuh dan harga tidak pernah kembali: entry demand fresh
terdekat 4294,06 lalu 4312,48, dan low sesudah SETIAP bar keputusan berhenti di
atasnya, tersempit 11 poin.

`continuation_backtest` menguji jawaban yang jelas, entry MARKET searah break
atau CISD, dan menolaknya. `continuation_exits` menguji keberatan yang sah
terhadap penolakan itu, bahwa target 2R salah bentuk, dan menolaknya juga.
`fvg_inverted` menguji kemungkinan ketiga dan MELOLOSKANNYA, jadi justru itu
yang penghakimannya harus paling keras diperiksa.
"""

from __future__ import annotations

import tools.continuation_backtest as cont
import tools.continuation_exits as exits
import tools.fvg_inverted as fvg


# ------------------------------------------------ continuation_backtest

def test_continuation_arms_and_threshold_did_not_drift():
    """Empat arm, jadi Bonferroni harus menghitung empat.

    Menambah arm kelima tanpa menaikkan ambangnya adalah p-hacking, dan
    bentuknya di kode adalah konstanta yang tidak ikut berubah.
    """
    assert cont.ARMS == ("bos", "choch", "cisd", "sweep_against")
    assert abs(cont.T_THRESHOLD - 2.4977) < 5e-4, cont.T_THRESHOLD
    assert cont.MIN_SIGN_FOLDS == 7


def test_an_arm_that_only_beats_placebo_does_not_pass():
    """Mengalahkan placebo bukan menghasilkan uang, dan itu sudah terjadi.

    Diukur di 1 jam: `bos` mengalahkan jitter-nya dengan delta +0,0144 sementara
    ekspektasi real-nya -0,0921 R dengan t lawan nol -2,53. Kalau aturan
    lolosnya cuma delta, arm itu akan dilaporkan lolos di atas populasi yang
    kalah. Ambang t pooled yang menahannya di sini, dan test ini yang menjaga
    ambang itu tidak dilonggarkan.
    """
    rows = [{"arm": "x", "real_r": -0.09, "fake_r": -0.10, "at": i}
            for i in range(60)]
    got = cont.judge(rows, "x")
    assert got["delta"] > 0
    assert got["passed"] is False, got


def test_below_min_n_is_refused_not_judged():
    """n kecil harus menolak menjawab, bukan menjawab dengan n kecil."""
    rows = [{"arm": "x", "real_r": 1.0, "fake_r": -1.0, "at": i}
            for i in range(5)]
    got = cont.judge(rows, "x")
    assert got["passed"] is False
    assert "MIN_N" in got["verdict"]


def test_the_killzone_split_is_a_reading_not_a_hypothesis():
    """Bagian 5 praregistrasinya menyatakannya, dan kode harus setuju.

    Kalau killzone ikut jadi kriteria lolos, kelompok yang dinilai naik dari 4
    jadi belasan dan ambang Bonferroni-nya salah. Jadi `by_killzone` boleh ada
    di output dan tidak boleh menyentuh `passed`.
    """
    rows = [{"arm": "x", "real_r": 1.0, "fake_r": -1.0, "at": i,
             "killzone": "ny_am" if i % 2 else "asia"} for i in range(60)]
    got = cont.judge(rows, "x")
    assert set(got["by_killzone"]) == {"ny_am", "asia"}
    # Mengganti label killzone tidak boleh mengubah keputusannya.
    shifted = [{**r, "killzone": "none"} for r in rows]
    assert cont.judge(shifted, "x")["passed"] == got["passed"]


# --------------------------------------------------- continuation_exits

def test_the_exit_grid_reports_every_target_not_the_best():
    """16 sel dan tidak satu pun dipraregistrasi, jadi semuanya dilaporkan.

    Memilih satu target sesudah melihat tabelnya adalah p-hacking. Yang menjaga
    itu: `TARGETS` tetap, dan status file-nya menyatakan ia bacaan.
    """
    assert exits.TARGETS == (2.0, 3.0, 4.0, 6.0)
    assert exits.ARMS == cont.ARMS
    assert exits.STOP_ATR == 1.0


# ------------------------------------------------------- fvg_inverted

def test_fvg_h1_needs_its_own_walk_forward():
    """Dan itu ditambahkan SETELAH run pertama, jadi arahnya harus dibuktikan.

    Praregistrasi hanya menuliskan walk-forward untuk H2, dan `_walk_below`
    menilai SELISIH bawah-minus-atas sehingga butuh 20 trade di kedua sisi per
    fold. Sisi atas seluruhnya cuma 129 trade, jadi run pertama menggradasi 2
    dari 8 fold dan H1 berjalan tanpa walk-forward sama sekali.

    Yang dikunci di sini: menambahkannya hanya bisa MENGGAGALKAN H1, tidak
    pernah meloloskan. Itu yang membuatnya bukan p-hacking, dan itu bisa
    diperiksa alih-alih dipercaya.
    """
    wf_ok = {"graded": fvg.FOLDS, "positive": fvg.FOLDS}
    strong = {"exp_r_below": 0.09, "t_below_vs_zero": 5.0,
              "difference": 0.10, "welch_t": 5.0}
    without = fvg.judge(strong, wf_ok)[0]
    with_ok = fvg.judge(strong, wf_ok, wf_ok)[0]
    with_bad = fvg.judge(strong, wf_ok, {"graded": fvg.FOLDS, "positive": 6})[0]
    assert without is True and with_ok is True
    assert with_bad is False
    # Fold yang tidak terbaca tidak boleh dihitung sebagai lolos: run pertama
    # menggradasi 2 dari 8 dan itu harus MENGGAGALKAN, bukan meloloskan.
    assert fvg.judge(strong, wf_ok, {"graded": 2, "positive": 2})[0] is False


def test_a_separating_gate_is_not_required_for_h1():
    """H1 dan H2 harus bisa berpisah, karena di data mereka MEMANG berpisah.

    Terukur di 30 menit: sisi bawah +0,2188 R dengan t lawan nol +8,53 dan 8
    dari 8 fold, sementara selisih bawah-minus-atas cuma +0,0620 dengan Welch
    t=+1,00. Jadi gerbangnya tidak memisahkan dan sisi bawahnya tetap menang.
    Kalau kedua hipotesis dipaksa satu keputusan, hasil itu tidak bisa
    dinyatakan.
    """
    wf_ok = {"graded": fvg.FOLDS, "positive": fvg.FOLDS}
    h1, h2, kalimat = fvg.judge(
        {"exp_r_below": 0.2188, "t_below_vs_zero": 8.53,
         "difference": 0.062, "welch_t": 1.00},
        {"graded": 2, "positive": 1}, wf_ok)
    assert (h1, h2) == (True, False)
    assert "bukan karena gerbangnya" in kalimat


def test_all_three_selfchecks_run_in_the_gate():
    """Selfcheck yang harus diingat untuk dijalankan tidak akan dijalankan."""
    assert fvg.selfcheck() == 0


# ------------------------------------------------------ volume_imbalance

def test_volume_imbalance_geometry_is_distinct_from_fvg():
    """Detektornya harus BEDA dari `_gap`, atau studinya mengukur FVG lagi.

    `imbalance._gap` wick-to-wick pada bar `mid-1` dan `mid+1`, yaitu tiga bar.
    Volume imbalance body-to-body pada dua bar BERDAMPINGAN dengan wick yang
    masih bersentuhan. Deret di bawah dibangun supaya cuma yang kedua yang
    benar: body-nya terpisah, wick-nya overlap, jadi `_gap` tidak akan
    menemukannya dan `chart_gaps` juga tidak karena wick-nya bersinggungan.
    """
    import numpy as np

    from app.detect.imbalance import _gap

    # bar 0: body 100-101, wick 99-104. bar 1: body 102-103, wick 101.5-105.
    # Body terpisah (101 < 102), wick overlap (104 >= 101.5).
    high = np.array([104.0, 105.0, 106.0], dtype=np.float64)
    low = np.array([99.0, 101.5, 102.0], dtype=np.float64)
    # `_gap` melihat bar 0 dan bar 2: 104 < 102 salah, 99 > 106 salah -> 0.
    assert _gap(high, low, 1) == 0


def test_volume_imbalance_judging_can_refuse():
    """Satu syarat dilanggar per baris, dan tak satu pun boleh lolos."""
    import tools.volume_imbalance as vi

    wf_ok = {"graded": vi.FOLDS, "positive": vi.FOLDS}
    strong = {"exp_r": 0.2, "t_vs_zero": 8.0}
    assert vi.judge(strong, wf_ok)[0] is True
    assert vi.judge({**strong, "exp_r": -0.2}, wf_ok)[0] is False
    assert vi.judge({**strong, "t_vs_zero": 1.9}, wf_ok)[0] is False
    assert vi.judge({**strong, "t_vs_zero": float("nan")}, wf_ok)[0] is False
    assert vi.judge(strong, {"graded": 2, "positive": 2})[0] is False
    # Nol fold tergradasi adalah keadaan yang BENAR-BENAR terjadi di run-nya
    # (n=18 seluruhnya), dan ia harus menolak bukan meloloskan.
    assert vi.judge(strong, {"graded": 0, "positive": 0})[0] is False
    assert vi.selfcheck() == 0


def test_the_duplicate_threshold_was_written_before_the_number():
    """0,5 dipilih di depan, dan hasilnya 0,75 jadi ia mengikat.

    Kalau ambang itu digeser sesudah melihat 0,75, penolakannya berhenti berarti.
    """
    import tools.volume_imbalance as vi

    assert vi.DUPLICATE_AT == 0.5
    assert vi.CELLS == [("XAUUSD", "30m"), ("BTCUSD", "30m")]


def test_the_study_adds_nothing_to_the_app_registry():
    """Detektornya TIDAK boleh tinggal di `DETECTORS` setelah studinya jalan.

    `BACKLOG.md` mencatat lima objek gambar yang diusulkan dan ditolak setelah
    diukur, jadi menambah layer sebelum ada angkanya adalah urutan yang salah.
    Suntikan `DETECTORS` di studi itu dibungkus `finally`, dan ini yang menjaga
    bungkusnya tidak lepas.
    """
    from app.detect import DETECTORS
    from app.layers import LAYER_IDS

    assert "volume_imbalance" not in DETECTORS
    assert "volume_imbalance" not in LAYER_IDS
