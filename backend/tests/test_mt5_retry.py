"""Tabrakan klien MT5 ditunggu, bukan diteruskan sebagai kegagalan.

Terminal MetaTrader 5 melayani satu klien Python pada satu waktu. Dengan daemon
auto-trade dan uvicorn 8100 sama sama hidup, proses ketiga menerima
`(-6, 'Terminal: Authorization failed')`. Diukur 30 Agustus 2026 pada proses
baru, 30 panggilan `history.load` berturut turut:

    tanpa retry   0 sukses, 30 gagal, 0,3 detik
    dengan retry  30 sukses, 0 gagal, 0,4 detik

Yang mahal bukan retry-nya. Yang mahal adalah gate yang merah karena rebutan
socket, lalu dibaca sebagai regresi kode.
"""

from __future__ import annotations

import pytest

from app.providers import mt5 as mt5mod


@pytest.fixture
def no_sleep(monkeypatch):
    """Jadwal jedanya dicatat, bukan dijalani."""
    waited: list[float] = []
    monkeypatch.setattr(mt5mod.time, "sleep", waited.append)
    return waited


def _initialize_that_fails(times: int, monkeypatch):
    calls = {"n": 0}

    def fake() -> bool:
        calls["n"] += 1
        return calls["n"] > times

    monkeypatch.setattr(mt5mod.mt5, "initialize", fake)
    return calls


def test_sukses_pertama_tidak_menunggu_sama_sekali(monkeypatch, no_sleep):
    _initialize_that_fails(0, monkeypatch)
    assert mt5mod._initialize_with_retry() is True
    assert no_sleep == []


def test_gagal_sekali_lalu_sukses(monkeypatch, no_sleep):
    calls = _initialize_that_fails(1, monkeypatch)
    assert mt5mod._initialize_with_retry() is True
    assert calls["n"] == 2
    assert no_sleep == [0.1]


def test_menyerah_setelah_seluruh_jadwal_habis(monkeypatch, no_sleep):
    calls = _initialize_that_fails(99, monkeypatch)
    assert mt5mod._initialize_with_retry() is False
    # Percobaan pertama tanpa jeda, lalu satu percobaan per jeda.
    assert calls["n"] == len(mt5mod._RETRY_WAITS) + 1
    assert no_sleep == list(mt5mod._RETRY_WAITS)


def test_anggaran_tunggunya_dibawah_empat_detik():
    """Ini berjalan di dalam request `/api/draw`, jadi angkanya mengikat."""
    assert sum(mt5mod._RETRY_WAITS) == pytest.approx(3.85)


def test_connect_mengangkat_error_terminal_yang_sebenarnya(monkeypatch, no_sleep):
    """Retry yang habis TIDAK boleh menelan `last_error()`.

    Pesan 'Authorization failed' itu satu satunya petunjuk bahwa sebabnya
    rebutan klien dan bukan terminal yang mati.
    """
    _initialize_that_fails(99, monkeypatch)
    monkeypatch.setattr(mt5mod.mt5, "last_error",
                        lambda: (-6, "Terminal: Authorization failed"))
    provider = mt5mod.MT5Provider()
    provider._connected = False
    with pytest.raises(mt5mod.ProviderError, match="Authorization failed"):
        provider._connect()


def test_connect_ikut_menunggu_bukan_cuma_helpernya(monkeypatch, no_sleep):
    """Yang mengikat `_connect` ke retry, bukan cuma helper yang berdiri sendiri.

    Tanpa test ini, melepas retry dari `_connect` dan kembali ke
    `mt5.initialize()` telanjang tidak membuat satu gate pun merah: keempat
    test di atas menguji helpernya, dan helper yang tidak dipanggil siapa pun
    tetap hijau.
    """
    calls = _initialize_that_fails(1, monkeypatch)
    monkeypatch.setattr(mt5mod.mt5, "terminal_info",
                        lambda: type("I", (), {"connected": True})())
    provider = mt5mod.MT5Provider()
    provider._connected = False
    assert provider._connect() is True
    assert calls["n"] == 2, "gagal sekali lalu sukses harus lolos, bukan diangkat"


def test_kedipan_link_broker_ditunggu(monkeypatch, no_sleep):
    """Link yang putus sesaat tidak boleh mematikan request.

    Diukur 30 Agustus 2026, 40 sampel selama 10 detik: `connected` False pada
    17 sampel, 43 persen. Menolak pada kedipan pertama berarti menolak hampir
    separuh request, dan itulah yang membuat gate merah tanpa sebab kode.
    """
    calls = {"n": 0}

    def flapping():
        calls["n"] += 1
        return type("I", (), {"connected": calls["n"] > 2})()

    monkeypatch.setattr(mt5mod.mt5, "terminal_info", flapping)
    assert mt5mod._broker_link_up() is True
    assert calls["n"] == 3


def test_link_yang_benar_benar_mati_tetap_diangkat(monkeypatch, no_sleep):
    monkeypatch.setattr(mt5mod.mt5, "terminal_info",
                        lambda: type("I", (), {"connected": False})())
    assert mt5mod._broker_link_up() is False
    assert no_sleep == list(mt5mod._RETRY_WAITS)


def test_terminal_info_none_diperlakukan_sebagai_mati(monkeypatch, no_sleep):
    monkeypatch.setattr(mt5mod.mt5, "terminal_info", lambda: None)
    assert mt5mod._broker_link_up() is False


def test_connect_ikut_menunggu_kedipan_bukan_cuma_helpernya(monkeypatch, no_sleep):
    """Mengikat `_connect` ke `_broker_link_up`, bukan cuma helpernya.

    Tanpa ini, kembali ke pemeriksaan `terminal_info()` sekali jalan tidak
    membuat satu gate pun merah.
    """
    monkeypatch.setattr(mt5mod.mt5, "initialize", lambda: True)
    calls = {"n": 0}

    def flapping():
        calls["n"] += 1
        return type("I", (), {"connected": calls["n"] > 1})()

    monkeypatch.setattr(mt5mod.mt5, "terminal_info", flapping)
    provider = mt5mod.MT5Provider()
    provider._connected = False
    assert provider._connect() is True
