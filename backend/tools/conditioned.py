"""Does any layer state separate the gate's expectancy? The pre-registered run.

    python -m tools.conditioned --symbol mt5:XAUUSD --interval 1h --bars 50000

THE COLUMN LIST IS CLOSED and lives in `docs/PRAREGISTRASI-KONDISI.md`, written
before this file produced a number. `COLUMNS` below is that list; adding to it
means writing a new pre-registration with a new date, not editing this tuple.

THE THRESHOLD IS COMPUTED, NOT CHOSEN. With `K` groups large enough to judge, a
two-sided alpha of 0.05 is divided by `K` and the critical `t` printed alongside
every row. That ordering matters: the tool counts the groups before it reports
any of them, so the bar cannot be lowered after a row looks interesting. This
project has already shipped one composite that ranked BACKWARDS - AUC 0.464 and
0.477 - and it got there by looking first.

WHAT A PASS MEANS. Three conditions, all stated up front: n >= 30, |t| past the
corrected critical value, and the same sign in both halves of the sample. A row
that clears all three earns a walk-forward run on its subpopulation. It does not
earn a place in `app/plan.py`.
"""

from __future__ import annotations

import argparse
import asyncio
from bisect import bisect_right
from datetime import datetime
from math import erfc, sqrt

import numpy as np

from app.aligned import load_aligned
from app.indicators import wilder_adx, bb_width
from app.cisd import cisds
from app.clock import NY
from app.conditions import at_bar
from app.correlation import correlations
from app.confluence import mark_nesting
from app.dealing_range import mark_dealing_range
from app.detect import DETECTORS
from app.ict import Rules, evaluate
from app.models import SupplyDemandParams
from app.judas import classify as judas_classify
from app.m4 import in_judas_window
from app.poi import confluence, other_boxes
from app.psp import detect as psp_detect
from app.detect.structure import swings
from app.quarters import ALL_DEGREES, true_opens
from app.resample import STEP_UP, resample
from tools import history
from tools.costed import POPULATION, trades
from tools.execute import POI_SLACK_BARS
from tools.quant import TCISD_PARTNER

#: The pre-registered columns. See the doc named in the module docstring.
COLUMNS = (
    "weekday",
    "hour_utc",
    "quarter_day",
    "quarter_session",
    "amd_profile",
    "in_manipulation_quarter",
    "manipulation_done",
    "range_band",
    "dfr_band",
    "bias_1d",
    "bias_4h",
    "bias_1h",
)

#: Kolom modul yatim, praregistrasi KETIGA pada 28 Agustus 2026. Daftarnya ada
#: di `docs/PRAREGISTRASI-YATIM.md` dan ditulis sebelum satu angka pun dihitung.
#: Terpisah dari dua daftar lain untuk alasan yang sama: menggabungkannya akan
#: menyembunyikan pertanyaan mana yang diajukan sebelum jawabannya ada.
#:
#: `app/ladder.py` dihapus 4 September 2026. Ia tabel lookup tanpa input pasar
#: (dinyatakan di praregistrasi), dan nol caller di luar test-nya sendiri.
ORPHAN_COLUMNS = (
    "in_judas_window",
    "judas_template",
    "psp_before_touch",
    "true_opens_in_zone",
    "ote_band",
)


#: The ICT checklist's own clauses, added as a SECOND pre-registration on
#: 2026-08-21. They are listed separately from `COLUMNS` because they were
#: registered later, and merging the two lists would hide which questions were
#: asked before any number existed for them.
#:
#: Every one of these is a clause `app/ict.py` can be told to REQUIRE. This is
#: what turns that switch from a preference into a decision with a figure behind
#: it: a clause that separates earns its place in `--require`, and one that does
#: not stays reported and unenforced.
ICT_COLUMNS = (
    "killzone",
    "discount_or_premium",
    "manipulation_quarter",
    "manipulation_seen",
    "poi_families",
    "poi_clean",
    "cisd_in_band",
    "dfr_side",
    "bias_agrees",
    "htf_nested",
    "poi_family_count",
    "ict_met",
)

#: Kolom korelasi partner, praregistrasi KEEMPAT pada 29 Agustus 2026. Daftarnya
#: ada di `docs/PRAREGISTRASI-KORELASI.md` dan ditulis sebelum satu angka pun
#: dihitung. Satu kolom, daftar tertutup.
#:
#: Terpisah dari tiga daftar lain karena tanggalnya lain, alasan yang sama
#: dengan pemisahan `ORPHAN_COLUMNS`: menggabungkannya akan menyembunyikan
#: pertanyaan mana yang diajukan sebelum jawabannya ada.
CORRELATION_COLUMNS = ("partner_corr_band",)

#: Kolom regime filter, praregistrasi KELIMA pada 4 September 2026. Daftarnya ada
#: di `docs/PRAREGISTRASI-REGIME.md` dan ditulis sebelum satu angka pun dihitung.
REGIME_COLUMNS = ("adx_band", "bb_width_regime")

#: Bar yang masuk jendela korelasi, berakhir di bar keputusan.
#:
#: 200 karena itu `_VOLUME_BASELINE_BARS` di `app/detect/supply_demand.py`, jadi
#: ia konvensi repo ini dan bukan angka baru. Bukan hasil pencarian.
CORR_BARS = 200

MIN_GROUP = 30
ALPHA = 0.05


def _critical_t(groups: int) -> float:
    """The two-sided normal critical value at `ALPHA / groups`.

    Normal rather than Student, and that is the honest simplification: every
    group here has n >= 30 by construction, where the two differ in the third
    decimal. Solved by bisection on `erfc` so this file keeps its no-scipy rule.
    """
    if groups <= 0:
        return float("inf")
    target = ALPHA / groups
    lo, hi = 0.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if erfc(mid / sqrt(2)) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _dfr_band(value: float | None) -> str | None:
    """`dfr_pos` cut into named thirds rather than reported raw.

    A continuous column cannot be grouped, and quartiles of the POPULATION would
    make the bands a function of the sample - so the cuts are the range's own
    geometry: inside it, above it, below it.
    """
    if value is None:
        return None
    if value > 1.0:
        return "above_range"
    if value < 0.0:
        return "below_range"
    return "inside_range"


def _adx_band(value: float) -> str:
    """Wilder's own ADX interpretation: <20 weak, 20-40 trending, >40 strong."""
    if value < 20:
        return "weak"
    if value <= 40:
        return "trending"
    return "strong"


def _bb_regime(bb_arr: np.ndarray, index: int) -> str:
    """BB Width percentile within trailing 200 bars, cut at 20/80 like regime.py."""
    start = max(0, index - CORR_BARS + 1)
    window = bb_arr[start:index + 1]
    if len(window) < 30:
        return "unknown"
    current = bb_arr[index]
    lo = float(np.percentile(window, 20))
    hi = float(np.percentile(window, 80))
    if current < lo:
        return "squeeze"
    if current > hi:
        return "expansion"
    return "normal"


def _partner(symbol: str) -> str:
    """Pasangan SSMT bawaan simbol, dari peta yang sudah ada di repo ini.

    `tools/quant.py:TCISD_PARTNER` adalah satu-satunya peta partner SSMT per
    instrumen yang sudah tertulis, jadi ia yang dipakai apa adanya. Praregistrasi
    Bagian 3 poin 6 melarang memilih partner per run: memilih partner setelah
    melihat hasil adalah pencarian yang menyamar jadi replikasi. Simbol yang
    tidak ada di peta melempar KeyError, karena default diam-diam ke XAGUSD
    adalah pilihan yang menyamar jadi bawaan.
    """
    prefix, sep, bare = symbol.rpartition(":")
    return f"{prefix}{sep}{TCISD_PARTNER[bare.upper()]}"


def _corr_band(
    series: dict[str, list], base: str, times: list[int], at: int
) -> str:
    """Pita nilai absolut korelasi partner pada bar keputusan `at`.

    ANTI-LOOKAHEAD ADA DI `bisect_right`. Grid dipotong di bar keputusan, jadi
    bar sesudahnya tidak pernah masuk jendela walaupun deretnya dipanjangkan.
    `tests/test_corr_lookahead.py` menyuntikkan bar masa depan dan menuntut
    pita-nya tidak berubah; praregistrasi membuang SELURUH run kalau test itu
    gagal, karena angka dari kolom yang melihat masa depan bukan angka yang
    lebih lemah, ia angka yang salah.

    Koefisiennya dari `app/correlation.py` dan bukan implementasi kedua: log
    return, Pearson, dan lantai `MIN_PAIRS` 30 semuanya sudah ditetapkan di
    sana. Di bawah 30 pasang return nilainya `unknown`, dan `unknown` adalah
    pita tersendiri, bukan nol dan bukan dibuang.
    """
    end = bisect_right(times, at)
    window = {s: rows[max(0, end - CORR_BARS):end] for s, rows in series.items()}
    found = correlations(window, base)
    if not found or found[0].full is None:
        return "unknown"
    r = abs(found[0].full)
    if r < 0.30:
        return "<0.30"
    if r < 0.60:
        return "0.30-0.60"
    if r < 0.80:
        return "0.60-0.80"
    return ">=0.80"


def rows_with_state(symbol: str, interval: str, bars: int, flat: bool) -> list[dict]:
    """Every gate-clearing trade, with layer state AND the ICT checklist attached.

    The checklist is evaluated at the TOUCH bar, not at the last bar, and the POI
    stack is capped at that instant. A study that scored the clauses with today's
    boxes would be grading the method on information the trade never had.
    """
    candles = history.load(symbol, interval, bars)
    # PARTNER SSMT PADA GRID IRISAN KETAT, praregistrasi 29 Agustus 2026.
    # `load_aligned` mengembalikan irisan waktu bar tanpa fill dan tanpa
    # interpolasi, dan itu syarat dan bukan optimasi: korelasi atas lubang yang
    # diisi maju adalah korelasi dengan data karangan di dalamnya. Deret ini
    # TERPISAH dari `candles`, jadi tidak ada satu pun detector di bawah yang
    # ikut berubah karena kolom ini ditambahkan.
    aligned, _ = asyncio.run(load_aligned([symbol, _partner(symbol)], interval, bars))
    corr_times = [c.time for c in aligned[symbol]]
    base = [
        r for r in trades("supply_demand", candles, interval, True,
                          symbol=symbol.split(":")[-1], broker="exness_raw",
                          flat_by_rollover=flat)
        if not r["skipped"] and r["cleared"]
    ]
    # The zone objects, indexed by the id the trade rows carry. Re-detected with
    # the same POPULATION params `trades` used, or the ids would not match.
    zones, _ = DETECTORS["supply_demand"](
        candles, SupplyDemandParams(**{**POPULATION, "show_broken": True})
    )
    by_id = {z.id: z for z in zones}
    # NESTING, STAMPED THE SAME WAY THE LIVE SCAN STAMPS IT. The first run of
    # this study measured `htf_nested` False on all 953 trades, which reads as
    # "gold never nests" and was the harness skipping the step: `candidates()`
    # resamples one degree up, detects there, and calls `mark_nesting`, and this
    # file did none of it. Second time the same class of bug has produced a column
    # of False here, after `cisd_levels`.
    #
    # NOT A LOOKAHEAD. `mark_nesting` requires the higher zone to have formed
    # strictly before the local zone's own birth and to still be alive at that
    # bar, so nothing about the future of the trade enters the stamp.
    higher_name = STEP_UP.get(interval)
    if higher_name:
        higher_bars = resample(candles, higher_name, interval)
        higher_zones, _ = DETECTORS["supply_demand"](
            higher_bars, SupplyDemandParams(**{**POPULATION, "show_broken": True})
        )
        for hz in higher_zones:
            hz.timeframe = higher_name
        mark_nesting(zones, higher_zones)
    others = other_boxes(candles)
    times = [c.time for c in candles]
    rules = Rules()
    # CISD LEVELS, and the first run of this study forgot to pass them. The
    # column came back False for all 953 trades, which reads as a market fact and
    # was a harness fact: `confluence` counts what it is given and it was given
    # nothing. Each event carries the bar it became knowable on, so the filter
    # below is a real anti-lookahead cut rather than a formality.
    events, _ = cisds(candles)
    cisd_by_time = sorted((int(e.time), float(e.level)) for e in events)

    # KOLOM MODUL YATIM, praregistrasi 28 Agustus 2026. Semua dihitung sekali
    # untuk deret, bukan sekali per trade, karena semuanya properti bar.
    #
    # `mark_dealing_range` MEMBACA DI SENTUHAN PERTAMA, dan di sini itu instan
    # yang benar: populasi ini memang first touch. Jalur order memakai
    # `mark_dealing_range_now` karena di sana belum ada sentuhan sama sekali.
    mark_dealing_range(zones, candles)
    open_by_time = sorted((int(lv.time), float(lv.price))
                          for lv in true_opens(candles, ALL_DEGREES))
    # Level untuk PSP: ekstrem swing yang sudah confirmed, sama seperti yang
    # dipakai `dealing_range`. PSP menuntut sapuan atas level kunci, dan swing
    # confirmed adalah level kunci yang repo ini sudah punya definisinya.
    high_arr = np.array([c.high for c in candles], dtype=np.float64)
    low_arr = np.array([c.low for c in candles], dtype=np.float64)
    psp_levels = [(s.confirmed_at, float(s.price))
                  for s in swings(high_arr, low_arr, 50, 50)]

    # REGIME COLUMNS, praregistrasi 4 September 2026. Dihitung sekali untuk
    # seluruh deret, dibaca per bar di loop. Anti-lookahead inheren: ADX dan
    # BB Width di bar i hanya memakai bar 0..i.
    close_arr = np.array([c.close for c in candles], dtype=np.float64)
    adx_arr = wilder_adx(high_arr, low_arr, close_arr, 14)
    bb_arr = bb_width(close_arr, 20, 2.0)

    out = []
    for row in base:
        touch = int(row["at"])
        state = at_bar(candles, touch, interval)
        state["dfr_band"] = _dfr_band(state.get("dfr_pos"))
        # Properti bar, bukan properti zona, jadi ia dipasang di luar penjaga
        # `zone is not None` di bawah.
        state["partner_corr_band"] = _corr_band(
            aligned, symbol, corr_times, times[touch]
        )
        state["adx_band"] = _adx_band(float(adx_arr[touch]))
        state["bb_width_regime"] = _bb_regime(bb_arr, touch)
        zone = by_id.get(row["zone_id"])
        if zone is not None:
            anatomy = zone.anatomy
            born_from = times[max(0, anatomy.leg_in_from - POI_SLACK_BARS)]
            born_to = times[min(len(times) - 1, anatomy.leg_out_to + POI_SLACK_BARS)]
            levels = [level for when, level in cisd_by_time if when <= times[touch]]
            stack = confluence(zone, others, times[touch], born_from, born_to,
                               cisd_levels=levels)
            checklist = evaluate(zone, state, stack, rules, at=times[touch])
            for condition in checklist:
                state[condition.name] = condition.met
            state["poi_family_count"] = stack.families

            # ---- kolom praregistrasi 28 Agustus 2026 ----
            when = datetime.fromtimestamp(times[touch], NY)
            state["in_judas_window"] = in_judas_window(when)
            # Bias London hari itu, dibaca dari bar 01:30-07:30 NY yang SUDAH
            # lewat pada bar sentuhan. Tidak ada bar sesudah sentuhan yang
            # ikut, jadi tidak ada hindsight.
            state["judas_template"] = judas_classify(
                *_london_bias(candles, touch)).template
            near = [lv for at, lv in psp_levels if at <= touch]
            state["psp_before_touch"] = bool(near) and psp_detect(
                candles, max(0, touch - 10), near, lookback=10) is not None
            inside = sum(1 for at, price in open_by_time
                         if at <= times[touch] and zone.bottom <= price <= zone.top)
            state["true_opens_in_zone"] = (
                "0" if inside == 0 else "1-3" if inside <= 3
                else "4-9" if inside <= 9 else "10+")
            state["ote_band"] = _ote_band(zone.dealing_range_pos,
                                          zone.side.value)
            # Bucketed, because "how much of the method was satisfied" is the
            # question a reader asks, and 11 separate counts would each be too
            # thin to judge.
            met = sum(1 for c in checklist if c.met is True)
            state["ict_met"] = f"{met // 2 * 2}-{met // 2 * 2 + 1}"
        out.append({**row, "state": state})
    return out


def _ote_band(pos: float | None, side: str) -> str:
    """Pita OTE arah-sadar, definisi yang sama dengan klausa `ote` di `app/ict.py`.

    Demand mau discount dalam 0,214-0,382; supply mau premium dalam 0,618-0,786.
    Satu-satunya definisi OTE di repo ini ada di `app/ict.py`, dan angka di sini
    diambil dari sana apa adanya. `None` berarti tidak ada dealing range, dan ia
    kelompok tersendiri, bukan digabung ke equilibrium.
    """
    if pos is None:
        return "none"
    lo, hi = (0.214, 0.382) if side == "demand" else (0.618, 0.786)
    if lo <= pos <= hi:
        return "ote"
    if pos < 0.5:
        return "discount"
    if pos > 0.5:
        return "premium"
    return "equilibrium"


def _london_bias(candles, touch: int) -> tuple[str, float]:
    """Bias sesi London hari itu dan lebar range-nya, dibaca sebelum `touch`.

    London 01:30-07:30 NY menurut `Buku=Pegangan.txt`. Bar sesudah `touch`
    tidak pernah ikut, jadi tidak ada bar dari masa depan yang menentukan
    template Judas.
    """
    day = datetime.fromtimestamp(candles[touch].time, NY).date()
    session = [c for c in candles[max(0, touch - 200):touch + 1]
               if datetime.fromtimestamp(c.time, NY).date() == day
               and 1 <= datetime.fromtimestamp(c.time, NY).hour < 8]
    if len(session) < 2:
        return "neutral", 0.0
    span = max(c.high for c in session) - min(c.low for c in session)
    move = session[-1].close - session[0].open
    if span <= 0:
        return "neutral", 0.0
    if move > span * 0.25:
        return "bullish", span
    if move < -span * 0.25:
        return "bearish", span
    return "neutral", span


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--bars", type=int, default=50000)
    parser.add_argument("--hold", action="store_true",
                        help="grade on the 80-bar horizon instead of the flat "
                             "rule. The flat rule is the shipped one")
    args = parser.parse_args()

    rows = rows_with_state(args.symbol, args.interval, args.bars, not args.hold)
    if not rows:
        print("no gate-clearing trades in this window")
        return
    everything = np.array([r["r"] for r in rows])
    half = len(rows) // 2
    print(f"{args.symbol} {args.interval} {args.bars} bar, exit "
          f"{'hold 80 bar' if args.hold else 'flat di rollover'}")
    print(f"populasi n={len(rows)}  exp R {everything.mean():+.3f}")

    # COUNTED BEFORE ANYTHING IS REPORTED. The critical value depends on how many
    # groups are judged, so the count has to happen in a first pass or the
    # threshold becomes a function of what the reader has already seen.
    judged = 0
    for column in COLUMNS + ICT_COLUMNS + ORPHAN_COLUMNS + CORRELATION_COLUMNS + REGIME_COLUMNS:
        seen: dict[object, int] = {}
        for row in rows:
            key = row["state"].get(column)
            seen[key] = seen.get(key, 0) + 1
        judged += sum(1 for count in seen.values() if count >= MIN_GROUP)
    critical = _critical_t(judged)
    print(f"{judged} grup layak dinilai, alpha {ALPHA}/{judged} = "
          f"{ALPHA / judged:.5f}, |t| kritis {critical:.2f}\n")

    for column in COLUMNS + ICT_COLUMNS + ORPHAN_COLUMNS + CORRELATION_COLUMNS + REGIME_COLUMNS:
        buckets: dict[object, list[dict]] = {}
        for row in rows:
            buckets.setdefault(row["state"].get(column), []).append(row)
        print(f"-- {column}")
        for key in sorted(buckets, key=lambda k: (k is None, str(k))):
            group = buckets[key]
            values = np.array([r["r"] for r in group])
            if len(group) < MIN_GROUP:
                print(f"   {str(key):18s} n={len(group):4d}  terlalu kecil")
                continue
            # AGAINST THE REST OF THE POPULATION, not against zero. Testing a
            # group against zero answers "is this group profitable", and with the
            # whole population at +0.221 every large group answers yes - the
            # first run of this tool printed LOLOS on BOTH sides of `bias_1d`,
            # which cannot be a separation by anybody's reading. The question in
            # the pre-registration is whether the column SEPARATES, so the null
            # is the complement of the group. Welch, because the two arms have no
            # reason to share a variance.
            rest = np.array([r["r"] for r in rows if r["state"].get(column) != key])
            if len(rest) < MIN_GROUP:
                print(f"   {str(key):18s} n={len(group):4d}  sisanya terlalu kecil")
                continue
            se = sqrt(
                values.var(ddof=1) / len(values) + rest.var(ddof=1) / len(rest)
            )
            delta = values.mean() - rest.mean()
            t = delta / se if se > 0 else float("nan")
            # The halves check is on the DELTA too, for the same reason: a group
            # whose advantage over the rest flips sign between halves has not
            # separated anything, it has taken turns.
            cut = rows[half]["at"]
            deltas = []
            for lo, hi in ((None, cut), (cut, None)):
                inside = np.array([
                    r["r"] for r in group
                    if (lo is None or r["at"] >= lo) and (hi is None or r["at"] < hi)
                ])
                outside = np.array([
                    r["r"] for r in rows
                    if r["state"].get(column) != key
                    and (lo is None or r["at"] >= lo) and (hi is None or r["at"] < hi)
                ])
                deltas.append(
                    inside.mean() - outside.mean()
                    if len(inside) and len(outside) else float("nan")
                )
            halves = (
                f"{deltas[0]:+.3f}/{deltas[1]:+.3f}"
                if not any(np.isnan(deltas)) else "  n/a  "
            )
            same_sign = (
                not any(np.isnan(deltas)) and (deltas[0] > 0) == (deltas[1] > 0)
            )
            verdict = "MEMISAHKAN" if abs(t) >= critical and same_sign else ""
            print(f"   {str(key):18s} n={len(group):4d}  exp R {values.mean():+.3f}"
                  f"  delta {delta:+.3f}  t={t:+6.2f}  paruh {halves}  {verdict}")
        print()


if __name__ == "__main__":
    main()
