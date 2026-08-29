"""Brief lengkap, dan jaminan bahwa "lengkap" itu bisa diperiksa.

Paket ini ada karena kekosongan yang tidak menjelaskan dirinya terbaca sama
persis dengan fakta pasar. Test di sini menjaga tiga hal yang membuat brief
berguna: semua layer diminta, cap display mati, dan rencana ikut dibangun.
"""

from __future__ import annotations

from tools.brief import collect, render


def test_every_drawable_layer_is_requested():
    """Registry adalah sumber kebenarannya, bukan daftar yang diketik ulang.

    Sebuah layer yang ditambahkan ke `app/layers.py` dan tidak ke sini akan
    membuat brief mengembalikan array kosong untuknya, dan array kosong di brief
    terbaca sebagai "tidak ada apa apa di pasar" alih alih "tidak diminta". Itu
    persis kesalahan yang menghasilkan kesimpulan "tidak ada zona supply di atas
    harga" pada 29 Agustus 2026, di bar yang punya dua puluh lima.
    """
    from app.layers import LAYERS

    drawable = {layer.id for layer in LAYERS if layer.id != "checklist"}
    assert set(collect.DRAWABLE) == drawable, (
        "tools/brief tidak meminta setiap layer yang bisa digambar; "
        f"selisih: {drawable ^ set(collect.DRAWABLE)}"
    )


def test_the_display_cap_is_off_so_the_sample_is_not_chosen_by_recency():
    """`max_zones_per_side=100` terbaca seperti "mati" dan ia maksimum schema.

    Ia memilih menurut KEBARUAN, dan cap itu sudah empat kali diam diam merusak
    pengukuran di repo ini: `docs/CALIBRATION.md` pernah mengklaim 20.000 bar
    per deret sementara sampelnya hidup di 9,6 persen terakhir. Hanya nol yang
    berarti tanpa cap.
    """
    req = collect.request_for("mt5:XAUUSD", "1h", 500, ["mt5:XAGUSD"])
    assert req.supply_demand.max_zones_per_side == 0
    assert req.session.max_quarters == 0


def test_the_three_layers_that_draw_nothing_by_default_get_their_params():
    """Cycle grid, defining range dan SSMT menggambar NOL dengan params bawaan,
    dan itu terukur. Menyalakannya tanpa params menghasilkan kekosongan yang
    tidak bisa dibedakan dari pasar yang sepi."""
    req = collect.request_for("mt5:XAUUSD", "1h", 500, ["mt5:XAGUSD", "mt5:XPTUSD"])
    assert req.session.quarters, "cycle grid tanpa degree menggambar nol"
    assert req.session.true_opens, "true open tanpa degree menggambar nol"
    assert req.dfr.degrees, "defining range tanpa degree menggambar nol"
    assert req.checklist.ssmt_symbols, "SSMT tanpa partner menggambar nol"


def test_candidates_are_ranked_across_every_timeframe_not_just_the_first():
    """Eksekusi terjadi di timeframe halus, bias dibaca di yang kasar.

    Versi pertama hanya memeringkat timeframe pertama, yang paling kasar, jadi
    kandidat terdekatnya 81,9 poin dari harga sementara timeframe eksekusi punya
    satu di 10,3 poin. Brief yang memeringkat salah satunya saja menyembunyikan
    separuh setup yang ada.
    """
    zone = {"id": "Z1", "kind": "RBR", "side": "demand", "state": "fresh",
            "departure_atr": 3.0, "dealing_range_pos": 0.4}
    per_tf = {
        "4h": {"drawing": {"zones": [dict(zone, id="FAR")]},
               "plans": [{"zone_id": "FAR", "entry": 4000.0, "stop": 3950.0,
                          "target": 4200.0, "reward_r": 4.0, "side": "demand"}]},
        "15m": {"drawing": {"zones": [dict(zone, id="NEAR")]},
                "plans": [{"zone_id": "NEAR", "entry": 4455.0, "stop": 4440.0,
                           "target": 4500.0, "reward_r": 3.0, "side": "demand"}]},
    }
    out = render.rank_candidates(per_tf, price=4456.219)
    assert [r["zone_id"] for r in out["with_target"]] == ["NEAR", "FAR"]
    assert out["with_target"][0]["timeframe"] == "15m"


def test_a_plan_without_a_target_is_counted_and_not_dropped():
    """Rencana tanpa target berarti tidak ada zona lawan hidup di depan harga,
    dan gerbang keenam menolaknya. Itu penolakan yang bisa disebut. Membuangnya
    dari brief membuat pembaca menyimpulkan engine cuma menemukan sedikit setup,
    padahal ia menemukan banyak dan menolak sebagian besar."""
    per_tf = {
        "1h": {
            "drawing": {"zones": [{"id": "A", "kind": "FVG", "side": "supply",
                                   "state": "fresh", "departure_atr": 1.0}]},
            "plans": [{"zone_id": "A", "entry": 4500.0, "stop": 4520.0,
                       "target": None, "side": "supply"}],
        }
    }
    out = render.rank_candidates(per_tf, price=4456.219)
    assert out["with_target"] == []
    assert out["without_target_count"] == 1
    assert "gerbang keenam" in out["without_target_note"]


def test_the_markdown_leads_with_what_must_not_be_concluded():
    """Blok CAUTION harus muncul SEBELUM angka mana pun.

    Agent membaca dari atas. Sebuah brief yang menaruh pagarnya di bawah tabel
    kandidat sudah terlambat: angkanya sudah dikutip.
    """
    b = {
        "symbol": "mt5:XAUUSD", "generated_at_ny": "2026-08-29 03:58 NY",
        "market_shut": True, "price": 4456.219, "base_timeframe": "1h",
        "timeframes": {}, "failures": [], "candidates": {"with_target": []},
        "layer_evidence": [], "clause_provenance": {}, "fibonacci": {"present": False},
    }
    md = render.markdown(b)
    caution = md.index("[!CAUTION]")
    assert caution < md.index("## Ringkasan per timeframe")
    assert "belum mengalahkan" in md, "pagar harus menyebut batas yang terukur"


# ------------------------------------------------- bacaan yang menjaring


def test_both_network_reads_share_one_event_loop():
    """SATU `asyncio.run`, dan ini bukan kerapian.

    Versi pertama memanggil `asyncio.run` dua kali, sekali untuk checklist dan
    sekali untuk triad. Yang pertama berhasil dan yang kedua gagal dengan
    `<asyncio.locks.Lock> is bound to a different event loop`, karena
    `app/providers` menyimpan satu `asyncio.Lock` per key dan sebuah Lock
    terikat ke loop tempat ia dibuat. `asyncio.run` menutup loop-nya saat
    selesai, jadi panggilan kedua mewarisi lock milik loop yang sudah mati dan
    SETIAP partner gagal.

    Yang muncul di permukaan bukan "loop salah" melainkan "nothing left to
    compare XAUUSD with", yaitu pesan yang terbaca seperti masalah data. Test
    ini menghitung berapa loop yang dibuat, bukan memeriksa hasilnya, karena
    hasilnya butuh terminal dan penyebabnya tidak.
    """
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[1] / "tools" / "brief" / "live.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    runs = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "run"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "asyncio"
    ]
    assert len(runs) == 1, (
        f"{len(runs)} panggilan asyncio.run di live.py. Tiap satunya membuat "
        "dan menutup loop sendiri, dan lock provider yang di-cache terikat ke "
        "loop pertama. Bungkus semuanya dalam satu run."
    )


def test_a_skipped_triad_partner_is_forwarded_and_not_swallowed():
    """Korelasi dua instrumen yang disajikan seolah korelasi tiga bukan angka
    yang lebih lemah, ia angka tentang sesuatu yang lain.

    `load_aligned` mengembalikan daftar `skipped`, dan brief harus
    meneruskannya. Diperiksa lewat source karena jalur aslinya butuh terminal.
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "tools" / "brief" / "live.py").read_text(encoding="utf-8")
    assert '"skipped": skipped' in src, "daftar partner yang di-skip tidak diteruskan"
    assert "skipped_note" in src, "partner yang di-skip diteruskan tanpa penjelasan"


def test_the_two_ote_sources_are_reported_side_by_side_and_neither_wins():
    """Dua definisi menjawab pertanyaan yang sama, dan tool pelapor tidak boleh
    memilih pemenangnya. Memilih adalah keputusan pemilik metode."""
    from tools.brief import live

    out = live.ote_reconciliation(
        {"present": True, "price_retracement": 0.376},
        {"range_band": "discount", "range_pos": 0.30},
    )
    assert out["from_structure_swings"]["retracement"] == 0.376
    assert out["from_dealing_range"]["band"] == "discount"
    assert out["agree_within_0_10"] is True
    assert "tidak memilih" in out["note"]

    jauh = live.ote_reconciliation(
        {"present": True, "price_retracement": 0.80},
        {"range_band": "discount", "range_pos": 0.20},
    )
    assert jauh["agree_within_0_10"] is False


def test_an_absent_dealing_range_says_so_instead_of_reading_as_zero():
    """29 Agustus 2026: grid memberi 0,376 sementara klausanya mengembalikan
    "no dealing range, no OTE reading". Absen bukan nol, dan absen bukan
    setuju."""
    from tools.brief import live

    out = live.ote_reconciliation(
        {"present": True, "price_retracement": 0.376},
        {"range_band": None, "range_pos": None},
    )
    assert out["from_dealing_range"]["present"] is False
    assert out["from_dealing_range"]["why_absent"]
    assert out["agree_within_0_10"] is None, "tidak terbaca bukan sepakat"


def test_an_unreadable_ssmt_partner_is_named_instead_of_reading_as_no_divergence():
    """Nol hit SSMT punya dua sebab yang sangat berbeda.

    Partner yang tidak terbaca dan partner yang terbaca tapi tidak
    berdivergensi keduanya menghasilkan `ssmt: []`. Diuji 29 Agustus 2026
    dengan `--partners mt5:TIDAKADA`: checklist mengembalikan nol hit, `notes`
    tidak menyebut partnernya sama sekali, dan brief melaporkan NOL kegagalan.
    Nama yang salah ketik lolos tanpa satu pun jejak di permukaan, dan
    pembacanya menyimpulkan pasar tidak berdivergensi.
    """
    from tools.brief import live

    health = live.partner_health(["mt5:TIDAKADA"], "1h", 300)
    assert len(health) == 1
    assert health[0]["readable"] is False
    assert health[0]["why"], "partner yang gagal harus membawa alasannya"
    assert "TIDAKADA" in health[0]["symbol"]


def test_a_readable_partner_is_not_reported_as_a_failure():
    """Gerbangnya harus membedakan, bukan menolak semuanya. Sebuah penjaga
    yang menandai tiap partner sebagai rusak akan memenuhi assertion di atas
    dengan sempurna sambil merusak produknya."""
    from tools.brief import live

    health = live.partner_health(["mt5:XAGUSD"], "1h", 300)
    assert health[0]["readable"] is True
    assert health[0]["bars"] > 0
    assert health[0]["why"] is None
