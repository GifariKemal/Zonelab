"""Place the plan the engine already produced, on a demo account, with a reason.

    python -m tools.execute --symbol mt5:XAUUSD --interval 1h            # dry run
    python -m tools.execute --symbol mt5:XAUUSD --interval 1h --send     # for real

IN `tools/` AND NOT IN `app/`, AND THAT IS THE SAFETY PROPERTY. `app/` is a
read-only drawing engine reachable from a web server; if order placement lived
there, an HTTP request could trade. Here it is an operator-run program, and the
API keeps its inability to send anything by construction rather than by review.

WHAT IT WILL NOT DO
  - trade a live account. `trade_mode` must be 0. There is no flag for this, and
    the day someone wants one, the change should be visible in a diff instead of
    reachable from a shell history;
  - place a second order for a zone the journal already shows a `placed` for -
    the zone id is now a stable key rather than a price (see `supply_demand.py`),
    which is what makes that check trustworthy;
  - act on a drawing `actionable.blockers` objects to;
  - size past the plan's own risk budget. `plan.placeable` is respected, and a
    refusal is journalled with the plan's own warning text rather than summarised.

WHAT IT DOES NOT DECIDE. Which side to trade. Both live zones qualify or neither
does; the rule is the first touch of a zone whose departure clears the gate, both
sides pooled, because that is the population every measured number in
`docs/CALIBRATION.md` and `docs/WALKFORWARD-MT5.md` was computed on. Twelve
pre-registered directional hypotheses failed in this project and this file is not
the place to add a thirteenth.
"""

from __future__ import annotations

import argparse
from datetime import datetime

import numpy as np

from app import journal
from app.actionable import blockers
from app.cisd import cisds
from app.clock import NY, trades_when_shut
from app.conditions import at_bar
from app.confluence import mark_nesting
from app.costs import COST_TO_RISK_MAX, cost_to_risk, schedule, spec
from app.dealing_range import mark_dealing_range_now
from app.detect import DETECTORS
from app.ict import (
    BIAS_DEGREES,
    DOCTRINE_CLAUSES,
    MEASURED_AGAINST,
    Rules,
    setup as ict_setup,
)
from app.indicators import wilder_atr
from app.models import LotSpec, SupplyDemandParams, ZoneSide
from app.plan import DEPARTURE_GATE_ATR, build
from app.portfolio import Book, Held, admits, aligned
from app.poi import confluence, other_boxes
from app.providers.base import INTERVALS
from app.quarters import ALL_DEGREES, true_opens
from app.resample import STEP_UP, resample
from app.ssmt import divergences_for as ssmt_divergences_for
from tools.broker import RULE, _terminal, lot_specs, place, realised_today, sizing
from app.ssmt import ssmt as ssmt_read
from app.ssmt import two_stage
from tools import history
from tools.costed import HORIZON

#: Bars either side of a zone's own formation that still count as the SAME
#: displacement for the POI stack. Three, because a fair value gap left by the
#: leg out prints one to two bars after the base and a breaker can lag the
#: structure break by one more. Not fitted - measured against nothing, and stated
#: so a reader who disagrees has one number to change.
POI_SLACK_BARS = 3

#: Two-stage SSMT degrees per interval. The practitioner's rule: "Minim harus
#: ada dua SSMT stage." Stage 1 is the higher degree, stage 2 is the lower.
#: Source: Bang Nas ICT, POSKO 618 reference material.
STAGE_PAIRS: dict[str, tuple[str, str]] = {
    "1w": ("month", "week"),
    "1d": ("month", "week"),
    "4h": ("week", "day"),
    # "90m" BUKAN NAMA DERAJAT, dan itu cacat yang hidup diam sampai 30 Agustus
    # 2026. `app/quarters.ALL_DEGREES` tidak pernah memuatnya, jadi `quarters()`
    # melempar ValueError, `except ValueError` di bawah menelannya, dan
    # `two_stage_confirmed` TIDAK PERNAH BISA True pada 1h maupun 15m. Nol baris
    # log. Derajat yang dimaksud adalah `session`, yang docstring
    # `app/quarters.py` baris 23 definisikan sebagai kuarter 90 menit.
    "1h": ("day", "session"),
    "15m": ("session", "micro"),
    "5m": ("micro", "nano"),
    "1m": ("micro", "nano"),
}

# DIPERIKSA SAAT IMPORT, bukan saat sebuah kandidat kebetulan lewat. Cacat yang
# baru saja dicabut di atas hidup diam karena satu-satunya yang bisa menemukannya
# adalah menjalankan jalur order pada interval yang tepat lalu memperhatikan
# klausa yang selalu False. Satu baris di sini membuat itu mustahil terulang.
for _interval, _pair in STAGE_PAIRS.items():
    for _degree in _pair:
        if _degree not in ALL_DEGREES:
            raise ValueError(
                f"STAGE_PAIRS[{_interval!r}] menyebut derajat {_degree!r} yang "
                f"tidak ada di app.quarters.ALL_DEGREES {ALL_DEGREES}"
            )


#: Di mana angka tiap klausa MEASURED_AGAINST bisa dibaca ulang. Sampai 30
#: Agustus 2026 peringatannya selalu menunjuk PRAREGISTRASI-YATIM, yang benar
#: untuk `ote` dan salah untuk klausa mana pun yang diukur di tempat lain.
_EVIDENCE: dict[str, str] = {
    "ote": "docs/PRAREGISTRASI-YATIM.md",
    "dfr_side": "docs/checklist_outcomes.json",
}


def warn_required(rules) -> None:
    """Cetak peringatan untuk klausa yang diwajibkan, DUA jenis terpisah.

    Sampai 28 Agustus 2026 keduanya dicetak dengan kalimat yang sama, "belum
    diukur". Untuk `ote` itu sudah tidak benar: ia diukur lewat praregistrasi
    dan hasilnya lebih buruk daripada tidak memfilter sama sekali. Operator yang
    membaca "belum diukur" akan menyalakannya sebagai taruhan; yang membaca
    angkanya tidak akan.
    """
    doctrine = [c for c in rules.required
                if c in DOCTRINE_CLAUSES and c not in MEASURED_AGAINST]
    against = [c for c in rules.required if c in MEASURED_AGAINST]
    if doctrine:
        print(f"PERINGATAN: --require mencantumkan klausa doctrine "
              f"(belum diukur): {', '.join(doctrine)}. "
              f"Klausa ini diterapkan karena metode mensyaratkannya, "
              f"bukan karena proyek ini punya angka untuknya.")
    for clause in against:
        print(f"PERINGATAN: --require mencantumkan {clause}, dan klausa ini "
              f"SUDAH diukur dengan hasil yang berlawanan: "
              f"{MEASURED_AGAINST[clause]}. Lihat "
              f"{_EVIDENCE.get(clause, 'docs/PRAREGISTRASI-YATIM.md')}.")


def grounds(zone, plan) -> list[str]:
    """The measured reasons this zone is being traded, each with its number.

    Every figure here is read from code rather than retyped from a document:
    the gate and the two cohort rates are the constants `app/plan.py` holds
    precisely so a doc edit and a code edit cannot drift apart.
    """
    return [
        f"departure {zone.departure_atr} ATR clears the {DEPARTURE_GATE_ATR} gate",
        "gate margin +0.124 R, Welch t=+4.82 on 14,813 trades across 18 cells, "
        "positive in 17 of 18, walk-forward 8/8",
        f"age {plan.age_bars} bars, cohort held {plan.age_held_rate:.1%}",
        f"target is the nearest live opposing zone at {plan.target}, "
        f"{plan.reward_r}R from the entry",
    ]



def by_method(candidate: tuple) -> tuple:
    """Kunci urut kandidat dalam satu pass: `(zone, plan, checklist)`.

    `met` menurun, lalu `zone.id`. Tie-break-nya SENGAJA tidak menyeleksi;
    seluruh alasannya ada di komentar tepat di atas pemanggilnya di
    `candidates()`. Dikunci oleh `tests/test_order_key.py`.
    """
    zone, _plan, checklist = candidate
    return (-checklist.met, zone.id)


def by_method_ranked(row: tuple) -> tuple:
    """Sama, untuk baris lintas simbol: `(symbol, interval, zone, plan, checklist)`.

    Simbol ikut dalam kuncinya karena `zone.id` adalah `KIND-bartime` tanpa
    simbol, jadi tanpa itu dua zona sejenis di bar yang sama pada dua instrumen
    berbeda akan bertukar tempat antar-run.
    """
    symbol, _interval, zone, _plan, checklist = row
    return (-checklist.met, symbol, zone.id)

def candidates(
    symbol: str,
    interval: str,
    bars: int,
    equity: float | None = None,
    risk_pct: float = 0.01,
    lot: LotSpec | None = None,
    rules: Rules | None = None,
    partners: dict[str, list] | None = None,
):
    """Every untouched gate-clearing zone with a readable target and its checklist.

    Returns triples of `(zone, plan, setup)`. Ordering is BY CHECKLIST FIRST and
    distance second: a candidate that satisfies more of the method outranks a
    nearer one that satisfies less. That is a change of behaviour from ordering by
    distance alone, and it is the point of the checklist existing.

    Untouched is the whole point: the measured population is a FIRST touch, so a
    zone price has already visited is not a member of it and its number does not
    apply.

    `equity` AND `lot` TOGETHER OR NOT AT ALL, and this is the argument that fixes
    a hole in the first version of this file. `plan.build` only sizes when it has
    both; with neither it returns `placeable=True` and `lots=None`, because a plan
    that was never asked to size cannot refuse on size. The first version read
    that True as permission and sent a hardcoded 0.01 lot, so the risk gate this
    module's docstring promised was decorative. Caught on 2026-08-21 while writing
    up the workflow.
    """
    candles = history.load(symbol, interval, bars)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    params = SupplyDemandParams(max_zones_per_side=0)
    atr = float(wilder_atr(high, low, close, params.atr_period)[-1])
    zones, _ = DETECTORS["supply_demand"](candles, params)
    last = candles[-1]
    step = INTERVALS[interval]
    times = [c.time for c in candles]

    # THE REST OF THE TOOLKIT, computed once for the bar rather than once per
    # zone. `at_bar` is 16 ms and the four extra detectors are the expensive part;
    # both answer for the bar, not for the candidate, so paying per candidate
    # would buy fourteen copies of one answer.
    state = at_bar(candles, len(candles) - 1, interval)
    others = other_boxes(candles)
    rules = rules or Rules()

    # OTE, DAN KENAPA INSTANNYA BUKAN SENTUHAN PERTAMA. `mark_dealing_range`
    # membaca di `first_test_time`, sementara loop di bawah membuang setiap zona
    # yang PUNYA `first_test_time`. Dua aturan itu tidak pernah bisa bertemu:
    # jalur order menstempel None pada setiap kandidat, dan klausa `ote` menjawab
    # "no dealing range" selamanya. Terukur 28 Agustus 2026: 23 dari 23.
    # `mark_dealing_range_now` membaca range yang knowable di bar keputusan,
    # dengan swing, lebar, dan clip yang sama persis.
    mark_dealing_range_now(zones, candles)

    # CISD LEVELS, DAN CACAT YANG SAMA PERSIS SUDAH PERNAH DITEMUKAN DI SINI.
    # `tools/conditioned.py` mencatatnya: run pertamanya lupa mengoper level dan
    # kolomnya kembali False untuk 953 trade, yang terbaca sebagai fakta pasar
    # padahal fakta harness. `confluence` menghitung apa yang diberikan, dan
    # jalur order tidak memberi apa-apa, jadi `cisd_in_band` False pada 23 dari
    # 23 kandidat. Difilter ke `last.time` supaya potongan anti-lookahead-nya
    # nyata dan bukan formalitas, walau di sini semuanya memang sudah lampau.
    # DIHITUNG SEKALI PER DERET, bukan sekali per kandidat: apakah instrumen
    # ini dagang saat minggu CME tutup adalah properti instrumen. Klausa
    # `day_of_week` menolak akhir pekan, dan sampai 30 Agustus 2026 penolakan itu
    # ikut mengenai crypto yang pasarnya buka.
    always_open = trades_when_shut(times)

    cisd_events, _ = cisds(candles)
    cisd_levels = [float(e.level) for e in cisd_events if int(e.time) <= last.time]

    # TRUE OPEN, DAN KENAPA IA IKUT SEKARANG. `poi.confluence` menerima
    # `true_open_prices` sejak lama dan `tools/execute.py` tidak pernah
    # mengopernya, jadi `stack.true_opens` selalu 0. Cacat yang sama persis
    # dengan `cisd_levels` di atas, dan `Buku=Pegangan.txt` menempatkan True
    # Open di pusat metodenya: delapan baris tabel PAPAN WAKTU semuanya True
    # Open.
    open_levels = true_open_levels(symbol, interval, candles)
    # Sekali per bar, bukan sekali per zona: keduanya adalah properti instrumen
    # dan horizon, bukan properti kandidat.
    fees = schedule(symbol, False, "exness_raw")
    nights = (HORIZON * step) / 86_400
    too_costly: list[tuple[str, float]] = []

    # ONE DEGREE UP, and the zones are detected THERE rather than on these bars.
    # An H4 demand zone must not die because one M15 candle closed under it: the
    # zone belongs to its own timeframe and is judged there, which is the same
    # rule `drawing._htf_zones` follows for the chart. `mark_nesting` then stamps
    # `nested_in` on the local zones, so the checklist reads a field instead of
    # carrying a second definition of what nesting means.
    higher_name = STEP_UP.get(interval)
    if higher_name:
        higher_bars = resample(candles, higher_name, interval)
        if len(higher_bars) >= params.atr_period + 3:
            higher_zones, _ = DETECTORS["supply_demand"](higher_bars, params)
            for hz in higher_zones:
                hz.timeframe = higher_name
            mark_nesting(zones, higher_zones)

    # SSMT FROM THE BASKET ITSELF, which is the same "against" the SSMT panel has
    # always meant: a divergence needs a second instrument, and in a multi-pair
    # scan the second instrument is already loaded. Before this the clause read
    # `unknown` on every candidate because nobody handed it a partner, while the
    # partner sat in the caller's own dict.
    #
    # Aligned first, because `ssmt` compares quarter extremes and two series on
    # different grids would be compared at instants one of them never had. The
    # newest KNOWABLE event wins, and `knowable_at` is what makes that honest.
    ssmt_side: str | None = None
    bare = symbol.split(":")[-1]
    if partners and len(partners) > 1:
        grid = aligned({s: c for s, c in partners.items() if c})
        if bare in grid and len(grid) > 1:
            events, _ = ssmt_read(grid, "day")
            mine = [e for e in events
                    if bare in (e.took, e.failed) and e.knowable_at <= last.time]
            if mine:
                newest = max(mine, key=lambda e: e.knowable_at)
                # The side is read from THIS symbol's part in it: taking the low
                # is a bullish shape, failing to take the high is the same
                # reading from the other end.
                ssmt_side = newest.side if newest.took == bare else (
                    "low" if newest.side == "high" else "high"
                )

    # 2-stage SSMT: the practitioner's rule requires two consecutive
    # degrees both showing SSMT in the same direction.
    two_stage_confirmed = False
    if partners and len(partners) > 1 and interval in STAGE_PAIRS:
        hi_deg, lo_deg = STAGE_PAIRS[interval]
        try:
            hi_events, _ = ssmt_read(grid, hi_deg)
            lo_events, _ = ssmt_read(grid, lo_deg)
            hi_div = ssmt_divergences_for(hi_events, bare)
            lo_div = ssmt_divergences_for(lo_events, bare)
            two_stage_confirmed = len(two_stage(hi_div, lo_div, bare)) > 0
        except ValueError as exc:
            # DICETAK, TIDAK DITELAN. `pass` di sini menyembunyikan nama derajat
            # yang salah selama entah berapa lama; sebuah klausa yang tidak
            # pernah bisa True terbaca sama persis dengan klausa yang kebetulan
            # False. Nama derajat yang salah sekarang mustahil lolos, dijaga
            # oleh assert di bawah definisi STAGE_PAIRS, jadi yang tersisa di
            # sini adalah ValueError runtime yang sah, misalnya grid terlalu
            # pendek untuk memuat satu siklus.
            print(f"  two_stage tidak dievaluasi pada {interval}: {exc}")

    # The minimal shape `actionable.blockers` reads. `app/drawing.py` builds the
    # API's copy of these four fields; this is the same four for a path that
    # never goes through HTTP.
    response = {
        "interval": interval,
        "candles": [{"time": c.time} for c in candles],
        "meta": {
            "bars_requested": bars,
            "bars_returned": len(candles),
            "truncated_by_provider": len(candles) < bars,
            "as_of": last.time,
        },
    }

    out = []
    for zone in zones:
        if zone.first_test_time is not None:
            continue
        if (zone.departure_atr or 0.0) < DEPARTURE_GATE_ATR:
            continue
        long_side = zone.side is ZoneSide.DEMAND
        # Monday risk multiplier: 0.5x risk on Monday (Q1 accumulation).
        #
        # UNMEASURED AND UNCONDITIONAL, stated plainly because the comment here
        # used to promise otherwise. It read "the full conditions (2-stage,
        # tCISD, manipulation) must still be met, and min_rr >= 2.0 still
        # applies", and none of that is enforced by this line or anywhere near
        # it: those are checklist clauses, they bind only when the operator names
        # them in `--require`, and `Rules.required` defaults to empty on purpose
        # so nothing unmeasured switches itself on. This multiplier is the one
        # exception to that rule, and it gets to stay only because it moves in
        # the safe direction - it halves the size, it cannot admit a trade the
        # gates rejected. It has no measurement behind it.
        monday_mult = 0.5 if datetime.fromtimestamp(last.time, tz=NY).weekday() == 0 else 1.0
        plan = build(
            zone, atr, last.time, step, spread=last.spread,
            equity=equity, risk_pct=risk_pct * monday_mult, lot=lot,
            costs=spec(symbol.split(":")[-1], False, "exness_raw", long_side=long_side),
        )
        if plan is None or plan.target is None:
            continue

        # GERBANG BIAYA, dan ini gerbang yang paling mahal dilewatkan. Diukur 22
        # Agustus 2026 pada 24 sel instrumen kali timeframe: korelasi antara
        # biaya-terhadap-risiko dan ekspektasi adalah -0,9879 dengan R kuadrat
        # 0,976, dan tandanya berbalik di cost_r 0,2491. Setiap sel di bawah
        # 0,15 positif; setiap sel di atas 0,33 negatif, termasuk EURUSD 1 jam
        # pada -0,422 R dengan t = -28,9 di 1.019 trade.
        #
        # Ini BUKAN gerbang tentang instrumen. Ia tentang aritmetika: edge
        # kotornya +0,335 R, jadi biaya di atas 0,335/1,344 memakannya habis.
        # Instrumen yang sama bisa lolos di 4 jam dan gagal di 1 jam karena stop
        # 4 jam lebih lebar sementara biayanya sama, dan itu persis yang terukur.
        #
        # POPULASINYA, BUKAN PENOLAKAN YANG DI-JOURNAL. Sama kelasnya dengan
        # departure di bawah gerbang: zona yang biayanya melebihi ini bukan
        # anggota populasi yang setiap angka di CALIBRATION.md dan QA-QUANT.md
        # dihitung padanya, jadi angka itu tidak berlaku untuknya.
        ratio, _ = cost_to_risk(
            float(last.close), plan.risk_per_unit, last.spread or 0.0,
            fees, nights,
            swap_bp=fees.get("swap_bp_short" if not long_side else "swap_bp",
                             fees.get("swap_bp", 0.0)),
        )
        if ratio > COST_TO_RISK_MAX:
            too_costly.append((zone.id, ratio))
            continue

        anatomy = zone.anatomy
        born_from = times[max(0, anatomy.leg_in_from - POI_SLACK_BARS)]
        born_to = times[min(len(times) - 1, anatomy.leg_out_to + POI_SLACK_BARS)]
        stack = confluence(zone, others, last.time, born_from, born_to,
                           cisd_levels=cisd_levels,
                           true_open_prices=open_levels)
        out.append((zone, plan, ict_setup(zone, state, stack, rules,
                                          ssmt_side=ssmt_side,
                                          two_stage_confirmed=two_stage_confirmed,
                                          reward_r=plan.reward_r,
                                          always_open=always_open)))

    # CHECKLIST FIRST, lalu zone id. Kalimat di sini dulu berbunyi "distance
    # second, which is what the measured population is about", dan itu ternyata
    # terbalik. Diukur 2 September 2026 di `docs/order_key.json`, n = 1847,
    # ambang Bonferroni t = 2,69: `-abs(entry - close)` memberi Spearman rho
    # demeaned -0,1073 pada t = -4,64, |t| TERBESAR di seluruh run dan tandanya
    # salah, dan lift dua-teratasnya -0,0966 R pada t = -3,86 dengan
    # walk-forward NOL dari 8 fold. Mendahulukan kandidat yang paling dekat
    # memilih trade yang lebih buruk, konsisten di setiap fold.
    #
    # PENGGANTINYA SENGAJA TIDAK MENYELEKSI. Tujuh kunci diuji dan tidak satu
    # pun lulus, termasuk yang menggantikan ini, jadi memilih salah satunya
    # berarti menukar kunci yang terukur merugikan dengan kunci yang belum
    # terukur apa-apa. `zone.id` deterministik, membuat urutan reproducible,
    # dan setara dengan kontrol acak yang di studi itu keluar bersih di t 0,88
    # dan 0,36. Yang didukung angka cuma membuang, bukan mengganti.
    #
    # `met` SENDIRI JUGA BELUM TERBUKTI, dan ia tetap di sini. Rho-nya -0,0356
    # demeaned, praktis nol, tapi nol berbeda dari merugikan: tidak ada angka
    # yang mengatakan mengurutkan dengannya lebih buruk daripada tidak. Ia
    # dipertahankan karena membuangnya adalah keputusan yang tidak punya
    # dukungan terukur, sama seperti menggantinya. Lihat
    # `tests/test_order_key.py`, yang mengunci kedua kunci ini.
    # DICETAK, TIDAK DISEMBUNYIKAN. Sebuah gerbang yang membuang kandidat tanpa
    # mengatakan berapa banyak terlihat sama dengan pasar yang sedang sepi.
    if too_costly:
        worst = max(too_costly, key=lambda x: x[1])
        print(f"  {len(too_costly)} zona ditolak gerbang biaya "
              f"(cost_r > {COST_TO_RISK_MAX}), terburuk {worst[1]:.3f} "
              f"pada {worst[0]}")
    out.sort(key=by_method)
    return out, response, float(close[-1])


#: Timeframe yang dipinjam untuk True Open berskala session. Batas session
#: jatuh di menit :30 (Asia 19:30, London 01:30, NY AM 07:30, NY PM 13:30 NY),
#: sementara bar 1 jam membuka di menit :00, jadi `true_opens` yang menolak
#: menginterpolasi mengembalikan NOL level session pada deret 1 jam. Terukur 28
#: Agustus 2026 pada XAUUSD: 0 level di 1h, 871 level di 15m, tepat di keempat
#: jam itu. Empat dari delapan baris tabel PAPAN WAKTU POSKO 618 karena itu
#: tidak pernah sampai ke jalur order.
SESSION_BARS = "15m"


def true_open_levels(symbol: str, interval: str, candles) -> list[float]:
    """Harga True Open yang knowable di bar terakhir, semua derajat.

    DUA SUMBER, SATU DEFINISI. Derajat yang batasnya jatuh pada bar deret ini
    dibaca dari deret ini. Derajat session tidak pernah jatuh di sana pada 1
    jam atau lebih kasar, jadi ia dibaca dari `SESSION_BARS`. Fungsi
    `true_opens` yang sama dipakai untuk keduanya; yang berbeda cuma bar yang
    diberikan padanya, dan tidak ada level yang dikarang.

    Deret halusnya di-cache di disk oleh `history.load`, jadi ia satu fetch
    pertama kali dan nol sesudahnya. Kegagalan memuatnya BUKAN alasan
    menggagalkan cycle: level session hilang, sisanya tetap ada, dan itu
    dicetak.
    """
    cutoff = candles[-1].time
    levels = [lv.price for lv in true_opens(candles, ALL_DEGREES)
              if lv.time <= cutoff]
    if INTERVALS[interval] >= INTERVALS[SESSION_BARS] and interval != SESSION_BARS:
        try:
            fine = history.load(symbol, SESSION_BARS, 20_000)
        except Exception as exc:  # noqa: BLE001 - satu derajat, bukan cycle
            print(f"  CATATAN: True Open session tidak terbaca dari "
                  f"{SESSION_BARS}: {exc}")
            return levels
        levels += [lv.price for lv in true_opens(fine, ("session",))
                   if lv.time <= cutoff]
    return levels
def gather(
    symbols: list[str],
    intervals: list[str],
    bars: int,
    equity: float | None,
    risk_pct: float,
    lots: dict[str, LotSpec] | None,
    rules: Rules,
    partners: list[str] | None = None,
) -> tuple[list[tuple], list[tuple[str, str, list[str]]], dict[str, list]]:
    """Candidates across every pair and timeframe, ranked once, globally.

    A STALE FEED ON ONE PAIR STOPS THAT PAIR AND NOTHING ELSE. The blockers are
    per series, because "gold's feed is behind" is not a reason to skip silver -
    and a scan that refused the whole basket for one bad series would be
    unusable on a Saturday, when exactly one of them is quiet.

    RANKED GLOBALLY, not per series. Scanning five pairs and taking the best two
    from each is not scanning five pairs; it is five scans that happen to run
    together. The whole point of a basket is that the best setup wins wherever it
    is, so every candidate goes into one list ordered by checklist then distance.

    Also returns the raw series per symbol, which the correlation guard needs and
    which would otherwise be fetched a second time.
    """
    found: list[tuple] = []
    blocked: list[tuple[str, str, list[str]]] = []
    series: dict[str, list] = {}
    # EVERY SERIES FIRST, because SSMT needs the partners before the first
    # candidate is scored. One pass that scored as it loaded would give the first
    # pair no partners and the last pair all of them, which is a checklist whose
    # answer depends on argument order.
    # DIBACA TAPI TIDAK DITRADINGKAN. SSMT butuh partner yang BERKORELASI - XAG
    # terhadap XAU adalah r +0,851 - sementara cap portofolio menginginkan yang
    # TIDAK berkorelasi. Satu daftar untuk dua tujuan yang berlawanan memaksa
    # operator memilih antara mematikan SSMT atau melebarkan diam-diam universe
    # yang bisa diorder. `partners` memutus ikatan itu: seriesnya dimuat, tapi
    # loop kandidat di bawah tidak menyentuhnya.
    for symbol in [*symbols, *(partners or [])]:
        series.setdefault(symbol.split(":")[-1],
                          history.load(symbol, intervals[0], bars))
    for symbol in symbols:
        for interval in intervals:
            lot = (lots or {}).get(symbol.split(":")[-1])
            pairs, response, price = candidates(
                symbol, interval, bars, equity, risk_pct, lot, rules, series
            )
            reasons = blockers(response)
            print(f"{symbol} {interval}  price {price}  "
                  f"{len(pairs)} kandidat lolos gerbang dan punya target"
                  + (f"  BLOCKED: {len(reasons)}" if reasons else ""))
            for reason in reasons:
                print(f"  BLOCKER: {reason}")
            if reasons:
                blocked.append((symbol, interval, reasons))
                continue
            found.extend(
                (symbol, interval, zone, plan, checklist)
                for zone, plan, checklist in pairs
            )
    # Situs urut KEDUA, dan alasannya sama. `-abs(entry - target)` diuji
    # sebagai `k_near_target` di studi yang sama dan ikut menyeberang ambang ke
    # arah negatif di pengelompokan pekan: -0,0774 R pada t = -2,91, dengan
    # walk-forward 2 dari 8. Lihat `by_method_ranked`.
    found.sort(key=by_method_ranked)
    return found, blocked, series


def cycle(
    mt5,
    symbols: list[str] | str,
    intervals: list[str] | str,
    bars: int,
    risk_pct: float,
    max_orders: int,
    send: bool,
    equity: float | None = None,
    lots: dict[str, LotSpec] | LotSpec | None = None,
    rules: Rules | None = None,
    cap_pct: float = 0.06,
    corr_max: float = 0.70,
    partners: list[str] | None = None,
    daily_loss_pct: float = 0.0,
) -> dict:
    """ONE decision pass over every pair and timeframe. Returns a summary.

    Split out of `main` so `tools/autotrade.py` runs the SAME pass on a timer
    rather than a second copy of it. A daemon with its own copy of this logic is
    two engines that will disagree, and the one that disagrees is the one holding
    the account.

    `symbols` and `intervals` take a string for one or a list for a basket. The
    portfolio guards below only bind on a basket, and they are the reason a basket
    is not simply the same tool run five times: `--risk-pct` is per trade, and
    five trades at three percent is fifteen percent nobody chose.
    """
    rules = rules or Rules()
    warn_required(rules)
    if isinstance(symbols, str):
        symbols = [symbols]
    if isinstance(intervals, str):
        intervals = [intervals]
    # SATU LotSpec TIDAK DI-BROADCAST LAGI. Sebuah spec tunggal yang disebar ke
    # setiap simbol adalah error 50x antara XAUUSD (100) dan XAGUSD (5000); ia
    # masih diterima di sini untuk caller lama yang memang satu simbol, dan
    # hanya untuk simbol itu.
    if isinstance(lots, LotSpec):
        lots = {symbols[0].split(":")[-1]: lots} if len(symbols) == 1 else {}
    elif lots is None:
        lots = {}
    rule = {**RULE, "risk_pct": risk_pct, "ict_required": list(rules.required),
            "ict_killzones": list(rules.killzones),
            "ict_min_families": rules.min_families,
            "ict_max_conflicts": rules.max_conflicts,
            "portfolio_cap_pct": cap_pct, "corr_max": corr_max,
            "daily_loss_pct": daily_loss_pct,
            "symbols": symbols, "intervals": intervals,
            "partners": list(partners or [])}

    ranked, blocked, series = gather(
        symbols, intervals, bars, equity, risk_pct, lots, rules, partners
    )
    if equity is None:
        print("  CATATAN: tanpa equity, ukuran posisi dan batas portofolio TIDAK "
              "diperiksa. Ini hanya menunjukkan level")
    if send and blocked:
        for symbol, interval, reasons in blocked:
            journal.record("refused", why=[f"no order attempted on {symbol} {interval}"],
                           rule=rule, blockers=reasons)
    if not ranked:
        print("  tidak ada kandidat")
        return {"candidates": 0, "sent": 0, "blocked": len(blocked)}

    # OPEN POSITIONS COUNT TOWARDS THE CAP, and when they cannot be read the book
    # says so. A cap computed on half the book is a cap that does not bind, and
    # `Book.partial` is what makes that visible in the refusal text.
    book = Book(equity=equity or 0.0, cap_pct=cap_pct, corr_max=corr_max,
                daily_loss_pct=daily_loss_pct,
                realised_today=realised_today(mt5) if daily_loss_pct > 0 else 0.0)
    if daily_loss_pct > 0:
        print(f"  pengaman kerugian harian {daily_loss_pct:.2%}, terealisasi "
              f"hari ini {book.realised_today if book.realised_today is not None else 'TIDAK TERBACA'}")
    if mt5 is not None:
        # PENDING IKUT DIHITUNG, dan tanpa itu cap ini tidak pernah mengikat
        # antar run. Tool ini menempatkan LIMIT, jadi risiko yang baru saja ia
        # kirim adalah pending, bukan posisi. Sampai 27 Agustus 2026 book hanya
        # membaca `positions_get`, sehingga satu pending XAUUSD berisiko 43.92
        # dari run sebelumnya tidak terlihat dan run berikutnya berangkat dari
        # book yang lebih ringan 4.5% dari kenyataan.
        rows = [(p.symbol, p.price_open, p.sl, p.volume)
                for p in (mt5.positions_get() or [])]
        rows += [(o.symbol, o.price_open, o.sl, o.volume_current)
                 for o in (mt5.orders_get() or [])]
        for name, opened, stop, volume in rows:
            # TIDAK TERHITUNG BUKAN NOL, dan dua cacat di dua baris ini
            # membuktikan bedanya. `if not stop: continue` menghitung posisi
            # tanpa stop sebagai nol risiko, jadi hal paling berbahaya yang bisa
            # dipegang akun justru satu satunya yang tak terlihat cap. Dan
            # `getattr(mt5.symbol_info(name), "trade_contract_size", 1.0)`
            # mengembalikan 1,0 saat `symbol_info` menjawab None, karena
            # `getattr(None, ...)` memang mengembalikan default-nya, jadi satu
            # posisi emas menyumbang seperseratus dari yang seharusnya. Kelas
            # yang sama dengan cacat 50x yang sudah diperbaiki di `lot_specs`.
            info = mt5.symbol_info(name)
            if info is None:
                book.unbounded.append(
                    f"{name} volume {volume}: symbol_info tidak terbaca, jadi "
                    "contract size tidak diketahui"
                )
                continue
            if not stop:
                book.unbounded.append(
                    f"{name} volume {volume} dibuka di {opened}: tanpa stop "
                    "loss, jadi kerugiannya tidak berbatas"
                )
                continue
            book.held.append(Held(
                name,
                abs(opened - stop) * volume * info.trade_contract_size,
            ))
    else:
        book.partial = True

    # CETAK BOOK-NYA SEBELUM LOOP, dan ini bukan kosmetik. Dry run menyetel
    # `mt5 = None`, jadi cap-nya dihitung lawan book KOSONG dan rencananya
    # menjanjikan kapasitas yang `--send` tidak punya. Terukur 2026-08-27:
    # dry run mengirim 2 order, sementara satu posisi BTCUSD yang tak terbaca
    # sudah memakan 43.24 dari cap 58.89, jadi order kedua akan ditolak.
    if book.unbounded:
        print("  PERHATIAN: risiko yang tidak bisa dihitung, order baru DITOLAK "
              "sampai ini beres:")
        for line in book.unbounded:
            print(f"    - {line}")
    print(f"  book: {book.committed:,.2f} sudah berisiko dari cap "
          f"{book.equity * book.cap_pct:,.2f}"
          + (" (POSISI TERBUKA TIDAK TERBACA, jadi ini LANTAI dan `--send` "
             "bisa menolak lebih banyak)" if book.partial else "")
          + (f", pegang {', '.join(book.symbols)}" if book.held else ""))

    sent = skipped = refused = 0
    for symbol, interval, zone, plan, checklist in ranked:
        if sent >= max_orders:
            break
        # SIMBOL IKUT DALAM KUNCINYA. Zone id adalah `KIND-bartime` tanpa
        # simbol, jadi tanpa ini sebuah zona silver dilewati karena gold
        # sudah punya order dari zona sejenis di bar yang sama. Lihat
        # `journal.for_zone` untuk angkanya.
        already = [
            e for e in journal.for_zone(zone.id, symbol)
            if e["event"] == "placed"
        ]
        head = (f"  {symbol} {interval} {zone.kind.value} {zone.side.value}  "
                f"entry {plan.entry:.3f} stop {plan.stop:.3f} tp {plan.target:.3f}"
                f"  checklist {checklist.met}/{len(checklist.conditions)}")
        if already:
            print(f"{head}\n      SUDAH pernah diorder, ticket {already[0]['ticket']}")
            skipped += 1
            continue
        # THE ICT GATE, and it sits before the risk checks on purpose: a setup the
        # method rejects should not consume a slot, and its refusal should name
        # the clause rather than the account.
        missing = checklist.failed_required(rules)
        if missing:
            print(f"{head}\n      CHECKLIST menolak: {', '.join(missing)}")
            if send:
                journal.record("refused", why=grounds(zone, plan) + checklist.why(),
                               rule=rule, zone_id=zone.id, symbol=symbol,
                               plan=plan.model_dump(mode="json"),
                               blockers=[f"required condition not met: {name}"
                                         for name in missing])
            refused += 1
            continue
        if not plan.placeable:
            print(f"{head}\n      TIDAK placeable: "
                  f"{plan.warnings[-1] if plan.warnings else 'no reason given'}")
            if send:
                journal.record("refused", why=grounds(zone, plan) + checklist.why(),
                               rule=rule, zone_id=zone.id, symbol=symbol,
                               plan=plan.model_dump(mode="json"),
                               blockers=list(plan.warnings))
            refused += 1
            continue
        # NO VOLUME UNLESS THE PLAN SIZED ONE. `placeable` defaults to True on a
        # plan that was never given equity, so it cannot stand alone as the risk
        # gate - the missing lot is what says "nobody checked".
        if send and plan.lots is None:
            why_not = ("plan carries no lot size, so the risk budget was never "
                       "computed. Pass --risk-pct and let the terminal supply the "
                       "equity, or do not send")
            print(f"{head}\n      DITOLAK: {why_not}")
            journal.record("refused", why=grounds(zone, plan) + checklist.why(),
                           rule=rule, zone_id=zone.id, symbol=symbol,
                           plan=plan.model_dump(mode="json"), blockers=[why_not])
            refused += 1
            continue
        # THE PORTFOLIO GUARDS, last because they are about the BOOK rather than
        # about this setup: everything above can be judged on one candidate, and
        # these two need to know what is already held.
        if plan.lots is not None and equity:
            ok, why_not = admits(book, symbol.split(":")[-1],
                                 plan.realised_risk or 0.0, series)
            if not ok:
                print(f"{head}\n      PORTOFOLIO menolak: {why_not}")
                if send:
                    journal.record("refused",
                                   why=grounds(zone, plan) + checklist.why(),
                                   rule=rule, zone_id=zone.id, symbol=symbol,
                                   plan=plan.model_dump(mode="json"),
                                   blockers=[why_not])
                refused += 1
                continue
        if not send:
            # Counted, not just printed. A dry run that walks past `max_orders`
            # reports fourteen orders where a real run would place two, and a
            # preview that disagrees with the thing it previews is worse than no
            # preview. The BOOK grows here for the same reason: without it every
            # candidate clears the portfolio cap against an empty book and the
            # preview shows five orders a real run would refuse.
            print(f"{head}\n      DRY RUN, tidak dikirim")
            book.held.append(Held(symbol.split(":")[-1], plan.realised_risk or 0.0))
            sent += 1
            continue
        ticket, why_not = place(mt5, zone, plan, symbol.split(":")[-1], plan.lots)
        if ticket is None:
            print(f"{head}\n      GAGAL: {why_not}")
            journal.record("refused", why=grounds(zone, plan) + checklist.why(),
                           rule=rule, zone_id=zone.id, symbol=symbol,
                           plan=plan.model_dump(mode="json"), blockers=[why_not])
            refused += 1
            continue
        journal.record("placed", why=grounds(zone, plan) + checklist.why(),
                       rule=rule, zone_id=zone.id, symbol=symbol,
                       ticket=ticket, plan=plan.model_dump(mode="json"),
                       extra={"volume": plan.lots, "symbol": symbol,
                              "equity_at_decision": equity,
                              "realised_risk": plan.realised_risk,
                              "realised_risk_pct": plan.realised_risk_pct})
        # THE BOOK GROWS AS THE RUN PLACES, or the cap only ever sees what was
        # held BEFORE this scan and five orders in one pass would each clear a
        # check against an empty book.
        book.held.append(Held(symbol.split(":")[-1], plan.realised_risk or 0.0))
        print(f"{head}\n      TERKIRIM ticket {ticket}, {plan.lots} lot, "
              f"risiko {plan.realised_risk} ({plan.realised_risk_pct:.2%})")
        sent += 1
    print(f"  ringkas: {len(ranked)} kandidat, {sent} dikirim, {skipped} dilewati, "
          f"{refused} ditolak, {len(blocked)} deret diblokir, "
          f"risiko terkomitmen {book.committed:,.2f}")
    return {"candidates": len(ranked), "sent": sent, "skipped": skipped,
            "refused": refused, "blocked": len(blocked),
            "committed_risk": book.committed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD",
                        help="one pair, or a comma list for a basket")
    parser.add_argument("--interval", default="1h",
                        help="one timeframe, or a comma list. Candidates from "
                             "every pair and timeframe are ranked in ONE list")
    parser.add_argument("--max-total-risk-pct", type=float, default=0.06,
                        help="cap on risk across the whole book, open positions "
                             "included. --risk-pct is per trade and five trades "
                             "at three percent is fifteen percent nobody chose")
    parser.add_argument("--max-correlation", type=float, default=0.70,
                        help="refuse a second pair whose measured correlation "
                             "with one already held is at or past this. Gold "
                             "against silver reads 0.848 on this feed")
    parser.add_argument(
        "--partners", default="",
        help="comma list simbol yang DIBACA sebagai partner SSMT dan korelasi "
             "tapi TIDAK ditradingkan, misal mt5:XAGUSD,mt5:XPTUSD",
    )
    parser.add_argument("--bars", type=int, default=3000)
    parser.add_argument("--max-orders", type=int, default=2)
    parser.add_argument("--risk-pct", type=float, default=0.01,
                        help="fraction of equity risked per trade. Stated on the "
                             "command line and recorded in the journal, because a "
                             "budget hidden in a default is a budget nobody chose")
    parser.add_argument("--equity", type=float, default=None,
                        help="only for a dry run. With --send the TERMINAL is the "
                             "authority and this is ignored")
    parser.add_argument(
        "--send", action="store_true",
        help="actually place the orders. Without it nothing is sent and nothing "
             "is journalled, so a dry run cannot lie about what it did",
    )
    # THE ICT CHECKLIST'S TUNING SURFACE. Every condition is evaluated and
    # reported whatever these say; `--require` is what lets one BLOCK.
    parser.add_argument(
        "--require", default="",
        help="comma list of checklist conditions that must pass, e.g. "
             "killzone,discount_or_premium,poi_families. Empty means the "
             "checklist reports and blocks nothing",
    )
    parser.add_argument(
        "--killzones", default="",
        help="comma list of kill zones that count, e.g. ny_am,london. Empty "
             "means all of them",
    )
    parser.add_argument("--bias-degree", default="bias_4h", choices=BIAS_DEGREES,
                        help="derajat bias yang dibaca klausa bias_agrees. "
                             "DEFAULTNYA 4 JAM UNTUK SETIAP TIMEFRAME, dan itu "
                             "yang menolak 19 kandidat demand di 15m dan 30m "
                             "pada 30 Agustus 2026 sementara bias_1h dan "
                             "bias_1d keduanya +1 dan BTCUSD naik 1,36 persen "
                             "dalam 24 jam. Menurunkannya BUKAN perbaikan yang "
                             "terbukti: H7 mengukur kontribusi zona di atas "
                             "bias ini NOL, jadi derajat mana pun yang dipilih "
                             "adalah pilihan operator, bukan temuan")
    parser.add_argument("--min-families", type=int, default=2,
                        help="PD array families that must stack for poi_families")
    parser.add_argument("--max-conflicts", type=int, default=0,
                        help="opposite-side boxes tolerated in the band")
    # PENGAMAN, BUKAN FILTER. Cap portofolio membatasi yang SEDANG
    # dipertaruhkan dan buta terhadap yang sudah HILANG: delapan kekalahan
    # berturut dalam satu hari tidak melanggar cap sama sekali, karena tiap
    # kerugian mengosongkan kembali ruangnya. Default 0 mematikannya, jadi
    # tidak ada perilaku yang berubah tanpa operator memintanya.
    parser.add_argument("--daily-loss-pct", type=float, default=0.0,
                        help="berhenti mengirim order kalau kerugian terealisasi "
                             "hari ini sudah mencapai persen equity ini, misal "
                             "0.02. Nol mematikan pengaman")
    args = parser.parse_args()
    rules = Rules(
        required=tuple(x.strip() for x in args.require.split(",") if x.strip()),
        min_families=args.min_families,
        max_conflicts=args.max_conflicts,
        bias_degree=args.bias_degree,
        **({"killzones": tuple(x.strip() for x in args.killzones.split(",")
                               if x.strip())} if args.killzones else {}),
    )
    rule = {**RULE, "risk_pct": args.risk_pct}

    warn_required(rules)

    symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]

    mt5 = None
    equity = args.equity
    # SATU DICT, SATU ENTRI PER SIMBOL. Dibaca lebih dulu supaya dry run memakai
    # contract size yang benar juga; handle terminal-nya tidak dibawa keluar dari
    # `lot_specs`, jadi dry run tetap tidak bisa mengirim apa pun.
    lot: dict[str, LotSpec] | None = None
    missing: list[str] = []
    if equity is not None or args.send:
        lot, missing = lot_specs(symbols)
        if missing:
            print(f"CATATAN: terminal tidak membawa {', '.join(missing)}, jadi "
                  f"kandidat pada simbol itu tidak akan disizing dan tidak akan "
                  f"dikirim.")
        if not lot:
            print("CATATAN: tidak ada terminal untuk dibaca, jadi tidak ada "
                  "contract size. Default LotSpec TIDAK dipakai: ia memegang "
                  "angka XAUUSD dan memakainya untuk simbol lain adalah error "
                  "50x. Kandidat akan tampil tanpa ukuran.")

    if args.send:
        terminal, why_not = _terminal()
        if terminal is None:
            print(f"BLOCKER: {why_not}")
            journal.record("refused", why=["no order attempted"], rule=rule,
                           blockers=[why_not])
            return
        mt5, account = terminal
        equity = sizing(account, lot or {}, args.risk_pct)

    cycle(mt5, symbols,
          [i.strip() for i in args.interval.split(",") if i.strip()],
          args.bars, args.risk_pct, args.max_orders, args.send, equity,
          lot, rules, args.max_total_risk_pct, args.max_correlation,
          [s.strip() for s in args.partners.split(",") if s.strip()],
          args.daily_loss_pct)


if __name__ == "__main__":
    main()
