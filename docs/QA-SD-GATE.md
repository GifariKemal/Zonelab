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

## Lengan L di 15m saja, dan kenapa jawabannya tidak

PF 1,377 di 15m adalah angka tertinggi di seluruh program ini, jadi
"pakai 15m saja" adalah pertanyaan yang wajar. Tiga pengukuran menutupnya, dan
tidak satu pun berupa pendapat.

**Satu, angkanya sebagian besar milik satu instrumen.**

| sel | n | exp_r | WR | PF | t | wf |
|---|---|---|---|---|---|---|
| **BTCUSD 15m** | 230 | **+0,3044** | 44,78% | **1,578** | 2,533 | 7/8 |
| **XAUUSD 15m** | 224 | +0,1092 | 38,39% | 1,189 | **0,973** | 4/8 |
| 15m gabungan | 454 | +0,2081 | 41,63% | 1,377 | 2,527 | **5/8** |

Di gold ia tidak signifikan, dan gabungannya gagal walk-forward. Angka 8 dari 8
milik lengan L adalah sifat agregat dua belas sel, bukan sifat 15m.

**Dua, kontrol pemilihan mengukur berapa banyak dari 1,377 itu milik prosedurnya.**
Mengambil PF timeframe TERBAIK untuk setiap lengan yang sudah diukur di 12 sel:

| lengan | PF gabungan | PF terbaik-dari-6 | tf |
|---|---|---|---|
| A produksi (rugi) | 0,847 | 0,891 | 30m |
| C body ratio 0,7 | 0,918 | 1,055 | 30m |
| F proximal body | 1,063 | 1,164 | 15m |
| I impulse_atr 1,5 | 1,002 | 1,091 | 30m |
| K produksi | 1,121 | 1,224 | 30m |
| **L K + proximal body** | 1,131 | **1,377** | 15m |
| M K + impulse_atr 1,5 | 1,067 | 1,193 | 30m |
| N K + body ratio 0,7 | 1,036 | 1,195 | 30m |

Median terbaik-dari-6 adalah 1,178, dan lengan L punya KENAIKAN TERBESAR dari
delapan lengan, +0,246. Jadi 1,377 adalah angka paling ter-inflasi-seleksi di
tabel, bukan yang paling kuat. Kalibrasi yang menenangkan: lengan A yang terukur
rugi tetap berhenti di 0,891, jadi prosedur ini tidak mengarang PF di atas 1 dari
lengan yang merugi - ia menaikkan sekitar 0,06 sampai 0,25.

**Tiga, dan ini yang menutupnya: enam instrumen yang tidak ikut memilih 15m.**
`tools/oos_symbols.py`, semuanya punya riwayat 15m dan 1m di venue yang sama:

| lengan | instrumen | n | exp_r | PF | t | wf |
|---|---|---|---|---|---|---|
| L | EURUSD | 212 | -0,1734 | 0,722 | -1,968 | 4/8 |
| L | GBPJPY | 195 | +0,2052 | 1,378 | +1,506 | 6/7 |
| L | USDJPY | 143 | -0,0269 | 0,958 | -0,186 | 1/3 |
| L | XAGUSD | 207 | +0,0206 | 1,033 | +0,185 | 3/8 |
| L | **ETHUSD** | 222 | **-0,2903** | 0,527 | **-4,235** | 0/7 |
| L | US30 | 232 | +0,0361 | 1,059 | +0,305 | 4/8 |

| lengan | n | exp_r | WR | PF | t | wf |
|---|---|---|---|---|---|---|
| **K produksi** | 979 | **-0,0830** | 37,90% | 0,855 | -1,899 | 1/8 |
| **L K + proximal body** | 1.211 | **-0,0433** | 35,43% | 0,929 | -0,954 | 3/8 |

**Keduanya rugi di luar sampel.** Edge 15m tidak berpindah sama sekali.

> [!WARNING]
> Angka PRODUKSI ikut jatuh, dan itu temuan tersendiri yang tidak dicari. Lengan
> K di 15m adalah +0,0672 di rig dan **-0,0830** di enam instrumen ini. Rig 12
> sel memakai dua instrumen; setiap angka di halaman ini adalah angka dua
> instrumen itu, dan ini pengukuran pertama yang menanyakan apakah ia berpindah.
>
> Riwayat 1m di terminal ini kira kira 69 hari, jadi tiap sel di sini jauh lebih
> pendek daripada sel rig dan n-nya 140 sampai 232 per instrumen. Cukup untuk
> menolak sebuah klaim, tidak cukup untuk menegakkan yang baru.

Satu hal yang bertahan lemah: lengan L KURANG rugi daripada K di luar sampel,
-0,0433 lawan -0,0830, konsisten dengan temuan 12 sel bahwa ia mengurangi rugi
di sel yang buruk. Itu bukan alasan mengirimnya.

## Cara mengulang

```bash
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.gate_sweep --detector supply_demand
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.sd_variants --cells 30m
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.sd_variants --cells all --only "A ,K "
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.oos_symbols
```

> [!WARNING]
> Tulis hasilnya ke file sementara dan pindahkan hanya kalau exit 0. Redirect
> langsung ke file ter-track memotongnya jadi 0 byte SEBELUM perintahnya jalan,
> dan sapuan 12 sel bisa mati di menit ke-20 karena otorisasi MT5 berkedip.

---

## S&D masuk rig TradingView, 8 September 2026, dan detektor kelima

Sampai hari ini S&D belum pernah lewat rig TradingView. Ia sudah punya EA MQL5
lengkap (`mql5/ZonelabSD.mq5` plus `SupplyDemandDetector.mqh`, dengan config
backtest XAU dan BTC dari M5 sampai H4), dan cermin Pine INDIKATOR "Zonelab SD"
yang divalidasi lewat proporsi bucket penolakan di bagian atas halaman ini. Yang
belum ada: strategy Pine yang lewat **kode bracket yang sama** dengan keempat
detektor imbalance, sehingga angkanya bisa disandingkan langsung.

Sekarang ada. `mql5/pine/ZonelabImbalanceStrategy.pine` jadi lima detektor,
`detektor 4=SD`.

### Bentuknya beda, dan itu bukan detail implementasi

Empat detektor lain tahu nilai gerbangnya di bar zona lahir. **S&D tidak.**
`departure_atr` diukur atas jendela yang DIPOTONG DI SENTUHAN PERTAMA, dan
`supply_demand.py` mencatat alasannya: tanpa potongan itu 34 persen zona yang
digambar produk akan GAGAL gerbang bila dinilai pada saat seorang trader
benar-benar bisa bertindak.

Terjemahan kausalnya, dan itu yang dipakai di Pine: **gerbang lolos kalau
excursion mencapai 2,0 ATR SEBELUM harga kembali menyentuh kotaknya, dalam 20
bar.** Ordernya karena itu tidak dipasang saat lahir melainkan saat ambangnya
tercapai - persis informasi yang tersedia saat itu, tanpa melihat ke depan.
Kalau harga menyentuh lebih dulu, kandidatnya mati tanpa pernah jadi order.

Konsekuensi yang harus dibaca bersama angkanya: zona S&D yang GAGAL gerbang
tidak pernah memasang limit, sementara di FVG dan OB limitnya terpasang lalu
barisnya disaring. Kolom `cand` karena itu **tidak sebanding antar detektor**
pada baris tabel yang sama.

### Regresi dijalankan sebelum angka S&D dipercaya

Menyisipkan detektor kelima menyentuh file yang dipakai empat detektor lain,
jadi sebelum membaca angka S&D, detektor 0 dijalankan ulang di XAUUSD harian:
**n=598, win 51,51%, PF 1,113, cand 1.479, gate 610** - identik digit demi digit
dengan baseline sebelum penyuntingan. Kode bersamanya utuh.

### Hasil S&D

| sel | n | win% | PF | placebo PF | margin PF | margin win |
|---|---|---|---|---|---|---|
| **XAU 1d** | 281 | 58,72 | **1,235** | 0,842 | **+0,393** | **+8,23** |
| XAU 4h | 714 | 55,88 | **1,043** | 0,916 | +0,127 | +5,45 |
| BTC 1d (2017+) | 119 | 42,86 | 0,744 | - | - | - |

**PF tertinggi dari kelima detektor di XAU harian**, di atas BRK 1,181, FVG
1,112, IFVG 1,067 dan OB 0,972. Dan di 4 jam ia kedua, di bawah FVG 1,091.

> [!WARNING]
> Baca margin placebo S&D dengan catatan yang LEBIH KERAS daripada di FVG.
> Menggeser kotak S&D menggeser PROXIMAL, dan excursion diukur DARI proximal,
> jadi geseran mengubah nilai gerbang itu sendiri - bukan cuma harga limitnya.
> Terlihat di hitungan: `gate` 331 jadi 463 di harian dan 748 jadi 1.023 di
> 4 jam. Lengan placebo memakai PERISTIWA yang berbeda, bukan kotak yang sama
> di tempat yang salah. Sama seperti yang sudah dicatat untuk IFVG.

## Dan run BTC membongkar cacat yang menyentuh SELURUH kolom harian BTC

Run BTC harian pertama memberi **PF 6,344 dengan exp_r +2,99 R** sementara
kolom RR-nya cuma 1,25. Itu tidak konsisten secara aritmetika - win rate 48,3%
dengan RR 1,25 seharusnya memberi exp_r sekitar -0,11 - jadi ia artefak, bukan
hasil, dan tidak dicatat sebagai angka.

Sebabnya riwayat BTC di TradingView mulai **2011-08-18**, saat harga sekitar 10
dolar. Sizing di rig ini `qty = risk_usd / risk`; kalau risk beberapa sen, qty
meledak dan satu trade menghasilkan ribuan R. Beberapa trade begitu mendominasi
seluruh sampel.

Dibatasi ke 2017 dan sesudahnya, dan **keempat detektor lain diuji ulang di
jendela yang sama**:

| detektor | BTC 1d jendela penuh (2011+) | BTC 1d 2017+ | selisih |
|---|---|---|---|
| FVG | **1,402** | **0,737** | **-0,665** |
| IFVG | **1,117** | **0,844** | **-0,273** |
| SD | 6,344 | 0,744 | -5,600 |
| BRK | 0,969 | 0,931 | -0,038 |
| OB | 0,939 | 0,907 | -0,032 |

**Tidak ada satu pun detektor di atas satu di BTC harian begitu riwayat awal
dibuang.** Dan yang jatuh paling jauh justru dua yang sebelumnya di ATAS satu,
sementara dua yang sudah di bawah satu nyaris tidak bergerak - persis pola yang
diharapkan kalau kelebihannya memang datang dari artefaknya.

### Apa yang ini cabut

- **FVG "di atas satu di tiga sel"** jadi dua: XAU 4h 1,091 dan XAU 1d 1,112.
  BTC 1d 1,402 dicabut.
- **IFVG "dua sel di atas satu"** jadi SATU: XAU 1d 1,067. Dan klaim yang lebih
  keras - "satu-satunya yang bertahan di BTC harian, 1,117 lawan placebo 0,812"
  - tidak berlaku lagi: di 2017+ ia 0,844.
- Setiap baris **BTC harian** di halaman benchmark empat detektor diukur di
  jendela penuh dan karena itu terkontaminasi.

Yang TIDAK tersentuh: seluruh sel XAUUSD, karena emas tidak pernah
diperdagangkan di harga yang membuat normalisasi R runtuh. Sel BTC 4 jam dan
1 jam belum diuji ulang dan harus dianggap tersangka sampai diuji.


## Stress test delapan periode S&D, 8 September 2026

Saringan terberat repo ini akhirnya dikenakan ke satu-satunya detektor yang
HIDUP. Batas periode identik dengan run OB, BRK dan IFVG; jendela diverifikasi
di baris `win` setiap run; baseline direproduksi lebih dulu (n=281, PF 1,235).

### FX:XAUUSD harian, sel tempat angka 1,235 berasal

| periode | n | win% | PF |
|---|---|---|---|
| 2000-2003 | 20 | 60,00 | **2,550** |
| 2003-2006 | 31 | 61,29 | 0,994 |
| 2006-2010 | 46 | 47,83 | 0,895 |
| 2010-2013 | 40 | 55,00 | **1,326** |
| 2013-2016 | 35 | 60,00 | **1,355** |
| 2016-2020 | 42 | 50,00 | 0,563 |
| 2020-2023 | 32 | 59,38 | **1,051** |
| **2023-2026** | 26 | 69,23 | **2,629** |
| **lolos** | | | **5 dari 8** |

**Dan periode SEKARANG adalah yang TERBAIK dari delapan**, 2,629. Itu kebalikan
dari IFVG (2023-2026 terburuk dari delapannya, 0,730) dan BRK (kedua terburuk,
0,683). Satu periode lagi nyaris lolos: 2003-2006 di 0,994.

### COMEX:GC1! harian, venue yang berbeda untuk logam yang sama

| periode | n | win% | PF |
|---|---|---|---|
| 2000-2003 | 22 | 63,64 | **1,323** |
| 2003-2006 | 35 | 54,29 | 0,603 |
| 2006-2010 | 45 | 42,22 | 0,606 |
| 2010-2013 | 24 | 62,50 | **1,164** |
| 2013-2016 | 26 | 50,00 | 0,728 |
| 2016-2020 | 36 | 38,89 | 0,761 |
| 2020-2023 | 26 | 65,38 | **1,303** |
| 2023-2026 | 27 | 55,56 | 0,752 |
| **lolos** | | | **3 dari 8** |

Baseline jendela penuh COMEX: n=251, win 51,79%, **PF 0,797** - di bawah satu,
lawan 1,235 di spot. **Emas yang sama, timeframe yang sama, venue berbeda, dan
putusannya berbalik.** Deret GC1! kontinu dan tidak disesuaikan, jadi ia membawa
lompatan roll yang dibaca detektor sebagai impuls asli; itu tersangka pertama
dan belum dipisahkan di sini.

### Peringkat sesudahnya

| detektor | PF XAU 1d | periode lolos | periode sekarang |
|---|---|---|---|
| **supply_demand** | **1,235** | **5 dari 8** | **2,629, TERBAIK dari delapannya** |
| BRK | 1,181 | 3 dari 8 | 0,683 |
| FVG | 1,112 | 6 dari 8 (diukur di 4 jam) | - |
| IFVG | 1,067 | 6 dari 8 | 0,730, terburuk dari delapannya |
| OB | 0,972 | 5 dari 8 | 1,041 |

**Tidak ada satu pun yang mencapai 8 dari 8**, dan itu aturan yang menggerbangi
`orderable`. S&D SATU-SATUNYA yang `orderable=True`, jadi ia gagal aturan yang
mengatur statusnya sendiri - persis alasan yang membuat `ifvg.orderable` tetap
mati. Bedanya, dan ini yang harus dibaca bersamaan: S&D gagal dengan periode
sekarang di PUNCAKNYA, sementara IFVG gagal dengan periode sekarang di dasarnya.

> [!WARNING]
> n per periode 20 sampai 46, jauh lebih tipis daripada run IFVG (135-173).
> Dua puluh trade tidak memisahkan 2,550 dari satu secara meyakinkan, dan
> 2003-2006 di 0,994 berarti hitungan 5-lawan-6 bergantung pada satu sisi koin.
> Yang ditopang tabel ini HITUNGAN lolos-gagal dan bentuknya lintas periode,
> bukan presisi tiap sel. Perbandingan FVG juga tidak sepenuhnya setara: ia
> satu-satunya yang delapan periodenya diukur di 4 jam, bukan harian.

## Dua cacat sizing ditemukan lewat COMEX, dan keduanya diperbaiki

Run COMEX pertama memberi **PF 0,800 berdampingan dengan exp_r -9,6389 R** -
mustahil untuk win 51,79% dengan RR 0,92.

**Cacat 1, `qty`.** Rig memakai `qty = risk_usd / risk`, yang diam-diam
mengasumsikan satu unit bergerak satu dolar per poin. Benar untuk CFD spot
(`pointvalue` 1), SALAH untuk futures: satu kontrak COMEX GC adalah 100 troy
ounce, jadi `pointvalue` 100 dan setiap R membesar seratus kali. **PF selamat
karena ia rasio dan pengalinya hilang; exp_r tidak.** Dikonfirmasi sampai empat
angka penting: sesudah `qsize()` memakai `syminfo.pointvalue` dan `risk_usd`
dinaikkan supaya `qty` tetap sama, n, win% dan PF identik sementara exp_r jadi
**-0,0964 = -9,6389 / 100**.

**Cacat 2, `notional`.** Baris biaya menghitung `entry_price * size` tanpa
pointvalue, jadi biaya futures 100 kali terlalu kecil - terbaca 0,0001 R padahal
XAU spot di sel sebanding membaca 0,015 R. Diperbaiki dengan pengali yang sama.

**Tidak ada angka lama yang dicabut karenanya:** XAUUSD dan BTCUSD keduanya
`pointvalue` 1, jadi kedua cacat tidak pernah menyentuh satu pun sel yang sudah
diukur. Yang berubah: instrumen ber-pointvalue bukan 1 sekarang bisa dipakai.
Baris `cfg` sekarang mengecho `pv` supaya skala feed terlihat.

> [!CAUTION]
> Model biaya persen SALAH KELAS untuk futures, bukan cuma salah angka. Bursa
> menagih komisi per KONTRAK; satu GC bernilai sekitar 350.000 dolar, jadi
> 0,0113 persen memberi 1.300 dolar per sisi padahal biaya nyatanya belasan
> dolar. Run COMEX di atas memakai 0,002 sebagai perkiraan komisi plus satu
> tick, dan itu angka yang DINYATAKAN, bukan turunan `app/costs.py`.


## Parity Pine lawan Zonelab, 8 September 2026: TIDAK identik, dan bedanya bisa didaftar

### Yang cocok: aritmetika gerbangnya

Jendela disamakan lebih dulu, dan itu perlu dua koreksi sebelum angkanya berarti.

**Koreksi pertama, denominatornya beda.** Pine menaikkan `c_cand` SESUDAH
saringan tinggi kotak dan drift; `supply_demand.py` menaikkan `candidates`
SEBELUM keduanya. Membandingkan keduanya apa adanya memberi selisih 5,11 poin
persen yang seluruhnya palsu.

**Koreksi kedua, jendelanya beda.** MT5 di mesin ini cuma memegang 3.128 bar
harian XAUUSD, mulai 2016-08-09, sementara Pine punya sampai 2000. Pine
dijalankan ulang dengan `win_from` 2016-08-09.

Pada jendela dan denominator yang sama:

| | kandidat mencapai gerbang | lolos | proporsi |
|---|---|---|---|
| Pine (FXCM) | 428 | 131 | **30,61%** |
| Python produksi (MT5) | 520 | 147 | **28,27%** |
| | | | **selisih 2,34 poin persen** |

Itu di dalam batas kesetiaan yang sudah dipatok halaman ini: validasi cermin
Pine 6 September mencatat selisih bucket terbesar 2,70 poin persen antara dua
venue. Jadi **gerbang keberangkatan berperilaku sama di kedua sisi.**

Hitungan kandidatnya sendiri berbeda 18 persen (428 lawan 520) dan itu memang
tidak bisa dibandingkan lintas feed: klasifikasi lilin bergantung pada
`range >= 1,0 x ATR[1]` dan `body_ratio >= 0,5`, keduanya sensitif terhadap OHLC
persis, jadi FXCM dan MT5 membagi bar jadi base lawan leg secara berbeda.

### Yang TIDAK ada di Pine, dan didaftar supaya tidak jadi kejutan

| ada di Python | di Pine | akibat |
|---|---|---|
| `_dedupe` (`merge_overlap_pct` 0,6) | **tidak ada** | produksi membuang zona sesisi yang bertumpuk; Pine memperdagangkan semuanya. Dimatikan (1,0) di sisi Python untuk perbandingan di atas |
| lifecycle dan `mitigation_pct` | tidak ada | Pine strategy, bukan penggambar; tidak ada `state` |
| `min_profit_margin` | tidak ada | default 0,0, tidak menyaring apa pun |
| `curve`, `formation_score`, `base_overlap`, `arrival_atr` | tidak ada | semuanya label, bukan saringan |
| `proximal_basis` "body" | tidak ada | default "wick", jadi tidak mengikat |

Satu perbedaan MEKANIK yang disengaja: Python menghitung `departure_atr` atas
jendela yang dipotong di sentuhan pertama; Pine mendaftarkan order saat ambang
2,0 ATR terlampaui. Keputusan lolos-gagalnya setara, mekanismenya tidak, dan
Pine tertinggal satu bar karena order didaftarkan di akhir bar.

**Jadi jawabannya: tidak identik.** Yang cocok aritmetika gerbangnya sampai 2,34
poin persen; yang berbeda bisa dihitung dan tidak satu pun mengikat di default,
kecuali `_dedupe` yang memang membuat populasi gambar lebih kecil dari populasi
trade.

### Catatan sampingan yang muncul dari jendela yang disamakan

Pine di 2016-08-09 sampai sekarang memberi **PF 0,957** pada n=102, sementara
jendela penuh 2000-2026 memberi 1,235. Konsisten dengan tabel delapan periode:
2016-2020 adalah periode terburuknya (0,563).

## Autodrawing S&D, diukur 8 September 2026

`e2e/pixel-truth.mjs` diarahkan ke `supply_demand`, XAUUSD harian, 2.000 bar:

| pemeriksaan | hasil |
|---|---|
| zona ditemukan di canvas | 6 dari 6 |
| ada kotak berdiri sendiri dan cukup tinggi | 4 dari 6 terukur, 2 berbagi pita harga |
| cukup tepi terbaca | **lolos, atas 4/4 dan bawah 4/4** |
| tepi ATAS di tempat skala harga menaruhnya | terburuk **0,4px** |
| tepi BAWAH di tempat skala harga menaruhnya | terburuk **0,5px** |
| kotak menutupi bar basis asalnya | terburuk **0,01 bar** di luar kotak |
| tepi kiri terbaca | **6 dari 6** |

**7 dari 7 lolos.** Coverage border 1,000 di keenam zona, sama seperti fvg dan
order_block, dan belahan terbalik-lawan-tidak-terbalik jadi 3 lolos lawan 2
gagal masih persis di garis inversi.

### Dua temuan yang khusus S&D

**Isyarat inversi ternyata AMBIGU.** Dua zona S&D yang bertumpuk tapi TIDAK
terbalik menghasilkan pita bergaris ganda yang tampak persis seperti
`inverted_inner_stroke` - isyarat "kotak di dalam kotak" yang dimasukkan ke
legenda 7 September sebagai penanda bahwa sebuah pita berganti peran. Auditor
membacanya begitu: zona DBR dikira terbalik padahal tidak. Grounding run ini
USABLE, jadi klaimnya tidak tercemar angka karangan.

**Nol zona supply digambar, dan itu bukan cacat detektor.** Auditor menduga
layer supply gagal render. Diperiksa langsung di detektor: XAU 1d memberi
**34 supply lawan 61 demand** dari 95 zona. Yang nol adalah yang lolos cap
tampilan - di pasar naik, dua belas zona terdekat harga semuanya demand. Jebakan
`max_zones_per_side` dalam wujud ketiga, dan kali ini ia membuat pembaca
menyimpulkan detektornya rusak.


## Isyarat inversi diperbaiki, 8 September 2026

### Apa yang ambigu

Sampai hari ini zona dengan `inverted_at` digambar dengan border KEDUA beberapa
piksel di dalam yang pertama, SOLID - "kotak di dalam kotak", satu-satunya
isyarat yang selamat di kotak kecil. Masalahnya **dua garis sejajar sewarna
adalah persis yang dihasilkan dua kotak SESISI yang tumpang tindih sebagian** -
tumpukan yang biasa di `supply_demand`, yang tidak punya zona terbalik sama
sekali.

Terukur di audit visual: zona DBR yang bottom-nya 4019,06 jatuh di bawah top
zona di bawahnya 4030,71 tergambar sebagai pita bergaris ganda, dan auditor
melaporkannya sebagai zona yang BERGANTI PERAN. Ia tidak. Grounding run itu
USABLE, jadi laporannya tidak tercemar angka karangan - isyaratnya memang
bertabrakan makna.

### Yang diperbaiki TEKSTURNYA, bukan geometrinya

Geometri tidak bisa membedakannya: tumpang tindih memang menghasilkan dua garis
sejajar, dan itu data yang benar. Tapi tumpang tindih **tidak bisa menghasilkan
garis putus-titik**, karena setiap border kotak lain solid.

Stroke dalam sekarang `[5 2 1 2]` dalam satuan device pixel. Polanya sengaja
bukan `[4 3]` (dipakai border zona yang belum `confirmed`) dan bukan `[1 3]`
(`--dash-fvg`, di rule proximal), jadi ketiganya tetap saling terbedakan. Dash
juga DISETEL ULANG lebih dulu, karena tanpa itu zona yang belum confirmed
mewarisi `[4 3]` dari border luarnya dan stroke dalamnya berhenti jadi isyarat
yang tetap.

### Diverifikasi tiga cara

**Terlihat.** Screenshot IFVG harian: stroke dalam jelas putus-titik, berbeda
tegas dari border luar yang solid.

**Auditor sekarang menalar benar.** Run ulang `chart-audit` pada
`supply_demand`, dan tumpukan yang sama dilaporkan sebagai: *"Per your own
legend this is an overlap of two same-side boxes, not an inversion, and both
lines do read as solid - so this is drawn correctly."* Ia memakai solidity
untuk membedakannya, yang persis fungsi perbaikan ini. Grounding USABLE.

**Nol regresi pengukuran.**

| detektor | sebelum | sesudah |
|---|---|---|
| ifvg | atas 4/7, bawah 5/7, galat 0,5 / 0,4px | **sama persis** |
| breaker | atas 1/5, bawah 3/5, galat 0,5 / 0,5px | **sama persis** |

Legenda `chart-audit.mjs` juga diperbarui: ia sekarang menyebut stroke dalam
DASH-DOT dan memperingatkan eksplisit agar dua garis SOLID sejajar TIDAK dibaca
sebagai inversi.

`pixel-truth.mjs` menyempitkan jendela pencarian jadi 3px untuk kedua kind
terbalik dengan alasan "stroke dalam memenangkan kontes baris terkuat". Premis
itu bergeser - stroke putus-titik tidak lagi mendarat utuh di satu baris - tapi
penyempitannya TIDAK dicabut, karena alasannya struktural (stroke luar ADALAH
kotaknya, yang dalam duduk 3px ke dalam), dan angkanya membuktikan tidak ada
yang bergerak. Dicatat di file itu supaya pembaca berikutnya tahu premisnya
sudah berubah.

### Satu klaim auditor lagi, diperiksa dan ditolak

Auditor melaporkan "rule vertikal hijau di tepi kiri kotak RBR atas yang
berlanjut ke bawah melewati border bawahnya sendiri", dengan catatan ia tidak
bisa memastikan itu bukan lilin. Diperiksa di gambarnya: itu **lilin impuls**,
batang hijau tinggi yang memulai rally di posisi x itu, membentang dari sekitar
4040 ke 4300. Bukan cacat gambar.


Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).
