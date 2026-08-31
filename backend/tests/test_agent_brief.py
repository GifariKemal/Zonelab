"""Agent membaca brief, dan angkanya ikut jadi angka yang boleh dikutip.

Sebelum 30 Agustus 2026 ada tiga hal yang tidak saling kenal: `tools/brief`
menarik seluruh bacaan ke file, `app/agent.py` mencerna satu response
/api/draw, dan jalur order tidak menyebut agent sama sekali (`grep -c agent`
menjawab 0 pada `tools/autotrade.py` dan `tools/execute.py`).

Yang diuji di sini satu sambungan: brief yang dilampirkan ke context sampai ke
payload, dan karena `grounding.numbers_in` berjalan di string juga, angka di
dalamnya lolos grounding. Tanpa sambungan itu model yang mengutip brief dengan
BENAR dilaporkan mengarang, dan kegagalannya terbaca seperti halusinasi.

Fixture config diimpor dari `test_agent`, bukan disalin.
"""

from __future__ import annotations

import asyncio
import json

from app import agent
from app.grounding import check

from test_agent import good_config

BRIEF = """# Brief Zonelab: mt5:BTCUSD

Harga acuan 78134.490 pada timeframe 4h.

- day_of_week: yes [doctrine] Sunday: instrumen ini dagang saat CME tutup
- min_rr: yes [doctrine] reward 30.6R against the stop
"""


def _payload(monkeypatch, context) -> dict:
    """Payload yang dikirim ke model, tanpa memanggil endpoint mana pun."""
    seen: dict = {}

    async def fake_complete(cfg, messages):
        seen["messages"] = messages
        return "ok"

    monkeypatch.setattr(agent, "_complete", fake_complete)
    asyncio.run(agent.chat([{"role": "user", "content": "halo"}], context))
    system = seen["messages"][0]["content"]
    return json.loads(system.split("you may quote:\n", 1)[1])


def test_brief_sampai_ke_payload(tmp_path, monkeypatch):
    good_config(tmp_path, monkeypatch)
    payload = _payload(monkeypatch, {"draw": {}, "brief": BRIEF})
    assert payload["brief"] == BRIEF


def test_tanpa_brief_payload_tidak_punya_fieldnya(tmp_path, monkeypatch):
    good_config(tmp_path, monkeypatch)
    assert "brief" not in _payload(monkeypatch, {"draw": {}})


def test_brief_kosong_tidak_dilampirkan(tmp_path, monkeypatch):
    good_config(tmp_path, monkeypatch)
    assert "brief" not in _payload(monkeypatch, {"draw": {}, "brief": "   "})


def test_angka_brief_lolos_grounding_hanya_kalau_brief_ikut():
    kutipan = "Harga acuan 78134.490 dan reward 30.6R."
    assert check(kutipan, {"brief": BRIEF}).grounded is True
    # Payload yang sama tanpa brief menolak kutipan yang BENAR itu.
    assert check(kutipan, {"zones": []}).grounded is False


def test_sistem_prompt_menyebut_source_klausa(tmp_path, monkeypatch):
    """Prompt harus mengatakan `doctrine` lawan `measured`.

    Tiga belas dari tujuh belas klausa adalah doktrin. Agent yang membaca brief
    tanpa diberi tahu bedanya akan mengutip keduanya dengan bobot yang sama.
    """
    assert "doctrine" in agent.SYSTEM
    assert "measured" in agent.SYSTEM
