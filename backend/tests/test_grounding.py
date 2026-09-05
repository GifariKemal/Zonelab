"""The guardrail on the language model, so it is a guarantee and not a hope.

These tests matter more than most here. Everything else in this project is
measured; a model is the one component that can produce a confident, specific,
numeric claim with nothing behind it. The check is the only thing standing
between that and the user, so it gets tested for what it must catch AND for
what it must not reject - a check that fires on ordinary prose would be turned
off within a day, which is the same as not having one.
"""

from __future__ import annotations

from app.grounding import check, numbers_in


PAYLOAD = {
    "entry": 4377.86,
    "stop": 4377.44,
    "departure_held_rate": 0.858,
    "age_bars": 23,
    "warnings": ["Kaki keluarnya 1.20 ATR, di ATAS gerbang 0.25 ATR."],
}


def test_a_reply_that_only_repeats_the_engine_s_numbers_passes():
    reply = "Entry di 4377.86, stop di 4377.44, dan zona ini berumur 23 bar."
    assert check(reply, PAYLOAD).grounded


def test_an_invented_price_is_caught():
    """The failure that matters: a specific, plausible, unsupported number."""
    verdict = check("Target berikutnya 4402.10.", PAYLOAD)
    assert not verdict.grounded
    assert 4402.10 in verdict.unsupported


def test_an_invented_probability_is_caught():
    """A model asked about a chart will happily produce a win rate. The engine
    never computes one, so any such number is fabricated by construction."""
    verdict = check("Peluang setup ini berhasil sekitar 78%.", PAYLOAD)
    assert not verdict.grounded


def test_a_rate_stored_as_a_fraction_may_be_spoken_as_a_percentage():
    """The engine stores 0.858 and the prose says 85,8. Same fact, two
    magnitudes. A check that knew only one would reject the correct sentence."""
    assert check("Kelompok ini bertahan 85,8%.", PAYLOAD).grounded
    assert check("Kelompok ini bertahan 0.858 dari waktu.", PAYLOAD).grounded


def test_rounding_is_allowed_but_a_new_magnitude_is_not():
    assert check("Entry sekitar 4377.9.", PAYLOAD).grounded
    assert not check("Entry sekitar 4477.9.", PAYLOAD).grounded


def test_numbers_inside_warning_strings_count_as_given():
    """The warnings are engine output too. A model quoting one back is
    repeating, not inventing."""
    assert check("Kaki keluarnya cuma 1.20 ATR, di atas gerbang 0.25.",
                 PAYLOAD).grounded


def test_ordinary_small_counts_do_not_trip_it():
    """A check that fires on 'the three legs' gets switched off, and a switched
    off check protects nobody."""
    assert check("Ada 3 kaki: masuk, base, keluar. 2 garisnya tidak setara.",
                 PAYLOAD).grounded


def test_a_comma_decimal_is_never_read_as_a_thousands_separator():
    """Reading 85,8 as 858 would invent a magnitude - the precise failure this
    module exists to prevent - so the ambiguous case must resolve to decimal."""
    assert 85.8 in numbers_in("bertahan 85,8 persen")
    assert 858.0 not in numbers_in("bertahan 85,8 persen")


def test_both_conventions_survive_in_one_string():
    found = numbers_in("harga 4.377,86 dan 4377.86")
    assert any(abs(v - 4377.86) < 0.01 for v in found)


def test_the_verdict_explains_itself_rather_than_just_failing():
    """A refusal the user cannot act on is a bug report addressed to nobody."""
    verdict = check("Target 4402.10 dan peluang 78%.", PAYLOAD)
    assert not verdict.grounded
    assert "4402.1" in verdict.reason() or "4402" in verdict.reason()
    assert "may not add" in verdict.reason()


def test_a_reply_with_no_numbers_at_all_is_grounded():
    assert check("Ini zona demand pembalikan.", PAYLOAD).grounded


def test_a_price_quoted_to_every_last_digit_is_grounded():
    """Writing ALL the digits is the trivially allowed case of "fewer digits".

    Zone prices arrive as float32 widened to float64, so a faithful quote can
    carry ten decimal places. The precision rule reads at most six and reported
    zero for a longer tail, which compared the price against itself rounded to a
    whole number and rejected it. The first real chart audit came back UNUSABLE
    for quoting nine of its own payload's prices back exactly - a checker that
    fails on perfect fidelity is failing at the one thing it exists to permit.
    """
    exact = 4476.2998046875
    verdict = check(f"Tepi atasnya {exact}.", {"top": exact})

    assert verdict.grounded, verdict.reason()
    # Fewer digits, correctly rounded, still passes: that is the original rule.
    assert check("Tepi atasnya 4476.30.", {"top": exact}).grounded
    # And the guarantee it must not have traded away to get there. Two decimals
    # is the precision the panel and the price axis actually show, so this is
    # the shape an invented price really arrives in.
    assert not check("Tepi atasnya 4476.31.", {"top": exact}).grounded


def test_an_integer_is_fewer_digits_and_not_different_digits():
    """Bentuk paling sederhana dari jaminan modul ini, dan ia pernah gagal.

    `_decimals` men-split token tanpa pemisah desimal dan mengembalikan panjang
    seluruh token, jadi "125" terbaca sebagai tiga angka desimal. Akibatnya
    pembulatan ke bilangan bulat, yaitu "digit lebih sedikit" dalam bentuk
    paling dasar, ditandai sebagai angka karangan dan pembaca mendapat badge
    merah pada jawaban yang jujur.
    """
    assert check("nilainya 150", {"value": 150.4}).grounded
    assert check("harga 4378", {"entry": 4377.86}).grounded
    # Dan yang tidak boleh ikut longgar: digit yang BERBEDA tetap ditolak.
    assert not check("nilainya 151", {"value": 150.4}).grounded
    assert not check("harga 4402", {"entry": 4377.86}).grounded


def test_arithmetic_that_lands_in_the_free_set_is_a_known_hole():
    """Batas yang diakui, dipaku supaya tidak dilupakan atau dibaca sebagai jaminan.

    Prompt melarang model berhitung dan menyebut itu aturan yang paling sering
    gagal. Tidak ada penegak mekanisnya. Aritmetika tertangkap hanya kalau
    hasilnya kebetulan tidak ada di payload, dan yang hasilnya jatuh di `_FREE`
    tidak pernah tertangkap.

    Test ini SENGAJA mengasersi perilaku yang tidak diinginkan. Kalau suatu hari
    ia gagal, itu berarti seseorang menutup celahnya, dan test inilah yang harus
    dihapus - bukan penegaknya.
    """
    # 102 - 100 = 2, dan 2 ada di _FREE, jadi ia lolos.
    assert check("jarak entry ke stop 2 poin", {"entry": 102.0, "stop": 100.0}).grounded
    # Hasil yang sama sekali di luar payload tetap tertangkap, jadi celahnya
    # sempit dan bukan lubang terbuka.
    assert not check(
        "jarak entry ke stop 27.3 poin", {"entry": 127.3, "stop": 100.0}
    ).grounded
