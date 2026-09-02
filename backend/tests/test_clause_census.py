"""Tiap klausa checklist: punya deteksi, punya gambar, terwire, terukur presisinya?

Pertanyaan itu datang berulang dan jawabannya tidak ada di satu tempat mana pun
sampai 2 September 2026. `app/ict.py:CLAUSE_OBJECT` menjawabnya, dan file ini
menjaga jawabannya tidak jadi basi.

Yang dijaga BUKAN isi tabelnya - itu keputusan, dan sebuah test tidak bisa
memutuskan layer mana yang menggambar apa. Yang dijaga sambungannya: tabel harus
menutup setiap klausa, setiap layer yang ia sebut harus benar-benar ada, dan
status parity yang ia klaim harus cocok dengan registry port yang sesungguhnya.
Sensus yang ditulis tangan di samping kode adalah kelas cacat yang sudah dua
kali membuat harness di repo ini merah tanpa ada yang tahu, jadi sambungannya
diperiksa alih-alih dipercaya.
"""

from __future__ import annotations

from app.ict import CLAUSE_OBJECT, MEASURED_AGAINST, Rules
from app.layers import LAYERS
from tools.checklist_outcomes import CLAUSES


def test_the_census_covers_every_clause():
    """Klausa baru harus mendarat di tabel, atau test ini merah.

    Itu satu-satunya mekanisme yang membuat "apakah klausa ini punya gambar"
    tetap terjawab untuk klausa kedelapan belas.
    """
    missing = [c for c in CLAUSES if c not in CLAUSE_OBJECT]
    assert not missing, f"klausa tanpa entri di CLAUSE_OBJECT: {missing}"
    stale = [c for c in CLAUSE_OBJECT if c not in CLAUSES]
    assert not stale, f"entri CLAUSE_OBJECT yang bukan klausa: {stale}"


def test_every_layer_named_actually_exists():
    """Nama layer yang basi lebih buruk daripada tidak ada nama.

    Sebuah tabel yang menunjuk `fibonacci` sebagai layer akan terbaca benar dan
    salah: grid OTE memang digambar, tapi ia menumpang layer `structure` dan
    tidak punya toggle sendiri. Nama yang tidak ada di registry adalah nama yang
    tidak bisa dinyalakan pembaca.
    """
    ids = {layer.id for layer in LAYERS}
    bad = [
        (clause, layer)
        for clause, (layer, _why) in CLAUSE_OBJECT.items()
        if layer is not None and layer not in ids
    ]
    assert not bad, f"CLAUSE_OBJECT menyebut layer yang tidak ada di registry: {bad}"


def test_a_clause_with_no_drawing_says_why():
    """Tidak digambar harus punya alasan, bukan `None` telanjang.

    Empat klausa tidak punya bentuk di harga: dua bacaan jam, satu arah
    turunan, satu rasio aritmetika. Itu keputusan yang benar, dan yang salah
    adalah membiarkan pembaca menyimpulkan gambarnya hilang.
    """
    thin = [
        clause
        for clause, (layer, why) in CLAUSE_OBJECT.items()
        if layer is None and len(why.strip()) < 40
    ]
    assert not thin, f"klausa tanpa gambar dan tanpa alasan yang bisa dibaca: {thin}"


def test_nothing_in_the_census_is_wired_to_decisions():
    """Punya gambar dan punya deteksi TIDAK berarti ikut memutuskan.

    Ketujuh belas klausa dihitung dan tiga belas objeknya digambar, dan tidak
    satu pun menggerbangi trade: `Rules.required` kosong. Perbedaan antara
    "terlihat" dan "ikut memutuskan" adalah perbedaan yang seluruh
    `tests/test_failed_criteria_not_wired.py` ada untuk menjaga, dan diulang di
    sini karena sensus ini yang akan dibaca orang yang bertanya "terwire?".
    """
    assert Rules().required == ()
    for clause in CLAUSES:
        assert clause not in Rules().required


def test_the_census_agrees_with_the_port_registry():
    """Klaim PORTED di catatan harus cocok dengan registry port yang sesungguhnya.

    `tools/mqh_parity.py` yang memegang status port, dan catatan di
    `CLAUSE_OBJECT` menyebutnya dengan kata. Dua tempat yang menyimpan fakta
    yang sama akan melayang, jadi yang disebut PORTED harus benar-benar ada di
    salah satu dict `PORTED*`, dan yang disebut UNPORTED harus ada di
    `UNPORTED`.

    Layer family Quarterly Theory TIDAK ADA di kedua dict, dan itu bukan
    kelalaian: sensus port di file itu hanya menutup family ICT. Catatan yang
    menyebutnya harus mengatakan begitu alih-alih mengklaim PORTED.
    """
    from tools import mqh_parity

    ported = set()
    for name in dir(mqh_parity):
        if name.startswith("PORTED"):
            ported |= set(getattr(mqh_parity, name))
    unported = set(mqh_parity.UNPORTED)

    wrong = []
    for clause, (layer, why) in CLAUSE_OBJECT.items():
        if layer is None:
            continue
        if "PORTED" in why and "UNPORTED" not in why and layer not in ported:
            wrong.append(f"{clause} menyebut PORTED tapi {layer} tidak ada di PORTED*")
        if "UNPORTED" in why and layer not in unported:
            wrong.append(f"{clause} menyebut UNPORTED tapi {layer} tidak ada di UNPORTED")
    assert not wrong, wrong


def test_the_quarterly_theory_clauses_say_they_are_outside_the_port_census():
    """Empat klausa membaca objek yang MQL5-nya tidak pernah dibandingkan.

    `session` dan `dfr` family Quarterly Theory, dan sensus port di
    `tools/mqh_parity.py` hanya menutup family ICT - jadi presisi keduanya
    lawan MQL5 bukan "terukur dan lolos" maupun "terukur dan gagal", melainkan
    BELUM PERNAH DITANYAKAN. Empat klausa berdiri di atas keduanya, dan
    catatannya harus mengatakannya alih-alih diam.
    """
    families = {layer.id: layer.family for layer in LAYERS}
    for clause, (layer, why) in CLAUSE_OBJECT.items():
        if layer is None or families.get(layer) != "Quarterly Theory":
            continue
        # CASE-INSENSITIVE, karena huruf besar di kalimatnya adalah pilihan
        # penekanan penulis dan bukan data. Versi pertama test ini mencari
        # "di luar" sementara catatannya menulis "DI LUAR", jadi ia merah atas
        # kalimat yang sudah benar.
        assert "di luar sensus port mql5" in why.lower() or "IDENTIK" in why, (
            f"{clause} membaca layer {layer} yang family Quarterly Theory, jadi "
            "presisinya lawan MQL5 belum pernah ditanyakan, dan catatannya "
            f"tidak mengatakannya: {why[:90]}"
        )


def test_every_clause_still_carries_its_measurement():
    """Sensus gambar tidak menggantikan sensus angka.

    Dua tabel, dua pertanyaan: `CLAUSE_OBJECT` menjawab "digambar di mana",
    `MEASURED_AGAINST` menjawab "angkanya berapa". Keduanya harus menutup
    ketujuh belas klausa, dan sebuah klausa yang punya gambar tapi tidak punya
    angka adalah tepat keadaan yang membuat operator menyalakannya sebagai
    taruhan.
    """
    for clause in CLAUSES:
        assert clause in CLAUSE_OBJECT, clause
        assert clause in MEASURED_AGAINST, clause
