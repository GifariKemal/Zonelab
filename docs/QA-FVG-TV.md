# QA FVG di TradingView, setelah perbaikan urutan lifecycle

6 September 2026. Lingkup: detektor `fvg`, dua instrumen (XAUUSD dan BTCUSD),
lima timeframe, diukur di TradingView Strategy Tester lewat
`mql5/pine/ZonelabFVGStrategy.pine`.

> [!IMPORTANT]
> Semua angka ekspektasi FVG yang lebih tua dari tanggal ini diukur dengan
> `replay_lifecycle` yang memeriksa pecah sebelum sentuh, dan karena itu terlalu
> optimis. Lihat bagian pertama.

## 1. Cacat yang diperbaiki

`replay_lifecycle` memeriksa `close` menembus distal SEBELUM memeriksa sentuhan.
Bar yang masuk zona lalu menutup di seberangnya keluar di `break` sebelum sempat
mencatat apa pun, jadi ia melaporkan `touches=0` dan `first_test_time=None`.
Tiga belas tool memakai `first_test_time` sebagai pemicu entry, sementara
`broker.py` hanya bisa LIMIT dan limitnya duduk di proximal - yang bar penyayat
itu tembus. Jalur hidup mengambil trade yang jalur ukur tidak pernah hitung,
dan yang tidak dihitung itu hampir seluruhnya loser.

Untuk sebuah FVG, kedua tepi kotak adalah proximal dan distal, jadi harga tidak
bisa mencapai distal tanpa melewati proximal. "Pecah tanpa pernah disentuh"
karena itu praktis kosong: sensus TradingView mencatat 0 pembatalan dari 3.116
zona di XAU 30m setelah urutannya benar.

XAUUSD 30m, gerbang 0,25, target 2R, resolusi 5m, 2025-04-08 ke depan:

| lengan | n | menang | kalah | exp_r | PF |
|---|---|---|---|---|---|
| pecah dulu (lama) | 1.045 | 515 | 530 | +0,4785 | 1,943 |
| sentuh dulu (baru) | 1.657 | 593 | 1.064 | +0,0736 | 1,115 |
| TradingView, aturan sama | 1.664 | 548 | 1.116 | - | 0,956 |

Winner-nya nyaris sama di ketiganya. Yang hilang di lengan lama adalah 530
lawan 1.064 loser. Populasi TradingView cocok dengan lengan baru, bukan lama.

Dampak pada rig repo sendiri (`intrabar.resolved`, XAU 30m, resolusi 5m):

| gerbang | sebelum | sesudah |
|---|---|---|
| mati | +0,3179 R, PF 1,799 | +0,0691 R, PF 1,137 |
| 0,25 | +0,5491 R, PF 2,223 | +0,0919 R, PF 1,155 |

t lawan nol untuk gerbang 0,25 turun ke +1,88, di bawah ambang Bonferroni
3,241 yang dipakai sweep aslinya.

**Gambar tidak bergeser.** `state` dan `time_to` ditentukan `break_index`, dan
bar yang jadi `break_index` tidak berubah. Diverifikasi pada 10.266 zona di
50.000 bar: 0 beda geometri, 0 beda `state`, 0 beda `time_to`. Yang berubah
hanya `touches` (4.283 zona) dan `first_test_time` (2.572 zona), dan arah
perubahannya benar - zona tersayat sekarang mengaku pernah disentuh.

Dijaga oleh `backend/tests/test_sliced_zone_never_tested.py` dari dua sisi.
Suite penuh: 1.320 lulus.

## 2. Rentang yang TradingView berikan, terukur

Dibaca dari dalam script, bukan diasumsikan.

| TF | bar | rentang XAU | tahun |
|---|---|---|---|
| 15m | 21.925 | 2025-09-30 sampai 2026-09-04 | 0,9 |
| 30m | 31.697 | 2024-01-02 sampai 2026-09-04 | 2,7 |
| 1h | 21.746 | 2023-01-02 sampai 2026-09-04 | 3,7 |
| 4h | 21.109 | 2013-01-02 sampai 2026-09-04 | 13,7 |
| 1d | 13.296 | 1970-02-26 sampai 2026-09-03 | 56 |

`use_bar_magnifier = true` wajib: tanpa itu setiap bar yang memuat stop DAN
target diselesaikan sebagai kalah. Terukur XAU 30m tanpa gerbang, PF 0,9396
tanpa lawan 0,9568 dengan, pada 6.409 lawan 6.408 trade.

## 3. Gerbang tidak menyortir DI 30m

Di 4h ia menyortir, dan kuat - lihat bagian 8. Yang di bawah ini khusus 30m.

XAU 30m, target 2R, stop 0,25 ATR, tanpa biaya:

| gerbang | n | PF | exp_r |
|---|---|---|---|
| mati | 6.410 | 0,957 | -0,0275 |
| 0,25 | 3.089 | 0,960 | -0,0268 |
| 0,50 | 4.593 | 0,981 | -0,0126 |
| 1,00 | 5.772 | 0,969 | -0,0201 |

Sebaran 0,957 sampai 0,981 di empat nilai. Gerbang `ceiling` yang direkomendasikan
`docs/QA-FVG-RECALIBRATION.md` (0,25) bukan yang terbaik dan selisihnya di dalam
noise. 0,5 dipakai untuk bagian 5 sampai 7 karena ia yang tertinggi di sini,
bukan karena ia terbukti memisahkan. Bagian 8 mengukurnya lagi di 4h pada
margin atas placebo dan sampai pada 0,25.

## 4. Kenaikan terhadap reward adalah placebo

XAU 30m, gerbang 0,5, stop 0,25 ATR, tanpa biaya:

| reward | PF asli | PF placebo (geser 1 ATR) |
|---|---|---|
| 2R | 0,981 | 1,044 |
| 4R | 1,038 | - |
| 6R | 1,093 | 1,090 |

PF naik monoton terhadap reward, dan di 6R kotak yang digeser 1 ATR memberi
1,090 lawan 1,093. Yang dipanen reward tinggi adalah struktur pasarnya, bukan
FVG-nya. **Tanpa lengan placebo, angka 1,093 akan terbaca sebagai temuan.**

## 5. Matriks penuh, dengan biaya dan kontrol

Konfigurasi: gerbang 0,5, target 4R, stop 1,0 ATR, horizon 80 bar, Bar Magnifier
menyala. Biaya dari `app/costs.py`: XAU 0,0113% per sisi, BTC 0,01329% per sisi
(profil broker, bukan `_default` Binance).

Stop dilebarkan dari 0,25 ke 1,0 ATR karena alasan struktural, bukan tuning:
sizing per risiko membuat notional berbanding terbalik dengan lebar stop, jadi
stop rapat membuat komisi menelan laba kotor. Di BTC 4h komisi turun dari 5,5%
ke 2,5% laba kotor begitu stop dilebarkan.

| pair | TF | n | win% | PF asli | PF placebo | selisih exp_r |
|---|---|---|---|---|---|---|
| XAU | 15m | 3.645 | 37,94 | 0,871 | - | - |
| XAU | 30m | 5.143 | 37,08 | 0,906 | - | - |
| XAU | 1h | 3.326 | 38,12 | 1,043 | 0,943 | +0,052 |
| XAU | 4h | 3.198 | 39,81 | **1,116** | 1,019 | +0,053 |
| XAU | 1d | 1.150 | 40,78 | 1,273 | **1,302** | -0,022 |
| BTC | 15m | 3.990 | 33,36 | 0,682 | - | - |
| BTC | 30m | 5.346 | 35,39 | 0,820 | - | - |
| BTC | 1h | 3.910 | 37,08 | 0,973 | 0,822 | +0,067 |
| BTC | 4h | 2.796 | 36,27 | **1,026** | 0,997 | +0,016 |
| BTC | 1d | 834 | 35,97 | 1,056 | **1,563** | -0,181 |

Baris bawah habis dimakan biaya: komisi 27% dari laba kotor di BTC 15m, 16% di
BTC 30m. Di 1d kedua instrumen, placebo MENGALAHKAN kotak asli, jadi PF di atas
1 di sana bukan milik detektor.

## 6. Hold-out

Setiap sel yang lolos bagian 5 dibelah dua dan diukur ulang di kedua paruh.

**XAUUSD 4h**, belah di 2020-01-01:

| paruh | n | PF asli | exp_r asli | PF placebo | exp_r placebo |
|---|---|---|---|---|---|
| 2013 sampai 2019 | 1.640 | 1,037 | +0,0198 | 0,917 | -0,0386 |
| 2020 sampai 2026 | 1.557 | 1,204 | +0,1058 | 1,143 | +0,0590 |

Positif di kedua paruh, dan margin atas placebo stabil: +0,058 dan +0,047 R.

**XAUUSD 1h**, belah di 2024-11-01: paruh pertama PF 0,971 (-0,0172 R), paruh
kedua PF 1,115 (+0,0625 R). **GUGUR.**

**BTCUSD 4h**, belah di 2021-01-01: paruh pertama PF 1,222 (+0,116 R), paruh
kedua PF 0,911 (-0,0515 R), dan di paruh kedua placebo (0,921) mengunggulinya.
**GUGUR.**

## 7. Kesimpulan sebelum tuning

> [!NOTE]
> Bagian ini adalah keadaan SEBELUM bagian 8. Angka finalnya ada di bagian 8.

Satu sel bertahan dari ketiga saringan - biaya, kontrol placebo, dan hold-out
dua paruh:

**XAUUSD 4h**, gerbang 0,5 ATR, target 4R, stop 1,0 ATR, horizon 80 bar.
n = 3.198 di 13,7 tahun, PF 1,116, exp_r +0,0613 R setelah biaya, margin atas
kotak yang digeser +0,053 R.

Yang TIDAK didukung angka pada tahap ini:
- FVG di 15m dan 30m, kedua instrumen. Biaya lebih besar dari edge-nya.
- FVG di 1d, kedua instrumen. Placebo menang.
- BTCUSD di timeframe mana pun.

Baris keempat daftar ini dulu berbunyi "gerbang ceiling 0,25 tidak memisahkan".
Itu benar untuk 30m dan SALAH untuk 4h, dan bagian 8 yang menemukannya: diukur
pada margin atas placebo dan bukan pada PF mentah, 0,25 memberi +0,065 R
sementara gerbang mati memberi +0,008.

exp_r +0,0613 R itu enam kali lebih kecil dari +0,4257 R yang tercatat di
`docs/QA-FVG-RECALIBRATION.md`, dan selisihnya adalah cacat di bagian 1.

## 8. Tuning, 6 September 2026

Aturan pemilihannya ditetapkan sebelum angkanya ada: **setiap parameter dipilih
di paruh 2013-2019 XAUUSD 4h saja, dan yang dilaporkan adalah paruh 2020-2026
yang tidak pernah dilihat saat memilih.** BTCUSD tidak dipakai untuk memilih apa
pun, jadi seluruh periodenya out-of-sample.

### Kenapa hanya aturan deteksi yang layak di-tuning

Lengan placebo memakai geometri trade YANG SAMA - stop, target, horizon - dan
hanya berbeda harga kotaknya. Jadi menaikkan PF lewat geometri menaikkan
placebo bersamaan, dan itu terukur: di XAUUSD 30m dengan target 6R, kotak asli
memberi PF 1,093 dan kotak yang digeser 1 ATR memberi 1,090. Sumbu yang bisa
membawa edge detektor hanyalah aturan yang mengubah KOTAK MANA yang ada.

Geometri karena itu dikunci lebih dulu, dipilih di paruh pertama:

| stop (ATR) | PF | | target | PF |
|---|---|---|---|---|
| 0,5 | 1,032 | | 2R | 1,033 |
| **1,0** | **1,037** | | **4R** | **1,037** |
| 1,5 | 0,982 | | 6R | 1,040 |
| 2,0 | 0,986 | | | |

Target praktis datar di 4h, yang justru menenangkan: di 30m target menyetir
segalanya, dan itu tanda tangan placebo. Stop 1,0 dipilih dari dua puncak yang
selisihnya di dalam noise, karena ia memikul separuh komisi stop 0,5.

### Aturan deteksi, satu faktor per kali

Dinilai pada **margin atas placebo**, bukan pada PF mentah. Paruh 2013-2019,
XAUUSD 4h, dengan biaya:

| konfigurasi | n | exp_r asli | exp_r placebo | margin | putusan |
|---|---|---|---|---|---|
| gerbang mati | 2.425 | -0,0003 | -0,0080 | +0,008 | - |
| gerbang 0,50 | 1.640 | +0,0198 | -0,0386 | +0,058 | - |
| **gerbang 0,25** | 1.050 | +0,0419 | -0,0229 | +0,065 | dasar |
| gerbang 0,15 | 685 | +0,0155 | -0,0718 | +0,087 | ditolak, n runtuh dan margin besarnya milik placebo yang buruk, bukan lengan asli yang kuat |
| plus min_gap 0,1 | 558 | +0,0707 | +0,0191 | +0,052 | **ditolak**, placebo ikut naik |
| plus filter_mother | 1.020 | +0,0661 | -0,0140 | +0,080 | **diterima** |
| plus min_body 0,3 | 933 | +0,0954 | -0,0259 | +0,121 | **diterima** |
| plus body_gap | 101 | -0,0358 | - | - | ditolak, populasi runtuh 848 ke 100 |

`min_gap_atr` adalah contoh paling jelas kenapa margin dan bukan PF: ia
menaikkan lengan asli dari +0,042 ke +0,071 R, dan seorang yang membaca PF akan
menyimpannya. Placebonya naik dari -0,023 ke +0,019 di saat yang sama, jadi
yang ia pilih adalah rezim harga yang lebih baik, bukan zona yang lebih baik.

`body_gap` runtuh karena ia MELEBARKAN kotak, dan gerbang ceiling membaca tinggi
kotak. Lihat bagian 10.

### Konfigurasi terpilih, dan ini yang sekarang ter-ship

`min_gap_atr` 0,0 - `gate ceiling` 0,25 ATR - **`filter_mother` menyala** -
**`min_body_ratio` 0,3** - `body_gap` mati - stop 1,0 ATR - target 4R -
horizon 80 bar.

### Hasil, dengan biaya

| pair | TF | rentang | n | win% | PF | exp_r | placebo | margin |
|---|---|---|---|---|---|---|---|---|
| XAU | 15m | 0,9 th | 2.206 | 34,04 | 0,864 | -0,0881 | - | - |
| XAU | 30m | 2,7 th | 3.209 | 34,43 | 0,985 | -0,0091 | - | - |
| XAU | 1h | 3,7 th | 2.016 | 36,61 | **1,175** | +0,1000 | 0,987 | **+0,107** |
| XAU | 4h | 13,7 th | 1.852 | 37,42 | **1,252** | +0,1393 | - | - |
| XAU | 1d | 56 th | 632 | 36,39 | 1,221 | +0,1322 | **1,446** | -0,060 |
| BTC | 4h | penuh | 1.691 | 31,93 | 0,938 | -0,0387 | **1,028** | -0,053 |

**XAUUSD 4h, paruh out-of-sample 2020-2026: PF 1,348, exp_r +0,1838 R, n 919**,
lawan placebo 1,283 (+0,1337). Margin detektornya +0,050 R; sisanya periode.
Paruh in-sample 2013-2019 memberi PF 1,166 dan margin +0,121.

**XAUUSD 1h lolos hold-out** di konfigurasi ini: paruh pertama PF 1,027, paruh
kedua 1,338. Di konfigurasi sebelum tuning ia gugur (paruh pertama 0,971).

Tuning menggandakan ekspektasi XAU 4h dari +0,0613 ke +0,1393 R.

### Yang tetap tidak didukung

- **BTCUSD.** Konfigurasi ter-tuning memberi PF 0,938 lawan placebo 1,028: di
  BTC, aturan FVG yang di-tuning LEBIH BURUK daripada kotak yang digeser acak.
  Diisolasi: gerbang 0,5 ke 0,25 yang memakan 1,026 ke 0,955, dan dua filter
  deteksi menambah -0,017. Gerbang 0,25 tetap dipakai karena ia sudah produksi
  dan paruh pertama XAU setuju dengannya.
- **15m dan 30m**, kedua instrumen. Komisi mengalahkan edge.
- **1d**, kedua instrumen. Placebo menang.

## 9. Akurasi gambar

`python -m tools.drawing_accuracy`, 50.760 kotak di tujuh deret:

    worst top edge error      0.000e+00 dari tinggi zona
    worst bottom edge error   0.000e+00
    rule violations           0

Nol, worst case bukan rata-rata. Tapi angka itu baru benar setelah dua
perbaikan pada alatnya sendiri.

**Aturan order block di alat itu basi.** Ia menuntut kotak sama dengan seluruh
rentang candle, empat hari setelah `detect_order_block` memindahkannya ke BODY.
Hasilnya 19.433 violation dari 53.629 kotak, tidak satu pun nyata. Perbaikan
pertama menyisakan 2.506, semuanya lantai `MIN_OB_BOX_RANGE`: body di bawah 15
persen rentang candle ditumbuhkan simetris lalu dijepit. Aturan itu sekarang
diturunkan ulang di alatnya, bukan diimpor, supaya pemeriksanya tidak ikut
setuju dengan detektor yang salah.

**`body_gap` mendokumentasikan dirinya terbalik.** Field-nya berbunyi
"Stricter: only counts gaps between candle bodies, not wicks". Diukur di XAUUSD
4h: 2.018 kotak sebelum dan 2.018 sesudah, jadi ia **tidak menyaring apa pun**,
dan 2.017 dari 2.018 menjadi **lebih lebar** - median tinggi berlipat dua, dan
satu doji menghasilkan kotak 7.997 kali tinggi wick-nya. Body memang duduk di
dalam wick, jadi pita body merentang lebih jauh ke dua arah. Deskripsinya
diperbaiki; perilakunya tidak diubah karena tidak ada yang mengukurnya.

**Port MQL5 tidak punya kedua filter itu.** `FVGDetector.mqh` mengaku "port
faithful" tapi tidak pernah mem-port `filter_mother` maupun `min_body_ratio`.
Selama keduanya mati secara default ia cocok karena kebetulan; begitu defaultnya
menyala, EA akan menggambar lebih banyak zona daripada engine tanpa satu pun
pesan. Keduanya ditambahkan, beserta cermin Python-nya di `ea_parity_fvg.py`
yang punya lubang yang sama. `python -m tools.ea_parity_fvg --interval 4h
--bars 20000`: 2.108 lawan 2.108, 0 mismatch.


**Port MQL5 order block menggambar objek yang berbeda dari engine, dan sudah
begitu sebelum sesi ini.** Ditemukan lewat `ea_parity_ob`, yang melaporkan
1.504 dari 1.504 mismatch dan tetap merah tanpa ada yang membacanya. Dua sebab,
keduanya perubahan 6 September 2026 yang tidak ikut di-port: kotaknya rentang
penuh lilin, bukan badan yang dimekarkan ke lantai 0,15; dan impulsnya diukur ke
WICK ekstrem, bukan ke CLOSE ekstrem. Arah perbaikannya tidak perlu diperdebatkan
karena `docs/QA-OB-GATE.md` sudah mengukurnya: PF 0,984 ke 1,320. Artinya EA yang
ter-ship menjalankan geometri yang terukur LEBIH BURUK sementara engine
menjalankan yang lebih baik. Keduanya diperbaiki, beserta cermin Python-nya di
`ea_parity_ob.py` yang salah dengan cara yang persis sama - dua kesalahan yang
saling meniadakan akan membuat gate hijau atas kode yang salah. Sekarang 1.504
lawan 1.504, 0 mismatch.

**`.set` yang ter-ship memakai `InpMinGapAtr` 0,1 sementara engine memakai 0,0.**
`ea_parity_fvg` tidak menangkapnya karena ia membaca parameter dari Python, bukan
dari `.set`. Diturunkan ke 0,0.


## 10. Audit over-engineering, 6 September 2026

Enam temuan diajukan, tiga dikerjakan, tiga DITARIK setelah diukur. Yang ditarik
ditulis di sini karena audit yang menyembunyikan tebakannya yang meleset tidak
lebih baik daripada tidak diaudit.

### Dikerjakan

**`body_gap` dihapus di lima tempat.** Ia mengaku "stricter" dan tidak menyaring
apa pun: 2.018 kotak sebelum dan 2.018 sesudah di XAUUSD 4h, sementara 2.017 dari
2.018 menjadi LEBIH LEBAR - median tinggi berlipat dua, satu doji menghasilkan
kotak 7.997 kali tinggi wick-nya. Body memang duduk di dalam wick, jadi pita body
merentang lebih jauh ke dua arah, dan gerbang ceiling membaca tinggi kotak:
menyalakannya memotong populasi 848 ke 100. Ia sudah kalah dua kali sebelum ini,
di `docs/fvg_filter_compare.json` varian F - terburuk dari tujuh, exp_r 0,1399
lawan 0,4263, Welch t 0,67, dan satu-satunya yang gagal walk-forward. Dibuang
dari `imbalance.py`, `params.py`, `types.ts`, Pine, dan varian F alat sweep-nya.
Alasannya dicatat di docstring modul supaya tidak ditambahkan lagi tanpa
pengukuran baru.

**Penjaga `if top <= bottom` di dalam cabang itu tak terjangkau, dan dibuktikan
bukan diduga**: gap wick-to-wick menjamin pita body lebih lebar, diukur 16.636
gap di tiga sel, 0 yang memicunya. Ia ikut hilang.

**Lima knob yang selama ini diterima diam-diam sekarang 422.**
`displacement_atr`, `displacement_bars`, `require_structure_break`,
`structure_break_bars` dan `structure_n` hanya dibaca `detect_order_block`, tapi
`ImbalanceParams` dipakai bersama empat detektor - jadi `POST /api/draw` dengan
`layers:["fvg"]` dan `imbalance.displacement_atr: 3.0` menjawab 200, menggambar
chart default, dan tidak mengatakan apa pun. Bentuk yang persis sama dengan
insiden `source` yang membuat `DrawRequest` menolak field tak dikenal; bedanya
field-field ini DIKENAL, cuma tidak dibaca, jadi `extra="forbid"` melewatkannya.
Hanya knob yang digeser dari default yang ditolak, supaya klien yang menyebar
seluruh blok dari `/api/config` tetap jalan. Konstantanya dijaga
`tests/test_shared_param_block.py`, yang menurunkan himpunan yang sama dari AST
dan menyamakannya - plus test kedua yang menolak knob tanpa pembaca sama sekali.

**Blok Displacement di panel tidak lagi tampil untuk FVG.** Empat barisnya hanya
bisa satu nilai di sana: `Size` adalah angka yang sama persis dengan `Departure`
di atasnya (komentar `imbalance.py` menyatakannya sengaja), `Left a gap` selalu
"yes" karena celahnya ADALAH definisi kotaknya, `Broke structure` selalu "not
tested", dan legnya tiga bar yang sama dengan kelahiran kotak. Untuk order block
keempatnya membawa isi, jadi bloknya tetap ada di sana.

### Ditarik

**Menghapus `min_gap_atr`.** Ia disapu oleh sepuluh alat termasuk `fvg_sweep`,
`walkforward` dan `detectors`. Menghapusnya menghapus rekaman yang membuktikan ia
ditolak, yang lebih buruk daripada menyimpan knob yang default-nya inert.

**Menghapus `settled` untuk kind imbalance.** Diukur: ia berbeda dari `confirmed`
pada 1 dari 1.121 zona supply_demand dan 0 dari 1.813 zona fvg. Jadi ia redundan
PER KIND, bukan secara global, dan komentarnya sudah menyatakan itu.

**"Port MQL5 menggambar 1.813 kotak di tempat engine menggambar 12."** Salah. EA
itu tidak menggambar sama sekali (`ObjectCreate` nol) dan sudah menyaring
`state != SD_STATE_FRESH`, sama dengan jalur order. Yang saya lihat adalah
populasi detektor, bukan yang tergambar.

### Blind spot yang ditutup dengan pengukuran

Tiga knob tidak pernah diukur untuk fvg. Ketiganya sekarang sudah, dan jawabannya
sama: tidak menggigit.

| knob | cara diukur | hasil |
|---|---|---|
| `atr_period` | margin atas placebo, XAU 4h paruh pertama | +0,1223 / +0,1213 / +0,1135 di periode 7 / 14 / 28. Rentang 4x menggeser 0,009 R |
| `mitigation_pct` | himpunan zona tergambar, XAU 4h | IDENTIK di 0,1 sampai 0,9 - 139 kotak, id yang sama, `fresh` diam di 45. Hanya label TESTED lawan MITIGATED yang bergerak, dan keduanya tergambar |
| `arrival_bars` | pembacaan kode | hanya masuk ke `arrival_atr`, yang dicatat tanpa skor dan tidak menyentuh `state` |

### Yang tersisa dan tidak disentuh

20 dari 39 field `Zone` konstan di seluruh 1.813 kotak fvg - `base_drift`,
`consolidation_quality`, `curve`, `nested_in`, `refinement` dan lima belas
lainnya. Itu harga memakai ulang `Zone` milik supply/demand, dibayar di setiap
respons API. Membelahnya adalah perubahan kontrak, bukan pembersihan.

Satu konstanta gerbang untuk dua detektor: `CEILING_KINDS = (FVG, IFVG)` berbagi
`DEPARTURE_GATE_ATR_CEILING`. Tidak ada jalan menyatakan nilai berbeda per
detektor apalagi per instrumen, padahal BTC terukur lebih baik di 0,5 daripada
0,25.


### Koreksi terpenting: hasil tuning tidak bertahan di bracket produksi

Bagian 8 diukur di harness TradingView dengan stop 1,0 ATR dan target 4R tetap.
`execute.py` memakai bracket yang BERBEDA: stop 0,25 ATR dan target dari zona
lawan. `tools/fvg_filter_compare` diarahkan ke 1h dan 4h dan dijalankan di
bracket produksi, XAUUSD dan BTCUSD digabung:

| varian | n | exp_r | PF | wf |
|---|---|---|---|---|
| A baseline | 2.472 | -0,0271 | 0,954 | 2/8 |
| B mother | 2.426 | -0,0293 | 0,950 | 2/8 |
| C mother + min_gap 0,05 | 1.789 | -0,0027 | 0,995 | 2/8 |
| D mother + min_gap 0,1 | 1.246 | -0,0024 | 0,996 | 2/8 |
| E mother + body 0,3 (ter-ship) | 2.221 | -0,0181 | 0,969 | 2/8 |
| G E + min_gap 0,05 | 1.669 | +0,0183 | 1,032 | 3/8 |

Tidak satu pun lolos aturan 8 dari 8 yang jadi gerbang proyek ini, dan lima dari
enam negatif. Di 30m pasca-perbaikan gambarannya sama: baseline +0,0049 PF 1,008
wf 4/8, terbaik C di +0,0236 PF 1,039 wf 4/8.

Sudah diukur juga bahwa lebar stop SENDIRIAN memindahkan 4h melewati 1,0 (0,959
di 0,25 lawan 1,116 di 1,0). Jadi PF 1,252 di bagian 8 adalah geometri bracket
sebanyak ia milik detektor - persis bacaan yang `detect/__init__.py` sebut
mendiskualifikasi sebuah temuan.

**`orderable` DIMATIKAN, 7 September 2026.** Sebelum sesi ini `fvg` bisa diorder
di 30m atas angka +0,2188 R walk-forward 8 dari 8; angka itu dihasilkan lifecycle
yang salah urutan dan sekarang +0,0919 R dengan t=+1,88. Tidak ada interval, tidak
ada bracket, dan tidak ada varian filter yang lolos aturan 8 dari 8. Yang dicabut
adalah klaimnya, bukan detektornya: ia tetap digambar, tetap punya gerbang, tetap
punya angka. `measured_intervals` dipertahankan sebagai catatan asal angkanya,
bentuk yang sama dengan `ifvg`; yang menolak sekarang `ORDERABLE_LAYERS`, satu
langkah lebih awal. Daemon tidak terpengaruh - ia jalan dengan `layer` default
`supply_demand` dan tanpa flag `--layer`, jadi ia tidak pernah meng-order fvg.

**Dan mematikannya menemukan cacat laten.** `GATE_DIRECTION` diturunkan dari
`layer.orderable`, sementara `grounds()` dan `cleared_gate` membacanya dengan
fallback `"floor"`. Jadi layer ber-plafon yang dimatikan menghilang dari peta itu
dan kalimatnya berbalik: zona yang lolos karena berada DI BAWAH plafon dilaporkan
"clears" gerbangnya - persis cacat yang dibawa enam order hidup pada 3 September
2026. `ifvg` sudah `orderable=False` dengan `gate="ceiling"` sebelum hari ini,
jadi lubang itu SUDAH menganga untuknya dan tidak ada satu test pun yang
mengujinya. Petanya sekarang diturunkan dari `layer.gate`: satu peta menjawab
"bagaimana membaca gerbang zona ini", `ORDERABLE_LAYERS` menjawab "bolehkah
diorder". Dijaga `tests/test_cisd_in_band_filter.py`.

**Konsekuensinya untuk dua default filter.** `filter_mother` dan
`min_body_ratio` diubah di bagian 8 atas bukti bracket TV. Di bracket produksi
keduanya bergantung bracket dan berada di dalam noise: lebih baik dari baseline
di 1h+4h (-0,0181 lawan -0,0271), lebih buruk di 30m (-0,0063 lawan +0,0049).
Keduanya TETAP MENYALA, tapi alasannya diganti: bukan edge, melainkan definisi -
inside bar dan doji memang bukan displacement - dan pengukuran di atas
menyatakan biayanya nol. `params.py` mencatat itu di tempatnya.

**`body_gap` justru makin kuat untuk dihapus.** Di 30m pasca-perbaikan ia tetap
yang terburuk dari tujuh: exp_r -0,0969, PF 0,822. Tiga kali diukur, tiga kali
kalah.


## 11. Seberapa akurat backtest-nya, 7 September 2026

Empat pertanyaan yang menentukan apakah angka di dokumen ini boleh dipercaya.
Semuanya diukur pada bracket ter-ship (gate 0,25 - filter_mother - min_body 0,3 -
stop 1,0 ATR - target 4R - horizon 80 - biaya 0,0113% per sisi).

### 1. Apakah dua rig setuju kalau diberi bracket yang sama

Ini yang paling penting dan yang paling lama tidak ditanyakan. Sepanjang dokumen
ini selisih antara harness TradingView dan rig Python disebut "bracket", tapi itu
dugaan sampai keduanya dijalankan pada bracket yang identik. Rig Python dijalankan
di konfigurasi Pine persis, di data MT5:

| | XAUUSD 4h | XAUUSD 1h |
|---|---|---|
| Python di data MT5 | PF **1,251** | PF **1,249** |
| TradingView | PF **1,252** | PF 1,175 |

Dua implementasi berbeda, dua feed berbeda, konvergen di 4h sampai digit ketiga.
Jadi selisih terhadap bracket produksi memang milik bracket, bukan milik rig yang
rusak. `n` berbeda (543 lawan 1.852) karena riwayat 4h MT5 mulai 2020-12
sementara TradingView memberi 2013, dan riwayat 15m yang jadi bar halus memotong
lebih jauh lagi - PF yang sama pada sampel yang berbeda justru menguatkan.

### 2. Apakah jawabannya bergerak kalau resolusinya diperhalus

Rentang disamakan ke irisan semua resolusi (2025-04-08 ke depan, n=174):

| bar halus | PF | exp_r |
|---|---|---|
| 1h | 1,503 | +0,3658 |
| 30m | 1,503 | +0,3658 |
| 15m | 1,460 | +0,3371 |
| 5m | 1,460 | +0,3371 |

Rentang dua belas kali lipat menggeser PF 2,9 persen. Mekanismenya jelas: stop
1,0 ATR dengan target 4R membuat sedikit bar memuat stop DAN target sekaligus,
jadi asumsi urutan intrabar hampir tidak punya tempat untuk menggigit. Bandingkan
bracket lama yang stopnya 0,25 ATR, tempat magnifier sendirian memindahkan PF
0,9396 ke 0,9568.

### 3. Apakah ada trade yang dibayar di bar entry-nya sendiri

`resolve()` menolak membayar target di bar entry dan menyebut asimetrinya sebagai
tanda tangan urutan intrabar yang diasumsikan ke arah yang menguntungkan.
Diukur di bracket ini: **0 menang dan 8 kalah** selesai di bar entry, 1,5 persen
dari 543 trade, dan membuang bar entry sama sekali tidak menggerakkan hasilnya -
PF 1,251 di kedua arah. Tidak ada asimetri untuk dikoreksi.

Juga diperiksa: **0 dari 543** limit gagal terisi di bar halus setelah proximal
tersentuh di bar kasar, jadi tidak ada trade yang hilang diam-diam di situ.

### 4. Seberapa rapuh terhadap selisih feed

Ini mata rantai terlemahnya. Ambang stop digeser `d` dolar, setara feed yang
wick-nya mencetak `d` lebih dalam. Risk median 13,86 USD:

| d (USD) | PF | exp_r | win% |
|---|---|---|---|
| 0,0 | 1,251 | +0,1947 | 25,23 |
| 0,2 | 1,201 | +0,1579 | 24,49 |
| 0,5 | 1,094 | +0,0750 | 22,84 |
| 1,0 | 1,070 | +0,0566 | 22,47 |
| 2,0 | 0,935 | -0,0539 | 20,26 |

Parity check mencatat selisih terukur MT5 lawan TradingView: median 0,18 dan
maksimum 1,20. Jadi jawaban yang jujur untuk "berapa PF-nya di broker Anda"
adalah **antara 1,07 dan 1,20**, bukan 1,25. Titik impasnya di sekitar
d = 1,7 USD. Bracket lama lebih rapuh lagi: dengan risk median 4,01 USD, d=0,2
memindahkan PF 1,943 ke 1,800.

### Ringkasan

Backtest-nya akurat dalam tiga dari empat sumbu: dua rig independen setuju,
resolusinya stabil, dan tidak ada asimetri bar-entry maupun trade yang hilang.
Yang TIDAK akurat adalah angka desimalnya lintas broker - satu selisih wick 0,2
dolar memakan seperlima edge-nya. Kutip 1,07 sampai 1,20, jangan 1,252.


### FVG murni, tanpa ATR sama sekali

Ditanyakan 7 September 2026: apa yang terjadi kalau ATR dicabut. Semua diturunkan
dari kotak itu sendiri - entry di proximal, stop di distal tanpa buffer, target R
kali tinggi kotak. Tidak ada gerbang, karena `departure_atr` ADALAH tinggi gap
dibagi ATR. XAUUSD, resolusi bar halus, biaya 0,0113% per sisi.

| R | win% | break-even teoretis | PF tanpa biaya | PF dengan biaya |
|---|---|---|---|---|
| 1 | 49,83 | 50,0 | 0,993 | 0,311 |
| 2 | 33,56 | 33,3 | 1,005 | 0,401 |
| 3 | 25,74 | 25,0 | 1,024 | 0,445 |
| 4 | 21,25 | 20,0 | 1,045 | 0,474 |

n=1.445 di 4h, dan pola yang sama di 1h (n=1.661) serta di kedua lengan filter.

**Win rate-nya menempel pada break-even teoretis di setiap R.** Itu bukan
"edge-nya kecil", itu bentuk sebuah lemparan koin: harga sama mungkinnya
menempuh R tinggi kotak ke arah proximal seperti satu tinggi kotak ke arah
distal, persis seperti jalan acak. Empat nilai R, dua timeframe, dua lengan
filter, semuanya sama. **Pola FVG sendiri, di geometrinya sendiri, tidak
membawa arah.**

**Dan tanpa ATR tidak ada lantai untuk risiko.** Tinggi kotak: minimum 0,0020
USD, p1 0,067, p10 0,613, median 4,136. Karena risk per unit ADALAH tinggi
kotak, biaya relatifnya meledak di ekor:

| biaya/risk | share trade |
|---|---|
| > 0,25 R | 31,8% |
| > 0,50 R | 16,9% |
| > 1,00 R | 8,9% |
| > 2,00 R | 4,8% |

Median 0,139 R, mean 0,881 R, maksimum 381 R. Sembilan persen trade membayar
komisi LEBIH BESAR dari seluruh risikonya sendiri. Itu yang membuat exp_r jatuh
ke -0,88 R meski medianya cuma -0,14.

**Jadi tugas ATR di detektor ini bukan sinyal dan bukan hiasan.** Buffer stop
memberi LANTAI pada risiko sehingga rasio biaya terbatas; gerbang ceiling memberi
PLAFON pada tinggi kotak sehingga targetnya masih terjangkau. Keduanya
mengubah kotak yang tak berdimensi menjadi trade yang bisa diukur. Yang mereka
tidak lakukan adalah menciptakan arah - itu tetap lemparan koin, dan konsekuensinya
langsung: PF 1,252 di bagian 8 berasal dari bracket-nya, bukan dari gap-nya.

Lantai yang sama bisa diberikan rentang lilin alih-alih ATR, seperti yang sudah
dilakukan `MIN_OB_BOX_RANGE`, dan itu akan sekaligus menghapus ketergantungan
jendela di atas. Ambang 0,25 dan 1,0 dikalibrasi dalam satuan ATR jadi keduanya
harus diukur ulang; itu perubahan terukur, bukan penggantian nama.


### Skala gerbang ditukar dari Wilder ke rata-rata TR, 7 September 2026

Dipesan sebagai "ganti ATR ke rentang lilin". Diukur, rentang lilin ternyata
pilihan terburuk dari tiga kandidat, dan yang menang adalah perubahan yang jauh
lebih kecil.

**Masalahnya bukan ATR, melainkan Wilder.** `wilder_atr` adalah RMA yang disemai
dari bar pertama, jadi nilainya di satu bar absolut bergantung berapa bar yang
dimuat pemanggil. Rata-rata biasa atas tepat 14 true range terakhir dihitung dari
14 bar dan sama di jendela mana pun.

Empat skala diuji, semua dengan ambang yang dicocokkan KUANTIL (supaya
populasinya sebanding) dan pengali buffer stop yang dicocokkan MEDIAN (supaya
risikonya sebanding). XAUUSD 4h, acuan 99.999 bar:

| skala | rasio berubah lawan acuan | paruh-1 | paruh-2 | berpasangan lawan Wilder |
|---|---|---|---|---|
| Wilder RMA (lama) | **46/96, 56/243, 45/630** | PF 1,050 | PF 1,616 | acuan |
| rata-rata TR 14 | 0 dari semuanya | PF 0,988 | PF 1,537 | -0,0534 R, t=-1,46 |
| Donchian 14 bar | 0 dari semuanya | PF 1,003 | PF 1,476 | -0,0472 R, t=-0,74 |
| rentang lilin tengah | 0 dari semuanya | PF 0,954 | PF 1,303 | -0,1357 R, t=-1,75 |

Tidak satu pun signifikan, jadi menukar skala tidak berbiaya terukur. Yang
dipilih rata-rata TR, dengan tiga alasan:

1. **Besaran dan satuannya sama**, jadi ambangnya tidak perlu bergerak. Ambang
   setara dihitung terpisah di delapan sel (XAU dan BTC kali 30m, 1h, 4h, 1d) dan
   keluar **0,2434 sampai 0,2573** - semuanya di dalam pembulatan 0,25 yang
   ter-ship. Rentang lilin butuh 0,1945 sampai 0,2275, yaitu kalibrasi ulang
   sungguhan.
2. **Penaltinya paling kecil bersama Donchian**, dan rentang lilin yang paling
   besar sekaligus paling dekat signifikan.
3. **Diff-nya satu fungsi.**

Diverifikasi di detektor yang ter-ship, bukan di skrip coretan: pada jendela 500,
1.200, 3.000 dan 8.000 bar, `departure_atr` yang berbeda dari acuan hanya 1, 3, 4
dan 5 zona, dan **indeks bar mereka semuanya 0 sampai 13** - di dalam warmup,
tempat rata-rata 14 bar memang belum bisa dihitung. Tidak satu pun di luar itu.
Geometri kotak tetap 0 beda, seperti sebelumnya. Dijaga
`backend/tests/test_scale_is_window_free.py`.

Diukur ulang di TradingView setelah penukaran, XAUUSD 4h dengan biaya:
**PF 1,266** dan exp_r +0,1472 pada n=1.835, dari 1,252 dan +0,1393. Naik tipis
di sini dan turun tipis di MT5 - tanda berlawanan dengan besaran yang sama, yang
memang bentuk "tidak ada selisih".

**Yang TIDAK ditukar**: `detect_order_block` masih Wilder, karena ambang impulsnya
dikalibrasi terhadap Wilder dan menukarnya butuh pengukurannya sendiri. Begitu
juga ATR yang dipakai `plan.build` untuk menaruh stop, yang dipakai bersama
supply_demand dan order_block yang masih orderable. Drift stop 8,57 USD di ekor
yang tercatat di bagian 11 karena itu BELUM tertutup untuk kedua layer itu.


## 12. Gerbang produk: win rate, replay, dan gambar yang mengikutinya

Ditetapkan 7 September 2026 sebagai syarat kelayakan fitur: detektor FVG boleh
menggambar di Zonelab hanya kalau backtest TradingView-nya punya win rate yang
baik dan bukan rugi, dan gambarnya harus mengikuti hasil backtest itu.

### Frontier win rate, dan kenapa ia trade-off bukan pilihan bebas

Win rate dan reward-to-risk terikat secara mekanis. Target 4R impas di win rate
20 persen, target 1R impas di 50. Menaikkan satu selalu menurunkan yang lain, dan
yang bisa dinilai adalah JARAK ke impas. XAUUSD 4h, 13,7 tahun, dengan biaya,
konfigurasi ter-ship:

| target | win% | impas teoretis | margin | PF |
|---|---|---|---|---|
| **1,0R** | **54,56** | 50,0 | +4,6 | 1,127 |
| 1,5R | 47,54 | 40,0 | +7,5 | 1,177 |
| 2,0R | 42,84 | 33,3 | +9,5 | 1,183 |
| 4,0R | 38,53 | 20,0 | +18,5 | 1,266 |

Keempatnya profit. **1R yang ter-ship**, karena kriteria yang dipesan adalah win
rate dan ia satu-satunya yang di atas 50 persen. 4R punya ekspektasi tertinggi
dan cukup ganti satu input kalau itu yang dicari; keduanya ditulis di header Pine
supaya pilihan itu tidak tersembunyi.

### 1R lolos ketiga saringan

| | n | win% | PF |
|---|---|---|---|
| XAU 4h penuh, 13,7 th | 1.712 | **54,56** | 1,127 |
| paruh 2013-2019 | 867 | 53,63 | 1,090 |
| paruh 2020-2026 | 845 | 55,50 | 1,167 |
| kontrol kotak-digeser | 1.681 | 41,94 | 0,963 |

Kedua paruh di atas 50 persen dan PF di atas 1. Dan **selisih ke placebo 12,6
poin win rate** - jauh lebih tajam daripada di 4R. Itu yang paling penting dari
seluruh tabel ini: selisih sebesar itu milik LETAK kotaknya, bukan bracketnya,
karena placebo memakai bracket yang sama persis dan hanya harganya yang digeser.

BTCUSD 4h di konfigurasi yang sama: win 51,20 persen lawan placebo 40,01 - jadi
letak kotaknya bekerja di sana juga, selisih 11,2 poin. Tapi PF-nya 0,985, tepat
di garis impas. **Detektornya jalan di BTC, biayanya yang memakan habis.** BTC
karena itu tidak dinyatakan lolos.

### Replay

Diverifikasi lewat Bar Replay TradingView, bukan cuma Strategy Tester. Riwayat
dipotong di 2024-06-03: n=1.604, win 53,43 persen, PF 1,088 - konsisten dengan
riwayat penuh, dan selisihnya persis trade setelah tanggal itu. Lalu dimajukan
tiga bar: **angkanya identik sampai digit terakhir**, hanya `buy_hold_return`
yang bergerak. Strategi ini tidak me-repaint riwayatnya saat bar baru datang,
yang berarti tidak ada lookahead di jalurnya.

### Gambar yang mengikuti backtest

Sampai hari ini kotak yang lolos gerbang dan yang tidak **tergambar identik** di
chart, dan verdictnya hanya muncul kalau pembaca mengklik zonanya. Itu
menyembunyikan satu-satunya hal yang backtest buktikan: yang diukur bukan
"sebuah FVG ada di sini", melainkan kohort yang lolos gerbangnya.

`zone-primitive.ts` sekarang menambahkan satu titik di caption - `●` lolos, `○`
tidak - memakai kosakata yang sama dengan panel. Satu titik dan bukan gaya garis
baru, karena garis putus-putus sudah berarti "kotaknya bisa bergeser" dan satu
kosakata visual tidak bisa membawa dua klaim. Ia DIAM di kind yang ambangnya
tidak pernah diukur, hari ini cuma BRK, karena `gate_cleared` selalu menjawab
sementara `gate_measured` yang membawa perbedaan antara "tidak lolos" dan "tidak
pernah ada yang mengukur".

Kotak yang tidak lolos tetap digambar, tidak disembunyikan. Menyembunyikannya
akan membuang informasi yang sama nilainya - dua kotak di satu harga adalah dua
klaim, dan itu argumen yang sama yang menahan merge overlap keluar dari
`_present`.

**KOTAK TIPIS SEMPAT BISU, dan itu ketahuan hanya karena screenshot-nya
dilihat.** Perubahan pertama lolos type-check dan lolos harness piksel, tapi
`LABEL_MIN_HEIGHT = 15` membuang SELURUH caption di kotak di bawah 15 piksel -
dan gerbang fvg adalah PLAFON pada tinggi gap, jadi kohort yang lolos SELALU
kotak kecil. Penandanya karena itu tak terlihat tepat di tempat ia paling
berarti. Terlihat di screenshot audit 4h: delapan zona, dua lolos gerbang, dan
tidak satu pun dari yang dua itu memajang penandanya. Sekarang kotak tipis
memajang titiknya saja; yang dibuang di ruang sempit adalah NAMA formasinya,
karena nama itu sama untuk setiap kotak di layer yang sama sementara verdictnya
tidak. Diverifikasi dengan melihat screenshot-nya lagi.

`e2e/chart-audit.mjs` ikut diperbarui: cerminnya sudah dua kali tertinggal dari
yang digambar (ia juga tidak pernah memuat " flipped"), dan cermin yang
tertinggal melaporkan chart yang BENAR sebagai salah.


## 13. Bracket produksi diukur ulang, 7 September 2026

Dipesan supaya `orderable` bisa dinyalakan. Jawabannya tidak, dan sapuannya
menemukan sesuatu yang lebih besar dari fvg.

### Lebar stop tidak pernah bisa disapu

`intrabar.resolved` punya parameter untuk `flat`, `entry_depth`, `breakeven_at`
dan `scale_at`, tapi TIDAK untuk lebar stop - ia selalu memakai
`DEFAULT_STOP_BUFFER_ATR`. Jadi satu-satunya sumbu geometri yang tidak pernah
diukur di bracket produksi adalah yang di harness TradingView terbukti paling
menggerakkan hasil. Parameternya ditambahkan, default-nya konstanta yang sama,
jadi setiap angka yang sudah tercatat tidak bergerak satu digit pun.

### 0,25 adalah nilai TERBURUK dari lima yang diuji

XAUUSD, bracket produksi apa adanya (entry proximal, target zona lawan, biaya
`app/costs.py`, potong harian 21:00 UTC, horizon 80 bar, resolusi bar halus),
gerbang ceiling 0,25:

| buffer | 4h PF | 4h win% | 1h PF | 1h win% |
|---|---|---|---|---|
| **0,25 (ter-ship)** | **0,792** | 34,17 | **0,961** | 32,86 |
| 0,50 | 0,920 | 44,04 | 1,147 | 44,65 |
| 1,00 | 1,017 | 53,21 | 1,149 | 55,97 |
| 1,50 | 1,149 | 56,65 | 1,131 | 61,48 |
| 2,00 | 1,097 | 57,11 | 1,108 | 63,99 |

Di 4h, 0,25 adalah satu-satunya nilai yang negatif di KEDUA paruh (PF 0,715 lalu
0,875). Melebarkannya ke 1,5 memindahkan win rate dari 34,17 ke 56,65 persen.

### Tapi walk-forward tetap tidak lolos

Aturan pra-registrasi proyek ini 8 dari 8. Delapan potong dengan purging fold,
sama seperti `fvg_sweep.walk_forward`:

| sel | buffer | n | exp_r | t | PF | win% | walk-forward |
|---|---|---|---|---|---|---|---|
| XAU 1h | 1,00 | 636 | +0,0529 | +1,40 | 1,149 | 56,0 | 6 dari 8 |
| XAU 1h | **1,50** | 636 | +0,0366 | +1,22 | 1,131 | 61,5 | **7 dari 8** |
| XAU 1h | 2,00 | 636 | +0,0252 | +1,00 | 1,108 | 64,0 | 6 dari 8 |
| XAU 4h | 1,00 | 436 | +0,0048 | +0,14 | 1,017 | 53,2 | 5 dari 8 |
| XAU 4h | 1,50 | 436 | +0,0277 | +1,06 | 1,149 | 56,7 | 5 dari 8 |
| XAU 4h | 2,00 | 436 | +0,0148 | +0,69 | 1,097 | 57,1 | 4 dari 8 |

Tidak satu pun 8 dari 8, dan t tertinggi +1,22. **`orderable` tetap mati.**
Terbaik yang pernah dicapai fvg pasca-perbaikan adalah 7 dari 8 di 1 jam dengan
buffer 1,5, dan itu belum cukup.

Perlu dicatat untuk perbandingan: `detect/__init__.py` mencantumkan
supply_demand di 6 dari 8 dan ia ORDERABLE hari ini. Tapi angka itu, dan ketiga
angka lain di daftar itu, semuanya diukur lewat lifecycle yang salah urutan.
Tidak satu pun sudah diukur ulang. Jadi 7 dari 8 milik fvg bukan "hampir sebaik
supply_demand" - ia satu-satunya angka walk-forward pasca-perbaikan yang ada di
repo ini.


### Sapuan yang sama pada dua layer yang MASIH hidup

`DEFAULT_STOP_BUFFER_ATR` satu konstanta untuk semua detektor, jadi begitu ia
terbukti salah untuk fvg, pertanyaannya tidak opsional: apa yang ia lakukan pada
`supply_demand` dan `order_block`, yang daemon perdagangkan dengan uang. Bracket
produksi yang sama, tiga sel, gerbang masing-masing:

**supply_demand**, gerbang 2,0:

| sel | buffer 0,25 | buffer 1,00 |
|---|---|---|
| XAU 1h | PF 1,354, +0,1159 R, t=+1,65 | PF 1,280, +0,0681 R |
| XAU 4h | PF 0,861, -0,0437 R | PF 0,957, -0,0085 R |
| BTC 1h | PF 0,800, -0,0893 R | PF 0,808, -0,0660 R |

**order_block**, gerbang 2,5:

| sel | buffer 0,25 | buffer 1,00 |
|---|---|---|
| XAU 1h | PF 0,788, -0,1412 R, t=-1,74 | PF 0,865, -0,0605 R |
| XAU 4h | **PF 0,495, -0,2897 R, t=-5,07** | PF 0,551, -0,1617 R, t=-4,20 |
| BTC 1h | PF 1,016, +0,0099 R | PF 0,979, -0,0097 R |

### Yang sebenarnya ditemukan sapuan ini

Pertanyaannya "bisakah fvg dinyalakan". Jawabannya tidak. Tapi jawaban itu datang
bersama tiga angka yang lebih penting:

1. **`order_block` signifikan NEGATIF di XAUUSD 4h, t = -5,07.** Itu satu-satunya
   |t| di atas 2 di seluruh tabel ini, dan arahnya salah. Ia negatif di dua dari
   tiga sel di kedua lebar stop. Layer ini ORDERABLE dan hidup. Evidence-nya di
   `layers.py` mengklaim PF 1,330 dengan walk-forward 8 dari 8, dan angka itu
   diukur lewat lifecycle yang salah urutan.
2. **`supply_demand` positif di satu dari tiga sel.** +0,1159 R di XAU 1h, negatif
   di XAU 4h dan BTC 1h. Ia juga orderable dan hidup, dan ia yang daemon pakai
   sebagai layer default.
3. **`fvg` positif di dua dari dua sel yang diuji** (+0,0366 dan +0,0277 R,
   walk-forward 7 dari 8 dan 5 dari 8) - tapi tetap di bawah aturan 8 dari 8.

Jadi urutan pasca-perbaikan, di bracket yang benar-benar dijalankan executor,
terbalik dari yang tercantum di `detect/__init__.py`: fvg positif di mana-mana
tapi lemah, supply_demand campur, order_block negatif dan satu-satunya yang
signifikan.

### `order_block` dimatikan, 7 September 2026

Ia bukan "belum terbukti" seperti fvg, ia terukur RUGI: PF 0,495 dan exp_r
-0,2897 R pada t = -5,07 di XAUUSD 4h, satu-satunya |t| di atas 2 di seluruh
sapuan tiga layer kali tiga sel, dengan arah yang salah. Melebarkan stop
mengurangi kerugiannya, tidak membalikkannya.

`ORDERABLE_LAYERS` sekarang `('supply_demand',)` - satu layer, dan satu itu pun
cuma positif di satu dari tiga sel. Baris `evidence` order_block TIDAK dicabut:
ia benar untuk apa yang diukurnya, yaitu populasi lifecycle yang salah urutan,
dan membiarkannya berdampingan dengan angka baru adalah rekamannya.

Daemon tidak terpengaruh: ia jalan dengan layer default `supply_demand` dan tanpa
flag `--layer`.

### Konstantanya TIDAK diubah, dan alasannya

Buffer 1,0 lebih baik atau setara di lima dari enam kombinasi layer-sel. Satu
yang tidak: supply_demand di XAU 1h, satu-satunya sel tempat satu-satunya layer
yang hidup dan positif benar-benar positif. Mengubah konstanta global akan
menukar sel itu demi sel-sel yang sudah negatif dengan atau tanpa perubahan.
Lebar stop per layer bisa dibuat, tapi hari ini tidak ada konsumen produksi yang
akan memakainya: fvg tidak orderable, dan gambar tidak membaca lebar stop sama
sekali. Diukur, dicatat, tidak dibangun.


## 14. BTCUSD, perlakuan penuh yang sama, 7 September 2026

Sampai bagian ini BTC hanya diukur tersebar dan sebagian dari sebelum skala
ditukar. Di sini ia mendapat yang sama dengan XAU: frontier reward, seluruh
timeframe, kontrol placebo, dan hold-out - semua di konfigurasi ter-ship
(gerbang 0,25 - filter_mother - min_body 0,3 - skala rata-rata TR - stop 1,0 ATR)
dengan biaya 0,01329% per sisi dari profil broker.

### Frontier reward, BTCUSD 4h

| target | win% | PF |
|---|---|---|
| 1,0R | 51,20 | 0,985 |
| 1,5R | 43,18 | 0,984 |
| 2,0R | 38,61 | 0,979 |
| 4,0R | 31,93 | 0,938 |

DATAR dan seluruhnya di bawah satu, dan itu perbedaan pertama dari XAU, tempat
PF naik bersama reward dari 1,127 ke 1,266. Di BTC tidak ada reward yang
menolong.

### Seluruh timeframe, target 1R

| TF | n | win% | PF | komisi / laba kotor |
|---|---|---|---|---|
| 15m | 2.130 | 46,67 | 0,656 | 32% |
| 30m | 3.029 | 48,13 | 0,806 | 20% |
| 1h | 2.188 | 49,18 | 0,882 | 11% |
| **4h** | 1.537 | **51,20** | **0,985** | **3,6%** |
| 1d | 447 | 45,41 | 0,948 | 1,2% |

Perhatikan kolom terakhir. Win rate BTC BAIK-BAIK SAJA di mana-mana, 45 sampai
51 persen. Yang berjalan seiring PF bukan win rate melainkan share komisi, dan
PF terbaik jatuh persis di timeframe tempat komisi terkecil yang masih punya
sampel. Ini bukan detektor yang gagal di BTC, ini biaya yang memakannya.

### Kontrol placebo mengonfirmasi itu

BTCUSD 4h, 1R:

| | n | win% | PF |
|---|---|---|---|
| kotak asli | 1.537 | **51,20** | 0,985 |
| kotak digeser 1 ATR | 1.537 | **40,01** | 0,976 |

**Selisih 11,2 poin win rate**, sebesar XAU yang 12,6. Letak kotaknya bekerja di
BTC persis seperti di XAU. Tapi selisih PF-nya cuma +0,009: seluruh keunggulan
lokasi itu diserap biaya sebelum sampai ke garis bawah.

### Hold-out

Belah di 2021-01-01: paruh pertama n=579 PF **1,081** (win 53,37), paruh kedua
n=958 PF **0,931** (win 49,90). GUGUR, dan polanya sama dengan yang terukur di
4R sebelumnya (1,222 lalu 0,911). Edge BTC hidup di paruh sebelum 2021 saja.

### Bracket produksi membalik sebagian cerita di atas

Semua angka di atas dari harness TradingView. Bracket produksi - target dari zona
lawan, bukan 1R tetap - memberi jawaban lain, dan BTC 1 jam justru sel TERKUAT
yang pernah diukur sesi ini:

| sel | buffer | n | exp_r | t | PF | win% | walk-forward |
|---|---|---|---|---|---|---|---|
| BTC 1h | 0,25 | 696 | +0,0554 | +0,85 | 1,094 | 37,4 | 6 dari 8 |
| BTC 1h | **1,00** | 696 | +0,0716 | **+1,96** | 1,210 | 57,9 | **7 dari 8** |
| BTC 1h | 1,50 | 696 | +0,0591 | **+2,05** | 1,223 | 63,5 | 6 dari 8 |
| BTC 4h | 0,25 | 424 | -0,0343 | -0,49 | 0,938 | 36,6 | 2 dari 8 |
| BTC 4h | 1,50 | 424 | +0,0073 | +0,27 | 1,038 | 55,7 | 4 dari 8 |

Bandingkan XAU yang terbaiknya t=+1,40 dan 7 dari 8. BTC 1 jam melewati keduanya.

**Selisih dua rig itu diisolasi, tidak ditebak.** Untuk XAU keduanya setuju sampai
digit ketiga (PF 1,251 lawan 1,252); untuk BTC tidak, jadi bracket TradingView
dijalankan di data MT5 untuk memisahkan feed dari bracket:

| | BTC 1h | BTC 4h |
|---|---|---|
| bracket TV, feed BITSTAMP | 0,882 | 0,985 |
| bracket TV, feed MT5 | 0,989 | 1,080 |
| bracket produksi, feed MT5 | 1,210 | 0,964 |

Feed menyumbang sekitar 0,107 di 1 jam; **target zona lawan menyumbang 0,221**.
Untuk XAUUSD pilihan target hampir netral (+0,4785 target 2R tetap lawan +0,4973
target zona lawan). Di BTC ia yang menentukan, dan itu asimetri yang belum
dijelaskan.

### Putusan BTC

Tidak lolos, tapi alasannya berbeda tergantung gerbang mana yang ditanya.

**Gerbang GAMBAR** yang dipesan - backtest TradingView dengan win rate baik dan
bukan rugi - TIDAK dilewati: PF terbaik 0,985 di 4 jam, dan hold-out-nya gugur
(1,081 lalu 0,931). Detektornya menyortir di sana (11,2 poin win rate atas
placebo, sebesar XAU), tapi biaya menyerap seluruhnya dan sisanya tidak bertahan
di paruh kedua.

**Gerbang ORDER** menjawab lain. Di bracket produksi, BTC 1 jam adalah sel
terkuat sesi ini: t=+1,96 dan walk-forward 7 dari 8 di buffer 1,0. Itu tetap
belum lolos - aturannya 8 dari 8, dan Bonferroni atas 16 konfigurasi yang disapu
menuntut t 2,9 sementara yang terbaik 2,05 - tapi ia menempatkan BTC 1 jam di
atas apa pun yang XAU hasilkan. Verdict "BTC tidak bekerja" yang saya tulis lebih
awal berdasar harness TradingView, dan di bracket yang executor jalankan itu
tidak benar.

Konsekuensi praktisnya berbeda dari XAU. Untuk XAU yang membatasi adalah bukti;
untuk BTC yang membatasi adalah biaya, dan itu bisa berubah tanpa satu baris kode
pun: broker dengan komisi lebih rendah menggeser seluruh kolom terakhir tabel di
atas. Kalau biaya BTC pernah turun setengah, sel 4h layak diukur ulang sebelum
apa pun disimpulkan lagi.


## 15. LTF, dua instrumen, dua bracket, 7 September 2026

Ditanyakan karena perdagangannya kemungkinan di sana. Jawabannya berbeda
tergantung bracket, lagi - dan kali ini yang terbalik adalah XAUUSD 30m.

### Harness TradingView, target 1R, dengan biaya

| TF | XAU win% | XAU PF | XAU komisi | BTC win% | BTC PF | BTC komisi |
|---|---|---|---|---|---|---|
| 5m | 47,86 | 0,631 | **55,2%** | 40,24 | **0,384** | **108,4%** |
| 15m | 49,44 | 0,794 | 25,2% | 46,67 | 0,656 | 32,5% |
| 30m | 50,02 | 0,833 | 25,2% | 48,13 | 0,806 | 19,6% |
| 1h | 52,99 | 0,971 | 16,9% | 49,18 | 0,882 | 11,1% |
| 4h | **54,56** | **1,127** | 8,7% | 51,20 | 0,985 | 3,6% |

Monoton sempurna dan searah di kedua instrumen: turun timeframe, win rate turun
dan share komisi naik. BTCUSD 5 menit membayar **108,4 persen** laba kotornya
sebagai komisi - ongkosnya sendiri lebih besar daripada seluruh trade menang
digabung.

Biaya masuk ke dalam klasifikasi menang-kalah, jadi kedua kolom itu tidak
sepenuhnya independen: sebagian penurunan win rate ADALAH biayanya.

### Bracket produksi, dan ia tidak setuju

| sel | buffer | n | exp_r | t | PF | win% | walk-forward |
|---|---|---|---|---|---|---|---|
| **XAU 30m** | **0,25** | 1.443 | +0,0767 | +1,50 | 1,129 | 37,0 | **7 dari 8** |
| XAU 30m | 1,00 | 1.443 | +0,0455 | **+1,74** | 1,126 | 56,3 | 6 dari 8 |
| XAU 30m | 1,50 | 1.443 | +0,0127 | +0,61 | 1,042 | 60,6 | 3 dari 8 |
| XAU 15m | 1,00 | 593 | +0,0163 | +0,41 | 1,043 | 56,0 | 5 dari 8 |
| BTC 30m | 1,00 | 1.443 | +0,0071 | +0,29 | 1,019 | 56,3 | 4 dari 8 |
| **BTC 15m** | **0,25** | 593 | **-0,1936** | **-3,31** | 0,701 | 30,0 | 2 dari 8 |
| BTC 15m | 1,00 | 593 | -0,0844 | **-2,30** | 0,794 | 50,3 | 1 dari 8 |
| BTC 15m | 1,50 | 593 | -0,0667 | **-2,12** | 0,805 | 55,8 | 2 dari 8 |

**XAUUSD 30m di buffer ter-ship memberi 7 dari 8** - sama dengan BTC 1 jam, dan
lebih baik dari XAU 4 jam yang jadi dasar default Pine. TradingView memberi 0,833
untuk sel yang sama. Sebabnya sama dengan BTC 1 jam: bracket produksi memakai
target dari zona lawan, harness memakai 1R tetap.

Dan di buffer 1,0 sel itu memberi win rate 56,3 persen di PF yang praktis sama
(1,126 lawan 1,129). Jadi win rate di sana bisa dipilih hampir tanpa biaya.

**BTCUSD 15 menit terukur RUGI SIGNIFIKAN**, t = -3,31 di buffer ter-ship. Itu
melewati ambang Bonferroni untuk dua belas perbandingan (2,87) dengan arah yang
salah, dan negatif di ketiga lebar stop. Ini temuan kedua di repo ini yang
|t|-nya di atas 2 dan menunjuk ke rugi, setelah order_block.

### Batas sampel yang harus dibaca bersama tabel itu

Bar halus untuk 15 menit adalah 1 menit, dan riwayat 1 menit MT5 di mesin ini
pendek: XAUUSD mulai 2026-05-27, BTCUSD mulai 2026-06-29. Jadi seluruh baris 15
menit berdiri di atas tiga bulan dan dua bulan. n=593 yang kecil di sana adalah
tanda SAMPEL PENDEK, bukan tanda edge lemah, dan dua hal itu terbaca sama kalau
batasnya tidak ditulis.

### Peringkat seluruh sel bracket produksi yang pernah diukur

| sel | buffer | t | PF | wf |
|---|---|---|---|---|
| BTC 1h | 1,50 | +2,05 | 1,223 | 6 dari 8 |
| BTC 1h | 1,00 | +1,96 | 1,210 | 7 dari 8 |
| XAU 30m | 1,00 | +1,74 | 1,126 | 6 dari 8 |
| XAU 30m | 0,25 | +1,50 | 1,129 | 7 dari 8 |
| XAU 1h | 1,00 | +1,40 | 1,149 | 6 dari 8 |
| XAU 4h | 1,50 | +1,06 | 1,149 | 5 dari 8 |

Dua teratas BTC 1 jam dan XAU 30 menit - bukan XAU 4 jam, yang jadi dasar default
Pine karena ia yang terbaik DI HARNESS. Tidak satu pun mencapai 8 dari 8, dan
Bonferroni atas 28 konfigurasi yang kini sudah disapu menuntut t sekitar 3,1.

## 17. Harness dan produksi disamakan, 7 September 2026

Sampai hari ini harness TradingView mengukur trade yang TIDAK diperdagangkan
siapa pun. Tiga selisih ditemukan dan ditutup, berurutan, dan tiap satu memindah
angkanya.

### 17.1 Tiga selisih yang ditutup

| # | harness lama | produksi (`intrabar.resolved`) |
|---|---|---|
| 1 | target R tetap | target dari zona lawan (`profit_zone_at`) |
| 2 | dinding dipilih saat zona LAHIR | dipilih saat SENTUHAN, `time[touch]` |
| 3 | hanya zona lolos gerbang jadi dinding | SELURUH keluaran detektor jadi dinding |

Nomor 2 dan 3 satu keluarga: keduanya membuat kumpulan dinding terlalu kecil,
jadi dinding terdekat yang ditemukan terlalu jauh, jadi target terlalu jauh.
Terbaca di kolom RR: BTC 1 jam turun dari RR 3,50 ke 1,12 setelah keduanya
ditutup, dan win rate naik 42,7 ke 51,8 persen.

Jejaknya di BTCUSD 1 jam, buffer 1,0, biaya 0,01329 persen, jendela penuh:

| harness | PF |
|---|---|
| target R tetap (lama) | 0,882 |
| target zona lawan, dinding di kelahiran | 0,941 |
| target zona lawan, dinding di sentuhan, semua zona | **0,995** |

Untuk XAUUSD 30 menit angka lamanya direproduksi PERSIS - 0,833 di mode R tetap,
sama digit demi digit dengan yang tercatat di bagian sebelumnya - jadi yang
berubah memang aturan targetnya, bukan harness-nya yang bergeser diam-diam.

### 17.2 Yang TIDAK bisa ditiru, dan itu dinyatakan

`strategy.entry` mengunci qty saat order DIPASANG. Produksi menghitung qty dari
ATR di bar SENTUHAN (`scale_at="touch"`), yang belum ada saat limitnya dipasang.
Jadi harness ini setara `scale_at="birth"`. Sumbu itu diukur terpisah supaya
tidak jadi tersangka gelap, dan ia hampir tidak bergerak:

| sel | scale | PF | walk-forward |
|---|---|---|---|
| XAU 30m | touch | 1,126 | 6 dari 8 |
| XAU 30m | birth | 1,138 | 5 dari 8 |
| BTC 1h | touch | 1,207 | 6 dari 8 |
| BTC 1h | birth | 1,256 | 7 dari 8 |

### 17.3 Angka produksi terbaik repo ini adalah angka SATU TAHUN

Ini temuan terpenting hari ini dan ia bukan tentang detektor.

`intrabar.resolved` melewati setiap zona yang sentuhannya jatuh sebelum bar
halus pertama tersedia. Riwayat bar halus MT5 di mesin ini:

| simbol | 5m mulai | 15m mulai | 1h mulai |
|---|---|---|---|
| XAUUSD | 2025-04-08 | 2022-06-13 | 2016-08-09 |
| BTCUSD | **2025-09-24** | 2023-10-31 | 2018-03-27 |

Jadi **BTC 1 jam PF 1,210 diukur pada 2025-09-24 sampai 2026-09-07 saja**, n=695
- bukan 2,7 tahun. Itu tidak pernah tertulis di sebelah angkanya, dan angka itu
yang dipakai untuk menyebut BTC 1 jam sel terkuat di repo.

Diuji langsung: harness TradingView dipotong ke jendela yang sama.

| BTC 1h, bracket produksi | n | PF |
|---|---|---|
| TradingView, BITSTAMP, 2024-01 ke depan | 2.193 | 0,995 |
| TradingView, BITSTAMP, 2025-09-24 ke depan | 760 | 1,070 |
| Python, MT5, 2025-09-24 ke depan | 695 | 1,207 |

n cocok (760 lawan 695). Jendela menyumbang sekitar +0,075. Sisanya, sekitar
+0,137, adalah feed plus resolusi intrabar - TradingView memakai magnifier 1
menit, rig Python memakai 5 menit, dan resolusi lebih halus SELALU menurunkan
hasil karena bar yang memuat stop dan target sekaligus berhenti diselesaikan
dengan aturan urutan.

Bahwa jendela pendek bukan satu-satunya sebab juga diperiksa, dengan menurunkan
resolusi ke 15 menit supaya jendelanya bisa dipanjangkan. Baris 15m adalah BATAS
ATAS, bukan pengukuran:

| sel | resolusi | n | PF | rentang |
|---|---|---|---|---|
| XAU 30m | 5m | 1.443 | 1,126 | 2025-04 .. 2026-09 |
| XAU 30m | 15m | 4.264 | 1,158 | 2022-06 .. 2026-09 |
| BTC 1h | 5m | 695 | 1,207 | 2025-09 .. 2026-09 |
| BTC 1h | 15m | 2.024 | 1,132 | 2023-10 .. 2026-09 |

Edge-nya tidak hilang di jendela panjang. Yang hilang adalah klaim bahwa BTC 1
jam istimewa: di jendela panjang ia 1,132, di bawah XAU 30 menit yang 1,158.

### 17.4 Sel terbaik sekarang XAUUSD 4 jam, dan ia terukur di 13,7 tahun

Semua di bawah ini dari harness yang sudah disamakan: target zona lawan, dinding
di sentuhan, seluruh zona jadi dinding, magnifier 1 menit, biaya 0,0113 persen
per sisi, gerbang 0,25.

Frontier buffer stop, XAUUSD 4 jam, 2013-01 sampai 2026-09:

| buffer | n | win% | PF |
|---|---|---|---|
| 0,50 | 1.694 | 39,02 | 1,058 |
| **1,00** | 1.709 | **50,56** | **1,091** |
| 1,50 | 1.727 | 55,24 | 1,081 |

Datar di ketiganya, yang menenangkan - bukan puncak setipis pisau.

**Kontrol placebo lewat.** Kotak digeser 1 ATR, sisi dan tinggi dan umur sama:

| | n | win% | PF | exp_r |
|---|---|---|---|---|
| kotak asli | 1.709 | **50,56** | 1,091 | +0,0417 |
| kotak digeser | 1.694 | **38,72** | 1,014 | +0,0063 |

**11,8 poin win rate**, dan exp_r 6,6 kali lipat. Letak kotaknya yang bekerja.

**Hold-out tidak roboh, dan arahnya terbalik dari biasanya:**

| paruh | n | win% | PF |
|---|---|---|---|
| 2013-01 .. 2020-01 | 861 | 47,62 | 1,007 |
| 2020-01 .. 2026-09 | 848 | 53,42 | **1,179** |

Paruh KEDUA lebih baik. Kalau seleksi dilakukan di paruh pertama, yang ditemukan
hampir datar (1,007) dan luar-sampelnya justru lebih baik. Itu kebalikan dari
pola BTC, yang hidup di paruh sebelum 2021 lalu mati.

**Stabilitas delapan periode berurutan** (bukan walk-forward rig Python, yang
punya purging - ini versi kasar dan dilabeli begitu):

| periode | n | win% | PF |
|---|---|---|---|
| 2013-01 .. 2014-09 | 170 | 45,29 | 1,040 |
| 2014-09 .. 2016-06 | 197 | 51,78 | 1,160 |
| 2016-06 .. 2018-02 | 252 | 46,83 | **0,793** |
| 2018-02 .. 2019-11 | 229 | 47,16 | **0,921** |
| 2019-11 .. 2021-07 | 186 | 53,23 | 1,317 |
| 2021-07 .. 2023-04 | 219 | 52,51 | 1,030 |
| 2023-04 .. 2024-12 | 226 | 54,42 | 1,143 |
| 2024-12 .. 2026-09 | 229 | 53,28 | 1,111 |

**6 dari 8.** Dua yang gagal berdampingan, 2016 sampai 2019, jadi ini bukan
derau melainkan satu rezim yang panjangnya hampir tiga tahun.

### 17.5 Sel lain, harness yang sama

| sel | jendela | n | win% | PF |
|---|---|---|---|---|
| XAU 4h | 13,7 th | 1.709 | 50,56 | **1,091** |
| BTC 1h | 2,7 th | 2.193 | 46,79 | 0,995 |
| XAU 30m | 2,7 th | 2.964 | 45,07 | 0,906 |

Baris XAU 30 menit DIKOREKSI 7 September 2026. Angka pertama yang tercatat
di sini, 0,956 pada n=2.586, diukur di build SEBELUM dinding dipindah ke
waktu terisi - study di chart masih snapshot lama, persis jebakan yang
ditulis di bagian 17.7 dan tetap terinjak. Diukur ulang di build yang benar
ia 0,906 pada n=2.964.
| XAU 30m | 1,4 th | 1.599 | 45,53 | 0,934 |
| BTC 4h | 9,7 th | 1.539 | 47,95 | 0,900 |

BTC 4 jam TURUN dari 0,985 ke 0,900 begitu target zona lawan dipakai. Aturan
target yang menolong XAU merugikan BTC di 4 jam, dan itu asimetri yang sama
dengan yang tercatat di bagian 14 - masih belum dijelaskan.

### 17.6 Putusan

Gerbang GAMBAR yang dipesan - backtest TradingView, win rate baik, bukan rugi -
**dilewati oleh satu sel saja: XAUUSD 4 jam.** PF 1,091 pada 1.709 trade di 13,7
tahun, win 50,56 persen, biaya broker sudah masuk, magnifier menyala, placebo
kalah 11,8 poin win rate, dan hold-out paruh kedua lebih kuat dari paruh pertama.

Yang MENAHANNYA dari lolos penuh: stabilitas 6 dari 8, bukan 8 dari 8, dengan
kegagalan mengumpul di 2016 sampai 2019. Aturan repo ini 8 dari 8, jadi
`fvg.orderable` tetap mati.

Tidak ada sel BTC yang lewat, di aturan target mana pun.

### 17.7 Dua jebakan alat yang ditemukan hari ini

**`barstate.islast` bohong di strategy.** Dengan `calc_on_every_tick = false`
script hanya jalan di bar yang sudah TUTUP, jadi selama bar realtime berjalan
`islast` tidak pernah menyala dan tabel hasilnya TIDAK ADA - sampai 30 menit
sekali di timeframe 30 menit. Terbaca persis seperti script rusak. Compiler
mencetak peringatan ini di SETIAP kompilasi sejak 8:39 malam 6 September dan
peringatannya dilewati sampai tabelnya benar-benar hilang. Yang benar
`barstate.islastconfirmedhistory`.

**Dialog Strategy Properties kembali ke nol setiap TradingView restart.** Komisi
yang dipasang lewat dialog itu HILANG, dan run tanpa biaya terbaca persis seperti
run dengan biaya - tidak ada yang merah, cuma PF-nya naik. `commission_value`
tidak bisa dijadikan input (Pine menuntut const), jadi biaya sekarang dipotong di
dalam script dari `entry_price` kali `size`, dan besarnya dicetak di tabel
sebagai baris `biaya (R)` supaya run tanpa biaya kelihatan.

Aplikasinya juga rusak dua kali hari ini: setelah menyala lebih dari sehari, dan
setelah berpindah simbol dari BTC ke XAU, chart menampilkan "This symbol doesn't
exist" sementara header tetap menunjukkan harga hidup, dan skala harganya
tertinggal di rentang simbol sebelumnya. Satu-satunya obat yang bekerja restart
aplikasi, dan setelah restart study di chart kembali ke snapshot LAMA - jadi
setelah setiap restart study harus dibuang dan ditambahkan ulang dari editor,
kalau tidak yang diukur adalah kode kemarin.

## 19. Timeframe mana yang efektif, 7 September 2026

Sapuan penuh di harness yang sudah disamakan (bagian 17): target zona lawan
dipilih saat sentuhan, seluruh zona jadi calon dinding, gerbang 0,25, buffer
stop 1,0 ATR, magnifier 1 menit, biaya broker dipotong di dalam script.

### XAUUSD, biaya 0,0113 persen per sisi

| TF | rentang | n | win% | PF | biaya R/trade | placebo PF | placebo win% | margin win |
|---|---|---|---|---|---|---|---|---|
| 1d | 56 th | 597 | 51,42 | 1,112 | 0,0150 | 1,068 | 43,27 | +8,15 |
| **4h** | 13,7 th | 1.709 | **50,56** | **1,091** | 0,0417 | 1,014 | 38,72 | **+11,84** |
| 1h | 3,7 th | 1.847 | 48,29 | 1,006 | 0,0746 | 0,881 | 36,36 | **+11,93** |
| 30m | 2,7 th | 2.964 | 45,07 | 0,906 | 0,1010 | 0,818 | 36,35 | +8,72 |
| 15m | - | tidak terukur | | | | | | |

### BTCUSD, biaya 0,01329 persen per sisi

| TF | rentang | n | win% | PF | biaya R/trade | placebo PF |
|---|---|---|---|---|---|---|
| 1d | 15 th | 452 | 46,24 | 1,402 | 0,0057 | **1,468** |
| 4h | 9,7 th | 1.539 | 47,95 | 0,900 | 0,0165 | - |
| 1h | 2,7 th | 2.193 | 46,79 | 0,995 | 0,0459 | - |
| 30m | 1,7 th | 2.996 | 44,66 | 0,804 | 0,0772 | - |
| 15m | - | tidak terukur | | | | |

### Yang dibaca dari dua tabel itu

**Sinyal detektornya DATAR antara 1 jam dan 4 jam.** Margin atas placebo +11,93
poin win rate di 1 jam dan +11,84 poin di 4 jam - praktis sama. Yang berbeda
biayanya: 0,0746 R per trade di 1 jam lawan 0,0417 R di 4 jam. Jadi bukan
detektornya yang membaik di timeframe tinggi, melainkan biayanya yang mengecil.

Biaya per trade naik hampir tujuh kali lipat dari harian ke 30 menit (0,0150
sampai 0,0978 R), dan di situlah seluruh kurva PF-nya. Sebabnya struktural: R
disizing dari lebar stop, dan makin rendah timeframe makin sempit stopnya, jadi
makin besar notional yang dibutuhkan untuk risiko yang sama - sementara komisi
dihitung dari notional.

**Titik impasnya 1 jam.** Di bawah itu biaya mengalahkan edge; di 4 jam ke atas
edge-nya lewat.

**BTCUSD harian TIDAK dihitung sebagai temuan.** PF 1,402 terlihat tertinggi di
seluruh repo, tapi kotak yang digeser 1 ATR memberi **1,468** - kontrolnya
MENANG. Yang terukur di sana drift instrumen, bukan letak kotaknya. Tanpa
kontrol itu angka 1,402 akan tercatat sebagai sel terbaik yang pernah diukur.

**Sel yang efektif: XAUUSD 4 jam.** PF tertinggi bukan miliknya (harian 1,112),
tapi margin atas placebo miliknya, dan n-nya 1.709 lawan 597. XAUUSD harian
marginnya separuh lebih tipis (+8,15 poin) di sampel yang jauh lebih kecil.

**15 menit tidak bisa diukur di mesin ini.** Chart TradingView Desktop mati -
"This symbol doesn't exist" sementara header tetap menampilkan harga hidup -
setiap kali timeframe 15 menit dipilih, di FX:XAUUSD maupun BITSTAMP:BTCUSD, dan
tetap mati sampai aplikasinya di-restart. Dicoba empat kali, termasuk langsung
sesudah restart bersih. Pemicunya timeframe, bukan simbol. Angka 15 menit di
bagian-bagian sebelumnya berasal dari sesi lain dan TIDAK diukur ulang di
harness yang sudah disamakan.

## 21. Ambang gerbang diperiksa ulang, dan ia tidak membayar dirinya

`DEPARTURE_GATE_ATR_CEILING = 0.25` dikalibrasi dua kali di atas dasar yang
sekarang tidak berlaku: `replay_lifecycle` yang memeriksa pecah sebelum sentuh,
dan bracket harness yang bukan bracket produksi. Keduanya sudah diperbaiki dan
ambangnya TIDAK pernah dilihat lagi. Di sini ia dilihat lagi.

Semua di XAUUSD 4 jam, 2013-01 sampai 2026-09, buffer stop 1,0 ATR, biaya masuk.

### Sapuan penuh

| gerbang | n | win% | PF | exp_r |
|---|---|---|---|---|
| mati | 4.156 | 53,66 | 1,111 | +0,0420 |
| 0,10 | 749 | 48,06 | 1,013 | +0,0068 |
| 0,15 | 1.124 | 50,27 | **1,169** | **+0,0797** |
| **0,25 (ter-ship)** | 1.709 | 50,56 | 1,091 | +0,0417 |
| 0,50 | 2.733 | 50,79 | 1,072 | +0,0309 |

Perhatikan bahwa **gerbang MATI mengalahkan gerbang ter-ship**, 1,111 lawan
1,091, pada 2,4 kali jumlah trade. Perhatikan juga bahwa kurvanya tidak monoton:
0,10 turun ke 1,013 lalu 0,15 melompat ke 1,169. Bentuk seperti itu tanda derau,
bukan tanda ambang.

Antrean pending diperiksa sebagai tersangka - di gerbang mati `max_pending` 80
mengusir 54 order di lengan placebo. Dinaikkan ke 500 dan angkanya TIDAK bergerak
satu digit pun (n 4.156, PF 1,111), jadi pengusiran itu bukan sebabnya.

### Kontrol placebo di tiga ambang

| gerbang | asli PF | asli win% | placebo PF | placebo win% | margin win |
|---|---|---|---|---|---|
| mati | 1,111 | 53,66 | 1,013 | 46,61 | +7,05 |
| 0,15 | 1,169 | 50,27 | 0,951 | 36,17 | **+14,10** |
| 0,25 | 1,091 | 50,56 | 1,014 | 38,72 | +11,84 |

Margin ini TIDAK sebanding antar baris dan itu harus dikatakan: geseran placebo
selalu 1 ATR, sementara kotak yang lolos gerbang ketat jauh lebih kecil dari 1
ATR. Jadi lengan bergerbang mendapat geseran yang lebih keras dalam satuan tinggi
kotaknya sendiri. Baris ini membuktikan tiap lengan mengalahkan kontrolnya
sendiri; ia TIDAK membuktikan lengan mana yang menyortir lebih baik.

### Keputusan di bawah disiplin IS/OOS repo ini

Aturannya: pilih di paruh pertama, laporkan paruh kedua. Belah 2020-01-01.

| gerbang | IS 2013-2020 | OOS 2020-2026 | n OOS |
|---|---|---|---|
| **mati** | **1,052** | 1,158 | **2.053** |
| 0,15 | 0,991 | 1,354 | 581 |
| 0,25 | 1,007 | 1,179 | 848 |

Yang menang di paruh pertama adalah **gerbang MATI**, dan luar-sampelnya 1,158
pada 2.053 trade. Gerbang 0,15 yang terlihat terbaik di sampel penuh justru
TERBURUK di paruh pertama - ia adalah persis apa yang dibeli dengan memilih di
atas seluruh data.

**Kesimpulan: di XAUUSD 4 jam, gerbang keberangkatan tidak membayar dirinya.**
Ia membuang 59 persen populasi dan tidak menaikkan PF. Yang ia berikan bukan
hasil melainkan lebih sedikit kotak di layar, dan itu properti tampilan, bukan
temuan terukur.

Catatan lingkup: ini SATU sel dan SATU belahan. Sebelum `DEPARTURE_GATE_ATR_CEILING`
diubah, hal yang sama harus diulang di XAU 1 jam dan harian, dan idealnya dengan
walk-forward berpurging, bukan hold-out dua paruh. Sampai itu ada, 0,25
dipertahankan - bukan karena ia terbukti, tapi karena menggantinya juga belum.

## 23. Sisa daftar dituntaskan, 7 September 2026

Bagian 21 menyimpulkan gerbang tidak membayar dirinya, tapi itu diukur di SATU
sel. Di sini sisa daftarnya dikerjakan, dan hasil pertamanya membalik kesimpulan
bagian 21.

### 23.1 Gerbang membayar di 1 jam dan harian, TIDAK di 4 jam

| TF XAUUSD | gerbang mati | gerbang 0,25 |
|---|---|---|
| 1d | 1,027 (n 1.483) | **1,112** (n 597) |
| 4h | **1,111** (n 4.156) | 1,091 (n 1.709) |
| 1h | 0,902 (n 4.135) | **1,006** (n 1.847) |

Antrean pending diperiksa di kedua lengan (`max_pending` 80 dinaikkan ke 500 di
1 jam dan 4 jam) dan angkanya tidak bergerak satu digit pun.

**Dua dari tiga timeframe bilang gerbangnya membayar, jadi 4 jam yang
pengecualian - bukan aturannya.** `DEPARTURE_GATE_ATR_CEILING = 0.25`
DIPERTAHANKAN, dan sekarang atas dasar tiga sel, bukan atas dasar kalibrasi lama
yang dasarnya sudah tidak berlaku.

Bagian 21 tetap berdiri sebagai catatan bahwa di 4 jam gerbang itu membuang 59
persen populasi tanpa menaikkan PF. Yang berubah kesimpulan cabutnya, bukan
pengukurannya.

### 23.2 Sisa parameter: SEMUANYA datar

XAUUSD 4 jam, sampel penuh, satu knob digerakkan satu kali:

| knob | nilai | PF |
|---|---|---|
| `horizon` | 20 / **80** / 300 | 1,088 / **1,091** / 1,091 |
| `atr_period` | 7 / **14** / 50 | 1,080 / **1,091** / 1,097 |
| `filter_mother` | mati / **nyala** | 1,061 / **1,091** |
| `min_body_ratio` | 0,0 / **0,3** | 1,085 / **1,091** |
| `min_gap_atr` | **0,0** / 0,10 | **1,091** / 1,075 (n separuh) |
| `wall_memory` | 30 / **300** / 1000 | 1,079 / **1,091** / 1,091 |

`horizon` datar karena trade-nya selesai di stop atau target jauh sebelum 20 bar
- knob itu tidak pernah mengikat. `wall_memory` sudah JENUH di 300: naik ke 1000
memberi angka yang identik digit demi digit, jadi pendekatan yang dinyatakan di
header Pine tidak menggigit.

`filter_mother` dan `min_body_ratio` dulu dipertahankan atas dasar definisi dan
dinyatakan BUKAN sebagai edge. Sekarang keduanya punya angka: yang pertama
+0,030 PF, yang kedua +0,006 pada 142 trade lebih sedikit. Dasar definisinya
tetap yang berlaku; angkanya tidak membantah dan tidak mendukung.

**Yang menggerakkan hasil cuma dua: ambang gerbang dan lebar stop.** Keduanya
sudah disapu. Tidak ada knob ketiga yang tersisa.

### 23.3 Walk-forward BERPURGING, dan ia tetap 6 dari 8

Bagian 17.4 memakai delapan periode berurutan tanpa purging dan dilabeli begitu.
Di sini tiap periode dipendekkan 80 bar (13,3 hari di 4 jam) di ujungnya, jadi
zona yang lahir di jendela itu tidak bisa keluar di periode berikutnya.

| periode | n | win% | PF berpurging | PF tanpa purging |
|---|---|---|---|---|
| 2013-01 .. 2014-09 | 167 | 44,91 | 1,039 | 1,040 |
| 2014-09 .. 2016-05 | 193 | 51,30 | 1,150 | 1,160 |
| 2016-06 .. 2018-02 | 246 | 47,56 | **0,802** | 0,793 |
| 2018-02 .. 2019-10 | 225 | 46,67 | **0,908** | 0,921 |
| 2019-11 .. 2021-07 | 182 | 53,85 | 1,349 | 1,317 |
| 2021-07 .. 2023-03 | 216 | 53,24 | 1,092 | 1,030 |
| 2023-04 .. 2024-12 | 221 | 54,30 | 1,149 | 1,143 |
| 2024-12 .. 2026-08 | 225 | 52,89 | 1,085 | 1,111 |

Tetap **6 dari 8**, dan dua yang gagal tetap yang sama. Purging tidak menolong
dan tidak melukai; aturan 8 dari 8 memang tidak terpenuhi.

### 23.4 Rezim 2016-2019 BUKAN kegagalan detektor

Dua periode yang gagal digabung (2016-06 sampai 2019-11) dan diberi kontrolnya:

| | n | win% | PF |
|---|---|---|---|
| kotak asli | 482 | **46,89** | 0,875 |
| kotak digeser 1 ATR | 470 | **34,47** | 0,811 |

Marginnya **+12,4 poin win rate**, sama besar dengan margin di sampel penuh
(+11,8). Detektornya menyortir persis sebaik biasanya sepanjang tiga tahun itu;
yang terjadi seluruh populasinya rugi, asli maupun digeser.

Itu mengubah cara 6 dari 8 harus dibaca. Bukan "detektornya rusak dua kali",
melainkan "perilaku emas 4 jam tidak menguntungkan selama tiga tahun dan tidak
ada letak kotak yang bisa menyelamatkannya".

### 23.5 Kontrol placebo untuk sel BTCUSD

| sel | asli PF | asli win% | placebo PF | placebo win% | putusan |
|---|---|---|---|---|---|
| BTC 1h | **0,995** | 46,79 | 0,890 | 37,04 | menyortir, tapi impas |
| BTC 4h | 0,900 | 47,95 | **0,948** | 36,42 | KONTROL MENANG |
| BTC 1d | 1,402 | 46,24 | **1,468** | 42,86 | KONTROL MENANG |

BTC 4 jam layak dilihat dua kali: kotak aslinya menang **11,5 poin win rate** dan
tetap KALAH di PF. Hit rate naik sementara ukuran menang-kalahnya memburuk lebih
cepat. Satu-satunya sel BTC yang menyortir sampai ke garis bawah adalah 1 jam,
dan di sana biaya menahannya persis di titik impas.

### 23.6 XAU 30 menit, dan satu angka basi yang ikut ketahuan

| | n | win% | PF |
|---|---|---|---|
| kotak asli | 2.964 | **45,07** | 0,906 |
| kotak digeser 1 ATR | 2.930 | **36,35** | 0,818 |

Menyortir +8,72 poin win rate dan tetap rugi - biayanya 0,1010 R per trade, yang
tertinggi dari seluruh sel yang diukur.

Angka asli 0,906 ini juga MENGOREKSI yang tercatat sebelumnya. Bagian 17.5 dan
19 sempat memuat 0,956 pada n=2.586, dan itu diukur di build sebelum dinding
dipindah ke waktu terisi: study di chart masih snapshot lama sesudah restart.
Jebakan itu ditulis sendiri di bagian 17.7 dan tetap terinjak. Setiap angka lain
di bagian 17, 19 dan 21 sudah diperiksa terhadap `no wall` dan `fill` di
tabelnya masing-masing dan semuanya dari build yang benar.

### 23.7 Keadaan akhir

Seluruh knob sudah disapu, seluruh sel yang bisa diukur sudah punya kontrolnya,
walk-forward sudah berpurging, dan rezim yang menahan sel terbaik sudah
dijelaskan. Yang tersisa satu lubang alat, bukan lubang analisis: timeframe 15
menit tidak bisa diukur karena TradingView Desktop mati setiap kali TF itu
dipilih.

Maksimum yang terukur untuk FVG di repo ini: **XAUUSD 4 jam, PF 1,091, 1.709
trade, 13,7 tahun, walk-forward berpurging 6 dari 8.** Aturan proyek 8 dari 8,
jadi `fvg.orderable` tetap mati - dan sekarang itu keputusan yang berdiri di
atas sapuan lengkap, bukan di atas satu sel yang belum diperiksa.

## 24. Yang belum dikerjakan

Daftar ini dipangkas 7 September 2026. Yang dicoret sudah dikerjakan di bagian
23: walk-forward berpurging untuk XAUUSD 4 jam, sapuan gerbang di 1 jam dan
harian, sapuan `atr_period` / `min_gap_atr` / `horizon` / `filter_mother` /
`min_body_ratio`, sensitivitas `wall_memory`, kontrol placebo untuk XAUUSD 30
menit dan seluruh sel BTCUSD, dan penjelasan rezim 2016-2019.

Yang benar-benar tersisa:

- **15 menit, dua instrumen.** Nol pengukuran di aturan target yang benar. Chart
  TradingView Desktop mati setiap kali timeframe itu dipilih - "This symbol
  doesn't exist" sementara header tetap menampilkan harga hidup - di FX:XAUUSD
  maupun BITSTAMP:BTCUSD, empat kali dicoba termasuk langsung sesudah restart
  bersih. Ini lubang ALAT, bukan lubang analisis, dan ia tidak bisa ditutup dari
  sisi Zonelab.
- **`supply_demand`, `order_block`, `ifvg` dan `breaker` belum diukur ulang.**
  Keempatnya memakai `replay_lifecycle` yang sama yang urutannya baru diperbaiki,
  jadi setiap angka gerbangnya bergerak dengan arah yang sama - dan ketiga
  selisih harness di bagian 17 juga berlaku untuk mereka.
- **Kenapa target zona lawan menolong XAU dan merugikan BTC di 4 jam.** Sudah
  tiga kali terukur (bagian 14, 17.5, dan kontrol placebo di 23.5 yang
  menunjukkan kotak BTC 4 jam menang 11,5 poin win rate lalu kalah di PF), belum
  sekali pun dijelaskan. Dugaan yang belum diuji: distribusi ukuran menang-kalah
  BTC berekor jauh lebih berat, jadi target dekat memotong ekor yang membayar.
- **BTCUSD butuh sapuan sendiri kalau ia harus diperdagangkan lewat layer ini.**
  Konfigurasi XAU yang dipinjam tidak bekerja di satu pun timeframe, dan
  paruh-pertamanya sendiri belum pernah dipakai untuk memilih apa pun.
- **`tools/calibrate.py:431`**, `first_touch` untuk lengan placebo tidak punya
  pemeriksaan pecah. Ia tidak perlu punya, tapi sebelum perbaikan 6 September
  2026 artinya lengan drawn dan lengan placebo dinilai dengan dua aturan entry
  berbeda. Setiap perbandingan placebo yang lebih tua dari tanggal itu harus
  dibaca dengan ini di kepala.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).
