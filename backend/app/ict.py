"""The ICT checklist, applied to one candidate, as a gate and as a ranking.

WHAT THIS IS FOR. The owner of this project trades ICT and Quarterly Theory, and
asked for the entry decision to read the whole toolkit rather than one detector.
This is that decision layer: kill zone, premium and discount, the manipulation
quarter, the POI stack, CISD, the defining range, and optionally SSMT and the
higher-timeframe bias. Each condition is switchable, each carries WHERE it came
from, and `Rules` is the whole tuning surface.

THREE SOURCES, LABELLED ON EVERY CONDITION, because a checklist whose premises
came from different places and did not say so reads as nine measurements when it
is one measurement and eight quotations:

  `measured`   the project has a number for it, in docs/CALIBRATION.md or
               docs/WALKFORWARD-MT5.md.
  `doctrine`   the sources state it and nothing here has measured it. It is
               applied because the reader follows the method, and that is a
               legitimate reason to apply a rule - it is not a legitimate reason
               to call it evidence.
  `nominated`  the caller supplied it. `deduce.py` set this precedent for the
               draw on liquidity: Zonelab refuses to infer a draw, so a human
               names it and the record says who did.

WHAT IT DOES NOT DO. It does not sum the conditions into a score. `Rules.required`
names which must be met and the rest are counted and reported, so two setups can
be ordered without anyone claiming a weight. The one time this project shipped a
weighted composite - `formation_score` - it ranked BACKWARDS, AUC 0.464 and 0.477,
and the weights were equal thirds precisely because fitting them would have been
fitting noise.

IO FREE. Every input is passed in. The kill zone comes from a clock, the quarterly
state from `conditions.at_bar`, the stack from `poi.confluence`, and SSMT from
whoever fetched the second instrument. That is what lets the measurement harness
run this 953 times without 953 provider calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .models import Zone, ZoneSide
from .poi import Confluence
from .pools import killzones_at

Source = Literal["measured", "doctrine", "nominated"]


@dataclass(frozen=True)
class Condition:
    """One clause, its verdict, where the verdict came from, and its number."""

    name: str
    met: bool | None  # None means NOT KNOWABLE here, never "no"
    source: Source
    detail: str


@dataclass
class Rules:
    """The tuning surface. Everything adjustable about the checklist is here.

    `required` is the gate. A condition named here and not met stops the trade;
    a condition NOT named here is still evaluated and still counted, so it can
    be measured before it is ever allowed to block anything. That ordering is
    the point: nothing gets promoted from reported to required without a number.

    The default `required` is EMPTY on purpose. Shipping with a full gate would
    switch on nine unmeasured filters at once and change the population every
    number in this project belongs to. The operator opts in per condition.
    """

    required: tuple[str, ...] = ()
    #: Which kill zones count as "in a kill zone". All of them by default; a
    #: reader who only trades the New York morning passes `("ny_am",)`.
    killzones: tuple[str, ...] = (
        "asia", "london", "ny_am", "london_close", "ny_pm", "silver_bullet",
    )
    #: Distinct PD array families that must stack for `poi_families` to pass.
    #: Two, because the doctrine's own example names an FVG and an order block.
    min_families: int = 2
    #: Opposite-side boxes tolerated in the same band before `poi_clean` fails.
    max_conflicts: int = 0
    #: Whether the higher-timeframe bias must agree with the zone's side.
    bias_degree: str = "bias_4h"


def evaluate(
    zone: Zone,
    state: dict[str, Any],
    stack: Confluence,
    rules: Rules | None = None,
    at: int | None = None,
    ssmt_side: str | None = None,
    draw: Literal["higher", "lower", "unnominated"] = "unnominated",
) -> list[Condition]:
    """The checklist for one candidate, in a fixed order.

    `state` is `conditions.at_bar` output. `stack` is `poi.confluence` output.
    `at` is the instant being judged, which is the touch bar in a measurement and
    the last bar in a live decision; it defaults to `state["at"]`.
    """
    rules = rules or Rules()
    when = int(at if at is not None else state.get("at") or 0)
    demand = zone.side is ZoneSide.DEMAND
    out: list[Condition] = []

    # ---------------------------------------------------------------- time
    zones_now = killzones_at(when)
    matched = tuple(name for name in zones_now if name in rules.killzones)
    out.append(Condition(
        "killzone", bool(matched), "doctrine",
        f"in {matched}" if matched else f"outside; clock says {zones_now or 'none'}",
    ))

    # ------------------------------------------------------- price location
    band = state.get("range_band")
    if band is None:
        out.append(Condition("discount_or_premium", None, "doctrine",
                             "no dealing range knowable at this bar"))
    else:
        # The doctrine's own rule: sell in premium, buy in discount. The
        # saturated readings count as their side rather than as unknown - price
        # above the whole range is not less premium than the top quartile.
        want = ("discount", "at_or_below_low") if demand else (
            "premium", "at_or_above_high")
        out.append(Condition(
            "discount_or_premium", band in want, "doctrine",
            f"band {band}, wanted one of {want}",
        ))

    # ------------------------------------------------------------ quarterly
    profile = state.get("amd_profile")
    in_manip = state.get("in_manipulation_quarter")
    out.append(Condition(
        "manipulation_quarter", in_manip, "doctrine",
        f"profile {profile or 'unknown'}, quarter {state.get('quarter_day')}",
    ))
    out.append(Condition(
        "manipulation_seen", state.get("manipulation_done"), "doctrine",
        "a sweep took the previous quarter's extreme inside the manipulation "
        "quarter" if state.get("manipulation_done") else
        "conjunction incomplete: either the quarter has not arrived or no sweep "
        "took the level",
    ))

    # ------------------------------------------------------------------ POI
    out.append(Condition(
        "poi_families", stack.families >= rules.min_families, "doctrine",
        f"{stack.families} of 4 families stack, wanted {rules.min_families}: "
        f"{ {k: v for k, v in stack.supports.items() if v} }",
    ))
    out.append(Condition(
        "poi_clean", stack.conflicts <= rules.max_conflicts, "doctrine",
        f"{stack.conflicts} opposite-side boxes in the band, tolerated "
        f"{rules.max_conflicts}",
    ))
    out.append(Condition(
        "cisd_in_band", stack.cisd > 0, "doctrine",
        f"{stack.cisd} CISD levels inside the box",
    ))

    # ------------------------------------------------------------------ DFR
    dfr = state.get("dfr_pos")
    if dfr is None:
        out.append(Condition("dfr_side", None, "doctrine",
                             "no defining range knowable at this bar"))
    else:
        # Above the range's own equilibrium for a supply, below it for a demand.
        # 0.5 is the range's midpoint by construction, not a fitted threshold.
        ok = dfr < 0.5 if demand else dfr > 0.5
        out.append(Condition("dfr_side", ok, "doctrine",
                             f"position {dfr} in the defining range"))

    # -------------------------------------------------------------- HTF zone
    # THE DOCTRINE'S CENTRAL MULTI-TIMEFRAME CLAIM: the higher timeframe sets the
    # bias, the lower one sets the entry. `confluence.mark_nesting` stamps
    # `nested_in` when this zone sits inside a same-side zone one degree up that
    # formed earlier and is still alive, so the clause is a lookup rather than a
    # second definition of nesting.
    #
    # MEASURED AT ZERO, TWICE, and the label says so. H2 in
    # docs/CALIBRATION.md tested nesting as a direction variable: p=0.33 with the
    # sign inverted at short horizons, and reliability was already disproved on
    # 2707 zones. A reader who requires this is choosing the method over this
    # project's own number, which is a legitimate choice made with open eyes.
    out.append(Condition(
        "htf_nested", bool(zone.nested_in), "measured",
        f"nested in {list(zone.nested_in)}" if zone.nested_in else
        "no same-side zone one degree up contains this one. H2 measured nesting "
        "at p=0.33",
    ))

    # ----------------------------------------------------------------- bias
    bias = state.get(rules.bias_degree)
    if bias is None:
        out.append(Condition("bias_agrees", None, "measured",
                             f"{rules.bias_degree} not knowable here"))
    else:
        # MEASURED, AND MEASURED AT ZERO. H7 in docs/CALIBRATION.md tested exactly
        # this and the zone added nothing over the bias alone - two of three
        # detectors came out slightly negative. Reported with that label so a
        # reader who switches it on knows they are choosing doctrine over the
        # project's own number.
        want = 1 if demand else -1
        out.append(Condition(
            "bias_agrees", bias == want, "measured",
            f"{rules.bias_degree}={bias}, wanted {want}. H7 measured the zone's "
            "contribution over bias at zero",
        ))

    # ----------------------------------------------------------------- SSMT
    if ssmt_side is None:
        out.append(Condition("ssmt", None, "measured",
                             "no partner series supplied to this call"))
    else:
        want_side = "low" if demand else "high"
        out.append(Condition(
            "ssmt", ssmt_side == want_side, "measured",
            f"newest knowable divergence on the {ssmt_side} side, wanted "
            f"{want_side}. Nothing connects a divergence to an outcome",
        ))

    # ------------------------------------------------- draw on liquidity
    if draw == "unnominated":
        out.append(Condition("draw_agrees", None, "nominated",
                             "no draw nominated; Zonelab does not infer one"))
    else:
        out.append(Condition(
            "draw_agrees", draw == ("higher" if demand else "lower"), "nominated",
            f"caller nominated draw={draw}",
        ))

    return out


@dataclass
class Setup:
    """The checklist plus the two numbers a caller acts on."""

    conditions: list[Condition] = field(default_factory=list)

    @property
    def met(self) -> int:
        """Conditions that passed. `None` is not a pass."""
        return sum(1 for c in self.conditions if c.met is True)

    @property
    def unknown(self) -> int:
        return sum(1 for c in self.conditions if c.met is None)

    def failed_required(self, rules: Rules) -> list[str]:
        """Required conditions that did not pass, naming each one.

        A required condition that is UNKNOWN counts as failed. Silence cannot
        pass as assent - the same rule `bias.alignment` applies to a Daily with
        no usable bias.
        """
        by_name = {c.name: c for c in self.conditions}
        return [
            name for name in rules.required
            if name not in by_name or by_name[name].met is not True
        ]

    def why(self) -> list[str]:
        """One line per condition, for the journal. Numbers included."""
        return [
            f"{c.name}: {'yes' if c.met else 'no' if c.met is False else 'unknown'}"
            f" [{c.source}] {c.detail}"
            for c in self.conditions
        ]


def setup(*args, **kwargs) -> Setup:
    """`evaluate` wrapped in the object callers actually want."""
    return Setup(conditions=evaluate(*args, **kwargs))
