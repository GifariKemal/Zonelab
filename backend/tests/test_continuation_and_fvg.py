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


# ----------------------------------------------------- shelf_conditioned

def test_a_seven_trade_group_is_not_a_finding():
    """`MIN_GROUP` yang menahannya, dan ia BENAR-BENAR harus menahan.

    Run pertama studi shelf memberi Welch t = +2,92 di sisi shelf, yang MELEWATI
    ambang Bonferroni 2,24. Bacaan naif akan menyebutnya lolos. n-nya 7 trade.
    Lantai n dan walk-forward yang mencegahnya jadi klaim, dan test ini yang
    menjaga keduanya tidak dilonggarkan sesudah melihat t sebesar itu.
    """
    import tools.shelf_conditioned as sh

    wf_ok = {"graded": sh.FOLDS, "positive": sh.FOLDS}
    seven = {"welch_t": 2.92, "n_on": 7, "n_off": 3489, "difference": 0.73}
    assert sh.judge(seven, wf_ok)[0] is False
    assert sh.MIN_GROUP == 30
    # Dan dengan n yang cukup, t yang sama HARUS lolos, atau yang menahannya
    # bukan n melainkan sesuatu yang lain.
    assert sh.judge({**seven, "n_on": 30}, wf_ok)[0] is True


def test_the_shelf_test_is_two_sided():
    """Bacaan klasik dan bacaan ICT memprediksi tanda berlawanan.

    Support yang memantul lawan equal-low yang disapu. Kalau penghakimannya satu
    arah, salah satu dari dua bacaan itu tidak bisa dinyatakan, dan yang
    terjadi di CISD adalah tanda TERBALIK yang menang.
    """
    import tools.shelf_conditioned as sh

    strong_neg = {"welch_t": -6.0, "n_on": 100, "n_off": 100, "difference": -0.2}
    ok, kalimat = sh.judge(strong_neg, {"graded": sh.FOLDS, "positive": 0})
    assert ok is True
    assert "lebih BURUK" in kalimat, kalimat


def test_the_setting_came_from_a_census_that_never_saw_an_outcome():
    """`SWING_N` dipilih dari jumlah shelf, bukan dari hasil.

    Itu perencanaan daya, bukan p-hacking, dan bedanya bisa diperiksa: `census`
    hanya menghitung shelf dan tidak pernah menyentuh R. Kalau suatu saat ia
    membaca outcome, pemilihannya berhenti sah dan test ini yang menangkapnya.
    """
    import inspect

    import tools.shelf_conditioned as sh

    src = inspect.getsource(sh.census)
    for forbidden in ("cell_rows", '"r"', "resolved", "exp_r"):
        assert forbidden not in src, f"census menyentuh outcome lewat {forbidden}"
    assert sh.SWING_N == 10 and sh.MIN_TOUCHES == 2


def test_both_shelf_arms_exist_and_the_degenerate_one_is_labelled():
    """Versi bar-sentuhan disimpan sebagai BACAAN, bukan dihapus.

    Ia gugur karena nyaris tautologi: shelf-nya di dalam band zona, jadi harga
    yang menyentuh zona hampir selalu sudah menembus shelf-nya. Terurai pada
    XAUUSD 30m fvg: 1.078 zona lolos syarat knowable dan NOL yang lolos "belum
    diambil". Menyimpannya dengan label yang menyebut sebabnya lebih berguna
    daripada menghapusnya, karena definisi itu terlihat masuk akal sampai
    angkanya dilihat.
    """
    import inspect

    import tools.shelf_conditioned as sh

    assert hasattr(sh, "_on_shelf_at_birth") and hasattr(sh, "_on_shelf")
    src = inspect.getsource(sh.rows_for)
    assert '"on_shelf": _on_shelf_at_birth(' in src, src
    assert "on_shelf_at_touch" in src
    # Yang dinilai HARUS yang dipatok di kelahiran.
    judged = inspect.getsource(sh.main)
    assert 'summarise(pooled, "on_shelf")' in judged
    assert 'reading_at_touch_degenerate' in judged


# ----------------------------------------------------- entry_probability

def test_the_h2_rule_is_looser_than_the_house_standard_and_says_so():
    """DINYATAKAN, bukan diperbaiki diam-diam.

    Aturan H2 yang dipraregistrasi adalah `positif >= graded - 1`. Untuk 7 fold
    itu berarti 6 dari 7, yang uji tandanya memberi p = 0,0625 dan TIDAK
    melewati 0,05. Standar rumah di setiap studi lain di repo ini 7 dari 8, p =
    0,0352.

    `fvg` lolos aturan itu dengan skill rata-rata +0,0136 di 6 dari 7 fold. Jadi
    ia lolos aturan yang ditulis dan TIDAK lolos standar rumah, dan kedua hal
    itu harus bisa dinyatakan sekaligus. Mengetatkan aturannya sekarang, setelah
    melihat hasilnya, adalah post-hoc; yang benar mencatat jaraknya.

    Test ini mengunci aturannya apa adanya supaya ia tidak diam-diam diperlonggar
    lagi, dan mengunci bahwa 6 dari 8 tetap gagal.
    """
    import tools.entry_probability as ep

    assert ep.judge_h2({"graded": 7, "positive": 6, "mean_skill": 0.01})[0] is True
    assert ep.judge_h2({"graded": 8, "positive": 6, "mean_skill": 0.01})[0] is False
    assert ep.judge_h2({"graded": 7, "positive": 5, "mean_skill": 0.01})[0] is False
    # Skill rata-rata negatif tidak boleh lolos betapa pun banyak fold positif.
    assert ep.judge_h2({"graded": 8, "positive": 8, "mean_skill": -0.001})[0] is False


def test_the_walk_forward_never_trains_on_the_future():
    """Fold k dilatih pada fold SEBELUMNYA saja, dan base rate-nya dari train.

    Base rate yang diambil dari test adalah jawaban yang bocor, dan sebuah model
    yang dibandingkan ke jawaban akan terlihat lebih buruk daripada seharusnya.
    """
    import inspect

    import tools.entry_probability as ep

    src = inspect.getsource(ep.walk_forward_skill)
    assert 'r["pos"] < lo' in src, "train harus SEBELUM fold ini"
    assert "float(ytr.mean())" in src, "base rate harus dari train"
    assert "_standardise(xtr, xte)" in src, "skala harus dari train"


def test_the_logistic_fit_is_deterministic_and_can_learn():
    """Tanpa keacakan, dan ia harus bisa belajar sinyal jelas.

    Kalau tidak bisa, angka null di studi itu tidak bisa dibedakan dari model
    yang rusak. Dan kalau tidak deterministik, hasilnya tidak bisa direplikasi.
    """
    import numpy as np

    import tools.entry_probability as ep

    rng = np.random.default_rng(7)
    x = rng.normal(size=(600, 2))
    y = (x[:, 0] > 0).astype(np.float64)
    a = ep.fit_logistic(x, y)
    b = ep.fit_logistic(x, y)
    assert np.array_equal(a, b), "dua run harus identik sampai bit terakhir"
    assert ep.brier(ep.predict(a, x), y) < 0.10
    assert ep.selfcheck() == 0
