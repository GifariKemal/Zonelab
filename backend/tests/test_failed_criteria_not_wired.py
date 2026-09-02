"""Klausa yang terukur tidak memisahkan tidak boleh menghitung probabilitas atau arah.

`docs/checklist_outcomes.json` menilai ketujuh belas klausa `app/ict.py:evaluate`
plus skor agregatnya, di 1855 trade, 8 instrumen, zona 1 jam diselesaikan di bar
5 menit, biaya `exness_raw`, dengan kritis Bonferroni 3,267 atas 46 grup.

SATU dari tujuh belas melewati ambang: `dfr_side` pada t = -3,543, dan ia
melewatinya KE ARAH SEBALIKNYA. Dua klausa KONSTAN di seluruh populasi, jadi
keduanya tidak bisa jadi kriteria apa pun. Empat belas sisanya diukur dan tidak
memisahkan.

Skor agregatnya juga tidak: `H_A_met_score.separates` false, Spearman rho -0,027
mentah dan -0,035 setelah di-demean per instrumen (kedua tandanya SALAH), median
split +0,046 R pada t = 0,839 dengan dua paruh berbeda tanda, dan 5 dari 8 fold
positif. Kelima kriteria praregistrasinya gagal.

File ini menahan konsekuensinya, dengan cara yang sama
`tests/test_psp_not_wired_to_decisions.py` menahan PSP: objeknya tetap DIBACA
dan tetap dilaporkan, dan ia dilarang memutuskan. Perbedaan antara "digambar
sebagai bacaan" dan "ikut memutuskan" adalah perbedaan yang komentar tidak bisa
menegakkan.
"""

from __future__ import annotations

import pathlib
import re

from app.ict import DOCTRINE_CLAUSES, MEASURED_AGAINST, Rules
from tools.checklist_outcomes import CLAUSES


def _source(name: str) -> str:
    root = pathlib.Path(__file__).resolve().parent.parent
    return (root / name).read_text(encoding="utf-8")


def test_every_clause_carries_its_number():
    """Tiap klausa harus punya angka, dan "belum diukur" tidak boleh lagi.

    `tools/execute.py:warn_required` memisahkan dua kalimat: klausa doctrine
    diperingatkan sebagai belum diukur, klausa di `MEASURED_AGAINST`
    diperingatkan dengan angkanya. Sampai 2 September 2026 lima belas klausa
    yang SUDAH diukur masih jatuh ke kalimat pertama, dan docstring fungsi itu
    sendiri sudah menyebut akibatnya: operator yang membaca "belum diukur" akan
    menyalakannya sebagai taruhan.
    """
    missing = [c for c in CLAUSES if c not in MEASURED_AGAINST]
    assert not missing, (
        "klausa yang sudah diukur di docs/checklist_outcomes.json tapi tidak "
        f"membawa angkanya di MEASURED_AGAINST: {missing}"
    )


def test_no_clause_is_required_by_default():
    """Gerbangnya kosong, dan itu yang membuat empat belas kegagalan tidak menggigit.

    `Rules.required` kosong berarti tidak satu pun klausa menghentikan trade
    tanpa operator menyalakannya sendiri. Kalau default ini pernah terisi, yang
    menyala adalah filter yang terukur tidak memisahkan, dan populasi setiap
    angka di project ini berubah dalam satu commit.
    """
    assert Rules().required == (), (
        "Rules.required tidak lagi kosong, jadi sebuah klausa menggerbangi "
        f"trade secara default: {Rules().required}"
    )


def test_the_aggregate_score_does_not_order_candidates():
    """`met` TIDAK BOLEH JADI KUNCI URUT, dan ini yang paling load-bearing.

    `--max-orders` default 2, jadi urutan kandidat memilih dua dari sekian yang
    lolos gerbang. Sampai 2 September 2026 kunci utamanya `-Setup.met` di dua
    tempat, dan skor itu terukur tidak memisahkan hasil dengan tanda yang justru
    negatif.

    `app/ict.py` sendiri menulis "It does not sum the conditions into a score".
    `tools/execute.py` menjumlahkannya lewat `Setup.met`. Salah satu dari dua
    kalimat itu harus mengalah, dan yang punya angka yang menang.

    Yang diperiksa SOURCE-nya dan bukan hanya fungsi kuncinya, karena sebuah
    `sort` KETIGA di file itu tidak akan terlihat oleh test yang cuma memanggil
    `by_method`.
    """
    # DUA LAPIS, dan lapis pertama ditemukan hampa lewat suntikan. Versi
    # pertama menyaring baris yang memuat `.sort(` DAN `.met`; kunci urutnya
    # sekarang fungsi bernama, jadi `out.sort(key=by_method)` tidak memuat
    # `.met` sama sekali dan menaruh `met` kembali ke dalam `by_method` LOLOS
    # test itu - guard yang hampa untuk kasus yang persis ia ditulis untuk itu.
    #
    # Versi kedua menyaring SELURUH file, dan itu terlalu lebar: baris yang
    # mencetak `checklist {met}/17` sebagai laporan akan merah juga, dan gate
    # yang merah karena sebuah print adalah gate yang akan dimatikan.
    #
    # Yang dipakai: isi kedua FUNGSI KUNCI, plus baris sort mana pun. Perilaku
    # kuncinya sendiri sudah dikunci di `tests/test_order_key.py` lewat dua
    # kandidat yang hanya berbeda `met` dan harus punya kunci identik - itu yang
    # tidak bisa dipalsukan oleh grep apa pun.
    src = _source("tools/execute.py")
    bodies = []
    for name in ("def by_method(", "def by_method_ranked("):
        i = src.index(name)
        j = src.index(chr(10) + "def ", i + 1)
        bodies.append(src[i:j])
    offenders = [
        f"{name} memuat .met"
        for name, body in zip(("by_method", "by_method_ranked"), bodies)
        if ".met" in body
    ]
    offenders += [
        line.strip()
        for line in src.splitlines()
        if re.search(r"\.sort\(|sorted\(", line) and ".met" in line
    ]
    assert not offenders, (
        "skor checklist kembali ikut memutuskan urutan, dan ia terukur tidak "
        "memisahkan (docs/checklist_outcomes.json, separates false, rho "
        f"-0,035 demeaned): {offenders}"
    )


def test_the_two_constant_clauses_are_named_as_constant():
    """Konstan berarti nol informasi, dan itu harus terbaca di teksnya.

    `two_stage_confirmed` dan `draw_agrees` konstan di 1855 trade. Sebuah kolom
    yang tidak pernah berubah tidak memisahkan apa pun secara definisi, jadi
    kalimatnya harus menyebut KONSTAN alih-alih melaporkan sebuah t yang tidak
    ada.
    """
    for clause in ("two_stage_confirmed", "draw_agrees"):
        text = MEASURED_AGAINST[clause]
        assert "KONSTAN" in text, (
            f"{clause} konstan di populasinya tapi teksnya tidak mengatakannya: "
            f"{text[:80]}"
        )


def test_the_duplicate_pair_is_named_as_duplicate():
    """Dua klausa yang selalu memberi angka yang sama adalah satu klausa.

    `manipulation_seen` dan `manipulation_after_accumulation` keduanya n=1032,
    delta -0,135, t=-2,890. Bukan mirip: identik. Keduanya tetap menambah satu
    ke denominator skor checklist, jadi satu fakta tentang pasar dihitung dua
    kali, dan pembaca yang melihat 12/17 mengira dua belas hal terpisah lolos.
    """
    text = MEASURED_AGAINST["manipulation_after_accumulation"]
    assert "IDENTIK" in text, (
        "pasangan duplikat tidak dinamai sebagai duplikat di teksnya: "
        f"{text[:80]}"
    )


def test_the_one_clause_that_separates_is_not_quietly_promoted():
    """`dfr_side` memisahkan KE ARAH SEBALIKNYA, jadi ia tetap bukan gerbang.

    t = -3,543 lawan kritis 3,267, dan urutannya monoton ke arah salah: klausa
    GAGAL memberi +0,148 R, UNKNOWN +0,059, TERPENUHI -0,066. Membalik doktrinnya
    di atas satu pengukuran adalah overfit yang sama, cuma tandanya lain, dan
    `app/ict.py` sudah menuliskan alasannya: pemisahan itu belum di-walk-forward
    per klausa.
    """
    assert "dfr_side" in MEASURED_AGAINST
    assert "SEBALIKNYA" in MEASURED_AGAINST["dfr_side"]
    assert "dfr_side" not in Rules().required
    # Ia tetap klausa doctrine, karena yang berubah angkanya dan bukan asalnya.
    assert "dfr_side" in DOCTRINE_CLAUSES
