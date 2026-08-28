"""The ICT dealing range reading, on series whose correct answer is arithmetic.

`dealing_range_pos` is the deviation docs/FIDELITY.md named: `curve` measures a
200-bar rolling window split in thirds and freezes it at the zone's birth, while
ICT reads premium/discount on a swing-to-swing range at the moment price arrives.
The two coexist and disagree by construction, so nothing here touches `curve`.

The test that matters most is the third one. The range must be knowable at the
touch bar, which means a swing that confirms after the touch may not be used; a
reading that used it would look excellent and be made entirely of the future.
It is asserted directly - the answer on the truncated series must equal the answer
on the full one - rather than trusted.

Nothing here tests whether the field predicts anything. It is reported, not
scored, and the docstring says why: the Seiden version of the same idea measured
unproven, and its raw value was an artefact of drift that only a per-side split
exposed.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_dealing_range.py -q
"""

from __future__ import annotations

import numpy as np

from app.dealing_range import mark_dealing_range, mark_dealing_range_now
from app.detect.structure import swings
from app.models import Anatomy, Candle, Zone, ZoneKind, ZoneSide, ZoneState

STEP = 900
T0 = 1_700_000_000 // 86_400 * 86_400
N = 2  # fractal width, so a hand-built fixture is long enough to confirm swings

ANATOMY = Anatomy(
    leg_in_from=0, leg_in_to=1, base_run_from=2, base_from=2, base_to=3,
    leg_out_from=4, leg_out_to=5,
)


def bar(t: int, o: float, c: float, hp: float = 0.0, lp: float = 0.0) -> Candle:
    return Candle(
        time=t, open=o, close=c, high=max(o, c) + hp, low=min(o, c) - lp, volume=1000.0
    )


def wave(points: list[float], per: int = 4) -> list[Candle]:
    """A zigzag through `points`. No wicks, so the pivot prices are the points."""
    rows: list[Candle] = []
    t = T0
    for a, b in zip(points, points[1:]):
        for k in range(per):
            o = a + (b - a) * k / per
            rows.append(bar(t, o, a + (b - a) * (k + 1) / per))
            t += STEP
    return rows


def zone(
    side: ZoneSide,
    proximal: float,
    height: float,
    touched_at: int | None,
) -> Zone:
    """A zone reduced to the fields this pass reads: side, proximal, first touch."""
    top, bottom = (
        (proximal, proximal - height)
        if side is ZoneSide.DEMAND
        else (proximal + height, proximal)
    )
    return Zone(
        id=f"{side.value}-{proximal}",
        kind=ZoneKind.RBR if side is ZoneSide.DEMAND else ZoneKind.DBD,
        side=side,
        state=ZoneState.FRESH if touched_at is None else ZoneState.TESTED,
        top=top,
        bottom=bottom,
        proximal=proximal,
        distal=bottom if side is ZoneSide.DEMAND else top,
        time_from=T0,
        time_to=T0 + 10_000 * STEP,
        formation_score=0.5,
        departure_atr=3.0,
        first_test_time=touched_at,
        anatomy=ANATOMY,
    )


def confirmed_range(rows: list[Candle], bar_index: int) -> tuple[float, float]:
    """The last confirmed swing high and low as of `bar_index`, computed here
    independently of the module under test so a fixture can be checked."""
    high = np.array([c.high for c in rows], dtype=np.float64)
    low = np.array([c.low for c in rows], dtype=np.float64)
    seen = [s for s in swings(high, low, N, N) if s.confirmed_at <= bar_index]
    return (
        [s.price for s in seen if s.high][-1],
        [s.price for s in seen if not s.high][-1],
    )


# --------------------------------------------------------------------------
# Read at the arrival, or not at all
# --------------------------------------------------------------------------


def test_an_untouched_zone_gets_no_reading_because_it_has_no_arrival_to_read_at():
    """ICT reads premium/discount when price ARRIVES. A zone price never reached
    has no such moment, and reading it at the zone's birth instead would silently
    turn this field into a second copy of `curve`."""
    rows = wave([100, 110, 100, 110])
    fresh = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=None)

    stats = mark_dealing_range([fresh], rows, swing_n=N)

    assert fresh.dealing_range_pos is None
    assert stats["untouched"] == 1.0
    assert stats["marked"] == 0.0


def test_the_reading_is_taken_at_the_first_touch_and_not_at_the_last_bar():
    """Two zones with identical geometry and different touch times must read
    differently once the range has moved between them. If they agree, the pass is
    reading some fixed bar instead of each zone's own arrival."""
    rows = wave([100, 110, 100, 110]) + wave([110, 130, 110], per=4)[1:]
    for k, row in enumerate(rows):  # re-time the spliced tail onto one grid
        rows[k] = row.model_copy(update={"time": T0 + k * STEP})

    early = rows[10].time
    late = rows[-1].time
    first = zone(ZoneSide.DEMAND, 110.0, 2.0, touched_at=early)
    second = zone(ZoneSide.DEMAND, 110.0, 2.0, touched_at=late)

    mark_dealing_range([first, second], rows, swing_n=N)

    assert confirmed_range(rows, 10) != confirmed_range(rows, len(rows) - 1)
    assert first.dealing_range_pos != second.dealing_range_pos


# --------------------------------------------------------------------------
# The one rule that makes it a measurement rather than a fiction
# --------------------------------------------------------------------------


def test_a_swing_confirmed_after_the_touch_bar_is_not_used():
    """The anti-lookahead property, asserted directly: truncating the series at
    the touch bar must not change the answer.

    The fixture is built so that hindsight would be visible. After the touch the
    series runs up to 130 and pivots there, which widens the range from 10 points
    to 30 - a zone at 110 reads 1.0 on the range that was knowable and 0.333 on
    the one that was not."""
    rows = wave([100, 110, 100, 110]) + wave([110, 130, 110], per=4)[1:]
    for k, row in enumerate(rows):
        rows[k] = row.model_copy(update={"time": T0 + k * STEP})
    touch_bar = 10

    high = np.array([c.high for c in rows], dtype=np.float64)
    low = np.array([c.low for c in rows], dtype=np.float64)
    later = [s for s in swings(high, low, N, N) if s.confirmed_at > touch_bar]
    assert later, "fixture proves nothing unless a swing confirms after the touch"
    assert max(s.price for s in later) == 130.0

    full = zone(ZoneSide.DEMAND, 110.0, 2.0, touched_at=rows[touch_bar].time)
    truncated = zone(ZoneSide.DEMAND, 110.0, 2.0, touched_at=rows[touch_bar].time)

    mark_dealing_range([full], rows, swing_n=N)
    mark_dealing_range([truncated], rows[: touch_bar + 1], swing_n=N)

    assert full.dealing_range_pos == truncated.dealing_range_pos == 1.0
    assert full.dealing_range_pos != round((110.0 - 100.0) / 30.0, 3)


# --------------------------------------------------------------------------
# The scale: 0 at the low, 1 at the high, both sides alike
# --------------------------------------------------------------------------


def test_a_zone_at_the_range_low_reads_zero_and_one_at_the_high_on_both_sides():
    """The scale is the range, not the zone, so the two sides share it. Note the
    proximal line is what is measured: the demand zone at the top reads 1.0 even
    though its distal sits two points lower."""
    rows = wave([100, 110, 100, 110])
    touched = rows[10].time
    assert confirmed_range(rows, 10) == (110.0, 100.0)

    zones = [
        zone(ZoneSide.DEMAND, 100.0, 2.0, touched),
        zone(ZoneSide.DEMAND, 110.0, 2.0, touched),
        zone(ZoneSide.SUPPLY, 100.0, 2.0, touched),
        zone(ZoneSide.SUPPLY, 110.0, 2.0, touched),
        zone(ZoneSide.DEMAND, 105.0, 2.0, touched),
    ]

    stats = mark_dealing_range(zones, rows, swing_n=N)

    assert [z.dealing_range_pos for z in zones] == [0.0, 1.0, 0.0, 1.0, 0.5]
    assert stats["marked"] == 5.0
    assert stats["marked.demand"] == 3.0
    assert stats["marked.supply"] == 2.0


def test_a_zone_outside_the_range_is_clipped_rather_than_reported_beyond_it():
    """Price can leave the range it was last dealing in. 0 and 1 are the ends of
    the interval the doctrine names, so beyond them there is nothing further to
    say, and a negative premium would read as a number rather than as an edge."""
    rows = wave([100, 110, 100, 110])
    touched = rows[10].time
    below = zone(ZoneSide.DEMAND, 80.0, 2.0, touched)
    above = zone(ZoneSide.SUPPLY, 140.0, 2.0, touched)

    mark_dealing_range([below, above], rows, swing_n=N)

    assert (below.dealing_range_pos, above.dealing_range_pos) == (0.0, 1.0)


# --------------------------------------------------------------------------
# When there is no range, say so
# --------------------------------------------------------------------------


def test_a_range_with_no_height_gets_no_reading_rather_than_a_midpoint():
    """A rise that wicked up to 100 early and back down to 100 later leaves the
    last confirmed high and the last confirmed low at the same price. Dividing by
    that would be a zero-division; substituting 0.5 would be worse, because an
    invented midpoint is indistinguishable from a measured one."""
    rows = [bar(T0 + i * STEP, 89.0 + i, 90.0 + i) for i in range(24)]
    rows[5] = bar(rows[5].time, 94.0, 95.0, hp=5.0)  # wick up to 100
    rows[14] = bar(rows[14].time, 103.0, 104.0, lp=3.0)  # wick down to 100
    assert confirmed_range(rows, 20) == (100.0, 100.0)

    flat = zone(ZoneSide.DEMAND, 102.0, 2.0, touched_at=rows[20].time)

    stats = mark_dealing_range([flat], rows, swing_n=N)

    assert flat.dealing_range_pos is None
    assert stats["no_range"] == 1.0


def test_a_series_too_short_to_confirm_a_swing_gets_no_reading():
    """At the shipped `swing_n` of 50 a 500-bar chart confirms its first swing
    only at bar 100, so early zones legitimately have no dealing range. That is
    an absence, and it is reported as one."""
    rows = wave([100, 110], per=4)
    touched = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=rows[-1].time)

    stats = mark_dealing_range([touched], rows, swing_n=50)

    assert touched.dealing_range_pos is None
    assert stats["no_range"] == 1.0


def test_a_touch_before_the_first_candle_is_counted_not_averaged_over():
    """Zones paired with candles they did not come from. The pass cannot read a
    range at a bar it does not have, and a caller who made that mistake needs to
    see it in the stats rather than in a silently empty column."""
    rows = wave([100, 110, 100, 110])
    stray = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=T0 - 10 * STEP)

    stats = mark_dealing_range([stray], rows, swing_n=N)

    assert stray.dealing_range_pos is None
    assert stats["off_series"] == 1.0


def test_a_previous_reading_is_cleared_when_it_can_no_longer_be_made():
    """The pass is re-run whenever the zone set changes, exactly like
    `mark_profit_zones`. A stale value left behind from an earlier run would
    outlive the range that produced it."""
    rows = wave([100, 110, 100, 110])
    stale = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=rows[10].time)
    mark_dealing_range([stale], rows, swing_n=N)
    assert stale.dealing_range_pos == 0.5

    stale.first_test_time = None
    mark_dealing_range([stale], rows, swing_n=N)

    assert stale.dealing_range_pos is None


# --------------------------------------------------------------------------
# The second instant: the decision bar, for a zone that has no arrival yet
# --------------------------------------------------------------------------


def test_the_decision_bar_reading_exists_exactly_where_the_arrival_reading_cannot():
    """Satu zona, satu deret, dua stamper, dua jawaban yang berbeda dan benar.

    Ini pasangan dari test untouched di atas, dan alasannya operasional.
    `tools/execute.py:candidates` menyimpan HANYA zona yang `first_test_time`-nya
    None, karena populasi terukur adalah first touch. Jadi `mark_dealing_range`
    menstempel None pada setiap kandidat order yang pernah dilewatkannya, dan
    klausa `ote` menjawab "no dealing range" selamanya. Terukur 28 Agustus 2026
    pada jalur order sungguhan: 23 dari 23 kandidat.

    Yang dijaga di sini bukan sebuah angka melainkan sebuah keberadaan: jalur
    order harus punya bacaan, dan jalur pengukuran harus tetap tidak punya.
    """
    rows = wave([100, 110, 100, 110])
    fresh = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=None)

    at_touch = mark_dealing_range([fresh], rows, swing_n=N)
    assert fresh.dealing_range_pos is None, "instan sentuhan tidak boleh berubah"
    assert at_touch["untouched"] == 1.0

    at_now = mark_dealing_range_now([fresh], rows, swing_n=N)
    assert fresh.dealing_range_pos is not None, (
        "tanpa bacaan di bar keputusan, klausa ote tidak pernah bisa lolos"
    )
    assert at_now["marked"] == 1.0
    assert at_now["marked.demand"] == 1.0


def test_the_decision_bar_reading_uses_the_range_confirmed_at_the_last_bar():
    """Angkanya, bukan cuma keberadaannya, dan dihitung ulang di luar modulnya.

    `confirmed_range` mengulang aritmetikanya dari `swings` secara independen,
    jadi kalau stamper diam-diam memakai swing yang belum confirmed, atau
    memakai distal alih-alih proximal, angka di bawah tidak akan cocok.
    """
    rows = wave([100, 110, 100, 110])
    hi, lo = confirmed_range(rows, len(rows) - 1)
    proximal = lo + (hi - lo) * 0.30
    fresh = zone(ZoneSide.DEMAND, proximal, 1.0, touched_at=None)

    mark_dealing_range_now([fresh], rows, swing_n=N)

    assert fresh.dealing_range_pos == round((proximal - lo) / (hi - lo), 3)
    assert 0.214 <= fresh.dealing_range_pos <= 0.382, (
        "0.30 harus jatuh di dalam band OTE demand, atau test ini tidak menguji "
        "apa pun tentang ote"
    )


def test_the_decision_bar_reading_never_uses_a_swing_confirmed_after_the_last_bar():
    """Aturan knowability diwarisi dari `range_at`, dan diperiksa bukan dipercaya.

    Ini satu-satunya hal yang berdiri antara bacaan ini dan hindsight, dan
    project ini sudah pernah menangkap dirinya sendiri melakukannya. Deret yang
    dipotong lebih pendek tidak boleh menghasilkan angka yang seolah tahu bar
    yang dipotong itu.
    """
    rows = wave([100, 110, 100, 110, 100, 140, 100])
    short = rows[: len(rows) - 2 * N]

    hi_short, lo_short = confirmed_range(short, len(short) - 1)
    hi_full, lo_full = confirmed_range(rows, len(rows) - 1)
    # PRASYARAT FIXTURE, ditegaskan supaya test ini tidak lulus dengan sia-sia.
    # Kalau kedua range kebetulan sama, assertion di bawah tidak menguji apa pun:
    # versi pertama test ini memakai wave yang range-nya 100-110 di KEDUA
    # potongan, jadi 105 terbaca 0,5 dua kali dan "berbeda" mustahil.
    assert (hi_short, lo_short) != (hi_full, lo_full), (hi_short, hi_full)

    a = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=None)
    b = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=None)
    mark_dealing_range_now([a], short, swing_n=N)
    mark_dealing_range_now([b], rows, swing_n=N)

    assert a.dealing_range_pos == round((105.0 - lo_short) / (hi_short - lo_short), 3)
    assert b.dealing_range_pos == round((105.0 - lo_full) / (hi_full - lo_full), 3)
    assert a.dealing_range_pos != b.dealing_range_pos, (
        "deret pendek dan deret panjang memberi angka sama: stamper membaca "
        "range yang belum knowable di bar terakhir deret pendek"
    )


def test_a_decision_bar_range_with_no_height_gets_no_reading_rather_than_a_midpoint():
    """Aturan yang sama dengan instan sentuhan: 0.5 karangan dilarang.

    Deret yang terlalu pendek untuk mengonfirmasi swing tidak punya range, dan
    sebuah midpoint yang disubstitusikan tidak bisa dibedakan dari yang terukur.
    """
    rows = wave([100, 110], per=2)[: N]
    fresh = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=None)

    stats = mark_dealing_range_now([fresh], rows, swing_n=N)

    assert fresh.dealing_range_pos is None
    assert stats["no_range"] == 1.0
    assert stats["marked"] == 0.0


def test_an_empty_series_clears_the_stamp_instead_of_raising():
    """Nol bar adalah kondisi nyata di hari libur, dan ia harus jadi None."""
    fresh = zone(ZoneSide.DEMAND, 105.0, 2.0, touched_at=None)
    fresh.dealing_range_pos = 0.42

    stats = mark_dealing_range_now([fresh], [], swing_n=N)

    assert fresh.dealing_range_pos is None
    assert stats["no_bars"] == 1.0


def test_the_order_path_default_matches_the_structure_layer_default():
    """Dua default `swing_n` di dua file, dan gridnya harus tetap satu.

    Yang dilihat operator dan yang dinilai engine dibangun dari primitif yang
    sama tapi lewat jalan berbeda. Chart memakai `StructureParams.swing_n` yang
    bisa diubah dari UI; jalur order memanggil `mark_dealing_range_now(zones,
    candles)` tanpa argumen, jadi ia selalu memakai default modul ini.

    Diukur 28 Agustus 2026 pada XAUUSD 1h, 3000 bar, ketiganya cocok persis
    selama nilainya sama:

        swing_n=20  grid 4605.310 -> 4697.152   range 4605.310 -> 4697.152
        swing_n=50  grid 4324.467 -> 4697.152   range 4324.467 -> 4697.152
        swing_n=80  grid 4310.912 -> 4449.863   range 4310.912 -> 4449.863

    Jadi satu-satunya cara keduanya berpisah adalah kedua DEFAULT itu bergeser
    sendiri-sendiri. Kalau itu terjadi, operator menatap satu grid sementara
    klausa `ote` memutuskan di grid lain, dan tidak ada apa pun yang akan
    mengatakannya. Test ini yang mengatakannya.

    Ia TIDAK menuntut UI dan daemon selalu memakai angka yang sama saat
    dijalankan: daemon sengaja tidak membaca input UI, properti keamanan yang
    sama dengan saklar auto-trade. Yang dijaga cuma default-nya.
    """
    import inspect

    from app.models.params import StructureParams
    from app.dealing_range import mark_dealing_range_now

    ui = StructureParams().swing_n
    order_path = inspect.signature(mark_dealing_range_now).parameters["swing_n"].default

    assert order_path == ui, (
        f"default berpisah: chart menggambar pada swing_n={ui}, klausa ote "
        f"menilai pada swing_n={order_path}. Operator akan membaca satu grid "
        f"dan engine memutuskan di grid lain."
    )
