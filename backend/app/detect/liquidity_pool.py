"""BSL dan SSL sebagai KOTAK: kluster pivot yang sepakat harga.

DETEKTOR KEDELAPAN, dan seperti CISD ia mengangkat konstruk yang di repo ini
sudah hidup sebagai GARIS. `app/liquidity.py` sudah membawa `side: BSL/SSL` -
tapi untuk ekstrem periode (PDH/PDL/PWH/PWL/FRI/MON) dan untuk dua sisi dealing
range. Itu pertanyaan "di mana ekstrem kemarin". Yang di sini pertanyaan lain:
"di mana beberapa pivot sepakat harga", yaitu equal highs dan equal lows. Dua
populasi berbeda, dan pengukuran salah satunya tidak berlaku untuk yang lain.

SISINYA TERBALIK DARI NAMANYA, DAN ITU BENAR
BSL adalah likuiditas BELI - buy stop - yang beristirahat DI ATAS harga. Harga
naik menuju kolam itu untuk mengambilnya, jadi pengamat mendekatinya dari bawah
dan kotaknya duduk di sisi SUPPLY dari peta ini. SSL cerminnya: sell stop di
bawah harga, sisi DEMAND. Menamainya "buy side" lalu menaruhnya di demand akan
membuat setiap pembaca salah baca arah, jadi pemetaannya ditulis sekali di sini
dan tidak diulang di tempat lain.

TOLERANSI MENGELOMPOKKAN, DAN SEJAK 8 September 2026 IA JUGA MENGGAMBAR SATU SISI
Proximal diambil dari sebaran pivot yang TERAMATI - equal high terendah untuk
BSL, equal low tertinggi untuk SSL - dan distal didorong `equal_tol_atr`
melewati pivot terekstrem, ke tempat stop beristirahat.

Versi pertama memakai sebaran teramati di KEDUA sisi dan sengaja menjaga
toleransi keluar dari geometri. Itu dicabut karena dua alasan yang menumpuk.
Pertama, ia salah soal konstruknya: kluster menyatakan harga-harga ini sama
DALAM toleransi, jadi kolam stop adalah pita toleransinya dan sebaran teramati
cuma sampel dari pita itu - ia mengecilkan kolamnya. Kedua, ia tidak terbaca:
keempat kotak di XAUUSD 15 menit lebih pendek dari 14 piksel, `pixel-truth`
membaca 3 dari 7 karena tak ada yang bisa diukur, dan tepi yang dibaca balik
meleset sampai 29,68 persen dari tinggi kotaknya sendiri.

Harga yang dibayar dinyatakan: `equal_tol_atr` kini menyentuh geometri, jadi
tinggi kotak - yang adalah jarak stop - ikut bergerak dengannya. Itu bisa
dipertahankan HANYA karena gerbang kind ini 0,0 dan tidak mengikat; kalau suatu
saat ia digerbangi, dua knob akan mengendalikan satu keputusan.

SATU KOTAK PER KLUSTER, DAN IA LAHIR SAAT SENTUHAN KE-`min_touches`
Sebuah kluster bisa terus tumbuh. Memancarkan ulang setiap kali anggota baru
datang akan menumpuk kotak di tempat yang sama; menunggu kluster SELESAI adalah
lookahead - tidak ada yang tahu di bar mana pivot terakhir sudah lewat. Jadi
kotaknya dipancarkan tepat saat anggota ke-`min_touches` DIKONFIRMASI, dan
anggota sesudahnya tidak memancarkan apa pun. Konsekuensinya kolam beranggota
empat digambarkan oleh dua anggota pertamanya saja, dan itu memang yang bisa
diketahui saat itu.

ANCHOR KLUSTER ADALAH ANGGOTA PERTAMA, BUKAN RATA-RATA BERJALAN
Rata-rata berjalan membuat kluster bisa MENGHANYUT: sepuluh pivot yang
masing-masing berjarak 0,09 ATR dari tetangganya akan masuk satu kluster yang
membentang 0,9 ATR, dan tidak ada satu pun pasangan di ujungnya yang "sama".
Dengan anchor tetap, setiap anggota berjarak paling jauh `equal_tol_atr` dari
harga yang sama, jadi klaim "equal" berlaku untuk seluruh anggota.

SKALANYA BEBAS-JENDELA, DAN DI SINI ITU LEBIH PENTING DARIPADA DI MANA PUN
`mean_true_range`, bukan `wilder_atr`. Wilder adalah RMA yang disemai dari bar
pertama, jadi nilainya di satu bar absolut bergantung berapa bar yang dimuat
pemanggil - `detect_fvg` ditukar karena itu pada 7 September 2026. Di sana ATR
cuma menskalakan sebuah RASIO; DI SINI ia menetapkan TOLERANSI PENGELOMPOKAN,
jadi ia memutuskan pivot mana yang masuk satu kolam dan karena itu menggeser
POPULASINYA, bukan cuma angkanya.

Terukur sebelum ditukar, XAUUSD harian dengan Wilder: deret penuh memberi 5 zona
yang lahir di 100 bar terakhir, potongan 100 bar saja memberi 4, dan himpunannya
BERBEDA - dua zona hanya ada di deret penuh, satu hanya ada di potongan. Itu juga
yang membuat parity lawan Pine terbaca meleset satu: Pine membaca seluruh
riwayat, run Python yang dibandingkan dengannya membaca 100 bar.

GERBANG: NOL, DINYATAKAN
Tinggi kotak di sini adalah sebaran yang kebetulan teramati di dalam toleransi,
jadi menggerbanginya adalah menggerbangi `equal_tol_atr` lewat pintu belakang.
Lihat catatan di `FLOOR_GATE_ATR`; kind-nya masuk `GATE_UNMEASURED_KINDS`.

BELUM ADA SATU PUN PENGUKURAN OUTCOME UNTUK KOTAK INI. Jangan kutip angka
`liquidity.py` untuknya - modul itu sendiri menyatakan tidak ada isinya yang
pernah diukur terhadap outcome.
"""

from __future__ import annotations

from ..indicators import mean_true_range
from ..models import Candle, LiquidityPoolParams, Zone, ZoneKind, ZoneSide
from .imbalance import _arrays, _finish, _present
from .structure import swings
from .supply_demand import _dedupe


def detect(
    candles: list[Candle], params: LiquidityPoolParams
) -> tuple[list[Zone], dict[str, float]]:
    """Satu kotak per kluster pivot, lahir saat sentuhan ke-`min_touches`."""
    stats: dict[str, float] = {
        "bars": float(len(candles)),
        "candidates": 0.0,
        "rejected_zero_height": 0.0,
        "rejected_zero_atr": 0.0,
        "rejected_overlap": 0.0,
        "clusters_grown": 0.0,
        "rejected_warmup": 0.0,
    }
    if len(candles) < 4:
        return _present([], params, stats, int(candles[-1].time) if candles else 0)

    time, _open, high, low, close = _arrays(candles)
    atr = mean_true_range(high, low, close, params.atr_period)
    pivots = swings(high, low, params.swing_n, params.swing_n)
    found: list[Zone] = []

    # Dua sisi diproses terpisah: sebuah swing high tidak pernah boleh masuk
    # kluster equal LOW, walau harganya kebetulan cocok.
    for is_high in (True, False):
        side_pivots = [p for p in pivots if p.high is is_high]
        # BANYAK KLUSTER HIDUP SEKALIGUS, dan versi pertama detektor ini salah
        # di sini: ia cuma membandingkan pivot baru dengan kluster yang PERSIS
        # sebelumnya, jadi dua equal high yang dipisahkan satu lower high tidak
        # pernah bertemu. Terukur nol kandidat di 100 bar XAUUSD harian - gagal
        # keras, bukan diam-diam salah.
        clusters: list[dict] = []
        for p in side_pivots:
            scale = float(atr[min(p.confirmed_at, len(atr) - 1)])
            if scale <= 0:
                stats["rejected_zero_atr"] += 1
                continue
            tol = params.equal_tol_atr * scale

            # KLUSTER MATI SAAT LIKUIDITASNYA DIAMBIL, dan itu sengaja bukan
            # lookback berjumlah bar. Sebuah kolam berhenti jadi kolam ketika
            # harga menembusnya - stop-nya sudah kena - jadi aturan matinya
            # datang dari konstruknya sendiri dan bukan dari konstanta baru.
            # Segmennya bar SETELAH anggota terakhir sampai SEBELUM pivot ini;
            # pivot ini sendiri dinilai oleh toleransi kluster di bawah.
            #
            # TOLERANSINYA MILIK KLUSTER, BUKAN MILIK PIVOT YANG BARU DATANG.
            # Versi pertama memakai ATR di bar pivot baru untuk menilai kluster
            # lama, yang berarti pita sebuah kolam ikut bergerak setiap kali
            # ada pivot baru di mana pun. Pita itu properti kolam - ia lahir
            # bersama anchor-nya - jadi ia dibekukan saat kluster dibuat.
            alive = []
            for c in clusters:
                lo, hi_ = c["last_idx"] + 1, p.index
                if hi_ > lo:
                    taken = (float(high[lo:hi_].max()) > c["anchor"] + c["tol"]
                             if is_high else
                             float(low[lo:hi_].min()) < c["anchor"] - c["tol"])
                    if taken:
                        continue
                alive.append(c)
            clusters = alive

            hit = next((c for c in clusters
                        if abs(p.price - c["anchor"]) <= c["tol"]), None)
            if hit is None:
                # KLUSTER TIDAK BOLEH LAHIR DI WARM-UP, dan tanpa ini kotaknya
                # REPAINT. `mean_true_range` merata-rata TEPAT `atr_period`
                # suku, jadi nilainya di bar yang punya cukup riwayat di
                # depannya tidak bergantung berapa bar yang dimuat - tapi di
                # bar-bar PERTAMA sebuah potongan ia merata-rata lebih sedikit
                # suku dan memberi angka lain.
                #
                # Selama toleransi cuma menentukan KEANGGOTAAN itu tidak
                # terlihat: ia sebuah ambang, dan ambang tahan terhadap geseran
                # kecil. Sejak pita toleransi masuk ke GEOMETRI, selisih itu
                # langsung jadi tepi yang bergerak - `test_no_repaint`
                # menangkapnya sebagai "grew left" pada
                # `BSL-1772064000-1772107200` begitu riwayat ditambahkan di
                # kiri. Jadi harganya dibayar di sini: kluster yang anchornya
                # tidak punya `atr_period` bar penuh di depannya tidak dibuat
                # sama sekali, alih-alih dibuat dengan skala yang belum jadi.
                if p.index < params.atr_period + 1:
                    stats["rejected_warmup"] += 1
                    continue
                # Anchor TETAP di anggota pertama - lihat docstring.
                clusters.append({"anchor": p.price, "tol": tol, "members": [p],
                                 "emitted": False, "last_idx": p.index})
                continue

            hit["members"].append(p)
            hit["last_idx"] = p.index
            if hit["emitted"]:
                # Kluster tumbuh sesudah kotaknya lahir. Tidak memancarkan
                # ulang - lihat docstring - tapi dihitung supaya populasi
                # yang tersembunyi ini bisa dibaca.
                stats["clusters_grown"] += 1
                continue

            members = hit["members"]
            if len(members) < params.min_touches:
                continue
            hit["emitted"] = True

            stats["candidates"] += 1
            prices = [m.price for m in members]
            lo_p, hi_p = float(min(prices)), float(max(prices))
            # PITA TOLERANSI DITAMBAHKAN DI SISI STOP, 8 September 2026, dan ia
            # mengubah apa yang kotak ini NYATAKAN - bukan cuma seberapa tebal
            # ia digambar.
            #
            # Versi pertama memakai sebaran pivot yang teramati apa adanya, dan
            # itu MENGECILKAN kolamnya. Kluster ini menyatakan "harga-harga ini
            # sama dalam `equal_tol_atr`", jadi pita tempat stop beristirahat
            # adalah pita toleransinya, bukan kebetulan di mana dua pivot
            # mendarat. Untuk BSL stop beli duduk DI ATAS equal high tertinggi;
            # untuk SSL cerminnya.
            #
            # Jadi PROXIMAL tidak bergerak - ia tetap equal high TERENDAH, harga
            # pertama yang disentuh saat harga naik - dan DISTAL didorong `tol`
            # melewati yang tertinggi. Stop sebuah trade dengan begitu duduk di
            # luar likuiditas yang disapu, bukan di tengahnya.
            #
            # DUA HAL IKUT BERUBAH DAN KEDUANYA DINYATAKAN. (1) `equal_tol_atr`
            # sekarang MASUK ke geometri, yang versi pertama sengaja hindari;
            # itu bisa dipertahankan hanya karena gerbang kind ini 0,0 dan tidak
            # mengikat, jadi tidak ada knob kedua yang diam-diam digerbangi.
            # (2) Kasus tinggi-nol hilang dengan sendirinya: kluster yang seluruh
            # pivotnya persis sama kini bertinggi `tol`, bukan nol. Penolaknya
            # DIPERTAHANKAN sebagai jaring - `tol` bisa nol kalau pemanggil
            # menyetel `equal_tol_atr = 0`.
            #
            # Alasan langsungnya legibilitas, dan itu terukur: dengan sebaran
            # teramati, KEEMPAT kotak di XAUUSD 15m lebih pendek dari 14 piksel
            # dan `pixel-truth` membaca 3 dari 7 karena tidak ada yang bisa
            # diukur, dengan tepi meleset sampai 29,68 persen tinggi kotaknya
            # sendiri.
            band = hit["tol"]
            top = hi_p + band if is_high else hi_p
            bottom = lo_p if is_high else lo_p - band
            if top - bottom <= 0:
                stats["rejected_zero_height"] += 1
                continue

            # BSL duduk di SUPPLY, SSL di DEMAND - lihat docstring.
            kind = ZoneKind.BSL if is_high else ZoneKind.SSL
            side = ZoneSide.SUPPLY if is_high else ZoneSide.DEMAND
            origin = members[0].index
            born = p.confirmed_at
            # Skala keberangkatan diambil di bar sebelum pivot pertama, sama
            # dengan lima detektor kotak lainnya.
            base = float(atr[max(0, origin - 1)])
            if base <= 0:
                stats["rejected_zero_atr"] += 1
                continue
            departure = round((top - bottom) / base, 3)

            zone = _finish(
                kind, side, top, bottom, origin, born,
                time, high, low, close, atr, params, departure,
            )
            if zone is not None:
                # Id membawa pivot PERTAMA dan pivot yang melahirkan kotaknya.
                # `_finish` menyusun id dari bar origin saja, dan dua kluster di
                # sisi yang sama tidak bisa berbagi pivot pertama - tapi
                # menuliskannya eksplisit lebih murah daripada membuktikannya,
                # pelajaran dari tabrakan id OTE.
                zone.id = f"{kind.value}-{int(time[origin])}-{int(time[p.index])}"
                found.append(zone)

    found = _dedupe(found, params.merge_overlap_pct, stats)
    return _present(found, params, stats, int(time[-1]))


def _selftest() -> None:
    """Sisi dan tepi, dihitung tangan, di kedua arah.

    Dua swing high di 110,0 dan 110,4 dengan toleransi yang memuat keduanya
    adalah satu kolam BSL: kotaknya 110,0..110,4 dan sisinya SUPPLY, karena
    harga naik MENUJU stop yang beristirahat di sana. Proximal sebuah zona
    supply adalah bottom, jadi harga menyentuh 110,0 lebih dulu - equal high
    yang lebih rendah - dan itu memang stop pertama yang kena.
    """
    tol = 0.5
    prices = [110.0, 110.4]
    top, bottom = max(prices) + tol, min(prices)
    assert (top, bottom) == (110.9, 110.0)
    proximal = bottom  # supply: harga naik, menyentuh equal high TERENDAH dulu
    assert proximal == 110.0
    # Distal duduk di luar equal high tertinggi, bukan di antaranya.
    assert top > max(prices)
    lows = [99.6, 100.0]
    top2, bottom2 = max(lows), min(lows) - tol
    proximal2 = top2  # demand
    assert (top2, bottom2) == (100.0, 99.1) and proximal2 == 100.0
    assert bottom2 < min(lows)
    # Pivot yang PERSIS sama tidak lagi memberi tinggi nol.
    same = [105.0, 105.0]
    assert (max(same) + tol) - min(same) == tol > 0

    # Anchor TETAP, bukan rata-rata berjalan: rantai yang menghanyut harus
    # putus, bukan menelan seluruh deret.
    anchor, tol = 100.0, 0.1
    chain = [100.0, 100.09, 100.18, 100.27]
    inside = [p for p in chain if abs(p - anchor) <= tol]
    assert inside == [100.0, 100.09], inside
