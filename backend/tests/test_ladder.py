"""Ladder cycle, dipaku ke empat baris sumbernya.

KENAPA FILE INI ADA. `app/ladder.py` pernah punya tabel yang melanggar aturan
yang ditulis docstring-nya sendiri, di tiga dari lima baris, dan waktu itu tidak
ada cara menyelesaikannya karena sumbernya cuma kutipan praktisi yang tidak
dimiliki repo ini. Sumbernya sekarang ada, di
`Referensi grup dan Bg Nas/Discord/Buku=Pegangan.txt`, dan tabelnya diturunkan
darinya alih-alih ditulis ulang.

Test ini menuliskan keempat baris itu SENDIRI, terpisah dari modulnya, supaya
yang dibandingkan bukan modul dengan dirinya sendiri. Kalau `SOURCE_RUNGS` atau
aturan satu-langkah bergerak, di sini yang gagal.
"""

from __future__ import annotations

from app.ladder import LADDER, SOURCE_RUNGS, for_cycle
from app.providers.base import INTERVALS

#: Empat baris sumber, ditranskripsi ulang di sini sebagai pasangan
#: (key level, expansion). Ini satu-satunya tempat di test ini yang boleh
#: mengetahui isi doktrinnya.
#:
#:   "Monthly key levels will produce weekly expansions"
#:   "Weekly key levels will produce daily expansions."
#:   "Daily key levels will produce 4hr expansions"
#:   "4hr pd arrays will produce 15min expansions."
SOURCE_LINES = (
    ("1M", "1w"),
    ("1w", "1d"),
    ("1d", "4h"),
    ("4h", "15m"),
)


def test_the_rungs_are_exactly_the_ones_the_source_names():
    """Lima rung, bukan tujuh, dan itu inti koreksinya.

    Komentar lama mengklaim rung-nya `1w -> 1d -> 4h -> 1h -> 15m -> 5m -> 1m`.
    Rung karangan itulah yang membuat aturan "dua langkah" jadi perlu: dengan
    `1h` diselipkan antara `4h` dan `15m`, satu langkah dari 4h mendarat di 1h
    sementara sumbernya bilang mendarat di 15m.
    """
    expected = ("1M",) + tuple(expansion for _, expansion in SOURCE_LINES)
    assert SOURCE_RUNGS == expected
    for invented in ("1h", "5m", "1m", "30m"):
        assert invented not in SOURCE_RUNGS, f"{invented} bukan rung di sumbernya"


def test_every_execution_chart_is_exactly_one_rung_below_its_read_chart():
    """Aturan satu-langkah, diuji sebagai properti atas SETIAP baris.

    Bukan mencocokkan tabel ke tabel: ia mengambil read chart tiap cycle, mencari
    expansion-nya di transkripsi sumber, lalu menuntut tabelnya sepakat.
    """
    expansion_of = dict(SOURCE_LINES)
    assert LADDER, "tabelnya kosong, jadi test ini tidak menguji apa pun"
    for cycle, (read_tf, exec_tf, _micro) in LADDER.items():
        assert read_tf in expansion_of, f"{cycle} membaca rung yang tidak ada di sumber"
        assert exec_tf == expansion_of[read_tf], (
            f"{cycle}: sumber bilang {read_tf} menghasilkan "
            f"{expansion_of[read_tf]}, tabel bilang {exec_tf}"
        )


def test_the_micro_entry_is_one_rung_below_execution_or_absent():
    """Dan absen berarti None, bukan tebakan.

    Sumbernya berhenti di 15min. Cycle `4h` karena itu tidak punya micro entry,
    dan mengisinya dengan `5m` akan mengarang rung keenam.
    """
    expansion_of = dict(SOURCE_LINES)
    for cycle, (_read, exec_tf, micro_tf) in LADDER.items():
        if exec_tf in expansion_of:
            assert micro_tf == expansion_of[exec_tf], cycle
        else:
            assert micro_tf is None, (
                f"{cycle}: sumbernya tidak punya rung di bawah {exec_tf}, "
                f"jadi micro harus None, bukan {micro_tf!r}"
            )
    # Dan kasus itu memang terjadi, jadi cabang di atas bukan kode mati.
    assert LADDER["4h"][2] is None


def test_a_rung_this_engine_cannot_fetch_is_reported_rather_than_substituted():
    """Read chart bulanan tidak bisa diambil, dan itu dikatakan.

    `INTERVALS` berjalan 1m sampai 1w, jadi candle bulanan tidak bisa diminta.
    Menggantinya dengan `1w` diam-diam akan membuat cycle monthly membaca chart
    yang salah dan tetap menjawab 200.
    """
    monthly = for_cycle("monthly")
    assert monthly is not None
    assert monthly.read_tf == "1M"
    assert "1M" not in INTERVALS
    assert monthly.unavailable == ("1M",)

    # Sisanya bisa diambil, jadi kolom itu bukan selalu terisi.
    for cycle in ("weekly", "daily", "4h"):
        ladder = for_cycle(cycle)
        assert ladder is not None
        assert ladder.unavailable == (), f"{cycle}: {ladder.unavailable}"


def test_the_invented_one_hour_cycle_is_gone():
    """`1h` pernah jadi baris di tabel lama. Ia bukan cycle di sumbernya."""
    assert for_cycle("1h") is None
    assert "1h" not in LADDER


def test_an_unknown_cycle_is_none_rather_than_a_default():
    assert for_cycle("nonsense") is None
    assert for_cycle("") is None


def test_a_psp_switches_the_route_and_nothing_else():
    """Route B hanya menambah PSP dan TOB; timeframe-nya tidak boleh bergerak."""
    direct = for_cycle("daily")
    late = for_cycle("daily", has_psp=True)
    assert direct is not None and late is not None
    assert direct.route != late.route
    assert "PSP" in late.route and "PSP" not in direct.route
    assert (direct.read_tf, direct.execution_tf, direct.micro_tf) == (
        late.read_tf,
        late.execution_tf,
        late.micro_tf,
    )
