"""Provider contract plus the interval vocabulary every provider maps into."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import Candle


class ProviderError(RuntimeError):
    """Upstream refused or returned something unusable.

    Raised with a message meant for the user, not a stack trace: a missing API
    key and a rate limit look identical from the frontend otherwise.
    """


# Canonical intervals. Providers translate these into their own dialect; the
# rest of the app only ever sees these strings.
INTERVALS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}


@runtime_checkable
class Provider(Protocol):
    name: str

    def available(self) -> bool:
        """False when the provider cannot run (no key, dependency down)."""
        ...

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        """Oldest-first candles, times in epoch seconds UTC, no duplicates."""
        ...


def normalize(rows: list[Candle], bars: int) -> list[Candle]:
    """Sort ascending, drop duplicate timestamps, keep the last `bars`.

    Duplicate bar times are common when an upstream splices a live bar onto a
    historical page. Two candles on one timestamp would make the chart throw and
    would double-count inside the detector, so they are collapsed here once
    rather than defended against everywhere downstream.
    """
    by_time: dict[int, Candle] = {}
    for row in rows:
        by_time[row.time] = row
    ordered = [by_time[t] for t in sorted(by_time)]
    return ordered[-bars:]
