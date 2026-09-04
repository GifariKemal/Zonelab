"""Jarak yang harus ditempuh MELAWAN tesis sebelum sebuah limit terisi.

Klausa ini lahir dari satu order pada 4 September 2026 yang arahnya benar dan
strukturnya salah. COT commercial -34.558, SSMT day Q2 bearish, dan premium di
ketiga true open: ketiganya bilang jual. Gold memang turun, 4469,711 ke 4382,73,
yaitu 86,98 dolar. Yang dipasang sell limit 4501,464, jadi 31,75 di ATAS pasar,
yaitu 2,10x ATR(14) H1 MELAWAN tesisnya sendiri. Ia tidak pernah terisi. Market
sell di harga saat itu, dengan stop yang sama 11,11, adalah +7,83 R.

Tidak satu pun dari tujuh belas klausa sebelumnya menanyakan jarak itu, dan
`ote` justru memperlakukan retracement sebagai SYARAT bukan sebagai risiko. Itu
bukan cacat aritmetika di satu order, itu kolom yang tidak ada.

YANG DIJAGA DI SINI TANDANYA, bukan ambangnya, dan itu karena ambangnya SUDAH
diukur dan GAGAL. Diukur 4 September 2026 di tiga sel, ambang 1,0x ATR dipatok
sebelum melihat angkanya, dijangkar di `anatomy.leg_out_to` yaitu bar pertama
sebuah limit bisa dipasang:

    supply_demand XAUUSD 30m  kecil -0,0425 (n=1437)  besar +0,0314 (n=359)
                              delta -0,0739  t=-1,19  walk-forward 5/8
    supply_demand XAUUSD 15m  kecil -0,0321 (n=621)   besar -0,0312 (n=141)
                              delta -0,0009  t=-0,01  walk-forward 3/8
    fvg XAUUSD 30m            kecil +0,1846 (n=1663)  besar +0,4000 (n=338)
                              delta -0,2154  t=-2,41  walk-forward 1/8

Praregistrasinya berbunyi ADVERSE KECIL LEBIH BAIK. Ketiga sel memberi
KEBALIKANNYA, yang masuk akal ekonomis karena limit yang lebih jauh mengisi di
harga yang lebih bagus. Arah balik itu tetap tidak lolos: walk-forward 5/8, 3/8,
1/8, dan sel yang |t| nya melewati ambang justru yang walk-forward 1/8. Kontrol
tanda-dibalik degenerate di ketiga sel (bucket 22, 4, dan nol baris).

DUA JEBAKAN JANGKAR, keduanya sudah dimakan sekali. Run pertama menjangkar di
`zone.time_from`, yang adalah bar zona MULAI terbentuk saat harga masih di dalam
zona: adverse di sana selalu negatif, max -0,03 di 400 zona, dan tidak
memisahkan apa pun. Dan adverse di bar kelahiran BUKAN `departure_atr`,
korelasinya -0,0345, meski sempat diduga sama.

Karena itu `max_adverse_atr` default nol, klausanya melaporkan dan tidak
menggerbang, dan test terakhir di file ini yang menjaga default itu tidak
berubah diam diam.
"""

from __future__ import annotations

from app.ict import Rules, evaluate
from app.models import ZoneSide

from tests.test_ict import named, stack, state, zone


def clause(side: ZoneSide, adverse: float | None, threshold: float = 0.0):
    return named(evaluate(
        zone(side), state(), stack(), Rules(max_adverse_atr=threshold),
        adverse_atr=adverse,
    ))["adverse_excursion"]


def test_the_order_that_produced_this_clause_fails_it():
    """Suntikan cacatnya: sell limit 2,10x ATR di atas pasar, tesis turun."""
    c = clause(ZoneSide.SUPPLY, +2.10, threshold=1.0)
    assert c.met is False
    assert "+2.10x ATR" in c.detail


def test_a_limit_just_below_the_market_passes_for_a_buy():
    """Sisi lain gerbang yang sama, supaya ia memisahkan dan tidak menolak semua."""
    c = clause(ZoneSide.DEMAND, +0.30, threshold=1.0)
    assert c.met is True


def test_an_entry_already_past_the_price_reads_negative():
    """Nol berarti limit di harga; negatif berarti ia akan terisi seketika.

    Dijaga karena `abs` akan membaca keduanya sama dengan excursion melawan, dan
    itu justru membalik arti klausanya.
    """
    c = clause(ZoneSide.SUPPLY, -0.75, threshold=1.0)
    assert c.met is True
    assert "-0.75x ATR" in c.detail


def test_a_caller_that_did_not_compute_it_gets_unknown_not_zero():
    """`None` bukan nol. Nol adalah klaim bahwa entry ada di harga."""
    c = clause(ZoneSide.SUPPLY, None)
    assert c.met is None
    assert "x ATR" not in c.detail


def test_the_default_reports_without_gating():
    """Default nol: angkanya terbaca, tapi ia tidak bisa memblokir apa pun.

    Ini yang membuat klausa ini tidak menyalakan gerbang tanpa angka, dan ia
    diuji supaya default-nya tidak berubah tanpa ada yang menyadarinya.
    """
    assert Rules().max_adverse_atr == 0.0
    c = clause(ZoneSide.SUPPLY, +2.10)
    assert c.met is None
    assert "+2.10x ATR" in c.detail
    assert "TIDAK memisahkan" in c.detail


# ------------------------------------------------------- aritmetika tandanya
# Dipisah dari klausanya karena inilah bagian yang bisa salah TANPA membuat satu
# pun test klausa di atas merah: klausa menerima angka jadi, fungsi ini yang
# memutuskan angka itu positif atau negatif. Angkanya diambil dari dua order
# yang benar benar dipasang 4 September 2026, jadi kalau rumusnya dibalik yang
# merah adalah dua kasus yang sudah terjadi.

from app.ict import adverse_excursion_atr  # noqa: E402


def test_the_gold_sell_limit_reads_positive():
    """Sell limit 4501,464 dengan pasar 4469,711 dan ATR H1 15,09: +2,10x."""
    got = adverse_excursion_atr(4501.464, 4469.711, 15.09, long_side=False)
    assert got is not None and round(got, 2) == 2.10


def test_the_btc_buy_limit_reads_positive_too():
    """Buy limit 78418,91 dengan pasar 81246,62 dan ATR H1 485,79: +5,82x.

    Sisi berlawanan, tanda yang sama, karena kedua limit menunggu harga datang
    melawan tesisnya. Ini yang membedakannya dari `abs`.
    """
    got = adverse_excursion_atr(78418.91, 81246.62, 485.79, long_side=True)
    assert got is not None and round(got, 2) == 5.82


def test_flipping_the_side_flips_the_sign():
    """Kontrol: rumus yang sama dengan `long_side` salah harus berubah tanda.

    Tanpa ini, `abs` di mana pun di dalam fungsi itu akan lolos setiap test lain
    di file ini.
    """
    a = adverse_excursion_atr(4501.464, 4469.711, 15.09, long_side=False)
    b = adverse_excursion_atr(4501.464, 4469.711, 15.09, long_side=True)
    assert a is not None and b is not None
    assert a > 0 > b and round(a + b, 9) == 0.0


def test_the_clause_reports_itself_as_measured_not_doctrine():
    """`doctrine` di sini akan jadi kalimat yang salah, dan mahal.

    `tools/execute.py:warn_required` memisahkan dua kalimat: klausa doctrine
    diperingatkan sebagai belum diukur, klausa di `MEASURED_AGAINST`
    diperingatkan DENGAN angkanya. Klausa ini sudah diukur dan gagal, jadi
    operator yang membaca "belum diukur" akan menyalakannya sebagai taruhan,
    padahal walk-forward-nya 1 dari 8 di sel dengan |t| terbesar.
    """
    from app.ict import MEASURED_AGAINST

    assert "adverse_excursion" in MEASURED_AGAINST
    for adverse in (None, +2.10):
        assert clause(ZoneSide.SUPPLY, adverse).source == "measured"


def test_zero_atr_gives_none_not_a_division():
    assert adverse_excursion_atr(100.0, 100.0, 0.0, long_side=True) is None
