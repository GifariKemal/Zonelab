"""Lock yang ditunggu tidak boleh dibawa ke `asyncio.run` berikutnya.

Sebuah `asyncio.Lock` terikat ke loop pada saat pertama ia benar-benar DITUNGGU,
bukan saat dibuat. Server hidup di satu loop selamanya, jadi ini tidak pernah
menggigit di sana. Yang menggigit adalah tool pengukuran: `asyncio.run` kedua di
process yang sama menemukan lock dari loop pertama yang sudah mati dan menerima
`RuntimeError: ... is bound to a different event loop`.

Terukur 30 Agustus 2026 pada `tools/true_open_matrix.py`, yang menjalankan 12
sel dalam satu process: 9 dari 12 sel mati, dan studi 12 sel di
`docs/PRAREGISTRASI-YATIM.md` runtuh jadi 3 sel. Ia gagal keras, bukan senyap,
tapi angka yang sudah diterbitkan tidak bisa dihasilkan ulang dengan perintah
yang tertulis di `docs/README.md`.

DUA PENUNGGU, BUKAN SATU. `Lock.acquire` pada lock yang bebas kembali tanpa
menyentuh loop sama sekali, jadi test satu-tugas hijau baik dengan maupun tanpa
perbaikannya. Cacatnya hanya muncul kalau lock-nya benar-benar diblokir.
"""

from __future__ import annotations

import asyncio

import pytest

from app import providers

KEY = ("uji", "XAUUSD", "1h", 300)


def _contend_once() -> None:
    """Satu `asyncio.run` yang membuat dua tugas berebut lock yang sama."""

    async def body() -> None:
        providers._drop_locks_from_a_dead_loop()

        async def hold() -> None:
            async with providers._locks.setdefault(KEY, asyncio.Lock()):
                await asyncio.sleep(0)

        await asyncio.gather(hold(), hold())

    asyncio.run(body())


@pytest.fixture(autouse=True)
def _bersihkan():
    providers._locks.pop(KEY, None)
    yield
    providers._locks.pop(KEY, None)
    providers._locks_loop = None


def test_dua_asyncio_run_berturut_turut_tidak_melempar():
    _contend_once()
    _contend_once()  # ini yang melempar sebelum 30 Agustus 2026


def test_lock_lama_memang_dibuang_saat_loop_berganti():
    _contend_once()
    tertinggal = providers._locks.get(KEY)
    assert tertinggal is not None, "run pertama harus meninggalkan lock-nya"

    async def loop_kedua() -> None:
        providers._drop_locks_from_a_dead_loop()

    asyncio.run(loop_kedua())
    assert KEY not in providers._locks


def test_loop_yang_sama_menyimpan_locknya():
    """Dedup per key adalah alasan `_locks` ada; membuangnya tiap panggilan
    akan membuat satu burst tweak parameter jadi dua belas panggilan upstream."""

    async def body() -> tuple:
        providers._drop_locks_from_a_dead_loop()
        providers._locks.setdefault(KEY, asyncio.Lock())
        pertama = providers._locks[KEY]
        providers._drop_locks_from_a_dead_loop()
        return pertama, providers._locks.get(KEY)

    pertama, kedua = asyncio.run(body())
    assert pertama is kedua
