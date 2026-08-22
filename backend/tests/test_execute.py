"""The executor's refusals, tested without a broker anywhere near them.

Everything here is about what must NOT happen. The happy path is one line of
`order_send` and the terminal proves it; these are the four ways a well-meaning
run destroys an account or an audit trail.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.models import Anatomy, Zone, ZoneKind, ZoneSide, ZoneState
from tools import execute


class FakeCheck:
    def __init__(self, retcode=0, comment="Done"):
        self.retcode, self.comment = retcode, comment


class FakeSend:
    def __init__(self, retcode=0, order=999, comment="ok"):
        self.retcode, self.order, self.comment = retcode, order, comment


class FakeMT5:
    """Only the surface `place` touches, and it records the request it was given."""

    TRADE_ACTION_PENDING = 5
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TIME_GTC = 0
    ORDER_FILLING_RETURN = 2

    def __init__(self, check=None, send=None):
        self.sent: list[dict] = []
        self._check = check or FakeCheck()
        self._send = send or FakeSend()

    def order_check(self, request):
        self.last_checked = request
        return self._check

    def order_send(self, request):
        self.sent.append(request)
        return self._send

    def last_error(self):
        return (-1, "fake")


def zone(kind=ZoneKind.DBD, side=ZoneSide.SUPPLY, zid="DBD-1787227200") -> Zone:
    return Zone(
        id=zid, kind=kind, side=side, state=ZoneState.FRESH,
        top=4623.28, bottom=4604.31, proximal=4604.31, distal=4623.28,
        time_from=1787227200, time_to=1787299200,
        formation_score=0.0, departure_atr=6.273,
        anatomy=Anatomy(leg_in_from=0, leg_in_to=1, base_run_from=1, base_from=1,
                        base_to=2, leg_out_from=3, leg_out_to=4),
    )


class FakePlan:
    side = ZoneSide.SUPPLY
    entry, stop, target = 4604.2213, 4628.0428, 4489.5667


def test_the_order_comment_is_truncated_to_what_the_terminal_accepts():
    """MetaTrader answers `Invalid "comment" argument` for an over-long comment
    and does not mention length. Measured on the connected terminal: 31 accepted,
    32 refused."""
    mt5 = FakeMT5()
    long_id = "DBD-" + "9" * 60
    ticket, why = execute.place(mt5, zone(zid=long_id), FakePlan(), "XAUUSD", 0.01)
    assert ticket == 999, why
    assert len(mt5.sent[0]["comment"]) <= execute.COMMENT_MAX


def test_prices_are_rounded_to_the_symbol_s_digits():
    """4604.2213 is not a price this symbol can hold. Sending it unrounded is how
    a pending order lands one tick away from the line the plan named."""
    mt5 = FakeMT5()
    execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    request = mt5.sent[0]
    assert request["price"] == 4604.221
    assert request["sl"] == 4628.043
    assert request["tp"] == 4489.567


def test_a_supply_zone_becomes_a_sell_limit():
    mt5 = FakeMT5()
    execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert mt5.sent[0]["type"] == FakeMT5.ORDER_TYPE_SELL_LIMIT


def test_a_refused_order_check_never_reaches_order_send():
    """The check exists to stop the send. If a non-zero retcode still sent, the
    check would be decoration."""
    mt5 = FakeMT5(check=FakeCheck(retcode=10015, comment="Invalid price"))
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket is None
    assert "10015" in why and "Invalid price" in why
    assert mt5.sent == [], "order_send ran after order_check refused"


def test_a_failed_send_reports_the_retcode_rather_than_a_ticket():
    mt5 = FakeMT5(send=FakeSend(retcode=10018, order=0, comment="Market closed"))
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket is None
    assert "10018" in why


# ------------------------------------------------------------------ the account


def fake_module(trade_mode: int, trade_allowed: bool = True):
    """A stand-in `MetaTrader5` module, injected into sys.modules so the lazy
    import inside `_terminal` finds it."""
    account = types.SimpleNamespace(
        login=1, server="Fake", trade_mode=trade_mode, trade_allowed=trade_allowed,
        equity=1000.0,
    )
    module = types.ModuleType("MetaTrader5")
    module.initialize = lambda: True
    module.account_info = lambda: account
    module.last_error = lambda: (0, "")
    return module


@pytest.mark.parametrize("mode,name", [(1, "contest"), (2, "REAL")])
def test_only_a_demo_account_is_accepted(monkeypatch, mode, name):
    """The one refusal with no flag to override it. A contest account is not
    real money either and is still refused, because the measured population is
    the demo the numbers were checked on and 'nearly demo' is not a category."""
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_module(mode))
    terminal, why = execute._terminal()
    assert terminal is None
    assert f"trade_mode={mode}" in why and "DEMO" in why


def test_a_demo_account_with_trading_disabled_is_refused(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_module(0, trade_allowed=False))
    terminal, why = execute._terminal()
    assert terminal is None
    assert "disabled" in why


def test_a_demo_account_is_accepted(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_module(0))
    terminal, why = execute._terminal()
    assert terminal is not None and why == ""


# ------------------------------------------------------------------- the grounds


def test_every_ground_carries_a_number():
    """`why` is the record a review reads. A line with no figure in it is an
    opinion, and this file's whole claim is that the engine does not have those."""
    plan = types.SimpleNamespace(age_bars=23, age_held_rate=0.772, target=4489.5667,
                                 reward_r=4.81)
    for line in execute.grounds(zone(), plan):
        assert any(ch.isdigit() for ch in line), line


def test_the_rule_names_the_gate_and_the_exit():
    """A journal line without these two cannot explain why an answer changed
    between one month and the next."""
    assert "departure_atr >=" in execute.RULE["gate"]
    assert "rollover" in execute.RULE["exit_rule"]
    assert execute.RULE["horizon_bars"] > 0


# ------------------------------------------------------------------- the sizing


def test_a_plan_with_no_lot_size_means_nobody_checked_the_risk():
    """The hole this section closes. `plan.build` returns `placeable=True` when it
    was never given equity, because a plan that was not asked to size cannot
    refuse on size. The first version of `tools/execute.py` read that True as
    permission and sent a hardcoded 0.01 lot, so the risk gate its own docstring
    promised was decorative.

    Asserted on the plan rather than on the executor because this is the property
    that made the executor wrong: True and None arriving together.
    """
    from app.plan import build

    plan = build(zone(), 19.0, 1787299200, 3600)
    assert plan is not None
    assert plan.placeable is True, "unchanged, and that is exactly the trap"
    assert plan.lots is None, (
        "no equity was supplied, so no lot was computed - and `lots is None` is "
        "the signal the executor must read"
    )


def test_a_plan_given_equity_refuses_when_the_minimum_lot_is_too_big():
    """A 1000-unit account at 1% cannot take a 23-point stop at 0.01 lot on a
    100-ounce contract: the minimum risks 23.7 against a 10.0 budget."""
    from app.models import LotSpec
    from app.plan import build

    plan = build(zone(), 19.0, 1787299200, 3600, equity=1000.0, risk_pct=0.01,
                 lot=LotSpec())
    assert plan is not None
    assert plan.placeable is False
    assert plan.lots is None
    assert any("anggaran risiko" in w for w in plan.warnings)


def test_a_bigger_account_sizes_the_same_trade():
    """The mirror, so the refusal above is a limit and not a permanent no."""
    from app.models import LotSpec
    from app.plan import build

    plan = build(zone(), 19.0, 1787299200, 3600, equity=25_000.0, risk_pct=0.01,
                 lot=LotSpec())
    assert plan is not None
    assert plan.placeable is True
    assert plan.lots is not None and plan.lots >= 0.01
    assert plan.realised_risk_pct is not None and plan.realised_risk_pct <= 0.01, (
        "realised risk may sit under the budget but never over it"
    )
