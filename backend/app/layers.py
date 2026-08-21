"""Every drawable thing in one registry, in the order it is drawn.

WHY THIS FILE EXISTS. Before it, turning something on took two different
mechanisms depending on what it was: box detectors were named in a `detectors`
list, and each of the seven overlays carried its own `enabled` boolean inside its
own params block. Same intent, two spellings, and a UI that had to know which was
which. The registry collapses both into one list of names, and `main._build`
became a loop over it instead of a chain of thirteen `if` statements.

THE ORDER IS LOAD-BEARING and is the tuple's own order, not a sort:

- `supply_demand` runs FIRST because it owns two passes nothing else has: the
  higher-timeframe nesting, and the road-ahead filter. Both must see only its own
  zones. A fair value gap has no opposing zone and no profit zone, so sweeping it
  through the road filter would apply one method's rule to another's drawing.
- The other box detectors APPEND rather than replace. A chart showing a supply
  zone and a fair value gap at the same price is showing two different claims
  about that price, and collapsing them would hide one.
- `structure` and everything after it draw no boxes, so they cannot be capped per
  side and must never be mistaken for detectors.
- `checklist` is last and is not a drawing at all. It is the only entry that can
  make extra provider calls, so it runs where the caller can see the cost.

WHAT A LAYER IS NOT. It is not a claim that the thing works. `evidence` is a
required field precisely so that the UI cannot show a toggle without showing what
is known about it, and for most of these the honest answer is that nothing has
been measured. Twelve pre-registered directional hypotheses have failed in this
project; a menu that made every entry look equal would be the most misleading
thing on the screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LayerKind = Literal["detector", "overlay", "report"]


@dataclass(frozen=True)
class Layer:
    """One thing the engine can draw, and what is known about it."""

    id: str
    label: str
    kind: LayerKind
    #: Attribute on `DrawRequest` holding this layer's knobs. Several detectors
    #: share `imbalance` on purpose: an IFVG is an FVG plus one more event, and
    #: giving them separate gap thresholds would let the two populations drift.
    params: str
    note: str
    #: What has been MEASURED about it. "Nothing" is a valid and common answer,
    #: and saying so is the point of the field.
    evidence: str


LAYERS: tuple[Layer, ...] = (
    Layer(
        id="supply_demand",
        label="Supply and demand",
        kind="detector",
        params="supply_demand",
        note="Impulse, base, impulse. The only detector shipped on by default.",
        evidence=(
            "The departure gate is validated: 85.8% against 64.4%, p<0.0001, and "
            "8 of 8 out-of-sample folds. The edge is a FIRST-TOUCH phenomenon - "
            "on later touches it is -0.2 to -4.3 points - and the headline is an "
            "interval of +15.1 to +21.3 points once cohort selection is counted."
        ),
    ),
    Layer(
        id="fvg",
        label="Fair value gap",
        kind="detector",
        params="imbalance",
        note="The unfilled gap between the first and third of three candles.",
        evidence=(
            "+10 to +25 points against placebo, and it passed walk-forward 8 of 8 "
            "on two geometries."
        ),
    ),
    Layer(
        id="order_block",
        label="Order block",
        kind="detector",
        params="imbalance",
        note="The LAST opposing candle before the impulse.",
        evidence="Measured through the same rig as the fair value gap, same result.",
    ),
    Layer(
        id="ifvg",
        label="Inverted fair value gap",
        kind="detector",
        params="imbalance",
        note="A gap price has closed through, read from the other side.",
        evidence=(
            "H8 measured it as a direction claim and it came out SIGNIFICANTLY "
            "NEGATIVE: knowing a box had inverted made a directional guess worse. "
            "Drawn for fidelity, never as a reading."
        ),
    ),
    Layer(
        id="breaker",
        label="Breaker block",
        kind="detector",
        params="imbalance",
        note="An order block that suffered the same event.",
        evidence="Same as the inverted gap, and the same H8 negative result.",
    ),
    Layer(
        id="structure",
        label="Market structure",
        kind="overlay",
        params="structure",
        note="Swings, BOS, CHoCH, sweeps and MSS, at two fractal scales.",
        evidence=(
            "H6 and H9 measured these exact objects for direction and both came "
            "out null. Drawn so the method can be seen, never as a bias. The "
            "sweep rule was CORRECTED 2026-08-20: a level now emits ONE sweep "
            "instead of re-arming, which is what the most-used open-source "
            "implementation of the identical predicate does. Measured on 3000 "
            "bars of XAUUSD 15m, 147 sweeps from 88 levels became 88 from 88 - "
            "one level had been swept seven times - and the BREAK count did not "
            "move. Any figure quoting 8,725 sweeps predates this."
        ),
    ),
    Layer(
        id="session",
        label="Cycle grid",
        kind="overlay",
        params="session",
        note="New York quarters and true opens, at eight nesting degrees.",
        evidence=(
            "The grid itself passes 26 property checks on 73,956 quarters, with "
            "no gap and no overlap. That is CONSISTENCY, not predictive value: "
            "nothing connects a quarter to an outcome.\n\n"
            "The eighth degree is `quadrennial`, four years with the US "
            "presidential election year as Q2, so 2024 and 2028 are Q2 and 2026 "
            "is Q4. Its anchor is a fact rather than a fitted number, which is "
            "the only reason it could be built at all. Its true open needs the "
            "approximate rule: Q2 opens on 1 January, the market is shut on 1 "
            "January every year, and under the strict rule the level measured "
            "zero times on ten years of hourly gold."
        ),
    ),
    Layer(
        id="gaps",
        label="Opening gaps",
        kind="overlay",
        params="gaps",
        note="NDOG and NWOG bands, and the event horizons between them.",
        evidence=(
            "No disclosed study exists by anyone. MEASURED HERE 2026-08-20 and "
            "NULL: respect at the first touch of the consequent encroachment, "
            "n=1955 touches from 1971 bands over four instruments, came out "
            "-0.58 ATR - price CONTINUES through it - at t=-2.54, which fails "
            "the Bonferroni bar of 0.01, and walk-forward 2 of 8. Not reliable "
            "in either direction. The median first touch is 3 bars after the "
            "18:00 bar, so half of all touches are the gap simply being filled. "
            "Doctrine, drawn as doctrine."
        ),
    ),
    Layer(
        id="cisd",
        label="Change in state of delivery",
        kind="overlay",
        params="cisd",
        note="A close beyond the OPEN of the last opposing run.",
        evidence=(
            "No published hit rate exists. MEASURED NULL 2026-08-20: forward "
            "move at 12 bars, bullish minus bearish so drift cancels, n=23270 "
            "over four instruments, DELTA -0.0195 ATR at t=-0.53 - wrong sign "
            "and six times under the bar - and the halves flip sign in 3 of the "
            "4 series. The charged spread is 13x the (negative) edge. Also "
            "measured: two gold feeds disagree about which bars carry a CISD 29% "
            "of the time, because one flipped candle open splits or merges a "
            "whole run."
        ),
    ),
    Layer(
        id="dfr",
        label="Defining range",
        kind="overlay",
        params="dfr",
        note="Q1's final two thirds, its 50% equilibrium and its projections.",
        evidence=(
            "SINGLE-SOURCED AND UNVERIFIED, which is the whole of what is known. "
            "The thirds rule reached this project from one description of a "
            "closed-source indicator and has never been checked against the "
            "course material it came from, let alone against outcomes. Four "
            "property tests pass on three instruments, which is implementation "
            "CONSISTENCY. The source gives the -0.5 and -1 extensions no "
            "direction, so both sides are drawn rather than one being chosen."
        ),
    ),
    Layer(
        id="ssmt",
        label="SSMT divergence",
        kind="overlay",
        # SHARES THE CHECKLIST'S BLOCK rather than duplicating three fields, the
        # same way four detectors share `imbalance`. `ssmt_symbols`,
        # `ssmt_degrees` and `ssmt_provider` already exist there and already
        # drive the same computation; a second copy would be two places to set
        # one basket and two chances for them to disagree.
        params="checklist",
        note="The cross-instrument divergence, drawn on this symbol's own price.",
        evidence=(
            "The RATE is almost entirely the pair you choose, measured 14.9% "
            "against silver and 59.5% against DXY at day degree - an inversely "
            "correlated partner disagrees by construction. Nothing connects a "
            "divergence to an outcome, by anyone. Drawn because it is the most "
            "frequent annotation in the reference charts, 33 of 51, and it was "
            "computed here for months while being visible only as a count."
        ),
    ),
    Layer(
        id="pools",
        label="Liquidity pools",
        kind="overlay",
        params="pools",
        note="Asian and London session extremes, as candidate targets.",
        evidence=(
            "MEASURED NULL, 2026-08-20. Pre-registered: an untaken session "
            "extreme is traded through within 96 bars more often than a "
            "placebo. n=7552 over four instruments, reach 72.03%. Against a "
            "SHUFFLED placebo +2.90pp, p=9.2e-05 - and that control was then "
            "shown to be defective: shuffling un-pairs a level's distance from "
            "its bar's volatility, and inside matched distance bands the gap is "
            "-0.68pp. The per-event JITTER control, which keeps the pairing, "
            "says +0.15pp. Walk-forward 4 of 8, sign test p=1.00. A taken pool "
            "is still drawn, dimmed."
        ),
    ),
    Layer(
        id="liquidity",
        label="Named levels",
        kind="overlay",
        params="liquidity",
        note="PDH, PDL, PWH, PWL and the named day extremes, plus ERL and IRL.",
        evidence=(
            "MEASURED NULL and the point estimate is NEGATIVE, 2026-08-20. "
            "Reach within 96 bars against a placebo at the same offset: "
            "PDH/PDL n=4152, -1.59pp [-3.28, +0.10], walk-forward 3 of 8; "
            "PWH/PWL n=747, -0.94pp, walk-forward 3 of 8. Negative on all four "
            "instruments, and the control used carries a tailwind in the "
            "overlay's favour, so the honest figure is at or below these. The "
            "draw-on-liquidity candidates are reported on each side and never "
            "resolved to one, because naming the draw is a forecast."
        ),
    ),
    Layer(
        id="projections",
        label="Deviation projections",
        kind="overlay",
        params="projections",
        note="Multiples of a session range projected past it.",
        evidence=(
            "MEASURED NULL 2026-08-20, and it is the largest non-zero thing in "
            "this group: reach within 96 bars off the Asian box, n=6320 levels "
            "from 2122 boxes, +0.46pp against a per-event jitter control "
            "[+0.08, +0.85] - which is 6.5x BELOW the pre-registered threshold "
            "and fails walk-forward at 6 of 8, p=0.29. The -0.5 multiple is "
            "reached 74.2% of the time and the jittered one 73.5%. Only ONE "
            "anchor and one direction rule were tested. The geometry itself was "
            "recovered from the reference chart and agrees with its price tags "
            "to 0.4 USD, which validates the TRANSCRIPTION and nothing else."
        ),
    ),
    Layer(
        id="news",
        label="Economic calendar",
        kind="overlay",
        params="news",
        note="Scheduled releases on the New York clock, from the ForexFactory feed.",
        evidence=(
            "None, and it cannot be measured from this source: only the CURRENT "
            "WEEK is published - nextweek, lastweek, thismonth and thisyear all "
            "return 404 - so there is no history to test anything against. "
            "`impact` is the feed's own label for how much attention an event "
            "gets, not a measured effect on price. What the source DOES give "
            "safely is that it publishes no `actual` value at all, so it cannot "
            "leak an outcome backwards onto a bar."
        ),
    ),
    Layer(
        id="checklist",
        label="Checklist",
        kind="report",
        params="checklist",
        note="The owner's own pre-trade items, answered with their evidence.",
        evidence=(
            "None of the items has been measured against outcomes, and the report "
            "deliberately carries no overall pass or fail. This is also the only "
            "layer that can make extra provider calls."
        ),
    ),
)

LAYER_IDS: frozenset[str] = frozenset(layer.id for layer in LAYERS)

#: Which params block on the request each layer reads, derived rather than
#: restated. `app/detect/__init__.py` used to carry its own `PARAMS_FOR` dict
#: saying the same thing for the five detectors, which is two sources for one
#: fact and the kind that drifts quietly: a detector pointed at the wrong
#: block still returns a 200 and still draws, just from the wrong knobs.
PARAMS_BY_ID: dict[str, str] = {layer.id: layer.params for layer in LAYERS}

#: The layers that draw boxes, so they can be checked against the detector
#: registry. A detector present in one and absent from the other is a control
#: wired to nothing, or a drawing nobody can switch off.
DETECTOR_IDS: frozenset[str] = frozenset(
    layer.id for layer in LAYERS if layer.kind == "detector"
)

#: The default chart: one detector, nothing else. Everything is opt-in because
#: chart ink is a measured quantity here - five detectors alone paint 31.6% of
#: it, and past roughly a third the boxes stop annotating price and become its
#: background.
DEFAULT_LAYERS: tuple[str, ...] = ("supply_demand",)


def catalogue() -> list[dict[str, str]]:
    """The registry as the API serves it, so the UI has ONE source of truth.

    The frontend used to hardcode which ids were detectors, which were overlays,
    and what each did. Every one of those lists could drift from the backend
    without anything failing, which is how a control ends up wired to nothing.
    """
    return [
        {
            "id": layer.id,
            "label": layer.label,
            "kind": layer.kind,
            "params": layer.params,
            "note": layer.note,
            "evidence": layer.evidence,
        }
        for layer in LAYERS
    ]
