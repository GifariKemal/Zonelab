"""Arah gerbang departure per kind, dan bahwa hanya ada SATU sumber untuknya.

Berkas ini ada karena angkanya pernah hidup di tiga tempat sekaligus:
`plan.py` memegang dua konstanta, `advisor.py` menuliskan `0.25` dan `2.0`
sebagai literal di enam tempat, dan keduanya mengulang `kind in (FVG, IFVG)`
sendiri-sendiri. Mengubah ambang di satu tempat tidak mengubah kalimat yang
dibaca pengguna di tempat lain, dan tidak ada test yang gagal.

Yang diikat di sini bukan cuma nilainya, tapi bahwa dua permukaan teks yang
mengutip ambang itu MENGUTIP zonanya.
"""

from app.advisor import explain
from app.models import (
    CEILING_KINDS,
    DEPARTURE_GATE_ATR,
    DEPARTURE_GATE_ATR_CEILING,
    Anatomy,
    Zone,
    ZoneKind,
    ZoneSide,
    ZoneState,
)
from app.plan import build

T0 = 1699920000
STEP = 900


def _zone(kind: ZoneKind, departure_atr: float) -> Zone:
    return Zone.model_construct(kind=kind, departure_atr=departure_atr)


def _full_zone(kind: ZoneKind, departure_atr: float) -> Zone:
    """Zona yang lengkap secara validasi, untuk permukaan yang merendernya."""
    return Zone(
        id=f"{kind.value}-1",
        kind=kind,
        side=ZoneSide.DEMAND,
        state=ZoneState.FRESH,
        timeframe="15m",
        top=100.0,
        bottom=98.0,
        proximal=100.0,
        distal=98.0,
        time_from=T0,
        time_to=T0 + 10 * STEP,
        formation_score=0.0,
        departure_atr=departure_atr,
        profit_zone_rr=2.0,
        anatomy=Anatomy(
            leg_in_from=0, leg_in_to=1, base_run_from=2,
            base_from=2, base_to=4, leg_out_from=5, leg_out_to=8,
        ),
    )


def _plan_for(zone: Zone):
    return build(zone, atr=1.0, now=T0 + 10 * STEP, interval_seconds=STEP,
                 spread=0.2)


#: Ambang yang BERLAKU per kind, ditulis satu per satu.
#:
#: VERSI PERTAMA TEST INI HAMPA, dan suntikan yang membuktikannya: ia
#: menurunkan ambang yang diharapkan dari `CEILING_KINDS` sendiri, jadi
#: menghapus `ZoneKind.IFVG` dari tuple itu membuat keenam test tetap lolos.
#: Sebuah test yang menanyakan "apakah computed field setuju dengan tuple yang
#: dipakainya" selalu menjawab ya. Yang mengikat sekarang adalah tabel di
#: bawah, yang menyebut kedelapan kind dan angkanya sebagai literal.
EXPECTED_GATE_ATR = {
    ZoneKind.RBR: 2.0,
    ZoneKind.DBR: 2.0,
    ZoneKind.DBD: 2.0,
    ZoneKind.RBD: 2.0,
    ZoneKind.OB: 2.0,
    ZoneKind.BRK: 2.0,
    ZoneKind.FVG: 0.25,
    ZoneKind.IFVG: 0.25,
}


def test_every_zone_kind_is_assigned_a_gate_direction():
    """Sensus, supaya kind baru tidak diam diam mewarisi lantai 2,0 ATR."""
    assert set(EXPECTED_GATE_ATR) == set(ZoneKind), (
        "kind baru masuk enum tanpa ambang gerbang yang dinyatakan: "
        f"{set(ZoneKind) ^ set(EXPECTED_GATE_ATR)}"
    )
    for kind, expected in EXPECTED_GATE_ATR.items():
        assert _zone(kind, 1.0).gate_atr == expected, kind


def test_the_ceiling_membership_is_exactly_the_two_measured_kinds():
    """Keanggotaan plafon, dipatok ke nama.

    Cuma FVG dan IFVG yang gerbangnya diukur terbalik. Sebuah kind yang
    ditambahkan ke tuple itu tanpa pengukurannya sendiri akan memakai ambang
    yang tidak pernah diukur untuknya, dan sebuah kind yang HILANG dari tuple
    itu akan dinilai dengan arah yang berlawanan.
    """
    assert set(CEILING_KINDS) == {ZoneKind.FVG, ZoneKind.IFVG}


def test_the_ceiling_kinds_clear_by_being_small():
    for kind in CEILING_KINDS:
        assert _zone(kind, DEPARTURE_GATE_ATR_CEILING - 0.01).gate_cleared
        assert not _zone(kind, DEPARTURE_GATE_ATR_CEILING + 0.01).gate_cleared
        # 3,0 ATR lolos lantai supply/demand dan GAGAL di sini. Ini keseluruhan
        # isi klaim "gerbangnya terbalik".
        assert not _zone(kind, 3.0).gate_cleared


def test_the_floor_kinds_clear_by_being_large():
    for kind in ZoneKind:
        if kind in CEILING_KINDS:
            continue
        assert _zone(kind, DEPARTURE_GATE_ATR + 0.01).gate_cleared
        assert not _zone(kind, DEPARTURE_GATE_ATR - 0.01).gate_cleared
        # 0,10 ATR lolos plafon FVG dan GAGAL di sini, arah yang berlawanan.
        assert not _zone(kind, 0.10).gate_cleared


def test_the_boundary_belongs_to_the_side_the_original_code_gave_it():
    """Persis di ambang: plafon EKSKLUSIF, lantai INKLUSIF.

    Dua perbandingan yang dipindahkan, `< 0.25` dan `>= 2.0`. Sebuah
    penulisan ulang yang menyeragamkan keduanya jadi `<=`/`>` akan menggeser
    kohortnya tanpa mengubah satu angka pun yang terlihat di layar.
    """
    assert not _zone(ZoneKind.FVG, DEPARTURE_GATE_ATR_CEILING).gate_cleared
    assert _zone(ZoneKind.DBR, DEPARTURE_GATE_ATR).gate_cleared


def test_the_advisor_quotes_the_threshold_the_zone_reports():
    """Anti-drift, dan ini cacat yang benar-benar terjadi.

    `advisor.py` menuliskan "0,25" dan "2,0" sebagai literal, jadi ambang di
    `plan.py` bisa diubah tanpa mengubah kalimat ini. Sekarang ambangnya
    dibaca dari zonanya, dan test ini yang menahannya di situ.
    """
    for kind, departure in ((ZoneKind.FVG, 1.50), (ZoneKind.DBR, 1.00)):
        zone = _full_zone(kind, departure)
        text = " ".join(
            n.text for n in explain(zone, _plan_for(zone), "15m").notes
        )
        quoted = f"{zone.gate_atr}".replace(".", ",")
        assert f"gerbang {quoted} ATR" in text, (kind, text)


def test_the_plan_warning_fires_on_the_verdict_the_zone_carries():
    """Peringatan gerbang muncul kalau dan hanya kalau zonanya tidak lolos."""
    for kind, departure in (
        (ZoneKind.FVG, 0.10),   # lolos plafon
        (ZoneKind.FVG, 1.50),   # gagal plafon
        (ZoneKind.DBR, 3.00),   # lolos lantai
        (ZoneKind.DBR, 1.00),   # gagal lantai
    ):
        zone = _full_zone(kind, departure)
        plan = _plan_for(zone)
        assert plan is not None, (kind, departure)
        fired = any("gerbang" in w for w in plan.warnings)
        assert fired is (not zone.gate_cleared), (kind, departure, plan.warnings)
