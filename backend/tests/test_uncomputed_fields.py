"""Field yang tidak dihitung sebuah detector harus terbaca None, bukan default.

Lima field di `Zone` hanya diisi oleh `detect/supply_demand.py`.
`detect/imbalance.py` tidak pernah mengirimkannya, jadi sampai 5 September 2026
setiap FVG, OB, IFVG dan BRK memakai default modelnya - dan panel merender
default itu sebagai hasil pengukuran:

    curve            0.5   -> "50%", ekuilibrium, yang doktrinnya sebut formasi
                              LEMAH. Pembacaan bermakna yang tidak pernah diukur
    base_overlap     1.0   -> `consolidation_quality` menjawab "original",
                              verdict BAIK, untuk kotak tanpa base sama sekali
    base_drift       0.0   -> "0.00", terbaca base sempurna tanpa drift
    profit_margin    0.0   -> "0.0x zone"
    curve_favourable False -> verdict negatif yang tidak pernah dinilai

Tidak ada satu pun test lama yang gagal saat kelima default itu masih terpasang,
dan itu sebabnya cacatnya hidup: seluruh test yang menyentuh field-field ini
membangun `Zone` dengan nilai eksplisit, jadi tidak ada yang pernah menanyakan
apa yang DETECTOR kirim. Berkas ini menanyakannya lewat detector sungguhan.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_uncomputed_fields.py -q
"""

from __future__ import annotations

from app.detect.imbalance import detect_fvg, detect_order_block
from app.detect.supply_demand import detect
from app.models import Candle, ImbalanceParams, SupplyDemandParams

STEP = 900
T0 = 1_700_000_000 // 86_400 * 86_400

#: Field yang HANYA supply/demand hitung. `consolidation_quality` ikut karena ia
#: computed field yang membaca dua di antaranya, dan verdict itu yang paling
#: menyesatkan saat inputnya default.
SUPPLY_DEMAND_ONLY = (
    "curve",
    "curve_favourable",
    "base_drift",
    "base_overlap",
    "profit_margin",
    "consolidation_quality",
)


def bar(t: int, o: float, c: float, hp: float = 0.0, lp: float = 0.0) -> Candle:
    return Candle(
        time=t, open=o, close=c, high=max(o, c) + hp, low=min(o, c) - lp,
        volume=1000.0,
    )


def _gap_series() -> list[Candle]:
    """Bar datar, lalu tiga bar yang sumbunya tidak bersentuhan, lalu datar.

    Cukup untuk membuat satu FVG bullish dan satu order block, tanpa ikut
    membangun formasi supply/demand yang lolos.
    """
    rows = [bar(T0 + i * STEP, 100.0, 100.0, 0.3, 0.3) for i in range(20)]
    t = T0 + 20 * STEP
    rows.append(bar(t, 100.0, 99.4, 0.1, 0.2))               # bearish, si block
    rows.append(bar(t + STEP, 99.4, 104.0, 0.3))             # impulse, si celah
    rows.append(bar(t + 2 * STEP, 104.0, 106.0, 0.3))
    rows += [
        bar(t + (3 + i) * STEP, 106.0, 106.0, 0.3, 0.3) for i in range(20)
    ]
    return rows


def _trend_series() -> list[Candle]:
    """Turun, base yang benar benar berhenti, lalu naik. Sebuah DBR."""
    rows = [bar(T0 + i * STEP, 110.0 - i, 109.0 - i, 0.3, 0.3) for i in range(10)]
    t = T0 + 10 * STEP
    rows += [
        bar(t + i * STEP, 100.0, 100.2, 0.3, 0.3) for i in range(4)
    ]                                                         # base yang menahan
    t2 = t + 4 * STEP
    rows += [
        bar(t2 + i * STEP, 100.2 + i * 3, 103.2 + i * 3, 0.3, 0.3)
        for i in range(10)
    ]
    return rows


def _imb() -> ImbalanceParams:
    return ImbalanceParams(
        atr_period=5, min_gap_atr=0.0, displacement_atr=0.5,
        displacement_bars=3, max_zones_per_side=0, show_broken=True,
    )


def test_the_imbalance_detectors_report_none_for_what_they_never_compute():
    """FVG dan order block: kelima field itu None, bukan angka.

    Ini test yang gagal kalau default modelnya dikembalikan.
    """
    rows = _gap_series()
    zones = detect_fvg(rows, _imb())[0] + detect_order_block(rows, _imb())[0]
    assert zones, "fixture tidak menghasilkan satu kotak pun"
    for z in zones:
        for name in SUPPLY_DEMAND_ONLY:
            assert getattr(z, name) is None, (z.kind, name, getattr(z, name))


def test_the_consolidation_verdict_is_withheld_rather_than_flattering():
    """Verdict base untuk kotak tanpa base adalah None, bukan `original`.

    Nilai defaultnya dulu 1.0 pada `base_overlap`, yang melewati ambang 0,5
    dan membuat setiap celah di engine ini dinilai konsolidasi ASLI.
    """
    rows = _gap_series()
    for z in detect_fvg(rows, _imb())[0]:
        assert z.consolidation_quality is None, z.kind
        assert z.consolidation_quality != "original"


def test_supply_demand_still_reports_all_five():
    """Sisi lain gerbangnya: detector yang MENGHITUNG tetap mengirim angka.

    Tanpa ini, mengubah kelima field jadi `None` di semua tempat akan lolos.
    """
    zones, _stats = detect(
        _trend_series(),
        SupplyDemandParams(max_zones_per_side=0, show_broken=True),
    )
    assert zones, "fixture tidak menghasilkan satu zona supply/demand pun"
    for z in zones:
        for name in SUPPLY_DEMAND_ONLY:
            assert getattr(z, name) is not None, (z.kind, name)
