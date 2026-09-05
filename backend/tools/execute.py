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
from app.cisd import RECENT_CISD_BARS, cisds, recent_in_band
from app.clock import NY, trades_when_shut
from app.conditions import at_bar
from app.confluence import mark_nesting
from app.costs import COST_TO_RISK_MAX, cost_to_risk, schedule, spec
from app.dealing_range import mark_dealing_range_now
from app.detect import DETECTORS
from app.ict import (
    adverse_excursion_atr,
    BIAS_DEGREES,
    DOCTRINE_CLAUSES,
    MEASURED_AGAINST,
    Rules,
    setup as ict_setup,
)
from app.indicators import bb_width, vwap as compute_vwap, volume_profile as compute_vp, wilder_adx, wilder_atr
from app.layers import LAYERS
from app.models import ImbalanceParams, LotSpec, SupplyDemandParams, ZoneSide
from app.plan import DEPARTURE_GATE_ATR, DEPARTURE_GATE_ATR_CEILING, build
from app.probability import outcome_odds, summary as odds_line
from app.portfolio import Book, Held, admits, aligned
from app.poi import confluence, other_boxes
from app.providers.base import INTERVALS
from app.quarters import ALL_DEGREES, true_opens
from app.resample import STEP_UP, resample
from app.ssmt import divergences_for as ssmt_divergences_for
from tools.broker import RULE, _terminal, loss_streak, lot_specs, place, realised_today, realised_this_week, sizing
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


def grounds(zone, plan, layer: str, odds: dict | None = None) -> list[str]:
    """The measured reasons this zone is being traded, each with its number.

    Every figure here is read from code or from the calibration table, never
    retyped from a document: the gate is the constant `app/plan.py` holds, its
    DIRECTION is the same `GATE_DIRECTION` that filtered the candidate, and the
    expectancy comes from `docs/entry_probability.json` through
    `app.probability.outcome_odds`. A doc edit and a code edit cannot drift.

    `layer` IS REQUIRED AND HAS NO DEFAULT, and that is the point of this
    signature. Until 3 September 2026 this function took only the zone and the
    plan, and it wrote two sentences that were true for `supply_demand` and
    false for every other layer:

      1. "departure X ATR clears the 2.0 gate" was written for `fvg` too, whose
         gate is `ceiling`. An fvg at 0.204 ATR is BELOW that gate, and below is
         its QUALIFYING side, so the journal recorded the qualifying condition
         as its own opposite.
      2. "gate margin +0.124 R, Welch t=+4.82 on 14,813 trades across 18 cells"
         is the `supply_demand` departure study at 1h and 4h. It was stamped on
         every order of every layer at every timeframe. For `fvg` the matching
         claim is measured FALSE: `docs/fvg_inverted.json` carries
         `h2_gate_stays_inverted: false`, Welch t 1.004 against a critical
         2.241, and `docs/fvg_resolution.json` carries
         `separation_survives: false`.

    Six live orders were journalled with both defects on 3 September 2026,
    tickets 4653163409, 4653163437, 4653163454, 4653163456, 4653163472 and
    4653163483. A default for `layer` would leave that reachable, so there is
    none, and the two callers in `tools/stress_decision.py` name theirs.

    THE RETYPED GATE-MARGIN SENTENCE IS GONE RATHER THAN MADE PER LAYER. There
    is no machine-readable per-layer separation figure to read one from, and a
    second hand-typed table is the same defect with more rows. What replaced it
    is the population this order actually belongs to, named and counted, from
    the file that already decides which side of the gate to report.
    """
    # ARAHNYA DARI SUMBER YANG SAMA dengan yang menyaring kandidatnya di
    # `candidates()`, jadi kalimat di journal tidak bisa melenceng dari gerbang
    # yang benar-benar dipakai untuk meloloskannya.
    if GATE_DIRECTION.get(layer, "floor") == "floor":
        gate = (f"departure {zone.departure_atr} ATR clears the "
                f"{DEPARTURE_GATE_ATR} ATR floor, the measured side for {layer}")
    else:
        gate = (f"departure {zone.departure_atr} ATR is below the "
                f"{DEPARTURE_GATE_ATR_CEILING} ATR ceiling, the measured side for {layer}")
    # `odds is None` DIUCAPKAN, tidak dilewati. Sebuah order pada populasi yang
    # belum diukur adalah fakta yang harus ada di journal-nya, dan n=0 adalah
    # angkanya - baris tanpa angka adalah opini, yang file ini menolak punya.
    if odds is None:
        evidence = (f"NO measured population for {layer} on this symbol and "
                    f"timeframe: n=0 in docs/entry_probability.json, so this "
                    f"order carries no expectancy figure")
    else:
        evidence = (f"measured population {odds['population']}: "
                    f"exp {odds['exp_r']:+.4f} R, P(target) "
                    f"{100 * odds['p_target']:.1f}%, n={odds['n']}, read from "
                    f"docs/entry_probability.json")
    return [
        gate,
        evidence,
        f"age {plan.age_bars} bars, cohort held {plan.age_held_rate:.1%}",
        f"target is the nearest live opposing zone at {plan.target}, "
        f"{plan.reward_r}R from the entry",
    ]



def _adverse_line(checklist) -> str:
    """Jarak melawan tesis, dari klausanya sendiri, atau string kosong.

    DIBACA DARI KLAUSA, BUKAN DIHITUNG ULANG. Dua definisi yang bisa melenceng
    adalah kelas cacat yang repo ini paling sering ketemu, dan di sini ia akan
    melenceng ke arah yang paling buruk: baris yang dicetak operator akan
    berbeda dari baris yang masuk journal.
    """
    # getattr, BUKAN akses langsung. Lima test di tests/test_enhancement_gates.py
    # memanggil jalur ini dengan checklist palsu yang conditions-nya daftar
    # integer, dan versi pertama fungsi ini meledak AttributeError di sana.
    # Menuntut fixture berubah supaya kode produksi jalan adalah arah
    # ketergantungan yang salah: baris cetak kosong sudah benar untuk checklist
    # yang tidak membawa klausanya.
    for c in getattr(checklist, "conditions", None) or ():
        if getattr(c, "name", None) != "adverse_excursion":
            continue
        detail = getattr(c, "detail", "") or ""
        if "x ATR" in detail:
            return f"  adverse {detail.split('x ATR')[0]}x ATR"
    return ""


def by_method(candidate: tuple) -> tuple:
    """Kunci urut kandidat dalam satu pass: `(zone, plan, checklist)`.

    `met` menurun, lalu `zone.id`. Tie-break-nya SENGAJA tidak menyeleksi;
    seluruh alasannya ada di komentar tepat di atas pemanggilnya di
    `candidates()`. Dikunci oleh `tests/test_order_key.py`.
    """
    _zone, _plan, _checklist = candidate
    return (_zone.id,)


def by_method_ranked(row: tuple) -> tuple:
    """Sama, untuk baris lintas simbol: `(symbol, interval, zone, plan, checklist)`.

    Simbol ikut dalam kuncinya karena `zone.id` adalah `KIND-bartime` tanpa
    simbol, jadi tanpa itu dua zona sejenis di bar yang sama pada dua instrumen
    berbeda akan bertukar tempat antar-run.
    """
    symbol, _interval, zone, _plan, _checklist = row
    return (symbol, zone.id)

#: Layer yang boleh dipasangi order, dan daftarnya sependek buktinya.
#:
#: `candidates()` memanggil `DETECTORS["supply_demand"]` sejak awal dan tidak
#: pernah punya cara memilih yang lain, jadi jalur order TERTUTUP untuk setiap
#: detektor ICT karena alasan struktural, satu lapis di atas cacat
#: `mark_profit_zones` yang ditutup 2 September 2026. Menutup cacat itu perlu
#: tapi belum cukup: zona ICT punya target sekarang, dan tetap tidak pernah
#: masuk loop ini.
#:
#: DAFTARNYA DIBATASI KE YANG DIUKUR LEWAT RIG BERBIAYA, `docs/detectors_costed.json`.
#: Hanya dua detektor pernah lewat situ. `order_block` PASS: gerbang departure
#: 2,0 ATR memisahkan, -0,0429 R di atas lawan -0,1192 R di bawah, selisih
#: +0,0764 dengan Welch t = +6,95, 17 dari 18 sel positif, walk-forward 8 dari 8.
#: `fvg` GAGAL dan gagalnya negatif serta signifikan: -0,1005 dengan t = -4,48
#: dan hanya 3 dari 17 sel positif, artinya untuk FVG gerbang itu TERBALIK.
#: Karena itu `fvg` tidak ada di sini meskipun zonanya sudah punya target.
#:
#: TIDAK SATU PUN DARI KETIGANYA POSITIF SENDIRI. supply_demand di atas gerbang
#: -0,0153 R, order_block -0,0429 R dengan t sendiri -6,21 yang berarti negatif
#: signifikan. Satu-satunya populasi lolos gerbang yang titik estimasinya
#: positif adalah order_block SETELAH `--no-cisd-in-band`, +0,0244 R, dan itu
#: pun belum pernah diuji lawan nol. Jadi memilih `order_block` di sini tanpa
#: filter itu memilih populasi yang lebih buruk daripada default.
#: DITURUNKAN DARI `app/layers.py`, TIDAK DITULIS ULANG DI SINI.
#:
#: Ketiga struktur di bawah dulu daftar literal berisi id layer, dan komentar
#: `Layer.family` di `app/layers.py` sudah menjelaskan kenapa itu berbahaya:
#: sebuah daftar kedua berisi id layer melenceng dari yang pertama tanpa suara,
#: dan sebuah layer yang salah terdaftar tetap menggambar, tetap menjawab 200,
#: dan terlihat benar. Menambah layer baru sekarang cukup di satu tempat.
#:
#: ANGKA YANG MEMBATASI DAFTARNYA, tetap dicatat di sini karena ia milik jalur
#: order. Hanya dua detektor pernah lewat rig berbiaya, `docs/detectors_costed.json`.
#: `order_block` PASS: -0,0429 R di atas gerbang lawan -0,1192 di bawah, selisih
#: +0,0764 dengan Welch t = +6,95, 17 dari 18 sel, walk-forward 8 dari 8.
#: `fvg` GAGAL di sana, -0,1005 dengan t = -4,48 dan 3 dari 17 sel, artinya
#: gerbangnya TERBALIK - lalu `tools/fvg_inverted.py` mengukur sisi BAWAH-nya di
#: 30 menit dan menemukan +0,2188 R di n=3.799 dengan t lawan nol +8,53 dan
#: walk-forward 8 dari 8, bertahan +0,1354 dan +0,1235 di kontrol resolusi 1
#: menit. Karena itu `fvg` masuk dengan gerbang `ceiling` dan hanya di 30m.
#:
#: TIDAK SATU PUN POSITIF SENDIRI di rig 1 jam: supply_demand -0,0153 R,
#: order_block -0,0429 dengan t sendiri -6,21.
ORDERABLE_LAYERS: tuple[str, ...] = tuple(
    layer.id for layer in LAYERS if layer.orderable
)
GATE_DIRECTION: dict[str, str] = {
    layer.id: (layer.gate or "floor") for layer in LAYERS if layer.orderable
}
MEASURED_INTERVALS: dict[str, tuple[str, ...]] = {
    layer.id: layer.measured_intervals
    for layer in LAYERS if layer.measured_intervals
}


def round_robin(rows: list[tuple]) -> list[tuple]:
    """Satu kandidat per simbol bergiliran, urutan di dalam simbol dipertahankan.

    KENAPA INI ADA. `by_method_ranked` mengembalikan `(symbol, zone.id)` dan
    `cycle` memotong daftarnya di `max_orders`, jadi urutan alfabetis simbol
    MENJADI prioritas. Dengan config daemon di `start.bat`,
    `--symbol mt5:XAUUSD,mt5:BTCUSD` dan `--max-orders` default 2, "BTCUSD"
    mendahului "XAUUSD" sehingga KEDUA slot selalu jatuh ke BTC dan XAU hanya
    dapat order kalau BTC punya kurang dari dua kandidat. Diukur 2 September
    2026: BTCUSD 30m 9 kandidat dan 15m 10 kandidat, jadi ambangnya tidak pernah
    tercapai dan XAU tidak akan pernah diorder oleh daemon.

    INI BUKAN KUNCI SELEKSI, dan bedanya penting. `tools/order_key.py`
    memprakregistrasi tujuh kandidat kunci urut dan TIDAK SATU PUN memisahkan
    hasil, yang sebabnya `by_method` cuma mengembalikan `(zone.id,)` sekarang.
    Fungsi ini tidak mengklaim kandidat mana lebih baik. Ia menghapus prioritas
    yang tidak pernah dipilih siapa pun, yaitu urutan abjad nama instrumen.

    Deterministik: urutan simbolnya datang dari daftar yang SUDAH terurut, jadi
    dua run di tree yang sama memberi hasil yang sama.
    """
    groups: dict[str, list[tuple]] = {}
    for row in rows:
        groups.setdefault(row[0], []).append(row)
    out: list[tuple] = []
    for i in range(max((len(g) for g in groups.values()), default=0)):
        out.extend(g[i] for g in groups.values() if i < len(g))
    return out


def candidates(
    symbol: str,
    interval: str,
    bars: int,
    equity: float | None = None,
    risk_pct: float = 0.01,
    lot: LotSpec | None = None,
    rules: Rules | None = None,
    partners: dict[str, list] | None = None,
    layer: str = "supply_demand",
    no_cisd_in_band: bool = False,
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
    if layer not in ORDERABLE_LAYERS:
        raise ValueError(
            f"layer {layer!r} tidak ada di ORDERABLE_LAYERS {ORDERABLE_LAYERS}; "
            "lihat komentar di sana untuk angka yang membatasi daftarnya"
        )
    allowed_intervals = MEASURED_INTERVALS.get(layer)
    if allowed_intervals is not None and interval not in allowed_intervals:
        raise ValueError(
            f"layer {layer!r} cuma terukur di {allowed_intervals}, bukan "
            f"{interval!r}. Lihat MEASURED_INTERVALS untuk kenapa: angkanya "
            "diukur di satu timeframe dan tidak berlaku di yang lain"
        )
    params = (
        SupplyDemandParams(max_zones_per_side=0)
        if layer == "supply_demand"
        else ImbalanceParams(max_zones_per_side=0)
    )
    atr = float(wilder_atr(high, low, close, params.atr_period)[-1])
    zones, _ = DETECTORS[layer](candles, params)
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
    above_gate: list[str] = []
    cisd_in_band: list[str] = []

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
            # LAYER YANG SAMA, karena `mark_nesting` menjawab "zona ini
            # bersarang di zona derajat atas", dan menyandingkan order block
            # lokal ke box supply/demand di atasnya akan menjawab pertanyaan
            # yang berbeda dengan nama yang sama.
            higher_zones, _ = DETECTORS[layer](higher_bars, params)
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
        # ARAHNYA PER LAYER, lihat `GATE_DIRECTION`. `floor` membuang yang di
        # BAWAH gerbang, `ceiling` membuang yang di ATAS, dan untuk `fvg`
        # arahnya terbalik karena populasi yang terukur ada di sisi bawahnya.
        departure = zone.departure_atr or 0.0
        if GATE_DIRECTION.get(layer, "floor") == "floor":
            if departure < DEPARTURE_GATE_ATR:
                continue
        elif departure >= DEPARTURE_GATE_ATR_CEILING:
            above_gate.append(zone.id)
            continue

        # FILTER CISD-DI-DALAM-BLOCK, dan ia POPULASI bukan penolakan.
        #
        # Sekelas dengan departure di bawah gerbang dan biaya di atas rasio:
        # sebuah order block yang memuat level CISD baru di dalam band-nya bukan
        # anggota populasi yang angka order_block dihitung padanya. Diukur pada
        # resolusi 5 menit dengan biaya, n=8.170: dengan CISD baru di dalam
        # -0,1119 R, tanpa +0,0244 R, delta -0,1363 dengan Welch t = -7,07 lawan
        # kritis 2,24 dan KEDELAPAN fold walk-forward bertanda sama. Itu
        # pemisahan terkuat yang repo ini punya.
        #
        # DAN INI YANG HARUS DIBACA SEBELUM MEMPERCAYAINYA: DI BAR KEPUTUSAN IA
        # HAMPIR TIDAK PERNAH MENGIKAT. Studinya mengevaluasi kondisinya di BAR
        # SENTUHAN (`now = times[row["at"]]`, `csid_ob_intrabar.py:147`), saat
        # harga sudah datang ke block. Loop ini mengevaluasinya di bar
        # KEPUTUSAN, saat harga masih jauh, dan sebuah CISD yang lahir dalam 50
        # bar terakhir duduk dekat harga sekarang sementara setiap zona yang
        # masih `fresh` justru yang jauh dari harga. Diukur pada XAUUSD 30m 2
        # September 2026: 4 CISD dalam 50 bar terakhir di 4304-4360 dengan harga
        # 4358, 20 order block fresh lolos gerbang di 3991-4139, dan NOL
        # persinggungan. Tanpa batas kebaruan 18 dari 20 kena, yang persis
        # kondisi degenerate 95 persen yang studinya tolak.
        # Jadi angka -0,1363 R itu BELUM terpasang di jalur order, dan flag ini
        # tidak boleh dibaca sebagai sudah. Yang benar mengevaluasinya di saat
        # pending terisi, dan hook itu belum ada. Flag-nya tetap di sini karena
        # ia benar untuk pemanggil yang memang punya bar sentuhan, dan karena
        # `cycle` mencetak saat ia tidak mengikat alih-alih diam.
        #
        # DEFAULTNYA MATI, dan itu bukan kehati-hatian kosong. Filter ini diukur
        # pada `order_block` saja. Memasangnya ke `supply_demand` berarti
        # memakai angka satu detektor untuk menyaring detektor lain, dan versi
        # supply/demand dari pertanyaan yang sama sudah diukur NULL sendiri
        # (`cisd_in_band`, t=-1,29, `docs/checklist_outcomes.json`).
        if no_cisd_in_band and recent_in_band(
            zone.bottom, zone.top, cisd_events, last.time, step
        ):
            cisd_in_band.append(zone.id)
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
        # JARAK MELAWAN TESIS, dihitung di sini karena di sinilah ketiga
        # angkanya ada sekaligus: entry dari plan, harga dari bar keputusan, dan
        # ATR yang sama yang men-scale stop-nya. `app/ict.py` tidak punya dua
        # dari tiga.
        adverse_atr = adverse_excursion_atr(
            plan.entry, float(last.close), atr, long_side)
        out.append((zone, plan, ict_setup(zone, state, stack, rules,
                                          ssmt_side=ssmt_side,
                                          two_stage_confirmed=two_stage_confirmed,
                                          reward_r=plan.reward_r,
                                          adverse_atr=adverse_atr,
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
    if no_cisd_in_band and not cisd_in_band and out:
        # SEBUAH GERBANG YANG DIMINTA DAN TIDAK MENGIKAT HARUS BERSUARA. Diam di
        # sini terbaca sama dengan "sudah disaring", dan itu kelas cacat yang
        # repo ini paling sering ketemu: laporan hijau di atas harness yang
        # tidak pernah memeriksa apa pun.
        print(f"  filter CISD-di-dalam-band DIMINTA TAPI TIDAK MENGIKAT: 0 dari "
              f"{len(out)} kandidat memuat CISD dalam {RECENT_CISD_BARS} bar. "
              f"Di bar keputusan kondisinya hampir selalu salah, lihat "
              f"komentarnya di gerbang itu")
    if above_gate:
        print(f"  {len(above_gate)} zona ditolak karena DI ATAS gerbang "
              f"{DEPARTURE_GATE_ATR_CEILING} ATR (arah gerbang layer ini `ceiling`, "
              f"populasi terukurnya sisi bawah): "
              f"{', '.join(above_gate[:4])}"
              f"{' ...' if len(above_gate) > 4 else ''}")
    if cisd_in_band:
        print(f"  {len(cisd_in_band)} zona ditolak filter CISD-di-dalam-band "
              f"(baru dalam {RECENT_CISD_BARS} bar): "
              f"{', '.join(cisd_in_band[:4])}"
              f"{' ...' if len(cisd_in_band) > 4 else ''}")
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


def _market_context(candles: list, _symbol: str) -> dict:
    """Enhancement context from bars already in memory. One call per symbol."""
    from datetime import timezone
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    volume = np.array([c.volume for c in candles], dtype=np.float64)

    # ADX
    adx_arr = wilder_adx(high, low, close, 14)
    adx = float(adx_arr[-1])
    adx_label = "weak" if adx < 20 else ("strong" if adx > 40 else "trending")

    # Bollinger Band Width percentile
    bbw = bb_width(close, 20, 2.0)
    bbw_last = float(bbw[-1])
    window = bbw[-200:] if len(bbw) >= 200 else bbw
    pct = float(np.sum(window < bbw_last) / len(window) * 100) if len(window) else 50
    bb_label = "squeeze" if pct < 20 else ("expansion" if pct > 80 else "normal")

    # ATR budget: today's range / ATR(14)
    atr_arr = wilder_atr(high, low, close, 14)
    atr_val = float(atr_arr[-1]) if atr_arr[-1] > 0 else 1.0
    last_dt = datetime.fromtimestamp(candles[-1].time, tz=timezone.utc)
    midnight = last_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight_ts = int(midnight.timestamp())
    today_bars = [c for c in candles if c.time >= midnight_ts]
    if today_bars:
        day_hi = max(c.high for c in today_bars)
        day_lo = min(c.low for c in today_bars)
        atr_pct_used = (day_hi - day_lo) / atr_val
    else:
        atr_pct_used = 0.0

    # VWAP daily
    anchor_idx = 0
    for i, c in enumerate(candles):
        if c.time >= midnight_ts:
            anchor_idx = i
            break
    vwap_arr = compute_vwap(high, low, close, volume, anchor_idx)
    vwap_val = float(vwap_arr[-1]) if not np.isnan(vwap_arr[-1]) else float(close[-1])
    vwap_position = "above" if close[-1] > vwap_val else "below"

    # Volume profile
    vp = compute_vp(high, low, close, volume)
    vp_poc = vp.get("poc", 0.0)
    vah = vp.get("vah", vp_poc)
    val_ = vp.get("val", vp_poc)
    last_close = float(close[-1])
    if last_close > vah:
        vp_position = "above_va"
    elif last_close < val_:
        vp_position = "below_va"
    else:
        vp_position = "in_va"

    return {
        "adx": adx, "adx_label": adx_label,
        "bb_width": bbw_last, "bb_label": bb_label,
        "atr_pct_used": atr_pct_used,
        "vwap_daily": vwap_val, "vwap_position": vwap_position,
        "vp_position": vp_position, "vp_poc": vp_poc,
    }


def _news_impact_score() -> int:
    """Sync news score 0-3. Same keywords as checklist._enrich_news_impact."""
    # ponytail: sync fetch, no async; try/except because feed may be down
    try:
        import json
        from urllib.request import urlopen, Request
        from app.news import FEED_URL, parse, select
        from app.clock import to_ny
        req = Request(FEED_URL, headers={"User-Agent": "Zonelab/0.1"})
        with urlopen(req, timeout=5) as resp:
            week = parse(json.loads(resp.read()))
        if week.error:
            return 0
        import time as _time
        now_ny = to_ny(int(_time.time())).date()
        from app.clock import to_ny as _to_ny
        high = select(week.events, impact="High")
        today_events = [e for e in high if _to_ny(e.time).date() == now_ny]
        if not today_events:
            return 0
        major = {"non-farm", "nonfarm", "cpi ", "fomc", "federal funds",
                 "interest rate decision", "monetary policy"}
        titles = [e.title.lower() for e in today_events]
        major_count = sum(1 for t in titles if any(kw in t for kw in major))
        if major_count >= 2:
            return 3
        if major_count == 1:
            return 2
        return 1
    except Exception:
        return 0


def _cot_signal(symbol: str) -> dict | None:
    """COT summary, lazy-imported because module may not exist in tests."""
    try:
        from app.cot import cot_summary
        return cot_summary(symbol.split(":")[-1])
    except Exception:
        return None


def daily_fvg_bias(daily: list, price: float) -> dict:
    """The newest unfilled daily FVG that CONTAINS `price`, or an empty dict.

    THE ONLY DEFINITION OF THIS GATE, and it is a function so a measurement can
    call it with a truncated series. `_htf_confluence` loads the LAST 200 daily
    bars, which is correct live and pure lookahead at a past bar; a rig that
    reimplemented the scan instead would be testing its own copy. `--htf-gate`
    blocks real orders on this answer, so the copy that gets measured has to be
    the copy that runs.

    Scanned newest first and stops at the first FVG that both survives and
    contains the price, so an older gap never overrides a newer one.

    "Filled" here means price CLOSED THROUGH THE FAR SIDE - a demand gap dies
    when a close lands below its bottom, a supply gap when a close lands above
    its top. That is full invalidation and not mitigation, and it is the rule
    the shipped gate already used; it is written down here rather than changed.
    """
    result: dict = {}
    if len(daily) < 3:
        return result
    for i in range(len(daily) - 2, 0, -1):
        c0, c2 = daily[i - 1], daily[i + 1]
        if c2.low > c0.high:
            top, bottom, side = c2.low, c0.high, "demand"
        elif c0.low > c2.high:
            top, bottom, side = c0.low, c2.high, "supply"
        else:
            continue
        filled = any(
            (daily[j].close > top if side == "supply" else daily[j].close < bottom)
            for j in range(i + 2, len(daily))
        )
        if filled:
            continue
        if bottom <= price <= top:
            result["htf_bias"] = "bearish" if side == "supply" else "bullish"
            result["htf_fvg_side"] = side
            result["htf_fvg_top"] = top
            result["htf_fvg_bottom"] = bottom
            break
    return result


def _htf_confluence(symbol: str, chart_candles: list) -> dict:
    """HTF PD Array (daily FVG), H1 CISD, PDH/PDL sweep. One call per symbol."""
    result: dict = {}
    price = chart_candles[-1].close if chart_candles else 0.0

    # 1. Daily FVG: is price inside one?
    try:
        result.update(daily_fvg_bias(history.load(symbol, "1d", 200), price))
    except Exception:
        pass

    # 2. CISD H1: most recent direction
    try:
        h1 = history.load(symbol, "1h", 200)
        if len(h1) >= 10:
            events, _ = cisds(h1)
            if events:
                last = events[-1]
                result["cisd_h1"] = last.direction
                result["cisd_h1_label"] = "bullish" if last.direction > 0 else "bearish"
                result["cisd_h1_level"] = last.level
    except Exception:
        pass

    # 3. PDH/PDL sweep from chart bars
    if len(chart_candles) >= 50:
        from app.clock import to_ny, ny_wall
        last_ny = to_ny(chart_candles[-1].time)
        midnight = ny_wall(last_ny.year, last_ny.month, last_ny.day, 0)
        prev_midnight = midnight - 86400
        prev_bars = [c for c in chart_candles if prev_midnight <= c.time < midnight]
        today_bars = [c for c in chart_candles if c.time >= midnight]
        if prev_bars and today_bars:
            pdh = max(c.high for c in prev_bars)
            pdl = min(c.low for c in prev_bars)
            today_high = max(c.high for c in today_bars)
            today_low = min(c.low for c in today_bars)
            result["bsl_swept"] = today_high > pdh
            result["ssl_swept"] = today_low < pdl
            if result["bsl_swept"] and not result["ssl_swept"]:
                result["sweep_bias"] = "bearish"
            elif result["ssl_swept"] and not result["bsl_swept"]:
                result["sweep_bias"] = "bullish"

    return result


def gather(
    symbols: list[str],
    intervals: list[str],
    bars: int,
    equity: float | None,
    risk_pct: float,
    lots: dict[str, LotSpec] | None,
    rules: Rules,
    partners: list[str] | None = None,
    layer: str = "supply_demand",
    no_cisd_in_band: bool = False,
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
                symbol, interval, bars, equity, risk_pct, lot, rules, series,
                layer=layer, no_cisd_in_band=no_cisd_in_band,
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
    return round_robin(found), blocked, series


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
    weekly_loss_pct: float = 0.0,
    layer: str = "supply_demand",
    no_cisd_in_band: bool = False,
    streak_halve: int = 0,
    adx_min: float = 0.0,
    atr_budget_max: float = 0.0,
    news_max: int = 99,
    htf_gate: bool = False,
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

    # EQUITY CURVE MANAGEMENT: setelah N kekalahan berturut, risk_pct dibelah
    # dua untuk setiap kelipatan N berikutnya. Berbeda dari daily/weekly cap
    # yang MENGHENTIKAN trading: ini MEMPERKECIL ukuran posisi secara bertahap.
    if streak_halve > 0 and mt5 is not None:
        streak = loss_streak(mt5)
        if streak is not None and streak >= streak_halve:
            scale = 0.5 ** (streak // streak_halve)
            print(f"  equity curve: {streak} kekalahan berturut, risk diturunkan "
                  f"{risk_pct:.4f} -> {risk_pct * scale:.4f} (x{scale})")
            risk_pct = risk_pct * scale
        elif streak is not None:
            print(f"  equity curve: {streak} kekalahan berturut, di bawah "
                  f"ambang {streak_halve}")
        else:
            print("  equity curve: streak TIDAK TERBACA, risk_pct tidak disentuh")
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
            "weekly_loss_pct": weekly_loss_pct,
            "symbols": symbols, "intervals": intervals,
            "partners": list(partners or []),
            "adx_min": adx_min, "atr_budget_max": atr_budget_max,
            "news_max": news_max, "htf_gate": htf_gate}

    ranked, blocked, series = gather(
        symbols, intervals, bars, equity, risk_pct, lots, rules, partners,
        layer=layer, no_cisd_in_band=no_cisd_in_band,
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

    # Enhancement gates: market context per symbol, computed once
    _contexts: dict[str, dict] = {}
    for _bare, _candles in series.items():
        if _candles:
            _contexts[_bare] = _market_context(_candles, _bare)

    # Global: news impact (one value for all symbols)
    _news_score = _news_impact_score()
    if _news_score > 0:
        print(f"  news impact: {_news_score}/3")

    # COT per symbol (cached per ISO week, at most one fetch)
    _cot: dict[str, dict | None] = {}
    for _sym in symbols:
        _bare_s = _sym.split(":")[-1]
        _cot_entry = _cot_signal(_sym)
        _cot[_bare_s] = _cot_entry
        if _cot_entry:
            print(f"  COT {_bare_s}: {_cot_entry.get('signal', '?')} "
                  f"(commercial {_cot_entry.get('commercial_net', '?')})")

    # HTF confluence per symbol: daily FVG, H1 CISD, PDH sweep
    _htf: dict[str, dict] = {}
    if htf_gate:
        for _sym in symbols:
            _bare_s = _sym.split(":")[-1]
            _candles = series.get(_bare_s, [])
            if _candles:
                _htf[_bare_s] = _htf_confluence(_sym, _candles)
                htf_info = _htf[_bare_s]
                parts = []
                if htf_info.get("htf_bias"):
                    parts.append(f"daily FVG {htf_info['htf_bias']}")
                if htf_info.get("cisd_h1_label"):
                    parts.append(f"CISD H1 {htf_info['cisd_h1_label']}")
                if htf_info.get("sweep_bias"):
                    parts.append(f"sweep {htf_info['sweep_bias']}")
                elif htf_info.get("bsl_swept"):
                    parts.append("BSL swept")
                elif htf_info.get("ssl_swept"):
                    parts.append("SSL swept")
                if parts:
                    print(f"  HTF {_bare_s}: {', '.join(parts)}")

    # OPEN POSITIONS COUNT TOWARDS THE CAP, and when they cannot be read the book
    # says so. A cap computed on half the book is a cap that does not bind, and
    # `Book.partial` is what makes that visible in the refusal text.
    book = Book(equity=equity or 0.0, cap_pct=cap_pct, corr_max=corr_max,
                daily_loss_pct=daily_loss_pct,
                realised_today=realised_today(mt5) if daily_loss_pct > 0 else 0.0,
                weekly_loss_pct=weekly_loss_pct,
                realised_this_week=realised_this_week(mt5) if weekly_loss_pct > 0 else 0.0)
    if daily_loss_pct > 0:
        print(f"  pengaman kerugian harian {daily_loss_pct:.2%}, terealisasi "
              f"hari ini {book.realised_today if book.realised_today is not None else 'TIDAK TERBACA'}")
    if weekly_loss_pct > 0:
        print(f"  pengaman kerugian mingguan {weekly_loss_pct:.2%}, terealisasi "
              f"minggu ini {book.realised_this_week if book.realised_this_week is not None else 'TIDAK TERBACA'}")
    # NONE BERARTI TIDAK TERBACA, BUKAN KOSONG. Set kosong akan menyatakan
    # "tidak ada ticket hidup", yang membuka setiap zona yang pernah diorder.
    live_tickets: set[int] | None = None
    if mt5 is not None:
        # PENDING IKUT DIHITUNG, dan tanpa itu cap ini tidak pernah mengikat
        # antar run. Tool ini menempatkan LIMIT, jadi risiko yang baru saja ia
        # kirim adalah pending, bukan posisi. Sampai 27 Agustus 2026 book hanya
        # membaca `positions_get`, sehingga satu pending XAUUSD berisiko 43.92
        # dari run sebelumnya tidak terlihat dan run berikutnya berangkat dari
        # book yang lebih ringan 4.5% dari kenyataan.
        positions = mt5.positions_get() or []
        pendings = mt5.orders_get() or []
        # DIPAKAI DUA KALI, dibaca sekali. Gate idempotensi di bawah butuh
        # daftar ticket yang HIDUP, dan membacanya lagi di sana akan menanyakan
        # order book dua kali untuk satu keputusan - dua jawaban yang bisa
        # berbeda kalau sebuah pending terisi di antaranya.
        live_tickets = {int(x.ticket) for x in (*positions, *pendings)}
        rows = [(p.symbol, p.price_open, p.sl, p.volume) for p in positions]
        rows += [(o.symbol, o.price_open, o.sl, o.volume_current)
                 for o in pendings]
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
        # GATE IDEMPOTENSI, dan ia dulu mengunci zona SELAMANYA. Ia menyaring
        # `event == "placed"` saja, jadi order yang sudah dibatalkan tetap
        # menahan zonanya dan penolakannya berbunyi "SUDAH pernah diorder,
        # ticket N". Diukur 2 September 2026: 35 zona punya record `placed` dan
        # 29 di antaranya tidak punya satu pun ticket yang masih hidup.
        #
        # DUA SUMBER, karena satu saja tidak cukup. `journal.open_tickets`
        # membuang yang journal TAHU sudah mati (13 dari 29); sisa 16 hilang
        # dari broker tanpa journal pernah tahu, dan cuma order book yang bisa
        # menjawab itu. `live_tickets` None berarti terminalnya tidak terbaca,
        # dan di keadaan itu jawaban konservatif dipertahankan: sebuah order
        # yang MUNGKIN masih ada tidak dipasang dua kali.
        already = journal.open_tickets(zone.id, symbol)
        if live_tickets is not None:
            already = [t for t in already if t in live_tickets]
        head = (f"  {symbol} {interval} {zone.kind.value} {zone.side.value}  "
                f"entry {plan.entry:.3f} stop {plan.stop:.3f} tp {plan.target:.3f}"
                # BACAAN, DAN DINAMAI BEGITU. Angka ini dicetak di sebelah order
                # yang sedang dikirim, jadi "checklist 12/17" terbaca sebagai
                # peringkat mutu - dan ia terukur bukan itu: skor agregatnya tidak
                # memisahkan hasil (docs/checklist_outcomes.json, separates false,
                # rho -0,035 demeaned), satu dari tujuh belas klausanya melewati
                # ambang dan ke arah sebaliknya, dua konstan, dan dua memberi angka
                # identik. Ia tetap dicetak karena operator ingin tahu klausa mana
                # yang terpenuhi; yang berubah kalimatnya berhenti mengklaim mutu.
                f"  klausa terpenuhi {checklist.met}/{len(checklist.conditions)}"
                f" (bacaan, bukan peringkat)"
                # DICETAK TERPISAH, TIDAK DILIPAT KE DALAM SKOR. Angka ini yang
                # hilang pada 4 September 2026 ketika sebuah sell limit dipasang
                # 2,10x ATR di ATAS pasar dengan tesis turun. Ia ada di detail
                # klausa sejak hari itu, dan detail klausa tidak dicetak di
                # sebelah order, jadi ia harus punya barisnya sendiri.
                + _adverse_line(checklist))
        # PELUANG DILEKATKAN DI TIAP KANDIDAT, dan sisinya dipilih dari sisi
        # gerbang layer ini bukan dari `zone.departure_atr` mentah. Untuk `fvg`
        # gerbangnya TERBALIK, jadi populasi yang benar-benar diorder adalah
        # sisi BAWAH (n=1939, P(target) 14,4%) dan bukan sisi atas (n=62,
        # P(target) 1,6%). Melaporkan sisi yang salah akan mencetak peluang dari
        # populasi yang tidak pernah diorder.
        odds = outcome_odds(
            layer, symbol, interval,
            cleared_gate=(GATE_DIRECTION.get(layer, "floor") == "floor"),
        )
        head += chr(10) + "      " + odds_line(odds)
        # SATU KALI PER KANDIDAT, dipakai enam cabang di bawah. Enam pemanggilan
        # identik adalah enam tempat argumennya bisa melenceng dari yang lain,
        # dan `layer` yang salah di salah satunya menulis gerbang yang keliru ke
        # journal tanpa satu pun cabang lain terlihat berubah.
        why_lines = grounds(zone, plan, layer, odds) + checklist.why()
        if already:
            print(f"{head}\n      SUDAH pernah diorder, ticket {already[0]}")
            skipped += 1
            continue

        # Enhancement gates: computed per-symbol context
        bare_sym = symbol.split(":")[-1]
        ctx = _contexts.get(bare_sym, {})

        # Enhancement gate: ADX minimum trend strength
        if adx_min > 0 and ctx.get("adx", 100) < adx_min:
            label = ctx.get("adx_label", "?")
            print(f"{head}\n      REGIME menolak: ADX {ctx['adx']:.1f} ({label}) < {adx_min}")
            if send:
                journal.record("refused", why=why_lines, rule=rule,
                               zone_id=zone.id, symbol=symbol,
                               plan=plan.model_dump(mode="json"),
                               blockers=[f"ADX {ctx['adx']:.1f} < {adx_min} (regime too weak)"])
            refused += 1
            continue

        # Enhancement gate: ATR budget exhaustion
        if atr_budget_max > 0 and ctx.get("atr_pct_used", 0) > atr_budget_max:
            print(f"{head}\n      ATR BUDGET menolak: {ctx['atr_pct_used']:.0%} used > {atr_budget_max:.0%}")
            if send:
                journal.record("refused", why=why_lines, rule=rule,
                               zone_id=zone.id, symbol=symbol,
                               plan=plan.model_dump(mode="json"),
                               blockers=[f"ATR budget {ctx['atr_pct_used']:.0%} > {atr_budget_max:.0%}"])
            refused += 1
            continue

        # Enhancement gate: high-impact news
        if _news_score >= news_max:
            print(f"{head}\n      NEWS menolak: impact {_news_score}/3 >= {news_max}")
            if send:
                journal.record("refused", why=why_lines, rule=rule,
                               zone_id=zone.id, symbol=symbol,
                               plan=plan.model_dump(mode="json"),
                               blockers=[f"news impact {_news_score} >= {news_max}"])
            refused += 1
            continue

        # Enhancement gate: HTF PD Array direction
        htf_info = _htf.get(bare_sym, {})
        htf_bias = htf_info.get("htf_bias")
        if htf_bias:
            zone_dir = "sell" if zone.side == ZoneSide.SUPPLY else "buy"
            htf_dir = "sell" if htf_bias == "bearish" else "buy"
            if zone_dir != htf_dir:
                print(f"{head}\n      HTF menolak: daily FVG {htf_bias}, "
                      f"zone {zone.side.value} berlawanan arah")
                if send:
                    journal.record("refused", why=why_lines, rule=rule,
                                   zone_id=zone.id, symbol=symbol,
                                   plan=plan.model_dump(mode="json"),
                                   blockers=[f"HTF daily FVG {htf_bias} vs zone {zone.side.value}"])
                refused += 1
                continue

        # Enhancement context (logged, not gating)
        if ctx:
            why_lines.append(f"regime: ADX {ctx.get('adx', 0):.1f} ({ctx.get('adx_label', '?')}), "
                             f"BB {ctx.get('bb_label', '?')}")
            why_lines.append(f"atr_budget: {ctx.get('atr_pct_used', 0):.0%} of daily ATR used")
            why_lines.append(f"vwap: {ctx.get('vwap_position', '?')}, vp: {ctx.get('vp_position', '?')}")
        if htf_info:
            parts = []
            if htf_bias:
                parts.append(f"daily FVG {htf_bias}")
            cisd_lbl = htf_info.get("cisd_h1_label")
            if cisd_lbl:
                parts.append(f"CISD H1 {cisd_lbl}")
            sweep_b = htf_info.get("sweep_bias")
            if sweep_b:
                parts.append(f"sweep {sweep_b}")
            if parts:
                why_lines.append(f"htf: {', '.join(parts)}")
        cot_info = _cot.get(bare_sym)
        if cot_info:
            why_lines.append(f"cot: {cot_info.get('signal', '?')} "
                             f"(commercial {cot_info.get('commercial_net', 0):+d})")

        # THE ICT GATE, and it sits before the risk checks on purpose: a setup the
        # method rejects should not consume a slot, and its refusal should name
        # the clause rather than the account.
        missing = checklist.failed_required(rules)
        if missing:
            print(f"{head}\n      CHECKLIST menolak: {', '.join(missing)}")
            if send:
                journal.record("refused", why=why_lines,
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
                journal.record("refused", why=why_lines,
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
            journal.record("refused", why=why_lines,
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
                                   why=why_lines,
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
            journal.record("refused", why=why_lines,
                           rule=rule, zone_id=zone.id, symbol=symbol,
                           plan=plan.model_dump(mode="json"), blockers=[why_not])
            refused += 1
            continue
        journal.record("placed", why=why_lines,
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
    parser.add_argument(
        "--layer", default="supply_demand", choices=ORDERABLE_LAYERS,
        help="detektor yang dipasangi order. Daftarnya dibatasi ke yang punya "
             "populasi terukur di rig berbiaya, lihat ORDERABLE_LAYERS. "
             "`fvg` HANYA di 30m dan gerbangnya TERBALIK di sana: populasi "
             "terukurnya sisi BAWAH gerbang, +0,2188 R di n=3.799 dengan t "
             "lawan nol +8,53 dan walk-forward 8 dari 8, bertahan +0,1354 dan "
             "+0,1235 di kontrol resolusi 1 menit")
    parser.add_argument(
        "--no-cisd-in-band", action="store_true",
        help="buang order block yang memuat level CISD baru (dalam 50 bar) di "
             "dalam band-nya. Diukur pada order_block: -0,1119 R dengan, "
             "+0,0244 R tanpa, delta -0,1363 t=-7,07, 8 dari 8 fold. Filter "
             "ini yang membuat order_block layak dipilih sama sekali")
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
    parser.add_argument("--weekly-loss-pct", type=float, default=0.0,
                        help="berhenti mengirim order kalau kerugian minggu ini "
                             "sudah mencapai persen equity. Nol mematikan pengaman")
    parser.add_argument("--streak-halve", type=int, default=0,
                        help="belah dua risk_pct setiap N kekalahan berturut. "
                             "Misal 3: 3 kalah -> 50%%, 6 kalah -> 25%%. "
                             "Nol mematikan")
    parser.add_argument("--adx-min", type=float, default=0.0,
                        help="Minimum ADX to allow orders (0=disabled)")
    parser.add_argument("--atr-budget-max", type=float, default=0.0,
                        help="Max ATR budget pct_used (0=disabled, 1.5=150%%)")
    parser.add_argument("--news-max", type=int, default=99,
                        help="Max news impact score (0-3, 99=disabled)")
    parser.add_argument("--htf-gate", action="store_true", default=False,
                        help="Enable HTF direction gate (daily FVG bias)")
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
          args.daily_loss_pct, args.weekly_loss_pct,
          args.layer, args.no_cisd_in_band, args.streak_halve,
          args.adx_min, args.atr_budget_max, args.news_max,
          args.htf_gate)


if __name__ == "__main__":
    main()
