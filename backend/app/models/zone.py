"""The zone itself, and the drawing that carries every shape."""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from .primitives import Anatomy, Displacement, Refinement, ZoneKind, ZoneSide, ZoneState
from .structure import FibonacciAnchor, SessionQuarter, StructureEvent, SwingPoint, TrueOpenLevel
from .gaps import EventHorizonLevel, GapStack, NewsEvent, OpeningGap, TierHorizon
from .liquidity import LiquidityPool, NamedLevel, RangeProjection
from .cycle import (
    CISDEvent,
    DefiningRangeBand,
    SMTDivergence,
    SSMTDivergence,
    VortexDial,
)
from .expectation import ExpectationFan
from .chart_gaps import ChartGapModel
from .wyckoff import WyckoffPhaseModel, WyckoffRangeModel
from .psp import PSPModel

#: Ambang gerbang departure dalam ATR, dan ARAHNYA berbeda per kind.
#:
#: SATU SUMBER, karena sebelumnya ada tiga. `plan.py` memegang kedua konstanta
#: ini, `advisor.py` menuliskan angka yang sama sebagai literal `0.25` dan
#: `2.0` di enam tempat, dan keduanya mengulang `kind in (FVG, IFVG)`
#: sendiri-sendiri. Zone card di frontend akan jadi sumber keempat kalau
#: menghitungnya sendiri. `layers.py:100-106` sudah mencatat bahaya yang persis
#: sama untuk id layer: sebuah daftar kedua melenceng dari yang pertama tanpa
#: suara.
#:
#: 2,0 ATR adalah LANTAI untuk formasi supply/demand, dan alasannya ada di
#: deskripsi `departure_atr` di bawah. 0,25 ATR adalah PLAFON untuk FVG dan
#: IFVG, karena di sana gerbangnya terukur TERBALIK:
#:
#:   FVG   exp_r +0,426 R di bawah plafon lawan +0,190 R di atasnya,
#:         welch t=4,58, walk-forward 8 dari 8. docs/QA-FVG-RECALIBRATION.md
#:   IFVG  exp_r +0,3450 lawan baseline +0,2348, welch t=+5,18, walk-forward
#:         8 dari 8, n=11.068 di 12 sel. docs/QA-IFVG-GATE.md, 5 Sep 2026.
#:         Arah plafon menang di SETIAP ambang yang diuji. Terukur di 15m
#:         sampai 4h; di 1d tandanya konsisten tapi |t| tertinggi 2,909 tidak
#:         melewati Bonferroni 2,914, dan di 1w populasinya 16 trade.
#:
#: PLAFON INI MENYORTIR KERAPATAN STOP, BUKAN KEMUNGKINAN BERHASIL, dan itu
#: harus dibaca bersama angka di atas karena keduanya benar sekaligus. Win rate
#: TURUN monoton saat plafon diperketat - 0,4777 di 3,0 ATR menjadi 0,3967 di
#: 0,1 ATR - sementara mean win naik dari 1,43 R ke 2,41 R dan mean loss hampir
#: tidak bergerak di sekitar -0,9 R.
#:
#: Mekanismenya bisa dinamai. Untuk FVG `departure_atr` ADALAH TINGGI GAP dalam
#: ATR (`detect/imbalance.py`, `size = (top - bottom) / scale`), bukan jarak
#: kaki keluar seperti pada supply/demand. `plan.py` menaruh target di zona
#: lawan terdekat dan stop di luar distal, jadi reward adalah jarak ABSOLUT ke
#: zona lawan sementara risk adalah tinggi box plus buffer. Plafon yang lebih
#: ketat menyimpan gap yang lebih kecil, gap yang lebih kecil memberi stop yang
#: lebih rapat, dan R dinormalisasi terhadap risk. exp_r dan profit factor tetap
#: naik karena keduanya dinormalisasi risiko, jadi plafon ini tetap berguna
#: sebagai PENYORTIR - tetapi harga justru lebih SERING kena stop pada kohort
#: yang ia pertahankan, dan siapa pun yang membacanya sebagai "setup yang lebih
#: sering benar" membacanya terbalik. Berlaku sama untuk kedua kind.
DEPARTURE_GATE_ATR = 2.0
#: TIDAK BERGERAK saat `detect_fvg` menukar skalanya dari Wilder ke
#: `mean_true_range` pada 7 September 2026, dan itu diperiksa bukan diasumsikan.
#: Ambang yang menyamakan populasi dihitung terpisah di delapan sel - XAUUSD dan
#: BTCUSD kali 30m, 1h, 4h, 1d - dan keluar 0,2434 sampai 0,2573. Semuanya di
#: dalam pembulatan angka ini, jadi menukar skalanya adalah perubahan tanpa
#: kalibrasi ulang. Bandingkan rentang lilin tengah, yang butuh 0,1945 sampai
#: 0,2275: itu kalibrasi ulang sungguhan, dan salah satu dari tiga alasan ia
#: tidak dipakai.
# DIPERIKSA ULANG 7 September 2026 dan TIDAK LOLOS, docs/QA-FVG-TV.md bagian 21.
# Angka ini dikalibrasi dua kali di atas dasar yang sudah tidak berlaku:
# `replay_lifecycle` yang memeriksa pecah sebelum sentuh, dan bracket harness
# yang bukan bracket produksi. Di harness yang sudah disamakan, XAUUSD 4 jam,
# MEMATIKAN gerbang mengalahkannya - PF 1,111 pada 4.156 trade lawan 1,091 pada
# 1.709 - dan di bawah disiplin pilih-di-paruh-pertama gerbang mati juga yang
# menang (1,052 lawan 1,007), dengan luar-sampel 1,158 pada 2.053 trade.
# Kurvanya tidak monoton (0,10 -> 1,013, 0,15 -> 1,169, 0,25 -> 1,091), bentuk
# yang menandai derau bukan ambang.
#
# LALU DIPERIKSA DI DUA SEL LAGI dan hasilnya BERBALIK, bagian 23.1. Di XAUUSD
# 1 jam gerbang mati memberi 0,902 lawan 1,006 bergerbang, dan di harian 1,027
# lawan 1,112. Dua dari tiga timeframe bilang gerbangnya membayar, jadi 4 jam
# yang pengecualian. Ambangnya BERTAHAN, dan sekarang atas dasar tiga sel yang
# diukur di harness yang benar - bukan atas dasar kalibrasi lama yang dasarnya
# sudah tidak berlaku.
DEPARTURE_GATE_ATR_CEILING = 0.25

#: Lantai PER KIND, karena 2,0 tidak selamat di setiap detector yang memakainya.
#:
#: supply/demand tetap 2,0: itu angka yang diukur untuknya di
#: `docs/QA-QUANT.md` bagian 6, selisih ekspektasi +0,124 R dengan Welch
#: t=+4,82.
#:
#: ORDER BLOCK SEMPAT 2,5 SELAMA SATU HARI, LALU KEMBALI KE 2,0, dan urutan
#: kejadiannya adalah isi catatan ini.
#:
#: Pagi 6 September 2026 `docs/QA-OB-GATE.md` menyapu tujuh ambang di 12 sel,
#: n=13.309, dan menemukan 2,0 gagal walk-forward 7 dari 8 sementara 2,5 lolos
#: 8 dari 8 dengan exp_r +0,0551 lawan +0,0281. Jadi lantai OB dinaikkan.
#:
#: Sore harinya detector-nya sendiri diperbaiki - kotak dari badan lilin, impuls
#: diukur ke close - dan gerbangnya DIUKUR ULANG pada populasi baru itu. Ia
#: tidak memisahkan lagi:
#:
#:     tanpa gerbang   n=7.777  exp_r +0,1600  PF 1,320
#:     lantai 2,0      n=4.582  exp_r +0,1705  PF 1,333   tidak memisahkan
#:     lantai 2,5      n=2.829  exp_r +0,1451  PF 1,275   tidak memisahkan
#:     lantai 3,0      n=1.784  exp_r +0,1307  PF 1,241   tidak memisahkan
#:
#: 2,5 MERUGIKAN sekarang, PF 1,275 lawan baseline 1,320. Sebabnya bisa
#: dinamai: filter impuls-dari-close sudah membuang populasi impuls lemah yang
#: dulu ditangkap gerbang departure, jadi keduanya menyaring hal yang sama dan
#: yang tersisa cuma memotong trade bagus. Tidak ada satu ambang pun yang lolos
#: praregistrasi pada detector baru.
#:
#: Dikembalikan ke 2,0, yang terukur PF 1,333 lawan 1,320 - selisih yang tidak
#: signifikan, jadi ia tidak merugikan. Dan dengan itu OB berhenti jadi kasus
#: khusus: divergensi per-kind yang diperkenalkan pagi itu tidak punya dasar
#: lagi. Peta ini dipertahankan karena BENTUKNYA yang mengikat - ia memaksa
#: kind baru menyatakan lantainya alih alih mewarisi diam diam.
FLOOR_GATE_ATR: dict[ZoneKind, float] = {
    ZoneKind.RBR: DEPARTURE_GATE_ATR,
    ZoneKind.DBR: DEPARTURE_GATE_ATR,
    ZoneKind.DBD: DEPARTURE_GATE_ATR,
    ZoneKind.RBD: DEPARTURE_GATE_ATR,
    ZoneKind.OB: DEPARTURE_GATE_ATR,
    ZoneKind.BRK: DEPARTURE_GATE_ATR,
    # OTE MENYATAKAN LANTAINYA, karena peta ini memaksa setiap kind baru
    # melakukannya. Doktrin OTE sendiri tidak membawa gerbang - ia aturan
    # tempat masuk, bukan aturan seleksi - jadi 2,0 di sini adalah PADANAN
    # yang dipilih, bukan angka yang diwarisi: ia mengukur panjang leg yang
    # membuat pitanya, sebagaimana empat kind di atas mengukur keberangkatan.
    ZoneKind.OTE: DEPARTURE_GATE_ATR,
    # NOL, dinyatakan, sama alasannya dengan detektor kotak peristiwa lain:
    # tinggi kotak CISD ADALAH jarak stopnya, jadi menggerbanginya memilih
    # antara 'cuma run besar' dan 'cuma stop rapat' dan tidak satu pun
    # bersumber. Ia disapu di TradingView, bukan ditebak di sini.
    ZoneKind.CISD: 0.0,
}
#: Kind yang gerbangnya plafon, bukan lantai.
#:
#: BRK TIDAK DI SINI, dan itu keputusan yang belum punya angka. Ia mewarisi
#: `departure_atr` dari order block induknya lewat mekanisme yang persis sama
#: dengan IFVG, lalu dinilai dengan lantai 2,0 ATR yang tidak pernah diukur
#: untuknya. SUDAH DIUKUR sejak 7 September 2026 dan kalimat di atas ketinggalan:
#: lihat paragraf `GATE_UNMEASURED_KINDS` di bawah (n=7.410, tidak
#: memisahkan dari 1,0 sampai 6,0) dan sapuan lantai BRK di
#: `docs/QA-OB-GATE.md`, tempat lantainya naik monoton dari 0,953 (mati)
#: ke 1,158 (4,0) lalu runtuh ke 0,861 di luar sampel. Jadi `gate_measured`
#: False untuk BRK sekarang berdiri di atas sapuan yang PERNAH DILAKUKAN
#: dan gagal, bukan di atas yang belum pernah dicoba. Rujukan lama ke
#: bagian penutup `QA-IFVG-GATE.md` juga sudah menggantung, karena bagian
#: itu sendiri sudah digantikan.
CEILING_KINDS = (ZoneKind.FVG, ZoneKind.IFVG)

#: exp_r kedua kohort plafon, PER KIND, sebagai (di bawah plafon, di atasnya).
#:
#: PER KIND KARENA PANEL PERNAH MENGUTIP ANGKA MILIK POPULASI LAIN. Sampai
#: 5 September 2026 `plan.py` dan `advisor.py` memegang satu pasang konstanta,
#: +0,426 dan +0,190, yang diukur pada FVG - dan mencetaknya di panel PLAN
#: sebuah zona IFVG. Angkanya terlihat persis seterukur angka yang benar.
#: Terlihat di layar hari itu pada zona IFVG 0,37 ATR: "Kohort ini exp_r
#: +0.190 R, lawan +0.426 R yang di bawah gerbang", sementara kohort IFVG yang
#: sebenarnya adalah +0,1597 lawan +0,3450.
#:
#: PRA-PERBAIKAN LIFECYCLE, DAN ITU BELUM PERNAH DICATAT DI SINI. Kedua
#: pasang diukur pada lifecycle yang memeriksa PECAH SEBELUM SENTUH.
#: Untuk FVG, sapuan yang sama sesudah diperbaiki memberi +0,0919 R di
#: t=+1,88 pada sisi BAWAH plafon - di bawah ambang Bonferroni 3,241 yang
#: dipakai sapuan aslinya - jadi +0,426 melebih-lebihkan sekitar 4,6 kali.
#: Untuk IFVG, `layers.py` mencatat bahwa setiap angka di
#: QA-IFVG-GATE.md sebelum bagian penutupnya mendahului perbaikan itu.
#:
#: TABELNYA TIDAK DIHAPUS dan angkanya tidak diganti, karena pasangan
#: terkoreksinya BELUM DIUKUR: tabel pasca-perbaikan di QA-FVG-TV.md
#: membandingkan gerbang MATI lawan 0,25, bukan kohort bawah lawan atas.
#: Mengarang pasangan baru akan mengulang persis kesalahan yang dicatat di
#: atas. Yang berubah 8 September 2026: `advisor.py` dan `plan.py` berhenti
#: mencetaknya sebagai angka BERLAKU dan menyebutnya pra-perbaikan.
#: Menyalakannya kembali sebagai klaim butuh sapuan kohort pasca-perbaikan.
#:
#:   FVG   docs/QA-FVG-RECALIBRATION.md
#:   IFVG  docs/QA-IFVG-GATE.md, n=11.068, 4.484 di bawah dan 6.584 di atas
CEILING_COHORT_EXP_R: dict[ZoneKind, tuple[float, float]] = {
    ZoneKind.FVG: (0.426, 0.190),
    ZoneKind.IFVG: (0.345, 0.160),
}

#: Keempat formasi supply/demand, yang survival rate-nya diukur di
#: `docs/QA-QUANT.md` bagian 6. Dinamai karena `plan.py` perlu membedakan
#: "punya survival rate sendiri" dari "kind lantai": OB dan BRK adalah kind
#: lantai dan tidak punya satu pun.
SUPPLY_DEMAND_KINDS = (ZoneKind.RBR, ZoneKind.DBR, ZoneKind.DBD, ZoneKind.RBD)

#: Kind yang verdict gerbangnya TIDAK LAYAK DITAMPILKAN, dan alasannya berbeda
#: per kind.
#:
#: SETIAP KIND MENDAPAT `gate_atr` DAN `gate_cleared`, karena keduanya
#: diturunkan dan tidak punya cara mengembalikan "tidak tahu". Daftar ini yang
#: menahan verdict itu di permukaan yang menampilkannya.
#:
#: BRK, SAMPAI 6 SEPTEMBER 2026, ada di sini karena BELUM PERNAH DIUKUR: ia
#: mewarisi `departure_atr` dari order block induknya lewat mekanisme yang sama
#: dengan IFVG, lalu dinilai dengan ambang milik induknya.
#:
#: SEKARANG IA TERUKUR, DAN TETAP DI SINI, dengan alasan yang berbalik.
#: `docs/QA-BRK-GATE.md`, 12 sel dan n=7.410: gerbangnya TIDAK MEMISAHKAN di
#: satu ambang pun dari 1,0 sampai 6,0. Baseline tanpa gerbang exp_r +0,2618
#: dengan t=+12,60, dan tiap lantai cuma memangkas populasi tanpa selisih yang
#: melewati Bonferroni. Sebuah verdict yang ditampilkan menyiratkan pemisahan
#: yang pengukurannya justru bantah, jadi ia tetap ditahan - bukan karena tidak
#: ada angkanya, melainkan karena angkanya mengatakan tidak ada gerbang.
#:
#: Yang SUDAH diukur DAN memisahkan, dengan sumbernya: keempat kind
#: supply/demand pada lantai 2,0 (`docs/CALIBRATION.md`), FVG pada plafon 0,25
#: (`docs/QA-FVG-RECALIBRATION.md`), IFVG pada plafon 0,25
#: (`docs/QA-IFVG-GATE.md`).
#:
#: OB TIDAK DI SINI meski gerbangnya juga berhenti memisahkan setelah detector
#: itu diperbaiki, dan itu perbedaan yang disengaja: lantainya masih MENGIKAT
#: jalur order-nya lewat `tools/execute.py`, jadi pembaca berhak melihat
#: verdict yang benar-benar menentukan apakah sebuah order dikirim.
#: OTE MASUK SEJAK 8 September 2026, dan alasannya lebih bersih daripada
#: BRK. BRK ada di sini karena mewarisi lantai induknya lalu gagal saat
#: lantainya sendiri disapu; OTE ada di sini karena doktrinnya TIDAK PUNYA
#: gerbang sama sekali. OTE aturan tempat masuk, bukan aturan seleksi, jadi
#: lantai 2,0 ATR pada panjang leg adalah padanan yang dipilih supaya ia
#: sebanding dengan empat detektor lain - dan permukaan yang menampilkan
#: verdict harus menahan diri sampai ia benar benar disapu.
GATE_UNMEASURED_KINDS = (ZoneKind.BRK, ZoneKind.OTE, ZoneKind.CISD)


class Zone(BaseModel):
    id: str
    kind: ZoneKind
    side: ZoneSide
    state: ZoneState
    timeframe: str = Field(
        default="",
        description=(
            "The timeframe whose candles formed this zone. Equal to the chart's "
            "interval for local zones, higher for projected ones. Supply and "
            "demand is a top-down method, so which timeframe drew a zone is part "
            "of what the zone means, not metadata."
        ),
    )

    # Geometry. top/bottom are absolute prices; proximal is the edge price
    # meets first on the way back, distal is the protective far edge.
    top: float
    bottom: float
    proximal: float
    distal: float

    time_from: int = Field(description="Left edge: base open time, epoch seconds")
    time_to: int = Field(
        description="Right edge: break time if broken, else last bar time"
    )

    formation_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How cleanly the zone was BUILT: base tightness, base compactness "
            "and leg-out volume, equally weighted. It is not a forecast, and it "
            "is WORSE than useless as a ranking: measured on 2707 resolved zones "
            "across five series it ranks BACKWARDS, AUC 0.464 and 0.477, so a "
            "higher score goes with a slightly worse outcome. Use it to order "
            "the display, never to rank opportunity. See docs/CALIBRATION.md."
        ),
    )
    departure_atr: float = Field(
        description=(
            "Size of the leg-out move in ATR at the base. This one IS validated, "
            "as a threshold rather than a gradient, and as a SORTER rather than a "
            "picker. On the instrument actually traded, on 5-minute bars, "
            "formations clearing 2 ATR held 43.0% against 40.2% - a hold-rate "
            "difference that is NOT significant. What is significant is the "
            "expectancy gap, +0.124 R at t=+4.82. The 85.8 against 64.4 this "
            "field used to quote was measured on Binance crypto, not on this "
            "instrument. Above 2 ATR more departure buys nothing. "
            "Two limits on reading it. The validation is a FIRST-TOUCH result: "
            "measured at touch 2 and later the same gate separates outcomes by "
            "-0.2, -2.5 and -4.3 points across the three geometries, so a zone "
            "that has already been visited carries no filter this project has "
            "validated. And on an IFVG or a BRK this number describes the leg "
            "that built the PARENT box, not the inversion - the inverted box was "
            "made by a close through a level, which has no leg to measure. "
            "`displacement` is left None there for the same reason."
        )
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gate_atr(self) -> float:
        """Ambang gerbang departure yang berlaku untuk kind ini, dalam ATR.

        Diturunkan, bukan dikirim, supaya pembaca mana pun - panel, advisor,
        executor, zone card - membandingkan `departure_atr` dengan angka yang
        sama.
        """
        if self.kind in CEILING_KINDS:
            return DEPARTURE_GATE_ATR_CEILING
        return FLOOR_GATE_ATR[self.kind]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gate_cleared(self) -> bool:
        """Apakah zona ini lolos gerbang departure-nya sendiri.

        ARAHNYA yang penting, dan itu yang membuat field ini ada. Untuk FVG dan
        IFVG lolos berarti departure di BAWAH plafon; untuk sisanya lolos
        berarti di ATAS lantai. Sebuah pembaca yang cuma melihat
        `departure_atr` tidak bisa tahu mana yang berlaku tanpa menghafal
        arahnya per kind, dan itu tepatnya kenapa zone card dulu memajang
        angkanya tanpa verdict.

        BACA BERSAMA `settled`. Selama `settled` masih False, window departure
        belum selesai tercetak, jadi verdict di sini masih bisa bergerak.
        """
        if self.kind in CEILING_KINDS:
            return self.departure_atr < DEPARTURE_GATE_ATR_CEILING
        return self.departure_atr >= FLOOR_GATE_ATR[self.kind]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gate_measured(self) -> bool:
        """Apakah ambang yang `gate_cleared` pakai pernah diukur untuk kind ini.

        `gate_cleared` selalu menjawab, karena ia aritmetika dan tidak punya
        cara mengembalikan "tidak tahu". Field ini yang membawa perbedaan itu,
        supaya permukaan yang menampilkan verdict bisa menahan diri di kind
        yang ambangnya diwarisi alih alih diukur. Hari ini itu cuma BRK.
        """
        return self.kind not in GATE_UNMEASURED_KINDS

    # NONE BERARTI TIDAK DIHITUNG, DAN ITU SEBABNYA KELIMA FIELD DI BAWAH
    # OPTIONAL. Semuanya hanya diisi oleh `detect/supply_demand.py`.
    # `detect/imbalance.py` tidak pernah mengirimkannya, jadi setiap FVG, OB,
    # IFVG dan BRK dulu memakai default model - dan default itu dirender panel
    # sebagai hasil pengukuran.
    #
    # Yang terjadi di layar sebelum 5 September 2026, pada zona FVG mana pun:
    #
    #     curve            0.5   ->  "50%", yaitu ekuilibrium, dan doktrinnya
    #                                menyebut ekuilibrium formasi LEMAH. Sebuah
    #                                pembacaan yang bermakna, tidak pernah diukur
    #     base_overlap     1.0   ->  `consolidation_quality` menjawab "original",
    #                                verdict BAIK, untuk kotak yang tidak punya
    #                                base sama sekali
    #     base_drift       0.0   ->  "0.00", terbaca base sempurna tanpa drift
    #     profit_margin    0.0   ->  "0.0x zone", terbaca terukur nol
    #     curve_favourable False ->  verdict negatif yang tidak pernah dinilai
    #
    # Membuatnya `None` tidak menyentuh satu baris pun di kedua detector:
    # `supply_demand` tetap mengirim angkanya, `imbalance` tetap tidak
    # mengirim apa pun. Yang berubah adalah apa yang bisa dibaca pembacanya.
    profit_margin: float | None = Field(
        default=None,
        description=(
            "Leg-out travel as a multiple of the zone's own height. This is the "
            "doctrine's own test, and the only hard number in it: a base is not "
            "a level unless the initial move away is at least 3x the level. "
            "Gated only if `min_profit_margin` is set. None on the imbalance "
            "detectors, which never compute it - a gap has no base whose height "
            "the leg-out could be a multiple of."
        ),
    )
    curve: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Where the zone sits in the prevailing range, 0 at the low and 1 at "
            "the high, measured only on bars that preceded it. The doctrine's "
            "'curve': demand is wholesale near 0, supply is retail near 1, and a "
            "textbook formation sitting at equilibrium is held to be a weak one "
            "because that is where imbalance is smallest. None on the imbalance "
            "detectors. It defaulted to 0.5 until 5 September 2026, which is "
            "exactly the equilibrium the doctrine calls weak, so every FVG "
            "reported the one reading nobody measured for it."
        ),
    )
    curve_favourable: bool | None = Field(
        default=None,
        description=(
            "True when the zone is on the useful side of the curve for its own "
            "side: demand in the lower third, supply in the upper third. None "
            "where `curve` is None, because the verdict has no input."
        ),
    )
    profit_zone_rr: float | None = Field(
        default=None,
        description=(
            "Distance from this zone's proximal line to the nearest live "
            "opposing zone, in units of this zone's own height. The doctrine's "
            "most-overlooked enhancer, and the reason zone validity depends on "
            "the pair of zones rather than on one alone. None when no opposing "
            "zone stands in the way."
        ),
    )
    crowded_at: int | None = Field(
        default=None,
        description=(
            "When a NEWLY FORMED opposing zone first pushed this zone's profit "
            "zone below `min_profit_zone_rr`, epoch seconds. The guidance says a "
            "zone stops being worth trading when the road ahead of it closes, "
            "which means validity has to be re-checked when ANOTHER ZONE IS "
            "BORN, not only when price moves. Every other lifecycle field here "
            "answers 'what did price do'; this one answers 'what did the rest of "
            "the chart do', and mixing the two into `state` would hide which "
            "cause applied. None when the road never closed."
        ),
    )
    refinement: Refinement | None = Field(
        default=None,
        description=(
            "Set when this zone was shrunk to the lower-timeframe base inside "
            "it. Carries the geometry it had before, so the refinement can be "
            "audited or undone. None when the zone was never refined."
        ),
    )
    arrival_atr: float | None = Field(
        default=None,
        description=(
            "How hard price travelled into the zone over the bars before its "
            "first touch, in ATR. Sources contradict each other on whether a "
            "fast arrival is good or bad, so this is measured rather than "
            "scored. None until the zone has been touched."
        ),
    )
    # Two descriptions of whether the base actually paused. Reported, not yet
    # filtered on: see docs/CALIBRATION.md before turning either into a gate.
    base_drift: float | None = Field(
        default=None,
        description=(
            "One-way travel across the base as a fraction of the base's own "
            "height. Near 0 means price came back to where it started; near 1 "
            "means the 'base' was a staircase that never paused. None on the "
            "imbalance detectors, which draw a gap rather than a base."
        ),
    )
    base_overlap: float | None = Field(
        default=None,
        description=(
            "Mean shared range between consecutive base bars. A real "
            "consolidation revisits the same prices; a slow trend does not. "
            "None on the imbalance detectors. It defaulted to 1.0, the perfect "
            "score, which pushed `consolidation_quality` to answer `original` "
            "for every gap in the engine."
        ),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def consolidation_quality(self) -> str | None:
        """`original` / `staircase` / `borderline`, read from the two base fields.

        A staircase (`base_drift` near 1) is a fake consolidation that never
        paused; a real consolidation (`base_overlap` near 1) revisits the same
        prices. The thresholds are the same 0.6 the `max_base_drift` gate uses,
        and 0.5 overlap, both stated rather than measured. Surfaces the verdict
        the two raw fields imply, so a reader does not have to derive it.

        None where there is no base to judge. Sebelum kedua field di atas jadi
        optional, verdict ini menjawab `original` - nilai TERBAIKNYA - untuk
        setiap FVG, OB, IFVG dan BRK, karena `base_overlap` default 1.0
        melewati ambang 0,5 tanpa ada satu bar base pun yang diperiksa.
        """
        if self.base_drift is None or self.base_overlap is None:
            return None
        if self.base_drift >= 0.6:
            return "staircase"
        if self.base_overlap >= 0.5:
            return "original"
        return "borderline"


    inverted_at: int | None = Field(
        default=None,
        description=(
            "IFVG and BRK only: when price closed through the original box, "
            "epoch seconds. `side` is the side the box became, and `distal` its "
            "far edge read from the new direction, so the geometry is the old "
            "rectangle entered from the other side rather than a new box."
        ),
    )
    dealing_range_pos: float | None = Field(
        default=None,
        description=(
            "ICT premium/discount: where the zone's proximal line sat inside the "
            "swing-to-swing dealing range AT ITS FIRST TOUCH, 0 at the range low "
            "and 1 at the high. This is NOT `curve`, and the difference is the "
            "deviation docs/FIDELITY.md listed: `curve` is a 200-bar rolling "
            "range split in thirds and frozen when the zone was born, which is "
            "the Seiden reading. ICT reads the position at the moment price "
            "arrives, on a range anchored to the last confirmed swing high and "
            "low. None until the zone has been touched, or when no dealing range "
            "could be established."
        ),
    )
    displacement: Displacement | None = Field(
        default=None,
        description=(
            "The qualifying leg as an object rather than a threshold. None for "
            "detectors that have no displacement concept."
        ),
    )
    structure_break_time: int | None = Field(
        default=None,
        description=(
            "Order block only, and only when `require_structure_break` is on: "
            "the break this block's impulse produced. None means the block was "
            "admitted without a structural requirement, which is this engine's "
            "default and its largest remaining ICT departure."
        ),
    )

    nested_in: list[str] = Field(
        default_factory=list,
        description=(
            "Higher timeframes whose zone of the same side encloses this one, "
            "and which already existed when this zone formed. The one "
            "multi-timeframe claim every school of this method agrees on, and "
            "one nobody has published a number for. Reported, not scored."
        ),
    )

    touches: int = 0
    penetration_pct: float = Field(
        default=0.0, description="Deepest entry into the zone, 0..1 of its height"
    )
    first_test_time: int | None = None

    settled: bool = Field(
        default=True,
        description=(
            "Every reported field for this zone is final given closed bars: the "
            "leg-out run has ended AND the departure window that decided the "
            "gate has fully printed. This is the flag `confirmed` was mistaken "
            "for. A zone that is confirmed but not settled still has a gate "
            "verdict that can move."
        ),
    )
    confirmed: bool = Field(
        default=True,
        description=(
            "False while the leg-out is still the newest run: the run can grow "
            "with the next bar, so the zone may still shift. The UI draws these "
            "dashed. "
            "It does NOT mean the zone is final, and its docstring used to claim "
            "exactly that. An audit measured a confirmed zone's departure_atr "
            "growing on 101 of 599 bar formations, its state changing 24 times "
            "and reverting 21, and the flag itself flipping True to False when a "
            "later bar extended the leg-out. Read it as `leg_out_open`, inverted. "
            "For finality use `settled`."
        ),
    )

    anatomy: Anatomy
    factors: dict[str, float] = Field(
        default_factory=dict, description="Score breakdown, sums to `formation_score`"
    )
    note: str = Field(default="", description="One-line human-readable rationale")


class Drawing(BaseModel):
    """Envelope for everything the engine draws: boxes, pivots and structure."""

    zones: list[Zone] = Field(default_factory=list)
    swings: list[SwingPoint] = Field(
        default_factory=list,
        description="Confirmed pivots, empty unless structure was requested",
    )
    structure: list[StructureEvent] = Field(
        default_factory=list,
        description=(
            "Breaks, sweeps and shifts, empty unless structure was requested. "
            "Ordered by time. Carries no direction claim: see StructureEvent."
        ),
    )
    fibonacci: FibonacciAnchor | None = Field(
        default=None,
        description=(
            "The two structural swing anchors the Fibonacci/OTE grid is drawn "
            "over: most recent confirmed swing low and high. None until the "
            "structure layer has confirmed a swing on both sides."
        ),
    )
    quarters: list[SessionQuarter] = Field(
        default_factory=list,
        description="Quarter divisions, empty unless a degree was requested",
    )
    vortex: VortexDial | None = Field(
        default=None,
        description=(
            "The 3-6-9 dial: digital roots of ring x sector, plus which ninth "
            "of each cycle the newest bar sits in. None unless the vortex layer "
            "was requested. CARRIES NO PRICE - it is arithmetic on the "
            "calendar, and nothing downstream of the renderer reads it."
        ),
    )
    true_opens: list[TrueOpenLevel] = Field(
        default_factory=list,
        description="True opens, empty unless a degree was requested",
    )
    dfr: list[DefiningRangeBand] = Field(
        default_factory=list,
        description=(
            "Defining ranges with their equilibrium and projections, empty "
            "unless the dfr layer was requested. Read off the bars already "
            "fetched, so it costs no provider call. The checklist reports the "
            "same object as a READING, without projections."
        ),
    )
    ssmt: list[SSMTDivergence] = Field(
        default_factory=list,
        description=(
            "Cross-instrument divergences positioned on THIS symbol's price, "
            "empty unless the ssmt layer was requested. The same events also "
            "appear in the checklist as `SSMTHit`, which is the reading; "
            "these are the shape. Costs one provider call per partner."
        ),
    )
    smt: list[SMTDivergence] = Field(
        default_factory=list,
        description=(
            "Regular (non-sequential) SMT divergences on this symbol's price. "
            "Liquidity readings rather than trend confirmations: one instrument "
            "took the running extreme, the other failed. Drawn as markers, not "
            "segments. Empty unless the ssmt layer was requested."
        ),
    )
    gaps: list[OpeningGap] = Field(
        default_factory=list,
        description="NDOG and NWOG bands, empty unless gaps were requested",
    )
    news: list[NewsEvent] = Field(
        default_factory=list,
        description="Scheduled releases in the chart's window. Empty unless requested.",
    )
    tier_horizons: list[TierHorizon] = Field(
        default_factory=list,
        description="One zone per gap kind. Empty unless gaps were requested.",
    )
    gap_stacks: list[GapStack] = Field(
        default_factory=list,
        description="Overlaps between gaps of different kinds. Empty unless gaps were requested.",
    )
    event_horizons: list[EventHorizonLevel] = Field(
        default_factory=list,
        description=(
            "Levels between adjacent gaps in PRICE order. Empty unless gaps were "
            "requested. These MOVE when a new gap appears: see EventHorizonLevel."
        ),
    )
    cisd: list[CISDEvent] = Field(
        default_factory=list,
        description="Delivery-state changes, empty unless requested. Ordered by time.",
    )
    pools: list[LiquidityPool] = Field(
        default_factory=list,
        description=(
            "Session extremes as candidate targets, empty unless requested. Zones "
            "are targets the same way, and are NOT duplicated here: an untouched "
            "box is already identifiable from `zones` by its own state."
        ),
    )
    levels: list[NamedLevel] = Field(
        default_factory=list,
        description="PDH, PDL, PWH, PWL and the named day extremes. Empty unless requested.",
    )
    projections: list[RangeProjection] = Field(
        default_factory=list,
        description="Deviation stacks off named ranges. Empty unless requested.",
    )
    expectation: ExpectationFan | None = Field(
        default=None,
        description=(
            "The expectation overlay's reading: measured R distributions for this "
            "cell, looked up from a precomputed table. None unless the expectation "
            "layer was requested, or when the cell was never measured."
        ),
    )
    chart_gaps: list[ChartGapModel] = Field(
        default_factory=list,
        description=(
            "Breakaway and measuring gaps, empty unless requested. A trend gap, "
            "not a session gap - see OpeningGap for the difference. Unmeasured."
        ),
    )
    wyckoff: list[WyckoffPhaseModel] = Field(
        default_factory=list,
        description=(
            "Wyckoff phase readings over a rolling trading range: spring, "
            "upthrust, sign of strength, sign of weakness. This is also the "
            "BREAKOUT reading: sos and sow are a range breakout confirmed by "
            "close, spring and upthrust are a false breakout on either side. "
            "A reading, never a bias. Empty unless requested. MEASURED NULL, "
            "docs/wyckoff_outcomes.json."
        ),
    )
    wyckoff_range: WyckoffRangeModel | None = Field(
        default=None,
        description=(
            "The trading range price stands in RIGHT NOW, one box: the last "
            "`lookback` bars. Not an event, so it is not in the list above - "
            "`phases()` only emits bars that touch a range edge. One box "
            "rather than one per phase is an ink-budget decision: at lookback "
            "20 a 500-bar series produces hundreds of phases, and the note in "
            "globals.css measured that past about a third of the chart boxes "
            "stop annotating price and become its background."
        ),
    )
    psp: list[PSPModel] = Field(
        default_factory=list,
        description=(
            "Precision swing points inside the three bars after an SSMT. Empty "
            "unless the psp layer was requested, and empty when the ssmt "
            "partner series could not be loaded. Measured null in "
            "docs/psp_outcomes.json, drawn as a reading."
        ),
    )
