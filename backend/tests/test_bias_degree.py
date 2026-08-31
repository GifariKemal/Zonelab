"""Derajat bias yang digerbangi bisa dipilih, dan pilihannya mengubah keputusan.

Sampai 30 Agustus 2026 `Rules.bias_degree` default `"bias_4h"` dan tidak ada
satu pun flag di `tools/execute.py` atau `tools/autotrade.py` yang bisa
mengubahnya. Zona 15 menit digerbangi bacaan 4 jam.

Terukur pada 30 Agustus 2026 pukul 19:00, BTCUSD 15m, harga 78647,30 setelah
naik 1,36 persen dalam 24 jam:

    bias_1h +1, bias_1d +1, bias_4h -1

    bias_4h   10 kandidat,  1 lolos   {'supply': 1}
    bias_1h   10 kandidat,  9 lolos   {'demand': 9}
    bias_1d   10 kandidat,  9 lolos   {'demand': 9}

MENURUNKAN DERAJATNYA BUKAN PERBAIKAN YANG TERBUKTI, dan test ini tidak
mengklaim begitu. H7 mengukur kontribusi zona di atas bias ini NOL, jadi derajat
mana pun adalah pilihan operator. Yang dipaku di sini cuma dua: pilihannya ADA,
dan nilai yang salah ketik ditolak keras bukan jadi klausa unknown yang senyap.
"""

from __future__ import annotations

import pytest

from app.bias import DEGREES
from app.ict import BIAS_DEGREES, Rules, evaluate

from test_ict import stack, state, zone


def _bias_clause(bias_degree: str, **over):
    conditions = evaluate(zone(), state(**over), stack(),
                          Rules(bias_degree=bias_degree))
    return next(c for c in conditions if c.name == "bias_agrees")


def test_setiap_derajat_bias_punya_nama_klausa_yang_sah():
    assert BIAS_DEGREES == tuple(f"bias_{d}" for d in DEGREES)
    assert "bias_4h" in BIAS_DEGREES
    assert "bias_15m" in BIAS_DEGREES


def test_defaultnya_tetap_4h():
    """Perubahan default adalah perubahan perilaku produksi, bukan refactor."""
    assert Rules().bias_degree == "bias_4h"


def test_derajat_yang_dipilih_yang_dibaca_bukan_yang_default():
    """Dua derajat yang BERTENTANGAN pada bar yang sama harus memberi jawaban
    yang berbeda. Ini bentuk persis dari BTCUSD 19:00: 1h bullish, 4h bearish."""
    over = {"bias_4h": -1, "bias_1h": 1}
    empat_jam = _bias_clause("bias_4h", **over)
    satu_jam = _bias_clause("bias_1h", **over)
    assert empat_jam.met != satu_jam.met
    assert "bias_4h" in empat_jam.detail
    assert "bias_1h" in satu_jam.detail


def test_derajat_yang_tidak_terbaca_jadi_unknown_bukan_diam_diam_lolos():
    klausa = _bias_clause("bias_15m")
    assert klausa.met is None
    assert "bias_15m" in klausa.detail


@pytest.mark.parametrize("tool", ["tools.autotrade", "tools.execute"])
def test_kedua_tool_mengekspos_flagnya(tool):
    """Knob yang cuma ada di dataclass adalah knob yang tak bisa diputar."""
    import importlib
    mod = importlib.import_module(tool)
    import inspect
    src = inspect.getsource(mod)
    assert '"--bias-degree"' in src
    assert "bias_degree=args.bias_degree" in src
