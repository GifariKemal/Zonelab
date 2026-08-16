"""The trade plan is arithmetic on validated geometry, so it gets arithmetic tests.

What is worth testing here is not that a subtraction works. It is the handful of
places where a plan could quietly lie: charging the spread on one leg instead of
both, inventing a target when there is no wall, or presenting a cohort rate in a
way that reads as a forecast.
"""

from __future__ import annotations

import pytest

from app.models import (
    Anatomy,
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
