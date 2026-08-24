"""Full Cycle Ladder — dynamic timeframe routing for multi-timeframe execution.

The practitioner's rule: "Monthly key levels will produce weekly expansions.
Weekly key levels will produce daily expansions. Daily key levels will produce
4hr expansions. 4hr pd arrays will produce 15min expansions."

This module maps the selected cycle to the required timeframes for each step:
  - Read Chart (Anticipatory PSP): 1 candle per quarter of the cycle
  - Execution Chart (SSMT/tCISD): 2 steps below the read chart
  - Micro Entry (TOB): 1 step below the execution chart

For the M4 Daily Cycle:
  - Bias/Read: 6H (anticipatory PSP)
  - Execution (SSMT/tCISD): 15M
  - Micro Entry (TOB): 5M

The engine MUST lock the narrative on the Read chart before scanning the
Execution chart for the SSMT/tCISD trigger. The two routes NEVER mix:
  Route A (Model 3/4/5): SSMT → tCISD
  Route B (Late Entry): SSMT → tCISD → PSP → TOB
"""

from __future__ import annotations

from dataclasses import dataclass

#: The ladder: cycle name → (read_tf, execution_tf, micro_tf).
#:
#: The read chart is ONE candle per quarter of the cycle. The execution
#: chart is two steps below. The micro entry is one step below execution.
#:
#: Steps are the standard interval ladder: 1w → 1d → 4h → 1h → 15m → 5m → 1m
LADDER: dict[str, tuple[str, str, str]] = {
    "monthly": ("1w", "4h", "1h"),
    "weekly": ("1d", "4h", "15m"),
    "daily": ("6h", "15m", "5m"),
    "4h": ("1h", "15m", "5m"),
    "1h": ("15m", "5m", "1m"),
}

#: The two execution routes. The engine logs which route is taken and NEVER
#: mixes them. Route A is the direct path; Route B requires a PSP.
ROUTE_A = "SSMT → tCISD"
ROUTE_B = "SSMT → tCISD → PSP → TOB"


@dataclass(frozen=True)
class CycleLadder:
    """The three timeframes for one cycle, and which route is active."""

    cycle: str
    read_tf: str
    execution_tf: str
    micro_tf: str
    route: str
    route_desc: str


def for_cycle(cycle: str, has_psp: bool = False) -> CycleLadder | None:
    """The ladder for a given cycle name.

    `cycle` is one of 'monthly', 'weekly', 'daily', '4h', '1h'.
    `has_psp` is True when a PSP has been detected, which activates Route B.

    Returns None when the cycle is not in the ladder.
    """
    if cycle not in LADDER:
        return None
    read_tf, exec_tf, micro_tf = LADDER[cycle]
    route = ROUTE_B if has_psp else ROUTE_A
    desc = (
        "Late entry: SSMT → tCISD → PSP → TOB"
        if has_psp
        else "Direct: SSMT → tCISD"
    )
    return CycleLadder(
        cycle=cycle,
        read_tf=read_tf,
        execution_tf=exec_tf,
        micro_tf=micro_tf,
        route=route,
        route_desc=desc,
    )