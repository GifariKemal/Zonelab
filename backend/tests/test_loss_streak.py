"""loss_streak: count consecutive losses from the most recent closed deal."""

from types import SimpleNamespace

from tools.broker import loss_streak


def _deal(profit, commission=0.0, swap=0.0, entry=1):
    return SimpleNamespace(profit=profit, commission=commission, swap=swap, entry=entry)


def _mt5(deals):
    return SimpleNamespace(history_deals_get=lambda *a: deals)


def test_none_when_mt5_is_none():
    assert loss_streak(None) is None


def test_zero_when_no_exits():
    assert loss_streak(_mt5([])) == 0


def test_zero_when_last_trade_won():
    deals = [_deal(-10), _deal(20)]
    assert loss_streak(_mt5(deals)) == 0


def test_counts_consecutive_losses_from_end():
    deals = [_deal(20), _deal(-5), _deal(-3), _deal(-1)]
    assert loss_streak(_mt5(deals)) == 3


def test_entry_deals_are_ignored():
    deals = [_deal(20, entry=0), _deal(-5), _deal(-1)]
    assert loss_streak(_mt5(deals)) == 2


def test_commission_and_swap_count():
    deals = [_deal(5, commission=-3, swap=-3)]
    assert loss_streak(_mt5(deals)) == 1


def test_none_when_terminal_raises():
    mt5 = SimpleNamespace(history_deals_get=lambda *a: (_ for _ in ()).throw(RuntimeError))
    assert loss_streak(mt5) is None
