"""Zona ICT harus punya target, atau jalur order tertutup untuk mereka.

`tools/execute.py` mensyaratkan target yang terbaca: sebuah zona tanpa
`plan.target` tidak pernah jadi kandidat. `plan.build` mengambil target dari
`zone.profit_zone_rr`, dan field itu diisi `mark_profit_zones`.

Sampai 2 September 2026 fungsi itu dipanggil di dua tempat saja,
`app/detect/supply_demand.py:673` dan jalur refinement `app/drawing.py:401`, dan
tidak satu pun menyentuh `app/detect/imbalance.py` atau `inversion.py`.
Akibatnya bukan "ICT lebih sulit diorder", melainkan jalur order TERTUTUP untuk
setiap detektor ICT, dan tertutupnya tidak pernah diputuskan siapa pun. Diukur
di empat kombinasi simbol-timeframe pada hari itu: 7, 10, 4 dan 8 zona ICT lolos
gerbang departure DAN masih fresh, dan NOL dari semuanya punya target, sementara
setiap zona supply_demand yang lolos gerbang dan fresh punya.

Yang paling mahal dari itu: `fvg` dan `order_block` adalah dua detektor dengan
bukti terkuat di repo ini, +10 sampai +25 poin lawan placebo dengan walk-forward
8 dari 8 di dua geometri, dan keduanya tepat yang tidak bisa diorder. Klaim
`supply_demand` lebih lemah, ia mengalahkan TIDAK ADA box, bukan placebo di
jarak yang disamakan.

`_present` adalah funnel bersama keempat detektor ICT, jadi di situlah kuncinya
dipasang: `detect_fvg` dan `detect_order_block` memanggilnya langsung, dan
`ifvg` plus `breaker` lewat `inversion._invert`. Menguji funnel-nya menguji
keempatnya sekaligus, dan tidak bergantung apakah sebuah fixture kebetulan
melahirkan kind tertentu.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from app.detect import DETECTORS
from app.detect.imbalance import _present
from app.models import Candle, ImbalanceParams, SupplyDemandParams, ZoneSide

from test_refine_and_crowding import zone

NOW = 5_000


def test_present_computes_the_road_for_both_sides():
    """Kunci utamanya, dan ia menatap funnel yang keempat detektor ICT lewati.

    Dua zona saling berlawanan, supply di 130 dan demand di 100, masing-masing
    tinggi 10. Jalan dari demand ke atas 30 harga = 3,0 kali tingginya sendiri,
    dan dari supply ke bawah sama. Angkanya dihitung di sini supaya test ini
    gagal kalau `mark_profit_zones` diganti sesuatu yang mengisi field-nya
    dengan nilai lain.
    """
    zones = [
        zone(ZoneSide.DEMAND, 100.0, 10.0, born=1_000),
        zone(ZoneSide.SUPPLY, 130.0, 10.0, born=1_000),
    ]
    out, _ = _present(zones, ImbalanceParams(max_zones_per_side=0), {}, NOW)
    assert len(out) == 2
    got = {z.side: z.profit_zone_rr for z in out}
    assert got == {ZoneSide.DEMAND: 3.0, ZoneSide.SUPPLY: 3.0}, (
        f"jalan tidak dihitung di `_present`, dapat {got}; tanpa itu "
        "`plan.build` tidak punya target dan jalur order tertutup untuk fvg, "
        "order_block, ifvg dan breaker sekaligus"
    )


def test_present_leaves_it_none_without_a_wall():
    """Penjaga arah sebaliknya: `None` yang benar tidak boleh dipalsukan.

    Satu zona sendirian tidak punya dinding lawan, jadi tidak punya jalan.
    Mengisi field itu dengan angka apa pun di keadaan ini akan mengarang target
    yang tidak ada dasarnya di chart, dan itu lebih buruk daripada cacat yang
    baru ditutup: yang lama menutup jalur order, yang ini membukanya ke arah
    yang salah.
    """
    zones = [zone(ZoneSide.DEMAND, 100.0, 10.0, born=1_000)]
    out, _ = _present(zones, ImbalanceParams(max_zones_per_side=0), {}, NOW)
    assert out[0].profit_zone_rr is None


def test_zero_now_skips_the_pass_instead_of_dating_it_zero():
    """`now=0` melewati pass-nya, bukan menjalankannya dengan waktu nol.

    Bedanya penting. Waktu nol akan menyatakan setiap zona belum lahir, jadi
    setiap dinding tersaring dan hasilnya `None` yang terlihat sah. Yang
    dituntut di sini cuma bahwa default-nya tidak diam-diam mengubah data.
    """
    zones = [
        zone(ZoneSide.DEMAND, 100.0, 10.0, born=1_000),
        zone(ZoneSide.SUPPLY, 130.0, 10.0, born=1_000),
    ]
    out, _ = _present(zones, ImbalanceParams(max_zones_per_side=0), {})
    assert all(z.profit_zone_rr is None for z in out)


def _two_sided() -> list[Candle]:
    """Deret yang melahirkan zona di KEDUA sisi sekaligus.

    Naik dengan celah, naik jauh, lalu turun dengan celah tapi berhenti di ATAS
    celah pertama. Berhentinya itu yang penting: kalau turunnya menembus celah
    demand awal, celah itu mati dan yang tersisa satu sisi saja, dan sebuah
    zona tanpa lawan memang `None` (lihat test di atas). Jadi fixture satu sisi
    akan merah untuk alasan yang benar dan menyembunyikan cacat yang dicari.
    """
    out: list[Candle] = []
    price = 100.0
    t = 1_700_000_000
    for bars, step in ((10, +3.0), (3, 0.0), (14, +5.0), (3, 0.0),
                       (10, -4.0), (4, 0.0)):
        for _ in range(bars):
            o = price
            price += step
            out.append(Candle(time=t, open=o, high=max(o, price) + 0.5,
                              low=min(o, price) - 0.5, close=price,
                              volume=100.0))
            t += 3600
    return out


@pytest.mark.parametrize("name", ("fvg", "supply_demand"))
def test_end_to_end_through_the_detector(name: str):
    """Bukti tambahan lewat detektor sungguhan, bukan `_present` langsung.

    Hanya dua kind di sini, dan itu disengaja: `order_block` dan `breaker`
    tidak melahirkan satu pun zona di deret sintetis ini (diukur, 0 dari 0),
    karena bentuknya tidak punya base yang mereka syaratkan. Menuntut mereka
    di sini berarti test yang skip diam-diam, dan funnel-nya sudah dikunci
    tiga test di atas.
    """
    params = (SupplyDemandParams(max_zones_per_side=0) if name == "supply_demand"
              else ImbalanceParams(max_zones_per_side=0))
    zones, _ = DETECTORS[name](_two_sided(), params)
    assert zones, f"{name} tidak melahirkan zona, fixture-nya rusak"
    missing = [z.id for z in zones if z.profit_zone_rr is None]
    assert not missing, (
        f"{name}: {len(missing)} dari {len(zones)} zona tanpa jalan terhitung "
        f"padahal deret ini punya kedua sisi hidup: {missing[:5]}"
    )


def test_the_call_exists_in_the_ict_funnel():
    """PENJAGA SOURCE, dan ia menatap tempat yang bisa hilang tanpa suara.

    Test di atas mengunci hasilnya lewat `_present`. Yang tidak mereka lihat:
    seseorang menghapus argumen `now` di salah satu pemanggil. Default-nya 0,
    dan 0 melewati pass-nya, jadi pemanggil yang lupa mengirimnya menutup
    jalur order kembali TANPA satu error pun dan tanpa satu test di atas
    berubah warna.
    """
    root = pathlib.Path(__file__).resolve().parent.parent / "app" / "detect"
    body = (root / "imbalance.py").read_text(encoding="utf-8")
    assert "mark_profit_zones(" in body[body.index("def _present("):], (
        "mark_profit_zones hilang dari `_present`, jadi jalur order tertutup "
        "lagi untuk keempat detektor ICT sekaligus"
    )
    for name in ("imbalance.py", "inversion.py"):
        text = (root / name).read_text(encoding="utf-8")
        calls = [c for c in re.findall(r"_present\(([^)]*)\)", text)
                 if "found: list" not in c]
        assert calls, f"{name}: tidak ada pemanggil `_present` yang terbaca"
        bare = [c for c in calls if c.count(",") < 3]
        assert not bare, (
            f"{name}: pemanggil `_present` tanpa argumen `now`, jadi pass-nya "
            f"dilewati tanpa suara: {bare}"
        )
