"""Opening gaps, the news around them, and the horizons between them."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OpeningGap(BaseModel):
    """The band between one session's last traded price and the next session's first.

    NDOG is the 17:00-to-18:00 New York gap on a Monday through Thursday evening;
    NWOG is the same geometry across the weekend, Friday's close against the
    Sunday 18:00 open. `ce` is the consequent encroachment, the midpoint.

    `approximate` is the field a reader must not skip. ICT states that these are
    read off 1-minute or 5-minute bars and never off a daily chart, because a
    daily bar's close is the SETTLEMENT price and settlement is a different number
    from the last price that actually traded before 17:00 - so a band read off
    dailies has an edge nothing ever traded at. The engine cannot refuse the bars
    it is given, so it flags instead: False only when the closing bar provably ends
    at 17:00 and the opening bar opens at 18:00. Hourly bars come out exact, 4-hour
    bars do not.
    """

    kind: Literal["NDOG", "NWOG"]
    top: float
    bottom: float
    ce: float = Field(description="Consequent encroachment: the midpoint of the band")
    close_time: int = Field(description="Open time of the bar whose CLOSE gave one edge")
    open_time: int = Field(
        description="Open time of the bar whose OPEN gave the other, and when the band became knowable"
    )
    approximate: bool
    label: str = Field(
        default="",
        description=(
            'Its position among gaps of the SAME kind, newest first: "D-1" is '
            "the latest daily gap, \"W-2\" the weekly one before last. Adopted "
            "from the reference indicator's own rendered labels.\n\n"
            "> A POSITION IN A LIST, not an identity. Every gap of a kind "
            "renumbers the moment a newer one forms, which is the same "
            "not-fixed-at-birth hazard `EventHorizonLevel` carries. Never key "
            "anything on it."
        ),
    )
    degree: str | None = Field(
        default=None,
        description=(
            "For an NWOG only: the cycle degree whose Q2 this weekend opens - "
            "`month` or `year` - or null. This is a LABEL selecting which "
            "weekend gap matters at which degree, NOT a fifth kind of gap. "
            "Measured over 29 month boundaries on gold: 16 carry no session "
            "break at all, and all 13 that do are weekends or public holidays. "
            "A calendar month change never closes the market by itself."
        ),
    )
    distance_to_ce: float | None = Field(
        default=None,
        description=(
            "Signed distance from the LAST BAR's close to this band's "
            "consequent encroachment. Negative means price sits below it.\n\n"
            "Reported as of that bar and nothing else. Unlike every other field "
            "here it is not fixed at birth - the band never moves, the distance "
            "moves on every tick - so it lives on the wire as a snapshot rather "
            "than on the engine's own object, where it would make a settled "
            "thing look live."
        ),
    )


class NewsEvent(BaseModel):
    """One scheduled economic release, on the clock rather than on the price.

    The owner's own method ties these to his cycle phases - he names NFP, CPI
    and FOMC against accumulation, manipulation and distribution - and his time
    board's `News/NFP 08:30 New York` row is the one line this engine could not
    answer until now.

    > `impact` IS THE FEED'S OWN LABEL for how much attention an event draws. It
    > is not a forecast and not a measured effect: nobody here has tested whether
    > a High row moves price more than a Low one, and with this source nobody
    > can, because only the CURRENT WEEK is published. There is no history to
    > measure against, and a study that used today's calendar against last
    > month's bars would be measuring the calendar.

    What the source does give safely is that it publishes **no actual value at
    all** - schedule, forecast and previous only - so it cannot leak an outcome
    backwards onto a bar. That is the property that makes it safe to draw live.

    `forecast` and `previous` are empty strings when the feed gives none. Empty
    means the feed said nothing, never zero.
    """

    time: int = Field(description="Epoch seconds, from the row's OWN UTC offset")
    title: str
    currency: str = Field(description="The affected currency, e.g. USD, not a country")
    impact: str = Field(
        description=(
            "The feed's own label, verbatim. A plain string rather than a "
            "three-way Literal on purpose: the source also publishes rows such "
            "as `Holiday` on other weeks, and narrowing the type would force a "
            "choice between a guarantee the parser cannot keep and discarding "
            "real calendar data to protect it. `High`, `Medium` and `Low` are "
            "what this week's 98 rows carried; they are observed, not a "
            "whitelist."
        )
    )
    forecast: str = ""
    previous: str = ""
    bar: int = Field(
        default=0,
        description=(
            "Open time of the bar the release happened DURING. A release almost "
            "never lands on a bar open - 08:30 New York is 12:30 UTC and an "
            "hourly axis has no such point - so the chart cannot ask the time "
            "scale for its x directly. It asks for this bar instead."
        ),
    )
    offset: float = Field(
        default=0.0,
        description=(
            "How far into that bar the release fell, 0 at its open and 1 at the "
            "next one. The chart multiplies it by the bar spacing, so 08:30 "
            "lands halfway between the 12:00 and 13:00 candles rather than on "
            "either. Events that fell while the market was shut have no bar to "
            "sit inside and are not sent at all."
        ),
    )


class GapStack(BaseModel):
    """Two gaps of DIFFERENT kinds whose bands overlap, and by how much.

    Adopted from the reference indicator, which renders it as `EV STACK W+D` with
    a percentage. Two gaps of the same kind overlapping is not a stack: the whole
    construct is about a lower degree landing on a higher one.

    > `fraction` is the overlap height over the SMALLER band's height, and that
    > denominator is a RECONSTRUCTION rather than a citation. It was recovered
    > arithmetically from one rendered figure - overlap 187.25 over the smaller
    > band 206.50 gives 90.7%, shown as 91% - and dividing by the union or by the
    > larger band would have given 29% and 30% on the same two bands. One label
    > pins one candidate and cannot rule the others out. `tests/test_gaps.py`
    > holds all three numbers so a silent swap fails loudly.

    Nothing here has been measured against outcomes, by this project or by the
    indicator's author, who publishes no study.
    """

    top: float
    bottom: float
    fraction: float = Field(
        description="Overlap height over the smaller band's height, 0 to 1"
    )
    kinds: list[str] = Field(description="The two kinds, in the order they were paired")
    open_times: list[int] = Field(
        description="Identifies the two gaps, matching `OpeningGap.open_time`"
    )
    knowable_at: int = Field(description="The later of the two gaps'")


class TierHorizon(BaseModel):
    """One zone per gap kind, reduced from the latest few gaps of that kind.

    The reference indicator draws these rather than one zone per gap: a `D` row
    from the newest NDOGs and a `W` row from the newest NWOGs. **Three per kind
    is the owner's own number, confirmed directly**, which makes it the one part
    of this construct that is sourced rather than reconstructed.

    > HOW THE THREE BECOME ONE TOP AND ONE BOTTOM IS UNRESOLVED. The reference's
    > published table reads D 28561.50..28768.00 and W 28580.75..29206.75 on
    > NASDAQ 100 E-mini at price 28164.00; our data for that instrument and
    > instant agrees on price to 5 points, so the comparison is like for like.
    > NONE of the four reductions tried reproduces it, and neither number is an
    > edge of any gap detected in that window - so either the reduction is an
    > operation not yet tried, or the reference finds its gaps at different
    > boundaries than 17:00 and 18:00 New York. One screenshot cannot separate
    > those. `reduction` therefore travels on every zone, and `app/gaps.py`
    > keeps all four candidates with the numbers each produced.

    Not fixed at birth: a new gap of a kind pushes the oldest out of the
    retained set and the whole zone moves without a price changing.
    """

    kind: Literal["NDOG", "NWOG"]
    reduction: str = Field(
        description="Which reading produced this zone: envelope, ce_span, newest or eh_span"
    )
    top: float
    bottom: float
    ce: float = Field(description="The zone's midpoint. The reference measures its Dist to this.")
    knowable_at: int
    open_times: list[int] = Field(
        default_factory=list,
        description="The gaps it consumed, oldest first, by their own open times",
    )


class EventHorizonLevel(BaseModel):
    """One price: the average of a gap's top and the bottom of the next gap UP.

    A LEVEL, not a band. The name collides in the wild - the reference script the
    owner works from uses "event horizon" for the gap ZONE instead, and the two
    readings produced non-overlapping bands on real gold - and this is the ICT
    reading. A caller that wants the zone reading wants the gap itself.

    Adjacency is in PRICE space, not time: the gaps are sorted by their own
    midpoints and each pairs with its neighbour above, so N gaps give N-1 levels.

    > This is the only object the engine draws whose value is NOT FIXED AT BIRTH.
    > Every zone here settles the moment it forms and its edges never move again.
    > A new gap appearing between two existing ones re-sorts the pairing and MOVES
    > a level already on the chart without a single price changing. Anything that
    > measures these must ask for the level set as of a bar, never as of now.
    """

    price: float
    knowable_at: int = Field(description="The later of the two gaps' open times")
    lower_open_time: int = Field(description="Identifies the gap below, in price")
    upper_open_time: int = Field(description="Identifies the gap above, in price")
