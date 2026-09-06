# Gerbang dan aturan deteksi supply and demand, diukur 6 September 2026

Detector tertua di repo ini, yang paling banyak dokumentasinya, dan satu satunya
yang ATURAN DETEKSINYA belum pernah disapu lawan outcome di rig yang sekarang.
`docs/CALIBRATION.md` menyapu `ImbalanceParams`, bukan `SupplyDemandParams`, dan
metodenya pun beda: held-rate lawan placebo, bukan exp_r dengan walk-forward.

> [!IMPORTANT]
> Hasilnya membalik urutan empat detector di repo ini. Supply and demand kini
> yang TERLEMAH dan satu satunya yang gagal praregistrasi. Docstring
> `app/detect/__init__.py` menyatakan sebaliknya sampai hari ini.

## Jawabannya, di depan

| detector | exp_r | PF | wf |
|---|---|---|---|
| ifvg | +0,3450 | 1,652 | 8/8 |
| breaker | +0,2631 | 1,566 | 8/8 |
| order_block | +0,1633 | 1,330 | 8/8 |
| **supply_demand** | **+0,0532** | **1,121** | **6/8** |

Dan angka positif itu bukan milik polanya. Tanpa gerbang departure, detector ini
terukur **-0,0514 dengan t=-5,61 lawan nol**: bukan lemah, melainkan berlawanan
arah. Yang membeli tanda positif adalah penyaringnya.

Dua puluh satu lengan aturan deteksi disapu. Tidak satu pun mengalahkan produksi.

## Gerbang departure, dua belas sel

Rig menjalankan S&D dengan `departure_min_atr = 0.0` (`POPULATION` di
`tools/calibrate.py`), jadi baris pertama adalah detector tanpa gerbang dan
sisanya gerbang dipasang sebagai saringan atas baris yang sudah selesai.

| lantai | n disimpan | exp_r disimpan | exp_r dibuang | WR | PF | wf | Welch t |
|---|---|---|---|---|---|---|---|
| tanpa gerbang | 8.624 | **-0,0514** | - | 51,11% | 0,847 | 0/8 | t lawan nol -5,61 |
| 1,0 | 3.910 | +0,0440 | -0,1305 | 56,39% | 1,145 | 6/8 | +9,42 |
| 1,5 | 2.882 | +0,0531 | -0,1038 | 56,32% | 1,168 | 5/8 | +7,68 |
| **2,0 (dikirim)** | **2.248** | **+0,0753** | -0,0961 | 55,74% | **1,227** | **6/8** | **+7,36** |
| 2,5 | 1.818 | +0,0649 | -0,0825 | 53,80% | 1,185 | 5/8 | +5,66 |
| 3,0 | 1.468 | +0,0645 | -0,0752 | 52,93% | 1,178 | 5/8 | +4,80 |
| 4,0 | 965 | +0,0716 | -0,0669 | 51,81% | 1,192 | 5/8 | +3,76 |
| 6,0 | 424 | +0,0790 | -0,0581 | 51,65% | 1,201 | 5/8 | +2,32 |

Ambang Bonferroni 2,9137. Tiap ambang memisahkan ke arah yang sama dan jauh
melewati ambang itu, dan **tidak satu pun mencapai walk-forward 8 dari 8**.

## Titik pasang gerbangnya sendiri menggeser angka

Produksi memasang `departure_min_atr` di titik DETEKSI, menolak kandidat sebelum
`_dedupe` dan `mark_crowding` melihatnya. `gate_sweep` memasang ambang yang sama
sebagai SARINGAN atas baris yang sudah selesai. Predikatnya sama, titik pasangnya
tidak, dan hasilnya tidak identik:

| penempatan | n | exp_r | PF | wf |
|---|---|---|---|---|
| saringan sesudahnya (`gate_sweep`) | 2.248 | +0,0753 | 1,227 | 6/8 |
| **saat deteksi (produksi)** | **2.200** | **+0,0532** | **1,121** | **6/8** |

48 trade dan 0,022 R. Jadi angka gerbang S&D yang selama ini diterbitkan di repo
ini **sedikit melebihkan** apa yang produksi jalankan. Untuk `order_block`, `fvg`
dan `breaker` asimetri ini tidak ada: rig memakai default penuh mereka.

Per timeframe, pada penempatan produksi:

| tf | n | exp_r | PF | wf |
|---|---|---|---|---|
| 15m | 374 | +0,0672 | 1,121 | 6/8 |
| 30m | 883 | **+0,1083** | **1,224** | 5/8 |
| 1h | 434 | +0,0596 | 1,135 | 5/8 |
| 4h | 375 | **-0,0437** | 0,857 | 3/8 |
| 1d | 134 | **-0,0977** | 0,589 | 0/1 |

4h dan 1d negatif bahkan dengan gerbangnya.

## Sapuan aturan deteksi, 21 lengan

`tools/sd_variants.py`, dua sel 30m untuk pass pertama. Semua diregistrasi
sebelum angkanya dilihat.

| lengan | n | exp_r | WR | PF | wf | t lawan A |
|---|---|---|---|---|---|---|
| A produksi (rig, tanpa gerbang) | 3.497 | -0,0405 | 54,16% | 0,891 | 2/8 | - |
| B lilin keluar body 0,70 | 1.659 | +0,0038 | 49,85% | 1,009 | 3/8 | +1,34 |
| C body ratio 0,7 kedua kaki | 1.598 | +0,0225 | 51,81% | 1,055 | 4/8 | +1,86 |
| D body ratio 0,6 | 2.642 | -0,0101 | 54,20% | 0,973 | 4/8 | +1,23 |
| E body ratio 0,4 (longgar) | 4.046 | -0,0402 | 54,20% | 0,891 | 2/8 | **+0,01** |
| F proximal_basis body | 2.837 | +0,0383 | 52,59% | 1,095 | 5/8 | +2,96 |
| G base_max_bars 3 | 3.574 | -0,0137 | 53,97% | 0,964 | 3/8 | +1,19 |
| H base_max_bars 12 | 3.417 | -0,0505 | 53,73% | 0,862 | 1/8 | -0,45 |
| I impulse_atr 1,5 | 1.358 | +0,0363 | 51,91% | 1,089 | 5/8 | +2,24 |
| J base_max_atr 1,5 | 2.177 | -0,0147 | 47,73% | 0,967 | 4/8 | +0,87 |
| **K gerbang 2,0 saat deteksi** | 883 | **+0,1083** | 46,66% | **1,224** | 5/8 | +2,98 |
| L K + proximal_basis body | 1.054 | +0,0496 | 40,23% | 1,089 | 5/8 | +1,80 |
| M K + impulse_atr 1,5 | 530 | +0,0908 | 45,66% | 1,193 | 4/8 | +2,10 |
| N K + body ratio 0,7 | 417 | +0,0972 | 43,17% | 1,195 | 6/8 | +1,78 |
| O K + body + impulse_atr 1,5 | 615 | +0,0414 | 42,28% | 1,079 | 3/8 | +1,31 |
| T K + impulse_atr 2,5 | 183 | +0,0631 | 40,98% | 1,125 | 3/7 | +0,84 |
| U K + impulse_atr 3,0 | 110 | +0,1328 | 40,00% | 1,257 | **0/0** | +0,97 |

Ambang Bonferroni 3,0233. Lengan P, Q, R, S tidak masuk tabel; alasannya di
bagian berikutnya.

### Menumpuk di atas gerbang MEMPERBURUK, dan itu polanya sendiri

Lengan F sendirian membawa exp_r dari -0,0405 ke +0,0383. Di atas gerbang, ia
menurunkan 0,1083 ke 0,0496. Sama untuk I: +0,0363 sendirian, tapi M memberi
0,0908 lawan 0,1083 milik K. Dua penyaring yang menyaring hal yang sama, dan
yang kedua cuma memotong trade bagus.

Pola yang identik dengan `docs/QA-OB-GATE.md`: gerbang departure order block
berhenti memisahkan begitu filter impuls-dari-close dikirim. Sebuah aturan yang
membantu populasi tanpa gerbang harus diukur ULANG di atas gerbangnya, dan
melewatkan langkah itu akan mengirim penyaring yang terlihat terukur.

### Lengan U tidak boleh dibaca

exp_r +0,1328 dan PF 1,257 di lengan U adalah angka tertinggi di tabel, dan ia
**tidak punya satu fold pun yang terbaca**: wf 0/0, n=110 di dua sel. Ia ada di
tabel supaya tidak dikutip dari tempat lain tanpa kolom wf-nya.

## Empat lengan yang mengukur nol, dan kenapa itu kesalahan rancangan

Lengan P, Q, R dan S menyapu `mitigation_pct`, dan keempatnya mengembalikan
angka yang IDENTIK dengan baselinenya sampai digit terakhir, Welch t = 0,0.

Dibuktikan langsung, bukan disimpulkan. 6.000 bar XAUUSD 30m:

| `mitigation_pct` | zona | geometri | state |
|---|---|---|---|
| 0,0 | 647 | acuan | broken 622, mitigated 25 |
| 0,5 (dikirim) | 647 | **identik** | broken 622, tested 5, fresh 8, mitigated 12 |
| 1,0 | 647 | **identik** | broken 622, tested 10, fresh 8, mitigated 7 |

`mitigation_pct` hanya mengubah LABEL `state`. Rig menghargai entry di proximal,
stop di luar distal, target di zona lawan terdekat, dan tidak satu pun membaca
`state`. Lengan itu tidak bisa menggerakkan satu trade pun, apa pun nilainya.

Kelas kegagalan yang sama dengan lengan D di `docs/QA-BRK-GATE.md`, dan sama
seperti di sana, seharusnya terlihat sebelum dijalankan.

> [!NOTE]
> Yang benar dari ini: `mitigation_pct = 0.5` memang OUTLIER terhadap seluruh
> literatur dan seluruh implementasi yang dibaca, tetapi outlier itu nyata untuk
> GAMBAR dan mustahil untuk backtest. Rig menyelesaikan tiap zona sekali di
> sentuhan pertama, yang kebetulan persis aturan "sekali pakai" yang literatur
> sebut, jadi ketidaksepakatan itu tidak bisa menggerakkan angka mana pun di
> halaman ini.

## Apa yang sebenarnya dikatakan sumbernya

Tiga penelusuran paralel: Pine TradingView beserta source-nya, literatur metode
Seiden, dan keluarga MQL5. Tiga temuan yang mengubah arah sapuan ini.

**Angka 0,5 yang kita kirim adalah satu satunya yang punya garis keturunan.**
Definisi base yang berulang di sumber tertulis adalah body <= 50 persen rentang,
jadi lilin exciting adalah komplemennya, dan indikator CienF/OTC memakai persis
50,0 persen sebagai default. Angka **70 persen adalah yang paling banyak dikutip
dan paling tidak bersumber**: nol dari tiga belas Pine terpopuler memakainya, dan
padanan terdekatnya 0,63 (333 boost) dan 0,75 (187 boost), keduanya di skrip
kecil. Null di lengan B dan C bukan pengukuran yang gagal, itu hasil yang benar
terhadap aturan yang tidak ada.

**Body mengukur kekuatan, wick menggambar box**, dan kedua keluarga sepakat.
Order Block Detector MQL5 memakai 50 persen body-to-range untuk break tapi
menggambar full high-low; Mitigation Tracker membandingkan body lawan ATR tapi
menggambar high-low. Kita melakukan persis itu. Lengan F, yang memindahkan
proximal ke body, adalah gerakan MENJAUH dari konsensus, dan ia gagal di atas
gerbang. Sensus tepi box dari tiga belas Pine: 6 wick murni, 1 body murni, 3
campuran (distal wick, proximal body), 3 sintetis (tinggi dari ATR).

**Tidak ada angka pembanding yang bisa dipakai.** Klaim 94 persen tidak punya
sumber primer. Artikel MQL5 20904 punya 9.663 pasangan base-exit XAUUSD M5 tapi
meng-cluster GEOMETRI LILIN tanpa satu variabel outcome pun di pipeline-nya,
jadi "84,6 persen" di sana mengukur bentuk lilin yang paling dominan dan bukan
zona yang paling sering bekerja; angka 3,0 yang keluar dari sana bukan threshold
tervalidasi. MQL5 Market nol backtest terpublikasi. Yang paling banyak dipakai
di MT5, Shved dengan 230 ribu view gabungan, **tidak punya konsep impulse sama
sekali**: fractal murni plus ATR fuzz.

Satu satunya bukti peer-reviewed yang berdekatan adalah Osler (2000) di FRBNY
Economic Policy Review, dan itu menguji level support/resistance yang
dipublikasikan enam firma FX, bukan konstruksi ini.

## Celah yang riset sebut paling jelas, dan yang ternyata tidak ada

Penelusuran literatur menyimpulkan bahwa **tidak ada sumber yang menguji leg-in**,
dan menandai penerapan `impulse_body_ratio` kita ke kedua kaki sebagai
penyimpangan yang layak diukur.

Ia bukan penyimpangan, dan itu terukur. Pada 6.000 bar XAUUSD 30m:

| | |
|---|---|
| run total | 1.971 |
| run bersebelahan berlabel SAMA | **0** |
| triple dengan base di tengah | 881 |
| ditolak oleh `leg_in[0] == 0` | **0** |

`runs` tidak pernah menghasilkan dua run bersebelahan berlabel sama, jadi base
run SELALU diapit run exciting. Kita tidak menerapkan tes leg-in terpisah; kita
menerapkan satu classifier dan struktur run melakukan sisanya. Sumbunya sudah
diuji oleh lengan E, yang melonggarkan classifier itu, dan hasilnya t=+0,01.

Baris `leg_in[0] == 0` di `app/detect/supply_demand.py` karena itu unreachable.
Ia DIPERTAHANKAN dan diberi catatan, bukan dihapus: ia menyatakan bentuk yang
loop-nya andalkan, dan kalau `runs` pernah berubah, baris itulah yang harus mulai
menolak alih alih loop membaca dua kaki searah sebagai formasi.

## Sapuan pertama yang dibuang

Versi pertama `tools/sd_variants.py` memakai `SupplyDemandParams(
max_zones_per_side=0, show_broken=True)` untuk lengan A, dan itu meleset DUA
knob dari populasi rig: `merge_overlap_pct` 0,6 lawan 1,0, dan
`departure_min_atr` 2,0 lawan 0,0. Sepuluh lengan pertama jadi varian dari
populasi ketiga yang tidak sebanding dengan angka S&D mana pun di repo ini.

Yang mengungkapkannya aritmetika, bukan kecurigaan: lengan A memberi n=274 di
30m sementara gerbang 12-sel menyimpan 895 di timeframe yang sama. `POPULATION`
sekarang diimpor dari `tools.calibrate`, satu sumber, dan `_selftest` mengikat
ketiga knob-nya.

## Multi timeframe, dan ia membalik bacaan 30m

Lengan yang punya sinyal di 30m diulang di dua belas sel. Yang berubah bukan
detailnya melainkan arahnya.

| lengan | n | exp_r | WR | PF | wf | t lawan A |
|---|---|---|---|---|---|---|
| A produksi (rig, tanpa gerbang) | 8.624 | -0,0514 | 51,11% | 0,847 | 0/8 | - |
| C body ratio 0,7 kedua kaki | 3.973 | -0,0303 | 48,18% | 0,918 | 1/8 | +1,13 |
| F proximal_basis body | 6.946 | +0,0233 | 51,24% | 1,063 | 6/8 | +4,76 |
| I impulse_atr 1,5 | 3.480 | +0,0007 | 49,17% | 1,002 | 5/8 | +2,70 |
| **K gerbang 2,0 (PRODUKSI)** | **2.200** | **+0,0532** | 44,82% | **1,121** | 6/8 | +3,70 |
| **L K + proximal body** | **2.631** | **+0,0638** | 41,77% | **1,131** | **8/8** | **+3,91** |
| M K + impulse_atr 1,5 | 1.333 | +0,0285 | 44,71% | 1,067 | 4/8 | +2,32 |
| N K + body ratio 0,7 | 1.108 | +0,0164 | 41,61% | 1,036 | 4/8 | +1,68 |

Di 30m sendirian, L LEBIH BURUK dari K: +0,0496 lawan +0,1083. Di dua belas sel
ia lebih baik di setiap sumbu dan satu satunya lengan di seluruh program ini yang
mencapai walk-forward 8 dari 8. Membaca sapuan dua sel saja akan menolak satu
satunya kandidat yang lolos fold-nya.

### Dan ia tetap tidak layak dikirim

> [!IMPORTANT]
> Angka +3,91 milik lengan L diukur lawan lengan A, dan **lengan A bukan
> produksi**. A menjalankan `departure_min_atr = 0.0`, populasi rig; produksi
> mengirim 2,0, yaitu lengan K. Welch t lengan L lawan K adalah **+0,272**, jauh
> di bawah ambang 3,0233 yang sama.
>
> Versi pertama `tools/sd_variants.py` mencetak verdict `"LEBIH BAIK dari
> produksi"` untuk lengan L. Labelnya sekarang menyebut lengan A, karena sebuah
> lengan yang mengalahkan baseline tanpa gerbang belum mengalahkan apa pun yang
> dikirim.

Per timeframe menjelaskan kenapa selisih gabungannya tipis: L menolong 15m
banyak, MERUSAK 30m, dan mengurangi rugi di 4h dan 1d.

| tf | K exp_r | L exp_r | K PF | L PF | K wf | L wf |
|---|---|---|---|---|---|---|
| 15m | +0,0672 | **+0,2081** | 1,121 | **1,377** | 6/8 | 5/8 |
| 30m | +0,1083 | **+0,0496** | 1,224 | **1,089** | 5/8 | 5/8 |
| 1h | +0,0596 | +0,0695 | 1,135 | 1,146 | 5/8 | 6/8 |
| 4h | -0,0437 | -0,0054 | 0,857 | 0,984 | 3/8 | 3/8 |
| 1d | -0,0977 | -0,0695 | 0,589 | 0,736 | 0/1 | 2/6 |

Tidak satu timeframe pun mencapai 8 dari 8 untuk kedua lengan; angka 8 dari 8
milik L adalah sifat agregatnya. Selisih bersihnya +0,0106 R.

## Cermin Pine, dan cacat yang ia temukan di dirinya sendiri

`Zonelab SD` ditulis di TradingView sebagai cermin `supply_demand.detect`,
dengan tabel jejak filter di sudut chart. Pola yang sama dengan `Zonelab OB` di
`docs/QA-OB-GATE.md`: yang dibandingkan PROPORSI penolakan, bukan koordinat box,
karena `FX:XAUUSD` dan `mt5:XAUUSD` adalah dua instrumen berbeda.

Run pertama cermin itu langsung menemukan cacat, dan cacatnya di cerminnya:
Python melaporkan `rejected_base_drifted` sebagai 14,01 persen kandidat dan
Pine-nya tidak punya bucket itu sama sekali. Aturan `|close[base_to] -
open[base_from]| / height <= max_base_drift` terlewat saat membaca detector.
Ditambahkan, dan DI URUTAN YANG SAMA - Python memeriksa drift sebelum departure,
dan urutan itu menentukan setiap proporsi sesudahnya adalah proporsi DARI apa.

Setelah diperbaiki, XAUUSD 30m:

| bucket | Python (mt5, 9.236 kandidat) | Pine (FX, 4.942 kandidat) | selisih |
|---|---|---|---|
| base too tall | 9,38% | 12,04% | +2,66 pp |
| base drifted | 14,01% | 11,31% | -2,70 pp |
| weak departure | 55,46% | 56,74% | +1,28 pp |
| drawn | 21,16% | 19,89% | -1,27 pp |

Selisih absolut terbesar **2,70 poin persen**, di dua venue dengan panjang
riwayat berbeda. Dua peringatan compiler juga ditolak alih alih diabaikan:
`ta.highest` di dalam conditional tidak dievaluasi tiap bar, jadi ekstrem base
dihitung dengan loop offset yang eksak.

## Benchmark lawan indikator lain di chart yang sama

`Supply and Demand Zones [BigBeluga]` ditambahkan ke chart yang sama, XAUUSD 30m.

**Jumlah box tidak dibandingkan**, dan itu pelajaran dari `docs/QA-OB-GATE.md`
di mana klaim "6 lawan 6440" ternyata membandingkan yang DITAMPILKAN dengan yang
DIDETEKSI. Keduanya di sini adalah hitungan tampilan, dan milik kita di-cap 40.

Yang dibandingkan tinggi box dan apakah kedua metode menunjuk harga yang sama:

| | tinggi minimum | median | maksimum |
|---|---|---|---|
| BigBeluga | 23,72 | 26,89 | 27,30 |
| Zonelab SD | 8,90 | 16,76 | 36,39 |

Tinggi mereka praktis konstan, dan itu memang konstruksinya: satu tepi adalah
wick extreme dan tepi lawannya `ATR(200) * 2`, jadi tingginya tidak membawa
informasi apa pun tentang lilinnya. Tinggi kita adalah rentang base sungguhan.

**7 dari 8 zona mereka beririsan dengan minimal satu zona kita.** Irisannya
sangat tidak merata: 100 persen, 73 persen, 65 persen, 57 persen, lalu 22, 4 dan
3,5 persen, dan satu tanpa irisan sama sekali. Jadi kedua metode menemukan
wilayah harga yang sebagian besar sama dan menggambar batas yang berbeda, yang
merupakan hasil yang diharapkan ketika satu pihak menurunkan tinggi dari ATR dan
pihak lain dari base.

## Cara mengulang

```bash
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.gate_sweep --detector supply_demand
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.sd_variants --cells 30m
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.sd_variants --cells all --only "A ,K "
```

> [!WARNING]
> Tulis hasilnya ke file sementara dan pindahkan hanya kalau exit 0. Redirect
> langsung ke file ter-track memotongnya jadi 0 byte SEBELUM perintahnya jalan,
> dan sapuan 12 sel bisa mati di menit ke-20 karena otorisasi MT5 berkedip.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).
