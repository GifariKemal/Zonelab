"""Market structure: swing points, breaks, and a directional bias.

The first object in this project that claims to say WHICH WAY rather than WHERE.

Everything measured here so far - supply and demand zones, fair value gaps,
order blocks - marks a location. All three beat a placebo control by 10 to 25
points and survive walk-forward, and none of them carries direction: four
pre-registered directional hypotheses, four nulls. The doctrine itself says why.
ICT and SMC put directional bias in market STRUCTURE and use zones only to
refine the entry. Structure decides which way; a zone decides where.

So this module exists to be measured, not to be believed.

THE ONE THING THAT MAKES OR BREAKS IT
A swing high at bar `i` is not knowable at bar `i`. It is knowable at bar
`i + LEFT`, once enough bars have printed to its right to confirm nothing
exceeded it. A detector that reacts to a swing the moment it forms is reading
bars that had not happened yet, and it would show a beautiful directional edge
made entirely of hindsight.

Every swing here therefore carries `confirmed_at`, and every break is tested
only against swings whose `confirmed_at` is at or before the breaking bar. That
single rule is the difference between a measurement and a fiction, and it is
asserted in the tests rather than trusted.

BREAK, NOT SWEEP
A break requires a bar to CLOSE beyond the swing. A wick through that closes
back inside is a sweep, which in most codifications is the opposite signal - it
is liquidity being taken, not structure giving way. Using the wick would merge
the two into one event and guarantee the detector cannot tell them apart.

BOS AND CHoCH
Both are closes beyond a confirmed swing. The difference is only which way the
bias was already pointing:

    bias      break beyond        name    means
    bullish   last swing HIGH     BOS     the trend continued
    bullish   last swing LOW      CHoCH   the trend may have turned
    bearish   last swing LOW      BOS     the trend continued
    bearish   last swing HIGH     CHoCH   the trend may have turned

Before any break has happened the bias is `none`, and the first break in either
direction sets it. Calling that first break a CHoCH would claim a character
changed from a character that was never established.

DISPLACEMENT, AND WHY AN MSS HERE NOW NEEDS A GAP
An MSS was paired here as two things: a sweep, then an opposite break. That is
two thirds of the definition. ICT's own 2022 mentorship IS retrievable, as SRT
transcripts, and in the lesson that exists to teach this construct he rules the
two-part reading out by name:

    "It's not that it goes above this old, relative equal high, and then goes
     down below that - that's not it, folks, that's not it. You have to see it
     go below that in displacement with energetic move, take out a short term
     low. That's how you filter out these trades that may not be high
     probability."               - 2022 Mentorship Episode 24, 2022-05-06

He never operationalises displacement as a candle size or an ATR multiple. He
operationalises it as an INEFFICIENCY INSIDE THE LEG, and he makes it a gate:

    "you don't have a trade entry yet, until you determine if it has a fair
     value gap. Where does that reside? Between the displacement high and the
     displacement low ... So in that range, that's where you're bullish fair
     value g[ap] resides - if there isn't one there, you don't have a trade."
                                 - 2022 Mentorship Episode 6, 2022-02-04

That is a test this repo already owns. `imbalance._gap` is the wick-to-wick
predicate the FVG detector runs on, so `mss_sweeps` asks it of the leg from the
sweep to the break and requires a gap in the BREAK's direction. No number was
invented and no field was added: the requirement belongs to the NAME, so it
decides which breaks are CALLED an MSS and nothing else. The break and the sweep
are both still emitted, so no population is deleted.

WHAT IS STILL NOT FAITHFUL, said plainly because it is a real hole
ICT checks the gap on the bar AFTER the break - "as soon as this candle closes,
does it create that fear value gap?", Episode 3 - and a gap centred on the break
bar needs the bar after it. Reading that bar would put the future inside an event
drawn at the break bar, which is the one thing this module exists to prevent. So
the leg is scanned for gaps centred at bars `sweep .. break-1` only, and an MSS
whose ONLY gap straddles the break bar is missed. Closing that needs a
`confirmed_at` on StructureEvent - the field SwingPoint already carries - so the
event could be stamped at the break and declared knowable one bar later.
StructureEvent is not this module's to change, so the hole is reported.

Two more departures, both ours. ICT requires no CLOSE beyond the level - "it does
not need to close above that. Okay, real important" (Episode 3), "preferably
close below that" (Episode 6) - while a break here always requires one, so our
MSS is a strict subset of his. And "energetic" is his adjective for the leg; it
is not tested, because he never gives it a number and every impulsiveness number
this repo invented is marked as invented.

THE OVERLAY, AND WHY IT IS NOT A SIGNAL
`overlay()` is the drawable face of everything above, and it closes the three
adoptions docs/FIDELITY.md lists as missing: two fractal widths run at once with
the small one told whether the large one agreed, a sweep told whether price ever
closed back inside the level it took, and the sweep-then-opposite-break pair
named as its own object, the Market Structure Shift.

It is drawn for FIDELITY and never as a direction signal. ICT puts bias in
structure and uses zones only to refine the entry, so a chart that cannot show
structure at two scales cannot show the method - and that is the whole reason.
The direction claim itself was tested and died twice. H6 tested BOS, CHoCH and
SWEEP as three separate cohorts and none of them survived. H9 tested the two-part
conjunction, a sweep then an opposite break: t = -0.79 and -0.12 on DELTA at the
primary horizon against a pre-registered bar of 3.0, the sign REVERSING between
the two halves, and on the large fractal the conjunction happened only 7 and 43
times, too rare to test at all. H11 in tools/mss.py then tested the THREE-part
conjunction drawn here - sweep, displacement, break - which is the one the
sources actually describe and which H9 never asked. See docs/CALIBRATION.md.

So nothing here filters. `reversed_within` reports the rejection every source
describes and drops no sweep that lacks it; `aligned_with_swing` reports the
crossing and excludes no event; an MSS is emitted ALONGSIDE the break it was
carved out of, because swallowing the break would leave the drawn population
disagreeing with the measured one. Measured, not believed - drawn least of all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from ..models import Candle, StructureEvent, StructureParams, SwingPoint


@dataclass(frozen=True)
class Swing:
    """A pivot, and the bar at which it became knowable."""

    index: int
    price: float
    high: bool
    confirmed_at: int


@dataclass(frozen=True)
class Break:
    """A close beyond a confirmed swing."""

    index: int  # the bar that closed beyond
    time: int
    # Narrowed to the three names this function can emit, so a typo cannot reach
    # the wire model. "MSS" is absent on purpose: it is a pairing of two of these
    # and is built by the overlay, not by the single forward pass here.
    kind: Literal["BOS", "CHoCH", "SWEEP"]
    direction: int  # +1 broke upward, -1 broke downward
    level: float  # the swing price that gave way
    swing_index: int  # which bar made that swing
    bias_before: int  # -1, 0 or +1


def swings(
    high: np.ndarray, low: np.ndarray, left: int, right: int
) -> list[Swing]:
    """Fractal pivots, each stamped with the bar it became knowable on.

    `left` bars must be lower (higher) on one side and `right` on the other. The
    two are separate because they do different jobs: `left` is how much history
    a pivot has to dominate, `right` is how long you must WAIT before you are
    allowed to know about it. Collapsing them into one number hides the second.

    Ties are broken by requiring a strict maximum on the left and a
    non-exceedance on the right. A flat top would otherwise register a pivot on
    every bar of the plateau.
    """
    out: list[Swing] = []
    n = len(high)
    for i in range(left, n - right):
        window_l = slice(i - left, i)
        window_r = slice(i + 1, i + 1 + right)
        if high[i] > high[window_l].max() and high[i] >= high[window_r].max():
            out.append(Swing(i, float(high[i]), True, i + right))
        if low[i] < low[window_l].min() and low[i] <= low[window_r].min():
            out.append(Swing(i, float(low[i]), False, i + right))
    return sorted(out, key=lambda s: (s.confirmed_at, s.index))


def breaks(
    candles: list[Candle], left: int = 2, right: int = 2
) -> tuple[list[Break], list[Swing]]:
    """Walk the bars once, emitting a break each time one closes beyond a swing.

    The loop is deliberately a single forward pass with no lookahead of any
    kind: at bar `i` it may only see swings already confirmed at `i`, and it
    tests only the CLOSE of bar `i`. Anything else would let a break know how
    the bar it broke on ended up.
    """
    if len(candles) < left + right + 2:
        return [], []

    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    times = [c.time for c in candles]

    found = swings(high, low, left, right)
    return walk_breaks(high, low, close, times, found), found


def walk_breaks(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    times: list[int],
    found: list[Swing],
    resweep: bool = False,
) -> list[Break]:
    """The forward pass `breaks` runs, over whatever swing list you hand it.

    Split out of `breaks` and otherwise unchanged, so an ALTERNATIVE pivot
    definition can be measured against ours without forking the break semantics.
    tools/mss.py uses it for the one-sided-pivot sensitivity: the whole point of
    that measurement is that only the pivot rule differs, which is only true if
    the loop below is literally the same loop.
    """
    by_confirm: dict[int, list[Swing]] = {}
    for swing in found:
        by_confirm.setdefault(swing.confirmed_at, []).append(swing)

    # The most recent CONFIRMED swing on each side, and the level each one put
    # in the way. They are replaced as new swings confirm and cleared when
    # broken, so a level can only be broken once.
    live_high: Swing | None = None
    live_low: Swing | None = None
    # SWINGS ALREADY SWEPT ONCE, so a level cannot emit a sweep twice.
    #
    # `docs/FIDELITY.md` lists unlimited re-sweeping as a DEPARTURE, and the
    # measured consequence was 8,725 sweeps against 9,210 breaks - a sweep for
    # every break, which is not what the object is supposed to be. The most-used
    # open-source implementation of the identical predicate, LuxAlgo's Liquidity
    # Sweeps at 20,752 likes, marks the level instead:
    #
    #     if not oO and not get.wic
    #         if high > get.prc and close < get.prc
    #             ...
    #             get.wic := true
    #
    # Measured here on 3000 bars of XAUUSD 15m: at swing width 5, 148 sweeps
    # come from only 89 distinct levels and one level was swept SEVEN times; at
    # width 50, 17 sweeps from 10 levels. So the drawn population falls about
    # 40% and not one sweep that was the FIRST taking of its level disappears.
    #
    # Keyed on the swing's own index rather than on its price: two swings can
    # sit at the same price and are two levels, and clearing on a break would
    # re-arm a level the break already consumed.
    swept: set[int] = set()
    bias = 0
    out: list[Break] = []

    for i in range(len(close)):
        for swing in by_confirm.get(i, ()):
            if swing.high:
                live_high = swing
            else:
                live_low = swing

        # A close beyond, never a wick. A wick through that closes back inside
        # is a SWEEP - liquidity taken - and calling it a break would merge two
        # opposite events into one name. Sweeps are emitted rather than silently
        # skipped: it is the only object in this doctrine with a peer-reviewed
        # mechanism behind it (stop orders clustering just beyond a level), and
        # a detector that drops them cannot ever be asked about them.
        #
        # Up is evaluated before down, so an outside bar that closes beyond BOTH
        # levels emits both and ends bearish. No source addresses that case; the
        # order is a stated choice, and both events are kept rather than one
        # being swallowed by an `elif`.
        if live_high is not None:
            if close[i] > live_high.price:
                kind = "BOS" if bias >= 0 else "CHoCH"
                out.append(
                    Break(i, times[i], kind, 1, live_high.price, live_high.index, bias)
                )
                bias = 1
                live_high = None
            elif high[i] > live_high.price:
                if resweep or live_high.index not in swept:
                    out.append(
                        Break(i, times[i], "SWEEP", 1, live_high.price,
                              live_high.index, bias)
                    )
                    swept.add(live_high.index)
                # The level stays armed for BREAKS either way, and its price is
                # unchanged. Raising it to the sweep wick would change every
                # break downstream, and doctrine is silent on which is right.

        if live_low is not None:
            if close[i] < live_low.price:
                kind = "BOS" if bias <= 0 else "CHoCH"
                out.append(
                    Break(i, times[i], kind, -1, live_low.price, live_low.index, bias)
                )
                bias = -1
                live_low = None
            elif low[i] < live_low.price:
                if resweep or live_low.index not in swept:
                    out.append(
                        Break(i, times[i], "SWEEP", -1, live_low.price,
                              live_low.index, bias)
                    )
                    swept.add(live_low.index)

    return out


def mss_sweeps(
    high: np.ndarray,
    low: np.ndarray,
    sweeps: list[Break],
    event: Break,
    window: int,
) -> list[Break]:
    """Sweeps that qualify `event` as a Market Structure Shift, oldest first.

    THE ONE DEFINITION. tools/mss.py imports this rather than restating it,
    because the drawn MSS and the measured MSS being two different objects is
    exactly how a chart ends up disagreeing with its own calibration.

    Three conditions, and the third is the one H9 never had:

      1. the sweep is inside `window` bars before the break;
      2. it took liquidity on the OPPOSITE side - liquidity taken above, then
         price goes down. A sweep the same way is a delayed continuation;
      3. the leg from that sweep to that break left a FAIR VALUE GAP pointing
         the way the break went. This is DISPLACEMENT, and it is ICT's own
         operationalisation of it rather than a size we chose: "you don't have a
         trade entry yet, until you determine if it has a fair value gap ...
         if there isn't one there, you don't have a trade" (Episode 6). See the
         module docstring for the quotes and for what is still not faithful.

    `_gap` is imported inside the function on purpose. `imbalance` imports
    `breaks` from this module, so a module-level import here would be circular -
    and writing the two-line comparison out again instead is precisely how the
    FVG detector and the MSS would come to disagree about what a gap is.

    The gap is looked for at bars `sweep .. break - 1`. Not the break bar: a gap
    centred there needs the bar AFTER the break, so an MSS drawn at the break
    would contain a bar that had not printed. That is the documented hole, not an
    oversight.

    The price is free at the shipped widths, and that is measured rather than
    assumed: 0.257s against 0.260s for the two-part pairing on 20,000 PAXGUSDT
    15m bars, min of 7 interleaved runs. It draws FEWER objects - 38 MSS against
    52 on that series, 31 against 58 on BTCUSDT 1h - which is the point.
    """
    from .imbalance import _gap

    return [
        s for s in sweeps
        if event.index - window <= s.index < event.index
        and s.direction == -event.direction
        and any(
            _gap(high, low, mid) == event.direction
            for mid in range(max(s.index, 1), event.index)
        )
    ]


def bias_series(candles: list[Candle], left: int = 2, right: int = 2) -> np.ndarray:
    """Directional bias at every bar, as -1, 0 or +1.

    Zero until the first break, because before that there is nothing to have a
    character, let alone to change it. The value at bar `i` uses only breaks
    that had already happened at `i`, so it is safe to read forward returns from
    it without leaking.
    """
    events, _ = breaks(candles, left, right)
    out = np.zeros(len(candles), dtype=np.int8)
    at = 0
    cursor = 0
    for i in range(len(candles)):
        while cursor < len(events) and events[cursor].index <= i:
            # A sweep is liquidity being taken, not structure giving way, so it
            # must not move the bias. Reading `direction` off every event
            # regardless of kind would let a wick flip the trend.
            if events[cursor].kind != "SWEEP":
                at = events[cursor].direction
            cursor += 1
        out[i] = at
    return out


def _reversed_within(
    candles: list[Candle], event: Break, window: int
) -> int | None:
    """Bars after a sweep until a close came back inside the swept level.

    The count starts at the NEXT bar, not at the sweep itself. A sweep's own bar
    closes inside by construction - that is what makes it a sweep rather than a
    break - so counting it would report 0 on every sweep in existence and
    measure nothing. The question the sources actually ask is whether the
    liquidity taken was then REJECTED, and the answer is a later close.

    None means it never happened inside the window, which covers both a level
    price accepted and a sweep too near the end of the series to have an answer
    yet. Reported, never required: no sweep is dropped for returning None.
    """
    for k in range(1, window + 1):
        j = event.index + k
        if j >= len(candles):
            return None
        close = candles[j].close
        inside = close < event.level if event.direction == 1 else close > event.level
        if inside:
            return k
    return None


def overlay(
    candles: list[Candle], params: StructureParams
) -> tuple[list[SwingPoint], list[StructureEvent], dict[str, float]]:
    """Everything a chart can draw about structure, at both fractal widths.

    Read the module docstring first: this is a FIDELITY drawing and carries no
    direction claim, H6 and H9 having measured that claim and found nothing.

    The two scales are `params.swing_n` and `params.internal_n`, run through the
    same `swings`/`breaks` pass so the drawn objects and the measured ones cannot
    diverge. Every internal event carries `aligned_with_swing`, the crossing
    nobody here had ever made: the swing-scale bias at that same bar, taken from
    `bias_series` so that it uses only breaks already knowable there. A bias of
    0 - no swing-scale break has happened yet - reads None rather than False,
    because False has to keep meaning "the major structure pointed the OTHER
    way". Collapsing the two would let anyone filtering on False collect events
    where there was no major structure to disagree with, and the whole point of
    this field is the disagreement.

    An MSS is paired by `mss_sweeps` above, the single definition tools/mss.py
    imports too: a real break, an OPPOSITE sweep inside `params.mss_window` bars
    before it, and a fair value gap in the leg between them. Its break is emitted
    beside it either way.

    `params.max_events` keeps only the newest events and is applied LAST, after
    every count below is taken. 0 means no cap, and measurement must pass 0: a
    recency cap confines a sample to the tail of the history and has already
    cost this project one round of calibration.
    """
    stats: dict[str, float] = {
        "swings.swing": 0.0, "swings.internal": 0.0, "swings.total": 0.0,
        "events.swing": 0.0, "events.internal": 0.0, "events.total": 0.0,
        "kind.BOS": 0.0, "kind.CHoCH": 0.0, "kind.SWEEP": 0.0, "kind.MSS": 0.0,
        "sweeps.reversed": 0.0, "internal.aligned_with_swing": 0.0,
        "events.dropped_by_cap": 0.0,
    }
    if not candles:
        return [], [], stats

    # Recomputed rather than derived from the events below, because this is the
    # one function that already guarantees bar `i` sees only breaks knowable at
    # `i`, and forking that rule is how a lookahead gets in.
    swing_bias = bias_series(candles, params.swing_n, params.swing_n)
    # Only the wicks, and only for the displacement test in `mss_sweeps`. Built
    # once here rather than per candidate break, which would be quadratic.
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)

    drawn: list[SwingPoint] = []
    events: list[StructureEvent] = []
    # Annotated because the wire models take a Literal, and an unannotated tuple
    # widens to `str`: the type checker is right that nothing otherwise stops a
    # third scale name reaching a field that only permits two.
    scales: tuple[tuple[Literal["swing", "internal"], int], ...] = (
        ("swing", params.swing_n),
        ("internal", params.internal_n),
    )
    for scale, n in scales:
        raw, found = breaks(candles, n, n)
        drawn += [
            SwingPoint(
                time=candles[s.index].time,
                price=s.price,
                high=s.high,
                confirmed_at=candles[s.confirmed_at].time,
                scale=scale,
            )
            for s in found
        ]
        stats[f"swings.{scale}"] = float(len(found))

        sweeps = [e for e in raw if e.kind == "SWEEP"]
        at_scale = 0
        for b in raw:
            event = StructureEvent(
                time=b.time,
                kind=b.kind,
                direction=b.direction,
                level=b.level,
                swing_time=candles[b.swing_index].time,
                bias_before=b.bias_before,
                scale=scale,
                aligned_with_swing=(
                    None
                    if scale == "swing" or swing_bias[b.index] == 0
                    else bool(swing_bias[b.index] == b.direction)
                ),
                reversed_within=(
                    _reversed_within(candles, b, params.sweep_reversal_bars)
                    if b.kind == "SWEEP" else None
                ),
            )
            events.append(event)
            at_scale += 1

            # The MSS pairing, from the shared `mss_sweeps` that tools/mss.py
            # measures with: an OPPOSITE sweep in the preceding window AND a
            # fair value gap in the leg. The nearest qualifying sweep is the one
            # NAMED, which is a display choice - qualifying is `any`, exactly as
            # measured.
            prior = (
                mss_sweeps(high, low, sweeps, b, params.mss_window)
                if b.kind != "SWEEP" else []
            )
            if prior:
                events.append(event.model_copy(update={
                    "kind": "MSS", "swept_at": candles[prior[-1].index].time,
                }))
                at_scale += 1
        stats[f"events.{scale}"] = float(at_scale)

    for kind in ("BOS", "CHoCH", "SWEEP", "MSS"):
        stats[f"kind.{kind}"] = float(sum(e.kind == kind for e in events))
    stats["swings.total"] = float(len(drawn))
    stats["events.total"] = float(len(events))
    stats["sweeps.reversed"] = float(
        sum(e.reversed_within is not None for e in events)
    )
    stats["internal.aligned_with_swing"] = float(
        sum(e.aligned_with_swing is True for e in events)
    )

    drawn.sort(key=lambda s: (s.confirmed_at, s.time))
    events.sort(key=lambda e: e.time)
    kept = events[-params.max_events:] if params.max_events else events
    stats["events.dropped_by_cap"] = float(len(events) - len(kept))
    return drawn, kept, stats
