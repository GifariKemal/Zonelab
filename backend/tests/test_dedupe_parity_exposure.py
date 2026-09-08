"""Detektor mana yang menggabung zona bertumpuk, dan kenapa daftarnya dikunci.

`_dedupe` membuang zona yang tumpang tindih lebih dari `merge_overlap_pct`.
Cermin Pine di `mql5/pine/ZonelabImbalanceStrategy.pine` TIDAK punya padanannya -
kata `overlap`, `merge_overlap`, dan `dedupe` nol kali di seluruh berkas itu -
jadi setiap detektor di daftar ini diukur di TradingView pada populasi yang
LEBIH BESAR daripada yang dihasilkan Zonelab.

Terukur 8 September 2026 di 100 bar FX:XAUUSD harian, feed yang sama untuk
keduanya: `cisd_zone` 13 lawan 9 (+44%), `ote` 10 lawan 9 (+11%),
`supply_demand` 6 lawan 6 (nol di jendela itu). Yang terakhir yang paling
penting karena ia satu-satunya detektor `orderable`.

Tes ini mengunci DAFTARNYA, bukan angkanya. Menambahkan `_dedupe` ke detektor
baru - atau membuangnya dari salah satu yang di sini - membuat paparan di atas
salah, dan itu harus gagal keras alih-alih hanyut diam-diam.
"""

from __future__ import annotations

import pathlib

#: Detektor yang menggabung tumpang tindih di Python dan TIDAK di Pine.
DEDUPING = {"cisd_zone", "ote", "supply_demand"}

_DETECT = pathlib.Path(__file__).resolve().parents[1] / "app" / "detect"
_PINE = (pathlib.Path(__file__).resolve().parents[2] / "mql5" / "pine"
         / "ZonelabImbalanceStrategy.pine")


def test_daftar_pemanggil_dedupe_terkunci() -> None:
    found = {p.stem for p in _DETECT.glob("*.py")
             if "_dedupe(" in p.read_text(encoding="utf-8")}
    assert found == DEDUPING, (
        f"pemanggil _dedupe berubah: {found}. Paparan parity Pine di docstring "
        "berkas ini dan di evidence `cisd_zone` ikut basi - ukur ulang lalu "
        "perbarui keduanya, jangan cuma menambal daftarnya."
    )


def test_pine_masih_tanpa_dedupe() -> None:
    """Kalau Pine SUDAH punya dedupe, seluruh premis di atas gugur."""
    src = _PINE.read_text(encoding="utf-8").lower()
    for word in ("merge_overlap", "dedupe"):
        assert word not in src, (
            f"Pine sekarang menyebut {word!r}. Kalau ia benar-benar menggabung "
            "tumpang tindih, angka TradingView tidak lagi kelebihan populasi "
            "dan catatan di evidence `cisd_zone` harus dicabut."
        )
