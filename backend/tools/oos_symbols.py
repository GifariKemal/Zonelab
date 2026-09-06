"""Kontrol out-of-sample: instrumen yang TIDAK ikut memilih sebuah aturan.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.oos_symbols

KENAPA BERKAS INI ADA. Rig 12 sel di seluruh `docs/QA-*-GATE.md` memakai dua
instrumen, XAUUSD dan BTCUSD. Setiap kali sebuah timeframe atau sebuah aturan
dipilih karena angkanya terbaik DI SANA, angka itu memuat seleksi, dan tidak ada
cara memisahkannya dengan menghitung ulang di dua instrumen yang sama.

Enam instrumen di bawah punya riwayat 15m DAN 1m di venue yang sama, jadi mereka
bisa diadili di resolusi halus persis seperti rig utamanya, dan tidak satu pun
pernah ikut memilih apa pun.

APA YANG IA JAWAB, dijalankan 6 September 2026 untuk lengan L di 15m. Lengan itu
dipilih karena PF 1,377 di 15m, tertinggi di seluruh sapuan S&D. Kontrol
pemilihan lebih dulu menunjukkan angka itu paling ter-inflasi dari delapan
lengan: PF gabungannya 1,131, dan mengambil timeframe terbaik menaikkan SETIAP
lengan, dengan median terbaik-dari-6 sebesar 1,178. Lalu berkas ini menjawabnya:

    K produksi           n= 979  exp_r -0,0830  PF 0,855  t -1,899  wf 1/8
    L K + proximal body  n=1211  exp_r -0,0433  PF 0,929  t -0,954  wf 3/8

Keduanya RUGI di luar sampel. Edge 15m itu tidak berpindah, dan ia bahkan tidak
merata di dalam sampelnya: BTCUSD 15m memberi PF 1,578 sementara XAUUSD 15m
memberi 1,189 dengan t 0,973.

Angka produksi ikut jatuh, dan itu temuan tersendiri: K di 15m adalah +0,0672 di
rig dan -0,0830 di enam instrumen ini.

BATASNYA. Riwayat 1m di terminal ini kira kira 69 hari, jadi tiap sel di sini
jauh lebih pendek daripada sel rig dan n-nya 140 sampai 232 per instrumen.
Cukup untuk menolak sebuah klaim, tidak cukup untuk menegakkan yang baru.
"""
from __future__ import annotations

import contextlib
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect.supply_demand import detect as detect_sd
from app.models import SupplyDemandParams
from tools.calibrate import POPULATION
from tools.detectors_costed import FOLDS, one_sample_t
from tools.gate_sweep import cell_rows as _cell_rows

#: ETHUSD DIBUANG, DAN BUKAN KARENA HASILNYA TIDAK DISUKAI. Ia tidak ada di
#: `BROKERS["exness_raw"]`, jadi `schedule()` jatuh ke default generik ala bursa
#: kripto: `commission_bp` 20,0 dan `slippage_bp` 2,0, lawan 0,15 sampai 1,31 dan
#: 0,5 di ketujuh instrumen lain. Dua puluh dua kali lipat BTCUSD.
#:
#: Yang mengungkapkannya: ETHUSD adalah instrumen paling negatif untuk KEEMPAT
#: detector sekaligus (-0,3942 ifvg, -0,3834 order_block, -0,3113 breaker,
#: -0,2903 S&D lengan L). Empat metode yang berbeda tidak gagal dengan pola yang
#: sama karena alasan yang sama kecuali penyebabnya bukan metodenya.
#:
#: Terminal MEMBAWA simbolnya - `history.load("mt5:ETHUSD", ...)` menjawab
#: 99.998 bar - jadi ini celah di tabel biaya, bukan instrumen yang tidak ada.
#: Sampai barisnya diturunkan dari terminal, ETHUSD tidak bisa diukur di sini.
OOS = ("EURUSD", "GBPJPY", "USDJPY", "XAGUSD", "US30")
ARMS = {
    "K produksi": {"departure_min_atr": 2.0},
    "L K + proximal body": {"departure_min_atr": 2.0, "proximal_basis": "body"},
}
#: Detector lain diuji APA ADANYA. `_cell_rows` memanggil `_params(name)` untuk
#: mereka, yang berarti default `ImbalanceParams` penuh, yang berarti produksi.
#: Tidak ada penukaran DETECTORS yang perlu dilakukan, dan itu sebabnya angka
#: mereka bisa langsung dibandingkan dengan `docs/QA-*-GATE.md`.
OTHERS = ("ifvg", "breaker", "order_block")
MIN_FOLD = 20
#: Timeframe yang diuji. 15m karena itu yang dipertanyakan, dan karena ia satu
#: satunya yang riwayat 1m-nya cukup untuk mengadili keenam instrumen.
TF = "15m"


def rates(rows: list[dict]) -> dict:
    r = np.array([x["r"] for x in rows])
    if not r.size:
        return {"n": 0}
    w, l = r[r > 0], r[r <= 0]
    gl = float(abs(l.sum()))
    return {
        "n": int(r.size),
        "exp_r": round(float(r.mean()), 4),
        "wr": round(float(w.size / r.size), 4),
        "pf": round(float(w.sum()) / gl, 3) if gl else None,
        "t": round(one_sample_t(r), 3) if r.size > 1 else None,
    }


def wf(rows: list[dict]) -> tuple[int, int]:
    e = np.linspace(0, 1, FOLDS + 1)
    g = p = 0
    for k in range(FOLDS):
        lo, hi = float(e[k]), float(e[k + 1])
        kept = np.array([x["r"] for x in rows if lo <= x["pos"] < hi and x["exit_pos"] < hi])
        if kept.size >= MIN_FOLD:
            g += 1
            p += 1 if kept.mean() > 0 else 0
    return p, g


def main() -> int:
    out: dict[str, list[dict]] = {name: [] for name in ARMS}
    for name, extra in ARMS.items():
        params = SupplyDemandParams(**{**POPULATION, **extra})
        original = DETECTORS["supply_demand"]
        DETECTORS["supply_demand"] = lambda c, _i, p=params: detect_sd(c, p)
        try:
            for sym in OOS:
                try:
                    with contextlib.redirect_stdout(sys.stderr):
                        rows, _span = _cell_rows("supply_demand", sym, TF)
                except Exception as exc:  # noqa: BLE001
                    print(f"  {name:22} {sym:8} GAGAL {exc}", file=sys.stderr)
                    continue
                r = rates(rows)
                pw, gw = wf(rows)
                print(f"  {name:22} {sym:8} n={r.get('n'):>5} exp_r={r.get('exp_r')} "
                      f"PF={r.get('pf')} t={r.get('t')} wf={pw}/{gw}", file=sys.stderr, flush=True)
                out[name].extend(rows)
        finally:
            DETECTORS["supply_demand"] = original

    # DETECTOR LAIN, pertanyaan yang sama. Kalau mereka juga jatuh di luar
    # sampel maka yang optimis adalah RIG-nya, bukan supply and demand.
    for name in OTHERS:
        acc: list[dict] = []
        for sym in OOS:
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    rows, _span = _cell_rows(name, sym, TF)
            except Exception as exc:  # noqa: BLE001
                print(f"  {name:22} {sym:8} GAGAL {exc}", file=sys.stderr)
                continue
            acc.extend(rows)
            r = rates(rows)
            print(f"  {name:22} {sym:8} n={r.get('n'):>5} exp_r={r.get('exp_r')} "
                  f"PF={r.get('pf')} t={r.get('t')}", file=sys.stderr, flush=True)
        out[name] = acc

    print()
    print("Instrumen ini tidak ikut memilih apa pun. Bandingkan dengan angka")
    print("rig di docs/QA-SD-GATE.md, bukan dengan harapan.")
    print()
    print(f"{'lengan':22} {'n':>6} {'exp_r':>8} {'WR':>7} {'PF':>6} {'t':>7} {'wf':>6}")
    for name, rows in out.items():
        if not rows:
            print(f"{name:22} kosong")
            continue
        r = rates(rows)
        pw, gw = wf(rows)
        print(f"{name:22} {r['n']:>6} {r['exp_r']:>8} {r['wr']:>7} {r['pf']:>6} "
              f"{r['t']:>7} {pw}/{gw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
