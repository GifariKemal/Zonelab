"""`ORDER_BLOCK_ONLY` harus tetap sama dengan apa yang kodenya benar-benar baca.

Konstanta itu ada supaya runtime tidak perlu membedah AST tiap request. Harga
dari konstanta adalah ia bisa basi, dan test ini yang membayarnya: himpunannya
diturunkan ULANG dari sumber, lalu disamakan. Sebuah knob baru yang cuma dibaca
`detect_order_block` dan lupa didaftarkan akan kembali jadi 200 tanpa efek untuk
pembaca yang hanya menyalakan `fvg`, yang persis defect yang konstanta ini ada
untuk menutup.

Diturunkan dari SUMBER dan bukan dari pemanggilan, karena memanggil detektornya
dengan knob yang diubah lalu melihat outputnya bergerak hanya membuktikan knob
itu berpengaruh PADA DERET ITU - sebuah knob yang kebetulan tidak menggigit di
fixture akan lolos sebagai "tidak dibaca".
"""

from __future__ import annotations

import ast
import pathlib

from app.models import ImbalanceParams
from app.models.params import ORDER_BLOCK_ONLY

ROOT = pathlib.Path(__file__).resolve().parents[1] / "app" / "detect"

#: Ekor yang dipakai BERSAMA oleh setiap detektor imbalance. Bacaannya milik
#: semua, jadi ia tidak boleh masuk selisih antar detektor.
SHARED = ("_finish", "_present", "_gap", "_arrays")


def _fns(path: pathlib.Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def _reads(node: ast.FunctionDef) -> set[str]:
    return {
        n.attr
        for n in ast.walk(node)
        if isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id in ("params", "p")
    }


def test_order_block_only_matches_the_source() -> None:
    imb = _fns(ROOT / "imbalance.py")
    sd = _fns(ROOT / "supply_demand.py")

    tail: set[str] = set(_reads(sd["replay_lifecycle"]))
    for name in SHARED:
        tail |= _reads(imb[name])

    fvg = _reads(imb["detect_fvg"]) | tail
    ob = _reads(imb["detect_order_block"]) | tail

    declared = set(ImbalanceParams.model_fields)
    derived = (ob - fvg) & declared

    assert derived == set(ORDER_BLOCK_ONLY), (
        f"ORDER_BLOCK_ONLY basi. Kode membaca {sorted(derived)}, "
        f"konstanta menyebut {sorted(ORDER_BLOCK_ONLY)}"
    )


def test_every_declared_knob_is_read_by_someone() -> None:
    """Sebuah knob yang TIDAK ADA detektor bacanya adalah dead flexibility.

    `body_gap` gugur di sini pada 6 September 2026 dan dihapus; ia dibaca, tapi
    yang dibacanya hanya membuat kotak lebih lebar. Test ini menangkap kasus
    yang lebih sederhana: knob yang tidak dibaca siapa pun.
    """
    imb = _fns(ROOT / "imbalance.py")
    sd = _fns(ROOT / "supply_demand.py")
    # `inversion.py` DITAMBAHKAN 9 September 2026, dan itu memperlengkap
    # penjaga ini alih-alih melonggarkannya: ia juga memakai `ImbalanceParams`,
    # jadi sebelum baris ini setiap knob yang HANYA dibaca di sana akan
    # dilaporkan yatim. `merge_overlap_pct` adalah kasus pertamanya.
    inv = _fns(ROOT / "inversion.py")
    seen: set[str] = set(_reads(sd["replay_lifecycle"]))
    for name in imb:
        seen |= _reads(imb[name])
    for name in inv:
        seen |= _reads(inv[name])

    orphan = sorted(set(ImbalanceParams.model_fields) - seen)
    assert not orphan, f"knob tanpa pembaca: {orphan}"


def test_an_inert_order_block_knob_is_refused_not_ignored() -> None:
    """Perilakunya, bukan cuma konstantanya.

    `POST /api/draw` dengan `layers:["fvg"]` dan `imbalance.displacement_atr`
    diubah menjawab 200 dan menggambar chart default sampai 6 September 2026.
    Itu bentuk yang sama dengan insiden `source` yang membuat `DrawRequest`
    menolak field tak dikenal - bedanya field ini DIKENAL, cuma tak ada yang
    membacanya, jadi `extra="forbid"` lewat begitu saja.
    """
    import pytest

    from app.models import DrawRequest
    from app.models.params import ImbalanceParams

    # Default lolos: klien yang menyebar seluruh blok dari `/api/config` -
    # yang dilakukan frontend ter-ship - tidak boleh ikut ditolak.
    DrawRequest(layers=["fvg"], imbalance=ImbalanceParams())

    for name in ORDER_BLOCK_ONLY:
        blank = ImbalanceParams()
        current = getattr(blank, name)
        moved = (not current) if isinstance(current, bool) else current + 1
        with pytest.raises(ValueError, match=name):
            DrawRequest(layers=["fvg"], imbalance=ImbalanceParams(**{name: moved}))
        # Dan diterima begitu layer yang membacanya menyala.
        DrawRequest(layers=["order_block"], imbalance=ImbalanceParams(**{name: moved}))
        DrawRequest(layers=["breaker"], imbalance=ImbalanceParams(**{name: moved}))
