"""The ICT checklist, applied to one candidate, as a gate and as a ranking.

WHAT THIS IS FOR. The owner of this project trades ICT and Quarterly Theory, and
asked for the entry decision to read the whole toolkit rather than one detector.
This is that decision layer: kill zone, premium and discount, the manipulation
quarter, the POI stack, CISD, the defining range, and optionally SSMT and the
higher-timeframe bias. Each condition is switchable, each carries WHERE it came
from, and `Rules` is the whole tuning surface.

THREE SOURCES, LABELLED ON EVERY CONDITION, because a checklist whose premises
came from different places and did not say so reads as nine measurements when it
is one measurement and eight quotations:

  `measured`   the project has a number for it, in docs/CALIBRATION.md or
               docs/WALKFORWARD-MT5.md.
  `doctrine`   the sources state it and nothing here has measured it. It is
               applied because the reader follows the method, and that is a
               legitimate reason to apply a rule - it is not a legitimate reason
               to call it evidence.
  `nominated`  the caller supplied it. `deduce.py` set this precedent for the
               draw on liquidity: Zonelab refuses to infer a draw, so a human
               names it and the record says who did.

WHAT IT DOES NOT DO. It does not sum the conditions into a score. `Rules.required`
names which must be met and the rest are counted and reported, so two setups can
be ordered without anyone claiming a weight. The one time this project shipped a
weighted composite - `formation_score` - it ranked BACKWARDS, AUC 0.464 and 0.477,
and the weights were equal thirds precisely because fitting them would have been
fitting noise.

IO FREE. Every input is passed in. The kill zone comes from a clock, the quarterly
state from `conditions.at_bar`, the stack from `poi.confluence`, and SSMT from
whoever fetched the second instrument. That is what lets the measurement harness
run this 953 times without 953 provider calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from .clock import NY
from .models import Zone, ZoneSide
from .poi import Confluence
from .bias import DEGREES as _BIAS_DEGREES
from .pools import killzones_at

Source = Literal["measured", "doctrine", "nominated"]


@dataclass(frozen=True)
class Condition:
    """One clause, its verdict, where the verdict came from, and its number."""

    name: str
    met: bool | None  # None means NOT KNOWABLE here, never "no"
    source: Source
    detail: str


@dataclass
class Rules:
    """The tuning surface. Everything adjustable about the checklist is here.

    `required` is the gate. A condition named here and not met stops the trade;
    a condition NOT named here is still evaluated and still counted, so it can
    be measured before it is ever allowed to block anything. That ordering is
    the point: nothing gets promoted from reported to required without a number.

    The default `required` is EMPTY on purpose. Shipping with a full gate would
    switch on nine unmeasured filters at once and change the population every
    number in this project belongs to. The operator opts in per condition.
    """

    required: tuple[str, ...] = ()
    #: Which kill zones count as "in a kill zone". All of them by default; a
    #: reader who only trades the New York morning passes `("ny_am",)`.
    killzones: tuple[str, ...] = (
        "asia", "london", "london_sb", "ny_am", "london_close", "ny_pm", "silver_bullet",
    )
    #: Distinct PD array families that must stack for `poi_families` to pass.
    #: Two, because the doctrine's own example names an FVG and an order block.
    min_families: int = 2
    #: Opposite-side boxes tolerated in the same band before `poi_clean` fails.
    max_conflicts: int = 0
    #: Whether the higher-timeframe bias must agree with the zone's side.
    #: Derajat bias yang dibaca klausa `bias_agrees`.
    #:
    #: DEFAULTNYA 4 JAM UNTUK SETIAP TIMEFRAME, dan sampai 30 Agustus 2026 tidak
    #: ada flag untuk mengubahnya di `tools/execute.py` maupun
    #: `tools/autotrade.py`. Akibatnya terukur pada 30 Agustus 2026 pukul 19:00:
    #: BTCUSD naik 1,36% dalam 24 jam, `bias_1h` +1 dan `bias_1d` +1, sementara
    #: `bias_4h` -1, dan gerbang membaca yang terakhir. Sembilan belas kandidat
    #: demand di 15m dan 30m ditolak oleh satu bacaan 4 jam.
    #:
    #: Nilai yang sah adalah `bias_` plus salah satu dari `app.bias.DEGREES`.
    #: Salah ketik akan membuat `state.get()` menjawab None dan klausanya jadi
    #: `unknown` selamanya, yang di repo ini dihitung GAGAL kalau ia diwajibkan.
    #: Diam adalah cara terburuk untuk salah, jadi ia divalidasi.
    bias_degree: str = "bias_4h"


#: Klausa yang sumbernya `doctrine` -- belum diukur oleh proyek ini. Daftar ini
#: sengaja eksplisit; kalau sebuah klausa pindah label, daftar ini harus ikut
#: berubah dan diff-nya terbaca.
DOCTRINE_CLAUSES: frozenset[str] = frozenset([
    "killzone", "day_of_week", "discount_or_premium", "manipulation_quarter",
    "manipulation_seen", "manipulation_after_accumulation",
    "poi_families", "poi_clean", "cisd_in_band", "dfr_side",
    "two_stage_confirmed", "min_rr", "ote",
])


#: Klausa yang SUDAH diukur dan hasilnya BURUK, dengan angkanya. Ini daftar
#: yang berbeda dari `DOCTRINE_CLAUSES`, dan bedanya penting: doctrine berarti
#: "belum ada angkanya", sementara ini berarti "ada angkanya, dan ia menunjuk ke
#: arah lain". Menyamakan keduanya di sebuah peringatan membuat operator
#: menyalakan gerbang yang sudah dibuktikan merugikan, dengan mengira ia sekadar
#: belum terbukti.
#:
#: Sumbernya `docs/PRAREGISTRASI-YATIM.md` Bagian 7 dan
#: `docs/checklist_outcomes.json`, keduanya ditulis sebelum angkanya dihitung.
#: Sebuah klausa masuk daftar ini hanya lewat praregistrasi.
#:
#: DAFTARNYA JADI TUJUH BELAS PADA 2 SEPTEMBER 2026, dari dua. Sampai hari itu
#: lima belas klausa yang SUDAH diukur di `checklist_outcomes.json` masih
#: diperingatkan sebagai "belum diukur" oleh `tools/execute.py:warn_required`,
#: dan docstring fungsi itu sendiri sudah menjelaskan kenapa itu kalimat yang
#: salah: "Operator yang membaca 'belum diukur' akan menyalakannya sebagai
#: taruhan; yang membaca angkanya tidak akan."
#:
#: Ambangnya kritis Bonferroni 3,267 atas 46 grup. SATU dari tujuh belas
#: melewatinya, `dfr_side`, dan ia melewatinya ke arah SEBALIKNYA. Dua klausa
#: KONSTAN di 1855 trade, jadi keduanya tidak bisa jadi kriteria apa pun: kolom
#: yang tidak pernah berubah tidak membawa satu bit informasi.
MEASURED_AGAINST: dict[str, str] = {
    "ote": ("direplikasi di 12 instrumen 1h: NOL sel lolos, |t| tertinggi 2,04 "
            "lawan kritis 3,20. Negatif di 10 dari 12 sel tapi tidak signifikan "
            "di satu pun, jadi ia tidak punya edge DAN tidak terbukti merugikan"),
    "dfr_side": (
        "MEMISAHKAN, DAN KE ARAH SEBALIKNYA. Diukur 30 Agustus 2026 di 8 "
        "instrumen, zona 1h diselesaikan di bar 5 menit, n=1855, biaya "
        "exness_raw: klausa TERPENUHI exp R -0,0660 pada n=1141 (delta -0,1676, "
        "t=-3,54), klausa GAGAL exp R +0,1481 pada n=341 (delta +0,1832, "
        "t=+3,41), lawan kritis Bonferroni 3,267 untuk 46 grup. Kedua paruh "
        "setanda, 8 dari 8 instrumen setanda pada sisi True, dan t tetap -3,32 "
        "setelah di-demean per instrumen. Urutannya monoton ke arah salah: "
        "False +0,148 > None +0,059 > True -0,066. Bukti di "
        "docs/checklist_outcomes.json"),
    # ---- Lima belas sisanya, diukur di docs/checklist_outcomes.json,
    # ---- n=1855 trade, 8 instrumen, zona 1h diselesaikan di bar 5 menit,
    # ---- biaya exness_raw, kritis Bonferroni 3,267 atas 46 grup.
    "min_rr": (
        "TIDAK MEMISAHKAN. Sel terkuatnya klausa GAGAL, n=1380, delta -0,2149 "
        "pada t=-2,988 lawan kritis 3,267, dan 8 dari 8 instrumen setanda. "
        "Magnitudonya yang terbesar di antara ketujuh belas dan ia tetap tidak "
        "melewati ambang, jadi yang dilaporkan besarnya DAN kegagalannya"),
    "manipulation_seen": (
        "TIDAK MEMISAHKAN. Klausa GAGAL, n=1032, delta -0,135 pada t=-2,890 "
        "lawan kritis 3,267, 8 dari 8 instrumen setanda"),
    "manipulation_after_accumulation": (
        "TIDAK MEMISAHKAN, dan angkanya IDENTIK dengan manipulation_seen: "
        "n=1032, delta -0,135, t=-2,890. Dua klausa yang selalu memberi angka "
        "yang sama adalah satu klausa yang dihitung dua kali, dan itu "
        "menggelembungkan denominator skor tanpa menambah informasi"),
    "discount_or_premium": (
        "TIDAK MEMISAHKAN. Klausa TERPENUHI, n=682, delta -0,0976 pada "
        "t=-2,044, 6 dari 8 instrumen setanda"),
    "poi_clean": (
        "TIDAK MEMISAHKAN. Klausa GAGAL, n=1098, delta -0,0818 pada t=-1,727, "
        "7 dari 8 instrumen setanda"),
    "cisd_in_band": (
        "TIDAK MEMISAHKAN di sini, n=58, delta +0,2205 pada t=1,291 dan hanya "
        "2 dari 4 instrumen setanda. Populasinya kecil, dan itu batas metode. "
        "Objek yang sama MEMISAHKAN kuat di pertanyaan yang berbeda: CISD di "
        "dalam order block memberi delta -0,136 R pada t=-7,07 dengan 8 dari 8 "
        "fold (docs/csid_ob_intrabar.json), jadi yang gagal di sini klausanya, "
        "bukan objeknya"),
    "manipulation_quarter": (
        "TIDAK MEMISAHKAN. Sel terkuatnya UNKNOWN, n=501, delta +0,0619 pada "
        "t=1,099, 4 dari 8 instrumen setanda"),
    "ssmt": (
        "TIDAK MEMISAHKAN sebagai klausa, n=921, delta +0,0447 pada t=0,982, "
        "5 dari 8 instrumen setanda. Layer-nya sendiri juga null: 0 dari 24 sel "
        "dengan tanda 12 lawan 12 (docs/ssmt_outcomes.json), dan menradingkannya "
        "dengan biaya memberi exp R -0,1318 lawan kontrol -0,1076 "
        "(docs/event_backtest.json)"),
    "bias_agrees": (
        "TIDAK MEMISAHKAN. Klausa GAGAL, n=921, delta -0,0427 pada t=-0,936, "
        "5 dari 8 instrumen setanda"),
    "day_of_week": (
        "TIDAK MEMISAHKAN. Klausa GAGAL, n=110, delta -0,0409 pada t=-0,329, "
        "6 dari 8 instrumen setanda"),
    "killzone": (
        "TIDAK MEMISAHKAN. Klausa GAGAL, n=611, delta -0,0075 pada t=-0,155, "
        "4 dari 8 instrumen setanda - praktis nol"),
    "htf_nested": (
        "TIDAK MEMISAHKAN. Klausa GAGAL, n=835, delta -0,0063 pada t=-0,138, "
        "4 dari 8 instrumen setanda - praktis nol"),
    "poi_families": (
        "TIDAK MEMISAHKAN, dan ia yang paling dekat ke nol dari ketujuh belas: "
        "n=292, delta +0,0016 pada t=0,025, 5 dari 8 instrumen setanda"),
    "two_stage_confirmed": (
        "KONSTAN di 1855 trade, jadi ia tidak bisa jadi kriteria apa pun. Kolom "
        "yang tidak pernah berubah tidak memisahkan apa pun secara definisi, dan "
        "ia tetap menambah satu ke denominator skor checklist"),
    "draw_agrees": (
        "KONSTAN di 1855 trade, dan ini BATAS METODE yang dinyatakan di depan: "
        "`app/ict.py` menolak menyimpulkan draw dan tidak ada manusia yang "
        "menominasikannya di dalam harness, jadi konstan None sudah bisa diduga "
        "sebelum diukur. Praregistrasinya menyebutnya supaya 'konstan' "
        "dilaporkan sebagai batas metode dan bukan sebagai nol yang mengesankan"),
}

#: KENAPA KLAUSANYA TIDAK DIBALIK SAJA. Karena pemisahan di atas BELUM
#: di-walk-forward per klausa: `docs/checklist_outcomes.json` membawa fold hanya
#: untuk skor agregat, bukan untuk `dfr_side`. Standar repo ini, tertulis di
#: docs/AUDIT-MENYELURUH.md, adalah gerbang menyala setelah lolos walk-forward,
#: bukan setelah lolos satu potong. Membalik doktrin di atas satu pengukuran
#: adalah overfit yang persis sama, cuma tandanya lain. Yang dilakukan di sini:
#: angkanya dicatat, dan `warn_required` di tools/execute.py memperingatkan
#: keras kalau operator mewajibkannya.


#: SENSUS PER KLAUSA: objek apa yang ia baca, layer mana yang MENGGAMBAR objek
#: itu, dan bagaimana ia diukur. Dijawab di satu tempat karena pertanyaannya
#: datang berulang dan jawabannya tidak ada di mana pun sampai 2 September 2026:
#: "apakah klausa ini punya drawing, deteksi, dan terwire".
#:
#: Ketujuh belasnya PUNYA DETEKSI - `evaluate` di bawah menghitung semuanya.
#: Tidak satu pun TERWIRE ke keputusan: `Rules.required` default kosong dan
#: `tests/test_failed_criteria_not_wired.py` menahannya. Yang berbeda-beda
#: DRAWING-nya, dan itu isi tabel ini.
#:
#: Nilainya `(layer_id, catatan)`. `layer_id` None berarti objeknya TIDAK
#: DIGAMBAR, dan catatannya menyebut kenapa - biasanya karena ia bacaan jam atau
#: aritmetika plan, bukan bentuk di harga. `tests/test_clause_census.py`
#: menuntut tabel ini menutup setiap klausa DAN setiap `layer_id` yang disebut
#: benar-benar ada di `app/layers.py`, jadi klausa baru atau layer yang berganti
#: nama membuatnya merah alih-alih membuatnya basi.
CLAUSE_OBJECT: dict[str, tuple[str | None, str]] = {
    "killzone": (
        None,
        "Bacaan jam dari `app/clock.py`, bukan bentuk di harga. TIDAK ADA "
        "gambar killzone di mana pun di frontend, dicari 2 September 2026: satu "
        "kemunculan kata itu di `src/lib/types.ts` dan itu sebuah komentar. "
        "Sesinya digambar oleh layer `session` sebagai grid kuarter, yang objek "
        "yang berbeda",
    ),
    "day_of_week": (
        None,
        "Bacaan jam. Hari dalam sepekan tidak punya bentuk di harga, dan "
        "menggambarnya berarti menggambar kalender",
    ),
    "discount_or_premium": (
        "liquidity",
        "Membaca `dealing_range.position_at`. Frame dealing range digambar "
        "layer `liquidity`, dan `levels-primitive.ts` memberinya prioritas "
        "klaim label lebih dulu daripada period extreme justru karena "
        "equilibrium-nya yang dibaca pembaca untuk premium lawan discount",
    ),
    "ote": (
        "structure",
        "Grid Fibonacci/OTE MENUMPANG layer `structure` dan bukan layer "
        "sendiri: `app/drawing.py:138` mengisi `FibonacciAnchor` dari swing "
        "confirmed terakhir di skala `swing`, jadi ia hanya muncul kalau "
        "structure menyala DAN kedua sisi sudah confirmed. Tidak ada `ote` "
        "maupun `fibonacci` di registry layer",
    ),
    "manipulation_quarter": (
        "session",
        "Membaca `quarterly.profile` plus grid `quarters`. Layer `session` "
        "(Cycle grid) yang menggambar kuarternya. Family Quarterly Theory, "
        "jadi ia DI LUAR sensus port MQL5 di `tools/mqh_parity.py`, yang cuma "
        "menutup family ICT",
    ),
    "manipulation_seen": (
        "dfr",
        "Membaca `quarterly.manipulation_done`, yang butuh DFR-nya. Layer "
        "`dfr` yang menggambar range-nya. Family Quarterly Theory, di luar "
        "sensus port MQL5",
    ),
    "manipulation_after_accumulation": (
        "dfr",
        "Sumber yang sama dengan `manipulation_seen`, dan angkanya IDENTIK di "
        "pengukurannya: n=1032, delta -0,135, t=-2,890. Dua klausa satu objek",
    ),
    "poi_families": (
        "order_block",
        "Membaca `poi.confluence` atas box dari SETIAP detektor zona, jadi "
        "layer yang disebut di sini wakil dan bukan satu-satunya: keluarga "
        "yang dihitung datang dari supply_demand, fvg, order_block, ifvg dan "
        "breaker bersama-sama. Kelimanya PORTED dan 0 mismatch",
    ),
    "poi_clean": (
        "order_block",
        "Sumber yang sama dengan `poi_families`, sisi yang berlawanan: box "
        "lawan-sisi di pita yang sama. Kelima detektor zona PORTED",
    ),
    "cisd_in_band": (
        "cisd",
        "Membaca `cisd.cisds`. Layer `cisd` menggambarnya dan ia PORTED ke "
        "MQL5 dengan 0 mismatch di 349 event",
    ),
    "dfr_side": (
        "dfr",
        "Membaca `quarterly.defining_range`. Layer `dfr` menggambarnya. SATU-"
        "SATUNYA klausa yang melewati ambang, dan ke arah SEBALIKNYA. Family "
        "Quarterly Theory, di luar sensus port MQL5",
    ),
    "htf_nested": (
        "supply_demand",
        "Membaca `confluence.mark_nesting`, yang membandingkan zona timeframe "
        "ini dengan zona timeframe di atasnya. Objeknya box HTF, digambar oleh "
        "detektor zona yang sama dengan tanda proyeksi. PORTED",
    ),
    "bias_agrees": (
        None,
        "Membaca `bias.alignment`, sebuah arah yang diturunkan dari deret di "
        "derajat `Rules.bias_degree`. Ia ANGKA dan bukan bentuk: tidak ada "
        "layer `bias` di registry, dan panel yang menampilkannya menampilkan "
        "kata",
    ),
    "ssmt": (
        "ssmt",
        "Membaca `ssmt.ssmt`. Layer `ssmt` menggambarnya, dan ia UNPORTED "
        "dengan alasan terukur di `tools/mqh_parity.py:UNPORTED`. Ditradingkan "
        "dengan biaya di `docs/event_backtest.json`: exp R -0,1318 lawan "
        "kontrol -0,1076",
    ),
    "two_stage_confirmed": (
        "ssmt",
        "Membaca `ssmt.two_stage`, dua derajat SSMT berurutan. Objek dan layer "
        "yang sama dengan `ssmt`. KONSTAN di 1855 trade, jadi ia tidak bisa "
        "jadi kriteria apa pun",
    ),
    "min_rr": (
        None,
        "Membaca `plan.reward_r`, aritmetika plan atas entry, stop dan target. "
        "Ketiga harga itu digambar sebagai garis plan, tapi RASIONYA angka dan "
        "bukan bentuk. EA MQL5 punya perhitungan RR-nya sendiri, dan itu "
        "divergensi yang `docs/QA-DETEKTOR.md` bagian 4 catat",
    ),
    "draw_agrees": (
        "liquidity",
        "Membaca `liquidity.dol_candidates`. Layer `liquidity` menggambar "
        "level-levelnya dan ia PORTED dengan 0 mismatch di 416 level. Tapi "
        "klausanya KONSTAN None: `app/ict.py` menolak menyimpulkan draw dan "
        "tidak ada manusia yang menominasikannya di dalam harness, jadi yang "
        "hilang bukan gambarnya melainkan penominasinya",
    ),
}


#: Nilai `Rules.bias_degree` yang sah, diturunkan dari `app.bias.DEGREES`
#: supaya menambah derajat di sana cukup sekali.
BIAS_DEGREES: tuple[str, ...] = tuple(f"bias_{d}" for d in _BIAS_DEGREES)


def evaluate(
    zone: Zone,
    state: dict[str, Any],
    stack: Confluence,
    rules: Rules | None = None,
    at: int | None = None,
    ssmt_side: str | None = None,
    draw: Literal["higher", "lower", "unnominated"] = "unnominated",
    two_stage_confirmed: bool = False,
    reward_r: float | None = None,
    always_open: bool = False,
) -> list[Condition]:
    """The checklist for one candidate, in a fixed order.

    `state` is `conditions.at_bar` output. `stack` is `poi.confluence` output.
    `at` is the instant being judged, which is the touch bar in a measurement and
    the last bar in a live decision; it defaults to `state["at"]`.
    """
    rules = rules or Rules()
    when = int(at if at is not None else state.get("at") or 0)
    demand = zone.side is ZoneSide.DEMAND
    out: list[Condition] = []

    # ---------------------------------------------------------------- time
    zones_now = killzones_at(when)
    matched = tuple(name for name in zones_now if name in rules.killzones)
    out.append(Condition(
        "killzone", bool(matched), "doctrine",
        f"in {matched}" if matched else f"outside; clock says {zones_now or 'none'}",
    ))

    # Day of week quality, per the practitioner's Quarterly Theory calendar.
    # Monday = Q1 (accumulation, off), Tuesday = Q2 (manipulation, high risk),
    # Wednesday = Q3 (distribution, highest probability), Thursday = Q4
    # (distribution/reversal), Friday = own profile. Weekend = no trading.
    #
    # MONDAY CONDITIONAL EXCEPTION: Monday trades are ALLOWED but only if
    # ALL extreme conditions are met (2-stage SSMT, tCISD, manipulation
    # after accumulation). When trading Monday, risk is multiplied by 0.5.
    ny_day = datetime.fromtimestamp(when, tz=NY).weekday()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                 "Saturday", "Sunday"]
    day_quality = {
        0: "Q1 accumulation - ALLOWED only if 2-stage, tCISD, and manipulation all confirmed. Risk × 0.5",
        1: "Q2 manipulation - high risk, wait for Q3",
        2: "Q3 distribution - highest probability",
        3: "Q4 distribution/reversal - high probability",
        4: "Friday own profile - medium",
        5: "weekend - no trading",
        6: "weekend - no trading",
    }
    # `always_open` DATANG DARI DERET INSTRUMENNYA, bukan dari daftar ticker.
    # Kalender di atas adalah minggu futures, dan sampai 30 Agustus 2026 ia
    # dipaksakan ke setiap instrumen: BTCUSD ditolak tiap Sabtu dan Minggu atas
    # nama hari libur forex, pada pasar yang jelas buka. Terukur hari itu, 2000
    # bar 1h di dalam `clock.market_shut`: XAUUSD 0, BTCUSD 621. Klausa ini
    # `doctrine`, jadi dua dari tujuh hari hilang tanpa satu angka pun di
    # belakangnya.
    day_ok = always_open or ny_day in (0, 1, 2, 3, 4)  # all weekdays
    monday_risk = 0.5 if ny_day == 0 else 1.0
    detail = f"{day_names[ny_day]}: {day_quality[ny_day]}"
    if always_open and ny_day >= 5:
        detail = (f"{day_names[ny_day]}: instrumen ini dagang saat minggu CME "
                  f"tutup, jadi kalender akhir pekan tidak berlaku untuknya")
    out.append(Condition(
        "day_of_week", day_ok, "doctrine",
        detail + (f" [risk × {monday_risk}]" if monday_risk < 1.0 else ""),
    ))

    # ------------------------------------------------------- price location
    band = state.get("range_band")
    if band is None:
        out.append(Condition("discount_or_premium", None, "doctrine",
                             "no dealing range knowable at this bar"))
    else:
        # The doctrine's own rule: sell in premium, buy in discount. The
        # saturated readings count as their side rather than as unknown - price
        # above the whole range is not less premium than the top quartile.
        want = ("discount", "at_or_below_low") if demand else (
            "premium", "at_or_above_high")
        out.append(Condition(
            "discount_or_premium", band in want, "doctrine",
            f"band {band}, wanted one of {want}",
        ))

    # ---------------------------------------------------------------- OTE
    # Optimal Trade Entry: the entry must rest deep inside the Fibonacci
    # OTE band (0.618-0.786 retracement) of the dealing range, not at
    # equilibrium. `dealing_range_pos` is 0 at the range low, 1 at the
    # high. For a demand (buy), the deep discount is near 0; for a supply
    # (sell), the deep premium is near 1. The OTE retracement band maps
    # to [0.214, 0.382] for buys and [0.618, 0.786] for sells.
    drp = zone.dealing_range_pos
    if drp is None:
        out.append(Condition("ote", None, "doctrine",
                             "no dealing range, no OTE reading"))
    else:
        # retracement = how far price pulled back from the extreme.
        # demand wants deep discount (drp near 0.214-0.382); supply wants
        # deep premium (drp near 0.618-0.786).
        # THE ONLY DEFINITION OF THE OTE BAND IN THIS REPO, and it is direction
        # aware, which the second copy was not. `app/fibonacci.py` carried its own
        # `in_ote` that returned the discount band for BOTH sides, while
        # `ote_bounds` in the same file read the ratios as positions and answered
        # the premium side - two functions in one file disagreeing about which
        # half of the range OTE sits in. Nothing imported it, so commit 4ab352a
        # "fixed" a band no caller ever read. Deleted rather than reconciled: this
        # line is six lines long, correct, and covered by tests/test_ict.py.
        ote_ok = (0.214 <= drp <= 0.382) if demand else (0.618 <= drp <= 0.786)
        out.append(Condition(
            "ote", ote_ok, "doctrine",
            f"entry at dealing-range {drp:.3f}, "
            f"OTE band {'0.214-0.382' if demand else '0.618-0.786'}"
            + ("" if ote_ok else ", in no man's land"),
        ))

    # ------------------------------------------------------------ quarterly
    profile = state.get("amd_profile")
    in_manip = state.get("in_manipulation_quarter")
    out.append(Condition(
        "manipulation_quarter", in_manip, "doctrine",
        f"profile {profile or 'unknown'}, quarter {state.get('quarter_day')}",
    ))
    out.append(Condition(
        "manipulation_seen", state.get("manipulation_done"), "doctrine",
        "a sweep took the previous quarter's extreme inside the manipulation "
        "quarter" if state.get("manipulation_done") else
        "conjunction incomplete: either the quarter has not arrived or no sweep "
        "took the level",
    ))
    # Structural rule from Quarterly Theory: after every 'A' (accumulation)
    # in the profile, manipulation MUST happen before any entry. "Perhatiin
    # sesudah A PASTI manipulation terdahulu." AMDX, XAMD, AAMD - all three
    # profiles have A before M. If the profile has an A and manipulation
    # hasn't been seen, the setup is a trap - the market hasn't completed
    # its accumulation phase.
    a_to_m = True
    a_to_m_detail = ""
    if profile and "A" in profile:
        manip_done = state.get("manipulation_done")
        if manip_done is True:
            a_to_m = True
            a_to_m_detail = f"profile {profile}, manipulation done"
        elif manip_done is False:
            a_to_m = False
            a_to_m_detail = (
                f"profile {profile} has accumulation but no manipulation "
                f"yet - setup is a trap until the sweep happens"
            )
        else:
            a_to_m = None
            a_to_m_detail = (
                f"profile {profile} has accumulation, manipulation not "
                f"knowable yet"
            )
    else:
        a_to_m = True
        a_to_m_detail = (
            f"profile {profile or 'unknown'}, no accumulation phase"
        )
    out.append(Condition(
        "manipulation_after_accumulation", a_to_m, "doctrine",
        a_to_m_detail,
    ))

    # ------------------------------------------------------------------ POI
    out.append(Condition(
        "poi_families", stack.families >= rules.min_families, "doctrine",
        f"{stack.families} of 4 families stack, wanted {rules.min_families}: "
        f"{ {k: v for k, v in stack.supports.items() if v} }",
    ))
    out.append(Condition(
        "poi_clean", stack.conflicts <= rules.max_conflicts, "doctrine",
        f"{stack.conflicts} opposite-side boxes in the band, tolerated "
        f"{rules.max_conflicts}",
    ))
    out.append(Condition(
        "cisd_in_band", stack.cisd > 0, "doctrine",
        f"{stack.cisd} CISD levels inside the box",
    ))

    # ------------------------------------------------------------------ DFR
    dfr = state.get("dfr_pos")
    if dfr is None:
        out.append(Condition("dfr_side", None, "doctrine",
                             "no defining range knowable at this bar"))
    else:
        # Above the range's own equilibrium for a supply, below it for a demand.
        # 0.5 is the range's midpoint by construction, not a fitted threshold.
        ok = dfr < 0.5 if demand else dfr > 0.5
        out.append(Condition("dfr_side", ok, "doctrine",
                             f"position {dfr} in the defining range"))

    # -------------------------------------------------------------- HTF zone
    # THE DOCTRINE'S CENTRAL MULTI-TIMEFRAME CLAIM: the higher timeframe sets the
    # bias, the lower one sets the entry. `confluence.mark_nesting` stamps
    # `nested_in` when this zone sits inside a same-side zone one degree up that
    # formed earlier and is still alive, so the clause is a lookup rather than a
    # second definition of nesting.
    #
    # MEASURED AT ZERO, TWICE, and the label says so. H2 in
    # docs/CALIBRATION.md tested nesting as a direction variable: p=0.33 with the
    # sign inverted at short horizons, and reliability was already disproved on
    # 2707 zones. A reader who requires this is choosing the method over this
    # project's own number, which is a legitimate choice made with open eyes.
    out.append(Condition(
        "htf_nested", bool(zone.nested_in), "measured",
        f"nested in {list(zone.nested_in)}" if zone.nested_in else
        "no same-side zone one degree up contains this one. H2 measured nesting "
        "at p=0.33",
    ))

    # ----------------------------------------------------------------- bias
    bias = state.get(rules.bias_degree)
    if bias is None:
        out.append(Condition("bias_agrees", None, "measured",
                             f"{rules.bias_degree} not knowable here"))
    else:
        # MEASURED, AND MEASURED AT ZERO. H7 in docs/CALIBRATION.md tested exactly
        # this and the zone added nothing over the bias alone - two of three
        # detectors came out slightly negative. Reported with that label so a
        # reader who switches it on knows they are choosing doctrine over the
        # project's own number.
        want = 1 if demand else -1
        out.append(Condition(
            "bias_agrees", bias == want, "measured",
            f"{rules.bias_degree}={bias}, wanted {want}. H7 measured the zone's "
            "contribution over bias at zero",
        ))

    # ----------------------------------------------------------------- SSMT
    if ssmt_side is None:
        out.append(Condition("ssmt", None, "measured",
                             "no partner series supplied to this call"))
    else:
        want_side = "low" if demand else "high"
        out.append(Condition(
            "ssmt", ssmt_side == want_side, "measured",
            f"newest knowable divergence on the {ssmt_side} side, wanted "
            f"{want_side}. Nothing connects a divergence to an outcome",
        ))

    # 2-stage SSMT: the practitioner's rule requires two consecutive
    # degrees both showing SSMT in the same direction. "Minim harus ada
    # dua SSMT stage." Stage 1 is the higher degree, stage 2 is the lower.
    out.append(Condition(
        "two_stage_confirmed", two_stage_confirmed, "doctrine",
        "two consecutive degrees both show SSMT in the same direction"
        if two_stage_confirmed else
        "no 2-stage SSMT confirmation on this timeframe",
    ))

    # Minimum RR: the practitioner's rule requires at least 2:1 reward to
    # risk before entry. Measured from the plan's own geometry.
    if reward_r is not None:
        out.append(Condition(
            "min_rr", reward_r >= 2.0, "doctrine",
            f"reward {reward_r:.1f}R against the stop, wanted >= 2.0"
            if reward_r >= 2.0 else
            f"reward {reward_r:.1f}R against the stop, below 2.0 minimum",
        ))
    else:
        out.append(Condition(
            "min_rr", None, "doctrine",
            "no target zone, reward cannot be computed",
        ))

    # ------------------------------------------------- draw on liquidity
    if draw == "unnominated":
        out.append(Condition("draw_agrees", None, "nominated",
                             "no draw nominated; Zonelab does not infer one"))
    else:
        out.append(Condition(
            "draw_agrees", draw == ("higher" if demand else "lower"), "nominated",
            f"caller nominated draw={draw}",
        ))

    return out


@dataclass
class Setup:
    """The checklist plus the two numbers a caller acts on."""

    conditions: list[Condition] = field(default_factory=list)

    @property
    def met(self) -> int:
        """Conditions that passed. `None` is not a pass."""
        return sum(1 for c in self.conditions if c.met is True)

    @property
    def unknown(self) -> int:
        return sum(1 for c in self.conditions if c.met is None)

    def failed_required(self, rules: Rules) -> list[str]:
        """Required conditions that did not pass, naming each one.

        A required condition that is UNKNOWN counts as failed. Silence cannot
        pass as assent - the same rule `bias.alignment` applies to a Daily with
        no usable bias.
        """
        by_name = {c.name: c for c in self.conditions}
        return [
            name for name in rules.required
            if name not in by_name or by_name[name].met is not True
        ]

    def why(self) -> list[str]:
        """One line per condition, for the journal. Numbers included."""
        return [
            f"{c.name}: {'yes' if c.met else 'no' if c.met is False else 'unknown'}"
            f" [{c.source}] {c.detail}"
            for c in self.conditions
        ]


def setup(*args, **kwargs) -> Setup:
    """`evaluate` wrapped in the object callers actually want."""
    return Setup(conditions=evaluate(*args, **kwargs))
