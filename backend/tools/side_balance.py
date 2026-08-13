"""Does the detector find demand and supply in equal measure?

    python -m tools.side_balance

The visual audit turned up 74 demand zones against 22 supply on a rising
market. Two explanations fit that, and they call for opposite responses:

  survivorship  supply zones formed just as often but price broke them on the
                way up, and broken zones are hidden by default. Correct.
  detection bias  the detector genuinely finds fewer supply formations.
                A bug, and a serious one on a chart tool.

Turning the state filter off separates them. If the ratio collapses toward 1
once broken zones are shown, it was survivorship. If it stays lopsided, the
detector is asymmetric and the asymmetry has to be found.
"""

from __future__ import annotations

from collections import Counter

from app.detect.supply_demand import detect
from app.models import SupplyDemandParams
from tools import history

SERIES = [
    ("PAXGUSDT", "15m"),
    ("PAXGUSDT", "1h"),
    ("BTCUSDT", "15m"),
    ("BTCUSDT", "1h"),
    ("ETHUSDT", "1h"),
]


def visible(candles) -> tuple[int, int]:
    """What the chart actually shows, at shipped defaults."""
    zones, _ = detect(candles, SupplyDemandParams())
    tally = Counter(z.side.value for z in zones)
    return tally["demand"], tally["supply"]


def found(candles) -> tuple[int, int]:
    """What the detector found, before any display cap or state filter.

    Read from stats rather than from the returned list, because the returned
    list is capped per side and would report 100/100 on any long window,
    which is the answer to a different question.
    """
    _, stats = detect(candles, SupplyDemandParams())
    return int(stats["found_demand"]), int(stats["found_supply"])


def main() -> None:
    print(f"{'series':<16}{'shown on chart':>16}{'actually found':>16}   ratio D:S")
    totals = [0, 0, 0, 0]

    for symbol, interval in SERIES:
        candles = history.load(symbol, interval, 20000)
        d1, s1 = visible(candles)
        d2, s2 = found(candles)
        totals = [totals[0] + d1, totals[1] + s1, totals[2] + d2, totals[3] + s2]
        print(
            f"{symbol + '-' + interval:<16}{f'{d1}D / {s1}S':>16}{f'{d2}D / {s2}S':>16}"
            f"   {d1 / max(s1, 1):.1f} -> {d2 / max(s2, 1):.1f}"
        )

    d1, s1, d2, s2 = totals
    print(
        f"\n{'pooled':<16}{f'{d1}D / {s1}S':>16}{f'{d2}D / {s2}S':>16}"
        f"   {d1 / max(s1, 1):.2f} -> {d2 / max(s2, 1):.2f}"
    )
    print(
        "\nA found ratio near 1 means the detector is symmetric and any\n"
        "imbalance on the chart is survivorship: supply formed as often, price\n"
        "simply broke it on the way up and broken zones are hidden. A found\n"
        "ratio that is itself lopsided means the detector is asymmetric, which\n"
        "would be a bug rather than a market condition."
    )


if __name__ == "__main__":
    main()
