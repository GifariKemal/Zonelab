"""Dua rig menjawab pertanyaan yang sama dan pada 2 September 2026 berlawanan.

Rig Python bilang fvg 30m +0,2188 R dengan t lawan nol +8,53 dan 8 dari 8 fold.
Strategy Tester bilang `ZonelabFVG_XAUUSD_M30` Profit Factor 0,86 di 622 trade.
Enam dari delapan sel tidak setuju TANDA-nya.

Yang dites di sini pembacaan tandanya sendiri, karena seluruh perbandingan itu
berdiri di atasnya: satu salah-baca "1 234.5" atau satu None yang dihitung
sebagai setuju akan mengubah verdict tanpa satu angka pengukuran pun berubah.
"""

from __future__ import annotations

import tools.mt5_python_parity as parity


def test_profit_factor_is_read_including_the_thousands_space():
    """MT5 menulis ribuan dengan SPASI, dan `float("1 234.5")` meledak.

    Report-nya sendiri memuat "3 441.36" di kolom drawdown, jadi format itu
    bukan hipotesis. Sebuah PF yang gagal di-parse mengembalikan None, dan None
    yang dihitung sebagai setuju akan menyembunyikan ketidaksepakatan.
    """
    assert parity._pf_sign({"Profit Factor": "1.34"}) == 1
    assert parity._pf_sign({"Profit Factor": "0.86"}) == -1
    assert parity._pf_sign({"Profit Factor": "1.00"}) == 0
    assert parity._pf_sign({"Profit Factor": "1 234.5"}) == 1


def test_an_unreadable_side_is_never_agreement():
    """Tidak terbaca bukan setuju, dan itu bedanya penolakan dari kelalaian."""
    assert parity._pf_sign({"Profit Factor": None}) is None
    assert parity._pf_sign({}) is None
    assert parity._pf_sign({"Profit Factor": "n/a"}) is None
    assert parity._r_sign({"exp_r": None}) is None
    assert parity.compare({"mql5_window": {"exp_r": None}},
                          {"Profit Factor": "1.34"})["agree"] is None
    assert parity.compare({"mql5_window": {}}, {"error": "x"})["agree"] is None


def test_the_real_disagreement_reads_as_disagreement():
    """Angka nyatanya, dan ia harus keluar sebagai TIDAK setuju.

    fvg XAUUSD 30m: Python +0,3024 R di jendela yang sama, MQL5 PF 0,86.
    supply_demand XAUUSD 30m: Python -0,0080, MQL5 PF 1,34. Keduanya
    berlawanan, dan keduanya harus terbaca begitu.
    """
    assert parity.compare({"mql5_window": {"exp_r": 0.3024}},
                          {"Profit Factor": "0.86"})["agree"] is False
    assert parity.compare({"mql5_window": {"exp_r": -0.0080}},
                          {"Profit Factor": "1.34"})["agree"] is False
    # Dan yang memang sepakat harus terbaca sepakat: ifvg XAUUSD +0,1659 lawan
    # PF 1,14.
    assert parity.compare({"mql5_window": {"exp_r": 0.1659}},
                          {"Profit Factor": "1.14"})["agree"] is True


def test_the_window_is_pinned_to_the_mql5_run():
    """Jendelanya dipatok, bukan dibaca dari file yang bisa di-regenerate.

    Kalau `docs/mt5-backtest.json` dijalankan ulang dengan tanggal lain,
    perbandingan ini harus TETAP membandingkan periode yang sama atau ia
    berhenti membandingkan apa pun. Angkanya karena itu konstanta di sini.
    """
    assert parity.WINDOW == ("2026.01.01", "2026.08.31")
    assert parity._epoch("2026.01.01") == 1767225600
    # Dan pemetaan EA ke detektor tidak boleh melenceng: sebuah sel yang salah
    # dipetakan akan membandingkan fvg ke supply_demand tanpa error.
    assert parity.EXPERT["fvg"] == "ZonelabFVG"
    assert parity.EXPERT["supply_demand"] == "ZonelabSD"
    assert parity.EXPERT["order_block"] == "ZonelabOB"
    assert parity.EXPERT["ifvg"] == "ZonelabIFVG"
    assert parity.PERIOD["30m"] == "M30"


def test_the_ea_counters_are_captured_from_a_log_delta():
    """Counter EA hilang di dua lapis sampai 2 September 2026.

    `Print` tidak masuk ke report `.htm`, dan log agent tester ditulis UTF-16LE
    di pohon terpisah dari data folder terminal. 260 report di `reports/` tidak
    memuat satu pun. Yang dikunci di sini: bacaannya DELTA, karena log harian
    memuat setiap sel yang sudah jalan hari itu dan membaca seluruh file akan
    melaporkan counter sel lain sebagai milik sel ini.
    """
    import inspect

    from tools import mt5_backtest

    src = inspect.getsource(mt5_backtest.read_counters)
    assert "fh.seek(start)" in src, "harus membaca dari offset, bukan dari awal"
    assert "utf-16-le" in src, "MT5 menulis UTF-16LE"
    assert "hits[-1]" in src, "OnDeinit mencetak di akhir; ambil yang terakhir"
    assert "skipped no-target" in mt5_backtest.COUNTERS
    assert "zones fresh" in mt5_backtest.COUNTERS
    # Dan ukurannya diambil SEBELUM terminal dijalankan, atau delta-nya nol.
    cell = inspect.getsource(mt5_backtest.run_cell)
    assert cell.index("before_logs = _agent_log_sizes()") < cell.index(
        "subprocess.run("), "ukuran log harus diambil sebelum tester jalan"


def test_reading_a_log_delta_finds_only_the_new_lines(tmp_path):
    """Dan itu diuji pada file sungguhan, bukan pada pembacaan source saja."""
    from tools import mt5_backtest

    log = tmp_path / "x" / "Agent-127.0.0.1-3000" / "logs" / "20260902.log"
    log.parent.mkdir(parents=True)
    old = "orders placed: 111\nzones fresh: 999\n".encode("utf-16-le")
    log.write_bytes(old)
    before = {log: len(old)}

    with open(log, "ab") as fh:
        fh.write("orders placed: 650\nskipped no-target: 75\n".encode("utf-16-le"))

    # `_agent_log_sizes` memindai APPDATA, jadi jalur itu ditambal ke tmp_path.
    original = mt5_backtest.AGENT_LOGS
    try:
        mt5_backtest.AGENT_LOGS = tmp_path
        got = mt5_backtest.read_counters(before)
    finally:
        mt5_backtest.AGENT_LOGS = original
    assert got == {"orders_placed": 650, "skipped_no_target": 75}, got
    assert "zones_fresh" not in got, "baris lama tidak boleh ikut terbaca"
