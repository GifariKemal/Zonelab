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
#: `liquidity_pool`, ditambahkan 8 September 2026, dan paparannya BUKAN SATU
#: ANGKA melainkan fungsi dari `equal_tol_atr` - satu-satunya dari empat yang
#: begitu. Ia bisa diukur tanpa menjalankan Pine sama sekali: karena Pine tidak
#: punya dedupe, populasi Pine PERSIS sama dengan `merge_overlap_pct=1.0`.
#: Diukur di riwayat penuh MT5:
#:
#:     sel          tol 0,10   tol 0,25   tol 0,50
#:     XAUUSD 1d      +2,0%      +7,1%     +16,4%
#:     XAUUSD 1h      +4,6%     +24,6%     +65,2%
#:     BTCUSD 1h      +9,7%     +42,1%    +103,6%
#:
#: Di default yang di-ship (0,1) selisihnya kecil; di 0,5 populasi Pine bisa
#: DUA KALI populasi Zonelab, karena toleransi lebar membuat kolam bertumpuk.
#: Jadi angka TradingView untuk layer ini hanya sebanding dengan Zonelab pada
#: toleransi yang sama DAN toleransi yang sempit.
DEDUPING = {"cisd_zone", "ote", "supply_demand", "liquidity_pool"}

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
    """Kalau Pine SUDAH punya dedupe, seluruh premis di atas gugur.

    KOMENTAR DIBUANG DULU, dan itu bukan kerapian melainkan koreksi. Versi
    pertama tes ini mencari kata di seluruh berkas, lalu gagal begitu blok
    detektor 7 ditambahkan - karena komentarnya berbunyi "TIDAK ADA DEDUPE DI
    SINI". Sebuah tes yang menyala pada prosa yang MENEGASKAN invariannya
    adalah tes yang salah baca, jadi yang diperiksa sekarang kodenya.
    """
    lines = _PINE.read_text(encoding="utf-8").splitlines()
    code = "\n".join(ln.split("//")[0] for ln in lines).lower()
    for word in ("merge_overlap", "dedupe"):
        assert word not in code, (
            f"Pine sekarang menyebut {word!r} DI KODE. Kalau ia benar-benar "
            "menggabung tumpang tindih, angka TradingView tidak lagi kelebihan "
            "populasi dan catatan di evidence `cisd_zone` harus dicabut."
        )
