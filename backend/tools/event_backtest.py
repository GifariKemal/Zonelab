"""Praregistrasi: apakah MENRADINGKAN ssmt dan psp menghasilkan uang setelah biaya.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.event_backtest \
        > ../docs/event_backtest.json

Ditulis 2 September 2026, SEBELUM satu angka pun dihitung. Bagian 1 sampai 9 di
bawah ini adalah praregistrasinya; angkanya keluar di stdout sebagai JSON.

===========================================================================
1. KENAPA INI ADA, DAN APA YANG IA BUKAN
===========================================================================

Diminta pemiliknya: "yang gagal, null tidak terukur, ataupun gk bisa di MT-5
kamu bisa bikin backtester sendiri via python". `ssmt` dan `psp` adalah dua
layer ICT yang tidak punya port MQL5, dan `tools/mqh_parity.py:UNPORTED`
mencatat alasannya.

TAPI KEDUANYA BUKAN "BELUM TERUKUR", dan itu harus dinyatakan di depan supaya
file ini tidak dibaca sebagai pengukuran pertama:

  - `ssmt`: NULL di 0 dari 24 sel, tanda terbagi 12 lawan 12
    (`docs/ssmt_outcomes.json`).
  - `psp`: NULL di 48 dari 48 sel, |z| terbesar 2,104 lawan bar Bonferroni
    3,279, dan `triad_crack_rate` identik 0,2644 untuk psp-sesudah-ssmt dan
    psp-sendirian, jadi premis pairing-nya tidak berdiri di data ini
    (`docs/psp_outcomes.json`). Ia juga dilarang menyentuh jalur keputusan oleh
    `tests/test_psp_not_wired_to_decisions.py`.

Keduanya diukur sebagai BACAAN: hit rate, resolusi bracket, arah. Yang belum
pernah ditanyakan pertanyaan yang berbeda dan lebih keras: kalau sebuah aturan
entry, stop dan target dipasang di atas event itu dan biaya broker dibebankan,
berapa R yang keluar. Bacaan yang null bisa saja tetap tradable kalau
distribusinya berekor; bacaan yang null DAN tidak tradable adalah dua fakta,
bukan satu.

INI JUGA BUKAN PENGGANTI STRATEGY TESTER. Ia tidak mensimulasikan book, tidak
mensimulasikan slippage per tick, dan tidak mengklaim reproduksi MT5. Yang ia
punya dan MT5 tidak: `ssmt` butuh dua instrumen ter-align pada grid kuarter,
yang di MQL5 berarti 500 sampai 700 baris untuk grid plus intersection
multi-symbol.

===========================================================================
2. POPULASI
===========================================================================

| Hal | Nilai |
|---|---|
| Instrumen | `SERIES` dari `tools/dfr_outcomes.py`, empat |
| Partner SSMT | `TCISD_PARTNER`, peta yang sudah ada di repo ini |
| Timeframe | 1 jam untuk keputusan, 5 menit untuk resolusi |
| Bar | 20.000 |
| Degree | day |

Partner TIDAK dipilih per run. `docs/PRAREGISTRASI-KORELASI.md` sudah melarang
itu: memilih partner setelah melihat hasil adalah pencarian yang menyamar jadi
replikasi, dan peta `TCISD_PARTNER` sudah ada sebelum file ini.

===========================================================================
3. ATURAN TRADE, DITETAPKAN SEKARANG DAN TIDAK DICARI
===========================================================================

| Hal | Aturan |
|---|---|
| Arah SSMT | side `low` diambil berarti LONG, side `high` berarti SHORT |
| Arah PSP | `direction` event-nya, `buy` atau `sell` |
| Entry | OPEN bar 1 jam berikutnya setelah event knowable |
| Stop | `STOP_ATR` x ATR(14) dari entry, melawan arah |
| Target | `RR` x jarak stop |
| Resolusi | bar 5 menit, dari bar entry ke depan |
| Horizon | `HORIZON` bar 1 jam; belum kena berarti flat di close |
| Biaya | `cost_to_risk` dengan profil `exness_raw`, dikurangkan dari R |

ARAH SSMT ADALAH DOKTRIN, BUKAN PILIHAN. Bullish SSMT adalah low yang diambil
satu instrumen dan tidak oleh partnernya, jadi long. Kalau tandanya ternyata
terbalik, itu temuan dan harus dilaporkan sebagai negatif, bukan dibalik
setelah melihat hasilnya - persis yang sudah terjadi pada `ifvg`, `breaker` dan
`cisd`, ketiganya keluar signifikan NEGATIF sebagai klaim arah.

STOP DAN TARGET BERTABRAKAN DI SATU BAR HALUS: STOP MENANG. Itu asumsi, dan ia
dinyatakan karena `docs/QA-QUANT.md` sudah mengukur harganya di jalur zona:
mengizinkan target di bar entry memberi +0,2021 R, melarangnya memberi
-0,0590 R, dan keduanya adalah sifat asumsi. Arah yang dipilih di sini yang
PESIMIS, karena angka yang menyanjung diri lewat asumsi timing adalah hal yang
paling mudah dipercaya dan paling sulit dibela.

`STOP_ATR` 1,0 dan `RR` 2,0 adalah PILIHAN, dan disebut begitu. 2R adalah target
tetap yang `tools/csid_ob_intrabar.py` sudah pakai; 1,0 ATR tidak punya
pendahulu di repo ini untuk event tanpa zona, karena tidak ada tepi zona untuk
menaruh stop di luarnya. Grid `{0,5, 1,0, 1,5} x {1,5, 2,0, 3,0}` DILAPORKAN
untuk transparansi dan TIDAK DINILAI: `K` Bonferroni dihitung hanya atas sel
yang dinilai, jadi grid itu tidak bisa menyelundup jadi pencarian.

===========================================================================
4. ARM, daftar tertutup
===========================================================================

| Arm | Event |
|---|---|
| `ssmt` | setiap divergensi SSMT degree day, arah dari side-nya |
| `psp_alone` | setiap PSP di SETIAP bar, tanpa syarat SSMT |
| `psp_after_ssmt` | PSP di dalam `WINDOW` bar setelah sebuah SSMT |

Arm ketiga adalah premis pairing-nya, dan ia diuji terpisah karena itu klaim
yang berbeda: `docs/psp_outcomes.json` sudah menemukan `triad_crack_rate`
identik untuk psp-sesudah-ssmt dan psp-sendirian, jadi kalau keduanya keluar
sama lagi di sini itu replikasi, bukan temuan baru.

`psp_alone` MEMINDAI SETIAP BAR, dan itu koreksi. Versi pertama memanggil
`psp.after_ssmt` untuk kedua arm dan membandingkan `bars_after_ssmt` dengan
`PAIR_WINDOW` 3 - sementara `app/psp.py:WINDOW` juga 3, jadi setiap PSP yang
ditemukan lolos syarat itu secara konstruksi. Kedua arm mengukur populasi yang
IDENTIK: n 728 keduanya, ekspektasi -0,123291 keduanya, hitungan per simbol sama
persis. Premis pairing-nya tidak diuji sama sekali, dan dua kolom angka yang
identik adalah satu-satunya alasan itu ketahuan.

===========================================================================
5. KONTROL
===========================================================================

PER-EVENT JITTER DI SUMBU WAKTU. Untuk tiap trade real, satu trade placebo
dengan ARAH YANG SAMA, instrumen yang sama, aturan stop dan target yang sama,
tapi entry-nya digeser `k` bar ke depan dengan `k ~ Uniform(JITTER_LO,
JITTER_HI)` bulat, di-seed deterministik dari identitas event-nya.

Ia menjawab satu pertanyaan yang "bandingkan dengan nol" tidak bisa jawab:
apakah yang menghasilkan R itu EVENT-nya, atau cuma arah plus volatilitas
instrumen itu di periode itu. `docs/zonelab-direction-drift-control` sudah
mencatat kenapa itu mengikat: run Wyckoff pertama palsu karena klaim arah diuji
lawan nol alih-alih lawan drift per-instrumen.

TIDAK ADA SHUFFLING. Kontrol shuffled `pools` memberi +2,90pp dengan
p = 9,2e-05 lalu terbukti cacat, karena mengacak memutus pasangan antara jarak
sebuah level dan volatilitas bar-nya sendiri.

===========================================================================
6. AMBANG LULUS, ditetapkan sekarang
===========================================================================

Sebuah arm hanya LULUS kalau keempatnya lolos:

1. `n >= MIN_N` trade.
2. Delta R berpasangan (real dikurangi placebo) POSITIF.
3. `|t| >` kritis dua sisi ber-Bonferroni, alpha 0,05 dibagi `K`, dengan `K`
   jumlah arm yang layak dinilai. `K` dicetak SEBELUM satu baris dilaporkan.
4. Walk-forward `FOLDS` fold berurutan waktu, sign test satu sisi p <= 0,05.
   Dengan 8 fold itu minimal 7 dari 8 fold delta-nya positif.

Ekspektasi R absolut DILAPORKAN tapi TIDAK dijadikan syarat lulus, dan itu
keputusan: sebuah arm yang mencetak +0,05 R sementara placebo-nya mencetak
+0,08 R sedang kalah dari arah-plus-volatilitas, dan menyebutnya lulus karena
angkanya positif adalah cara paling rapi untuk menipu diri.

===========================================================================
7. YANG TIDAK DIJAWAB
===========================================================================

- Tidak ada model book. `--max-orders` tidak ada di sini, jadi ia mengasumsikan
  setiap trade diambil. `docs/order_key.json` mencatat bahwa asumsi itu berlaku
  di setiap rig pengukuran di repo ini.
- Tidak ada slippage per tick. Biayanya dari tabel `exness_raw` yang diturunkan
  dari terminal, dan itu satu angka per instrumen.
- Satu degree saja (day). SSMT di degree lain adalah populasi lain.
- Ia tidak mengubah status `psp`: `tests/test_psp_not_wired_to_decisions.py`
  tetap melarangnya menyentuh jalur order, apa pun angka di sini.

===========================================================================
8. SELF-CHECK DAN ORACLE
===========================================================================

`--selftest` menjalankan simulator pada bar buatan yang jawabannya diketahui:
sebuah long yang targetnya tersentuh harus memberi +RR dikurangi biaya, yang
stopnya tersentuh harus memberi -1 dikurangi biaya, dan bar yang menyentuh
KEDUANYA harus memberi hasil stop.

`--oracle` menambahkan arm yang arahnya dibaca dari masa depan. Ia HARUS lulus.
Studi yang melaporkan nol pemenang tanpa pernah menunjukkan pemenang seperti
apa yang bisa ia lihat sedang melaporkan diamnya sendiri.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)
"""

from __future__ import annotations

import argparse
import bisect
import contextlib
import json
import random
import sys
from math import comb, sqrt

import numpy as np
from statistics import NormalDist

from app.costs import cost_to_risk, schedule
from app.indicators import wilder_atr
from app.psp import after_ssmt as psp_after_ssmt
from app.psp import at_bar as psp_at_bar
from app.ssmt import ssmt as ssmt_read
from tools.checklist_outcomes import TCISD_PARTNER, _aligned
from tools.dfr_outcomes import FOLDS, MIN_N, SERIES
from tools.quant import clean

BROKER = "exness_raw"
INTERVAL = "1h"
FINE = "5m"
DEGREE = "day"

#: Aturan trade, ditetapkan di Bagian 3 dan tidak dicari.
STOP_ATR = 1.0
RR = 2.0
HORIZON = 96
ATR_PERIOD = 14

#: Jendela "sesudah SSMT" adalah `app/psp.py:WINDOW` itu sendiri, dibaca dan
#: tidak dipilih ulang - jadi arm `psp_after_ssmt` adalah apa pun yang
#: `psp.after_ssmt` kembalikan, tanpa filter kedua. Filter kedua yang
#: membandingkan `bars_after_ssmt` dengan angka yang sama adalah tautologi, dan
#: itu yang membuat versi pertama file ini mengukur satu populasi dua kali.

#: Geseran kontrol, dalam bar 1 jam. Cukup jauh untuk keluar dari jendela event
#: dan cukup dekat untuk tetap di regime yang sama.
JITTER_LO = 5
JITTER_HI = 40

#: Grid yang DILAPORKAN dan TIDAK DINILAI. Lihat Bagian 3.
GRID_STOPS = (0.5, 1.0, 1.5)
GRID_RRS = (1.5, 2.0, 3.0)


def _seed(*parts: object) -> random.Random:
    return random.Random("|".join(str(p) for p in parts))


def simulate(
    coarse, fine, atr, i_entry: int, direction: int, fees: dict,
    stop_atr: float = STOP_ATR, rr: float = RR,
) -> float | None:
    """R bersih satu trade, atau None kalau ia tidak bisa dibuka.

    Entry di OPEN bar `i_entry`. Stop dan target dari ATR bar SEBELUMNYA, jadi
    tidak ada satu angka pun di aturan entry yang datang dari bar entry itu
    sendiri.

    STOP MENANG saat satu bar halus menyentuh keduanya. Lihat Bagian 3: arah
    asumsi yang dipilih yang pesimis.
    """
    if i_entry < 1 or i_entry >= len(coarse):
        return None
    scale = float(atr[i_entry - 1])
    if scale <= 0:
        return None

    entry = float(coarse[i_entry].open)
    risk = stop_atr * scale
    if risk <= 0:
        return None
    stop = entry - direction * risk
    target = entry + direction * risk * rr

    start = coarse[i_entry].time
    end_index = min(len(coarse) - 1, i_entry + HORIZON)
    stop_at = coarse[end_index].time

    lo = bisect.bisect_left(fine.times, start)
    hi = bisect.bisect_right(fine.times, stop_at)
    gross = None
    for k in range(lo, hi):
        hit_stop = (
            fine.low[k] <= stop if direction > 0 else fine.high[k] >= stop
        )
        hit_target = (
            fine.high[k] >= target if direction > 0 else fine.low[k] <= target
        )
        if hit_stop:
            gross = -1.0
            break
        if hit_target:
            gross = rr
            break
    if gross is None:
        # Flat di close horizon. Tidak ada bar halus berarti tidak ada resolusi,
        # dan trade yang tidak bisa diselesaikan DIBUANG alih-alih dinilai nol.
        if hi <= lo:
            return None
        gross = direction * (fine.close[hi - 1] - entry) / risk

    spread = coarse[i_entry].spread
    if spread is None and fees.get("spread_bp") is not None:
        spread = entry * fees["spread_bp"] / 10_000
    nights = (HORIZON * 3600) / 86_400
    cost_r, _ = cost_to_risk(
        entry, risk, spread or 0.0, fees, nights,
        swap_bp=fees.get("swap_bp" if direction > 0 else "swap_bp_short",
                         fees.get("swap_bp", 0.0)),
    )
    return gross - cost_r


class Fine:
    """Bar halus sebagai array sejajar, sekali per simbol."""

    __slots__ = ("times", "high", "low", "close")

    def __init__(self, candles):
        self.times = [c.time for c in candles]
        self.high = [c.high for c in candles]
        self.low = [c.low for c in candles]
        self.close = [c.close for c in candles]


def rows_for(symbol: str, bars: int, oracle: bool = False) -> list[dict]:
    """Satu baris per trade: R real dan R placebo, per arm."""
    coarse, _, _ = clean(f"mt5:{symbol}", INTERVAL, bars)
    if len(coarse) < 500:
        return []
    small, _, _ = clean(f"mt5:{symbol}", FINE, 99_999)
    if len(small) < 500:
        return []
    fine = Fine(small)
    fees = schedule(symbol, False, BROKER)

    # ARRAY, BUKAN LIST. `wilder_atr` bertipe untuk ndarray dan pyright
    # menangkapnya sebelum satu baris dijalankan; list-nya jalan hari ini lewat
    # duck typing dan akan berhenti jalan di hari numpy dipakai lebih dalam.
    high = np.array([c.high for c in coarse], dtype=np.float64)
    low = np.array([c.low for c in coarse], dtype=np.float64)
    close = np.array([c.close for c in coarse], dtype=np.float64)
    atr = wilder_atr(high, low, close, ATR_PERIOD)
    times = [c.time for c in coarse]

    # PARTNER TIDAK DIKARANG. `TCISD_PARTNER` memetakan dua belas instrumen dan
    # ETHUSD bukan salah satunya - ia muncul di sana hanya sebagai partner
    # BTCUSD, satu arah. Menambahkan kebalikannya berarti MEMILIH partner, yang
    # Bagian 2 larang, jadi instrumen tanpa partner terdeklarasi dilewati dan
    # ketiadaannya dicatat di output. Populasi yang menyusut karena alasan yang
    # tertulis lebih baik daripada populasi penuh yang separuh partnernya dipilih
    # oleh orang yang sedang membaca hasilnya.
    partner = TCISD_PARTNER.get(symbol)
    if partner is None:
        print(f"{symbol}: DILEWATI, tidak ada partner di TCISD_PARTNER",
              file=sys.stderr)
        return []
    grid, _ = _aligned([f"mt5:{symbol}", f"mt5:{partner}"], INTERVAL, 99_999)
    grid = {s.split(":")[-1]: rows for s, rows in grid.items() if rows}
    if len(grid) < 2:
        return []
    events, _ = ssmt_read(grid, DEGREE)

    out: list[dict] = []

    def add(arm: str, key: str, i_entry: int, direction: int) -> None:
        real = simulate(coarse, fine, atr, i_entry, direction, fees)
        if real is None:
            return
        rng = _seed(symbol, arm, key, direction)
        shift = rng.randint(JITTER_LO, JITTER_HI)
        fake = simulate(coarse, fine, atr, i_entry + shift, direction, fees)
        if fake is None:
            return
        out.append(
            {
                "symbol": symbol,
                "arm": arm,
                "at": times[i_entry],
                "direction": direction,
                "real_r": real,
                "fake_r": fake,
            }
        )

    for ev in events:
        # Hanya event yang menyentuh SIMBOL INI. Sebuah divergensi antara dua
        # instrumen lain bukan sinyal di chart ini.
        if symbol not in (ev.took, ev.failed):
            continue
        # EVENT DI LUAR JENDELA BAR DIBUANG, dan ini cacat yang sudah menipu
        # run pertama. `_aligned` selalu meminta 99.999 bar sementara `coarse`
        # dipotong ke `--bars`, jadi setiap event yang MENDAHULUI bar pertama
        # membuat `bisect_left` mengembalikan 0 dan trade-nya dibuka di bar 1.
        # Ribuan event berbeda lalu jadi satu trade yang sama dengan kunci
        # berbeda: run `--bars 6000` melaporkan n=7709 untuk `ssmt` sementara
        # run 20.000 bar memberi n=1597, dan arm oracle-nya LULUS di atas
        # tumpukan itu. Bar lebih sedikit menghasilkan event lebih banyak adalah
        # angka yang tidak mungkin, dan itu yang membuatnya ketahuan.
        i = bisect.bisect_left(times, ev.knowable_at)
        if i >= len(times) or times[i] < ev.knowable_at:
            continue
        if ev.knowable_at < times[0]:
            continue
        # ARAH DARI DOKTRIN, lihat Bagian 3. Low yang diambil berarti long.
        direction = 1 if ev.side == "low" else -1
        if ev.took != symbol:
            # Simbol ini yang GAGAL mengambil, jadi ia sisi lain dari bacaan
            # yang sama: gagal mengambil high adalah bentuk bullish.
            direction = -direction
        add("ssmt", f"ssmt-{ev.knowable_at}", i + 1, direction)

        got = psp_after_ssmt(coarse, i)
        if got is not None:
            d = 1 if got.direction == "buy" else -1
            add("psp_after_ssmt", f"pair-{got.at}", got.at + 1, d)

        if oracle:
            # ARAH DARI MASA DEPAN. Lihat Bagian 8: ia harus lulus.
            j = i + 1
            if j + 1 < len(times):
                ahead = 1 if close[min(len(close) - 1, j + 12)] > close[j] else -1
                add("oracle_lookahead", f"oracle-{ev.knowable_at}", j, ahead)

    # PSP SENDIRIAN, dipindai di SETIAP bar. Lihat Bagian 4: arm ini tidak ada
    # di versi pertama, dan tanpanya premis pairing tidak bisa diuji.
    seen: set[int] = set()
    for i in range(1, len(coarse) - 1):
        got = psp_at_bar(coarse, i)
        if got is None or i in seen:
            continue
        seen.add(i)
        d = 1 if got.direction == "buy" else -1
        add("psp_alone", f"alone-{i}", i + 1, d)
    return out


def _sign_test(positive: int, folds: int) -> float:
    if folds == 0:
        return 1.0
    return sum(comb(folds, k) for k in range(positive, folds + 1)) / 2**folds


def _paired(rows: list[dict]) -> tuple[float, float, int, float, float]:
    """Delta berpasangan, t, n, ekspektasi real, ekspektasi placebo."""
    diff = [r["real_r"] - r["fake_r"] for r in rows]
    n = len(diff)
    real = sum(r["real_r"] for r in rows) / n if n else 0.0
    fake = sum(r["fake_r"] for r in rows) / n if n else 0.0
    if n < 2:
        return (diff[0] if n else 0.0), 0.0, n, real, fake
    mean = sum(diff) / n
    var = sum((d - mean) ** 2 for d in diff) / (n - 1)
    se = sqrt(var / n)
    return mean, (mean / se if se > 0 else 0.0), n, real, fake


def _walk(rows: list[dict]) -> dict:
    ordered = sorted(rows, key=lambda r: r["at"])
    if len(ordered) < FOLDS * 2:
        return {"graded": 0, "positive": 0, "p": 1.0, "deltas": []}
    edges = [round(i * len(ordered) / FOLDS) for i in range(FOLDS + 1)]
    deltas = []
    for a, b in zip(edges, edges[1:]):
        chunk = ordered[a:b]
        if len(chunk) >= 2:
            deltas.append(_paired(chunk)[0])
    positive = sum(1 for d in deltas if d > 0)
    return {
        "graded": len(deltas),
        "positive": positive,
        "p": _sign_test(positive, len(deltas)),
        "deltas": [round(d, 4) for d in deltas],
    }


def study(series, oracle: bool = False) -> dict:
    rows: list[dict] = []
    skipped: list[str] = []
    for symbol, _iv, bars in series:
        name = symbol.split(":")[-1]
        with contextlib.redirect_stdout(sys.stderr):
            got = rows_for(name, bars, oracle)
        rows.extend(got)
        if not got:
            skipped.append(name)
        print(f"{name}: {len(got)} trade", file=sys.stderr)
    if not rows:
        return {"error": "populasi kosong"}

    by_arm: dict[str, list[dict]] = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)

    judged = [arm for arm, rs in by_arm.items() if len(rs) >= MIN_N]
    k = max(1, len(judged))
    critical = NormalDist().inv_cdf(1 - (0.05 / k) / 2)

    cells: dict[str, dict] = {}
    for arm, rs in sorted(by_arm.items()):
        delta, t, n, real, fake = _paired(rs)
        wf = _walk(rs)
        cells[arm] = {
            "n": n,
            "exp_r_real": real,
            "exp_r_control": fake,
            "delta_r": delta,
            "t": t,
            "walk_forward": wf,
            "judged": arm in judged,
            "passes": bool(
                n >= MIN_N and delta > 0 and abs(t) > critical and wf["p"] <= 0.05
            ),
            "by_symbol": {
                s: len([r for r in rs if r["symbol"] == s])
                for s in sorted({r["symbol"] for r in rs})
            },
        }

    winners = sorted(a for a, c in cells.items() if c["passes"])
    return {
        "preregistered": "tools/event_backtest.py, 2026-09-02",
        "asked_by": "pemiliknya: backtester Python untuk yang tidak bisa di MT5",
        "already_measured_null": {
            "ssmt": "0 dari 24 sel, tanda 12 lawan 12 (docs/ssmt_outcomes.json)",
            "psp": "48 dari 48 sel null, |z| maks 2,104 lawan bar 3,279 "
                   "(docs/psp_outcomes.json)",
        },
        "rules": {
            "stop_atr": STOP_ATR, "rr": RR, "horizon_bars": HORIZON,
            "interval": INTERVAL, "fine": FINE, "degree": DEGREE,
            "broker": BROKER,
            "both_hit_in_one_fine_bar": "stop menang, asumsi pesimis",
        },
        "control": {
            "shape": "per-event jitter di sumbu waktu, arah sama",
            "shift_bars": [JITTER_LO, JITTER_HI],
        },
        "population": {
            "n_trades": len(rows),
            "symbols": sorted({r["symbol"] for r in rows}),
            # DICATAT, TIDAK DIDIAMKAN. Populasi yang menyusut tanpa mengatakan
            # instrumen mana yang hilang terlihat sama dengan populasi penuh.
            "skipped": skipped,
        },
        "arms_judged": len(judged),
        "alpha_corrected": 0.05 / k,
        "critical_t": critical,
        "cells": cells,
        "passes": winners,
        "verdict": (
            f"LULUS: {winners}" if winners else "TIDAK ADA ARM YANG LULUS"
        ),
    }


def _selftest() -> None:
    """Simulator dijalankan pada bar buatan yang jawabannya diketahui."""
    from app.models import Candle

    def bar(t, o, h, low_, c):
        return Candle(time=t, open=o, high=h, low=low_, close=c, volume=1.0,
                      spread=0.0)

    fees = {"commission_bp": 0.0, "slippage_bp": 0.0, "swap_bp": 0.0,
            "spread_bp": 0.0}
    coarse = [bar(3600 * i, 100, 101, 99, 100) for i in range(200)]
    atr = [1.0] * 200

    # Target tersentuh: long, risk 1,0, target 102. Bar halus naik ke 102.
    up = Fine([bar(3600 + 300 * i, 100, 102.5, 99.5, 102) for i in range(20)])
    got = simulate(coarse, up, atr, 1, 1, fees)
    assert got is not None and abs(got - RR) < 1e-9, got

    # Stop tersentuh: bar halus turun ke 98,9, stop di 99.
    down = Fine([bar(3600 + 300 * i, 100, 100.2, 98.9, 99) for i in range(20)])
    got = simulate(coarse, down, atr, 1, 1, fees)
    assert got is not None and abs(got + 1.0) < 1e-9, got

    # KEDUANYA di satu bar halus: stop menang. Lihat Bagian 3.
    both = Fine([bar(3600 + 300 * i, 100, 102.5, 98.9, 100) for i in range(20)])
    got = simulate(coarse, both, atr, 1, 1, fees)
    assert got is not None and abs(got + 1.0) < 1e-9, got

    # Biaya DIKURANGKAN, bukan diabaikan.
    costly = {**fees, "commission_bp": 10.0}
    paid = simulate(coarse, up, atr, 1, 1, costly)
    assert paid is not None and paid < RR - 1e-6, paid

    # Kontrol di-seed stabil.
    assert _seed("a", 1).randint(5, 40) == _seed("a", 1).randint(5, 40)
    print("selftest OK", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=0)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--oracle", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    series = SERIES if not args.bars else tuple(
        (s, i, args.bars) for s, i, _ in SERIES
    )
    out = study(series, args.oracle)
    json.dump(out, sys.stdout, indent=2, default=str)
    print()
    return 0 if "error" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
