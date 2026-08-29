"""Dua permukaan checklist, dan jaminan bahwa keduanya membaca satu sumber.

Zonelab punya DUA hal yang wajar disebut checklist, dan menyamakannya adalah
kesalahan yang audit 29 Agustus 2026 sendiri lakukan lalu koreksi:

  `app/ict.py`        klausa bernama dengan `met` boolean, plus kosakata
                      gerbang `Rules.required`. Ini yang bisa MEMBLOKIR trade,
                      dan ia hanya terjangkau dari `tools/execute.py`,
                      `tools/autotrade.py` dan `tools/conditioned.py`.
  `app/checklist.py`  `ChecklistReport`, bacaan terstruktur atas pertanyaan
                      pra-trade pemiliknya, sengaja TANPA pass/fail
                      keseluruhan. Ini yang dilihat web app.

Keduanya menjawab pertanyaan berbeda, jadi menyatukannya bukan perbaikan. Yang
BENAR-BENAR berbahaya adalah kalau keduanya mulai menghitung fakta yang sama
lewat dua jalur, karena dua jalur yang boleh berbeda pada akhirnya akan
berbeda, dan repo ini punya daftar panjang insiden dengan bentuk itu: satu
daftar nama layer yang ditulis dua kali, satu `PARAMS_FOR` yang menduplikasi
registry, satu pasangan warna yang hidup di lima file.

Hari ini keduanya bermuara di `app/quarterly.py` yang sama. File ini menjaga
supaya itu tetap benar.
"""

from __future__ import annotations

import ast
import pathlib

#: Fakta yang KEDUA permukaan laporkan, dan fungsi tunggal yang menghasilkannya.
#: Kalau salah satu permukaan berhenti memakai fungsi ini, ia mulai punya
#: jawabannya sendiri, dan dua jawaban untuk satu pertanyaan adalah persis
#: kondisi yang membuat UI dan order bisa tidak sepakat tanpa ada yang tahu.
SHARED = ("defining_range", "manipulation_done")

ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _imported_from_quarterly(path: pathlib.Path) -> set[str]:
    """Nama apa saja yang file ini ambil dari `app.quarterly`.

    Dibaca lewat AST dan bukan lewat regex, karena `import quarterly` lalu
    `quarterly.defining_range(...)` dan `from .quarterly import defining_range`
    adalah dua bentuk yang sama sahnya dan sebuah regex akan melihat satu saja.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("quarterly"):
            names |= {a.name for a in node.names}
        if isinstance(node, ast.ImportFrom) and node.module is None:
            # `from . import quarterly`
            module_aliases |= {a.asname or a.name for a in node.names
                               if a.name == "quarterly"}
    if module_aliases:
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in module_aliases):
                names.add(node.attr)
    return names


def test_both_checklist_surfaces_read_the_same_quarterly_functions():
    """Satu sumber untuk manipulasi dan defining range, dibuktikan per file.

    `app/checklist.py` memanggilnya langsung. `app/ict.py` tidak memanggil apa
    pun: ia fungsi murni atas sebuah state dict, dan state itu disusun
    `app/conditions.py`, yang memanggil dua fungsi yang sama. Jadi jalur yang
    diperiksa di sini adalah checklist lawan conditions.
    """
    web = _imported_from_quarterly(ROOT / "checklist.py")
    cli = _imported_from_quarterly(ROOT / "conditions.py")

    for name in SHARED:
        assert name in web, (
            f"app/checklist.py tidak lagi mengambil {name} dari app/quarterly. "
            "Kalau ia punya salinannya sendiri, laporan web dan gerbang CLI "
            "bisa menjawab berbeda untuk pertanyaan yang sama."
        )
        assert name in cli, (
            f"app/conditions.py tidak lagi mengambil {name} dari app/quarterly. "
            "State dict yang dibaca app/ict.py akan punya sumber kedua."
        )


def test_neither_surface_defines_its_own_copy_of_the_shared_readings():
    """Mengimpor nama yang benar tidak cukup kalau ada definisi lokal yang
    membayanginya. Ini bentuk drift yang paling sulit dilihat di diff: impor
    lama tetap ada di atas, dan fungsi baru dengan nama sama muncul di bawah.
    """
    for filename in ("checklist.py", "conditions.py", "ict.py"):
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        local = {n.name for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        clash = sorted(local & set(SHARED))
        assert not clash, (
            f"app/{filename} mendefinisikan {clash}, yang membayangi fungsi "
            "dengan nama sama di app/quarterly.py. Dua implementasi untuk satu "
            "pertanyaan adalah dua jawaban yang menunggu untuk berbeda."
        )


def test_only_one_of_the_two_surfaces_can_block_a_trade():
    """Perbedaan yang HARUS tetap ada, dipaku supaya tidak hilang diam-diam.

    Kosakata gerbang hidup di `app/ict.py` saja. `app/checklist.py` sengaja
    tidak punya pass/fail keseluruhan, dan `ChecklistReport` menyatakan alasannya
    sendiri: item-itemnya klaim terpisah dengan provenance terpisah, dan
    meruntuhkannya jadi satu boolean akan menyembunyikan mana yang menanggung
    beban, sekaligus menyajikan checklist yang dicentang tangan seolah engine
    sudah memvalidasinya.

    Kalau suatu saat `checklist.py` mendapat `required`, itu keputusan besar dan
    harus dibuat sadar, bukan lolos di dalam diff.
    """
    web = (ROOT / "checklist.py").read_text(encoding="utf-8")
    gate = (ROOT / "ict.py").read_text(encoding="utf-8")

    assert "required" in gate, "kosakata gerbang hilang dari app/ict.py"
    assert "required" not in web, (
        "app/checklist.py sekarang menyebut `required`. Permukaan web sengaja "
        "tidak bisa memblokir trade; kalau itu berubah, ubahlah dengan sengaja "
        "dan perbarui test ini beserta alasannya."
    )
