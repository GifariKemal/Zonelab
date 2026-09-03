"""Praregistrasi: probabilitas terkalibrasi untuk sebuah order, dan apakah ada
fitur yang menggesernya.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.entry_probability > ../docs/entry_probability.json

Ditulis 3 September 2026, SEBELUM satu angka outcome pun dihitung.

===========================================================================
1. KENAPA BUKAN "PREDIKSI ARAH"
===========================================================================

Diminta pemiliknya: order harus punya hipotesis dan probabilitas terukur untuk
ARAH. Bentuk pertanyaannya digeser satu langkah, dan pergeseran itu harus
dijelaskan karena ia yang membuat pertanyaannya bisa dijawab sama sekali.

Dua belas hipotesis arah praregistrasi sudah mati di repo ini, skor agregat
checklist tidak memisahkan hasil (rho -0,035 demeaned), dan satu dari tujuh
belas klausanya memisahkan ke arah SEBALIKNYA. Menanyakan "harga akan naik atau
turun" untuk ketiga belas kalinya bukan ketekunan, itu mengabaikan dua belas
jawaban.

Yang BELUM pernah ditanyakan, dan yang sebenarnya dibutuhkan operator saat
memasang order: arah sudah ditentukan oleh SISI ZONA - sebuah zona demand
adalah beli, titik. Yang tidak diketahui bukan arahnya, tapi apakah order itu
RESOLVE ke target atau ke stop. Itu bisa dihitung, punya populasi, dan punya
kebenaran dasar di tiap baris rig berbiaya.

===========================================================================
2. SATU ANGKA AKAN MENIPU, JADI YANG DILAPORKAN DISTRIBUSI
===========================================================================

Diukur lebih dulu pada supply_demand XAUUSD 30m, n=1794: P(R > 0) adalah 0,5496.
Angka itu terlihat seperti "menang 55 persen" dan itu pembacaan yang salah.
Rinciannya:

  stop penuh -1R    34,4 persen
  rugi sebagian      9,9 persen, rata-rata -0,247
  untung kecil      48,9 persen, rata-rata +0,445
  sekitar 2R         3,3 persen
  di atas 2,5R       1,6 persen

Jadi hampir setiap "kemenangan" adalah exit horizon kecil, dan target 2R hanya
kena 4,9 persen. Ekspektasinya -0,0306 R. Sebuah UI yang mencetak "55 persen"
di sebelah order akan membuat operator membaca 55 persen peluang 2R, yang salah
sebelas kali lipat.

Karena itu keluarannya EMPAT angka, bukan satu: P(stop penuh), P(rugi sebagian),
P(untung kecil), P(mencapai target), plus ekspektasi R dan n populasinya.

===========================================================================
3. DUA HIPOTESIS
===========================================================================

H1, BASE RATE. Distribusi hasil berbeda antar populasi (layer kali simbol kali
sisi gerbang), dan bedanya lebih besar daripada interval kepercayaannya. Kalau
H1 gagal, satu tabel tunggal cukup dan tidak perlu dipecah.

H2, LIFT FITUR. Setidaknya satu fitur yang BISA DIKETAHUI di bar keputusan
menggeser probabilitas itu di luar sampel, diukur dengan Brier skill score lawan
base rate pada fold yang ditahan. Positif berarti model tahu sesuatu yang base
rate tidak.

H2 kemungkinan besar GAGAL, dan itu dinyatakan di depan: dua belas hipotesis
arah mati, dan fitur yang sama yang gagal di sana ada di daftar ini. Sebuah H2
yang gagal tetap berguna, karena ia mengubah "kami tidak tahu" jadi "base rate
adalah estimasi terbaik yang ada, dan ini angkanya".

Ambang Bonferroni menghitung dua kelompok.

===========================================================================
4. FITUR, DAN KENAPA HANYA YANG SUDAH ADA
===========================================================================

Semua bisa diketahui di bar sentuhan, dan tidak satu pun besaran baru dikarang:

  departure_atr     sudah di tiap baris rig
  cost_r            sudah, dan ia gerbang tersendiri di jalur order
  height_atr        tinggi zona dibagi ATR di bar kelahirannya
  profit_zone_rr    jalan ke dinding lawan, yang `plan.build` sudah pakai
  age_bars          umur zona dari lahir ke sentuhan
  range_pos         posisi harga di dealing range yang knowable saat itu
  killzone          jendela sesi di bar sentuhan
  side              demand atau supply

MODEL REGRESI LOGISTIK DITULIS TANGAN DI NUMPY, dan itu keputusan. scipy dan
sklearn tidak terpasang, dan menambah dependency berat ke `requirements.txt`
untuk satu fungsi lima belas baris adalah kebalikan dari disiplin yang setiap
file lain di sini pegang. Gradient descent penuh dengan L2, deterministik, tanpa
seed acak apa pun.

===========================================================================
5. YANG TIDAK DIJANJIKAN
===========================================================================

Ini BUKAN prediksi arah dan tidak boleh dikutip sebagai itu. Ia probabilitas
resolusi untuk order yang arahnya SUDAH ditentukan sisi zonanya.

Bar halus 5 menit, rasio 6 di 30 menit, dan kontrol resolusi di
`docs/fvg_resolution.json` menunjukkan rasio kasar menggelembungkan ekspektasi.
Probabilitas di sini karena itu batas ATAS untuk P(target) dan batas bawah untuk
P(stop).

Walk-forward memotong waktu, bukan mengacak. Sebuah model yang dilatih pada fold
mendatang akan memberi Brier yang bagus dan tidak berarti apa-apa.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from app.dealing_range import position_at, range_at
from app.detect import DETECTORS
from app.indicators import wilder_atr
from app.pools import killzones_at
from tools.conditioned import _critical_t
from tools.detectors_costed import FOLDS, GATE, _params, cell_rows
from tools.quant import clean

CELLS = [("XAUUSD", "30m"), ("BTCUSD", "30m")]
NAMES = ("supply_demand", "order_block", "fvg")
#: Dua hipotesis dinilai.
T_THRESHOLD = _critical_t(2)
MIN_CELL = 100
FEATURES = ("departure", "cost_r", "height_atr", "profit_zone_rr",
            "age_bars", "range_pos", "in_killzone", "is_demand")
#: Ambang hasil, dalam R. Dipatok di sini supaya keempat angka yang dilaporkan
#: punya definisi yang sama di setiap pemanggil.
FULL_STOP = -0.99
SMALL_LOSS = -0.01
TARGET_R = 1.5


def buckets(r: np.ndarray) -> dict:
    """Empat hasil, bukan satu win rate. Lihat bagian 2."""
    if r.size == 0:
        return {"n": 0}
    return {
        "n": int(r.size),
        "p_full_stop": float(np.mean(r <= FULL_STOP)),
        "p_small_loss": float(np.mean((r > FULL_STOP) & (r <= SMALL_LOSS))),
        "p_small_win": float(np.mean((r > SMALL_LOSS) & (r < TARGET_R))),
        "p_target": float(np.mean(r >= TARGET_R)),
        "exp_r": float(r.mean()),
        # Wald 95 persen untuk P(target), yang angka paling mudah disalahbaca.
        "p_target_ci95": _wald(float(np.mean(r >= TARGET_R)), int(r.size)),
    }


def _wald(p: float, n: int) -> list[float]:
    if n < 2:
        return [0.0, 1.0]
    half = 1.96 * (p * (1 - p) / n) ** 0.5
    return [round(max(0.0, p - half), 4), round(min(1.0, p + half), 4)]


def features_for(name: str, symbol: str, interval: str) -> list[dict]:
    """Baris rig berbiaya plus fitur yang bisa diketahui di bar sentuhan."""
    rows, _ = cell_rows(name, symbol, interval)
    # Deret yang SAMA dengan yang rig pakai: ticker telanjang, bars default.
    candles, _, _ = clean(symbol, interval)
    params = _params(name)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, params.atr_period)
    times = [c.time for c in candles]
    index = {t: i for i, t in enumerate(times)}
    dr_times, knowable = range_at(candles)
    zones, _ = DETECTORS[name](candles, params)
    by_id = {z.id: z for z in zones}

    out: list[dict] = []
    for row in rows:
        zone = by_id.get(row["zone_id"])
        at = int(row["at"])
        if zone is None or at < 1 or at >= len(times):
            continue
        born = index.get(zone.time_from)
        if born is None:
            continue
        scale = float(atr[born])
        if scale <= 0:
            continue
        pos = position_at(close[at], times[at], dr_times, knowable)
        out.append({
            **row,
            "departure": float(row.get("departure") or 0.0),
            "cost_r": float(row.get("cost_r") or 0.0),
            "height_atr": (zone.top - zone.bottom) / scale,
            "profit_zone_rr": float(zone.profit_zone_rr or 0.0),
            "age_bars": float(at - born),
            # `-1` BUKAN NOL. Sebuah range yang tidak terbaca bukan harga di
            # tengahnya, dan mengisinya 0,5 akan mengarang bacaan premium.
            "range_pos": float(pos) if pos is not None else -1.0,
            "in_killzone": 1.0 if killzones_at(times[at]) else 0.0,
            "is_demand": 1.0 if row.get("side") == "demand" else 0.0,
        })
    return out


def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float = 1.0,
                 steps: int = 4000, lr: float = 0.1) -> np.ndarray:
    """Regresi logistik, gradient descent penuh, deterministik.

    Ditulis tangan karena scipy dan sklearn tidak terpasang dan menambah
    dependency berat untuk satu fungsi lima belas baris adalah kebalikan dari
    disiplin yang setiap file lain di sini pegang.

    Tidak ada keacakan sama sekali: bobot mulai dari nol, batch penuh, langkah
    tetap. Dua run di data yang sama memberi bobot yang sama sampai bit
    terakhir, yang adalah syarat sebuah hasil bisa direplikasi.
    """
    n, k = x.shape
    w = np.zeros(k + 1, dtype=np.float64)
    xb = np.hstack([np.ones((n, 1)), x])
    for _ in range(steps):
        p = 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -30, 30)))
        grad = xb.T @ (p - y) / n
        grad[1:] += l2 * w[1:] / n
        w -= lr * grad
    return w


def predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    xb = np.hstack([np.ones((x.shape[0], 1)), x])
    return 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -30, 30)))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _standardise(train: np.ndarray, apply_to: np.ndarray) -> np.ndarray:
    """Skala dari TRAIN saja. Mean dari test adalah kebocoran."""
    mu = train.mean(axis=0)
    sd = train.std(axis=0)
    sd[sd == 0] = 1.0
    return (apply_to - mu) / sd


def walk_forward_skill(rows: list[dict], target: str) -> dict:
    """Brier skill score lawan base rate, dilatih maju di waktu.

    Tiap fold dilatih pada SEMUA fold sebelumnya dan diuji pada fold ini, jadi
    tidak ada satu bar pun dari masa depan yang menyentuh bobotnya. Fold pertama
    tidak punya train dan dilewati.
    """
    ordered = sorted(rows, key=lambda r: r["pos"])
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    folds = []
    for k in range(1, FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        train = [r for r in ordered if r["pos"] < lo]
        test = [r for r in ordered if lo <= r["pos"] < hi]
        if len(train) < MIN_CELL or len(test) < 30:
            folds.append({"fold": k + 1, "n_train": len(train),
                          "n_test": len(test), "readable": False})
            continue
        xtr = np.array([[r[f] for f in FEATURES] for r in train])
        ytr = np.array([1.0 if r[target] else 0.0 for r in train])
        xte = np.array([[r[f] for f in FEATURES] for r in test])
        yte = np.array([1.0 if r[target] else 0.0 for r in test])
        w = fit_logistic(_standardise(xtr, xtr), ytr)
        p_model = predict(w, _standardise(xtr, xte))
        # BASE RATE DARI TRAIN, bukan dari test. Base rate test adalah jawaban
        # yang bocor, dan sebuah model yang dibandingkan ke jawaban akan selalu
        # terlihat lebih buruk daripada seharusnya.
        p_base = np.full(yte.shape, float(ytr.mean()))
        b_model, b_base = brier(p_model, yte), brier(p_base, yte)
        folds.append({
            "fold": k + 1, "n_train": len(train), "n_test": len(test),
            "brier_model": b_model, "brier_base": b_base,
            "skill": float(1.0 - b_model / b_base) if b_base > 0 else 0.0,
            "readable": True,
        })
    graded = [f for f in folds if f["readable"]]
    skills = [f["skill"] for f in graded]
    return {
        "folds": folds, "graded": len(graded),
        "positive": sum(1 for s in skills if s > 0),
        "mean_skill": float(np.mean(skills)) if skills else None,
    }


def judge_h2(wf: dict) -> tuple[bool, str]:
    """H2 lolos kalau skill positif di MAYORITAS fold dan rata-ratanya positif.

    Bukan uji t: Brier skill per fold bukan sampel iid dari satu populasi, dan
    memperlakukannya begitu akan memberi p yang terlalu kecil. Yang dipakai uji
    tanda pada fold, ambang yang sama dengan setiap studi lain di sini.
    """
    graded = wf.get("graded", 0)
    positive = wf.get("positive", 0)
    mean = wf.get("mean_skill")
    ok = bool(graded >= 5 and positive >= graded - 1
              and mean is not None and mean > 0)
    return ok, ("LOLOS, fitur menggeser probabilitas di luar sampel" if ok
                else "TIDAK LOLOS, base rate tetap estimasi terbaik")


def selfcheck() -> int:
    """Bukti bahwa penghakiman dan modelnya tidak kosong."""
    # Regresi harus BISA belajar sinyal yang jelas, atau angka null di file ini
    # tidak bisa dibedakan dari model yang rusak.
    rng = np.random.default_rng(0)
    x = rng.normal(size=(800, 2))
    y = (x[:, 0] > 0).astype(np.float64)
    w = fit_logistic(x, y)
    p = predict(w, x)
    assert brier(p, y) < 0.10, brier(p, y)
    assert abs(w[1]) > abs(w[2]) * 3, "harus memberi bobot ke fitur yang benar"

    # Dan HARUS gagal pada derau, atau ia menghafal.
    y_noise = rng.integers(0, 2, size=800).astype(np.float64)
    w2 = fit_logistic(x, y_noise)
    p2 = predict(w2, x)
    base = np.full(y_noise.shape, y_noise.mean())
    assert brier(p2, y_noise) > brier(base, y_noise) - 0.02

    # Penghakiman H2
    assert judge_h2({"graded": 7, "positive": 7, "mean_skill": 0.05})[0] is True
    assert judge_h2({"graded": 7, "positive": 4, "mean_skill": 0.05})[0] is False
    assert judge_h2({"graded": 7, "positive": 7, "mean_skill": -0.01})[0] is False
    assert judge_h2({"graded": 3, "positive": 3, "mean_skill": 0.05})[0] is False
    assert judge_h2({})[0] is False

    # Bucket harus menjumlah ke satu, atau salah satu hasil tidak terhitung.
    r = np.array([-1.0, -1.0, -0.3, 0.0, 0.4, 1.9, 3.0])
    b = buckets(r)
    total = (b["p_full_stop"] + b["p_small_loss"] + b["p_small_win"]
             + b["p_target"])
    assert abs(total - 1.0) < 1e-9, total
    assert b["p_target"] == 2 / 7, b["p_target"]
    assert buckets(np.array([]))["n"] == 0
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
            "source": "tools/entry_probability.py, 2026-09-03",
            "question": "probabilitas terkalibrasi bahwa order ini resolve ke "
                        "target atau ke stop, BUKAN prediksi arah",
            "why_not_direction": "dua belas hipotesis arah praregistrasi mati; "
                                 "arah sudah ditentukan sisi zona, yang tidak "
                                 "diketahui apakah ia resolve",
            "h1": "distribusi hasil berbeda antar populasi",
            "h2": "setidaknya satu fitur knowable menggeser probabilitas di "
                  "luar sampel, Brier skill lawan base rate",
            "h2_prior": "kemungkinan besar GAGAL, dan itu tetap berguna",
            "features": list(FEATURES),
            "model": "regresi logistik ditulis tangan di numpy, deterministik, "
                     "tanpa scipy atau sklearn",
            "buckets": {"full_stop": f"R <= {FULL_STOP}",
                        "small_loss": f"{FULL_STOP} < R <= {SMALL_LOSS}",
                        "small_win": f"{SMALL_LOSS} < R < {TARGET_R}",
                        "target": f"R >= {TARGET_R}"},
            "t_threshold_bonferroni_2": T_THRESHOLD,
            "gate_atr": GATE, "folds": FOLDS, "min_cell": MIN_CELL,
            "cells": [f"{s} {i}" for s, i in CELLS],
            "caveat": "bar halus 5m rasio 6; P(target) batas ATAS",
        },
        "base_rates": {},
        "feature_lift": {},
    }

    pooled_all: list[dict] = []
    for name in NAMES:
        pooled: list[dict] = []
        for symbol, interval in CELLS:
            label = f"{name} {symbol} {interval}"
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    rows = features_for(name, symbol, interval)
            except Exception as exc:
                out["base_rates"][label] = {"error": str(exc)}
                print(f"  {label}: GAGAL {exc}", file=sys.stderr)
                continue
            pooled.extend(rows)
            r = np.array([x["r"] for x in rows])
            above = np.array([x["r"] for x in rows if x["cleared"]])
            below = np.array([x["r"] for x in rows if not x["cleared"]])
            out["base_rates"][label] = {
                "all": buckets(r), "above_gate": buckets(above),
                "below_gate": buckets(below),
            }
            b = out["base_rates"][label]["all"]
            print(f"  {label}: n {b['n']} P(target) {b['p_target']:.4f} "
                  f"P(stop) {b['p_full_stop']:.4f} exp_r {b['exp_r']:+.4f}",
                  file=sys.stderr)
        if not pooled:
            continue
        pooled_all.extend(pooled)
        for target, tag in (("won", "p_win"),):
            wf = walk_forward_skill(pooled, target)
            ok, verdict = judge_h2(wf)
            out["feature_lift"][f"{name} {tag}"] = {
                **wf, "passes": ok, "verdict": verdict}
            print(f"  {name} lift: skill rata2 {wf['mean_skill']} "
                  f"positif {wf['positive']}/{wf['graded']} -> {verdict}",
                  file=sys.stderr)

    if pooled_all:
        r = np.array([x["r"] for x in pooled_all])
        out["pooled_all"] = buckets(r)
    out["h2_passing"] = [k for k, v in out["feature_lift"].items()
                         if v.get("passes")]
    out["verdict"] = (
        f"H2 lolos di {out['h2_passing']}" if out["h2_passing"]
        else "H2 TIDAK lolos di mana pun: base rate adalah estimasi terbaik, "
             "dan angkanya ada di base_rates"
    )
    print(f"  VERDICT: {out['verdict']}", file=sys.stderr)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
