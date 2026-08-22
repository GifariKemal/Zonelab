"""Point of interest: how many PD arrays stack at one price.

THE DOCTRINE'S OWN DEFINITION, quoted from the glossary on this machine: "a
specific price level or narrow zone that warrants active attention because
multiple PD array tools converge at the same price - an FVG overlapping an Order
Block at the OTE Fibonacci retracement". A POI is not a new object; it is a count
of the objects already drawn that sit on top of each other.

WHY IT DID NOT EXIST BEFORE. Every one of those objects has been detected here
for months and each was reported alone. `docs/BACKLOG.md` Bagian 3 names it as
missing and `docs/FIDELITY.md` says the same in different words. The parts were
all present and nothing counted them.

SAME SIDE ONLY, and that rule is inherited rather than invented: `confluence.py`
already decided it for higher-timeframe nesting - "a demand zone inside a supply
zone is a conflict, not confluence". A bearish fair value gap sitting inside a
demand zone is not three reasons to buy, it is a disagreement, and it is counted
as one: `conflicts` is its own number and is never netted off `supports`.

NOTHING HERE IS SCORED OR WEIGHTED. It returns counts and names. What a count is
worth is `tools/conditioned.py`'s question, and the answer has to come from the
953-trade population rather than from this file having an opinion.

ANTI-LOOKAHEAD IS THE CALLER'S `as_of`. An object that formed after the moment
being judged could not have been part of the reader's picture, and counting it is
reading the answer off the future. Every candidate is filtered on `time_from <=
as_of`, and the harness passes the TOUCH bar's time rather than the last bar's.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .detect import DETECTORS
from .models import Candle, ImbalanceParams, Zone

#: The four box families that can stack with a supply or demand zone. `ifvg` and
#: `breaker` are here even though H8 measured post-inversion touches at zero,
#: because this module COUNTS and does not judge - and their presence at a price
#: is a fact about the chart whatever it turns out to be worth.
FAMILIES = ("fvg", "order_block", "ifvg", "breaker")


@dataclass
class Confluence:
    """What sits on top of one zone, and what argues with it."""

    #: Same-side boxes overlapping the zone's price band, by family.
    supports: dict[str, int] = field(default_factory=dict)
    #: Opposite-side boxes in the same band. A disagreement, reported separately.
    conflicts: int = 0
    #: Named levels inside the band: CISD closes and true opens.
    cisd: int = 0
    true_opens: int = 0
    #: Distinct FAMILIES supporting, which is the doctrine's own reading of
    #: "multiple PD array tools". Three order blocks are one tool three times.
    @property
    def families(self) -> int:
        return sum(1 for count in self.supports.values() if count)

    @property
    def total_supports(self) -> int:
        return sum(self.supports.values())


def other_boxes(
    candles: list[Candle], params: ImbalanceParams | None = None
) -> dict[str, list[Zone]]:
    """Run the four imbalance families once, for every zone to be scored against.

    ONCE PER SERIES, NOT ONCE PER ZONE. `replay_lifecycle` is 72% of a full
    chart's cost and these four detectors call it thousands of times; scoring
    fourteen candidates would have paid that fourteen times over for an identical
    answer.
    """
    settings = params or ImbalanceParams(max_zones_per_side=0, show_broken=True)
    return {name: DETECTORS[name](candles, settings)[0] for name in FAMILIES}


def _overlaps(a: Zone, lo: float, hi: float) -> bool:
    """Any price overlap at all, which is what "at the same price" means here.

    Not a containment fraction. `confluence.py` demands 80% containment because
    it compares a zone against a HIGHER timeframe zone several times its height,
    where any-overlap matches nearly everything. These are same-timeframe boxes
    of comparable size, and the doctrine's claim is that they touch.
    """
    return min(a.top, hi) > max(a.bottom, lo)


def confluence(
    zone: Zone,
    others: dict[str, list[Zone]],
    as_of: int,
    born_from: int,
    born_to: int,
    cisd_levels: list[float] | None = None,
    true_open_prices: list[float] | None = None,
) -> Confluence:
    """Count what stacks on `zone` from the SAME displacement, up to `as_of`.

    `born_from` and `born_to` bracket the zone's own formation in wall clock, and
    a supporting box has to have been born inside that bracket. THAT RESTRICTION
    IS THE WHOLE DEFINITION, and it was added after measuring the version without
    it: "any same-side box overlapping this price, ever" marked 14 of 14 live
    candidates with all four families present, with conflicts running 68 against
    75 supports. A condition satisfied by every case distinguishes nothing, which
    is the same trap `confluence.py` records for any-overlap nesting.

    It is also the doctrine's actual claim. The glossary's example is "price
    displaces bullishly leaving an FVG from 4500-4510, the last bearish candle
    before the move sits at 4503-4507" - one impulse, three objects. A fair value
    gap from four months earlier that happens to sit at the same price is not
    part of that setup, it is a coincidence at a number.
    """
    lo, hi = zone.bottom, zone.top
    out = Confluence(supports={name: 0 for name in FAMILIES})
    for name, boxes in others.items():
        for box in boxes:
            if not born_from <= box.time_from <= min(born_to, as_of):
                continue
            if not _overlaps(box, lo, hi):
                continue
            if box.side is zone.side:
                out.supports[name] += 1
            else:
                out.conflicts += 1
    out.cisd = sum(1 for level in (cisd_levels or []) if lo <= level <= hi)
    out.true_opens = sum(1 for price in (true_open_prices or []) if lo <= price <= hi)
    return out
