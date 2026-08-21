"""The trade plan is arithmetic on validated geometry, so it gets arithmetic tests.

What is worth testing here is not that a subtraction works. It is the handful of
places where a plan could quietly lie: charging the spread on one leg instead of
both, inventing a target when there is no wall, or presenting a cohort rate in a
way that reads as a forecast.
"""

from __future__ import annotations

import pytest

from app.costs import BROKERS, COSTS, spec
from app.models import (
    Anatomy,
    CostSpec,
    LotSpec,
    TradePlan,
    Zone,
    ZoneKind,
    ZoneSide,
    ZoneState,
)
from app.plan import DEFAULT_STOP_BUFFER_ATR, build

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


def test_a_long_pays_the_spread_on_entry_and_again_on_the_stop():
    """A stop below a long is hit on the other side of the book from the fill.
    Charging one leg only is the commonest way a backtest beats its own market."""
    free = build(zone(), atr=1.0, now=T0 + 10 * STEP, interval_seconds=STEP)
    paid = build(zone(), atr=1.0, now=T0 + 10 * STEP, interval_seconds=STEP,
                 spread=0.5)
    assert free is not None and paid is not None

    # The stop does not move; the fill does, and the risk widens by the spread.
    assert paid.stop == pytest.approx(free.stop)
    assert paid.entry == pytest.approx(free.entry + 0.5)
    assert paid.risk_per_unit == pytest.approx(free.risk_per_unit + 0.5)
    # And the reward shrinks, because the target did not move with the fill.
    assert paid.reward_r is not None and free.reward_r is not None
    assert paid.reward_r < free.reward_r


def test_a_short_pays_it_the_other_way():
    plan = build(
        zone(side=ZoneSide.SUPPLY, proximal=98.0, distal=100.0),
        atr=1.0, now=T0 + 10 * STEP, interval_seconds=STEP, spread=0.5,
    )
    assert plan is not None
    assert plan.entry == pytest.approx(97.5)  # sold into, so filled lower
    assert plan.stop == pytest.approx(100.0 + DEFAULT_STOP_BUFFER_ATR)


def test_the_stop_sits_beyond_the_distal_not_on_it():
    """On it would be inside the noise the distal was drawn from."""
    plan = build(zone(), atr=2.0, now=T0, interval_seconds=STEP)
    assert plan is not None
    assert plan.stop == pytest.approx(98.0 - DEFAULT_STOP_BUFFER_ATR * 2.0)
    assert plan.stop < 98.0


def test_no_wall_ahead_means_no_target_rather_than_a_convention():
    plan = build(zone(profit_zone_rr=None), atr=1.0, now=T0,
                 interval_seconds=STEP)
    assert plan is not None
    assert plan.target is None
    assert plan.reward_r is None
    assert any("konvensi" in w for w in plan.warnings)


def test_direction_is_never_claimed():
    """Nine hypotheses say this field cannot be filled honestly, so it is a
    stated None rather than a missing key."""
    plan = build(zone(), atr=1.0, now=T0, interval_seconds=STEP)
    assert plan is not None
    assert plan.direction_evidence is None
    assert "direction_evidence" in TradePlan.model_fields


def test_a_zone_below_the_departure_gate_says_so_with_both_rates():
    plan = build(zone(departure_atr=1.0), atr=1.0, now=T0,
                 interval_seconds=STEP)
    assert plan is not None
    assert plan.departure_held_rate == 0.644
    assert any("di BAWAH gerbang 2.0 ATR" in w for w in plan.warnings)


def test_age_comes_from_the_interval_not_from_bar_count_guessing():
    plan = build(zone(), atr=1.0, now=T0 + 40 * STEP, interval_seconds=STEP)
    assert plan is not None
    assert plan.age_bars == 40
    assert plan.age_held_rate == 0.772  # the 10-59 band


def test_a_missing_spread_is_reported_rather_than_treated_as_zero():
    plan = build(zone(), atr=1.0, now=T0, interval_seconds=STEP)
    assert plan is not None
    assert plan.spread_charged is None
    assert any("tidak menerbitkan spread" in w for w in plan.warnings)


def test_position_size_needs_an_account_and_is_absent_without_one():
    without = build(zone(), atr=1.0, now=T0, interval_seconds=STEP)
    with_eq = build(zone(), atr=1.0, now=T0, interval_seconds=STEP,
                    equity=10_000.0, risk_pct=0.01)
    assert without is not None and with_eq is not None
    assert without.units is None
    # 1% of 10k is 100 of risk; the stop is 2.25 away, so 44.44 units.
    assert with_eq.units == pytest.approx(100.0 / with_eq.risk_per_unit, rel=1e-6)


def test_a_degenerate_zone_yields_no_plan_rather_than_a_division():
    assert build(zone(top=98.0, bottom=98.0), atr=1.0, now=T0,
                 interval_seconds=STEP) is None
    assert build(zone(), atr=0.0, now=T0, interval_seconds=STEP) is None


def lots_for(equity: float, stop_usd: float, **over) -> TradePlan:
    """A plan whose stop is exactly `stop_usd` per ounce, sized on `equity`."""
    z = zone(top=100.0 + stop_usd, bottom=100.0, proximal=100.0 + stop_usd,
             distal=100.0, **over)
    plan = build(z, atr=0.0001, now=T0, interval_seconds=STEP,
                 equity=equity, risk_pct=0.01,
                 lot=LotSpec(**over.pop("lot", {})) if "lot" in over else LotSpec())
    assert plan is not None
    return plan


def test_a_size_is_floored_to_the_step_never_rounded_up():
    """Rounding up would let realised risk exceed the budget, and a risk limit
    that rounding can breach is not a limit."""
    # 10000 at 1% is 100 of budget; a 3 USD stop is 300 per lot -> 0.333 lots.
    plan = lots_for(10_000.0, 3.0)
    assert plan.lots == pytest.approx(0.33)
    assert plan.realised_risk is not None and plan.realised_risk <= 100.0


def test_a_stop_too_wide_for_the_account_is_refused_not_clamped_up():
    """The trap this guards: clamping to the minimum lot silently risks MORE
    than asked. A small account with a wide stop simply cannot take the trade,
    and the honest answer is to say so."""
    # 500 at 1% is 5 of budget; a 20 USD stop costs 2000 per lot, so even the
    # 0.01 minimum risks 20 - four times the budget.
    plan = lots_for(500.0, 20.0)
    assert plan.placeable is False
    assert plan.lots is None
    assert any("tidak bisa mengambil trade" in w for w in plan.warnings)


def test_the_placeability_threshold_is_equity_times_risk_against_the_stop():
    """With min lot 0.01 and 100 units per lot, the trade is placeable roughly
    when the risk budget reaches the stop distance in price units.

    Only roughly: the stop sits BEYOND the distal by the ATR buffer, so the real
    risk is a shade wider than the raw zone height and the boundary sits just
    above the tidy arithmetic. Asserting the tidy number would be asserting a
    formula rather than the behaviour."""
    assert lots_for(520.0, 5.0).placeable is True     # budget 5.20 over ~5.00
    assert lots_for(480.0, 5.0).placeable is False    # budget 4.80 under it


def test_realised_risk_is_reported_when_it_diverges_from_the_budget():
    """One step is a big slice of a small account, so nominal and realised part
    company exactly where the user can least afford the difference."""
    plan = lots_for(1_000.0, 7.0)  # budget 10, per lot 700 -> 0.014 -> 0.01
    assert plan.lots == pytest.approx(0.01)
    assert plan.realised_risk == pytest.approx(7.0)
    assert plan.realised_risk_pct == pytest.approx(0.007)
    assert any("risiko sebenarnya" in w for w in plan.warnings)


def test_commission_is_charged_on_both_sides_at_open_and_shrinks_the_size():
    free = build(zone(top=105.0, bottom=100.0, proximal=105.0, distal=100.0),
                 atr=0.0001, now=T0, interval_seconds=STEP,
                 equity=1_000.0, lot=LotSpec())
    paid = build(zone(top=105.0, bottom=100.0, proximal=105.0, distal=100.0),
                 atr=0.0001, now=T0, interval_seconds=STEP,
                 equity=1_000.0, lot=LotSpec(commission_round_turn=11.0))
    assert free is not None and paid is not None
    assert paid.lots is not None and free.lots is not None
    assert paid.lots <= free.lots


def test_margin_is_computed_and_scales_with_leverage():
    tight = build(zone(top=105.0, bottom=100.0, proximal=105.0, distal=100.0),
                  atr=0.0001, now=T0, interval_seconds=STEP, equity=10_000.0,
                  lot=LotSpec(leverage=200.0))
    loose = build(zone(top=105.0, bottom=100.0, proximal=105.0, distal=100.0),
                  atr=0.0001, now=T0, interval_seconds=STEP, equity=10_000.0,
                  lot=LotSpec(leverage=2000.0))
    assert tight is not None and loose is not None
    assert tight.margin_required is not None and loose.margin_required is not None
    # Loose, because margin is reported rounded to the cent and the ratio is
    # taken between two already-rounded numbers.
    assert tight.margin_required == pytest.approx(loose.margin_required * 10, rel=0.01)


def test_no_lot_spec_means_no_lots_rather_than_an_assumed_venue():
    plan = build(zone(), atr=1.0, now=T0, interval_seconds=STEP, equity=10_000.0)
    assert plan is not None
    assert plan.lots is None and plan.placeable is True


# The costs. Until these fields existed the plan charged the SPREAD ONLY, so the
# reward on screen was the frictionless one while the project's own measurement
# said costs take 9.4% to 20.5% of R on gold - and at the upper figure the
# out-of-sample walk-forward fell from 8 of 8 slices to 4 of 8. So what is worth
# testing is not the multiplication. It is that an unmeasured cost reads as
# unmeasured, that a measured spread outranks an assumed one, and that the spread
# is still charged exactly once.


def test_an_unknown_symbol_is_charged_nothing_and_the_plan_says_so():
    """None means NOT MEASURED here, never 'measured as free'. A zero-filled
    spec would quietly reinstate the frictionless reward these fields remove."""
    assert spec("XAGUSD") is None  # silver has no researched row
    assert spec("_default") is None  # the crypto fallback is not a symbol

    plan = build(zone(), atr=1.0, now=T0, interval_seconds=STEP)
    assert plan is not None
    assert plan.cost_charged is None
    assert plan.cost_share_of_reward is None
    assert plan.carry_per_night is None
    assert any("TANPA GESEKAN" in w for w in plan.warnings)


def test_a_measured_spread_beats_the_assumed_constant():
    """The table's 1.6bp is itself a measured median, borrowed from the one feed
    that publishes both sides of the book. This bar's own book still wins."""
    gold = spec("XAUUSD")
    assert gold is not None and gold.spread_bp == 1.6

    assumed = build(zone(), atr=1.0, now=T0, interval_seconds=STEP, costs=gold)
    measured = build(zone(), atr=1.0, now=T0, interval_seconds=STEP, spread=0.5,
                     costs=gold)
    assert assumed is not None and measured is not None
    # 1.6bp of the 100.0 proximal is 0.016, and the plan names it as borrowed.
    assert assumed.spread_charged == pytest.approx(0.016)
    assert any("konstanta 1,6 bp" in w for w in assumed.warnings)
    # The feed's 0.5 replaces it rather than adding to it.
    assert measured.spread_charged == pytest.approx(0.5)
    assert measured.entry == pytest.approx(100.5)
    assert not any("konstanta" in w for w in measured.warnings)


def test_the_spread_is_charged_once_even_though_the_cost_table_also_names_it():
    """A report once claimed the spread was charged twice and the arithmetic
    refuted it: the fill rises one full spread and the stop does not move, which
    is identical to paying half a spread on each leg. `cost_charged` reports that
    same spread as a component, so it must not add a second one."""
    schedule = CostSpec(commission_bp=None, slippage_bp=None, spread_bp=None)
    free = build(zone(), atr=1.0, now=T0, interval_seconds=STEP, costs=schedule)
    paid = build(zone(), atr=1.0, now=T0, interval_seconds=STEP, spread=0.5,
                 costs=schedule)
    assert free is not None and paid is not None
    assert paid.stop == pytest.approx(free.stop)
    assert paid.entry == pytest.approx(free.entry + 0.5)
    assert paid.risk_per_unit == pytest.approx(free.risk_per_unit + 0.5)
    assert paid.cost_charged == pytest.approx(0.5)  # once, not 1.0
    # And an all-None schedule says which lines are missing rather than adding
    # them up as zeroes.
    assert any("hilang" in w for w in paid.warnings)


def test_the_plan_charges_carry_for_every_night_it_assumes():
    gold = spec("XAUUSD")
    assert gold is not None and gold.carry_bp_per_night == 1.0
    over = spec("XAUUSD").model_copy(update={"nights": 2})

    intraday = build(zone(), atr=1.0, now=T0, interval_seconds=STEP, spread=0.0,
                     costs=gold)
    held = build(zone(), atr=1.0, now=T0, interval_seconds=STEP, spread=0.0,
                 costs=over)
    assert intraday is not None and held is not None
    # 1.0bp of the 100.0 proximal, per rollover crossed.
    assert intraday.carry_per_night == pytest.approx(0.01)
    assert held.carry_per_night == pytest.approx(0.01)
    assert held.cost_charged == pytest.approx(intraday.cost_charged + 0.02)
    # nights=0 is an ASSUMPTION of an intraday hold, and a zone entry can sit
    # unfilled for days, so the plan names it and reports the per-night figure
    # even at zero nights so the reader can do the multiplication.
    assert any("MENGASUMSIKAN" in w for w in intraday.warnings)
    assert not any("MENGASUMSIKAN" in w for w in held.warnings)


def test_cost_share_of_reward_is_absent_when_there_is_no_reward_to_share():
    gold = spec("XAUUSD")
    walled = build(zone(), atr=1.0, now=T0, interval_seconds=STEP, costs=gold)
    open_road = build(zone(profit_zone_rr=None), atr=1.0, now=T0,
                      interval_seconds=STEP, costs=gold)
    assert walled is not None and open_road is not None
    assert walled.target is not None and walled.cost_charged is not None
    # 0.66bp of commission plus slippage, 1.6bp of assumed spread and one 1.0bp
    # rollover, against the 3.984 to target.
    assert walled.cost_share_of_reward == pytest.approx(
        walled.cost_charged / abs(walled.target - walled.entry), rel=1e-3
    )
    assert open_road.target is None
    assert open_road.cost_charged is not None  # the cost is still real
    assert open_road.cost_share_of_reward is None


def test_the_exness_night_fee_is_carried_rather_than_dropped():
    """4.545bp per night, verified from Exness's own Help Center: 200 USD per lot
    on a 100oz XAUUSD lot held past 21:00 UTC. It is larger than every other cost
    in the model combined, and the CostSpec field it belongs in is carry.

    THE SWAP ON TOP OF IT IS A SIDE. Read off the connected terminal on
    2026-08-20, XAUUSD: `swap_long` -541.4 points, which on a 100 ounce lot is
    -54.14 USD a night and 1.20bp at gold 4500, against `swap_short` of exactly
    zero. So a long carries 4.545 + 1.20 and a short carries 4.545 and nothing
    else. This used to be one number for both, and one number charged every
    short for a cost it never pays - an error that leans the same way the
    drawing does, because a demand zone is a long.
    """
    exness = spec("XAUUSD", broker="exness_zero")
    assert exness is not None
    assert exness.carry_bp_per_night == pytest.approx(5.745), "long: admin + swap"
    assert exness.carry_asymmetric is True

    short = spec("XAUUSD", broker="exness_zero", long_side=False)
    assert short is not None
    assert short.carry_bp_per_night == pytest.approx(4.545), "short: admin only"
    assert exness.commission_bp == 0.25
    assert "BROKERS[exness_zero]" in exness.source

    # A row nobody has read side by side must behave exactly as it did before:
    # one figure, both sides, and `carry_asymmetric` False so nothing downstream
    # implies a measurement that was never taken.
    generic_long = spec("XAUUSD")
    generic_short = spec("XAUUSD", long_side=False)
    assert generic_long is not None and generic_short is not None
    assert generic_long.carry_bp_per_night == generic_short.carry_bp_per_night
    assert generic_long.carry_asymmetric is False

    conservative = spec("XAUUSD", conservative=True)
    assert conservative is not None
    assert conservative.commission_bp == 3.0  # IBKR's published 1.5bp per side
    assert "CONSERVATIVE" in conservative.source


def test_the_product_and_the_harness_read_the_same_table():
    """The whole reason app/costs.py exists. When the table lived in
    tools/costed.py the shipped plan could not reach it, and a corrected cost
    landed in the measurement only."""
    from tools import costed

    assert costed.schedule.__module__ == "app.costs"
    assert costed.BROKERS is BROKERS
    assert spec("yahoo:XAUUSD") == spec("XAUUSD")  # the routing prefix is not a symbol
    assert spec("XAUUSD").commission_bp == COSTS["XAUUSD"]["commission_bp"]
