"""Menambah `source` tidak boleh menggeser satu angka pun pada default.

`tools/quant.clean` dan `tools/intrabar.resolved` memikul angka yang sudah
diterbitkan: gerbang departure +0,1105 R di `docs/QA-QUANT.md`, walk-forward 8
dari 8, dan seluruh `docs/detectors_costed.json`. Keduanya baru diberi parameter
`source` pada 30 Agustus 2026 supaya sebuah hasil bisa direplikasi di venue
kedua, dan satu-satunya cara perubahan itu aman adalah kalau jalur default-nya
identik.

`source` ADALAH PREFIX `history.load`, bukan nama venue bebas. Yang dikenal cuma
`mt5` dan `yahoo`. Binance dan Dukascopy adalah routing untuk simbol TELANJANG,
jadi keduanya dipilih dengan `source=""`. Menamainya "binance" terbaca benar dan
menghasilkan `binance:BTCUSDT`, yang dijawab Binance dengan HTTP 400.
"""

from __future__ import annotations

import inspect

from tools import intrabar, quant


def test_default_kedua_fungsi_tetap_mt5():
    assert inspect.signature(quant.clean).parameters["source"].default == "mt5"
    assert inspect.signature(intrabar.resolved).parameters["source"].default == "mt5"


def test_prefix_yang_sudah_ditulis_pemanggil_dihormati():
    """`mt5:XAUUSD` tidak boleh jadi `mt5:mt5:XAUUSD`."""
    assert intrabar._venue("mt5:XAUUSD", "mt5") == "mt5:XAUUSD"
    assert intrabar._venue("yahoo:XAUUSD", "mt5") == "yahoo:XAUUSD"


def test_source_kosong_berarti_telanjang():
    """Binance dan Dukascopy tidak punya prefix; keduanya routing telanjang."""
    assert intrabar._venue("BTCUSDT", "") == "BTCUSDT"
    assert intrabar._venue("BTCUSDT", "mt5") == "mt5:BTCUSDT"


def test_clean_membangun_ticker_yang_sama_seperti_sebelumnya(monkeypatch):
    """Yang dipaku BUKAN hasilnya, tapi string yang dikirim ke history.load."""
    dilihat: list[str] = []

    def fake_load(symbol, interval, bars, refresh=False):
        dilihat.append(symbol)
        return []

    monkeypatch.setattr(quant.history, "load", fake_load)
    monkeypatch.setattr(quant.history, "irregular_prefix", lambda rows, iv: 0)

    quant.clean("XAUUSD", "1h", 100)
    quant.clean("XAUUSD", "1h", 100, source="")
    quant.clean("yahoo:XAUUSD", "1h", 100)
    assert dilihat == ["mt5:XAUUSD", "XAUUSD", "yahoo:XAUUSD"]


def test_resolved_memakai_venue_yang_sama_untuk_kasar_dan_halus(monkeypatch):
    """Bar kasar venue A diselesaikan bar halus venue B adalah cacat instrumen.

    `tools/history.py` sudah mencatat bahwa mt5, yahoo dan telanjang adalah tiga
    INSTRUMEN berbeda, terukur 56 dolar berjarak pada menit yang sama.
    """
    kasar: list[str] = []
    halus: list[str] = []

    monkeypatch.setattr(intrabar, "clean",
                        lambda s, i, b, src: (kasar.append(f"{src}:{s}"), ([], 0, 0))[1])

    def fake_load(symbol, interval, bars, refresh=False):
        halus.append(symbol)
        return []

    monkeypatch.setattr(intrabar.history, "load", fake_load)
    intrabar.resolved("BTCUSD", "1h", "5m")
    assert kasar == ["mt5:BTCUSD"]
    assert halus == ["mt5:BTCUSD"]

    kasar.clear(); halus.clear()
    intrabar.resolved("BTCUSDT", "1h", "5m", source="")
    assert kasar == [":BTCUSDT"]
    assert halus == ["BTCUSDT"]
