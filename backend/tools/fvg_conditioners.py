"""Tiga klaim praktisi tentang FVG, diukur sebagai pengkondisi resolved R.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.fvg_conditioners > ../docs/fvg_conditioners.json

DARI MANA PERTANYAANNYA. Diminta 8 September 2026, dan dikutip apa adanya supaya
yang diukur bisa dibandingkan dengan yang ditanyakan:

    "FVG yang high probability udah termasuk dalam premium (buat sells) dan
     discount (buat buys). Gap itu kalo berbobot sm PSP, termasuk lebih
     probability. Kalo price udah ngepurge liquidity sebelumnya di timeframe
     seleksi kita."

Tiga klaim, jadi tiga lengan, plus satu gabungan karena klaim kedua ditulis
sebagai TAMBAHAN di atas yang pertama ("termasuk lebih") dan bukan sebagai
pengganti.

KENAPA INI BUKAN DETEKTOR PSP. Permintaan awalnya PSP sebagai detektor kotak,
dan itu bertabrakan dengan `tests/test_psp_not_wired_to_decisions.py`: guard itu
melarang string `psp` di `advisor.py`, sementara setiap `ZoneKind` WAJIB punya
kalimat di sana. Alih-alih melonggarkan guard yang berdiri di atas null 48 sel,
PSP dipakai di sini sebagai PENGKONDISI - yang memang bentuk klaimnya.

PRIOR-NYA RENDAH DAN DINYATAKAN DI DEPAN. Empat hal sudah diukur di repo ini dan
semuanya melawan hipotesis di bawah:

  1. `docs/psp_outcomes.json`, 48 sel, nol memisahkan, |z| terbesar 2,10 lawan
     ambang 3,28. H2 di sana khusus menanyakan apakah SSMT di depan PSP
     menambah sesuatu, dan laju crack triad identik di kedua lengan
     (0,2644 lawan 0,2644).
  2. `tools/conditioned.py`, 12 kolom, nol lolos.
  3. `tools/conditioned_structure.py`, `sweep_before_touch` - yang paling dekat
     dengan klaim ketiga - null di keenam grupnya, |t| terbesar 2,16 lawan
     ambang 3,14.
  4. `tools/conditioned_gaps.py`, 7 kolom, `separating` kosong.

APA YANG BELUM PERNAH DIUKUR, dan itu alasan file ini ada: keempat rig di atas
berjalan di populasi `supply_demand`. Tak satu pun menguji pengkondisi apa pun
di atas populasi FVG, dan tak satu pun menguji posisi premium/discount sebagai
pengkondisi. Zona FVG bahkan tidak membawa `dealing_range_pos` - terukur None di
6.390 dari 6.390 - jadi posisinya harus distempel di sini.

=============================== PRAREGISTRASI ===============================
Ditulis 8 September 2026, SEBELUM satu angka pun dihitung dari file ini.

HIPOTESIS, empat, semuanya DUA SISI. Arah yang diklaim praktisi dicatat sebagai
`predicted` di keluaran supaya bisa dibaca, tapi ambangnya dua sisi: tiga dari
empat prior di atas negatif atau null, jadi menetapkan tanda di depan berarti
memilih arah setelah melihat data lain.

  H1 favourable_side   FVG demand yang proximal-nya di DISCOUNT dan FVG supply
                       yang proximal-nya di PREMIUM punya resolved R berbeda
                       dari yang tidak. Prediksi praktisi: lebih tinggi.
  H2 psp_before_touch  FVG yang didahului PSP punya resolved R berbeda.
                       Prediksi: lebih tinggi.
  H3 purge_before_touch FVG yang didahului sapuan likuiditas punya resolved R
                       berbeda. Prediksi: lebih tinggi.
  H4 fav_and_psp       Gabungan H1 dan H2, diuji lawan SISA populasi, supaya
                       ia bisa dibaca sebaris dengan tiga yang lain.
  H5 psp_given_fav     PSP DI ANTARA yang sudah favourable saja. INI klaim
                       praktisi yang sesungguhnya - "termasuk lebih" berarti
                       PSP menambah DI ATAS posisi, bukan menang lawan yang
                       posisinya salah. H4 tidak bisa memisahkan keduanya, dan
                       membaca H4 sebagai jawaban atas klaim itu adalah cara
                       studi ini bisa keliru tanpa satu angka pun salah.
                       Pembedaan yang sama yang dipakai `docs/psp_outcomes.json`
                       antara H1 dan H2-nya.

SYARAT LOLOS, keempatnya harus terpenuhi:
  n >= 30 di kedua lengan,
  |t| Welch >= ambang Bonferroni untuk 8 grup yang dinilai,
  tanda sama di kedua paruh sampel,
  walk-forward 8 fold dengan tanda yang stabil (>= 7 dari 8).

Lengan yang menguasai lebih dari 95 persen populasi dilaporkan sebagai
degenerat, bukan sebagai hasil.

BATAS YANG DINYATAKAN, DUA.

H3 HAMPIR DEGENERAT KARENA DEFINISINYA, bukan karena pasarnya. `purge` benar
kalau ADA satu saja level terkonfirmasi yang ditembus lalu ditutup kembali di
dalam `PSP_LOOKBACK` bar. Dengan fraktal 50 bar ada puluhan level hidup di tiap
titik, jadi hampir setiap jendela sepuluh bar menyapu sesuatu - terukur 84,7
persen populasi. Sebuah syarat yang dipenuhi 85 persen sampel tidak bisa jadi
penyaring selektif walaupun ia memisahkan. Versi yang lebih ketat - level
TERDEKAT saja, atau level yang jaraknya di bawah sekian ATR - adalah pertanyaan
yang BERBEDA dan butuh praregistrasi sendiri; mengetatkannya sesudah melihat
hasil ini adalah memilih definisi setelah melihat jawabannya. Hal yang sama
berlaku untuk H2 pada sembilan instrumen, tempat laju PSP terbaca 82,4 persen
(di XAUUSD sendiri 55,8).

`position_at` mengembalikan None sampai KEDUA sisi
dealing range terkonfirmasi, dan zona dengan posisi None DIBUANG dari H1 dan H4
alih-alih dianggap tidak-favourable. Menganggapnya tidak-favourable akan
mencampur "diukur di sisi yang salah" dengan "belum bisa diukur", dan dua hal
itu tidak sama.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from app.dealing_range import mark_dealing_range
from app.models.zone import DEPARTURE_GATE_ATR_CEILING
from app.detect import DETECTORS
from app.detect.structure import swings
from app.psp import detect as psp_detect
from tools.csid_ob_intrabar import (
    FOLDS,
    MIN_GROUP,
    SYMBOLS,
    _critical_t,
    _welch,
)
from tools.detectors_costed import _params, resolved_as
from tools.quant import clean

#: Berapa bar sebelum sentuhan sebuah PSP masih dihitung "mendahului" zona.
#: Sama dengan `lookback` yang dipakai `tools/conditioned.py` untuk kolom yang
#: sama, supaya dua rig tidak diam-diam memakai dua definisi PSP.
PSP_LOOKBACK = 10

#: Lebar fraktal untuk level kunci PSP dan untuk sapuan. 50 menyamai
#: `dealing_range` dan `conditioned.py`; ia DIPILIH di sana dan diwarisi di
#: sini, bukan diukur ulang.
SWING_N = 50

#: Jumlah grup yang dinilai: lima pengkondisi kali dua lengan.
K = 10


def _cell_rows(symbol: str, interval: str) -> list[dict]:
    """Trade FVG yang terselesaikan, tiap satu distempel keempat pengkondisi."""
    fine = {"1h": "5m", "4h": "15m", "1d": "1h"}[interval]
    with contextlib.redirect_stdout(sys.stderr):
        raw = resolved_as("fvg", symbol, interval, fine)
    # GERBANGNYA PLAFON, BUKAN LANTAI, dan versi pertama file ini salah di sini.
    # `intrabar.resolved` menstempel `cleared = departure_atr >= 2.0`, yang
    # adalah gerbang ORDER BLOCK; menyalinnya apa adanya - seperti yang
    # dilakukan `csid_ob_intrabar`, tempat ia memang benar - membuang 93 persen
    # populasi FVG. Terukur di XAUUSD 1 jam: 204 zona lolos lantai 2,0 lawan
    # 2.931 yang lolos plafon 0,25 yang sesungguhnya. Studi pertama karena itu
    # berjalan di n=37 dan null-nya tidak berarti apa-apa.
    rows = [r for r in raw
            if r["departure"] is not None
            and r["departure"] < DEPARTURE_GATE_ATR_CEILING]
    if not rows:
        return []
    candles, _, _ = clean(symbol, interval)
    zones, _ = DETECTORS["fvg"](candles, _params("fvg"))
    # Stempel posisi dealing range DI SENTUHAN PERTAMA. Populasi ini memang
    # first touch, jadi itu instan yang benar - alasan yang sama yang ditulis
    # `tools/conditioned.py` untuk pilihan yang sama.
    mark_dealing_range(zones, candles)
    by_id = {z.id: z for z in zones}

    times = [c.time for c in candles]
    index_of = {int(t): i for i, t in enumerate(times)}
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    pivots = swings(high, low, SWING_N, SWING_N)
    psp_levels = [(s.confirmed_at, float(s.price)) for s in pivots]

    out: list[dict] = []
    for r in rows:
        zone = by_id.get(r["zone_id"])
        if zone is None:
            continue
        touch = index_of.get(r["at"] if isinstance(r["at"], int) else -1)
        if touch is None:
            touch = r["at"] if isinstance(r["at"], int) else None
        if touch is None or touch < 1 or touch >= len(candles):
            continue

        pos = zone.dealing_range_pos
        fav: bool | None = None
        if pos is not None:
            fav = pos < 0.5 if zone.side.value == "demand" else pos > 0.5

        # LEVEL YANG SUDAH TERKONFIRMASI SAJA, jadi tidak ada bar sesudah
        # sentuhan yang ikut. `confirmed_at <= touch` adalah seluruh aturan
        # anti-lookahead di sini.
        near = [lv for at, lv in psp_levels if at <= touch]
        psp = bool(near) and psp_detect(
            candles, max(0, touch - PSP_LOOKBACK), near,
            lookback=PSP_LOOKBACK,
        ) is not None

        # SAPUAN: dalam `PSP_LOOKBACK` bar sebelum sentuhan, harga menembus
        # sebuah level terkonfirmasi lalu MENUTUP kembali di sisi asalnya.
        # Definisi yang sama dengan penolakan PSP, tanpa syarat triad - itulah
        # yang membedakan H3 dari H2.
        lo = max(0, touch - PSP_LOOKBACK)
        purge = False
        for at, lv in psp_levels:
            if at > touch:
                continue
            for j in range(lo, touch):
                if high[j] > lv >= candles[j].close:
                    purge = True
                    break
                if low[j] < lv <= candles[j].close:
                    purge = True
                    break
            if purge:
                break

        out.append({
            "r": r["r"], "at": r["at"], "cell": f"{symbol} {interval}",
            "favourable_side": fav,
            "psp_before_touch": psp,
            "purge_before_touch": purge,
            "fav_and_psp": None if fav is None else (fav and psp),
            # None untuk yang TIDAK favourable, jadi mereka keluar dari
            # perbandingan alih-alih masuk lengan bawah. Itu yang membuat H5
            # menanyakan "PSP menambah di atas posisi" dan bukan "posisi plus
            # PSP mengalahkan segalanya".
            "psp_given_fav": psp if fav else None,
        })
    return out


def _walk_forward(rows: list[dict], key: str) -> dict:
    """Delta antar lengan di `FOLDS` potongan waktu yang sama panjang."""
    usable = [r for r in rows if r[key] is not None]
    if not usable:
        return {"folds": 0, "same_sign": 0, "deltas": []}
    order = sorted(usable, key=lambda r: r["at"])
    size = max(1, len(order) // FOLDS)
    deltas: list[float] = []
    for f in range(FOLDS):
        chunk = order[f * size:(f + 1) * size] if f < FOLDS - 1 else order[f * size:]
        a = [r["r"] for r in chunk if r[key]]
        b = [r["r"] for r in chunk if not r[key]]
        deltas.append(float(np.mean(a) - np.mean(b)) if a and b else float("nan"))
    good = [d for d in deltas if not np.isnan(d)]
    if not good:
        return {"folds": 0, "same_sign": 0, "deltas": deltas}
    sign = 1 if float(np.nanmean(deltas)) >= 0 else -1
    same = sum(1 for d in good if (d >= 0) == (sign > 0))
    return {"folds": len(good), "same_sign": same, "deltas": deltas}


def _judge(rows: list[dict], key: str, predicted: str, crit: float) -> dict:
    usable = [r for r in rows if r[key] is not None]
    a = np.array([r["r"] for r in usable if r[key]])
    b = np.array([r["r"] for r in usable if not r[key]])
    res: dict = {
        "predicted": predicted,
        "n_true": int(len(a)), "n_false": int(len(b)),
        "dropped_unmeasurable": int(len(rows) - len(usable)),
        "exp_r_true": float(a.mean()) if len(a) else None,
        "exp_r_false": float(b.mean()) if len(b) else None,
    }
    if len(a) < 2 or len(b) < 2:
        res["verdict"] = "degenerat: satu lengan kosong"
        return res
    total = len(a) + len(b)
    delta = float(a.mean() - b.mean())
    t = _welch(a, b)
    half = len(usable) // 2
    order = sorted(usable, key=lambda r: r["at"])
    halves = []
    for chunk in (order[:half], order[half:]):
        x = [r["r"] for r in chunk if r[key]]
        y = [r["r"] for r in chunk if not r[key]]
        halves.append(float(np.mean(x) - np.mean(y)) if x and y else float("nan"))
    wf = _walk_forward(rows, key)
    # TANDA ANTAR INSTRUMEN, konvensi yang dipakai `conditioned_structure.py`
    # dan tidak ada di versi pertama file ini. Walk-forward menguji stabilitas
    # LINTAS WAKTU; ini mengujinya lintas PASAR, dan sebuah pengkondisi yang
    # tandanya berbalik antar instrumen tidak bisa disebut sifat FVG.
    cells: dict[str, float] = {}
    for cell in sorted({r["cell"] for r in usable}):
        chunk = [r for r in usable if r["cell"] == cell]
        x = [r["r"] for r in chunk if r[key]]
        y = [r["r"] for r in chunk if not r[key]]
        if x and y:
            cells[cell] = float(np.mean(x) - np.mean(y))
    same = sum(1 for v in cells.values() if (v >= 0) == (delta >= 0))
    res.update({
        "per_cell_delta": cells,
        "cells_same_sign": f"{same}/{len(cells)}",
        "delta": delta, "welch_t": t, "critical_t": crit,
        "halves_delta": halves,
        "halves_same_sign": bool(
            not any(np.isnan(halves)) and (halves[0] >= 0) == (halves[1] >= 0)
        ),
        "walk_forward": wf,
        "degenerate": (max(len(a), len(b)) / total) > 0.95,
    })
    res["separates"] = bool(
        min(len(a), len(b)) >= MIN_GROUP
        and abs(t) >= crit
        and res["halves_same_sign"]
        and wf["same_sign"] >= 7
        and same >= len(cells) - 1
        and not res["degenerate"]
    )
    return res


def study(symbols: list[str], interval: str) -> dict:
    rows: list[dict] = []
    per_cell: dict[str, dict] = {}
    for symbol in symbols:
        try:
            got = _cell_rows(symbol, interval)
        except Exception as exc:  # noqa: BLE001 - dilaporkan per sel
            per_cell[f"{symbol} {interval}"] = {"error": str(exc)}
            continue
        rows += got
        per_cell[f"{symbol} {interval}"] = {"n": len(got)}
        print(f"  {symbol}: {len(got)} trade", file=sys.stderr)
    if not rows:
        return {"error": "populasi kosong", "cells": per_cell}

    crit = _critical_t(K)
    keys = (
        ("favourable_side", "lebih tinggi"),
        ("psp_before_touch", "lebih tinggi"),
        ("purge_before_touch", "lebih tinggi"),
        ("fav_and_psp", "lebih tinggi"),
        ("psp_given_fav", "lebih tinggi"),
    )
    results = {k: _judge(rows, k, pred, crit) for k, pred in keys}
    separating = [k for k, v in results.items() if v.get("separates")]
    return {
        "preregistered": "tools/fvg_conditioners.py, 2026-09-08",
        "question": "apakah posisi premium/discount, PSP, atau sapuan likuiditas "
                    "mengkondisikan resolved R sebuah FVG",
        "rig": "tools.detectors_costed.resolved_as(fvg), bar halus, biaya",
        "threshold": {
            "groups_judged": K, "critical_t": crit, "min_group": MIN_GROUP,
            "requires": ["n>=30 kedua lengan", "|t| Welch >= critical_t",
                         "tanda sama di kedua paruh",
                         "walk-forward >= 7 dari 8",
                         "tanda sama di >= n-1 instrumen"],
        },
        "cells": per_cell,
        "population": {"n": len(rows)},
        "results": results,
        "separating": separating,
        "verdict": "MEMISAHKAN: " + ", ".join(separating) if separating
        else f"NULL: tidak satu pun dari {len(results)} lengan memisahkan",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, args.interval)
    json.dump(out, sys.stdout, indent=2, default=float)
    print()
    return 0 if "error" not in out else 1


def _selftest() -> None:
    """Lengan yang tidak bisa diukur DIBUANG, bukan dihitung sebagai False.

    Itu satu-satunya keputusan di berkas ini yang bisa diam-diam salah:
    memperlakukan `dealing_range_pos is None` sebagai "tidak favourable" akan
    mencampur dua hal berbeda dan menggeser delta ke arah yang tidak diukur.
    """
    rows = [
        {"r": 1.0, "at": 1, "favourable_side": True},
        {"r": -1.0, "at": 2, "favourable_side": False},
        {"r": 5.0, "at": 3, "favourable_side": None},
    ]
    usable = [r for r in rows if r["favourable_side"] is not None]
    assert len(usable) == 2, usable
    a = [r["r"] for r in usable if r["favourable_side"]]
    b = [r["r"] for r in usable if not r["favourable_side"]]
    assert a == [1.0] and b == [-1.0]
    # Kalau None dihitung sebagai False, lengan bawah jadi [-1, 5] dan
    # deltanya berbalik tanda. Itu yang dicegah.
    wrong_b = [r["r"] for r in rows if not r["favourable_side"]]
    assert wrong_b == [-1.0, 5.0]
    assert (a[0] - sum(b) / len(b)) > 0 > (a[0] - sum(wrong_b) / len(wrong_b))


if __name__ == "__main__":
    raise SystemExit(main())
