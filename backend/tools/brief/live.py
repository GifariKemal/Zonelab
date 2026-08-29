"""Bagian brief yang menuntut provider call, dipisah karena ia bisa gagal.

`collect.py` sinkron dan tidak menyentuh jaringan: ia memanggil engine di atas
bar yang sudah ada. Dua bacaan tidak bisa begitu. Checklist mengambil per bias
timeframe dan per simbol SSMT, dan triad mengambil tiga instrumen sekaligus.
Keduanya hidup di jalur async `app/main.py`.

KENAPA DIPISAH FILE, bukan sekadar dipisah fungsi. Bagian yang bisa gagal harus
bisa gagal SENDIRIAN. Kalau partner SSMT tidak terbaca, brief tetap harus keluar
dengan seluruh bacaan struktural yang tidak butuh partner mana pun, dan
kegagalannya disebut alih alih membuat seluruh perintah exit bukan nol.

DAN KEGAGALAN PARTNER DITERUSKAN, TIDAK DITELAN. `app/aligned.load_aligned`
mengembalikan daftar `skipped` berisi partner yang tidak datang, dan sebuah
brief yang membuang daftar itu menyajikan korelasi dua instrumen seolah ia
korelasi tiga. Itu bukan angka yang lebih lemah, itu angka tentang sesuatu yang
lain.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.aligned import load_aligned
from app.checklist import build as checklist_build
from app.correlation import correlations
from app.pools import killzones_at
from app.providers import resolve
from app.triad import TRIAD_FAMILIES, truth_asset
from tools import history

#: Provider yang TIDAK membawa partner triad. Binance melayani tiga dari dua
#: puluh instrumen dan Yahoo tidak membawa CFD broker sama sekali, jadi triad di
#: atas keduanya selalu gagal. Diambil dari alasan yang sama yang ditulis
#: `app/main.py`, dan substitusinya DILAPORKAN, tidak diam-diam.
NEEDS_MT5 = ("binance", "yahoo", None)


async def _checklist(symbol: str, interval: str, bars: int,
                     partners: list[str]) -> dict[str, Any]:
    """Laporan checklist penuh, atau alasan kenapa ia tidak ada.

    Dijalankan lewat `asyncio.run` karena `checklist.build` async: ia mengambil
    satu deret per bias timeframe dan satu per simbol SSMT. Itu tiga sampai lima
    provider call, dan tiap satunya bisa gagal tanpa membatalkan sisanya.
    """
    from tools.brief.collect import request_for

    rows = history.load(symbol, interval, bars)
    if not rows:
        return {"present": False, "why": "provider mengembalikan nol bar"}
    req = request_for(symbol, interval, bars, partners)
    used = symbol.split(":")[0] if ":" in symbol else "mt5"
    try:
        report, stats = await checklist_build(rows, req, used)
    except Exception as exc:  # noqa: BLE001 - satu bacaan, bukan seluruh brief
        return {"present": False,
                "why": f"{type(exc).__name__}: {exc}",
                "note": "checklist butuh provider call; brief lainnya tetap sah"}
    return {
        "present": True,
        "report": report.model_dump(mode="json"),
        "stats": stats,
        # `extra_fetches` dibawa apa adanya. Ia satu satunya angka yang
        # mengatakan berapa panggilan provider yang dibayar bacaan ini, dan
        # tanpa itu sebuah brief yang lambat tidak bisa dijelaskan.
        "extra_fetches": (stats or {}).get("extra_fetches"),
    }


async def _triad(symbol: str, interval: str, bars: int,
                 family: str = "monetary") -> dict[str, Any]:
    """Truth Asset dan korelasi triad, dengan partner yang gagal DISEBUT."""
    fam = TRIAD_FAMILIES.get(family)
    if fam is None:
        return {"present": False,
                "why": f"triad {family!r} tidak dikenal, pilih dari "
                       f"{sorted(TRIAD_FAMILIES)}"}
    base = symbol.split(":")[-1]
    asked = symbol.split(":")[0] if ":" in symbol else None
    symbols = [base, *[p for p in fam[1:] if p != base]]

    used = "mt5" if asked in NEEDS_MT5 else asked
    try:
        series, load_stats = await load_aligned(symbols, interval, bars, used)
    except Exception as exc:  # noqa: BLE001
        return {"present": False, "why": f"{type(exc).__name__}: {exc}"}

    found = truth_asset(series, base, family)
    skipped = (load_stats or {}).get("skipped") or []
    return {
        "present": True,
        "family": family,
        "base": base,
        "partners_requested": symbols[1:],
        # SUBSTITUSI PROVIDER DILAPORKAN. Sampai field ini ada, caller yang
        # meminta binance mendapat harga MT5 tanpa satu pun cara mengetahuinya,
        # dan korelasi serta Truth Asset-nya dihitung dari tape yang berbeda
        # dari yang diminta.
        "provider_asked": asked,
        "provider_used": resolve(used).name,
        "provider_substituted": (asked in NEEDS_MT5 and asked != "mt5"),
        # PARTNER YANG DI-SKIP DITERUSKAN. Korelasi dua instrumen yang
        # disajikan seolah korelasi tiga bukan angka yang lebih lemah, ia
        # angka tentang sesuatu yang lain.
        "skipped": skipped,
        "skipped_note": ("partner ini tidak datang, jadi bacaan di bawah "
                         "menghitung lebih sedikit instrumen daripada yang "
                         "diminta") if skipped else None,
        "truth_asset": None if found is None else {
            "symbol": found.symbol,
            "scores": {k: round(v, 4) for k, v in found.scores.items()},
            "note": ("skor konsolidasi terendah, yaitu rasio range terhadap "
                     "ATR-nya sendiri. Truth Asset BUKAN arah."),
        },
        "correlations": [
            {"symbol": c.symbol,
             "full": None if c.full is None else round(c.full, 4),
             "recent": None if c.recent is None else round(c.recent, 4),
             "pairs": c.pairs, "sign_changed": c.sign_changed}
            for c in correlations(series, base)
        ],
        "correlation_note": (
            "Pearson atas log return pada grid irisan ketat, tanpa fill. "
            "Pita 0,60-0,80 diukur 29 Agustus 2026 sebagai pengkondisi dan "
            "TIDAK memisahkan hasil: t terbesar 0,19 lawan kritis 3,48."
        ),
        "killzones_now": list(killzones_at(int(__import__("time").time()))),
    }


def ote_reconciliation(fib: dict, state: dict) -> dict[str, Any]:
    """Dua sumber menjawab "di mana harga dalam retracement", dibawa berdampingan.

    Grid Fibonacci dihitung dari swing STRUKTUR (`drawing.fibonacci`, dua pivot
    terkonfirmasi terakhir). Klausa `ote` di `app/ict.py` membacanya dari
    DEALING RANGE (`state["range_band"]`, swing-to-swing dibaca saat harga
    tiba). Keduanya sah dan keduanya menjawab pertanyaan yang sedikit berbeda.

    Pada 29 Agustus 2026 keduanya menjawab berbeda di bar yang sama: grid
    memberi retracement 0,376 sementara klausanya mengembalikan "no dealing
    range, no OTE reading". Sebuah brief yang membawa satu saja akan
    menyembunyikan bahwa ada dua, dan pembaca akan mengira ia punya satu
    jawaban ketika ia punya dua.

    Fungsi ini TIDAK memilih pemenang. Memilihnya adalah keputusan pemilik
    tentang mana definisi OTE yang berlaku di metodenya, bukan keputusan yang
    boleh diselundupkan sebuah tool pelapor.
    """
    band = state.get("range_band")
    pos = state.get("range_pos")
    grid = fib.get("price_retracement") if fib.get("present") else None
    agree = None
    if grid is not None and pos is not None:
        # Keduanya dinormalkan 0..1 pada rentangnya masing masing, jadi
        # selisihnya bisa dibandingkan walau rentangnya berbeda.
        agree = abs(float(grid) - float(pos)) <= 0.10
    return {
        "from_structure_swings": {
            "source": "drawing.fibonacci, dua pivot terkonfirmasi terakhir",
            "retracement": grid,
            "present": bool(fib.get("present")),
            "why_absent": None if fib.get("present") else fib.get("why"),
        },
        "from_dealing_range": {
            "source": "app/conditions.at_bar -> state['range_band'], dibaca "
                      "app/ict.py klausa ote dan discount_or_premium",
            "band": band,
            "position": pos,
            "present": band is not None,
            "why_absent": None if band is not None else
                          "tidak ada dealing range yang bisa diketahui di bar ini",
        },
        "agree_within_0_10": agree,
        "note": ("Dua definisi, dua jawaban yang sah. Tool ini tidak memilih "
                 "pemenang: mana yang berlaku adalah keputusan pemilik metode. "
                 "Klausa ote sendiri sudah diukur di 12 instrumen dan NOL "
                 "lolos, jadi memilih definisi tidak mengubah bahwa ia belum "
                 "punya nilai terukur."),
    }


async def _both(symbol: str, interval: str, bars: int,
                partners: list[str]) -> dict[str, Any]:
    return {
        "checklist": await _checklist(symbol, interval, bars, partners),
        "triad": await _triad(symbol, interval, bars),
    }


def gather(symbol: str, interval: str, bars: int,
           partners: list[str]) -> dict[str, Any]:
    """Kedua bacaan yang menjaring, di dalam SATU event loop.

    SATU LOOP, DAN INI BUKAN KERAPIAN. Versi pertama memanggil `asyncio.run`
    dua kali, sekali untuk checklist dan sekali untuk triad. Yang pertama
    berhasil, yang kedua gagal dengan:

        ProviderError: nothing left to compare XAUUSD with:
        DXY: <asyncio.locks.Lock ...> is bound to a different event loop

    Sebabnya `app/providers` menyimpan satu `asyncio.Lock` per key di
    `_locks`, dan sebuah `asyncio.Lock` terikat ke loop tempat ia dibuat.
    `asyncio.run` membuat loop baru dan menutupnya saat selesai, jadi
    panggilan kedua mewarisi lock milik loop yang sudah mati dan SETIAP
    partner gagal. Yang terlihat di permukaan bukan "loop salah", melainkan
    "tidak ada partner yang bisa dibandingkan", yaitu pesan yang terbaca
    seperti masalah data.

    Satu `asyncio.run` yang membungkus keduanya menghilangkan seluruh kelas
    kesalahan itu, dan menambah bacaan async ketiga nanti tidak akan
    menghidupkannya kembali.
    """
    return asyncio.run(_both(symbol, interval, bars, partners))
