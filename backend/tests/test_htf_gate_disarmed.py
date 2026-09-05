"""`--htf-gate` tidak boleh diam-diam kembali diarmed tanpa angkanya ikut bicara.

Gerbang ini diarmed di `start.bat` pada 5 September 2026 SEBELUM ada satu angka
pun, lalu diukur pada hari yang sama dan hasilnya berlawanan: kohort yang ia
buang memberi +0,1265 R sementara yang ia simpan memberi +0,0129 R, n=1828.
Angka lengkapnya di `docs/ALUR-ORDER.md` bagian 3b.

Yang dijaga di sini BUKAN "flag itu haram". Operator boleh menjalankan apa pun
di akunnya sendiri, dan `tools/autotrade.py` masih menerima `--htf-gate`. Yang
dijaga: kalau ia menyala, angkanya HARUS ikut tercetak. Sebuah gerbang yang
kembali menyala diam-diam adalah persis keadaan yang seluruh dokumen ini ada
untuk mencegah.
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_start_bat_does_not_arm_the_gate_silently():
    """Kalau `AT_FLAGS` membawa `--htf-gate`, alasannya harus ada di file itu."""
    source = (ROOT / "start.bat").read_text(encoding="utf-8", errors="ignore")
    flags = re.search(r'^set "AT_FLAGS=(.*)"', source, re.M)
    assert flags, "AT_FLAGS tidak ketemu di start.bat; test ini jadi hampa"
    if "--htf-gate" not in flags.group(1):
        return
    assert "htf_gate_outcomes" in source or "ALUR-ORDER" in source, (
        "AT_FLAGS mengarmed --htf-gate tanpa satu baris pun di start.bat yang "
        "menunjuk ke angkanya. Gerbang ini sudah diukur dan hasilnya berlawanan"
    )


def test_arming_the_gate_prints_the_number():
    """Menyalakan flag harus berisik; mematikannya harus diam."""
    from tools.autotrade import HTF_GATE_MEASURED, warn_htf_gate

    quiet = io.StringIO()
    with redirect_stdout(quiet):
        warn_htf_gate(False)
    assert quiet.getvalue() == "", quiet.getvalue()

    loud = io.StringIO()
    with redirect_stdout(loud):
        warn_htf_gate(True)
    said = loud.getvalue()
    assert "PERINGATAN" in said
    # Angka yang menentukan harus benar-benar ikut, bukan sekadar kata
    # "sudah diukur" yang bisa dibaca sebagai formalitas.
    for number in ("1828", "0,1265", "0,0129", "2,638"):
        assert number in said, f"{number} hilang dari peringatan"
    assert "docs/htf_gate_outcomes.json" in HTF_GATE_MEASURED
