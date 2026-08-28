"""Full Cycle Ladder - which timeframe reads, which executes, which enters.

THE SOURCE, quoted exactly, and it is four lines rather than a diagram. From
`Referensi grup dan Bg Nas/Discord/Buku=Pegangan.txt`, repeated almost word for
word in `Whatsapp/chat.md` on 10 August 2026:

    Monthly key levels will produce weekly expansions
    Weekly key levels will produce daily expansions.
    Daily key levels will produce 4hr expansions
    4hr pd arrays will produce 15min expansions.

RESOLVED 27 AUGUST 2026, and the earlier note in this file was right to refuse.
It said the table did not match the rule above it and that nothing in the file
could settle which was wrong, because the source was a practitioner quote nobody
had. The quote is now in the repo, and it settles it in two ways at once:

  1. EVERY STEP IS ONE STEP. The old docstring said the execution chart sits
     "2 steps below the read chart". That is not in the source. Monthly to
     weekly, weekly to daily, daily to 4hr, 4hr to 15min - four rows, one step
     each.
  2. THE LADDER HAS FIVE RUNGS, NOT SEVEN. The old comment claimed the rungs
     were `1w -> 1d -> 4h -> 1h -> 15m -> 5m -> 1m`, and it is that invented
     ladder that made a second step necessary: with `1h` inserted between `4h`
     and `15m`, one step from 4h lands on 1h and the source says it lands on
     15min. The source never names 1h, 5m or 1m as a rung.

So the two disagreed because the rungs were wrong, and the rule was patched to
compensate. With the source's own rungs, the rule needs no patch.

WHAT THE SOURCE DOES NOT SAY, stated rather than extrapolated. It stops at
15min: there is no rung below it, so the `4h` cycle has no micro entry here and
`micro_tf` is None rather than a guessed `5m`. And `1h` is not a cycle in this
ladder at all - it was in the old table and is gone, because putting it back
would reintroduce the exact rung that broke the arithmetic.

THE MONTHLY READ CHART IS NOT FETCHABLE, and that is a fact about the engine
rather than about the doctrine. `providers.base.INTERVALS` runs 1m to 1w, so a
monthly candle cannot be requested. The row is kept with its true rung name
because the doctrine has it, and `for_cycle` reports it as unavailable instead
of silently substituting 1w.

STILL NOT WIRED. `for_cycle` has no caller. What changed is that the table is now
the source's table, so wiring it no longer means shipping a guess.

    Route A (Model 3/4/5): SSMT -> tCISD
    Route B (Late Entry):  SSMT -> tCISD -> PSP -> TOB

The engine must lock the narrative on the read chart before scanning the
execution chart for the trigger, and the two routes never mix.
"""

from __future__ import annotations

from dataclasses import dataclass

from .providers.base import INTERVALS

#: The rungs the source names, coarsest first. FIVE, and the count is the whole
#: correction: `1h`, `5m` and `1m` are real intervals and are not rungs of this
#: ladder. `1M` is a rung with no interval behind it, see the module docstring.
SOURCE_RUNGS: tuple[str, ...] = ("1M", "1w", "1d", "4h", "15m")

#: Cycle name to the rung it reads from. The names are the ones the practitioner
#: uses when he says "Q2 monthly cycle" or "daily cycle".
CYCLE_RUNG: dict[str, str] = {
    "monthly": "1M",
    "weekly": "1w",
    "daily": "1d",
    "4h": "4h",
}

#: cycle -> (read_tf, execution_tf, micro_tf). DERIVED from the four lines above
#: rather than written out, so the one-step rule cannot drift away from the rungs
#: the way it did before. `micro_tf` is None where the source has no rung left.
LADDER: dict[str, tuple[str, str, str | None]] = {}
for _cycle, _rung in CYCLE_RUNG.items():
    _i = SOURCE_RUNGS.index(_rung)
    LADDER[_cycle] = (
        SOURCE_RUNGS[_i],
        SOURCE_RUNGS[_i + 1],
        SOURCE_RUNGS[_i + 2] if _i + 2 < len(SOURCE_RUNGS) else None,
    )

#: The two execution routes. The engine logs which route is taken and NEVER
#: mixes them. Route A is the direct path; Route B requires a PSP.
ROUTE_A = "SSMT -> tCISD"
ROUTE_B = "SSMT -> tCISD -> PSP -> TOB"


@dataclass(frozen=True)
class CycleLadder:
    """The timeframes for one cycle, and which route is active.

    `unavailable` names the rungs this engine cannot fetch, so a caller reads the
    gap instead of discovering it when a request 502s. Empty for every cycle
    except `monthly`, which reads a monthly candle no provider here serves.
    """

    cycle: str
    read_tf: str
    execution_tf: str
    micro_tf: str | None
    route: str
    route_desc: str
    unavailable: tuple[str, ...]


def for_cycle(cycle: str, has_psp: bool = False) -> CycleLadder | None:
    """The ladder for a given cycle name, or None when it is not a cycle here.

    `cycle` is one of 'monthly', 'weekly', 'daily', '4h'. `has_psp` is True once
    a PSP has been detected, which activates Route B.
    """
    if cycle not in LADDER:
        return None
    read_tf, exec_tf, micro_tf = LADDER[cycle]
    rungs = [tf for tf in (read_tf, exec_tf, micro_tf) if tf is not None]
    return CycleLadder(
        cycle=cycle,
        read_tf=read_tf,
        execution_tf=exec_tf,
        micro_tf=micro_tf,
        route=ROUTE_B if has_psp else ROUTE_A,
        route_desc=(
            "Late entry: SSMT -> tCISD -> PSP -> TOB"
            if has_psp
            else "Direct: SSMT -> tCISD"
        ),
        unavailable=tuple(tf for tf in rungs if tf not in INTERVALS),
    )
