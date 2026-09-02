"""Praregistrasi: apakah entry KELANJUTAN menghasilkan uang setelah biaya.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.continuation_backtest \
        > ../docs/continuation_backtest.json

Ditulis 2 September 2026, SEBELUM satu angka pun dihitung.

===========================================================================
1. KENAPA INI ADA
===========================================================================

Pada 2 September 2026 XAUUSD rally dari 4282,31 ke 4397,85, 115,54 poin atau
2,70 persen, dan bagian tajamnya dua bar 30 menit berurutan mulai 09:00 New
York: +27,16 lalu +26,99. Zonelab tidak mengambil satu pun bagian darinya, dan
sebabnya BUKAN cacat.

Direkonstruksi per bar keputusan dari 06:00 sampai 13:00 UTC di 15 menit: entry
demand fresh terdekat yang lolos gerbang adalah 4294,06, lalu 4312,48 setelah
zona baru lahir 11:30, dan low sesudah SETIAP bar keputusan tidak pernah
mencapainya. Jarak tersempitnya di 10:00 UTC: entry 13,0 poin di bawah harga,
dan low sesudahnya berhenti 11 poin DI ATAS entry itu. Di 30 menit lebih jauh
lagi, 4172,92 sepanjang hari, 129 poin di bawah low hari itu.

Jadi lubangnya kapabilitas, bukan bug: SATU-SATUNYA entry long di engine ini
adalah limit di zona yang belum tersentuh, yaitu di belakang harga, dan di hari
tren satu arah harga tidak kembali. Setiap populasi yang pernah diukur di repo
ini berbentuk "harga KEMBALI ke sebuah level".

Dan gerakannya bukan news kalender. Feed-nya sehat (`NewsWeek.error` kosong, 113
event terbaca); event USD hari itu ADP Non-Farm Employment Change 12:15 UTC
(Medium) dan Factory Orders 14:00 UTC (Low). ADP cuma memberi spike ke 4344,72
lalu pudar. Rally-nya mulai 13:00 UTC, yaitu 09:00 New York, dan tidak ada satu
pun event di kalender pada jam itu.

===========================================================================
2. YANG DIUKUR, DAN APA YANG IA BUKAN
===========================================================================

Pertanyaannya: kalau sebuah aturan MENTRADINGKAN event kelanjutan dengan stop
dan target tetap dan biaya nyata, apakah hasilnya positif.

Ini BUKAN pengukuran arah, dan bedanya sudah membunuh klaim di repo ini
sebelumnya. `cisd` sebagai klaim arah NULL, t=-0,53 (`app/layers.py`). Bacaan
null tidak berarti trading-nya null, dan sebaliknya; `tools/event_backtest.py`
ada karena pertanyaan kedua itu belum pernah ditanyakan untuk ssmt dan psp.

EMPAT ARM, semuanya bisa diketahui di bar entry-nya BY CONSTRUCTION.
`structure.breaks` adalah satu forward pass tanpa lookahead apa pun, docstring
-nya menyatakan bahwa di bar i ia hanya boleh melihat swing yang sudah
confirmed di i dan hanya menguji CLOSE bar i, dan `cisd.cisds` dibentuk
mengikuti pola yang sama. Jadi entry di OPEN bar sesudah event-nya tidak
memerlukan satu angka pun dari masa depan.

  bos            entry searah break BOS
  choch          entry searah break CHoCH
  cisd           entry searah CISD
  sweep_against  entry LAWAN arah SWEEP, karena sweep adalah break yang gagal

Plus `oracle`, yang membuktikan rig ini BISA melaporkan LOLOS. Tanpanya sebuah
hasil "tidak ada yang lolos" tidak bisa dibedakan dari rig yang rusak.

===========================================================================
3. ATURAN YANG DIPAKAI, DAN KENAPA PERSIS INI
===========================================================================

`simulate` dari `tools/event_backtest.py`, tidak disalin ulang, supaya angkanya
SEBANDING dengan ssmt dan psp yang sudah diukur di rig itu. Konsekuensinya
aturannya juga sama dan tidak boleh diubah di sini: entry di OPEN bar
berikutnya, stop 1,0 ATR dan target 2,0 R dari ATR bar SEBELUMNYA, horizon 96
bar, biaya `exness_raw`, dan STOP MENANG saat satu bar halus menyentuh stop dan
target sekaligus. Asumsi terakhir itu pesimis dan dipilih begitu.

PLACEBO PER-EVENT JITTER, bukan shuffle. Untuk tiap trade real satu trade
placebo dibuka di event yang SAMA tapi digeser k bar ke depan,
k ~ Uniform(5, 40), di-seed deterministik dari identitas event-nya. Kontrol pool
yang di-shuffle sudah terbukti cacat di repo ini, jadi ia tidak dipakai.

===========================================================================
4. ATURAN LOLOS
===========================================================================

Per arm: delta berpasangan (real minus placebo) > 0, |t| di atas ambang
Bonferroni untuk EMPAT arm yang dinilai, n minimal MIN_N, dan walk-forward
minimal 7 dari 8 fold bertanda sama (uji tanda p = 0,0352).

Ekspektasi real sendiri juga dilaporkan lawan nol, karena mengalahkan placebo
tidak sama dengan menghasilkan uang: sebuah arm bisa mengalahkan jitter dan
tetap negatif setelah biaya, dan itu keadaan yang sudah terjadi di rig sebelah.

===========================================================================
5. YANG TIDAK DIJANJIKAN
===========================================================================

Killzone TIDAK ikut dinilai. Kasus yang memicu studi ini terjadi di jam buka New
York, dan membelah tiap arm per killzone akan mengalikan kelompok yang dinilai
dari 4 jadi belasan tanpa hipotesis yang ditulis lebih dulu. Angka per killzone
DICETAK sebagai bacaan supaya bisa jadi praregistrasi berikutnya, dan tidak
boleh dikutip sebagai hasil yang lolos.

Timeframe-nya 1 jam, sama dengan `event_backtest`, bukan 30 menit tempat order
dipasang. Itu batas yang sama yang `docs/lowtf_costed.json` ada untuk menutup di
sisi zona, dan ia belum ditutup di sisi event.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from app.cisd import cisds
from app.costs import schedule
from app.detect.structure import breaks
from app.indicators import wilder_atr
from app.pools import killzones_at
from tools.conditioned import _critical_t
from tools.dfr_outcomes import FOLDS, MIN_N, SERIES
from tools.intrabar import FINER
from tools.event_backtest import (
    ATR_PERIOD,
    BROKER,
    FINE,
    INTERVAL,
    JITTER_HI,
    JITTER_LO,
    Fine,
    _paired,
    _seed,
    _walk,
    simulate,
)
from tools.quant import clean

ARMS = ("bos", "choch", "cisd", "sweep_against")
ORACLE = "oracle"
T_THRESHOLD = _critical_t(len(ARMS))
MIN_SIGN_FOLDS = 7


def rows_for(symbol: str, bars: int, oracle: bool = False,
             interval: str = INTERVAL, fine_name: str = FINE) -> list[dict]:
    """Satu baris per trade: R real dan R placebo, per arm.

    `interval` bisa digeser karena di sisi ZONA jawabannya berbeda per
    timeframe: gerbang departure memberi -0,0153 R di 1 jam dan +0,1125 R di 30
    menit (`docs/lowtf_costed.json`). Pertanyaan yang sama belum pernah
    ditanyakan untuk event, jadi default-nya tetap 1 jam supaya angka yang sudah
    tercatat tidak bergeser, dan 30 menit dijalankan sebagai hipotesis terpisah.

    PERINGATAN RESOLUSI. Bar halus 30 menit adalah 5 menit, rasio 6, terkasar di
    tabel `FINER`, sementara 1 jam ke 5 menit adalah 12. Kontrol resolusi di
    `docs/lowtf_resolution.json` menunjukkan rasio kasar MENGGELEMBUNGKAN
    ekspektasi di keempat sel yang diuji, jadi angka 30 menit di sini adalah
    batas ATAS dan bukan estimasi.
    """
    coarse, _, _ = clean(f"mt5:{symbol}", interval, bars)
    if len(coarse) < 500:
        return []
    small, _, _ = clean(f"mt5:{symbol}", fine_name, 99_999)
    if len(small) < 500:
        return []
    fine = Fine(small)
    fees = schedule(symbol, False, BROKER)
    high = np.array([c.high for c in coarse], dtype=np.float64)
    low = np.array([c.low for c in coarse], dtype=np.float64)
    close = np.array([c.close for c in coarse], dtype=np.float64)
    atr = wilder_atr(high, low, close, ATR_PERIOD)
    times = [c.time for c in coarse]
    out: list[dict] = []

    def add(arm: str, key: str, i_event: int, direction: int) -> None:
        # ENTRY DI BAR SESUDAH EVENT-NYA. Event dikonfirmasi oleh CLOSE bar
        # `i_event`, jadi open bar berikutnya adalah harga pertama yang boleh
        # dipakai tanpa mengetahui bagaimana bar itu berakhir.
        i_entry = i_event + 1
        real = simulate(coarse, fine, atr, i_entry, direction, fees)
        if real is None:
            return
        rng = _seed(symbol, arm, key, direction)
        shift = rng.randint(JITTER_LO, JITTER_HI)
        fake = simulate(coarse, fine, atr, i_entry + shift, direction, fees)
        if fake is None:
            return
        zones = killzones_at(times[i_entry])
        out.append({"symbol": symbol, "arm": arm, "at": times[i_entry],
                    "direction": direction, "real_r": real, "fake_r": fake,
                    "killzone": zones[0] if zones else "none"})

    found, _ = breaks(coarse)
    for b in found:
        if b.index + 1 >= len(coarse):
            continue
        key = f"{b.kind}-{b.time}"
        if b.kind == "BOS":
            add("bos", key, b.index, b.direction)
        elif b.kind == "CHoCH":
            add("choch", key, b.index, b.direction)
        else:
            # SWEEP ADALAH BREAK YANG GAGAL, jadi doktrinnya menradingkannya
            # LAWAN arah break-nya. Tanda dibalik di sini dan bukan di
            # pembacaan, supaya arm ini bisa dibandingkan ke `bos` tanpa satu
            # definisi arah yang berbeda ikut pindah.
            add("sweep_against", key, b.index, -b.direction)

    events, _ = cisds(coarse)
    for e in events:
        if e.index + 1 < len(coarse):
            add("cisd", f"cisd-{e.time}", e.index, e.direction)

    if oracle:
        # ORACLE: arah yang benar, dibaca dari masa depan. Ia HARUS lolos, dan
        # kalau tidak maka rig ini tidak bisa melaporkan lolos dan angka lain di
        # file ini tidak berarti apa pun.
        step = max(1, len(coarse) // 400)
        for i in range(ATR_PERIOD + 2, len(coarse) - 2, step):
            ahead = min(len(coarse) - 1, i + 8)
            add(ORACLE, f"oracle-{times[i]}", i,
                1 if close[ahead] > close[i] else -1)
    return out


def _by_killzone(rows: list[dict]) -> dict:
    """Bacaan per killzone, BUKAN hipotesis. Lihat bagian 5."""
    out: dict = {}
    # `.get`, karena baris tanpa label killzone tidak boleh MERUNTUHKAN
    # penghakimannya. Label itu bacaan, dan bacaan yang hilang bukan alasan
    # untuk tidak menjawab pertanyaan yang dinilai.
    for name in sorted({r.get("killzone", "none") for r in rows}):
        mine = [r["real_r"] for r in rows
                if r.get("killzone", "none") == name]
        out[name] = {"n": len(mine), "exp_r": sum(mine) / len(mine)}
    return out


def judge(rows: list[dict], arm: str) -> dict:
    mine = [r for r in rows if r["arm"] == arm]
    if len(mine) < MIN_N:
        return {"n": len(mine), "passed": False,
                "verdict": f"n di bawah MIN_N {MIN_N}"}
    delta, t, n, real, fake = _paired(mine)
    wf = _walk(mine)
    real_arr = np.array([r["real_r"] for r in mine], dtype=np.float64)
    se = float(real_arr.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
    passed = bool(delta > 0 and abs(t) > T_THRESHOLD
                  and wf.get("graded", 0) >= FOLDS
                  and wf.get("positive", 0) >= MIN_SIGN_FOLDS)
    return {
        "n": n, "exp_r_real": real, "exp_r_placebo": fake,
        "delta": delta, "paired_t": t,
        "t_real_vs_zero": float(real / se) if se > 0 else None,
        "walk_forward": wf,
        "by_killzone": _by_killzone(mine),
        "passed": passed,
        "verdict": "LOLOS" if passed else "TIDAK LOLOS",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=20000)
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--interval", default=INTERVAL,
                    help="timeframe kasar. Default 1h, sama dengan "
                         "event_backtest, supaya angkanya sebanding")
    ap.add_argument("--fine", default="",
                    help="bar halus. Kosong berarti tabel FINER")
    args = ap.parse_args()

    fine_name = args.fine or FINER.get(args.interval, "5m")
    rows: list[dict] = []
    for symbol, _declared, bars in SERIES:
        bare = symbol.split(":")[-1]
        with contextlib.redirect_stdout(sys.stderr):
            got = rows_for(bare, min(bars, args.bars), oracle=args.oracle,
                           interval=args.interval, fine_name=fine_name)
        print(f"{bare}: {len(got)} trade", file=sys.stderr)
        rows.extend(got)

    out = {
        "preregistration": {
            "source": "tools/continuation_backtest.py, 2026-09-02",
            "question": "apakah entry KELANJUTAN (searah break atau CISD) "
                        "positif setelah biaya, lawan placebo jitter per-event",
            "why": "XAU rally 115,54 poin dan engine tidak punya satu pun entry "
                   "yang bisa ikut: entry long satu-satunya adalah limit di zona "
                   "belum tersentuh, dan harga tidak pernah kembali",
            "arms": list(ARMS),
            "rule": f"entry open bar+1, stop 1,0 ATR, target 2,0 R, horizon 96, "
                    f"biaya {BROKER}, stop menang saat seri",
            "placebo": f"jitter per-event Uniform({JITTER_LO},{JITTER_HI}) bar",
            "t_threshold_bonferroni": T_THRESHOLD,
            "min_n": MIN_N, "folds": FOLDS, "min_sign_folds": MIN_SIGN_FOLDS,
            "interval": args.interval, "fine": fine_name,
            "not_judged": "killzone dicetak sebagai bacaan, bukan hipotesis",
        },
        "population": {"n_total": len(rows),
                       "symbols": sorted({r["symbol"] for r in rows})},
        "arms": {arm: judge(rows, arm) for arm in ARMS},
    }
    if args.oracle:
        out["oracle"] = judge(rows, ORACLE)
    out["any_passed"] = [a for a, v in out["arms"].items() if v.get("passed")]
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
