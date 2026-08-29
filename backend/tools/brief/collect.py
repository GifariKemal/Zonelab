"""Menarik satu bacaan lengkap dari engine, tanpa lewat API.

Setiap fungsi di sini mengembalikan dict yang bisa di-JSON-kan langsung, dan
setiap kekosongan membawa alasannya. Aturan itu bukan kosmetik: sebuah array
kosong yang tidak menjelaskan dirinya terbaca sama persis dengan "pasar sedang
sepi", dan pada 29 Agustus 2026 tiga pembacaan keliru berturut turut lahir dari
kekosongan yang sebenarnya berarti "layer-nya tidak diminta".
"""

from __future__ import annotations

import time
from typing import Any

from app import vortex
from app.conditions import at_bar
from app.drawing import build
from app.main import _annotate
from app.ict import DOCTRINE_CLAUSES, MEASURED_AGAINST, Rules, setup as ict_setup
from app.layers import LAYERS, catalogue
from app.models import (
    Anatomy,
    ChecklistParams,
    DFRParams,
    DrawRequest,
    LiquidityParams,
    PoolParams,
    SessionParams,
    SupplyDemandParams,
)
from app.poi import confluence, other_boxes
from app.providers.base import INTERVALS
from app.quarters import ALL_DEGREES
from tools import history
from tools.execute import POI_SLACK_BARS

#: Setiap layer yang bisa digambar, diambil dari registry dan bukan diketik
#: ulang. `checklist` dikecualikan karena ia laporan dan butuh jalur async yang
#: melakukan provider call; ia ditarik terpisah.
DRAWABLE = tuple(layer.id for layer in LAYERS if layer.id != "checklist")

#: TIGA LAYER MENGGAMBAR NOL DENGAN PARAMS BAWAAN, dan itu terukur bukan
#: dugaan: cycle grid, defining range, dan SSMT. Menyalakannya tanpa params
#: menghasilkan array kosong yang terbaca seperti "tidak ada apa apa", yang
#: adalah cara paling mudah menarik kesimpulan keliru dari mesin yang benar.
DEGREES_FOR_GRID = ("week", "day", "session")
DEGREES_FOR_DFR = ("week", "day")


def request_for(symbol: str, interval: str, bars: int, partners: list[str]) -> DrawRequest:
    """Satu `DrawRequest` dengan SEMUA layer menyala dan params yang mereka butuh."""
    return DrawRequest(
        symbol=symbol.split(":")[-1],
        provider=symbol.split(":")[0] if ":" in symbol else None,
        interval=interval,
        bars=bars,
        layers=list(DRAWABLE),
        # Cap display DIMATIKAN. `max_zones_per_side=100` terbaca seperti "mati"
        # dan ia maksimum schema, padahal ia memilih menurut KEBARUAN. Cap itu
        # sudah empat kali diam diam merusak pengukuran di project ini; hanya 0
        # yang berarti tanpa cap.
        supply_demand=SupplyDemandParams(max_zones_per_side=0),
        session=SessionParams(
            quarters=list(DEGREES_FOR_GRID),
            true_opens=list(DEGREES_FOR_GRID),
            max_quarters=0,
        ),
        dfr=DFRParams(degrees=list(DEGREES_FOR_DFR)),
        pools=PoolParams(sessions=["asia", "london"]),
        liquidity=LiquidityParams(periods=["day", "week"]),
        checklist=ChecklistParams(
            degree="day",
            ssmt_symbols=[p.split(":")[-1] for p in partners],
            bias_timeframes=["4h", "1d"],
        ),
    )


def _empty_note(name: str, drawn: int, meta: dict[str, Any]) -> str | None:
    """Kenapa sebuah layer menggambar nol, kalau memang nol."""
    if drawn:
        return None
    overlays = meta.get("overlays") or {}
    stats = overlays.get(name) if isinstance(overlays, dict) else None
    if isinstance(stats, dict) and stats:
        return f"nol digambar; stats layer: {stats}"
    if isinstance(meta.get(name), dict):
        return f"nol digambar; stats layer: {meta[name]}"
    return "nol digambar, dan layer ini tidak melaporkan stats apa pun"


def one_timeframe(symbol: str, interval: str, bars: int,
                  partners: list[str]) -> dict[str, Any]:
    """Semua yang bisa digambar pada satu timeframe, plus provenance-nya."""
    rows = history.load(symbol, interval, bars)
    if not rows:
        return {"interval": interval, "error": "provider mengembalikan nol bar"}
    req = request_for(symbol, interval, bars, partners)
    drawing, meta = build(rows, req)
    payload = drawing.model_dump(mode="json")

    step = INTERVALS[interval]
    last = rows[-1]
    lag = max(0, int(time.time()) - (last.time + step))
    counts, notes = {}, {}
    for field, value in payload.items():
        n = len(value) if isinstance(value, list) else (0 if value is None else 1)
        counts[field] = n
        why = _empty_note(field, n, meta)
        if why:
            notes[field] = why

    # RENCANA DIBANGUN DI SINI, dan itu bukan detail. `app/drawing.build`
    # menggambar bentuk; entry, stop, target, RR, lot dan biaya lahir di
    # `app/main._annotate`, yang hidup di jalur async API. Versi pertama brief
    # ini memanggil `build` saja lalu mencari `drawing["plans"]`, tidak
    # menemukannya, dan melaporkan "nol rencana punya zona lawan hidup" pada
    # bar yang sebenarnya punya tiga belas. Kekosongan yang terbaca sebagai
    # fakta pasar, yaitu persis kesalahan yang paket ini ada untuk mencegahnya.
    plans, advice = _annotate(drawing.zones, rows, req)

    return {
        "interval": interval,
        "bars_requested": bars,
        "bars_returned": len(rows),
        "last_bar": {
            "time": last.time, "open": last.open, "high": last.high,
            "low": last.low, "close": last.close, "spread": last.spread,
        },
        # LAG DILAPORKAN SEBAGAI ANGKA, bukan sebagai boolean. `tools/execute.py`
        # menolak deret yang tertinggal lebih dari satu interval penuh, dan
        # angka mentahnya membiarkan pembaca melihat SEBERAPA basi, yang pada
        # akhir pekan berarti pasar tutup dan bukan feed rusak.
        "feed_lag_seconds": lag,
        "feed_stale_for_execution": lag > step,
        "counts": counts,
        "empty_because": notes,
        "meta": meta,
        "drawing": payload,
        "plans": [p.model_dump(mode="json") for p in plans],
        "advice": [a.model_dump(mode="json") for a in advice],
    }


def cycle_now(rows, interval: str, degree: str = "day") -> dict[str, Any]:
    """Di mana kita berada sekarang menurut jam New York, per derajat."""
    state = at_bar(rows, len(rows) - 1, interval, degree=degree)
    dial = vortex.dial(rows[-1].time)
    return {
        "conditioning_state": {k: v for k, v in state.items()
                               if isinstance(v, (int, float, str, bool, type(None)))},
        "vortex": dial.model_dump(mode="json"),
    }


def ict_reading(zone_json: dict, plan_json: dict, rows, interval: str,
                degree: str = "day") -> dict[str, Any]:
    """Ketujuh belas klausa untuk satu kandidat, dengan sumber tiap klausa.

    `source` dibawa apa adanya karena ia yang membedakan "doktrin menyatakan
    ini" dari "project ini mengukurnya". Agent yang membaca brief tanpa field
    itu akan mengutip keduanya dengan bobot yang sama, dan sebelas dari tiga
    belas klausa di sini tidak punya satu angka pun di belakangnya.
    """
    from app.models import Zone, ZoneKind, ZoneSide, ZoneState

    zone = Zone(
        id=zone_json["id"], kind=ZoneKind(zone_json["kind"]),
        side=ZoneSide(zone_json["side"]), state=ZoneState(zone_json["state"]),
        top=zone_json["top"], bottom=zone_json["bottom"],
        proximal=zone_json["proximal"], distal=zone_json["distal"],
        time_from=zone_json["time_from"], time_to=zone_json["time_to"],
        formation_score=zone_json.get("formation_score", 0.0),
        departure_atr=zone_json.get("departure_atr"),
        anatomy=Anatomy(**zone_json["anatomy"]),
    )
    state = at_bar(rows, len(rows) - 1, interval, degree=degree)
    step = rows[-1].time - rows[-2].time
    stack = confluence(
        zone, other_boxes(rows), as_of=rows[-1].time,
        born_from=zone.time_from - POI_SLACK_BARS * step,
        born_to=zone.time_from + POI_SLACK_BARS * step,
    )
    s = ict_setup(zone, state, stack, Rules(), reward_r=plan_json.get("reward_r"))
    return {
        "zone_id": zone.id,
        "met": s.met,
        "total": len(s.conditions),
        "poi_stack": {"supports": stack.supports, "conflicts": stack.conflicts,
                      "families": stack.families, "cisd": stack.cisd,
                      "true_opens": stack.true_opens},
        "conditions": [
            {"name": c.name, "met": c.met, "source": c.source, "detail": c.detail}
            for c in s.conditions
        ],
    }


def fib_grid(drawing: dict, price: float) -> dict[str, Any]:
    """Grid Fibonacci lengkap termasuk ekstensi, plus posisi harga di dalamnya.

    DUA SUMBER MENJAWAB PERTANYAAN YANG SAMA DAN KEDUANYA DIBAWA. Grid ini
    dihitung dari swing struktur, sementara klausa `ote` di `app/ict.py`
    membacanya dari dealing range. Pada 29 Agustus 2026 keduanya menjawab
    berbeda di bar yang sama: grid memberi retracement 0,376 sementara klausanya
    mengembalikan "no dealing range, no OTE reading". Bukan salah satunya yang
    keliru, keduanya menjawab pertanyaan yang sedikit berbeda, dan brief yang
    hanya membawa satu akan menyembunyikan bahwa ada dua.
    """
    fib = drawing.get("fibonacci")
    if not fib or fib.get("low") is None or fib.get("high") is None:
        return {"present": False,
                "why": "belum ada swing terkonfirmasi di kedua sisi; layer "
                       "structure harus menyala dan menemukan dua pivot"}
    lo, hi = fib["low"], fib["high"]
    span = hi - lo
    if span <= 0:
        return {"present": False, "why": f"rentang tidak sah: low {lo} high {hi}"}
    ratios = {
        "1.000_invalidasi": 1.0, "0.786_ote": 0.786, "0.705_ote": 0.705,
        "0.618_ote": 0.618, "0.500_equilibrium": 0.5,
        "0.382_batas_atas_ote_demand": 0.382, "0.214_batas_bawah_ote_demand": 0.214,
        "0.000": 0.0, "-0.27_ekstensi": -0.27, "-0.618_ekstensi": -0.618,
        "-1.000_ekstensi": -1.0,
    }
    return {
        "present": True,
        "swing_low": lo, "swing_high": hi, "span": span,
        "low_at": fib.get("low_at"), "high_at": fib.get("high_at"),
        "price_retracement": round((price - lo) / span, 4),
        "levels": {name: round(lo + r * span, 3) for name, r in ratios.items()},
        "note": ("pita OTE arah-sadar: demand 0,214-0,382, supply 0,618-0,786. "
                 "Klausa ote diukur di 12 instrumen dan NOL lolos, |t| tertinggi "
                 "2,04 lawan kritis 3,20"),
    }


def evidence_table() -> list[dict[str, str]]:
    """Registry layer apa adanya, termasuk field `evidence` yang wajib.

    Disalin dan tidak diringkas. Lima dari tujuh belas entry membawa hasil
    MEASURED NULL dan dua membawa hasil NEGATIF, dan meringkasnya jadi "ada"
    atau "tidak ada" akan membuang justru bagian yang paling mahal dibayar.
    """
    return catalogue()


def clause_provenance() -> dict[str, Any]:
    """Klausa mana yang doktrin, dan klausa mana yang sudah diukur berlawanan."""
    return {
        "doctrine_clauses": sorted(DOCTRINE_CLAUSES),
        "measured_against": dict(MEASURED_AGAINST),
        "note": ("doctrine berarti sumbernya menyatakan dan project ini belum "
                 "punya angka. measured_against berarti ADA angkanya dan ia "
                 "menunjuk ke arah lain."),
    }


def known_degrees() -> list[str]:
    return list(ALL_DEGREES)
