"""Multi-pair scanning multiplies risk unless something stops it.

`--risk-pct 0.03` is PER TRADE. Five pairs armed at once is fifteen percent of the
account with nobody having chosen that number, and every individual order was
inside its own limit the whole time. That is the first guard.

The second is that correlated pairs are not separate bets. Measured on this feed:
gold against silver reads +0.848 on hourly log returns and +0.794 on 4h. Two
shorts across those is closer to one double-size short, and a money cap cannot see
it because it counts currency, not sameness.
"""

from __future__ import annotations

from app.models import Candle
from app.portfolio import Book, Held, admits, aligned

STEP = 3600
T0 = 1_700_000_000


def bars(prices: list[float], start: int = T0, step: int = STEP) -> list[Candle]:
    return [
        Candle(time=start + i * step, open=p, high=p * 1.001, low=p * 0.999,
               close=p, volume=1.0)
        for i, p in enumerate(prices)
    ]


def book(equity=1000.0, cap=0.06, corr=0.7, held=None) -> Book:
    return Book(equity=equity, cap_pct=cap, corr_max=corr, held=list(held or []))


# ------------------------------------------------------------------ the cap


def test_an_empty_book_admits_a_trade_inside_the_cap():
    assert admits(book(), "XAUUSD", 25.0) == (True, "")


def test_the_cap_counts_what_is_already_held():
    """The whole point. Each of these is inside a 3% per-trade budget and the
    third one breaks a 6% book."""
    b = book(held=[Held("XAUUSD", 25.0), Held("XAGUSD", 25.0)])
    ok, why = admits(b, "XPTUSD", 25.0)
    assert not ok
    assert "7.50%" in why and "6.00%" in why, why


def test_the_refusal_carries_the_arithmetic():
    ok, why = admits(book(held=[Held("XAUUSD", 55.0)]), "XAGUSD", 20.0)
    assert not ok
    assert "55.00" in why and "20.00" in why and "1,000.00" in why


def test_an_unknown_equity_refuses_rather_than_passing():
    """No equity means no cap can be applied, and no cap means the guard is
    decoration. The failure direction has to be "do not trade"."""
    ok, why = admits(Book(equity=0.0, cap_pct=0.06, corr_max=0.7), "XAUUSD", 1.0)
    assert not ok and "equity is not known" in why


def test_a_partial_book_says_so_in_the_refusal():
    """When open positions could not be read the cap is computed on part of the
    book, so the number is a floor and the text says which."""
    b = book(held=[Held("XAUUSD", 100.0)])
    b.partial = True
    ok, why = admits(b, "XAGUSD", 1.0)
    assert not ok and "FLOOR" in why


# ---------------------------------------------------------- the correlation


def rising(n: int, base: float, step: float) -> list[float]:
    return [base + i * step for i in range(n)]


def test_two_series_that_move_together_are_refused():
    """Built rather than fetched, so the threshold is what is being tested and
    not this week's market."""
    same = {"A": bars(rising(200, 100.0, 1.0)), "B": bars(rising(200, 50.0, 0.5))}
    ok, why = admits(book(equity=1e6, cap=0.9, held=[Held("B", 10.0)]), "A", 10.0,
                     same)
    assert not ok
    assert "correlation guard" in why and "paired returns" in why


def test_an_uncorrelated_series_is_admitted():
    alternating = [100.0 + (5.0 if i % 2 else -5.0) for i in range(200)]
    series = {"A": bars(rising(200, 100.0, 1.0)), "B": bars(alternating)}
    ok, _ = admits(book(equity=1e6, cap=0.9, held=[Held("B", 10.0)]), "A", 10.0,
                   series)
    assert ok


def test_the_guard_only_looks_at_pairs_actually_held():
    """A correlated series in the dict that is not in the book is not a conflict.
    Otherwise scanning a basket would refuse everything in it."""
    same = {"A": bars(rising(200, 100.0, 1.0)), "B": bars(rising(200, 50.0, 0.5))}
    ok, _ = admits(book(equity=1e6, cap=0.9), "A", 10.0, same)
    assert ok, "nothing is held, so nothing can be correlated with it"


def test_two_proportional_series_read_exactly_one():
    """`50 + 0.5i` is `0.5 x (100 + i)`, so the two series have IDENTICAL log
    returns and the coefficient is 1.0 rather than merely high. Asserted because
    the first version of the test below assumed 0.99 would admit them, and a
    threshold test built on a wrong coefficient tests nothing."""
    same = {"A": bars(rising(200, 100.0, 1.0)), "B": bars(rising(200, 50.0, 0.5))}
    ok, why = admits(book(equity=1e6, cap=0.9, corr=0.99,
                          held=[Held("B", 10.0)]), "A", 10.0, same)
    assert not ok
    assert "+1.000" in why, why


def test_the_threshold_is_a_parameter():
    """Same series, two thresholds, two verdicts. Uses the WEAKLY correlated pair,
    because a perfectly correlated one is refused at every threshold and would
    hide a broken parameter."""
    alternating = [100.0 + (5.0 if i % 2 else -5.0) for i in range(200)]
    series = {"A": bars(rising(200, 100.0, 1.0)), "B": bars(alternating)}
    held = [Held("B", 10.0)]
    assert admits(book(equity=1e6, cap=0.9, corr=0.70, held=held), "A", 10.0,
                  series)[0] is True
    assert admits(book(equity=1e6, cap=0.9, corr=0.001, held=held), "A", 10.0,
                  series)[0] is False


# -------------------------------------------------------------- alignment


def test_alignment_keeps_only_shared_bar_times():
    """`correlations` reads what it is handed and does not re-align, by its own
    docstring. Handing it two grids would compute a coefficient over bars that
    never coexisted."""
    a = bars([1.0, 2.0, 3.0, 4.0])
    b = bars([1.0, 2.0, 3.0], start=T0 + STEP)
    got = aligned({"A": a, "B": b})
    assert [c.time for c in got["A"]] == [c.time for c in got["B"]]
    assert len(got["A"]) == 3


def test_alignment_of_disjoint_series_is_empty_rather_than_wrong():
    a = bars([1.0, 2.0])
    b = bars([1.0, 2.0], start=T0 + 999 * STEP)
    assert aligned({"A": a, "B": b}) == {}


def test_one_series_needs_no_alignment():
    a = bars([1.0, 2.0])
    assert aligned({"A": a}) == {"A": a}


def test_the_daily_loss_guard_refuses_once_today_has_lost_enough():
    """Cap portofolio buta terhadap apa yang sudah HILANG, dan itu celahnya.

    `cap_pct` membatasi berapa yang SEDANG dipertaruhkan. Delapan kekalahan
    berturut dalam satu hari tidak melanggarnya sama sekali, karena setiap
    kerugian mengosongkan kembali ruang yang dipakai kerugian sebelumnya. Akun
    bisa habis pelan-pelan tanpa satu pun order melanggar satu pun gerbang yang
    ada sebelum 28 Agustus 2026.
    """
    from app.portfolio import Book, admits

    book = Book(equity=1000.0, cap_pct=0.06, corr_max=0.70,
                daily_loss_pct=0.02, realised_today=-19.0)
    ok, why = admits(book, "XAUUSD", 10.0)
    assert ok is True, why

    book.realised_today = -20.0
    ok, why = admits(book, "XAUUSD", 10.0)
    assert ok is False
    assert "daily loss guard" in why and "2.00%" in why, why


def test_an_unreadable_daily_result_refuses_rather_than_assuming_zero():
    """Tidak terbaca bukan nol, dan di sini bedanya adalah uang.

    Aturan yang sama dengan `Candle.spread` yang None ketika tak terukur, dan
    dengan `Book.partial`. Sebuah pengaman yang menganggap riwayat kosong
    berarti hari ini bersih akan melaporkan aman tepat pada hari terminal
    bermasalah, yaitu hari ia paling dibutuhkan.
    """
    from app.portfolio import Book, admits

    book = Book(equity=1000.0, cap_pct=0.06, corr_max=0.70,
                daily_loss_pct=0.02, realised_today=None)
    ok, why = admits(book, "XAUUSD", 10.0)
    assert ok is False
    assert "could not be read" in why, why


def test_the_guard_is_off_by_default_and_changes_nothing():
    """Default nol, jadi tidak ada perilaku yang bergeser tanpa diminta.

    Termasuk saat hari ini sudah rugi besar: dengan pengaman mati, satu-satunya
    yang mengikat tetap `cap_pct`, persis seperti sebelum pengaman ini ada.
    """
    from app.portfolio import Book, admits

    book = Book(equity=1000.0, cap_pct=0.06, corr_max=0.70,
                realised_today=-500.0)
    assert book.daily_loss_pct == 0.0
    ok, why = admits(book, "XAUUSD", 10.0)
    assert ok is True, why

    # Dan dengan pengaman mati, `realised_today=None` pun tidak menolak.
    book.realised_today = None
    assert admits(book, "XAUUSD", 10.0)[0] is True
