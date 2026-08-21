"""What does the staircase gate actually remove?

    python -m tools.drift_gate_impact

Four independent visual audits called the same defect most often: a run of
small candles that walks steadily in one direction, marked as a base. They also
agreed on where the line falls, reading it off the engine's own `base_drift`:
staircases 0.42 to 0.86, bases they passed 0.02 to 0.34.

Before shipping a gate on that reading, two things need checking. How many
zones does it cost, and does the surviving population still cover every
formation and both sides. A filter that quietly wipes out one formation type is
worse than the defect it fixes.
"""

from __future__ import annotations


from app.detect.supply_demand import detect
from app.models import SupplyDemandParams
from tools import history

SERIES = [("PAXGUSDT", "15m"), ("PAXGUSDT", "1h"), ("BTCUSDT", "15m"), ("ETHUSDT", "1h")]
THRESHOLDS = [1.0, 0.8, 0.7, 0.6, 0.5, 0.4]


def main() -> None:
    loaded = [(f"{s}-{tf}", history.load(s, tf, 20000)) for s, tf in SERIES]

    # Counted from the rejection tally, NOT from the returned list. The list is
    # capped per side, so when the gate removes a zone another slides into its
    # slot and the total never moves: three separate measurements in this repo
    # have been silently flattened by that cap before this one.
    print(f"{'max drift':>10}{'candidates':>12}{'gated out':>11}{'share':>8}   found D:S")

    for threshold in THRESHOLDS:
        params = SupplyDemandParams(max_base_drift=threshold)
        candidates = gated = demand = supply = 0
        for _, candles in loaded:
            _, stats = detect(candles, params)
            candidates += int(stats["candidates"])
            gated += int(stats["rejected_base_drifted"])
            demand += int(stats["found_demand"])
            supply += int(stats["found_supply"])

        print(
            f"{threshold:>10.1f}{candidates:>12}{gated:>11}{gated / max(candidates, 1):>7.1%}"
            f"   {demand}:{supply}  ratio {demand / max(supply, 1):.2f}"
        )

    print(
        "\nA threshold that skews the found demand:supply ratio is removing a\n"
        "shape rather than a defect. The shipped default is 0.6."
    )


if __name__ == "__main__":
    main()
