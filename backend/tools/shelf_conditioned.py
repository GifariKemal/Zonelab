"""Praregistrasi: apakah zona yang duduk di shelf support/resistance lebih baik?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.shelf_conditioned > ../docs/shelf_conditioned.json

Ditulis 2 September 2026, SEBELUM satu angka outcome pun dihitung.

===========================================================================
1. SUPPORT DAN RESISTANCE SUDAH ADA DI SINI, DAN BELUM PERNAH DIUKUR
===========================================================================

Ditanya apakah Zonelab perlu support dan resistance. Ia sudah punya:
`app/liquidity.equal_levels` mengelompokkan swing SESISI yang harganya berada
dalam pita `tolerance_atr` dari anggota pertama, menuntut `min_touches`, dan
menghitung sentuhannya. Itu definisi S&R klasik, dengan nama ICT REQH dan REQL.

Tiga hal yang membuat pertanyaannya tetap terbuka:

  defaultnya MATI     `LiquidityParams.equal_levels` = false
  tidak pernah diukur ia muncul di empat dokumen `.md` dan di NOL file
                      `docs/*.json`, dan file JSON itu yang menyimpan hasil
  tidak terwire       layer `liquidity` tidak pernah menyentuh `tools/execute.py`

Jadi jawabannya bukan "belum ada", tapi "ada, mati, dan belum pernah diuji".

===========================================================================
2. DIUKUR SEBAGAI KONDISI, BUKAN SEBAGAI OBJEK BARU
===========================================================================

Sebuah level bukan zona, jadi ia tidak bisa langsung masuk rig R teresolusi
tanpa mengarang lebar band dan jarak stop. Mengarang dua angka untuk menguji
satu klaim adalah cara sebuah hasil jadi tidak berarti.

Yang ditanyakan karena itu: di antara trade yang SUDAH terukur, apakah zona yang
proximal-nya duduk di shelf resolve lebih baik daripada yang tidak. Nol parameter
baru, rig yang sama dengan setiap detector lain, dan hasilnya langsung bisa
dipakai: kalau memisahkan, ia jadi filter di jalur order untuk fvg dan
supply_demand yang sekarang memegang order hidup.

Bentuknya sama persis dengan `tools/csid_ob_intrabar.py`, yang menanyakan hal
setara untuk CISD di dalam order block dan menemukan pemisahan dengan TANDA
TERBALIK.

===========================================================================
3. DUA SISI, DAN KENAPA HIPOTESISNYA HARUS DUA ARAH
===========================================================================

Bacaan klasik: shelf low adalah support, jadi zona demand di atasnya lebih kuat.
Bacaan ICT: equal lows adalah LIKUIDITAS, stop yang menumpuk di bawahnya, jadi
harga menyapunya alih-alih memantul. Kedua bacaan itu memprediksi tanda yang
berlawanan dari kondisi yang sama, jadi hipotesisnya dua arah dan itu ditulis
sebelum angkanya ada.

PRIMER, sesisi: zona demand dengan shelf REQL di dalam band-nya, zona supply
dengan REQH. SEKUNDER dan cuma BACAAN: pasangan lawan sisi, dilaporkan tanpa
dinilai supaya jumlah kelompok tidak membengkak.

===========================================================================
4. SETELAN, DAN KENAPA MEMILIHNYA BUKAN P-HACKING
===========================================================================

Pada default yang dikapalkan, `swing_n=50`, `equal_levels` menghasilkan 21 shelf
di XAUUSD dan 35 di BTCUSD sepanjang 50.000 bar 30 menit. Mengkondisikan ~1.800
trade pada 21 shelf memberi segelintir kecocokan, dan sebuah null dari populasi
sekecil itu tidak mengatakan apa-apa tentang S&R, ia mengatakan sesuatu tentang
n.

Sensus lengkapnya dijalankan lebih dulu dan disimpan di output ini. Yang penting:
SENSUS ITU MENGHITUNG JUMLAH SHELF SAJA DAN TIDAK PERNAH MENYENTUH OUTCOME. Jadi
memilih setelan darinya adalah perencanaan daya, bukan pemilihan hasil, dan
perbedaan itu bisa diperiksa: tidak satu pun angka R dihitung sebelum
`SWING_N` di bawah ditetapkan.

Aturan pemilihannya ditulis di depan: setelan TERKASAR di sensus yang memberi
lebih dari 100 shelf per simbol. Itu `swing_n=10`, `min_touches=2`, yang memberi
313 dan 386. `min_touches` tetap 2, default fungsinya.

===========================================================================
5. ATURAN LOLOS
===========================================================================

Per detector: |Welch t| di atas ambang Bonferroni untuk DUA kelompok yang
dinilai, n minimal `MIN_GROUP` di kedua sisi, dan walk-forward minimal 7 dari 8
fold bertanda sama. Dua sisi, jadi selisih negatif yang signifikan juga
MEMISAHKAN, dan tandanya dilaporkan apa adanya.

===========================================================================
6. YANG TIDAK DIJANJIKAN
===========================================================================

Bar halus 30 menit adalah 5 menit, rasio 6, dan kontrol resolusi di
`docs/lowtf_resolution.json` serta `docs/fvg_resolution.json` menunjukkan rasio
kasar MENGGELEMBUNGKAN ekspektasi absolut. Studi ini membandingkan DUA KELOMPOK
yang keduanya diukur di resolusi yang sama, jadi penggelembungan itu sebagian
besar saling meniadakan di selisihnya, tapi angka absolut per kelompok tetap
batas atas.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from app.detect import DETECTORS
from app.liquidity import equal_levels
from app.models import ZoneSide
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, _params, cell_rows, welch
from tools.quant import clean

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
NAMES = ("supply_demand", "fvg")
#: Dua detector dinilai, jadi Bonferroni menghitung dua.
T_THRESHOLD = _critical_t(len(NAMES))
MIN_GROUP = 30
MIN_SIGN_FOLDS = 7
#: Dipilih dari sensus JUMLAH SHELF, sebelum satu angka R dihitung. Lihat
#: bagian 4: setelan terkasar yang memberi lebih dari 100 shelf per simbol.
SWING_N = 10
MIN_TOUCHES = 2


def census(candles: list) -> dict:
    """Jumlah shelf per setelan. TIDAK menyentuh outcome sama sekali."""
    out: dict = {}
    for n in (50, 20, 10, 5):
        lv = equal_levels(candles, swing_n=n, min_touches=MIN_TOUCHES)
        out[f"swing_n={n}"] = {
            "shelves": len(lv),
            "reqh": sum(1 for x in lv if x.name.startswith("REQH")),
            "reql": sum(1 for x in lv if x.name.startswith("REQL")),
            "untaken": sum(1 for x in lv if x.taken_at is None),
        }
    return out


def _on_shelf_at_birth(zone, levels, same_side: bool) -> bool:
    """Versi yang DIPATOK DI KELAHIRAN zona, dan kenapa versi pertama gugur.

    Definisi pertama di file ini mengevaluasi "belum diambil" di BAR SENTUHAN,
    dan itu nyaris tautologi: shelf-nya berada DI DALAM band zona, jadi harga
    yang datang menyentuh zona hampir selalu sudah menembus shelf-nya lebih
    dulu. Terurai per filter pada XAUUSD 30m, supply_demand: 4.951 zona punya
    shelf di dalam band, 3.413 setelah disamakan sisinya, 1.884 setelah syarat
    knowable, dan EMPAT BELAS setelah "belum diambil". Untuk fvg angka
    terakhirnya NOL dari 1.078, karena band FVG sempit sehingga menyentuh
    zonanya sama dengan mengambil shelf-nya.

    Populasi yang runtuh dari 1.078 ke nol karena satu syarat bukan temuan
    pasar, itu definisi yang memakan dirinya sendiri.

    Versi ini menanyakan yang doktrinnya maksud: apakah ADA S&R di harga ini
    ketika zonanya lahir. Keduanya dipatok di `zone.time_from`, jadi kondisinya
    tetap di kelahiran dan tidak bisa dicemari oleh sentuhan yang datang
    kemudian. Anti-lookahead-nya tetap utuh: `knowable_at <= time_from` berarti
    shelf itu sudah bisa digambar sebelum zonanya ada.
    """
    return _match(zone, levels, zone.time_from, same_side)


def _on_shelf(zone, levels, now: int, same_side: bool) -> bool:
    """Apakah band zona ini memuat shelf yang MASIH BERDIRI di `now`?

    Tiga syarat, dan ketiganya mengikat:

      di dalam band   `bottom <= price <= top`, jadi shelf itu benar-benar
                      berada di tempat zona ini akan diorder
      sudah diketahui `knowable_at <= now`, yang menjaga tidak ada lookahead:
                      sebuah shelf butuh `min_touches` konfirmasi dan yang
                      terakhir bisa jatuh SETELAH bar sentuhan
      belum diambil   `taken_at` kosong atau masih di depan `now`. Sebuah level
                      yang sudah ditembus bukan lagi support, dan menghitungnya
                      akan mencampur dua keadaan yang doktrinnya bedakan
    """
    return _match(zone, levels, now, same_side)


def _match(zone, levels, at: int, same_side: bool) -> bool:
    """Satu definisi kecocokan, dievaluasi di `at`. Dipakai kedua arm."""
    want_high = (zone.side is ZoneSide.SUPPLY) if same_side else (
        zone.side is ZoneSide.DEMAND)
    for level in levels:
        if level.name.startswith("REQH") is not want_high:
            continue
        if level.knowable_at > at:
            continue
        if level.taken_at is not None and level.taken_at <= at:
            continue
        if zone.bottom <= level.price <= zone.top:
            return True
    return False


def rows_for(name: str, symbol: str, interval: str) -> tuple[list[dict], dict]:
    rows, _ = cell_rows(name, symbol, interval)
    # DERET YANG SAMA PERSIS dengan yang `cell_rows` pakai, dan itu bukan detail.
    # `intrabar.resolved` memanggil `clean(symbol, interval, 99_999, "mt5")`
    # dengan ticker TELANJANG. Run pertama file ini memakai
    # `clean(f"mt5:{symbol}", interval, 50_000)`, dan deret yang lebih pendek
    # memberi zone id serta indeks `at` yang berbeda: BTCUSD mencocokkan NOL
    # dari baris-barisnya dan XAUUSD cuma 590 dari 1.793. Angka nol itu yang
    # membuatnya ketahuan, bukan review.
    candles, _, _ = clean(symbol, interval)
    times = [c.time for c in candles]
    levels = equal_levels(candles, swing_n=SWING_N, min_touches=MIN_TOUCHES)
    zones, _ = DETECTORS[name](candles, _params(name))
    by_id = {z.id: z for z in zones}

    out: list[dict] = []
    for row in rows:
        zone = by_id.get(row["zone_id"])
        at = int(row["at"])
        if zone is None or at < 1 or at >= len(times):
            continue
        now = times[at]
        out.append({
            **row,
            "on_shelf": _on_shelf_at_birth(zone, levels, True),
            "on_shelf_opposite": _on_shelf_at_birth(zone, levels, False),
            "on_shelf_at_touch": _on_shelf(zone, levels, now, True),
        })
    return out, {"shelves": len(levels), "n_rows": len(out),
                 "n_on_shelf_at_birth": sum(1 for r in out if r["on_shelf"]),
                 "n_on_shelf_opposite":
                     sum(1 for r in out if r["on_shelf_opposite"]),
                 "n_on_shelf_at_touch_degenerate":
                     sum(1 for r in out if r["on_shelf_at_touch"])}


def _walk(rows: list[dict], key: str) -> dict:
    """8 fold, selisih on-minus-off di tiap fold, digabung lewat `pos`."""
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    out = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = [r for r in opened if r["exit_pos"] < hi]
        on = [r["r"] for r in kept if r[key]]
        off = [r["r"] for r in kept if not r[key]]
        entry: dict = {"fold": k + 1, "n_on": len(on), "n_off": len(off),
                       "purged": len(opened) - len(kept)}
        if len(on) >= 20 and len(off) >= 20:
            entry["difference"] = float(np.mean(on) - np.mean(off))
            entry["readable"] = True
        else:
            entry["readable"] = False
        out.append(entry)
    graded = [e for e in out if e["readable"]]
    return {"folds": out, "graded": len(graded),
            "positive": sum(1 for e in graded if e["difference"] > 0)}


def judge(stats: dict, wf: dict) -> tuple[bool, str]:
    """Dua sisi: selisih negatif yang signifikan juga MEMISAHKAN."""
    raw = stats.get("welch_t")
    t = float(raw) if isinstance(raw, (int, float)) else float("nan")
    same = wf.get("positive", 0)
    graded = wf.get("graded", 0)
    ok = bool(t == t and abs(t) > T_THRESHOLD
              and stats.get("n_on", 0) >= MIN_GROUP
              and stats.get("n_off", 0) >= MIN_GROUP
              and graded >= FOLDS
              and max(same, graded - same) >= MIN_SIGN_FOLDS)
    if not ok:
        return False, "TIDAK MEMISAHKAN"
    arah = "lebih baik" if (stats.get("difference") or 0.0) > 0 else "lebih BURUK"
    return True, f"MEMISAHKAN, zona di shelf {arah}"


def summarise(rows: list[dict], key: str) -> dict:
    on = np.array([r["r"] for r in rows if r[key]])
    off = np.array([r["r"] for r in rows if not r[key]])
    out: dict = {"n_on": int(on.size), "n_off": int(off.size),
                 "exp_r_on": float(on.mean()) if on.size else None,
                 "exp_r_off": float(off.mean()) if off.size else None}
    if on.size > 1 and off.size > 1:
        out["difference"] = float(on.mean() - off.mean())
        out["welch_t"] = welch(on, off)
    return out


def selfcheck() -> int:
    wf_ok = {"graded": FOLDS, "positive": FOLDS}
    strong = {"welch_t": 6.0, "n_on": 100, "n_off": 100, "difference": 0.2}
    assert judge(strong, wf_ok)[0] is True
    # Dua sisi: tanda negatif yang kuat juga memisahkan, dan kalimatnya beda.
    neg = {**strong, "welch_t": -6.0, "difference": -0.2}
    ok, kalimat = judge(neg, {"graded": FOLDS, "positive": 0})
    assert ok is True and "lebih BURUK" in kalimat, kalimat
    assert judge({**strong, "welch_t": 1.9}, wf_ok)[0] is False
    assert judge({**strong, "n_on": 5}, wf_ok)[0] is False
    assert judge({**strong, "n_off": 5}, wf_ok)[0] is False
    assert judge(strong, {"graded": 4, "positive": 4})[0] is False
    assert judge(strong, {"graded": FOLDS, "positive": 4})[0] is False
    assert judge({**strong, "welch_t": float("nan")}, wf_ok)[0] is False
    assert judge({}, {})[0] is False
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()

    out: dict = {
        "preregistration": {
            "source": "tools/shelf_conditioned.py, 2026-09-02",
            "question": "apakah zona yang proximal-nya duduk di shelf "
                        "support/resistance resolve berbeda dari yang tidak",
            "two_sided": "bacaan klasik memprediksi lebih baik, bacaan ICT "
                         "memprediksi disapu; keduanya ditulis sebelum angkanya",
            "condition": "shelf di dalam band, knowable, dan belum diambil, "
                         "semuanya dievaluasi di KELAHIRAN zona",
            "why_not_at_touch": "versi bar-sentuhan nyaris tautologi karena "
                                "shelf-nya di dalam band: 1.078 ke NOL untuk "
                                "fvg XAUUSD setelah satu syarat. Dilaporkan "
                                "sebagai bacaan, tidak dinilai",
            "settings": {"swing_n": SWING_N, "min_touches": MIN_TOUCHES,
                         "chosen_from": "sensus JUMLAH shelf, tanpa outcome; "
                                        "terkasar yang memberi >100 per simbol"},
            "judged_groups": len(NAMES),
            "t_threshold_bonferroni": T_THRESHOLD,
            "min_group": MIN_GROUP, "folds": FOLDS,
            "min_sign_folds": MIN_SIGN_FOLDS,
            "cells": [f"{s} {i}" for s, i in CELLS],
            "secondary_not_judged": "pasangan lawan sisi, dilaporkan saja",
        },
        "census": {},
        "cells": {},
        "detectors": {},
    }

    with contextlib.redirect_stdout(sys.stderr):
        for symbol, interval in CELLS:
            candles, _, _ = clean(symbol, interval)
            out["census"][f"{symbol} {interval}"] = census(candles)
    print(f"  sensus: {json.dumps(out['census'])[:200]}", file=sys.stderr)

    for name in NAMES:
        pooled: list[dict] = []
        for symbol, interval in CELLS:
            label = f"{name} {symbol} {interval}"
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    rows, info = rows_for(name, symbol, interval)
            except Exception as exc:
                out["cells"][label] = {"error": str(exc)}
                print(f"  {label}: GAGAL {exc}", file=sys.stderr)
                continue
            out["cells"][label] = info
            pooled.extend(rows)
            print(f"  {label}: {info}", file=sys.stderr)
        if not pooled:
            out["detectors"][name] = {"verdict": "tidak ada baris"}
            continue
        stats = summarise(pooled, "on_shelf")
        wf = _walk(pooled, "on_shelf")
        ok, verdict = judge(stats, wf)
        out["detectors"][name] = {
            **stats, "walk_forward": wf, "separates": ok, "verdict": verdict,
            "reading_opposite_side": summarise(pooled, "on_shelf_opposite"),
            "reading_at_touch_degenerate": summarise(pooled, "on_shelf_at_touch"),
        }
        print(f"  {name}: on {stats.get('exp_r_on')} off {stats.get('exp_r_off')} "
              f"selisih {stats.get('difference')} welch {stats.get('welch_t')} "
              f"wf {wf['positive']}/{wf['graded']} -> {verdict}", file=sys.stderr)

    out["separating"] = [n for n, v in out["detectors"].items()
                         if v.get("separates")]
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
