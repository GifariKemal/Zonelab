"""The rollover rule, and the two positions this tool must not touch.

`rollovers` is tested here rather than beside the backtest because this is the
reason it stopped being a nested function: the same arithmetic now charges a
simulated night and closes a real position, and a second copy would let those two
disagree about what a night is.
"""

from __future__ import annotations

import types

import datetime
import sys

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
    """Default 10009, karena ITU yang dibalas terminal saat sukses. Fixture ini
    dulu default 0 dan itu menyandi cacatnya: `order_check` sukses pada 0,
    `order_send` TIDAK. Lihat `execute.send_ok`."""

    def __init__(self, retcode=10009, comment="ok"):
        self.retcode, self.comment = retcode, comment


class FakeMT5:
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_REMOVE = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    #: Digit per simbol. Fixture lama tidak punya `symbol_info` sama sekali,
    #: yang cocok dengan `close` versi lama karena ia memakai default 3 mati.
    DIGITS = {"XAUUSD": 3, "EURUSD": 5, "GBPUSD": 5}

    def __init__(self, send=None, tick: FakeTick | None = FakeTick(), known=True):
        self.sent: list[dict] = []
        self._send = send or FakeSend()
        self._tick = tick
        self._known = known

    def symbol_info_tick(self, symbol):
        return self._tick

    def symbol_info(self, symbol):
        if not self._known:
            return None
        digits = self.DIGITS.get(symbol)
        return None if digits is None else types.SimpleNamespace(digits=digits)

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

    def on(self, symbol):
        """Pindahkan posisi ini ke simbol lain, supaya satu fixture melayani
        emas tiga desimal dan FX lima desimal tanpa dua kelas."""
        self.symbol = symbol
        return self


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


def test_a_close_that_answers_10009_is_closed_and_not_reported_as_failed():
    """Cacat yang sama dengan `execute.place`, dan konsekuensinya lebih buruk:
    posisi benar-benar tertutup lalu ditulis sebagai penolakan, sehingga journal
    menyatakan masih terbuka sesuatu yang sudah tidak ada."""
    mt5 = FakeMT5(send=FakeSend(retcode=10009))
    closed, why = flatten.close(mt5, Position(kind=FakeMT5.POSITION_TYPE_BUY))
    assert closed, why
    assert why == ""


def test_retcode_zero_from_a_close_is_not_success():
    mt5 = FakeMT5(send=FakeSend(retcode=0))
    closed, why = flatten.close(mt5, Position(kind=FakeMT5.POSITION_TYPE_BUY))
    assert not closed
    assert "retcode=0" in why


class FiveDigitTick:
    bid, ask = 1.0823412, 1.0824187


def test_a_five_digit_close_keeps_all_five_digits():
    """Cacat kembar dari `execute.place`, di jalur yang menutup posisi.

    `close` memakai `price_digits: int = 3` sebagai default, dan
    `tools/autotrade.py` memanggilnya TANPA argumen, jadi penutupan rollover
    otomatis membulatkan tiap simbol ke tiga desimal. Pada EURUSD itu mengirim
    1,082 untuk bid 1,08234, dan penutupan market yang harganya meleset tiga
    setengah pip di rollover adalah penutupan yang berhak ditolak broker.
    """
    mt5 = FakeMT5(tick=FiveDigitTick())
    ok, why = flatten.close(mt5, Position(kind=0).on("EURUSD"))
    assert ok, why
    assert mt5.sent[0]["price"] == 1.08234


def test_a_close_without_a_readable_symbol_refuses_rather_than_guessing():
    mt5 = FakeMT5(known=False)
    ok, why = flatten.close(mt5, Position(kind=0))
    assert not ok
    assert "digit" in why.lower(), why
    assert not mt5.sent, "tidak boleh ada order yang terkirim"


def test_the_close_carries_a_deviation_so_a_rollover_requote_still_fills():
    """Versi sebelumnya mengirim `TRADE_ACTION_DEAL` tanpa field `deviation`
    sama sekali, sementara `live_ping` menyetel 20 untuk probe market-nya.
    Penutupan rollover terjadi tepat saat spread paling lebar."""
    mt5 = FakeMT5()
    flatten.close(mt5, Position(kind=0))
    assert mt5.sent[0]["deviation"] == flatten.CLOSE_DEVIATION
    assert flatten.CLOSE_DEVIATION > 0


class FakeOrder:
    def __init__(self, ticket=7, magic=618, age=0, now=1_787_900_000):
        self.ticket, self.magic = ticket, magic
        self.time_setup = now - age


class OrdersMT5(FakeMT5):
    def __init__(self, orders=(), **kw):
        super().__init__(**kw)
        self._orders = list(orders)

    def orders_get(self, **kw):
        return self._orders


NOW = 1_787_900_000
DAY = 24 * 3600


def test_a_pending_older_than_the_window_is_found_and_a_fresh_one_is_not():
    """Tanpa ini tidak ada apa pun di jalur normal yang pernah membatalkan
    apa pun: tiap order GTC, dan `TRADE_ACTION_REMOVE` hanya ada di
    `live_ping`. Pending yang tidak pernah terisi memakan cap selamanya dan
    mengunci zonanya lewat gerbang idempotency."""
    old = FakeOrder(ticket=1, age=4 * DAY, now=NOW)
    fresh = FakeOrder(ticket=2, age=2 * 3600, now=NOW)
    mt5 = OrdersMT5(orders=[old, fresh])

    found = flatten.stale_pendings(mt5, NOW)
    assert [o.ticket for o in found] == [1]


def test_an_order_that_is_not_ours_is_never_cancelled():
    """Kepemilikan dibaca dari `magic`, bukan dari journal.

    Journal-nya lokal, gitignored, dan tidak pernah direkonsiliasi dengan
    broker, jadi ia bukan sumber yang aman untuk memutuskan order mana yang
    boleh disentuh. Order tangan di terminal yang sama harus lolos dari sapuan
    ini, dan itu jaminan yang harus dites, bukan diasumsikan.
    """
    theirs = FakeOrder(ticket=99, magic=0, age=30 * DAY, now=NOW)
    mt5 = OrdersMT5(orders=[theirs])
    assert flatten.stale_pendings(mt5, NOW) == []


def test_a_pending_with_no_setup_time_is_left_alone():
    """Umur yang tidak diketahui bukan umur nol dan bukan umur tak terhingga.
    Membatalkan berdasarkan umur yang tidak terbaca akan menghapus order yang
    baru saja dikirim."""
    mt5 = OrdersMT5(orders=[FakeOrder(ticket=3, age=0, now=0)])
    assert flatten.stale_pendings(mt5, NOW) == []


def test_cancelling_uses_the_same_success_predicate_as_closing():
    """`order_send` sukses pada 10009 atau 10008, bukan pada 0. Dua tool sudah
    pernah salah bersamaan soal ini."""
    mt5 = OrdersMT5(orders=[])
    ok, why = flatten.cancel(mt5, FakeOrder(ticket=5))
    assert ok, why
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_REMOVE
    assert mt5.sent[0]["order"] == 5

    refused = OrdersMT5(orders=[], send=FakeSend(retcode=0, comment="ok"))
    ok, why = flatten.cancel(refused, FakeOrder(ticket=5))
    assert not ok, "retcode 0 dari order_send BUKAN sukses"

# ------------------------------------------------- simbol yang diperiksa


def test_a_comma_list_is_read_as_many_symbols_and_the_venue_prefix_is_dropped():
    """`tools/execute.py --symbol` has taken a comma list for a long time and
    this one took a single name with a default of XAUUSD, so running it while the
    book held XAUUSD AND BTCUSD closed the gold and printed nothing about the
    rest, exit code zero. The prefix is dropped because the journal and the
    switch hold `mt5:XAUUSD` while `positions_get` wants the bare ticker."""
    assert flatten.wanted_symbols("XAUUSD") == ["XAUUSD"]
    assert flatten.wanted_symbols("XAUUSD,BTCUSD") == ["XAUUSD", "BTCUSD"]
    assert flatten.wanted_symbols("mt5:XAUUSD, mt5:BTCUSD") == ["XAUUSD", "BTCUSD"]
    assert flatten.wanted_symbols("XAUUSD,,  ,BTCUSD") == ["XAUUSD", "BTCUSD"]
    assert flatten.wanted_symbols("") == []


class CountingMT5(FakeMT5):
    """Mencatat simbol mana yang benar-benar ditanyakan ke terminal."""

    def __init__(self, holding: dict | None = None):
        super().__init__()
        self.asked: list[str] = []
        self.holding = holding or {}

    def positions_get(self, symbol=None):
        self.asked.append(symbol)
        return self.holding.get(symbol, [])


def test_every_requested_symbol_is_queried_even_when_the_first_holds_nothing(
        tmp_path, monkeypatch, capsys):
    """The half-fix has a specific shape: the old code returned as soon as the
    FIRST symbol had no positions, so a book whose only open trade was on the
    SECOND symbol was reported as "tidak ada posisi terbuka" and left alone."""
    monkeypatch.setattr(journal, "DIRECTORY", tmp_path / ".journal")
    held = Position(ticket=77, kind=0, at=0).on("BTCUSD")
    mt5 = CountingMT5(holding={"BTCUSD": [held]})
    monkeypatch.setattr(flatten, "_terminal",
                        lambda: ((mt5, types.SimpleNamespace(login=1, trade_mode=0)), ""))
    monkeypatch.setattr(sys, "argv", ["flatten", "--symbol", "XAUUSD,BTCUSD"])
    flatten.main()
    assert mt5.asked == ["XAUUSD", "BTCUSD"], mt5.asked
    out = capsys.readouterr().out
    assert "XAUUSD: tidak ada posisi terbuka" in out, out
    assert "ticket 77" in out, out

