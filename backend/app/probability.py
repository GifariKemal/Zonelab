"""Peluang terukur untuk sebuah order, dilekatkan di kandidatnya.

Sampai 3 September 2026 setiap order di engine ini dipasang tanpa satu angka pun
yang mengatakan seberapa sering setup seperti itu berakhir bagaimana. Operator
melihat entry, stop, target, dan risiko dalam dolar; yang tidak ada peluangnya.

SATU ANGKA AKAN MENIPU, DAN ITU SEBABNYA MODUL INI MENGEMBALIKAN EMPAT.
Diukur pada supply_demand XAUUSD 30m, n=1794: P(R > 0) adalah 0,5496. Itu
terbaca seperti "menang 55 persen", dan pembacaan itu salah sebelas kali lipat
untuk apa yang orang kira. Rinciannya: stop penuh 34,4 persen, rugi sebagian
9,9 persen, untung KECIL 48,9 persen dengan rata-rata +0,445 R, dan target 2R
hanya 4,9 persen. Hampir setiap "kemenangan" adalah exit horizon kecil.
Ekspektasinya -0,0306 R.

Jadi yang dikembalikan P(stop penuh), P(rugi sebagian), P(untung kecil) dan
P(target), plus ekspektasi R, plus n populasinya, plus interval kepercayaan
untuk angka yang paling mudah disalahbaca.

INI BUKAN PREDIKSI ARAH, dan penamaannya sengaja tidak memberi ruang untuk itu.
Arah sebuah order sudah ditentukan SISI ZONA: zona demand adalah beli. Yang
modul ini jawab hanya seberapa sering order semacam itu resolve ke mana, pada
populasi yang diukur. Dua belas hipotesis arah praregistrasi mati di repo ini,
dan modul ini tidak mencoba yang ketiga belas.

ANGKANYA DIBACA DARI FILE, TIDAK DIHITUNG DI SINI. `docs/entry_probability.json`
dihasilkan `tools/entry_probability.py` yang praregistrasinya ada di docstring-
nya. Menghitung ulang di runtime berarti dua definisi populasi yang bisa
melenceng, dan itu kelas cacat yang repo ini paling sering ketemu.

POPULASI YANG TIDAK DIUKUR MENGEMBALIKAN None, bukan tebakan. Sebuah layer atau
timeframe yang belum pernah lewat rig itu tidak punya peluang, dan mengisinya
dengan rata-rata global akan memberi angka yang terlihat sah untuk setup yang
tidak pernah dilihat siapa pun.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Tabel kalibrasi, satu satunya sumber angkanya.
TABLE = Path(__file__).resolve().parent.parent.parent / "docs" / "entry_probability.json"

#: Ambang bucket, disalin dari tool yang menghasilkannya. Kalau keduanya
#: melenceng, angka yang dilaporkan berhenti berarti, dan
#: `tests/test_probability.py` mengunci keduanya sama.
FULL_STOP = -0.99
SMALL_LOSS = -0.01
TARGET_R = 1.5

_cache: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        loaded = json.loads(TABLE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # File hilang atau rusak bukan alasan menjatuhkan jalur order. Ia
        # alasan untuk TIDAK melaporkan peluang, dan itu bedanya.
        loaded = {}
    _cache = loaded if isinstance(loaded, dict) else {}
    return _cache


def outcome_odds(layer: str, symbol: str, interval: str,
                 cleared_gate: bool | None = None) -> dict[str, Any] | None:
    """Distribusi hasil terukur untuk populasi ini, atau None kalau tidak ada.

    `cleared_gate` memilih sisi gerbang departure. `None` mengembalikan seluruh
    populasi. Sisi itu penting dan bukan detail: untuk `fvg` gerbangnya
    TERBALIK, dan sisi bawahnya n=1939 dengan P(target) 0,1444 sementara sisi
    atasnya n=62 dengan P(target) 0,0161. Melaporkan yang salah akan
    menyembunyikan populasi yang sebenarnya diorder.

    `symbol` boleh membawa prefix venue; ia dipotong, karena tabelnya memakai
    ticker telanjang persis seperti rig yang menghasilkannya.
    """
    rates = (_load().get("base_rates") or {})
    bare = symbol.split(":")[-1]
    entry = rates.get(f"{layer} {bare} {interval}")
    if not isinstance(entry, dict) or "error" in entry:
        return None
    key = ("all" if cleared_gate is None
           else "above_gate" if cleared_gate else "below_gate")
    got = entry.get(key)
    if not isinstance(got, dict) or not got.get("n"):
        return None
    return {**got, "population": f"{layer} {bare} {interval} {key}"}


def summary(odds: dict[str, Any] | None) -> str:
    """Satu baris untuk dicetak di sebelah kandidat.

    P(target) DULU, karena itu angka yang operator kira ia beli. n ikut di
    setiap baris supaya sebuah peluang dari 62 trade tidak terbaca sama dengan
    peluang dari 1.939.
    """
    if odds is None:
        return "peluang: BELUM DIUKUR untuk populasi ini"
    lo, hi = odds.get("p_target_ci95") or [0.0, 1.0]
    return (
        f"peluang: target {100 * odds['p_target']:.1f}% "
        f"(CI {100 * lo:.1f}-{100 * hi:.1f}), stop penuh "
        f"{100 * odds['p_full_stop']:.1f}%, untung kecil "
        f"{100 * odds['p_small_win']:.1f}%, exp {odds['exp_r']:+.4f} R, "
        f"n={odds['n']}"
    )
