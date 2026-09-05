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
    CEILING_COHORT_EXP_R,
    CEILING_KINDS,
    GATE_UNMEASURED_KINDS,
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
    ZoneKind.FVG: 0.25,   # DIUKUR, docs/QA-FVG-RECALIBRATION.md
    ZoneKind.IFVG: 0.25,  # DIUKUR, docs/QA-IFVG-GATE.md
}

#: KEDUANYA SEKARANG TERUKUR, dan urutan kejadiannya layak dicatat karena satu
#: di antaranya sempat dikirim sebagai analogi.
#:
#: Plafon 0,25 lahir dari sweep FVG di commit 44196e2. Sweep itu menyuntik
#: `detect_fvg` ke `DETECTORS` dan tidak menyentuh satu zona inversi pun, tetapi
#: commit yang sama memasukkan `ZoneKind.IFVG` ke `CEILING_KINDS`. Versi pertama
#: berkas ini menamai test di bawah "the two measured kinds" dan menulis "Cuma
#: FVG dan IFVG yang gerbangnya diukur terbalik". Kalimat itu SALAH untuk IFVG
#: dan sempat ter-push di 864d0d8.
#:
#: `docs/QA-IFVG-GATE.md` menutupnya pada 5 September 2026, 12 sel dan
#: n=11.068: arah plafon menang di SETIAP ambang, dan di 0,25 exp_r +0,3450
#: lawan baseline +0,2348 dengan Welch t=+5,18 dan walk-forward 8 dari 8.
#: Terukur di 15m sampai 4h; di 1d tandanya konsisten tetapi |t| tertinggi 2,909
#: tidak melewati Bonferroni 2,914, dan di 1w populasinya 16 trade.
#:
#: YANG DIUKUR ITU ARAH DAN AMBANGNYA, BUKAN SEBUAH KLAIM HIT RATE. Win rate
#: JUSTRU TURUN saat plafon diperketat, 0,4777 di 3,0 ATR menjadi 0,3967 di 0,1
#: ATR, sementara mean win naik dari 1,43 R ke 2,41 R. Untuk FVG `departure_atr`
#: adalah TINGGI GAP dalam ATR, jadi plafon yang lebih ketat menyimpan gap yang
#: lebih kecil, gap yang lebih kecil memberi stop yang lebih rapat, dan R
#: dinormalisasi terhadap risk. Gerbang ini menyortir kerapatan stop.
IFVG_GATE_MEASURED_AT = "docs/QA-IFVG-GATE.md, 2026-09-05, n=11068"


def test_every_zone_kind_is_assigned_a_gate_direction():
    """Sensus, supaya kind baru tidak diam diam mewarisi lantai 2,0 ATR."""
    assert set(EXPECTED_GATE_ATR) == set(ZoneKind), (
        "kind baru masuk enum tanpa ambang gerbang yang dinyatakan: "
        f"{set(ZoneKind) ^ set(EXPECTED_GATE_ATR)}"
    )
    for kind, expected in EXPECTED_GATE_ATR.items():
        assert _zone(kind, 1.0).gate_atr == expected, kind


def test_the_ceiling_membership_is_pinned_to_names():
    """Keanggotaan plafon, dipatok ke nama, dan keduanya terukur.

    Test ini menahan keanggotaannya supaya perubahan di kedua arah terlihat:
    menambah kind memberinya ambang yang tidak pernah diukur untuknya, dan
    menghapus kind menilainya dengan arah yang berlawanan. BRK sengaja TIDAK
    di sini - ia mewarisi `departure_atr` dari order block induknya lewat
    mekanisme yang sama dan memakai lantai 2,0 ATR yang belum pernah diukur
    untuknya, dicatat di `docs/QA-IFVG-GATE.md` bagian penutup.
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


#: Kind yang ambangnya PERNAH diukur untuk dirinya sendiri, ditulis satu per
#: satu dengan sumbernya. Diturunkan dari `GATE_UNMEASURED_KINDS` akan jadi
#: tautologi yang sama yang membuat versi pertama sensus di atas hampa.
GATE_MEASURED = {
    ZoneKind.RBR: "docs/CALIBRATION.md",
    ZoneKind.DBR: "docs/CALIBRATION.md",
    ZoneKind.DBD: "docs/CALIBRATION.md",
    ZoneKind.RBD: "docs/CALIBRATION.md",
    ZoneKind.OB: "docs/CALIBRATION.md, rig yang sama dengan fvg",
    ZoneKind.FVG: "docs/QA-FVG-RECALIBRATION.md",
    ZoneKind.IFVG: "docs/QA-IFVG-GATE.md",
}


def test_only_the_kinds_with_their_own_measurement_claim_one():
    """BRK memajang verdict dari ambang yang tidak pernah diukur untuknya.

    `gate_cleared` selalu menjawab karena ia aritmetika, jadi tanpa
    `gate_measured` sebuah kotak BRK di zone card membawa titik verdict yang
    terlihat sama otoritatifnya dengan titik pada FVG. Lantai 2,0 ATR yang
    dipakainya adalah ambang milik ORDER BLOCK induknya, diwarisi lewat
    mekanisme yang sama dengan IFVG dan tidak pernah diukur pada populasi
    breaker.
    """
    for kind in ZoneKind:
        expected = kind in GATE_MEASURED
        assert _zone(kind, 1.0).gate_measured is expected, kind
    assert ZoneKind.BRK not in GATE_MEASURED
    assert set(GATE_MEASURED) | set(GATE_UNMEASURED_KINDS) == set(ZoneKind), (
        "kind baru masuk enum tanpa dinyatakan terukur atau belum terukur"
    )


def test_each_ceiling_kind_quotes_its_own_cohort_not_another_populations():
    """Cacat yang terlihat di layar sebelum diperbaiki, 5 September 2026.

    Panel PLAN sebuah zona IFVG 0,37 ATR mencetak "Kohort ini exp_r +0.190 R,
    lawan +0.426 R yang di bawah gerbang". Kedua angka itu milik FVG. Kohort
    IFVG yang sebenarnya +0,160 lawan +0,345, diukur di
    `docs/QA-IFVG-GATE.md` pada n=11.068.

    Yang diikat: angka yang DICETAK harus angka kind itu sendiri, di kedua
    permukaan teks dan di field `departure_held_rate` yang membawanya.
    """
    assert CEILING_COHORT_EXP_R[ZoneKind.FVG] != CEILING_COHORT_EXP_R[ZoneKind.IFVG], (
        "kalau kedua kind memakai angka yang sama, test ini tidak bisa "
        "membedakan tabel per kind dari satu pasang konstanta"
    )
    assert set(CEILING_COHORT_EXP_R) == set(CEILING_KINDS)

    for kind in CEILING_KINDS:
        below, above = CEILING_COHORT_EXP_R[kind]
        other = next(k for k in CEILING_KINDS if k is not kind)
        wrong_below, wrong_above = CEILING_COHORT_EXP_R[other]

        # Di ATAS plafon, jadi peringatannya menyala dan mengutip kohortnya.
        zone = _full_zone(kind, 1.50)
        plan = _plan_for(zone)
        assert plan is not None
        assert plan.departure_held_rate == above, (kind, plan.departure_held_rate)

        text = " ".join(plan.warnings) + " " + " ".join(
            n.text for n in explain(zone, plan, "15m").notes
        )
        assert f"+{above:.3f}" in text, (kind, text)
        assert f"+{wrong_above:.3f}" not in text, (
            f"{kind} mengutip angka kohort {other}", text,
        )
        assert f"+{wrong_below:.3f}" not in text, (
            f"{kind} mengutip angka kohort {other}", text,
        )


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
