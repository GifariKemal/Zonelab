"""Setiap `_selftest()` di repo ini dijalankan oleh gate, bukan oleh niat baik.

KENAPA FILE INI ADA, dan tanggalnya 5 September 2026.

Sebelas modul di `app/` dan `tools/` punya fungsi `_selftest()` yang menyuntik
cacat lalu memeriksanya, ditulis persis mengikuti aturan repo ini bahwa gate
baru harus dibuktikan tidak kosong. Sembilan di antaranya sudah ada sebelum
hari ini. Dan `grep -rn selftest` di seluruh repo mengembalikan NOL pemanggil
di luar `if __name__ == "__main__"` masing-masing:

    $ grep -rn "selftest" --include=*.bat --include=*.md --include=*.mjs .
    (kosong sebelum hari ini)

Jadi kesebelasnya hanya jalan kalau ada manusia yang mengetik nama modulnya.
`pytest` tidak pernah menyentuhnya, dan `pytest` adalah gate yang dibaca
sebelum orang bilang selesai. Itu bentuk kegagalan yang sudah dua kali memakan
waktu di project ini dengan nama berbeda: sebuah pemeriksaan yang ADA, hijau,
dan tidak pernah dijalankan oleh apa pun yang menilai.

Yang ditutup file ini cuma satu hal: pemanggilnya. Isi tiap selftest tetap
milik modulnya.

TIDAK ADA YANG BOLEH MENYENTUH IO DI SINI. Ketiga `_selftest` yang sempat
dicurigai memanggil provider ternyata tidak: `load_aligned` di
`tools/psp_outcomes.py` dan `tools/ssmt_outcomes.py` ada di `_load`, fungsi
lain, dan satu-satunya "mt5" di `app/qt.py` adalah string di fixture. Kalau
suatu hari sebuah selftest mulai memanggil provider, ia akan membuat suite ini
bergantung pada terminal yang hidup, dan `docs/` sudah mencatat dua sebab gate
MT5 merah secara acak. Selftest yang butuh IO harus dipindah ke tool-nya
sendiri, bukan dibiarkan di sini.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Selftest yang SENGAJA tidak dijalankan di sini, dengan alasannya. Kosong
#: hari ini. Sebuah nama boleh masuk daftar ini hanya bersama alasan yang
#: menyebut apa yang ia butuhkan dan kenapa itu tidak boleh ada di suite.
EXCLUDED: dict[str, str] = {}


def _modules() -> list[str]:
    """Setiap modul di `app/` dan `tools/` yang mendefinisikan `_selftest`."""
    found = []
    for folder in ("app", "tools"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"^def _selftest\(", source, re.M):
                name = ".".join(path.relative_to(ROOT).with_suffix("").parts)
                if name not in EXCLUDED:
                    found.append(name)
    return found


MODULES = _modules()


def test_discovery_found_something():
    """Nol modul terdeteksi akan membuat file ini lolos secara HAMPA.

    Sebuah suite yang menjalankan nol test melaporkan hijau, dan itu persis
    penyakit yang file ini ada untuk mengobati. Angka bawahnya sengaja jauh di
    bawah jumlah sekarang: yang dijaga adalah "penemuannya masih bekerja",
    bukan "jumlahnya masih persis sama".
    """
    assert len(MODULES) >= 8, MODULES


@pytest.mark.parametrize("module", MODULES)
def test_selftest_passes(module: str):
    """Jalankan `_selftest()` modul itu. Ia melempar AssertionError kalau gagal."""
    importlib.import_module(module)._selftest()
