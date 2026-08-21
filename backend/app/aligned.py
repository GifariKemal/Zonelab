"""Several symbols on ONE time grid, which is what a cross-instrument read needs.

Every other fetch path here answers "what did this instrument do". A divergence
read - gold against silver, DXY against EURUSD - asks "what did these two do AT
THE SAME MOMENT", and that question has no answer until the bars share a clock.

The failure mode this module exists to prevent is silent. Two feeds whose bar
boundaries differ by one minute, or one feed that is short a bar at 13:45,
produce a divergence that is an artefact of the clock rather than a fact about
the market, and nothing downstream can tell the two apart: the candles are real,
the prices are real, only the pairing is wrong.

So the grid is the INTERSECTION of the symbols' bar times and nothing else. No
carry-forward, no interpolation, no flat padding. A fabricated bar in one leg of
a divergence test manufactures the divergence it is then read as evidence for.

Different instruments trade different sessions and that is NOT an error to be
repaired. Gold runs a near-24-hour session with a daily break, crypto never
closes, an index keeps exchange hours. Intersection handles that correctly by
construction - the hours they do not share simply do not appear - so anyone who
later "fixes" the resulting gaps by filling them has reintroduced the exact lie
this module was written to remove. What the intersection costs is reported in
`stats` instead, so a caller can see a 500-bar request return 340 and decide.
"""

from __future__ import annotations

import asyncio

from .models import Candle
from .providers import ProviderError, get_candles

# Below this the shared grid is too short to answer anything, so returning it
# would be a handful of bars wearing the shape of a full series. Not a new
# threshold: `get_candles` already clamps any request under 50 bars up to 50, so
# 50 is the app's own declared minimum for a usable series.
MIN_GRID = 50


async def load_aligned(
    symbols: list[str],
    interval: str,
    bars: int,
    provider: str | None = None,
) -> tuple[dict[str, list[Candle]], dict[str, object]]:
    """Fetch each symbol and return only the bars all of them share.

    Returns `(series, stats)` where every list in `series` has the same length
    and the same timestamps in the same order, and `stats` carries:

        fetched:<SYMBOL>  bars the provider returned for that symbol
        kept:<SYMBOL>     bars of that symbol that survived the intersection
        grid              size of the shared grid (every `kept:` equals it)
        requested         bars the caller asked for

    `skipped` carries one message per symbol the provider could not serve, and
    the corresponding `fetched:<SYMBOL>` is absent rather than zero.

    Prices are never touched. This module aligns TIME.

    THE FIRST SYMBOL IS REQUIRED AND THE REST ARE NOT, which is a correction
    rather than an original design. `asyncio.gather` was called without
    `return_exceptions`, so ONE unavailable partner cancelled the whole read:
    asking for gold against silver, the dollar, oil, the Nasdaq, bitcoin, the yen
    AND the ten-year returned `{"drawn": 0, "error": "mt5 does not carry US10Y"}`
    - seven valid partners lost to one that this broker has no contract for, and
    the loss was total rather than partial. Every caller puts the chart's own
    symbol first and partners after it, so that is the split the signature now
    states: without the base there is nothing to compare against, and without one
    partner there are still the others.

    Raises ProviderError when the base symbol fails, when nothing is left to
    compare it with, or when the shared grid is shorter than `MIN_GRID`, with the
    per-symbol counts in the message - a cross-instrument read that quietly falls
    back to six bars is worse than one that stops.
    """
    # Duplicates would fetch the same instrument twice and then collapse into one
    # dict key anyway, so the caller's order is kept and the repeats dropped.
    wanted = list(dict.fromkeys(symbols))
    if not wanted:
        raise ProviderError("load_aligned needs at least one symbol")

    # Concurrently: five symbols fetched serially is five round trips deep on a
    # live request, and a divergence read is useless if it arrives late.
    fetched = await asyncio.gather(
        *(get_candles(symbol, interval, bars, provider) for symbol in wanted),
        return_exceptions=True,
    )

    series: dict[str, list[Candle]] = {}
    skipped: list[str] = []
    for symbol, result in zip(wanted, fetched):
        if isinstance(result, BaseException):
            if symbol == wanted[0]:
                # The base symbol is the one thing here that cannot be dropped:
                # every partner is compared against it.
                raise ProviderError(f"{symbol} is the base symbol and {result}")
            skipped.append(f"{symbol}: {result}")
            continue
        series[symbol] = result[0]

    # Only when partners were ASKED FOR and every one of them failed. A single
    # symbol is a legitimate call - the intersection of one set is itself, and
    # `tools/` uses it that way - so the condition is about losing a comparison
    # that was requested, not about the count.
    if len(wanted) > 1 and len(series) < 2:
        raise ProviderError(
            f"nothing left to compare {wanted[0]} with: " + "; ".join(skipped)
        )

    grid = set.intersection(*({c.time for c in rows} for rows in series.values()))

    # `object` rather than `float`, so the SKIPPED PARTNERS can travel as the
    # sentences they are. A count alone would tell a reader that something was
    # dropped without saying what or why, and "mt5 does not carry US10Y" is the
    # whole answer.
    stats: dict[str, object] = {
        "grid": float(len(grid)),
        "requested": float(bars),
        "skipped": skipped,
    }
    for symbol, rows in series.items():
        stats[f"fetched:{symbol}"] = float(len(rows))
        # Equal to `grid` for every symbol by construction. Reported per symbol
        # anyway, because the pair a reader needs is fetched-against-kept for
        # ONE instrument: that is the number that says which feed was short.
        stats[f"kept:{symbol}"] = float(len(grid))

    if len(grid) < MIN_GRID:
        counts = ", ".join(f"{s}={len(rows)}" for s, rows in series.items())
        raise ProviderError(
            f"{len(wanted)} symbols on {interval} share only {len(grid)} bar times "
            f"(fetched {counts}, asked for {bars}, minimum {MIN_GRID}). They are "
            f"not on a common grid; nothing was filled in to hide it."
        )

    return {s: [c for c in rows if c.time in grid] for s, rows in series.items()}, stats
