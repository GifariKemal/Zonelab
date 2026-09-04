"""Praregistrasi kelima: apakah checklist ICT memisahkan hasil, klausa demi klausa.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.checklist_outcomes \
        > ../docs/checklist_outcomes.json

Ditulis 30 Agustus 2026, SEBELUM satu angka pun dihitung. Bagian 1 sampai 6 di
bawah ini adalah praregistrasinya; angkanya keluar di stdout sebagai JSON.

===========================================================================
1. PERTANYAANNYA, DAN KENAPA IA BELUM PERNAH DIJAWAB
===========================================================================

`app/layers.py` menyatakan untuk layer `checklist`: "None of the items has been
measured against outcomes". Itu tidak lagi seluruhnya benar - praregistrasi
kedua (21 Agustus 2026, `docs/PRAREGISTRASI-KONDISI.md` bagian 8) sudah menguji
sepuluh klausa, dan praregistrasi ketiga sudah menguji `ote`. Yang belum:

  a. Enam klausa sisa dari tujuh belas: `day_of_week`,
     `manipulation_after_accumulation`, `two_stage_confirmed`, `min_rr`,
     `ssmt`, `draw_agrees`. Empat di antaranya TIDAK PERNAH BISA menyala di
     `tools/conditioned.py` karena harness itu memanggil `evaluate` tanpa
     `ssmt_side`, `two_stage_confirmed`, `reward_r`, dan `always_open`. Kolom
     yang seragam bukan temuan, ia keluhan, dan praregistrasi kedua sudah
     kena dua kali (`cisd_in_band` dan `htf_nested`). Harness ini mengisi
     keempat argumen itu dengan cara yang sama persis dengan `tools/execute.py`.

  b. YANG PALING LOAD-BEARING: skor agregat `met`. `tools/execute.py` baris
     terakhir `candidates()` mengurutkan kandidat dengan
     `out.sort(key=lambda t: (-t[2].met, ...))`, jadi kandidat dengan skor
     checklist lebih tinggi DIDAHULUKAN. Tidak ada satu angka pun di repo ini
     yang mendukung bahwa skor lebih tinggi berarti hasil lebih baik.
     `app/ict.py` sendiri menulis "It does not sum the conditions into a score",
     dan `tools/execute.py` menjumlahkannya lewat `Setup.met`.

===========================================================================
2. POPULASI DAN OUTCOME
===========================================================================

| Hal        | Nilai |
|---|---|
| Instrumen  | `SYMBOLS` di bawah, delapan, daftar tertutup |
| Timeframe  | 1 jam, zona dideteksi di sana |
| Resolusi   | bar 5 menit, lewat `tools/intrabar.py:resolved` |
| Populasi   | first touch tiap zona `supply_demand` dengan `departure_atr >= 2.0` dan target terbaca |
| Outcome    | R multiple setelah biaya `exness_raw`, flat di rollover 21:00 UTC |

RESOLUSI INTRABAR MENGIKAT, dan bukan kehalusan. `docs/QA-QUANT.md` mencatat
apa yang terjadi tanpanya: mengizinkan target di bar entry memberi +0,2021 R,
melarangnya memberi -0,0590 R, dan keduanya adalah sifat asumsi. Studi ini
memakai `resolved()` sehingga ambiguitasnya menyusut dari 60 menit ke 5.
Harganya dinyatakan: riwayat 5 menit di terminal ini hanya sampai April 2025,
jadi populasinya jauh lebih kecil daripada 953 trade praregistrasi kedua.

===========================================================================
3. YANG DIUJI, DAFTAR TERTUTUP
===========================================================================

  - `met`, skor checklist, sebagai level (0..17) dan sebagai split median.
  - Ketujuh belas klausa `app/ict.py:evaluate`, dalam urutan tetapnya, satu
    per satu lawan sisa populasi.

`ote` ikut diuji ulang walau `app/ict.py:MEASURED_AGAINST` sudah memuat
angkanya (12 instrumen 1h, nol sel lolos, |t| tertinggi 2,04 lawan kritis 3,20).
Ia dihitung di sini sebagai replikasi pada resolusi intrabar, bukan sebagai
temuan baru, dan verdict-nya menyebut angka lama itu.

`draw_agrees` diuji sebagai kolom walau sudah bisa diduga hasilnya konstan
`None`: `app/ict.py` menolak menyimpulkan draw dan tidak ada manusia yang
menominasikannya di dalam harness. Dinyatakan SEKARANG supaya "konstan" nanti
dilaporkan sebagai batas metode, bukan sebagai nol yang mengesankan.

===========================================================================
4. HIPOTESIS, DAN AMBANGNYA
===========================================================================

H-A (UTAMA), tiga bacaan yang semuanya ditulis sekarang:

  A1  MONOTON. Ekspektansi R tidak menurun pada setiap pasangan level `met`
      bertetangga yang `n >= MIN_GROUP`. Dilaporkan sebagai jumlah pasangan
      yang naik lawan jumlah pasangan seluruhnya. Lolos hanya kalau SEMUA
      pasangan tidak menurun.
  A2  TREN. Spearman rho antara `met` dan R positif, dengan
      `t = rho * sqrt((n-2)/(1-rho^2))` melewati nilai kritis terkoreksi.
  A3  SPLIT MEDIAN. Ekspektansi R pada `met > median(met)` melebihi
      `met <= median(met)`, Welch t melewati nilai kritis terkoreksi, dan
      tandanya sama di kedua paruh. Ini bacaan yang paling dekat dengan apa
      yang `execute.py` benar-benar lakukan: ia mengurutkan, jadi yang penting
      adalah apakah separuh atas mengalahkan separuh bawah.

H-B, per klausa: klausa memisahkan kalau ketiganya lolos, sama persis dengan
`docs/PRAREGISTRASI-KONDISI.md` bagian 4:

  1. `n >= 30` per grup.
  2. `|t|` Welch (grup lawan sisanya) melewati nilai kritis Bonferroni.
  3. Tanda selisihnya bertahan di kedua paruh sampel.

KOREKSI BANYAK-PERBANDINGAN. Alpha dua sisi 0,05 dibagi K, dengan K jumlah
SELURUH grup yang layak dinilai: tiap level `met` dengan n >= 30, ditambah
kontras split median (satu), ditambah tiap nilai tiap klausa dengan n >= 30.
K dihitung di lintasan pertama sebelum satu baris pun dilaporkan, memakai
`tools/conditioned.py:_critical_t` supaya ambangnya tidak bisa digeser setelah
melihat hasil.

KONTROL INSTRUMEN. Populasi ini menggabungkan delapan instrumen yang
ekspektansi dasarnya berbeda tanda (gerbang biaya `COST_TO_RISK_MAX` menolak
sebagian dari mereka di jalur order). Kalau distribusi `met` juga berbeda antar
instrumen, tren gabungan bisa lahir dari komposisi dan bukan dari checklist.
Jadi H-A2 dan H-A3 dihitung DUA KALI dan keduanya dilaporkan apa pun hasilnya:
sekali pada R mentah, sekali pada R yang sudah dikurangi rata-rata
instrumennya sendiri. Kalau keduanya tidak sepakat, yang di-demean yang
dipercaya, dan itu ditetapkan sekarang.

WALK-FORWARD. Seluruh baris diurutkan waktu lalu dipotong `FOLDS` bagian
sama-banyak. Tiap fold melaporkan n, rho, dan delta split median. Fold yang
gagal dilaporkan dengan namanya. TIDAK ADA PURGING di sini dan itu bukan
kelalaian: tidak ada satu parameter pun yang dipasang dari data, jadi tidak ada
kebocoran train ke test yang bisa di-purge. Yang dijawab walk-forward di sini
cuma satu: apakah tandanya bertahan sepanjang waktu.

===========================================================================
5. YANG TIDAK AKAN DILAKUKAN
===========================================================================

  - Tidak menambah instrumen, klausa, atau timeframe setelah melihat hasil.
  - Tidak membuang instrumen yang ekspektansinya negatif. Gerbang biaya
    membuangnya di jalur order, dan itu keputusan lain; membuangnya di sini
    setelah melihat hasil adalah pencarian.
  - Tidak memberi bobot pada klausa. `formation_score` memeringkat TERBALIK
    (AUC 0,464 dan 0,477) dan bobotnya sepertiga rata justru supaya tidak
    memfit noise.
  - Tidak melaporkan kolom konstan sebagai nol. Kolom yang cuma punya satu
    nilai dilaporkan `constant` beserta nilainya.

TAMBAHAN POST-HOC, DILABELI SEBAGAI POST-HOC. Run praregistrasi mengembalikan
SATU pemisahan, `dfr_side`, dan kontrol instrumen di bagian 4 cuma melindungi
H-A. Sebuah pemisahan pada R mentah di populasi delapan instrumen bisa lahir
dari komposisi: kalau nilai klausanya menumpuk di instrumen yang ekspektansinya
memang lebih rendah, kolomnya memisahkan instrumen dan bukan setup. Jadi tiap
grup klausa sekarang membawa TIGA angka tambahan, dan ketiganya post-hoc:
`delta_dm` dan `t_dm` pada R yang sudah dikurangi rata-rata instrumennya, dan
`symbols_same_sign` yang menghitung berapa dari delapan instrumen tandanya sama
dengan tanda gabungan. Angka praregistrasi (`delta`, `t`, `halves_delta`,
`separates`) TIDAK diubah dan tetap yang menentukan verdict; tiga angka baru itu
hanya boleh melemahkan bacaan, tidak boleh menguatkannya.

===========================================================================
6. YANG SUDAH DIKETAHUI AKAN BERPERILAKU ANEH
===========================================================================

  - `two_stage_confirmed` di `tools/execute.py` dihitung atas SELURUH jendela
    yang dimuat (`--bars` default 3000) tanpa batas kebaruan, jadi ia
    kemungkinan besar True hampir selalu setelah warm-up. Harness ini memakai
    jendela 3000 bar yang sama, berakhir di bar sentuhan, supaya angkanya
    adalah angka jalur order dan bukan angka baru. Kalau ia keluar konstan,
    itu temuan tentang jalur order, dan dilaporkan begitu.

CATATAN YANG DITAMBAHKAN SETELAH HARNESS CRASH, SEBELUM SATU HASIL DIBACA.
`tools/execute.py:STAGE_PAIRS` memetakan `1h` ke `("day", "90m")` dan `15m` ke
`("90m", "micro")`, dan `"90m"` BUKAN derajat yang ada: `app/quarters.py`
mengenal `quadrennial, year, month, week, day, session, micro, nano`, dan
`quarters()` melempar ValueError untuk nama lain. Di `execute.py` lemparan itu
ditangkap `except ValueError: pass`, jadi `two_stage_confirmed` di jalur order
TIDAK PERNAH BISA True pada 1 jam maupun 15 menit, tanpa satu baris log pun.
Terdeteksi 30 Agustus 2026 saat harness ini memanggil `ssmt_read` tanpa
penangkap itu.

Konsekuensinya untuk studi ini, ditetapkan sebelum angkanya dibaca:
`STAGE_FALLBACK` menerjemahkan `"90m"` ke `"session"`, derajat tepat di bawah
`day` di `ALL_DEGREES` dan jelas yang dimaksud pemetaan itu. Field
`shipped_stage_pair_valid` di output mencatat bahwa pasangan yang dikirim tidak
sah, sehingga angka klausa ini adalah angka klausa yang DIMAKSUD, bukan angka
klausa yang dijalankan produksi. Klausa yang dijalankan produksi konstan False,
dan itu temuan tersendiri.
  - `draw_agrees` konstan `None`, lihat bagian 3.
  - `min_rr` dihitung dari `plan.reward_r`, dan populasi ini SUDAH menuntut
    target terbaca, jadi distribusinya condong.
"""

from __future__ import annotations

import argparse
import asyncio
import bisect
import contextlib
import json
import sys
from math import sqrt

import numpy as np

from app.aligned import load_aligned
from app.cisd import cisds
from app.clock import trades_when_shut
from app.conditions import at_bar
from app.confluence import mark_nesting
from app.costs import cost_to_risk, schedule
from app.dealing_range import mark_dealing_range
from app.detect import DETECTORS
from app.ict import MEASURED_AGAINST, Rules, evaluate
from app.indicators import wilder_atr
from app.models import SupplyDemandParams
from app.plan import build
from app.poi import confluence, other_boxes
from app.profit_zone import profit_zone_at
from app.providers.base import INTERVALS
from app.resample import STEP_UP, resample
from app.ssmt import divergences_for as ssmt_divergences_for
from app.ssmt import ssmt as ssmt_read
from app.ssmt import two_stage
from tools.calibrate import POPULATION
from tools.conditioned import ALPHA, MIN_GROUP, _critical_t
from tools.execute import POI_SLACK_BARS, STAGE_PAIRS
from tools import history
from tools.intrabar import FINER, resolved

#: Malam yang MUNGKIN dilewati, dipakai untuk membebani swap ke
#: `cost_to_risk`. Angka dan rumusnya disalin dari `tools/execute.py:240`
#: supaya cost_r di sini adalah angka gerbang biaya jalur order, bukan
#: definisi kedua yang kebetulan mirip.
COST_HORIZON = 96
from tools.quant import BROKER, TCISD_PARTNER, clean

#: Daftar tertutup, bagian 2. Delapan karena tiap instrumen di sini punya
#: partner SSMT di `TCISD_PARTNER` dan riwayat 5 menit di terminal ini. Bukan
#: hasil pencarian: ini `tools/broker_costs.py:SYMBOLS` dikurangi XPTUSD
#: (riwayat 1 jam cuma 15k bar), BTCUSD (riwayat 5 menit mulai September 2025),
#: dan GBPJPY (partnernya EURUSD, pasangan silang yang bukan pasangan SSMT).
SYMBOLS = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
           "US30", "USOIL")

#: Ketujuh belas klausa `app/ict.py:evaluate`, dalam urutan tetapnya.
CLAUSES = (
    "killzone", "day_of_week", "discount_or_premium", "ote",
    "manipulation_quarter", "manipulation_seen",
    "manipulation_after_accumulation", "poi_families", "poi_clean",
    "cisd_in_band", "dfr_side", "htf_nested", "bias_agrees", "ssmt",
    "two_stage_confirmed", "min_rr", "draw_agrees", "adverse_excursion",
)

#: Sudah diukur sebelum studi ini, jadi verdict-nya mengutip dan bukan mengklaim.
ALREADY = tuple(MEASURED_AGAINST)

#: Jendela SSMT, dalam bar, berakhir di bar sentuhan. 3000 karena itu default
#: `--bars` di `tools/execute.py`, jadi angka ini adalah angka jalur order.
LIVE_BARS = 3000

#: Nama derajat di `STAGE_PAIRS` yang tidak ada di `app/quarters.py:ALL_DEGREES`,
#: diterjemahkan ke derajat yang repo ini benar-benar punya. Lihat catatan di
#: bagian 6 docstring: tanpa ini `two_stage_confirmed` konstan False.
STAGE_FALLBACK = {"90m": "session"}

FOLDS = 8


#: SATU EVENT LOOP UNTUK SELURUH RUN. `asyncio.run` membuat loop baru tiap
#: panggilan, dan lock modul di dalam provider MT5 terikat ke loop pertama:
#: simbol kedua gagal dengan "is bound to a different event loop" dan
#: `load_aligned` melaporkannya sebagai partner yang tidak tersedia, yang
#: terbaca sebagai fakta provider padahal fakta harness. `tools/conditioned.py`
#: tidak kena karena ia memanggilnya sekali per proses.
_LOOP: asyncio.AbstractEventLoop | None = None


def _aligned(symbols: list[str], interval: str, bars: int):
    global _LOOP
    if _LOOP is None:
        _LOOP = asyncio.new_event_loop()
    series, stats = _LOOP.run_until_complete(
        load_aligned(symbols, interval, bars))
    # JALUR MUAT KEDUA, dan ia tidak lewat `tools.history`. `load_aligned`
    # memanggil `app.providers.get_candles` langsung, jadi patokan di
    # `history.load` tidak menyentuhnya sama sekali dan grid SSMT tetap
    # bergerak sementara sisanya beku. Dua sisi yang dipatok setengah lebih
    # buruk daripada dua sisi yang sama-sama hidup, karena yang pertama
    # TERLIHAT reproducible.
    return {s: history.cut(rows) for s, rows in series.items()}, stats


def _welch(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Selisih rata-rata dan t Welch. Dua lengan tak punya alasan berbagi varians."""
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    se = sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    delta = float(a.mean() - b.mean())
    return delta, (delta / se if se > 0 else float("nan"))


def _spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Rho Spearman dan t-nya. Rank rata-rata untuk kembar, karena `met` integer."""
    n = len(x)
    if n < 4:
        return float("nan"), float("nan")
    rx, ry = _ranks(x), _ranks(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = sqrt(float((rx * rx).sum()) * float((ry * ry).sum()))
    if denom <= 0:
        return float("nan"), float("nan")
    rho = float((rx * ry).sum() / denom)
    if abs(rho) >= 1.0:
        return rho, float("inf")
    return rho, rho * sqrt((n - 2) / (1 - rho * rho))


def _ranks(v: np.ndarray) -> np.ndarray:
    """Rank rata-rata. `met` punya banyak kembar, jadi rank kompetisi akan bias."""
    order = np.argsort(v, kind="mergesort")
    out = np.empty(len(v), dtype=np.float64)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        out[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return out


def rows_for(symbol: str, interval: str, fine: str) -> list[dict]:
    """Tiap trade yang lolos gerbang, diselesaikan di bar halus, plus checklist.

    Outcome-nya datang dari `tools/intrabar.py:resolved`; checklist-nya
    dievaluasi di BAR SENTUHAN dengan empat argumen yang `tools/execute.py`
    isi dan `tools/conditioned.py` tidak. Join-nya lewat `zone_id`, dan zona
    dideteksi ulang dengan `POPULATION` yang sama supaya id-nya cocok.
    """
    fine_rows = [r for r in resolved(symbol, interval, fine) if r["cleared"]]
    if not fine_rows:
        return []

    candles, _, _ = clean(symbol, interval)
    params = SupplyDemandParams(**{**POPULATION, "show_broken": True})
    zones, _ = DETECTORS["supply_demand"](candles, params)
    by_id = {z.id: z for z in zones}

    # NESTING DAN DEALING RANGE, distempel seperti jalur order menstempelnya.
    # Praregistrasi kedua kena dua kali: kolom yang seragam False karena
    # harness-nya melewatkan langkah, bukan karena pasarnya begitu.
    higher_name = STEP_UP.get(interval)
    if higher_name:
        higher_bars = resample(candles, higher_name, interval)
        higher_zones, _ = DETECTORS["supply_demand"](higher_bars, params)
        for hz in higher_zones:
            hz.timeframe = higher_name
        mark_nesting(zones, higher_zones)
    mark_dealing_range(zones, candles)

    others = other_boxes(candles)
    times = [c.time for c in candles]
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    atr = wilder_atr(high, low, close, params.atr_period)
    step = INTERVALS[interval]
    fees = schedule(symbol, False, BROKER)
    always_open = trades_when_shut(times)
    rules = Rules()

    events, _ = cisds(candles)
    cisd_by_time = sorted((int(e.time), float(e.level)) for e in events)
    cisd_times = [t for t, _ in cisd_by_time]

    # SSMT DARI PARTNER BAWAAN SIMBOL, peta yang sudah ada di repo ini. Memilih
    # partner per run adalah pencarian yang menyamar jadi replikasi, dan
    # `docs/PRAREGISTRASI-KORELASI.md` sudah melarangnya.
    partner = TCISD_PARTNER[symbol]
    grid, _ = _aligned([f"mt5:{symbol}", f"mt5:{partner}"], interval, 99_999)
    grid = {s.split(":")[-1]: rows for s, rows in grid.items() if rows}
    shipped = STAGE_PAIRS[interval]
    hi_deg, lo_deg = (STAGE_FALLBACK.get(d, d) for d in shipped)
    stage_pair_valid = shipped == (hi_deg, lo_deg)
    by_degree: dict[str, list] = {}
    if len(grid) > 1:
        for degree in {"day", hi_deg, lo_deg}:
            found, _ = ssmt_read(grid, degree)
            by_degree[degree] = sorted(found, key=lambda e: e.knowable_at)
    knowable = {d: [e.knowable_at for e in evs] for d, evs in by_degree.items()}

    def window(degree: str, now: int) -> list:
        """Event derajat `degree` yang knowable di `now`, jendela `LIVE_BARS` bar.

        Potongan kanannya anti-lookahead; potongan kirinya menyamai jendela yang
        `tools/execute.py` muat, supaya `two_stage_confirmed` di sini adalah
        angka jalur order dan bukan definisi baru.
        """
        evs = by_degree.get(degree)
        if not evs:
            return []
        keys = knowable[degree]
        lo = bisect.bisect_left(keys, now - LIVE_BARS * step)
        hi = bisect.bisect_right(keys, now)
        return evs[lo:hi]

    out: list[dict] = []
    for row in fine_rows:
        touch = int(row["at"])
        zone = by_id.get(row["zone_id"])
        if zone is None or touch < 1:
            continue
        now = times[touch]
        scale = float(atr[touch - 1])
        if scale <= 0:
            continue

        # REWARD, dari geometri plan yang sama dengan yang `resolved` pakai.
        at_touch = zone.model_copy(update={
            "profit_zone_rr": profit_zone_at(zone, zones, now)})
        spread = candles[touch].spread
        if spread is None and fees.get("spread_bp") is not None:
            spread = float(close[touch]) * fees["spread_bp"] / 10_000
        plan = build(at_touch, scale, now, step, spread=spread)
        if plan is None:
            continue

        state = at_bar(candles, touch, interval)
        anatomy = zone.anatomy
        born_from = times[max(0, anatomy.leg_in_from - POI_SLACK_BARS)]
        born_to = times[min(len(times) - 1, anatomy.leg_out_to + POI_SLACK_BARS)]
        levels = [lv for t, lv in cisd_by_time[:bisect.bisect_right(cisd_times, now)]]
        stack = confluence(zone, others, now, born_from, born_to,
                           cisd_levels=levels)

        # SISI SSMT, dibaca dari bagian simbol INI dalam divergensinya, sama
        # persis dengan `tools/execute.py`: mengambil low adalah bentuk bullish,
        # gagal mengambil high adalah bacaan yang sama dari ujung lain.
        ssmt_side = None
        mine = [e for e in window("day", now) if symbol in (e.took, e.failed)]
        if mine:
            newest = mine[-1]
            ssmt_side = newest.side if newest.took == symbol else (
                "low" if newest.side == "high" else "high")

        confirmed = False
        if by_degree:
            hi_div = ssmt_divergences_for(window(hi_deg, now), symbol)
            lo_div = ssmt_divergences_for(window(lo_deg, now), symbol)
            confirmed = len(two_stage(hi_div, lo_div, symbol)) > 0

        checklist = evaluate(zone, state, stack, rules, at=now,
                             ssmt_side=ssmt_side, two_stage_confirmed=confirmed,
                             reward_r=plan.reward_r, always_open=always_open)
        # KUNCI URUT KANDIDAT, semuanya terbaca di bar keputusan.
        #
        # Ditulis di sini dan bukan di harness kedua karena definisi populasi
        # ada di fungsi INI. Sebuah rig yang membangun ulang populasinya sendiri
        # untuk menguji kunci urut sedang menguji kunci urut DAN populasi
        # sekaligus, dan kalau hasilnya berbeda tidak ada yang tahu yang mana
        # penyebabnya. Prefix `k_` supaya tidak pernah bentrok dengan nama
        # klausa checklist, yang ditulis ke dict yang sama di bawah.
        cost_r, _ = cost_to_risk(
            float(close[touch]), plan.risk_per_unit, spread or 0.0, fees,
            (COST_HORIZON * step) / 86_400,
        )
        record = {
            "symbol": symbol, "zone_id": row["zone_id"], "time": now,
            "r": float(row["r"]),
            "met": sum(1 for c in checklist if c.met is True),
            "unknown": sum(1 for c in checklist if c.met is None),
            "shipped_stage_pair_valid": stage_pair_valid,
            "k_met": sum(1 for c in checklist if c.met is True),
            "k_near_close": -abs(plan.entry - float(close[touch])),
            "k_near_target": -abs(plan.entry - plan.target)
            if plan.target is not None else None,
            "k_reward_r": plan.reward_r,
            "k_cheap": -cost_r,
            "k_departure": zone.departure_atr,
        }
        for c in checklist:
            record[c.name] = c.met
        out.append(record)
    return out


def _judged_groups(rows: list[dict]) -> int:
    """K, dihitung SEBELUM satu hasil pun dilaporkan.

    Urutannya yang penting: kalau K dihitung setelah tabelnya terbaca, ambangnya
    jadi fungsi dari apa yang sudah dilihat pembaca.
    """
    k = 1  # kontras split median pada `met`
    for column in ("met",) + CLAUSES:
        seen: dict[object, int] = {}
        for row in rows:
            key = row.get(column)
            seen[key] = seen.get(key, 0) + 1
        k += sum(1 for n in seen.values() if n >= MIN_GROUP)
    return k


def _halves_agree(rows: list[dict], pick, key: str = "r") -> tuple[list[float], bool]:
    """Delta grup lawan sisanya di tiap paruh waktu, dan apakah tandanya sama."""
    ordered = sorted(rows, key=lambda r: r["time"])
    cut = len(ordered) // 2
    deltas = []
    for part in (ordered[:cut], ordered[cut:]):
        a = np.array([r[key] for r in part if pick(r)])
        b = np.array([r[key] for r in part if not pick(r)])
        deltas.append(float(a.mean() - b.mean()) if len(a) and len(b)
                      else float("nan"))
    ok = not any(np.isnan(deltas)) and (deltas[0] > 0) == (deltas[1] > 0)
    return deltas, ok


def _trend(rows: list[dict], key: str) -> dict:
    """H-A2 dan H-A3 pada satu kolom outcome, mentah atau di-demean."""
    met = np.array([r["met"] for r in rows], dtype=np.float64)
    val = np.array([r[key] for r in rows], dtype=np.float64)
    rho, t = _spearman(met, val)
    median = float(np.median(met))
    top = val[met > median]
    bottom = val[met <= median]
    delta, welch = _welch(top, bottom)
    halves, same = _halves_agree(rows, lambda r: r["met"] > median, key)
    return {
        "spearman_rho": rho, "spearman_t": t,
        "median_met": median,
        "n_above": int(len(top)), "n_at_or_below": int(len(bottom)),
        "exp_r_above": float(top.mean()) if len(top) else None,
        "exp_r_at_or_below": float(bottom.mean()) if len(bottom) else None,
        "median_split_delta": delta, "median_split_t": welch,
        "halves_delta": halves, "halves_same_sign": same,
    }


def _levels(rows: list[dict]) -> list[dict]:
    """Tabel ekspektansi per level `met`, dengan CI 95 persen."""
    buckets: dict[int, list[float]] = {}
    for row in rows:
        buckets.setdefault(int(row["met"]), []).append(row["r"])
    out = []
    for met in sorted(buckets):
        v = np.array(buckets[met])
        se = float(v.std(ddof=1) / sqrt(len(v))) if len(v) > 1 else 0.0
        out.append({
            "met": met, "n": len(v), "exp_r": float(v.mean()), "se": se,
            "ci_lo": float(v.mean() - 1.96 * se),
            "ci_hi": float(v.mean() + 1.96 * se),
            "judged": len(v) >= MIN_GROUP,
        })
    return out


def _monotone(levels: list[dict]) -> dict:
    """H-A1. Hanya level yang layak dinilai yang ikut, dan itu ditetapkan di muka."""
    judged = [lv for lv in levels if lv["judged"]]
    pairs = [(judged[i]["met"], judged[i + 1]["met"],
              judged[i + 1]["exp_r"] - judged[i]["exp_r"])
             for i in range(len(judged) - 1)]
    rising = sum(1 for *_, d in pairs if d >= 0)
    return {
        "levels_judged": [lv["met"] for lv in judged],
        "adjacent_pairs": len(pairs),
        "non_decreasing": rising,
        "steps": [{"from": a, "to": b, "delta_exp_r": d} for a, b, d in pairs],
        "monotone": bool(pairs) and rising == len(pairs),
    }


def _clause(rows: list[dict], name: str, critical: float) -> dict:
    """H-B untuk satu klausa: tiap nilai lawan sisa populasi."""
    buckets: dict[object, list[dict]] = {}
    for row in rows:
        buckets.setdefault(row.get(name), []).append(row)
    if len(buckets) == 1:
        only = next(iter(buckets))
        return {"clause": name, "constant": True, "value": only,
                "n": len(rows),
                "verdict": f"konstan {only} di seluruh populasi, tidak bisa "
                           f"memisahkan apa pun"}
    groups = []
    separates = []
    for key in sorted(buckets, key=lambda k: (k is None, str(k))):
        group = buckets[key]
        inside = np.array([r["r"] for r in group])
        rest = np.array([r["r"] for r in rows if r.get(name) != key])
        entry: dict = {"value": key, "n": len(group),
                       "exp_r": float(inside.mean())}
        if len(group) < MIN_GROUP or len(rest) < MIN_GROUP:
            entry["judged"] = False
            groups.append(entry)
            continue
        delta, t = _welch(inside, rest)
        halves, same = _halves_agree(rows, lambda r, k=key: r.get(name) == k)
        passed = abs(t) >= critical and same
        # POST-HOC, bagian 5. Tiga angka yang hanya boleh melemahkan bacaan.
        delta_dm, t_dm = _welch(
            np.array([r["r_dm"] for r in group]),
            np.array([r["r_dm"] for r in rows if r.get(name) != key]))
        agree = 0
        per_symbol = 0
        for sym in {r["symbol"] for r in rows}:
            mine = [r for r in rows if r["symbol"] == sym]
            a = np.array([r["r"] for r in mine if r.get(name) == key])
            b = np.array([r["r"] for r in mine if r.get(name) != key])
            if not len(a) or not len(b):
                continue
            per_symbol += 1
            agree += (a.mean() - b.mean() > 0) == (delta > 0)
        entry.update({"judged": True, "delta": delta, "t": t,
                      "halves_delta": halves, "halves_same_sign": same,
                      "separates": passed,
                      "delta_dm": delta_dm, "t_dm": t_dm,
                      "symbols_same_sign": f"{agree}/{per_symbol}"})
        if passed:
            separates.append(key)
        groups.append(entry)
    judged = [g for g in groups if g.get("judged")]
    out = {"clause": name, "constant": False, "groups": groups,
           "separates": separates,
           "strongest_t": max((abs(g["t"]) for g in judged), default=None)}
    if name in ALREADY:
        out["prior_measurement"] = MEASURED_AGAINST[name]
    return out


def study(symbols: list[str], interval: str, fine: str) -> dict:
    """Satu run penuh. Semua ambang dihitung sebelum satu hasil dilaporkan."""
    per_symbol: dict[str, list[dict]] = {}
    for symbol in symbols:
        rows = rows_for(symbol, interval, fine)
        print(f"  {symbol}: {len(rows)} trade", file=sys.stderr)
        if rows:
            per_symbol[symbol] = rows
    pooled = [r for rows in per_symbol.values() for r in rows]
    if not pooled:
        return {"error": "tidak ada trade yang bisa diselesaikan di bar halus"}

    # KONTROL INSTRUMEN, bagian 4. Dihitung sebelum tesnya, bukan sesudah.
    means = {s: float(np.mean([r["r"] for r in rows]))
             for s, rows in per_symbol.items()}
    for row in pooled:
        row["r_dm"] = row["r"] - means[row["symbol"]]

    k = _judged_groups(pooled)
    critical = _critical_t(k)

    levels = _levels(pooled)
    ordered = sorted(pooled, key=lambda r: r["time"])
    size = len(ordered) // FOLDS
    folds = []
    for i in range(FOLDS):
        part = ordered[i * size:(i + 1) * size if i < FOLDS - 1 else len(ordered)]
        met = np.array([r["met"] for r in part], dtype=np.float64)
        val = np.array([r["r"] for r in part], dtype=np.float64)
        rho, t = _spearman(met, val)
        median = float(np.median(met))
        delta, welch = _welch(val[met > median], val[met <= median])
        folds.append({
            "fold": i + 1, "n": len(part),
            "from": part[0]["time"], "to": part[-1]["time"],
            "exp_r": float(val.mean()),
            "spearman_rho": rho, "spearman_t": t,
            "median_split_delta": delta, "median_split_t": welch,
            "positive": bool(delta > 0) if not np.isnan(delta) else None,
        })

    raw = _trend(pooled, "r")
    demeaned = _trend(pooled, "r_dm")
    mono = _monotone(levels)
    verdict_a = {
        "A1_monotone": mono["monotone"],
        "A2_trend_raw": bool(abs(raw["spearman_t"]) >= critical
                             and raw["spearman_rho"] > 0),
        "A2_trend_demeaned": bool(abs(demeaned["spearman_t"]) >= critical
                                  and demeaned["spearman_rho"] > 0),
        "A3_median_split_raw": bool(raw["median_split_t"] >= critical
                                    and raw["halves_same_sign"]),
        "A3_median_split_demeaned": bool(demeaned["median_split_t"] >= critical
                                         and demeaned["halves_same_sign"]),
    }
    return {
        "preregistered": "docstring tools/checklist_outcomes.py, 2026-08-30",
        "run": {"interval": interval, "fine": fine,
                "symbols": list(per_symbol), "folds": FOLDS,
                "ssmt_window_bars": LIVE_BARS, "broker": BROKER},
        "population": {
            "n": len(pooled),
            "exp_r": float(np.mean([r["r"] for r in pooled])),
            "per_symbol": {s: {"n": len(rows), "exp_r": means[s]}
                           for s, rows in per_symbol.items()},
            "met_min": min(r["met"] for r in pooled),
            "met_max": max(r["met"] for r in pooled),
            "shipped_stage_pair_valid": all(
                r["shipped_stage_pair_valid"] for r in pooled),
            "unknown_mean": float(np.mean([r["unknown"] for r in pooled])),
        },
        "threshold": {"alpha": ALPHA, "groups_judged": k,
                      "alpha_corrected": ALPHA / k, "critical_t": critical,
                      "min_group": MIN_GROUP},
        "H_A_met_score": {
            "levels": levels, "monotone": mono,
            "raw": raw, "instrument_demeaned": demeaned,
            "walk_forward": folds,
            "folds_positive": sum(1 for f in folds if f["positive"]),
            "verdict": verdict_a,
            "separates": any(verdict_a.values()),
        },
        "H_B_clauses": [_clause(pooled, name, critical) for name in CLAUSES],
        # BARIS MENTAHNYA, ringkas. Studi ini membayar sekitar 80 menit terminal
        # MT5 untuk 1855 baris, dan tanpa ini setiap pemeriksaan ulang membayar
        # lagi. Kolom di depan, baris sebagai array, karena satu objek per baris
        # membuat file ini lima kali lebih besar tanpa menambah satu fakta pun.
        "rows": {
            "columns": ["symbol", "time", "r", "met", "unknown"] + list(CLAUSES),
            "data": [[r["symbol"], r["time"], round(r["r"], 6), r["met"],
                      r["unknown"]] + [r[c] for c in CLAUSES] for r in ordered],
        },
    }


def _selftest() -> None:
    """Cacat yang tool ini ditulis untuk menangkap, disuntikkan lalu diperiksa."""
    rise = [{"met": m, "r": m * 1.0, "time": i, "symbol": "X"}
            for i, m in enumerate([0] * 40 + [1] * 40 + [2] * 40)]
    fall = [{**r, "r": -r["r"]} for r in rise]
    assert _monotone(_levels(rise))["monotone"] is True
    assert _monotone(_levels(fall))["monotone"] is False
    assert _trend(rise, "r")["spearman_rho"] > 0.9
    assert _trend(fall, "r")["spearman_rho"] < -0.9
    # Rank rata-rata, bukan rank kompetisi: `met` penuh kembar.
    assert list(_ranks(np.array([1.0, 1.0, 2.0]))) == [1.5, 1.5, 3.0]
    # Welch memisahkan dua rata-rata yang jelas berbeda dan tidak memisahkan
    # dua yang sama.
    a, b = np.arange(100.0), np.arange(100.0) + 30
    assert _welch(b, a)[1] > 5 and abs(_welch(a, a.copy())[1]) < 1e-9
    # Ambang mengetat saat grup bertambah, yang adalah seluruh gunanya.
    assert _critical_t(200) > _critical_t(20)
    print("selftest ok", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--fine", default="")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    fine = args.fine or FINER.get(args.interval, "5m")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    # `resolved` mencetak zona yang entry-nya tidak terisi ke stdout, dan stdout
    # di sini adalah file JSON-nya. Dialihkan ke stderr, tidak dibuang.
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, args.interval, fine)
    json.dump(out, sys.stdout, indent=2, default=str)
    print()
    return 0 if "error" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
