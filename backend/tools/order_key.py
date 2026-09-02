"""Praregistrasi: kunci urut mana yang sebaiknya memilih dua order itu.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.order_key \
        > ../docs/order_key.json

Ditulis 2 September 2026, SEBELUM satu angka pun dihitung. Bagian 1 sampai 7 di
bawah ini adalah praregistrasinya; angkanya keluar di stdout sebagai JSON.

===========================================================================
1. PERTANYAANNYA, DAN KENAPA IA BELUM PERNAH DIJAWAB
===========================================================================

`tools/execute.py` mengurutkan kandidat di dua tempat, baris 395 dan 496, dan
di keduanya kunci utamanya `-Setup.met`, skor checklist ICT. `--max-orders`
default 2, jadi urutan itu MEMILIH dua kandidat mana yang benar-benar dikirim
saat lebih dari dua lolos gerbang.

Skor itu sudah diukur dan TIDAK memisahkan hasil. `docs/checklist_outcomes.json`
menilai 46 grup pada ambang Bonferroni t = 3,267 dan melaporkan
`H_A_met_score.separates: false`: Spearman rho -0,027 mentah dan -0,035 setelah
di-demean per instrumen, keduanya BERTANDA SALAH, median split +0,046 R pada
t = 0,839 dengan dua paruh yang berbeda tanda, dan 5 dari 8 fold positif.

Jadi kunci urut yang dipakai jalur order hari ini adalah besaran yang sudah
terbukti tidak berhubungan monoton dengan hasil. Yang BELUM pernah ditanyakan:
apakah ada besaran lain yang tersedia di bar keputusan yang berhubungan.

DAN INI BELUM PERNAH BISA TERLIHAT. Tidak satu pun rig pengukuran di repo ini
memperhitungkan `max_orders`: semuanya menghitung ekspektasi per trade dengan
asumsi SETIAP trade diambil. Di bawah asumsi itu urutan tidak punya arti sama
sekali, jadi tidak ada harness yang pernah punya alasan untuk melihatnya.

===========================================================================
2. POPULASI, dan kenapa ia dipinjam dan bukan dibangun ulang
===========================================================================

Populasinya `tools.checklist_outcomes.rows_for`, dipanggil apa adanya, dan
field kunci urutnya ditambahkan DI SANA dan bukan di sini.

Itu keputusan, bukan kemalasan. Definisi populasi tinggal di fungsi itu:
gerbang departure >= 2,0 ATR, resolusi 5 menit lewat `tools/intrabar.py`,
biaya `exness_raw`, sentuhan pertama yang `cleared`. Sebuah rig yang membangun
ulang populasinya sendiri untuk menguji kunci urut sedang menguji kunci urut
DAN populasi sekaligus, dan kalau angkanya nanti berbeda dari
`checklist_outcomes.json` tidak akan ada yang bisa mengatakan yang mana
penyebabnya.

| Hal | Nilai |
|---|---|
| Instrumen | `checklist_outcomes.SYMBOLS`, delapan, daftar tertutup |
| Timeframe | 1 jam, resolusi 5 menit |
| Outcome | R multiple setelah biaya, kolom `r` |
| Unit | satu trade |

===========================================================================
3. KUNCI YANG DIUJI, daftar tertutup
===========================================================================

Semuanya terbaca di bar keputusan, tidak satu pun memakai apa pun dari masa
depan. Semuanya ditulis supaya BESAR = DIURUTKAN LEBIH DULU, jadi tanda yang
diharapkan sama untuk semua dan tidak ada kunci yang dibalik setelah melihat
hasilnya.

| Kunci | Isinya | Kenapa masuk daftar |
|---|---|---|
| `k_met` | skor checklist | yang dipakai jalur order sekarang |
| `k_near_close` | `-abs(entry - close)` | tie-breaker kedua yang dipakai sekarang |
| `k_near_target` | `-abs(entry - target)` | tie-breaker di situs urut kedua, baris 496 |
| `k_reward_r` | R multiple ke target | geometri plan, tersedia gratis |
| `k_cheap` | `-cost_to_risk` | prior terkuat di repo ini, lihat bawah |
| `k_departure` | kekuatan kaki keluar zona | sudah jadi gerbang di 2,0, belum pernah jadi urutan |
| `k_random` | seeded per zona | KONTROL |

`k_cheap` masuk dengan prior yang paling kuat dan itu dinyatakan SEKARANG:
`tools/execute.py` mencatat korelasi -0,9879 dengan R kuadrat 0,976 antara
biaya-terhadap-risiko dan ekspektasi di 24 sel. Kalau ia menang, itu bukan
temuan baru melainkan konfirmasi bahwa besaran yang sudah dipakai sebagai
GERBANG juga berguna sebagai URUTAN. Menyatakan prior di depan supaya
kemenangannya tidak dilaporkan lebih mengesankan dari seharusnya.

`k_random` di-seed deterministik dari `zone_id` plus simbol, jadi re-run
memberi angka identik dan tidak ada "coba seed lain".

===========================================================================
4. DUA UJI, dan kenapa satu saja tidak cukup
===========================================================================

UJI A, MONOTON. Spearman rho antara kunci dan `r`, mentah dan setelah di-demean
per instrumen. Ini uji yang bebas asumsi: ia tidak butuh tahu kandidat mana
bersaing dengan siapa. Kalau sebuah kunci tidak berhubungan monoton dengan
hasil, mengurutkan dengannya tidak bisa memilih trade yang lebih baik, apa pun
mekanika slot-nya.

Demean per instrumen WAJIB dilaporkan berdampingan dengan yang mentah. Delapan
instrumen dengan ekspektasi dasar berbeda bisa memanufaktur rho tanpa satu pun
hubungan di dalam instrumen mana pun.

UJI B, LIFT DUA TERATAS. Uji A bisa melewatkan kunci yang rho-nya nol tapi
menaruh trade bagus di PUNCAK, dan puncak itulah yang diambil `max_orders`.
Jadi kandidat dikelompokkan, dua teratas menurut kunci diambil, dan delta-nya
adalah rata-rata R yang terambil dikurangi rata-rata R seluruh grup.

PENGELOMPOKANNYA APROKSIMASI, DAN ITU DINYATAKAN DI DEPAN. Set kandidat yang
sesungguhnya adalah apa yang `candidates()` kembalikan pada satu pass, dan
membangunnya ulang menuntut memutar ulang deteksi zona di tiap bar. Yang
dipakai di sini: satu grup per simbol per hari kalender, dan sebagai
pemeriksaan kedua per simbol per pekan. Trade dalam satu hari di satu simbol
memang bersaing memperebutkan slot yang sama. Sebuah kunci yang menang di
kedua pengelompokan lebih kuat daripada yang menang di salah satunya.

Grup dengan kurang dari tiga trade DIBUANG dari Uji B: dengan dua atau kurang,
dua teratas adalah seluruh grup dan delta-nya nol secara identik untuk setiap
kunci, jadi memasukkannya hanya menggelembungkan n dan mengencerkan t.

`k_random` adalah KONTROL SEKALIGUS PEMERIKSAAN RIG. Ekspektasinya nol tepat di
Uji B. Kalau ia keluar tidak nol secara signifikan, yang rusak rig-nya dan
bukan pasarnya, dan run itu dilaporkan gagal alih-alih dibaca.

===========================================================================
5. AMBANG LULUS, ditetapkan sekarang
===========================================================================

Sebuah kunci hanya LULUS kalau keempatnya lolos:

1. `n >= 30` di uji yang bersangkutan.
2. Tanda benar: rho > 0 di Uji A, delta > 0 di Uji B.
3. `|t| >` nilai kritis dua sisi ber-Bonferroni, alpha 0,05 dibagi `K`, dengan
   `K` = jumlah kunci yang layak dinilai. `K` dihitung dan dicetak SEBELUM satu
   baris pun dilaporkan.
4. Walk-forward `FOLDS` fold berurutan waktu, sign test satu sisi p <= 0,05.
   Dengan 8 fold itu berarti minimal 7 dari 8 fold bertanda benar (p = 0,0352);
   6 dari 8 memberi p = 0,1445 dan GAGAL.

Kunci yang lulus Uji A saja atau Uji B saja dilaporkan sebagai lulus SEBAGIAN
dan tidak direkomendasikan menggantikan apa pun. Dua uji yang tidak sepakat
adalah alasan untuk mengukur lagi, bukan untuk memilih yang hasilnya disukai.

===========================================================================
6. YANG TIDAK DIJAWAB STUDI INI
===========================================================================

- Ia tidak mengukur `max_orders` berapa yang benar. Ia mengambil 2 karena itu
  yang di-default `tools/execute.py`, dan pertanyaan berapa slot yang optimal
  adalah pertanyaan lain yang butuh model book yang sesungguhnya.
- Ia tidak memodelkan order yang ditempatkan lalu tidak pernah terisi. Populasi
  ini hanya memuat sentuhan yang terjadi. Order yang menggantung memang menahan
  slot di dunia nyata, dan efeknya di sini NOL secara konstruksi.
- Ia tidak menguji kombinasi kunci. Dua kunci yang digabung adalah ruang
  pencarian, dan ruang pencarian butuh praregistrasi sendiri.

POPULASINYA DIPATOK, dan patokan itu ada karena drift-nya terukur. Dua run
pertama di tree yang sama pada 2 September 2026 memberi n = 1847 lalu n = 1850:
`rows_for` membaca ekor MT5 yang hidup dan bar baru tutup di antara keduanya.
Verdict-nya kebetulan bertahan dan |t| terbesarnya bergeser -4,64 ke -4,66.
"Kebetulan bertahan" adalah persis yang `e2e/labels.mjs` lakukan sampai ia
memberi 7/9, 8/9, 8/9, 7/9, 9/9 di tree yang sama tanpa satu baris kode berubah.

`--as-of` menyalakan `tools.history.AS_OF`, default `PINNED_AS_OF`. Itu memotong
KEDUA jalur muat: `history.load`, yang melayani `intrabar.resolved` dan
`quant.clean`, DAN grid SSMT yang `checklist_outcomes._aligned` ambil lewat
`app.providers` tanpa menyentuh `tools.history` sama sekali. Memotong satu saja
menghasilkan studi yang TERLIHAT reproducible, yang lebih buruk daripada studi
yang jujur bergerak.

`--as-of 0` mengembalikan ekor hidup, dan angkanya tidak boleh dibandingkan
dengan angka yang dipatok.

===========================================================================
7. SELF-CHECK
===========================================================================

`--selftest` menjalankan Uji B pada grup buatan yang jawabannya diketahui:
sebuah kunci yang sempurna berkorelasi harus memberi lift positif maksimum,
kunci terbalik harus memberi lift negatif dengan besar yang sama, dan grup
berukuran dua harus memberi nol tepat. Sebuah rig lift yang tidak pernah
diperiksa bisa melaporkan angka bagus untuk kunci apa pun.

`--oracle` menjawab pertanyaan yang berlawanan dan lebih penting: apakah rig ini
BISA melaporkan LULUS. Ia memuat populasi dari cache dan menambahkan `k_oracle`
yang isinya outcome-nya sendiri, sebuah kunci yang curang karena ia melihat masa
depan. Kunci itu HARUS lulus kedua uji di setiap pengelompokan. Sebuah studi yang
melaporkan nol pemenang tanpa pernah menunjukkan pemenang seperti apa yang bisa
ia lihat sedang melaporkan diamnya sendiri, bukan diamnya pasar.

Cache-nya ditulis `--cache PATH` saat run biasa. Ia ada supaya pemeriksaan ini
berbiaya detik alih-alih memuat ulang delapan instrumen di resolusi 5 menit.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone
from math import sqrt

import numpy as np

from tools import history
from tools.checklist_outcomes import (
    FOLDS,
    SYMBOLS,
    _spearman,
    rows_for,
)
from tools.intrabar import FINER

#: Slot order, angka default `--max-orders` di `tools/execute.py`.
TAKE = 2

#: Grup di bawah ini tidak bisa membedakan kunci: dua teratas adalah seluruh
#: grup. Lihat Bagian 4.
MIN_GROUP = TAKE + 1

KEYS = (
    "k_met", "k_near_close", "k_near_target", "k_reward_r", "k_cheap",
    "k_departure", "k_random",
)


def _seeded(symbol: str, zone_id: str) -> float:
    """Angka acak stabil di [0, 1) dari identitas trade-nya.

    Deterministik lintas run dan lintas mesin: `hash()` bawaan Python di-salt
    per proses, jadi memakainya akan membuat kontrol ini berubah tiap run dan
    membuat "coba seed lain" mungkin tanpa ada yang menyadarinya.
    """
    digest = hashlib.sha256(f"{symbol}:{zone_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _day(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%d")


def _week(epoch: int) -> str:
    at = datetime.fromtimestamp(epoch, timezone.utc).isocalendar()
    return f"{at.year}-W{at.week:02d}"


def _t_one_sample(v: np.ndarray) -> tuple[float, float]:
    """Mean dan t satu sampel lawan nol. t = 0 saat variansnya nol."""
    if len(v) < 2:
        return (float(v.mean()) if len(v) else 0.0), 0.0
    se = float(v.std(ddof=1)) / sqrt(len(v))
    mean = float(v.mean())
    return mean, (mean / se if se > 0 else 0.0)


def _demeaned(rows: list[dict], key: str) -> tuple[np.ndarray, np.ndarray]:
    """Kunci dan r, keduanya dikurangi rata-rata instrumennya sendiri.

    Delapan instrumen dengan ekspektasi dasar berbeda bisa memanufaktur rho
    tanpa satu pun hubungan di dalam instrumen mana pun, jadi angka ini
    dilaporkan berdampingan dengan yang mentah dan bukan menggantikannya.
    """
    by_symbol: dict[str, list[dict]] = {}
    for row in rows:
        by_symbol.setdefault(row["symbol"], []).append(row)
    xs: list[float] = []
    ys: list[float] = []
    for group in by_symbol.values():
        x = np.array([g[key] for g in group], dtype=np.float64)
        y = np.array([g["r"] for g in group], dtype=np.float64)
        xs.extend(x - x.mean())
        ys.extend(y - y.mean())
    return np.array(xs), np.array(ys)


def lift(rows: list[dict], key: str, bucket) -> tuple[np.ndarray, int]:
    """Delta per grup: rata-rata R dua teratas menurut `key` dikurangi rata-rata grup.

    Ties dipecah dengan `zone_id` supaya urutannya deterministik. Tanpa itu dua
    kandidat berskor sama akan dipilih menurut urutan iterasi dict, dan kunci
    dengan banyak tie - `k_met` bilangan bulat 0..17 adalah yang terburuk -
    akan mengukur urutan baris dan bukan kuncinya.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["symbol"], bucket(row["time"])), []).append(row)

    deltas: list[float] = []
    for group in groups.values():
        if len(group) < MIN_GROUP:
            continue
        order = sorted(group, key=lambda g: (-g[key], g["zone_id"]))
        taken = np.array([g["r"] for g in order[:TAKE]], dtype=np.float64)
        whole = np.array([g["r"] for g in group], dtype=np.float64)
        deltas.append(float(taken.mean() - whole.mean()))
    return np.array(deltas, dtype=np.float64), len(groups)


def _folds(values: list, pick) -> list[float | None]:
    """`FOLDS` potongan berurutan waktu, nilai `pick` tiap potongan."""
    if len(values) < FOLDS:
        return [None] * FOLDS
    edges = np.linspace(0, len(values), FOLDS + 1).astype(int)
    return [
        pick(values[a:b]) if b - a >= 2 else None
        for a, b in zip(edges, edges[1:])
    ]


def _sign_test(deltas: list[float | None], want_positive: bool = True) -> dict:
    """Berapa fold yang bertanda benar, plus p satu sisi binomial di 0,5."""
    graded = [d for d in deltas if d is not None]
    good = sum(1 for d in graded if (d > 0) == want_positive and d != 0)
    n = len(graded)
    # p = P(X >= good) untuk X ~ Binomial(n, 0.5), dihitung eksak.
    from math import comb
    p = sum(comb(n, k) for k in range(good, n + 1)) / 2**n if n else 1.0
    return {"graded": n, "correct_sign": good, "p": p,
            "deltas": [None if d is None else round(d, 4) for d in graded]}


def study(symbols: list[str], interval: str, fine: str,
          cache: str = "") -> dict:
    rows: list[dict] = []
    for symbol in symbols:
        got = rows_for(symbol, interval, fine)
        for row in got:
            row["k_random"] = _seeded(symbol, row["zone_id"])
        rows.extend(got)
        print(f"{symbol}: {len(got)} trade", file=sys.stderr)

    if not rows:
        return {"error": "populasi kosong"}
    rows.sort(key=lambda r: r["time"])
    if cache:
        pathlib.Path(cache).write_text(json.dumps(rows, default=str),
                                       encoding="utf-8")
    return graded(rows, interval, fine, KEYS)


def graded(rows: list[dict], interval: str, fine: str,
           keys: tuple[str, ...]) -> dict:
    """Nilai `keys` atas `rows`. Dipisah supaya `--oracle` memakai jalur ini juga.

    Kalau pemeriksaan oracle memakai penilai kedua, yang ia buktikan adalah
    penilai kedua itu bisa melaporkan lulus, yang bukan pertanyaannya.
    """

    # Kunci yang punya None di baris mana pun DIBUANG dari populasi utama, bukan
    # diisi. `k_near_target` None ketika plan tidak punya target, dan mengisinya
    # dengan nol akan mengurutkan trade tanpa target ke tengah daftar seolah itu
    # sebuah pendapat.
    usable = [k for k in keys
              if all(r.get(k) is not None for r in rows)]
    dropped = [k for k in keys if k not in usable]

    judged = len(usable)
    critical = _critical_t(0.05 / judged) if judged else 0.0

    out: dict = {
        "preregistered": "tools/order_key.py, 2026-09-02",
        "question": ("kunci urut mana yang sebaiknya memilih dua order, "
                     "tools/execute.py baris 395 dan 496"),
        "take": TAKE,
        "as_of": history.AS_OF,
        "population": {
            "n": len(rows), "symbols": sorted({r["symbol"] for r in rows}),
            "interval": interval, "fine": fine,
            "exp_r_all": float(np.mean([r["r"] for r in rows])),
        },
        "keys_judged": judged,
        "keys_dropped": dropped,
        "alpha_corrected": 0.05 / judged if judged else None,
        "critical_t": critical,
        "test_a_monotone": {},
        "test_b_lift": {},
    }

    for key in usable:
        x = np.array([r[key] for r in rows], dtype=np.float64)
        y = np.array([r["r"] for r in rows], dtype=np.float64)
        rho, t_rho = _spearman(x, y)
        dx, dy = _demeaned(rows, key)
        rho_d, t_d = _spearman(dx, dy)

        wf = _folds(rows, lambda chunk, k=key: _spearman(
            np.array([c[k] for c in chunk], dtype=np.float64),
            np.array([c["r"] for c in chunk], dtype=np.float64),
        )[0])
        sign = _sign_test(wf)
        out["test_a_monotone"][key] = {
            "n": len(rows),
            "spearman_rho": rho, "t": t_rho,
            "spearman_rho_demeaned": rho_d, "t_demeaned": t_d,
            "walk_forward": sign,
            "passes": bool(
                len(rows) >= 30 and rho_d > 0
                and abs(t_d) > critical and sign["p"] <= 0.05
            ),
        }

        out["test_b_lift"][key] = {}
        for name, bucket in (("per_symbol_day", _day),
                             ("per_symbol_week", _week)):
            deltas, n_groups = lift(rows, key, bucket)
            mean, t = _t_one_sample(deltas)
            wf_b = _folds(
                sorted(rows, key=lambda r: r["time"]),
                lambda chunk, k=key, b=bucket: float(lift(chunk, k, b)[0].mean())
                if len(lift(chunk, k, b)[0]) else None,
            )
            sign_b = _sign_test(wf_b)
            out["test_b_lift"][key][name] = {
                "groups_total": n_groups, "groups_judged": len(deltas),
                "mean_delta_r": mean, "t": t,
                "walk_forward": sign_b,
                "passes": bool(
                    len(deltas) >= 30 and mean > 0
                    and abs(t) > critical and sign_b["p"] <= 0.05
                ),
            }

    # KONTROL DIPERIKSA SEBELUM HASILNYA DIBACA. Lihat Bagian 4: kalau kunci
    # acak menunjukkan lift yang signifikan, yang rusak rig-nya.
    control = out["test_b_lift"].get("k_random", {})
    broken = [
        name for name, cell in control.items()
        if abs(cell["t"]) > critical
    ]
    out["control_ok"] = not broken
    if broken:
        out["control_failure"] = (
            f"kunci acak memberi lift signifikan di {broken}; rig-nya yang "
            "rusak, angka di atas tidak boleh dibaca"
        )

    winners = sorted(
        (k for k in usable if k != "k_random"
         and out["test_a_monotone"][k]["passes"]
         and all(c["passes"] for c in out["test_b_lift"][k].values())),
        key=lambda k: -out["test_a_monotone"][k]["spearman_rho_demeaned"],
    )
    partial = [
        k for k in usable if k != "k_random" and k not in winners
        and (out["test_a_monotone"][k]["passes"]
             or any(c["passes"] for c in out["test_b_lift"][k].values()))
    ]
    out["passes_both"] = winners
    out["passes_one"] = partial
    out["verdict"] = (
        f"LULUS KEDUA UJI: {winners}" if winners
        else f"TIDAK ADA KUNCI YANG LULUS KEDUA UJI; lulus sebagian: {partial}"
    )
    return out


def _critical_t(alpha: float) -> float:
    """Kritis dua sisi pada df besar, dari normal. Sama dengan rig lain di repo."""
    from statistics import NormalDist
    return NormalDist().inv_cdf(1 - alpha / 2)


def _selftest() -> None:
    """Uji B dijalankan pada grup yang jawabannya diketahui. Lihat Bagian 7."""
    rows = [
        {"symbol": "X", "zone_id": f"z{i}", "time": 1_700_000_000,
         "r": float(i), "k_perfect": float(i), "k_inverted": float(-i)}
        for i in range(5)
    ]
    # Grup 0..4: rata-rata 2,0. Dua teratas menurut k_perfect adalah 4 dan 3,
    # rata-rata 3,5, jadi lift +1,5. Terbalik mengambil 0 dan 1, lift -1,5.
    good, _ = lift(rows, "k_perfect", _day)
    bad, _ = lift(rows, "k_inverted", _day)
    assert good.tolist() == [1.5], good
    assert bad.tolist() == [-1.5], bad

    # Grup berukuran TAKE dibuang, bukan dinilai nol: nol yang dinilai akan
    # mengencerkan t setiap kunci sekaligus dan membuat semuanya terlihat lebih
    # dekat ke kontrol daripada sebenarnya.
    two = rows[:2]
    empty, total = lift(two, "k_perfect", _day)
    assert len(empty) == 0 and total == 1, (empty, total)

    # Kontrol acak harus stabil lintas run.
    assert _seeded("XAUUSD", "SD-123") == _seeded("XAUUSD", "SD-123")
    assert _seeded("XAUUSD", "SD-123") != _seeded("XAGUSD", "SD-123")
    print("selftest OK", file=sys.stderr)


def _oracle(cache: str) -> int:
    """Kunci yang melihat masa depan harus LULUS. Lihat Bagian 7."""
    rows = json.loads(pathlib.Path(cache).read_text(encoding="utf-8"))
    for row in rows:
        row["k_oracle"] = row["r"]
    out = graded(rows, "1h", "5m", ("k_oracle", "k_random"))
    a = out["test_a_monotone"]["k_oracle"]
    b = out["test_b_lift"]["k_oracle"]
    print(f"oracle A: rho_dem {a['spearman_rho_demeaned']:.4f} "
          f"t {a['t_demeaned']:.2f} wf {a['walk_forward']['correct_sign']}"
          f"/{a['walk_forward']['graded']} passes={a['passes']}", file=sys.stderr)
    for name, cell in b.items():
        print(f"oracle B {name}: delta {cell['mean_delta_r']:.4f} "
              f"t {cell['t']:.2f} wf {cell['walk_forward']['correct_sign']}"
              f"/{cell['walk_forward']['graded']} passes={cell['passes']}",
              file=sys.stderr)
    ok = a["passes"] and all(c["passes"] for c in b.values())
    print(f"oracle di passes_both: {out['passes_both']}", file=sys.stderr)
    if not ok or "k_oracle" not in out["passes_both"]:
        print("ORACLE GAGAL: rig ini tidak bisa melaporkan LULUS, jadi nol "
              "pemenangnya tidak berarti apa-apa", file=sys.stderr)
        return 1
    print("ORACLE OK: rig bisa melaporkan LULUS", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--fine", default="")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--cache", default="")
    parser.add_argument("--as-of", type=int, default=history.PINNED_AS_OF,
                        help="epoch patokan ekor; 0 berarti ekor hidup")
    parser.add_argument("--oracle", default="",
                        help="path cache; nilai kunci yang melihat masa depan")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if args.oracle:
        return _oracle(args.oracle)
    fine = args.fine or FINER.get(args.interval, "5m")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    # DIPASANG SEBELUM SATU BAR PUN DIMUAT. Sebuah patokan yang dipasang
    # setelah pemuatan pertama memberi populasi campuran, dan campurannya
    # bergantung urutan simbol.
    history.AS_OF = args.as_of
    print(f"as_of {history.AS_OF} "
          f"({'ekor hidup' if not history.AS_OF else 'dipatok'})",
          file=sys.stderr)
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, args.interval, fine, args.cache)
    json.dump(out, sys.stdout, indent=2, default=str)
    print()
    return 0 if "error" not in out and out.get("control_ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
