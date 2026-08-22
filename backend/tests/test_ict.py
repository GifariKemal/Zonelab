"""The ICT checklist gates and ranks, and every clause says where it came from.

The owner trades this method and asked for the entry decision to read the whole
toolkit. That makes two things load-bearing, and both are asserted here:

  1. A REQUIRED CLAUSE THAT IS UNKNOWN COUNTS AS FAILED. Silence cannot pass as
     assent - the same rule `bias.alignment` applies to a Daily with no usable
     bias. Without it, a checklist run on a warm-up bar would place orders on
     nine unanswered questions.
  2. EVERY CLAUSE CARRIES ITS SOURCE. `measured` means this project has a number,
     `doctrine` means the sources say so and nothing here has checked, and
     `nominated` means a human supplied it. A checklist that mixed those without
     saying so reads as nine measurements when it is one and eight quotations.
"""

from __future__ import annotations

import pytest

from app import clock
from app.ict import Rules, evaluate, setup
from app.models import Anatomy, Zone, ZoneKind, ZoneSide, ZoneState
from app.poi import Confluence

#: New York 08:00, inside `ny_am` and nothing else.
NY_MORNING = clock.ny_wall(2026, 8, 21, 8, 0)


def zone(side: ZoneSide = ZoneSide.SUPPLY) -> Zone:
    kind = ZoneKind.DBD if side is ZoneSide.SUPPLY else ZoneKind.DBR
    return Zone(
        id=f"{kind.value}-1", kind=kind, side=side, state=ZoneState.FRESH,
        top=110.0, bottom=100.0,
        proximal=100.0 if side is ZoneSide.SUPPLY else 110.0,
        distal=110.0 if side is ZoneSide.SUPPLY else 100.0,
        time_from=1_700_000_000, time_to=1_700_003_600,
        formation_score=0.0, departure_atr=6.0,
        anatomy=Anatomy(leg_in_from=0, leg_in_to=1, base_run_from=1, base_from=1,
                        base_to=2, leg_out_from=3, leg_out_to=4),
    )


def state(**over) -> dict:
    base = {
        "at": NY_MORNING,
        "range_band": "premium",
        "amd_profile": "XAMD",
        "quarter_day": "Q3",
        "in_manipulation_quarter": True,
        "manipulation_done": True,
        "dfr_pos": 0.9,
        "bias_4h": -1,
    }
    base.update(over)
    return base


def stack(families: int = 2, conflicts: int = 0, cisd: int = 1) -> Confluence:
    supports = {"fvg": 0, "order_block": 0, "ifvg": 0, "breaker": 0}
    for name in list(supports)[:families]:
        supports[name] = 1
    return Confluence(supports=supports, conflicts=conflicts, cisd=cisd)


def named(conditions) -> dict:
    return {c.name: c for c in conditions}


# ------------------------------------------------------------------- the gate


def test_a_required_clause_that_is_unknown_counts_as_failed():
    """The property the whole gate rests on."""
    got = setup(zone(), state(range_band=None), stack())
    assert named(got.conditions)["discount_or_premium"].met is None
    assert got.failed_required(Rules(required=("discount_or_premium",))) == [
        "discount_or_premium"
    ]


def test_an_empty_required_tuple_blocks_nothing():
    """The shipped default. Turning on nine unmeasured filters at once would
    change the population every number in this project belongs to."""
    got = setup(zone(), state(manipulation_done=False), stack(cisd=0))
    assert got.failed_required(Rules()) == []
    assert got.met < len(got.conditions), "and it still reports the failures"


def test_a_required_clause_that_failed_is_named():
    got = setup(zone(), state(), stack(cisd=0))
    assert got.failed_required(Rules(required=("cisd_in_band",))) == ["cisd_in_band"]


def test_a_condition_that_is_not_required_still_gets_evaluated():
    """Report before block. Nothing gets promoted to required without a number,
    and it cannot get a number if it was never computed."""
    got = setup(zone(), state(), stack(cisd=0))
    assert named(got.conditions)["cisd_in_band"].met is False


# --------------------------------------------------------------- the doctrine


@pytest.mark.parametrize("side,band,want", [
    (ZoneSide.SUPPLY, "premium", True),
    (ZoneSide.SUPPLY, "discount", False),
    (ZoneSide.DEMAND, "discount", True),
    (ZoneSide.DEMAND, "premium", False),
])
def test_sell_in_premium_and_buy_in_discount(side, band, want):
    got = named(evaluate(zone(side), state(range_band=band), stack()))
    assert got["discount_or_premium"].met is want


@pytest.mark.parametrize("side,band", [
    (ZoneSide.SUPPLY, "at_or_above_high"),
    (ZoneSide.DEMAND, "at_or_below_low"),
])
def test_a_saturated_band_counts_as_its_own_side(side, band):
    """Price above the whole range is not LESS premium than the top quartile.
    Treating the clipped reading as unknown would refuse every trade in a market
    that has left its range."""
    got = named(evaluate(zone(side), state(range_band=band), stack()))
    assert got["discount_or_premium"].met is True


def test_the_killzone_set_is_a_parameter():
    """A reader who only trades the New York morning says so, and a reader who
    trades all of them says nothing. The windows themselves are approximations by
    their own source's admission."""
    morning = named(evaluate(zone(), state(), stack(), Rules(killzones=("ny_am",))))
    assert morning["killzone"].met is True
    afternoon = named(evaluate(zone(), state(), stack(), Rules(killzones=("ny_pm",))))
    assert afternoon["killzone"].met is False
    assert "ny_am" in afternoon["killzone"].detail, (
        "a refusal has to say what the clock actually read"
    )


def test_min_families_is_a_parameter():
    assert named(evaluate(zone(), state(), stack(families=2),
                          Rules(min_families=2)))["poi_families"].met is True
    assert named(evaluate(zone(), state(), stack(families=2),
                          Rules(min_families=3)))["poi_families"].met is False


def test_a_conflicting_box_fails_poi_clean_by_default():
    assert named(evaluate(zone(), state(), stack(conflicts=1)))["poi_clean"].met is False
    assert named(evaluate(zone(), state(), stack(conflicts=1),
                          Rules(max_conflicts=1)))["poi_clean"].met is True


@pytest.mark.parametrize("side,dfr,want", [
    (ZoneSide.SUPPLY, 0.9, True),
    (ZoneSide.SUPPLY, 0.1, False),
    (ZoneSide.DEMAND, 0.1, True),
    (ZoneSide.DEMAND, 0.9, False),
])
def test_the_defining_range_side(side, dfr, want):
    got = named(evaluate(zone(side), state(dfr_pos=dfr), stack()))
    assert got["dfr_side"].met is want


# ----------------------------------------------------------------- the labels


def test_every_condition_carries_a_source_and_a_detail():
    for c in evaluate(zone(), state(), stack()):
        assert c.source in ("measured", "doctrine", "nominated"), c
        assert c.detail, c.name


def test_the_bias_clause_says_it_was_measured_at_zero():
    """A reader switching this on is choosing doctrine over this project's own
    number, and the clause says so rather than letting them find out later."""
    got = named(evaluate(zone(), state(), stack()))["bias_agrees"]
    assert got.source == "measured"
    assert "H7" in got.detail


def test_ssmt_and_draw_are_unknown_until_supplied():
    got = named(evaluate(zone(), state(), stack()))
    assert got["ssmt"].met is None
    assert got["draw_agrees"].met is None
    assert got["draw_agrees"].source == "nominated"


def test_a_nominated_draw_agrees_with_the_side_it_should():
    demand = named(evaluate(zone(ZoneSide.DEMAND), state(), stack(), draw="higher"))
    assert demand["draw_agrees"].met is True
    supply = named(evaluate(zone(ZoneSide.SUPPLY), state(), stack(), draw="higher"))
    assert supply["draw_agrees"].met is False


def test_the_journal_lines_all_carry_a_number_or_a_name():
    """`why()` goes straight into the journal beside the order. A line with
    nothing checkable in it is an opinion."""
    for line in setup(zone(), state(), stack()).why():
        assert ":" in line and "[" in line, line
