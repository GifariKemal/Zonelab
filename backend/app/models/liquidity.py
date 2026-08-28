"""Range readings, pools, named levels, and the projections off them."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RangeReading(BaseModel):
    """Where price sits in one candidate range, and which range that was."""

    anchor: str
    degree: str = Field(description="The PARENT degree the window was taken from")
    time_from: int
    time_to: int = Field(description="The last bar actually included, so coverage is visible")
    complete: bool = Field(description="False while the window is still running")
    bars: int
    high: float
    low: float
    equilibrium: float = Field(description="The 50% line, which is the whole measurement")
    position: float = Field(
        description=(
            "0 at the low, 1 at the high, deliberately NOT clipped: a closed "
            "window can have price outside it, and clipping would hide that."
        )
    )
    reading: Literal["premium", "discount", "equilibrium"]


class PremiumDiscount(BaseModel):
    """The TIME-anchored premium and discount read, which is the third one here.

    Three different readings of the same idea now live in this engine and using
    the wrong one is the easy mistake, so they are named together:

    | Field | Anchored to |
    |---|---|
    | `Zone.curve` | swings, Seiden's reading, frozen when the zone is born |
    | `Zone.dealing_range_pos` | the last SWING pair, ICT's dealing range |
    | this | a CLOCK: the cycle one degree above the one being traded |

    The clock is the entire point. This is the reading the owner's own procedure
    uses, and it is SINGLE-SOURCED, so the anchor is a parameter and **every**
    candidate is returned rather than only the chosen one. A reader who can see
    that the running parent cycle says discount while the last closed one says
    premium has learned something a single boolean would have destroyed;
    `disagree` says when that is the case without needing to be read.
    """

    degree: str = Field(description="The degree being TRADED, not the anchor's")
    anchor: str
    at: int = Field(description="The bar this was read at")
    price: float
    chosen: RangeReading | None = Field(
        default=None, description="None when the chosen anchor had no window"
    )
    readings: list[RangeReading] = Field(default_factory=list)
    absent: list[str] = Field(
        default_factory=list,
        description=(
            "One entry per anchor that produced nothing, WITH its reason. At the "
            "day degree a Friday produces three of these, because the week has "
            "four quarters and Friday is in none of them."
        ),
    )
    disagree: bool = Field(
        default=False, description="True when the anchors do not all give the same word"
    )


class LiquidityPool(BaseModel):
    """A named session's extreme, as a candidate target.

    BSL is the session high (buy-side liquidity), SSL the low. Asia is 19:00 to
    00:00 New York and London is 02:00 to 05:00, both ICT's own windows.

    A taken pool is still reported. "London high already got taken" is the fact
    that kills a trade idea, so removing it would remove the reason.

    > The London window opens at 02:00 New York, which on the spring-forward day
    > is an hour that DOES NOT EXIST. `clock.py` could state that no quarter
    > boundary ever lands between 02:00 and 03:00, so the question never arose
    > there; it arises here. With `fold=0` the open maps to 03:00 EDT and the
    > killzone is two real hours that day. That is a consequence of a choice, not
    > a citation - no source says what a 02:00 killzone is on a day without an
    > 02:00.
    """

    session: str
    side: Literal["BSL", "SSL"]
    price: float
    window_from: int
    window_to: int
    bars: int
    covered: bool = Field(
        description=(
            "False when the feed did not span the whole window. A partial window's "
            "high is NOT the session high, and saying so is the difference between "
            "a missing answer and a wrong one."
        )
    )
    knowable_at: int = Field(description="When the session closed. Nothing before this.")
    taken_at: int | None = Field(
        default=None,
        description=(
            "The FIRST bar that traded strictly through it, or None while it "
            "stands. An equal high is a touch, not a take: the session's own bar "
            "made that high."
        ),
    )


class NamedLevel(BaseModel):
    """A named horizontal level, which is the object his practice uses most.

    A named ray with its label at the right edge appears on 24 of 24 of his own
    annotated price charts; Fibonacci appears on 12%. So PDH, PWH, Friday's low
    and the rest all arrive as one shape with one vocabulary, and the NAME is
    what types them - colour deliberately does not, because his own charts use
    the same colour for different objects.

    A taken level is still reported, the same rule `LiquidityPool` follows: "the
    previous day high already got taken" is the fact that kills an idea.
    """

    name: str = Field(
        description=(
            "PDH, PDL, PWH, PWL, FRI H, MON L, RNG H, EQ 50 and so on. AT MOST "
            "EIGHT CHARACTERS, because the canvas draws it left-aligned from a "
            "46px label column with no clamp and simply loses the rest - which "
            "four shipped names had been doing. tests/test_liquidity.py pins it."
        )
    )
    price: float
    knowable_at: int = Field(description="When the period that made it closed")
    taken_at: int | None = Field(
        default=None, description="First bar strictly through it, None while it stands"
    )
    side: Literal["BSL", "SSL"] | None = Field(
        default=None,
        description=(
            "A high is buy-side, a low is sell-side. NULL where the source does "
            "not state one: a dealing-range edge and an internal zone are levels "
            "without a buy-side or sell-side reading, and an earlier version of "
            "the wiring INFERRED the side from the level's name - which got every "
            "external high wrong, because that name was `range_high` in lower case "
            "and the test was for `HIGH`. Absent beats guessed, the same rule "
            "`Candle.spread` follows by being None rather than 0."
        ),
    )
    derived: bool = Field(
        default=False,
        description=(
            "True where the price is ARITHMETIC ON OTHER LEVELS rather than one "
            "the market printed. The dealing range's equilibrium and its two "
            "quartile boundaries are derived; its high and low are not, and "
            "neither is a previous day high. The canvas draws a derived level "
            "dashed and a printed one solid, which is the reference set's own "
            "convention - a dashed 50% inside a range appears on 36 of its 51 "
            "charts while the named period extremes are solid. "
            "A SEPARATE FIELD RATHER THAN A READING OF `boundary`, because "
            "`boundary` means which day boundary the period was measured on and "
            "the range frame all carries `range`. Testing `boundary == 'range'` "
            "would have dashed the range's own high and low too - prices the "
            "market really traded - and overloading one field with a second "
            "meaning is how a style rule silently becomes wrong."
        ),
    )
    boundary: str = Field(
        description=(
            "Which day boundary the period was measured on: `cycle` is 18:00 New "
            "York, which is the grid the rest of this engine draws and the CME "
            "open; `midnight` is the calendar day. THEY GIVE DIFFERENT NUMBERS on "
            "the same bars, so the choice travels with the level rather than "
            "being assumed by whoever reads it."
        )
    )
    window_from: int
    window_to: int
    gap_at_open: int = Field(
        description=(
            "Seconds at the start of the window with no bar in them. Not a "
            "boolean: a session pool can ask whether its window was covered, but "
            "a day cycle ALWAYS ends in a market closure - measured, every one of "
            "14 day cycles ends with 3600 unbarred seconds and every week cycle "
            "with 176400 - so a covered flag would have read False on every "
            "correct level."
        )
    )
    gap_at_close: int


class RangeLiquidityReport(BaseModel):
    """ERL and IRL: what rests outside the dealing range, and what sits inside it.

    His procedure alternates between the two. External is the range's own
    extremes; internal is the unfilled inefficiency between them, which is why it
    is built from zones that were already detected rather than from a second pass.
    """

    at: int
    high: float
    low: float
    high_time: int
    low_time: int
    knowable_at: int
    external: list[NamedLevel] = Field(default_factory=list)
    internal: list[NamedLevel] = Field(default_factory=list)


class DrawCandidate(BaseModel):
    """One untaken level, with how far it is. NOT a prediction that price goes there."""

    name: str
    price: float
    distance: float
    knowable_at: int


class DrawOnLiquidity(BaseModel):
    """The untaken liquidity above and below, and deliberately never one answer.

    A "draw on liquidity" names where price is going, which makes it a forecast,
    and this project has had TWELVE pre-registered directional hypotheses fail.
    So this reports the CANDIDATES on each side and refuses to pick.

    EITHER SIDE MAY BE EMPTY, and an earlier version of this docstring claimed
    otherwise - that there is untaken liquidity in both directions at every
    moment. That is false and a test caught it: price that has run above every
    previous-period high leaves nothing untaken above it. An empty side is a
    fact about what has already been swept, not a nomination of the other one.
    """

    at: int
    price: float
    above: list[DrawCandidate] = Field(default_factory=list)
    below: list[DrawCandidate] = Field(default_factory=list)


class ProjectionLevel(BaseModel):
    """One standard-deviation projection off a range, with his own label."""

    multiple: float = Field(description="The label as he draws it: 0, -0.5, -1, -1.5, 2, 2.5")
    price: float
    taken_at: int | None = None


class RangeProjection(BaseModel):
    """A range and the multiples of its own height projected beyond it.

    The stack of short labelled segments beside a session box is one of the most
    frequent objects on his charts. The geometry was recovered from image 27 in
    `Referensi grup dan Bg Nas` and checked against that chart's own price tags: it agrees to
    within 0.4 USD, which is tighter than the boxes could be measured.

    `price = origin - direction * multiple * height`, where `origin` is the range
    edge IN THE DIRECTION OF TRAVEL. That is why the label set looks asymmetric
    and skips +0.5 and +1: those are the range's own midpoint and far edge, both
    already drawn as the box itself.

    DIRECTION IS NEVER INFERRED. On his own charts it is read from where price
    went after the box, which is hindsight. The engine takes it as an argument or
    draws both ways, and does neither by guessing.
    """

    time_from: int
    time_to: int
    high: float
    low: float
    height: float
    direction: int = Field(description="+1 travelling up, -1 travelling down")
    origin: float = Field(description="The edge multiple 0 sits on")
    bars: int
    knowable_at: int = Field(description="First bar proving the range closed")
    label: str = Field(description="Which range this is, so two stacks can be told apart")
    levels: list[ProjectionLevel] = Field(default_factory=list)
