"""The rollover rule, and the two positions this tool must not touch.

`rollovers` is tested here rather than beside the backtest because this is the
reason it stopped being a nested function: the same arithmetic now charges a
simulated night and closes a real position, and a second copy would let those two
disagree about what a night is.
"""

from __future__ import annotations

import datetime

from app import journal
from tools import flatten
from tools.costed import ROLLOVER_HOUR_UTC, rollovers

RULE = {"gate": "x", "exit_rule": "flat at rollover"}


def utc(y, m, d, hh=0, mm=0) -> int:
    return int(datetime.datetime(y, m, d, hh, mm, tzinfo=datetime.UTC).timestamp())


# ------------------------------------------------------------------- arithmetic


def test_no_rollover_inside_one_trading_day():
    """09:00 to 19:00 on the same date crosses nothing."""
    assert rollovers(utc(2026, 8, 21, 9), utc(2026, 8, 21, 19)) == 0


def test_the_boundary_is_the_hour_itself():
    assert ROLLOVER_HOUR_UTC == 21
    assert rollovers(utc(2026, 8, 21, 20, 59), utc(2026, 8, 21, 21, 1)) == 1


def test_a_friday_fill_reopening_on_sunday_crosses_three():
    """The case that decided the live rule. Filled Friday 11:00, and the first
    price at or after Friday's rollover is Sunday's reopen 50 hours later, by
    which time three rollover instants have passed."""
    assert rollovers(utc(2026, 8, 21, 11), utc(2026, 8, 23, 22)) == 3


def test_holding_over_a_week_counts_every_night():
    assert rollovers(utc(2026, 8, 21, 11), utc(2026, 8, 26, 20)) == 5


def test_an_exit_before_the_entry_does_not_go_negative_by_accident():
    """Not a real case, and asserted anyway: a negative night count would be
    silently subtracted from an expectancy."""
    assert rollovers(utc(2026, 8, 21, 21, 1), utc(2026, 8, 21, 20, 59)) == -1


# ---------------------------------------------------------------------- closing


class FakeTick:
    bid, ask = 4580.451, 4580.549


class FakeSend:
    def __init__(self, retcode=0, comment="ok"):
        self.retcode, self.comment = retcode, comment


class FakeMT5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1

    def __init__(self, send=None, tick: FakeTick | None = FakeTick()):
        self.sent: list[dict] = []
        self._send = send or FakeSend()
        self._tick = tick

    def symbol_info_tick(self, symbol):
        return self._tick

    def order_send(self, request):
        self.sent.append(request)
        return self._send

    def last_error(self):
        return (-1, "fake")


class Position:
    def __init__(self, ticket=1, kind=1, volume=0.01, at=0):
        self.ticket, self.type, self.volume = ticket, kind, volume
        self.symbol, self.price_open, self.profit, self.swap = "XAUUSD", 4604.221, 20.0, 0.0
        self.time = at


def test_a_short_is_closed_by_a_buy_at_the_ask():
    """The wrong side of the book here is a silent cost on every close."""
    mt5 = FakeMT5()
    done, why = flatten.close(mt5, Position(kind=1))
    assert done, why
    request = mt5.sent[0]
    assert request["type"] == FakeMT5.ORDER_TYPE_BUY
    assert request["price"] == 4580.549
    assert request["position"] == 1


def test_a_long_is_closed_by_a_sell_at_the_bid():
    mt5 = FakeMT5()
    flatten.close(mt5, Position(kind=FakeMT5.POSITION_TYPE_BUY))
    assert mt5.sent[0]["type"] == FakeMT5.ORDER_TYPE_SELL
    assert mt5.sent[0]["price"] == 4580.451


def test_a_failed_close_reports_the_retcode():
    mt5 = FakeMT5(send=FakeSend(retcode=10018, comment="Market closed"))
    done, why = flatten.close(mt5, Position())
    assert not done and "10018" in why


def test_a_missing_tick_is_a_refusal_and_not_a_guess():
    mt5 = FakeMT5(tick=None)
    done, why = flatten.close(mt5, Position())
    assert not done and "no tick" in why
    assert mt5.sent == []


# ----------------------------------------------------------------- the grounds


def test_every_ground_carries_a_number():
    for line in flatten.why_closed(3, utc(2026, 8, 21, 11)):
        assert any(ch.isdigit() for ch in line), line


# --------------------------------------------------------------- ownership rule


def test_a_position_the_journal_never_placed_is_not_ours(tmp_path, monkeypatch):
    """The refusal that keeps this tool out of somebody else's trade. A hand-made
    position on the same symbol has an exit rule this tool has no record of."""
    monkeypatch.setattr(journal, "DIRECTORY", tmp_path / ".journal")
    journal.record("placed", why=["n=1"], rule=RULE, zone_id="Z", ticket=111, at=100)
    assert [e["ticket"] for e in journal.for_ticket(111)] == [111]
    assert journal.for_ticket(222) == [], (
        "a ticket with no journal line must come back empty, which is what "
        "tools/flatten reads to decide not to touch it"
    )
