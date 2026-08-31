"""Praregistrasi keenam: apakah `structure` dan `projections` MENGKONDISIKAN kohort zona.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.conditioned_structure \
        > ../docs/conditioned_structure.json

Ditulis 30 Agustus 2026, SEBELUM satu angka pun dihitung. Bagian 1 sampai 7 di
bawah ini adalah praregistrasinya; angkanya keluar di stdout sebagai JSON.

===========================================================================
1. PERTANYAANNYA, DAN KENAPA IA BELUM PERNAH DIAJUKAN
===========================================================================

`app/layers.py` mencatat untuk layer `structure`: "H6 and H9 measured these
exact objects for direction and both came out null". Untuk `projections`:
"MEASURED NULL 2026-08-20 ... +0,46pp lawan kontrol jitter per-event, 6,5x DI
BAWAH ambang praregistrasi, gagal walk-forward 6 dari 8".

Kedua angka itu menjawab pertanyaan yang sama: apakah objeknya memprediksi arah
BERDIRI SENDIRI. Keduanya null. Yang BELUM pernah ditanya: apakah objeknya
mengkondisikan ekspektansi kohort zona yang sudah lolos gerbang. Itu pertanyaan
lain, dan jawaban null untuk yang pertama tidak menjawabnya.

`tools/conditioned.py` sudah menguji 29 kolom dan nol lolos, tapi tidak satu pun
menyentuh struktur atau proyeksi: mencari 'swing', 'bos', 'choch', 'sweep',
'mss', 'proj' di 29 nama itu menjawab daftar kosong.

PRIOR-NYA RENDAH DAN ITU DINYATAKAN DI DEPAN. 29 kolom sudah nol, dan
`docs/reality_check.json` (White's RC, Hansen's SPA, Romano-Wolf StepM)
memastikan itu bukan artefak Bonferroni. Hasil null di sini adalah hasil yang
diharapkan, dan ia akan dilaporkan sebagai null.

===========================================================================
2. POPULASI DAN OUTCOME
===========================================================================

| Hal        | Nilai |
|---|---|
| Instrumen  | `tools/checklist_outcomes.py:SYMBOLS`, delapan, daftar tertutup |
| Timeframe  | 1 jam, zona dideteksi di sana |
| Resolusi   | bar 5 menit, lewat `tools/intrabar.py:resolved` |
| Populasi   | first touch tiap zona `supply_demand` dengan `departure_atr >= 2.0` dan target terbaca |
| Outcome    | R multiple setelah biaya `exness_raw`, flat di rollover 21:00 UTC |

DAFTAR INSTRUMEN DIPINJAM, BUKAN DIPILIH. `SYMBOLS` di `checklist_outcomes.py`
sudah tertutup dan sudah disaring untuk hal yang studi ini juga butuhkan:
riwayat 5 menit yang ada di terminal ini. Menyusun daftar baru berarti memilih,
dan memilih instrumen adalah pencarian yang menyamar jadi lingkup.

RESOLUSI INTRABAR MENGIKAT. `docs/QA-QUANT.md`: mengizinkan target di bar entry
memberi +0,2021 R, melarangnya memberi -0,0590 R, dan keduanya sifat asumsi.
Studi ini memakai `resolved()` sehingga ambiguitasnya menyusut dari 60 menit ke
5. Harganya dinyatakan: riwayat 5 menit di terminal ini pendek, jadi populasinya
jauh lebih kecil daripada 953 trade praregistrasi kedua.

===========================================================================
3. KOLOM YANG DIUJI, DAFTAR TERTUTUP
===========================================================================

Lima kolom struktur kali DUA skala fraktal, ditambah satu kolom proyeksi.

  `bos_before_touch_{skala}`    sisi BOS TERAKHIR di dalam hidup zona, relatif
                                sisi zona: `agree`, `oppose`, `none`
  `choch_before_touch_{skala}`  sama, untuk CHoCH
  `sweep_before_touch_{skala}`  sisi SWEEP terakhir: `into` kalau sapuannya
                                mengambil likuiditas di seberang arah trade
                                (demand disapu ke bawah, supply ke atas),
                                `away` kalau sebaliknya, `none`
  `mss_side_{skala}`            sama, untuk MSS
  `bars_since_last_break_{skala}` bar sejak BOS-atau-CHoCH terakhir sebelum
                                sentuhan, di-bucket
  `projection_in_band`          berapa level proyeksi range London jatuh di
                                dalam band zona, di-bucket

DUA SKALA, KEDUANYA, DAN ITU BUKAN PEMBOROSAN. `app/detect/structure.py:overlay`
menggambar `swing` (swing_n=50) dan `internal` (internal_n=5) berdampingan.
Memilih satu skala setelah melihat hasilnya adalah pencarian; memilih satu
sebelum melihat hasilnya tetap pilihan yang tidak ada sumbernya. Keduanya diuji,
dan harganya cuma K yang lebih besar.

JENDELA EVENT ADALAH HIDUP ZONA, BUKAN ANGKA YANG DIPILIH. Event dihitung dari
`zone.anatomy.leg_out_to` (bar zona selesai terbentuk) sampai bar sentuhan,
eksklusif. Tidak ada satu pun sumber yang menerbitkan "N bar sebelum sentuhan",
dan menyapu N adalah memilih jawaban. Jendela ini ditentukan sepenuhnya oleh
objek yang sudah ada: zona lahir, lalu struktur patah atau tidak sebelum harga
kembali. `bars_since_last_break` memakai lookback tak terbatas justru supaya
kebasian event terbaca sebagai kolom tersendiri dan tidak tersembunyi di dalam
jendela.

EVENT TERAKHIR, BUKAN "ADA ATAU TIDAK ADA". Event terakhir adalah yang masih
hidup di bar sentuhan. "Ada BOS searah" dan "ada BOS berlawanan" bisa benar
dua-duanya di jendela yang sama, dan menggabungkan keduanya jadi satu boolean
akan melaporkan `True` pada bar yang strukturnya justru sedang melawan.

`none` ADALAH KELOMPOK TERSENDIRI, bukan `False`. Alasannya diambil dari
`app/detect/structure.py:overlay` sendiri, yang menolak menggabungkan
`aligned_with_swing` False dengan None: False harus tetap berarti "struktur
mayor menunjuk arah LAIN". Tidak ada event sama sekali bukan event yang
melawan.

BUCKET DITETAPKAN DI DEPAN, BUKAN DARI SAMPEL. `bars_since_last_break`:
`0-9`, `10-49`, `50-249`, `250+`. `projection_in_band`: `0`, `1`, `2+`.
Kuartil populasi akan membuat potongannya jadi fungsi dari sampel, dan
`tools/conditioned.py:_dfr_band` sudah menolak itu untuk alasan yang sama.

PROYEKSI: SATU SESI, DUA ARAH, ENAM LEVEL BAWAAN. Sesi `london` karena itu
`ProjectionParams.sessions` bawaan yang dikirim. Arah KEDUANYA karena
`ProjectionParams.direction` bawaannya 0 dan `app/projections.py` menyatakan
kenapa: arah pada chart aslinya dibaca dari ke mana harga pergi SETELAH range,
dan itu hindsight. Level `(0, -0.5, -1, -1.5, 2, 2.5)` adalah transkripsi
27.jpeg, dipakai apa adanya. Jadi 12 harga per range, dihitung lawan
`[zone.bottom, zone.top]`.

Range yang dipakai adalah range London TERBARU yang `knowable_at`-nya sudah
lewat pada bar sentuhan. Range diambil dari `app/overlays.py:_session_ranges`
supaya jendelanya byte-for-byte sama dengan jendela yang ray pool digambar dari
sana, dan harganya dari `app/projections.py:projection` supaya tandanya tidak
pernah difork. `at` dipotong ke bar pembukti pertama: harga level TIDAK BISA
bergerak dengan `at` (modul itu menyatakannya), jadi pemotongan ini hanya
membuat `_taken` berhenti setelah satu bar alih-alih menyapu 30 ribu.

===========================================================================
4. ANTI-LOOKAHEAD
===========================================================================

Tiga potongan, dan yang ketiga diuji dan bukan diklaim.

  a. Event dipotong di `e.time < times[touch]`, JADI CLOSE BAR SENTUHAN SENDIRI
     TIDAK IKUT. Entry terisi di dalam bar sentuhan, jadi close bar itu belum
     ada saat keputusan diambil. `<=` akan memberi struktur sebuah bar yang
     belum ditutup.
  b. Proyeksi dipotong di `knowable_at <= times[touch]`, dan `knowable_at`
     menurut definisi `app/projections.py` adalah bar pertama yang MEMBUKTIKAN
     range-nya sudah tutup.
  c. `_selftest` memotong deret di bar N, menghitung state di sentuhan
     sebelum N, lalu menyambung 300 bar baru dan menuntut state-nya IDENTIK.
     Kalau test itu gagal, seluruh run dibuang. Angka dari kolom yang melihat
     masa depan bukan angka yang lebih lemah, ia angka yang salah.

===========================================================================
5. HIPOTESIS, AMBANG, DAN APA YANG DIHITUNG LOLOS
===========================================================================

H0: tidak satu pun nilai dari sebelas kolom di bagian 3 memisahkan ekspektansi
R kohort ini dari sisa kohort.

Sebuah nilai kolom MEMISAHKAN kalau EMPAT syarat terpenuhi, dan keempatnya
ditulis sekarang:

  1. `n >= MIN_GROUP` (30) di grupnya DAN di sisanya.
  2. `|t|` Welch (grup lawan sisa populasi) melewati nilai kritis Bonferroni.
  3. Tanda selisihnya bertahan di KEDUA paruh sampel (urut waktu).
  4. Tanda selisihnya bertahan setelah R dikurangi rata-rata INSTRUMENNYA
     sendiri.

Syarat 4 adalah tambahan atas `docs/PRAREGISTRASI-KONDISI.md` bagian 4, dan ia
praregistrasi di sini dan bukan post-hoc. Alasannya: populasi ini menggabungkan
delapan instrumen yang ekspektansi dasarnya berbeda tanda. Kalau nilai kolomnya
menumpuk di instrumen yang ekspektansinya memang lebih rendah, kolomnya
memisahkan INSTRUMEN dan bukan setup. `tools/checklist_outcomes.py` menemukan
persis itu setelah run-nya selesai dan harus melabelinya post-hoc; di sini ia
mengikat dari awal.

KOREKSI BANYAK-PERBANDINGAN. Alpha dua sisi 0,05 dibagi K, dengan K jumlah
SELURUH nilai kolom yang layak dinilai (`n >= 30` di grup dan di sisanya). K
dihitung di lintasan pertama SEBELUM satu baris pun dilaporkan, memakai
`tools/conditioned.py:_critical_t`, sehingga ambangnya tidak bisa digeser
setelah tabelnya terbaca. Nilai kritisnya dicetak di `threshold` bersama K.

n MINIMAL. 30 per grup, sama dengan `tools/conditioned.py:MIN_GROUP`. Grup di
bawah itu dilaporkan dengan n-nya dan `judged: false`, tidak dibuang diam-diam.

WALK-FORWARD. Seluruh baris diurutkan waktu lalu dipotong `FOLDS` (8) bagian
sama banyak, angka yang sama dengan gerbang departure supaya bisa dibandingkan
langsung. Tiap nilai kolom yang layak dinilai melaporkan berapa fold tandanya
sama dengan tanda gabungan, DAN nomor fold yang gagal. Tidak ada purging: tidak
ada satu parameter pun yang dipasang dari data di sini, jadi tidak ada kebocoran
train ke test yang bisa di-purge.

===========================================================================
6. YANG TIDAK AKAN DILAKUKAN
===========================================================================

  - Tidak menambah instrumen, kolom, skala, sesi, atau timeframe setelah
    melihat hasil.
  - Tidak menyapu `swing_n`, `internal_n`, `mss_window`, atau level proyeksi.
    Tidak ada sumber primer yang menerbitkan angkanya, dan menyapu adalah
    memilih jawaban.
  - Tidak membuang instrumen yang ekspektansinya negatif.
  - Tidak melaporkan kolom konstan sebagai nol. Kolom yang cuma punya satu
    nilai dilaporkan `constant` beserta nilainya.
  - Tidak menulis apa pun ke `app/`. Kolom yang memisahkan mendapat
    walk-forward pada subpopulasinya, bukan tempat di `app/plan.py`.

===========================================================================
7. YANG SUDAH DIKETAHUI AKAN BERPERILAKU ANEH
===========================================================================

  - MSS JARANG. Diukur di sini sebelum studinya jalan: 33.976 bar XAUUSD 1h
    memberi 2.910 event dan hanya 48 di antaranya MSS, dari 890 BOS, 859 CHoCH
    dan 1.113 SWEEP. Jadi `mss_side` kemungkinan besar hampir seluruhnya
    `none`, dan kalau ia konstan itu dilaporkan sebagai batas metode, bukan
    sebagai nol yang mengesankan.
  - ATURAN SWEEP SUDAH DIPERBAIKI 20 Agustus 2026: satu level memancarkan SATU
    sweep, bukan re-arming. Pada 3000 bar XAUUSD 15m angkanya 88 sweep dari 88
    level, turun dari 147. ANGKA 8.725 SWEEP MENDAHULUI PERBAIKAN ITU dan tidak
    dipakai di mana pun di sini.
  - `bars_since_last_break_swing` akan besar: swing_n 50 memberi 291 event swing
    di 33.976 bar, jadi bucket `250+` mungkin memuat sebagian besar populasi.
"""

from __future__ import annotations

import argparse
import bisect
import contextlib
import json
import sys

import numpy as np

from app import projections as proj
from app.detect import DETECTORS
from app.detect.structure import overlay as structure_overlay
from app.models import Candle, StructureParams, SupplyDemandParams
from app.overlays import _session_ranges
from tools.calibrate import POPULATION
from tools.checklist_outcomes import FOLDS, SYMBOLS, _clause
from tools.conditioned import ALPHA, MIN_GROUP, _critical_t
from tools.intrabar import FINER, resolved
from tools.quant import BROKER, clean

#: Kedua skala fraktal yang `app/detect/structure.py:overlay` gambar.
SCALES = ("swing", "internal")

#: Kolom struktur, per skala. Daftar tertutup, bagian 3.
STRUCTURE_COLUMNS = (
    "bos_before_touch",
    "choch_before_touch",
    "sweep_before_touch",
    "mss_side",
    "bars_since_last_break",
)

#: Seluruh kolom yang diuji, dalam urutan tetapnya.
COLUMNS = tuple(
    f"{name}_{scale}" for scale in SCALES for name in STRUCTURE_COLUMNS
) + ("projection_in_band",)

#: Sesi yang diproyeksikan. `ProjectionParams.sessions` bawaan, bukan pilihan.
PROJECTION_SESSION = "london"

#: Bucket `bars_since_last_break`, ditetapkan di depan. Bagian 3.
BREAK_AGE_EDGES = (10, 50, 250)
BREAK_AGE_NAMES = ("0-9", "10-49", "50-249", "250+")


def _age_band(bars: int | None) -> str:
    """Umur break terakhir, di-bucket dengan potongan yang ditetapkan di depan."""
    if bars is None:
        return "none"
    return BREAK_AGE_NAMES[bisect.bisect_right(BREAK_AGE_EDGES, bars)]


def _relative(direction: int, side: str) -> str:
    """Arah event relatif sisi zona. Demand mau +1, supply mau -1."""
    wanted = 1 if side == "demand" else -1
    return "agree" if direction == wanted else "oppose"


def _sweep_relative(direction: int, side: str) -> str:
    """Sapuan yang mengambil likuiditas DI SEBERANG arah trade adalah `into`.

    Demand ditradingkan long, jadi sapuan ke BAWAH (direction -1) mengambil
    sell-side liquidity di bawah zona lalu harga kembali naik ke dalamnya. Itu
    bacaan doktriner "sweep into demand". Supply kebalikannya.
    """
    into = -1 if side == "demand" else 1
    return "into" if direction == into else "away"


def _projection_prices(candles: list[Candle]) -> list[tuple[int, tuple[float, ...]]]:
    """Harga level tiap range London, dengan bar yang membuktikan range itu tutup.

    Satu entry per range, memuat 12 harga: enam level bawaan kali dua arah.
    Diurutkan menaik menurut `knowable_at`, supaya pencarian per trade cuma
    satu bisect.

    `at` DIPOTONG KE BAR PEMBUKTI PERTAMA dan itu bukan pemotongan hasil.
    `app/projections.py` menyatakan harga level tidak bergerak dengan `at`; yang
    bergerak cuma `taken_at`, dan studi ini tidak memakainya. Tanpa potongan ini
    `_taken` menyapu seluruh sisa deret untuk tiap level tiap range.
    """
    times = [c.time for c in candles]
    out: list[tuple[int, tuple[float, ...]]] = []
    for _, high, low in _session_ranges(candles, [PROJECTION_SESSION]):
        after = bisect.bisect_left(times, high.window_to)
        if after >= len(times):
            continue
        prices: list[float] = []
        knowable: int | None = None
        for direction in (1, -1):
            found = proj.projection(
                candles, high.window_from, high.window_to,
                high.price, low.price, direction, at=times[after],
            )
            if found is None:
                continue
            knowable = found.knowable_at
            prices += [level.price for level in found.levels]
        if knowable is not None and prices:
            out.append((knowable, tuple(prices)))
    out.sort(key=lambda row: row[0])
    return out


def _events_by_scale(
    candles: list[Candle],
) -> dict[str, dict[str, list[tuple[int, int]]]]:
    """Event struktur sebagai `(waktu, arah)`, per skala dan per jenis.

    Dari `overlay` apa adanya, dengan `max_events=0`: cap kebaruan mengurung
    sampel di ekor riwayat dan sudah pernah memakan satu putaran kalibrasi di
    project ini. `StructureParams` sisanya bawaan, tidak disapu.
    """
    _, events, _ = structure_overlay(candles, StructureParams(max_events=0))
    out: dict[str, dict[str, list[tuple[int, int]]]] = {
        scale: {kind: [] for kind in ("BOS", "CHoCH", "SWEEP", "MSS", "BREAK")}
        for scale in SCALES
    }
    for event in events:
        rows = out[event.scale]
        rows[event.kind].append((event.time, event.direction))
        # BREAK adalah BOS-atau-CHoCH: struktur yang benar-benar patah. SWEEP
        # sengaja tidak ikut, aturan yang sama dengan `bias_series`, yang
        # menolak membiarkan sebuah wick membalik trend.
        if event.kind in ("BOS", "CHoCH"):
            rows["BREAK"].append((event.time, event.direction))
    for rows in out.values():
        for kind in rows:
            rows[kind].sort()
    return out


def _last_before(rows: list[tuple[int, int]], lo: int, hi: int) -> int | None:
    """Arah event terakhir dengan `lo <= waktu < hi`, atau None.

    `hi` EKSKLUSIF, dan itu potongan anti-lookahead bagian 4a: bar sentuhan
    close-nya belum ada saat entry terisi di dalamnya.
    """
    end = bisect.bisect_left(rows, (hi, -2))
    start = bisect.bisect_left(rows, (lo, -2))
    return rows[end - 1][1] if end > start else None


def _state(zone, touch: int, times: list[int], events, projections) -> dict:
    """Sebelas kolom untuk satu trade, semuanya knowable di bar sentuhan."""
    now = times[touch]
    birth = times[min(zone.anatomy.leg_out_to, len(times) - 1)]
    side = zone.side.value
    state: dict[str, object] = {}
    for scale in SCALES:
        rows = events[scale]
        for name, kind, how in (
            ("bos_before_touch", "BOS", _relative),
            ("choch_before_touch", "CHoCH", _relative),
            ("sweep_before_touch", "SWEEP", _sweep_relative),
            ("mss_side", "MSS", _relative),
        ):
            direction = _last_before(rows[kind], birth, now)
            state[f"{name}_{scale}"] = (
                "none" if direction is None else how(direction, side)
            )
        # Lookback TAK TERBATAS, sengaja: kebasian event adalah pertanyaan
        # kolom ini, jadi ia tidak boleh dipotong jendela hidup zona.
        end = bisect.bisect_left(rows["BREAK"], (now, -2))
        age = None
        if end:
            age = touch - bisect.bisect_left(times, rows["BREAK"][end - 1][0])
        state[f"bars_since_last_break_{scale}"] = _age_band(age)

    at = bisect.bisect_right(projections, (now, ())) - 1
    if at < 0:
        state["projection_in_band"] = "none"
    else:
        inside = sum(1 for price in projections[at][1]
                     if zone.bottom <= price <= zone.top)
        state["projection_in_band"] = (
            "0" if inside == 0 else "1" if inside == 1 else "2+"
        )
    return state


def rows_for(symbol: str, interval: str, fine: str) -> list[dict]:
    """Tiap trade yang lolos gerbang, diselesaikan di bar halus, plus state.

    Outcome dari `tools/intrabar.py:resolved`; state dari `structure_overlay`
    dan `app/projections.py`. Join lewat `zone_id`, dan zona dideteksi ulang
    dengan `POPULATION` yang sama supaya id-nya cocok.
    """
    fine_rows = [r for r in resolved(symbol, interval, fine) if r["cleared"]]
    if not fine_rows:
        return []
    candles, _, _ = clean(symbol, interval)
    zones, _ = DETECTORS["supply_demand"](
        candles, SupplyDemandParams(**{**POPULATION, "show_broken": True}))
    by_id = {z.id: z for z in zones}
    times = [c.time for c in candles]
    events = _events_by_scale(candles)
    projections = _projection_prices(candles)

    out = []
    for row in fine_rows:
        touch = int(row["at"])
        zone = by_id.get(row["zone_id"])
        if zone is None or touch < 1:
            continue
        out.append({
            "symbol": symbol, "zone_id": row["zone_id"], "time": times[touch],
            "r": float(row["r"]), "side": zone.side.value,
            **_state(zone, touch, times, events, projections),
        })
    return out


def _judged_groups(rows: list[dict]) -> int:
    """K, dihitung SEBELUM satu hasil pun dilaporkan. Bagian 5."""
    k = 0
    for column in COLUMNS:
        seen: dict[object, int] = {}
        for row in rows:
            seen[row.get(column)] = seen.get(row.get(column), 0) + 1
        k += sum(1 for n in seen.values()
                 if n >= MIN_GROUP and len(rows) - n >= MIN_GROUP)
    return k


def _folds(rows: list[dict], pick, sign: float) -> dict:
    """Walk-forward untuk satu nilai kolom: berapa fold tandanya bertahan.

    Fold yang gagal disebut nomornya, karena "6 dari 8" tanpa nomornya tidak
    bisa diperiksa ulang.
    """
    ordered = sorted(rows, key=lambda r: r["time"])
    size = len(ordered) // FOLDS
    same, failed, deltas = 0, [], []
    for i in range(FOLDS):
        part = ordered[i * size:(i + 1) * size if i < FOLDS - 1 else len(ordered)]
        a = np.array([r["r"] for r in part if pick(r)])
        b = np.array([r["r"] for r in part if not pick(r)])
        if len(a) < 2 or len(b) < 2:
            deltas.append(None)
            failed.append(i + 1)
            continue
        delta = float(a.mean() - b.mean())
        deltas.append(delta)
        if (delta > 0) == (sign > 0):
            same += 1
        else:
            failed.append(i + 1)
    return {"folds": FOLDS, "same_sign": same, "failed_folds": failed,
            "deltas": deltas}


def _column(rows: list[dict], name: str, critical: float) -> dict:
    """H0 untuk satu kolom, dengan syarat keempat bagian 5 mengikat.

    `_clause` dipakai apa adanya supaya aritmetika Welch, paruh, dan demeaning
    tidak difork. Yang ditambahkan di sini cuma pengetatan verdict-nya: syarat 4
    (tanda bertahan setelah demeaning) adalah praregistrasi di studi ini, bukan
    post-hoc seperti di `checklist_outcomes.py`.
    """
    out = _clause(rows, name, critical)
    out.pop("prior_measurement", None)
    if out.get("constant"):
        return out
    strict = []
    for group in out["groups"]:
        if not group.get("judged"):
            continue
        agree = (group["delta_dm"] > 0) == (group["delta"] > 0)
        group["demeaned_same_sign"] = bool(agree)
        group["separates"] = bool(group["separates"] and agree)
        group["walk_forward"] = _folds(
            rows, lambda r, k=group["value"]: r.get(name) == k, group["delta"])
        if group["separates"]:
            strict.append(group["value"])
    out["separates"] = strict
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

    means = {s: float(np.mean([r["r"] for r in rows]))
             for s, rows in per_symbol.items()}
    for row in pooled:
        row["r_dm"] = row["r"] - means[row["symbol"]]

    k = _judged_groups(pooled)
    critical = _critical_t(k)
    ordered = sorted(pooled, key=lambda r: r["time"])
    size = len(ordered) // FOLDS
    folds = []
    for i in range(FOLDS):
        part = ordered[i * size:(i + 1) * size if i < FOLDS - 1 else len(ordered)]
        folds.append({"fold": i + 1, "n": len(part),
                      "from": part[0]["time"], "to": part[-1]["time"],
                      "exp_r": float(np.mean([r["r"] for r in part]))})

    columns = [_column(pooled, name, critical) for name in COLUMNS]
    return {
        "preregistered": "docstring tools/conditioned_structure.py, 2026-08-30",
        "run": {"interval": interval, "fine": fine, "symbols": list(per_symbol),
                "folds": FOLDS, "broker": BROKER, "scales": list(SCALES),
                "projection_session": PROJECTION_SESSION},
        "population": {
            "n": len(pooled),
            "exp_r": float(np.mean([r["r"] for r in pooled])),
            "per_symbol": {s: {"n": len(rows), "exp_r": means[s]}
                           for s, rows in per_symbol.items()},
        },
        "threshold": {"alpha": ALPHA, "groups_judged": k,
                      "alpha_corrected": ALPHA / k if k else None,
                      "critical_t": critical, "min_group": MIN_GROUP,
                      "requires": ["n>=30 grup dan sisanya",
                                   "|t| Welch >= critical_t",
                                   "tanda sama di kedua paruh",
                                   "tanda sama setelah demeaning instrumen"]},
        "walk_forward": folds,
        "columns": columns,
        "separating": [c["clause"] for c in columns if c.get("separates")],
        "rows": {
            "columns": ["symbol", "time", "r", "side"] + list(COLUMNS),
            "data": [[r["symbol"], r["time"], round(r["r"], 6), r["side"]]
                     + [r[c] for c in COLUMNS] for r in ordered],
        },
    }


def _fake(n: int, seed: int = 7) -> list[Candle]:
    """Deret acak yang bisa direproduksi, untuk test lookahead bagian 4c."""
    rng = np.random.default_rng(seed)
    price = 100.0
    out = []
    for i in range(n):
        price += float(rng.normal(0, 1))
        span = abs(float(rng.normal(0, 0.5))) + 0.1
        out.append(Candle(time=1_600_000_000 + i * 3600, open=price,
                          high=price + span, low=price - span, close=price))
    return out


class _Zone:
    """Zona palsu seminimal yang `_state` baca. Bukan model wire."""

    def __init__(self, at: int, top: float, bottom: float, side: str) -> None:
        self.anatomy = type("A", (), {"leg_out_to": at})()
        self.top, self.bottom = top, bottom
        self.side = type("S", (), {"value": side})()


def _synth(early: float, late: float, n: int = 800) -> list[dict]:
    """Kohort palsu yang kolom `col`-nya memisahkan sebesar `early` lalu `late`.

    Noise-nya nyata dan seed-nya tetap, supaya `t` yang keluar berukuran wajar:
    tanpa noise `t` melompat ke ribuan dan syarat 2 tidak bisa diuji terpisah
    dari syarat 3.
    """
    rng = np.random.default_rng(11)
    out = []
    for i in range(n):
        hot = i % 2 == 0
        lift = early if i < n // 2 else late
        value = (lift if hot else -lift) + float(rng.normal(0, 1))
        out.append({"symbol": "X", "time": i, "col": "hot" if hot else "cold",
                    "r": value, "r_dm": value})
    return out


def _selftest() -> None:
    """Cacat yang tool ini ditulis untuk menangkap, disuntikkan lalu diperiksa."""
    # 1. BUCKET. Potongannya ditetapkan di depan, jadi ia harus jatuh di tempat
    # yang ditulis praregistrasi dan bukan satu langkah di sebelahnya.
    assert [_age_band(x) for x in (0, 9, 10, 49, 50, 249, 250, None)] == [
        "0-9", "0-9", "10-49", "10-49", "50-249", "50-249", "250+", "none"]
    assert _relative(1, "demand") == "agree" and _relative(1, "supply") == "oppose"
    assert _sweep_relative(-1, "demand") == "into"
    assert _sweep_relative(-1, "supply") == "away"

    # 2. `hi` EKSKLUSIF. Event tepat di bar sentuhan tidak boleh terbaca, dan
    # jendela hidup zona memang memotong di kiri.
    rows = [(10, 1), (20, -1), (30, 1)]
    assert _last_before(rows, 0, 30) == -1
    assert _last_before(rows, 0, 31) == 1
    assert _last_before(rows, 25, 30) is None

    # 3. GERBANGNYA TIDAK KOSONG. Kolom yang benar-benar memisahkan harus
    # LOLOS; kalau tidak, verdict null di file ini tidak berarti apa-apa.
    strong = _synth(0.5, 0.5)
    assert _column(strong, "col", 3.0)["separates"], \
        "kolom yang jelas memisahkan dilaporkan tidak memisahkan"
    # Dan tiap syarat memang mengikat, satu per satu. `_synth(0.5, -0.15)`
    # sengaja tetap lolos syarat 2 (delta gabungan besar) supaya kegagalannya
    # bisa DITELUSURI ke syarat 3 dan bukan ke ambang t.
    assert not _column(_synth(0.5, -0.15), "col", 3.0)["separates"], \
        "syarat 3 (tanda di kedua paruh) tidak mengikat"
    assert not _column(strong, "col", 99.0)["separates"], \
        "syarat 2 (|t| lewat kritis) tidak mengikat"
    flipped = [{**r, "r_dm": -r["r_dm"]} for r in strong]
    assert not _column(flipped, "col", 3.0)["separates"], \
        "syarat 4 (tanda setelah demeaning) tidak mengikat"
    thin = [{**r, "col": "hot" if i < 5 else "cold"}
            for i, r in enumerate(strong)]
    assert not _column(thin, "col", 3.0)["separates"], \
        "syarat 1 (n >= 30) tidak mengikat"

    # 4. ANTI-LOOKAHEAD, bagian 4c. State di sentuhan sebelum N harus identik
    # ketika 300 bar baru disambung di belakang.
    candles = _fake(1200)
    cut, touch = 900, 850
    zone = _Zone(700, candles[touch].high + 1, candles[touch].low - 1, "demand")
    short = candles[:cut]
    a = _state(zone, touch, [c.time for c in short],
               _events_by_scale(short), _projection_prices(short))
    b = _state(zone, touch, [c.time for c in candles],
               _events_by_scale(candles), _projection_prices(candles))
    assert a == b, f"state melihat masa depan: {a} != {b}"
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
