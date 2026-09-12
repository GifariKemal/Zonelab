"""Optimal trade entry: the 0,618-0,786 retracement band of one structural leg.

DETEKTOR KEENAM, DAN IA MENGUKUR APA YANG SUDAH DIGAMBAR. Grid Fibonacci/OTE
sudah tampil di chart sejak lama lewat `frontend/src/components/
fibonacci-primitive.ts`, sembilan level di atas dua anchor swing yang diisi
`drawing.py:_draw_structure`. Yang belum pernah ada: sebuah KOTAK dari pita itu,
dengan lifecycle, gerbang dan bracket yang sama dengan lima detektor lain -
jadi tidak ada satu angka pun tentang pita yang benar benar dilihat pembaca.

DUA DEFINISI OTE HIDUP DI REPO INI DAN MEREKA TIDAK SETUJU. Modul ini memakai
yang PERTAMA, dan itu pilihan yang harus dinyatakan:

  1. SWING STRUKTUR - `structure.swings`, anchor low dan high confirmed
     terakhir. Ini yang DIGAMBAR, dan ini yang dipakai di sini.
  2. DEALING RANGE - `dealing_range.mark_dealing_range`, `swing_n=50`, dibaca
     pada `first_test_time`. Ini yang dipakai klausa `ote` di `app/ict.py:510`.

`tools/brief/live.py:ote_reconciliation` mencatat keduanya menjawab pertanyaan
yang sama dan berbeda: 29 Agustus 2026 pada bar yang sama, grid memberi
retracement 0,376 sementara klausa menjawab "no dealing range, no OTE reading".
Ia sengaja menolak memilih pemenang. Modul ini memilih definisi (1) BUKAN karena
ia lebih benar melainkan karena ia yang tampil di layar, dan yang tampil di layar
adalah yang belum punya angka.

APA YANG SUDAH DIUKUR, DAN ITU TENTANG DEFINISI (2), BUKAN INI
`docs/PRAREGISTRASI-YATIM.md` bagian 7 dan 10 menguji pita OTE dealing-range
sebagai SARINGAN atas sentuhan pertama zona supply/demand - bukan sebagai
penghasil kotak. Hasilnya: NOL dari dua belas sel lolos, negatif di 10 dari 12,
|t| tertinggi 2,04 lawan kritis 3,20. Kesimpulan dokumen itu: sebagai edge
terbantah tuntas, sebagai racun tidak terbukti.

Itu bukan pengukuran modul ini, dan modul ini tidak boleh dibaca seolah ia
sudah punya angka. Tapi ia juga tidak boleh dibaca seolah papan tulisnya
kosong: bukti terdekat yang ada menunjuk ke bawah.

GEOMETRI
Leg diambil dari dua anchor confirmed terakhir. Kalau swing high lebih baru
dari swing low, legnya NAIK dan retracement turun ke pita, jadi kotaknya
DEMAND; sebaliknya SUPPLY. Pitanya antara 0,618 dan 0,786 dari leg, dan tepi
yang harga temui lebih dulu saat retrace adalah yang DANGKAL - 0,618 - jadi ia
proximal dan 0,786 distal. Stop duduk di luar distal, sama seperti empat
detektor lain.

Rasionya `0.618` dan `0.786` diambil dari `fibonacci-primitive.ts:LEVELS`, satu
satunya tempat pita itu digambar, supaya kotak dan grid tidak bisa hanyut.
`0.705` ada di grid sebagai garis tengah dan TIDAK dipakai di sini: ia titik,
bukan tepi.

GERBANG: LANTAI PADA PANJANG LEG DALAM ATR, dan itu pilihan yang dinyatakan.
Doktrin OTE tidak membawa gerbang apa pun - ia aturan tempat masuk, bukan
aturan seleksi. Empat detektor lain digerbangi kekuatan keberangkatan, jadi
padanan terdekatnya panjang leg yang membuat pitanya. Dengan lantai default
2,0 ATR itu berarti "cuma retrace dari leg yang benar benar bergerak".
"""

from __future__ import annotations

import numpy as np

from ..indicators import wilder_atr
from ..models import Candle, OteParams, Zone, ZoneKind, ZoneSide
from .imbalance import _arrays, _finish, _present
from .structure import swings
from .supply_demand import _dedupe

#: Tepi pita, cermin `fibonacci-primitive.ts:LEVELS`.
OTE_NEAR = 0.618
OTE_FAR = 0.786


def detect(candles: list[Candle], params: OteParams) -> tuple[list[Zone], dict[str, float]]:
    """Satu kotak per pasangan anchor confirmed, lahir saat anchor kedua confirm."""
    stats: dict[str, float] = {
        "bars": float(len(candles)),
        "candidates": 0.0,
        "rejected_zero_leg": 0.0,
        "rejected_zero_atr": 0.0,
        "rejected_weak_leg": 0.0,
        # DISEMAI DI SINI, karena `_dedupe` menaikkannya tanpa membuat
        # kuncinya. Modul ini berjanji setiap penolakan mendarat di
        # `stats`; kunci yang hilang memberi KeyError, bukan nol diam.
        "rejected_overlap": 0.0,
    }
    if len(candles) < 3:
        return _present([], params, stats, int(candles[-1].time) if candles else 0)

    time, _open, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)
    pivots = swings(high, low, params.swing_n, params.swing_n)
    if not pivots:
        return _present([], params, stats, int(time[-1]))

    # Satu jalan maju - pola yang sama dengan `dealing_range.range_at`. Sebuah
    # pivot baru boleh dipakai di `confirmed_at`, bukan di barnya sendiri, jadi
    # urutannya urutan KETERSEDIAAN dan bukan urutan kejadian.
    order = sorted(pivots, key=lambda s: (s.confirmed_at, s.index))
    last_hi = None
    last_lo = None
    seen: set[tuple[int, int]] = set()
    found: list[Zone] = []

    for piv in order:
        if piv.high:
            last_hi = piv
        else:
            last_lo = piv
        if last_hi is None or last_lo is None:
            continue
        key = (last_lo.index, last_hi.index)
        if key in seen:
            continue
        seen.add(key)

        leg = float(last_hi.price - last_lo.price)
        if leg <= 0:
            stats["rejected_zero_leg"] += 1
            continue
        stats["candidates"] += 1

        # Anchor mana yang lebih baru menentukan arah leg, dan arah leg
        # menentukan sisi. Leg NAIK di-retrace turun, jadi pitanya demand.
        up = last_hi.index > last_lo.index
        if up:
            top = float(last_hi.price) - OTE_NEAR * leg
            bottom = float(last_hi.price) - OTE_FAR * leg
            side = ZoneSide.DEMAND
        else:
            bottom = float(last_lo.price) + OTE_NEAR * leg
            top = float(last_lo.price) + OTE_FAR * leg
            side = ZoneSide.SUPPLY

        origin = last_lo.index if up else last_hi.index
        # `confirmed_at` adalah BAR, bukan waktu - lihat `Swing` di structure.py.
        born = int(max(last_hi.confirmed_at, last_lo.confirmed_at))
        if born >= len(time) or born <= origin:
            continue

        scale = float(atr[origin])
        if scale <= 0:
            stats["rejected_zero_atr"] += 1
            continue
        departure = round(leg / scale, 3)
        if departure < params.leg_min_atr:
            stats["rejected_weak_leg"] += 1
            continue

        zone = _finish(
            ZoneKind.OTE, side, top, bottom, origin, born,
            time, high, low, close, atr, params, departure,
        )
        if zone is not None:
            # ID HARUS MEMBAWA KEDUA ANCHOR, dan detektor ini satu satunya yang
            # begitu. `_finish` menyusun id dari kind plus bar ORIGIN, dan itu
            # unik untuk lima detektor lain karena kotaknya dibuat dari lilin
            # yang berbeda. Di sini TIDAK: pasangan anchor berurutan berbagi satu
            # anchor, jadi dua pita berbeda bisa punya origin yang sama dan
            # karenanya id yang sama.
            #
            # Sebelum dedupe cacat ini tidak terlihat - `{z.id: z}` diam diam
            # menyimpan yang terakhir. Begitu `_dedupe` masuk, yang bertahan jadi
            # bergantung populasi, jadi jendela pendek dan jendela penuh bisa
            # menyimpan pita BERBEDA di bawah id yang sama, dan
            # `test_no_repaint` membacanya sebagai geometri yang bergeser -
            # "grew right: OTE-1774544400". Testnya benar dan cacatnya milik saya.
            zone.id = f"{ZoneKind.OTE.value}-{int(time[last_lo.index])}-{int(time[last_hi.index])}"
            found.append(zone)

    # DIDEDUPE SEBELUM DITAMPILKAN, dan alasannya geometri detektor ini.
    # Pasangan anchor berurutan berbagi satu anchor, jadi pita berikutnya
    # hampir selalu memotong pita sebelumnya. Tanpa ini audit visual tidak
    # bisa memisahkan dua kotak yang bertumpuk. Memakai ulang `_dedupe`
    # milik supply_demand, bukan menulis versi kedua: aturannya sama -
    # tumpang tindih diukur terhadap tinggi yang LEBIH KECIL, dan yang
    # bertahan dipilih prioritas tampilan lalu `departure_atr`.
    found = _dedupe(found, params.merge_overlap_pct, stats)
    return _present(found, params, stats, int(time[-1]))


def _selftest() -> None:
    """Leg naik memberi kotak demand, dan tepinya di 0,618 dan 0,786.

    Dihitung tangan supaya kekeliruan tanda tidak bisa lewat: leg 0 -> 100,
    pita demand duduk di 100 - 61,8 = 38,2 (proximal) sampai 100 - 78,6 = 21,4
    (distal). Itu juga persis mirror `ict.py`, yang menyatakan pita demand
    0,214-0,382 dalam satuan posisi dealing range.
    """
    lo, hi, leg = 0.0, 100.0, 100.0
    top = hi - OTE_NEAR * leg
    bottom = hi - OTE_FAR * leg
    assert abs(top - 38.2) < 1e-9, top
    assert abs(bottom - 21.4) < 1e-9, bottom
    # Leg turun adalah cerminnya, dan proximal pindah ke tepi BAWAH.
    b2 = lo + OTE_NEAR * leg
    t2 = lo + OTE_FAR * leg
    assert abs(b2 - 61.8) < 1e-9 and abs(t2 - 78.6) < 1e-9, (b2, t2)
    assert OTE_NEAR < OTE_FAR, "proximal harus lebih dangkal dari distal"
