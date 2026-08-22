"""May this position be added to what is already held? Two questions, both hard.

MULTI-PAIR SCANNING MULTIPLIES RISK BY DEFAULT, and that is the whole reason this
file exists. `--risk-pct 0.03` means three percent PER TRADE, so five pairs armed
at once is fifteen percent of the account on the table with nobody having chosen
that number. A per-trade budget is not a portfolio budget and treating it as one
is how an account dies while every individual order was inside its limit.

AND CORRELATED PAIRS ARE NOT SEPARATE BETS. Measured on this machine 2026-08-21:
gold against silver reads a Pearson of 0.850 on log returns, gold against platinum
0.750. Two shorts across those is closer to one double-size short than to two
independent trades, and the risk cap above cannot see that - it counts money, not
sameness. So the correlation is read from `app/correlation.py`, the same code the
SSMT panel reports from, rather than from a hardcoded list of "metals".

WHAT IS DELIBERATELY NOT HERE. Any opinion about whether a basket is a good idea,
and any attempt to net offsetting positions. A long gold and a short silver at
0.85 correlation may be a spread trade or may be two mistakes, and nothing in this
project has measured which. Both are refused by the same rule, and the refusal
names the coefficient so the operator can override it deliberately.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .correlation import correlations
from .models import Candle


@dataclass
class Held:
    """One commitment already made, in the two terms the guards need."""

    symbol: str
    risk: float  # account currency at risk if the stop is hit


@dataclass
class Book:
    """What is committed so far, and what it refuses to add."""

    equity: float
    cap_pct: float
    corr_max: float
    held: list[Held] = field(default_factory=list)
    #: True when open broker positions could not be read, so `committed` is only
    #: what this run placed. Reported rather than hidden: a cap computed on half
    #: the book is a cap that does not bind.
    partial: bool = False

    @property
    def committed(self) -> float:
        return sum(h.risk for h in self.held)

    @property
    def symbols(self) -> list[str]:
        return sorted({h.symbol for h in self.held})


def aligned(series: dict[str, list[Candle]]) -> dict[str, list[Candle]]:
    """Trim every series to the bar times ALL of them share.

    `correlations` reads what it is handed and does not re-align, by its own
    docstring, so handing it two series on different grids would compute a
    coefficient over bars that never coexisted. The intersection is taken here,
    explicitly, rather than assumed upstream.
    """
    if len(series) < 2:
        return series
    common: set[int] | None = None
    for candles in series.values():
        times = {c.time for c in candles}
        common = times if common is None else (common & times)
    if not common:
        return {}
    return {
        symbol: [c for c in candles if c.time in common]
        for symbol, candles in series.items()
    }


def admits(
    book: Book,
    symbol: str,
    risk: float,
    series: dict[str, list[Candle]] | None = None,
) -> tuple[bool, str]:
    """Would adding this position break either guard? Returns (ok, reason).

    The reason is empty when it is allowed, and carries the arithmetic when it is
    not. It goes into the journal verbatim.
    """
    if book.equity <= 0:
        return False, "equity is not known, so no portfolio cap can be applied"

    total = book.committed + risk
    if total / book.equity > book.cap_pct:
        return False, (
            f"portfolio cap: {book.committed:,.2f} already at risk plus "
            f"{risk:,.2f} is {total / book.equity:.2%} of {book.equity:,.2f}, "
            f"over the {book.cap_pct:.2%} cap"
            + (" (open positions could not be read, so this is a FLOOR)"
               if book.partial else "")
        )

    if series and book.held:
        pairs = aligned({s: c for s, c in series.items() if c})
        if symbol in pairs:
            for reading in correlations(pairs, symbol):
                if reading.symbol not in book.symbols:
                    continue
                if reading.full is None:
                    continue
                if abs(reading.full) >= book.corr_max:
                    return False, (
                        f"correlation guard: {symbol} against "
                        f"{reading.symbol} reads {reading.full:+.3f} on "
                        f"{reading.pairs} paired returns, at or past "
                        f"{book.corr_max:+.3f}. Already holding "
                        f"{reading.symbol}, so this is closer to one larger "
                        f"position than to two"
                    )
    return True, ""
