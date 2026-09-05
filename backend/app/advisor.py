"""Explain a drawing in sentences, each one carrying the number behind it.

An advisor that predicts would have to invent the one thing twelve pre-registered
hypotheses could not produce. This one explains instead, and the difference is
not modesty - it is what makes the other sentences worth believing. Every line
below is either a measurement from docs/CALIBRATION.md or arithmetic on geometry
that has been verified to the pixel. The line that says what cannot be known is
mandatory and is emitted last, so it cannot be scrolled past.

WRITTEN IN INDONESIAN, deliberately. This is the teaching surface, `/docs` is
already Indonesian, and the person it teaches asked for it in Indonesian. The
control panel stays English because its labels name API fields.

WHY IT IS RULE-BASED RATHER THAN A LANGUAGE MODEL
A model would be free to produce a sentence no measurement supports, which is
exactly the failure this project spent nine hypotheses avoiding. Rules can be
unit-tested against the numbers they quote; prose cannot. A model can be layered
on top later to rephrase these findings, but it must not be the thing that
decides what is true.
"""

from __future__ import annotations

from .models import CEILING_COHORT_EXP_R, CEILING_KINDS, Advice, Note, TradePlan, Zone, ZoneKind, ZoneSide
from .plan import pct

# Each formation, and what the leg names actually mean. The reversal ones are
# the ones people misread: DBR is a drop that STOPPED, which is why it is demand.
FORMATIONS: dict[ZoneKind, tuple[str, str]] = {
    ZoneKind.DBR: ("Drop-Base-Rally",
                   "harga turun, berhenti, lalu naik - jadi ini demand pembalikan"),
    ZoneKind.RBR: ("Rally-Base-Rally",
                   "harga naik, jeda, lalu lanjut naik - demand penerusan"),
    ZoneKind.RBD: ("Rally-Base-Drop",
                   "harga naik, berhenti, lalu turun - supply pembalikan"),
    ZoneKind.DBD: ("Drop-Base-Drop",
                   "harga turun, jeda, lalu lanjut turun - supply penerusan"),
    ZoneKind.FVG: ("Fair Value Gap",
                   "tiga lilin yang sumbunya tidak bersentuhan, jadi ada pita "
                   "harga yang dilewati tanpa transaksi dua arah"),
    ZoneKind.OB: ("Order Block",
                  "lilin berlawanan terakhir sebelum gerakan impulsif"),
    # Peran kotaknya berbalik, bukan kotak baru: harga menutup melewatinya, lalu
    # pita yang sama dibaca dari arah sebelah. Penjelasannya harus menyebut
    # hasil ukurnya, karena inilah satu-satunya konstruk di daftar ini yang
    # doktrinnya jual sebagai arah dan H8 justru mengukurnya NEGATIF signifikan
    # di ketiga detektor: tahu sebuah kotak terbalik membuat tebakan arah lebih
    # buruk daripada tidak tahu.
    ZoneKind.IFVG: ("Inversion Fair Value Gap",
                    "gap yang ditembus penutupan, lalu dibaca dari sisi "
                    "sebaliknya - diukur di sini TIDAK membawa arah"),
    ZoneKind.BRK: ("Breaker Block",
                   "order block yang ditembus penutupan, lalu dibaca dari sisi "
                   "sebaliknya - diukur di sini TIDAK membawa arah"),
}


def explain(zone: Zone, plan: TradePlan | None, interval: str) -> Advice:
    kind_name, kind_why = FORMATIONS[zone.kind]
    side = "demand" if zone.side is ZoneSide.DEMAND else "supply"
    height = zone.top - zone.bottom

    notes: list[Note] = [
        Note(
            topic="Bentuknya",
            text=(
                f"Ini {kind_name} di timeframe {interval}: {kind_why}. Kotaknya "
                f"setinggi {height:.4g}, digambar dari lilin base-nya sendiri, "
                f"bukan dari perkiraan."
            ),
            learn="formasi",
        ),
        Note(
            topic="Dua garisnya tidak setara",
            text=(
                f"Garis proksimal di {zone.proximal:.4g} adalah tepi yang ditemui "
                f"harga lebih dulu, dan itu tempat masuknya. Garis distal di "
                f"{zone.distal:.4g} adalah tepi pelindung: kalau harga MENUTUP "
                f"melewatinya, zonanya batal, bukan sekadar tersentuh."
            ),
            learn="garis",
        ),
    ]

    # The departure gate is the one thing here that passed walk-forward in all
    # three bracket geometries, so it is stated as a cohort rate with its own n.
    # Arah dan ambangnya DITURUNKAN dari zonanya. Modul ini menuliskan `0.25`
    # dan `2.0` sebagai literal sampai 5 September 2026, jadi mengubah ambang
    # terukur di `plan.py` tidak mengubah kalimat yang dibaca pengguna di sini.
    ceiling = zone.kind in CEILING_KINDS
    cleared = zone.gate_cleared
    # `str` dari float, bukan `:.2f`: yang pertama memberi "2.0" dan "0.25",
    # yang kedua memberi "2.00" dan memaksa strip yang memakan nol terakhir
    # sampai jadi "2". Koma karena kalimat ini Bahasa Indonesia.
    gate_text = f"{zone.gate_atr}".replace(".", ",")
    if ceiling:
        # ANGKA KOHORT MILIK KIND INI. Keduanya ditulis sebagai literal +0,426
        # dan +0,190 sampai 5 September 2026, yaitu angka FVG, dan dicetak apa
        # adanya di ADVISOR sebuah zona IFVG yang kohortnya +0,345 lawan +0,160.
        below, above = CEILING_COHORT_EXP_R[zone.kind]
        low = f"{below:.3f}".replace(".", ",")
        high = f"{above:.3f}".replace(".", ",")
        cleared_text = (
            f"Itu di bawah gerbang {gate_text} ATR. Kohort {zone.kind.value} "
            f"ini exp_r +{low} R lawan +{high} R yang di atasnya, dan yang "
            f"disortir adalah KERAPATAN STOP: win rate justru turun saat "
            f"plafon diperketat."
        )
        not_cleared_text = (
            f"Itu di ATAS gerbang {gate_text} ATR. Kohort {zone.kind.value} "
            f"ini exp_r +{high} R lawan +{low} R yang di bawahnya."
        )
    else:
        cleared_text = (
            f"Itu di ATAS gerbang {gate_text} ATR. Kohort ini bertahan lebih "
            f"tinggi di walk-forward."
        )
        not_cleared_text = (
            f"Itu di BAWAH gerbang {gate_text} ATR. Kohort ini bertahan lebih "
            f"rendah di walk-forward."
        )
    notes.append(Note(
        topic="Seberapa layak dipercaya",
        text=(
            f"Kaki keluarnya {zone.departure_atr:.2f} ATR. "
            + (cleared_text if cleared else not_cleared_text)
        ),
        learn="panel",
    ))

    if plan is not None:
        notes.append(Note(
            topic="Umurnya",
            text=(
                f"Zona ini berumur {plan.age_bars} bar. Kelompok seumur ini "
                f"bertahan {pct(plan.age_held_rate)}. Yang meluruh adalah WAKTU, "
                f"bukan jumlah sentuhan - pembacaan jumlah sentuhan dulu tampak "
                f"kuat lalu runtuh jadi 77,2 / 77,2 / 77,1 persen begitu "
                f"dibandingkan pada umur yang sama."
            ),
            learn="siklus",
        ))

        target = (
            f"Targetnya {plan.target:.4g}, yaitu zona lawan terdekat yang masih "
            f"hidup, jadi {plan.reward_r:.2f}R."
            if plan.target is not None and plan.reward_r is not None
            else "Tidak ada zona lawan hidup di depannya, jadi tidak ada target "
                 "yang bisa dibaca dari chart. Angka apa pun di situ akan jadi "
                 "konvensi, bukan bacaan."
        )
        notes.append(Note(
            topic="Kalau kamu masuk di sini",
            text=(
                f"Entry {plan.entry:.4g}, stop {plan.stop:.4g}, jadi risikonya "
                f"{plan.risk_per_unit:.4g} per unit. {target}"
                + (
                    f" Spread {plan.spread_charged:.4g} sudah dibebankan ke entry "
                    f"maupun stop, karena stop dieksekusi di sisi buku yang "
                    f"berlawanan dengan entry."
                    if plan.spread_charged is not None else ""
                )
            ),
            learn="jalan",
        ))

        for warning in plan.warnings:
            notes.append(Note(topic="Perhatian", text=warning, learn=None))

    # Always last, always present. This is the finding, not a disclaimer.
    notes.append(Note(
        topic="Yang TIDAK bisa saya katakan",
        text=(
            f"Apakah harga akan datang ke {side} ini, dan ke mana ia pergi "
            f"sesudahnya. Dua belas hipotesis arah pre-registered diuji di "
            f"proyek ini dan dua belasnya nol; dua yang terakhir bahkan gagal "
            f"ke arah kebalikan "
            f"doktrinnya. Gambar ini memberitahu DI MANA, bukan KE MANA. Arah "
            f"harus datang dari kamu atau dari sesuatu di luar gambar ini."
        ),
        learn="apa",
    ))

    return Advice(zone_id=zone.id, notes=notes)
