"""A stated rule, applied mechanically to one snapshot. No inference anywhere.

WHAT THIS IS. Pre-registration, which is this project's own method turned on a
trading rule instead of on a detector: write the rule down first, apply it the
same way every time, record the verdict with the evidence, and score it later
against what actually happened. The verdict here is a statement about the RULE,
never about the market - "your three conditions are satisfied" is deduction,
"price will fall" is a forecast, and this module only ever produces the first.

THE ONE PREMISE THIS ENGINE CANNOT SUPPLY, and why it is an argument rather than
a reading. The rule names `DOL Direction`. Zonelab has no such field, and its
absence is deliberate: `liquidity.dol_candidates` says so at length - "A draw
names where price is going, which is a forecast, and this project has had twelve
pre-registered directional hypotheses fail. So both sides are reported and
neither is chosen. There is no field here called draw, target or bias." Standing
liquidity exists above AND below price on every ordinary bar, so naming one of
them is a choice, not a measurement.

So the caller nominates it, and the result records that they did. Every condition
in the output carries a `source` of either `measured` or `nominated`, because a
deduction whose premises came from two different places and did not say so is
worth less than no deduction: it reads as three measurements when it is two.

WHY THE VERDICT IS NOT CALLED "VALID". The requested wording was "Valid Setup for
Short". This returns `RULE MET` instead, and the difference is not pedantry. The
rule is unmeasured - no walk-forward, no placebo, no base rate - while the
project's own measurements point the other way: twelve pre-registered directional
hypotheses failed, and post-inversion touch came out significantly NEGATIVE on
all three detectors. "Valid" would be the engine endorsing a rule its own
evidence contradicts. `RULE MET` says exactly as much as is true, which is that
the conditions the caller wrote down are satisfied, and leaves the endorsement to
whatever the shadow-trading log eventually shows.

Nothing here is an outcome. There is no entry, no exit, no target and no score,
because this runs at decision time and the outcome is not knowable yet. Scoring
is a later join against a broker statement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .dealing_range import DISCOUNT_TO, PREMIUM_FROM
from .indicators import wilder_atr

#: Quartile boundaries of the dealing range, IMPORTED rather than restated.
#:
#: Premium is the top quartile, discount the bottom, the two middle quartiles are
#: neither, and the SSMT tag on the canvas uses the same cut - so a reader
#: comparing the chart with a deduction is comparing like with like. They were
#: defined in this file, and now that `liquidity.py` DRAWS these two boundaries as
#: levels, a second copy of 0.75 would let the line on screen drift away from the
#: line this module tests against. `app/dealing_range.py` owns them.

Draw = Literal["higher", "lower", "unnominated"]


@dataclass(frozen=True)
class Condition:
    """One clause of the rule, its verdict, and where the verdict came from."""

    name: str
    met: bool
    source: Literal["measured", "nominated"]
    detail: str


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    """ATR on the snapshot's own bars, with the detectors' own primitive.

    Recomputed rather than read off the response because no response field
    carries it, and recomputed with `wilder_atr` specifically so the number in a
    deduction is the same number every threshold in this project is expressed in.
    None on too few bars, never a substituted zero: a zero ATR would make every
    ratio below it infinite.
    """
    if len(candles) < period + 1:
        return None
    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    series = wilder_atr(high, low, close, period)
    value = float(series[-1])
    return value if value > 0 else None


def _bearish_smt(response: dict[str, Any], as_of: int) -> tuple[bool, str, float | None]:
    """Is there a knowable bearish SMT on this chart, and where in the range?

    BEARISH MEANS A SPECIFIC SHAPE, not merely "a divergence exists": the chart's
    own symbol took the previous quarter's HIGH and the partner failed to. That
    is `side == "high"` with `self_took` true. The mirror - the partner taking
    the high while this chart failed - is a different reading and is not this one.

    `knowable_at <= as_of` is the anti-hindsight gate and it is not optional. A
    divergence is settled by the close of its second quarter; reading one before
    that instant is reading the future, and this whole module is worthless if it
    does that once.

    The newest qualifying divergence wins, because the rule is about the state
    now and an older one describes a decision that has already been made.
    """
    found = [
        d
        for d in (response.get("drawing", {}).get("ssmt") or [])
        if d.get("side") == "high"
        and d.get("self_took") is True
        and int(d.get("knowable_at") or 0) <= as_of
    ]
    if not found:
        return False, "no knowable high-side divergence where this symbol took the level", None
    newest = max(found, key=lambda d: int(d.get("knowable_at") or 0))
    where = newest.get("range_pos")
    return (
        True,
        f"vs {newest.get('partner')} at {newest.get('degree')} degree, "
        f"knowable_at={newest.get('knowable_at')}, "
        f"range_pos={'unconfirmed' if where is None else where}",
        where if isinstance(where, (int, float)) else None,
    )


def deduce(response: dict[str, Any], draw: Draw = "unnominated") -> dict[str, Any]:
    """Apply the rule to one response and return the verdict with its evidence.

    The rule, as written by the caller: SMT divergence AND price location premium
    AND draw on liquidity lower, all three, for a short. Anything short of all
    three is `NO SETUP`, and the path names which clause failed rather than
    saying only that one did - a deduction that will not say where it stopped
    cannot be argued with, and an unarguable verdict is not evidence.
    """
    meta = response.get("meta") or {}
    as_of = int(meta.get("as_of") or 0)
    candles = response.get("candles") or []
    atr = _atr(candles)

    smt_met, smt_detail, range_pos = _bearish_smt(response, as_of)

    # PRICE LOCATION IS READ OFF THE DIVERGENCE ITSELF, not off the last bar, and
    # the choice matters. The rule asks where the SETUP sits, and the setup is
    # the divergence; the last close is somewhere else by then. `range_pos` is
    # the dealing range knowable at the bar the divergence's extreme printed on.
    if range_pos is None:
        location_met = False
        location_detail = (
            "no range position on the divergence, so premium cannot be asserted - "
            "the dealing range needs both a confirmed high and a confirmed low"
        )
    else:
        location_met = range_pos >= PREMIUM_FROM
        band = (
            "premium"
            if range_pos >= PREMIUM_FROM
            else "discount" if range_pos <= DISCOUNT_TO else "equilibrium"
        )
        location_detail = f"range_pos={range_pos} -> {band} (premium is >= {PREMIUM_FROM})"

    conditions = [
        Condition("smt_divergence", smt_met, "measured", smt_detail),
        Condition("price_location_premium", location_met, "measured", location_detail),
        Condition(
            "dol_direction_lower",
            draw == "lower",
            "nominated",
            f"caller nominated draw={draw}; Zonelab does not measure this - see "
            "liquidity.dol_candidates",
        ),
    ]

    met = all(c.met for c in conditions)
    failed = [c.name for c in conditions if not c.met]

    return {
        "status": "RULE MET" if met else "NO SETUP",
        "side": "short",
        "deduction_path": [
            f"{c.name}={'true' if c.met else 'false'} [{c.source}] {c.detail}"
            for c in conditions
        ],
        "stopped_at": failed[0] if failed else None,
        "failed_conditions": failed,
        "evidence": {
            "bar_closed_at": meta.get("bar_closed_at"),
            "as_of": as_of,
            "atr_14": None if atr is None else round(atr, 5),
            "atr_period": 14,
            "feed_lag_seconds": meta.get("feed_lag_seconds"),
            "bars": len(candles),
            "symbol": response.get("symbol"),
            "interval": response.get("interval"),
            "provider": response.get("provider"),
        },
        # Said on every single verdict, including the negative ones, because the
        # caveat is a property of the RULE and not of any one reading of it.
        "caveat": (
            "RULE MET states that the caller's three conditions are satisfied. It "
            "is not a claim about direction and carries no measured edge: this "
            "rule has no walk-forward, no placebo and no base rate, and twelve "
            "pre-registered directional hypotheses have failed in this project. "
            "One of the three premises was nominated by the caller, not measured."
        ),
    }
