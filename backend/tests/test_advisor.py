"""The advisor's job is to be true, so the tests check its claims, not its prose.

Wording is free to change. What is not free to change: that it never claims a
direction, that the numbers it quotes are the numbers in the objects it was
given, and that the sentence about what cannot be known is always present and
always last.
"""

from __future__ import annotations

from app.advisor import FORMATIONS, explain
from app.models import Anatomy, Zone, ZoneKind, ZoneSide, ZoneState
from app.plan import build

T0 = 1699920000
STEP = 900


def zone(**over) -> Zone:
    base = dict(
        id="z1", kind=ZoneKind.DBR, side=ZoneSide.DEMAND, state=ZoneState.FRESH,
        timeframe="15m", top=100.0, bottom=98.0, proximal=100.0, distal=98.0,
        time_from=T0, time_to=T0 + 10 * STEP, formation_score=0.5,
        departure_atr=3.0, profit_zone_rr=2.0,
        anatomy=Anatomy(leg_in_from=0, leg_in_to=1, base_run_from=2,
                        base_from=2, base_to=4, leg_out_from=5, leg_out_to=8),
    )
    base.update(over)
    return Zone(**base)


def advice_for(**over):
    z = zone(**over)
    plan = build(z, atr=1.0, now=T0 + 10 * STEP, interval_seconds=STEP,
                 spread=0.2)
    return explain(z, plan, "15m")


def test_every_formation_can_be_explained():
    """A kind with no entry would raise a KeyError in front of the user."""
    for kind in ZoneKind:
        assert kind in FORMATIONS


def test_the_last_note_is_always_what_cannot_be_known():
    for over in ({}, {"profit_zone_rr": None}, {"departure_atr": 0.5},
                 {"kind": ZoneKind.FVG}, {"side": ZoneSide.SUPPLY}):
        notes = advice_for(**over).notes
        assert "TIDAK" in notes[-1].topic
        # The ANCHOR, not the numeral. This line said "sembilan" and that is how
        # the drift survived: the count moved to twelve in 35 other files and the
        # one assertion that could have caught it was pinning the stale word.
        # `tests/test_prose_consistency.py` owns the numeral and owns it in both
        # languages; this test owns the fact that the note is present at all.
        assert "pre-registered" in notes[-1].text.lower()
        assert "hipotesis arah" in notes[-1].text.lower()


def test_it_never_tells_anyone_to_buy_or_sell():
    """The whole point. Any imperative here would be unsupported by nine tests."""
    banned = ("beli ", "jual ", "buy ", "sell ", "long ", "short ",
              "akan naik", "akan turun")
    for over in ({}, {"side": ZoneSide.SUPPLY}, {"kind": ZoneKind.OB}):
        text = " ".join(n.text.lower() for n in advice_for(**over).notes)
        for word in banned:
            assert word not in text, f"advisor said {word!r}"


def test_it_quotes_the_gate_the_zone_is_actually_on_the_right_side_of():
    # S&D zone (DBR default): floor gate at 2.0 ATR
    passed_sd = " ".join(n.text for n in advice_for(departure_atr=3.0).notes)
    failed_sd = " ".join(n.text for n in advice_for(departure_atr=1.0).notes)
    assert "di ATAS gerbang 2,0 ATR" in passed_sd
    assert "di BAWAH gerbang 2,0 ATR" in failed_sd
    # FVG zone: ceiling gate at 0.25 ATR
    passed_fvg = " ".join(
        n.text for n in advice_for(kind=ZoneKind.FVG, departure_atr=0.1).notes)
    failed_fvg = " ".join(
        n.text for n in advice_for(kind=ZoneKind.FVG, departure_atr=1.0).notes)
    assert "di bawah gerbang 0,25 ATR" in passed_fvg
    assert "di ATAS gerbang 0,25 ATR" in failed_fvg


def test_no_wall_ahead_is_said_rather_than_filled_in():
    text = " ".join(n.text for n in advice_for(profit_zone_rr=None).notes)
    assert "tidak ada target" in text.lower()
    assert "konvensi" in text


def test_the_prices_it_quotes_are_the_plan_s_own_prices():
    z = zone()
    plan = build(z, atr=1.0, now=T0 + 10 * STEP, interval_seconds=STEP,
                 spread=0.2)
    assert plan is not None
    text = " ".join(n.text for n in explain(z, plan, "15m").notes)
    assert f"{plan.entry:.4g}" in text
    assert f"{plan.stop:.4g}" in text


def test_every_concept_note_points_at_a_docs_section():
    """A teaching surface that teaches nothing is decoration."""
    notes = advice_for().notes
    concepts = [n for n in notes if n.topic != "Perhatian"]
    assert all(n.learn for n in concepts)


def test_it_still_explains_a_zone_with_no_plan():
    z = zone(top=98.0, bottom=98.0)  # degenerate, build() returns None
    advice = explain(z, None, "15m")
    assert len(advice.notes) >= 3
    assert "TIDAK" in advice.notes[-1].topic
