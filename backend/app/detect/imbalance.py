"""Fair value gaps and order blocks.

Two more boxes, from the ICT and SMC lineage rather than the Seiden one. They
are here for one reason: this project has a measurement rig that has killed four
plausible findings, and the only honest way to add a detector is to put it
through that rig rather than to ship it and hope.

WHAT THEY ARE, AND HOW FIRM THE DEFINITIONS ARE

**Fair value gap.** The one crisply defined object in the whole SMC vocabulary,
and the only detector here whose rule admits no discretion at all: three
consecutive bars where the first bar's high sits below the third bar's low, or
the first's low above the third's high. The middle bar moved far enough that the
wicks on either side never met, so a band of prices was skipped. The box is that
band. Nothing is chosen, nothing is fitted, and two implementations that read
the definition will produce identical output.

**Order block.** Contested, and the contest matters. The common statement is
"the last opposite-coloured candle before a strong impulsive move". Sources
disagree about (a) whether the move must break structure, (b) whether the box is
the candle's whole range or only its body, and (c) how strong "strong" is. There
is no primary source that settles any of the three. So the choices are stated:
the box is the WHOLE RANGE of the last opposite-coloured candle, the move must
clear `impulse_atr` ATR, and no structure break is required. A structure-break
variant is a different detector and would need its own measurement.

WHY THEY REUSE `Zone`
Both are boxes with a near edge, a far edge and a lifecycle, which is what
`Zone` already models. Inventing a second shape would double the drawing code,
the inspector, and the pixel harness for no gain. The `kind` field says which
detector drew it.

WHAT IS DELIBERATELY NOT HERE
No scoring, no ranking, no composite. The supply/demand detector shipped a score
and had to retract it; starting these two without one is the lesson applied
rather than repeated.

WHERE THIS DEPARTS FROM THE SOURCES, checked 2026-08-15
The primary source for both patterns is a YouTube channel. There is no book, no
paper, no canon, and every written definition in circulation is a third-party
codification of a video. So the departures are listed rather than argued, and
two of them were settled by measurement instead of opinion.

  FVG geometry            NO DEPARTURE. Wick-to-wick, `h1 < l3` or `l1 > h3`,
                          is the consensus and is what the two measured studies
                          test. Body-to-body is a DIFFERENT NAMED PATTERN (a
                          volume imbalance), not a variant of this one.

  no middle-candle test   Some codifications require the middle candle to close
                          in the gap's direction. Measured on 16,693 gaps across
                          four series: that test would reject **12 of them,
                          0.1%**. The departure is real and negligible, and now
                          it is a number rather than an argument.

  min_gap_atr = 0.1       OURS. No primary source has a minimum. Indicator
                          defaults range from 0 (off) to 0.25 x ATR. SWEPT, and
                          the result is worth knowing: the gap-versus-placebo
                          difference is LARGEST with the filter off (+29.1
                          points) and shrinks as the threshold rises (+25.2 at
                          the shipped 0.1, +15.3 at 0.5). So this threshold buys
                          CHART READABILITY and pays for it in measured edge. It
                          is not a quality filter and must not be read as one.
                          Results here are also not comparable to published FVG
                          statistics, which gate nothing at all.

  consequent encroachment ALREADY PRESENT, under another name. The 50% level is
                          the most-cited operational level in this literature.
                          `penetration_pct >= 0.5` is exactly "price traded to
                          the midpoint", and `mitigation_pct` ships at 0.5, so a
                          box in state `mitigated` has by definition reached it.
                          Not added as a separate field, because a second name
                          for one number is how two fields drift apart.

  order block box         Whole high-to-low range. The most common convention,
                          and the WIDEST of three - which mechanically raises
                          the touch rate against a body-only detector, so
                          cross-study comparison is invalid.

  no structure break      NOW OFFERED, still off by default. Contested rule:
                          required by some codifications, "recommended not
                          mandatory" by others, absent from the candle-level
                          definition itself. Since 2026-08-17
                          `require_structure_break` implements the ICT reading -
                          the impulse must CLOSE beyond a swing that was already
                          confirmed when it broke, from `structure.breaks` at
                          `structure_n` either side, within
                          `structure_break_bars` of the block candle, in the
                          impulse's own direction. A SWEEP never qualifies: the
                          sources call it the opposite event, liquidity taken
                          rather than structure giving way, and admitting one
                          would merge the two into one name. The break is
                          recorded on the box in `structure_break_time`, so the
                          claim is auditable bar by bar rather than asserted.
                          Cost, measured with no state filter and no cap on the
                          cached series: PAXGUSDT 1h 3536 blocks become 936
                          (26.5%), BTCUSDT 1h 4045 become 1208 (29.9%), XAUUSD 1h
                          2674 become 741 (27.7%). The gate throws away roughly
                          three blocks in four and RUNS FASTER doing it: 0.48s
                          against 1.01s on 20,000 bars, because 2600 fewer boxes
                          is 2600 fewer lifecycle replays and the structure pass
                          costs less than they did. So nothing about the price
                          argues either way. Whether the survivors are BETTER has
                          not been measured, and until it has, "fewer and
                          stricter" is not a finding.
                          It ships OFF, and the reason is unchanged: the figures
                          usually quoted to justify requiring it (52% against
                          65-68% on 2,400 setups) are UNTRACEABLE - the page they
                          are attributed to contains no statistics at all.
                          Neither camp has evidence, and this project does not
                          ship a gate it has not put through the rig. The excuse
                          for not OFFERING the rule has expired now that
                          app/detect/structure.py computes exactly it; the excuse
                          for not defaulting it on has not.

  displacement as a size  STILL THE TEST, no longer the whole report. Every box
                          from this module now carries a `Displacement`: where
                          the leg ran, its size in ATR, whether it left a fair
                          value gap, and whether it broke structure. That last
                          field is None whenever no structure was computed for
                          the call - which is every call with the gate off - and
                          None is NOT False. What GATES a box is still the size
                          plus the optional break above; the object exists so the
                          two structural properties ICT actually names are
                          readable on the box instead of only in this docstring.
                          `left_gap` uses the SAME wick-to-wick predicate the gap
                          detector uses, `_gap`, because two definitions of a gap
                          in one file is how they drift apart.
                          The object is not free and the price is stated: one per
                          box, plus four gap comparisons, is +12% on the
                          order-block path (1.13s against 1.01s for 3536 boxes on
                          20,000 bars, min of 7 interleaved runs). The population
                          it describes is unchanged, field for field, on the same
                          series.

  1.5 ATR over 5 bars     OURS ENTIRELY. No published ATR multiple exists for
                          "impulsive"; the nearest analogues are "2-3x average
                          candle size" asserted without derivation. Swept: the
                          ATR multiple behaves like the old detector's departure
                          gate - stricter means a wider margin over placebo
                          (+8.3 at 0.5 ATR, +15.5 at the shipped 1.5, +18.9 at
                          2.5) and far fewer boxes (46,868 down to 8,758). The
                          BAR WINDOW barely matters at all: +16.1, +15.5, +15.4
                          for 3, 5 and 10 bars. One invented number that turns
                          out to carry no weight, which is the best thing a
                          sweep can tell you about a number you made up.

  opposite-coloured       Read as `close < open`. Others codify the same phrase
                          as `close < close[1]`, which picks a different candle
                          on inside and outside bars. Nobody resolves it.

WHAT THE MEASURED LITERATURE SAYS, since it bears on how loudly to claim anything
Two studies disclose their method. One tested FVG reaction against a random
placebo on four futures over seven years and found the reaction real - beating
random in 34 of 36 cells by about 5 points - while the tradeable edge was
consumed by costs in 17 of 18 configurations. The other ran 54 mechanical SMC
variations on 2.55 million EURUSD bars and found **none profitable** after half
a pip. Both match the shape of what this project keeps finding on its own
detector: the reaction is real, the edge is not established.
"""

from __future__ import annotations

import numpy as np

from ..indicators import EPS, wilder_atr
from ..models import (
    Anatomy,
    Candle,
    Displacement,
    ImbalanceParams,
    Zone,
    ZoneKind,
    ZoneSide,
    ZoneState,
)
from .structure import breaks
from ..profit_zone import mark_profit_zones
from .supply_demand import cap_per_side, replay_lifecycle


def _arrays(candles: list[Candle]):
    return (
        np.array([c.time for c in candles], dtype=np.int64),
        np.array([c.open for c in candles], dtype=np.float64),
        np.array([c.high for c in candles], dtype=np.float64),
        np.array([c.low for c in candles], dtype=np.float64),
        np.array([c.close for c in candles], dtype=np.float64),
    )


def _gap(high: np.ndarray, low: np.ndarray, mid: int) -> int:
    """Wick-to-wick fair value gap centred on bar `mid`. +1 up, -1 down, 0 none.

    The single definition of a gap in this file. `detect_fvg` reads it to find
    boxes and `detect_order_block` reads it to answer whether its impulse left an
    inefficiency behind; writing the comparison out twice is how the two answers
    would eventually disagree about what a gap is.
    """
    if high[mid - 1] < low[mid + 1]:
        return 1
    if low[mid - 1] > high[mid + 1]:
        return -1
    return 0


def _finish(
    kind: ZoneKind,
    side: ZoneSide,
    top: float,
    bottom: float,
    origin: int,
    born: int,
    time: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    params: ImbalanceParams,
    displacement: float,
    *,
    leg: Displacement | None = None,
    break_time: int | None = None,
) -> Zone | None:
    """Wrap a raw box in the same lifecycle and contract as a supply zone.

    `born` is the bar the box became knowable, and the lifecycle starts on the
    bar AFTER it. Starting on the bar itself would let the candle that created
    the gap count as the first test of it, which is how a detector ends up
    reporting that its own construction touched it.

    `leg` and `break_time` are the described displacement and the structure break
    that qualified the box. Both are keyword-only and default to absent, so the
    one other caller, inversion.py, keeps working unchanged and cannot acquire
    either of them by accident of argument order: an inverted box inherits its
    parent's
    geometry, and describing the parent's leg as the child's would be a claim
    nobody has measured.
    """
    if top - bottom <= EPS:
        return None
    is_demand = side is ZoneSide.DEMAND
    proximal, distal = (top, bottom) if is_demand else (bottom, top)

    life = replay_lifecycle(
        time, high, low, close, atr, top, bottom, distal, is_demand,
        born + 1, params,
    )
    return Zone(
        # No price in the identity - see the note at the matching line in
        # `supply_demand.py`. The ORIGIN bar is what distinguishes the inversion
        # families: fourteen breakers in one fixture share an `inverted_at` and a
        # `time_from`, and only their parent's origin tells them apart, so that is
        # the component that had to survive. Measured: zero collisions across
        # 24,647 fvg, order block, ifvg and breaker boxes on 50,000 bars.
        id=f"{kind.value}-{int(time[origin])}",
        kind=kind,
        side=side,
        state=life.state,
        top=top,
        bottom=bottom,
        proximal=proximal,
        distal=distal,
        time_from=int(time[origin]),
        time_to=(
            int(time[life.break_index]) if life.break_index is not None
            else int(time[-1])
        ),
        formation_score=0.0,  # deliberately unscored, see the module docstring
        departure_atr=round(displacement, 3),
        displacement=leg,
        structure_break_time=break_time,
        touches=life.touches,
        penetration_pct=round(life.penetration, 4),
        first_test_time=life.first_test_time,
        arrival_atr=life.arrival_atr,
        confirmed=born < len(close) - 1,
        # An imbalance has no departure window to wait out - the box is fixed
        # the moment it is knowable - so settled and confirmed coincide here.
        # They are still two fields, because they mean different things and the
        # next detector may well separate them.
        settled=born < len(close) - 1,
        anatomy=Anatomy(
            leg_in_from=origin, leg_in_to=origin,
            base_run_from=origin, base_from=origin, base_to=origin,
            leg_out_from=born, leg_out_to=born,
        ),
        note=f"{kind.value}: displacement {displacement:.1f} ATR, {life.state.value}",
    )


def detect_fvg(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Three bars whose outer wicks never met.

    The gap is knowable when the THIRD bar closes, not when the first one does,
    so that is the bar the lifecycle starts after. Getting this wrong would let
    the middle bar - the one that created the gap by flying through it - be
    counted as having tested it.
    """
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n, "candidates": 0, "rejected_too_small": 0,
        "rejected_state_filter": 0,
    }
    if n < params.atr_period + 3:
        return [], stats

    time, _open, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)

    found: list[Zone] = []
    for i in range(1, n - 1):
        first, third = i - 1, i + 1
        direction = _gap(high, low, i)
        if direction == 0:
            continue
        up = direction == 1
        stats["candidates"] += 1

        top, bottom = (
            (float(low[third]), float(high[first])) if up
            else (float(low[first]), float(high[third]))
        )
        scale = float(atr[max(0, first - 1)])
        if scale <= EPS or (top - bottom) < params.min_gap_atr * scale:
            stats["rejected_too_small"] += 1
            continue

        size = (top - bottom) / scale
        zone = _finish(
            ZoneKind.FVG,
            ZoneSide.DEMAND if up else ZoneSide.SUPPLY,
            top, bottom, first, third,
            time, high, low, close, atr, params,
            size,
            # The three bars ARE the leg here, and the gap IS the inefficiency,
            # so `left_gap` is true by construction rather than by test.
            # `broke_structure` stays None: no structure is computed for gaps at
            # all, and None says "not tested" where False would say "tested and
            # failed". `atr` repeats `departure_atr` on purpose - the scalar
            # remains the gate, the object only describes it.
            leg=Displacement(
                time_from=int(time[first]),
                time_to=int(time[third]),
                atr=round(size, 3),
                left_gap=True,
            ),
        )
        if zone is not None:
            found.append(zone)

    return _present(found, params, stats, int(candles[-1].time) if candles else 0)


def detect_order_block(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """The last opposite-coloured candle before an impulsive move.

    Scanned forward, and the impulse is measured from the block candle's own
    close to the extreme of the `displacement_bars` that follow it. Measuring to
    the end of some later swing instead would make the box depend on where a
    human decided the swing ended, which is the discretion this file exists to
    avoid.

    LAST, and this word used to be a lie. Until 2026-08-16 the scan marked EVERY
    opposite-coloured candle whose forward window cleared the threshold, so a run
    of three bearish candles before a rally produced three order blocks stacked
    on each other, all sharing one impulse. The docstring said "last" and the
    code said "any". It showed in the population: 21565 order blocks against
    12745 fair value gaps on identical bars, with the surplus being the same
    observation counted several times - which inflates n, correlates outcomes,
    and makes every order block statistic rest on a smaller effective sample
    than it claims.

    Last is now enforced the only way that needs no discretion: the very next
    candle must close the other way, because that candle is the start of the
    impulse. In a run of three bearish candles only the third has a bullish
    successor.

    STRUCTURE, opt-in. With `require_structure_break` the impulse must also close
    beyond a confirmed swing - the ICT requirement this detector shipped without
    for a year. Off by default and for a stated reason; read the module
    docstring's departure list before turning it on or reading anything into it.
    """
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n, "candidates": 0, "rejected_weak_move": 0,
        "rejected_not_last": 0, "rejected_no_structure_break": 0,
        "rejected_state_filter": 0,
    }
    if n < params.atr_period + params.displacement_bars + 2:
        return [], stats

    time, open_, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)

    # Structure only when the gate asks for it. It is a second full pass over the
    # bars - fractal swings plus a forward walk - and paying for it on every call
    # would buy nothing for the default path, which is why `broke_structure` is
    # None rather than False there. None means NOT TESTED.
    #
    # SWEEPs are dropped at the door instead of at the test below. A sweep is a
    # wick through a level that closed back inside: the sources read it as
    # liquidity taken, the OPPOSITE event to structure giving way, so it can
    # never qualify a block and must not be one dropped `if` away from doing so.
    breaks_at: dict[int, list] = {}
    if params.require_structure_break:
        for event in breaks(candles, params.structure_n, params.structure_n)[0]:
            if event.kind != "SWEEP":
                breaks_at.setdefault(event.index, []).append(event)

    found: list[Zone] = []
    for i in range(1, n - params.displacement_bars - 1):
        scale = float(atr[max(0, i - 1)])
        if scale <= EPS:
            continue
        bearish = close[i] < open_[i]
        window = slice(i + 1, i + 1 + params.displacement_bars)

        # A bearish candle before an up move is a bullish block, and the
        # reverse. Both directions are checked on every bar rather than one
        # being inferred from the other, because a doji satisfies neither.
        if bearish:
            move = (float(high[window].max()) - float(close[i])) / scale
            side = ZoneSide.DEMAND
        elif close[i] > open_[i]:
            move = (float(close[i]) - float(low[window].min())) / scale
            side = ZoneSide.SUPPLY
        else:
            continue

        stats["candidates"] += 1
        if move < params.displacement_atr:
            stats["rejected_weak_move"] += 1
            continue

        # The "last" in the definition, tested AFTER the impulse because the
        # impulse is the requirement and "last" only decides which candle gets
        # the box. Ordered the other way, a chart with no impulse anywhere would
        # report its rejections under the wrong reason.
        #
        # The next candle has to close the other way, because that candle is the
        # move starting - which is exactly what makes this one the final candle
        # of its colour before it. A doji successor counts as neither and is
        # rejected, the same way a doji block candle is rejected above.
        nxt = i + 1
        turned = close[nxt] > open_[nxt] if bearish else close[nxt] < open_[nxt]
        if not turned:
            stats["rejected_not_last"] += 1
            continue

        # The structural test, LAST of the three so each rejection lands under
        # the reason that actually fired. A block with no impulse is not reported
        # as a block that failed to break structure.
        #
        # `impulse` is the direction the move ran, which is the direction the
        # break must have: a bearish block precedes an UP move, and a break
        # downward inside that window is a different event about a different
        # level. The window is the bars AFTER the block candle - the impulse is
        # what has to do the breaking, not the block candle itself - and it stops
        # at `structure_break_bars`, which is as far forward as this detector is
        # allowed to look. `breaks()` supplies the rest of the honesty: it tests
        # only against swings whose `confirmed_at` had already passed, so no
        # break here knows about a pivot nobody could see yet.
        impulse = 1 if bearish else -1
        born = i + params.displacement_bars
        break_time = None
        if params.require_structure_break:
            hit = next(
                (
                    e
                    for k in range(1, params.structure_break_bars + 1)
                    for e in breaks_at.get(i + k, ())
                    if e.direction == impulse
                ),
                None,
            )
            if hit is None:
                stats["rejected_no_structure_break"] += 1
                continue
            # A box is not knowable before the evidence that admitted it. With
            # the default windows the break lands inside the impulse window and
            # this changes nothing; with `structure_break_bars` set wider than
            # `displacement_bars` it is the difference between a lifecycle that
            # starts after the box exists and one that starts before.
            break_time, born = hit.time, max(born, hit.index)

        zone = _finish(
            ZoneKind.OB, side, float(high[i]), float(low[i]), i,
            born,
            time, high, low, close, atr, params, move,
            leg=Displacement(
                time_from=int(time[nxt]),
                time_to=int(time[i + params.displacement_bars]),
                atr=round(move, 3),
                # None with the gate off, and True with it on because a block
                # that did not break structure never reaches this line. False is
                # therefore unreachable here by construction, not by omission:
                # answering False would require measuring structure on the
                # default path, which costs a second pass for a field nothing
                # currently reads.
                broke_structure=True if params.require_structure_break else None,
                # The same wick-to-wick rule the gap detector uses, asked of the
                # impulse instead of a standalone triple. Centres run to
                # `displacement_bars - 1` so the third bar of any gap is at most
                # the bar the box became knowable on - one bar further and the
                # box would be describing a candle that had not printed yet. A
                # gap the other way is not this leg's inefficiency.
                left_gap=any(
                    _gap(high, low, m) == impulse
                    for m in range(nxt, i + params.displacement_bars)
                ),
            ),
            break_time=break_time,
        )
        if zone is not None:
            found.append(zone)

    return _present(found, params, stats, int(candles[-1].time) if candles else 0)


def _present(
    found: list[Zone], params: ImbalanceParams, stats: dict[str, float],
    now: int = 0,
) -> tuple[list[Zone], dict[str, float]]:
    """State filter, the two cross-zone passes, and the per-side cap.

    `now` ADALAH KENAPA FUNGSI INI PUNYA PARAMETER KETIGA, dan ia ditambahkan
    2 September 2026 untuk menutup cacat yang menutup jalur order bagi SETIAP
    detektor ICT. `plan.build` mengambil target dari `zone.profit_zone_rr`;
    field itu diisi `mark_profit_zones`, dan sampai hari itu fungsi tersebut
    dipanggil HANYA di `supply_demand.py:673` dan di jalur refinement
    `drawing.py:401`. Tidak satu pun menyentuh modul ini.
    ORDER PATH BUKAN CUMA LEBIH SULIT UNTUK ICT, IA TERTUTUP. `tools/execute.py`
    mensyaratkan target yang terbaca, jadi zona ICT yang lolos gerbang departure
    DAN masih fresh tetap tidak pernah jadi kandidat. Diukur di empat kombinasi
    simbol-timeframe pada 2 September 2026: 7, 10, 4 dan 8 zona ICT lolos
    gerbang dan fresh, dan NOL dari semuanya punya target, sementara setiap zona
    supply_demand yang lolos gerbang dan fresh punya.
    Yang paling mahal dari itu: `fvg` dan `order_block` adalah dua detektor
    dengan bukti TERKUAT di repo ini - +10 sampai +25 poin lawan placebo dengan
    walk-forward 8 dari 8 di dua geometri - dan keduanya tepat yang tidak bisa
    diorder. Klaim `supply_demand` lebih lemah: ia mengalahkan TIDAK ADA box,
    bukan placebo di jarak yang disamakan.
    DINDINGNYA SE-DETEKTOR, sama seperti supply_demand. `mark_profit_zones`
    mencari zona lawan terdekat di dalam DAFTAR YANG DIBERIKAN, dan daftar di
    sini hanya zona modul ini. Jadi dinding sebuah FVG adalah FVG lawan
    terdekat, bukan order block terdekat. Itu batasan yang sama yang sudah
    dipegang supply_demand sejak awal, dan menyatukan daftarnya adalah
    perubahan doktrin yang butuh pengukurannya sendiri.
    `now` default 0 supaya pemanggil lama tidak pecah, dan 0 berarti kedua pass
    dilewati - bukan berarti dijalankan dengan waktu nol, yang akan menyatakan
    setiap zona belum lahir.

    Deliberately the same shape as the supply/demand detector's tail, including
    that zero disables the cap. A measurement taken through a recency cap is a
    measurement of the tail of the history, and that mistake has already cost
    this project one full round of calibration.

    NO overlap merge here, and that is a decision rather than an omission. It
    was tried: reusing supply and demand's `_dedupe` cut same-side overlaps by
    74%, and it was reverted the same hour because it was removing real objects.

    THE REASON THAT STILL STANDS: two gaps at different bars are two events, not
    one drawn twice, and ICT treats stacked gaps as meaningful. That is true
    whatever `_dedupe` ranks by, and it alone is enough to keep the merge out.

    What no longer holds is the mechanism the revert was blamed on at the time.
    `_dedupe` then tiebroke on `formation_score`, which is 0.0 for every zone
    this module builds, so the winner was whatever happened to sort first: on
    one test that meant keeping a 0.3-wide sliver and discarding the 4.5-wide
    gap containing it. It tiebreaks on `departure_atr` now, and every zone built
    here carries a real displacement in that field, so a reader must not
    conclude the survivor would still be arbitrary. It would be the widest
    displacement, a defensible pick. The merge stays out on the paragraph above
    instead, which is the half of the argument that was never about sort order.

    The redundancy the merge was hiding was real, but its cause was the order
    block detector marking EVERY opposite candle instead of the last one. That
    is fixed at the source in `detect_order_block`.
    """
    allowed = {ZoneState.FRESH, ZoneState.TESTED}
    if params.show_mitigated:
        allowed.add(ZoneState.MITIGATED)
    if params.show_broken:
        allowed.add(ZoneState.BROKEN)
    visible = [z for z in found if z.state in allowed]
    stats["rejected_state_filter"] = len(found) - len(visible)

    # SETELAH filter state, SEBELUM cap, urutan yang sama dengan
    # `supply_demand.py`. Sebuah dinding yang chart-nya tidak punya ruang untuk
    # menggambar tetap dinding, dan mengukur jalan terhadap subset yang tergambar
    # membuatnya terlihat lebih panjang tepat sebesar apa yang cap buang.
    # HANYA `mark_profit_zones`, BUKAN `mark_crowding`. Yang kedua butuh
    # `min_profit_zone_rr`, dan `ImbalanceParams` tidak punya field itu -
    # menambahkannya berarti menambah knob yang belum pernah diukur untuk
    # menyelesaikan masalah yang berbeda. `crowded_at` karena itu tetap None di
    # zona ICT, sama seperti sebelum perubahan ini, dan itu tidak mengubah apa
    # pun yang teramati: diukur 2 September 2026 di empat kind, NOL dari 40 zona
    # punya `crowded_at` terisi.
    if visible and now > 0:
        mark_profit_zones(visible, now)

    result = cap_per_side(visible, params.max_zones_per_side)
    stats["zones"] = len(result)
    stats["found_demand"] = sum(1 for z in found if z.side is ZoneSide.DEMAND)
    stats["found_supply"] = len(found) - stats["found_demand"]
    return result, stats
