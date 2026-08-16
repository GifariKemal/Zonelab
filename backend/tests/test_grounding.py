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
    "warnings": ["Kaki keluarnya 1.20 ATR, di BAWAH gerbang 2.0 ATR."],
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
    assert check("Kaki keluarnya cuma 1.20 ATR, di bawah gerbang 2.0.",
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
