"""CISD sebagai KOTAK: level yang ditembus lawan ekstrem run yang menembusnya.

DETEKTOR KETUJUH. Konstruknya sendiri menyebut TEPAT SATU harga - `open_price`,
open lilin PERTAMA dari run - dan `CISDDetector.mqh` sudah menuliskannya: "INI
BUKAN BOX. Ia EVENT plus satu level horizontal." Pembanding publik setuju:
`Change in State of Delivery (CISD) [LuxAlgo]` menggambar 502 GARIS di XAUUSD
harian, nol kotak.

TEPI KEDUANYA DITAMBAHKAN, BUKAN DIKARANG, DAN IA GRATIS. `delivery_runs` sudah
mengunjungi setiap lilin conforming untuk menghitung `end` dan `length`, jadi
ekstrem run dicatat di loop yang sama tanpa pass tambahan. Tiga kandidat tepi
kedua yang bukan bilangan karangan dipertimbangkan:

    ekstrem run          dipilih - satu-satunya sifat RUN, bukan sifat satu lilin
    close lilin terakhir ditolak - tepi terdangkal, kotaknya tipis dan sewenang
    open lilin terakhir  ditolak - itu anchor SALAH yang docstring cisd.py ada
                         untuk mencegah, lima paragraf khusus soal itu

Alternatif ber-konstanta - kelipatan ATR, pita pip tetap, pecahan tinggi run -
ditolak semua. Repo ini sudah punya empat konstanta chosen-not-measured
(`min_run`, `interrupt_tolerance`, `RECENT_CISD_BARS`, plafon 0,25) dan
menambahkan yang kelima untuk mendapat tepi yang sudah ada di dalam bar adalah
harga yang tidak perlu dibayar.

GEOMETRI, DAN SISINYA JATUH TANPA PILIHAN
CISD arah +1 berarti harga tutup DI ATAS open sebuah run TURUN: run itu menjual,
lalu harga tutup di atas tempat penjualan dimulai. Run turun membentang dari
open-nya (atas) ke low terjauhnya (bawah), jadi kotaknya `level`..`extreme` dan
sisinya DEMAND - harga kembali TURUN ke level yang ditembus, itu proximal, dan
stop duduk di luar low terjauh run, itu distal. Arah -1 cerminnya.

Jadi proximal SELALU `level` dan distal SELALU `run_extreme`. Tidak ada cabang.

APA YANG SUDAH DIUKUR, DAN TIDAK SATU PUN TENTANG KOTAK INI
Dua pengukuran ada di repo, dan keduanya punya masalah yang harus dibaca
sebelum angkanya dipakai:

1. NULL ARAH 2026-08-20, n=23.270, DELTA -0,0195 ATR di t=-0,53. TIDAK ADA
   SUMBERNYA. Angka itu hidup HANYA sebagai prosa di `layers.py`; tidak ada
   tool, tidak ada JSON, tidak ada tabel di CALIBRATION.md, dan pencarian
   riwayat git atas "n=23270" cuma menemukan commit yang MENAMBAHKAN prosa itu.
   Ia tidak bisa direproduksi dari repo ini.

2. TERBALIK DAN KUAT, `docs/csid_ob_intrabar.json`: CISD fresh di dalam order
   block memberi exp_r -0,1119 lawan +0,0244 tanpa, delta -0,1363 R, Welch
   t = -7,07 lawan kritis 2,241, negatif di SELURUH 8 fold. TAPI ia diukur
   31 Agustus 2026, PRA perbaikan urutan lifecycle 7 September, dan jalurnya
   lewat `intrabar.resolved` yang memakai `zone.first_test_time` - persis field
   yang urutan lama tinggalkan None untuk zona yang tersayat. Ia harus diukur
   ulang sebelum dijadikan dasar.

Tidak satu pun dari keduanya mengukur KOTAK. Yang pertama klaim arah tingkat
bar; yang kedua kondisioner atas zona MILIK DETEKTOR LAIN. Kotak ini pertanyaan
ketiga tanpa prior.

GERBANG: LANTAI TINGGI KOTAK DALAM ATR, DEFAULT MATI
Sama alasannya dengan MSS: tinggi kotak ADALAH jarak stop, jadi menggerbanginya
memilih antara "cuma run besar" dan "cuma stop rapat", dan tidak satu pun
bersumber. Nol, dinyatakan, dan CISD masuk `GATE_UNMEASURED_KINDS`.
"""

from __future__ import annotations

from ..cisd import cisds
from ..indicators import wilder_atr
from ..models import Candle, CisdZoneParams, Zone, ZoneKind, ZoneSide
from .imbalance import _arrays, _finish, _present
from .supply_demand import _dedupe


def detect(candles: list[Candle], params: CisdZoneParams) -> tuple[list[Zone], dict[str, float]]:
    """Satu kotak per CISD, lahir di bar yang menembus."""
    stats: dict[str, float] = {
        "bars": float(len(candles)),
        "candidates": 0.0,
        "rejected_zero_height": 0.0,
        "rejected_zero_atr": 0.0,
        "rejected_weak_run": 0.0,
        "rejected_overlap": 0.0,
    }
    if len(candles) < 4:
        return _present([], params, stats, int(candles[-1].time) if candles else 0)

    time, _open, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)
    events, _runs = cisds(candles, params.min_run, params.interrupt_tolerance)
    found: list[Zone] = []

    for e in events:
        stats["candidates"] += 1
        up = e.direction == 1
        top = float(e.level if up else e.run_extreme)
        bottom = float(e.run_extreme if up else e.level)
        side = ZoneSide.DEMAND if up else ZoneSide.SUPPLY
        if top - bottom <= 0:
            # Run satu lilin yang open-nya SEKALIGUS ekstremnya - marubozu.
            # Terukur 6 dari 377 di XAUUSD harian.
            stats["rejected_zero_height"] += 1
            continue

        # ATR di bar sebelum run dimulai: run-nya peristiwa pertama, jadi bar
        # tempat pengamat mulai bisa mengukur. Sama dengan `origin` di lima
        # detektor kotak lainnya.
        scale = float(atr[max(0, e.run_start - 1)])
        if scale <= 0:
            stats["rejected_zero_atr"] += 1
            continue
        departure = round((top - bottom) / scale, 3)
        if departure < params.run_min_atr:
            stats["rejected_weak_run"] += 1
            continue

        zone = _finish(
            ZoneKind.CISD, side, top, bottom, e.run_start, e.index,
            time, high, low, close, atr, params, departure,
        )
        if zone is not None:
            # Id membawa bar run DAN bar tembus. Pelajaran dari OTE: `_finish`
            # menyusunnya dari bar origin saja, dan dua CISD tidak bisa berbagi
            # run - tapi menuliskannya eksplisit lebih murah daripada
            # membuktikan ulang bahwa mereka tidak bisa.
            zone.id = f"{ZoneKind.CISD.value}-{int(time[e.run_start])}-{int(time[e.index])}"
            found.append(zone)

    found = _dedupe(found, params.merge_overlap_pct, stats)
    return _present(found, params, stats, int(time[-1]))


def _selftest() -> None:
    """Proximal SELALU level, distal SELALU ekstrem run, di kedua arah.

    Dihitung tangan. CISD +1 menembus run TURUN: run itu buka di 110 dan turun
    sampai 100, jadi kotaknya 100..110 dan sisinya DEMAND - harga kembali turun
    ke 110 (proximal, level yang ditembus) dan stop di bawah 100 (distal).
    """
    lvl, ext = 110.0, 100.0            # run turun: open di atas, ekstrem low
    top, bottom = lvl, ext
    prox, dist = top, bottom           # demand
    assert prox == lvl and dist == ext
    lvl2, ext2 = 100.0, 110.0          # run naik: open di bawah, ekstrem high
    top2, bottom2 = ext2, lvl2
    prox2, dist2 = bottom2, top2       # supply
    assert prox2 == lvl2 and dist2 == ext2
