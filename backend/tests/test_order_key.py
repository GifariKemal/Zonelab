"""Kunci urut kandidat dikunci di sini, karena ia memilih order mana yang dikirim.

`tools/execute.py` mengurutkan kandidat di dua tempat dan `--max-orders` default
2, jadi urutan itu memilih dua dari sekian kandidat yang lolos gerbang. Sampai
2 September 2026 tie-break-nya `abs(entry - close)`, mendahulukan kandidat yang
paling dekat, dan `docs/order_key.json` mengukurnya: Spearman rho demeaned
-0,1073 pada t = -4,64 melawan ambang Bonferroni 2,69, |t| terbesar di seluruh
run dengan tanda yang SALAH, dan lift dua-teratasnya -0,0966 R pada t = -3,86
dengan walk-forward NOL dari 8 fold.

Yang test ini jaga bukan "urutannya begini". Ia menjaga satu hal yang lebih
sempit dan lebih penting: **jarak tidak boleh ikut memutuskan lagi**. Kunci itu
sudah pernah ada di sana selama berbulan-bulan dengan sebuah komentar yang
menyatakan ia benar, dan komentar tidak gagal saat asumsinya salah.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

from tools.execute import by_method, by_method_ranked


@dataclass
class FakeZone:
    id: str


@dataclass
class FakePlan:
    entry: float
    target: float


@dataclass
class FakeChecklist:
    met: int


def _candidate(zone_id: str, met: int, entry: float, target: float = 0.0):
    return (FakeZone(zone_id), FakePlan(entry, target), FakeChecklist(met))


def test_higher_checklist_score_still_wins():
    """`met` tetap kunci utama, dan itu keputusan yang dinyatakan.

    Rho-nya -0,0356 demeaned, praktis nol, tapi nol berbeda dari merugikan:
    tidak ada angka yang mengatakan mengurutkan dengannya lebih buruk daripada
    tidak. Ia dipertahankan karena membuangnya tidak punya dukungan terukur,
    sama seperti menggantinya. Kalau nanti ada angka yang mengatakan sebaliknya,
    test inilah yang harus diubah, dengan sengaja.
    """
    low = _candidate("SD-100", met=3, entry=10.0)
    high = _candidate("SD-200", met=9, entry=10.0)
    assert sorted([low, high], key=by_method) == [high, low]


def test_distance_to_close_does_not_decide():
    """DUA KANDIDAT BER-`met` SAMA DIURUTKAN ID, BUKAN JARAK.

    Kasusnya disusun supaya kedua urutan itu BERBEDA: `SD-200` jauh lebih dekat
    ke harga, jadi kunci lama akan menaruhnya lebih dulu, sementara id menaruh
    `SD-100` lebih dulu. Sebuah kasus di mana keduanya sepakat akan lolos tanpa
    memeriksa apa pun.
    """
    far = _candidate("SD-100", met=5, entry=100.0)
    near = _candidate("SD-200", met=5, entry=1.0)
    # Harga di 0, jadi `near` berjarak 1 dan `far` berjarak 100.
    assert sorted([near, far], key=by_method) == [far, near]


def test_distance_to_target_does_not_decide():
    """Situs urut kedua, `k_near_target`, yang juga terukur negatif.

    -0,0774 R pada t = -2,91 di pengelompokan pekan, walk-forward 2 dari 8.
    Sama seperti di atas, kasusnya disusun supaya jarak dan id tidak sepakat.
    """
    wide = ("XAUUSD", "1h", FakeZone("SD-100"), FakePlan(100.0, 0.0),
            FakeChecklist(5))
    tight = ("XAUUSD", "1h", FakeZone("SD-200"), FakePlan(100.0, 99.0),
             FakeChecklist(5))
    assert sorted([tight, wide], key=by_method_ranked) == [wide, tight]


def test_symbol_separates_identical_zone_ids():
    """Zone id adalah `KIND-bartime` TANPA simbol.

    Dua zona sejenis di bar yang sama pada dua instrumen berbeda punya id yang
    identik, jadi tanpa simbol di dalam kuncinya urutan keduanya ditentukan
    urutan iterasi dan bertukar antar-run.
    """
    gold = ("XAUUSD", "1h", FakeZone("SD-1"), FakePlan(1.0, 0.0),
            FakeChecklist(5))
    silver = ("XAGUSD", "1h", FakeZone("SD-1"), FakePlan(1.0, 0.0),
              FakeChecklist(5))
    assert sorted([gold, silver], key=by_method_ranked) == [silver, gold]
    assert by_method_ranked(gold) != by_method_ranked(silver)


def test_the_key_is_total_so_two_runs_agree():
    """Tidak ada dua kandidat berbeda yang boleh punya kunci yang sama.

    Kunci yang seri menyerahkan urutannya ke urutan masukan, dan urutan masukan
    datang dari iterasi deteksi zona. Itu reproducible hari ini dan tidak ada
    yang menjaganya tetap begitu.
    """
    pool = [_candidate(f"SD-{i}", met=5, entry=float(i)) for i in range(12)]
    keys = [by_method(c) for c in pool]
    assert len(set(keys)) == len(keys)


def test_no_sort_in_execute_decides_on_a_distance():
    """PENJAGA REGRESI, dan ia menatap source-nya sendiri.

    Empat test di atas mengunci fungsi kuncinya. Yang tidak mereka lihat adalah
    seseorang menambahkan `sort` KETIGA di `execute.py` dengan `abs(...)` di
    dalamnya, atau mengembalikan jaraknya langsung ke pemanggil alih-alih ke
    fungsi kunci. Itu bentuk drift yang sudah dua kali memakan repo ini lewat
    sensus yang harus disunting tangan, jadi yang diperiksa di sini source-nya
    dan bukan daftar yang ditulis ulang di samping source.
    """
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "tools" / "execute.py").read_text(encoding="utf-8")
    offenders = [
        line.strip() for line in src.splitlines()
        if re.search(r"\.sort\(|sorted\(", line) and "abs(" in line
    ]
    assert not offenders, (
        "jarak kembali jadi kunci urut di execute.py, dan ia terukur "
        "merugikan (docs/order_key.json, t = -4,64, walk-forward 0 dari 8): "
        f"{offenders}"
    )
