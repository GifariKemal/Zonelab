"""`dfr_side` diukur, memisahkan, dan tandanya TERBALIK.

Diukur 30 Agustus 2026 di 8 instrumen, zona 1h diselesaikan di bar 5 menit,
n=1855, biaya `exness_raw`, bukti di `docs/checklist_outcomes.json`:

    klausa TERPENUHI   n=1141   exp R -0,0660   delta -0,1676   t=-3,54
    klausa GAGAL       n= 341   exp R +0,1481   delta +0,1832   t=+3,41
    tidak terbaca      n= 373   exp R +0,0591   delta +0,0759   t=+1,20

Kritis Bonferroni 3,267 untuk 46 grup. Kedua paruh setanda, 8 dari 8 instrumen
setanda di sisi True, dan t tetap -3,32 setelah di-demean per instrumen.

KLAUSANYA TIDAK DIBALIK, dan itu keputusan yang dipaku di sini. Pemisahan ini
belum di-walk-forward per klausa; `docs/checklist_outcomes.json` membawa fold
hanya untuk skor agregat. Standar repo ini adalah gerbang menyala setelah lolos
walk-forward. Membalik doktrin di atas satu pengukuran adalah overfit yang sama,
cuma tandanya lain.
"""

from __future__ import annotations

from app.ict import DOCTRINE_CLAUSES, MEASURED_AGAINST, Rules
from tools.execute import warn_required


def test_dfr_side_terdaftar_sebagai_diukur_berlawanan():
    assert "dfr_side" in MEASURED_AGAINST
    catatan = MEASURED_AGAINST["dfr_side"]
    for angka in ("-0,0660", "1141", "-3,54", "+0,1481", "341", "3,267"):
        assert angka in catatan, f"{angka} hilang dari catatan dfr_side"
    assert "checklist_outcomes.json" in catatan


def test_klausanya_tidak_dibalik_di_kode():
    """Kalau suatu hari ia dibalik, itu harus keputusan sadar, bukan drift."""
    from app.ict import evaluate
    import inspect

    src = inspect.getsource(evaluate)
    assert '"dfr_side", ok, "doctrine"' in src


def test_mewajibkannya_memicu_peringatan_keras_bukan_yang_lunak(capsys):
    warn_required(Rules(required=("dfr_side",)))
    keluar = capsys.readouterr().out
    assert "SUDAH diukur dengan hasil yang berlawanan" in keluar
    assert "belum diukur" not in keluar
    assert "checklist_outcomes.json" in keluar


def test_ote_tetap_menunjuk_dokumennya_sendiri(capsys):
    """Satu peta bukti untuk dua klausa harus memberi jawaban berbeda."""
    warn_required(Rules(required=("ote",)))
    keluar = capsys.readouterr().out
    assert "PRAREGISTRASI-YATIM.md" in keluar
    assert "checklist_outcomes.json" not in keluar


def test_dfr_side_dikeluarkan_dari_peringatan_doctrine_polos():
    """Ia doctrine DAN measured-against; yang kedua harus menang."""
    assert "dfr_side" in DOCTRINE_CLAUSES
    polos = [c for c in ("dfr_side",)
             if c in DOCTRINE_CLAUSES and c not in MEASURED_AGAINST]
    assert polos == []
