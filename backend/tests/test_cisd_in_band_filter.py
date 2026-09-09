"""Filter CISD-di-dalam-band, dan batas di mana ia berhenti berlaku.

Pemisahan terkuat yang repo ini punya: order block yang memuat level CISD baru
di dalam band-nya menghasilkan -0,1119 R, yang tanpanya +0,0244 R, delta
-0,1363 dengan Welch t = -7,07 lawan kritis 2,24 di n=8.170, dan kedelapan fold
walk-forward bertanda sama (`docs/csid_ob_intrabar.json`).

Yang dikunci di sini bukan cuma bahwa filternya bekerja. Ketiga syaratnya harus
mengikat masing-masing, karena definisi yang bergeser sedikit menyaring
populasi lain dan angka di atas tidak berlaku untuknya. Dan yang terakhir
mengunci batasnya: di bar KEPUTUSAN kondisinya hampir selalu salah, jadi flag
itu tidak boleh dibaca sebagai "angka -0,1363 sudah terpasang".
"""

from __future__ import annotations

import pytest

from app.cisd import RECENT_CISD_BARS, CISD, recent_in_band

STEP = 1800
NOW = 1_000_000


def ev(level: float, time: int) -> CISD:
    """CISD yang cuma dua field-nya dibaca `recent_in_band`."""
    # `run_extreme` tidak dipakai `recent_in_band` - ia menyaring atas `level`
    # dan `time` saja - jadi di sini ia cuma harus ADA. Diberi nilai yang
    # konsisten dengan arah +1 (run turun, ekstremnya di bawah level) supaya
    # fixture-nya tidak menyandi kotak yang mustahil.
    return CISD(index=0, time=time, direction=1, level=level,
                run_start=0, run_end=1, run_length=2, run_extreme=level - 1.0)


def test_a_recent_level_inside_the_band_is_found():
    assert recent_in_band(100.0, 110.0, [ev(105.0, NOW - 10 * STEP)], NOW, STEP)


def test_the_band_binds():
    """Level di luar band tidak dihitung, meskipun baru."""
    assert not recent_in_band(100.0, 110.0, [ev(120.0, NOW)], NOW, STEP)
    # Dan tepinya termasuk, sesuai `bottom <= level <= top` di studinya.
    assert recent_in_band(100.0, 110.0, [ev(110.0, NOW)], NOW, STEP)
    assert recent_in_band(100.0, 110.0, [ev(100.0, NOW)], NOW, STEP)


def test_the_recency_binds_and_it_is_the_whole_tightening():
    """Level basi di dalam band tidak dihitung.

    Separuh kebaruan ini yang membuat kondisinya tidak degenerate: tanpanya 95
    persen order block memuat SEBUAH level CISD, dan diukur pada XAUUSD 30m 18
    dari 20 kandidat kena.
    """
    just_inside = NOW - RECENT_CISD_BARS * STEP
    assert recent_in_band(100.0, 110.0, [ev(105.0, just_inside)], NOW, STEP)
    assert not recent_in_band(100.0, 110.0, [ev(105.0, just_inside - 1)],
                              NOW, STEP)


def test_the_future_binds_and_that_is_the_anti_lookahead_half():
    """Level yang belum lahir di `now` tidak boleh terbaca.

    `0 <= now - e.time` yang menjaganya. Tanpa sisi ini filternya membaca masa
    depan, dan setiap angka yang diukur di atasnya jadi bocor.
    """
    assert not recent_in_band(100.0, 110.0, [ev(105.0, NOW + STEP)], NOW, STEP)


def test_step_scales_the_window_not_the_bar_count():
    """Jendelanya 50 BAR, jadi ia melebar bersama timeframe-nya.

    Kalau ia dipatok ke detik, 50 bar di 30 menit dan 50 bar di 1 jam akan
    menyaring dua populasi berbeda dengan satu nama.
    """
    stale = NOW - 60 * STEP
    assert not recent_in_band(100.0, 110.0, [ev(105.0, stale)], NOW, STEP)
    assert recent_in_band(100.0, 110.0, [ev(105.0, stale)], NOW, STEP * 2)


def test_the_orderable_list_holds_exactly_the_measured_one():
    """PENJAGA DAFTAR, dan ia sudah berubah tiga kali.

    Mula-mula ia menuntut `"fvg" not in ORDERABLE_LAYERS`. Lalu `fvg` masuk
    pada 2 September 2026 atas +0,2188 R dengan walk-forward 8 dari 8 dari
    `fvg_inverted`. Pada 7 September 2026 ia keluar lagi, dan kali ini bukan
    karena pertanyaannya berubah melainkan karena angkanya rontok: angka 8 dari
    8 itu diukur lewat `replay_lifecycle` yang memeriksa pecah SEBELUM sentuh,
    jadi ia menghitung populasi yang jalur order tidak akan pernah dapat.
    Setelah urutannya diperbaiki, rig yang sama membaca +0,0919 R dengan
    t=+1,88 - di bawah ambang Bonferroni 3,241 yang dipakai sweep itu sendiri.
    Diukur ulang di bracket produksi pada 1 jam dan 4 jam, XAU dan BTC
    digabung, tidak satu pun dari enam varian lolos: baseline PF 0,954 di
    -0,0271 R, konfigurasi ter-ship 0,969 di -0,0181 R, terbaik 1,032 di
    +0,0183 R dengan walk-forward 3 dari 8. `docs/QA-FVG-TV.md`.

    `order_block` menyusul keluar di hari yang sama dan alasannya lebih keras
    daripada fvg: ia bukan "belum terbukti", ia terukur RUGI. Bracket produksi,
    XAUUSD 4h, PF 0,495 dan exp_r -0,2897 R pada t = -5,07 - satu-satunya |t| di
    atas 2 di seluruh sapuan tiga layer kali tiga sel, dan arahnya salah.

    Yang dikunci di sini tetap sama: daftarnya berisi TEPAT layer yang punya
    angka, dan yang berikutnya tidak bisa masuk tanpa test ini berubah warna.
    Tersisa satu, dan satu itu pun cuma positif di satu dari tiga sel.

    KEEMPAT KALI, 9 September 2026: daftarnya sekarang KOSONG. `supply_demand`
    dimatikan atas keputusan pemilik - "kita masih membangun detector" - dan
    angkanya mendukung: layer itu sendiri 5 dari 8 di aturan yang menggerbangi
    status ini, jadi `orderable=True` berdiri di atas keputusan lama dan bukan
    di atas aturan yang berlaku. Nol dari DELAPAN detektor lolos aturan itu.

    Yang dikunci tetap sama bentuknya: daftar ini berisi tepat layer yang punya
    angka, dan sekarang tidak ada. Menyalakan yang berikutnya tetap harus
    membuat test ini berubah warna lebih dulu.
    """
    from tools.execute import ORDERABLE_LAYERS
    assert set(ORDERABLE_LAYERS) == set()
    for absent in ("supply_demand", "fvg", "order_block", "ifvg", "breaker",
                   "ote", "cisd_zone", "liquidity_pool"):
        assert absent not in ORDERABLE_LAYERS


def test_an_unmeasured_layer_is_refused_loudly():
    """Layer di luar daftar harus gagal, bukan diam-diam jatuh ke default.

    Diam di sini akan memasang order pada populasi yang tidak pernah diukur
    sambil melaporkan nama layer yang diminta.
    """
    from tools.execute import candidates
    with pytest.raises(ValueError, match="ORDERABLE_LAYERS"):
        candidates("mt5:XAUUSD", "30m", 10, layer="ifvg")


def test_a_layer_that_cannot_be_ordered_keeps_its_gate_direction():
    """MEMATIKAN `orderable` TIDAK BOLEH MEMBALIK KALIMAT GERBANGNYA.

    `GATE_DIRECTION` diturunkan dari `layer.orderable` sampai 7 September 2026,
    dan `grounds()` membacanya dengan fallback "floor". Jadi sebuah layer
    ber-plafon yang dimatikan menghilang dari peta itu dan kalimatnya berbalik:
    zona yang lolos karena berada DI BAWAH plafon dilaporkan "clears" gerbangnya
    - persis cacat yang dibawa enam order hidup pada 3 September 2026.

    `ifvg` sudah `orderable=False` dengan `gate="ceiling"` sebelum itu, jadi
    lubangnya sudah menganga untuknya dan tidak ada yang mengujinya; mematikan
    `fvg` akan menambah yang kedua. Petanya sekarang diturunkan dari
    `layer.gate`, dan test ini yang menjaga pemisahan itu: satu peta menjawab
    "bagaimana membaca gerbang zona ini", satu lagi "bolehkah diorder".
    """
    from tools.execute import GATE_DIRECTION, MEASURED_INTERVALS, ORDERABLE_LAYERS

    assert "fvg" not in ORDERABLE_LAYERS
    assert "ifvg" not in ORDERABLE_LAYERS
    # Tapi keduanya TETAP punya arah gerbang, dan arahnya plafon.
    assert GATE_DIRECTION["fvg"] == "ceiling"
    assert GATE_DIRECTION["ifvg"] == "ceiling"
    assert GATE_DIRECTION["supply_demand"] == "floor"
    assert GATE_DIRECTION["order_block"] == "floor"
    # `measured_intervals` bertahan sebagai catatan asal angkanya, bukan sebagai
    # gerbang - yang menolak sekarang `ORDERABLE_LAYERS`, satu langkah lebih awal.
    assert MEASURED_INTERVALS["fvg"] == ("1h", "4h")
    assert "supply_demand" not in MEASURED_INTERVALS
    assert "order_block" not in MEASURED_INTERVALS


def test_fvg_is_refused_at_every_interval_and_the_error_says_why():
    """ARAH PENOLAKANNYA BERBALIK DUA KALI, dan sekarang ia menolak semuanya.

    Test ini dulu menolak 1 jam dan menerima 30 menit, lalu kebalikannya, dan
    sejak 7 September 2026 `fvg` tidak bisa diorder di interval mana pun. Yang
    berubah bukan interval yang benar melainkan bahwa tidak ada yang benar:
    lihat `test_the_orderable_list_holds_exactly_the_measured_two`.

    Pesannya harus menyebut `ORDERABLE_LAYERS`, bukan interval, supaya pembaca
    yang mencoba tidak menyimpulkan ia cuma perlu pindah timeframe.
    """
    from tools.execute import candidates
    for interval in ("15m", "30m", "1h", "4h"):
        with pytest.raises(ValueError, match="ORDERABLE_LAYERS"):
            candidates("mt5:XAUUSD", interval, 10, layer="fvg")


def test_the_ceiling_keeps_the_measured_side_and_drops_the_other():
    """Arah gerbangnya harus benar-benar membalik, bukan cuma dinamai begitu.

    Diukur: cuma 129 dari 3.928 zona fvg lolos gerbang 2,0 ATR, dan 129 itu
    yang TIDAK pernah diuji lawan nol. `floor` untuk fvg akan memasang order
    pada 129 itu sambil membuang 3.799 yang sudah diukur, yaitu kebalikan dari
    apa yang angkanya katakan.
    """
    import inspect

    from app.models import Zone, ZoneKind
    from tools.execute import GATE_DIRECTION, candidates

    def verdict(kind: ZoneKind, departure: float) -> bool:
        return Zone.model_construct(kind=kind, departure_atr=departure).gate_cleared

    # ARAHNYA DIUJI SEBAGAI PERILAKU, bukan sebagai teks sumber. Versi
    # pertama test ini mencari dua string perbandingan di dalam `candidates`,
    # dan itu berhenti bekerja begitu jalur order berhenti menyimpan ambangnya
    # sendiri - yang justru perbaikan, bukan regresi.
    #
    # 1,0 ATR: di ATAS plafon fvg jadi dibuang, di BAWAH lantai supply/demand
    # jadi juga dibuang. 3,0 ATR dan 0,1 ATR memisahkan keduanya, dan tandanya
    # berlawanan. Itulah keseluruhan isi klaim "arahnya membalik".
    assert verdict(ZoneKind.FVG, 0.1) is True
    assert verdict(ZoneKind.FVG, 3.0) is False
    assert verdict(ZoneKind.DBR, 0.1) is False
    assert verdict(ZoneKind.DBR, 3.0) is True
    assert GATE_DIRECTION.get("fvg") == "ceiling"

    # DAN JALUR ORDER MEMBACANYA, bukan menghitung ulang. Sebuah salinan kedua
    # di sini adalah cara ambang order block yang naik ke 2,5 pada 6 September
    # 2026 bisa gagal sampai ke order tanpa satu test pun gagal.
    src = inspect.getsource(candidates)
    assert "zone.gate_cleared" in src, "jalur order tidak membaca verdict zonanya"
